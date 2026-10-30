# 运行手册：ppt-agent

## 1. 环境

- Python 3.10+（开发机为 3.11.8）
- 依赖：`python-pptx==1.0.2`、`lxml==5.2.2`、`Pillow==10.2.0`
- 不需要 LibreOffice；预览用浏览器打开 `preview.html`
- 可选：Chrome，用于把 HTML 预览截成图做人工复核

```bash
cd ppt-agent
python3 -m pip install -r requirements.txt
```

## 2. 第一次跑通

```bash
make run          # 离线模式，生成 tmp/demo/decks/demo/
make evals        # 37 条评测
make test         # 33 条单元测试
make check        # 结构自检
```

产物：

```
tmp/demo/decks/demo/
├── brief.json
├── outline.json
├── deck.json
├── deck.pptx      ← 交付物
├── preview.html   ← 浏览器打开
├── deck.md        ← 讲稿
├── qa.json
└── run.jsonl
```

## 3. 接真实模型

```bash
export PPT_PROVIDER=openai
export PPT_BASE_URL=https://api.deepseek.com/v1
export PPT_MODEL=deepseek-chat
export PPT_API_KEY=sk-...        # 只放在 shell 或 .env，不入库

python3 src/ppt.py --root out --slug q4 init --topic "季度复盘" --slides 12 --points "收入增长 12%;交付延期;聚焦两个行业" --force
python3 src/ppt.py --root out --slug q4 pipeline
```

换模型只改环境变量；提示词仍在 `prompts/`，改完必须：

```bash
make evals && make baseline
```

## 4. 日常命令

```bash
# 查看进度
python3 src/ppt.py --root tmp/demo --slug demo status

# 只重渲染（改主题、改版式参数后）
python3 src/ppt.py --root tmp/demo --slug demo render --theme ocean

# 质检，阻断项退出码 1
python3 src/ppt.py --root tmp/demo --slug demo check --json

# 回读任意 PPTX
python3 src/ppt.py inspect some.pptx --json
```

## 5. 日志与可观测

- 每阶段追加一行 JSON 到 `decks/<slug>/run.jsonl`：`ts`、`trace_id`、`stage`、`ms`、`provider`、`usage`（prompt/completion tokens）。
- 失败不写 trace 到 stdout，只返回结构化 `error`；排查时先看 `qa.json` 的 findings，再看 `run.jsonl` 的耗时与 token。
- 30 页 deck 渲染约 0.7s；一次真实模型生成约 20–60s，取决于模型。

## 6. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `UNKNOWN_THEME` | 主题名拼错或路径不存在 | 用 `swiss/ocean/warm/ink`，或检查 JSON 路径 |
| `LOW_CONTRAST_THEME` | 自定义主题正文对比度 <4.5 | 调深前景或调浅背景 |
| `OVERFLOW` | 某页文字太多 | 删要点、缩短句子，或把页数调大 |
| `TITLE_TOO_LONG` | 标题超过 34 字宽（封面 44） | 压到 20 字以内 |
| `IMAGE_NOT_FOUND` | 图片路径相对当前目录不对 | 用绝对路径或相对项目根目录 |
| `MOCK_NO_LLM` | 在 mock 模式下调了模型接口 | 设 `PPT_PROVIDER=openai` |
| `HTTP_401` | 密钥错误 | 重新导出 `PPT_API_KEY` |
| PPTX 打开字体不对 | 本机没有 PingFang SC | 改主题 `font_title/font_body` 为本机字体 |
| 页数与预期差 1 | 模型多写/少写了一页 | 看 `outline.json`，重跑 outline 或调 brief |

## 7. 回滚

- 代码：git 回到上一个 tag（`v0.1.0`），产物目录不受影响。
- 提示词：`prompts/` 与代码同仓，回滚代码即回滚提示词。
- 产物：每个 deck 目录自包含，删掉目录即可重来；`tmp/` 不入库。
- 模型切换导致质量下降：把 `PPT_MODEL` 改回上一个值，重跑 `make evals` 对比。

## 8. 发布前检查

```bash
make test && make evals && make check
```

- 37/37 通过，基线无回归。
- `qa.json` 对示例 deck 为 0 阻断。
- 没有 `PPT_API_KEY` 出现在仓库（`check-structure.py` 会扫）。
