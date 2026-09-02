from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v061_new_step_picker_is_simplified_but_legacy_execution_remains_compatible():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    assert "EDITOR_STEP_KINDS = (" in text
    editor_block = text.split("EDITOR_STEP_KINDS = (", 1)[1].split(")", 1)[0]
    assert "STEP_SET" in editor_block
    assert "STEP_WAIT" in editor_block
    assert "STEP_WAIT_STABLE" in editor_block
    assert "STEP_SAMPLE" in editor_block
    assert "STEP_MANUAL_INPUT" in editor_block
    assert "STEP_SAVE_RESULT" in editor_block
    assert "STEP_WAIT_UNTIL" not in editor_block
    assert "STEP_CALCULATE" not in editor_block
    assert "STEP_ASSERT" not in editor_block
    # Old V0.6.0 plans can still be loaded/run; only the new-step UI is simplified.
    assert "if wanted in SUPPORTED_STEPS and wanted not in kinds" in text


def test_v061_step_switch_recursively_clears_nested_layouts():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    assert "def _clear_layout(layout)" in text
    assert "child_layout = item.layout()" in text
    assert "StepDialog._clear_layout(child_layout)" in text
    assert "child_layout.deleteLater()" in text
    assert "self._clear_layout(self.body_layout)" in text


def test_v061_default_plan_has_no_calculate_assert_or_wait_until_nodes():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    block = text.split("def _install_default_plan", 1)[1].split("def _parameter_rows", 1)[0]
    assert '"kind": STEP_CALCULATE' not in block
    assert '"kind": STEP_ASSERT' not in block
    assert '"kind": STEP_WAIT_UNTIL' not in block
