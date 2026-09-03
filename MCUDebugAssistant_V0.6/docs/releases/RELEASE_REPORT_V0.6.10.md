# RELEASE REPORT — V0.6.10 Compact Connection Panel

## Scope
Small UI-only cleanup based on user hardware workflow feedback.

## Changes
- Added `−/+` collapsible J-Link connection details.
- Auto-collapse on successful connect; auto-expand on disconnect.
- Always-visible connection summary and Disconnect.
- Active-session configuration remains locked even when details are manually expanded.
- Removed duplicate Automation numbering: hidden vertical headers; Workflow is now Step/Summary; Results keeps Case.

## Preserved
- Single J-Link owner
- V0.6.9 Memory history behavior
- V0.6.7 Watch commit semantics
- V0.4.23 Scope performance path
- V0.6.x Automation execution semantics

## Verification
- compileall: PASS
- pytest: 111 passed
- ZIP integrity: PASS
- Windows/PySide6 visual smoke: PENDING_USER_QT_SMOKE
- Real J-Link: no I/O behavior change; not re-claimed
