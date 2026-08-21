from __future__ import annotations

from app.security.rate_limiter import RateLimiter


def test_allows_up_to_max_requests_within_window() -> None:
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("client-a", now=0.0) is True
    assert limiter.allow("client-a", now=1.0) is True
    assert limiter.allow("client-a", now=2.0) is True


def test_blocks_request_beyond_max_within_window() -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("client-a", now=0.0) is True
    assert limiter.allow("client-a", now=1.0) is True
    assert limiter.allow("client-a", now=2.0) is False


def test_old_hits_outside_window_are_forgotten() -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=10)
    assert limiter.allow("client-a", now=0.0) is True
    assert limiter.allow("client-a", now=1.0) is True
    assert limiter.allow("client-a", now=2.0) is False
    # Advance past the window — the first two hits should have expired.
    assert limiter.allow("client-a", now=11.0) is True


def test_different_clients_have_independent_budgets() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("client-a", now=0.0) is True
    assert limiter.allow("client-b", now=0.0) is True
    assert limiter.allow("client-a", now=0.5) is False
    assert limiter.allow("client-b", now=0.5) is False


def test_retry_after_seconds_is_zero_when_not_blocked() -> None:
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    assert limiter.retry_after_seconds("client-a", now=0.0) == 0.0


def test_retry_after_seconds_reflects_oldest_hit_expiry() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=10)
    limiter.allow("client-a", now=0.0)
    assert limiter.retry_after_seconds("client-a", now=3.0) == 7.0


def test_retry_after_seconds_never_negative() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=10)
    limiter.allow("client-a", now=0.0)
    assert limiter.retry_after_seconds("client-a", now=100.0) == 0.0


def test_invalid_max_requests_raises() -> None:
    for bad_value in (0, -1):
        try:
            RateLimiter(max_requests=bad_value, window_seconds=60)
            raise AssertionError(f"expected ValueError for max_requests={bad_value}")
        except ValueError:
            pass


def test_invalid_window_seconds_raises() -> None:
    for bad_value in (0, -1):
        try:
            RateLimiter(max_requests=5, window_seconds=bad_value)
            raise AssertionError(f"expected ValueError for window_seconds={bad_value}")
        except ValueError:
            pass
