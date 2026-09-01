from core.presentation_pacer import PresentationPacer


def test_144hz_uses_fractional_millisecond_pattern_without_overscheduling():
    p = PresentationPacer(144)
    now = 0.0
    delays = []
    for _ in range(144):
        delay_ms = p.next_delay_ms(now)
        delays.append(delay_ms)
        now += delay_ms / 1000.0

    assert min(delays) >= 1
    assert 6 in delays and 7 in delays
    assert 0.95 <= sum(delays) / 1000.0 <= 1.05


def test_late_tick_skips_catchup_burst():
    p = PresentationPacer(60)
    first = p.next_delay_ms(0.0)
    assert 16 <= first <= 17

    # Simulate an external 80 ms pause. The next request is one future frame,
    # never a stream of immediate catch-up callbacks.
    delay_ms = p.next_delay_ms(0.080)
    assert delay_ms >= 1


def test_60hz_needs_about_one_callback_per_frame():
    p = PresentationPacer(60)
    now = 0.0
    delays = []
    for _ in range(60):
        delay_ms = p.next_delay_ms(now)
        delays.append(delay_ms)
        now += delay_ms / 1000.0

    assert len(delays) == 60
    assert min(delays) >= 16
    assert max(delays) <= 17
    assert 0.95 <= sum(delays) / 1000.0 <= 1.05
