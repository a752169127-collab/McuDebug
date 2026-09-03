# START_HERE_FOR_NEW_AI

你正在接手 **MCU Debug Assistant**。

开始任何开发前，必须按顺序读取：

1. `AGENTS.md`
2. `SKILL.md`
3. `docs/state/PROJECT_STATE.yaml`
4. `docs/state/LATEST_HANDOFF.md`
5. `docs/state/ISSUE_LEDGER.md`
6. `docs/state/TEST_STATUS.md`
7. `docs/state/VERSION_HISTORY.md`
8. `docs/architecture/ADR.md`
9. `docs/architecture/PROJECT_CONTEXT.md`
10. `docs/architecture/ARCHITECTURE.md`
11. `docs/architecture/KNOWN_PITFALLS.md`
12. `CHANGELOG.md`
13. `docs/releases/README.md`，只在需要版本历史时再读取对应 Release Report
14. 当前任务相关源码与测试

**不要默认读取全部历史 Release Report。** 当前状态、最新交接和最新 Release Report 足以完成绝大多数二次开发；只有追溯某个旧设计/回归来源时才读取历史报告。

实际仓库状态优先于旧文档。

以后按 `docs/development/WORKFLOW.md` 形成闭环。默认原则是：**最小修改、只读相关上下文、证据足够即停止分析、测试达标即 STOP**。

`问题定义 → 最小证据 → Change Plan → 实现 → 自动测试 → 硬件状态 → 更新真正变化的项目记忆 → STOP`

不要只修改代码，也不要为了“完整”而每轮重写全部 Agent/Docs。每轮结束后必须让一个完全没有旧聊天记录的新 AI 也能继续开发。


> Current baseline: V0.6.17 — Manual Input Enter Confirm.
