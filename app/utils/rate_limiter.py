from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """Simple per-user rate limiter using sliding window."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        timestamps = self._requests[user_id]
        self._requests[user_id] = [t for t in timestamps if t > cutoff]
        if len(self._requests[user_id]) >= self.max_requests:
            return False
        self._requests[user_id].append(now)
        return True
