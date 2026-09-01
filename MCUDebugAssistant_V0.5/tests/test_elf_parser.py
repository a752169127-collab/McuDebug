from pathlib import Path
import struct

from symbols.elf_parser import parse_elf_symbols


def _align(value: int, alignment: int = 4) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def _make_minimal_elf32(path: Path) -> None:
    shstr = b"\0.shstrtab\0.strtab\0.symtab\0.data\0"
    strtab = b"\0g_value\0"
    sym_null = b"\0" * 16
    sym_value = struct.pack("<IIIBBH", 1, 0x20000000, 4, (1 << 4) | 1, 0, 4)
    symtab = sym_null + sym_value
    data = b"\x78\x56\x34\x12"

    ehdr_size = 52
    off_shstr = ehdr_size
    off_strtab = off_shstr + len(shstr)
    off_symtab = _align(off_strtab + len(strtab), 4)
    off_data = off_symtab + len(symtab)
    shoff = _align(off_data + len(data), 4)

    blob = bytearray(shoff + 5 * 40)
    ident = bytearray(16)
    ident[:4] = b"\x7fELF"
    ident[4] = 1  # ELF32
    ident[5] = 1  # little endian
    ident[6] = 1  # version
    blob[:16] = ident
    ehdr = struct.pack(
        "<HHIIIIIHHHHHH",
        2, 40, 1, 0, 0, shoff, 0,
        52, 0, 0, 40, 5, 1,
    )
    blob[16:52] = ehdr
    blob[off_shstr:off_shstr + len(shstr)] = shstr
    blob[off_strtab:off_strtab + len(strtab)] = strtab
    blob[off_symtab:off_symtab + len(symtab)] = symtab
    blob[off_data:off_data + len(data)] = data

    names = {
        ".shstrtab": shstr.index(b".shstrtab"),
        ".strtab": shstr.index(b".strtab"),
        ".symtab": shstr.index(b".symtab"),
        ".data": shstr.index(b".data"),
    }
    shdrs = [
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (names[".shstrtab"], 3, 0, 0, off_shstr, len(shstr), 0, 0, 1, 0),
        (names[".strtab"], 3, 0, 0, off_strtab, len(strtab), 0, 0, 1, 0),
        (names[".symtab"], 2, 0, 0, off_symtab, len(symtab), 2, 1, 4, 16),
        (names[".data"], 1, 0x3, 0x20000000, off_data, len(data), 0, 0, 4, 0),
    ]
    for i, sh in enumerate(shdrs):
        blob[shoff + i * 40: shoff + (i + 1) * 40] = struct.pack("<IIIIIIIIII", *sh)
    path.write_bytes(blob)


def test_parse_minimal_elf32_symbol(tmp_path):
    elf = tmp_path / "sample.axf"
    _make_minimal_elf32(elf)
    result = parse_elf_symbols(elf)
    symbol = next(s for s in result.symbols if s.name == "g_value")
    assert symbol.address == 0x20000000
    assert symbol.size == 4
    assert symbol.type_name == "uint32"
    assert symbol.writable is True
    assert symbol.section == ".data"
