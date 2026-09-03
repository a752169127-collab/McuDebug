# AGENTS.md — MCU Debug Assistant 长期开发 Agent

## 使命

你是 MCU Debug Assistant 的长期工程 Agent。你的职责不只是写代码，而是维护一个可持续、可追踪、可交接的 AI 软件研发闭环。

每次迭代必须完成：

1. 读取当前项目状态。
2. 把用户反馈转成明确 Issue。
3. 复现或定义复现条件。
4. 优先收集证据，不凭感觉大改架构。
5. 建立根因假设并逐项证伪。
6. 做最小、安全、可回滚的修改。
7. 自动回归测试。
8. 生成新版本。
9. 更新 Project State / Issue / Test / ADR / Handoff / Changelog。
10. 输出“解决了什么、证据是什么、还剩什么、下一步怎么验证”。

## 工程克制原则（长期最高优先级）

- 默认最小修改，不扩大用户当前任务。
- 已验证稳定区域默认不动；没有证据不要顺手重构。
- 分析只做到足够支持安全决策；证据充分后停止继续发散。
- 性能问题先确认 Release/RUN 环境，再看现有证据；不要默认新增 instrumentation。
- 只有现有证据不足时才允许加入临时诊断，且必须可关闭、低侵入，并在 Release 前移除。
- 不因“最佳实践”替换已经实机稳定的实现。
- Acceptance Criteria + 自动回归满足后停止开发；硬件项标 `PENDING_HARDWARE`，不要继续无目标优化。
- 普通 Bug/性能清理默认限制在相关模块内；若需要跨层重构，先说明为什么局部修复不够。

---

## 一、开发前必须读取

按顺序读取：

- `docs/state/PROJECT_STATE.yaml`
- `docs/state/LATEST_HANDOFF.md`
- `docs/state/ISSUE_LEDGER.md`
- `docs/state/TEST_STATUS.md`
- `docs/state/VERSION_HISTORY.md`
- `docs/architecture/ADR.md`
- `docs/architecture/PROJECT_CONTEXT.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/KNOWN_PITFALLS.md`
- `CHANGELOG.md`
- `docs/releases/README.md`（仅用于定位需要的历史 Release Report）
- 当前任务相关源码与测试
- 用户最新日志、截图、复现步骤

历史 `docs/releases/RELEASE_REPORT_*.md` 默认**不要全读**；只有当前状态/交接无法解释设计来源或回归时，才按 `docs/releases/README.md` 精确追溯。

不要因为聊天历史很长就猜测旧状态；以当前仓库和这些状态文件为准。

---

## 文档与 AI 知识库布局（V0.6.16）

- 根目录只保留高频入口：`README.md / START_HERE_FOR_NEW_AI.md / AGENTS.md / SKILL.md / CHANGELOG.md`。
- `docs/state/`：当前状态、Issue、测试状态、版本历史、最新交接；这是二次开发最优先读取的动态记忆。
- `docs/architecture/`：架构、ADR、项目上下文、已知陷阱、渲染设计；用于理解长期不变量和设计原因。
- `docs/development/`：Workflow、自动更新 Checklist、给新 AI 的辅助提示。
- `docs/releases/`：历史 Release Report 与索引；默认只读最新/相关版本，不做无差别全量读取。
- 文档移动只改变知识库路径，不得改变 J-Link/Scope/Memory/Automation 运行逻辑。
- 新版本结束时必须更新 `docs/releases/README.md` 的 Current 条目，并在 `docs/releases/` 新建当前版本 Release Report。

## 二、不可破坏的项目架构原则

### J-Link 单 Owner
- J-Link DLL / Session 只能由一个 Worker 持有。
- GUI 不直接调用 J-Link。
- Watch / Scope 不各自开线程抢 J-Link Session。

### Sampling 与 UI 分离
必须区分：
- Acquisition Rate
- Curve Geometry Update Rate
- Table Refresh Rate
- Presentation / View FPS

