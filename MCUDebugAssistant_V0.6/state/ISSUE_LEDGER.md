# ISSUE_LEDGER

## UX-MEMORY-SYMBOL-TYPED-NAV-V066
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE / PENDING_HARDWARE
Severity: medium

### User request
Memory Address/Symbol 查询历史除了 Symbol/地址外还需要显示成员类型；跳转到 AXF/DWARF 标量成员时，Memory 内存值显示应第一次就采用该变量类型，例如 `uint8` 自动切换成 `UInt8`，而不是仍保持 Byte Hex。

### Design / Fix
- 历史仍使用独立小型 MRU，不污染 AXF Completion Model；popup 改为 History / Type / Address 三列，编辑框 320~520 px 尺寸不变。
- Type/Address 元数据从当前 SymbolIndex 本地解析，AXF reload 后刷新；无 ReadMemEx/WriteMemEx。
- `_goto_symbol()` 对受支持的 exact scalar `type_name` 先应用 Memory display type，再 goto 地址；struct/array/unknown 与纯数值地址不猜类型。

### Verification
- compileall: PASS
- full pytest: 97 passed
- symbol datatype helper + static typed-navigation/history regression: PASS
- Windows/PySide6 three-column history popup visual smoke: PENDING_USER_QT_SMOKE
- Real AXF/J-Link `uint8/int16/float` jump display: PENDING_HARDWARE

## FIX-MEMORY-HISTORY-QT6-SIGNAL-V065
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE
Severity: high

### User evidence / symptom
V0.6.4 crashes during `MemoryExplorerPage` construction with `IndexError: Signature "activated(QString)" not found for signal: "activated". Available candidates: "activated(int)"`. A `QThread: Destroyed while thread ... is still running` message follows process teardown.

### Root Cause
The V0.6.4 history combo used PyQt/older-overload style `self.address_combo.activated[str]`. In the user's PySide6/Qt6 binding, QComboBox exposes `activated(int)` and does not provide `activated(QString)` under that signal name. The constructor therefore throws before the window finishes building.

### Fix
Connect `self.address_combo.activated` to an integer-index handler. Resolve the selected history text with `itemText(index)` and reuse the existing `_goto()` path. No new target I/O or Symbol model rebuild is added.

### Verification
- compileall/pytest: see V0.6.5 TEST_STATUS
- user Windows/PySide6 startup: PENDING_USER_QT_SMOKE
- real history selection with AXF/J-Link: PENDING_HARDWARE

## UX-AUTOMATION-RESULT-HISTORY-V063
Status: CODE_COMPLETE / PENDING_QT_SMOKE / PENDING_HARDWARE
Severity: medium

### User evidence / expected behavior
用户希望 Results 保留稳态采样的平均值、最小值、最大值；Run 只在整轮执行结束后清空运行态内容。新一轮 Run 不应自动删除历史 Results。原 Export CSV 应改为 Results 页内一键复制到剪贴板，直接粘贴 Excel，并提供手动 Clear Results。

### Root Cause / product mismatch
V0.6.2 为解决内部统计泄漏，把新 SAMPLE 默认收敛成 Avg-only，并在 `_run_all()` 启动时清空 `_results`。CSV 导出也放在顶层 toolbar，和用户“连续测量、累计结果、直接贴 Excel”的真实工作流不匹配。

### Fix
- 新 SAMPLE 默认正式输出 Avg/Min/Max；Std 仍可显式选择，Count 仍内部。
- `_run_all()` 不再清空 Results；新 Case 继续 append。
- 全部 Case 完成仍只清空 Runtime 表并自动切 Results。
- 顶层 Export CSV 移除；Results 页新增 Copy Results（TSV + header → clipboard）和 Clear Results。
- Clear Results 需用户确认，并是正常 UI 中唯一清空累计结果的入口。

### Verification
- compileall: PASS
- full pytest: 87 passed
- V0.6.3 persistent-result / TSV-copy / manual-clear static regression: PASS
- Qt clipboard/button smoke: PENDING_ENVIRONMENT
- Real AXF/J-Link accumulated multi-run results: PENDING_HARDWARE

