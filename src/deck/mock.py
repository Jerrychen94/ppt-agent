"""离线内容生成：不调用模型，用 brief 的要点做确定性成稿。

作用有两个：让 `make run` 与评测在无密钥环境下可复现；同时充当
内容质量的兜底（模型不可用时至少能交出一份结构完整的稿子）。
"""

from __future__ import annotations

import math
import re
from typing import Any

DEFAULT_SECTIONS_ZH = ["背景与判断", "核心发现", "行动建议"]
DEFAULT_SECTIONS_EN = ["Context", "Findings", "Next steps"]


def _clip(text: str, limit: int) -> str:
    text = str(text).strip()
    return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"


def _split_point(text: str, limit: int = 42) -> list[str]:
    """长要点按标点拆成多条，避免单条溢出。"""
    text = str(text).strip()
    if len(text) <= limit:
        return [text]
    parts = [part for part in re.split(r"(?<=[，。；、,!?;])", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) <= limit:
            current += part
        else:
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks or [_clip(text, limit)]


def _sections(brief: dict[str, Any]) -> list[dict[str, Any]]:
    if brief.get("sections"):
        return [
            {"title": _clip(section["title"], 18), "points": list(section["points"])}
            for section in brief["sections"]
        ]
    points = list(brief.get("key_points") or [])
    if not points:
        topic = brief["topic"]
        if brief["language"] == "en":
            return [
                {"title": "Why now", "points": [f"The context behind {topic}"]},
                {"title": "What matters", "points": [f"The main decision for {topic}"]},
                {"title": "Next steps", "points": [f"What we will do about {topic}"]},
            ]
        return [
            {"title": "背景与判断", "points": [f"{topic}为什么现在值得讨论"]},
            {"title": "核心发现", "points": [f"{topic}的关键判断"]},
            {"title": "行动建议", "points": [f"{topic}下一步怎么推进"]},
        ]
    count = 3 if len(points) >= 6 else (2 if len(points) >= 3 else 1)
    names = DEFAULT_SECTIONS_EN if brief["language"] == "en" else DEFAULT_SECTIONS_ZH
    size = math.ceil(len(points) / count)
    return [
        {"title": names[index % len(names)], "points": points[index * size : (index + 1) * size]}
        for index in range(count)
        if points[index * size : (index + 1) * size]
    ]


def _chunks(points: list[str], size: int = 3) -> list[list[str]]:
    return [points[index : index + size] for index in range(0, len(points), size)] or [[]]


def _unique_title(base: str, used: set[str]) -> str:
    if base not in used:
        used.add(base)
        return base
    for index in range(2, 20):
        candidate = f"{base} · {index}"
        if candidate not in used:
            used.add(candidate)
            return candidate
    return base


def _build_raw(brief: dict[str, Any]) -> list[dict[str, Any]]:
    topic = brief["topic"]
    goal = brief.get("goal") or ""
    sections = _sections(brief)
    raw: list[dict[str, Any]] = [
        {"kind": "cover", "title": topic, "subtitle": goal, "section": ""}
    ]
    for section in sections:
        raw.append(
            {
                "kind": "section",
                "title": section["title"],
                "subtitle": _clip(section["points"][0], 46) if section["points"] else "",
                "section": section["title"],
                "points": section["points"],
            }
        )
        for chunk in _chunks(section["points"]):
            raw.append(
                {
                    "kind": "content",
                    "title": _clip(chunk[0], 22) if chunk else section["title"],
                    "section": section["title"],
                    "points": chunk,
                }
            )
    raw.append({"kind": "closing", "title": "谢谢" if brief["language"] == "zh" else "Thank you", "subtitle": "欢迎交流与提问" if brief["language"] == "zh" else "Questions & discussion", "section": ""})
    return raw


def _trim(raw: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    """删章节页 → 合并同章节内容页 → 删末尾内容页。"""
    while len(raw) > target:
        removed = False
        for index in range(len(raw) - 2, 0, -1):
            if raw[index]["kind"] == "section" and raw[index - 1]["kind"] != "cover":
                raw.pop(index)
                removed = True
                break
        if removed:
            continue
        for index in range(len(raw) - 2, 0, -1):
            if (
                raw[index]["kind"] == "content"
                and raw[index + 1]["kind"] == "content"
                and raw[index]["section"] == raw[index + 1]["section"]
                and len(raw[index]["points"]) + len(raw[index + 1]["points"]) <= 5
            ):
                raw[index]["points"] = raw[index]["points"] + raw[index + 1]["points"]
                raw.pop(index + 1)
                removed = True
                break
        if removed:
            continue
        for index in range(len(raw) - 2, 0, -1):
            if raw[index]["kind"] == "content":
                raw.pop(index)
                removed = True
                break
        if not removed:
            break
    if not any(item["kind"] == "content" for item in raw):
        for item in raw:
            if item["kind"] == "section":
                item["kind"] = "content"
                break
    return raw


def _expand(raw: list[dict[str, Any]], target: int, brief: dict[str, Any]) -> list[dict[str, Any]]:
    """页数不够时补有信息量的页面：数据、节奏、行动，最后才用金句。"""
    language = brief["language"]
    sections = _sections(brief)
    base_points = [point for point in (brief.get("key_points") or []) if point][:3] or [brief["topic"]]
    extras: list[str] = []
    if brief.get("stats") and not any(item.get("kind") == "stats" for item in raw):
        extras.append("stats")
    if len(base_points) >= 3:
        extras.append("timeline")
    extras.extend(["two-col", "quote"])

    section_name = sections[-1]["title"] if sections else ""
    while len(raw) < target:
        kind = extras.pop(0) if extras else "quote"
        insert_at = len(raw) - 1
        if kind == "stats":
            raw.insert(
                insert_at,
                {"kind": "stats", "title": "关键数据" if language == "zh" else "By the numbers", "section": section_name, "points": []},
            )
        elif kind == "timeline":
            raw.insert(
                insert_at,
                {
                    "kind": "timeline",
                    "title": "推进节奏" if language == "zh" else "Rollout plan",
                    "section": section_name,
                    "points": base_points,
                },
            )
        elif kind == "two-col":
            raw.insert(
                insert_at,
                {
                    "kind": "two-col",
                    "title": "把结论落到行动" if language == "zh" else "From insight to action",
                    "section": section_name,
                    "points": base_points,
                },
            )
        else:
            raw.insert(
                insert_at,
                {
                    "kind": "quote",
                    "title": "一句话总结" if language == "zh" else "In one line",
                    "section": "",
                    "points": [brief.get("goal") or brief["topic"]],
                },
            )
    return raw


def build_outline(brief: dict[str, Any]) -> dict[str, Any]:
    target = int(brief["slide_count"])
    raw = _build_raw(brief)
    raw = _trim(raw, target)
    raw = _expand(raw, target, brief)

    used: set[str] = set()
    counters: dict[str, int] = {}
    stats_used = False
    section_names = [item["title"] for item in _sections(brief)] or [""]
    middle = section_names[len(section_names) // 2] if section_names else ""

    slides: list[dict[str, Any]] = []
    for item in raw:
        kind = item["kind"]
        if kind == "cover":
            slides.append(
                {
                    "layout": "title",
                    "title": item["title"],
                    "subtitle": item["subtitle"],
                    "section": "",
                    "points": [],
                }
            )
        elif kind == "section":
            slides.append(
                {
                    "layout": "section",
                    "title": _unique_title(_clip(item["title"], 18), used),
                    "subtitle": item["subtitle"],
                    "section": item["title"],
                    "points": item["points"],
                }
            )
        elif kind == "content":
            name = item["section"]
            order = counters.get(name, 0)
            counters[name] = order + 1
            if order == 0:
                layout = "bullets"
            elif order == 1 and brief.get("stats") and not stats_used and name == middle:
                layout = "stats"
                stats_used = True
            elif order == 1:
                layout = "two-col"
            elif order == 2:
                layout = "timeline"
            else:
                layout = "quote"
            title = _unique_title(_clip(item["title"], 22), used)
            slides.append(
                {
                    "layout": layout,
                    "title": title,
                    "subtitle": "",
                    "section": name,
                    "points": item["points"],
                }
            )
        elif kind == "stats":
            slides.append(
                {
                    "layout": "stats",
                    "title": "关键数据" if brief["language"] == "zh" else "By the numbers",
                    "subtitle": "",
                    "section": item["section"],
                    "points": [],
                }
            )
        elif kind in ("timeline", "two-col"):
            slides.append(
                {
                    "layout": kind,
                    "title": _unique_title(item["title"], used),
                    "subtitle": "",
                    "section": item.get("section", ""),
                    "points": item["points"],
                }
            )
        elif kind == "quote":
            slides.append(
                {
                    "layout": "quote",
                    "title": _unique_title("一句话总结" if brief["language"] == "zh" else "In one line", used),
                    "subtitle": "",
                    "section": "",
                    "points": item["points"],
                }
            )
        else:  # closing
            slides.append({"layout": "closing", "title": item["title"], "subtitle": item["subtitle"], "section": "", "points": []})

    if len(slides) < 3:
        points = list(brief.get("key_points") or [brief["topic"]])
        slides.insert(
            1,
            {
                "layout": "bullets",
                "title": _clip(points[0], 22),
                "subtitle": "",
                "section": "",
                "points": points,
            },
        )
    return {"title": brief["topic"], "slides": slides[:target] if len(slides) > target else slides}


def _notes(brief: dict[str, Any], slide: dict[str, Any]) -> str:
    layout = slide["layout"]
    if brief["language"] == "en":
        if layout == "title":
            return f"Open with the topic and the goal: {brief.get('goal') or brief['topic']}. Give one sentence on why it matters now, then move on."
        if layout == "section":
            return "A short transition. State the question this section answers, then go straight to the first evidence slide."
        if layout == "closing":
            return "Recap the three takeaways, leave thirty seconds for questions, and promise to share the deck afterwards."
        return f"Lead with the conclusion: {slide['title']}. Back it with one number or example, then hand off with a single sentence."
    if layout == "title":
        return f"开场先报主题与目标：{brief.get('goal') or brief['topic']}。用一句话说明为什么现在讲，再翻页。"
    if layout == "section":
        return "过渡页。用一句话点出这一章要回答的问题，停一拍，直接进入下一页的证据。"
    if layout == "closing":
        return "收束三个要点，留三十秒给提问；会后把这份 deck 与讲稿发到群里。"
    if layout == "quote":
        text = (slide.get("quote") or {}).get("text") or slide["title"]
        return f"停两秒，把这句话读出来：{text}。再用一句话说明它和上一页的关系。"
    if layout == "stats":
        return "先让数字自己说话，停一拍；再解释每个数字背后的口径与变化原因。"
    if layout == "timeline":
        return "按时间顺序讲三步，每步只说一个动作和一个结果；最后停在最后一步的收益上。"
    bullets = slide.get("bullets") or []
    first = bullets[0] if bullets else slide["title"]
    second = bullets[1] if len(bullets) > 1 else ""
    extra = f"再用「{second}」补一个证据。" if second else ""
    return f"这一页先给结论：{first}。{extra}讲完停一拍，用一句话把听众带到下一页。"


def compose_deck(brief: dict[str, Any], outline: dict[str, Any]) -> dict[str, Any]:
    language = brief["language"]
    slides: list[dict[str, Any]] = []
    for index, item in enumerate(outline["slides"], 1):
        layout = item["layout"]
        points = [str(point) for point in item.get("points") or []]
        slide: dict[str, Any] = {
            "id": f"s{index:02d}",
            "layout": layout,
            "section": item.get("section", ""),
            "title": item["title"],
            "subtitle": item.get("subtitle", ""),
            "bullets": [],
            "insight": "",
            "stats": [],
            "steps": [],
            "quote": {},
            "image": "",
            "notes": "",
        }

        if layout == "title":
            slide["subtitle"] = brief.get("goal") or (
                f"面向{brief.get('audience') or '听众'}的汇报" if language == "zh" else f"A briefing for {brief.get('audience') or 'the audience'}"
            )
        elif layout == "section":
            if points:
                slide["subtitle"] = _clip("这一章回答：" + points[0], 46) if language == "zh" else _clip("This section answers: " + points[0], 60)
            else:
                slide["subtitle"] = item.get("subtitle", "")
        elif layout in ("bullets", "two-col", "image"):
            bullets: list[str] = []
            for point in points:
                bullets.extend(_split_point(point))
            if bullets and bullets[0] == slide["title"]:
                bullets = bullets[1:]
            if len(bullets) < 2:
                extras_zh = ["先小范围试点，再逐步推广", "用数据复盘，每两周对齐一次", "把有效做法沉淀成团队规范"]
                extras_en = ["Start with a small pilot, then scale", "Review the data every two weeks", "Turn what works into team practice"]
                extras = extras_en if language == "en" else extras_zh
                position = sum(1 for existing in slides if existing.get("layout") in ("bullets", "two-col", "image"))
                extra = extras[position % len(extras)]
                if extra not in bullets:
                    bullets.append(extra)
            slide["bullets"] = bullets[:5]
            slide["insight"] = _clip(brief.get("goal") or (points[-1] if points else item["title"]), 70)
        elif layout == "stats":
            slide["stats"] = [dict(stat) for stat in brief.get("stats") or []]
            if len(slide["stats"]) < 3:
                slide["layout"] = "bullets"
                slide["bullets"] = [f"{stat['value']} {stat['label']}" for stat in slide["stats"]] or points[:4]
        elif layout == "timeline":
            labels_zh = ["验证", "试点", "复盘", "推广", "固化"]
            labels_en = ["Validate", "Pilot", "Review", "Scale", "Embed"]
            labels = labels_en if language == "en" else labels_zh
            steps = [
                {"title": labels[index % len(labels)], "detail": point}
                for index, point in enumerate(points)
            ][:5]
            if len(steps) < 3:
                slide["layout"] = "bullets"
                slide["bullets"] = points[:5]
            else:
                slide["steps"] = steps
        elif layout == "quote":
            slide["quote"] = {
                "text": points[0] if points else (brief.get("goal") or item["title"]),
                "attribution": brief.get("presenter") or ("本次汇报" if language == "zh" else "This deck"),
            }
        elif layout == "closing":
            slide["subtitle"] = item.get("subtitle") or ("欢迎交流与提问" if language == "zh" else "Questions & discussion")

        slide["notes"] = _notes(brief, slide)
        slides.append(slide)

    return {
        "meta": {
            "title": brief["topic"],
            "subtitle": brief.get("goal", ""),
            "audience": brief.get("audience", ""),
            "presenter": brief.get("presenter", ""),
            "date": brief.get("date", ""),
            "language": language,
            "theme": brief.get("theme", "swiss"),
            "provider": "mock",
        },
        "slides": slides,
    }
