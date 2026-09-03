# RELEASE REPORT — V0.6.13 Stable Semantic Refresh

## User issue
Symbols View jumped back to the originally navigated Symbol whenever refreshed, making it impossible to browse farther rows under Auto Refresh. The destination row also looked permanently selected.

## Root cause
Every new memory block called `_rebuild_model()`, which always chose the row nearest `_anchor_address`, set it current and called `scrollTo(PositionAtCenter)`. Data refresh was accidentally acting like a navigation command.

## Fix
- One-shot anchor focus only for explicit Symbol navigation.
- Subsequent refresh preserves user scroll state.
- Navigation no longer leaves an artificial selected row.
- User-created selection can survive refresh without owning the viewport.
- Cached refresh skips an unchanged model rebuild.
- No change to bounded semantic block read, Single J-Link Owner or write semantics.

## Verification
- compileall: PASS
- pytest: 123 passed
- targeted V0.6.13: 4 passed
- Windows/PySide6 visual smoke: PENDING_USER_QT_SMOKE
- Real J-Link/AXF Auto Refresh: PENDING_HARDWARE
