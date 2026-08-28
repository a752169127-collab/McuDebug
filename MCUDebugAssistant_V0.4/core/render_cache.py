from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

import numpy as np


@dataclass
class ChannelRenderData:
    x: np.ndarray
    y: np.ndarray


@dataclass
class ScopeRenderCache:
    """Viewport-adjacent raw display cache.

    The cache deliberately stores *raw* channel Y values. Gain/Offset are a
    cheap presentation transform and therefore do not invalidate expensive raw
    buffer slicing/downsampling.

    A cache normally spans several viewport widths. Panning inside that span is
    then a pure ViewBox transform: no ScopeDataStore.curve() and no setData().
    The cache is rebuilt only when the viewport approaches/leaves its margin,
    when channel definitions change, or when live acquisition advances beyond
    the cached right edge.
    """

    low: float | None = None
    high: float | None = None
    channels: dict[int, ChannelRenderData] = field(default_factory=dict)
    source_first_x: float | None = None
    source_last_x: float | None = None
    build_count: int = 0
    view_span: float | None = None

    def clear(self) -> None:
        self.low = None
        self.high = None
        self.channels.clear()
        self.source_first_x = None
        self.source_last_x = None
        self.view_span = None

    @property
    def valid(self) -> bool:
        return self.low is not None and self.high is not None and self.high > self.low

    def covers(self, x_range: tuple[float, float] | None, channel_ids: Iterable[int]) -> bool:
        if not self.valid or x_range is None:
            return False
        try:
            low, high = float(x_range[0]), float(x_range[1])
        except Exception:
            return False
        if not (math.isfinite(low) and math.isfinite(high) and high > low):
            return False
        if low < float(self.low) or high > float(self.high):
            return False
        return all(int(cid) in self.channels for cid in channel_ids)

    def margin_contains(self, x_range: tuple[float, float] | None, fraction: float = 0.18) -> bool:
        """Whether the viewport stays comfortably away from cache edges."""
        if not self.valid or x_range is None:
            return False
        low, high = map(float, x_range)
        cache_span = float(self.high) - float(self.low)
        if cache_span <= 0:
            return False
        pad = cache_span * max(0.0, min(0.45, float(fraction)))
        return low >= float(self.low) + pad and high <= float(self.high) - pad

    def build(
        self,
        store,
        channel_ids: Iterable[int],
        x_range: tuple[float, float],
        display_limit_per_channel: int,
        margin_spans: float = 1.25,
    ) -> None:
        low, high = map(float, x_range)
        if not (math.isfinite(low) and math.isfinite(high) and high > low):
            self.clear()
            return
        span = high - low
        margin = max(0.0, float(margin_spans)) * span
        data_low = store.first_x
        data_high = store.last_x
        cache_low = low - margin
        cache_high = high + margin
        if data_low is not None:
            cache_low = max(cache_low, float(data_low))
        if data_high is not None:
            cache_high = min(cache_high, float(data_high))
        if cache_high <= cache_low:
            cache_low, cache_high = low, high

        ids = [int(cid) for cid in channel_ids]
        channels: dict[int, ChannelRenderData] = {}
        # V0.4.11 steady-state geometry rule:
        #
        # The old renderer multiplied the PlotCurveItem point budget by the
        # cache/view width ratio.  That meant a fresh capture started with only
        # a few hundred drawable points, then silently grew to several thousand
        # points/channel once the prefetch cache had enough history.  Raw Ring
        # Buffer usage was bounded, but QPainter work per frame was not, causing
        # the characteristic "starts near 140 FPS, later settles near 50 FPS".
        #
        # Keep a small fixed guard above the viewport pixel budget instead.  Raw
        # data is still fully retained in ScopeDataStore; only presentation
        # geometry is capped. Peak-preserving reduction protects extrema.
        limit = max(64, min(50_000, int(display_limit_per_channel * 1.35)))
        for cid in ids:
            x, y = store.curve(cid, display_limit=limit, x_range=(cache_low, cache_high))
            channels[cid] = ChannelRenderData(x=x, y=y)

        self.low = float(cache_low)
        self.high = float(cache_high)
        self.channels = channels
        self.source_first_x = store.first_x
        self.source_last_x = store.last_x
        self.view_span = float(span)
        self.build_count += 1

    def channel(self, channel_id: int) -> tuple[np.ndarray, np.ndarray]:
        item = self.channels.get(int(channel_id))
        if item is None:
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
        return item.x, item.y
