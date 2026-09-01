# ADR

## ADR-001 — Single J-Link Owner
所有 J-Link DLL 访问由单 Worker/Owner 承担。

## ADR-002 — Raw / Display Separation
显示变换不能修改 Raw Data。

## ADR-003 — Sampling / UI Decoupling
Acquisition、Curve Update、Table Refresh、Presentation FPS 分离。

## ADR-004 — Single ViewBox Stacked
Stacked 使用 Logical Lanes 减少多 ViewBox/Axis 成本。

## ADR-005 — CPU Raster Main Renderer
QOpenGLWidget 实机无优势，CPU Raster 作为主路径。

## ADR-006 — Instrument Before Rewrite
不明 Stall 优先测量，不连续凭猜测重写多个层。

## ADR-007 — Release Performance Outside Debugger
正式高刷性能必须使用 RUN 模式，不以 debugpy/pydevd 结果验收。

## ADR-008 — Release Scope Has No Default Stall Instrumentation
正式 Scope 默认路径不创建 performance watchdog、诊断写线程或额外
event-loop Timer，也不持续执行 Worker/Paint/Presentation 分段计时。
未来如需恢复诊断，必须使用显式且默认关闭的开关；关闭时不得安装
诊断 Timer/线程/Signal，也不得在热路径构造日志或更新时间统计。


## ADR-009 — Release Presentation Uses Single-shot Absolute Deadlines
V0.4.23 将 V0.4.20/V0.4.21 的高频 persistent timer polling 替换为 single-shot `Qt.PreciseTimer` + floating-point absolute deadline。

理由：persistent driver 的必要性主要来自 debugger 阶段 timer-starvation 观察；在 Release 路径中它会产生明显多于目标 FPS 的 Qt timer callbacks。Single-shot 方案让 timer callback 数量接近 presentation frame 数，同时继续 skip missed slots、禁止 catch-up burst。

回退条件：只有新的 **RUN/非 debugpy** 实机证据证明 single-shot timer delivery 不可靠，才允许重新评估 persistent driver；不得直接恢复旧 Stall instrumentation。

## ADR-010 — Memory Explorer Uses Visible-Range Reads
V0.5.0 的 Memory Explorer 使用虚拟 32-bit 地址滚动，但只向 J-Link 请求当前可见行附近的小块数据。滚动请求 debounce，已被当前 block 覆盖时不重复读。

理由：MCU 的 SWD/J-Link 访问成本远高于本机进程内存，而且 Memory-mapped Peripheral 的读取可能具有硬件副作用。不能照搬 PC Cheat Engine 的全地址扫描/大范围 speculative read。

## ADR-011 — Default Memory Writes Do Not Read Back Verify
V0.5.0 中普通 Typed Write、Watch Write、Memory Explorer Write 以 `JLINK_WriteMemEx` 返回完整写入长度作为成功条件，默认不追加 `JLINK_ReadMemEx` 校验。

理由：用户明确要求去掉每次写后的重复读取成本；原 `write_and_verify()` 保留为底层可选能力，但不在默认产品写路径调用。需要确认目标当前值时，由用户显式 Read/F5。

## ADR-012 — Memory Explorer Direct Edit Uses One Confirmation Boundary
V0.5.1 将 Memory Explorer 的交互写入分成两类：
- Byte Hex/Text 直接键入、粘贴属于显式 direct edit，立即发送写请求；
- 双击 Value/Text 先进入编辑弹窗，用户点击 OK 即视为确认。

MainWindow 不再为 Memory Explorer 额外叠加第二层 `QMessageBox.question()`。独立 Typed Memory R/W 表单仍保留其原有显式确认。

理由：第二层确认会破坏 Cheat Engine 式连续内存编辑，并使 Text/Hex 直接输入无法成立。该决策只改变 Memory Explorer 的 UI confirmation boundary，不改变单 J-Link Owner、WriteMemEx-only 成功语义和可见窗口读取策略。

## ADR-013 — Memory Symbol Search Is Local and Model-backed
V0.5.3 的 Memory `Address / Symbol` 输入不在每个字符输入时重新构建符号控件，也不访问 J-Link。AXF/ELF/DWARF 加载时一次建立 `SymbolIndex` 和扁平 completion model；输入阶段使用 Qt `QCompleter + MatchContains` 本地过滤，Enter 确认后才进入既有 `goto_address → visible-window ReadMemEx` 链。

理由：符号搜索是纯元数据操作，与目标内存读取无关；把每次键入绑定到模型重建或 J-Link I/O 会复现早期 Watch/AXF 搜索卡顿。数组和结构体地址直接复用 parser 已展开的完整路径，不新增运行时 C 表达式求值器。

