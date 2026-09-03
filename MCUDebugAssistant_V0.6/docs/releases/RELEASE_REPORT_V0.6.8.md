# RELEASE REPORT — V0.6.8 Memory Symbol/History Reliability

## Problems addressed
1. Selecting a valid AXF Symbol and pressing Enter could end at an unrelated saved history entry such as `__lit__00000000`.
2. Existing users could still have a narrow Memory Symbol column because older persisted manual-width state overrode the new auto-fit default.
3. History only supported Clear All; no single-entry delete.

## Root cause
The editable History `QComboBox` and the AXF `QCompleter` share one line edit. V0.6.7 correctly removed stale QCompleter fallback, but the combo's own `activated(int)` remained directly wired to history navigation. On Windows/PySide6 the same Enter used to commit a completer candidate can also produce combo activation, so a stale MRU current row may navigate after the correct Symbol. Separately, old QSettings stored `symbol_auto_fit=false` without a versioned mode and therefore defeated the new default.

## Changes
- Added `NavigationHistoryComboBox` with popup-session gating.
- `QCompleter.activated` is the single Symbol candidate commit path.
- Exact editor Enter supports only exact Symbol or raw address; no currentCompletion/currentIndex guessing.
- History row can be removed by right-click `Delete This History` or Delete key.
- Added `symbol_width_mode=auto/manual`; legacy state without the mode migrates to auto.
- Kept Symbol-first display and typed Memory view selection.

## Preserved
- Single J-Link owner.
- Visible-range Memory reads.
- WriteMemEx-only default writes (no forced read-back verify).
- AXF/DWARF local completion model and no per-key target I/O.
- Watch, Scope and Test Automation behavior.

## Verification
- `python -m compileall -q .`: PASS
- `pytest -q`: 105 passed
- Windows/PySide6 GUI smoke: PENDING_USER_QT_SMOKE
- Real AXF/J-Link destination: PENDING_HARDWARE
