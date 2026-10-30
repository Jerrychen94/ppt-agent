# 任务：设计演示文稿骨架

根据下面的 brief，输出整套稿子的页面骨架。这一阶段只定结构与标题，不展开文案。

## Brief

```json
{{BRIEF}}
```

## 要求

1. 页数等于 `slide_count`（不超过 ±1）；第 1 页必须是 `title`，最后 1 页必须是 `closing`。
2. 拆成 2–4 个章节：每个章节先放一页 `section`，再放 1–3 页内容。
3. 内容页在 `bullets`、`two-col`、`stats`、`timeline`、`quote`、`image` 之间轮换，避免连续三页同一版式。
4. 标题写成结论句，20 字以内；同一套稿子里标题不重复。
5. 每页 2–4 条 `points`，每条 30 字以内。points 写“这一页要拿出的证据”，不是目录。
6. `stats` 页的 points 给 3–4 个“数字 + 含义”；`timeline` 页的 points 给 3–5 个步骤。
7. 没有真实数据时不要用 `stats`；没有合适图片时不要用 `image`。
8. `section` 页的 `points` 写该章节要回答的问题。

## 输出格式

```json
{
  "title": "整套稿子的标题",
  "slides": [
    {
      "layout": "title",
      "title": "封面标题",
      "subtitle": "一句话价值主张",
      "section": "",
      "points": []
    },
    {
      "layout": "section",
      "title": "章节标题",
      "subtitle": "",
      "section": "章节标题",
      "points": ["这一章要回答的问题"]
    },
    {
      "layout": "bullets",
      "title": "结论式标题",
      "subtitle": "",
      "section": "章节标题",
      "points": ["证据一", "证据二", "证据三"]
    }
  ]
}
```
