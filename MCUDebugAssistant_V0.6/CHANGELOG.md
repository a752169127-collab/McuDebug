# V0.6.16 — AI Documentation Layout

## Changed
- Historical Release Reports moved from root to `docs/releases/`.
- Project state moved to `docs/state/`; ADR/architecture references to `docs/architecture/`; Workflow/Checklist/AI helper to `docs/development/`.
- Added `docs/README.md` and `docs/releases/README.md` indexes.
- Updated START_HERE / AGENTS / SKILL / manifest and active document links so a fresh AI can navigate subfolders directly.
- Root now keeps only stable entry documentation rather than one Release Report per version.
- Window title updated to V0.6.16; no runtime debugging behavior changed.

## Verification
- compileall PASS; full pytest 136 passed; V0.6.16 targeted documentation-layout regression 5 passed.

---

# CHANGELOG

## V0.6.15 — Cross-Module Symbol Actions
- Added Memory Symbol `Add to Scope` while retaining `Add to Watch / Copy Symbol`; Raw Memory selections can also be sent to Scope.
- Added Watch row context actions: `Add to Scope / Open in Memory / Copy Symbol`.
- Added Scope channel context actions: `Open in Memory / Add to Watch / Copy Symbol`; RTT target-defined channels keep only safe copy behavior because they do not carry AXF addresses.
- Added `MemoryExplorerPage.open_symbol_location()`: exact name+address matches use semantic Symbol navigation, while manually named rows fall back to raw address navigation without guessing identity.
- Cross-module actions reuse the existing Watch/Scope/Memory objects and the single `JLinkWorker`; no new probe owner or acquisition path was introduced.
- Added V0.6.15 static regressions for menu surfaces, MainWindow signal wiring, RTT guard, Memory semantic fallback, and single-worker preservation.

## V0.6.14 — Symbol Navigation Focus
- Explicit Symbol/member navigation in Symbols View now centers and highlights the resolved typed row once, making the destination visually unambiguous.
- Refresh preserves only an actually selected row instead of stale `currentIndex()` state, so a cleared selection stays cleared.
- Clicking empty Symbols viewport space clears both selection and current index; later Auto Refresh does not resurrect it.
- No changes to J-Link I/O, bounded semantic block reads, AXF/DWARF parsing, or Scope/Watch paths.
- Added V0.6.14 static regressions for one-shot navigation selection, real-selection refresh semantics and blank-space deselection.

## V0.6.13 — Stable Semantic Refresh
- Fixed Symbols View auto/manual refresh snapping the vertical viewport back to the original navigation anchor after every block update.
- Symbol navigation now centers the anchor once; subsequent refresh/model rebuilds preserve vertical/horizontal scroll position.
- Removed the artificial persistent row selection created by navigation; only user-created selections persist across refresh.
- Cached semantic refresh no longer rebuilds an unchanged local model. No J-Link read amplification or acquisition-path changes.
- Added V0.6.13 regression coverage for refresh viewport preservation, one-shot anchor focus and patch-byte view preservation.

## V0.6.12 — Semantic Memory View
- Added `Memory View: Auto / Raw / Symbols`. Auto keeps numeric-address navigation in the CE-style Raw view and switches Symbol/member navigation to the semantic typed view.
- Added a bounded `SymbolMemoryView` that lists nearby scalar AXF/DWARF leaves as `Address / Symbol / Type / Value`, so arrays such as `m_BiasAD[0]...[3]` appear as real members instead of only `+00/+02/...` cells.
- Each Symbol row decodes from its own normalized datatype/size (`uint8/uint16/uint32/float/double/...`) while sharing one raw block read. No per-symbol J-Link reads were introduced.
- Added `SymbolIndex.scalar_starts_in_range()` with DWARF-first duplicate suppression and `plan_symbol_read_window()` using the existing 2 KiB Memory read ceiling.
- Symbol rows support double-click typed edit and context actions for Add to Watch / Copy Symbol. Raw Hex/Text editing remains unchanged.
- Added V0.6.12 regression coverage for array-member ordering, DWARF preference, bounded semantic read planning, mode wiring and shared block-cache fanout.

## V0.6.11 — Engineering Presets
- Replaced single-step SpinBox UX for Memory Auto Refresh, Watch polling, Scope sampling and Scope buffer with editable engineering preset drop-downs.
- Presets: Memory `100/200/500/1000/2000/5000 ms`; Watch `10/20/50/100/200/500/1000/2000 ms`; Scope sampling `10/20/50/100/200/500/1000/2000/5000 Hz`; Scope buffer `1/2/5/10/15/30/60/120 s`.
- Scope FPS now uses the same editable preset control with `15/30/60/90/120/144 FPS`.
- Custom in-range values remain typeable and persisted; existing integer settings remain compatible.
- Scope buffer keeps the existing 120 s maximum to preserve the current 1.5M-point raw-ring product bound. No acquisition, J-Link ownership, timing or buffer algorithms were changed.

