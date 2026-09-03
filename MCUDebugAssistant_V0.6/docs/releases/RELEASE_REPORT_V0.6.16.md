# RELEASE REPORT — V0.6.16 AI Documentation Layout

## Goal

整理不断增长的工程文档，避免根目录被大量历史 Release Report 和状态文件占满，同时保持新 AI 可以直接接手二次开发。

## Changed

- `RELEASE_REPORT_*.md` → `docs/releases/`。
- `state/*` → `docs/state/`，其中 ADR 归入 `docs/architecture/ADR.md`。
- 架构/上下文/陷阱/Rendering 文档 → `docs/architecture/`。
- Workflow/Checklist/AI helper → `docs/development/`。
- 根目录仅保留 `README.md / START_HERE_FOR_NEW_AI.md / AGENTS.md / SKILL.md / CHANGELOG.md` 作为稳定文档入口。
- 新增 `docs/README.md` 与 `docs/releases/README.md`。
- `manifest.json`、Agent、Skill、Workflow、README 和所有当前路径引用同步到新布局。
- GUI 版本标题更新到 V0.6.16；运行时功能逻辑不变。

## AI Handoff Strategy

新 AI 不需要全量读取历史 Release Report。优先读取 `START_HERE_FOR_NEW_AI.md`、`docs/state/PROJECT_STATE.yaml`、`docs/state/LATEST_HANDOFF.md`、必要的 Issue/Test/ADR，然后按 `docs/releases/README.md` 精确追溯历史。

## Runtime Impact

None. 本版为工程治理/文档布局调整，不修改 J-Link single-owner、Scope acquisition/render、Watch、Memory 或 Test Automation 数据链。

## Verification

- compileall: PASS
- full pytest: 136 passed
- documentation layout regression: 5 passed
- Qt smoke: not required for pure documentation move; GUI title only
- hardware: not required; runtime target access unchanged
