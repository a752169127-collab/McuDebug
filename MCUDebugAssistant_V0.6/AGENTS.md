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

- `state/PROJECT_STATE.yaml`
- `state/ISSUE_LEDGER.md`
- `state/VERSION_HISTORY.md`
- `state/TEST_STATUS.md`
- `state/LATEST_HANDOFF.md`
- `docs/PROJECT_CONTEXT.md`
- `docs/ARCHITECTURE.md`
- `docs/KNOWN_PITFALLS.md`
- 当前源码与测试
- 最新 CHANGELOG
- 用户最新日志、截图、复现步骤

不要因为聊天历史很长就猜测旧状态；以当前仓库和这些状态文件为准。

---

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
- 支持 CE 风格直接编辑：Byte 区两位 Hex 直接写、Text 区键入/粘贴直接写、拖动/Shift 选择连续内存块并复制。
- 双击编辑弹窗的 OK 本身就是确认；Memory Explorer 直接编辑路径禁止再叠加第二个确认框。手工 Typed R/W 面板可保留独立确认。
- V0.5 默认 Write 以 WriteMemEx 完整 byte count 为成功条件；除非有新明确需求，不要重新给所有写操作强制 ReadBack Verify。

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
