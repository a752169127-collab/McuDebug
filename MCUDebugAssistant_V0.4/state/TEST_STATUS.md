# TEST_STATUS

## Automated
每版必须：
- compileall
- pytest
- targeted regression

### V0.4.23
- `python -m compileall -q .`: PASS
- full `pytest`: **39 passed**
- `test_presentation_pacer.py`: PASS — 144 Hz 6/7 ms absolute-deadline pattern; no catch-up burst; 60 Hz one-callback-per-frame model
- `test_release_scope_cleanup.py`: PASS — no Stall runtime; single-shot timer required; no live resize diagnostic in append hot path
- Qt offscreen `ScopePage` construction: **PENDING_ENVIRONMENT** — current execution environment has no `PySide6`
- Real J-Link/HSS/RTT hardware: **PENDING_HARDWARE**
- Result: `VERIFIED_AUTOMATED` for pure-Python/static scope changes; GUI/hardware runtime pending

### V0.4.21
- Environment: Codex Python 3.12, NumPy 2.3.5, pytest 9.1.1
- `compileall`: PASS
- full `pytest`: 38 passed
- targeted default-release diagnostic cleanup tests: PASS
- Qt smoke: Python 3.14, PySide6 6.11.2, pyqtgraph 0.14.0; offscreen `ScopePage` construction PASS
- Result: VERIFIED_AUTOMATED
- Real J-Link/HSS/RTT hardware: PENDING_HARDWARE

## Hardware validation record
必须记录：
- version
- RUN/DBG
- device
- J-Link DLL
- SWD/JTAG speed
- source HSS/RTT
- requested/actual Hz
- channels/types
- buffer
- Overlay/Stacked
- Follow
- FPS target
- FG/BG
- duration
- result

## Status vocabulary
- VERIFIED_AUTOMATED
- VERIFIED_SYNTHETIC
- VERIFIED_USER_HARDWARE
- PENDING_HARDWARE
- PENDING_ENVIRONMENT
- HYPOTHESIS
- DISPROVED
