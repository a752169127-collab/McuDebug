# RELEASE REPORT — V0.5.3

## Release
**MCU Debug Assistant V0.5.3 — Symbol Address Navigation**

## User issues addressed
1. Memory 地址栏无法直接输入 AXF 变量名并换算地址。
2. 希望 `array[1]`、结构体成员等已有 DWARF 路径可直接跳转。
3. 希望输入部分变量名时像 Watch AXF Filter 一样出现候选列表，Enter 确认且输入不卡。

## Technical changes
- `SymbolIndex` 建立名称索引并支持 exact full-path lookup。
- Memory 地址栏挂接三列 `QStandardItemModel + QCompleter(MatchContains)`。
- AXF load 时一次构建 completion rows；键入阶段只有本地 Qt filter。
- Enter 选中符号后换算为 32-bit 地址，再复用原 `goto_address()` + visible-window read。

## Non-regression boundaries
- No J-Link access on symbol keystrokes.
- No AXF reparse on symbol keystrokes.
- Single J-Link Worker unchanged.
- Memory write behavior unchanged.
- Scope V0.4.23 unchanged.

## Verification
- `python -m compileall -q .`: PASS
- `pytest -q`: 57 passed
- Exact member/array path regression: PASS
- Completion wiring/no-per-key target I/O static regression: PASS
- PySide6 runtime popup: PENDING_ENVIRONMENT
- Real AXF/J-Link navigation: PENDING_HARDWARE
