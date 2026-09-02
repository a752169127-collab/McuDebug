# VERSION_HISTORY

- V0.6.3 — Persistent Results + Excel Clipboard: new SAMPLE defaults to Avg/Min/Max; Results persist across Test Runs; Results tab owns one-click TSV clipboard copy and explicit Clear Results; completed runs clear only Runtime detail.

- V0.6.2 — Clean Automation Results: separates internal Runtime Context from user Results, makes SAMPLE output Avg-only by default with optional Min/Max/Std, hides Count from result schema, and opens Results automatically when the run completes.

- V0.6.1 — Workflow Simplification + Step Dialog Layout Fix: hides WAIT UNTIL/CALCULATE/ASSERT from new-step creation while retaining V0.6.0 saved-plan compatibility; recursively clears nested dynamic Qt layouts to fix label/font overlap when switching Step Type.

- V0.6.0 — Test Automation Studio: adds a no-code Parameter Matrix + generic Workflow engine (SET/WAIT/WAIT UNTIL/WAIT STABLE/SAMPLE/MANUAL INPUT/CALCULATE/ASSERT/SAVE), AXF/DWARF symbol-based execution through the single J-Link Worker, result table/CSV, and saved Test Plans. First validated scenario model: steady-state calibration sweep with manual external-instrument input.

- V0.5.5 — Memory Symbol Resize + Watch Commit Fix: draggable/persisted Memory Symbol column width and Set Value write-on-focus-out with dirty/duplicate guards.

- V0.5.4 — Symbol Completion Popup Fix: fixes user-reproduced header-only/too-short multi-column QCompleter popup by enforcing a stable visible height, while preserving local MatchContains filtering and zero target I/O per keystroke.

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
- V0.5.0 — Memory Explorer: visible-range virtual 32-bit hex viewer, CE-style display/context options, AXF/DWARF symbol overlays, changed-byte display, add-to-Watch, and WriteMemEx-only default write semantics (no read-back verify).

- V0.5.1 — Memory Explorer Interaction Upgrade: SRAM-base first view, aligned/elided Symbol column, distinct address color, CE-style direct Hex/Text editing, drag/Shift range selection, batch Hex/Text copy/paste, and double-click edit without a second confirmation modal.

- V0.5.2 — AXF Symbol Auto-load: restored saved AXF/ELF is now actively parsed at startup when the file exists, then propagated to Memory/Watch/Scope; stale paths are skipped without directory guessing.

- V0.5.3 — Symbol Address Navigation: Memory Address bar accepts numeric addresses or AXF/DWARF variable/member/array paths, with local model-backed contains filtering and Enter-to-address navigation without per-key J-Link traffic.
