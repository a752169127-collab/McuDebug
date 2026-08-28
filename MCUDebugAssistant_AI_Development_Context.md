# MCU Debug Assistant — AI 开发上下文与演进记录

> 用途：将本文件直接提供给新的 AI 模型，使其在没有历史聊天记录的情况下继续开发。  
> 当前整理版本：V0.3.16  
> 技术栈：Python / PySide6 / pyqtgraph / NumPy / ctypes / SEGGER J-Link DLL / AXF-ELF-DWARF

---

## 0. 项目定位

MCU Debug Assistant 是一个“Keil Watch + J-Scope + AXF Symbol Browser”式 MCU 调试工具。

核心能力：

- J-Link DLL 直接连接 MCU。
- `JLINK_ReadMemEx()` / `JLINK_WriteMemEx()` 做普通内存读写。
- HSS / RTT 做 Scope 高速采样。
- AXF / ELF / DWARF 自动解析变量、结构体成员和数组成员。
- Watch：Current / Average / Min / Max / Set Value。
- Scope：Overlay / Stacked / Buffer / FPS / Follow / Gain / Offset / Color / Cursor / Hover / CSV。
- 后续目标：死机调试、算法回溯、通用 MCU 调试与验证平台。

---

# 1. 不可破坏的架构原则

1. **J-Link DLL 只能由一个 JLinkWorker / Session Owner 持有。** GUI、Watch、Scope 均不能直接抢 J-Link。
2. **Sampling Rate 与 GUI Refresh/FPS 必须解耦。** 统计使用全部真实采样点，GUI 只按较低频率刷新。
3. **Raw Data 与 Display Data 必须分离。** Raw 用于统计/CSV/Cursor/Probe，Display 才应用 Downsample/Gain/Offset。
4. **Gain / Offset 只改显示：** `Y_display = Y_raw * Gain + Offset`。
5. **Show 只控制显示。** 隐藏期间仍采样并保存历史。
6. **Pause 不清数据。** 保留 Buffer / Statistics / Range / Cursor / Gain / Offset。
7. **Start 表示新的实验。** Start 前清旧 Scope Buffer 与 Statistics。
8. **AXF Reload 必须重新绑定地址。** 按完整 Symbol Name 匹配；不存在则删除。
9. **Symbol Search 禁止每输入一个字符重建 QTableWidget。** 正确方案：Model/View + Proxy Filter。
10. **长缓存禁止反复 `np.concatenate(old_history, new_data)` 整段复制。** 当前用 Chunked Buffer。
11. **显示必须先裁 Visible Window，再 Downsample。**
12. **Downsample 使用 Peak Preserve（每 bucket 保留 Min/Max）。**
13. **拖动期间优先交互。** 冻结非必要 Curve setData / Hover / Table refresh，HSS/RTT/Raw/Statistics 继续。
14. **Follow 只移动 X，不自动改 Y。**
15. **Actual Hz 与 Requested Hz 必须分开。** 当前真实测试存在 1000 Hz requested → ~496~499 Hz actual。

---

# 2. 总体架构

```text
PySide6 GUI
  ├─ Watch
  ├─ Scope
  ├─ Memory R/W
  └─ Log
        │
        ▼
Data / Display Layer
  ├─ Statistics
  ├─ Scope Buffer
  ├─ Visible Window
  ├─ Downsample
  ├─ Gain / Offset
  └─ Cursor / Probe
        │
        ▼
JLinkWorker
  ├─ Connect / Disconnect
  ├─ ReadMemEx / WriteMemEx
  ├─ HSS
  └─ RTT
        │
        ▼
JLink_x64.dll → MCU
```

另一条核心链：

```text
AXF / ELF / DWARF → Symbol Model → Watch / Scope Channel Definition
```

---

# 3. V0.1 — J-Link 底座

目标：建立真实板级最小闭环。

已实现并实机验证：

- Connect / Disconnect。
- SWD / JTAG。
- Speed。
- Device。
- `JLINK_ReadMemEx()`。
- `JLINK_WriteMemEx()`。
- Write 后 ReadBack Verify。
- int8/uint8/int16/uint16/int32/uint32/int64/uint64/float/double。

---

# 4. J-Link Device / DLL

## Device Dialog

目标做成 J-Scope 风格：

```text
Device [ STM32... ] [...]
```

`...` 调用 SEGGER 原生：

- `JLINK_DEVICE_SelectDialog()`
- `JLINK_DEVICE_GetInfo()`

## 跨电脑 DLL 问题

不同电脑 J-Link DLL 版本不一致时，可能出现：

```text
Target device selection cancelled
```

这不一定真是用户取消，可能是 SelectDialog API 版本不兼容。

当前建议：

- 64 位 Python 优先 `JLink_x64.dll`。
- 后续增加 DLL path/version/capability/return code 诊断。

---

