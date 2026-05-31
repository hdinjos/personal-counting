import app.utils.rate_limiter as rl_mod
from app.utils.rate_limiter import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_blocks_after_limit(monkeypatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(rl_mod.time, "time", clock)
    limiter = RateLimiter(max_requests=3, window_seconds=60)

    assert limiter.is_allowed(1) is True
    assert limiter.is_allowed(1) is True
    assert limiter.is_allowed(1) is True
    assert limiter.is_allowed(1) is False


def test_allows_again_after_window(monkeypatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(rl_mod.time, "time", clock)
    limiter = RateLimiter(max_requests=1, window_seconds=60)

    assert limiter.is_allowed(1) is True
    assert limiter.is_allowed(1) is False
    clock.now += 61
    assert limiter.is_allowed(1) is True


def test_stale_entries_pruned(monkeypatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(rl_mod.time, "time", clock)
    limiter = RateLimiter(max_requests=5, window_seconds=60)

    limiter.is_allowed(1)
    assert 1 in limiter._requests
    clock.now += 61
    # A request from another user triggers the prune sweep.
    limiter.is_allowed(2)
    assert 1 not in limiter._requests
