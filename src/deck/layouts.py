"""九种版式：每种版式只做一件事，且所有文案都经过溢出测量。"""

from __future__ import annotations

from typing import Any

from .model import BULLET_MAX
from .scene import Builder, Scene
from .theme import Theme

MARGIN = 0.85
CONTENT_W = 13.333 - 2 * MARGIN


def _body_items(slide: dict[str, Any]) -> list[str]:
    items = [str(item) for item in slide.get("bullets") or [] if str(item).strip()]
    if items:
        return items
    if slide.get("insight"):
        return [str(slide["insight"])]
    if slide.get("subtitle"):
        return [str(slide["subtitle"])]
    return []


def _title(b: Builder) -> None:
    slide, theme = b.slide, b.theme
    b.rect(MARGIN, 1.68, 0.62, 0.09, "accent")
    b.text(MARGIN, 2.0, 11.2, 2.1, slide["title"], 50, "fg", bold=True, min_size=28)
    subtitle = slide.get("subtitle") or slide.get("insight") or ""
    b.text(MARGIN, 4.3, 10.6, 1.0, subtitle, 20, "muted", min_size=14)
    audience = slide.get("audience") or ""
    presenter = slide.get("presenter") or ""
    date = slide.get("date") or ""
    meta = " · ".join(part for part in (presenter, audience, date) if part)
    if meta:
        b.text(MARGIN, 6.45, 9.5, 0.4, meta, 11.5, "muted", font="latin")
    b.rect(11.6, 2.0, 0.9, 0.9, "accent", radius=0.45)
    b.rect(11.78, 2.18, 0.54, 0.54, "bg", radius=0.27)


def _section(b: Builder) -> None:
    slide, theme = b.slide, b.theme
    number = f"{int(slide.get('_section_no') or b.page):02d}"
    b.text(8.2, 1.15, 4.3, 2.3, number, 118, theme.tint(theme.accent, 0.28), bold=True, align="right", font="latin")
    b.text(MARGIN, 2.05, 7.4, 0.35, f"SECTION {number}", 11, "accent", bold=True, font="latin")
    b.text(MARGIN, 2.45, 7.5, 1.9, slide["title"], 40, "fg", bold=True, min_size=24)
    b.line(MARGIN, 4.55, MARGIN + 1.9, 4.55, "accent", 2.0)
    detail = " · ".join(_body_items(slide)) or slide.get("subtitle", "")
    b.text(MARGIN, 4.8, 7.6, 1.4, detail, 15, "muted", min_size=11)


def _bullets(b: Builder) -> None:
    slide = b.slide
    b.header(slide["title"], slide.get("section", ""))
    items = _body_items(slide)[:BULLET_MAX]
    b.bullet_stack(items, MARGIN + 0.4, 2.28, CONTENT_W - 0.4, 4.15, size=21, min_size=13)
    b.footer()


def _two_col(b: Builder) -> None:
    slide = b.slide
    b.header(slide["title"], slide.get("section", ""))
    items = _body_items(slide)[:BULLET_MAX]
    b.bullet_stack(items, MARGIN + 0.4, 2.28, 6.2, 4.05, size=20, min_size=12)

    card_x, card_w = 7.55, 4.93
    b.rect(card_x, 2.15, card_w, 4.35, "card", radius=0.06)
    b.text(card_x + 0.3, 2.38, card_w - 0.6, 0.3, "关键结论", 10.5, "accent", bold=True, font="latin")
    insight = slide.get("insight") or (items[-1] if items else "")
    b.text(card_x + 0.3, 2.62, card_w - 0.6, 3.55, insight, 19, "fg", min_size=12, anchor="middle")
    b.footer()


def _stats(b: Builder) -> None:
    slide = b.slide
    b.header(slide["title"], slide.get("section", ""))
    stats = [item for item in slide.get("stats") or [] if item.get("value")][:4]
    if len(stats) < 3:
        b.scene.warnings.append(
            {"code": "LAYOUT_FALLBACK", "message": "stats 数据不足 3 组，已按要点渲染", "hint": "补足 stats 或换成 bullets"}
        )
        b.bullet_stack(_body_items(slide)[:BULLET_MAX], MARGIN + 0.4, 2.28, CONTENT_W - 0.4, 4.1, size=21, min_size=13)
        b.footer()
        return
    gap = 0.28
    count = len(stats)
    card_w = (CONTENT_W - gap * (count - 1)) / count
    for index, item in enumerate(stats):
        x = MARGIN + index * (card_w + gap)
        b.rect(x, 2.55, card_w, 3.0, "card", radius=0.05)
        b.rect(x, 2.55, card_w, 0.07, "accent")
        b.text(x + 0.3, 2.95, card_w - 0.6, 1.05, item["value"], 44, "accent", bold=True, min_size=24, font="latin")
        b.text(x + 0.3, 4.12, card_w - 0.6, 1.0, item.get("label", ""), 13.5, "muted", min_size=10)
    b.footer()


