# RELEASE REPORT — V0.6.4 Memory Navigation History

## Goal
让 Memory Explorer 的 `Address / Symbol` 输入框保留成功查询过的 Symbol/地址，并通过与原编辑框同尺寸的可编辑下拉框快速复用；同时允许用户显式清空历史。

## Implementation
- `QLineEdit` 升级为 editable `QComboBox`，编辑区域仍保持 320~520 px 原尺寸范围。
- 原 AXF/DWARF `QCompleter(MatchContains)` 继续挂在 Combo 的 line edit 上；键入搜索路径不重建 Symbol Model、不访问 J-Link。
- 仅成功导航才进入历史：数值地址规范化为 `0xXXXXXXXX`，Symbol 保存完整已解析名称；重复项移动到最前。
- 最多保存 50 条 MRU 历史，并通过 `memory_explorer_state` / QSettings 跨启动持久化。
- 下拉选择历史项后复用现有 `_goto()` 路径自动跳转。
- 增加 `Clear History`，只清历史，不修改当前地址/符号文本，不触发目标 I/O。
- 新会话仍按 V0.5.1 规则首次显示 `0x20000000`；历史恢复和首屏地址相互独立。

## Verification
- compileall: PASS
- pytest: 91 passed
- Qt visual/interaction smoke: PENDING_ENVIRONMENT
- Real AXF/J-Link history navigation: PENDING_HARDWARE
