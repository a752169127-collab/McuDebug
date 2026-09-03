# RELEASE REPORT — V0.6.11 Engineering Presets

## Scope
UI-only parameter-entry improvement based on user feedback that +/- SpinBox stepping is inefficient for engineering timing/rate values.

## Changes
- Added reusable `IntPresetComboBox`: editable preset drop-down with bounded integer `value()/setValue()/valueChanged` compatibility.
- Memory Auto Refresh presets: 100/200/500/1000/2000/5000 ms; default 1000 ms; custom 100..10000 ms.
- Watch Sample every presets: 10/20/50/100/200/500/1000/2000 ms; default 100 ms; custom 1..60000 ms.
- Scope Sampling presets: 10/20/50/100/200/500/1000/2000/5000 Hz; default 1000 Hz; custom 1..10000 Hz.
- Scope Buffer presets: 1/2/5/10/15/30/60/120 s; default 30 s; custom 1..120 s.
- Scope FPS presets: 15/30/60/90/120/144 FPS; default 60 FPS; custom 1..144 FPS.
- Existing integer QSettings values remain compatible; custom values do not get inserted into the preset list.

## Design boundary
Scope Buffer intentionally remains capped at 120 s. The current raw ring is bounded at 1.5M points; adding a 300 s UI preset without redesigning/validating capacity could make high-rate captures retain less time than the UI promises.

## Preserved
- Single J-Link owner and Worker routing.
- Watch sampling semantics and statistics.
- Memory Auto Refresh timer semantics.
- HSS/RTT acquisition and requested-rate semantics.
- Scope preallocated Ring Buffer implementation and 1.5M-point bound.
- V0.4.23 single-shot absolute-deadline presentation pacing.
- V0.6.10 compact connection / Automation table UI.

## Verification
- compileall: PASS
- pytest: 114 passed
- `test_engineering_presets_v0611_static.py`: PASS
- PySide6/Windows preset/custom-entry smoke: PENDING_USER_QT_SMOKE (PySide6 unavailable in this environment)
- Real J-Link I/O behavior: unchanged; no new hardware success claim

## Recommended user smoke
1. Watch: select 20/100/500 ms and type custom 333 ms; verify displayed Sample Rate and live interval update.
2. Memory: Auto Refresh select 100/1000/5000 ms and type custom 750 ms.
3. Scope: Sampling select 100/1000/5000 Hz; verify period label and requested start rate.
4. Scope: Buffer select 5/30/120 s before Start; verify it remains locked during acquisition.
5. Scope: FPS select 30/60/144 and type custom 75; verify View target follows the value.
