"""渲染后端：同一份 Scene 输出 PPTX、HTML 预览与 Markdown 讲稿。"""

from __future__ import annotations

import base64
import html
import os
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from lxml import etree

from .layouts import build_scene
from .scene import Line, Picture, Rect, Scene, TextBox
from .theme import Theme

ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
ANCHOR = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}


def build_scenes(deck: dict[str, Any], theme: Theme) -> list[Scene]:
    meta = deck.get("meta", {})
    slides = deck["slides"]
    total = len(slides)
    scenes: list[Scene] = []
    section_no = 0
    for index, slide in enumerate(slides, 1):
        merged = dict(slide)
        merged.setdefault("audience", meta.get("audience", ""))
        merged.setdefault("presenter", meta.get("presenter", ""))
        merged.setdefault("date", meta.get("date", ""))
        if slide["layout"] == "section":
            section_no += 1
            merged["_section_no"] = section_no
        scenes.append(build_scene(merged, theme, index, total, str(meta.get("title") or "")))
    return scenes


def _rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value.lstrip("#").upper())


def _set_run_font(run, name: str, ea_name: str, size: float, color: str, bold: bool) -> None:
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = name
    run.font.color.rgb = _rgb(color)
    rpr = run._r.get_or_add_rPr()
    for tag, typeface in (("a:ea", ea_name), ("a:cs", name)):
        node = rpr.find(qn(tag))
        if node is None:
            node = etree.SubElement(rpr, qn(tag))
        node.set("typeface", typeface)


def render_pptx(deck: dict[str, Any], theme: Theme, path: Path) -> dict[str, Any]:
    scenes = build_scenes(deck, theme)
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    for scene in scenes:
        slide = prs.slides.add_slide(blank)
        background = slide.background.fill
        background.solid()
        background.fore_color.rgb = _rgb(scene.bg)

        for element in scene.elements:
            if isinstance(element, Rect):
                shape = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE if element.radius else MSO_SHAPE.RECTANGLE,
                    Inches(element.x),
                    Inches(element.y),
                    Inches(element.w),
                    Inches(element.h),
                )
                shape.fill.solid()
                shape.fill.fore_color.rgb = _rgb(element.fill)
                if element.line:
                    shape.line.color.rgb = _rgb(element.line)
                    shape.line.width = Pt(element.line_width or 1)
                else:
                    shape.line.fill.background()
                if element.radius and shape.adjustments:
                    shape.adjustments[0] = min(0.5, element.radius / max(min(element.w, element.h), 0.01))
            elif isinstance(element, Line):
                connector = slide.shapes.add_connector(
                    1, Inches(element.x1), Inches(element.y1), Inches(element.x2), Inches(element.y2)
                )
                connector.line.color.rgb = _rgb(element.color)
                connector.line.width = Pt(element.width)
            elif isinstance(element, Picture):
                try:
                    slide.shapes.add_picture(element.path, Inches(element.x), Inches(element.y), Inches(element.w), Inches(element.h))
                except Exception:
                    box = slide.shapes.add_shape(
                        MSO_SHAPE.RECTANGLE, Inches(element.x), Inches(element.y), Inches(element.w), Inches(element.h)
                    )
                    box.fill.solid()
                    box.fill.fore_color.rgb = _rgb(theme.card)
                    box.line.fill.background()
            elif isinstance(element, TextBox):
                box = slide.shapes.add_textbox(Inches(element.x), Inches(element.y), Inches(element.w), Inches(element.h))
                frame = box.text_frame
                frame.word_wrap = True
                frame.auto_size = MSO_AUTO_SIZE.NONE
                frame.margin_left = 0
                frame.margin_right = 0
                frame.margin_top = 0
                frame.margin_bottom = 0
                frame.vertical_anchor = ANCHOR.get(element.anchor, MSO_ANCHOR.TOP)
                paragraph = frame.paragraphs[0]
                paragraph.alignment = ALIGN.get(element.align, PP_ALIGN.LEFT)
                paragraph.line_spacing = 1.0
                paragraph.space_before = Pt(0)
                paragraph.space_after = Pt(0)
                run = paragraph.add_run()
                run.text = element.text
                name = theme.font_title if element.font == "title" else theme.font_latin
                ea_name = theme.font_title if element.font == "title" else theme.font_body
                _set_run_font(run, name, ea_name, element.size, element.color, element.bold)

        if scene.notes:
            slide.notes_slide.notes_text_frame.text = scene.notes

    prs.core_properties.title = str(deck.get("meta", {}).get("title") or "")
    prs.core_properties.author = "ppt-agent"
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))
    return verify_pptx(path)


