from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_common_timing_controls_use_editable_preset_combo():
    main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
    memory = (ROOT / "ui" / "memory_explorer.py").read_text(encoding="utf-8")
    scope = (ROOT / "ui" / "scope_page.py").read_text(encoding="utf-8")

    assert "WATCH_INTERVAL_PRESETS_MS = [10, 20, 50, 100, 200, 500, 1000, 2000]" in main
    assert "self.sample_interval_spin = IntPresetComboBox(" in main

    assert "self.auto_interval = IntPresetComboBox(" in memory
    assert "[100, 200, 500, 1000, 2000, 5000]" in memory

    assert "self.sample_hz_spin = IntPresetComboBox(" in scope
    assert "[10, 20, 50, 100, 200, 500, 1000, 2000, 5000]" in scope
    assert "self.buffer_seconds_spin = IntPresetComboBox(" in scope
    assert "[1, 2, 5, 10, 15, 30, 60, 120]" in scope
    assert "self.fps_combo = IntPresetComboBox(" in scope
    assert "[15, 30, 60, 90, 120, 144]" in scope


def test_preset_combo_keeps_custom_value_api_and_no_increment_arrows():
    source = (ROOT / "ui" / "preset_combo.py").read_text(encoding="utf-8")
    assert "class IntPresetComboBox(QComboBox)" in source
    assert "self.setEditable(True)" in source
    assert "QComboBox.InsertPolicy.NoInsert" in source
    assert "def value(self) -> int" in source
    assert "def setValue(self, value: int)" in source
    assert "valueChanged = Signal(int)" in source
    assert "QSpinBox" not in source.replace("QSpinBox-like", "")


def test_scope_buffer_presets_do_not_expand_existing_memory_bound():
    source = (ROOT / "ui" / "scope_page.py").read_text(encoding="utf-8")
    # Keep the proven 120 s product bound; larger values can make the fixed
    # 1.5M-point ring silently retain less time at high requested sample rates.
    assert "maximum=120" in source
    assert "[1, 2, 5, 10, 15, 30, 60, 120]" in source