1000 Hz 采样不等于 Qt 控件 1000 Hz 刷新。

### Raw 与 Display 分离
Raw MCU 数据用于：
- Statistics
- CSV
- Cursor
- Probe
- 数据复现

Display 才使用：
- Downsample
- Gain
- Offset
- Lane Mapping
- Render Cache

### Scope 语义
- `Show`：只控制显示，不停止采样，不清历史。
- `Pause`：停止采样，但保留 Buffer、Range、Cursor、Gain/Offset、统计。
- `Start`：新的实验，会清上一轮 Scope Buffer 与统计。
- `Follow`：只控制 X 轴跟随，不每帧自动改变 Y。
- `View All`：明确查看整个缓存。

### Watch Set Value 提交语义
- Set Value 用户实际编辑后，按 Enter 或编辑器因点击其它位置失焦都必须提交并写入。
- focus-out 不能对未修改的单元格产生写操作；Enter 与 editingFinished 必须去重，禁止一次编辑重复写两次。

### AXF Reload / Startup Auto-load
- 按完整 Symbol Path 重新绑定。
- 更新 Address / Type。
- 缺失或歧义符号必须删除，禁止继续访问旧地址。
- 启动时如果 QSettings 中保存的 AXF/ELF 路径仍然存在，必须自动解析并把符号同步给 Watch / Scope / Memory；不能只恢复路径文本而让 SymbolIndex 为空。
- 保存路径不存在时只记录并跳过，不扫描目录猜测其它 AXF，也不阻塞启动。

### Memory Explorer
- 仍由唯一 J-Link Worker 执行 ReadMemEx / WriteMemEx；GUI 禁止直接访问 DLL。
- 默认只读可见地址窗口附近，不做全 32-bit 地址扫描。
- Peripheral Space 禁止自动大范围预读；用户看哪里才读哪里。
- 滚动必须 debounce/合并，禁止每个 scrollbar tick 无界排队 J-Link 读取。
- 新会话默认从 MCU SRAM 基址 `0x20000000` 打开；不要恢复上次随机浏览地址覆盖首次有用视图。
- Symbol 列必须保持单行对齐和 elide；列右边界允许用户拖动调整宽度，禁止把多个长符号用自由文本拼接后覆盖 Hex 区。调整列宽仅属于 Presentation，不得触发 AXF 重解析或 J-Link 读取。
- Address / Symbol 输入框的符号搜索必须基于 AXF 加载时一次构建的本地 Model/Index；每次键入不得重建 Symbol UI、不得触发 J-Link 读取。完整成员路径和数组路径（如 `obj.member`、`buffer[1]`）必须直接解析到已加载符号地址。
- Memory Address / Symbol 查询历史只记录成功导航项，使用独立 MRU 状态持久化；下拉历史不得替代/重建 AXF Completion Model。清空历史仅清导航记录，不清当前地址、不访问目标。
- Memory 历史下拉可显示当前 SymbolIndex 解析出的 Type/Address 元数据；AXF reload 后刷新。精确标量 Symbol/成员导航时，若 `type_name` 属于支持类型，必须在 goto 前把 Memory Display Type 自动切换为该类型；raw 地址、struct/array/unknown 禁止猜类型。此过程不得增加目标 I/O。
- 支持 CE 风格直接编辑：Byte 区两位 Hex 直接写、Text 区键入/粘贴直接写、拖动/Shift 选择连续内存块并复制。
- 双击编辑弹窗的 OK 本身就是确认；Memory Explorer 直接编辑路径禁止再叠加第二个确认框。手工 Typed R/W 面板可保留独立确认。
- V0.5 默认 Write 以 WriteMemEx 完整 byte count 为成功条件；除非有新明确需求，不要重新给所有写操作强制 ReadBack Verify。

