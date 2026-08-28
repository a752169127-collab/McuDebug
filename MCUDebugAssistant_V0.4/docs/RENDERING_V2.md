# Scope Rendering V2 Architecture — V0.4.9

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
Presentation Clock
```

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
