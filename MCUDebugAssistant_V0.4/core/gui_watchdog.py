from __future__ import annotations

"""Out-of-band GUI heartbeat watchdog.

The ordinary Scope profiler measures work *inside* GUI callbacks.  A long gap
between two presentation ticks can still happen while the GUI thread is blocked
in some other Python callback, inside a native Qt call, or while the whole
process is temporarily not scheduled.  This watchdog samples the Python stack
from a separate daemon thread whenever the GUI heartbeat becomes stale.

It intentionally does not touch Qt objects from the watchdog thread.  Captures
are stored in a small thread-safe deque and consumed/logged later by the GUI
thread after it resumes.
"""

from collections import deque
from dataclasses import dataclass
import sys
import threading
import time
import traceback
from typing import Iterable


@dataclass(frozen=True)
class GuiWatchdogCapture:
    stale_ms: float
    detected_at: float
    gui_thread_id: int
    gui_stack: tuple[str, ...]
    gui_top: str
    classification: str
    watchdog_poll_gap_ms: float
    other_thread_tops: tuple[str, ...]


class GuiHeartbeatWatchdog:
    """Sample the GUI Python stack while presentation heartbeats are stale."""

    def __init__(self, *, threshold_ms: float = 120.0, poll_ms: float = 20.0, max_samples_per_episode: int = 4) -> None:
        self.threshold_s = max(0.050, float(threshold_ms) / 1000.0)
        self.poll_s = max(0.005, float(poll_ms) / 1000.0)
        self.max_samples_per_episode = max(1, int(max_samples_per_episode))
        self._lock = threading.Lock()
        self._heartbeat = 0.0
        self._gui_thread_id = 0
        self._active = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._captures: deque[GuiWatchdogCapture] = deque(maxlen=16)
        self._episode_samples = 0
        self._episode_active = False
        self._last_sample_at = 0.0
        self._max_poll_gap_ms = 0.0

    def start(self, gui_thread_id: int | None = None) -> None:
        with self._lock:
            self._gui_thread_id = int(gui_thread_id or threading.get_ident())
            self._heartbeat = time.perf_counter()
            self._active = True
            self._episode_samples = 0
            self._episode_active = False
            self._last_sample_at = 0.0
            self._max_poll_gap_ms = 0.0
            self._captures.clear()
        self._stop_event.clear()
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="ScopeGuiWatchdog", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._active = False
        self._stop_event.set()

    def beat(self, now: float | None = None) -> None:
        t = float(now if now is not None else time.perf_counter())
        with self._lock:
            self._heartbeat = t
            self._episode_samples = 0
            self._episode_active = False
            self._last_sample_at = 0.0

    def pop_captures(self) -> list[GuiWatchdogCapture]:
        with self._lock:
            out = list(self._captures)
            self._captures.clear()
            return out

    def max_poll_gap_ms(self) -> float:
        with self._lock:
            return float(self._max_poll_gap_ms)

    @staticmethod
    def _format_stack(frame, limit: int = 12) -> tuple[str, ...]:
        if frame is None:
            return ()
        try:
            extracted = traceback.extract_stack(frame, limit=limit)
        except Exception:
            return ()
        lines: list[str] = []
        for item in extracted:
            filename = item.filename.replace("\\", "/")
            lines.append(f"{filename}:{item.lineno} in {item.name}: {item.line or ''}".strip())
        return tuple(lines)

    @staticmethod
    def _classify(stack: Iterable[str]) -> str:
        text = "\n".join(stack)
        probes = (
            ("paintEvent", "qt-paint"),
            ("append_samples", "scope-append"),
            ("_render_if_dirty", "scope-render"),
            ("_follow_latest", "scope-follow"),
            ("_viewport_tick", "scope-presentation"),
            ("_canvas_mouse_moved", "scope-mouse"),
            ("_refresh_hover_probe", "scope-hover"),
            ("_update_hover_tooltip", "scope-hover"),
            ("appendPlainText", "log-widget"),
            ("exec()", "qt-native-event-loop"),
            ("app.exec", "qt-native-event-loop"),
        )
        for needle, label in probes:
            if needle in text:
                return label
        # A GUI thread blocked in Qt's native event loop normally exposes only
        # main.py -> app.exec() as its Python frame.  Keep a separate fallback
        # label for a stack that contains no Scope/UI callback at all.
        if stack and not any("/ui/" in line or "scope_page.py" in line for line in stack):
            return "outside-python-scope"
        return "other-python"

    @staticmethod
    def _thread_name_map() -> dict[int, str]:
        result: dict[int, str] = {}
        try:
            for thread in threading.enumerate():
                if thread.ident is not None:
                    result[int(thread.ident)] = str(thread.name)
        except Exception:
            pass
        return result

    def _capture(self, stale_s: float, now: float, poll_gap_ms: float) -> None:
        with self._lock:
            gui_tid = int(self._gui_thread_id)
        try:
            frames = sys._current_frames()
        except Exception:
            frames = {}
        gui_frame = frames.get(gui_tid)
        gui_stack = self._format_stack(gui_frame)
        gui_top = gui_stack[-1] if gui_stack else "<no Python frame>"
        classification = self._classify(gui_stack)

        names = self._thread_name_map()
        other: list[str] = []
        for tid, frame in frames.items():
            if int(tid) == gui_tid or threading.current_thread().ident == tid:
                continue
            stack = self._format_stack(frame, limit=5)
            top = stack[-1] if stack else "<no Python frame>"
            other.append(f"{names.get(int(tid), 'thread')}[{int(tid)}]: {top}")
            if len(other) >= 5:
                break

        capture = GuiWatchdogCapture(
            stale_ms=float(stale_s * 1000.0),
            detected_at=float(now),
            gui_thread_id=gui_tid,
            gui_stack=gui_stack,
            gui_top=gui_top,
            classification=classification,
            watchdog_poll_gap_ms=float(poll_gap_ms),
            other_thread_tops=tuple(other),
        )
        with self._lock:
            self._captures.append(capture)

    def _run(self) -> None:
        last_poll = time.perf_counter()
        while not self._stop_event.wait(self.poll_s):
            now = time.perf_counter()
            poll_gap_ms = max(0.0, (now - last_poll) * 1000.0)
            last_poll = now
            with self._lock:
                self._max_poll_gap_ms = max(self._max_poll_gap_ms, poll_gap_ms)
                active = bool(self._active)
                heartbeat = float(self._heartbeat)
                episode_samples = int(self._episode_samples)
                last_sample_at = float(self._last_sample_at)
            if not active or heartbeat <= 0.0:
                continue
            stale_s = now - heartbeat
            if stale_s < self.threshold_s:
                continue
            # During one stall take a few samples, spaced far enough apart to
            # reveal whether the GUI remains in the same frame or changes state.
            if episode_samples >= self.max_samples_per_episode:
                continue
            if last_sample_at > 0.0 and now - last_sample_at < 0.080:
                continue
            self._capture(stale_s, now, poll_gap_ms)
            with self._lock:
                self._episode_active = True
                self._episode_samples += 1
                self._last_sample_at = now
