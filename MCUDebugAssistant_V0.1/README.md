
## V0.1.2 Target Device Settings

Device 输入框右侧新增 `...` 按钮，直接调用 J-Link DLL 的原生设备选择窗口：

- `JLINK_DEVICE_SelectDialog()` / `JLINKARM_DEVICE_SelectDialog()`
- 选择后使用 `JLINK_DEVICE_GetInfo()` / `JLINKARM_DEVICE_GetInfo()` 获取设备名称
- 自动把选择结果写回 Device 输入框
- Device 留空后点击 Connect，也会先弹出这个原生 Target Device Settings 窗口

该窗口由 SEGGER J-Link DLL 自己提供，不是 Python 仿制列表，因此设备数据库与当前选择的 J-Link DLL 保持一致。

# MCU Debug Assistant V0.1.2.2

V0.1.2 is the real-hardware foundation of the MCU debugging/algorithm-analysis tool.

## Included

- Windows GUI using PySide6
- J-Link directory selection + automatic scan of J-Link DLLs in that directory
- The program directory is checked first, so a compatible J-Link DLL placed beside the tool can be selected directly
- Automatically prefers `JLink_x64.dll` on 64-bit Python and `JLinkARM.dll` on 32-bit Python when present
- Device can be left empty; J-Link DLL is then allowed to show its own target-device selection dialog during connection
- Device can still be entered explicitly when desired
- SWD / JTAG
- Editable J-Link interface-speed dropdown in kHz, with common presets such as 1000 / 1334 / 1600 / 2000 / 2667 / 3200 / 4000 / 4800 / 5334 / 6000 kHz
- `JLINK_ReadMemEx`
- `JLINK_WriteMemEx`
- Read-after-write byte verification
- int8 / uint8 / int16 / uint16 / int32 / uint32 / int64 / uint64 / float / double
- Decimal and hexadecimal integer input
- Typed value + raw-byte display
- Persist connection settings between runs
- Confirmation before every memory write

## Device selection behavior

The Device field is intentionally optional.

- Enter an exact J-Link device identifier when you already know it.
- Leave it empty when you want J-Link DLL to perform device selection. V0.1.2 does not reject an empty Device field; it leaves the device unspecified and calls `JLINK_Connect()`, allowing the normal J-Link device-selection dialog to appear when required.

This matches the intended SEGGER generic-debugger workflow much better than forcing a manually typed part number.

## J-Link DLL selection

The UI now treats the J-Link installation folder as the primary setting:

1. Select a J-Link directory.
2. The tool scans that directory for `JLink*.dll`.
3. Choose the DLL from the dropdown.
4. Click **刷新DLL** after copying/replacing a DLL in the folder.

Startup search order:

1. This application's directory
2. Current working directory
3. Installed `Program Files\\SEGGER\\JLink*` directories on Windows

The DLL itself is not distributed with this project.

Python and DLL bitness must match.

## Interface speed vs sampling rate

These must remain two different concepts.

### Target interface speed

The current `kHz` control configures SWD/JTAG communication speed through J-Link. It is not the waveform sampling rate.

### Sampling rate (V0.2 / Scope)

The later sampling engine will follow the J-Scope concept:

- User-facing setting uses **Sampling Rate (Hz / kHz)**.
- The UI also shows the derived sample period, e.g. `1000 Hz = 1 ms/sample`, `10 kHz = 100 us/sample`.
- Acquisition frequency and graph repaint frequency are independent.
- Example: HSS may acquire at 1000 Hz while the GUI redraws at only 20-30 Hz.
- HSS and RTT will be alternative acquisition sources feeding the same waveform engine, not separate waveform pages.
- The supported/actual HSS rate will later be constrained by J-Link capability, target interface bandwidth, variable count and data width.

This separation is important: a 5-10 kHz acquisition stream should not force the Qt GUI itself to repaint 5-10 thousand times per second.

## Deliberately NOT implemented yet

- Watch list / periodic refresh / statistics
- Waveform plotting
- HSS acquisition
- RTT waveform acquisition
- X1 / X2 / Y1 / Y2 cursors
- AXF / ELF / DWARF symbol parsing
- RTT Console

RTT Console is not part of the current plan. HSS and RTT belong to the same future Scope acquisition selection.

## Requirements

- Windows 10/11
- Python 3.10+ recommended
- SEGGER J-Link Software installed
- J-Link probe and target MCU

```bash
pip install -r requirements.txt
python main.py
```

## First hardware test

1. Close another debugger session if it owns the same J-Link.
2. Start the tool.
3. Verify the J-Link directory and DLL dropdown.
4. Leave Device blank and click Connect; confirm that the J-Link target-device selection flow works on your machine.
5. Alternatively, enter the exact device identifier and connect directly.
6. Read a known `uint32_t` RAM variable and compare with Keil.
7. Read a known `float` RAM variable and compare with Keil.
8. Write a harmless RAM test variable and verify it from Keil.

Do not start write testing on peripheral-register or Flash addresses.

## Memory API

V0.1.2 still uses the requested APIs:

- `JLINK_ReadMemEx`
- `JLINK_WriteMemEx`

The fourth argument remains `AccessWidth = 0` (automatic/default access width). Typed interpretation is handled by the Python data-type layer.
