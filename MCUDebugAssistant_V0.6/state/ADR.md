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


## ADR-014 — Memory Symbol Width Is Presentation State
V0.5.5 允许用户拖动 Memory Symbol/Hex 分隔线并持久化 `symbol_width_px`。该动作只更新本地 column geometry、horizontal scrollbar 和 repaint，禁止触发 AXF/DWARF 重解析、Symbol model rebuild 或 J-Link I/O。

理由：长结构体/数组成员路径需要临时展开查看，但列宽调整本质是 Presentation 需求，不应污染符号解析或目标访问热路径。

## ADR-015 — Watch Set Value Commits on Enter or Modified Focus-out
V0.5.5 将 Set Value 的提交边界定义为“用户完成一次实际编辑”：`textEdited` 后，Enter 或 editor 的 `editingFinished` 都执行一次 commit + write。未修改的 focus-out 不写；dirty 在首次 commit 前清零，避免 Return 与 editingFinished 对同一次编辑重复写。

理由：只监听 `returnPressed` 会让点击别处时出现 UI 已提交但目标未写的语义不一致；而无 dirty guard 的 focus-out 又可能造成误写或双写。

## ADR-016 — Test Automation Is an Orchestration Layer, Not a Second Debugger Owner
V0.6.0 的 Test Automation 只负责 Parameter Matrix、Workflow 状态机、稳态/统计/判定和结果组织。所有目标读写仍通过现有唯一 `JLinkWorker`。Automation Page 不 import/call J-Link Backend。

V0.6.0 为确定执行时序，在 Test Run 启动时停止 Watch/Scope 连续采样，再以 request/response polling 执行 SET / WAIT / SAMPLE。未来若需要测试期间同步高带宽 Scope，必须设计共享采样源或调度优先级，不能再开第二 Session。

理由：自动化测试应该复用已有 Runtime I/O，而不是制造新的 Probe 竞争和并发语义。

## ADR-017 — No-code Plans Use Structured Tokens and Operations, Not eval/exec
Test Plan 中参数通过 `${Name}` Token 引用；CALCULATE / ASSERT 只允许白名单运算和比较。V0.6.0 不执行任意 Python、YAML 表达式、`eval()` 或 `exec()`。

理由：测试方案需要可保存、可审查、可复现，并可未来迁移到不同 Probe/外部仪器。任意脚本执行会把安全性、可验证性和 UI 无代码目标一起破坏。

## ADR-018 — Parameter Matrix and Workflow Are Separate Product Concepts
Parameter Matrix 定义“测哪些参数组合”；Workflow 定义“每个 Case 如何执行”。呼吸机 RPM、PEEP、电机 SpeedRef、BMS 电压等都只是 Matrix 数据，不进入 Workflow Engine 的业务分支。

理由：防止 Test Automation 演化成大量产品专用页面，同时避免用户为了枚举自己手写 Loop/Script。


## ADR-019 — Keep the Default No-code Workflow Surface Small
V0.6.1 新建步骤只暴露 SET / WAIT / WAIT STABLE / SAMPLE / MANUAL INPUT / SAVE RESULT。WAIT UNTIL / CALCULATE / ASSERT 在 V0.6.0 中已实现，但当前用户场景认为不必要，因此只作为旧 Test Plan 兼容能力保留。这样减少配置噪声，同时避免破坏已保存计划。

## ADR-020 — Rebuild Dynamic Step Forms by Recursive Layout Destruction
StepDialog 切换 Step Type 时必须递归清理嵌套 QLayout 与其 child widgets。原因：QFormLayout/QHBoxLayout 不是 `item.widget()`，只删除顶层 widget 会使旧标签残留并覆盖新 UI。该变更限定在 Presentation/UI 生命周期，不触及 Worker、Polling 或 Test Engine。


## ADR-021 — Runtime Context Is Not the Test Result Schema
V0.6.2 将 Automation `_context` 定义为执行期内部状态容器，而不是最终 Results/CSV 的列集合。SAMPLE 可内部保留 Count/Avg/Min/Max/Std 以支持诊断和旧计划，但 Case Result 只通过显式 output-key 投影：Parameter、用户选中的统计、Manual Input 和显式计算/判定输出。新 SAMPLE 默认仅输出 Avg，Count 永不作为默认用户结果。

理由：把整个运行上下文直接导出会泄漏 `.current/.stable_spread/count/std` 等内部字段，降低无代码测试结果可读性，并把执行实现细节错误地固化为产品结果 schema。


## ADR-022 — Results Persist Across Runs and Copy as TSV
V0.6.3 将 Automation Results 定义为用户显式积累的数据集，而不是单次 Run 的临时缓存。`Run All` 只重置当前执行状态，不清空 `_results`；运行结束只清空 Runtime 表。历史结果只能通过 Results 页 `Clear Results` 在用户确认后清除。

Results 的快速外部交换采用带表头 TSV 写入系统剪贴板，而不是每次弹出 CSV 文件保存流程。Excel 可直接按 Tab/换行解析为二维表。

理由：真实标定/枚举场景通常需要连续跑多轮并累积结果，然后直接粘贴到现有 Excel 分析表；自动清空与文件导出会打断该工作流。
