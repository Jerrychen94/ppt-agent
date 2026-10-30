# 设计：ppt-agent

## 1. 问题判断

自动做 PPT 的难点不在“写字”，而在三件事同时成立：

1. **内容有判断**：一页一个观点，标题是结论，不是目录。
2. **版式不塌**：文本不溢出、层级清楚、整套节奏有变化。
3. **结果可编辑**：交付物必须是原生 PPTX，而不是一堆截图。

大模型擅长第 1 件，不擅长第 2、3 件——让它直接写 python-pptx 代码，最常见的失败是坐标拍脑袋、文字压出边界、十页长一个样。所以本项目的分工是：**模型负责内容，代码负责几何**。

## 2. 借鉴了哪些开源项目

### 2.1 PPTAgent（中科院软件所，EMNLP 2025）

- 仓库：<https://github.com/icip-cas/PPTAgent>，论文：<https://arxiv.org/abs/2501.03936>
- 核心：两阶段——先分析参考 PPT 的版式与功能类型，再基于选中的参考页**生成编辑动作**；配套 PPTEval 从 Content、Design、Coherence 三个维度评估。
- 借来的：
  - **两阶段生成**：本项目拆成 `outline`（骨架）与 `compose`（成稿），中间落盘可检查。
  - **三维质检**：内容（标题/要点/讲稿）、设计（溢出/密度/对比度）、连贯（重复标题/版式节奏）。
  - **编辑式而非重写式**：版式确定后只填字段，模型不碰坐标。
- 没借的：模板归纳需要参考 PPTX 与视觉模型，链路重；本版先用内置版式，把“参考模板”留到下一版。

### 2.2 DeepPresenter（ACL 2026，同一团队）

- 论文：<https://arxiv.org/abs/2602.22839>
- 核心：环境 grounded 的反思——先生成、再在真实环境里看结果、再修。
- 借来的：**渲染后回读校验**。本项目的 `render` 会用 python-pptx 重新打开文件，确认页数、标题、备注真的写进去了，而不是假定保存成功。
- 没借的：沙箱内 20+ 工具与自主研究；本版把输入限定为 brief，不做联网检索。

### 2.3 Presenton

- 仓库：<https://github.com/presenton/presenton>（Apache 2.0）
- 核心：自托管 AI PPT 生成，HTML + Tailwind 模板，导出可编辑 PPTX，提供 API 与 MCP。
- 借来的：
  - **主题令牌**（背景/前景/强调/卡片/字体）驱动整套视觉，而不是每页写死颜色。
  - **命令 + JSON 契约**的调用方式，方便被上层系统集成。
  - **可编辑导出**是硬要求。
- 没借的：HTML 模板 + 浏览器截图转 PPTX 的路线。它灵活，但转换层会丢可编辑性；本项目直接生成 PPTX 原生形状。

### 2.4 presentation_agent

- 仓库：<https://github.com/xueyouluo/presentation_agent>
- 核心：HTML 幻灯片 + 截图 + 视觉反馈循环。
- 借来的：**HTML 预览作为人工复核入口**。同一份几何同时渲染 PPTX 与 HTML，改了版式一眼能看出来。
- 没借的：把截图回喂多模态模型做评审。v1 用确定性测量替代，成本低、可回归。

### 2.5 基础库

