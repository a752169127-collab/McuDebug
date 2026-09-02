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
