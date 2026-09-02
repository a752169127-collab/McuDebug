from __future__ import annotations

"""Small DWARF 2/3 reader aimed at embedded AXF/ELF files.

This module intentionally covers the subset commonly emitted by ARM Compiler 5
(armcc) and many embedded GCC builds.  It exists so Keil AXF structure members
can be browsed without depending on pyelftools being installed.
"""

from dataclasses import dataclass, field
from pathlib import Path
import struct
from typing import Iterable


# DWARF tags used here.
DW_TAG_ARRAY_TYPE = 0x01
DW_TAG_CLASS_TYPE = 0x02
DW_TAG_ENUMERATION_TYPE = 0x04
DW_TAG_MEMBER = 0x0D
DW_TAG_POINTER_TYPE = 0x0F
DW_TAG_COMPILE_UNIT = 0x11
DW_TAG_STRUCTURE_TYPE = 0x13
DW_TAG_TYPEDEF = 0x16
DW_TAG_UNION_TYPE = 0x17
DW_TAG_BASE_TYPE = 0x24
DW_TAG_CONST_TYPE = 0x26
DW_TAG_VARIABLE = 0x34
DW_TAG_VOLATILE_TYPE = 0x35
DW_TAG_RESTRICT_TYPE = 0x37

# Attributes.
DW_AT_SIBLING = 0x01
DW_AT_LOCATION = 0x02
DW_AT_NAME = 0x03
DW_AT_BYTE_SIZE = 0x0B
DW_AT_BIT_SIZE = 0x0D
DW_AT_LOWER_BOUND = 0x22
DW_AT_UPPER_BOUND = 0x2F
DW_AT_ABSTRACT_ORIGIN = 0x31
DW_AT_COUNT = 0x37
DW_AT_DATA_MEMBER_LOCATION = 0x38
DW_AT_DECLARATION = 0x3C
DW_AT_ENCODING = 0x3E
DW_AT_EXTERNAL = 0x3F
DW_AT_SPECIFICATION = 0x47
DW_AT_TYPE = 0x49

# Forms.
DW_FORM_ADDR = 0x01
DW_FORM_BLOCK2 = 0x03
DW_FORM_BLOCK4 = 0x04
DW_FORM_DATA2 = 0x05
DW_FORM_DATA4 = 0x06
DW_FORM_DATA8 = 0x07
DW_FORM_STRING = 0x08
DW_FORM_BLOCK = 0x09
DW_FORM_BLOCK1 = 0x0A
DW_FORM_DATA1 = 0x0B
DW_FORM_FLAG = 0x0C
DW_FORM_SDATA = 0x0D
DW_FORM_STRP = 0x0E
DW_FORM_UDATA = 0x0F
DW_FORM_REF_ADDR = 0x10
DW_FORM_REF1 = 0x11
DW_FORM_REF2 = 0x12
DW_FORM_REF4 = 0x13
DW_FORM_REF8 = 0x14
DW_FORM_REF_UDATA = 0x15
DW_FORM_INDIRECT = 0x16
DW_FORM_SEC_OFFSET = 0x17
DW_FORM_EXPRLOC = 0x18
DW_FORM_FLAG_PRESENT = 0x19

# DWARF expression opcodes needed for static MCU data.
DW_OP_ADDR = 0x03
DW_OP_CONSTU = 0x10
DW_OP_CONSTS = 0x11
DW_OP_PLUS = 0x22
DW_OP_PLUS_UCONST = 0x23
DW_OP_LIT0 = 0x30
DW_OP_LIT31 = 0x4F

# Encodings.
DW_ATE_ADDRESS = 0x01
DW_ATE_BOOLEAN = 0x02
DW_ATE_FLOAT = 0x04
DW_ATE_SIGNED = 0x05
DW_ATE_SIGNED_CHAR = 0x06
DW_ATE_UNSIGNED = 0x07
DW_ATE_UNSIGNED_CHAR = 0x08


class DwarfLiteError(ValueError):
    pass


@dataclass
class _Abbrev:
    tag: int
    has_children: bool
    attrs: list[tuple[int, int]]


