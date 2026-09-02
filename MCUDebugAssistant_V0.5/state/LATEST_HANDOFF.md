# LATEST_HANDOFF

## 当前版本
V0.5.5 — Memory Symbol Resize + Watch Commit Fix（基于 V0.5.4）。

## 本轮输入
1. Memory Symbol 列宽固定，长变量名看不全且无法主动拉宽。
2. Watch Set Value 输入后不按 Enter、点击其它位置时不会执行目标写入。

## 根因与修改
- Memory 是自绘 View，Symbol 宽度硬编码 `cw * 32`；现加入分隔线 hit-test/拖动 resize，12~120 字符范围，宽度持久化，双击恢复默认。
- Watch delegate 旧逻辑仅监听 `returnPressed`；现以 `textEdited` dirty 标志统一处理 Enter 与 `editingFinished`，focus-out 先 commit model，再下一 event-loop turn 发既有写请求，并以 dirty clear 防双写。

## 保持不变
- Symbol resize 不解析 AXF、不访问 J-Link。
- Watch 实际写仍由唯一 JLinkWorker 执行 WriteMemEx。
- 默认写不增加 ReadBack Verify。
- V0.4.23 Scope 高性能架构不修改。

## 验证
- compileall: PASS
- pytest: 63 passed
- PySide6 runtime: PENDING_ENVIRONMENT
- Real J-Link/Windows interaction: PENDING_USER_HARDWARE

## 实机优先验证
1. Memory 将鼠标放到 Symbol 与 Hex 分隔线上，确认出现左右 resize cursor；拖宽后长变量名可见。
2. 关闭重开软件，确认 Symbol 宽度保持。
3. Watch Set Value 输入例如 `123`，不按 Enter，直接点击另一个单元格；Log 应出现一次 WATCH WRITE REQUEST，MCU 值应更新。
4. 同一值按 Enter，确认只写一次，不因随后失焦再写第二次。
