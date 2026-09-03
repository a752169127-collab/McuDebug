## V0.6.15 Cross-module workflow direction

V0.6.15 starts treating an AXF/DWARF Symbol as a shared object across Memory, Watch and Scope rather than making the user re-search it in each page. Context menus route only local `name/address/type` metadata through MainWindow. No new target access path is created. Exact Symbol identity is confirmed by both full name and address before Semantic Memory navigation; otherwise navigation falls back to the raw address. RTT Scope channels remain stream-defined and are not assumed to be memory-addressable.

## V0.6.14 Memory navigation direction
- Symbols View 的显式 Symbol/member 导航需要“可见定位反馈”：目标 typed row 一次性居中并高亮。
- 刷新仍是数据更新，不是导航命令；不得再次根据 anchor 改 viewport。
- selection 的持久化只看真正 `selectedRows()`；点击空白区域清掉 selection/current index 后，刷新必须保持未选中状态。

# PROJECT_CONTEXT

## V0.6.13 Memory refresh direction
- Semantic `Symbols` view refresh is now non-navigational: the original Symbol anchor is centered once only.
- Auto Refresh preserves the user viewport and no longer leaves an artificial navigation selection.
- This is a Presentation-state fix only; bounded shared block reads and Single J-Link Owner are unchanged.

## V0.6.12 Memory direction
- Memory 从“Raw grid + Symbol annotation”扩展为“双 renderer”：Raw 保留 CE 风格，Symbols 把 AXF/DWARF leaf 当作 typed runtime objects。
- 典型效果：导航 `BlowerParamsObj.m_BiasAD[0]` 后，可直接看到附近 `[0]/[1]/[2]/[3]` 以及其它相邻成员，各自用真实类型和大小解码。
- 这不是扩大扫描范围：Semantic view 仍最多读取约 2 KiB neighborhood，并且所有行共享同一个 raw block。
- 产品差异化进一步从“看地址”转向“地址 + C Symbol + 类型 + Runtime Value”的统一视图。

## Project
MCU Debug Assistant

## Goal
长期演进的 MCU Runtime Debug / Validation 平台：**J-Scope 风格 Scope + Keil Watch + AXF/ELF/DWARF Symbol Browser + Symbol-aware Memory Explorer + No-code Test Automation**，当前 Probe 为 J-Link HSS/RTT。

## 四条主链

```text
MCU → J-Link → JLinkWorker → Acquisition → Raw Ring Buffer
                                      ├─ Statistics / Cursor / CSV
                                      └─ Render Cache → Scope Presentation
```

```text
AXF/ELF/DWARF → Symbol Model → Watch / Scope / Memory Symbol Overlay
```

```text
Memory Scroll/Goto → Visible Window Planner → JLinkWorker → ReadMemEx → Memory View
Memory Edit        → Encode/Raw Bytes        → JLinkWorker → WriteMemEx
```

```text
Parameter Matrix → Generated Cases → No-code Workflow → JLinkWorker Runtime I/O
                                      ├─ Stable / Sample / Statistics
                                      ├─ Manual External Measurement
                                      └─ Calculate / Assert / Results / Clipboard
```

## 当前成熟度
- J-Link 单地址 Memory R/W：历史实机验证
- Watch：较成熟
- ARMCC5 DWARF3：当前场景成熟
- Scope Rendering V2：V0.4.23 基线保持
- V0.5.5 Memory Explorer：Symbol-aware CE 风格内存浏览/编辑基线保持
- V0.6.12 Semantic Memory：Auto/Raw/Symbols 双 renderer，AXF/DWARF leaf 按成员真实类型从共享 block 解码。
- V0.6.11 Test Automation Studio：Parameter Matrix + 精简通用 Workflow + 稳态/统计/人工测量；Runtime Context 与 Results 分离，SAMPLE 默认输出 Avg/Min/Max，Std 可选，Count 保持内部；Results 跨多次 Run 累积，一键复制 TSV 到 Excel，显式 Clear 才清空。

