# PROJECT_CONTEXT

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
- V0.6.5 Test Automation Studio：Parameter Matrix + 精简通用 Workflow + 稳态/统计/人工测量；Runtime Context 与 Results 分离，SAMPLE 默认输出 Avg/Min/Max，Std 可选，Count 保持内部；Results 跨多次 Run 累积，一键复制 TSV 到 Excel，显式 Clear 才清空。

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

- V0.6.6: Memory navigation history shows History/Type/Address metadata; exact scalar AXF/DWARF Symbol/member jumps automatically apply the matching Memory display type before navigation, while raw addresses/non-scalars preserve the current view.