def verify_pptx(path: Path) -> dict[str, Any]:
    """回读 PPTX，确认页数、文本与备注真的写进去了。"""
    prs = Presentation(str(path))
    slides = []
    for index, slide in enumerate(prs.slides, 1):
        entries = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text.strip()
            if not text:
                continue
            sizes = [
                run.font.size.pt
                for paragraph in shape.text_frame.paragraphs
                for run in paragraph.runs
                if run.font.size is not None
            ]
            entries.append({"text": text, "size": max(sizes) if sizes else 0.0, "top": int(shape.top or 0)})
        notes = ""
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        slides.append({"index": index, "texts": [item["text"] for item in entries], "entries": entries, "notes": notes})

    def _title(entries: list[dict[str, Any]]) -> str:
        def usable(item: dict[str, Any]) -> bool:
            text = item["text"].strip()
            return len(text) > 1 and not text.replace(" ", "").isdigit() and not text.startswith("SECTION ")

        pool = [item for item in entries if usable(item) and item["size"] >= 20]
        if not pool:
            pool = [item for item in entries if usable(item)] or entries
        if not pool:
            return ""
        return min(pool, key=lambda item: item["top"])["text"]

    titles = [_title(item["entries"]) for item in slides]
    for item in slides:
        item.pop("entries", None)

    return {
        "slides": len(slides),
        "bytes": path.stat().st_size,
        "titles": titles,
        "notes_count": sum(1 for item in slides if item["notes"]),
        "details": slides,
    }


