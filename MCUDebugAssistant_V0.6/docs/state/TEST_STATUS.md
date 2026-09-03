# V0.6.16

## Automated

- `python -m compileall -q .`: PASS
- `pytest -q`: PASS — 136 passed
- V0.6.16 documentation-layout targeted regression: PASS — 5 passed

## Runtime / Qt / Hardware

- V0.6.16 changes documentation layout and GUI title only; no target I/O behavior changed.
- PySide6 functional smoke for V0.6.15/V0.6.14/V0.6.12 remains `PENDING_USER_QT_SMOKE`.
- Real J-Link/AXF validation remains `PENDING_HARDWARE`.
- Scope long-run Release validation remains pending.

## Release constraint

Do not claim Qt/hardware validation from documentation-path tests.
