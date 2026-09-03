# RELEASE REPORT — V0.6.15 Cross-Module Symbol Actions

## User value
The same AXF/DWARF variable can now move directly between Memory, Watch and Scope without reopening Symbol Browser and searching again.

## Changes
- Memory Symbol: Add to Watch / Add to Scope / Copy Symbol.
- Raw Memory selected address: Add to Watch / Add to Scope.
- Watch Variable: Add to Scope / Open in Memory / Copy Symbol.
- Scope HSS Channel: Open in Memory / Add to Watch / Copy Symbol.
- Scope RTT: address-dependent actions disabled; Copy channel name retained.
- `Open in Memory` validates exact Symbol full-name + address; unmatched/manual rows fall back to Raw address.
- Scope HSS channel additions are rejected while sampling.
- Cross-module routing remains local UI Signal wiring; single J-Link Worker/session unchanged.

## Verification
- `python -m compileall -q .`: PASS
- full `pytest -q`: 131 passed
- targeted `test_cross_module_symbol_actions_v0615_static.py`: 5 passed
- PySide6 runtime in build environment: unavailable
- Windows Qt smoke: PENDING_USER_QT_SMOKE
- Real J-Link/AXF routing: PENDING_HARDWARE

## Suggested smoke
Use one known scalar AXF member and verify Memory -> Scope, Watch -> Memory, Scope -> Watch, duplicate suppression, sampling lock, and RTT disabled actions.
