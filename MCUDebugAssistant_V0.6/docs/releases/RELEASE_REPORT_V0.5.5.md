# RELEASE REPORT — V0.5.5

## Release
MCU Debug Assistant V0.5.5 — Memory Symbol Resize + Watch Commit Fix

## User issues
1. Memory Symbol 列宽不可调，长变量名无法展开查看。
2. Watch Set Value 输入后点击其它位置不写 MCU。

## Implementation
- `ui/memory_explorer.py`: draggable Symbol/Hex divider, persisted `symbol_width_px`, 12~120-char clamp, double-click default reset.
- `ui/watch_table.py`: dirty SetValueDelegate; Enter/focus-out unified commit/write; duplicate/unmodified guards.
- `ui/main_window.py`: UI help/docstring/version text updated.

## Preserved
- Single J-Link Owner
- WriteMemEx-only default writes
- AXF local completion/no per-key target I/O
- V0.4.23 Scope performance architecture

## Verification
- compileall: PASS
- pytest: 63 passed
- Qt runtime: PENDING_ENVIRONMENT
- Real J-Link: PENDING_HARDWARE
