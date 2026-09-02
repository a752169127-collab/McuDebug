# KNOWN_PITFALLS

1. HSS Timestamp 当数据 → 固定变量画成 ramp/triangle。
2. Watch 每采样点更新 Qt 表格 → GUI 卡。
3. AXF Search 每按键重建整个表 → 卡。
4. `np.concatenate` 整段历史 → 越跑越慢。
5. 多 PlotWidget / ViewBox Stacked → 高刷成本高。
6. 激进修改 QGraphicsView update mode → follower lane 显示异常。
7. QOpenGLWidget viewport → 实机不如 CPU Raster。
8. whole-buffer extrema fit 当前局部 Lane → 旧异常点撑坏 Y scale。
9. Mouse move 中 `QLabel.adjustSize()` → watchdog 抓到 stall。
10. VS Code debugpy/pydevd 会污染高刷性能结论。
11. Watchdog 长 stack 直接 append GUI Log 也可能干扰实时性。
12. live ring resize 不适合实时路径，应 Start 前预分配。
13. Stall 几百 ms 而所有 measured task 都 <10ms 时，不要继续优化已被排除模块。
14. 临时 watchdog、event-loop probe、逐帧/逐 poll 计时不能长期留在默认 Release 热路径。

15. 为绕过 debugger 阶段 timer starvation 而长期保留高频 persistent polling，会产生大量无效 Qt callback；Release 应优先一帧一回调，除非新的 RUN 证据证明不成立。
16. AI 性能优化容易过度分析/过度开发：已有证据足够时应最小修改、验证、达标即停。
17. MCU Memory Viewer 不能照搬 PC Cheat Engine 的全地址扫描思路；SWD/J-Link 带宽有限，而且 Peripheral Read 可能有副作用。默认只读可见窗口附近。
18. Memory 滚动不能每个 scrollbar tick 都立即排队 ReadMemEx；使用 debounce + 已覆盖窗口检查，避免 J-Link Worker 队列堆积。
19. `WriteMemEx` 成功与“回读验证相等”是两种语义。V0.5 默认前者；不要无需求重新给所有写入附加 ReadMemEx。
20. AXF/ELF 符号可能与 DWARF container/member 重叠；Memory 显示优先精确 DWARF scalar/member，不要按名称随意选第一个符号。

21. Memory Symbol 一行拼多个长名称会破坏列对齐并覆盖 Hex；保持单一对齐 Symbol 列，每行只显示最相关项并 elide；列宽允许用户拖动调整。
22. Memory Explorer 直接键入后再弹第二个确认框会破坏 CE 式编辑体验；direct edit 立即写，双击弹窗的 OK 即确认。
23. Text pane 点击不能退化成 row base；必须按字符/编码单元映射到具体 byte address，否则文本输入会写错位置。
24. 只支持单 cell copy 不够用于内存分析；拖动/Shift range selection 与批量 Hex/Text clipboard 是 Memory Explorer 基础能力。

## Memory Symbol 输入卡顿
不要把 `Address / Symbol` 的 `textChanged` 连接到 AXF 重新解析、Symbol row 重建或 J-Link ReadMemEx。符号输入必须只过滤 AXF load 时已构建的本地 model；用户 Enter 确认地址后才允许触发 Memory visible-window read。


25. 自定义多列 `QCompleter + QTreeView` 在部分 Windows/Qt 样式下可能按未稳定的 row size hint 把 popup 压成 header-only；Memory Symbol 候选 popup 需要稳定最小高度。

26. Memory Symbol 列宽完全固定会让长 AXF/DWARF 路径只能看到省略文本；允许拖动列边界，但 resize 热路径只能重算本地几何/重绘，不能触发符号解析或目标读取。
27. Watch Set Value 只绑定 `returnPressed` 会造成“输入后点击别处，UI 提交但 MCU 未写”的语义 Bug；用 dirty + editingFinished/Enter 统一提交，并防止双发。

## V0.6 Test Automation Pitfalls

### 不要把场景写死成产品专用页面
错误：为“呼吸机 RPM 标定”“电机转速扫描”分别写一套执行代码。
正确：场景只保存为 Parameter Matrix + Workflow 配置；V0.6.1 默认编辑器只暴露 SET / WAIT / STABLE / SAMPLE / INPUT / SAVE 等高频通用步骤；旧高级节点只做兼容。

### 不要在 GUI 中直接访问 J-Link
Automation Page 只能发请求；真实 `ReadMemEx/WriteMemEx` 继续由唯一 `JLinkWorker` 执行。不要为了测试引擎再开第二 Session/Thread。

### 不要把达到稳态等同于读取一次当前值
`WAIT STABLE` 只负责判断系统已稳定；稳定后必须进入独立 SAMPLE 窗口重新统计 Avg/Min/Max/Std，避免把过渡阶段样本混进最终标定值。

### 不要允许任意 eval/exec 作为“灵活性”捷径
Test Plan 是长期可保存、可审查的工程资产。V0.6.0 使用 `${Parameter}` Token、白名单 CALCULATE 和 ASSERT；不要把 Python 表达式执行塞入测试文件。

### 自动化运行不要与连续 Watch/Scope 无限制竞争
V0.6.0 为确定时序，在 Test Run 启动时停止 Watch/Scope 连续采样，再由 request/response polling 驱动测试。以后若要并行 Scope 记录，应明确做调度优先级/共享采样源，而不是直接同时堆请求。

### Timeout 不是一定的 FAIL
稳态/条件等待的 Timeout 必须由用例配置动作：Continue+Mark、Skip Case、Stop Run。标定场景中“不稳定”本身也可能是需要保留的数据。

### 动态表单只删 widget，不删嵌套 layout
错误：Step Type 切换时只处理 `item.widget()`。`QFormLayout` 本身是 layout item，内部 label/editor 不会被释放，连续切换后会出现文字叠影/“字体花掉”。
正确：递归清理 `item.layout()`，再删除其中 widgets/layout。


### 不要把 Runtime Context 整包导出成 Results
错误：Case 结束时遍历整个 `_context`，会把 SAMPLE `count/min/max/std`、WAIT STABLE `.current/.stable_spread`、SET 回执等内部执行状态全部变成结果列，用户看到大量“乱七八糟”的字段。
正确：内部 Context 保留完整数据用于执行/兼容，最终 Results 只投影 Parameter + 用户显式选择的 SAMPLE 统计 + Manual Input/显式输出。V0.6.3 默认 SAMPLE 输出 Avg/Min/Max；Std 仅显式选择时输出，Count 永远是内部采样元数据。


### 不要在 Run Start 隐式清空 Results
Results 是跨多次测试运行累积的用户数据。新 Run 只能清理运行态/Case 状态，不得 `self._results.clear()`。清空必须由 Results 页 `Clear Results` 明确触发并确认。复制给 Excel 应使用 TSV，不要为了复制再创建临时 CSV 文件。
