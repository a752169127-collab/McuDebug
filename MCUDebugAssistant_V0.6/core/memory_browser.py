from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Iterable, Sequence

from core.datatype import decode_value, get_type_info, supported_types


BYTES_PER_ROW = 16
ADDRESS_SPACE_SIZE = 1 << 32
MAX_ADDRESS = ADDRESS_SPACE_SIZE - 1
DISPLAY_TYPES = ("byte", *supported_types())
TEXT_ENCODINGS = ("ASCII", "UTF-8", "UTF-16 LE", "GBK")
SEPARATOR_BYTES = (1, 2, 4, 8)
DEFAULT_RAM_BASE = 0x20000000


def text_edit_unit_size(encoding: str) -> int:
    """Byte step used when selecting/editing the text pane.

    UTF-16LE has a natural two-byte code unit. Variable-width encodings remain
    byte-addressable; typed text is encoded and advances by the actual payload
    length after a write.
    """
    if encoding == "UTF-16 LE":
        return 2
    if encoding in TEXT_ENCODINGS:
        return 1
    raise ValueError(f"Unsupported text encoding: {encoding}")


def encode_text_input(text: str, encoding: str) -> bytes:
    """Encode Memory Explorer text-pane input into target bytes."""
    value = str(text)
    if not value:
        return b""
    if encoding == "ASCII":
        try:
            return value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("ASCII text can only contain characters 0x00..0x7F") from exc
    codec = {
        "UTF-8": "utf-8",
        "UTF-16 LE": "utf-16-le",
        "GBK": "gbk",
    }.get(encoding)
    if codec is None:
        raise ValueError(f"Unsupported text encoding: {encoding}")
    try:
        return value.encode(codec)
    except UnicodeEncodeError as exc:
        raise ValueError(f"Text cannot be encoded as {encoding}") from exc


def format_hex_block(raw: bytes, *, bytes_per_line: int = BYTES_PER_ROW) -> str:
    """Format a selected memory range for clipboard use."""
    data = bytes(raw)
    if bytes_per_line <= 0:
        raise ValueError("bytes_per_line must be > 0")
    return "\n".join(
        data[i:i + bytes_per_line].hex(" ").upper()
        for i in range(0, len(data), bytes_per_line)
    )


def parse_address(text: str) -> int:
    value_text = str(text).strip()
    if not value_text:
        raise ValueError("Address is empty")
    try:
        address = int(value_text, 0)
    except ValueError as exc:
        raise ValueError(f"Invalid address: {value_text}") from exc
    if not 0 <= address <= MAX_ADDRESS:
        raise ValueError("32-bit MCU addresses only")
    return address


def update_navigation_history(
    history: Sequence[str],
    query: str,
    *,
    max_items: int = 50,
) -> list[str]:
    """Return MRU Memory Address/Symbol history after a successful navigation.

    Numeric addresses are normalized to canonical 32-bit hex. Symbol/member
    paths retain the spelling selected from AXF/DWARF. Duplicate entries are
    moved to the front rather than appended again. This helper is pure so the
    UI can persist history without coupling search typing to target I/O.
    """
    text = str(query).strip()
    if not text:
        return [str(item) for item in history if str(item).strip()][:max(0, int(max_items))]
    if max_items <= 0:
        return []
    try:
        text = f"0x{parse_address(text):08X}"
    except ValueError:
        pass
    key = text.casefold()
    result = [text]
    for item in history:
        value = str(item).strip()
        if not value or value.casefold() == key:
            continue
        result.append(value)
        if len(result) >= max_items:
            break
    return result


def symbol_display_type(type_name: str | None) -> str | None:
    """Return the Memory display type implied by an exact scalar symbol.

    AXF/DWARF scalar types are already normalized to the datatype names used by
    Watch/Scope (uint8/int16/float/...). Containers/arrays or unknown types are
    intentionally ignored so symbolic navigation never guesses a view format.
    """
    text = str(type_name or "").strip()
    return text if text in supported_types() else None


def display_unit_size(display_type: str) -> int:
    if display_type == "byte":
        return 1
    return get_type_info(display_type).size


