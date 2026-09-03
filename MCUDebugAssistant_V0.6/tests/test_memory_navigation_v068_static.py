from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "ui" / "memory_explorer.py").read_text(encoding="utf-8")


def test_symbol_completion_cannot_be_overwritten_by_combo_history_activation():
    combo_start = SOURCE.index("class NavigationHistoryComboBox")
    combo_end = SOURCE.index("class HexMemoryView", combo_start)
    combo = SOURCE[combo_start:combo_end]
    assert "_history_popup_session" in combo
    assert "def showPopup" in combo
    assert "def hidePopup" in combo
    assert "if not self._history_popup_session" in combo
    assert "history_activated.emit" in combo

    page_start = SOURCE.index("class MemoryExplorerPage")
    page = SOURCE[page_start:]
    assert "self.address_combo.history_activated.connect(self._history_activated)" in page
    assert "self.address_combo.activated.connect(self._history_activated)" not in page


def test_enter_does_not_guess_from_completer_current_index():
    assert "_selected_completion_symbol" not in SOURCE
    assert "currentCompletion()" not in SOURCE
    start = SOURCE.index("    def _address_return_pressed")
    end = SOURCE.index("    def _history_metadata", start)
    block = SOURCE[start:end]
    assert "allow_completion_fallback=False" in block
    assert "QCompleter.activated" in block


def test_old_width_settings_migrate_to_auto_but_new_manual_mode_can_persist():
    assert '"symbol_width_mode": "auto" if self._symbol_auto_fit else "manual"' in SOURCE
    start = SOURCE.index("    def load_settings_state")
    end = SOURCE.index("    def goto_address", start)
    block = SOURCE[start:end]
    assert 'state.get("symbol_width_mode", "")' in block
    assert "self._symbol_auto_fit = True" in block
    assert 'width_mode == "auto"' in block


def test_history_can_delete_one_item_without_clearing_current_navigation():
    assert "def _delete_history_row" in SOURCE
    assert "Delete This History" in SOURCE
    assert "Qt.Key.Key_Delete" in SOURCE
    start = SOURCE.index("    def _delete_history_row")
    end = SOURCE.index("    def _show_history_context_menu", start)
    block = SOURCE[start:end]
    assert "current_text = self.address_edit.text()" in block
    assert "self._sync_navigation_history_combo()" in block
    assert "self.address_combo.setEditText(current_text)" in block
    assert "read_requested.emit" not in block
    assert "write_requested.emit" not in block
