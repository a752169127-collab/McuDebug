from pathlib import Path


SOURCE = Path('ui/memory_explorer.py').read_text(encoding='utf-8')


def _method_block(name: str, *, after: str = 'class SymbolMemoryView') -> str:
    start = SOURCE.index(f'    def {name}', SOURCE.index(after))
    next_def = SOURCE.find('\n    def ', start + 8)
    return SOURCE[start:] if next_def < 0 else SOURCE[start:next_def]


def test_symbol_refresh_does_not_rebuild_cached_model_or_scroll_to_anchor():
    block = _method_block('refresh')
    assert 'if cached and not force:' in block
    assert 'return' in block
    cached_tail = block.split('if cached and not force:', 1)[1].split('self.read_requested.emit', 1)[0]
    assert '_rebuild_model' not in cached_tail
    assert 'scrollTo' not in block


def test_symbol_block_refresh_preserves_view_except_one_pending_navigation_focus():
    block = _method_block('set_block')
    assert 'focus_anchor = self._focus_anchor_on_next_block' in block
    assert 'self._focus_anchor_on_next_block = False' in block
    assert 'preserve_view=not focus_anchor' in block
    assert 'focus_anchor=focus_anchor' in block


def test_rebuild_restores_scroll_after_selection_and_navigation_focus_is_one_shot():
    block = _method_block('_rebuild_model')
    assert 'vscroll = self.tree.verticalScrollBar().value() if preserve_view else 0' in block
    assert 'selected_rows = self.tree.selectionModel().selectedRows()' in block
    assert 'self.tree.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)' in block
    assert 'QItemSelectionModel.SelectionFlag.ClearAndSelect' in block
    assert block.index('row = row_by_name.get(selected_name, -1)') < block.index('self.tree.verticalScrollBar().setValue(vscroll)')


def test_patch_bytes_preserves_semantic_viewport():
    block = _method_block('patch_bytes')
    assert 'self._rebuild_model(preserve_view=True)' in block