def format_display_value(raw: bytes, display_type: str) -> str:
    if display_type == "byte":
        if len(raw) != 1:
            raise ValueError("byte display requires exactly one byte")
        return f"{raw[0]:02X}"
    value = decode_value(raw, display_type)
    info = get_type_info(display_type)
    if info.integer:
        return str(value)
    return f"{float(value):.7g}"


def display_value_chars(display_type: str) -> int:
    """Stable character width used by the custom painter.

    It is intentionally conservative so values do not cause per-frame geometry
    measurement/layout churn.
    """
    return {
        "byte": 2,
        "int8": 4,
        "uint8": 3,
        "int16": 6,
        "uint16": 5,
        "int32": 11,
        "uint32": 10,
        "int64": 20,
        "uint64": 20,
        "float": 13,
        "double": 17,
    }[display_type]


def _printable_text(text: str) -> str:
    return "".join(ch if (ch.isprintable() and ch not in "\r\n\t") else "." for ch in text)


def decode_text(raw: bytes, encoding: str) -> str:
    if encoding == "ASCII":
        return "".join(chr(b) if 32 <= b <= 126 else "." for b in raw)
    codec = {
        "UTF-8": "utf-8",
        "UTF-16 LE": "utf-16-le",
        "GBK": "gbk",
    }.get(encoding)
    if codec is None:
        raise ValueError(f"Unsupported text encoding: {encoding}")
    # Rows are intentionally decoded independently. A replacement character is
    # preferable to carrying decoder state across arbitrary memory-row jumps.
    return _printable_text(raw.decode(codec, errors="replace"))


@dataclass(frozen=True)
class ReadWindow:
    address: int
    size: int


def plan_read_window(
    first_row: int,
    visible_rows: int,
    *,
    bytes_per_row: int = BYTES_PER_ROW,
    margin_rows: int = 8,
    max_read_bytes: int = 2048,
) -> ReadWindow:
    if first_row < 0:
        raise ValueError("first_row must be >= 0")
    if visible_rows <= 0:
        visible_rows = 1
    if bytes_per_row <= 0:
        raise ValueError("bytes_per_row must be > 0")
    if margin_rows < 0:
        raise ValueError("margin_rows must be >= 0")
    if max_read_bytes < bytes_per_row:
        raise ValueError("max_read_bytes is too small")

    total_rows = ADDRESS_SPACE_SIZE // bytes_per_row
    first_row = min(first_row, total_rows - 1)
    start_row = max(0, first_row - margin_rows)
    end_row = min(total_rows, first_row + visible_rows + margin_rows)
    start = start_row * bytes_per_row
    size = max(bytes_per_row, (end_row - start_row) * bytes_per_row)
    size = min(size, max_read_bytes, ADDRESS_SPACE_SIZE - start)
    # All caller-visible windows stay row-aligned so rendering and cache updates
    # are deterministic.
    size -= size % bytes_per_row
    if size <= 0:
        size = min(bytes_per_row, ADDRESS_SPACE_SIZE - start)
    return ReadWindow(start, size)


@dataclass(frozen=True)
class ResolvedSymbol:
    name: str
    base_address: int
    size: int
    type_name: str | None
    kind: str
    source: str

    @property
    def end_address(self) -> int:
        return self.base_address + max(1, self.size)


