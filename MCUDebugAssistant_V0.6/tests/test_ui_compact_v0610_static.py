from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_connection_panel_is_collapsible_and_auto_collapses_after_connect():
    source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'self.connection_toggle_btn = QToolButton()' in source
    assert 'self.connection_details = QWidget()' in source
    assert 'def _set_connection_details_collapsed' in source
    assert 'self.connection_details.setVisible(not self._connection_collapsed)' in source
    assert 'self.connection_toggle_btn.setText("+" if self._connection_collapsed else "−")' in source
    assert 'self._set_connection_details_collapsed(bool(connected))' in source
    # Disconnect remains in the compact always-visible header.
    header_pos = source.index('header.addWidget(self.disconnect_btn)')
    details_pos = source.index('self.connection_details = QWidget()')
    assert header_pos < details_pos


def test_automation_business_tables_do_not_duplicate_row_numbers():
    source = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    assert 'self.parameter_table.verticalHeader().setVisible(False)' in source
    assert 'self.step_table = QTableWidget(0, 2)' in source
    assert 'self.step_table.setHorizontalHeaderLabels(["Step", "Summary"])' in source
    assert 'self.step_table.verticalHeader().setVisible(False)' in source
    assert 'self.runtime_table.verticalHeader().setVisible(False)' in source
    assert 'self.results_table.verticalHeader().setVisible(False)' in source
    assert 'self.step_table.setHorizontalHeaderLabels(["#", "Step", "Summary"])' not in source
