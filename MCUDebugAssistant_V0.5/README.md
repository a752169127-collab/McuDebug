# MCU Debug Assistant V0.5.4 — Symbol Completion Popup Fix

V0.5.4 基于 V0.5.3，修复 Memory `Address / Symbol` 候选下拉框在 Windows/Qt 下高度过短、只有表头而看不到真实匹配变量的问题；符号解析与本地过滤逻辑不变。

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
