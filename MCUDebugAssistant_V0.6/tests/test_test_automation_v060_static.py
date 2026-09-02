from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v060_main_window_wires_test_automation_through_worker():
    text = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'self.tabs.addTab(self.test_automation_page, "Test Automation")' in text
    assert "automation_snapshot_requested.connect(self._worker.read_automation_snapshot)" in text
    assert "automation_write_requested.connect(self._worker.write_automation_value)" in text
    assert "self.test_automation_page.set_symbols(result.symbols)" in text


def test_automation_page_never_imports_jlink_backend_or_dll():
    text = (ROOT / "ui" / "automation_page.py").read_text(encoding="utf-8")
    assert "JLinkBackend" not in text
    assert "JLINK_" not in text
    assert "snapshot_requested = Signal" in text
    assert "write_requested = Signal" in text


def test_v060_contains_parameter_matrix_and_generic_workflow_steps():
    text = (ROOT / "core" / "test_automation.py").read_text(encoding="utf-8")
    for token in (
        'STEP_SET = "SET"',
        'STEP_WAIT_STABLE = "WAIT_STABLE"',
        'STEP_SAMPLE = "SAMPLE"',
        'STEP_MANUAL_INPUT = "MANUAL_INPUT"',
        'STEP_CALCULATE = "CALCULATE"',
        'STEP_ASSERT = "ASSERT"',
        'COMBINATION_CARTESIAN = "cartesian"',
        'COMBINATION_ZIP = "zip"',
    ):
        assert token in text


def test_automation_worker_uses_single_owner_read_write_paths():
    text = (ROOT / "debugger" / "jlink_worker.py").read_text(encoding="utf-8")
    assert "def read_automation_snapshot" in text
    assert "self._jlink.read_memory" in text
    assert "def write_automation_value" in text
    assert "self._jlink.write_memory" in text
