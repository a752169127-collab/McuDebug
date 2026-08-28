# MCU Debug Assistant V0.4.16

V0.4.16 is a diagnostic-focused continuation of Rendering V2. Real-board V0.4.15 logs showed 200–700 ms GUI gaps while all instrumented Scope work stayed below roughly 10 ms. This release adds an out-of-band GUI heartbeat watchdog so the next stall identifies **where the GUI Python thread actually is during the pause**.

Keep the same stress test:

```text
3 Channels
Overlay
HSS requested 1000 Hz
Buffer 30 s
Follow ON
FPS 144
```

When a stall occurs, copy the new Log lines beginning with:

```text
Scope watchdog:
Scope watchdog[1]:
Scope watchdog threads:
Scope GUI stall:
```

The important fields are:

- `class=` — stack classification (`qt-paint`, `scope-render`, `scope-mouse`, `qt-native-event-loop`, etc.)
- `stale=` — how stale the GUI heartbeat was when sampled
- `pollGap=` / `watchdogGapMax=` — whether the independent watchdog thread itself was also starved
- `GUI ...` — actual Python stack tail sampled during the stall

If the GUI stack is only `main.py -> app.exec()` while Scope/worker timings remain low, the remaining pause is outside normal Python Scope processing and should be investigated at the Qt/Windows message-loop/scheduler layer rather than by further changing Ring Buffer or waveform geometry.
