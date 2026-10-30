"""数据模型与校验：brief（需求）→ outline（骨架）→ deck（成稿）。

原则：结构问题在写文件之前就报错，不把坏数据留到渲染阶段。
"""

from __future__ import annotations

from typing import Any

from .errors import StageError
from .textfit import measure

LAYOUTS = (
    "title",
    "section",
    "bullets",
    "two-col",
    "stats",
    "timeline",
    "quote",
    "image",
    "closing",
)

CONTENT_LAYOUTS = {"bullets", "two-col", "stats", "timeline", "quote", "image"}

SLIDE_MIN = 3
SLIDE_MAX = 30
BULLET_MAX = 5
BULLET_UNITS_MAX = 56
TITLE_UNITS_MAX = 34
NOTES_MIN = 20


def units(text: str) -> float:
    """视觉宽度单位：1 个汉字 ≈ 1，拉丁字符 ≈ 0.5。"""
    return measure(str(text), 1.0)


def _text(value: Any, field: str, *, required: bool = False, limit: int = 200) -> str:
    if value is None:
        if required:
            raise StageError("MISSING_FIELD", f"缺少字段: {field}", f"补充 {field} 后重试")
        return ""
    if not isinstance(value, str):
        raise StageError("INVALID_FIELD", f"{field} 必须是字符串", "传字符串")
    text = value.strip()
    if required and not text:
        raise StageError("EMPTY_FIELD", f"{field} 不能为空", f"填写 {field}")
    if len(text) > limit:
        raise StageError("FIELD_TOO_LONG", f"{field} 超过 {limit} 字符", "缩短后重试")
    return text


def normalize_brief(data: Any) -> dict[str, Any]:
    """校验并补全 brief。"""
    if not isinstance(data, dict):
        raise StageError("INVALID_BRIEF", "brief 必须是 JSON 对象", "传入 {\"topic\": \"...\"}")

    raw_topic = str(data.get("topic") or data.get("title") or "").strip()
    if not raw_topic:
        raise StageError("EMPTY_TOPIC", "topic 不能为空", "用一句话说明这份 deck 讲什么")
    topic = _text(raw_topic, "topic", required=True, limit=80)
    language = str(data.get("language") or data.get("lang") or "zh").lower()
    if language not in ("zh", "en"):
        raise StageError("INVALID_LANGUAGE", f"不支持的语言: {language}", "可选 zh / en")

    try:
        slide_count = int(data.get("slide_count") or 10)
    except (TypeError, ValueError) as exc:
        raise StageError("INVALID_SLIDE_COUNT", "slide_count 必须是整数", "例如 10") from exc
    if not SLIDE_MIN <= slide_count <= SLIDE_MAX:
        raise StageError(
            "INVALID_SLIDE_COUNT",
            f"slide_count 超出范围: {slide_count}",
            f"取值 {SLIDE_MIN}–{SLIDE_MAX}",
        )

    raw_points = data.get("key_points") or []
    if not isinstance(raw_points, list):
        raise StageError("INVALID_BRIEF", "key_points 必须是字符串数组", "例如 [\"要点一\", \"要点二\"]")
    key_points = [_text(item, "key_points[]", limit=60) for item in raw_points if str(item).strip()]
    if len(key_points) > 12:
        raise StageError("TOO_MANY_POINTS", "key_points 最多 12 条", "合并相近要点")

    sections: list[dict[str, Any]] = []
    raw_sections = data.get("sections") or []
    if not isinstance(raw_sections, list):
        raise StageError("INVALID_BRIEF", "sections 必须是数组", "例如 [{\"title\": \"背景\"}]")
    for index, item in enumerate(raw_sections):
        if not isinstance(item, dict):
            raise StageError("INVALID_BRIEF", f"sections[{index}] 必须是对象", "含 title 与 points")
        title = _text(item.get("title"), f"sections[{index}].title", required=True, limit=24)
        raw = item.get("points") or []
        if not isinstance(raw, list):
            raise StageError("INVALID_BRIEF", f"sections[{index}].points 必须是数组", "传字符串数组")
        points = [_text(p, f"sections[{index}].points[]", limit=60) for p in raw if str(p).strip()]
        if not points:
            raise StageError(
                "EMPTY_SECTION",
                f"章节「{title}」没有要点",
                "每个章节至少给 1 条 points",
            )
        if len(points) > 5:
            raise StageError("TOO_MANY_POINTS", f"章节「{title}」要点超过 5 条", "拆成两个章节")
        sections.append({"title": title, "points": points})
    if len(sections) > 6:
        raise StageError("TOO_MANY_SECTIONS", "sections 最多 6 个", "合并章节")

    stats: list[dict[str, str]] = []
    raw_stats = data.get("stats") or []
    if raw_stats:
        if not isinstance(raw_stats, list):
            raise StageError("INVALID_BRIEF", "stats 必须是数组", "例如 [{\"value\": \"42%\", \"label\": \"转化率\"}]")
        for index, item in enumerate(raw_stats):
            if not isinstance(item, dict):
                raise StageError("INVALID_BRIEF", f"stats[{index}] 必须是对象", "含 value 与 label")
            stats.append(
                {
                    "value": _text(item.get("value"), f"stats[{index}].value", required=True, limit=12),
                    "label": _text(item.get("label"), f"stats[{index}].label", required=True, limit=24),
                }
            )
        if not 3 <= len(stats) <= 4:
            raise StageError("INVALID_STATS", "stats 需要 3–4 组", "补足或删减")

    return {
        "topic": topic,
        "goal": _text(data.get("goal"), "goal", limit=160),
        "audience": _text(data.get("audience"), "audience", limit=80),
        "presenter": _text(data.get("presenter"), "presenter", limit=40),
        "date": _text(data.get("date"), "date", limit=40),
        "language": language,
        "slide_count": slide_count,
        "theme": str(data.get("theme") or "swiss"),
        "key_points": key_points,
        "sections": sections,
        "stats": stats,
    }


