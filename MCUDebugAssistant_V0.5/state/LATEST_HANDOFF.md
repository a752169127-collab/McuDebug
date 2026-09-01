# LATEST_HANDOFF

## 当前版本
V0.5.4 — Symbol Completion Popup Fix（基于 V0.5.3）。

## 本轮输入
用户实机截图：Memory `Address / Symbol` 输入 `MaxRp` 时，下方 popup 只看到 Symbol/Type/Address 表头，没有候选行；同一屏 Memory Symbol 列已经存在 `MaxRpm`，说明变量确实已被 AXF/SymbolIndex 加载。

## 结论与修改
- 不是变量缺失，而是自定义 `QCompleter + QTreeView` popup 高度在该 Windows/Qt 环境下过短。
- 只做几何修复：候选 popup 固定最小 240 px、最大 420 px。
- 保留 V0.5.3 本地 `MatchContains` 模型过滤；输入过程中仍不访问 J-Link，不重建 AXF model。

## 验证
- 用户截图症状：VERIFIED_USER_HARDWARE
- 新静态回归覆盖 popup 稳定高度与 no-per-key-I/O 约束。
- compileall: PASS；pytest: 59 passed。
- 用户 Windows/PySide6 修复后候选行：PENDING_USER_HARDWARE。

## 实机优先验证
1. AXF 自动加载完成。
2. Memory 输入 `MaxRp`，确认候选列表能看到 `MaxRpm` 行，而不是只有表头。
3. 输入更短片段如 `Max`、`Rpm`，确认多候选可滚动。
4. ↑/↓ + Enter 选择后确认跳转地址正确。
5. 快速连续输入/删除，确认不卡且输入期间没有 Memory Read。
