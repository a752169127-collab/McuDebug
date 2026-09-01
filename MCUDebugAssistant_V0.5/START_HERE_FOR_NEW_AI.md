# START_HERE_FOR_NEW_AI

你正在接手 **MCU Debug Assistant**。

开始任何开发前，必须按顺序读取：

1. `AGENTS.md`
2. `SKILL.md`
3. `state/PROJECT_STATE.yaml`
4. `state/ISSUE_LEDGER.md`
5. `state/VERSION_HISTORY.md`
6. `state/TEST_STATUS.md`
7. `state/ADR.md`
8. `state/LATEST_HANDOFF.md`
9. `docs/PROJECT_CONTEXT.md`
10. `docs/ARCHITECTURE.md`
11. `docs/KNOWN_PITFALLS.md`
12. 当前源码、测试与最新 CHANGELOG

实际仓库状态优先于旧文档。

以后按 `WORKFLOW.md` 形成闭环。默认原则是：**最小修改、只读相关上下文、证据足够即停止分析、测试达标即 STOP**。

`问题定义 → 最小证据 → Change Plan → 实现 → 自动测试 → 硬件状态 → 更新真正变化的项目记忆 → STOP`

不要只修改代码，也不要为了“完整”而每轮重写全部 Agent/Docs。每轮结束后必须让一个完全没有旧聊天记录的新 AI 也能继续开发。
