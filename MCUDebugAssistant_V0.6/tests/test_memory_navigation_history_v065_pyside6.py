from pathlib import Path


def test_v065_qcombobox_history_uses_qt6_int_activated_signal():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    assert "self.address_combo.activated.connect(self._history_activated)" in source
    assert "self.address_combo.activated[str]" not in source


def test_v065_history_activation_resolves_text_from_combo_index():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    start = source.index("    def _history_activated")
    end = source.index("    def _rebuild_symbol_completion_model", start)
    block = source[start:end]
    assert "index: int" in block
    assert "self.address_combo.itemText(index)" in block
    assert "self._goto()" in block
    assert "read_requested.emit" not in block
    assert "write_requested.emit" not in block