@dataclass
class _Die:
    offset: int
    tag: int
    attrs: dict[int, object]
    cu_offset: int
    addr_size: int
    children: list[int] = field(default_factory=list)
    parent: int | None = None


@dataclass(frozen=True)
class DwarfObject:
    name: str
    address: int
    size: int
    type_name: str | None
    kind: str
    scope: str = ""

    @property
    def addable(self) -> bool:
        return self.kind == "scalar" and self.type_name is not None


def _u16(data: bytes, off: int, endian: str) -> tuple[int, int]:
    return struct.unpack_from(endian + "H", data, off)[0], off + 2


def _u32(data: bytes, off: int, endian: str) -> tuple[int, int]:
    return struct.unpack_from(endian + "I", data, off)[0], off + 4


def _u64(data: bytes, off: int, endian: str) -> tuple[int, int]:
    return struct.unpack_from(endian + "Q", data, off)[0], off + 8


def _uleb(data: bytes, off: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while off < len(data):
        b = data[off]
        off += 1
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            return value, off
        shift += 7
        if shift > 70:
            break
    raise DwarfLiteError("Invalid ULEB128")


def _sleb(data: bytes, off: int) -> tuple[int, int]:
    value = 0
    shift = 0
    last = 0
    while off < len(data):
        b = data[off]
        off += 1
        last = b
        value |= (b & 0x7F) << shift
        shift += 7
        if not (b & 0x80):
            break
        if shift > 70:
            raise DwarfLiteError("Invalid SLEB128")
    else:
        raise DwarfLiteError("Invalid SLEB128")
    if shift < 64 and (last & 0x40):
        value |= -(1 << shift)
    return value, off


def _cstring(data: bytes, off: int) -> tuple[str, int]:
    end = data.find(b"\0", off)
    if end < 0:
        raise DwarfLiteError("Unterminated DWARF string")
    return data[off:end].decode("utf-8", errors="replace"), end + 1


def _elf_sections(path: str | Path) -> tuple[dict[str, bytes], str, int]:
    blob = Path(path).read_bytes()
    if len(blob) < 52 or blob[:4] != b"\x7fELF":
        raise DwarfLiteError("Not an ELF/AXF file")
    elf_class = blob[4]
    enc = blob[5]
    endian = "<" if enc == 1 else ">" if enc == 2 else None
    if endian is None or elf_class not in (1, 2):
        raise DwarfLiteError("Unsupported ELF format")

    if elf_class == 1:
        fmt = endian + "HHIIIIIHHHHHH"
        fields = struct.unpack_from(fmt, blob, 16)
        shoff, shentsize, shnum, shstrndx = fields[5], fields[10], fields[11], fields[12]
        shfmt = endian + "IIIIIIIIII"
    else:
        fmt = endian + "HHIQQQIHHHHHH"
        fields = struct.unpack_from(fmt, blob, 16)
        shoff, shentsize, shnum, shstrndx = fields[5], fields[10], fields[11], fields[12]
        shfmt = endian + "IIQQQQIIQQ"

    headers = []
    expected = struct.calcsize(shfmt)
    for i in range(shnum):
        f = struct.unpack_from(shfmt, blob, shoff + i * shentsize)
        headers.append({"name_off": f[0], "offset": f[4], "size": f[5]})
    shstr = headers[shstrndx]
    names = blob[shstr["offset"]: shstr["offset"] + shstr["size"]]
    result: dict[str, bytes] = {}
    for h in headers:
        noff = h["name_off"]
        end = names.find(b"\0", noff)
        name = names[noff:end].decode("ascii", errors="replace") if end >= 0 else ""
        result[name] = blob[h["offset"]: h["offset"] + h["size"]]
    return result, endian, elf_class


class _Reader:
    def __init__(self, path: str | Path) -> None:
        sections, endian, _elf_class = _elf_sections(path)
        self.info = sections.get(".debug_info", b"")
        self.abbrev = sections.get(".debug_abbrev", b"")
        self.debug_str = sections.get(".debug_str", b"")
        self.endian = endian
        if not self.info or not self.abbrev:
            raise DwarfLiteError("No .debug_info/.debug_abbrev")
        self._abbrev_cache: dict[int, dict[int, _Abbrev]] = {}
        self.dies: dict[int, _Die] = {}

    def _abbrev_table(self, base: int) -> dict[int, _Abbrev]:
        cached = self._abbrev_cache.get(base)
        if cached is not None:
            return cached
        off = base
        table: dict[int, _Abbrev] = {}
        while off < len(self.abbrev):
            code, off = _uleb(self.abbrev, off)
            if code == 0:
                break
            tag, off = _uleb(self.abbrev, off)
            if off >= len(self.abbrev):
                raise DwarfLiteError("Truncated abbrev table")
            has_children = self.abbrev[off] != 0
            off += 1
            attrs: list[tuple[int, int]] = []
            while True:
                attr, off = _uleb(self.abbrev, off)
                form, off = _uleb(self.abbrev, off)
                if attr == 0 and form == 0:
                    break
                attrs.append((attr, form))
            table[code] = _Abbrev(tag, has_children, attrs)
        self._abbrev_cache[base] = table
        return table

    def _form(self, form: int, off: int, cu_offset: int, version: int, addr_size: int) -> tuple[object, int]:
        d = self.info
        if form == DW_FORM_INDIRECT:
            actual, off = _uleb(d, off)
            return self._form(actual, off, cu_offset, version, addr_size)
        if form == DW_FORM_ADDR:
            if addr_size == 4:
                return _u32(d, off, self.endian)
            if addr_size == 8:
                return _u64(d, off, self.endian)
            raise DwarfLiteError(f"Unsupported address size {addr_size}")
        if form == DW_FORM_DATA1:
            return d[off], off + 1
        if form == DW_FORM_DATA2:
            return _u16(d, off, self.endian)
        if form in (DW_FORM_DATA4, DW_FORM_SEC_OFFSET):
            return _u32(d, off, self.endian)
        if form == DW_FORM_DATA8:
            return _u64(d, off, self.endian)
        if form == DW_FORM_STRING:
            return _cstring(d, off)
        if form == DW_FORM_STRP:
            str_off, off = _u32(d, off, self.endian)
            if not self.debug_str:
                return "", off
            s, _ = _cstring(self.debug_str, str_off)
            return s, off
        if form == DW_FORM_FLAG:
            return bool(d[off]), off + 1
        if form == DW_FORM_FLAG_PRESENT:
            return True, off
        if form == DW_FORM_UDATA:
            return _uleb(d, off)
        if form == DW_FORM_SDATA:
            return _sleb(d, off)
        if form == DW_FORM_REF1:
            return cu_offset + d[off], off + 1
        if form == DW_FORM_REF2:
            v, off = _u16(d, off, self.endian)
            return cu_offset + v, off
        if form == DW_FORM_REF4:
            v, off = _u32(d, off, self.endian)
            return cu_offset + v, off
        if form == DW_FORM_REF8:
            v, off = _u64(d, off, self.endian)
            return cu_offset + v, off
        if form == DW_FORM_REF_UDATA:
            v, off = _uleb(d, off)
            return cu_offset + v, off
        if form == DW_FORM_REF_ADDR:
            # DWARF2 uses address-size; DWARF3+ uses offset-size.  Embedded AXF
            # files here use 32-bit offsets in both cases.
            if version == 2 and addr_size == 8:
                return _u64(d, off, self.endian)
            return _u32(d, off, self.endian)
        if form in (DW_FORM_BLOCK, DW_FORM_EXPRLOC):
            n, off = _uleb(d, off)
            return d[off:off + n], off + n
        if form == DW_FORM_BLOCK1:
            n = d[off]
            off += 1
            return d[off:off + n], off + n
        if form == DW_FORM_BLOCK2:
            n, off = _u16(d, off, self.endian)
            return d[off:off + n], off + n
        if form == DW_FORM_BLOCK4:
            n, off = _u32(d, off, self.endian)
            return d[off:off + n], off + n
        raise DwarfLiteError(f"Unsupported DWARF form 0x{form:X} at 0x{off:X}")

    def parse(self) -> dict[int, _Die]:
        off = 0
        d = self.info
        while off + 11 <= len(d):
            cu_offset = off
            unit_length, p = _u32(d, off, self.endian)
            if unit_length == 0:
                off += 4
                continue
            if unit_length == 0xFFFFFFFF:
                raise DwarfLiteError("DWARF64 is not supported by dwarf_lite")
            end = cu_offset + 4 + unit_length
            if end > len(d):
                raise DwarfLiteError("Truncated compilation unit")
            version, p = _u16(d, p, self.endian)
            abbrev_offset, p = _u32(d, p, self.endian)
            addr_size = d[p]
            p += 1
            table = self._abbrev_table(abbrev_offset)
            stack: list[int] = []
            while p < end:
                die_off = p
                code, p = _uleb(d, p)
                if code == 0:
                    if stack:
                        stack.pop()
                    continue
                ab = table.get(code)
                if ab is None:
                    raise DwarfLiteError(f"Unknown abbrev {code} at .debug_info+0x{die_off:X}")
                attrs: dict[int, object] = {}
                for attr_name, form in ab.attrs:
                    value, p = self._form(form, p, cu_offset, version, addr_size)
                    attrs[attr_name] = value
                parent = stack[-1] if stack else None
                die = _Die(die_off, ab.tag, attrs, cu_offset, addr_size, parent=parent)
                self.dies[die_off] = die
                if parent is not None and parent in self.dies:
                    self.dies[parent].children.append(die_off)
                if ab.has_children:
                    stack.append(die_off)
            off = end
        return self.dies


def _resolve_attr(dies: dict[int, _Die], die: _Die, attr: int, seen: set[int] | None = None):
    if attr in die.attrs:
        return die.attrs[attr]
    seen = seen or set()
    if die.offset in seen:
        return None
    seen.add(die.offset)
    for ref_attr in (DW_AT_SPECIFICATION, DW_AT_ABSTRACT_ORIGIN):
        ref = die.attrs.get(ref_attr)
        if isinstance(ref, int) and ref in dies:
            value = _resolve_attr(dies, dies[ref], attr, seen)
            if value is not None:
                return value
    return None


def _type_die(dies: dict[int, _Die], die: _Die) -> _Die | None:
    ref = _resolve_attr(dies, die, DW_AT_TYPE)
    return dies.get(ref) if isinstance(ref, int) else None


def _unwrap(dies: dict[int, _Die], die: _Die | None) -> _Die | None:
    wrappers = {DW_TAG_TYPEDEF, DW_TAG_CONST_TYPE, DW_TAG_VOLATILE_TYPE, DW_TAG_RESTRICT_TYPE}
    seen: set[int] = set()
    while die is not None and die.tag in wrappers and die.offset not in seen:
        seen.add(die.offset)
        die = _type_die(dies, die)
    return die


def _name(dies: dict[int, _Die], die: _Die) -> str:
    v = _resolve_attr(dies, die, DW_AT_NAME)
    return str(v) if v is not None else ""


def _int_attr(dies: dict[int, _Die], die: _Die, attr: int, default: int = 0) -> int:
    v = _resolve_attr(dies, die, attr)
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _decode_uleb_from_expr(expr: bytes, off: int = 0) -> tuple[int, int]:
    return _uleb(expr, off)


def _decode_sleb_from_expr(expr: bytes, off: int = 0) -> tuple[int, int]:
    return _sleb(expr, off)


def eval_static_address(expr: bytes, addr_size: int = 4, endian: str = "<") -> int | None:
    if not expr or expr[0] != DW_OP_ADDR:
        return None
    if addr_size == 4 and len(expr) >= 5:
        return struct.unpack_from(endian + "I", expr, 1)[0]
    if addr_size == 8 and len(expr) >= 9:
        return struct.unpack_from(endian + "Q", expr, 1)[0]
    return None


def eval_member_offset(expr: bytes) -> int | None:
    """Evaluate the constant member-location expressions emitted by armcc/GCC."""
    if not expr:
        return 0
    op = expr[0]
    if op == DW_OP_PLUS_UCONST:
        value, _ = _decode_uleb_from_expr(expr, 1)
        return value
    if op == DW_OP_CONSTU:
        value, p = _decode_uleb_from_expr(expr, 1)
        # A following DW_OP_plus is a common equivalent representation.
        if p == len(expr) or (p + 1 == len(expr) and expr[p] == DW_OP_PLUS):
            return value
    if op == DW_OP_CONSTS:
        value, p = _decode_sleb_from_expr(expr, 1)
        if p == len(expr) or (p + 1 == len(expr) and expr[p] == DW_OP_PLUS):
            return value
    if DW_OP_LIT0 <= op <= DW_OP_LIT31 and len(expr) == 1:
        return op - DW_OP_LIT0
    return None


def _scalar(dies: dict[int, _Die], die: _Die | None) -> tuple[str | None, int]:
    die = _unwrap(dies, die)
    if die is None:
        return None, 0
    size = _int_attr(dies, die, DW_AT_BYTE_SIZE, 0)
    if die.tag == DW_TAG_BASE_TYPE:
        enc = _int_attr(dies, die, DW_AT_ENCODING, 0)
        if enc == DW_ATE_FLOAT:
            return {4: "float", 8: "double"}.get(size), size
        if enc in (DW_ATE_SIGNED, DW_ATE_SIGNED_CHAR):
            return {1: "int8", 2: "int16", 4: "int32", 8: "int64"}.get(size), size
        if enc in (DW_ATE_ADDRESS, DW_ATE_BOOLEAN, DW_ATE_UNSIGNED, DW_ATE_UNSIGNED_CHAR):
            return {1: "uint8", 2: "uint16", 4: "uint32", 8: "uint64"}.get(size), size
    if die.tag == DW_TAG_ENUMERATION_TYPE:
        return {1: "int8", 2: "int16", 4: "int32", 8: "int64"}.get(size), size
    if die.tag == DW_TAG_POINTER_TYPE:
        if size <= 0:
            size = die.addr_size
        return {1: "uint8", 2: "uint16", 4: "uint32", 8: "uint64"}.get(size), size
    return None, size


def _display_container_type(dies: dict[int, _Die], die: _Die) -> str:
    n = _name(dies, die)
    if die.tag == DW_TAG_STRUCTURE_TYPE:
        return f"struct {n}" if n else "struct"
    if die.tag == DW_TAG_UNION_TYPE:
        return f"union {n}" if n else "union"
    if die.tag == DW_TAG_CLASS_TYPE:
        return f"class {n}" if n else "class"
    if die.tag == DW_TAG_ARRAY_TYPE:
        return "array"
    return n


def _array_count(dies: dict[int, _Die], die: _Die) -> int | None:
    total = 1
    found = False
    for child_off in die.children:
        child = dies[child_off]
        # DW_TAG_subrange_type == 0x21
        if child.tag != 0x21:
            continue
        found = True
        cnt = _resolve_attr(dies, child, DW_AT_COUNT)
        if cnt is None:
            upper = _resolve_attr(dies, child, DW_AT_UPPER_BOUND)
            lower = _resolve_attr(dies, child, DW_AT_LOWER_BOUND)
            if upper is None:
                return None
            cnt = int(upper) - int(lower or 0) + 1
        cnt = int(cnt)
        if cnt < 0:
            return None
        total *= cnt
    return total if found else None


def _type_size(dies: dict[int, _Die], die: _Die | None) -> int:
    die = _unwrap(dies, die)
    if die is None:
        return 0
    scalar_type, scalar_size = _scalar(dies, die)
    if scalar_type is not None:
        return scalar_size
    size = _int_attr(dies, die, DW_AT_BYTE_SIZE, 0)
    if size > 0:
        return size
    if die.tag == DW_TAG_ARRAY_TYPE:
        elem = _type_die(dies, die)
        count = _array_count(dies, die)
        return _type_size(dies, elem) * count if count else 0
    return 0


def _flatten(
    dies: dict[int, _Die],
    name: str,
    address: int,
    type_die: _Die | None,
    scope: str,
    *,
    max_array_elements: int = 256,
    depth: int = 0,
) -> list[DwarfObject]:
    if depth > 16:
        return []
    die = _unwrap(dies, type_die)
    if die is None:
        return []

    scalar_type, scalar_size = _scalar(dies, die)
    if scalar_type is not None:
        return [DwarfObject(name, address, scalar_size, scalar_type, "scalar", scope)]

    if die.tag in (DW_TAG_STRUCTURE_TYPE, DW_TAG_CLASS_TYPE, DW_TAG_UNION_TYPE):
        size = _int_attr(dies, die, DW_AT_BYTE_SIZE, 0)
        out = [DwarfObject(name, address, size, _display_container_type(dies, die), "container", scope)]
        anon = 0
        for child_off in die.children:
            member = dies[child_off]
            if member.tag != DW_TAG_MEMBER or DW_AT_BIT_SIZE in member.attrs:
                continue
            member_type = _type_die(dies, member)
            if member_type is None:
                continue
            mname = _name(dies, member)
            if not mname:
                anon += 1
                mname = f"<anon{anon}>"
            if die.tag == DW_TAG_UNION_TYPE:
                offset = 0
            else:
                loc = _resolve_attr(dies, member, DW_AT_DATA_MEMBER_LOCATION)
                if loc is None:
                    offset = 0
                elif isinstance(loc, int):
                    offset = loc
                elif isinstance(loc, (bytes, bytearray)):
                    offset = eval_member_offset(bytes(loc))
                else:
                    offset = None
                if offset is None:
                    continue
            out.extend(_flatten(
                dies, f"{name}.{mname}", address + int(offset), member_type, scope,
                max_array_elements=max_array_elements, depth=depth + 1,
            ))
        return out

    if die.tag == DW_TAG_ARRAY_TYPE:
        elem_type = _type_die(dies, die)
        count = _array_count(dies, die)
        size = _type_size(dies, die)
        out = [DwarfObject(name, address, size, "array", "container", scope)]
        if elem_type is None or count is None or count <= 0 or count > max_array_elements:
            return out
        elem_size = _type_size(dies, elem_type)
        if elem_size <= 0:
            return out
        for i in range(count):
            out.extend(_flatten(
                dies, f"{name}[{i}]", address + i * elem_size, elem_type, scope,
                max_array_elements=max_array_elements, depth=depth + 1,
            ))
        return out

    return []


def parse_dwarf_objects(path: str | Path, raw_symbols: Iterable[object]) -> list[DwarfObject]:
    """Return global/static variables and recursively expanded scalar members.

    ``raw_symbols`` only needs ``name`` and ``address`` attributes. It supplies
    stable addresses for declaration DIEs that do not carry DW_AT_location.
    """
    reader = _Reader(path)
    dies = reader.parse()
    raw_by_name: dict[str, list[object]] = {}
    for sym in raw_symbols:
        raw_by_name.setdefault(str(sym.name), []).append(sym)

    out: list[DwarfObject] = []
    for die in dies.values():
        if die.tag != DW_TAG_VARIABLE:
            continue
        name = _name(dies, die)
        if not name:
            continue
        tdie = _type_die(dies, die)
        if tdie is None:
            continue

        addr: int | None = None
        loc = _resolve_attr(dies, die, DW_AT_LOCATION)
        if isinstance(loc, (bytes, bytearray)):
            addr = eval_static_address(bytes(loc), die.addr_size, reader.endian)
        # Location-list offsets (DW_FORM_data4) are for locals; do not treat them
        # as target addresses. Global declarations can still use the ELF symbol.
        if addr is None:
            candidates = raw_by_name.get(name, [])
            if len(candidates) == 1:
                addr = int(candidates[0].address)
        if addr is None:
            continue

        external = bool(_resolve_attr(dies, die, DW_AT_EXTERNAL) or False)
        scope = "Global" if external else "Static/Local"
        out.extend(_flatten(dies, name, addr, tdie, scope))

    unique: dict[tuple[str, int], DwarfObject] = {}
    for obj in out:
        key = (obj.name, obj.address)
        old = unique.get(key)
        # Prefer scalar leaves over a less-specific container record if a compiler
        # emitted overlapping descriptions.
        if old is None or (old.kind != "scalar" and obj.kind == "scalar"):
            unique[key] = obj
    return sorted(unique.values(), key=lambda s: (s.name.lower(), s.address))
