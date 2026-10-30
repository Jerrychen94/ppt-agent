"""命令行入口：init / outline / compose / render / check / pipeline / status / inspect / eval。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import providers, stages, workspace
from .errors import AgentError
from .providers import MockProvider

STAGE_HELP = """
工作流：
  1. init      写 brief（主题、受众、页数、主题色）
  2. outline   生成页面骨架（版式 + 标题 + 要点）
  3. compose   填成稿（要点、数据、讲稿备注）
  4. render    输出 PPTX / HTML 预览 / Markdown 讲稿
  5. check     质检（溢出、密度、讲稿、一致性），有阻断项则退出码 1

一条命令跑完：ppipeline
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ppt",
        description="从主题或资料生成可编辑 PPTX 的 agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=STAGE_HELP,
    )
    parser.add_argument("--root", default=".", help="工作区根目录（deck 放在 <root>/decks/<slug>）")
    parser.add_argument("--slug", help="deck 标识；只有一个 deck 时可省略")
    parser.add_argument("--provider", choices=["mock", "openai"], help="模型提供方；默认读环境变量")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=argparse.SUPPRESS)
    common.add_argument("--slug", default=argparse.SUPPRESS)
    common.add_argument("--provider", choices=["mock", "openai"], default=argparse.SUPPRESS)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    common.add_argument("--theme", help="覆盖主题：swiss / ocean / warm / ink 或主题 JSON 路径")

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", parents=[common], help="建立 deck 与 brief")
    p_init.add_argument("--topic", help="主题（必填，除非用 --brief）")
    p_init.add_argument("--brief", help="从 JSON 文件读完整 brief")
    p_init.add_argument("--slides", type=int, default=10, help="页数（3–30）")
    p_init.add_argument("--audience", default="", help="受众")
    p_init.add_argument("--goal", default="", help="汇报目标（一句话）")
    p_init.add_argument("--presenter", default="", help="讲者")
    p_init.add_argument("--date", default="", help="日期")
    p_init.add_argument("--lang", choices=["zh", "en"], default="zh")
    p_init.add_argument("--points", default="", help="要点，用分号分隔")
    p_init.add_argument("--force", action="store_true", help="覆盖已有 deck")

    sub.add_parser("outline", parents=[common], help="生成大纲")
    sub.add_parser("compose", parents=[common], help="填充成稿")
    sub.add_parser("render", parents=[common], help="渲染 PPTX / HTML / Markdown")
    sub.add_parser("check", parents=[common], help="质检（阻断项退出码 1）")
    sub.add_parser("status", parents=[common], help="查看进度")
    p_pipe = sub.add_parser("pipeline", parents=[common], help="一次跑完 outline→check")
    p_pipe.add_argument("--brief", help="从 JSON 文件读完整 brief（deck 不存在时使用）")
    p_pipe.add_argument("--force", action="store_true")

    p_inspect = sub.add_parser("inspect", parents=[common], help="回读 PPTX 结构与文本")
    p_inspect.add_argument("path", help="pptx 路径")

    sub.add_parser("eval", parents=[common], help="评测入口：stdin 读 JSON 请求")

    return parser


def _deck_slug(args: argparse.Namespace) -> str:
    if getattr(args, "slug", None):
        return args.slug
    names = workspace.list_decks(Path(args.root))
    if len(names) == 1:
        return names[0]
    if not names:
        raise AgentError("DECK_NOT_FOUND", "工作区没有 deck", "先运行 init --topic ...")
    raise AgentError("AMBIGUOUS_SLUG", f"有多个 deck，请用 --slug 指定: {', '.join(names)}", "例如 --slug demo")


def _provider(args: argparse.Namespace) -> providers.Provider:
    return providers.from_env(getattr(args, "provider", None))


def _brief_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "brief", None):
        path = Path(args.brief).expanduser()
        if not path.is_file():
            raise AgentError("BRIEF_NOT_FOUND", f"找不到 brief 文件: {path}", "检查路径")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AgentError("INVALID_JSON", f"brief 不是合法 JSON: {exc}", "检查 JSON 格式") from exc
    if not getattr(args, "topic", None):
        raise AgentError("MISSING_TOPIC", "缺少 --topic", "传入 --topic 或 --brief")
    data: dict[str, Any] = {
        "topic": args.topic,
        "audience": args.audience,
        "goal": args.goal,
        "presenter": args.presenter,
        "date": args.date,
        "language": args.lang,
        "slide_count": args.slides,
        "theme": getattr(args, "theme", "swiss") or "swiss",
    }
    points = [part.strip() for part in (args.points or "").split(";") if part.strip()]
    if points:
        data["key_points"] = points
    return data