## UX-AUTOMATION-RESULTS-V062
Status: CODE_COMPLETE / PENDING_QT_SMOKE / PENDING_HARDWARE
Severity: medium

### User evidence / symptom
用户实机截图显示测试完成后 Run 页仍保留最后一个 Case 的 `Symbol.avg/count/max/min/std` 等字段；用户只需要稳态平均值，`count/std` 等被视为结果噪声。

### Root Cause
V0.6.1 的 SAMPLE `flatten()` 把 Count/Avg/Min/Max/Std 全部写入 `_context`，而 `_finish_case()` 又把整个 `_context` 无差别导出 Results。Runtime 执行状态和正式测试结果没有边界；运行完成后 UI 也停留在 Run 页。

### Fix
- SAMPLE 内部仍计算全部统计，保持旧 CALCULATE/ASSERT 兼容。
- 新 SAMPLE Step 增加 Result Statistics：Avg/Min/Max/Std，默认仅 Avg；Count 不作为可选结果。
- 每个 Case 使用显式 output-key 投影结果，仅 Parameter、选中 SAMPLE 指标、Manual Input 与显式 legacy output 进入 Results/CSV。
- Run 完成后清空最后 Runtime 表并自动切换 Results。

### Verification
- compileall: PASS
- full pytest: 82 passed
- V0.6.2 result-projection static regression: PASS
- Qt visual smoke: PENDING_ENVIRONMENT
- Real AXF/J-Link result columns: PENDING_HARDWARE


## FIX-AUTOMATION-STEP-DIALOG-OVERLAP-V061
Status: CODE_COMPLETE / PENDING_QT_SMOKE
Severity: high

### Symptom
Workflow Step 对话框切换 Assert/Calculate/其它 Step Type 后，旧 Label/Edit 与新表单重叠，表现为文字“花掉”。

### Root Cause
`_clear_body()` 只删除 `QLayoutItem.widget()`，没有递归处理 `QLayoutItem.layout()`。QFormLayout/QHBoxLayout 的 child labels/editors 因此残留。

### Fix
递归销毁 nested layout/widget tree 后再 rebuild body。

### Verification
- static regression: recursive layout clear path present
- Qt visual smoke: PENDING_ENVIRONMENT

## UX-AUTOMATION-SIMPLIFY-STEPS-V061
Status: CODE_COMPLETE
Severity: medium

### Decision
新建步骤只显示 SET / WAIT / WAIT STABLE / SAMPLE / MANUAL INPUT / SAVE RESULT。WAIT UNTIL / CALCULATE / ASSERT 不再作为默认 UI 能力；旧 V0.6.0 plan 仍可加载/执行/编辑对应 legacy node。



## FEAT-TEST-AUTOMATION-V060
Status: CODE_COMPLETE / PENDING_QT_SMOKE / PENDING_HARDWARE

### Version
V0.6.0

### User scenario / goal
用户需要无代码自动测试：枚举多组 MCU 设置值（首个真实场景为呼吸机转速），写目标变量，等待压力/流量按波动窗口进入稳态或超时，再采集稳态平均值，人工输入外部设备测量值，保存结果并自动进入下一组。后续希望同一机制可用于电机/BMS/电源等，不被某个产品页面写死。

### Product decision
- Parameter Matrix 与 Workflow 分离。
- Matrix 负责 List/Range 和 Cartesian/Zip 枚举；Workflow 负责每个 Case 的通用步骤。
- 不要求用户写 Python/YAML；不使用 eval/exec。
- 呼吸机只是默认模板，不是引擎分支。

