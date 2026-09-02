### V0.6.3
- `python -m compileall -q .`: PASS
- full `pytest`: **87 passed**
- SAMPLE new/default result statistics Avg/Min/Max static regression: PASS
- new Run preserves existing Results static regression: PASS
- Results-owned Copy Results / Clear Results controls static regression: PASS
- TSV header+rows clipboard path for Excel static regression: PASS
- completed-run Runtime clear + Results preservation regression: PASS
- Qt clipboard/buttons visual smoke: **PENDING_ENVIRONMENT** — PySide6 unavailable in current execution environment
- Real AXF + J-Link multi-run accumulated Results: **PENDING_HARDWARE**

### V0.6.2
- `python -m compileall -q .`: PASS
- full `pytest`: **82 passed**
- Avg-only default SAMPLE result selection static regression: PASS
- explicit Case Result projection (no whole-context dump) static regression: PASS
- completed-run Runtime clear + auto Results tab static regression: PASS
- full internal Count/Avg/Min/Max/Std retention for legacy calculations: PASS (static + existing core stats tests)
- Qt visual/result-table smoke: **PENDING_ENVIRONMENT** — PySide6 unavailable in current execution environment
- Real AXF + J-Link result columns: **PENDING_HARDWARE**

### V0.6.1
- `python -m compileall -q .`: PASS
- full `pytest`: **78 passed**
- simplified new-step picker static regression: added
- recursive dynamic-layout cleanup static regression: added
- Qt Step Type switching visual smoke: **PENDING_ENVIRONMENT** — PySide6 unavailable in current execution environment
- Real J-Link behavior: unchanged by this UI fix; V0.6.1 automation hardware run remains **PENDING_HARDWARE**

# TEST_STATUS

### V0.6.0
- `python -m compileall -q .`: PASS
- full `pytest -q`: **75 passed**
- `test_test_automation_core.py`: PASS — List/Range, Cartesian/Zip, no-eval Token resolution, multi-signal StableDetector, Sample Avg/Min/Max/Std, Calculate/Assert
- `test_test_automation_v060_static.py`: PASS — Test Automation tab/worker wiring, GUI no direct J-Link access, generic workflow node baseline
- Qt GUI Runtime Smoke: **PENDING_ENVIRONMENT** — PySide6 unavailable in current execution environment
- Real AXF + J-Link SET/WAIT/STABLE/SAMPLE workflow: **PENDING_HARDWARE**
- Long RPM sweep / timeout action behavior: **PENDING_HARDWARE**
- PF300 / VT650 automatic acquisition: **NOT IMPLEMENTED** — V0.6.0 uses Manual Input
- Result: `VERIFIED_AUTOMATED` for pure-core/static architecture only

### V0.5.5
- compileall: PASS
- pytest: 63 passed
- Memory Symbol resize/persistence static regression: PASS
- Watch Set Value Enter/focus-out dirty commit static regression: PASS
- Qt GUI Runtime Smoke: PENDING_ENVIRONMENT (PySide6 unavailable)
- Real J-Link Set Value focus-out write: PENDING_HARDWARE
- Real Windows Symbol drag-resize: PENDING_HARDWARE


## Automated
### V0.5.4
- User-reproduced popup symptom: VERIFIED_USER_HARDWARE (header-only/too-short candidate popup)
- Popup stable-height static regression: PASS
- compileall: PASS
- pytest: 59 passed
- Real Windows/PySide6 candidate-row visibility after fix: PENDING_USER_HARDWARE

每版必须：
- compileall
- pytest
- targeted regression

### V0.5.3
- `python -m compileall -q .`: PASS
- full `pytest`: **57 passed**
- `test_memory_browser.py`: PASS — exact symbol-name lookup, struct/array path (`buffer[1]`) resolution, DWARF preference and stable preferred-symbol ordering
- `test_memory_symbol_jump_v053_static.py`: PASS — model-backed QCompleter/MatchContains wiring and no address-edit per-keystroke J-Link/read connection
- Qt Symbol/Type/Address completion popup: **PENDING_ENVIRONMENT** — current execution environment has no PySide6
- Real AXF/DWARF symbol Enter-to-address + J-Link visible read: **PENDING_HARDWARE**
- Result: `VERIFIED_AUTOMATED` for core/static V0.5.3 behavior

### V0.5.2
- `python -m compileall -q .`: PASS
- full `pytest`: **53 passed**
- `test_symbol_autoload_v052_static.py`: PASS — startup scheduling, existing-file guard, Watch/Scope/Memory rebind path
- Qt startup with saved real AXF: **PENDING_ENVIRONMENT**
- Real J-Link is not required to prove parser auto-load, but Memory symbol overlay hardware check remains **PENDING_HARDWARE**

### V0.5.1
- `python -m compileall -q .`: PASS
- full `pytest`: **51 passed**
- `test_memory_browser.py`: PASS — text input encoding, UTF-16 edit unit, batch Hex clipboard plus V0.5.0 planner/symbol/format coverage
- `test_memory_explorer_v051_static.py`: PASS — RAM-base first view, direct edit/range copy paths, no second Memory Explorer modal confirmation
- Qt GUI smoke: **PENDING_ENVIRONMENT** — current execution environment has no PySide6
- Real J-Link CE-style direct Hex/Text editing, drag selection, symbol alignment: **PENDING_HARDWARE**
- Result: `VERIFIED_AUTOMATED` for pure-Python/static V0.5.1 behavior

### V0.5.0
- `python -m compileall -q .`: PASS
- full `pytest`: **46 passed**
- `test_memory_browser.py`: PASS — 32-bit address parsing, bounded visible read window, data display, text encoding, DWARF/member symbol resolution
- `test_memory_write_no_verify.py`: PASS — worker typed-write path uses `write_memory()` and release UI no longer claims Write+Verify
- Qt GUI smoke: **PENDING_ENVIRONMENT** — current execution environment has no PySide6
- Real J-Link Memory Explorer: **PENDING_HARDWARE**
- Result: `VERIFIED_AUTOMATED` for pure-Python/static Memory Explorer logic

### V0.4.23
- `python -m compileall -q .`: PASS
- full `pytest`: 39 passed at that release
- Scope presentation pacing / release cleanup regression: PASS
- Real J-Link/HSS/RTT: PENDING_HARDWARE

## Hardware validation record
必须记录：
- version
- RUN/DBG
- device
- J-Link DLL
- SWD/JTAG speed
- Memory address/range and region type (RAM/Flash/Peripheral)
- manual/auto refresh interval
- AXF/ELF + DWARF availability
- display type / text encoding / symbol options
- Scope concurrent state if applicable
- result

## Status vocabulary
- VERIFIED_AUTOMATED
- VERIFIED_SYNTHETIC
- VERIFIED_USER_HARDWARE
- PENDING_HARDWARE
- PENDING_ENVIRONMENT
- HYPOTHESIS
- DISPROVED
