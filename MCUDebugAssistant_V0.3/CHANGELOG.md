# V0.3.7

- Fixed a Stacked-mode freeze when `查看所有波形` was clicked with many channels.
  - Stacked plots share one linked X axis, so the full-buffer fit now sets X range only on the master plot instead of repeatedly calling `setXRange()` on every linked ViewBox.
  - Live-follow uses the same master-X update rule, reducing linked-range event storms during normal streaming too.
  - Full-buffer Y fitting no longer allocates `raw * Gain + Offset` arrays for every channel; it derives displayed extrema from raw min/max and the channel transform.
- Added user-selectable Scope refresh FPS, J-Scope style.
  - Editable preset list: 1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60 FPS.
  - Valid range is 1..60 FPS; default is 30 FPS.
  - FPS controls only pyqtgraph/table rendering. HSS/RTT sampling frequency remains independent.
  - The J-Link worker can deliver Scope chunks at up to 60 Hz, while every raw sample is still appended to the Scope buffer/statistics/export path.
  - At low FPS, intermediate GUI frames are skipped but no raw samples are discarded.
- FPS setting is persisted with the Scope project settings.
- `查看所有波形` renders pending samples immediately before performing the full-buffer fit.

# V0.3.6

- Fixed `查看所有波形`: it no longer relies on pyqtgraph `autoRange()` or the previous ViewBox X span.
- X range is now taken directly from the complete data currently retained in the Scope buffer (`first buffered sample -> latest buffered sample`). Once the configured buffer is full this is exactly the configured rolling buffer width; before it fills, all captured data is used without adding empty time.
- Overlay mode computes one Y range from all visible channels over the complete buffer after Gain/Offset.
- Stacked mode computes an independent complete-buffer Y range for each visible channel.
- Constant-value signals get a stable non-zero Y margin so a value such as 1000 is clearly visible.
- `查看所有波形` remains one-shot and does not toggle `跟随最新数据`. If follow is enabled, the fitted full-buffer X width becomes the subsequent rolling window width.

# V0.3.5

- Scope Stop is now `暂停采样`: stopping HSS/RTT preserves the complete in-memory buffer and Current/Average/Min/Max so the stopped waveform can be inspected. Restarting appends to the existing capture instead of clearing it.
- Added resumed-timeline continuity when HSS/RTT timestamps restart from zero.
- Reworked J-Scope keyboard semantics: `+/-` modifies selected-channel Gain; `Ctrl +/-` modifies selected-channel Offset. These are display transforms (`raw * Gain + Offset`) and never modify raw samples or CSV export.
- Scope channel list moved below the plot and expanded with Current / Average / Min / Max / Gain / Offset.
- Added mouse-follow X probe line plus floating all-channel sample readout.
- Moved Log to its own main tab to maximize Scope/Watch workspace.
- Added explicit right-click `清空缓存数据`; buffer clearing is no longer coupled to Pause/Resume.

# V0.3.4

- 修复勾选“跟随最新数据”后 X 轴缩放会被下一帧恢复的问题：现在实时跟随保存用户当前 X 窗口宽度，只平移窗口右边界到最新样本。
- 跟随开启时仍可用鼠标缩放/调整 X、Y；新的 X 缩放范围会立即成为后续跟随窗口宽度。
- 跟随更新前后显式保存并恢复每个 Plot 的 YRange，确保实时滚动绝不改变 Y 轴范围/基线。
- “查看所有波形”执行一次 Fit 后会记录新的 X 窗口宽度，但不会改变跟随复选框状态。

# Changelog

## V0.3.4 - Follow-latest ownership / context export

- Moved Scope raw CSV export from the toolbar into the custom waveform right-click menu as `导出缓存数据...`.
- Replaced the toolbar export button with a `跟随最新数据` checkbox.
- The checkbox is now the only control that enables/disables live follow. Mouse pan/zoom and `查看所有波形` no longer change follow state.
- Live follow updates X range only; it never changes Y range, Y zoom, or baseline.
- Hidden pyqtgraph's built-in `A` auto-range button and disabled continuous ViewBox auto-range so incoming samples cannot silently rescale Y.
- `查看所有波形` remains an explicit one-shot fit and immediately disables automatic ranging again.
- Follow-latest state is persisted in the Scope profile.

