# V0.4.23 — High Performance Clean

## Scope presentation hot-path simplification

V0.4.23 基于 V0.4.21 做 Release 性能减法，不扩展功能、不重写 Scope。

Changed:

- 将 V0.4.21 的 2~8 ms persistent `PreciseTimer` polling + `consume_due()` 改为 **single-shot `PreciseTimer` + absolute deadline**。
- 144 FPS 的调度目标从约 500 次 timer callback/s 收敛到约 144 次 presentation callback/s；60 FPS 从约 200 次/s 收敛到约 60 次/s。该数字是调度唤醒数量的理论变化，不代表实机 FPS 提升百分比。
- Missed deadlines 继续直接跳过，不产生 catch-up render burst。
- 暂停/非采样状态使用 20 Hz 轻量 presentation clock。
- `append_samples()` 删除每批 Ring capacity 前后比较和 live-resize warning 构造；Ring 仍在 Start 前按 requested Hz × Buffer 预分配。
- 更新 FPS Tooltip，使 UI 与当前真实调度架构一致。

Retained:

- J-Link 单 Owner Worker。
- HSS/RTT 协议与 timestamp 语义。
- Ring Buffer / Render Cache / Transform Follow。
- CPU Raster / Single-ViewBox logical-lane Stacked。
- Overlay/Stacked、Follow、Show、Pause、Start、View All、Gain/Offset、CSV、AXF rebind。
- `LiveLatencyGuard`。
- V0.4.21 已完成的 watchdog / event-loop probe / debugger detection / 高频 profiling 清理。

AI engineering updates:

- `AGENTS.md` 增加工程克制原则：最小修改、证据足够即停止分析、稳定区默认不动、达标即停。
- `WORKFLOW.md` 改为小 Diff + Release Gate + STOP 的闭环流程。
- `SKILL.md` 更新 V0.4.23 高性能 Scope 方法和已否定方向。
- `docs/*` / `state/*` 同步本版架构、问题、验证状态。

## Verification

- `python -m compileall -q .`: PASS
- full `pytest`: **39 passed**
- targeted release cleanup / presentation pacing regression: PASS
- Qt offscreen ScopePage smoke: NOT RUN in current environment (`PySide6` unavailable)
- real J-Link/HSS/RTT performance A/B: `PENDING_HARDWARE`

---

# V0.4.21

## Release Scope hot-path cleanup

V0.4.21 retires the temporary Stall investigation runtime from the default
high-performance Scope path. It does not change HSS/RTT data, retained raw
samples, display transforms or user interaction semantics.

Removed:

- `ScopeGuiWatchdog` stack-sampling thread and classification logic.
- asynchronous `scope_diagnostics_*.log` writer thread.
- 25 ms Qt event-loop probe and presentation starvation/gap classification.
- debugpy/pydevd detection and `Scope PERF WARNING` logging.
- worker poll/read/decode performance Signal and continuous timing.
- Paint FPS, 1% low, jitter, paint max, render/follow/setData/table/hover/append
  stage timing and diagnostic status formatting.
- diagnostic-only/dead counters in PresentationPacer, Render Cache, Ring Buffer
  and Worker state.

Retained:

- single J-Link owner Worker and all connection/error protections.
- HSS timestamp and RTT-normal decoding.
- acquisition batching and Actual Hz.
- preallocated NumPy Ring Buffer, statistics, cursor/probe and CSV export.
- persistent PreciseTimer presentation driver and absolute deadline gate.
- CPU raster, Render Cache, peak-preserving reduction and logical-lane Stacked.
- Overlay/Stacked, Follow, Show, Pause, Start, View All, Gain/Offset and AXF rebind semantics.
- LiveLatencyGuard, hover coalescing and bounded/batched product logs.

## Verification

- `compileall`: PASS
- `pytest`: 38 passed
- default-release diagnostic cleanup regression: PASS
- Python 3.14 / PySide6 6.11.2 offscreen ScopePage smoke: PASS
- real J-Link/HSS/RTT validation: PENDING_HARDWARE

---

# V0.4.20

## Persistent Presentation Driver

V0.4.19 diagnostics showed that a long presentation gap does not always mean the entire Qt GUI event loop is blocked. In some traces the 25 ms Qt event-loop probe continued to run while the per-frame single-shot presentation timer did not fire for hundreds of milliseconds.

Changes:

- Replaced the per-frame single-shot `_viewport_timer` re-arm path with one persistent repeating `Qt.PreciseTimer`.
- Added a cheap absolute-deadline gate (`PresentationPacer.consume_due`) so the persistent driver never renders above the requested FPS.
- High-refresh targets use a 2~8 ms driver polling interval; idle/paused mode falls back to 50 ms.
- Removed all per-frame `QTimer.stop()/start()` and `next_delay_ms()` scheduling from `_viewport_tick()`.
- Missed deadlines skip directly to the next future slot; no catch-up render bursts.
- Added driver callback-rate telemetry (`D:` / `driverHz`).

## Stall attribution split

- Renamed the former generic `Scope GUI stall` concept to **presentation gap** in the V0.4.20 path.
- Qt event-loop stalls are independently detected by the 25 ms event-loop probe.
- Added **presentation starvation** detection when the Qt event loop is still healthy but presentation age exceeds the threshold.
- Starvation logs include timer active state, `remainingTime()`, persistent driver interval/rate, loop gap, target FPS and DBG/RUN environment.
- Status line now exposes `Gap:` and `PS:` separately.

## Tests

- Added persistent deadline-gate tests.
- Added missed-slot / no-catch-up-burst test.
- Added persistent driver interval tests.
- `compileall`: PASS
- `pytest`: 41 passed

---

# V0.4.19

## Non-invasive diagnostics / GUI log isolation

- Full watchdog stacks are written asynchronously to `logs/scope_diagnostics_*.log`.
- GUI Log receives compact summaries only.
- Log widget uses NoWrap, disabled undo/redo, 2000-block cap, and batched writes.
- Watchdog sampling is reduced under debugpy/pydevd.
