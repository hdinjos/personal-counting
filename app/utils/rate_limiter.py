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

        # Prune stale users to prevent the dict from growing unbounded.
        for uid in list(self._requests.keys()):
            fresh = [t for t in self._requests[uid] if t > cutoff]
            if fresh:
                self._requests[uid] = fresh
            else:
                del self._requests[uid]

        recent = self._requests.get(user_id, [])
        if len(recent) >= self.max_requests:
            return False
        recent.append(now)
        self._requests[user_id] = recent
        return True
