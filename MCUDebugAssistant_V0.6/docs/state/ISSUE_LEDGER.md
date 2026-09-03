# ISSUE_LEDGER

# GOV-AI-DOC-LAYOUT-V0616
- Version: V0.6.16
- Status: CODE_COMPLETE / VERIFIED_AUTOMATED
- Severity: low
- Request: reduce ZIP root clutter from accumulating Release Reports/state/dev docs while preserving reliable AI secondary-development handoff.
- Root cause: historical/current documentation used a flat/root-heavy layout; every release added another top-level file and AI entry docs referenced old paths directly.
- Fix: indexed `docs/releases`, `docs/state`, `docs/architecture`, `docs/development`; stable root entrypoints; manifest/Agent/Skill/Workflow/path references updated.
- Runtime impact: none.
- Automated evidence: compileall PASS; full pytest 136 passed; targeted V0.6.16 5 passed.
- Acceptance: no root `RELEASE_REPORT_*.md`; all manifest document paths exist; no stale active references to old `state/` or root Workflow paths; fresh AI read order documented.


## FEAT-CROSS-MODULE-SYMBOL-ACTIONS-V0615
- Version: V0.6.15
- Status: CODE_COMPLETE / VERIFIED_AUTOMATED / PENDING_USER_QT_SMOKE / PENDING_HARDWARE
- Severity: medium
- User need: avoid re-searching the same AXF variable separately in Memory, Watch and Scope.
- Implemented:
  - Memory Symbol -> Add to Watch / Add to Scope / Copy Symbol.
  - Watch Variable -> Add to Scope / Open in Memory / Copy Symbol.
  - Scope HSS Channel -> Open in Memory / Add to Watch / Copy Symbol.
  - RTT channel guard: no address-dependent routing.
  - Open-in-Memory exact Symbol identity check with raw-address fallback.
  - No new J-Link owner/session or target I/O path.
- Automated evidence: compileall PASS; full pytest 131 passed; targeted V0.6.15 5 passed.
- Pending: Windows/PySide6 context-menu smoke and real AXF/J-Link end-to-end routing.


## UX-ENGINEERING-PRESETS-V0611
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE
Severity: low

### Version
V0.6.11

### User evidence / request
- Memory Auto Refresh、Scope Sampling/Buffer、Watch Sample every 使用 SpinBox `+1/-1`，跨常用档位调整不方便。
- 用户希望改为下拉选择常用值，同时保持特殊参数可输入。

### Design / Fix
- 新增统一 `IntPresetComboBox`，提供 editable QComboBox + bounded integer `value()/setValue()/valueChanged` API。
- Memory：100/200/500/1000/2000/5000 ms。
- Watch：10/20/50/100/200/500/1000/2000 ms。
- Scope Sampling：10/20/50/100/200/500/1000/2000/5000 Hz。
- Scope Buffer：1/2/5/10/15/30/60/120 s；不扩张现有 120 s / 1.5M-point product boundary。
- Scope FPS：15/30/60/90/120/144 FPS。
- 所有控件允许键入合法范围自定义值，并继续用整数 settings。

### Verification
- compileall: PASS
- pytest: 114 passed
- Windows/PySide6 preset/custom-value visual smoke: PENDING_USER_QT_SMOKE
- Target I/O semantics: unchanged


## UX-COMPACT-CONNECTION-AUTOMATION-V0610
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE
Severity: low

### Version
V0.6.10

### User evidence / request
- J-Link Connection 区连接成功后长期占用较大垂直空间，希望像 `+/-` 一样可折叠/锁起。
- Test Automation Workflow 的 Qt 行号 + `#` 列、Results 的 Qt 行号 + `Case` 列形成重复编号。

### Design / Fix
- Connection header 常驻 `−/+`、status、Disconnect；详情区单独 QWidget，可折叠。成功连接自动折叠，断开自动展开；已连接时展开详情仍保持配置 disabled。
- Automation Parameter/Workflow/Run/Results 隐藏 verticalHeader；Workflow 从 3 列改为 `Step/Summary` 两列，Results 继续保留业务 `Case`。

### Verification
- compileall: PASS
- pytest: 111 passed
- PySide6/Windows visual smoke: PENDING_USER_QT_SMOKE
- Target I/O semantics: unchanged


