# MCU Debug Assistant V0.3.7

## V0.3.7 Stacked Fit + Scope FPS

### Stacked `查看所有波形` freeze fix

Stacked plots are X-linked. V0.3.6 repeatedly set the same X range on every linked plot, which could generate a large range-notification chain when many channels were visible. V0.3.7 sets the full-buffer X range only on the first/master plot; linked plots follow automatically. Y fitting remains independent per stacked channel.

The Y-fit path also avoids allocating a full transformed array for every channel. The displayed extrema are calculated from raw min/max plus Gain/Offset.

### Scope FPS

The Scope toolbar now has an editable `FPS` selector with J-Scope-like presets: `1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60`. Any integer from 1 to 60 is accepted. Default: 30 FPS.

`Sampling` and `FPS` are independent:

```text
HSS Sampling = 1000 Hz
Scope FPS     = 30 FPS

1000 raw samples/s -> buffer/statistics/export
30 redraws/s       -> pyqtgraph + Scope table
```

Reducing FPS reduces GUI load without reducing the HSS/RTT data captured. The J-Link worker may emit Scope chunks at up to 60 Hz so a 60 FPS display setting can be honored.


## V0.3.6 查看所有波形

`查看所有波形` 现在直接按照 Scope 当前缓存中的完整数据计算坐标范围，不再使用 pyqtgraph `autoRange()`：

- X轴：缓存第一个采样点到最后一个采样点。缓存达到设定时间后，例如 Buffer=30s，就是最新30秒完整铺满横轴。
- Overlay：所有可见通道经过 Gain/Offset 后统一计算完整缓存 Y Min/Max。
- Stacked：每个通道独立按照自身完整缓存计算 Y Min/Max。
- 常量波形也会自动留出 Y 轴上下边距。
- 该按钮只做一次 Fit，不切换“跟随最新数据”。

# MCU Debug Assistant V0.3.6

V0.3.6 keeps the verified J-Link memory read/write, Watch, AXF/ELF, HSS/RTT Scope and performance behavior, and fixes full-buffer fitting for `查看所有波形`.

## Run

```bash
pip install -r requirements.txt
python main.py
```

Windows uses the SEGGER J-Link DLL selected in the connection area. Keep Python and DLL bitness matched.

## Existing Watch functions

- `JLINK_ReadMemEx` / `JLINK_WriteMemEx` memory access and write-back verification.
- Watch: Name / Address / Type / Current / Set Value / Average / Min / Max.
- Edit `Set Value` and press Enter to write immediately.
- Watch acquisition/statistics run in the J-Link worker; GUI snapshots are limited to about 25 Hz.
- `复制平均值` copies values only as one TAB-separated Excel row.
- AXF/ELF browser supports the supplied Keil ARMCC5/DWARF3 file, including structure/array members.
- Reloading AXF rebinds Watch/Scope addresses by full symbol name; missing symbols are removed.
- Shift/Ctrl multi-select and Delete are supported.




## V0.3.5 Scope analysis / Gain / mouse probe

- `暂停采样` only stops HSS/RTT acquisition. Buffered waveform data and Scope statistics remain on screen for analysis; pressing Start again resumes/appends instead of clearing the capture.
- HSS/RTT timestamps that restart from zero after resume are shifted forward to keep one continuous display timeline.
- Scope display transform is `Y_display = Y_raw * Gain + Offset`. Raw samples, statistics, X1/X2 raw values and CSV export are not modified by Gain/Offset.
- On the focused waveform, `+` / `-` changes the selected channel Gain by ×1.25 / ÷1.25; `Ctrl +` / `Ctrl -` changes the selected channel Offset. Gain and Offset are also directly editable in the channel table.
- Moving the mouse over the waveform shows a vertical X probe line and a floating readout for every active channel at the nearest acquired sample. If a display transform is active, the tooltip shows raw value and transformed display value.
- The Scope channel table is moved below the waveform and now contains: Show / Name / Address / Type / Current / Average / Min / Max / Gain / Offset. Statistics are based on raw acquired values.
- Log is now a separate main tab so Watch and Scope can use the full vertical workspace.
- Right-click waveform menu keeps cursor/export actions and also provides `清空缓存数据` for explicitly starting a fresh capture.

## V0.3.4 follow / export behavior

- `跟随最新数据` is the single source of truth for live scrolling. When checked, only the X window follows the newest buffered sample; Y range/baseline are never changed by follow.
- Unchecking it freezes the current X view. Mouse pan/zoom and `查看所有波形` do not modify the checkbox state.
- pyqtgraph's built-in `A` auto-range control is hidden and continuous auto-ranging is disabled.
- `查看所有波形` performs a one-shot fit only.
- Raw CSV export is available from the custom waveform right-click menu as `导出缓存数据...`; it exports the current full buffer rather than display-decimated points.

## V0.3.1 HSS frame fix

HSS sampling now explicitly starts with `JLINK_HSS_FLAG_TIMESTAMP_US`. The raw stream is decoded as:

```text
[timestamp_us U32][configured HSS block data...]
```

