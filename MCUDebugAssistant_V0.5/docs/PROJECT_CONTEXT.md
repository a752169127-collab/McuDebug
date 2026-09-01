# PROJECT_CONTEXT

## Project
MCU Debug Assistant

## Goal
长期演进的 MCU 调试平台：**J-Scope 风格 Scope + Keil Watch + AXF/ELF/DWARF Symbol Browser + Symbol-aware Memory Explorer**，支持 J-Link HSS/RTT。

## 三条主链

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

## 当前成熟度
- J-Link 单地址 Memory R/W：历史实机验证
- Watch：较成熟
- ARMCC5 DWARF3：当前场景成熟
- Scope Rendering V2：V0.4.23 基线保持
- V0.5.4 Memory Explorer：继承 V0.5.3 Address / Symbol 本地过滤与跳转，并修复用户实机发现的多列候选 popup 高度过短/只有表头问题；真实 J-Link 地址跳转继续待验证

## V0.5.4 Memory 原则
- GUI 不直接访问 J-Link。
- 只读可见窗口附近，不全地址扫描。
- Peripheral 区不做后台预读/扫描。
- Auto Refresh 默认关闭。
- 新会话首屏固定 `0x20000000`；Symbol 列固定几何并 elide。
- 若上次保存的 AXF/ELF 路径仍存在，启动后自动解析并同步 Watch / Scope / Memory；失效路径只跳过，不自动扫描其它文件。
- Address / Symbol 输入框既可输入 `0x20000000`，也可输入 AXF/DWARF 完整符号路径；数组下标和结构体成员使用解析器已生成的精确符号地址。
- 符号过滤模型只在 AXF/ELF 加载时构建一次；打字只做本地 MatchContains 过滤，不能触发 J-Link ReadMemEx。
- Byte Hex/Text 支持直接输入；连续选择支持批量复制；双击弹窗 OK 即确认。
- 普通写入默认以 WriteMemEx 完整 byte count 为成功条件，不追加 ReadMemEx Verify。
- 用户需要确认时可 F5/Read 主动读取，这是独立读操作，而不是每次写的强制成本。