## UX-MEMORY-HISTORY-STABLE-V069
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE
Severity: medium

### Version
V0.6.9

### User evidence / request
- History 下拉内右键菜单会随着 QComboBox popup 收起而消失，希望改成常驻按钮单删。
- 选择一个已有 History 成员只是为了再次导航，不希望该记录因此被重新排到列表顶部。

### Design / Fix
- Address / Symbol 右侧新增 `Delete History` 常驻按钮。History 选择后 popup 可以正常关闭，按钮仍可删除刚刚选择的单条记录；当前 Memory 地址/编辑框文本保持不变。
- `_history_activated()` 不再调用通用 `_navigate_query(... remember=True)`，而是直接本地解析 Symbol/raw address 并用 `remember=False` 导航，因此不会调用 MRU 更新，也不会改变历史顺序。
- 新手工输入并成功导航的 Symbol/地址仍继续使用 bounded/deduplicated MRU 记录规则。
- History popup 右键菜单不再接线为主删除路径；Delete 键保留为辅助快捷键。

### Verification
- compileall: PASS
- pytest: 109 passed
- PySide6/Windows button + stable-order smoke: PENDING_USER_QT_SMOKE
- Target I/O semantics: unchanged; history operations are local-only

## FIX-MEMORY-COMBO-COMPLETER-RACE-V068
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE / PENDING_HARDWARE

### Version
V0.6.8

### User evidence
Selecting an intended AXF variable in Memory completion and pressing Enter could end at an unrelated saved history Symbol such as `__lit__00000000` (`0x080001C0`). Long Symbol names could also remain truncated after upgrade because an old manual width setting stayed active. User requested deleting a single history entry.

### Root cause
- V0.6.7 still allowed editable `QComboBox.activated(int)` to call history navigation without proving the History popup was the active interaction. The same Enter used by QCompleter could therefore cause a second MRU navigation.
- Legacy settings had no explicit width-mode version, so saved `symbol_auto_fit=false` survived the new auto-fit default.

### Fix
- Added popup-session-gated `NavigationHistoryComboBox`; only its own opened History popup forwards activation.
- QCompleter.activated is the only partial Symbol candidate commit path; raw line Enter resolves exact Symbol/address only.
- Added per-row History delete via context menu/Delete key.
- Added explicit `symbol_width_mode` and legacy migration to auto-fit.

### Verification
- compileall: PASS
- pytest: 105 passed
- user Windows/PySide6 smoke: PENDING
- real J-Link destination: PENDING_HARDWARE


## FIX-MEMORY-NAV-KEYBOARD-V067
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE / PENDING_HARDWARE
Severity: high

### User evidence / symptom
Memory Address/Symbol 输入时，用方向键选择 Symbol/历史候选后按 Enter 会出现跳转地址错误；完整 Symbol 名需要手动拉宽才能看全；Symbol 跳转后编辑框更希望保留 Symbol，而不是被地址替换。

### Root cause / fix
- Editable QComboBox + QCompleter 的 Enter 路径可能同时触发，旧 `_goto()` 还会回退到通用 `currentCompletion()`，隐藏 popup 时可能拿到陈旧候选。
- History activation 旧路径先写回 editor 再走 `_goto()`，会再次混入 completer 状态。
- 现在 Enter 在可见 completer 中只读取当前明确高亮 QModelIndex 并消费该键；History 直接读取所选 MRU model row，禁止 stale completion fallback。
- Symbol goto 使用 `display_text=symbol.name` 保留完整路径；raw address 保持 canonical hex。
- Memory 可见 Symbol 列与两个 popup 都自动 fit；计算仅使用本地 SymbolIndex/FontMetrics。

### Verification
- compileall: PASS
- full pytest: 101 passed
- targeted static regression: PASS
- Windows/PySide6 arrow/Enter + popup visual smoke: PENDING_USER_QT_SMOKE
- real AXF/J-Link destination address: PENDING_HARDWARE

## FIX-WATCH-SAMEVALUE-FOCUSOUT-V067
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE / PENDING_HARDWARE
Severity: high

### User evidence / symptom
Watch Set Value 用鼠标编辑后点击其它位置，有时如果输入值和原单元格相同不会触发 MCU 写入；按 Enter 才能稳定写。

