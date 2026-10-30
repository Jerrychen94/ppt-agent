# 契约：ppt-agent

> 对外承诺。契约变化 = 主版本变化。所有失败都输出 JSON，并带 `error.code / message / hint`。

## 1. 调用方式

```bash
# 常规 CLI
python3 src/ppt.py --root <dir> --slug <slug> init --topic "..." [--brief brief.json]
python3 src/ppt.py --root <dir> --slug <slug> outline|compose|render|check|status
python3 src/ppt.py --root <dir> --slug <slug> pipeline [--brief brief.json]

# 评测/被脚本调用：stdin 读 JSON，stdout 写 JSON
python3 src/ppt.py eval < request.json
```

- 全局参数：`--root`（默认 `.`）、`--slug`、`--provider mock|openai`、`--json`、`--theme`。
- 非 `--json` 时输出人读摘要；所有阶段都返回结构化对象，`--json` 输出完整对象。
- `eval` 永远只输出一行 JSON，便于评测器取最后一行解析。

## 2. 输入

### 2.1 brief（`init` / `pipeline` / eval）

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| topic | string | 是 | 1–80 字 | 主题；同时作为封面标题与 slug 来源 |
| goal | string | 否 | ≤160 字 | 汇报目标，进入封面副标题与讲稿 |
| audience | string | 否 | ≤80 字 | 受众 |
| presenter | string | 否 | ≤40 字 | 讲者 |
| date | string | 否 | ≤40 字 | 日期，原样展示 |
| language | string | 否 | `zh` / `en`，默认 `zh` | 文案语言 |
| slide_count | int | 否 | 3–30，默认 10 | 页数，成品必须一致 |
| theme | string | 否 | 内置主题名或主题 JSON 路径，默认 `swiss` | 主题 |
| key_points | string[] | 否 | 0–12 条，每条 ≤60 字 | 要点；缺省时由模型或 mock 推断 |
| sections | object[] | 否 | 0–6 个；每个 `title` + `points`（1–5 条） | 自定义章节结构 |
| stats | object[] | 否 | 3–4 组 `{value,label}` | 供 `stats` 版式使用 |

示例：

```json
{
  "topic": "AI 编程助手试点",
  "goal": "说服管理层在下季度试点",
  "audience": "研发管理者",
  "language": "zh",
  "slide_count": 9,
  "theme": "swiss",
  "key_points": ["人均每周节省 4.2 小时", "评审通过率提升 18%"]
}
```

### 2.2 eval 请求

```json
{
  "cmd": "pipeline | init | outline | compose | render | check | status | inspect",
  "slug": "case-id",
  "root": "tmp/evals",
  "brief": {"topic": "..."},
  "deck": {"meta": {}, "slides": []},
  "theme": "ocean",
  "provider": "mock",
  "force": true,
  "pre": [{"cmd": "init", "slug": "case-id", "brief": {"topic": "..."}}]
}
```

- `deck` 仅用于 `render` / `check`：直接注入待检成稿。
- `pre` 按顺序先执行，用于构造“已存在 deck”这类前置状态。

## 3. 输出

### 3.1 产物

目录：`<root>/decks/<slug>/`

| 文件 | 说明 |
|---|---|
| `brief.json` | 归一化后的需求 |
| `outline.json` | 页面骨架（版式 + 标题 + 要点） |
| `deck.json` | 成稿（结构见 3.2） |
| `deck.pptx` | 16:9 原生 PPTX，可编辑 |
| `preview.html` | 自包含预览，可直接打印为 PDF |
| `deck.md` | 讲稿版 Markdown |
| `qa.json` | 质检报告 |
| `run.jsonl` | 结构化日志：ts / trace_id / stage / ms / usage |

### 3.2 deck.json

