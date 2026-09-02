from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "ui" / "watch_table.py").read_text(encoding="utf-8")


def test_watch_set_value_writes_on_enter_or_focus_out_after_user_edit():
    assert "editor.textEdited.connect(mark_dirty)" in SOURCE
    assert "editor.returnPressed.connect(commit_if_dirty)" in SOURCE
    assert "editor.editingFinished.connect(commit_if_dirty)" in SOURCE
    assert "self.commitData.emit(editor)" in SOURCE
    assert "self.commit_requested.emit" in SOURCE


def test_watch_set_value_focusout_guard_avoids_duplicate_or_unmodified_write():
    assert 'editor.setProperty("watch_set_value_dirty", False)' in SOURCE
    assert 'if not bool(editor.property("watch_set_value_dirty"))' in SOURCE
    assert 'editor.setProperty("watch_set_value_dirty", False)' in SOURCE
