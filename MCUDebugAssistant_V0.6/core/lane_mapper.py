from __future__ import annotations

import math
from typing import Iterable

import numpy as np


DEFAULT_MARGIN = 0.08


def lane_bounds(index: int, count: int, margin: float = DEFAULT_MARGIN) -> tuple[float, float, float, float]:
    """Return (lane_bottom, lane_top, inner_bottom, inner_top).

    Visual channel index 0 is the top lane. The shared ViewBox uses a simple
    world Y range [0, count], with higher Y toward the top of the canvas.
    """
    count = max(1, int(count))
    index = min(max(0, int(index)), count - 1)
    margin = min(max(0.0, float(margin)), 0.45)
    bottom = float(count - index - 1)
    top = bottom + 1.0
    return bottom, top, bottom + margin, top - margin


def lane_index_from_y(y: float, count: int) -> int | None:
    """Map shared ViewBox Y to the top-to-bottom visual lane index."""
    count = int(count)
    if count <= 0 or not math.isfinite(float(y)):
        return None
    # Keep clicks exactly on the top border inside the first lane.
    yy = min(max(float(y), 0.0), max(0.0, float(count) - 1e-12))
    bottom_based = int(math.floor(yy))
    return min(max(0, count - 1 - bottom_based), count - 1)


def _safe_range(y_range: tuple[float, float] | None) -> tuple[float, float]:
    if y_range is None:
        return -1.0, 1.0
    lo, hi = float(y_range[0]), float(y_range[1])
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return -1.0, 1.0
    if hi < lo:
        lo, hi = hi, lo
    if hi - lo <= 1e-15:
        pad = max(1.0, abs(lo) * 0.05)
        return lo - pad, hi + pad
    return lo, hi


def map_values_to_lane(
    values,
    y_range: tuple[float, float] | None,
    index: int,
    count: int,
    margin: float = DEFAULT_MARGIN,
):
    """Map display Y values into a fixed shared-ViewBox lane.

    Values outside the lane's fixed display range are clipped at the lane edge,
    matching the visual clipping behavior of the old independent ViewBoxes.
    """
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return arr
    lo, hi = _safe_range(y_range)
    _bottom, _top, inner_bottom, inner_top = lane_bounds(index, count, margin)
    scale = (inner_top - inner_bottom) / (hi - lo)
    mapped = inner_bottom + (arr - lo) * scale
    return np.clip(mapped, inner_bottom, inner_top)


def map_value_to_lane(
    value: float,
    y_range: tuple[float, float] | None,
    index: int,
    count: int,
    margin: float = DEFAULT_MARGIN,
) -> float:
    arr = map_values_to_lane(np.asarray([float(value)], dtype=np.float64), y_range, index, count, margin)
    return float(arr[0])


def unmap_value_from_lane(
    lane_y: float,
    y_range: tuple[float, float] | None,
    index: int,
    count: int,
    margin: float = DEFAULT_MARGIN,
) -> float:
    lo, hi = _safe_range(y_range)
    _bottom, _top, inner_bottom, inner_top = lane_bounds(index, count, margin)
    yy = min(max(float(lane_y), inner_bottom), inner_top)
    frac = (yy - inner_bottom) / max(1e-15, inner_top - inner_bottom)
    return lo + frac * (hi - lo)


def lane_axis_ticks(
    channel_ids: Iterable[int],
    names: dict[int, str],
    y_ranges: dict[int, tuple[float, float]],
    margin: float = DEFAULT_MARGIN,
) -> list[tuple[float, str]]:
    """Generate one shared AxisItem's ticks for all stacked lanes."""
    ids = [int(cid) for cid in channel_ids]
    count = len(ids)
    ticks: list[tuple[float, str]] = []
    for index, cid in enumerate(ids):
        _bottom, _top, inner_bottom, inner_top = lane_bounds(index, count, margin)
        lo, hi = _safe_range(y_ranges.get(cid))
        mid_pos = (inner_bottom + inner_top) * 0.5
        mid = (lo + hi) * 0.5
        name = str(names.get(cid, cid))
        short_name = name.split(".")[-1] if "." in name else name
        ticks.append((inner_top, f"{hi:.4g}"))
        ticks.append((mid_pos, f"{short_name} | {mid:.4g}"))
        ticks.append((inner_bottom, f"{lo:.4g}"))
    return ticks
