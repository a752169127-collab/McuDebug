from pathlib import Path

from core.memory_browser import symbol_display_type


def test_symbol_display_type_accepts_only_supported_scalar_types():
    assert symbol_display_type("uint8") == "uint8"
    assert symbol_display_type("int16") == "int16"
    assert symbol_display_type("float") == "float"
    assert symbol_display_type("array") is None
    assert symbol_display_type("struct MotorCtrl") is None
    assert symbol_display_type(None) is None


def test_v066_history_popup_shows_query_type_and_address_without_resizing_editor():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    assert 'setHorizontalHeaderLabels(["History", "Type", "Address"])' in source
    assert "self.address_combo.setMinimumWidth(320)" in source
    assert "self.address_combo.setMaximumWidth(520)" in source
    assert "self.address_combo.setModel(self._history_model)" in source
    assert "self.address_combo.setView(history_popup)" in source
    assert "def _history_metadata" in source
    assert "symbol.type_name or symbol.kind" in source


def test_v066_symbol_navigation_applies_axf_scalar_type_before_goto():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    start = source.index("    def _goto_symbol")
    end = source.index("    def _selection_changed", start)
    block = source[start:end]
    assert "display_type = symbol_display_type(symbol.type_name)" in block
    assert "self.view.set_display_type(display_type)" in block
    assert block.index("self.view.set_display_type(display_type)") < block.index("self.goto_address(symbol.base_address, display_text=symbol.name)")


def test_v066_history_metadata_refreshes_after_symbol_reload_without_target_io():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    page_start = source.index("class MemoryExplorerPage")
    start = source.index("    def set_symbols(self, symbols)", page_start)
    end = source.index("    def clear_symbols", start)
    block = source[start:end]
    assert "self._sync_navigation_history_combo()" in block

    start = source.index("    def _history_metadata")
    end = source.index("    def _sync_navigation_history_combo", start)
    block = source[start:end]
    assert "read_requested.emit" not in block
    assert "write_requested.emit" not in block
