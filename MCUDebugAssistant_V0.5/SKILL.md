# SKILL.md — MCU Debug Assistant 项目技能知识

## 项目定位

MCU Debug Assistant 是一个 Python 桌面 MCU 调试工具，目标体验接近：

**Keil Watch + J-Scope + AXF Symbol Browser + Symbol-aware Memory Explorer**

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
- V0.5 默认写入：WriteMemEx 完整 byte count 即成功，不追加 ReadBack Verify
- `write_and_verify()` 仅保留为可选底层能力，不在默认产品写路径使用
- int8/uint8/int16/uint16/int32/uint32/int64/uint64/float/double


### Memory Explorer (V0.5)
- 32-bit 虚拟地址空间，16 Bytes/Row，自绘 `QAbstractScrollArea`。
- 新会话首屏固定从 `0x20000000` SRAM 基址开始；用户随后可 Go/Ctrl+G 浏览任意 32-bit 地址。
- 只读可见窗口 + margin，滚动 debounce；不全地址扫描。
- Auto Refresh 默认 OFF，避免与 HSS/RTT 无意义竞争 J-Link Owner。
- Display Type：Byte/各整数/float/double。
- Text Encoding：ASCII/UTF-8/UTF-16LE/GBK；Text pane 支持直接键入与粘贴编码后写入。
- Byte Hex pane 支持 CE 式两位 Hex 直接写；非 Byte typed view 支持 in-cell editor。
- 鼠标拖动/Shift 可选择连续 byte range；Ctrl+C/右键可批量复制 Hex 或按当前文本编码复制。
- 双击 Value/Text 打开编辑弹窗；按 OK 后直接进入 Worker 写入，不再弹第二层 confirmation。
- Symbol 列为固定宽度单行对齐列，长名称 elide；一行优先一个最相关的 exact/offset symbol，避免多符号拼接覆盖 Hex。
- Address 使用与 Memory value 不同的 palette role，便于视觉区分。
- Context Menu：显示符号、符号偏移、变化、分隔符、编辑、复制/粘贴、加 Watch。
- `SymbolIndex` 优先精确 DWARF scalar/member，再解析 containing symbol + offset。
- Peripheral Space 不做自动扫描/大范围 speculative read。

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

## 当前 V0.5.x 技术演进

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

### V0.5.4 Memory Explorer 交互基线
- 保留 V0.4.23 Scope 高性能架构，不因 Memory 功能重构 Scope。
- Memory Block Read/Write 与 Watch/Scope 共用唯一 `JLinkWorker`。
- UI 虚拟滚动不代表预读整个 4GB；实际 ReadMemEx 只覆盖可见附近小块。
- 写入成功后本地 patch 显示，不自动 ReadBack；显式 F5 才是下一次读取。
- 启动时恢复的 `symbol_file` 若仍存在，事件循环启动后自动 `_load_symbol_file(..., rebind_watch=True)`；让 Memory/Watch/Scope 首次进入时已经有真实 SymbolIndex，而不是只有 AXF 路径字符串。
- 自动加载只认已保存的明确文件路径；路径失效时记录并跳过，不递归扫描工作目录猜测 AXF。
- Memory Address Bar 同时接受 32-bit 数值地址与 AXF/DWARF 完整符号路径；例如 `BlowerParamsObj.m_PosSpeed`、`buffer[1]`、`ctrl.channels[1].gain` 可直接换算并跳转。
- 符号输入使用一次构建的 `QStandardItemModel + QCompleter(MatchContains)`；输入字符时只在本地模型过滤，不重建行、不访问 J-Link。下拉列表同时显示 Symbol / Type / Address，方向键选择后 Enter 即跳转。
- 自定义多列 `QCompleter + QTreeView` popup 必须保留稳定可见高度，不能依赖初次 row size hint 把短查询/单结果候选压缩成只剩表头；V0.5.4 基线为 240~420 px。

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
