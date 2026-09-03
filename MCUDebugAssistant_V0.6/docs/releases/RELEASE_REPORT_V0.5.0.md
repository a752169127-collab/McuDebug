# RELEASE REPORT — V0.5.0 Memory Explorer

## Goal
把原单地址 Memory R/W 升级为 Symbol-aware Hex Memory Explorer，并移除默认写后回读校验。

## Implemented
- Virtual 32-bit Memory View / 16 Bytes per row
- Visible-range block reads with debounce
- CE-style context options: display type, text encoding, separator, symbols, symbol offsets, changes
- AXF/ELF/DWARF SymbolIndex
- Edit / copy / add to Watch
- Optional auto refresh, default OFF
- Worker block read/write under single J-Link owner
- Typed/Watch/Explorer writes use WriteMemEx only by default

## Automated Verification
- compileall: PASS
- pytest: 46 passed
- targeted memory logic: PASS
- targeted no-readback-write regression: PASS

## Pending
- PySide6 GUI smoke in a Qt-capable environment
- Real Windows + J-Link hardware validation
- RAM edit/readback validation by explicit F5
- AXF/DWARF symbol overlay validation against a real firmware image

## Confidence
- Pure Python / static logic: VERIFIED_AUTOMATED
- Qt interaction: PENDING_ENVIRONMENT
- J-Link behavior: PENDING_HARDWARE
