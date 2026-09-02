from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v063_new_sample_defaults_to_avg_min_max_without_std():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    assert 'data.get("statistics") or ["avg", "min", "max"]' in text
    default_block = text.split("def _install_default_plan", 1)[1].split("def _parameter_rows", 1)[0]
    assert '"statistics": ["avg", "min", "max"]' in default_block
    # Std remains available only as an explicit opt-in statistic.
    assert '(("avg", "Avg"), ("min", "Min"), ("max", "Max"), ("std", "Std"))' in text


def test_v063_starting_a_new_run_preserves_accumulated_results():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    run_all = text.split("def _run_all", 1)[1].split("def stop_run", 1)[0]
    assert "self._results.clear()" not in run_all
    assert "self.results_table.setRowCount(0)" not in run_all
    assert "result history is intentionally cumulative across runs" in run_all


def test_v063_results_tab_owns_copy_and_manual_clear_controls():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    toolbar = text.split("def _build_ui", 1)[1].split("def _build_parameter_group", 1)[0]
    assert 'QPushButton("Export CSV")' not in toolbar
    results = text.split("def _build_results_page", 1)[1].split("# ---------- Symbols / connection ----------", 1)[0]
    assert 'QPushButton("Copy Results")' in results
    assert 'QPushButton("Clear Results")' in results
    assert "self._copy_results_to_clipboard" in results
    assert "self._clear_results" in results


def test_v063_copy_is_tsv_with_header_for_excel_and_clear_is_explicit():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    copy_block = text.split("def _copy_results_to_clipboard", 1)[1].split("def _clear_results", 1)[0]
    assert '"\\t".join(self._result_columns)' in copy_block
    assert 'QApplication.clipboard().setText("\\n".join(lines))' in copy_block
    clear_block = text.split("def _clear_results", 1)[1]
    assert "QMessageBox.question" in clear_block
    assert "self._results.clear()" in clear_block
    assert 'self._result_columns = ["Case", "Status"]' in clear_block


def test_v063_completed_run_still_clears_runtime_only_and_opens_results():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    completion = text.split("if self._case_index >= len(self._cases):", 1)[1].split("case = dict", 1)[0]
    assert "self.runtime_table.setRowCount(0)" in completion
    assert "self._results.clear()" not in completion
    assert "self.lower_tabs.setCurrentIndex(1)" in completion