class SymbolIndex:
    """Address-oriented index over existing ELF/DWARF symbol records.

    The parser can produce overlapping container/member/ELF records. Exact
    DWARF scalar/member records are preferred, while containing records are
    resolved to the smallest useful object. No J-Link access occurs here.
    """

    def __init__(self, symbols: Iterable[object] = ()) -> None:
        by_start: dict[int, list[ResolvedSymbol]] = {}
        for sym in symbols:
            try:
                address = int(getattr(sym, "address"))
                size = int(getattr(sym, "size", 0) or 0)
                name = str(getattr(sym, "name"))
            except Exception:
                continue
            if not name or not 0 <= address <= MAX_ADDRESS:
                continue
            item = ResolvedSymbol(
                name=name,
                base_address=address,
                size=max(1, size),
                type_name=getattr(sym, "type_name", None),
                kind=str(getattr(sym, "kind", "scalar")),
                source=str(getattr(sym, "source", "")),
            )
            by_start.setdefault(address, []).append(item)

        self._by_start = {addr: tuple(items) for addr, items in by_start.items()}
        self._starts = sorted(self._by_start)
        self._entries: list[ResolvedSymbol] = []
        self._entry_starts: list[int] = []
        for addr in self._starts:
            for item in self._by_start[addr]:
                self._entries.append(item)
                self._entry_starts.append(addr)

        self._prefix_max_end: list[int] = []
        max_end = -1
        for item in self._entries:
            max_end = max(max_end, item.end_address)
            self._prefix_max_end.append(max_end)

        # Name-oriented lookup is built once per AXF/ELF load. Memory Explorer
        # symbol search must stay entirely local while the user types: no J-Link
        # reads and no per-key model rebuilds. Preserve all records here, then
        # choose the best DWARF/ELF representation only when resolving a name.
        by_name: dict[str, list[ResolvedSymbol]] = {}
        for item in self._entries:
            by_name.setdefault(item.name.casefold(), []).append(item)
        self._by_name = {name: tuple(items) for name, items in by_name.items()}
        self._preferred_by_name: tuple[ResolvedSymbol, ...] = tuple(
            sorted(
                (self._pick_name(items) for items in self._by_name.values()),
                key=lambda item: item.name.casefold(),
            )
        )

    def __bool__(self) -> bool:
        return bool(self._entries)

    @staticmethod
    def _source_rank(source: str) -> int:
        low = source.lower()
        if "dwarf" in low:
            return 3
        if "elf" in low:
            return 1
        return 2

    @classmethod
    def _pick_exact(cls, items: Sequence[ResolvedSymbol]) -> ResolvedSymbol | None:
        if not items:
            return None
        return max(
            items,
            key=lambda s: (
                cls._source_rank(s.source),
                1 if s.kind == "scalar" else 0,
                s.name.count(".") + s.name.count("["),
                -s.size,
            ),
        )

    @classmethod
    def _pick_name(cls, items: Sequence[ResolvedSymbol]) -> ResolvedSymbol:
        # Prefer DWARF because it carries the exact member/array address and C
        # type. A container beats a guessed raw ELF scalar when both describe
        # the same symbolic path.
        return max(
            items,
            key=lambda s: (
                cls._source_rank(s.source),
                1 if s.source.lower().startswith("dwarf") else 0,
                1 if s.kind == "scalar" else 0,
                s.name.count(".") + s.name.count("["),
                -s.size,
            ),
        )

    def exact_name(self, name: str) -> ResolvedSymbol | None:
        """Resolve a complete AXF/DWARF path such as ``foo.bar[1]``.

        Matching is case-insensitive for convenience, while the returned record
        always preserves the exact symbol spelling from the debug information.
        """
        text = str(name).strip()
        if not text:
            return None
        items = self._by_name.get(text.casefold(), ())
        if not items:
            return None
        exact_case = [item for item in items if item.name == text]
        return self._pick_name(exact_case or items)

    def preferred_symbols(self) -> tuple[ResolvedSymbol, ...]:
        """One stable display/search record per symbolic path."""
        return self._preferred_by_name

    def search_names(self, query: str, *, limit: int = 50) -> list[ResolvedSymbol]:
        """Small pure-Python helper used for fallback/automated tests.

        The Qt UI uses a model-backed QCompleter so typing does not rebuild rows.
        This helper intentionally performs no target I/O.
        """
        needle = str(query).strip().casefold()
        if not needle or limit <= 0:
            return []
        result: list[ResolvedSymbol] = []
        for item in self._preferred_by_name:
            if needle in item.name.casefold():
                result.append(item)
                if len(result) >= limit:
                    break
        return result

    def exact(self, address: int) -> ResolvedSymbol | None:
        return self._pick_exact(self._by_start.get(int(address), ()))

    def resolve(self, address: int) -> ResolvedSymbol | None:
        address = int(address)
        exact = self.exact(address)
        if exact is not None:
            return exact
        if not self._entries:
            return None
        i = bisect_right(self._entry_starts, address) - 1
        candidates: list[ResolvedSymbol] = []
        while i >= 0:
            if self._prefix_max_end[i] <= address:
                break
            item = self._entries[i]
            if item.base_address <= address < item.end_address:
                candidates.append(item)
            i -= 1
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda s: (
                1 if s.kind == "scalar" else 0,
                self._source_rank(s.source),
                -s.size,
                s.name.count(".") + s.name.count("["),
            ),
        )

    def describe(self, address: int, *, show_offset: bool = True) -> str:
        item = self.resolve(address)
        if item is None:
            return ""
        offset = int(address) - item.base_address
        if offset and show_offset:
            return f"{item.name}+0x{offset:X}"
        if offset:
            return ""
        return item.name

    def starts_in_range(self, start: int, end: int, *, limit: int = 3) -> list[ResolvedSymbol]:
        if end <= start or not self._starts:
            return []
        lo = bisect_left(self._starts, int(start))
        hi = bisect_left(self._starts, int(end))
        result: list[ResolvedSymbol] = []
        for addr in self._starts[lo:hi]:
            item = self._pick_exact(self._by_start[addr])
            if item is not None:
                result.append(item)
                if len(result) >= limit:
                    break
        return result

    def scalar_starts_in_range(
        self, start: int, end: int, *, limit: int = 512
    ) -> list[ResolvedSymbol]:
        """Return typed scalar/member Symbols whose *start* address is in range.

        This is the local metadata source for the semantic Memory view. Containers
        are intentionally omitted because their scalar leaves (including array
        elements such as ``obj.bias[0]``..``[3]``) are the rows users can read/edit.
        Multiple parser records for the same symbolic path are collapsed with the
        same DWARF-first preference used by exact-name navigation. No target I/O
        occurs here.
        """
        if end <= start or not self._starts or limit <= 0:
            return []
        lo = bisect_left(self._starts, int(start))
        hi = bisect_left(self._starts, int(end))
        result: list[ResolvedSymbol] = []
        seen: set[tuple[str, int]] = set()
        for addr in self._starts[lo:hi]:
            typed_items = [
                item for item in self._by_start.get(addr, ())
                if item.kind == "scalar" and symbol_display_type(item.type_name) is not None
            ]
            # When DWARF knows real members at an address, do not also show an
            # ELF size-guessed object at the same address. This keeps semantic
            # rows focused on ``obj.member`` / ``array[i]`` rather than duplicate
            # fallback names. ELF scalars remain useful when DWARF is unavailable.
            if any(self._source_rank(item.source) >= 3 for item in typed_items):
                typed_items = [item for item in typed_items if self._source_rank(item.source) >= 3]
            by_name: dict[str, list[ResolvedSymbol]] = {}
            for item in typed_items:
                by_name.setdefault(item.name.casefold(), []).append(item)
            for items in by_name.values():
                item = self._pick_name(items)
                key = (item.name.casefold(), item.base_address)
                if key in seen:
                    continue
                seen.add(key)
                result.append(item)
                if len(result) >= limit:
                    return result
        return result


