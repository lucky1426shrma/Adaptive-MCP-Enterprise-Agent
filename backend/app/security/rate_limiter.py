"""In-memory sliding-window rate limiter.

Deliberately simple — single-process, in-memory — appropriate for a
portfolio project and a single backend instance. DOCUMENTED LIMITATION:
this does NOT coordinate across multiple backend replicas; a real
multi-instance deployment needs a shared store (Redis, etc.) instead of
this class. Kept as a small, replaceable component specifically so that
swap is possible later without touching the middleware that calls it
(`app/security/rate_limit_middleware.py`).

Dependency-free (stdlib only) — see `backend/tests/test_rate_limiter.py`,
which actually runs, using an injectable clock for determinism.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, Optional


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = {}

    def allow(self, key: str, now: Optional[float] = None) -> bool:
        """Return True if `key` may make a request now, recording it if so.

        `now` is injectable for deterministic tests; production callers
        omit it and get `time.monotonic()`.
        """
        current_time = now if now is not None else time.monotonic()
        window_start = current_time - self._window_seconds
        hits = self._hits.setdefault(key, deque())

        while hits and hits[0] < window_start:
            hits.popleft()

        if len(hits) >= self._max_requests:
            return False

        hits.append(current_time)
        return True

    def retry_after_seconds(self, key: str, now: Optional[float] = None) -> float:
        """How long until `key`'s oldest in-window hit expires, if currently blocked."""
        current_time = now if now is not None else time.monotonic()
        hits = self._hits.get(key)
        if not hits:
            return 0.0
        oldest = hits[0]
        return max(0.0, (oldest + self._window_seconds) - current_time)
