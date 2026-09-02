from __future__ import annotations

import math


class PresentationPacer:
    """Absolute-deadline helper for one single-shot Qt presentation timer.

    Qt timers accept integer millisecond delays, while common refresh targets
    such as 144 Hz have fractional periods.  The pacer keeps a floating-point
    absolute deadline and returns a positive integer delay for the next frame.
    Late callbacks skip missed slots instead of issuing catch-up bursts.

    The Release path therefore needs one timer callback per presentation frame
    rather than a faster persistent polling timer.
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
        """Return the next positive single-shot delay and advance one deadline."""
        now = float(now)
        period = self._period_s
        if self._next_deadline is None:
            self._next_deadline = now + period
        elif self._next_deadline <= now:
            missed = math.floor((now - self._next_deadline) / period) + 1
            self._next_deadline += missed * period

        delay_s = max(0.001, self._next_deadline - now)
        delay_ms = max(1, int(round(delay_s * 1000.0)))
        self._next_deadline += period
        return delay_ms
