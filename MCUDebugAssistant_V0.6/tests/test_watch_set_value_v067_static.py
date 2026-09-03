from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "ui" / "watch_table.py").read_text(encoding="utf-8")


def test_set_value_commit_is_model_commit_authoritative_and_same_value_safe():
    assert "def setModelData(self, editor, model, index)" in SOURCE
    assert "dirty = isinstance(editor, QLineEdit)" in SOURCE
    assert "super().setModelData(editor, model, index)" in SOURCE
    assert "if not dirty:" in SOURCE
    assert "self.commit_requested.emit" in SOURCE
    assert "editor.returnPressed.connect" not in SOURCE
    assert "editor.editingFinished.connect" not in SOURCE
