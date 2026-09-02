from dataclasses import dataclass

import pytest

from core.memory_browser import (
    SymbolIndex,
    decode_text,
    display_unit_size,
    format_display_value,
    parse_address,
    plan_read_window,
)


@dataclass
class S:
    name: str
    address: int
    size: int
    type_name: str | None = None
    kind: str = "scalar"
    source: str = "DWARF"


def test_parse_address_32_bit():
    assert parse_address("0x20000000") == 0x20000000
    assert parse_address("4294967295") == 0xFFFFFFFF
    with pytest.raises(ValueError):
        parse_address("0x100000000")


def test_read_window_is_aligned_and_bounded():
    w = plan_read_window(0x20000000 // 16, 30, margin_rows=8, max_read_bytes=2048)
    assert w.address % 16 == 0
    assert w.size % 16 == 0
    assert w.address <= 0x20000000
    assert w.address + w.size > 0x20000000
    assert w.size <= 2048

    tail = plan_read_window(0xFFFFFFFF // 16, 10)
    assert tail.address + tail.size <= 1 << 32


def test_display_formatting():
    assert display_unit_size("byte") == 1
    assert display_unit_size("float") == 4
    assert format_display_value(b"\xAB", "byte") == "AB"
    assert format_display_value(b"\x00\x00\x80\x3f", "float") == "1"


def test_text_decoding():
    assert decode_text(b"Hello\x00!", "ASCII") == "Hello.!"
    assert "Hello" in decode_text("Hello".encode("utf-16-le"), "UTF-16 LE")


def test_symbol_index_prefers_dwarf_member_and_offsets():
    index = SymbolIndex(
        [
            S("g_ctrl", 0x20001000, 32, "struct Ctrl", "container", "DWARF-lite"),
            S("g_ctrl.speed", 0x20001004, 4, "float", "scalar", "DWARF-lite"),
            S("g_ctrl", 0x20001000, 32, None, "object", "ELF symbol"),
        ]
    )
    assert index.describe(0x20001004) == "g_ctrl.speed"
    assert index.describe(0x20001006) == "g_ctrl.speed+0x2"
    assert index.describe(0x20001020) == ""
    starts = index.starts_in_range(0x20001000, 0x20001010)
    assert [s.name for s in starts] == ["g_ctrl", "g_ctrl.speed"]


def test_text_input_encoding_and_edit_unit():
    from core.memory_browser import encode_text_input, text_edit_unit_size

    assert encode_text_input("AB", "ASCII") == b"AB"
    assert encode_text_input("中", "UTF-8") == "中".encode("utf-8")
    assert encode_text_input("A", "UTF-16 LE") == b"A\x00"
    assert text_edit_unit_size("ASCII") == 1
    assert text_edit_unit_size("UTF-16 LE") == 2
    with pytest.raises(ValueError):
        encode_text_input("中", "ASCII")


def test_format_hex_block_for_batch_clipboard():
    from core.memory_browser import format_hex_block

    data = bytes(range(20))
    lines = format_hex_block(data).splitlines()
    assert lines[0] == "00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F"
    assert lines[1] == "10 11 12 13"


def test_symbol_name_lookup_supports_members_and_array_indices():
    index = SymbolIndex(
        [
            S("buffer", 0x20002000, 16, "array", "container", "DWARF-lite"),
            S("buffer[0]", 0x20002000, 4, "uint32", "scalar", "DWARF-lite"),
            S("buffer[1]", 0x20002004, 4, "uint32", "scalar", "DWARF-lite"),
            S("ctrl.channels[1].gain", 0x20002124, 4, "float", "scalar", "DWARF-lite"),
        ]
    )

    assert index.exact_name("buffer[1]").base_address == 0x20002004
    assert index.exact_name("BUFFER[1]").base_address == 0x20002004
    assert index.exact_name("ctrl.channels[1].gain").base_address == 0x20002124
    assert [item.name for item in index.search_names("channels[1]", limit=10)] == [
        "ctrl.channels[1].gain"
    ]


def test_symbol_name_index_prefers_dwarf_record_and_is_stably_sorted():
    index = SymbolIndex(
        [
            S("z_value", 0x20003000, 4, "uint32", "scalar", "ELF symbol"),
            S("z_value", 0x20003004, 4, "float", "scalar", "DWARF-lite"),
            S("a_value", 0x20001000, 4, "uint32", "scalar", "DWARF-lite"),
        ]
    )

    assert index.exact_name("z_value").base_address == 0x20003004
    assert [item.name for item in index.preferred_symbols()] == ["a_value", "z_value"]
