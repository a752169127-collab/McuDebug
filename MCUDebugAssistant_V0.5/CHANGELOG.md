# V0.5.4 — Symbol Completion Popup Fix

## Fixed
- 修复 Memory `Address / Symbol` 使用自定义多列 `QTreeView` 作为 `QCompleter` popup 时，在 Windows/Qt 样式下候选窗口可能被压缩到接近表头高度，导致像 `MaxRpm` 这种已存在的匹配符号看不到。
- Completion popup 增加稳定可见高度（240~420 px），短查询、单结果和多结果都保留可浏览候选区域。

## Performance / Preserved
- 仅修复 popup 几何，不改变 `QStandardItemModel + QCompleter(MatchContains)` 本地过滤架构。
- 输入字符仍不重建 AXF Symbol model、不解析 AXF、不触发 J-Link ReadMemEx。
- V0.5.3 完整符号/数组/成员地址跳转、V0.5.2 自动加载 AXF、V0.5.1 Memory 直接编辑、V0.4.23 Scope 性能架构全部保持。

## Verification
- User screenshot reproduces header-only/too-short popup: VERIFIED_USER_HARDWARE (symptom)
- compileall / pytest: see `state/TEST_STATUS.md`
- Qt popup runtime after fix: PENDING_USER_HARDWARE

---

# V0.5.3 — Symbol Address Navigation

## Added
- Memory `Address / Symbol` 统一输入框：支持数值地址、AXF/DWARF 变量、结构体成员和数组成员路径。
- 输入部分名称时显示 Symbol / Type / Address 下拉候选；支持 contains filter、大小写不敏感和 Enter 确认。
- `SymbolIndex.exact_name()` / `preferred_symbols()` / `search_names()`，复用 parser 已展开的 `foo.bar` / `buffer[1]` 路径。

## Performance
- completion model 只在 AXF/ELF load/reload 时构建一次。
- 输入每个字符时不重建 Symbol rows、不重新解析 AXF、不访问 J-Link。
- completion model 离屏构建并一次替换，降低 AXF auto-load 时增量 UI invalidation。

## Preserved
- V0.5.2 startup AXF auto-load。
- V0.5.1 CE-style Memory direct editing / block clipboard。
- Visible-window Memory reads、single J-Link owner、WriteMemEx-only default write。
- V0.4.23 Scope high-performance architecture。

## Verification
- compileall: PASS
- pytest: 57 passed
- Qt completion popup: PENDING_ENVIRONMENT
- real AXF + J-Link symbol jump: PENDING_HARDWARE

---

# V0.5.2 — AXF Symbol Auto-load

## Fixed
- 启动恢复 `symbol_file` 时不再只恢复路径文本；若文件仍存在，会自动解析 AXF/ELF/DWARF 并把符号同步给 Memory / Watch / Scope。
- 保存路径已失效时自动加载只记录并跳过，不搜索目录猜测替代文件。

## Preserved
- V0.5.1 Memory Explorer CE 风格编辑/复制交互保持。
- J-Link 单 Owner、visible-window read、WriteMemEx-only 默认写语义保持。
- V0.4.23 Scope 高性能链不修改。

## Verification
- compileall / pytest: 53 passed
- Qt startup with saved AXF: PENDING_ENVIRONMENT

---

# V0.5.1 — Memory Explorer Interaction Upgrade

## Fixed

- 首次启动/加载 Memory 时现在固定定位 `0x20000000`，避免首屏落在 0 地址或旧会话随机地址。
- Symbol 列改为固定字符宽度、单行左对齐、超长名称 elide；不再把多个符号用 `|` 拼接后挤入 Hex 区。
- Address 与 Memory value 使用不同 palette role，改善地址/数据视觉区分。

## Added

- Byte Hex 区 CE 风格两位 Hex 直接输入写入并自动前移。
- 非 Byte typed view 的 in-cell editor。
- Text 区按 ASCII / UTF-8 / UTF-16LE / GBK 直接键入与粘贴写入。
- 鼠标拖动 / Shift 连续 byte range 选择。
- 批量复制内存块为 Hex 或按当前文本编码复制。
- Hex block / Text block Ctrl+V 写入。
- 双击 Value/Text 的弹窗编辑。

## Changed

- Memory Explorer direct edit 不再弹第二层 `QMessageBox`；双击编辑弹窗的 OK 即确认，直接键入/粘贴直接写。
- 独立 Typed Memory R/W 表单仍保留原显式写确认。
- `JLINK_WriteMemEx` 完整 byte count 仍是默认写成功条件，不追加 ReadMemEx Verify。

## Preserved

- Visible-window + debounce 读取策略不变。
- J-Link 单 Owner 不变。
- V0.4.23 Scope 高性能链不重构。

## Verification

- `python -m compileall -q .`: PASS
- `pytest -q`: 51 passed
- Qt smoke: PENDING_ENVIRONMENT
- Real J-Link: PENDING_HARDWARE

---

# V0.5.0 — Memory Explorer

V0.5.0 建立 Symbol-aware visible-range Memory Explorer 基线：32-bit 虚拟地址浏览、显示类型/编码/符号/变化、block read/write、WriteMemEx-only 默认写语义。
