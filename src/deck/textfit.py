"""文本排版估算：不依赖字体文件，跨机器结果一致。

PPTX 不会替我们换行到“刚好不溢出”，所以版式引擎必须自己算：
先把字号缩到能放下，再交给 python-pptx 绘制。估算刻意偏保守
（行高 1.32 倍、CJK 按 1 em），宁可留白，也不要压字。
"""

from __future__ import annotations

EMU_PER_INCH = 914400
PT_PER_INCH = 72.0
LINE_SPACING = 1.32


def emu_to_pt(value: float) -> float:
    return value / EMU_PER_INCH * PT_PER_INCH


def pt_to_emu(value: float) -> int:
    return int(round(value / PT_PER_INCH * EMU_PER_INCH))


def char_width_em(ch: str) -> float:
    """单字符宽度（em）。CJK/全角按 1 em，拉丁按经验值。"""
    code = ord(ch)
    if code >= 0x2E80:  # CJK、假名、全角标点、emoji
        return 1.0
    if ch in " \t":
        return 0.28
    if ch in ".,;:!?'\"()[]|":
        return 0.26
    if ch in "ilI":
        return 0.28
    if ch in "mwMW@%":
        return 0.82
    if ch.isdigit():
        return 0.56
    if ch.isupper():
        return 0.62
    return 0.52


def measure(text: str, size_pt: float) -> float:
    """文本单行宽度（pt）。"""
    return sum(char_width_em(ch) for ch in text) * size_pt


def wrap_text(text: str, size_pt: float, width_pt: float) -> list[str]:
    """按宽度折行，CJK 可任意断，拉丁尽量在空格断。"""
    width_pt = max(width_pt, size_pt * 2)
    lines: list[str] = []
    for para in str(text).split("\n"):
        if not para:
            lines.append("")
            continue
        buf = ""
        buf_w = 0.0
        for ch in para:
            w = char_width_em(ch) * size_pt
            if buf and buf_w + w > width_pt:
                if ch == " ":
                    lines.append(buf.rstrip())
                    buf, buf_w = "", 0.0
                    continue
                space = buf.rfind(" ")
                if space > 0 and space >= len(buf) * 0.45:
                    lines.append(buf[:space].rstrip())
                    buf = buf[space + 1 :] + ch
                    buf_w = measure(buf, size_pt)
                else:
                    lines.append(buf.rstrip())
                    buf, buf_w = ch, w
            else:
                buf += ch
                buf_w += w
        lines.append(buf.rstrip())
    return lines or [""]


def line_height_pt(size_pt: float, spacing: float = LINE_SPACING) -> float:
    return size_pt * spacing


def text_height_pt(lines: list[str], size_pt: float, spacing: float = LINE_SPACING) -> float:
    return max(1, len(lines)) * line_height_pt(size_pt, spacing)


def fit_text(
    text: str,
    width_pt: float,
    height_pt: float,
    max_pt: float,
    min_pt: float,
    spacing: float = LINE_SPACING,
) -> tuple[float, list[str], bool]:
    """返回 (字号, 折行结果, 是否放得下)。放不下时停在 min_pt 并标记 False。"""
    min_pt = min(min_pt, max_pt)
    size = max_pt
    while size >= min_pt - 0.01:
        lines = wrap_text(text, size, width_pt)
        if text_height_pt(lines, size, spacing) <= height_pt + 0.5:
            return size, lines, True
        size -= 1
    return min_pt, wrap_text(text, min_pt, width_pt), False


def fit_stack(
    items: list[str],
    width_pt: float,
    height_pt: float,
    max_pt: float,
    min_pt: float,
    gap_pt: float,
    spacing: float = LINE_SPACING,
) -> tuple[float, list[list[str]], bool]:
    """多条要点整体选字号：所有条目共用一个字号，放不下时返回 min_pt。"""
    if not items:
        return max_pt, [], True
    min_pt = min(min_pt, max_pt)
    size = max_pt
    while size >= min_pt - 0.01:
        wrapped = [wrap_text(item, size, width_pt) for item in items]
        total = sum(text_height_pt(lines, size, spacing) for lines in wrapped) + gap_pt * (len(items) - 1)
        if total <= height_pt + 0.5:
            return size, wrapped, True
        size -= 1
    return min_pt, [wrap_text(item, min_pt, width_pt) for item in items], False
