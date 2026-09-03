from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "ui" / "memory_explorer.py").read_text(encoding="utf-8")


def test_completion_enter_has_one_authoritative_qcompleter_commit_path():
    assert "self.address_edit.returnPressed.connect(self._address_return_pressed)" in SOURCE
    assert "self._symbol_completer.activated[str].connect(self._symbol_completion_activated)" in SOURCE
    start = SOURCE.index("    def _address_return_pressed")
    end = SOURCE.index("    def _navigate_query", start)
    block = SOURCE[start:end]
    assert "popup.isVisible()" in block
    assert "return" in block
    assert "currentCompletion()" not in SOURCE
    assert "_selected_completion_symbol" not in SOURCE


def test_history_activation_is_popup_scoped_and_symbol_text_is_preserved():
    combo_start = SOURCE.index("class NavigationHistoryComboBox")
    combo_end = SOURCE.index("class HexMemoryView", combo_start)
    combo = SOURCE[combo_start:combo_end]
    assert "self._history_popup_session = True" in combo
    assert "if not self._history_popup_session" in combo
    assert "self.history_activated.emit(int(index))" in combo

    start = SOURCE.index("    def _history_activated")
    end = SOURCE.index("    def _auto_fit_popup_columns", start)
    block = SOURCE[start:end]
    assert "self._history_model.item(index, 0)" in block
    assert "self._goto_symbol(symbol, remember=False)" in block
    assert "self._remember_navigation_query" not in block

    goto_start = SOURCE.index("    def _goto_symbol")
    goto_end = SOURCE.index("    def _selection_changed", goto_start)
    goto_block = SOURCE[goto_start:goto_end]
    assert "display_text=symbol.name" in goto_block


def test_symbol_names_auto_fit_in_memory_and_both_popups_without_target_io():
    assert "self._symbol_auto_fit = True" in SOURCE
    assert "def _auto_symbol_width" in SOURCE
    assert "self._auto_fit_popup_columns" in SOURCE
    assert "fm.horizontalAdvance(text)" in SOURCE
    auto_start = SOURCE.index("    def _auto_symbol_width")
    auto_end = SOURCE.index("    def _column_geometry", auto_start)
    block = SOURCE[auto_start:auto_end]
    assert "read_requested.emit" not in block
    assert "write_requested.emit" not in block