### Acceptance Criteria
- Parameter List/Range，支持 Cartesian Product 和 Zip，并可 Preview Cases。
- Workflow 至少支持 SET / WAIT / WAIT UNTIL / WAIT STABLE / SAMPLE / MANUAL INPUT / CALCULATE / ASSERT / SAVE RESULT。
- SET/WAIT/SAMPLE 变量使用已加载 AXF/DWARF 完整 Symbol Path。
- WAIT STABLE 支持多 Signal Max-Min threshold、Window、Hold、Polling、Timeout、Continue/Skip/Stop。
- SAMPLE 在稳态之后独立统计 Count/Avg/Min/Max/Std。
- MANUAL INPUT 可录入外部压力/流量等测量值；后续仪器接入不改 Test Engine。
- Plan 可保存/加载 JSON；Results 可导出 CSV。
- GUI 不直接访问 J-Link；Automation 读写由唯一 JLinkWorker 完成。
- Test Run 不与 Watch/Scope 连续采样无界竞争；V0.6.0 启动 Run 时停止两者。

### Implementation
- `core/test_automation.py`: Parameter case generation、Token resolution、StableDetector、Sample statistics、Calculate/Assert。
- `ui/automation_page.py`: Parameter Matrix、Workflow Editor、Run/Results、Manual Input、Plan JSON、CSV。
- `debugger/jlink_worker.py`: automation snapshot / typed write request-response API。
- `ui/main_window.py`: Test Automation tab、worker wiring、AXF symbol propagation、settings persistence、exclusive polling start semantics。

### Verification
- compileall: PASS
- full pytest: 75 passed
- pure-core Parameter/Stable/Sample/Calculate/Assert regression: PASS
- static single-owner/UI wiring regression: PASS
- Qt runtime smoke: PENDING_ENVIRONMENT
- real AXF/J-Link run: PENDING_HARDWARE
- external instrument automatic read: NOT IMPLEMENTED (manual input only)

### Confidence
- Core algorithms/model: VERIFIED_AUTOMATED
- Static architecture wiring: VERIFIED_AUTOMATED
- Qt interaction: PENDING_ENVIRONMENT
- Hardware workflow timing/results: PENDING_HARDWARE

---

## FIX-MEMORY-SYMBOL-WIDTH-V055
Status: CODE_COMPLETE / PENDING_USER_HARDWARE

### Version
V0.5.5

### Symptom
Memory Symbol 列宽固定，长变量/成员路径只能看到 elide 文本，用户无法主动拉宽查看完整名称。

### Root cause
自绘 `HexMemoryView._column_geometry()` 将 Symbol 宽度硬编码为 `cw * 32`，没有任何 resize hit-test / drag state。

### Fix
- Symbol/Hex 分隔线增加 SizeHor hit-test 与拖动 resize。
- 宽度限制 12~120 等宽字符；双击分隔线恢复默认。
- `symbol_width_px` 纳入 Memory Explorer settings 持久化。
- resize 只重算本地 geometry/scrollbar/repaint，不访问 J-Link。

### Verification
- compileall: PASS
- pytest: 63 passed
- static regression: PASS
- Real Windows drag/visual behavior: PENDING_USER_HARDWARE

---

## FIX-WATCH-SETVALUE-FOCUSOUT-V055
Status: CODE_COMPLETE / PENDING_USER_HARDWARE

### Version
V0.5.5

### Symptom
Watch Set Value 输入新值后，如果不按 Enter 而直接点击其它位置，编辑内容可离开 editor，但不会触发 MCU 写入。

### Root cause
旧 `SetValueDelegate` 的 `write_requested` 只由 `QLineEdit.returnPressed` 驱动；focus-out 的常规 model commit 没有对应 target write 信号。

### Fix
- `textEdited` 标记 dirty。
- Enter 与 `editingFinished` 共用 `commit_if_dirty()`：先 `commitData`，下一 event-loop turn 发 write request。
- commit 前清 dirty，避免 Enter 之后紧接 editingFinished 对同一次编辑重复写。
- 未修改 editor 的 focus-out 不写。

### Verification
- compileall: PASS
- pytest: 63 passed
- static delegate regression: PASS
- Real J-Link click-away write: PENDING_USER_HARDWARE

---

## FIX-MEMORY-SYMBOL-POPUP-V054
Status: CODE_COMPLETE / PENDING_USER_HARDWARE