def _timeline(b: Builder) -> None:
    slide = b.slide
    b.header(slide["title"], slide.get("section", ""))
    steps = [item for item in slide.get("steps") or [] if item.get("title")][:5]
    if len(steps) < 3:
        steps = [{"title": item[:12], "detail": item} for item in _body_items(slide)[:4]]
    if len(steps) < 2:
        b.bullet_stack(_body_items(slide)[:BULLET_MAX], MARGIN + 0.4, 2.28, CONTENT_W - 0.4, 4.1, size=21, min_size=13)
        b.footer()
        return
    count = len(steps)
    col_w = CONTENT_W / count
    line_y = 3.2
    b.line(MARGIN, line_y, MARGIN + CONTENT_W, line_y, "muted", 1.25)
    for index, step in enumerate(steps):
        center = MARGIN + col_w * index + col_w / 2
        b.rect(center - 0.19, line_y - 0.19, 0.38, 0.38, "accent", radius=0.19)
        b.text(center - 0.19, line_y - 0.19, 0.38, 0.38, str(index + 1), 10.5, "bg", bold=True, align="center", anchor="middle", font="latin")
        b.text(center - col_w / 2 + 0.12, 2.12, col_w - 0.24, 0.8, step["title"], 14.5, "fg", bold=True, align="center", min_size=10)
        b.text(center - col_w / 2 + 0.14, 3.58, col_w - 0.28, 2.2, step.get("detail", ""), 11.5, "muted", align="center", min_size=9)
    b.footer()


def _quote(b: Builder) -> None:
    slide = b.slide
    quote = slide.get("quote") or {}
    text = str(quote.get("text") or slide.get("insight") or " ".join(_body_items(slide)[:1]) or slide["title"])
    attribution = str(quote.get("attribution") or "")
    b.text(MARGIN - 0.1, 0.55, 2.2, 1.7, "\u201c", 120, "accent", font="title")
    b.text(MARGIN + 0.05, 1.95, 11.3, 2.7, text, 31, "fg", min_size=18)
    b.line(MARGIN + 0.1, 5.05, MARGIN + 1.5, 5.05, "accent", 2.0)
    if attribution:
        b.text(MARGIN + 0.1, 5.22, 8.0, 0.4, attribution, 13, "muted")
    b.footer()


def _image(b: Builder) -> None:
    slide = b.slide
    b.header(slide["title"], slide.get("section", ""))
    box_x, box_y, box_w, box_h = MARGIN, 2.15, 6.25, 4.4
    path = str(slide.get("image") or "")
    if path:
        x, y, w, h = box_x, box_y, box_w, box_h
        try:
            from PIL import Image

            with Image.open(path) as handle:
                ratio = handle.width / max(handle.height, 1)
            if ratio > box_w / box_h:
                w, h = box_w, box_w / ratio
                x, y = box_x, box_y + (box_h - h) / 2
            else:
                h, w = box_h, box_h * ratio
                x, y = box_x + (box_w - w) / 2, box_y
        except Exception:  # 读不到尺寸就按整块铺，交给 picture() 报缺失
            pass
        b.picture(x, y, w, h, path)
    else:
        b.picture(box_x, box_y, box_w, box_h, path or "missing.png")

    b.bullet_stack(_body_items(slide)[:4], 7.45, 2.3, 5.0, 3.9, size=17, min_size=11)
    b.footer()


def _closing(b: Builder) -> None:
    slide = b.slide
    b.text(MARGIN, 2.45, CONTENT_W, 1.5, slide["title"] or "谢谢", 62, "fg", bold=True, align="center", min_size=32)
    b.rect(6.05, 4.12, 1.22, 0.07, "accent")
    b.text(MARGIN, 4.4, CONTENT_W, 0.9, slide.get("subtitle") or "欢迎交流与提问", 18, "muted", align="center", min_size=12)
    meta = " · ".join(part for part in (slide.get("presenter"), slide.get("date")) if part)
    if meta:
        b.text(MARGIN, 5.45, CONTENT_W, 0.4, meta, 11, "muted", align="center", font="latin")


LAYOUT_BUILDERS = {
    "title": _title,
    "section": _section,
    "bullets": _bullets,
    "two-col": _two_col,
    "stats": _stats,
    "timeline": _timeline,
    "quote": _quote,
    "image": _image,
    "closing": _closing,
}


def build_scene(slide: dict[str, Any], theme: Theme, page: int, total: int, deck_title: str) -> Scene:
    builder = Builder(theme, slide, page, total, deck_title)
    LAYOUT_BUILDERS[slide["layout"]](builder)
    return builder.scene
