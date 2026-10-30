"""测试共用样例。"""

from __future__ import annotations

BRIEF = {
    "topic": "AI 编程助手试点",
    "goal": "说服管理层在下季度试点",
    "audience": "研发管理者",
    "presenter": "Jerry",
    "language": "zh",
    "slide_count": 9,
    "theme": "swiss",
    "key_points": [
        "人均每周节省 4.2 小时",
        "评审通过率提升 18%",
        "上手周期从 6 周降到 3 周",
        "先在两个小组试点",
        "建立提示词规范",
        "每两周复盘数据",
    ],
}


def deck(notes: bool = True) -> dict:
    return {
        "meta": {"title": "汇报的结构", "audience": "团队", "presenter": "Jerry", "language": "zh", "theme": "swiss"},
        "slides": [
            {
                "id": "s01",
                "layout": "title",
                "title": "有效的汇报长什么样",
                "subtitle": "从结构到讲稿的五个动作",
                "notes": "开场先给结论，用一句话说明这次汇报要解决什么问题。" if notes else "",
            },
            {
                "id": "s02",
                "layout": "bullets",
                "section": "结构",
                "title": "先给结论，再给证据",
                "bullets": ["每页只讲一个观点", "标题写成结论句", "证据不超过三条"],
                "notes": "这一页先给结论，再用三个动作说明结构，最后过渡到数据页。" if notes else "",
            },
            {
                "id": "s03",
                "layout": "stats",
                "section": "结构",
                "title": "三个数字说明问题",
                "stats": [
                    {"value": "42%", "label": "决策时间缩短"},
                    {"value": "3x", "label": "复用率提升"},
                    {"value": "18", "label": "团队已试用"},
                ],
                "notes": "让数字自己说话，再解释口径与变化原因，停在最后一个数字上。" if notes else "",
            },
            {
                "id": "s04",
                "layout": "closing",
                "title": "谢谢",
                "subtitle": "欢迎交流",
                "notes": "收束三个要点，留三十秒给提问，会后把材料发到群里。" if notes else "",
            },
        ],
    }


def slide(layout: str, **overrides) -> dict:
    base = {
        "id": "s02",
        "layout": layout,
        "section": "结构",
        "title": "先给结论，再给证据",
        "subtitle": "一句话说明",
        "bullets": ["每页只讲一个观点", "标题写成结论句", "证据不超过三条"],
        "insight": "结论先行能显著降低理解成本",
        "stats": [
            {"value": "42%", "label": "决策时间缩短"},
            {"value": "3x", "label": "复用率提升"},
            {"value": "18", "label": "团队已试用"},
        ],
        "steps": [
            {"title": "试点", "detail": "两个小组先跑一个月"},
            {"title": "复盘", "detail": "对比效率与质量数据"},
            {"title": "推广", "detail": "沉淀规范后全量推开"},
        ],
        "quote": {"text": "好的汇报不是讲完，而是让听众能做决定", "attribution": "本次汇报"},
        "image": "",
        "notes": "这一页先给结论，再用三个动作说明结构，最后过渡到数据页。",
    }
    base.update(overrides)
    return base
