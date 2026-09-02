# RELEASE REPORT — V0.6.5 PySide6 Memory History Startup Fix

## Goal
修复 V0.6.4 在用户 Windows/PySide6 环境启动时因 Memory 历史下拉信号签名不兼容导致的崩溃。

## Root Cause
`QComboBox.activated[str]` 请求 `activated(QString)` 重载，但用户的 PySide6/Qt6 绑定只提供 `activated(int)`；因此 `MemoryExplorerPage.__init__()` 直接抛 `IndexError`。随后的 QThread destroyed 信息是异常退出后的级联提示。

## Fix
- `address_combo.activated.connect(...)` 使用 Qt6/PySide6 可用的 integer activation signal。
- `_history_activated(index)` 使用 `address_combo.itemText(index)` 获取 MRU 项并复用 `_goto()`。
- MRU 持久化、Clear History、AXF completer、Memory visible-range reads、Watch/Scope/Automation 均保持不变。

## Verification
- compileall: PASS
- pytest: 93 passed
- User Windows/PySide6 startup: PENDING_USER_QT_SMOKE
- Real AXF/J-Link history navigation: PENDING_HARDWARE
