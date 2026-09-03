from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_PAGE = ROOT / "ui" / "automation_page.py"


def _manual_dialog_source() -> str:
    text = AUTOMATION_PAGE.read_text(encoding="utf-8")
    start = text.index("class ManualInputDialog")
    end = text.index("\n\nclass TestAutomationPage", start)
    return text[start:end]


def test_manual_input_confirm_is_the_default_enter_action() -> None:
    source = _manual_dialog_source()
    assert 'confirm = QPushButton("Confirm / Next")' in source
    assert "confirm.setDefault(True)" in source
    assert "confirm.setAutoDefault(True)" in source
    assert "confirm.clicked.connect(self._confirm)" in source


def test_manual_input_stop_cannot_become_dialog_auto_default() -> None:
    source = _manual_dialog_source()
    assert 'stop = QPushButton("Stop Run")' in source
    assert "stop.setDefault(False)" in source
    assert "stop.setAutoDefault(False)" in source
    assert "stop.setFocusPolicy(Qt.FocusPolicy.ClickFocus)" in source
    assert "stop.clicked.connect(self._stop)" in source
    assert "returnPressed.connect(self._stop)" not in source


def test_manual_input_skip_is_not_the_enter_default() -> None:
    source = _manual_dialog_source()
    assert "skip.setDefault(False)" in source
    assert "skip.setAutoDefault(False)" in source
