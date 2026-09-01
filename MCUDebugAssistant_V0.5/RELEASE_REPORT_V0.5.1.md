# RELEASE REPORT — V0.5.1 Memory Explorer Interaction Upgrade

## Scope
针对用户实机截图反馈的 6 个 Memory Explorer 交互缺口做局部修复，不重构 J-Link Worker 或 Scope。

## Resolved
- 首屏 SRAM `0x20000000`。
- Symbol 固定列对齐/elide。
- Text 直接输入/粘贴写。
- Address/value 颜色区分。
- 连续 byte range 批量复制 Hex/Text。
- CE 式 Hex 直接输入、typed in-cell editor、双击弹窗编辑。

## Write semantics
Memory Explorer 的直接键入和粘贴立即进入单 J-Link Worker 写队列；双击弹窗点击 OK 即确认。仍使用 `JLINK_WriteMemEx` 完整 byte count 作为成功条件，不自动 ReadBack Verify。

## Verification
- compileall: PASS
- pytest: 51 passed
- Qt GUI runtime: PENDING_ENVIRONMENT
- Real J-Link: PENDING_HARDWARE

## Risk / rollback
改动集中在 `ui/memory_explorer.py`、Memory Explorer MainWindow write wrapper 和纯函数 helper。Scope、Watch acquisition、J-Link backend ownership 未改。若实机 direct edit 有地址映射问题，可单独回滚 V0.5.1 interaction layer，不影响 V0.5.0 block-read baseline。
