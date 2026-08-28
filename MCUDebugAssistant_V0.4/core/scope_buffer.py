from __future__ import annotations

import math
from typing import Iterable, Iterator

import numpy as np


class ScopeDataStore:
    """Preallocated NumPy ring buffer used by Scope Rendering V2.

    V0.3.x used a chunk deque to avoid repeated full-history ``np.concatenate``.
    That solved the worst long-run copy amplification, but rendering still had to
    walk/merge chunks before every viewport redraw. V0.4 moves the retained raw
    capture into a true circular buffer:

    * append is O(new samples), with no history movement;
    * trimming advances a logical start index instead of slicing old arrays;
    * a viewport intersects at most two contiguous physical slices;
    * raw statistics remain independent from the rolling display buffer;
    * display decimation remains anchored to absolute acquisition indices.

    The public API intentionally matches the V0.3 ScopeDataStore so the J-Link,
    HSS/RTT, cursor, export and statistics layers do not need to change.
    """

    _INITIAL_CAPACITY = 4096

    def __init__(self, seconds: float = 30.0, max_points: int = 1_500_000) -> None:
        self.seconds = max(1.0, float(seconds))
        self.max_points = max(1, int(max_points))
        self.x_is_time = True

        self._capacity = min(self.max_points, self._INITIAL_CAPACITY)
        self._x = np.empty(self._capacity, dtype=np.float64)
        self._absolute_index = np.empty(self._capacity, dtype=np.int64)
        self._values: dict[int, np.ndarray] = {}
        self._start = 0
        self._size = 0
        self._next_sample_index = 0

        # Statistics are session statistics (since clear/start), not rolling
        # buffer statistics. This matches the established Watch/Scope semantics.
        self._stats: dict[int, dict[str, float | int | None]] = {}

        # Buffer extrema are lazy because they are needed mainly for View All.
        self._extrema_cache: dict[int, tuple[float, float] | None] = {}
        self._revision = 0

    # ---------- Basic properties ----------
    @property
    def sample_count(self) -> int:
        return int(self._size)

    @property
    def has_data(self) -> bool:
        return self._size > 0

    @property
    def revision(self) -> int:
        """Monotonic mutation counter for render-cache diagnostics."""
        return int(self._revision)

    @property
    def first_x(self) -> float | None:
        if self._size <= 0:
            return None
        return float(self._x[self._start])

    @property
    def last_x(self) -> float | None:
        if self._size <= 0:
            return None
        return float(self._x[self._physical_index(self._size - 1)])

    @property
    def channel_ids(self) -> set[int]:
        return set(self._values)

    @property
    def capacity(self) -> int:
        return int(self._capacity)

    def set_seconds(self, seconds: float) -> None:
        self.seconds = max(1.0, float(seconds))
        self._trim_time_window()

    def clear(self) -> None:
        self._start = 0
        self._size = 0
        self._next_sample_index = 0
        self._stats = {}
        self._extrema_cache = {}
        self._revision += 1

    def reserve_capacity(self, required: int, channel_ids: Iterable[int] = ()) -> int:
        """Preallocate a complete live-capture ring outside the hot path.

        V0.4.14 still started at 4096 samples and doubled the ring in
        ``append()``.  ``append_samples()`` runs in the GUI thread, so a capacity
        boundary could allocate/copy X plus every channel while the 144 Hz
        presentation loop was active.  Reserve the expected session footprint
        before acquisition begins so steady-state append never reallocates.
        """
        target = min(self.max_points, max(1, int(required)))
        self._ensure_capacity(target)
        for raw_cid in channel_ids:
            cid = int(raw_cid)
            arr = self._values.get(cid)
            if arr is None:
                self._values[cid] = np.full(self._capacity, np.nan, dtype=np.float64)
            elif arr.size != self._capacity:
                replacement = np.full(self._capacity, np.nan, dtype=np.float64)
                old = self._materialize_channel(cid)
                replacement[: old.size] = old
                self._values[cid] = replacement
        return int(self._capacity)

    # ---------- Ring helpers ----------
    def _physical_index(self, logical_offset: int) -> int:
        return (self._start + int(logical_offset)) % self._capacity

    def _segments(self, logical_start: int = 0, logical_stop: int | None = None):
        """Yield physical slices for [logical_start, logical_stop)."""
        start = max(0, int(logical_start))
        stop = self._size if logical_stop is None else min(self._size, max(start, int(logical_stop)))
        count = stop - start
        if count <= 0:
            return
        physical = self._physical_index(start)
        first_count = min(count, self._capacity - physical)
        yield slice(physical, physical + first_count), start
        remain = count - first_count
        if remain > 0:
            yield slice(0, remain), start + first_count

    def _ensure_capacity(self, required: int) -> None:
        required = min(self.max_points, max(1, int(required)))
        if required <= self._capacity:
            return
        new_capacity = self._capacity
        while new_capacity < required:
            new_capacity = min(self.max_points, max(new_capacity * 2, required))
            if new_capacity == self._capacity:
                break

        old_x, old_abs = self._materialize_base()
        old_values = {cid: self._materialize_channel(cid) for cid in self._values}

        self._capacity = int(new_capacity)
        self._x = np.empty(self._capacity, dtype=np.float64)
        self._absolute_index = np.empty(self._capacity, dtype=np.int64)
        self._values = {cid: np.full(self._capacity, np.nan, dtype=np.float64) for cid in old_values}
        self._start = 0
        if self._size:
            self._x[: self._size] = old_x
            self._absolute_index[: self._size] = old_abs
            for cid, arr in old_values.items():
                self._values[cid][: self._size] = arr

    def _materialize_base(self) -> tuple[np.ndarray, np.ndarray]:
        if self._size <= 0:
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.int64)
        x_parts = []
        i_parts = []
        for sl, _ in self._segments():
            x_parts.append(self._x[sl])
            i_parts.append(self._absolute_index[sl])
        if len(x_parts) == 1:
            return x_parts[0].copy(), i_parts[0].copy()
        return np.concatenate(x_parts), np.concatenate(i_parts)

    def _materialize_channel(self, channel_id: int) -> np.ndarray:
        cid = int(channel_id)
        arr = self._values.get(cid)
        if arr is None or self._size <= 0:
            return np.full(self._size, np.nan, dtype=np.float64)
        parts = [arr[sl] for sl, _ in self._segments()]
        if len(parts) == 1:
            return parts[0].copy()
        return np.concatenate(parts)

    def _drop_left(self, count: int) -> None:
        count = min(self._size, max(0, int(count)))
        if count <= 0:
            return
        self._start = self._physical_index(count)
        self._size -= count
        self._extrema_cache.clear()
        self._revision += 1

    def _trim_time_window(self) -> None:
        if not self.x_is_time or self._size <= 1 or self.last_x is None:
            return
        cutoff = float(self.last_x) - float(self.seconds)
        # Old samples are removed exactly once over their lifetime. A simple
        # head advance is amortized O(new samples) and avoids materializing X.
        drop = 0
        while drop < self._size:
            idx = self._physical_index(drop)
            if float(self._x[idx]) >= cutoff:
                break
            drop += 1
        if drop:
            self._drop_left(drop)

    # ---------- Append / statistics ----------
    @staticmethod
    def _estimate_step(x_new: np.ndarray, previous_tail: np.ndarray | None = None) -> float:
        if x_new.size >= 2:
            diffs = np.diff(x_new)
            positive = diffs[diffs > 0]
            if positive.size:
                return float(np.median(positive))
        if previous_tail is not None and previous_tail.size >= 2:
            diffs = np.diff(previous_tail)
            positive = diffs[diffs > 0]
            if positive.size:
                return float(np.median(positive))
        return 1e-6

    def append(self, times, values: dict[int, list], x_is_time: bool) -> None:
        x_new = np.asarray(times, dtype=np.float64).reshape(-1)
        if x_new.size == 0:
            return
        self.x_is_time = bool(x_is_time)

        # HSS/RTT resume can restart target timestamps at zero. Preserve the
        # established monotonic session-X behavior by shifting the new block.
        last = self.last_x
        if last is not None and float(x_new[0]) <= float(last):
            previous_tail = None
            if self._size >= 2:
                previous_tail = np.asarray([
                    self._x[self._physical_index(self._size - 2)],
                    self._x[self._physical_index(self._size - 1)],
                ], dtype=np.float64)
            step = self._estimate_step(x_new, previous_tail)
            x_new = x_new + (float(last) + step - float(x_new[0]))

        # If one worker delivery is larger than the maximum retained buffer,
        # only its newest tail can survive anyway.
        if x_new.size > self.max_points:
            keep = self.max_points
            x_new = x_new[-keep:]
            values = {int(cid): list(seq)[-keep:] for cid, seq in values.items()}

        n = int(x_new.size)
        self._ensure_capacity(min(self.max_points, self._size + n))

        # When the ring is full, discard exactly the number of oldest samples
        # that the new block will overwrite.
        overflow = max(0, self._size + n - self._capacity)
        if overflow:
            self._drop_left(overflow)

        value_arrays: dict[int, np.ndarray] = {}
        for raw_cid, seq in values.items():
            cid = int(raw_cid)
            arr = np.asarray(seq, dtype=np.float64).reshape(-1)
            if arr.size != n:
                padded = np.full(n, np.nan, dtype=np.float64)
                padded[: min(arr.size, n)] = arr[:n]
                arr = padded
            value_arrays[cid] = arr
            self._update_stats(cid, arr)
            if cid not in self._values:
                self._values[cid] = np.full(self._capacity, np.nan, dtype=np.float64)

        # New capacity may have been allocated before a new channel was seen;
        # existing channel arrays must always match the ring capacity.
        for cid, arr in list(self._values.items()):
            if arr.size != self._capacity:
                replacement = np.full(self._capacity, np.nan, dtype=np.float64)
                old = self._materialize_channel(cid)
                replacement[: old.size] = old
                self._values[cid] = replacement

        write_logical = self._size
        remaining = n
        src = 0
        while remaining > 0:
            physical = self._physical_index(write_logical)
            count = min(remaining, self._capacity - physical)
            sl = slice(physical, physical + count)
            self._x[sl] = x_new[src : src + count]
            self._absolute_index[sl] = np.arange(
                self._next_sample_index + src,
                self._next_sample_index + src + count,
                dtype=np.int64,
            )
            for cid, ring in self._values.items():
                incoming = value_arrays.get(cid)
                if incoming is None:
                    ring[sl] = np.nan
                else:
                    ring[sl] = incoming[src : src + count]
            src += count
            remaining -= count
            write_logical += count

        self._size += n
        self._next_sample_index += n
        self._extrema_cache.clear()
        self._revision += 1
        self._trim_time_window()

    def _update_stats(self, channel_id: int, values: np.ndarray) -> None:
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return
        cid = int(channel_id)
        state = self._stats.setdefault(cid, {
            "count": 0,
            "sum": 0.0,
            "current": None,
            "minimum": None,
            "maximum": None,
        })
        state["count"] = int(state["count"]) + int(finite.size)
        state["sum"] = float(state["sum"]) + float(np.sum(finite, dtype=np.float64))
        state["current"] = float(finite[-1])
        lo = float(np.min(finite))
        hi = float(np.max(finite))
        state["minimum"] = lo if state["minimum"] is None else min(float(state["minimum"]), lo)
        state["maximum"] = hi if state["maximum"] is None else max(float(state["maximum"]), hi)

    def stats_snapshot(self) -> dict[int, dict]:
        result: dict[int, dict] = {}
        for cid, state in self._stats.items():
            count = int(state["count"])
            result[int(cid)] = {
                "count": count,
                "current": state["current"],
                "average": (float(state["sum"]) / count) if count else None,
                "minimum": state["minimum"],
                "maximum": state["maximum"],
            }
        return result

    # ---------- Rolling-buffer extrema ----------
    def buffer_extrema(self, channel_id: int) -> tuple[float, float] | None:
        cid = int(channel_id)
        if cid in self._extrema_cache:
            return self._extrema_cache[cid]
        if cid not in self._values or self._size <= 0:
            self._extrema_cache[cid] = None
            return None
        lo = math.inf
        hi = -math.inf
        found = False
        ring = self._values[cid]
        for sl, _ in self._segments():
            part = ring[sl]
            finite = part[np.isfinite(part)]
            if finite.size:
                found = True
                lo = min(lo, float(np.min(finite)))
                hi = max(hi, float(np.max(finite)))
        result = (lo, hi) if found else None
        self._extrema_cache[cid] = result
        return result

    # ---------- Rendering ----------
    def _window_parts(self, channel_id: int, x_range: tuple[float, float] | None):
        cid = int(channel_id)
        ring = self._values.get(cid)
        low = high = None
        if x_range is not None:
            try:
                low, high = float(x_range[0]), float(x_range[1])
                if not (math.isfinite(low) and math.isfinite(high) and high > low):
                    low = high = None
            except Exception:
                low = high = None

        for sl, logical_base in self._segments():
            xs_all = self._x[sl]
            if xs_all.size == 0:
                continue
            if low is not None and high is not None:
                if float(xs_all[-1]) < low or float(xs_all[0]) > high:
                    continue
                a = int(np.searchsorted(xs_all, low, side="left"))
                b = int(np.searchsorted(xs_all, high, side="right"))
            else:
                a, b = 0, int(xs_all.size)
            if b <= a:
                continue
            xs = xs_all[a:b]
            abs_idx = self._absolute_index[sl][a:b]
            if ring is None:
                ys = np.full(xs.size, np.nan, dtype=np.float64)
            else:
                ys = ring[sl][a:b]
            yield xs, ys, abs_idx

    def curve(
        self,
        channel_id: int,
        display_limit: int = 10_000,
        x_range: tuple[float, float] | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        if self._size <= 0:
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
        parts = list(self._window_parts(channel_id, x_range))
        if not parts:
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
        if len(parts) == 1:
            x, y, absolute = parts[0]
        else:
            x = np.concatenate([p[0] for p in parts])
            y = np.concatenate([p[1] for p in parts])
            absolute = np.concatenate([p[2] for p in parts])
        limit = max(4, int(display_limit))
        if x.size <= limit:
            return x, y
        return self._peak_preserving_downsample(x, y, absolute, limit)

    @staticmethod
    def _peak_preserving_downsample(
        x: np.ndarray,
        y: np.ndarray,
        absolute_index: np.ndarray,
        display_limit: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Phase-stable min/max envelope with a vectorized contiguous fast path."""
        n = int(x.size)
        limit = max(4, int(display_limit))
        if n <= limit:
            return x, y

        bucket_size = max(2, int(math.ceil((2.0 * n) / float(limit))))
        if n >= 2 and np.all(np.diff(absolute_index) == 1):
            first_abs = int(absolute_index[0])
            last_exclusive_abs = int(absolute_index[-1]) + 1
            first_aligned_abs = ((first_abs + bucket_size - 1) // bucket_size) * bucket_size
            last_aligned_abs = (last_exclusive_abs // bucket_size) * bucket_size
            mid_start = max(0, first_aligned_abs - first_abs)
            mid_stop = max(mid_start, min(n, last_aligned_abs - first_abs))
            pieces: list[np.ndarray] = []

            def partial_indices(start: int, stop: int) -> np.ndarray:
                if stop <= start:
                    return np.empty(0, dtype=np.int64)
                ys = y[start:stop]
                finite = np.flatnonzero(np.isfinite(ys))
                if finite.size == 0:
                    return np.asarray([start], dtype=np.int64)
                vals = ys[finite]
                a = start + int(finite[int(np.argmin(vals))])
                b = start + int(finite[int(np.argmax(vals))])
                if a == b:
                    return np.asarray([a], dtype=np.int64)
                return np.asarray(sorted((a, b)), dtype=np.int64)

            if mid_start > 0:
                pieces.append(partial_indices(0, mid_start))

            mid_len = mid_stop - mid_start
            if mid_len >= bucket_size:
                rows = mid_len // bucket_size
                matrix = y[mid_start : mid_start + rows * bucket_size].reshape(rows, bucket_size)
                finite = np.isfinite(matrix)
                row_valid = np.any(finite, axis=1)
                min_matrix = np.where(finite, matrix, np.inf)
                max_matrix = np.where(finite, matrix, -np.inf)
                min_local = np.argmin(min_matrix, axis=1)
                max_local = np.argmax(max_matrix, axis=1)
                row_base = mid_start + np.arange(rows, dtype=np.int64) * bucket_size
                min_idx = row_base + min_local.astype(np.int64)
                max_idx = row_base + max_local.astype(np.int64)
                lo = np.minimum(min_idx, max_idx)
                hi = np.maximum(min_idx, max_idx)
                pair = np.empty(rows * 2, dtype=np.int64)
                pair[0::2] = lo
                pair[1::2] = hi
                if not np.all(row_valid):
                    pair_rows = pair.reshape(rows, 2)
                    invalid_rows = np.flatnonzero(~row_valid)
                    pair_rows[invalid_rows, 0] = row_base[invalid_rows]
                    pair_rows[invalid_rows, 1] = row_base[invalid_rows]
                pieces.append(pair)

            if mid_stop < n:
                pieces.append(partial_indices(mid_stop, n))

            if pieces:
                idx = np.concatenate(pieces)
                if idx.size >= 2:
                    keep = np.concatenate(([True], idx[1:] != idx[:-1]))
                    idx = idx[keep]
                if idx.size > limit:
                    select = np.linspace(0, idx.size - 1, limit, dtype=np.int64)
                    idx = idx[select]
                return x[idx], y[idx]

        bucket_ids = absolute_index // bucket_size
        boundaries = np.flatnonzero(np.diff(bucket_ids)) + 1
        starts = np.concatenate(([0], boundaries))
        stops = np.concatenate((boundaries, [n]))
        indices: list[int] = []
        for start, stop in zip(starts.tolist(), stops.tolist()):
            ys = y[start:stop]
            finite = np.flatnonzero(np.isfinite(ys))
            if finite.size == 0:
                indices.append(start)
                continue
            vals = ys[finite]
            a = start + int(finite[int(np.argmin(vals))])
            b = start + int(finite[int(np.argmax(vals))])
            if a == b:
                indices.append(a)
            elif a < b:
                indices.extend((a, b))
            else:
                indices.extend((b, a))
        idx = np.asarray(indices, dtype=np.int64)
        if idx.size > limit:
            select = np.linspace(0, idx.size - 1, limit, dtype=np.int64)
            idx = idx[select]
        return x[idx], y[idx]

    # ---------- Lookup / export ----------
    def nearest(self, channel_id: int, x_value: float) -> tuple[float, float] | None:
        if self._size <= 0:
            return None
        cid = int(channel_id)
        ring = self._values.get(cid)
        best: tuple[float, float, float] | None = None  # distance, x, y
        for sl, _ in self._segments():
            xs = self._x[sl]
            if xs.size == 0:
                continue
            pos = int(np.searchsorted(xs, float(x_value), side="left"))
            for local in (pos - 1, pos):
                if local < 0 or local >= xs.size:
                    continue
                y = np.nan if ring is None else float(ring[sl][local])
                if not math.isfinite(y):
                    continue
                xv = float(xs[local])
                cand = (abs(xv - float(x_value)), xv, y)
                if best is None or cand[0] < best[0]:
                    best = cand
        if best is None:
            return None
        return best[1], best[2]

    def iter_rows(self, channel_ids: Iterable[int]) -> Iterator[tuple[float, list[float | None]]]:
        ids = [int(cid) for cid in channel_ids]
        for sl, _ in self._segments():
            xs = self._x[sl]
            channel_parts = {cid: self._values.get(cid) for cid in ids}
            for i, xv in enumerate(xs):
                row: list[float | None] = []
                for cid in ids:
                    arr = channel_parts[cid]
                    if arr is None:
                        row.append(None)
                        continue
                    value = float(arr[sl][i])
                    row.append(value if math.isfinite(value) else None)
                yield float(xv), row

    def chunk_count(self) -> int:
        """Compatibility diagnostic: a ring has one or two physical segments."""
        if self._size <= 0:
            return 0
        return 1 if self._start + self._size <= self._capacity else 2

    def materialize(self, channel_id: int) -> tuple[np.ndarray, np.ndarray]:
        x, _ = self._materialize_base()
        return x, self._materialize_channel(int(channel_id))