# 5. Watch 演进

Watch 表核心字段：

```text
Name | Address | Type | Current | Set Value | Average | Min | Max
```

支持：

- 多变量。
- 周期采样。
- Current / Average / Min / Max。
- Clear Statistics。
- Shift/Ctrl 多选。
- Delete 删除。
- 删除按钮保留。
- 配置持久化。

## Set Value

最终正确交互：

```text
编辑 Set Value
    ↓
Enter
    ↓
WriteMemEx
    ↓
ReadMemEx
    ↓
Verify
```

不要回退为“输入后再点 Write 按钮”。

## Average Copy

剪贴板只复制数值，TAB 分隔，直接粘贴 Excel 一行：

```text
38.0523545\t-7.69749951\t125.3
```

不弹窗，只写 Log。

---

# 6. Watch 卡顿问题

症状：大约 20+ 变量后 GUI 明显卡。

根因：每个采样点逐个更新 Current/Avg/Min/Max。

示例：20变量 × 4列 × 100Hz = 8000 次 Cell 更新/秒。

解决：

- JLinkWorker 内采样 + 在线统计。
- GUI 只收 Latest Snapshot。
- GUI 刷新约 25 Hz。
- 批量更新。
- 关闭动态 ResizeToContents。
- row_id → row 映射。

结果：20+ Watch 已无明显卡顿。

---

# 7. AXF / ELF / DWARF

## Symbol Browser

```text
AXF → ELF Symbol Table → DWARF → Global/Static/Struct/Array/Member → Symbol Browser → Watch/Scope
```

## ARMCC5 DWARF3 真实兼容

真实 AXF：ARM Compiler 5.06 / DWARF3。

真实变量：

```text
BlowerParamsObj = 0x20002894
m_PosSpeed      offset 132 → 0x20002918
m_Position      offset 136 → 0x2000291C
```

旧解析器漏成员原因：

```text
DW_AT_data_member_location
uses DW_FORM_block + DW_OP_plus_uconst
```

旧代码只支持 constant/exprloc。

修复：增加 ARMCC5 DWARF2/3 成员 offset 解析。

真实 AXF 解析量大约：

- 4398 symbol/member records
- 4055 watchable

## Symbol Search 卡顿

旧版：每输入字符清表、重建几百/几千行。

修复：

- `QStandardItemModel`
- `QSortFilterProxyModel`
- `QTreeView`
- debounce

## AXF Reload Rebind

```text
Parse AXF
 ↓
按完整 Name 匹配
 ↓
更新 Address / Type
 ↓
清旧统计
 ↓
不存在 → 删除变量
```

---

# 8. Scope V0.3 功能

采样源：HSS / RTT。

已实现：

- AXF 添加通道。
- Overlay / Stacked。
- Sampling Rate。
- Actual Hz。
- Buffer。
- FPS 1~60。
- Follow Latest。
- View All。
- Show。
- Start / Pause。
- Gain / Offset。
- Color。
- Current / Avg / Min / Max。
- Mouse Probe。
- X1/X2/Y1/Y2。
- Value@X1/Value@X2。
- CSV Export。
- History Mode。
- Interaction Mode / Cache。
- Visible-window peak-preserve downsample。

RTT 不是独立 Console 页面，而是 Scope 的采样源之一。

---

# 9. HSS Timestamp 大 Bug

症状：固定 1000 的变量画成递增/三角波；int16 更异常。

根因：HSS 第一个字段是 Timestamp，旧代码把 Timestamp 当成变量数据。

正确 Frame：

```text
[Timestamp U32][Payload]
```

修复：

- Timestamp 单独解析为 X。
- Payload 才走 int16/uint32/float 等类型解码。
- X 使用 `(timestamp - first_timestamp)/1e6`。

---

# 10. Scope Buffer 长时间卡顿

旧实现：每批数据 `np.concatenate(old, new)`，每次复制整个历史。

结果：数据越多越卡。

修复：Chunked Scope Buffer，小 chunk 累积并周期性合并。

---

# 11. Sampling / FPS / Actual

Buffer 用户可设，默认约 30s。

FPS：1~60。

必须理解：

```text
Requested Sampling
      ↓
J-Link / HSS
      ↓
Actual Sampling
      ↓
Raw Buffer
      ↓
Display FPS
```

真实测试：

```text
Requested = 1000 Hz
Actual ≈ 496~499 Hz
```

环境：GD32F425 / SWD 6000kHz / 3 channels / J-Link DLL V8.10。

不要把这个直接归因于 GUI 丢点，需要继续查 HSS/J-Link 吞吐。

---

# 12. Follow / View All

## Follow

只负责 X 轴跟最新。

如果用户将 X 窗口缩成 2s：

```text
Follow → [latest-2s, latest]
```

不能自动改 YRange。

左键拖动超过阈值：自动关闭 Follow。