### Version
V0.5.4

### User evidence / symptom
用户截图中 `Address / Symbol` 输入 `MaxRp`，Memory Symbol 列已经显示真实 `MaxRpm`，说明 AXF/SymbolIndex 中变量存在；但 completion popup 只显示 `Symbol / Type / Address` 表头，候选数据行不可见，窗口高度明显过短。

### Root cause / strongest hypothesis
自定义多列 `QTreeView` 作为 `QCompleter` popup 时，Windows/Qt 样式下 popup 初次按 row size hint 计算几何，可能在候选行尚未形成稳定 size hint 时把高度压缩到接近 header-only。符号数据本身并未缺失。

### Fix
- `ui/memory_explorer.py`: completion `QTreeView` 设置稳定 `minimumHeight=240`、`maximumHeight=420`。
- 不增加 `textChanged/textEdited` 热路径，不改变 AXF model 构建、MatchContains 过滤或 J-Link 访问链。

### Acceptance Criteria
- 输入 `MaxRp` 等短/部分变量名时，只要 SymbolIndex 中存在匹配项，popup 至少可见若干候选行，不再只有表头。
- Symbol / Type / Address 三列继续显示。
- 键入过程不新增 J-Link ReadMemEx、AXF 重解析或模型重建。

### Verification
- User screenshot symptom: VERIFIED_USER_HARDWARE
- Static geometry regression: PASS
- compileall: PASS
- full pytest: 59 passed
- Real Windows/PySide6 popup after fix: PENDING_USER_HARDWARE

### Confidence
- Symptom/root-cause match: HIGH HYPOTHESIS supported by screenshot geometry
- Code fix/static semantics: VERIFIED_AUTOMATED after release tests
- Final GUI behavior: PENDING_USER_HARDWARE

---


## FEAT-MEMORY-SYMBOL-JUMP-V053
Status: CODE_COMPLETE / PENDING_QT_SMOKE / PENDING_HARDWARE

### Version
V0.5.3

### User evidence / symptoms
1. Memory Address 只能输入数值地址，不能直接输入 AXF 变量名换算并跳转。
2. 希望支持解析器已有的结构体成员和数组路径，例如 `buffer[1]`。
3. 输入部分变量名时，希望像 Watch AXF 成员搜索一样在输入框下方实时过滤候选，按 Enter 确认，而且不能因搜索导致卡顿。

### Acceptance Criteria
- 同一个 Address / Symbol 输入框接受数值地址和完整符号路径。
- `foo.bar`、`buffer[1]`、`ctrl.channels[1].gain` 等已由 AXF/DWARF parser 展开的路径可精确解析地址。
- 部分输入显示 Symbol / Type / Address 候选列表，MatchContains、大小写不敏感。
- Enter 可确认当前候选或完整符号并跳到目标地址。
- Symbol model 只在 AXF load/reload 时构建；每个键入字符不重建 model、不解析 AXF、不触发 J-Link。
- 现有数值地址 Go、visible-window read、单 J-Link Owner 不变。

### Implementation
- `core/memory_browser.py`: `SymbolIndex` 新增一次构建的 name index、`exact_name()`、`preferred_symbols()`、`search_names()`。
- `ui/memory_explorer.py`: Address 改为 Address / Symbol；新增多列 `QStandardItemModel + QCompleter(MatchContains)`，候选显示 Symbol / Type / Address。
- AXF set_symbols 时离屏构建完整 completion model 后一次 swap；输入热路径只走 Qt 本地 filter。
- 完整符号或当前 completion Enter 后调用既有 `goto_address()`，此时才按 visible-window 规则读取目标内存。

### Verification
- compileall: PASS
- pytest: 57 passed
- exact member/array name regression: PASS
- model-backed/no-per-key-J-Link static regression: PASS
- Qt completer popup runtime: PENDING_ENVIRONMENT
- real AXF + J-Link goto: PENDING_HARDWARE

