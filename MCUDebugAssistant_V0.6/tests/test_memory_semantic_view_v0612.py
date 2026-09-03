from dataclasses import dataclass
from pathlib import Path

from core.memory_browser import SymbolIndex, plan_symbol_read_window


@dataclass
class S:
    name: str
    address: int
    size: int
    type_name: str | None = None
    kind: str = "scalar"
    source: str = "DWARF-lite"


def test_scalar_symbol_neighborhood_returns_array_members_in_address_order():
    index = SymbolIndex(
        [
            S("obj.bias", 0x20001000, 8, "array", "container"),
            S("obj.bias[0]", 0x20001000, 2, "uint16"),
            S("obj.bias[1]", 0x20001002, 2, "uint16"),
            S("obj.bias[2]", 0x20001004, 2, "uint16"),
            S("obj.bias[3]", 0x20001006, 2, "uint16"),
            S("obj.position", 0x20001008, 4, "float"),
        ]
    )
    rows = index.scalar_starts_in_range(0x20001000, 0x2000100C)
    assert [(row.name, row.type_name, row.size) for row in rows] == [
        ("obj.bias[0]", "uint16", 2),
        ("obj.bias[1]", "uint16", 2),
        ("obj.bias[2]", "uint16", 2),
        ("obj.bias[3]", "uint16", 2),
        ("obj.position", "float", 4),
    ]


def test_scalar_symbol_neighborhood_prefers_real_dwarf_member_over_elf_guess_at_same_address():
    index = SymbolIndex(
        [
            S("obj", 0x20002000, 4, "uint32", "scalar", "ELF symbol"),
            S("obj.value", 0x20002000, 4, "float", "scalar", "DWARF-lite"),
        ]
    )
    rows = index.scalar_starts_in_range(0x20002000, 0x20002004)
    assert [row.name for row in rows] == ["obj.value"]


def test_symbol_read_window_is_bounded_aligned_and_contains_target():
    target = 0x200028B8
    window = plan_symbol_read_window(target)
    assert window.address % 16 == 0
    assert window.size % 16 == 0
    assert window.size <= 2048
    assert window.address <= target < window.address + window.size


def test_v0612_ui_has_auto_raw_symbols_modes_and_one_block_feeds_both_views():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    assert "class SymbolMemoryView(QWidget):" in source
    assert 'self.view_mode_combo.addItem("Auto", "auto")' in source
    assert 'self.view_mode_combo.addItem("Raw", "raw")' in source
    assert 'self.view_mode_combo.addItem("Symbols", "symbols")' in source
    assert 'self._model.setHorizontalHeaderLabels(["Address", "Symbol", "Type", "Value"])' in source
    assert "scalar_starts_in_range(start, end, limit=512)" in source
    assert "format_display_value(raw, display_type)" in source

    start = source.index("    def set_block(self, address: int, data: bytes) -> None:", source.index("class MemoryExplorerPage"))
    end = source.index("    def patch_bytes", start)
    block = source[start:end]
    assert "self.view.set_block(address, data)" in block
    assert "self.symbol_view.set_block(address, data)" in block


def test_v0612_auto_mode_is_symbol_for_symbol_navigation_and_raw_for_numeric_navigation():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    start = source.index("    def _effective_view_mode")
    end = source.index("    def _apply_view_mode", start)
    block = source[start:end]
    assert 'self._last_navigation_kind == "symbol"' in block
    assert 'else "raw"' in block

    goto_start = source.index("    def _goto_symbol")
    goto_end = source.index("    def _active_view", goto_start)
    goto_block = source[goto_start:goto_end]
    assert 'self._last_navigation_kind = "symbol"' in goto_block
