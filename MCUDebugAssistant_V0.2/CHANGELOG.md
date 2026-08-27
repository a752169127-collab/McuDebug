# V0.2.5

- AXF/ELF 增加“重新加载”：重新解析后按完整变量名刷新 Watch 地址和类型。
- 新 AXF 不存在的 Watch 变量自动删除；同名歧义且无法用旧地址唯一识别时也删除以避免错误绑定。
- AXF 重绑定后清空旧 Current/Avg/Min/Max。
- Watch 改为 ExtendedSelection，支持 Shift/Ctrl 多选。
- Delete 键可删除全部选中变量；删除按钮保留并支持批量删除。

# Changelog

## V0.2.4 - Excel-friendly average copy

- `复制平均值` now copies average values only; variable names are omitted.
- Values are TAB-separated so one paste fills one Excel row across columns.
- Variables without samples produce an empty field, preserving Watch column order.
- Copy remains silent; completion is reported only in Log.

## V0.2.3 - Keil AXF struct members + fast symbol search

- Fixed ARM Compiler 5 / DWARF3 structure-member parsing.
- Added built-in lightweight DWARF 2/3 parser for embedded AXF files; `pyelftools` is no longer required for common Keil ARMCC5 structure browsing.
- Supports legacy `DW_FORM_block` expressions used by ARMCC5 for:
  - `DW_AT_location` / `DW_OP_addr`
  - `DW_AT_data_member_location` / `DW_OP_plus_uconst`
- Structure and array containers are preserved so the browser can show a hierarchy instead of only a flat leaf list.
- Replaced the old `QTableWidget` symbol browser with a model/view `QTreeView`.
- Search no longer destroys/recreates every table row on every keystroke.
- Search filtering is performed by a `QSortFilterProxyModel`; tree expansion is coalesced after typing to avoid UI stalls.
- Symbol browser columns now follow the J-Scope-style layout: Name / Type / Size / Address / Select.
- Leaf symbols are selected with check boxes, then added to Watch with OK.
- Tested against the supplied Keil AXF: `BlowerParamsObj` expands as `struct _BLDC_PARAMS_OBJ_` and resolves `m_PosSpeed` to `0x20002918` and `m_Position` to `0x2000291C`, both `float`.

## V0.2.2 - Clipboard averages + AXF/ELF symbols

- Average snapshot copies directly to clipboard and reports status in Log.
- Added initial AXF/ELF symbol browser and DWARF support.

## V0.2.6 - Watch performance

- Decoupled Watch acquisition/statistics from GUI painting.
- `JLINK_ReadMemEx` sampling still runs at the requested interval in the J-Link worker thread.
- Mean/Min/Max are now accumulated in the worker for every successful acquisition cycle.
- Qt receives only the newest Watch snapshot at up to 25 Hz; intermediate display frames are discarded, but statistical samples are not.
- Watch snapshot updates are applied as one batch instead of one row/signal at a time.
- Removed live `ResizeToContents` behavior for Current/Average/Min/Max columns to avoid repeated header relayout.
- Watch cell text is changed only when the displayed string actually changed.
- Clear Statistics resets both UI-side cached values and worker-side authoritative statistics.
- Actual Sample Rate remains the measured acquisition rate, not the GUI refresh rate.