### Confidence
- Core symbol-name resolution: VERIFIED_AUTOMATED
- UI wiring/static hot-path semantics: VERIFIED_AUTOMATED
- Qt popup interaction: PENDING_ENVIRONMENT
- Hardware address navigation: PENDING_HARDWARE

---

## FIX-AXF-AUTOLOAD-V052
Status: CODE_COMPLETE / PENDING_QT_SMOKE

### Version
V0.5.2

### User evidence / symptom
程序启动后虽然会恢复上一次 AXF/ELF 路径文本，但不会自动调用解析器，因此 Memory Explorer 首次进入时 SymbolIndex 为空，必须再次手工“重新加载”。

### Expected behavior
如果保存的 AXF/ELF 文件仍然存在，应用启动后自动加载符号，并同步 Memory / Watch / Scope。

### Root cause
`_load_settings()` 只执行 `symbol_file_edit.setText(...)`，没有调用 `_load_symbol_file()`。

### Fix
- MainWindow 完成 UI/settings 初始化后使用 `QTimer.singleShot(0, self._auto_load_saved_symbol_file)`。
- helper 只检查明确保存路径；`Path.is_file()` 成功才调用 `_load_symbol_file(..., rebind_watch=True)`。
- 路径失效时仅 Log + skip，不扫描目录猜测其它 AXF。

### Verification
- compileall: PASS
- pytest: 53 passed
- targeted static regression: PASS
- Qt startup with real AXF: PENDING_ENVIRONMENT
- Real AXF/DWARF + J-Link: PENDING_HARDWARE

### Confidence
- Static/startup wiring: VERIFIED_AUTOMATED
- GUI runtime: PENDING_ENVIRONMENT

---

## FEAT-MEMORY-INTERACTION-V051
Status: CODE_COMPLETE / PENDING_HARDWARE

### Version
V0.5.1

### User evidence / symptoms
1. 首次加载 Memory 没有稳定落到 `0x20000000` RAM 基址。
2. Symbol 列多个长符号拼接后无法像 CE 一样整齐对齐。
3. Text 区只能看，不能直接键入文本修改内存。
4. Address 与 Memory value 颜色相同，不易区分。
5. 只能复制单 cell，不能选择连续内存块批量复制。
6. 不能像 CE 一样直接在表格输入修改，也需要双击弹窗修改。

### Acceptance Criteria
- 新应用会话首屏稳定定位 `0x20000000`。
- Symbol 为固定列几何，单行、左对齐、超长 elide，不覆盖 Hex。
- Byte Hex cell 可直接键入两位 Hex 写入并前移。
- Text cell 可按当前编码直接键入/粘贴写入。
- 非 Byte display 支持 in-cell typed edit。
- 双击 Value/Text 弹窗编辑；OK 即确认，不再弹第二层写确认。
- 鼠标拖动/Shift 可连续选择 byte range，Ctrl+C/右键批量复制 Hex/Text。
- Address 使用不同于 Memory value 的 palette role。
- J-Link 单 Owner、visible-window read、no-readback-write 原则保持。

### Implementation
- `ui/memory_explorer.py`：新增 byte-range selection、Text hit-test、direct Hex/Text write、typed in-cell editor、block copy/paste、固定 Symbol column、地址独立 palette。
- `core/memory_browser.py`：新增 `DEFAULT_RAM_BASE`、`encode_text_input()`、`text_edit_unit_size()`、`format_hex_block()`。
- `ui/main_window.py`：Memory Explorer direct write 移除第二层 `QMessageBox`; manual Typed R/W confirmation 保留。
- Memory Explorer settings 不再恢复旧浏览地址，新会话首屏固定 SRAM base。

### Verification
- compileall: PASS
- pytest: 51 passed
- text encoding / batch clipboard regression: PASS
- direct edit/range copy/static semantics regression: PASS
- Qt smoke: PENDING_ENVIRONMENT
- Real J-Link: PENDING_HARDWARE

### Confidence
- Core/static behavior: VERIFIED_AUTOMATED
- GUI runtime: PENDING_ENVIRONMENT
- Hardware write semantics: PENDING_HARDWARE

