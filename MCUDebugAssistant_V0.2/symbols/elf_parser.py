from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Iterable


@dataclass(frozen=True)
class ElfSymbol:
    name: str
    address: int
    size: int
    type_name: str | None
    scope: str = ""
    section: str = ""
    writable: bool = False
    source: str = "ELF symbol"
    kind: str = "scalar"

    @property
    def addable(self) -> bool:
        return self.kind == "scalar" and self.type_name is not None and 0 <= self.address <= 0xFFFFFFFF


@dataclass(frozen=True)
class ElfParseResult:
    path: str
    symbols: tuple[ElfSymbol, ...]
    has_dwarf: bool
    used_dwarf: bool
    warning: str = ""


class ElfFormatError(ValueError):
    pass


# ELF constants used by the lightweight fallback parser.
_SHT_SYMTAB = 2
_SHT_DYNSYM = 11
_STT_OBJECT = 1
_SHF_WRITE = 0x1
_SHN_UNDEF = 0
_SHN_LORESERVE = 0xFF00


def _guess_scalar_type(size: int) -> str | None:
    return {
        1: "uint8",
        2: "uint16",
        4: "uint32",
        8: "uint64",
    }.get(int(size))


def _decode_c_string(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    end = data.find(b"\0", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("utf-8", errors="replace")


def _read_exact(blob: bytes, offset: int, size: int) -> bytes:
    end = offset + size
    if offset < 0 or size < 0 or end > len(blob):
        raise ElfFormatError("ELF/AXF file is truncated or contains invalid offsets")
    return blob[offset:end]


def _parse_symbol_table_fallback(path: str | Path) -> tuple[list[ElfSymbol], bool]:
    """Parse STT_OBJECT symbols without external dependencies.

    Keil AXF files are ELF containers, so this gives us a reliable baseline even
    when pyelftools/DWARF is not available. Exact C types cannot be recovered
    from a normal ELF symbol table; 1/2/4/8-byte objects therefore get a safe
    integer-width guess that the user can change in Watch.
    """

    blob = Path(path).read_bytes()
    if len(blob) < 16 or blob[:4] != b"\x7fELF":
        raise ElfFormatError("Selected file is not an ELF/AXF file")

    elf_class = blob[4]
    data_encoding = blob[5]
    if elf_class not in (1, 2):
        raise ElfFormatError(f"Unsupported ELF class: {elf_class}")
    if data_encoding == 1:
        endian = "<"
    elif data_encoding == 2:
        endian = ">"
    else:
        raise ElfFormatError(f"Unsupported ELF data encoding: {data_encoding}")

    if elf_class == 1:
        ehdr_fmt = endian + "HHIIIIIHHHHHH"
        shdr_fmt = endian + "IIIIIIIIII"
        sym_fmt = endian + "IIIBBH"
    else:
        ehdr_fmt = endian + "HHIQQQIHHHHHH"
        shdr_fmt = endian + "IIQQQQIIQQ"
        sym_fmt = endian + "IBBHQQ"

    ehdr_size = struct.calcsize(ehdr_fmt)
    fields = struct.unpack(ehdr_fmt, _read_exact(blob, 16, ehdr_size))
    # Common field positions for 32/64-bit ELF headers.
    e_shoff = fields[5]
    e_shentsize = fields[10]
    e_shnum = fields[11]
    e_shstrndx = fields[12]
    expected_sh_size = struct.calcsize(shdr_fmt)
    if e_shentsize < expected_sh_size:
        raise ElfFormatError("Invalid ELF section header size")
    if e_shnum == 0:
        raise ElfFormatError("ELF extended section counts are not supported in this version")

    sections: list[dict] = []
    for i in range(e_shnum):
        raw = _read_exact(blob, e_shoff + i * e_shentsize, expected_sh_size)
        f = struct.unpack(shdr_fmt, raw)
        if elf_class == 1:
            sh = {
                "name_off": f[0], "type": f[1], "flags": f[2], "addr": f[3],
                "offset": f[4], "size": f[5], "link": f[6], "info": f[7],
                "align": f[8], "entsize": f[9],
            }
        else:
            sh = {
                "name_off": f[0], "type": f[1], "flags": f[2], "addr": f[3],
                "offset": f[4], "size": f[5], "link": f[6], "info": f[7],
                "align": f[8], "entsize": f[9],
            }
        sections.append(sh)

    if not 0 <= e_shstrndx < len(sections):
        raise ElfFormatError("Invalid section-name string table index")
    shstr = sections[e_shstrndx]
    shstr_data = _read_exact(blob, shstr["offset"], shstr["size"])
    for sh in sections:
        sh["name"] = _decode_c_string(shstr_data, sh["name_off"])

    has_dwarf = any(str(sh.get("name", "")).startswith(".debug_") for sh in sections)
    result: list[ElfSymbol] = []
    seen: set[tuple[str, int]] = set()
    sym_expected = struct.calcsize(sym_fmt)

    for symtab in sections:
        if symtab["type"] not in (_SHT_SYMTAB, _SHT_DYNSYM):
            continue
        link = symtab["link"]
        if not 0 <= link < len(sections):
            continue
        strtab = sections[link]
        strings = _read_exact(blob, strtab["offset"], strtab["size"])
        entsize = symtab["entsize"] or sym_expected
        if entsize < sym_expected:
            continue
        count = symtab["size"] // entsize

        for i in range(count):
            raw = _read_exact(blob, symtab["offset"] + i * entsize, sym_expected)
            f = struct.unpack(sym_fmt, raw)
            if elf_class == 1:
                st_name, st_value, st_size, st_info, _st_other, st_shndx = f
            else:
                st_name, st_info, _st_other, st_shndx, st_value, st_size = f
            st_type = st_info & 0x0F
            st_bind = st_info >> 4
            if st_type != _STT_OBJECT or st_size <= 0 or st_value == 0:
                continue
            if st_shndx == _SHN_UNDEF or st_shndx >= _SHN_LORESERVE:
                continue
            name = _decode_c_string(strings, st_name).strip()
            if not name or name.startswith("$"):
                continue
            if not 0 <= st_shndx < len(sections):
                section_name = ""
                writable = False
            else:
                owner = sections[st_shndx]
                section_name = str(owner.get("name", ""))
                writable = bool(owner.get("flags", 0) & _SHF_WRITE)
            scope = {0: "Local", 1: "Global", 2: "Weak"}.get(st_bind, f"Bind{st_bind}")
            key = (name, int(st_value))
            if key in seen:
                continue
            seen.add(key)
            result.append(
                ElfSymbol(
                    name=name,
                    address=int(st_value),
                    size=int(st_size),
                    type_name=_guess_scalar_type(int(st_size)),
                    scope=scope,
                    section=section_name,
                    writable=writable,
                    source="ELF symbol",
                    kind="scalar" if _guess_scalar_type(int(st_size)) is not None else "object",
                )
            )

    result.sort(key=lambda s: (s.name.lower(), s.address))
    return result, has_dwarf


def _dwarf_name(die) -> str:
    attr = die.attributes.get("DW_AT_name")
    if attr is None:
        return ""
    value = attr.value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _dwarf_int_attr(die, name: str, default: int | None = None) -> int | None:
    attr = die.attributes.get(name)
    if attr is None:
        return default
    try:
        return int(attr.value)
    except Exception:
        return default


def _dwarf_type_die(die):
    if "DW_AT_type" not in die.attributes:
        return None
    try:
        return die.get_DIE_from_attribute("DW_AT_type")
    except Exception:
        return None


def _unwrap_dwarf_type(die):
    wrappers = {
        "DW_TAG_typedef",
        "DW_TAG_const_type",
        "DW_TAG_volatile_type",
        "DW_TAG_restrict_type",
        "DW_TAG_atomic_type",
    }
    seen = set()
    while die is not None and die.tag in wrappers and die.offset not in seen:
        seen.add(die.offset)
        die = _dwarf_type_die(die)
    return die


def _dwarf_scalar_type(die) -> tuple[str | None, int]:
    die = _unwrap_dwarf_type(die)
    if die is None:
        return None, 0
    size = _dwarf_int_attr(die, "DW_AT_byte_size", 0) or 0

    if die.tag == "DW_TAG_base_type":
        enc = _dwarf_int_attr(die, "DW_AT_encoding", 0) or 0
        # DWARF encodings: address=1, boolean=2, float=4, signed=5,
        # signed_char=6, unsigned=7, unsigned_char=8.
        if enc == 4:
            return ({4: "float", 8: "double"}.get(size), size)
        if enc in (5, 6):
            return ({1: "int8", 2: "int16", 4: "int32", 8: "int64"}.get(size), size)
        if enc in (1, 2, 7, 8):
            return ({1: "uint8", 2: "uint16", 4: "uint32", 8: "uint64"}.get(size), size)
        return _guess_scalar_type(size), size

    if die.tag == "DW_TAG_enumeration_type":
        # Most Cortex-M enums are signed int unless the compiler says otherwise.
        return ({1: "int8", 2: "int16", 4: "int32", 8: "int64"}.get(size), size)

    if die.tag == "DW_TAG_pointer_type":
        return ({1: "uint8", 2: "uint16", 4: "uint32", 8: "uint64"}.get(size), size)

    return None, size


def _attr_expr_bytes(attr) -> bytes | None:
    """Return expression bytes for DW_FORM_exprloc *or legacy DW_FORM_block*.

    ARM Compiler 5 / DWARF3 commonly emits locations and structure-member
    offsets as DW_FORM_block. pyelftools correctly exposes the bytes, but the
    previous implementation rejected the form before parsing it.
    """
    try:
        from elftools.dwarf.descriptions import describe_form_class

        form_class = describe_form_class(attr.form)
        if form_class not in ("exprloc", "block") and not str(attr.form).startswith("DW_FORM_block"):
            return None
        value = attr.value
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, (list, tuple)):
            return bytes(value)
    except Exception:
        return None
    return None


def _dwarf_location_addr(die, dwarfinfo) -> int | None:
    attr = die.attributes.get("DW_AT_location")
    if attr is None:
        return None
    expr = _attr_expr_bytes(attr)
    if expr is None:
        return None
    try:
        from elftools.dwarf.dwarf_expr import DWARFExprParser

        ops = DWARFExprParser(dwarfinfo.structs).parse_expr(expr)
        if len(ops) == 1 and ops[0].op_name == "DW_OP_addr" and ops[0].args:
            return int(ops[0].args[0])
    except Exception:
        return None
    return None


def _dwarf_member_offset(member, dwarfinfo) -> int | None:
    attr = member.attributes.get("DW_AT_data_member_location")
    if attr is None:
        return 0
    try:
        from elftools.dwarf.descriptions import describe_form_class
        from elftools.dwarf.dwarf_expr import DWARFExprParser

        form_class = describe_form_class(attr.form)
        if form_class == "constant":
            return int(attr.value)
        expr = _attr_expr_bytes(attr)
        if expr is not None:
            ops = DWARFExprParser(dwarfinfo.structs).parse_expr(expr)
            if len(ops) == 1 and ops[0].op_name in ("DW_OP_plus_uconst", "DW_OP_constu", "DW_OP_consts"):
                return int(ops[0].args[0])
            if len(ops) == 1 and ops[0].op_name.startswith("DW_OP_lit"):
                return int(ops[0].op_name.removeprefix("DW_OP_lit"))
            if len(ops) == 2 and ops[-1].op_name == "DW_OP_plus" and ops[0].args:
                return int(ops[0].args[0])
    except Exception:
        return None
    return None

def _dwarf_array_count(array_die) -> int | None:
    total = 1
    found = False
    for child in array_die.iter_children():
        if child.tag != "DW_TAG_subrange_type":
            continue
        found = True
        count = _dwarf_int_attr(child, "DW_AT_count", None)
        if count is None:
            upper = _dwarf_int_attr(child, "DW_AT_upper_bound", None)
            lower = _dwarf_int_attr(child, "DW_AT_lower_bound", 0) or 0
            if upper is None:
                return None
            count = upper - lower + 1
        if count < 0:
            return None
        total *= count
    return total if found else None


def _flatten_dwarf_type(
    name: str,
    address: int,
    type_die,
    dwarfinfo,
    scope: str,
    max_array_elements: int = 256,
    depth: int = 0,
) -> list[ElfSymbol]:
    if depth > 12:
        return []
    die = _unwrap_dwarf_type(type_die)
    if die is None:
        return []

    scalar_type, scalar_size = _dwarf_scalar_type(die)
    if scalar_type is not None:
        return [
            ElfSymbol(
                name=name,
                address=address,
                size=scalar_size,
                type_name=scalar_type,
                scope=scope,
                section="",
                writable=True,
                source="DWARF",
                kind="scalar",
            )
        ]

    if die.tag in ("DW_TAG_structure_type", "DW_TAG_class_type", "DW_TAG_union_type"):
        tag_prefix = {
            "DW_TAG_structure_type": "struct",
            "DW_TAG_class_type": "class",
            "DW_TAG_union_type": "union",
        }[die.tag]
        container_name = _dwarf_name(die)
        container_size = _dwarf_int_attr(die, "DW_AT_byte_size", 0) or 0
        output: list[ElfSymbol] = [
            ElfSymbol(
                name=name, address=address, size=container_size,
                type_name=f"{tag_prefix} {container_name}" if container_name else tag_prefix,
                scope=scope, section="", writable=True, source="DWARF", kind="container",
            )
        ]
        anon_index = 0
        for member in die.iter_children():
            if member.tag != "DW_TAG_member":
                continue
            # Bitfields cannot be represented by a normal byte-address/type Watch entry.
            if "DW_AT_bit_size" in member.attributes:
                continue
            offset = 0 if die.tag == "DW_TAG_union_type" else _dwarf_member_offset(member, dwarfinfo)
            if offset is None:
                continue
            member_type = _dwarf_type_die(member)
            if member_type is None:
                continue
            member_name = _dwarf_name(member)
            if not member_name:
                anon_index += 1
                member_name = f"<anon{anon_index}>"
            output.extend(
                _flatten_dwarf_type(
                    f"{name}.{member_name}",
                    address + offset,
                    member_type,
                    dwarfinfo,
                    scope,
                    max_array_elements=max_array_elements,
                    depth=depth + 1,
                )
            )
        return output

    if die.tag == "DW_TAG_array_type":
        element_type = _dwarf_type_die(die)
        if element_type is None:
            return []
        count = _dwarf_array_count(die)
        array_size = _dwarf_int_attr(die, "DW_AT_byte_size", 0) or 0
        output: list[ElfSymbol] = [
            ElfSymbol(
                name=name, address=address, size=array_size, type_name="array",
                scope=scope, section="", writable=True, source="DWARF", kind="container",
            )
        ]
        if count is None or count <= 0 or count > max_array_elements:
            return output
        elem_die = _unwrap_dwarf_type(element_type)
        _, elem_size = _dwarf_scalar_type(elem_die)
        if elem_size <= 0:
            elem_size = _dwarf_int_attr(elem_die, "DW_AT_byte_size", 0) or 0
        if elem_size <= 0:
            return []
        for i in range(count):
            output.extend(
                _flatten_dwarf_type(
                    f"{name}[{i}]",
                    address + i * elem_size,
                    element_type,
                    dwarfinfo,
                    scope,
                    max_array_elements=max_array_elements,
                    depth=depth + 1,
                )
            )
        return output

    return []


def _parse_dwarf_symbols(path: str | Path, raw_symbols: Iterable[ElfSymbol]) -> list[ElfSymbol]:
    """Use pyelftools, when installed, to recover exact C scalar types and members."""
    from elftools.elf.elffile import ELFFile

    raw_by_name: dict[str, list[ElfSymbol]] = {}
    for sym in raw_symbols:
        raw_by_name.setdefault(sym.name, []).append(sym)

    output: list[ElfSymbol] = []
    with open(path, "rb") as fp:
        elf = ELFFile(fp)
        if not elf.has_dwarf_info():
            return []
        dwarfinfo = elf.get_dwarf_info()

        for cu in dwarfinfo.iter_CUs():
            for die in cu.iter_DIEs():
                if die.tag != "DW_TAG_variable":
                    continue
                name = _dwarf_name(die)
                if not name:
                    continue
                type_die = _dwarf_type_die(die)
                if type_die is None:
                    continue
                addr = _dwarf_location_addr(die, dwarfinfo)
                if addr is None:
                    # For some compiler/debug-info combinations, the variable DIE
                    # omits a simple absolute DW_OP_addr but the ELF symbol table
                    # still provides a stable address.
                    candidates = raw_by_name.get(name, [])
                    if len(candidates) == 1:
                        addr = candidates[0].address
                    else:
                        continue
                external_attr = die.attributes.get("DW_AT_external")
                scope = "Global" if external_attr is not None and bool(external_attr.value) else "Static/Local"
                output.extend(
                    _flatten_dwarf_type(name, addr, type_die, dwarfinfo, scope)
                )

    # De-duplicate leaf members that can appear in overlapping debug/symbol records.
    unique: dict[tuple[str, int], ElfSymbol] = {}
    for sym in output:
        unique[(sym.name, sym.address)] = sym
    return sorted(unique.values(), key=lambda s: (s.name.lower(), s.address))


def parse_elf_symbols(path: str | Path) -> ElfParseResult:
    path = str(Path(path).expanduser().resolve())
    raw_symbols, has_dwarf = _parse_symbol_table_fallback(path)
    warning_parts: list[str] = []
    used_dwarf = False
    symbols = raw_symbols
    dwarf_symbols: list[ElfSymbol] = []

    if has_dwarf:
        # Prefer the built-in embedded DWARF reader. It explicitly supports the
        # ARMCC5 DWARF3 DW_FORM_block expressions used by Keil AXF files and
        # therefore works even when pyelftools is not installed.
        try:
            from .dwarf_lite import parse_dwarf_objects

            objs = parse_dwarf_objects(path, raw_symbols)
            dwarf_symbols = [
                ElfSymbol(
                    name=o.name, address=o.address, size=o.size, type_name=o.type_name,
                    scope=o.scope, section="", writable=True, source="DWARF-lite", kind=o.kind,
                )
                for o in objs
            ]
            if dwarf_symbols:
                used_dwarf = True
        except Exception as exc:
            warning_parts.append(f"Built-in DWARF parse failed: {exc}")

        # If the lightweight reader could not handle a newer compiler/DWARF
        # dialect, use pyelftools when available as the general fallback.
        if not dwarf_symbols:
            try:
                dwarf_symbols = _parse_dwarf_symbols(path, raw_symbols)
                if dwarf_symbols:
                    used_dwarf = True
            except ModuleNotFoundError:
                warning_parts.append("pyelftools is not installed")
            except Exception as exc:
                warning_parts.append(f"pyelftools DWARF parse failed: {exc}")

        if dwarf_symbols:
            merged: dict[tuple[str, int], ElfSymbol] = {
                (s.name, s.address): s for s in dwarf_symbols
            }
            for sym in raw_symbols:
                merged.setdefault((sym.name, sym.address), sym)
            symbols = sorted(merged.values(), key=lambda s: (s.name.lower(), s.address, s.kind))
        elif warning_parts:
            warning_parts.append("using ELF symbol-table fallback only; structure/member expansion is unavailable")

    return ElfParseResult(
        path=path,
        symbols=tuple(symbols),
        has_dwarf=has_dwarf,
        used_dwarf=used_dwarf,
        warning="; ".join(warning_parts),
    )
