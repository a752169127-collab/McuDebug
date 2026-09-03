# RELEASE REPORT — V0.6.6 Symbol Typed Memory Navigation

## User request
1. Memory Address/Symbol 历史下拉需要看到成员 Type。
2. 通过 Symbol/member 跳转时，Memory 应第一次就用 AXF/DWARF 类型解释内存，例如 uint8 自动切 UInt8。

## Implementation
- History combo popup upgraded to a small three-column `QStandardItemModel + QTreeView`: History / Type / Address. The editable field keeps its 320~520 px width.
- History metadata is resolved from the current SymbolIndex and refreshed after symbol load/reload.
- Added `symbol_display_type()` to accept only supported scalar datatype names.
- `_goto_symbol()` applies the scalar display type before `goto_address()`, so the first destination frame uses the correct interpretation.
- Numeric addresses and container/unknown types preserve the current display type.

## Preserved
- PySide6/Qt6 combo activation uses `activated(int)` from V0.6.5.
- AXF completion remains a separate local QCompleter model with no per-key J-Link reads.
- Memory reads remain visible-range only through the single JLinkWorker.
- Watch, Scope and Test Automation behavior are unchanged.

## Verification
- compileall: PASS
- pytest: 97 passed
- Windows/PySide6 visual popup: PENDING_USER_QT_SMOKE
- Real AXF/J-Link typed navigation: PENDING_HARDWARE