### Root cause / fix
旧实现把 target write 绑在 QLineEdit 的 `returnPressed/editingFinished` 边缘信号，再手工 `commitData`。在 delegate 焦点切换/同值 model 不变化时存在时序不稳定。V0.6.7 改为：`textEdited` 只标 dirty，Enter/focus-out 都让 Qt 正常走 delegate commit，`setModelData()` 更新 model 后对 dirty edit 发一次 write。即使文本与原值相同也会写；未编辑不写，dirty 清零防重复。

### Verification
- compileall: PASS
- full pytest: 101 passed
- same-value delegate commit static regression: PASS
- real Windows mouse focus-out same-value write: PENDING_USER_QT_SMOKE / PENDING_HARDWARE

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
Status: SUPERSEDED_BY_V0.6.7_AUTO_FIT

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
Status: PARTIAL_FIX / SUPERSEDED_BY_FIX-WATCH-SAMEVALUE-FOCUSOUT-V067

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

## FEAT-MEMORY-SEMANTIC-V0612
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE / PENDING_HARDWARE
Severity: high

### Request
When browsing memory near an AXF/DWARF variable/member, show nearby real scalar members (including array elements like `[0]...[3]`) with their own Address/Type/Value instead of forcing users to infer values from fixed byte offsets.

### Acceptance criteria
- Raw CE-style Memory remains available.
- Add Auto/Raw/Symbols view modes.
- Symbol navigation in Auto opens typed Symbol rows; numeric address navigation remains Raw.
- Nearby scalar leaves are shown in address order and decoded with each member's own datatype size.
- Array members expanded by existing DWARF parser appear individually.
- One bounded block read feeds all visible Symbol rows; no per-member J-Link reads.
- DWARF typed members suppress same-address ELF size-guess duplicates.
- Typed edit/Add-to-Watch remain available from Symbol rows.

### Implementation
- Added `SymbolIndex.scalar_starts_in_range()` and `plan_symbol_read_window()`.
- Added `SymbolMemoryView` and stacked Auto/Raw/Symbols Memory presentation.
- Shared worker block result is fanned out to Raw and Symbol local caches.

### Verification
- compileall: PASS
- pytest: 119 passed
- targeted semantic-memory tests: 5 passed
- PySide6/Windows visual: PENDING_USER_QT_SMOKE
- real AXF/J-Link typed values/edit: PENDING_HARDWARE

## FIX-MEMORY-SYMBOL-REFRESH-SNAP-V0613
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE / PENDING_HARDWARE
Severity: high

### Symptom
In Symbols View, Auto Refresh rebuilt the model and snapped the user's scroll position back to the originally navigated Symbol. The anchor row also appeared permanently selected.

### Root cause
`_rebuild_model()` unconditionally selected the row nearest `_anchor_address` and called `scrollTo(PositionAtCenter)` on every block update.

### Fix
Separate navigation focus from refresh state: one-shot anchor centering on navigation; preserve viewport/user selection on later block updates; no cached-model rebuild.

### Verification
compileall PASS; pytest 123 passed; Windows/PySide6 and real J-Link smoke pending.


## FIX-MEMORY-SYMBOL-NAV-FOCUS-V0614
Status: CODE_COMPLETE / PENDING_USER_QT_SMOKE / PENDING_HARDWARE
Severity: medium

### User evidence / desired behavior
- In Symbols View, entering a variable did not give an obvious jump/selection cue at the resolved member.
- Desired: explicit Symbol navigation should visibly jump to and select the resolved member; clicking empty space should cancel that selection.

### Root cause
V0.6.13 intentionally removed the navigation selection to solve the earlier refresh-forced-selection issue. It also preserved selection state from `currentIndex()`, but Qt can retain a current index after `clearSelection()`, allowing an apparently cleared row to be restored on the next model rebuild.

### Fix
- Explicit navigation centers and selects the anchor row once.
- Refresh preserves only `selectionModel().selectedRows()`, never a stale current index.
- Empty viewport click clears both selection and current index.
- Scroll restoration remains after selection restoration, so Auto Refresh cannot pull the viewport back.

### Verification
- compileall: PASS
- pytest: 126 passed
- V0.6.14 targeted static tests: 3 passed
- Windows/PySide6 visual and real AXF/J-Link navigation: PENDING_USER_QT_SMOKE / PENDING_HARDWARE
