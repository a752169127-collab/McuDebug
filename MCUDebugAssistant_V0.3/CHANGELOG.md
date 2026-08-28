# V0.3.16

- Interaction-first Scope patch focused on J-Scope-like mouse pan smoothness without replacing the existing PlotWidget architecture.
- Manual left-drag now enters an explicit interaction cache mode:
  - prepares one lightweight full-buffer waveform snapshot before panning,
  - freezes curve `setData()`, statistics-table repaint and hover lookup while the button is held,
  - lets mouse motion primarily move ViewBox transforms,
  - redraws the final visible window at full detail only once on release.
- Stacked manual X synchronization can run up to 60 Hz during interaction because curve rebuilding is frozen; final release still forces exact alignment.
- Replaced pure-line `PlotDataItem` traces with lighter `PlotCurveItem` traces to remove unused scatter/data-mapping overhead.
- Curve-data refresh is now capped independently at 30 Hz while viewport/Follow animation may still run at the selected 1~60 FPS. This reduces expensive repeated buffer slicing/downsampling/setData calls without lowering raw HSS/RTT sampling rate.
- QTableWidget statistics updates are completely skipped while a left-button drag is active.
- Gain/Offset drawing avoids allocating a transformed Y array for the common Gain=1 / Offset=0 case.
- Existing V0.3.15 fixed-history behavior, Show semantics, pause retention, HSS/RTT capture and raw-data export remain unchanged.

# V0.3.15

- Fixed Overlay/Stacked rebuild order that could leave axes fitted to the full capture while curves still contained only pyqtgraph's default `0..1` X slice.
- Plot rebuilds now preserve the current X window before the first curve materialization; View switching then explicitly fits the full retained buffer and redraws against that fitted range.
- `跟随最新数据` OFF now acts as a static history-analysis mode: incoming samples to the right of the visible window do not repeatedly call `setData()`.
- Statistics and raw acquisition remain live even when the historical curves are not being redrawn.
- Pan/zoom marks the viewport dirty so the newly visible X slice is fetched from the raw Scope buffer on the fixed render clock.
- Stacked left-drag follower synchronization is throttled to ~30 Hz during drag and forced exact on release, reducing ViewBox work during interaction.
- Rolling-buffer trim detection refreshes the fixed view only when retained-history expiry actually reaches the visible window.

# V0.3.14

- Scope `Show` is now presentation-only, matching J-Scope semantics.
  - Hiding a channel no longer changes the HSS acquisition definition.
  - Hidden channels continue to be sampled and remain in the raw Scope buffer.
  - Showing the channel again immediately restores its previously captured waveform.
  - Overlay hides/shows the existing curve; Stacked hides/shows the existing plot widget. No plot rebuild or buffer reset occurs.
- `开始采样` now starts a fresh acquisition session.
  - Previous Scope raw samples and Current/Average/Min/Max are cleared before HSS/RTT starts.
  - `暂停采样` remains the analysis operation and continues to preserve the current capture and view.
- Scope channel table layout changed to `Show | Color | Name | Address | Type | Current | Average | Min | Max | Gain | Offset`.
  - Color is now a compact swatch immediately before the variable name.
  - The `#RRGGBB` text is no longer shown.
  - Double-click the swatch to change the trace color.
  - Color and Show state are still persisted in the Scope configuration.
