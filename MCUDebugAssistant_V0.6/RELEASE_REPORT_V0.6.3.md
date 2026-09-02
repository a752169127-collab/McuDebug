# RELEASE REPORT — V0.6.3 Persistent Results + Excel Clipboard

## User issues
1. Results should keep steady-state Avg / Min / Max; only the Run/runtime view should be cleared when a run finishes.
2. Starting a new test run must not erase previous Results.
3. Remove the top-level Export CSV workflow; provide one-click copy from Results so the full table can be pasted directly into Excel.
4. Provide an explicit manual button to clear all Results.

## Implementation
- New/missing SAMPLE statistics default to `avg / min / max`; `std` remains opt-in and `count` remains internal only.
- Removed result clearing from `_run_all()`; result rows and dynamic columns now accumulate across runs.
- Kept completed-run behavior: clear `runtime_table` and switch to Results.
- Results page now owns `Copy Results` and `Clear Results`.
- Copy Results serializes current result columns plus all rows as TSV and writes directly to the Qt system clipboard.
- Clear Results requires explicit confirmation, then resets the accumulated result store/table.
- Removed top-toolbar Export CSV action and file-save path for automation results.

## Preserved
- Runtime Context != Result Schema.
- Internal Count/Avg/Min/Max/Std statistics remain available for compatibility.
- Parameter Matrix, WAIT STABLE, request/response polling and single J-Link owner remain unchanged.
- V0.5.5 Memory/Watch and V0.4.23 Scope paths are unchanged.

## Automated verification
- `python -m compileall -q .`: PASS
- `pytest -q`: 87 passed
- targeted V0.6.3 static result-history/clipboard regressions: PASS
- ZIP integrity: PASS (after packaging)

## Pending
- Qt button/clipboard smoke: PENDING_ENVIRONMENT (PySide6 unavailable in this environment)
- Real AXF + J-Link multi-run accumulated results: PENDING_HARDWARE

## Hardware/user smoke checklist
1. Create a SAMPLE and verify Avg/Min/Max are selected by default; Std is not.
2. Run 2–3 cases and confirm Results contains Avg/Min/Max while Run is cleared at completion.
3. Run the same/another plan again without clearing Results; old rows must remain and new rows append.
4. Click Results → Copy Results and paste into Excel; headers and cells must align correctly.
5. Click Clear Results, reject once (data remains), then confirm (all result rows clear).