def _print_findings(findings: list[dict[str, str]], limit: int = 12) -> None:
    for item in findings[:limit]:
        label = "阻断" if item["level"] == "error" else "提醒"
        slide = f" {item['slide']}" if item.get("slide") else ""
        print(f"  [{label}] {item['code']}{slide}: {item['message']}")
        if item.get("hint"):
            print(f"         建议：{item['hint']}")
    if len(findings) > limit:
        print(f"  … 还有 {len(findings) - limit} 条")


def _print_human(payload: dict[str, Any]) -> None:
    stage = payload.get("stage")
    result = payload.get("result") or {}
    artifacts = payload.get("artifacts") or []
    if stage == "init":
        brief = result.get("brief", {})
        print(f"已建立 deck：{payload['slug']}（{brief.get('slide_count')} 页，主题 {brief.get('theme')}）")
        print(f"  brief: {artifacts[0] if artifacts else ''}")
    elif stage == "outline":
        print(f"大纲：{result.get('slide_count')} 页")
        print("  版式：" + " → ".join(result.get("layouts") or []))
        if result.get("fixes"):
            print("  自动修复：" + "、".join(result["fixes"]))
    elif stage == "compose":
        deck = result.get("deck", {})
        print(f"成稿：{deck.get('slide_count')} 页，讲稿覆盖 {result.get('notes_ratio', 0):.0%}")
    elif stage == "render":
        pptx = result.get("pptx", {})
        qa = result.get("qa", {})
        print(f"已渲染：{pptx.get('slides')} 页，{pptx.get('bytes', 0) / 1024:.0f} KB")
        for path in artifacts:
            print(f"  - {path}")
        print(f"质检：{'通过' if qa.get('ok') else '未通过'}（阻断 {qa.get('errors')}，提醒 {qa.get('warnings')}）")
    elif stage == "check":
        qa = result.get("qa", {})
        print(f"质检得分：{qa.get('score')}，阻断 {qa.get('errors')}，提醒 {qa.get('warnings')}")
    elif stage == "pipeline":
        qa = result.get("qa", {})
        pptx = result.get("pptx", {})
        print(f"完成：{pptx.get('slides')} 页，质检 {'通过' if qa.get('ok') else '未通过'}，得分 {qa.get('score')}")
        print("  " + " → ".join(step["stage"] for step in result.get("steps", [])))
    elif stage == "status":
        print(f"deck：{result.get('title')}（{payload['slug']}）")
        for item in result.get("board", []):
            print(f"  {'✔' if item['done'] else '–'} {item['stage']}")
        if payload.get("next"):
            print(f"下一步：{payload['next']}")
    elif stage == "inspect":
        data = result
        print(f"PPTX：{data.get('slides')} 页，{data.get('bytes', 0) / 1024:.0f} KB，含讲稿 {data.get('notes_count')} 页")
        for item in data.get("details", [])[:5]:
            print(f"  {item['index']:02d}. {(item['texts'][0] if item['texts'] else '')[:40]}")
    findings = payload.get("findings") or []
    if findings:
        _print_findings(findings)


def _emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human(payload)


