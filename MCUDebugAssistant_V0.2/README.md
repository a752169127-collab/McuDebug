# MCU Debug Assistant V0.2.6

V0.2.6 keeps the verified J-Link memory read/write, Watch and AXF/ELF functionality, and optimizes Watch performance when monitoring many variables.

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Watch

- Multiple variables: Name / Address / Type / Current / Set Value / Average / Min / Max.
- `Set Value`: edit the cell and press Enter to write immediately, then read back for verification.
- Periodic `JLINK_ReadMemEx` sampling runs in the J-Link worker thread.
- Clear statistics without deleting Watch variables.
- `复制平均值` copies values only as one TAB-separated row, ready to paste directly into Excel. No variable-name header and no popup are used; status is written to Log.

## AXF / ELF symbol browser

Choose a Keil `.axf` or ELF file and press `添加成员...`.

The browser is intentionally close to J-Scope:

```text
Name                         Type                       Size  Address      Select
AXF file
  BlowerParamsObj            struct _BLDC_PARAMS_OBJ_   160  0x20002894
    m_PosSpeed               float                        4  0x20002918   [ ]
    m_Position               float                        4  0x2000291C   [ ]
```

Check one or more scalar members in the Select column and press OK to add them to Watch.

### Keil ARMCC5 support

ARM Compiler 5 commonly writes DWARF3 member locations in legacy block expressions such as:

```text
DW_AT_data_member_location: DW_FORM_block
DW_OP_plus_uconst: 132
```

V0.2.3 has a built-in DWARF 2/3 reader that understands this representation. For the supplied AXF it resolves:

```text
BlowerParamsObj             0x20002894   struct _BLDC_PARAMS_OBJ_   160
BlowerParamsObj.m_PosSpeed  0x20002918   float                       4
BlowerParamsObj.m_Position  0x2000291C   float                       4
```

The built-in parser also handles common scalar types, typedef/const/volatile wrappers, structures, unions, arrays and static absolute MCU addresses. `pyelftools` remains in `requirements.txt` as a fallback for other DWARF dialects/newer toolchains.

## Fast search implementation

The old browser rebuilt a `QTableWidget` every time Search changed. That caused input lag even with only a few hundred symbols.

V0.2.3 instead builds the symbol tree once:

```text
AXF -> DWARF parse -> QStandardItemModel -> QSortFilterProxyModel -> QTreeView
```

Typing only changes the proxy filter. Rows are not recreated and column sizes are not recomputed. Tree expansion is delayed briefly and coalesced so rapid typing remains responsive.

## V0.2.6 Watch performance model

Watch acquisition and GUI refresh are intentionally decoupled:

```text
J-Link Worker
  JLINK_ReadMemEx @ requested rate
        |
        +--> Current / Mean / Min / Max (every sample)
        |
        `--> latest display snapshot <= 25 Hz
                         |
                         v
                    Watch GUI
```

For example, at a requested 100 Hz sample rate with 20 variables, all 100 samples/s still participate in statistics, while Qt repaints the table at no more than about 25 FPS. This prevents the GUI event queue from being flooded by per-sample/per-cell updates. `Actual` continues to report the measured acquisition rate, not display FPS.

The dynamic result columns also no longer use `ResizeToContents`, preventing a costly column-width recalculation whenever values change.

## Current scope

V0.2.x is still the Watch stage. HSS/RTT waveform sampling is not implemented here yet. AXF/ELF parsing is kept as a separate symbol subsystem so it can later be reused by Scope and crash/HardFault analysis.


## V0.2.5 AXF Reload / Multi-delete

- AXF / ELF 行新增“重新加载”按钮。
- 重新加载会按 Watch 的完整变量名重新绑定符号地址；地址或基础类型变化时自动更新。
- 重新绑定后清空该变量旧的 Current / Average / Min / Max，避免新旧固件统计混在一起。
- 新 AXF 已不存在的 Watch 变量会自动删除。
- 同名符号有歧义且旧地址也无法唯一匹配时，为避免绑定到错误变量会自动删除并在 Log 中统计。
- Watch 列表支持 Shift / Ctrl 多选。
- 选中一个或多个 Watch 变量后按 Delete 可直接删除；“删除变量”按钮继续保留且同样支持批量删除。
