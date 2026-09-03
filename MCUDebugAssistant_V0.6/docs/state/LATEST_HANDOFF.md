# LATEST_HANDOFF — V0.6.17

## What changed

V0.6.17 fixes a destructive Test Automation Manual Input keyboard interaction. Pressing Return/Enter while entering a manual/external measurement now confirms the input (`Confirm / Next`) instead of allowing Qt to activate `Stop Run` as an unintended default button.

## Implementation

- `Confirm / Next`: `setDefault(True)` + `setAutoDefault(True)`.
- `Skip Case`: explicitly non-default/non-auto-default.
- `Stop Run`: explicitly non-default/non-auto-default and `ClickFocus`; it remains an explicit stop action.
- No changes to Automation Engine, case generation, polling, single J-Link owner, Results, Watch, Scope or Memory.

## Automated verification

- compileall: PASS
- full pytest: 139 passed
- V0.6.17 targeted Manual Input regression: 3 passed

## Pending user validation

On Windows/PySide6, run a plan containing `Manual Input`, type a valid value and press Enter. The dialog should confirm and continue to the next workflow step/case. Verify `Stop Run` only stops when explicitly clicked.

## Preserved baselines

- V0.6.16 indexed AI documentation layout.
- V0.6.15 cross-module Symbol actions.
- V0.6.12–V0.6.14 Semantic Memory behavior.
- V0.4.23 Scope high-performance path and single J-Link owner.
