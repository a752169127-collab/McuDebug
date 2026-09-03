from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "ui" / "watch_table.py").read_text(encoding="utf-8")


def test_watch_set_value_writes_from_delegate_commit_for_enter_or_focus_out():
    assert "editor.textEdited.connect(mark_dirty)" in SOURCE
    assert "def setModelData(self, editor, model, index)" in SOURCE
    assert "super().setModelData(editor, model, index)" in SOURCE
    assert "self.commit_requested.emit" in SOURCE


def test_watch_set_value_same_value_edit_still_writes_but_untouched_cell_does_not():
    assert 'editor.setProperty("watch_set_value_dirty", False)' in SOURCE
    assert 'bool(editor.property("watch_set_value_dirty"))' in SOURCE
    assert "if not dirty:" in SOURCE
    assert "re-entering the same value" in SOURCE
