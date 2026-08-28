import numpy as np

from core.scope_buffer import ScopeDataStore
from core.render_cache import ScopeRenderCache


def test_render_cache_covers_multiple_view_widths_and_reuses_raw_data():
    store = ScopeDataStore(seconds=60, max_points=100_000)
    x = np.arange(0.0, 30.0, 0.001)
    store.append(x, {1: np.sin(x), 2: np.cos(x)}, True)

    cache = ScopeRenderCache()
    cache.build(store, [1, 2], (10.0, 12.0), display_limit_per_channel=1200, margin_spans=1.0)
    assert cache.valid
    assert cache.covers((9.0, 13.0), [1, 2])
    assert not cache.covers((2.0, 4.0), [1, 2])
    cx, cy = cache.channel(1)
    assert cx.size == cy.size
    assert cx.size <= 50_000


def test_new_data_outside_static_history_does_not_invalidate_coverage():
    store = ScopeDataStore(seconds=60, max_points=100_000)
    x = np.arange(0.0, 20.0, 0.01)
    store.append(x, {1: x}, True)
    cache = ScopeRenderCache()
    cache.build(store, [1], (5.0, 7.0), display_limit_per_channel=500, margin_spans=1.0)
    builds = cache.build_count

    store.append(np.arange(20.0, 22.0, 0.01), {1: np.arange(20.0, 22.0, 0.01)}, True)
    assert cache.covers((5.0, 7.0), [1])
    assert cache.build_count == builds


def test_render_geometry_budget_does_not_grow_with_prefetch_width():
    """Presentation point count stays pixel-budgeted, not cache-width-budgeted."""
    store = ScopeDataStore(seconds=120, max_points=500_000)
    x = np.arange(0.0, 100.0, 0.001)
    store.append(x, {1: np.sin(7.0 * x)}, True)

    cache = ScopeRenderCache()
    display_limit = 1000
    cache.build(store, [1], (50.0, 52.0), display_limit_per_channel=display_limit, margin_spans=3.0)
    cx, _ = cache.channel(1)
    # V0.4.10 multiplied by cache/view width (~7x here). V0.4.11 caps
    # submitted PlotCurveItem geometry near the screen pixel budget.
    assert cx.size <= int(display_limit * 1.35)