### V0.6.15 Cross-Module Symbol Actions 基线
- Memory Symbol 的跨模块动作统一为 `Add to Watch / Add to Scope / Copy Symbol`；Watch 为 `Add to Scope / Open in Memory / Copy Symbol`；Scope 为 `Open in Memory / Add to Watch / Copy Symbol`。
- 跨模块动作只传递 `name/address/type`，禁止因此新增 J-Link Session、Worker 或直接 DLL I/O；仍由 MainWindow 连接现有模块对象。
- `Open in Memory` 必须用 Symbol 全名 + 地址双重确认 AXF/DWARF 身份；精确匹配才走 Semantic Symbol 导航。手工命名/不匹配变量退化为 Raw address，禁止按同名或邻近地址猜 Symbol。
- Scope RTT channel 是 target-defined stream，不保证有 AXF address；`Open in Memory` 与 `Add to Watch` 必须禁用/拒绝，Copy channel name 可保留。
- Scope 正在采样时禁止通过跨模块菜单改变 HSS channel definition；与原 Add/Remove 控件的锁定语义一致。
- Copy Symbol 属于纯本地剪贴板动作，不访问 J-Link、不重建 SymbolIndex。

### V0.6.14 Semantic Navigation / Selection 基线
- `_anchor_address` 只用于规划 Semantic bounded read neighborhood，不是长期滚动位置。
- 显式 Symbol/member 导航允许一次性把目标滚到中间并选中目标行，给用户明确定位反馈；Auto/Manual Refresh 禁止再次 `scrollTo(anchor)`。
- Refresh/model rebuild 只允许按 `selectionModel().selectedRows()` 保留真实 selection，禁止用 stale `currentIndex()` 推断选择。
- Symbols viewport 空白处单击必须清除 selection + current index；之后 refresh 不得重新选回。
- Refresh/model rebuild 必须保持用户 vertical/horizontal viewport；cached non-force refresh 不重建相同 Symbol model。

### V0.6.12 Semantic Memory View 基线
- Memory 同时保留 `Raw` 与 `Symbols` 两种 renderer；`Auto` 只根据导航语义选择 renderer，不允许在滚动过程中启发式反复切换。
- Symbol view 只显示可安全按已知标量类型解释的 AXF/DWARF/ELF leaf；struct/array container、padding、unknown 不得伪造成标量。
- 同一地址存在 DWARF typed leaf 与 ELF size-guess fallback 时，Semantic view 优先 DWARF，避免重复/错误语义。
- 每个成员按自己的 normalized type/size 解码；禁止把整个 Semantic view 强制套用一个全局 Display Type。
- Semantic view 必须复用一个 bounded raw block read（当前 max 2048 B）并在本地切片；严禁“每个 Symbol 一次 ReadMemEx”。
- Raw Memory 仍是 Buffer、padding、未知内存、协议数据和底层布局的权威视图，不能被 Semantic view 删除或弱化。
- Symbol view 的列宽/排序/值格式属于 Presentation；不得导致 AXF 重解析或额外 Probe I/O。

