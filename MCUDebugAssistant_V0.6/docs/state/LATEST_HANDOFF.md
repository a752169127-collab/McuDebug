# LATEST_HANDOFF — V0.6.16

## What changed

V0.6.16 is an engineering-governance release. Runtime behavior is intentionally unchanged from V0.6.15. Documentation is now grouped under `docs/` so the ZIP root remains readable as release history grows.

## Read order for next AI

1. `START_HERE_FOR_NEW_AI.md`
2. `AGENTS.md` / `SKILL.md`
3. `docs/state/PROJECT_STATE.yaml`
4. this file
5. `docs/state/ISSUE_LEDGER.md` / `docs/state/TEST_STATUS.md`
6. `docs/architecture/ADR.md` / `ARCHITECTURE.md` only as needed
7. `docs/releases/README.md` then only the relevant historical report

Do not read every historical release by default.

## Automated verification

- compileall: PASS
- full pytest: 136 passed
- V0.6.16 targeted documentation-layout regression: 5 passed


## Functional baseline preserved

- V0.6.15 Memory/Watch/Scope cross-module Symbol actions.
- V0.6.14 one-shot Symbol navigation selection + blank-space deselect.
- V0.6.13 refresh preserves Semantic Memory viewport.
- V0.6.12 typed Semantic Memory from one bounded block read.
- V0.6.11 engineering preset combo controls.
- V0.4.23 Scope high-performance architecture and single J-Link owner remain protected.

## Pending user/hardware validation

- Windows/PySide6 smoke for V0.6.15 context menus and recent Memory UI behavior.
- Real AXF/J-Link validation for Semantic Memory mixed types/arrays.
- Long-run Scope Release-mode hardware validation.
- Test Automation multi-signal stable/sample workflows on hardware.

## Packaging rule

For future releases, create the report under `docs/releases/`, update `docs/releases/README.md`, and keep root entry files stable.