def plan_symbol_read_window(
    address: int,
    *,
    before_bytes: int = 512,
    after_bytes: int = 1536,
    alignment: int = BYTES_PER_ROW,
    max_read_bytes: int = 2048,
) -> ReadWindow:
    """Plan one bounded block read around a semantic Symbol navigation target.

    Symbol rows are decoded from this shared raw block; the view never issues one
    ReadMemEx per variable/member. The default 2 KiB neighborhood matches the
    existing Memory Explorer bounded-read ceiling while showing adjacent
    structure/array members without broad target scanning.
    """
    address = max(0, min(MAX_ADDRESS, int(address)))
    before_bytes = max(0, int(before_bytes))
    after_bytes = max(1, int(after_bytes))
    alignment = max(1, int(alignment))
    max_read_bytes = max(alignment, int(max_read_bytes))

    start = max(0, address - before_bytes)
    start -= start % alignment
    end = min(ADDRESS_SPACE_SIZE, address + after_bytes)
    if end <= start:
        end = min(ADDRESS_SPACE_SIZE, start + alignment)
    size = min(max_read_bytes, end - start)
    if size > alignment:
        size -= size % alignment
    if size <= 0:
        size = min(alignment, ADDRESS_SPACE_SIZE - start)
    return ReadWindow(start, size)
