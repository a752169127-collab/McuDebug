# RELEASE REPORT — V0.6.1 Workflow Simplification + Step Dialog Layout Fix

## User feedback
1. Assert / Calculate / Wait Until are unnecessary for the current no-code workflow.
2. Changing Workflow Step Type causes labels/text to overlap and look corrupted.

## Root cause
The overlap is a Qt dynamic-layout lifecycle bug: `StepDialog._clear_body()` removed only direct widgets. Nested `QFormLayout` / `QHBoxLayout` items and their child labels/editors survived, so every type switch could stack old controls under the new form.

## Changes
- New Step Type list: SET / WAIT / WAIT STABLE / SAMPLE / MANUAL INPUT / SAVE RESULT.
- WAIT UNTIL / CALCULATE / ASSERT retained only for V0.6.0 saved-plan compatibility.
- Default plan no longer inserts Calculate nodes.
- Added recursive nested-layout/widget destruction before rebuilding StepDialog body.
- No change to JLinkWorker, polling protocol, Memory, Watch, Scope, AXF parser, or write semantics.

## Verification
- compileall: PASS
- pytest: 78 passed
- targeted V0.6.1 static regression: PASS
Qt visual smoke remains PENDING_ENVIRONMENT if PySide6 is unavailable.
Real J-Link automation remains PENDING_HARDWARE.