```json
{
  "meta": {
    "title": "整套稿子的标题",
    "audience": "研发管理者",
    "presenter": "Jerry",
    "language": "zh",
    "theme": "swiss",
    "provider": "mock",
    "slide_count": 9,
    "generated_at": "2026-10-30T12:00:00+00:00"
  },
  "slides": [
    {
      "id": "s03",
      "layout": "bullets",
      "section": "背景与判断",
      "title": "人均每周节省 4.2 小时",
      "subtitle": "",
      "bullets": ["代码评审一次通过率提升 18%", "先小范围试点，再逐步推广"],
      "insight": "",
      "stats": [],
      "steps": [],
      "quote": {},
      "image": "",
      "notes": "这一页先给结论，再用一个数据支撑，最后过渡到下一页。"
    }
  ]
}
```

- `layout` 取值固定 9 种：`title`、`section`、`bullets`、`two-col`、`stats`、`timeline`、`quote`、`image`、`closing`。
- `stats` 为 `[{value,label}]`；`steps` 为 `[{title,detail}]`；`quote` 为 `{text,attribution}`。
- `bullets` 允许字符串数组，也接受 `[{text}]`，落盘前会归一化。

### 3.3 阶段返回对象

```json
{
  "ok": true,
  "stage": "render",
  "slug": "demo",
  "artifacts": [".../deck.pptx", ".../preview.html"],
  "result": {},
  "findings": [],
  "gate": {"passed": true, "errors": 0, "warnings": 0, "reasons": []},
  "next": "check"
}
```

`result` 的关键字段：

| 阶段 | 字段 |
|---|---|
| init | `brief` |
| outline | `title`、`slide_count`、`layouts`、`fixes` |
| compose | `deck`（title/slide_count/layouts/titles）、`notes_ratio` |
| render | `deck`、`pptx`（slides/bytes/notes_count/titles）、`html`、`markdown`、`qa` 摘要 |
| check | `qa`（完整报告）、`stats` |
| pipeline | `deck`、`pptx`、`qa`、`steps` |
| status | `title`、`slide_count`、`board` |
| inspect | `slides`、`bytes`、`titles`、`notes_count`、`details` |

### 3.4 qa.json

```json
{
  "ok": true,
  "score": 100,
  "errors": 0,
  "warnings": 0,
  "findings": [
    {"level": "warn", "code": "DUPLICATE_TITLE", "message": "标题重复 2 次", "slide": "s05", "hint": "换一个差异化标题"}
  ],
  "stats": {"slides": 9, "characters": 647, "avg_bullets": 0.78, "notes_ratio": 1.0, "layouts": {}, "theme": "swiss"}
}
```

`level=error` 为阻断项，`warn` 只提醒。`score = 100 - 10*errors - 3*warnings`，下限 0。

## 4. 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 成功；`check` / `pipeline` 表示无阻断项 |
| 1 | 可预期失败（参数、校验、模型、质检阻断） |
| 2 | 保留给评测器的回归判定，CLI 不使用 |

## 5. 错误码

