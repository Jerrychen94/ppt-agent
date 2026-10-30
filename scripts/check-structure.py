#!/usr/bin/env python3
"""结构自检：检查一个 agent 项目（或本规范套件）是否满足约定。

用法:
    python3 scripts/check-structure.py <目录>

退出码: 0 通过（可能有提醒），1 有阻断项。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED = {
    "README.md": "项目说明",
    "CHANGELOG.md": "变更记录",
    "docs/contract.md": "输入输出契约",
    "docs/design.md": "设计文档",
    "evals/config.json": "评测配置",
    ".gitignore": "忽略规则",
}

CONTRACT_SECTIONS = ["输入", "输出", "错误码", "边界"]

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "疑似 API key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "疑似 GitHub token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "疑似 AWS key"),
    (re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"), "疑似私钥"),
]

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "logs", "outputs"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

problems: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def is_suite(root: Path) -> bool:
    return (root / "docs" / "01-流程规范.md").exists()


def check_suite(root: Path) -> None:
    for name in ["README.md", "AGENTS.md", "scripts/new-agent.sh", "scripts/run-evals.py"]:
        if not (root / name).exists():
            fail(f"缺少 {name}")
    for name in ["01-流程规范", "02-分层模型与项目结构", "03-形态适配指南", "04-评测与质量规范", "05-发布运维与安全", "06-反模式与速查"]:
        if not (root / "docs" / f"{name}.md").exists():
            fail(f"缺少 docs/{name}.md")
    for name in ["需求卡", "设计文档", "契约", "发布说明", "决策记录ADR"]:
        if not (root / "templates" / f"{name}.md").exists():
            fail(f"缺少 templates/{name}.md")
    for name in ["01-立项清单", "02-开发清单", "03-上线清单", "04-复盘清单"]:
        if not (root / "checklists" / f"{name}.md").exists():
            fail(f"缺少 checklists/{name}.md")
    if not (root / "templates" / "project-skeleton" / "Makefile").exists():
        fail("缺少 templates/project-skeleton/Makefile")


def check_project(root: Path) -> None:
    for rel, desc in REQUIRED.items():
        if not (root / rel).exists():
            fail(f"缺少 {rel}（{desc}）")

    contract = root / "docs" / "contract.md"
    if contract.exists():
        text = contract.read_text(encoding="utf-8")
        for section in CONTRACT_SECTIONS:
            if section not in text:
                fail(f"contract.md 缺少“{section}”相关内容")
        for placeholder in ["<agent 名称>", "TODO", "____"]:
            if placeholder in text:
                warn(f"contract.md 仍有占位内容: {placeholder}")

    cases_dir = root / "evals" / "cases"
    cases = sorted(cases_dir.glob("*.json")) + sorted(cases_dir.glob("*.jsonl")) if cases_dir.exists() else []
    if not cases:
        fail("evals/cases/ 下没有用例")
    else:
        ids: set[str] = set()
        for path in cases:
            try:
                raw = path.read_text(encoding="utf-8")
                items = [json.loads(line) for line in raw.splitlines() if line.strip()] if path.suffix == ".jsonl" else [json.loads(raw)]
            except json.JSONDecodeError as exc:
                fail(f"{path.name} 不是合法 JSON: {exc}")
                continue
            for item in items if isinstance(items, list) else [items]:
                case_id = item.get("id")
                if not case_id:
                    fail(f"{path.name} 缺少 id")
                elif case_id in ids:
                    fail(f"用例 id 重复: {case_id}")
                else:
                    ids.add(case_id)
                if not item.get("expect"):
                    fail(f"{case_id or path.name} 缺少 expect 断言")
                if not item.get("tags"):
                    warn(f"{case_id or path.name} 缺少 tags，无法分层统计")
        total = len(ids)
        if total < 30:
            warn(f"用例只有 {total} 条，规范建议 ≥30 条")
        if not (root / "evals" / "baseline.json").exists():
            warn("还没有 evals/baseline.json，达标后用 --update-baseline 生成")

    if not (root / "docs" / "runbook.md").exists():
        warn("缺少 docs/runbook.md（上线前需要）")
    if not (root / "prompts").exists():
        warn("没有 prompts/ 目录（若提示词写在代码里可忽略）")
    if not (root / "tests").exists():
        warn("没有 tests/ 目录")


def walk_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and not any(part in SKIP_DIRS for part in path.parts):
            yield path


def check_secrets(root: Path) -> None:
    for path in walk_files(root):
        if path.name in {".env.example", ".gitignore"} or path.suffix in {".png", ".jpg", ".pdf", ".zip"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if path.suffix == ".md":
            # 文档里常以行内代码形式列举密钥模式，不应算泄漏
            text = re.sub(r"`[^`]*`", "", text)
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"{path.relative_to(root)} 疑似含密钥（{label}）")


def check_quotes(root: Path) -> None:
    for path in walk_files(root):
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        pairs = [("\u201c", "\u201d", "双引号"), ("\u2018", "\u2019", "单引号")]
        for left, right, label in pairs:
            if text.count(left) != text.count(right):
                fail(f"{path.relative_to(root)} {label}不配对: {text.count(left)} 左 / {text.count(right)} 右")


def check_links(root: Path) -> None:
    for path in walk_files(root):
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for raw in LINK_RE.findall(text):
            target = raw.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#")[0].strip()
            if not target or "{" in target or "<" in target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                fail(f"{path.relative_to(root)} 链接失效: {target}")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").expanduser().resolve()
    if not root.is_dir():
        print(f"不是目录: {root}")
        return 1

    suite = is_suite(root)
    print(f"检查 {'规范套件' if suite else 'agent 项目'}: {root}")
    print("-" * 56)

    if suite:
        check_suite(root)
    else:
        check_project(root)
    check_secrets(root)
    check_quotes(root)
    check_links(root)

    for item in warnings:
        print(f"提醒  {item}")
    for item in problems:
        print(f"阻断  {item}")

    print("-" * 56)
    if problems:
        print(f"未通过：{len(problems)} 项阻断，{len(warnings)} 项提醒")
        return 1
    print(f"通过：0 项阻断，{len(warnings)} 项提醒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
