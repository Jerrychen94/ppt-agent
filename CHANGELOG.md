# CHANGELOG

## 0.1.1 — 2026-10-31

仓库工程化。契约、版式与产物均未变化，评测基线不变。

### 新增

- `LICENSE`：MIT。
- GitHub Actions：Python 3.10 / 3.11 / 3.12 矩阵跑 `make test`、`make evals`、`make check`，并端到端生成示例 deck 作为构建产物。
- `scripts/`：内置评测执行器与结构自检脚本，clone 后不依赖父目录即可完成验证。
- `.editorconfig`；README 增加徽章、环境要求、参与贡献与许可证说明。

### 变更

- `make` 默认读取 `scripts/` 下的工具；要走父仓库版本可用 `make evals TOOLS=../scripts`。

## 0.1.0 — 2026-10-30

首版。

### 新增

- 流水线：`init → outline → compose → render → check`，`pipeline` 一次跑完。
- 9 种版式：title / section / bullets / two-col / stats / timeline / quote / image / closing。
- 4 套主题：swiss / ocean / warm / ink，支持自定义主题 JSON（含对比度校验）。
- 渲染：原生 PPTX（python-pptx）、自包含 HTML 预览、Markdown 讲稿；渲染后回读校验。
- 确定性文本适配：CJK 1 em、保守行高 1.32，放不下则标记 `OVERFLOW`。
- 质检 18 项：溢出、标题长度、要点密度、重复标题、版式节奏、讲稿完整度、对比度、图片缺失等。
- 模型：OpenAI 兼容接口（DeepSeek 等），失败重试 1 次并回传错误让模型修正。
- 离线 mock：无密钥可跑，输出确定性成稿。
- 评测：37 条用例（含 10 条负例），基线 `evals/baseline.json`。
- 单元测试：33 条。
- 文档：需求卡、设计（含开源项目借鉴说明）、契约、2 份 ADR、运行手册。

### 已知限制

- 不支持 4:3 与自定义画布。
- 不支持模板导入、图表、配图生成、多模态视觉评审。
- HTML 预览是几何复现，不等同于 PowerPoint 渲染结果。
