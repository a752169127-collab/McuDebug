from core.presentation_pacer import PresentationPacer


def test_144hz_uses_fractional_millisecond_pattern_without_overscheduling():
    p = PresentationPacer(144)
    now = 0.0
    delays = []
    for _ in range(144):
        d = p.next_delay_ms(now)
        delays.append(d)
        now += d / 1000.0
    assert min(delays) >= 1
    assert 6 in delays and 7 in delays
    # One second of requested 144 Hz should stay near one second, not the
    # 0.864 s produced by a fixed 6 ms repeating QTimer.
    assert 0.95 <= sum(delays) / 1000.0 <= 1.05


def test_late_tick_skips_catchup_burst():
    p = PresentationPacer(60)
    first = p.next_delay_ms(0.0)
    assert first >= 16
    # Pretend the GUI was blocked for 80 ms. Next scheduling delay should still
    # be positive rather than a run of immediate catch-up callbacks.
    d = p.next_delay_ms(0.080)
    assert d >= 1
