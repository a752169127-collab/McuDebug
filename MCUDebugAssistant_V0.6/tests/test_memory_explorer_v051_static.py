from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_memory_explorer_starts_at_ram_base_and_does_not_restore_stale_address():
    source = (ROOT / "ui" / "memory_explorer.py").read_text(encoding="utf-8")
    assert "DEFAULT_RAM_BASE" in source
    assert "self.goto_address(DEFAULT_RAM_BASE)" in source
    assert 'state.get("address"' not in source


def test_memory_explorer_has_direct_edit_and_range_copy_paths():
    source = (ROOT / "ui" / "memory_explorer.py").read_text(encoding="utf-8")
    assert "_handle_hex_nibble" in source
    assert "_write_text_payload" in source
    assert "_copy_block_hex" in source
    assert "_copy_block_text" in source
    assert "mouseMoveEvent" in source
    assert "text_edit_requested" in source


def test_memory_explorer_write_has_no_second_modal_confirmation():
    source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
    start = source.index("def _write_memory_block")
    end = source.index("def _add_memory_address_to_watch", start)
    body = source[start:end]
    assert "memory_block_write_requested.emit" in body
    assert "QMessageBox.question" not in body
