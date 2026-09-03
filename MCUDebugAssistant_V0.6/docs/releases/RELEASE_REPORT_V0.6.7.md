# RELEASE REPORT — V0.6.7 Memory Navigation + Reliable Watch Commit

## Issues fixed
1. Memory Symbol/history keyboard selection could navigate to the wrong address after Up/Down + Enter.
2. Long Symbol/member names required manual width dragging to read.
3. Symbol navigation replaced the Address/Symbol editor text with a raw address instead of keeping the Symbol.
4. Watch Set Value mouse focus-out could miss an explicit same-value write while Enter worked.

## Root causes
- Editable QComboBox and QCompleter had overlapping Enter paths; generic fallback could reuse stale completion state.
- History selection round-tripped through the editor and generic goto path.
- Symbol column/popup widths were fixed or user-resized rather than content-driven.
- Watch target write was attached to line-edit edge signals rather than the delegate's model-commit point.

## Implementation
- Intercept Enter only when the completion popup has an explicit highlighted row; resolve that QModelIndex exactly once.
- History `activated(int)` reads the selected MRU model row and navigates directly.
- Symbol goto preserves `symbol.name`; numeric goto remains canonical hex.
- Auto-fit visible Memory Symbol width with a bounded cache; auto-fit local History/Completion model columns.
- Move Watch dirty-write emission to `QStyledItemDelegate.setModelData()` after `super().setModelData()`.

## Preserved
- Single J-Link owner.
- Default WriteMemEx without forced read-back verify.
- AXF/DWARF local model completion, no per-key target I/O.
- Typed Symbol Memory display.
- V0.4.23 Scope performance architecture and V0.6 Test Automation behavior.

## Verification
- compileall: PASS
- pytest: 101 passed
- Qt GUI smoke: PENDING_USER_QT_SMOKE
- Real AXF/J-Link hardware validation: PENDING_HARDWARE
