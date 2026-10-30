"""主题：颜色、字体与字号尺度。

配色只做“深底白字 / 浅底深字”两类，正文对比度必须 ≥ 4.5（WCAG AA）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import StageError


def parse_color(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise StageError("INVALID_COLOR", f"颜色格式不合法: {value}", "使用 #RRGGBB")
    try:
        return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise StageError("INVALID_COLOR", f"颜色格式不合法: {value}", "使用 #RRGGBB") from exc


def to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, int(v))) for v in rgb))


def blend(fg: str, bg: str, ratio: float) -> str:
    """把 fg 以 ratio 混合进 bg，用于浅色装饰块。"""
    f = parse_color(fg)
    b = parse_color(bg)
    return to_hex(tuple(f[i] * ratio + b[i] * (1 - ratio) for i in range(3)))  # type: ignore[arg-type]


def _luminance(color: str) -> float:
    rgb = [v / 255 for v in parse_color(color)]
    linear = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    l1, l2 = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    fg: str
    muted: str
    accent: str
    card: str
    font_title: str = "PingFang SC"
    font_body: str = "PingFang SC"
    font_latin: str = "Helvetica Neue"

    def tint(self, color: str, ratio: float) -> str:
        return blend(color, self.bg, ratio)

    def check(self) -> list[str]:
        """返回对比度问题；空列表表示通过。"""
        problems = []
        if contrast(self.fg, self.bg) < 4.5:
            problems.append(f"正文与背景对比度不足: {contrast(self.fg, self.bg):.2f}")
        if contrast(self.muted, self.bg) < 3.0:
            problems.append(f"辅助文字与背景对比度不足: {contrast(self.muted, self.bg):.2f}")
        if contrast(self.accent, self.bg) < 3.0:
            problems.append(f"强调色与背景对比度不足: {contrast(self.accent, self.bg):.2f}")
        return problems


THEMES: dict[str, Theme] = {
    "swiss": Theme(
        name="swiss",
        bg="#FAFAF8",
        fg="#16181D",
        muted="#6B7280",
        accent="#D92D20",
        card="#F0F0EA",
    ),
    "ocean": Theme(
        name="ocean",
        bg="#0B1B33",
        fg="#F7FAFC",
        muted="#9FB3C8",
        accent="#4CC9F0",
        card="#13294B",
    ),
    "warm": Theme(
        name="warm",
        bg="#FBF6EE",
        fg="#2B2118",
        muted="#7A6A58",
        accent="#B5471E",
        card="#F1E7D8",
    ),
    "ink": Theme(
        name="ink",
        bg="#121316",
        fg="#F5F3EE",
        muted="#A8A29A",
        accent="#F2C14E",
        card="#1D1F24",
    ),
}


def load_theme(name_or_path: str | None) -> Theme:
    name = (name_or_path or "swiss").strip()
    if not name:
        name = "swiss"
    if name in THEMES:
        return THEMES[name]
    path = Path(name).expanduser()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StageError("INVALID_THEME", f"主题文件不是合法 JSON: {exc}", "检查 JSON 格式") from exc
        try:
            theme = Theme(**data)
        except TypeError as exc:
            raise StageError("INVALID_THEME", f"主题字段不完整: {exc}", "参考 themes/swiss.json") from exc
        problems = theme.check()
        if problems:
            raise StageError("LOW_CONTRAST_THEME", "；".join(problems), "提高对比度后重试")
        return replace(theme)
    raise StageError(
        "UNKNOWN_THEME",
        f"未知主题: {name}",
        "可选 " + "、".join(sorted(THEMES)) + "，或传入主题 JSON 路径",
    )
