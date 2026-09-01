# ISSUE_LEDGER

## PERF-SCOPE-V043-HARDWARE
Status: CODE_COMPLETE / PENDING_HARDWARE

### Version
V0.4.23

### Goal
在 V0.4.21 已清理 Stall instrumentation 的基础上，继续减少默认 Scope Release 热路径无效工作，不改变产品语义。

### Evidence
- V0.4.21 在 144 FPS 下使用 2 ms persistent presentation driver，理论触发约 500 Qt timer callbacks/s，但目标 presentation 只有 144/s。
- 60 FPS 下 driver 约 5 ms，对应约 200 callbacks/s，目标 presentation 只有 60/s。
- Persistent driver 的主要动机来自 debugger 阶段观察到的 timer starvation；后续已经确认 debugpy/pydevd 会污染高刷 Qt 调度结论。
- V0.4.21 已经删除 watchdog/event-loop/debugger/stage profiling，因此可以进一步让 Release presentation 回到更小的调度面。

### Fix
- `PresentationPacer` 改为 single-shot absolute-deadline delay generator。
- `_viewport_timer` 改为 `setSingleShot(True)`；每个 presentation frame 结束后只 arm 下一次 deadline。
- 迟到帧直接跳过，不 catch-up。
- 非采样状态使用 20 Hz presentation clock。
- GUI `append_samples()` 删除 per-chunk ring capacity 比较与 warning。

### Verification
- compileall: PASS
- pytest: 39 passed
- release cleanup regression: PASS
- presentation pacing synthetic regression: PASS
- Qt offscreen smoke: PENDING_ENVIRONMENT (PySide6 unavailable here)
- real Windows + J-Link + HSS/RTT: PENDING_HARDWARE

### Stop condition
如果 RUN 模式实机的 Overlay/Stacked/Follow/Drag/Zoom/30s/5min 回归正常，则关闭本 Issue；不要继续无证据重构 Scope。

---


## PERF-SCOPE-RELEASE-CLEANUP
Status: CODE_COMPLETE / PENDING_HARDWARE

### Version
V0.4.21

### Symptom
V0.4.20 kept the previous Stall investigation runtime enabled in the default
Scope path: watchdog and diagnostic-writer threads, a 25 ms Qt event-loop probe,
worker poll/read/decode timers, paint/presentation/stage counters and verbose
Stall classification logs.

### Expected behavior
Release Scope must keep acquisition, Ring Buffer, rendering and interaction
semantics while doing no continuous Stall investigation work by default.

### Root cause / evidence
- V0.4.18-V0.4.20 diagnostics remained wired unconditionally after the debugger
  environment was identified as a major source of event-loop disturbance.
- The 5 ms HSS poll performed poll/read/decode timing on every callback.
- Every presentation tick touched watchdog locks; a second GUI Timer fired every
  25 ms; every paint maintained FPS/jitter/percentile inputs.

### Fix
- Removed GUI watchdog, asynchronous diagnostic writer, event-loop probe,
  presentation-gap/starvation classification and debugger detection.
- Removed worker performance Signal and hot-path timing.
- Removed paint/render/follow/setData/table/hover/append telemetry and the
  diagnostic status line.
- Retained acquisition/presentation/hover product Timers, Actual Hz, Ring resize
  warning, LiveLatencyGuard and the complete Rendering V2 pipeline.

### Verification
- `compileall`: PASS
- `pytest`: 38 passed
- PySide6 offscreen ScopePage construction: PASS
- Default-release static cleanup regression: PASS
- Hardware RUN A/B: PENDING_HARDWARE

---

## PERF-QT-EVENTLOOP
Status: CLOSED_AS_DEBUG_DIAGNOSTIC

### Symptom
Scope occasionally experiences 100–900ms gaps.

### Evidence
In several logs:
- render/follow/setData/table/hover/append were sub-ms or low-ms,
- paint max was around low tens of ms,
- worker/read/decode were far below stall,
- ring resize = 0,
- watchdog classified GUI as `qt-native-event-loop`,
- Python stack showed `main.py -> app.exec()`,
- debugpy/pydevd was active.

### Conclusion
Current Scope Python functions cannot explain the full gap.
The default event-loop/watchdog investigation runtime was retired in V0.4.21.
This closure does not claim that a release-mode Qt stall can never occur.

---

## PERF-PRESENTATION-STARVATION
Status: CLOSED_AS_DEBUG_DIAGNOSTIC

### Symptom
Presentation can show a large gap while general Qt event-loop probe is less delayed.

### Direction
The persistent polling driver was a V0.4.20/V0.4.21 workaround derived from debugger-era observations.
V0.4.23 supersedes that direction with single-shot absolute-deadline pacing to reduce idle timer callbacks.
Reopen persistent polling only if new RUN-mode evidence proves single-shot delivery is unreliable.

---

## PERF-HOVER-ADJUSTSIZE
Status: FIXED

### Evidence
Watchdog stack captured:
`SignalProxy -> _mouse_moved -> _show_hover_at_host_pos -> hover_label.adjustSize()`

### Fix
Remove adjustSize from high-frequency mouse path, use cached geometry and throttled tooltip update.

---

## PERF-RING-RESIZE
Status: FIXED / DISPROVED_AS_CURRENT_STALL

Session ring preallocated.
Later logs:
`append ~0.1ms`, `resize=0`.

---

## PERF-GPU
Status: CLOSED

QOpenGLWidget viewport was not beneficial.
CPU Raster remains main path.

---

## HSS-ACTUAL-RATE
Status: OPEN

Observed example:
requested 1000Hz, actual ~496–499Hz
with GD32F425RG, SWD6000kHz, J-Link DLL V8.10, 3 channels.

Do not confuse acquisition throughput with GUI display reduction.