- [python-pptx](https://github.com/scanny/python-pptx)：写 PPTX 原生形状、文本框、备注。
- Pillow：只用于读取图片宽高，做等比缩放。

## 3. 架构与六层对应

```
brief.json ──outline──▶ outline.json ──compose──▶ deck.json
                                                    │
                                          build_scenes（纯几何）
                                                    │
                        ┌───────────────────────────┼───────────────────────────┐
                        ▼                           ▼                           ▼
                    deck.pptx                  preview.html                  deck.md
                        └───────────────────────┬───────────────────────────┘
                                                ▼
                                             qa.json
```

| 层 | 本项目的落点 |
|---|---|
| L1 指令 | `prompts/system.md`、`outline.md`、`compose.md`；规则写成清单 |
| L2 能力 | `providers.py`（模型）、`render.py`（PPTX/HTML/MD）、`textfit.py`（测量） |
| L3 编排 | `stages.py`：init → outline → compose → render → check |
| L4 知识 | 无检索；brief 是唯一事实源，数字必须来自 brief |
| L5 评测 | `evals/` 37 条，四类分层，含 10 条负例 |
| L6 运行 | `cli.py`、`run.jsonl` 结构化日志、环境变量配置 |

## 4. 关键设计

### 4.1 确定性版式引擎

模型只产出结构化字段（版式、标题、要点、数据、讲稿），坐标由 9 个版式函数计算：

| 版式 | 用途 |
|---|---|
| `title` | 封面 |
| `section` | 章节过渡 |
| `bullets` | 要点页 |
| `two-col` | 左要点 + 右结论卡 |
| `stats` | 3–4 个关键数字 |
| `timeline` | 3–5 步流程 |
| `quote` | 金句 |
| `image` | 图文 |
| `closing` | 结尾 |

所有坐标以英寸为单位，16:9（13.333 × 7.5）。版心左右各 0.85 英寸，页脚固定在 6.92。

### 4.2 Scene：一份几何，三种输出

版式函数产出与后端无关的 `Scene`（文本框、矩形、线、图片）。PPTX、HTML、QA 都读同一份 Scene：

- 预览与交付物不会“看起来不一样”。
- 溢出判断只做一次，不存在“QA 说没事、导出却压字”。
- 新增导出格式（PDF、Keynote）只需再写一个 renderer。

### 4.3 文本适配

`textfit.py` 用字符宽度模型估算：CJK/全角 1 em，拉丁按字符类别取 0.26–0.82 em，行高 1.32 倍。对每个文本框从最大字号向下试，直到放得下；仍放不下就标记 `OVERFLOW`，由质检阻断。

估算刻意保守：实际 PowerPoint 单倍行距约 1.2 倍，估算用 1.32，宁可留白。

### 4.4 离线 mock

`mock.py` 用 brief 的要点做确定性成稿，保证：

- 没有 API key 也能 `make run` 与跑完整评测；
- 评测结果与模型无关，回归信号稳定；
- 模型不可用时至少能交出一份结构完整的稿子。

mock 不是“假装有模型”，它在输出里明确标注 `provider: mock`。

### 4.5 失败显式

- 结构问题（页数、版式、章节为空、主题不存在）在写文件前抛错，带 `code/message/hint`。
- 视觉问题（溢出、标题过长、重复标题）进 `qa.json`；阻断项让 `check`/`pipeline` 退出码为 1。
- 模型输出不合规时，带错误信息重试一次；仍失败就报错，不“尽量解析”。

## 5. 控制流与数据形状

| 阶段 | 输入 | 输出 | 失败 |
|---|---|---|---|
| init | brief | `brief.json` | 校验错误 |
| outline | brief | `outline.json` | 模型 JSON 错误 / 页数越界 |
| compose | brief + outline | `deck.json` | 缺字段 / 版式非法 |
| render | deck | `deck.pptx`、`preview.html`、`deck.md`、`qa.json` | 图片缺失 / 主题非法 |
| check | deck | `qa.json` | 有阻断项时退出码 1 |

## 6. 失败设计

| 情况 | 策略 | 用户看到 |
|---|---|---|
| 模型超时/5xx | 重试 2 次，指数退避 | `UPSTREAM_ERROR` + 检查网络提示 |
| 模型输出非 JSON | 去围栏、截取首尾大括号；失败重试一次 | `INVALID_JSON` |
| 输出结构不合规 | 带错误反馈重试一次 | `INVALID_OUTLINE` / `INVALID_DECK` |
| 输入超长 | 入口校验 | `FIELD_TOO_LONG` |
| 图片不存在 | 版式画占位并记录 | `IMAGE_NOT_FOUND`（阻断） |
| 文本放不下 | 缩到最小字号后标记 | `OVERFLOW`（阻断） |
| 主题缺失/对比度不足 | 加载时校验 | `UNKNOWN_THEME` / `LOW_CONTRAST_THEME` |

## 7. 成本与性能

- 一次生成 2 次模型调用（outline + compose），约 6–10k 输出 token；离线模式 0 调用。
- 30 页 deck 渲染 < 1 秒（本机 Python 3.11）。
- 成本上限：单次 ≤ 2 次调用、每次 ≤ 7000 输出 token；无自动重试风暴。

## 8. 评测方案

- 37 条用例，分层：简单 20%、正常 45%、困难 20%、负例/边界 30%+。
- 判分：确定性断言（JSON 路径、退出码、关键字符串），不做 LLM judge。
- 覆盖：入口校验、页数边界（3/30）、主题、英文、图片缺失、非法版式、重复标题、溢出、讲稿缺失、磁盘状态（重复 init）。
- 基线：`evals/baseline.json`，`make evals` 自动对比，跌幅 >5 个百分点判回归。

## 9. 非目标与下一步

**这一版不做**：在线编辑、模板归纳、配图生成、图表、多模态评审。

**下一步优先级**：

1. 模板导入：从一份参考 PPTX 提取母版与占位符，走 PPTAgent 的编辑式路线。
2. 视觉评审：渲染成 PNG，用多模态模型按 rubric 打分，只做提醒不阻断。
3. 图表版式：接入 python-pptx chart，支持柱状/折线/环形。
4. 文档输入：从 Markdown/PDF 抽取要点，进入 brief。
