# RELEASE REPORT — V0.6.14 Symbol Navigation Focus

## User issue
Symbols View needed explicit Symbol navigation to visibly jump to/select the resolved member, while still allowing the user to cancel that selection with a normal click elsewhere.

## Change
- Symbol/member navigation centers and selects the destination row once.
- Refresh preserves only actual selected rows and never scrolls to the navigation anchor.
- Clicking empty Symbols viewport space clears both selection and current index.
- Cleared selection remains cleared across Auto Refresh/model rebuild.

## Architecture impact
Presentation-only. No J-Link session/read/write path, Symbol parsing, Scope, Watch, Automation or semantic read-window changes.

## Verification
- `python -m compileall -q .`: PASS
- `pytest -q`: 126 passed
- targeted V0.6.14 static: 3 passed
- Windows/PySide6 visual: PENDING_USER_QT_SMOKE
- real AXF/J-Link: PENDING_HARDWARE
