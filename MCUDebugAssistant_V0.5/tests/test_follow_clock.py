from core.follow_clock import FollowPresentationClock


def test_follow_clock_moves_between_arrivals_without_exceeding_real_tail():
    clock = FollowPresentationClock(min_latency_s=0.010, max_latency_s=0.050, latency_multiplier=2.0)
    clock.observe(1.000, 10.000)
    clock.observe(1.020, 10.020)

    a = clock.visual_right(1.020, 10.021)
    b = clock.visual_right(1.020, 10.025)
    assert b > a
    assert b <= 1.020


def test_follow_clock_latency_tracks_packet_interval():
    clock = FollowPresentationClock(min_latency_s=0.010, max_latency_s=0.080, latency_multiplier=2.0)
    clock.observe(0.000, 5.000)
    clock.observe(0.020, 5.020)
    assert 0.035 <= clock.presentation_latency_s <= 0.045


def test_follow_clock_slowly_corrects_jittery_arrival_phase():
    clock = FollowPresentationClock(max_offset_correction_s=0.002)
    clock.observe(0.000, 100.000)
    baseline = clock.visual_right(0.100, 100.050)
    # A deliberately late packet should not cause a large camera phase jump.
    clock.observe(0.100, 100.130)
    after = clock.visual_right(0.100, 100.131)
    assert abs(after - baseline) < 0.08
