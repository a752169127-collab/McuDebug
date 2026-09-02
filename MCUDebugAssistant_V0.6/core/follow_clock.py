from __future__ import annotations


class FollowPresentationClock:
    """Jitter-buffered presentation clock for Scope live-follow.

    Acquisition workers often deliver timestamped samples in small bursts.  If
    the viewport snaps directly to ``last_x`` on each delivery, the user sees
    packet cadence rather than monitor cadence.  This clock estimates the
    mapping between target timestamps and host monotonic time, deliberately
    displays a small amount behind the newest sample, and lets the camera move
    continuously between packet deliveries.

    It never invents waveform samples.  It only returns a presentation X for the
    viewport.  The caller still clamps to the newest real sample.
    """

    def __init__(
        self,
        *,
        min_latency_s: float = 0.040,
        max_latency_s: float = 0.120,
        latency_multiplier: float = 1.8,
        interval_alpha: float = 0.15,
        offset_alpha: float = 0.08,
        max_offset_correction_s: float = 0.004,
    ) -> None:
        self.min_latency_s = float(min_latency_s)
        self.max_latency_s = float(max_latency_s)
        self.latency_multiplier = float(latency_multiplier)
        self.interval_alpha = float(interval_alpha)
        self.offset_alpha = float(offset_alpha)
        self.max_offset_correction_s = float(max_offset_correction_s)
        self.reset()

    def reset(self) -> None:
        self._offset_s: float | None = None
        self._arrival_interval_s: float | None = None
        self._last_arrival_wall: float | None = None
        self._last_data_x: float | None = None

    @property
    def arrival_interval_s(self) -> float | None:
        return self._arrival_interval_s

    @property
    def presentation_latency_s(self) -> float:
        interval = self._arrival_interval_s
        if interval is None or interval <= 0.0:
            return self.min_latency_s
        latency = interval * self.latency_multiplier
        return max(self.min_latency_s, min(self.max_latency_s, latency))

    def observe(self, data_x: float, wall_now: float) -> None:
        data_x = float(data_x)
        wall_now = float(wall_now)

        if self._last_arrival_wall is not None:
            dt = wall_now - self._last_arrival_wall
            if 0.0 < dt < 1.0:
                if self._arrival_interval_s is None:
                    self._arrival_interval_s = dt
                else:
                    a = self.interval_alpha
                    self._arrival_interval_s = (1.0 - a) * self._arrival_interval_s + a * dt

        observed_offset = wall_now - data_x
        if self._offset_s is None:
            self._offset_s = observed_offset
        else:
            # PLL-like slow phase correction: packet jitter cannot yank the
            # presentation camera by a large amount on a single delivery.
            error = observed_offset - self._offset_s
            correction = self.offset_alpha * error
            limit = self.max_offset_correction_s
            correction = max(-limit, min(limit, correction))
            self._offset_s += correction

        self._last_arrival_wall = wall_now
        self._last_data_x = data_x

    def visual_right(self, newest_real_x: float, wall_now: float, latency_floor_s: float = 0.0) -> float:
        newest_real_x = float(newest_real_x)
        wall_now = float(wall_now)
        if self._offset_s is None:
            return newest_real_x
        predicted_stream_x = wall_now - self._offset_s
        latency = max(self.presentation_latency_s, max(0.0, float(latency_floor_s)))
        latency = min(self.max_latency_s, latency)
        presentation_x = predicted_stream_x - latency
        # Never move beyond a real captured sample.  If acquisition genuinely
        # stalls longer than the jitter buffer, the camera waits at the tail.
        return min(newest_real_x, presentation_x)
