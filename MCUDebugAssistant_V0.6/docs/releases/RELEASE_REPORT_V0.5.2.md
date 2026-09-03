# RELEASE REPORT — V0.5.2

## Issue
`FIX-AXF-AUTOLOAD-V052`

## Problem
V0.5.1 restores the saved AXF/ELF path into the UI but does not parse it at application startup. Symbol-aware Memory therefore starts without symbols until the user presses Reload.

## Change
A deferred startup hook checks the persisted symbol path and, when it is still a file, reuses the existing `_load_symbol_file(..., rebind_watch=True)` path. No directory-wide AXF discovery was added.

## Preserved
- Single J-Link Owner
- V0.5.1 Memory Explorer interactions
- Visible-window Memory reads
- No default write read-back verify
- V0.4.23 Scope rendering path

## Verification
- compileall: PASS
- pytest: 53 passed
- targeted static regression: PASS
- Qt real startup: PENDING_ENVIRONMENT
- J-Link symbol-overlay validation: PENDING_HARDWARE