---

## FEAT-MEMORY-EXPLORER-V050
Status: CODE_COMPLETE / PENDING_HARDWARE

### Version
V0.5.0

### Goal
把单地址 Memory R/W 升级为类似 Cheat Engine 的 MCU Memory Explorer，并支持 AXF/ELF/DWARF 符号显示；默认写入不再强制回读验证。

### Acceptance Criteria
- 32-bit 地址可跳转、滚动浏览，16 Bytes/Row。
- 只读可见窗口附近，不能全地址扫描。
- 右键可切换显示类型、文本编码、分隔符、显示符号/偏移、显示变化。
- AXF/DWARF 结构体成员可映射到对应内存地址。
- 可编辑并写入，WriteMemEx 成功后不自动 ReadMemEx Verify。
- 可从选中内存地址加入 Watch。
- J-Link 单 Owner 不变；Scope 稳定架构不重构。

### Implementation
- 新增 `core/memory_browser.py`。
- 新增 `ui/memory_explorer.py` 自绘虚拟内存视图。
- `JLinkWorker` 新增 block read/write slot + signal。
- MainWindow Memory Tab 集成 Typed R/W + Explorer。
- AXF reload 同步 Memory SymbolIndex。
- Typed/Watch write 默认改用 `write_memory()`，不调用 `write_and_verify()`。

### Verification
- compileall: PASS
- pytest: 46 passed
- Memory planner/symbol/format targeted regression: PASS
- no-readback-write static regression: PASS
- Qt smoke: PENDING_ENVIRONMENT
- Real J-Link: PENDING_HARDWARE

### Confidence
- Core/static behavior: VERIFIED_AUTOMATED
- GUI runtime: PENDING_ENVIRONMENT
- Hardware behavior: PENDING_HARDWARE

---

## PERF-SCOPE-V043-HARDWARE
Status: CODE_COMPLETE / PENDING_HARDWARE

### Version
V0.4.23

### Goal
在 V0.4.21 已清理 Stall instrumentation 的基础上，继续减少默认 Scope Release 热路径无效工作，不改变产品语义。

### Evidence
- V0.4.21 在 144 FPS 下使用 2 ms persistent presentation driver，理论触发约 500 Qt timer callbacks/s，但目标 presentation 只有 144/s。
- 60 FPS 下 driver 约 5 ms，对应约 200 callbacks/s，目标 presentation 只有 60/s。
- Persistent driver 的主要动机来自 debugger 阶段观察到的 timer starvation；后续已经确认 debugpy/pydevd 会污染高刷 Qt 调度结论。
- V0.4.21 已经删除 watchdog/event-loop/debugger/stage profiling，因此可以进一步让 Release presentation 回到更小的调度面。

### Fix
- `PresentationPacer` 改为 single-shot absolute-deadline delay generator。
- `_viewport_timer` 改为 `setSingleShot(True)`；每个 presentation frame 结束后只 arm 下一次 deadline。
- 迟到帧直接跳过，不 catch-up。
- 非采样状态使用 20 Hz presentation clock。
- GUI `append_samples()` 删除 per-chunk ring capacity 比较与 warning。

### Verification
- compileall: PASS
- pytest: 39 passed
- release cleanup regression: PASS
- presentation pacing synthetic regression: PASS
- Qt offscreen smoke: PENDING_ENVIRONMENT (PySide6 unavailable here)
- real Windows + J-Link + HSS/RTT: PENDING_HARDWARE

### Stop condition
如果 RUN 模式实机的 Overlay/Stacked/Follow/Drag/Zoom/30s/5min 回归正常，则关闭本 Issue；不要继续无证据重构 Scope。

---


## PERF-SCOPE-RELEASE-CLEANUP
Status: CODE_COMPLETE / PENDING_HARDWARE

### Version
V0.4.21

### Symptom
V0.4.20 kept the previous Stall investigation runtime enabled in the default
Scope path: watchdog and diagnostic-writer threads, a 25 ms Qt event-loop probe,
worker poll/read/decode timers, paint/presentation/stage counters and verbose
Stall classification logs.

