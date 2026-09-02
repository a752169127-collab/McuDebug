# LATEST_HANDOFF — V0.6.6

## What changed
1. Memory Address/Symbol MRU popup now presents `History / Type / Address` columns; the editable combo itself remains the original 320~520 px footprint.
2. History metadata is resolved only from the current local `SymbolIndex`. AXF reload refreshes the metadata; opening/typing history still causes zero target I/O.
3. Exact scalar Symbol/member navigation now applies the AXF/DWARF datatype before `goto_address()`. `uint8` therefore opens as UInt8 immediately; int16/uint16/int32/uint32/int64/uint64/float/double behave likewise.
4. Raw addresses and non-scalar types (`struct`, `array`, unknown) do not guess a type and preserve the current Memory display mode.
5. V0.6.5 `QComboBox.activated(int)` compatibility, local Symbol completer, visible-range Memory reads and single J-Link owner are preserved.

## Verification
- compileall: PASS
- pytest: 97 passed
- Windows/PySide6 history popup smoke: PENDING_USER_QT_SMOKE
- Real AXF/J-Link typed Symbol jump: PENDING_HARDWARE

## First user smoke
1. Load AXF and query a known `uint8` member; confirm popup shows `uint8` and its address.
2. Press Enter/select it; Memory value pane should switch from Byte Hex to UInt8 on the first jump.
3. Repeat with float/uint16 and verify type follows the Symbol.
4. Select a raw numeric history address; current display type should remain unchanged.
5. Reload AXF and confirm history Type/Address columns refresh without UI stalls.

## Do not regress
Do not infer scalar types from arbitrary raw addresses or containers. Symbol-driven display typing is only for supported exact AXF/DWARF scalar types, and history metadata remains local presentation state with no additional J-Link traffic.
