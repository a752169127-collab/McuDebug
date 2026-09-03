# MCU Debug Assistant Documentation Map

本目录是工程的长期知识库。根目录的 `START_HERE_FOR_NEW_AI.md` 是 AI 接手入口。

## 快速读取

1. `../START_HERE_FOR_NEW_AI.md`
2. `state/PROJECT_STATE.yaml`
3. `state/LATEST_HANDOFF.md`
4. `state/ISSUE_LEDGER.md` / `state/TEST_STATUS.md`
5. `architecture/ADR.md` / `architecture/ARCHITECTURE.md`（需要架构背景时）
6. `releases/README.md`（需要追溯版本时）

## 目录职责

- `state/`：当前状态、Issue、测试状态、版本历史、最新交接。高频、动态。
- `architecture/`：长期设计原则、ADR、上下文、陷阱和渲染设计。低频、稳定。
- `development/`：AI/人工开发流程、发布 Checklist、交接辅助说明。
- `releases/`：各版本 Release Report。历史档案，默认不要全部读取。

## AI 上下文原则

优先使用“当前状态 + 最新交接 + 当前任务源码/测试”。只有遇到历史设计原因、回归来源或兼容性判断时，才通过 `releases/README.md` 查相关版本报告。