## V0.5.5 Memory / Watch 原则
- GUI 不直接访问 J-Link。
- 只读可见窗口附近，不全地址扫描。
- Peripheral 区不做后台预读/扫描。
- Auto Refresh 默认关闭。
- 新会话首屏固定 `0x20000000`；Symbol 列单行 elide，宽度可拖动调整并持久化。
- 若上次保存的 AXF/ELF 路径仍存在，启动后自动解析并同步 Watch / Scope / Memory；失效路径只跳过，不自动扫描其它文件。
- Address / Symbol 输入框既可输入 `0x20000000`，也可输入 AXF/DWARF 完整符号路径；数组下标和结构体成员使用解析器已生成的精确符号地址。
- 符号过滤模型只在 AXF/ELF 加载时构建一次；打字只做本地 MatchContains 过滤，不能触发 J-Link ReadMemEx。
- Byte Hex/Text 支持直接输入；连续选择支持批量复制；双击弹窗 OK 即确认。
- 普通写入默认以 WriteMemEx 完整 byte count 为成功条件，不追加 ReadMemEx Verify。
- 用户需要确认时可 F5/Read 主动读取，这是独立读操作，而不是每次写的强制成本。

- Watch Set Value 实际编辑后，Enter 或 focus-out 都会提交写入；未修改 focus-out 不写，避免重复/误写。

## V0.6.x Test Automation 原则
- 场景用于验证通用抽象，不把“呼吸机转速标定”写死成业务页面。
- Parameter Matrix 与 Workflow 分离；同一 Workflow 可被 RPM、压力、电机速度、BMS 电压等不同参数组合复用。
- Test Step 的变量来自已加载 AXF/DWARF Symbol；输入/选择不产生目标访问。
- 自动化执行时由唯一 JLinkWorker 完成 snapshot/write；GUI 只做状态机/编排。
- 当前 `WAIT STABLE` 采用多 Signal Max-Min 波动窗口；达到稳态后 SAMPLE 使用新的测量窗口，内部计算 Avg/Min/Max/Std/Count。最终 Results 默认只暴露 Avg，额外统计由用户显式选择。
- 外部仪器 V0.6.0 通过 Manual Input；PF300/VT650 等自动读取应以 Measurement Adapter 扩展，不修改 Test Engine。
- 不执行任意用户脚本；`${Name}` Token、结构化 Calculate、Assert 是当前表达能力边界。


- V0.6.5: Memory Address/Symbol keeps the V0.6.4 persistent MRU history and fixes PySide6/Qt6 combo activation by using `activated(int)` + `itemText(index)`; Symbol completion remains local/non-blocking.

- V0.6.7: fixes keyboard Symbol/history Enter address races, preserves Symbol text after Symbol navigation, auto-fits Memory/popup Symbol widths, and moves Watch same-value focus-out writes to the delegate model-commit path.
- V0.6.9: makes single-history deletion a persistent button action and keeps history order stable when navigating previously saved Symbol/address entries.
- V0.6.8: isolates Symbol completion from editable-history combo activation, adds per-item MRU deletion, and migrates old narrow Symbol-width settings to automatic full-name fitting.
- V0.6.6: Memory navigation history shows History/Type/Address metadata; exact scalar AXF/DWARF Symbol/member jumps automatically apply the matching Memory display type before navigation, while raw addresses/non-scalars preserve the current view.


## V0.6.10 UI direction
- Connection setup is a transient task, so after a successful J-Link connect the large configuration panel collapses automatically and gives vertical space back to Watch/Scope/Memory/Test Automation.
- Connection summary and Disconnect stay visible at all times; `+` reopens details for inspection.
- Automation tables avoid duplicate visual numbering: Workflow row order is sufficient, while Results keeps the explicit business `Case` field.


## V0.6.11 UI direction
- Engineering timing/rate parameters should optimize for common choices rather than one-unit stepping. Use editable preset drop-downs for Memory refresh, Watch polling, Scope sampling/buffer/FPS.
- Presets improve speed but must not make the tool rigid: advanced users can type a custom in-range integer.
- Preserve current data-path semantics and integer settings compatibility; this iteration is UX-only, not a sampling architecture change.
