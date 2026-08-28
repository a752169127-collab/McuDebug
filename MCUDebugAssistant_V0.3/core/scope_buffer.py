from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import bisect
import math
from typing import Iterable, Iterator

import numpy as np


@dataclass
class _ScopeChunk:
    x: np.ndarray
    values: dict[int, np.ndarray]
    minima: dict[int, float]
    maxima: dict[int, float]
    level: int = 0
    # Absolute acquisition sample index of x[0].  It never changes when the
    # rolling buffer trims its left edge, so display decimation stays phase-
    # stable instead of visibly "breathing" as old samples are discarded.
    start_index: int = 0

    @property
    def size(self) -> int:
        return int(self.x.size)

    @property
    def first_x(self) -> float:
        return float(self.x[0])

    @property
    def last_x(self) -> float:
        return float(self.x[-1])

    @classmethod
    def create(
        cls,
        x: np.ndarray,
        values: dict[int, np.ndarray],
        level: int = 0,
        start_index: int = 0,
    ) -> "_ScopeChunk":
        minima: dict[int, float] = {}
        maxima: dict[int, float] = {}
        for cid, arr in values.items():
            finite = arr[np.isfinite(arr)]
            if finite.size:
                minima[int(cid)] = float(np.min(finite))
                maxima[int(cid)] = float(np.max(finite))
        return cls(x=x, values=values, minima=minima, maxima=maxima, level=int(level), start_index=int(start_index))

    def sliced(self, start: int) -> "_ScopeChunk | None":
        start = max(0, int(start))
        if start <= 0:
            return self
        if start >= self.size:
            return None
        values = {cid: arr[start:] for cid, arr in self.values.items()}
        return _ScopeChunk.create(self.x[start:], values, level=self.level, start_index=self.start_index + start)


