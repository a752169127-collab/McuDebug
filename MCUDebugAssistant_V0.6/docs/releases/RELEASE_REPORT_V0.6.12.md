# RELEASE REPORT — V0.6.12 Semantic Memory View

## User request
When AXF/DWARF is available, Memory should show nearby real variables/members such as `BlowerParamsObj.m_BiasAD[0]...[3]` rather than forcing the user to infer values from fixed `+00/+02/...` offsets. Each member must use its own real datatype/size.

## Design
- Preserve the existing CE-style Raw Memory view.
- Add a second semantic Symbol view instead of replacing Raw.
- Add `Auto / Raw / Symbols` view modes.
- `Auto`: Symbol/member navigation -> Symbols; explicit numeric-address navigation -> Raw.
- Symbol view lists typed scalar leaves in a bounded neighborhood and decodes all rows from one shared raw block read.
- No per-member target reads and no new J-Link owner/session.

## Implementation
- `core/memory_browser.py`
  - `SymbolIndex.scalar_starts_in_range()` returns typed scalar/member leaves in address order.
  - DWARF typed leaves suppress same-address ELF size-guess fallback rows.
  - `plan_symbol_read_window()` plans a bounded/aligned neighborhood read, maximum 2048 bytes.
- `ui/memory_explorer.py`
  - New `SymbolMemoryView` with `Address / Symbol / Type / Value` columns.
  - Full Symbol paths auto-fit locally.
  - Mixed member types decode independently from shared bytes.
  - Double-click typed edit; context Add to Watch / Copy Symbol.
  - `MemoryExplorerPage` adds `View: Auto / Raw / Symbols` using a stacked Raw/Symbol renderer.
  - One worker read result is fanned out to both local caches; inactive view never initiates per-symbol I/O.

## Preserved behavior
- Single J-Link Owner.
- Visible/bounded Memory reads.
- No forced read-back verify after writes.
- Raw Hex/Text direct edit, batch copy/paste, Symbol history and local QCompleter.
- V0.6 Test Automation and V0.4.23 Scope path unchanged.

## Verification
- `python -m compileall -q .`: PASS
- `pytest -q`: 119 passed
- Targeted V0.6.12 semantic-memory regression: 5 passed
- PySide6/Windows visual smoke: PENDING_ENVIRONMENT / PENDING_USER_QT_SMOKE
- Real AXF/J-Link semantic values/edit: PENDING_HARDWARE

## Hardware acceptance checklist
1. Load a real AXF containing a struct array member such as `m_BiasAD[0]...[3]`.
2. Navigate by Symbol with View=Auto; confirm Symbols view opens.
3. Confirm each array element appears as a separate row with its exact address/type/value.
4. Confirm adjacent mixed types are decoded correctly.
5. Refresh/Auto Refresh and confirm only one bounded Memory read is issued per refresh, not one read per row.
6. Double-click a writable scalar row, edit it, and confirm normal WriteMemEx-only product semantics.
7. Navigate by raw numeric address with View=Auto; confirm classic Raw view remains available.
