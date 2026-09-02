from pathlib import Path

from core.memory_browser import update_navigation_history


def test_navigation_history_is_mru_deduplicated_and_canonicalizes_addresses():
    history = []
    history = update_navigation_history(history, "MaxRpm")
    history = update_navigation_history(history, "0x20000060")
    history = update_navigation_history(history, "maxrpm")

    assert history == ["maxrpm", "0x20000060"]
    history = update_navigation_history(history, "0X20000060")
    assert history == ["0x20000060", "maxrpm"]


def test_navigation_history_is_bounded_and_ignores_blank_entries():
    history = []
    for i in range(10):
        history = update_navigation_history(history, f"symbol_{i}", max_items=4)
    assert history == ["symbol_9", "symbol_8", "symbol_7", "symbol_6"]
    assert update_navigation_history(history, "   ", max_items=4) == history


def test_v064_memory_ui_uses_editable_combo_with_persistent_clearable_history():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    assert "self.address_combo = QComboBox()" in source
    assert "self.address_combo.setEditable(True)" in source
    assert "QComboBox.InsertPolicy.NoInsert" in source
    assert "self.address_edit = self.address_combo.lineEdit()" in source
    assert '"navigation_history": list(self._navigation_history)' in source
    assert "def _history_activated" in source
    assert "def _clear_navigation_history" in source
    assert "self.clear_history_btn" in source
    assert "self.address_combo.setMinimumWidth(320)" in source
    assert "self.address_combo.setMaximumWidth(520)" in source


def test_history_selection_reuses_existing_goto_path_not_target_io_per_keystroke():
    source = Path("ui/memory_explorer.py").read_text(encoding="utf-8")
    block = source[source.index("    def _history_activated"):source.index("    def _rebuild_symbol_completion_model")]
    assert "self._goto()" in block
    assert "read_requested.emit" not in block
    assert "write_requested.emit" not in block