### Test Automation Studio
- Test Automation 是 Watch/Scope/Memory 之上的编排层，不得拥有独立 J-Link Session，也不得从 GUI 直接调用 DLL。
- V0.6.0 自动化读写必须经过唯一 `JLinkWorker`；测试 Run 开始时停止连续 Watch/Scope sampling，使用 request/response polling 保证执行语义确定。
- Parameter Matrix 与 Workflow 分离：Matrix 决定“测试哪些 Case”，Workflow 决定“每个 Case 怎么执行”。禁止为某个呼吸机/电机场景把业务流程硬编码进引擎。
- 无代码 Test Plan 禁止 `eval()`/`exec()` 和任意 Python/YAML 脚本执行。参数引用使用 `${Name}` Token。V0.6.1 新建步骤默认只暴露 SET / WAIT / WAIT STABLE / SAMPLE / MANUAL INPUT / SAVE RESULT；V0.6.0 的 WAIT UNTIL / CALCULATE / ASSERT 仅为旧计划兼容保留，不再作为默认编辑器能力。
- AXF/DWARF Symbol 在文件 load/reload 时一次同步给 Automation；编辑步骤时只做本地 Symbol completion，不允许每个字符访问目标。
- `WAIT STABLE` 必须明确 Window / Threshold / Hold / Timeout / Timeout Action；达到稳态后再进入 SAMPLE，不能把一次瞬时值当稳态测量。
- 动态 Step Dialog 切换类型时必须递归销毁旧的嵌套 Layout/Widget；只删除顶层 Widget 会残留 QFormLayout 标签并造成文字重叠。
- SAMPLE 内部统计至少保留 Count / Avg / Min / Max / Std，供稳态分析与旧计划兼容；用户结果与内部 Runtime Context 必须分离。V0.6.3 新建 SAMPLE 默认输出 Avg/Min/Max，Std 由用户显式勾选，Count 永远作为内部采样元数据而非结果列。外部设备先通过 MANUAL INPUT 注入，未来仪器 Adapter 不能污染 Test Engine 的业务流程。
- 自动化测试硬件结论必须记录真实 Parameter Case、Symbol、Polling interval、Timeout、结果；synthetic/pure-core 测试不能声称真实 J-Link 自动化通过。
- Results 属于用户累积测试记录：启动新 Run 不得隐式清空；Run 完成只清空 Runtime 表。结果清空必须由 Results 页显式操作；Excel 快速交换使用带表头 TSV 剪贴板复制。

### 性能
禁止回退：
- 每批 `np.concatenate(old_history, new_data)`
- 采样率驱动 QTableWidget 高频刷新
- 每个搜索字符重建整个 Symbol UI
- 多个独立 PlotWidget/Scene 的旧 Stacked 架构
- 在鼠标移动热路径调用 `adjustSize()`
- 为追 FPS 随意修改 Qt update mode 而不做正确性 A/B

### V0.6.11 Engineering Preset Controls 基线
- Memory Auto Refresh、Watch Sample every、Scope Sampling/Buffer/FPS 使用统一可编辑工程预设下拉，不再使用单步 `+1/-1` SpinBox 作为主交互。
- 预设只是快捷值，不是能力上限；控件必须允许用户直接键入合法范围内的自定义整数，并继续通过整数 `value()/setValue()` 与现有 settings/worker 语义兼容。
- 预设选择/自定义输入只改变本地参数值，不得因为 UI 控件替换改变 J-Link I/O、Scope acquisition、Ring Buffer、Presentation Pacer 或 Watch sampling 语义。
- Scope Buffer 保持当前 1~120 s 产品范围；不要仅为了增加下拉选项扩张 Ring `max_points=1_500_000` 或制造“配置 300 s 但高采样率实际保留不足”的误导。
- 常用预设：Memory `100/200/500/1000/2000/5000 ms`；Watch `10/20/50/100/200/500/1000/2000 ms`；Scope Sampling `10/20/50/100/200/500/1000/2000/5000 Hz`；Buffer `1/2/5/10/15/30/60/120 s`；FPS `15/30/60/90/120/144`。

### V0.6.10 Compact Connection / Automation Table UI 基线
- J-Link Connection 配置区允许 `− / +` 折叠；成功连接后自动折叠，断开后自动展开。折叠时必须保留连接状态摘要和 `Disconnect`，不能让用户为了断开而先展开面板。
- 已连接时即使用户手动展开，DLL/Device/Interface/Speed 等配置仍保持 disabled；折叠只是 Presentation，不能改变 Session 配置或产生额外 J-Link I/O。
- Test Automation 业务表格隐藏 Qt `verticalHeader`，避免与业务 Case/顺序信息重复；Workflow 不再保留显式 `#` 列，执行顺序由行顺序表达。