## V0.6.10 — Compact Connection Panel
- J-Link Connection configuration can be collapsed/expanded with a persistent `− / +` control.
- Successful connection auto-collapses the configuration area while leaving the connection summary and `Disconnect` visible; disconnect auto-expands it again. Connected configuration fields remain disabled even if manually expanded.
- Test Automation hides duplicate Qt vertical row headers; Workflow removes the redundant explicit `#` column and Results keeps only its business `Case` column.
- No changes to J-Link ownership, acquisition, Memory, Watch write semantics, or Automation execution.

## V0.6.9 — Stable History Controls
- Added a persistent `Delete History` toolbar button beside the Address/Symbol history control. It removes the selected/current history entry after the combo popup closes, while preserving the current Memory destination.
- Existing history selection is navigation-only and no longer updates MRU order. Choosing a saved Symbol/address repeatedly leaves the history list in the same order.
- Newly typed successful queries still use the existing bounded/deduplicated MRU insertion rule.
- Removed the History popup context-menu wiring as the primary delete path because nested popup menus can disappear when the editable QComboBox closes on Windows/PySide6. Delete-key remains a secondary shortcut.
- Preserves V0.6.8 Symbol/completer isolation, Symbol-first display, typed navigation, auto-fit, single J-Link owner and no-readback writes.

## V0.6.8 — Memory Symbol/History Reliability
- Fixed the remaining editable `QComboBox + QCompleter` Enter race: Symbol completion is now committed only by `QCompleter.activated`; the history combo forwards `activated(int)` only when its own MRU popup was actually opened. A Symbol selection can no longer be overwritten by a stale history row such as `__lit__00000000`.
- Address / Symbol Enter no longer guesses from completer `currentIndex/currentCompletion`; exact Symbol/raw-address text uses a deterministic path, while partial candidate selection is owned by the completer.
- Added per-item history deletion: right-click a history row and choose `Delete This History`, or highlight it and press Delete. `Clear History` remains the explicit remove-all action.
- Added `symbol_width_mode` settings migration. Older saved narrow manual widths are migrated to automatic full-visible-Symbol fitting once; new V0.6.8 manual drags can still persist explicitly as manual mode.
- Preserves Symbol-first editor display, typed Symbol navigation, local AXF filtering, single J-Link owner and no-readback default writes.

## V0.6.7 — Memory Navigation + Reliable Watch Commit
- Fixed keyboard Symbol completion/history Enter navigation so the explicitly highlighted row is resolved exactly once; stale `QCompleter.currentCompletion()` state is no longer used for hidden-popup fallback.
- History activation now resolves the selected MRU model row directly instead of round-tripping through the editable combo/completer state.
- Symbol navigation preserves the full Symbol/member name in the Address / Symbol editor; raw manually-entered numeric addresses remain canonical `0xXXXXXXXX`.
- Memory Symbol column now auto-fits the longest visible Symbol by default with a cached, local-only width calculation; double-click returns to auto-fit after a manual width override.
- History and Symbol completion popups auto-fit Symbol/Type/Address columns when their local models are rebuilt, reducing manual header resizing.
- Watch Set Value commit moved to `QStyledItemDelegate.setModelData()`, making Enter and mouse focus-out share the same authoritative commit path. Explicitly re-entering the same value still produces a hardware write; untouched cells do not, and the dirty guard prevents duplicate writes.
- Preserves single J-Link owner, no read-back verify default writes, AXF local completion and V0.4.23 Scope performance architecture.

## V0.6.6 — Symbol Typed Memory Navigation
- Memory Address/Symbol history popup now shows three columns: History, Type, Address, while preserving the original editable combo width.
- History Type/Address metadata is resolved locally from the latest AXF/DWARF SymbolIndex and refreshed on symbol reload; no target I/O is added to history display.
- Navigating to an exact scalar Symbol/member automatically applies its AXF/DWARF datatype to the Memory value pane before the jump (`uint8`, `int16`, `float`, etc.).
- Raw numeric addresses and non-scalar/unknown Symbol types do not trigger datatype guessing and preserve the current Memory display type.
- Preserves V0.6.5 Qt6 `activated(int)` history compatibility, local QCompleter filtering, visible-range reads and single J-Link owner.

## V0.6.5 — PySide6 Memory History Startup Fix
- Fixed startup crash in Memory Explorer on PySide6/Qt6 caused by `QComboBox.activated[str]`; Qt6 exposes the combo activation signal as `activated(int)` and separate text signals.
- History selection now resolves the MRU entry with `itemText(index)` and reuses the existing `_goto()` path.
- No change to Symbol QCompleter filtering, MRU persistence, Memory I/O, Watch, Scope, or Test Automation behavior.

## V0.6.4 — Memory Navigation History
- Memory `Address / Symbol` upgraded to an editable history combo at the original editor width.
- Successful Symbol/address navigation is stored as a 50-item MRU list and persisted in QSettings.
- History drop-down selection reuses the existing local Symbol/address resolution path; typing still performs zero J-Link I/O.
- Added explicit `Clear History` without clearing the current address field.

# V0.6.3 — Persistent Results + Excel Clipboard

