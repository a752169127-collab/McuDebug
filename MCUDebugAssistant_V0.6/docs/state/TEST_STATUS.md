# V0.6.17

## Automated

- `python -m compileall -q .`: PASS
- `pytest -q`: PASS — 139 passed
- V0.6.17 Manual Input Enter/default-button targeted regression: PASS — 3 passed

## Runtime / Qt / Hardware

- PySide6 is unavailable in the current execution environment, so actual QDialog Return/Enter focus behavior is `PENDING_USER_QT_SMOKE`.
- Real J-Link/AXF behavior is unchanged by V0.6.17 and remains `PENDING_HARDWARE` for prior open items.
- Scope long-run Release validation remains pending.

## Acceptance smoke

1. Start a Test Automation plan with a `Manual Input` step.
2. Type a valid numeric measurement into the input field.
3. Press Enter. Expected: `Confirm / Next`, workflow continues; the run is not stopped.
4. Click `Stop Run`. Expected: entire run stops.

Do not claim Qt key-event validation from static tests alone.
