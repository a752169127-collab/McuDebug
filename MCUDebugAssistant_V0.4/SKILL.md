# SKILL.md — MCU Debug Assistant 项目技能知识

## 项目定位

MCU Debug Assistant 是一个 Python 桌面 MCU 调试工具，目标体验接近：

**Keil Watch + J-Scope + AXF Symbol Browser**

主要技术：
- Python
- PySide6 / Qt
- pyqtgraph
- NumPy
- ctypes
- SEGGER J-Link DLL
- AXF / ELF / DWARF
- HSS / RTT

---

## 核心功能

### J-Link / Memory
- J-Link DLL 扫描
- x64 Python 优先 `JLink_x64.dll`
- SWD/JTAG
- Speed
- SEGGER 原生 Device Settings（兼容性需注意）
- `JLINK_ReadMemEx`
- `JLINK_WriteMemEx`
- Write + ReadBack Verify
- int8/uint8/int16/uint16/int32/uint32/int64/uint64/float/double

### Watch
- 多变量
- Current / Average / Min / Max
- Enter 写 Set Value
- 多选删除
- Average 以 Tab 分隔复制到 Excel
- AXF Reload Rebind
- Worker 采样/统计，GUI 低频 Snapshot

### AXF / ELF / DWARF
真实 ARMCC5 案例：
- ARM Compiler 5.06
- DWARF3
- `BlowerParamsObj = 0x20002894`
- `m_PosSpeed offset=132 -> 0x20002918`
- `m_Position offset=136 -> 0x2000291C`

ARMCC5 结构体成员关键：
`DW_AT_data_member_location = DW_FORM_block + DW_OP_plus_uconst`

Symbol Search 使用：
`QStandardItemModel + QSortFilterProxyModel + QTreeView + debounce`

### Scope
采样源：
- HSS
- RTT

功能：
- Overlay
- Stacked
- Sampling Request
- Actual Hz
- Buffer
- FPS
- Follow
- View All
- Show
- Start / Pause
- Gain / Offset
- Color
- Current / Avg / Min / Max
- Mouse Probe
- X1/X2/Y1/Y2
- CSV
- History Mode
- Interaction Mode
- Render Cache
- Ring Buffer

---

## 重要历史问题与结论

### HSS Timestamp Bug
HSS frame：
`[Timestamp U32][Payload]`

Timestamp 必须独立解析成 X，不能当 Channel Data。

### Watch 卡顿
原因：高频逐 Cell 更新。
解决：Worker Statistics + GUI Snapshot。

### Symbol Search 卡顿
原因：每个字符重建控件。
解决：Model/View + Proxy + debounce。

### Scope 长时间 Buffer 卡顿
旧：反复 concatenate。
后：Chunk Buffer，再到预分配 Ring Buffer。

### Zoom 后点变少
错误：
先对整个30s降采样，再看100ms。

正确：
先取需要范围，再 Peak-Preserve reduction。

### Stacked 性能
旧：
多个 PlotWidget / ViewBox / Axis。

演进：
单 GraphicsScene → Single ViewBox + Logical Lanes。

这个方向显著改善了 Stacked 流畅度。

### Lane Y 坐标
不要用整个30秒旧异常值决定当前局部 Lane Y Range。
实时/局部历史优先使用当前可见窗口。
`View All` 才使用整个 Buffer。

### GPU 实验
`QGraphicsView + QOpenGLWidget` 并不等于真正 GPU Scope。
实机反馈 CPU Raster 更流畅。
当前主路线：CPU Raster。
只有未来真正做 VBO/Shader Renderer 才重新评估 GPU。

### Hover Stall
Watchdog 曾明确抓到：
`SignalProxy -> _mouse_moved -> _show_hover_at_host_pos -> QLabel.adjustSize()`

所以高频 Mouse Move 中禁止做 Widget 动态布局/adjustSize。

### Ring Resize
实时 Ring Buffer 需要 Session Start 预分配。
如果日志显示 `resize=0`、append sub-ms，则 Ring resize 已经不是当前 Stall 原因。

### Debug Environment
高刷性能必须区分：
- `RUN`
- `DBG`

debugpy/pydevd 下的 Qt Timer/Event Loop 数据不能直接当 release performance。

---

## 当前 V0.4.x 技术演进

V0.4 主线从“功能堆叠”转为“Rendering V2 + Release 热路径收敛”。

当前 V0.4.23 高性能原则：
- Single Scene / Single ViewBox logical-lane Stacked
- Preallocated Ring Buffer
- Render Cache + visible-window peak preserve
- Transform Follow
- Acquisition / curve geometry / presentation FPS 分离
- `LiveLatencyGuard` 只保留真实调度优化，不承担诊断
- **single-shot PreciseTimer + absolute deadline**：目标每个展示帧只产生一次 presentation timer callback
- 暂停时降为 20 Hz 轻量 presentation clock
- GUI append 热路径不做 ring-capacity 诊断比较/日志构造
- 默认 Release 不安装 watchdog、event-loop probe、debugger detector 或逐帧 profiling

### 性能问题的推荐判断顺序

1. 先确认是否为正常 RUN / `python main.py`，debugpy/pydevd 数据不能当 Release 结论。
2. 先看用户可见症状和已有测试，不默认全项目 profiling。
3. 判断问题属于 acquisition、buffer/cache、presentation scheduling、paint/geometry 还是 interaction。
4. 一旦证据足以解释问题，停止继续扩展假设。
5. 优先减少热路径工作/唤醒，而不是增加新的复杂机制。
6. 小 Diff 后立刻做 A/B / regression；达标即停。

## 当前已排除/不应反复回退的假设

没有新证据不要重新把主要问题归因于：
- HSS decode 需要几百 ms
- 正常 Paint 需要几百 ms
- live ring resize（Start 前已预分配）
- hover adjustSize（已移出高频路径）
- 单纯“Python 画不动”
- QOpenGLWidget 一定更快
- 必须用高频 persistent timer 才能稳定展示（该方向源自 debugger 阶段现象，V0.4.23 改回更低唤醒的一帧一回调策略）

需要新的 Release/RUN 证据才允许重开。