def _normalize_outline_slide(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StageError("INVALID_OUTLINE", f"slides[{index}] 必须是对象", "含 layout/title/title")
    layout = str(raw.get("layout") or "").strip()
    if layout not in LAYOUTS:
        raise StageError(
            "INVALID_LAYOUT",
            f"slides[{index}] 未知版式: {layout or '(空)'}",
            "可选 " + "、".join(LAYOUTS),
        )
    title = _text(raw.get("title"), f"slides[{index}].title", required=True, limit=60)
    points = raw.get("points") or []
    if not isinstance(points, list):
        raise StageError("INVALID_OUTLINE", f"slides[{index}].points 必须是数组", "传字符串数组")
    points = [_text(p, f"slides[{index}].points[]", limit=80) for p in points if str(p).strip()]
    if len(points) > 6:
        raise StageError("TOO_MANY_POINTS", f"slides[{index}] 要点超过 6 条", "拆页")
    return {
        "layout": layout,
        "title": title,
        "section": _text(raw.get("section"), f"slides[{index}].section", limit=24),
        "subtitle": _text(raw.get("subtitle"), f"slides[{index}].subtitle", limit=120),
        "points": points,
    }


def validate_outline(outline: Any, brief: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """校验模型产出的骨架，并补全封面/结尾。返回 (outline, 修复记录)。"""
    if not isinstance(outline, dict) or not isinstance(outline.get("slides"), list):
        raise StageError("INVALID_OUTLINE", "outline 必须含 slides 数组", "让模型返回 {\"slides\": [...]}")
    raw_slides = outline["slides"]
    if not 1 <= len(raw_slides) <= SLIDE_MAX:
        raise StageError(
            "INVALID_OUTLINE",
            f"outline 页数不合法: {len(raw_slides)}",
            f"控制在 {SLIDE_MIN}–{SLIDE_MAX} 页",
        )
    slides = [_normalize_outline_slide(item, i) for i, item in enumerate(raw_slides)]

    fixes: list[str] = []
    if slides[0]["layout"] != "title":
        slides.insert(
            0,
            {
                "layout": "title",
                "title": brief["topic"],
                "section": "",
                "subtitle": brief.get("goal", ""),
                "points": [],
            },
        )
        fixes.append("补封面")
    if slides[-1]["layout"] != "closing":
        slides.append(
            {"layout": "closing", "title": "谢谢", "section": "", "subtitle": "欢迎交流与提问", "points": []}
        )
        fixes.append("补结尾")
    if not SLIDE_MIN <= len(slides) <= SLIDE_MAX:
        raise StageError(
            "INVALID_OUTLINE",
            f"补全后页数不合法: {len(slides)}",
            f"控制在 {SLIDE_MIN}–{SLIDE_MAX} 页",
        )

    title = _text(outline.get("title") or brief["topic"], "outline.title", limit=80)
    return {"title": title, "slides": slides}, fixes


def _normalize_bullets(raw: Any, slide_index: int) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise StageError("INVALID_DECK", f"slides[{slide_index}].bullets 必须是数组", "传字符串数组")
    bullets: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            item = item.get("text", "")
        text = str(item).strip()
        if text:
            bullets.append(text)
    return bullets


def _normalize_pairs(raw: Any, keys: tuple[str, str], slide_index: int, field: str) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise StageError("INVALID_DECK", f"slides[{slide_index}].{field} 必须是数组", "传对象数组")
    pairs: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        first = str(item.get(keys[0], "")).strip()
        second = str(item.get(keys[1], "")).strip()
        if first:
            pairs.append({keys[0]: first, keys[1]: second})
    return pairs


def validate_deck(deck: Any, brief: dict[str, Any] | None = None) -> dict[str, Any]:
    """校验成稿结构；只做结构性检查，视觉问题留给 checks。"""
    if not isinstance(deck, dict) or not isinstance(deck.get("slides"), list):
        raise StageError("INVALID_DECK", "deck 必须含 slides 数组", "先运行 compose")
    raw_slides = deck["slides"]
    if not SLIDE_MIN <= len(raw_slides) <= SLIDE_MAX:
        raise StageError("INVALID_DECK", f"页数不合法: {len(raw_slides)}", f"控制在 {SLIDE_MIN}–{SLIDE_MAX} 页")

    slides: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_slides):
        if not isinstance(raw, dict):
            raise StageError("INVALID_DECK", f"slides[{index}] 必须是对象", "检查 deck.json")
        layout = str(raw.get("layout") or "").strip()
        if layout not in LAYOUTS:
            raise StageError(
                "INVALID_LAYOUT",
                f"slides[{index}] 未知版式: {layout or '(空)'}",
                "可选 " + "、".join(LAYOUTS),
            )
        slide = {
            "id": str(raw.get("id") or f"s{index + 1:02d}"),
            "layout": layout,
            "section": str(raw.get("section") or "").strip(),
            "title": str(raw.get("title") or "").strip(),
            "subtitle": str(raw.get("subtitle") or "").strip(),
            "bullets": _normalize_bullets(raw.get("bullets"), index),
            "insight": str(raw.get("insight") or "").strip(),
            "stats": _normalize_pairs(raw.get("stats"), ("value", "label"), index, "stats"),
            "steps": _normalize_pairs(raw.get("steps"), ("title", "detail"), index, "steps"),
            "quote": raw.get("quote") if isinstance(raw.get("quote"), dict) else {},
            "image": str(raw.get("image") or "").strip(),
            "notes": str(raw.get("notes") or "").strip(),
        }
        if layout != "image" and not slide["title"]:
            raise StageError("INVALID_DECK", f"slides[{index}] 缺少标题", "每页都要有 title")
        slides.append(slide)

    meta = dict(deck.get("meta") or {})
    if brief:
        meta.setdefault("title", brief["topic"])
        meta.setdefault("language", brief["language"])
        meta.setdefault("audience", brief.get("audience", ""))
        meta.setdefault("presenter", brief.get("presenter", ""))
        meta.setdefault("theme", brief.get("theme", "swiss"))
    meta["slide_count"] = len(slides)
    return {"meta": meta, "slides": slides}


def deck_summary(deck: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": deck["meta"].get("title", ""),
        "slide_count": len(deck["slides"]),
        "layouts": [slide["layout"] for slide in deck["slides"]],
        "titles": [slide["title"] for slide in deck["slides"]],
    }