def _picture_src(path: str, html_path: Path) -> str:
    source = Path(path)
    try:
        size = source.stat().st_size
        if size <= 4 * 1024 * 1024:
            import mimetypes

            mime = mimetypes.guess_type(source.name)[0] or "image/png"
            data = base64.b64encode(source.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"
    except OSError:
        pass
    return Path(os.path.relpath(source, html_path.parent)).as_posix()


def _html_element(element: Any, theme: Theme, html_path: Path) -> str:
    if isinstance(element, Rect):
        radius = f"border-radius:{element.radius * 96:.1f}px;" if element.radius else ""
        border = f"border:{(element.line_width or 1) * 96 / 72:.1f}px solid {element.line};" if element.line else ""
        return (
            f'<div class="el" style="left:{element.x * 96:.2f}px;top:{element.y * 96:.2f}px;'
            f'width:{element.w * 96:.2f}px;height:{element.h * 96:.2f}px;background:{element.fill};{radius}{border}"></div>'
        )
    if isinstance(element, Line):
        width = ((element.x2 - element.x1) ** 2 + (element.y2 - element.y1) ** 2) ** 0.5
        angle = 0.0
        if abs(element.x2 - element.x1) > 1e-6:
            import math

            angle = math.degrees(math.atan2(element.y2 - element.y1, element.x2 - element.x1))
        return (
            f'<div class="el" style="left:{element.x1 * 96:.2f}px;top:{element.y1 * 96:.2f}px;'
            f'width:{width * 96:.2f}px;height:{max(element.width, 1):.2f}px;background:{element.color};'
            f'transform-origin:0 50%;transform:rotate({angle:.2f}deg);"></div>'
        )
    if isinstance(element, Picture):
        src = _picture_src(element.path, html_path)
        return (
            f'<img class="el" src="{src}" style="left:{element.x * 96:.2f}px;top:{element.y * 96:.2f}px;'
            f'width:{element.w * 96:.2f}px;height:{element.h * 96:.2f}px;object-fit:contain;" />'
        )
    if isinstance(element, TextBox):
        font = theme.font_title if element.font == "title" else theme.font_body
        justify = {"top": "flex-start", "middle": "center", "bottom": "flex-end"}[element.anchor]
        lines = html.escape("\n".join(element.lines))
        return (
            f'<div class="el txt" style="left:{element.x * 96:.2f}px;top:{element.y * 96:.2f}px;'
            f'width:{element.w * 96:.2f}px;height:{element.h * 96:.2f}px;'
            f'font-family:{html.escape(font)};font-size:{element.size * 96 / 72:.2f}px;'
            f'color:{element.color};font-weight:{700 if element.bold else 400};'
            f'text-align:{element.align};justify-content:{justify};line-height:{element.spacing};">'
            f"{lines}</div>"
        )
    return ""


def render_html(deck: dict[str, Any], theme: Theme, path: Path) -> dict[str, Any]:
    scenes = build_scenes(deck, theme)
    meta = deck.get("meta", {})
    blocks = []
    for scene in scenes:
        elements = "".join(_html_element(element, theme, path) for element in scene.elements)
        blocks.append(f'<section class="slide" style="background:{scene.bg}">{elements}</section>')
    title = html.escape(str(meta.get("title") or "deck"))
    document = f"""<!doctype html>
<html lang="{html.escape(str(meta.get('language') or 'zh'))}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0e0f12; color:#ddd; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }}
  header {{ padding:22px 28px 6px; }}
  header h1 {{ font-size:18px; margin:0 0 4px; font-weight:600; }}
  header p {{ margin:0; color:#8b8f98; font-size:12px; }}
  main {{ padding:18px 0 60px; }}
  .wrap {{ width:min(1280px, 94vw); margin:0 auto; }}
  .frame {{ width:1280px; height:720px; transform-origin:top left; margin:0 auto 26px; box-shadow:0 10px 40px rgba(0,0,0,.45); }}
  .slide {{ position:relative; width:1280px; height:720px; overflow:hidden; }}
  .el {{ position:absolute; }}
  .txt {{ display:flex; flex-direction:column; white-space:pre; overflow:hidden; }}
  @media print {{
    body {{ background:#fff; }} header {{ display:none; }} main {{ padding:0; }}
    .wrap {{ width:auto; }} .frame {{ margin:0; box-shadow:none; page-break-after:always; }}
    @page {{ size:13.333in 7.5in; margin:0; }}
  }}
</style>
</head>
<body>
<header><h1>{title}</h1><p>{len(scenes)} 页 · 主题 {html.escape(theme.name)} · 由 ppt-agent 生成</p></header>
<main><div class="wrap">
{''.join(f'<div class="frame">{block}</div>' for block in blocks)}
</div></main>
<script>
function fit() {{
  document.querySelectorAll('.frame').forEach(function (frame) {{
    var scale = frame.parentElement.clientWidth / 1280;
    frame.style.transform = 'scale(' + scale + ')';
    frame.style.height = (720 * scale) + 'px';
  }});
}}
window.addEventListener('resize', fit); fit();
</script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return {"bytes": path.stat().st_size, "slides": len(scenes)}


def render_markdown(deck: dict[str, Any], path: Path) -> dict[str, Any]:
    meta = deck.get("meta", {})
    lines = [f"# {meta.get('title') or '演示文稿'}", ""]
    if meta.get("audience"):
        lines.append(f"受众：{meta['audience']}  ")
    lines.append("")
    for index, slide in enumerate(deck["slides"], 1):
        lines.append(f"## {index:02d}. {slide.get('title') or ''}")
        if slide.get("subtitle"):
            lines.append(f"*{slide['subtitle']}*")
        lines.append("")
        for bullet in slide.get("bullets") or []:
            lines.append(f"- {bullet}")
        for stat in slide.get("stats") or []:
            lines.append(f"- **{stat.get('value', '')}** {stat.get('label', '')}")
        for step in slide.get("steps") or []:
            lines.append(f"- **{step.get('title', '')}** {step.get('detail', '')}")
        quote = slide.get("quote") or {}
        if quote.get("text"):
            lines.append(f"> {quote['text']}")
            if quote.get("attribution"):
                lines.append(f"> — {quote['attribution']}")
        if slide.get("notes"):
            lines.append("")
            lines.append(f"> 讲稿：{slide['notes']}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"bytes": path.stat().st_size}
