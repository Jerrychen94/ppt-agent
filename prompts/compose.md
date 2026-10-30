# 任务：把骨架填成可讲的成稿

根据 brief 与 outline，为每一页补齐文案、数据与讲稿备注。版式已经定好，不要改 `layout`。

## Brief

```json
{{BRIEF}}
```

## Outline

```json
{{OUTLINE}}
```

## 每页要填的字段

| 字段 | 适用版式 | 规则 |
|---|---|---|
| subtitle | title / section / closing | 一句话，40 字以内 |
| bullets | bullets / two-col / image | 3–5 条，每条 28 字以内，动宾结构 |
| insight | two-col | 一条结论，30 字以内 |
| stats | stats | 3–4 组 `{value,label}`，value 含单位 |
| steps | timeline | 3–5 组 `{title,detail}`，title 10 字以内 |
| quote | quote | `{text,attribution}`，text 30 字以内 |
| notes | 所有页 | 40–120 字口播提示：先说什么、用什么证据、怎么过渡 |

## 要求

1. 逐页写，不要漏页；`slides` 数量与 outline 完全一致，顺序不变。
2. 标题可以微调得更像结论句，但不能超过 20 字，也不能与其它页重复。
3. 数字必须来自 brief；brief 没有的数字不要编。
4. 讲稿备注写“怎么讲”：先给结论，再给证据，最后一句过渡。
5. `meta` 里保留 title、audience、presenter、language、theme。

## 输出格式

```json
{
  "meta": {
    "title": "整套稿子的标题",
    "audience": "受众",
    "presenter": "讲者",
    "language": "zh",
    "theme": "swiss"
  },
  "slides": [
    {
      "id": "s01",
      "layout": "bullets",
      "section": "章节标题",
      "title": "结论式标题",
      "subtitle": "",
      "bullets": ["要点一", "要点二", "要点三"],
      "insight": "",
      "stats": [],
      "steps": [],
      "quote": {},
      "image": "",
      "notes": "这一页先给结论，再用两个事实支撑，最后过渡到下一页。"
    }
  ]
}
```
