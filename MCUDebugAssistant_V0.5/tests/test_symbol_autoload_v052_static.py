from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _main_window_source() -> str:
    return (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")


def test_saved_symbol_file_is_scheduled_for_startup_autoload():
    source = _main_window_source()
    assert "QTimer.singleShot(0, self._auto_load_saved_symbol_file)" in source


def test_symbol_autoload_only_uses_existing_saved_file_and_rebinds_consumers():
    source = _main_window_source()
    start = source.index("def _auto_load_saved_symbol_file")
    end = source.index("def _browse_symbol_file", start)
    body = source[start:end]
    assert "self.symbol_file_edit.text().strip()" in body
    assert ".is_file()" in body
    assert "self._load_symbol_file(str(candidate), rebind_watch=True)" in body
    assert ".glob(" not in body
