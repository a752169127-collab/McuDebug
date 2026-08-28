from __future__ import annotations

import math


class PresentationPacer:
    """Absolute-deadline GUI presentation pacer.

    QTimer accepts integer milliseconds. A fixed ``int(1000/fps)`` interval
    overschedules high-refresh targets (144 Hz -> 6 ms -> 166.7 timer events/s)
    and lets Qt coalesce a varying number of requests, which produces uneven
    frame pacing. This helper keeps an absolute floating-point deadline and
    alternates integer millisecond delays as needed (for example 6/7 ms at
    144 Hz) while skipping missed deadlines instead of issuing catch-up bursts.
    """

    def __init__(self, fps: float = 60.0) -> None:
        self._fps = 60.0
        self._period_s = 1.0 / 60.0
        self._next_deadline: float | None = None
        self.set_fps(fps)

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def period_s(self) -> float:
        return self._period_s

    def set_fps(self, fps: float) -> None:
        fps = max(1.0, float(fps))
        self._fps = fps
        self._period_s = 1.0 / fps
        self._next_deadline = None

    def reset(self, now: float | None = None) -> None:
        self._next_deadline = None if now is None else float(now) + self._period_s

    def next_delay_ms(self, now: float) -> int:
        now = float(now)
        period = self._period_s
        if self._next_deadline is None:
            self._next_deadline = now + period
        elif self._next_deadline <= now:
            # Skip missed slots. Never schedule a burst of zero-delay catch-up
            # callbacks because that creates another form of visible judder.
            missed = math.floor((now - self._next_deadline) / period) + 1
            self._next_deadline += missed * period

        delay_s = max(0.001, self._next_deadline - now)
        # Round against the absolute deadline. The fractional remainder is kept
        # in _next_deadline, so 144 Hz naturally alternates 6/7 ms callbacks.
        delay_ms = max(1, int(round(delay_s * 1000.0)))
        self._next_deadline += period
        return delay_ms
