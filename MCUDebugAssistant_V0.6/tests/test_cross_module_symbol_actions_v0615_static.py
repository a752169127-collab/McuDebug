from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_memory_symbol_menu_exposes_watch_scope_copy_and_relay():
    text = _text("ui/memory_explorer.py")
    assert 'add_watch_action = menu.addAction("Add to Watch")' in text
    assert 'add_scope_action = menu.addAction("Add to Scope")' in text
    assert 'copy_symbol_action = menu.addAction("Copy Symbol")' in text
    assert 'self.add_scope_requested.emit(symbol.name, symbol.base_address, display_type)' in text
    assert 'memory_view.add_scope_requested.connect(self.add_scope_requested.emit)' in text


def test_watch_context_menu_exposes_scope_memory_copy():
    text = _text("ui/watch_table.py")
    assert 'add_scope_requested = Signal(str, object, str)' in text
    assert 'open_memory_requested = Signal(str, object, str)' in text
    assert 'add_scope_action = menu.addAction("Add to Scope")' in text
    assert 'open_memory_action = menu.addAction("Open in Memory")' in text
    assert 'copy_symbol_action = menu.addAction("Copy Symbol")' in text
    assert 'QApplication.clipboard().setText(name)' in text


def test_scope_context_menu_exposes_memory_watch_copy_and_rtt_guard():
    text = _text("ui/scope_page.py")
    assert 'open_memory_requested = Signal(str, object, str)' in text
    assert 'add_watch_requested = Signal(str, object, str)' in text
    assert 'open_memory_action = menu.addAction("Open in Memory")' in text
    assert 'add_watch_action = menu.addAction("Add to Watch")' in text
    assert 'copy_symbol_action = menu.addAction("Copy Symbol")' in text
    assert 'valid_symbol_address = info is not None and not self._rtt_mode' in text
    assert 'if self._source != "HSS" or self._sampling:' in text


def test_main_window_wires_cross_module_actions_without_new_probe_owner():
    text = _text("ui/main_window.py")
    assert 'self.watch_table.add_scope_requested.connect(self._add_symbol_to_scope)' in text
    assert 'self.watch_table.open_memory_requested.connect(self._open_symbol_in_memory)' in text
    assert 'self.scope_page.open_memory_requested.connect(self._open_symbol_in_memory)' in text
    assert 'self.scope_page.add_watch_requested.connect(self._add_memory_address_to_watch)' in text
    assert 'self.memory_explorer.add_scope_requested.connect(self._add_symbol_to_scope)' in text
    assert 'self.memory_explorer.open_symbol_location(name, address, type_name)' in text
    # Cross-module navigation is UI-local and must not create a second backend/worker.
    assert text.count('self._worker = JLinkWorker()') == 1


def test_open_in_memory_prefers_exact_symbol_semantics_and_falls_back_to_raw_address():
    text = _text("ui/memory_explorer.py")
    assert 'def open_symbol_location(self, name: str, address: int, type_name: str = "")' in text
    assert 'if symbol is not None and int(symbol.base_address) == address:' in text
    assert 'self._goto_symbol(symbol, remember=False)' in text
    assert 'self._last_navigation_kind = "address"' in text