## V0.3.2 - Scope interaction / buffer / export

- Disabled pyqtgraph's built-in right-click menu so right click is reserved for the custom X1/X2/Y1/Y2 cursor menu.
- Scope buffer time is now user-configurable from 1 to 120 seconds; default increased from 5 s to 30 s.
- Added dedicated CSV raw-data export for the current Scope buffer (`Time(s)` / sample index + channel columns), UTF-8 BOM for convenient Excel opening.
- Added J-Scope-like keyboard interaction on the focused plot:
  - `+` / `-`: vertical zoom in / out.
  - `Ctrl +` / `Ctrl -`: move the visible waveform baseline up / down.
- Mouse click gives the plot keyboard focus; keyboard Y operations do not disable X-axis live follow.
- Buffer/view settings persist with the existing Scope profile.

## V0.3.1 - HSS timestamp / waveform fix

- Fixed HSS frame parsing: every sample is treated as `U32 timestamp_us + configured memory payload`.
- `JLINK_HSS_Start()` now explicitly enables `JLINK_HSS_FLAG_TIMESTAMP_US`.
- HSS timestamp drives the Scope X axis; requested sample rate is no longer used to synthesize timestamps.
- Fixed constant int16/uint32 signals being drawn as timestamp/value alternating ramps or triangular bands.
- Added timestamp wrap handling and partial-read buffering tests.
- Added live rolling X-axis follow; manual pan/zoom stops follow and `查看所有波形` resumes it.
- Regression suite: 13 tests.

## V0.3 - Scope HSS / RTT

- Added Scope page using pyqtgraph.
- Added `HSS` and `RTT` as waveform acquisition sources in the same Scope page.
- Added J-Link HSS bindings: `JLINK_HSS_Start`, `JLINK_HSS_Read`, `JLINK_HSS_Stop`.
- Added RTT terminal bindings and automatic discovery of the first `JScope_<FORMAT>` Up Buffer.
- Added J-Scope RTT Normal packet parser for `t4`, `b1`, `f4`, `i1/i2/i4`, `u1/u2/u4`.
- HSS Scope channels can be added through the existing AXF/ELF symbol browser.
- AXF reload now rebinds HSS Scope channel addresses/types and removes missing channels.
- Added Overlay and Stacked waveform layouts.
- Added `查看所有波形` auto-range.
- Added X1/X2/Y1/Y2 draggable cursor lines and right-click set/delete commands.
- Added ΔX / ΔY plus selected-channel Value@X1 / Value@X2 using nearest acquired samples.
- Added short Scope buffer: 5 seconds, maximum 50000 samples.
- Acquisition remains in the single J-Link owner worker; GUI receives chunks at up to about 25 Hz.
- Added display decimation above 10000 points without changing cursor source data.
- Added Scope persistence for HSS channels, source, sample rate and display layout.

## V0.2.6 - Watch performance

- Decoupled Watch acquisition/statistics from GUI painting.
- `JLINK_ReadMemEx` sampling still runs at the requested interval in the J-Link worker thread.
- Mean/Min/Max are accumulated for every successful acquisition cycle.
- Qt receives only the newest Watch snapshot at up to 25 Hz.
- Removed live `ResizeToContents` behavior for dynamic Watch columns.

## V0.2.5 - AXF Reload / Multi-delete

- Added AXF/ELF reload and Watch symbol rebinding.
- Missing/ambiguous Watch symbols are removed rather than rebound unsafely.
- Added Shift/Ctrl multi-selection and Delete-key removal.

## V0.2.4 - Excel-friendly average copy

- `复制平均值` copies average values only, TAB-separated for one-row Excel paste.

## V0.2.3 - Keil AXF struct members + fast search

- Fixed ARM Compiler 5 / DWARF3 structure-member parsing.
- Added built-in lightweight DWARF 2/3 parser.
- Replaced per-keystroke table reconstruction with QTreeView + proxy filtering.

## V0.2.2 - Clipboard averages + AXF/ELF symbols

- Added clipboard average snapshot and initial AXF/ELF symbol browser.
