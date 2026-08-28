# MCU Debug Assistant V0.4.12

本版本延续 V0.4 Rendering V2：J-Link Worker、HSS/RTT、AXF/DWARF、Watch、NumPy Ring Buffer、Render Cache、Single ViewBox Stacked、Overlay fast path、Presentation Clock 均保持兼容。

## V0.4.12 重点

- 删除无收益的 GPU 实验路径，统一 CPU Raster；
- Windows 实时采样期间启用 1 ms timer、关闭执行速度/Timer Resolution power throttling；
- Scope 运行期间 Process / GUI thread 使用 Above Normal（不使用 High/Realtime）；
- 实时采样区间关闭 Python cyclic GC，Pause 后再空闲收集；
- 新增 Presentation Tick FPS 与 Event-loop Stall 诊断。

### 状态栏

例如：

```text
P:137/144 T:143 1%:118 J:1.7ms Stall:0/0ms pts:3.3k FG
```

- `P`：Qt 实际 Paint FPS；
- `T`：Presentation Scheduler 实际 Tick FPS；
- `1%`：最近帧的 1% Low；
- `J`：Paint frame interval jitter；
- `Stall`：本轮采样 GUI 长停顿次数 / 最大停顿毫秒；
- `pts`：当前提交给 PlotCurveItem 的几何点数；
- `FG/BG`：窗口是否拥有前台焦点。

如果切到其它程序以后 `T` 仍接近 144、但 `P` 接近 60，说明主要剩余限制来自 Qt/Windows DWM 的后台 paint 合并，而不是采样/定时器。

## 推荐验证

```text
3 Channels
Overlay
1000 Hz request
30 s buffer
144 FPS
Follow latest = ON
```

连续运行 5~10 分钟，并分别记录：

1. 前台状态下 `P / T / 1% / J / Stall / pts`；
2. 切换到其它窗口但仍能看到 Scope 时同一组指标；
3. 偶发短暂停顿后 `Stall` 是否增加，以及 Log 中的 `Scope GUI stall: xxx ms`。
