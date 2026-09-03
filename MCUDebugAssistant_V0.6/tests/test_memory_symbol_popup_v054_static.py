from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "ui" / "memory_explorer.py").read_text(encoding="utf-8")


def test_symbol_completion_popup_has_stable_visible_height():
    assert "completion_popup.setMinimumHeight(240)" in SOURCE
    assert "completion_popup.setMaximumHeight(420)" in SOURCE
    assert "self._symbol_completer.setMaxVisibleItems(14)" in SOURCE


def test_popup_height_fix_keeps_local_model_filtering_only():
    # Regression guard: fixing popup geometry must not reintroduce per-key AXF
    # model rebuild or target reads. QLineEdit still delegates matching to the
    # already-built QCompleter model.
    assert "self.address_edit.setCompleter(self._symbol_completer)" in SOURCE
    assert "self._symbol_completer.setFilterMode(Qt.MatchFlag.MatchContains)" in SOURCE
    assert "self.address_edit.textChanged.connect" not in SOURCE
    # V0.6.9 may observe textEdited only for a bounded local (<=50 row)
    # history-delete selection state. It must not rebuild AXF rows or touch target I/O.
    if "self.address_edit.textEdited.connect" in SOURCE:
        start = SOURCE.index("    def _history_editor_text_edited")
        end = SOURCE.index("    def _clear_navigation_history", start)
        block = SOURCE[start:end]
        assert "_rebuild_symbol_completion_model" not in block
        assert "_install_symbol_completion_model" not in block
        assert "read_requested.emit" not in block
        assert "write_requested.emit" not in block