The timestamp is used for the X axis and is **not** decoded as a target variable. This fixes the V0.3 failure mode where a constant value could appear as an alternating timestamp/value ramp or dense triangular waveform. The decoder supports U32 timestamp wrap and partial `JLINK_HSS_Read()` chunks.

Live plots now return to automatic rolling follow on Start and on `查看所有波形`. A manual mouse pan/zoom disables follow so historical data can be inspected; pressing `查看所有波形` resumes live follow.

## V0.3 Scope

The Scope page has two acquisition sources:

### HSS

HSS is the normal AXF-symbol waveform path:

```text
AXF / ELF symbol
       ↓
Name + Address + Type
       ↓
JLINK_HSS_Start()
       ↓
JLINK_HSS_Read()
       ↓
short Scope buffer
       ↓
pyqtgraph
```

Usage:

1. Connect J-Link normally.
2. Open **Scope**.
3. Keep Source = `HSS`.
4. Press `AXF添加成员...` and select one or more scalar AXF members.
5. Set Sampling Hz.
6. Press `开始采样`.

The Scope channel table supports the same scalar types used by Watch: int8/uint8/int16/uint16/int32/uint32/int64/uint64/float/double.

HSS channels with adjacent/overlapping memory are merged into compact memory blocks. Unrelated address gaps are not merged.

### RTT (J-Scope RTT Normal compatible)

RTT is not a separate page. Select Source = `RTT` in Scope. The host starts RTT processing and finds the first Up Buffer whose name matches:

```text
JScope_<FORMAT>
```

Supported packet tokens in V0.3:

```text
t4       uint32 timestamp in microseconds, first field only
b1       boolean
i1/i2/i4 signed integers
u1/u2/u4 unsigned integers
f4       float
```

Example target-side channel name:

```text
JScope_t4f4f4
```

Each packet is then:

```text
uint32_t timestamp_us
float    Value1
float    Value2
```

If `t4` exists, Scope X is target time in seconds relative to the first packet. Without `t4`, X is Sample Index.

RTT Normal channels are target-defined, so the AXF member picker is disabled in RTT mode.

## Scope display

Two display modes are available:

- `Overlay`: all visible channels share one plot.
- `Stacked`: each visible channel has its own Y axis while plots share the X axis.

`查看所有波形` calls auto-range for all current plots. Mouse wheel/pan behavior is provided by pyqtgraph.

### X1 / X2 / Y1 / Y2 cursors

Right-click inside a waveform to:

```text
设置 X1 / X2 / Y1 / Y2
删除 X1 / X2 / Y1 / Y2
删除全部游标
```

Cursor lines are draggable. The status row shows:

```text
X1, X2, ΔX
Y1, Y2, ΔY
Selected channel
Value@X1
Value@X2
```

`Value@X1` and `Value@X2` use the nearest real acquired sample of the selected channel rather than inventing an interpolated value.

In Stacked mode Y1/Y2 belong to the currently selected channel plot. X1/X2 are synchronized across all stacked plots.

## Buffer and GUI performance

V0.3 deliberately uses a short live buffer:

```text
5 seconds
maximum 50000 points
```

Acquisition is separated from GUI painting:

```text
J-Link owner worker
      │
      ├─ HSS / RTT acquisition
      │
      └─ chunks accumulated
              │
              ▼
        GUI <= about 25 Hz
              │
              ▼
           Scope curves
```

High sample rates therefore do not imply an equally high Qt repaint rate. Curves are also display-decimated when the current visible buffer contains more than 10000 points; cursor lookup still uses the original buffered samples.

## AXF reload

The existing AXF reload operation now also rebinds HSS Scope channels:

```text
Reload AXF
   ↓
parse symbols again
   ↓
match complete symbol path
   ↓
update Scope Address / Type
   ↓
remove channels that no longer exist
```

For the supplied AXF the regression check still resolves:

```text
BlowerParamsObj.m_PosSpeed  0x20002918  float
BlowerParamsObj.m_Position  0x2000291C  float
```

## V0.3 intentionally not included yet

The following remain outside this version: RTT Console, long recordings/replay, event markers, pause-display mode, time-range export and other advanced Scope features.


## V0.3.2 Scope interaction

Scope no longer shows pyqtgraph's own `View All / X axis / Y axis / Export...` context menu. Right click is owned only by the MCU Debug Assistant cursor menu.

The live in-memory buffer is configurable in the Scope toolbar (`Buffer`, 1..120 s, default 30 s). `导出缓存数据...` in the waveform right-click menu writes the exact currently buffered samples to CSV rather than exporting a plot image. The first column is `Time(s)` for timestamped HSS/RTT or `Sample Index` when RTT has no timestamp; following columns are the Scope channels.

Click a waveform so it has keyboard focus, then use:

```text
+          Y zoom in
-          Y zoom out
Ctrl +     move waveform baseline up
Ctrl -     move waveform baseline down
```

These commands modify only the visible Y range. They do not change the sampled raw values used by cursors or CSV export, and they do not stop live X-axis following. Mouse pan/zoom still disables live follow until `查看所有波形` is used again.
