import numpy as np

from core.lane_mapper import (
    lane_bounds,
    lane_index_from_y,
    map_value_to_lane,
    map_values_to_lane,
    unmap_value_from_lane,
)


def test_lane_order_is_top_to_bottom():
    assert lane_bounds(0, 3)[:2] == (2.0, 3.0)
    assert lane_bounds(1, 3)[:2] == (1.0, 2.0)
    assert lane_bounds(2, 3)[:2] == (0.0, 1.0)
    assert lane_index_from_y(2.5, 3) == 0
    assert lane_index_from_y(1.5, 3) == 1
    assert lane_index_from_y(0.5, 3) == 2


def test_lane_map_round_trip():
    yr = (-300.0, 100.0)
    for value in (-300.0, -100.0, 100.0):
        lane_y = map_value_to_lane(value, yr, 1, 3)
        restored = unmap_value_from_lane(lane_y, yr, 1, 3)
        assert abs(restored - value) < 1e-9


def test_lane_mapping_clips_like_independent_viewbox():
    mapped = map_values_to_lane(np.asarray([-1000.0, 0.0, 1000.0]), (-100.0, 100.0), 0, 2)
    _bottom, _top, inner_bottom, inner_top = lane_bounds(0, 2)
    assert mapped[0] == inner_bottom
    assert mapped[-1] == inner_top
    assert inner_bottom < mapped[1] < inner_top
