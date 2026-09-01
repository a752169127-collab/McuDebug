# VERSION_HISTORY

- V0.1.x — J-Link connect, memory R/W, device selection.
- V0.2.x — Watch, stats, AXF/ELF/DWARF, search/rebind/performance.
- V0.3.x — Scope HSS/RTT, timestamp fix, Overlay/Stacked, cursors, buffer/FPS, chunk storage, visible-window reduction, interaction optimization.
- V0.4.0 — Rendering V2: single Scene, ring buffer, render cache.
- V0.4.1–V0.4.6 — high-refresh/painter/GPU experiments; several low-level painter changes rolled back.
- V0.4.7 — Single ViewBox logical-lane Stacked, major smoothness gain.
- V0.4.8 — visible-window lane Y fit.
- V0.4.9–V0.4.11 — Overlay fast path, pacing, steady-state geometry.
- V0.4.12–V0.4.17 — latency guard, transform follow, profiling, preallocation, watchdog, hover hot-path fix.
- V0.4.18–V0.4.19 — debugger detection, event-loop attribution, non-invasive diagnostics/log batching.
- V0.4.20 — direction: persistent presentation driver + absolute deadline gate; split Qt event-loop stall and presentation starvation.
- V0.4.21 — Release Scope cleanup: removed default watchdog/event-loop/debugger/worker/paint profiling while retaining acquisition, Ring Buffer, persistent presentation pacing and Rendering V2 behavior.

- V0.4.23 — High Performance Clean: based on V0.4.21; replaced persistent presentation polling with single-shot absolute-deadline pacing, removed per-chunk ring-resize diagnostic, and updated Agent/Workflow/Skill for minimal evidence-driven development.

Repository state overrides this summary.