### V0.6.9 Memory History Stable-order / Delete-button 基线
- Address / Symbol History 的单条删除主入口是常驻 `Delete History` 按钮；不能依赖 QComboBox popup 内嵌右键菜单作为唯一删除方式。
- 用户从 History 选择既有 Symbol/地址时只执行导航，不调用 MRU update，不改变历史顺序。只有用户新输入并成功导航的查询才允许按 MRU 规则插入/去重。
- `Delete History` 删除当前选中/当前查询对应的单条历史，必须保留当前 Memory 地址与编辑框文本，且不得产生 J-Link Read/Write。`Clear History` 才是全部清空。
- History 删除/选择仍是本地状态操作；不得重建 AXF completion model，不得访问目标。

### V0.6.8 Memory Symbol / History Reliability 基线
- `Address / Symbol` 的 AXF 候选确认只有 `QCompleter.activated` 可以提交候选；禁止再次从 line edit Enter 读取 completer currentIndex/currentCompletion 猜候选。
- editable `QComboBox` 的 `activated(int)` 只有在用户确实打开过 History popup 的 session 内才能转成历史导航；Symbol completion Enter 绝不能触发历史 MRU 二次导航。
- Symbol 导航后编辑框保留完整 Symbol；原始地址导航才显示 canonical `0xXXXXXXXX`。
- History 必须支持单条删除以及 Clear All；V0.6.9 起单删主入口为常驻 `Delete History` 按钮，Delete 键可辅助。删除历史只更新本地记录/QSettings，不改变当前地址、不访问 J-Link。
- Symbol 主列默认 auto-fit；V0.6.8 新增显式 `symbol_width_mode`。旧配置没有该字段时必须迁移到 auto，避免历史窄列状态继续遮住完整变量名。新版本用户主动拖列才允许持久化 manual mode。

### V0.6.7 Memory Navigation / Watch Commit 基线
- Address/Symbol 输入的键盘候选确认必须使用当前 popup 明确高亮行；禁止在 popup 隐藏/无明确选择时使用陈旧 `currentCompletion()` 猜 Symbol。History activation 必须直接按所选 MRU model row 导航，避免 editable combo + completer 双重 Enter 竞态。
- Symbol 导航后编辑框保留完整 Symbol path；只有用户明确以数值地址导航时才显示 canonical `0xXXXXXXXX`。
- Memory Symbol 列默认自动适应当前可见 Symbol 全名；popup 在本地 Model rebuild 时自动 fit。自动宽度计算只能访问本地 SymbolIndex/FontMetrics，禁止因此产生 J-Link I/O 或每个键入字符全模型重建。
- Watch Set Value 的硬件写触发以 delegate `setModelData()` 正式 commit 为准：Enter / focus-out 统一；用户重新输入与原单元格相同的值仍视为显式写请求；未编辑不写，dirty guard 去重。

---

## 三、标准闭环流程

### Phase A — Issue Intake

把反馈转成结构化 Issue：

- Issue ID
- 版本
- 症状
- 期望行为
- 实际行为
- 复现步骤
- 环境
- 严重度
- 用户证据
- 涉及模块

例如“感觉卡”必须进一步转成：
- Paint FPS
- Presentation Tick FPS
- 1% Low
- Jitter
- event-loop gap
- paint max
- worker/read/decode
- append
- points
- Follow
- Overlay/Stacked
- FG/BG
- DBG/RUN

### Phase B — Diagnosis

建立假设矩阵：

| Hypothesis | 支持证据 | 反证 | 如何证伪 |
|---|---|---|---|

优先复用已有日志/测试/代码证据；只有证据不足时才做最小、临时 instrumentation。

如果 Stall=700ms，而：
- paintMax=10ms
- render=1ms
- append=0.2ms
- worker=8ms

则这些模块已经不足以解释 700ms。不要继续把主要精力放在那里。

### Phase C — Design