### Expected behavior
Release Scope must keep acquisition, Ring Buffer, rendering and interaction
semantics while doing no continuous Stall investigation work by default.

### Root cause / evidence
- V0.4.18-V0.4.20 diagnostics remained wired unconditionally after the debugger
  environment was identified as a major source of event-loop disturbance.
- The 5 ms HSS poll performed poll/read/decode timing on every callback.
- Every presentation tick touched watchdog locks; a second GUI Timer fired every
  25 ms; every paint maintained FPS/jitter/percentile inputs.

### Fix
- Removed GUI watchdog, asynchronous diagnostic writer, event-loop probe,
  presentation-gap/starvation classification and debugger detection.
- Removed worker performance Signal and hot-path timing.
- Removed paint/render/follow/setData/table/hover/append telemetry and the
  diagnostic status line.
- Retained acquisition/presentation/hover product Timers, Actual Hz, Ring resize
  warning, LiveLatencyGuard and the complete Rendering V2 pipeline.

### Verification
- `compileall`: PASS
- `pytest`: 38 passed
- PySide6 offscreen ScopePage construction: PASS
- Default-release static cleanup regression: PASS
- Hardware RUN A/B: PENDING_HARDWARE

---

## PERF-QT-EVENTLOOP
Status: CLOSED_AS_DEBUG_DIAGNOSTIC

### Symptom
Scope occasionally experiences 100–900ms gaps.

### Evidence
In several logs:
- render/follow/setData/table/hover/append were sub-ms or low-ms,
- paint max was around low tens of ms,
- worker/read/decode were far below stall,
- ring resize = 0,
- watchdog classified GUI as `qt-native-event-loop`,
- Python stack showed `main.py -> app.exec()`,
- debugpy/pydevd was active.

### Conclusion
Current Scope Python functions cannot explain the full gap.
The default event-loop/watchdog investigation runtime was retired in V0.4.21.
This closure does not claim that a release-mode Qt stall can never occur.

---

## PERF-PRESENTATION-STARVATION
Status: CLOSED_AS_DEBUG_DIAGNOSTIC

### Symptom
Presentation can show a large gap while general Qt event-loop probe is less delayed.

### Direction
The persistent polling driver was a V0.4.20/V0.4.21 workaround derived from debugger-era observations.
V0.4.23 supersedes that direction with single-shot absolute-deadline pacing to reduce idle timer callbacks.
Reopen persistent polling only if new RUN-mode evidence proves single-shot delivery is unreliable.

---

## PERF-HOVER-ADJUSTSIZE
Status: FIXED

### Evidence
Watchdog stack captured:
`SignalProxy -> _mouse_moved -> _show_hover_at_host_pos -> hover_label.adjustSize()`

### Fix
Remove adjustSize from high-frequency mouse path, use cached geometry and throttled tooltip update.

---

## PERF-RING-RESIZE
Status: FIXED / DISPROVED_AS_CURRENT_STALL

Session ring preallocated.
Later logs:
`append ~0.1ms`, `resize=0`.

---

## PERF-GPU
Status: CLOSED

QOpenGLWidget viewport was not beneficial.
CPU Raster remains main path.

---

## HSS-ACTUAL-RATE
Status: OPEN

Observed example:
requested 1000Hz, actual ~496–499Hz
with GD32F425RG, SWD6000kHz, J-Link DLL V8.10, 3 channels.

Do not confuse acquisition throughput with GUI display reduction.


## FEAT-MEMORY-NAV-HISTORY-V064
- Status: CODE_COMPLETE / PENDING_QT_SMOKE / PENDING_HARDWARE
- Request: remember successful Memory Symbol/address queries, show them in a same-size editable dropdown, allow explicit clear.
- Acceptance: MRU persisted; symbol/address selectable; duplicate-safe; clear does not alter current address; no J-Link I/O while typing/opening history.
- Implementation: editable QComboBox + existing QCompleter + pure MRU helper.