def run_command(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    command = args.command

    if command == "eval":
        raise AgentError("INTERNAL", "eval 由 cmd_eval 处理", "")

    if command == "inspect":
        return stages.inspect_pptx(Path(args.path).expanduser())

    if command == "init":
        brief = _brief_from_args(args)
        slug = args.slug or workspace.slugify(brief.get("topic", "deck"))
        return stages.run_init(root, slug, brief, force=args.force)

    if command == "pipeline":
        raw_brief = None
        if getattr(args, "brief", None):
            path = Path(args.brief).expanduser()
            if not path.is_file():
                raise AgentError("BRIEF_NOT_FOUND", f"找不到 brief 文件: {path}", "检查路径")
            try:
                raw_brief = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise AgentError("INVALID_JSON", f"brief 不是合法 JSON: {exc}", "检查 JSON 格式") from exc
        slug = args.slug or (workspace.slugify(raw_brief.get("topic", "deck")) if raw_brief else _deck_slug(args))
        if not workspace.exists(root, slug) and not raw_brief:
            raise AgentError("DECK_NOT_FOUND", f"找不到 deck: {slug}", "先 init，或用 --brief 指定完整需求")
        return stages.run_pipeline(
            root,
            slug,
            _provider(args),
            raw_brief=raw_brief,
            force=getattr(args, "force", False),
            theme_name=getattr(args, "theme", None),
        )

    slug = _deck_slug(args)
    if command == "status":
        return stages.run_status(root, slug)
    if command == "outline":
        return stages.run_outline(root, slug, _provider(args))
    if command == "compose":
        return stages.run_compose(root, slug, _provider(args))
    if command == "render":
        return stages.run_render(root, slug, theme_name=getattr(args, "theme", None))
    if command == "check":
        return stages.run_check(root, slug, theme_name=getattr(args, "theme", None))
    raise AgentError("UNKNOWN_COMMAND", f"未知命令: {command}", "")


# ---------------------------------------------------------------- eval


def _eval_request(request: dict[str, Any]) -> dict[str, Any]:
    for pre in request.get("pre") or []:
        _eval_request(pre)
    root = Path(request.get("root") or "tmp/evals").expanduser().resolve()
    slug = request.get("slug") or "eval-deck"
    command = request["cmd"]
    provider = MockProvider() if request.get("provider", "mock") == "mock" else providers.from_env("openai")
    theme_name = request.get("theme")
    force = request.get("force", True)

    if command == "init":
        return stages.run_init(root, slug, request.get("brief") or {}, force=force)

    if command == "pipeline":
        if "brief" not in request:
            raise AgentError("INVALID_REQUEST", "pipeline 需要 brief", "传入 brief 对象")
        return stages.run_pipeline(root, slug, provider, raw_brief=request["brief"], force=force, theme_name=theme_name)

    if command in ("outline", "compose"):
        if not workspace.exists(root, slug):
            if "brief" not in request:
                raise AgentError("DECK_NOT_FOUND", f"找不到 deck: {slug}", "先 init 或传 brief")
            stages.run_init(root, slug, request["brief"], force=True)
        if command == "outline":
            return stages.run_outline(root, slug, provider)
        return stages.run_compose(root, slug, provider)

    if command in ("render", "check"):
        deck = request.get("deck")
        paths = workspace.paths(root, slug)
        if deck is not None:
            paths["dir"].mkdir(parents=True, exist_ok=True)
            workspace.save_json(paths["deck"], deck)
        if not paths["deck"].exists():
            raise AgentError("MISSING_FILE", "找不到 deck.json", "先 compose 或传 deck")
        if command == "render":
            return stages.run_render(root, slug, theme_name=theme_name)
        return stages.run_check(root, slug, theme_name=theme_name)

    if command == "status":
        return stages.run_status(root, slug)

    if command == "inspect":
        return stages.inspect_pptx(Path(request["path"]))

    raise AgentError("UNKNOWN_COMMAND", f"eval 不支持的命令: {command}", "")


def cmd_eval() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": {"code": "INVALID_REQUEST", "message": str(exc)}}, ensure_ascii=False))
        return 1
    if not isinstance(request, dict) or "cmd" not in request:
        print(
            json.dumps(
                {"ok": False, "error": {"code": "INVALID_REQUEST", "message": "缺少 cmd"}}, ensure_ascii=False
            )
        )
        return 1
    try:
        stages.new_trace()
        payload = _eval_request(request)
    except AgentError as exc:
        print(json.dumps({"ok": False, "error": exc.as_dict()}, ensure_ascii=False))
        return 1
    except (OSError, ValueError, KeyError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": {"code": "INTERNAL", "message": str(exc)}}, ensure_ascii=False
            )
        )
        return 1

    payload["ok"] = bool(payload.get("gate", {}).get("passed", True))
    print(json.dumps(payload, ensure_ascii=False))
    if request["cmd"] in ("check", "pipeline") and not payload["ok"]:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "eval":
        return cmd_eval()

    try:
        stages.new_trace()
        payload = run_command(args)
    except AgentError as exc:
        error = exc.as_dict()
        if args.json:
            print(json.dumps({"ok": False, "error": error}, ensure_ascii=False))
        else:
            print(f"错误：{error['code']} - {error['message']}", file=sys.stderr)
            if error.get("hint"):
                print(f"提示：{error['hint']}", file=sys.stderr)
        return 1

    _emit(payload, args.json)
    if args.command in ("check", "pipeline") and not payload["gate"]["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
