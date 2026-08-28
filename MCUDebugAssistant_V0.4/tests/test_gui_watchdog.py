from __future__ import annotations

import threading
import time

from core.gui_watchdog import GuiHeartbeatWatchdog


def test_watchdog_captures_stale_gui_stack() -> None:
    watchdog = GuiHeartbeatWatchdog(threshold_ms=40, poll_ms=5, max_samples_per_episode=2)
    watchdog.start(gui_thread_id=threading.get_ident())
    try:
        # Deliberately stop beating while this test thread remains in Python.
        deadline = time.perf_counter() + 0.16
        while time.perf_counter() < deadline:
            # sleep releases the GIL so the watchdog can sample this thread.
            time.sleep(0.01)
        captures = watchdog.pop_captures()
        assert captures
        assert captures[0].stale_ms >= 35.0
        assert captures[0].gui_thread_id == threading.get_ident()
        assert captures[0].gui_stack
    finally:
        watchdog.stop()


def test_watchdog_beat_resets_episode() -> None:
    watchdog = GuiHeartbeatWatchdog(threshold_ms=35, poll_ms=5, max_samples_per_episode=1)
    watchdog.start(gui_thread_id=threading.get_ident())
    try:
        time.sleep(0.07)
        first = watchdog.pop_captures()
        assert first
        watchdog.beat()
        time.sleep(0.01)
        assert watchdog.pop_captures() == []
        time.sleep(0.06)
        second = watchdog.pop_captures()
        assert second
    finally:
        watchdog.stop()
