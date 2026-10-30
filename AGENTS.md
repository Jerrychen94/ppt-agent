# ppt-agent 项目约定

给编码 agent 的补充约定，优先级低于仓库根 `AGENTS.md`。

## 提交前

```bash
make test && make evals && make check
```

评测全绿后再 `make baseline`。

## 改动边界

- `docs/contract.md` 是对外承诺。改字段、改版式语义、改退出码 = 主版本变化。
- 版式只加函数：在 `layouts.py` 注册新布局，并在 `model.LAYOUTS`、`checks.py` 同步；不要把坐标写进提示词。
- 提示词在 `prompts/`，每次改动都要重跑评测，并在 `CHANGELOG.md` 写明“改了什么、为什么、指标变化”。
- mock 的输出必须保持确定性；不要在 mock 里用随机数或当前时间参与内容生成。
- 新增依赖要锁版本，写进 `requirements.txt` 和 `.env.example`（如涉及配置）。

## 代码风格

- 代码、字段、错误码用英文；文档与注释用中文。
- 失败必须抛 `AgentError`（带 code/message/hint），不要 `except: pass`。
- 中文内容使用弯引号（“ ” ‘ ’），不用 ASCII 直引号。
- 新增质检项要同时加单元测试与至少一条 eval 用例。

## 产物

- `tmp/`、`.env` 不入库。
- 示例 deck 由 `make run` 生成，不提交二进制产物。
