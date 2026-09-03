# WORKFLOW.md — AI 自闭环开发工作流

```text
用户任务 / Bug / 性能问题
        ↓
01 读取 State + 相关 Docs（不要全仓库无差别分析）
        ↓
02 定义目标 / Acceptance Criteria / 不可破坏行为
        ↓
03 用现有证据定位最小影响范围
        ↓
04 Change Plan（小 Diff；必要时才加临时诊断）
        ↓
05 实现
        ↓
06 compileall + pytest + targeted regression
        ↓
07 PASS ? ──否──> 只针对失败根因修复 ──┐
        │                               │
       是 <─────────────────────────────┘
        ↓
08 更新 Agent / Docs / Skill / State 中真正变化的内容
        ↓
09 Hardware 项标 PENDING_HARDWARE
        ↓
10 STOP
```

## 默认开发策略

- **最小修改优先**：不顺手重构、不新增无关抽象、不提前开发未来功能。
- **证据优先但不过度分析**：已有证据足够时立即进入方案与验证。
- **诊断不是产品功能**：临时 watchdog / 高频计时 / probe 不进入默认 Release 热路径。
- **稳定区保护**：没有明确需求或失败证据，不改 J-Link owner、协议解析、Ring Buffer 语义、Watch/AXF 稳定逻辑。
- **达标即停**：Acceptance Criteria、自动测试和必要回归通过后结束本轮。

## 每轮开发完更新

只更新真正变化的文件：

- `docs/state/PROJECT_STATE.yaml`：当前版本、焦点、Open Issues。
- `docs/state/ISSUE_LEDGER.md`：症状、证据、根因、修复、状态。
- `docs/state/VERSION_HISTORY.md`：这一版为什么存在。
- `docs/state/TEST_STATUS.md`：自动测试与硬件测试分开。
- `docs/architecture/ADR.md`：仅架构决策变化时追加。
- `docs/state/LATEST_HANDOFF.md`：让新 AI 可以直接继续。
- `CHANGELOG.md`：面向用户的版本变化。
- `AGENTS.md`：只有出现长期工程规则时更新。
- `SKILL.md`：只有出现可复用方法/经验时更新。
- `docs/*`：只有项目事实/架构真的变化时更新。
- `docs/releases/README.md`：每个 Release 更新 Current/模块历史索引；历史报告默认按需读取。

## Release Gate

- `compileall` PASS
- full `pytest` PASS
- targeted regression PASS
- state/changelog/handoff 已同步
- 硬件未验证项明确 `PENDING_HARDWARE`
- 默认 Release 热路径无临时诊断开销

达到 Gate 后 **STOP**，不要继续无目标优化。


> Current baseline: V0.6.17 — Manual Input Enter Confirm.
