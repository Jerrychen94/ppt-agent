"""确定性质检：溢出、密度、一致性、讲稿完整度。

这里不调用模型——模型评审属于可选的下一版能力。所有判断都能在
离线环境下复现，因而适合做回归门禁。
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .model import BULLET_MAX, BULLET_UNITS_MAX, NOTES_MIN, SLIDE_MAX, SLIDE_MIN, TITLE_UNITS_MAX, units
from .render import build_scenes
from .theme import Theme


def _finding(level: str, code: str, message: str, slide: str = "", hint: str = "") -> dict[str, str]:
    item = {"level": level, "code": code, "message": message, "slide": slide}
    if hint:
        item["hint"] = hint
    return item


def _slide_has_content(slide: dict[str, Any]) -> bool:
    layout = slide["layout"]
    if layout in ("bullets", "two-col", "image"):
        return bool(slide.get("bullets") or slide.get("insight") or slide.get("subtitle"))
    if layout == "stats":
        return len(slide.get("stats") or []) >= 3
    if layout == "timeline":
        return len(slide.get("steps") or []) >= 2
    if layout == "quote":
        return bool((slide.get("quote") or {}).get("text") or slide.get("insight"))
    return True


def qa(deck: dict[str, Any], theme: Theme) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    slides = deck["slides"]

    if not SLIDE_MIN <= len(slides) <= SLIDE_MAX:
        findings.append(
            _finding("error", "SLIDE_COUNT", f"页数 {len(slides)} 超出 {SLIDE_MIN}–{SLIDE_MAX}", hint="调整页数")
        )
    if slides[0]["layout"] != "title":
        findings.append(_finding("error", "MISSING_COVER", "第一页必须是封面", slides[0]["id"], "补 title 版式"))
    if slides[-1]["layout"] != "closing":
        findings.append(_finding("error", "MISSING_CLOSING", "最后一页必须是结尾", slides[-1]["id"], "补 closing 版式"))

    for problem in theme.check():
        findings.append(_finding("error", "LOW_CONTRAST", problem, hint="调整主题配色"))

    titles: Counter[str] = Counter()
    layout_runs: list[str] = []
    total_chars = 0
    bullet_total = 0

    for slide in slides:
        slide_id = slide["id"]
        layout = slide["layout"]
        title = slide.get("title") or ""
        titles[title] += 1
        layout_runs.append(layout)

        if title:
            title_units = units(title)
            title_limit = 44 if layout == "title" else TITLE_UNITS_MAX
            total_chars += len(title)
            if title_units > title_limit:
                findings.append(
                    _finding(
                        "error",
                        "TITLE_TOO_LONG",
                        f"标题过长（{title_units:.0f} 字宽）: {title[:20]}",
                        slide_id,
                        "压到 20 字以内或拆成主副标题",
                    )
                )
            elif title_units > TITLE_UNITS_MAX * 0.78:
                findings.append(
                    _finding("warn", "TITLE_LONG", f"标题偏长（{title_units:.0f} 字宽）: {title[:20]}", slide_id, "再精简一点")
                )

        bullets = [str(item) for item in slide.get("bullets") or []]
        bullet_total += len(bullets)
        for bullet in bullets:
            total_chars += len(bullet)
            width = units(bullet)
            if width > BULLET_UNITS_MAX:
                findings.append(
                    _finding(
                        "error",
                        "BULLET_TOO_LONG",
                        f"要点过长（{width:.0f} 字宽）: {bullet[:20]}",
                        slide_id,
                        "一条要点只说一件事，控制在 28 字内",
                    )
                )
            elif width > BULLET_UNITS_MAX * 0.72:
                findings.append(_finding("warn", "BULLET_LONG", f"要点偏长: {bullet[:20]}", slide_id, "再精简一点"))
        if len(bullets) > BULLET_MAX:
            findings.append(
                _finding(
                    "error",
                    "TOO_MANY_BULLETS",
                    f"{len(bullets)} 条要点，超过上限 {BULLET_MAX}",
                    slide_id,
                    "合并要点或拆页",
                )
            )
        elif len(bullets) == BULLET_MAX:
            findings.append(_finding("warn", "DENSE_SLIDE", f"{len(bullets)} 条要点，信息密度偏高", slide_id, "考虑拆页"))

        if layout in ("bullets", "two-col", "stats", "timeline", "quote") and not _slide_has_content(slide):
            findings.append(
                _finding("error", "EMPTY_CONTENT", "该页没有有效内容", slide_id, "补 bullets / stats / steps / quote")
            )

        notes = slide.get("notes") or ""
        total_chars += len(notes)
        if not notes:
            findings.append(_finding("warn", "MISSING_NOTES", "缺少讲稿备注", slide_id, "补 40–120 字口播提示"))
        elif len(notes) < NOTES_MIN:
            findings.append(_finding("warn", "SHORT_NOTES", f"讲稿过短（{len(notes)} 字）", slide_id, "补到 40 字以上"))

    for title, count in titles.items():
        if title and count > 1:
            findings.append(_finding("warn", "DUPLICATE_TITLE", f"标题重复 {count} 次: {title}", hint="换一个差异化标题"))

    run = 1
    for index in range(1, len(layout_runs)):
        if layout_runs[index] == layout_runs[index - 1]:
            run += 1
            if run >= 3 and layout_runs[index] == "bullets":
                findings.append(
                    _finding(
                        "warn",
                        "REPETITIVE_LAYOUT",
                        f"连续 {run} 页都是 bullets 版式",
                        slides[index]["id"],
                        "换成 two-col / stats / timeline 增加节奏",
                    )
                )
                run = 0
        else:
            run = 1

    for index, slide in enumerate(slides):
        if slide["layout"] == "section" and index + 1 < len(slides) and slides[index + 1]["layout"] == "closing":
            findings.append(_finding("warn", "ORPHAN_SECTION", "章节页之后直接结束", slide["id"], "补一页该章节内容"))

    scenes = build_scenes(deck, theme)
    for scene in scenes:
        for warning in scene.warnings:
            level = "error" if warning["code"] in ("OVERFLOW", "IMAGE_NOT_FOUND") else "warn"
            findings.append(_finding(level, warning["code"], warning["message"], scene.slide_id, warning.get("hint", "")))

    errors = sum(1 for item in findings if item["level"] == "error")
    warnings = sum(1 for item in findings if item["level"] == "warn")
    score = max(0, min(100, 100 - 10 * errors - 3 * warnings))
    return {
        "ok": errors == 0,
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "stats": {
            "slides": len(slides),
            "characters": total_chars,
            "avg_bullets": round(bullet_total / max(len(slides), 1), 2),
            "notes_ratio": round(sum(1 for s in slides if s.get("notes")) / max(len(slides), 1), 2),
            "layouts": dict(Counter(layout_runs)),
            "theme": theme.name,
        },
    }
