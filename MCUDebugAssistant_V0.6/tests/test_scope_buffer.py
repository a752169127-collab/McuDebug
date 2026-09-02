import numpy as np

from core.scope_buffer import ScopeDataStore


def test_chunked_buffer_appends_and_trims_without_growing_array_contract():
    store = ScopeDataStore(seconds=2.0, max_points=10_000)
    for block in range(6):
        t0 = block * 0.5
        times = np.arange(t0, t0 + 0.5, 0.1)
        store.append(times, {1: np.full(times.size, block, dtype=float)}, True)

    assert store.has_data
    assert store.last_x is not None
    assert store.first_x is not None
    assert store.last_x - store.first_x <= 2.000001
    assert store.sample_count <= 21
    # Oldest blocks have been trimmed; extrema reflect the retained buffer only.
    lo, hi = store.buffer_extrema(1)
    assert lo >= 1.0
    assert hi == 5.0


def test_curve_downsamples_without_materializing_full_history():
    store = ScopeDataStore(seconds=1000.0, max_points=100_000)
    for block in range(100):
        times = np.arange(block * 100, block * 100 + 100, dtype=float)
        store.append(times, {1: times * 2.0}, False)

    assert store.sample_count == 10_000
    x, y = store.curve(1, display_limit=500)
    assert 450 <= x.size <= 500
    assert x.size == y.size
    assert np.allclose(y, x * 2.0)


def test_nearest_and_export_rows_preserve_raw_values():
    store = ScopeDataStore(seconds=10.0, max_points=1000)
    store.append([0.0, 0.1, 0.2], {1: [10, 20, 30], 2: [-1, -2, -3]}, True)
    store.append([0.3, 0.4], {1: [40, 50], 2: [-4, -5]}, True)

    assert store.nearest(1, 0.26) == (0.3, 40.0)
    rows = list(store.iter_rows([1, 2]))
    assert rows[0] == (0.0, [10.0, -1.0])
    assert rows[-1] == (0.4, [50.0, -5.0])


def test_resume_timestamp_is_shifted_forward():
    store = ScopeDataStore(seconds=30.0, max_points=1000)
    store.append([0.0, 0.001, 0.002], {1: [1, 2, 3]}, True)
    store.append([0.0, 0.001], {1: [4, 5]}, True)
    x, y = store.materialize(1)
    assert np.all(np.diff(x) > 0)
    assert list(y) == [1, 2, 3, 4, 5]


def test_display_decimation_phase_stays_stable_when_rolling_buffer_trims():
    store = ScopeDataStore(seconds=1000.0, max_points=1000)
    x0 = np.arange(1000, dtype=float)
    store.append(x0, {1: x0.copy()}, False)
    before_x, _ = store.curve(1, display_limit=100)
    assert before_x[0] == 0.0

    # Add only three points. The rolling buffer trims [0,1,2]. Only the partial
    # first envelope bucket may change; all complete absolute-index buckets must
    # keep the same selected extrema instead of the entire waveform changing
    # decimation phase.
    x1 = np.arange(1000, 1003, dtype=float)
    store.append(x1, {1: x1.copy()}, False)
    after_x, _ = store.curve(1, display_limit=100)
    assert after_x[0] == 3.0
    assert np.array_equal(before_x[1:40], after_x[1:40])


def test_curve_zoom_window_uses_visible_samples_not_whole_buffer_decimation():
    store = ScopeDataStore(seconds=60.0, max_points=100_000)
    times = np.arange(0.0, 30.0, 0.001)  # 30k raw points at 1 kHz
    values = np.sin(times * 10.0)
    store.append(times, {1: values}, True)

    # A 100 ms zoom contains only ~101 samples. It must return those samples
    # directly even though the complete 30 s buffer is much larger than the
    # display point budget. Older code decimated the full buffer first and left
    # only a handful of points inside this zoom window.
    x, y = store.curve(1, display_limit=1000, x_range=(10.0, 10.1))
    assert 95 <= x.size <= 105
    assert x.size == y.size
    assert x[0] >= 10.0
    assert x[-1] <= 10.1 + 1e-12


def test_peak_downsampling_keeps_narrow_spike():
    store = ScopeDataStore(seconds=100.0, max_points=100_000)
    times = np.arange(10_000, dtype=float)
    values = np.zeros(10_000, dtype=float)
    values[4321] = 123.0
    store.append(times, {1: values}, False)
    x, y = store.curve(1, display_limit=400)
    assert np.max(y) == 123.0
    assert 4321.0 in x[y == 123.0]


def test_visible_window_curve_excludes_historical_outlier_for_lane_fit():
    """V0.4.8 lane fitting depends on the visible X window, not full history."""
    store = ScopeDataStore(seconds=30.0, max_points=10000)
    x = np.arange(0.0, 10.0, 0.01)
    delay = 50.0 + 10.0 * np.sin(x)
    pos = delay.copy()
    # Historical outlier outside the current 5..10 s viewport.
    pos[100] = 19.0
    store.append(x, {1: delay, 2: pos}, x_is_time=True)

    assert store.buffer_extrema(2)[0] == 19.0
    _x1, y1 = store.curve(1, display_limit=4000, x_range=(5.0, 10.0))
    _x2, y2 = store.curve(2, display_limit=4000, x_range=(5.0, 10.0))
    assert np.min(y2) > 39.0
    assert abs(float(np.min(y1)) - float(np.min(y2))) < 1e-12
    assert abs(float(np.max(y1)) - float(np.max(y2))) < 1e-12


def test_reserve_capacity_preallocates_channels_and_avoids_growth():
    store = ScopeDataStore(seconds=30.0, max_points=100_000)
    reserved = store.reserve_capacity(33_500, [1, 2, 3])
    assert reserved >= 33_500
    assert {1, 2, 3}.issubset(store.channel_ids)
    before = store.capacity

    # A representative live stream comfortably inside the reservation must not
    # trigger another capacity growth.
    x = np.arange(0, 20_000, dtype=np.float64) / 1000.0
    store.append(x, {1: x, 2: x * 2, 3: -x}, True)
    assert store.capacity == before
    assert store.sample_count == 20_000
