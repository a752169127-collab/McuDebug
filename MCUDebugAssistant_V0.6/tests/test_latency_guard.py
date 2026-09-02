import gc

from core.latency_guard import LiveLatencyGuard


def test_latency_guard_is_idempotent_and_restores_gc_state():
    original = gc.isenabled()
    guard = LiveLatencyGuard()
    try:
        first = guard.activate()
        second = guard.activate()
        assert first.active
        assert second.active
        assert not gc.isenabled()
        stopped = guard.deactivate()
        assert not stopped.active
        if original:
            assert gc.isenabled()
    finally:
        if original and not gc.isenabled():
            gc.enable()
        elif not original and gc.isenabled():
            gc.disable()


def test_idle_collect_returns_integer():
    guard = LiveLatencyGuard()
    assert isinstance(guard.collect_idle(), int)