## View All

正确语义：

```text
Xmin = Buffer first time
Xmax = Buffer last time
```

Overlay：所有 visible channel 的 display Min/Max。

Stacked：各自独立 Y fit。

---

# 13. Pause / Start / Show

## Pause

必须：

- 停 HSS/RTT。
- 保留 Raw Buffer。
- 保留 Statistics。
- 保留 X/Y Range。
- 保留 Cursor。
- 保留 Gain/Offset。
- 不 View All。
- 不 rebuild plot。

## Start

表示新实验：

- 清旧 Buffer。
- 清统计。
- 开始新采样。

## Show

只控制可见性：

- 隐藏时仍采样。
- 隐藏期间继续保存历史。
- 再 Show 恢复完整历史。

---

# 14. Gain / Offset / Color

```text
Y_display = Y_raw * Gain + Offset
```

快捷键：

```text
+        Gain ×1.25
-        Gain ÷1.25
Ctrl +   Offset +
Ctrl -   Offset -
```

列表选中成员后快捷键必须直接生效，不要求波形先获取焦点。

Color：

- 位于 Name 前。
- 只显示色块，不显示十六进制文本。
- 双击选色。

---

# 15. Mouse Probe / Cursor

Mouse Probe：

- 鼠标在波形内移动，有一根 X 跟随线。
- 浮窗显示所有通道该时刻 Y。

旧问题：pyqtgraph InfiniteLine + Follow 会产生大量竖线残影。

修复：Mouse X line 改成独立 QWidget / pixel overlay，不参与 ViewBox data transform。

Cursor 右键菜单：

```text
Set X1 / X2 / Y1 / Y2
Delete X1 / X2 / Y1 / Y2
Delete All Cursor
Export Buffer
Clear Buffer
```

Value@X 使用最近真实采样点。

---

# 16. Visible Window Downsampling

旧错误：

```text
30s buffer → 先全局 downsample → 再只显示100ms
```

导致用户放大后看到的点反而更少。

修复：

```text
Raw Buffer → 先切当前 XRange → 再判断是否 downsample
```

1000Hz 看 100ms，理论上应能看到约100个真实采样点。

Downsample 使用 Min/Max Peak Preserve。

---

# 17. Absolute Sample Index

旧问题：滚动 buffer 删除左侧样本后，全局 downsample 相位变化，视觉像波形左右抖。

修复：每个 Sample 维护 absolute index，使 downsample 相位稳定。

---

# 18. History / Analyze Mode

Follow OFF 后，不只是“不移动 X”，而是静态历史分析模式。

例如当前看 10~12s，但最新采样已经到 30s：

- HSS继续。
- Raw Buffer继续。
- Statistics继续。
- 当前 10~12s Curve 不因为右侧新数据反复 setData。

只有用户拖动、Zoom、或当前历史被 Buffer 淘汰时才重绘。

---

# 19. Stacked 卡顿/卡死演进

最严重阶段：

- 2 channels Stacked 正常。
- 3 channels + Follow → 卡死/未响应。

尝试与修复：

- pyqtgraph XLink → 自定义 X 同步。
- Follow setXRange 限频。
- Follow 与 FPS 解耦。
- 总 ViewBox 更新预算。
- 只 Master 监听 XRange。
- 批量更新。
- History Mode。
- Interaction Mode。
- Interaction Cache。

现状：已经基本避免直接卡死，但仍达不到 J-Scope 的丝滑手感，Stacked 比 Overlay 明显更重。

---

# 20. 固定 Render Clock

旧问题：HSS chunk 到达存在抖动，UI 只在数据来了才刷新，视觉上“有时快、有时慢”。

修复：GUI FPS Timer 成为唯一 Render Clock，数据 arrival 与显示节奏分离。

注意：Viewport 可平滑推进，但不能制造虚假采样点。

---

# 21. Interaction Mode / Cache（V0.3.16）

目标：专门优化鼠标拖动。

拖动开始：

- 准备轻量整段显示缓存。
- Follow OFF。
- 冻结 Curve setData / Hover / Statistics table refresh / 非必要 GUI work。

继续：

- HSS / RTT。
- Raw Buffer。
- Statistics。

拖动期间主要只做 ViewBox Transform。

鼠标释放：按最终 XRange 做一次精确 redraw。

同时 `PlotDataItem` → `PlotCurveItem`，减少多余 Scatter/DataMapping 开销。

---

# 22. 当前最大未解决问题

## A. J-Scope 级丝滑拖动

V0.3.16 已经大量修补，但仍有差距。

可能根因：当前 Stacked 仍有多个 Plot/ViewBox/Scene 更新成本。

如果停止修补，推荐 V0.4：

```text
Raw Buffer
   ↓
LOD Pyramid
   ↓
Render Cache
   ↓
GraphicsLayoutWidget / Single Scene
   ↓
View Transform
```

