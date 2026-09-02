from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v062_sample_result_selection_remains_explicit_and_count_hidden():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    assert 'for metric, label in (("avg", "Avg"), ("min", "Min"), ("max", "Max"), ("std", "Std"))' in text
    assert 'data.get("statistics") or ["avg", "min", "max"]' in text
    # Count remains an internal sampling statistic, not a selectable result column.
    sample_ui = text.split("elif kind == STEP_SAMPLE:", 1)[1].split("elif kind == STEP_MANUAL_INPUT:", 1)[0]
    assert '"count"' not in sample_ui


def test_v062_result_table_uses_explicit_case_outputs_not_entire_runtime_context():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    finish = text.split("def _finish_case", 1)[1].split("def _next_case_timer", 1)[0]
    assert "for key in self._case_output_keys" in finish
    assert "for key, value in self._context.items()" not in finish
    assert "self._case_output_keys = list(case.keys())" in text
    assert 'self._register_case_output(f"{name}.{metric}")' in text


def test_v062_sampling_keeps_full_internal_statistics_for_legacy_calculation_compatibility():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    sample_done = text.split("all_stats = accumulator.flatten()", 1)[1].split("self._complete_step()", 1)[0]
    assert "self._context.update(all_stats)" in sample_done
    assert 'statistics = self._operation.get("statistics") or ["avg", "min", "max"]' in sample_done


def test_v062_completed_run_clears_runtime_context_view_and_opens_results_tab():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    completion = text.split("if self._case_index >= len(self._cases):", 1)[1].split("case = dict", 1)[0]
    assert 'self.run_step_label.setText("Done — see Results")' in completion
    assert "self.runtime_table.setRowCount(0)" in completion
    assert "self.lower_tabs.setCurrentIndex(1)" in completion
