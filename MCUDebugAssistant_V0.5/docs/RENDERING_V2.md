# Scope Rendering V2 Architecture — V0.4.23

## Core pipeline

```text
Acquisition (HSS / RTT)
        ↓
Raw Ring Buffer
        ↓
Statistics / Cursor / CSV
        ↓
Render Cache
        ↓
Visible-window / peak-preserving display reduction
        ↓
Gain / Offset
        ↓
PlotCurveItem
        ↓
Single ViewBox
        ↓
Single-shot PreciseTimer + Absolute Deadline
```

## Presentation clock
V0.4.23 每个展示帧由一个 single-shot `Qt.PreciseTimer` 驱动。`PresentationPacer` 用浮点绝对 deadline 生成 6/7 ms（144 Hz）或 16/17 ms（60 Hz）等整数毫秒延迟。迟到时直接跳到未来 deadline，不补画漏掉的帧。

这取代 V0.4.20/V0.4.21 的 2~8 ms persistent polling driver，目标是减少 Qt event-loop 无效 timer callback，而不是改变 HSS/RTT 采样率。

## Stacked
Stacked uses one ViewBox and maps every channel into a logical vertical lane. There are no follower ViewBoxes. Each lane keeps its own real-value Y range through `LaneMapper`; the lane coordinate is presentation-only.

Lane Y ranges are fitted from the current visible X window by default. Live Follow checks them at low rate with expand-immediately / shrink-with-hysteresis behavior. `View All` uses the complete retained Buffer.

## Overlay
Overlay also uses one ViewBox. V0.4.9 removes pyqtgraph's scene-resident LegendItem and replaces it with a QWidget legend. This is important because scene text/swatch items otherwise repaint during every ViewBox translation.

At high requested viewport FPS, Overlay receives a tighter pixel geometry budget than Stacked. Peak-preserving min/max reduction keeps narrow extrema visible, and zoomed windows below the limit still contain every raw sample.

## Selection
Selection never changes raw data. The selected channel receives the highest Z value and a modestly wider pen. Overlay non-selected traces are darkened, making the selected trace visually dominant even when two waveforms are nearly identical.

## Rules that remain mandatory
- Sampling rate != GUI FPS.
- Raw data != display data.
- Show never changes acquisition.
- Pause preserves data; Start clears the prior session.
- Gain / Offset are display-only.
- Do not return to repeated whole-history `np.concatenate`.
- Do not use multiple Stacked ViewBoxes again without a measured reason.
