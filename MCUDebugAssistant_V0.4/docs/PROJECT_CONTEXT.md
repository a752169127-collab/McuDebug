# PROJECT_CONTEXT

## Project
MCU Debug Assistant

## Goal
长期演进的 MCU 调试平台：J-Scope 风格 Scope + Keil Watch + AXF/ELF/DWARF Symbol Browser，支持 J-Link HSS/RTT。

## 两条主数据链

```text
MCU → J-Link → JLinkWorker → Acquisition → Raw Ring Buffer
                                      ├─ Statistics / Cursor / CSV
                                      └─ Render Cache → Scope Presentation
```

```text
AXF/ELF/DWARF → Symbol Model → Watch / Scope Channel Definition
```

## 当前成熟度
- J-Link Memory R/W：已实机验证
- Watch：较成熟
- ARMCC5 DWARF3：当前场景成熟
- Scope 功能：丰富
- Rendering V2：Single Scene / Ring Buffer / Render Cache / Single-ViewBox Stacked / Transform Follow
- Release 高刷长时间稳定性：继续硬件验证

## V0.4.23 当前结论
- V0.4.21 已移除 Stall 调查阶段默认 watchdog / probe / stage profiling。
- V0.4.23 进一步把 persistent 2~8 ms presentation polling 改为 single-shot absolute-deadline pacing。
- 目的不是增加新功能，而是降低 Qt event-loop 无效唤醒和默认热路径工作量。
- Ring Buffer 仍在 Start 前预分配；GUI append 不做每批 capacity 诊断。
- 正式性能只在 RUN / 非 debugpy 环境评价。

如果实际源码版本更高，以仓库和 `state/PROJECT_STATE.yaml` 为准。
