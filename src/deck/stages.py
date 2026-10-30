"""流水线阶段：init → outline → compose → render → check。"""

from __future__ import annotations

import contextvars
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import checks, mock, render, workspace
from .errors import ProviderError, StageError
from .model import deck_summary, normalize_brief, validate_deck, validate_outline
from .providers import Message, Provider, parse_json
from .theme import Theme, load_theme

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
_TRACE: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def new_trace() -> str:
    """一次请求一个 trace_id，串起同一 deck 的多个阶段日志。"""
    trace = uuid.uuid4().hex[:12]
    _TRACE.set(trace)
    return trace


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _prompt(name: str) -> str:
    path = PROMPTS / name
    if not path.exists():
        raise StageError("MISSING_PROMPT", f"找不到提示词: {name}", "检查 prompts/ 目录")
    return path.read_text(encoding="utf-8")


def _fill(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def _log(root: Path, slug: str, stage: str, started: float, provider: Provider | None, extra: dict[str, Any] | None = None) -> None:
    event = {
        "ts": _now(),
        "trace_id": _TRACE.get() or uuid.uuid4().hex[:12],
        "stage": stage,
        "ms": round((time.perf_counter() - started) * 1000),
    }
    if provider is not None:
        event["provider"] = provider.name
        event["usage"] = dict(provider.usage)
    if extra:
        event.update(extra)
    workspace.log_event(root, slug, event)


def _result(
    stage: str,
    slug: str,
    *,
    artifacts: list[Path] | None = None,
    result: dict[str, Any] | None = None,
    findings: list[dict[str, str]] | None = None,
    next_stage: str | None = None,
    gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "stage": stage,
        "slug": slug,
        "artifacts": [str(path) for path in artifacts or []],
        "result": result or {},
        "findings": findings or [],
        "gate": gate or {"passed": True, "errors": 0, "warnings": 0, "reasons": []},
        "next": next_stage,
    }


def _qa_gate(report: dict[str, Any]) -> dict[str, Any]:
    reasons = [item["code"] for item in report["findings"] if item["level"] == "error"]
    return {
        "passed": report["ok"],
        "errors": report["errors"],
        "warnings": report["warnings"],
        "reasons": reasons[:8],
    }


def load_brief(root: Path, slug: str) -> dict[str, Any]:
    return workspace.load_json(workspace.paths(root, slug)["brief"])


def run_init(root: Path, slug: str, raw_brief: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    brief = normalize_brief(raw_brief)
    workspace.create(root, slug, brief, force=force)
    _log(root, slug, "init", started, None)
    return _result(
        "init",
        slug,
        artifacts=[workspace.paths(root, slug)["brief"]],
        result={"brief": brief},
        next_stage="outline",
    )


def _generate_outline(provider: Provider, brief: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if provider.name == "mock":
        outline, fixes = validate_outline(mock.build_outline(brief), brief)
        return outline, fixes

    system = _prompt("system.md")
    prompt = _fill(_prompt("outline.md"), BRIEF=json.dumps(brief, ensure_ascii=False, indent=2))
    last: Exception | None = None
    for attempt in range(2):
        try:
            text = provider.complete(
                [Message("system", system), Message("user", prompt)], temperature=0.4, max_tokens=4000
            )
            return validate_outline(parse_json(text), brief)
        except (StageError, ProviderError) as exc:
            last = exc
            prompt += (
                f"\n\n上一次输出不合格（{getattr(exc, 'code', 'ERROR')}: {getattr(exc, 'message', str(exc))}）。"
                "请修正后只输出一个 JSON 对象。"
            )
    raise last or StageError("OUTLINE_FAILED", "大纲生成失败", "重试或换模型")


def run_outline(root: Path, slug: str, provider: Provider) -> dict[str, Any]:
    started = time.perf_counter()
    brief = load_brief(root, slug)
    outline, fixes = _generate_outline(provider, brief)
    path = workspace.paths(root, slug)["outline"]
    workspace.save_json(path, outline)
    _log(root, slug, "outline", started, provider, {"slides": len(outline["slides"]), "fixes": fixes})
    return _result(
        "outline",
        slug,
        artifacts=[path],
        result={
            "title": outline["title"],
            "slide_count": len(outline["slides"]),
            "layouts": [slide["layout"] for slide in outline["slides"]],
            "fixes": fixes,
        },
        next_stage="compose",
    )


def _generate_deck(provider: Provider, brief: dict[str, Any], outline: dict[str, Any]) -> dict[str, Any]:
    if provider.name == "mock":
        return mock.compose_deck(brief, outline)

    system = _prompt("system.md")
    prompt = _fill(
        _prompt("compose.md"),
        BRIEF=json.dumps(brief, ensure_ascii=False, indent=2),
        OUTLINE=json.dumps(outline, ensure_ascii=False, indent=2),
    )
    last: Exception | None = None
    for attempt in range(2):
        try:
            text = provider.complete(
                [Message("system", system), Message("user", prompt)], temperature=0.45, max_tokens=7000
            )
            data = parse_json(text)
            data.setdefault("meta", {})
            data["meta"].update(
                {
                    "title": data["meta"].get("title") or brief["topic"],
                    "audience": data["meta"].get("audience") or brief.get("audience", ""),
                    "presenter": data["meta"].get("presenter") or brief.get("presenter", ""),
                    "date": data["meta"].get("date") or brief.get("date", ""),
                    "language": brief["language"],
                    "theme": data["meta"].get("theme") or brief.get("theme", "swiss"),
                    "provider": provider.name,
                }
            )
            return validate_deck(data, brief)
        except (StageError, ProviderError) as exc:
            last = exc
            prompt += (
                f"\n\n上一次输出不合格（{getattr(exc, 'code', 'ERROR')}: {getattr(exc, 'message', str(exc))}）。"
                "请修正后只输出一个 JSON 对象。"
            )
    raise last or StageError("COMPOSE_FAILED", "成稿失败", "重试或换模型")


def run_compose(root: Path, slug: str, provider: Provider) -> dict[str, Any]:
    started = time.perf_counter()
    brief = load_brief(root, slug)
    outline = workspace.load_json(workspace.paths(root, slug)["outline"])
    deck = _generate_deck(provider, brief, outline)
    deck = validate_deck(deck, brief)
    deck["meta"]["generated_at"] = _now()
    deck["meta"]["provider"] = provider.name
    path = workspace.paths(root, slug)["deck"]
    workspace.save_json(path, deck)
    _log(root, slug, "compose", started, provider, {"slides": len(deck["slides"])})
    return _result(
        "compose",
        slug,
        artifacts=[path],
        result={"deck": deck_summary(deck), "notes_ratio": checks_notes_ratio(deck)},
        next_stage="render",
    )


def checks_notes_ratio(deck: dict[str, Any]) -> float:
    slides = deck.get("slides") or []
    return round(sum(1 for slide in slides if slide.get("notes")) / max(len(slides), 1), 2)


def _theme_for(deck: dict[str, Any], override: str | None) -> Theme:
    return load_theme(override or deck.get("meta", {}).get("theme") or "swiss")


def run_render(root: Path, slug: str, *, theme_name: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    paths = workspace.paths(root, slug)
    deck = validate_deck(workspace.load_json(paths["deck"]))
    theme = _theme_for(deck, theme_name)
    deck["meta"]["theme"] = theme.name

    pptx = render.render_pptx(deck, theme, paths["pptx"])
    html = render.render_html(deck, theme, paths["html"])
    markdown = render.render_markdown(deck, paths["markdown"])
    report = checks.qa(deck, theme)
    workspace.save_json(paths["deck"], deck)
    workspace.save_json(paths["qa"], report)
    _log(root, slug, "render", started, None, {"slides": pptx["slides"], "qa_ok": report["ok"]})

    return _result(
        "render",
        slug,
        artifacts=[paths["pptx"], paths["html"], paths["markdown"], paths["qa"]],
        result={
            "deck": deck_summary(deck),
            "pptx": {
                "slides": pptx["slides"],
                "bytes": pptx["bytes"],
                "notes_count": pptx["notes_count"],
                "titles": pptx["titles"],
            },
            "html": html,
            "markdown": markdown,
            "qa": {"ok": report["ok"], "score": report["score"], "errors": report["errors"], "warnings": report["warnings"]},
        },
        findings=report["findings"],
        next_stage="check",
        gate=_qa_gate(report),
    )


def run_check(root: Path, slug: str, *, theme_name: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    paths = workspace.paths(root, slug)
    deck = validate_deck(workspace.load_json(paths["deck"]))
    theme = _theme_for(deck, theme_name)
    report = checks.qa(deck, theme)
    workspace.save_json(paths["qa"], report)
    _log(root, slug, "check", started, None, {"qa_ok": report["ok"], "score": report["score"]})
    return _result(
        "check",
        slug,
        artifacts=[paths["qa"]],
        result={"qa": report, "stats": report["stats"]},
        findings=report["findings"],
        next_stage=None,
        gate=_qa_gate(report),
    )


def run_status(root: Path, slug: str) -> dict[str, Any]:
    paths = workspace.paths(root, slug)
    if not paths["brief"].exists():
        raise StageError("DECK_NOT_FOUND", f"找不到 deck: {slug}", "先运行 init")
    brief = workspace.load_json(paths["brief"])
    board = [
        {"stage": "init", "done": True, "artifact": str(paths["brief"])},
        {"stage": "outline", "done": paths["outline"].exists(), "artifact": str(paths["outline"])},
        {"stage": "compose", "done": paths["deck"].exists(), "artifact": str(paths["deck"])},
        {"stage": "render", "done": paths["pptx"].exists(), "artifact": str(paths["pptx"])},
        {"stage": "check", "done": paths["qa"].exists(), "artifact": str(paths["qa"])},
    ]
    next_stage = next((item["stage"] for item in board if not item["done"]), None)
    return _result(
        "status",
        slug,
        result={"title": brief["topic"], "slide_count": brief["slide_count"], "board": board},
        next_stage=next_stage,
    )


def run_pipeline(
    root: Path,
    slug: str,
    provider: Provider,
    *,
    raw_brief: dict[str, Any] | None = None,
    force: bool = False,
    theme_name: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    paths = workspace.paths(root, slug)
    steps: list[dict[str, Any]] = []

    if not paths["brief"].exists():
        if not raw_brief:
            raise StageError("DECK_NOT_FOUND", f"找不到 deck: {slug}", "先运行 init，或传 --brief")
        run_init(root, slug, raw_brief, force=force)

    outline = run_outline(root, slug, provider)
    steps.append({"stage": "outline", "passed": outline["gate"]["passed"], "errors": outline["gate"]["errors"]})
    deck = run_compose(root, slug, provider)
    steps.append({"stage": "compose", "passed": deck["gate"]["passed"], "errors": deck["gate"]["errors"]})
    rendered = run_render(root, slug, theme_name=theme_name)
    steps.append({"stage": "render", "passed": rendered["gate"]["passed"], "errors": rendered["gate"]["errors"]})
    checked = run_check(root, slug, theme_name=theme_name)
    steps.append({"stage": "check", "passed": checked["gate"]["passed"], "errors": checked["gate"]["errors"]})
    _log(root, slug, "pipeline", started, provider, {"ms_total": round((time.perf_counter() - started) * 1000)})

    return _result(
        "pipeline",
        slug,
        artifacts=[Path(path) for path in rendered["artifacts"]],
        result={
            "deck": rendered["result"]["deck"],
            "pptx": rendered["result"]["pptx"],
            "qa": checked["result"]["qa"],
            "steps": steps,
        },
        findings=checked["findings"],
        next_stage=None,
        gate=checked["gate"],
    )


def inspect_pptx(path: Path) -> dict[str, Any]:
    if not Path(path).exists():
        raise StageError("FILE_NOT_FOUND", f"找不到文件: {path}", "确认路径")
    try:
        info = render.verify_pptx(Path(path))
    except Exception as exc:  # pptx 损坏或不是 zip 包
        raise StageError("INVALID_PPTX", f"无法读取 PPTX: {exc}", "确认文件是有效的 .pptx") from exc
    return {"ok": True, "stage": "inspect", "result": info}