理想目标：拖动只移动“摄像机”，不触发数据切片/downsample/setData。

Stacked 推荐从：

```text
QVBoxLayout
 ├ PlotWidget
 ├ PlotWidget
 └ PlotWidget
```

改为：

```text
GraphicsLayoutWidget
 ├ PlotItem
 ├ PlotItem
 └ PlotItem
```

进一步可考虑 Single ViewBox + lane coordinate mapping。

## B. HSS Actual Hz

1000Hz request → ~496~499Hz actual 未定位。

继续检查：

- J-Link型号。
- SWD speed。
- channel count。
- channel width。
- 地址是否连续。
- HSS period / flags。
- DLL版本。
- transfer strategy。

## C. J-Link DLL 跨电脑兼容

不同 DLL 版本可能导致 Device Dialog 失败。

建议后续加入：

- DLL Path。
- DLL Version。
- Exported API capability。
- Return code。
- 新旧 SelectDialog 兼容。

## D. RTT

RTT Scope 路径已接入，真实板级验证仍不足。

---

# 23. 当前功能清单

## Connection
- J-Link directory scan
- DLL selection
- Device / native Target Device Settings
- SWD / JTAG
- Speed
- Connect / Disconnect

## Memory
- ReadMemEx / WriteMemEx / Verify
- 全基础整数/浮点类型

## Watch
- 多变量
- Sample interval/rate
- Current / Average / Min / Max
- Clear
- Set Value + Enter
- Multi-select delete
- Copy averages to Excel row
- Config persistence

## AXF
- ELF symbol
- DWARF
- ARMCC5 DWARF3
- Struct / Array
- Fast filter/search
- Add Watch / Scope
- Reload Rebind

## Scope
- HSS / RTT
- Overlay / Stacked
- Buffer / FPS / Actual Hz
- View All / Follow / Show / Start / Pause
- Gain / Offset / Color
- Current / Avg / Min / Max
- Mouse Probe
- X1/X2/Y1/Y2
- Value@X1/Value@X2
- CSV
- History Mode
- Interaction Mode / Cache
- Visible Window + Peak Preserve Downsample

---

# 24. 新 AI 接手阅读顺序

1. JLinkWorker / JLink backend。
2. HSS reader/parser。
3. Scope Raw Buffer。
4. Symbol parser/model。
5. Watch sample/statistics pipeline。
6. Scope display pipeline。
7. ViewBox / Follow / Interaction logic。
8. UI table event handling。

---

# 25. 禁止回退的旧方案

不要：

- GUI QTimer 直接调用 ReadMemEx。
- Sampling 1000Hz 就让 Qt 表格 1000Hz 刷。
- Show OFF 时停止采样或清数据。
- Pause 时 View All。
- Start 时继续拼接上一轮实验。
- 长缓存重新改回每帧整段 `np.concatenate`。
- Symbol 搜索每个字符重建 UI。
- Gain/Offset 修改 Raw Buffer。
- pyqtgraph AutoRange 与自定义 Follow 同时开。
- 先全局 Downsample 再 Zoom。
- 把 Requested Hz 当真实 Actual Hz。
- 未做性能验证就恢复大量双向 XLink。

---

# 26. 推荐后续性能指标

下一位 AI/开发者应加入：

```text
HSS Actual Hz
HSS Read Time
Raw Buffer Append Time
Visible Slice Time
Downsample Time
Gain/Offset Time
Curve setData Time
ViewBox Follow Time
Stacked X Sync Time
GUI Render FPS
Dropped Render Frames
Qt Event Loop Stall
```

目标是把“感觉卡”变成可测量问题。

---

# 27. 给新模型的最短 Prompt

> 我正在继续开发 MCU Debug Assistant。请先完整阅读本文件，不要推翻已有架构。当前版本 V0.3.16。底层使用 Python/PySide6/pyqtgraph/J-Link DLL；Watch 使用 ReadMemEx/WriteMemEx；Scope 支持 HSS/RTT；AXF/ELF/DWARF 已支持 ARMCC5 DWARF3 结构体成员。最重要的约束是 JLinkWorker 单Owner、Sampling与GUI FPS解耦、Raw与Display分离、Show不影响采样、Pause不清数据、Start清旧实验、Gain/Offset只影响Display、AXF Reload必须重绑定地址。目前最大问题是 Scope 尤其 Stacked 的拖动/Follow仍达不到 J-Scope丝滑手感；已有 Chunk Buffer、Visible Window Downsample、Peak Preserve、Fixed Render Clock、History Mode、Interaction Mode、Interaction Cache 等优化。不要退回旧方案。若继续修补，优先做性能测量和减少 ViewBox/setData 工作；若升级架构，考虑 GraphicsLayoutWidget 单Scene + LOD Pyramid + Render Cache。