| code | 触发 | hint |
|---|---|---|
| `EMPTY_TOPIC` | topic 为空 | 用一句话说明讲什么 |
| `MISSING_TOPIC` | 缺 `--topic` 且无 `--brief` | 补参数 |
| `INVALID_BRIEF` | brief 不是对象/字段类型错 | 检查 JSON |
| `INVALID_FIELD` / `EMPTY_FIELD` | 字段类型错或为空 | 修正字段 |
| `FIELD_TOO_LONG` | 超过字段上限 | 缩短 |
| `INVALID_LANGUAGE` | 非 `zh/en` | 改语言 |
| `INVALID_SLIDE_COUNT` | 页数非整数或不在 3–30 | 改页数 |
| `TOO_MANY_POINTS` / `TOO_MANY_SECTIONS` | 要点/章节超限 | 合并 |
| `EMPTY_SECTION` | 章节没有要点 | 每章至少 1 条 |
| `INVALID_STATS` | stats 不是 3–4 组 | 补足或删减 |
| `INVALID_OUTLINE` | 骨架结构不合法 | 重跑 outline |
| `INVALID_LAYOUT` | 版式不在 9 种内 | 换合法版式 |
| `INVALID_DECK` | 成稿结构不合法 | 重跑 compose |
| `INVALID_JSON` | 输入/模型输出不是 JSON | 检查格式 |
| `DECK_NOT_FOUND` | 找不到 deck | 先 init |
| `DECK_EXISTS` | 重复 init 未加 force | 换 slug 或加 --force |
| `AMBIGUOUS_SLUG` | 多个 deck 未指定 slug | 加 --slug |
| `MISSING_FILE` / `FILE_NOT_FOUND` | 中间产物缺失 | 先跑前一步 |
| `UNKNOWN_THEME` | 主题名或路径不存在 | 用内置主题或检查路径 |
| `INVALID_THEME` / `LOW_CONTRAST_THEME` | 主题字段缺失/对比度不足 | 修 JSON |
| `INVALID_COLOR` | 颜色不是 `#RRGGBB` | 修颜色 |
| `INVALID_PROVIDER` / `MISSING_API_KEY` | provider 配置错误 | 查环境变量 |
| `HTTP_4xx/5xx` / `UPSTREAM_ERROR` | 模型接口失败 | 查密钥/网络 |
| `MOCK_NO_LLM` | mock 模式试图调模型 | 设 `PPT_PROVIDER=openai` |
| `INVALID_REQUEST` | eval 请求缺 cmd / 非 JSON | 修请求 |
| `UNKNOWN_COMMAND` | 未知命令 | 看 `--help` |
| `MISSING_PROMPT` | `prompts/` 缺文件 | 恢复仓库文件 |

质检 findings 的 code：`TITLE_TOO_LONG`、`TITLE_LONG`、`BULLET_TOO_LONG`、`BULLET_LONG`、`TOO_MANY_BULLETS`、`DENSE_SLIDE`、`EMPTY_CONTENT`、`MISSING_NOTES`、`SHORT_NOTES`、`DUPLICATE_TITLE`、`REPETITIVE_LAYOUT`、`ORPHAN_SECTION`、`OVERFLOW`、`IMAGE_NOT_FOUND`、`LAYOUT_FALLBACK`、`SLIDE_COUNT`、`MISSING_COVER`、`MISSING_CLOSING`、`LOW_CONTRAST`。

## 6. 边界与限制

| 项 | 上限 | 超出表现 |
|---|---|---|
| 页数 | 3–30 | `INVALID_SLIDE_COUNT` / `SLIDE_COUNT` |
| topic | 80 字 | `FIELD_TOO_LONG` |
| 单条要点 | 60 字 | `FIELD_TOO_LONG`（入口）；56 字宽触发 `BULLET_TOO_LONG` |
| 每页要点 | 5 条 | `TOO_MANY_BULLETS` |
| 封面标题 | 44 字宽 | `TITLE_TOO_LONG` |
| 内容页标题 | 34 字宽 | `TITLE_TOO_LONG` |
| 讲稿 | 建议 40–120 字 | 少于 20 字 `SHORT_NOTES`，为空 `MISSING_NOTES` |
| 图片 | PNG/JPG/WebP，建议 ≤4 MB | 不存在或无权限 → `IMAGE_NOT_FOUND` |
| 页脚 | 固定 8.5pt | 不参与正文适配 |
| 字号下限 | 正文 9pt、标题 19pt（封面 28pt） | 缩到下限仍放不下 → `OVERFLOW` |

坐标固定 16:9（13.333 × 7.5 英寸），不支持 4:3 或自定义尺寸——这是本版契约的一部分。

## 7. 成本预算

- 每次 `outline` 1 次调用（≤4000 输出 token），`compose` 1 次调用（≤7000 输出 token）。
- 模型失败重试最多 1 次（同一阶段），总调用 ≤4 次。
- 离线 mock 0 次调用、0 成本。
- 日志记录 prompt/completion token，便于按次核算。

## 8. 版本与兼容

- 0.1.0：首版契约。
- 新增版式、新增 CLI 命令属于次版本；`deck.json` 字段改名、版式语义变化属于主版本。
- 提示词变更不改变契约，但必须重跑 `make evals` 并更新 `CHANGELOG.md`。
