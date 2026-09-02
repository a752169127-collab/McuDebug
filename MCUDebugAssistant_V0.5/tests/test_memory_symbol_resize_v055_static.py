from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "ui" / "memory_explorer.py").read_text(encoding="utf-8")


def test_memory_symbol_column_is_user_resizable_and_persisted():
    assert "self._symbol_width_px: int | None = None" in SOURCE
    assert '"symbol_width_px": self._symbol_width_px' in SOURCE
    assert "self._symbol_resize_hit" in SOURCE
    assert "self._resize_symbol_column_to" in SOURCE
    assert "Qt.CursorShape.SizeHorCursor" in SOURCE


def test_symbol_resize_preserves_single_column_elide_rendering():
    assert "fm.elidedText(symbol_text, Qt.TextElideMode.ElideRight" in SOURCE
    assert "max_symbol_w = cw * 120" in SOURCE
    assert "symbol_w = max(min_symbol_w" in SOURCE
