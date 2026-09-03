# RELEASE REPORT — V0.6.17 Manual Input Enter Confirm

## User problem

In Test Automation, while the workflow is waiting for an external/manual measurement, pressing Enter after typing a value could activate `Stop Run` and terminate the entire generated-case run. This makes repetitive calibration/validation workflows easy to destroy accidentally.

## Root cause

`ManualInputDialog` uses custom `QPushButton` actions rather than a standard button box, but did not explicitly define the QDialog default-button policy. In Qt, Return/Enter from a line editor can activate a default/auto-default push button. `Stop Run` was therefore unsafe as an implicit keyboard target.

## Fix

- `Confirm / Next` is explicitly the dialog default and auto-default button.
- `Skip Case` is explicitly not default/auto-default.
- `Stop Run` is explicitly not default/auto-default and uses `Qt.FocusPolicy.ClickFocus`.
- Stop remains connected only to the existing explicit `_stop()` action.

## Architecture impact

UI-only. No changes to:

- single J-Link worker/session ownership;
- Automation request/response polling;
- Parameter Matrix / Workflow engine;
- Results accumulation/schema;
- Watch / Scope / Memory;
- target read/write behavior.

## Verification

- compileall: PASS
- full pytest: 139 passed
- targeted `test_automation_manual_input_enter_v0617_static.py`: 3 passed
- Windows/PySide6 actual key interaction: PENDING_USER_QT_SMOKE

## Acceptance

Typing a valid Manual Input value and pressing Enter must confirm the value and continue. The full run must not stop unless `Stop Run` is explicitly activated by the user.
