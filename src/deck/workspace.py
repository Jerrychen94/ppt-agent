"""工作区：一个 deck 一个目录，所有中间产物落盘可复查。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .errors import StageError

FILES = ("brief.json", "outline.json", "deck.json", "deck.pptx", "preview.html", "deck.md", "qa.json")


def slugify(text: str, fallback: str = "deck") -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", (text or "").strip().lower(), flags=re.UNICODE)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_")
    return cleaned[:48] or fallback


def deck_dir(root: Path, slug: str) -> Path:
    return Path(root).expanduser().resolve() / "decks" / slug


def paths(root: Path, slug: str) -> dict[str, Path]:
    base = deck_dir(root, slug)
    return {
        "dir": base,
        "brief": base / "brief.json",
        "outline": base / "outline.json",
        "deck": base / "deck.json",
        "pptx": base / "deck.pptx",
        "html": base / "preview.html",
        "markdown": base / "deck.md",
        "qa": base / "qa.json",
        "log": base / "run.jsonl",
    }


def exists(root: Path, slug: str) -> bool:
    return paths(root, slug)["brief"].exists()


def create(root: Path, slug: str, brief: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    target = deck_dir(root, slug)
    if target.exists() and not force:
        raise StageError("DECK_EXISTS", f"deck 已存在: {slug}", "换一个 --slug，或加 --force 覆盖")
    target.mkdir(parents=True, exist_ok=True)
    save_json(paths(root, slug)["brief"], brief)
    return brief


def list_decks(root: Path) -> list[str]:
    base = Path(root).expanduser().resolve() / "decks"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "brief.json").exists())


def load_json(path: Path) -> Any:
    if not path.exists():
        raise StageError("MISSING_FILE", f"找不到文件: {path}", "先运行前一步命令")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StageError("INVALID_JSON", f"文件不是合法 JSON: {path.name}", str(exc)) from exc


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def log_event(root: Path, slug: str, event: dict[str, Any]) -> None:
    path = paths(root, slug)["log"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
