from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_scope_has_no_stall_investigation_runtime() -> None:
    scope_source = (ROOT / "ui" / "scope_page.py").read_text(encoding="utf-8")
    worker_source = (ROOT / "debugger" / "jlink_worker.py").read_text(encoding="utf-8")
    main_source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")

    banned_scope_tokens = (
        "GuiHeartbeatWatchdog",
        "AsyncDiagnosticWriter",
        "_event_loop_probe_timer",
        "_consume_gui_watchdog_captures",
        "_detect_python_debugger",
        "presentation starvation",
        "Scope presentation gap",
        "Scope PERF WARNING",
        "measured_paint_fps",
    )
    for token in banned_scope_tokens:
        assert token not in scope_source

    assert "scope_perf" not in worker_source
    assert "_on_scope_perf" not in main_source


def test_release_scope_keeps_product_timers_and_latency_guard() -> None:
    scope_source = (ROOT / "ui" / "scope_page.py").read_text(encoding="utf-8")
    worker_source = (ROOT / "debugger" / "jlink_worker.py").read_text(encoding="utf-8")

    assert "PresentationPacer" in scope_source
    assert "presentation_driver_interval_ms" not in scope_source
    assert "setSingleShot(True)" in scope_source
    assert "_arm_next_presentation" in scope_source
    assert "LiveLatencyGuard" in scope_source
    assert "self._hover_timer = QTimer(self)" in scope_source
    assert "self._scope_timer = QTimer(self)" in worker_source


def test_release_scope_has_no_hot_path_resize_diagnostic() -> None:
    scope_source = (ROOT / "ui" / "scope_page.py").read_text(encoding="utf-8")

    assert "Scope WARNING: live ring resize" not in scope_source
    assert "capacity_before = int(self._data.capacity)" not in scope_source
