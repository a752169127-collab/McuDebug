# MCU Debug Assistant V0.3.16

V0.3.16 is a focused Scope interaction-performance patch. It keeps the existing V0.3.x architecture but makes mouse pan much closer to an oscilloscope/J-Scope interaction path.

## V0.3.16 highlights

- Left-button drag uses a lightweight full-buffer interaction cache. During the gesture, curves are not rebuilt and raw acquisition continues normally.
- Curve data refresh is capped at 30 Hz independently from the user-selected 1~60 FPS viewport/render clock.
- Stacked follower X ranges may synchronize up to 60 Hz while dragging, with exact final alignment on release.
- Scope traces use `PlotCurveItem` instead of the heavier `PlotDataItem` because the application only needs line traces.
- Statistics-table refresh and hover value lookup are suspended during active drag, then resume immediately after release.
- After release, the final viewport is redrawn once from the complete raw Scope buffer at normal high-detail resolution.
- HSS/RTT sampling rate, statistics and export remain based on all raw samples; interaction caching changes display work only.

## Rendering model

`HSS/RTT raw capture -> ScopeDataStore -> <=30 Hz curve materialization -> 1~60 FPS ViewBox animation / interaction`

During a manual pan:

`raw capture continues -> curves frozen to interaction cache -> mouse moves ViewBox -> release -> one precise viewport redraw`

## Scope Show semantics

`Show` only controls whether a channel is drawn. It does not stop HSS acquisition and does not delete historical samples. A hidden channel can be shown again later and its existing buffered waveform reappears immediately.

## Start vs Pause

- `开始采样`: begins a new capture and clears the old Scope buffer/statistics first.
- `暂停采样`: stops acquisition while preserving all captured data, current zoom/pan, Gain/Offset and analysis cursors.

## Channel table

The Scope table is ordered as:

`Show | Color | Name | Address | Type | Current | Average | Min | Max | Gain | Offset`

Color is displayed as a compact swatch rather than hexadecimal text. Double-click the swatch to choose another trace color.

All V0.3.13 HSS/RTT, Watch, AXF/DWARF, cursor, Gain/Offset, FPS and export features remain available.
