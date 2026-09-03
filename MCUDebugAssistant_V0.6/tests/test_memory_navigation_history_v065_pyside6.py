from pathlib import Path


def test_qcombobox_history_keeps_qt6_int_activation_but_scopes_it_to_own_popup():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    assert "class NavigationHistoryComboBox(QComboBox)" in source
    assert "self.activated.connect(self._forward_history_activation)" in source
    assert "history_activated = Signal(int)" in source
    assert "self.address_combo.history_activated.connect(self._history_activated)" in source
    assert "self.address_combo.activated[str]" not in source


def test_history_activation_resolves_selected_model_row_directly_without_target_io():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    start = source.index("    def _history_activated")
    end = source.index("    def _auto_fit_popup_columns", start)
    block = source[start:end]
    assert "index: int" in block
    assert "self._history_model.item(index, 0)" in block
    assert "self._goto_symbol(symbol, remember=False)" in block
    assert "self._remember_navigation_query" not in block
    assert "read_requested.emit" not in block
    assert "write_requested.emit" not in block
