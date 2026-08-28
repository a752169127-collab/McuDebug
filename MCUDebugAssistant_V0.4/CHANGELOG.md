# V0.4.16 — GUI Stall Watchdog

## Why this version exists

Real-board V0.4.15 profiling showed a 273 ms GUI stall while every measured hot path remained tiny:

- append: 0.1 / 0.2 ms, no ring resize
- paint max: ~10 ms
- worker: ~6 ms
- HSS read/decode: sub-ms to a few ms
- render/follow/setData/table: sub-ms

This means the long pause occurs **between** already-profiled callbacks. V0.4.16 stops guessing and samples the GUI Python stack from an out-of-band daemon watchdog while the presentation heartbeat is stale.

## Added

- `core/gui_watchdog.py`
  - independent daemon heartbeat monitor
  - 120 ms stale threshold
  - up to four stack samples per stall episode
  - captures GUI stack plus top frames from other Python threads
  - records watchdog's own scheduling gap
- Stall logs now include `wd=<class>/<stale_ms>` and watchdog scheduling gap.
- Status line includes compact `WD:` classification.
- After the GUI resumes, Log prints:
  - watchdog episode summary
  - sampled GUI stack(s)
  - first-sample top frames from other Python threads

## Interpretation

- `class=qt-paint`: GUI was inside paintEvent during the stall.
- `class=scope-*`: an unprofiled/recursive Scope Python path is visible in the stack.
- `class=qt-native-event-loop` or `outside-python-scope`: GUI was inside native Qt/Windows event processing rather than Scope Python code.
- If `watchdogGapMax` is close to the GUI stall duration, the watchdog itself was not scheduled either; that points toward process-wide OS scheduling or GIL starvation rather than a Qt-main-thread-only blockage.

No acquisition, AXF, Ring Buffer, Rendering V2, Single-ViewBox Stacked, Transform Follow, or HSS semantics were changed.
