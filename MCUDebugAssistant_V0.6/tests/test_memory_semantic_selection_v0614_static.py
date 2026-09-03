from pathlib import Path


SOURCE = Path('ui/memory_explorer.py').read_text(encoding='utf-8')


def _method_block(name: str, *, after: str = 'class SymbolMemoryView') -> str:
    start = SOURCE.index(f'    def {name}', SOURCE.index(after))
    next_def = SOURCE.find('\n    def ', start + 8)
    return SOURCE[start:] if next_def < 0 else SOURCE[start:next_def]


def test_symbol_navigation_centers_and_selects_target_once():
    block = _method_block('_rebuild_model')
    focus = block.split('if focus_anchor and', 1)[1].split('if preserve_view:', 1)[0]
    assert 'self.tree.setCurrentIndex(index)' in focus
    assert 'QItemSelectionModel.SelectionFlag.ClearAndSelect' in focus
    assert 'QItemSelectionModel.SelectionFlag.Rows' in focus
    assert 'self.tree.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)' in focus
    assert 'self.tree.clearSelection()' not in focus


def test_refresh_preserves_real_selection_not_stale_current_index():
    block = _method_block('_rebuild_model')
    assert 'selected_rows = self.tree.selectionModel().selectedRows()' in block
    pre_clear = block.split('self._model.removeRows', 1)[0]
    assert 'self.tree.currentIndex()' not in pre_clear
    assert 'row = row_by_name.get(selected_name, -1)' in block
    assert 'self.tree.clearSelection()' in block
    assert 'self.tree.setCurrentIndex(QModelIndex())' in block


def test_clicking_empty_symbol_view_space_clears_selection_and_current_index():
    block = _method_block('eventFilter')
    assert 'watched is self.tree.viewport()' in block
    assert 'QEvent.Type.MouseButtonPress' in block
    assert 'not self.tree.indexAt(position).isValid()' in block
    assert 'self.tree.clearSelection()' in block
    assert 'self.tree.setCurrentIndex(QModelIndex())' in block
