# ARCHITECTURE

## Layer 1 — Device Interface
J-Link backend / 单 Session Owner。

## Layer 2 — Acquisition
Watch sampling / HSS / RTT / timestamp & payload decode。

## Layer 3 — Symbol
ELF / DWARF / symbol model / rebind。

## Layer 4 — Raw Data
Preallocated Ring Buffer / stats / CSV / cursor source。

## Layer 5 — Display Preparation
Visible range / peak preserve / Render Cache / Gain Offset / lane mapping。

## Layer 6 — Presentation
Qt / pyqtgraph / Follow / Pan / Zoom / Cursor / Hover。

V0.4.23 presentation clock：

```text
PresentationPacer absolute deadline
        ↓
Single-shot PreciseTimer
        ↓
_viewport_tick()
        ↓
arm next deadline
```

目标是每个展示帧只触发一次 timer callback；错过的帧直接跳过，不 catch-up burst。
Acquisition Rate、Heavy Curve Refresh、Presentation FPS 继续彼此独立。

## Layer 7 — Optional Diagnostics
默认 Release 不安装 Scope performance watchdog、诊断线程、event-loop probe、debugger detector 或 Worker/Paint 高频计时。未来诊断必须显式启用，关闭时不能留下高频 Timer/Thread/Counter。

### 依赖原则
- Acquisition 不依赖具体 Widget。
- Raw Data 不被显示逻辑修改。
- Display reduction 不影响 CSV/统计原始数据。
- Diagnostics 关闭时必须从热路径消失，而不是只关闭输出。
- Stable Zone 默认不因局部性能问题被跨层重构。
