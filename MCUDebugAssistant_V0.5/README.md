# MCU Debug Assistant V0.5.5 — Memory Symbol Resize + Watch Commit Fix

V0.5.5 基于 V0.5.4，修复 Memory Symbol 列宽无法调整，以及 Watch Set Value 输入后点击其它位置不触发写入的问题；保持现有 AXF 搜索、Memory visible-window、单 J-Link Owner 和 Scope 高性能架构不变。

## V0.5.5 重点
- Memory Symbol 列右边界可直接鼠标拖动调整宽度，长变量名需要时可以展开查看；双击分隔线恢复默认宽度。
- Symbol 列宽会跟随 Memory Explorer 设置持久化，下次启动继续使用。
- Watch `Set Value`：输入后按 Enter 会写；输入后直接点击其它单元格/控件也会提交并写入 MCU。
- 只有用户实际编辑过 Set Value 才在 focus-out 触发写入，避免单纯浏览/切换焦点产生重复写操作。

## V0.5.4 重点

- 直接输入 `0x20000000`：按原逻辑跳转。
- 直接输入 `BlowerParamsObj.m_PosSpeed`：从已加载 AXF/DWARF 精确换算地址并跳转。
- 直接输入 `buffer[1]`、`ctrl.channels[1].gain`：使用解析器已经展开的数组/成员符号地址。
- 输入部分变量名时，下方出现 Symbol / Type / Address 候选列表。
- 候选使用一次构建的 Qt Model + `QCompleter(MatchContains)`；打字不重建列表、不访问 J-Link。
- 方向键选择候选后 Enter，或输入完整变量名直接 Enter，立即跳到对应地址。
- V0.5.2 的启动 AXF 自动加载、V0.5.1 的 CE 风格编辑/批量复制、V0.5.0 的 visible-window 读取均保持。

## 符号跳转示例

```text
Address / Symbol: BlowerParamsObj.m_PosSpeed
                    ↓ Enter
AXF/DWARF SymbolIndex
                    ↓
              0x20002918
                    ↓
             Memory Explorer
```

输入 `BlowerParamsObj` 时，下拉列表可继续显示其成员，例如：

```text
Symbol                         Type       Address
BlowerParamsObj                struct     0x20002894
BlowerParamsObj.m_PosSpeed     float      0x20002918
BlowerParamsObj.m_Position     float      0x2000291C
```

## 运行

```text
run.bat
```

## 当前验证状态

- compileall / pytest：见 `state/TEST_STATUS.md`
- Qt 下拉交互真实运行：PENDING_ENVIRONMENT
- 真实 AXF + J-Link 跳转读取：PENDING_HARDWARE