## Changed
- New SAMPLE steps default to user-facing `Avg / Min / Max`; `Std` remains explicit opt-in and `Count` remains internal metadata.
- Starting a new Test Automation run no longer clears previous Results; runs append to the existing result table until the user explicitly clears it.
- Removed the top-level `Export CSV` action. Results now owns `Copy Results` and `Clear Results` controls.
- `Copy Results` copies the complete result table as tab-separated text with a header row for direct paste into Excel.
- `Clear Results` is the only normal UI path that clears accumulated results and requires explicit confirmation.
- Completed runs still clear only the Run/Runtime table and automatically open Results.

## Preserved
- Runtime Context remains separate from the user Result schema.
- Full internal Count/Avg/Min/Max/Std statistics remain available for compatibility.
- Single J-Link owner, polling execution, Memory/Watch fixes and Scope high-performance path are unchanged.

# V0.6.2 — Clean Automation Results

## Changed
- SAMPLE now exposes selectable Result Statistics: Avg / Min / Max / Std; default is Avg only.
- Sample Count remains internal metadata and is no longer a normal user-facing result.
- Case Results/CSV now use explicit output projection instead of dumping the whole Runtime Context.
- When all cases complete, Runtime detail is cleared and the UI automatically opens Results.

## Preserved
- Full Count/Avg/Min/Max/Std are still calculated internally, so legacy Calculate/Assert plans can continue referencing hidden statistics.
- Single J-Link owner, Polling execution, WAIT STABLE, V0.5.5 Memory/Watch and V0.4.23 Scope paths are unchanged.

# V0.6.1 — Workflow Simplification + Step Dialog Layout Fix

## Changed
- New Step Type picker now exposes only SET / WAIT / WAIT STABLE / SAMPLE / MANUAL INPUT / SAVE RESULT.
- V0.6.0 WAIT UNTIL / CALCULATE / ASSERT remain supported only for saved-plan compatibility and are not offered for new steps.
- Default steady-state calibration template no longer inserts CALCULATE nodes.

## Fixed
- Fixed overlapping/garbled labels after repeatedly changing Workflow Step Type. Root cause: `_clear_body()` deleted direct widgets but left nested QFormLayout/QHBoxLayout trees alive. V0.6.1 recursively destroys nested layouts/widgets before rebuilding the form.

# V0.6.0 — Test Automation Studio

## Added
- New `Test Automation` tab with no-code Parameter Matrix + ordered Workflow editor.
- Parameter List/Range and Cartesian/Zip enumeration with Case Preview.
- Generic workflow nodes: SET, WAIT, WAIT UNTIL, WAIT STABLE, SAMPLE, MANUAL INPUT, CALCULATE, ASSERT, SAVE RESULT.
- AXF/DWARF symbol completion for MCU variables used by test steps.
- Multi-signal Max-Min steady-state detection with Window/Hold/Polling/Timeout and Continue/Skip/Stop timeout behavior.
- Stable-window follow-up SAMPLE statistics: Count/Avg/Min/Max/Std.
- Manual external measurement input for PF300/VT650-style workflows, plus structured error calculations and assertions.
- Test Plan JSON save/load, runtime context, dynamic results table and CSV export.

## Architecture
- Automation target access remains in the existing single `JLinkWorker`; GUI never calls J-Link directly.
- Test Run stops continuous Watch/Scope sampling in V0.6.0 and uses deterministic request/response polling.
- No arbitrary `eval/exec`; `${Parameter}` tokens and whitelisted Calculate/Assert operations are used instead.
- Parameter Matrix and Workflow are separate so respiratory, motor, BMS, power and calibration scenarios can reuse the same engine.

## Verification
- compileall: PASS
- pytest: 75 passed
- Qt Runtime Smoke: PENDING_ENVIRONMENT
- Real AXF/J-Link Automation: PENDING_HARDWARE

---

# V0.5.5 — Memory Symbol Resize + Watch Commit Fix

## Fixed
- Memory Symbol 列不再固定 32 字符宽；可拖动 Symbol/Hex 之间的分隔线自由调整，解决长变量名被 elide 后无法展开查看的问题。
- Watch `Set Value` 输入后如果不按 Enter、直接点击其它位置，现会先提交编辑内容再走既有 WriteMemEx 写路径；不再出现表格值看似改了但 MCU 未写入。

## Interaction / Performance
- Symbol resize 只改变绘制几何和横向滚动范围，不重新解析 AXF、不访问 J-Link。
- Set Value focus-out 只对 `textEdited` 标记过的编辑器触发；Enter + editingFinished 使用 dirty guard 去重，避免一次编辑重复写两次。
- V0.5.4 Symbol completion、本地 MatchContains、V0.4.23 Scope 性能链保持不变。

## Verification
- `python -m compileall -q .`: PASS
- `pytest -q`: 63 passed
- Windows/PySide6 resize interaction: PENDING_USER_HARDWARE
- Real J-Link Set Value focus-out write: PENDING_USER_HARDWARE

---

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
- compileall / pytest: see `docs/state/TEST_STATUS.md`
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
