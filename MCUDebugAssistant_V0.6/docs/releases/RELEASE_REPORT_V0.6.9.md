# RELEASE REPORT — V0.6.9 Stable History Controls

## Problems addressed
1. The History popup context menu can disappear when the editable QComboBox popup closes on Windows/PySide6, making per-item deletion unreliable.
2. Selecting a saved history Symbol/address currently reuses the normal remember path and therefore moves the selected item to the top; the user wants history order to remain stable during reuse.

## Changes
- Added persistent `Delete History` button next to the Address/Symbol history control.
- The button deletes the selected/current history record after the popup closes, while preserving current Memory destination and editor text.
- Existing History selection is navigation-only and does not call the MRU update helper.
- Newly typed successful queries still use the existing 50-entry bounded/deduplicated MRU rule.
- Removed context-menu wiring from the History popup as the primary deletion UX; Delete-key remains available as a secondary shortcut.

## Preserved
- V0.6.8 editable-combo/QCompleter Enter isolation.
- Symbol-first editor display and typed Memory navigation.
- Auto-fit Symbol columns.
- Single J-Link owner, visible-range reads and WriteMemEx-only default writes.
- Watch, Scope and Test Automation behavior.

## Verification
- `python -m compileall -q .`: PASS
- `pytest -q`: 109 passed
- PySide6/Windows History button/order smoke: PENDING_USER_QT_SMOKE
- Real J-Link: no new target-I/O path introduced; prior typed Symbol destination validation remains PENDING_HARDWARE
