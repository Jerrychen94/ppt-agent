"""渲染场景：版式只产出与后端无关的图元，PPTX 与 HTML 共用同一份几何。

这样预览所见即所得：HTML 预览、QA 溢出判断、PPTX 最终输出都读同一组坐标。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .textfit import fit_text, fit_stack
from .theme import Theme

EMU_PER_INCH = 914400


@dataclass
class TextBox:
    x: float
    y: float
    w: float
    h: float
    text: str
    lines: list[str]
    size: float
    color: str
    bold: bool = False
    align: str = "left"
    anchor: str = "top"
    font: str = "body"
    spacing: float = 1.32
    overflow: bool = False


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float
    fill: str
    line: str | None = None
    line_width: float = 0.0
    radius: float = 0.0


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    width: float = 1.0


@dataclass
class Picture:
    x: float
    y: float
    w: float
    h: float
    path: str


@dataclass
class Scene:
    slide_id: str
    layout: str
    bg: str
    title: str = ""
    elements: list[Any] = field(default_factory=list)
    notes: str = ""
    warnings: list[dict[str, str]] = field(default_factory=list)


class Builder:
    """版式构造器：负责坐标、配色别名与文本适配。"""

    def __init__(self, theme: Theme, slide: dict[str, Any], page: int, total: int, deck_title: str = ""):
        self.theme = theme
        self.slide = slide
        self.page = page
        self.total = total
        self.deck_title = deck_title
        self.scene = Scene(
            slide_id=str(slide.get("id") or f"s{page:02d}"),
            layout=str(slide.get("layout") or ""),
            bg=theme.bg,
            title=str(slide.get("title") or ""),
            notes=str(slide.get("notes") or ""),
        )

    # ------------------------------------------------------------ 基础图元

    def color(self, value: str) -> str:
        aliases = {
            "fg": self.theme.fg,
            "muted": self.theme.muted,
            "accent": self.theme.accent,
            "bg": self.theme.bg,
            "card": self.theme.card,
        }
        return aliases.get(value, value)

    def background(self, color: str | None = None) -> None:
        self.scene.bg = self.color(color or "bg")

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str,
        *,
        line: str | None = None,
        line_width: float = 0.0,
        radius: float = 0.0,
    ) -> Rect:
        element = Rect(x, y, w, h, self.color(fill), self.color(line) if line else None, line_width, radius)
        self.scene.elements.append(element)
        return element

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = "fg", width: float = 1.0) -> Line:
        element = Line(x1, y1, x2, y2, self.color(color), width)
        self.scene.elements.append(element)
        return element

    def picture(self, x: float, y: float, w: float, h: float, path: str) -> Picture | None:
        from pathlib import Path

        source = Path(path).expanduser()
        if not source.is_file():
            self.scene.warnings.append(
                {"code": "IMAGE_NOT_FOUND", "message": f"找不到图片: {path}", "hint": "检查 image 路径"}
            )
            self.rect(x, y, w, h, "card")
            self.text(x, y + h / 2 - 0.25, w, 0.5, "图片缺失", 13, "muted", align="center")
            return None
        element = Picture(x, y, w, h, str(source))
        self.scene.elements.append(element)
        return element

    def text(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        text: str,
        size: float,
        color: str = "fg",
        *,
        bold: bool = False,
        align: str = "left",
        anchor: str = "top",
        font: str = "body",
        min_size: float | None = None,
        spacing: float = 1.32,
    ) -> TextBox | None:
        content = "" if text is None else str(text)
        if not content.strip():
            return None
        min_size = min(size, min_size or max(9.0, size * 0.58))
        fitted, lines, ok = fit_text(
            content,
            width_pt=max(w * 72 - 2, 20),
            height_pt=max(h * 72 - 2, 12),
            max_pt=size,
            min_pt=min_size,
            spacing=spacing,
        )
        box = TextBox(
            x=x,
            y=y,
            w=w,
            h=h,
            text=content,
            lines=lines,
            size=fitted,
            color=self.color(color),
            bold=bold,
            align=align,
            anchor=anchor,
            font=font,
            spacing=spacing,
            overflow=not ok,
        )
        if not ok:
            self.scene.warnings.append(
                {
                    "code": "OVERFLOW",
                    "message": f"文本放不下（最小字号仍溢出）: {content[:24]}",
                    "hint": "缩短文案或拆页",
                }
            )
        self.scene.elements.append(box)
        return box

    def text_lines(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        lines: list[str],
        size: float,
        color: str = "fg",
        *,
        bold: bool = False,
        align: str = "left",
        anchor: str = "top",
        font: str = "body",
        spacing: float = 1.32,
    ) -> TextBox:
        box = TextBox(
            x=x,
            y=y,
            w=w,
            h=h,
            text="\n".join(lines),
            lines=lines,
            size=size,
            color=self.color(color),
            bold=bold,
            align=align,
            anchor=anchor,
            font=font,
            spacing=spacing,
        )
        self.scene.elements.append(box)
        return box

    # ------------------------------------------------------------ 组合件

    def bullet_stack(
        self,
        items: list[str],
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        size: float = 21.0,
        min_size: float = 14.0,
        color: str = "fg",
        marker: str = "accent",
        gap: float = 0.24,
    ) -> bool:
        """竖排要点，统一字号；返回是否放得下。"""
        if not items:
            return True
        width_pt = max(w * 72 - 2, 20)
        height_pt = max(h * 72 - 2, 12)
        fitted, wrapped, ok = fit_stack(items, width_pt, height_pt, size, min_size, gap * 72)
        cursor = y
        for lines in wrapped:
            line_h = len(lines) * fitted * 1.32 / 72
            self.rect(x - 0.38, cursor + fitted / 72 * 0.42, 0.14, 0.14, marker, radius=0.02)
            self.text_lines(x, cursor, w, max(line_h, 0.3), lines, fitted, color)
            cursor += line_h + gap
        if not ok:
            self.scene.warnings.append(
                {
                    "code": "OVERFLOW",
                    "message": f"要点过多放不下（{len(items)} 条）",
                    "hint": "减少要点或拆页",
                }
            )
        return ok

    def footer(self) -> None:
        if not self.deck_title and not self.page:
            return
        color = "muted"
        self.text(0.85, 6.92, 8.0, 0.3, self.deck_title[:40], 8.5, color, font="latin")
        self.text(10.4, 6.92, 2.1, 0.3, f"{self.page:02d} / {self.total:02d}", 8.5, color, align="right", font="latin")

    def header(self, title: str, kicker: str = "", *, title_size: float = 30.0) -> None:
        if kicker:
            self.text(0.85, 0.52, 11.6, 0.3, kicker.upper(), 10.5, "accent", bold=True, font="latin")
        self.text(0.85, 0.9, 11.6, 0.92, title, title_size, "fg", bold=True, min_size=19)
        self.line(0.85, 1.92, 2.75, 1.92, "accent", 2.0)