修改前明确：
- 当前最强根因/假设
- 修改哪些模块
- 哪些行为必须保持
- 预期结果
- 回滚点

架构变化要追加 ADR。

### Phase D — Implement

- 尽量局部修改。
- 保持接口兼容。
- 未定位根因时先缩小范围；必要时才加入最小临时诊断，Release 前必须移除或默认零开销关闭。
- 一轮尽量不要同时更换多个无关性能机制，否则无法 A/B。

### Phase E — Verify

最低要求：
- `compileall`
- 全量 `pytest`
- 针对此 Issue 的 Regression Test（可行时）
- 配置兼容检查
- 源码静态检查

真实硬件无法自动验证时必须标：
`PENDING_HARDWARE`

禁止把 synthetic test 写成“实机通过”。

### Phase F — Release

版本通过自动测试后：
- 更新版本号
- 打包
- 更新 CHANGELOG
- 更新 PROJECT_STATE
- 更新 ISSUE_LEDGER
- 更新 VERSION_HISTORY
- 更新 TEST_STATUS
- 更新 LATEST_HANDOFF
- 架构改变时更新 ADR

### Phase G — Conclusion

每个版本回答必须说明：

1. 解决哪个问题
2. 根因/证据
3. 技术改动
4. 哪些东西没有动
5. 自动测试结果
6. 实机验证步骤
7. 仍存在的问题
8. 如果失败，下一步需要用户提供什么证据

---

## 四、结论可信度

使用统一标签：

- `VERIFIED_AUTOMATED`
- `VERIFIED_SYNTHETIC`
- `VERIFIED_USER_HARDWARE`
- `PENDING_HARDWARE`
- `HYPOTHESIS`
- `DISPROVED`

不要把 HYPOTHESIS 自动升级为事实。

---

## 五、性能测试规则

记录环境：

- RUN / DBG
- Python
- PySide6 / Qt
- pyqtgraph
- J-Link DLL
- Device
- SWD/JTAG Speed
- HSS/RTT
- Requested Hz
- Actual Hz
- Channel count/types
- Buffer
- Overlay/Stacked
- Follow
- FPS target
- FG/BG
- Test duration

VS Code F5 / debugpy / pydevd 只能用于诊断，不能作为 release performance 结论。

---

## 六、Definition of Done

Issue 只有同时满足以下条件才算 DONE：

- 代码修改完成
- 自动测试 PASS
- Regression 已补或有合理说明
- 用户硬件验证 PASS，或明确 PENDING_HARDWARE
- Issue Ledger 更新
- Project State 更新
- Version History 更新
- Test Status 更新
- Changelog 更新
- Handoff 更新
- 架构变化写 ADR

“代码写完”不等于完成。

### V0.6.5 PySide6 Combo Signal 兼容基线
- Memory Address/Symbol 历史 `QComboBox` 在 PySide6/Qt6 下使用 `activated(int)`；禁止使用当前绑定不存在的 `activated[str] / activated(QString)`。
- 历史点击通过 index → `itemText(index)` 取查询文本，再复用 `_goto()`；不得为此增加 J-Link I/O、重建 AXF Symbol Model 或改变 MRU 语义。
- 构造阶段异常导致的 `QThread: Destroyed while thread is still running` 优先视为上游初始化异常的级联结果；先修第一个 traceback，不把级联提示误判成独立线程根因。

### V0.6.6 Symbol Typed Memory Navigation 基线
- Address/Symbol 编辑框尺寸保持 320~520 px；历史 popup 使用 History/Type/Address 三列，小型 MRU 与 AXF QCompleter Model 继续完全分离。
- History Type/Address 只从当前 SymbolIndex 本地解析，打开/刷新历史不得访问 J-Link。
- exact scalar Symbol 跳转按 AXF/DWARF 类型自动切换 Memory Display Type；仅允许 core.datatype 支持的类型，不对 raw address/container 猜测。
