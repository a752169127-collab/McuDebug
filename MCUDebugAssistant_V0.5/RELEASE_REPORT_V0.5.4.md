# RELEASE REPORT — V0.5.4

## Name
MCU Debug Assistant V0.5.4 — Symbol Completion Popup Fix

## User-reproduced issue
`Address / Symbol` 输入 `MaxRp` 后，popup 只有 Symbol/Type/Address 表头；同屏 Memory Symbol 列已有 `MaxRpm`，证明符号数据存在，问题属于 popup 可见区域几何。

## Change
Custom QTreeView completion popup now has a stable 240 px minimum and 420 px maximum height. No symbol model rebuild, AXF parse, or J-Link read was added to the typing path.

## Verification
`compileall`: PASS; `pytest`: 59 passed. Real Windows/PySide6 confirmation remains PENDING_USER_HARDWARE.
