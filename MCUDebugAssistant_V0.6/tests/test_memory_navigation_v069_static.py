from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "ui" / "memory_explorer.py").read_text(encoding="utf-8")


def _block(start_name: str, end_name: str) -> str:
    start = SOURCE.index(f"    def {start_name}")
    end = SOURCE.index(f"    def {end_name}", start)
    return SOURCE[start:end]


def test_history_has_persistent_single_delete_button():
    assert 'self.delete_history_btn = QPushButton("Delete History")' in SOURCE
    assert 'self.delete_history_btn.clicked.connect(self._delete_selected_history)' in SOURCE
    assert 'self.address_edit.textEdited.connect(self._history_editor_text_edited)' in SOURCE
    delete_block = _block("_delete_selected_history", "_delete_history_row")
    assert "self._navigation_history = [" in delete_block
    assert "self._selected_history_query = None" in delete_block
    assert "self.address_combo.setEditText(current_text)" in delete_block
    assert "read_requested.emit" not in delete_block
    assert "write_requested.emit" not in delete_block


def test_selecting_existing_history_does_not_reorder_history():
    history_block = _block("_history_activated", "_auto_fit_popup_columns")
    assert "self._selected_history_query = query" in history_block
    assert "self._goto_symbol(symbol, remember=False)" in history_block
    assert "self._remember_navigation_query" not in history_block
    assert "update_navigation_history" not in history_block
    assert "self._navigate_query" not in history_block


def test_history_context_menu_is_not_primary_wiring_anymore():
    # QComboBox popups can close when a nested context menu opens on Windows.
    # V0.6.9 keeps single-delete available as a normal toolbar button instead.
    init_start = SOURCE.index("class MemoryExplorerPage")
    init_end = SOURCE.index("        # Build the symbol rows", init_start)
    init_block = SOURCE[init_start:init_end]
    assert "customContextMenuRequested.connect" not in init_block
    assert "Delete History" in init_block


def test_typing_clears_stale_delete_target_unless_text_matches_history():
    block = _block("_history_editor_text_edited", "_clear_navigation_history")
    assert "self._selected_history_query = next(" in block
    assert "self._navigation_history" in block
    assert "self._update_delete_history_button()" in block
    assert "read_requested.emit" not in block
    assert "write_requested.emit" not in block
