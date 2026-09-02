from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "ui" / "memory_explorer.py").read_text(encoding="utf-8")


def test_memory_address_bar_supports_model_backed_symbol_completion():
    assert 'QCompleter' in SOURCE
    assert 'setFilterMode(Qt.MatchFlag.MatchContains)' in SOURCE
    assert 'self._symbol_completion_model = QStandardItemModel' in SOURCE
    assert 'self.address_edit.setCompleter(self._symbol_completer)' in SOURCE
    assert 'self._symbol_index.exact_name(text)' in SOURCE
    assert 'self._symbol_completer.currentCompletion()' in SOURCE


def test_symbol_search_path_does_not_request_jlink_per_keystroke():
    # The only text-change behavior is QCompleter's local model filtering. There
    # must be no address_edit.textChanged -> refresh/read_requested connection.
    assert 'address_edit.textChanged.connect' not in SOURCE
    assert 'Address / Symbol' in SOURCE
    assert 'buffer[1]' in SOURCE