class ScopeDataStore:
    """Chunked Scope history optimized for long-running acquisition.

    Previous V0.3.x versions kept one growing NumPy array per signal and called
    ``np.concatenate`` for every acquisition chunk. Once the buffer reached
    hundreds of thousands of samples this turned every append into an O(N)
    full-buffer copy, so CPU and memory traffic increased continuously with run
    time.  Switching Stacked/Overlay or fitting all curves then happened while
    the UI was already under heavy copy pressure and could appear to freeze.

    This implementation stores acquisition chunks in a deque. Appending is O(new
    samples), trimming drops/slices only the oldest chunk, and rendering
    materializes at most ``display_limit`` samples per channel. Full-buffer Y
    extrema are computed from cached per-chunk minima/maxima rather than scanning
    every raw sample when the user clicks "View All".
    """

    def __init__(self, seconds: float = 30.0, max_points: int = 1_500_000) -> None:
        self.seconds = max(1.0, float(seconds))
        self.max_points = max(1, int(max_points))
        self.x_is_time = True
        self._chunks: deque[_ScopeChunk] = deque()
        self._point_count = 0
        self._stats: dict[int, dict[str, float | int | None]] = {}
        self._lookup_cache_valid = False
        self._lookup_chunks: tuple[_ScopeChunk, ...] = ()
        # Compact each fixed group of raw acquisition chunks exactly once.
        # This keeps render iteration bounded without repeatedly copying one ever-
        # growing tail buffer. A sample is copied at most once by compaction.
        self._compact_group = 16
        self._raw_tail_count = 0
        self._lookup_ends: tuple[float, ...] = ()
        self._next_sample_index = 0

    # ---------- Basic properties ----------
    @property
    def sample_count(self) -> int:
        return int(self._point_count)

    @property
    def has_data(self) -> bool:
        return self._point_count > 0 and bool(self._chunks)

    @property
    def first_x(self) -> float | None:
        return self._chunks[0].first_x if self._chunks else None

    @property
    def last_x(self) -> float | None:
        return self._chunks[-1].last_x if self._chunks else None

    @property
    def channel_ids(self) -> set[int]:
        result: set[int] = set()
        for chunk in self._chunks:
            result.update(chunk.values)
        return result

    def set_seconds(self, seconds: float) -> None:
        self.seconds = max(1.0, float(seconds))
        self._trim()

    def clear(self) -> None:
        self._chunks.clear()
        self._point_count = 0
        self._stats = {}
        self._raw_tail_count = 0
        self._next_sample_index = 0
        self._invalidate_lookup_cache()

    # ---------- Append / trim ----------
    def append(self, times, values: dict[int, list], x_is_time: bool) -> None:
        x_new = np.asarray(times, dtype=np.float64)
        if x_new.size == 0:
            return
        self.x_is_time = bool(x_is_time)

        last_x = self.last_x
        if last_x is not None and x_new[0] <= last_x:
            step = self._estimate_step(x_new)
            x_new = x_new + (float(last_x) + step - float(x_new[0]))

        value_arrays: dict[int, np.ndarray] = {}
        for raw_cid, seq in values.items():
            cid = int(raw_cid)
            new = np.asarray(seq, dtype=np.float64)
            if new.size != x_new.size:
                padded = np.full(x_new.size, np.nan, dtype=np.float64)
                padded[: min(new.size, x_new.size)] = new[: x_new.size]
                new = padded
            value_arrays[cid] = new
            self._update_stats(cid, new)

        chunk_start_index = self._next_sample_index
        self._next_sample_index += int(x_new.size)
        self._chunks.append(
            _ScopeChunk.create(x_new, value_arrays, level=0, start_index=chunk_start_index)
        )
        self._point_count += int(x_new.size)
        self._raw_tail_count += 1
        self._compact_tail_if_needed()
        self._invalidate_lookup_cache()
        self._trim()

    def _compact_tail_if_needed(self) -> None:
        if self._raw_tail_count < self._compact_group:
            return
        group: list[_ScopeChunk] = []
        for _ in range(self._compact_group):
            if not self._chunks:
                break
            chunk = self._chunks.pop()
            if chunk.level != 0:
                # Defensive fallback; restore anything popped and recalculate.
                self._chunks.append(chunk)
                for item in reversed(group):
                    self._chunks.append(item)
                self._recompute_raw_tail_count()
                return
            group.append(chunk)
        group.reverse()
        if len(group) != self._compact_group:
            for item in group:
                self._chunks.append(item)
            self._recompute_raw_tail_count()
            return

        all_ids: set[int] = set()
        for chunk in group:
            all_ids.update(chunk.values)
        x = np.concatenate([chunk.x for chunk in group])
        merged_values: dict[int, np.ndarray] = {}
        for cid in all_ids:
            parts = []
            for chunk in group:
                arr = chunk.values.get(cid)
                if arr is None:
                    parts.append(np.full(chunk.size, np.nan, dtype=np.float64))
                else:
                    parts.append(arr)
            merged_values[cid] = np.concatenate(parts)
        self._chunks.append(_ScopeChunk.create(x, merged_values, level=1, start_index=group[0].start_index))
        self._raw_tail_count = 0

    def _recompute_raw_tail_count(self) -> None:
        count = 0
        for chunk in reversed(self._chunks):
            if chunk.level != 0:
                break
            count += 1
        self._raw_tail_count = count

    def _estimate_step(self, x_new: np.ndarray) -> float:
        if x_new.size >= 2:
            diffs = np.diff(x_new)
            positive = diffs[diffs > 0]
            if positive.size:
                return float(np.median(positive))
        if self._chunks:
            tail = self._chunks[-1].x
            if tail.size >= 2:
                diffs = np.diff(tail)
                positive = diffs[diffs > 0]
                if positive.size:
                    return float(np.median(positive))
        return 1e-6 if self.x_is_time else 1.0

    def _trim(self) -> None:
        if not self._chunks:
            return

        changed = False

        # Time-window trim. Drop complete chunks first, then slice only one front
        # chunk if the cutoff lands inside it.
        if self.x_is_time and self.first_x is not None and self.last_x is not None:
            cutoff = float(self.last_x) - float(self.seconds)
            while self._chunks and self._chunks[0].last_x < cutoff:
                chunk = self._chunks.popleft()
                self._point_count -= chunk.size
                changed = True
            if self._chunks and self._chunks[0].first_x < cutoff:
                first = self._chunks[0]
                start = int(np.searchsorted(first.x, cutoff, side="left"))
                if start > 0:
                    replacement = first.sliced(start)
                    self._chunks.popleft()
                    self._point_count -= first.size
                    if replacement is not None:
                        self._chunks.appendleft(replacement)
                        self._point_count += replacement.size
                    changed = True

        # Hard point-count cap. Again, only the oldest chunk may need slicing.
        while self._chunks and self._point_count > self.max_points:
            excess = self._point_count - self.max_points
            first = self._chunks[0]
            if excess >= first.size:
                self._chunks.popleft()
                self._point_count -= first.size
                changed = True
                continue
            replacement = first.sliced(excess)
            self._chunks.popleft()
            self._point_count -= first.size
            if replacement is not None:
                self._chunks.appendleft(replacement)
                self._point_count += replacement.size
            changed = True
            break

        if changed:
            self._recompute_raw_tail_count()
            self._invalidate_lookup_cache()

    # ---------- Statistics ----------
    def _update_stats(self, channel_id: int, values: np.ndarray) -> None:
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return
        state = self._stats.setdefault(channel_id, {
            "count": 0,
            "sum": 0.0,
            "current": None,
            "minimum": None,
            "maximum": None,
        })
        state["count"] = int(state["count"]) + int(finite.size)
        state["sum"] = float(state["sum"]) + float(np.sum(finite, dtype=np.float64))
        state["current"] = float(finite[-1])
        chunk_min = float(np.min(finite))
        chunk_max = float(np.max(finite))
        state["minimum"] = chunk_min if state["minimum"] is None else min(float(state["minimum"]), chunk_min)
        state["maximum"] = chunk_max if state["maximum"] is None else max(float(state["maximum"]), chunk_max)

    def stats_snapshot(self) -> dict[int, dict]:
        result = {}
        for cid, state in self._stats.items():
            count = int(state["count"])
            result[cid] = {
                "count": count,
                "current": state["current"],
                "average": (float(state["sum"]) / count) if count else None,
                "minimum": state["minimum"],
                "maximum": state["maximum"],
            }
        return result

    def buffer_extrema(self, channel_id: int) -> tuple[float, float] | None:
        cid = int(channel_id)
        mins: list[float] = []
        maxs: list[float] = []
        for chunk in self._chunks:
            if cid in chunk.minima:
                mins.append(chunk.minima[cid])
                maxs.append(chunk.maxima[cid])
        if not mins:
            return None
        return min(mins), max(maxs)

    # ---------- Rendering / lookup ----------
    def curve(
        self,
        channel_id: int,
        display_limit: int = 10_000,
        x_range: tuple[float, float] | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return viewport-aware, peak-preserving display samples.

        Only samples that intersect ``x_range`` are considered. This is crucial
        when a long rolling buffer is zoomed into a short interval: display
        decimation must be based on the visible sample count, not the complete
        30/60/120 s history, otherwise the zoomed waveform appears to lose points.

        When reduction is required, min/max buckets are anchored to the absolute
        acquisition sample index so a rolling buffer does not change the
        downsampling phase on every trim. Raw history/statistics/export are never
        modified.
        """
        cid = int(channel_id)
        if not self._chunks or self._point_count <= 0:
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)

        display_limit = max(4, int(display_limit))
        low: float | None = None
        high: float | None = None
        if x_range is not None:
            try:
                low, high = float(x_range[0]), float(x_range[1])
                if not (math.isfinite(low) and math.isfinite(high) and high > low):
                    low = high = None
            except Exception:
                low = high = None

        x_parts: list[np.ndarray] = []
        y_parts: list[np.ndarray] = []
        index_parts: list[np.ndarray] = []
        for chunk in self._chunks:
            if low is not None and high is not None:
                if chunk.last_x < low or chunk.first_x > high:
                    continue
                start = int(np.searchsorted(chunk.x, low, side="left"))
                stop = int(np.searchsorted(chunk.x, high, side="right"))
            else:
                start = 0
                stop = chunk.size
            if stop <= start:
                continue

            xs = chunk.x[start:stop]
            arr = chunk.values.get(cid)
            if arr is None:
                ys = np.full(xs.size, np.nan, dtype=np.float64)
            else:
                ys = arr[start:stop]
            if xs.size:
                x_parts.append(xs)
                y_parts.append(ys)
                index_parts.append(np.arange(chunk.start_index + start, chunk.start_index + stop, dtype=np.int64))

        if not x_parts:
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
        if len(x_parts) == 1:
            x = x_parts[0]
            y = y_parts[0]
            absolute_index = index_parts[0]
        else:
            x = np.concatenate(x_parts)
            y = np.concatenate(y_parts)
            absolute_index = np.concatenate(index_parts)

        if x.size <= display_limit:
            return x, y
        return self._peak_preserving_downsample(x, y, absolute_index, display_limit)

    @staticmethod
    def _peak_preserving_downsample(
        x: np.ndarray,
        y: np.ndarray,
        absolute_index: np.ndarray,
        display_limit: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Stable min/max envelope downsampling with a vectorized fast path.

        The acquisition indices are normally contiguous, which lets all complete
        buckets be reduced by NumPy in one operation. Only the first/last partial
        bucket need tiny scalar handling. This matters for 30 s x 1 kHz buffers:
        three Stacked channels can be redrawn without thousands of Python bucket
        loops per frame.
        """
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
                # All-NaN buckets need one NaN point rather than bogus extrema.
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
                # Remove duplicate index pairs (constant/all-NaN buckets) while
                # preserving temporal order.
                if idx.size >= 2:
                    keep = np.concatenate(([True], idx[1:] != idx[:-1]))
                    idx = idx[keep]
                if idx.size > limit:
                    select = np.linspace(0, idx.size - 1, limit, dtype=np.int64)
                    idx = idx[select]
                return x[idx], y[idx]

        # Defensive fallback for any future non-contiguous acquisition index
        # representation. This path is uncommon and prioritizes correctness.
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

    def _invalidate_lookup_cache(self) -> None:
        self._lookup_cache_valid = False

    def _ensure_lookup_cache(self) -> None:
        if self._lookup_cache_valid:
            return
        chunks = tuple(self._chunks)
        self._lookup_chunks = chunks
        self._lookup_ends = tuple(chunk.last_x for chunk in chunks)
        self._lookup_cache_valid = True

    def nearest(self, channel_id: int, x_value: float) -> tuple[float, float] | None:
        if not self._chunks:
            return None
        cid = int(channel_id)
        self._ensure_lookup_cache()
        chunks = self._lookup_chunks
        ends = self._lookup_ends
        if not chunks:
            return None

        index = bisect.bisect_left(ends, float(x_value))
        if index >= len(chunks):
            index = len(chunks) - 1

        # The chosen chunk is normally enough. Check adjacent chunks as well so
        # a cursor close to a chunk boundary selects the true nearest sample.
        best: tuple[float, float, float] | None = None  # distance, x, y
        for chunk_index in {max(0, index - 1), index, min(len(chunks) - 1, index + 1)}:
            chunk = chunks[chunk_index]
            arr = chunk.values.get(cid)
            if arr is None or chunk.size == 0:
                continue
            pos = int(np.searchsorted(chunk.x, x_value))
            candidates = []
            if pos < chunk.size:
                candidates.append(pos)
            if pos > 0:
                candidates.append(pos - 1)
            for p in candidates:
                value = float(arr[p])
                if not math.isfinite(value):
                    continue
                x = float(chunk.x[p])
                candidate = (abs(x - float(x_value)), x, value)
                if best is None or candidate[0] < best[0]:
                    best = candidate
        if best is None:
            return None
        return best[1], best[2]

    # ---------- Export ----------
    def iter_rows(self, channel_ids: Iterable[int]) -> Iterator[tuple[float, list[float | None]]]:
        ids = [int(cid) for cid in channel_ids]
        for chunk in self._chunks:
            arrays = [chunk.values.get(cid) for cid in ids]
            for i, x in enumerate(chunk.x):
                row: list[float | None] = []
                for arr in arrays:
                    if arr is None:
                        row.append(None)
                        continue
                    value = float(arr[i])
                    row.append(value if math.isfinite(value) else None)
                yield float(x), row

    # ---------- Test / diagnostics helpers ----------
    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def materialize(self, channel_id: int) -> tuple[np.ndarray, np.ndarray]:
        """Return complete current-buffer arrays. Intended for tests/debug only."""
        cid = int(channel_id)
        if not self._chunks:
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)
        xs: list[np.ndarray] = []
        ys: list[np.ndarray] = []
        for chunk in self._chunks:
            xs.append(chunk.x)
            arr = chunk.values.get(cid)
            if arr is None:
                ys.append(np.full(chunk.size, np.nan, dtype=np.float64))
            else:
                ys.append(arr)
        return np.concatenate(xs), np.concatenate(ys)
