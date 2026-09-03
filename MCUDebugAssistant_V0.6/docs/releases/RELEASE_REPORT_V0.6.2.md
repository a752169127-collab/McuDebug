# RELEASE REPORT — V0.6.2 Clean Automation Results

## User issue
Test Automation finished with Run table showing `symbol.avg/count/max/min/std` and other context fields. For the current steady-state measurement workflow, the user expects a clean average-value result rather than internal sampling metadata.

## Root cause
V0.6.1 treated the complete Runtime `_context` as the final Result schema. SAMPLE correctly computed full statistics, but every metric and other execution state was exported indiscriminately.

## Changes
- SAMPLE Step: selectable Avg/Min/Max/Std; Avg is default. Count remains internal only.
- Runtime keeps full sampling statistics for legacy Calculate/Assert compatibility.
- Results/CSV use explicit per-case output keys instead of the whole Runtime Context.
- Parameters, selected sample statistics and Manual Input are the normal output surface.
- Run completion clears the last runtime table and automatically selects Results.

## Preserved
- No J-Link/Worker/Polling architecture changes.
- No changes to WAIT STABLE acquisition semantics.
- V0.5.5 Memory/Watch and V0.4.23 Scope paths unchanged.

## Verification
- compileall: PASS
- pytest: 82 passed
- targeted V0.6.2 static regressions: PASS
- Qt visual smoke: PENDING_ENVIRONMENT
- Real J-Link: PENDING_HARDWARE
