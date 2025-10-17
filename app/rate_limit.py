from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict


class InMemoryRateLimiter:
    """Tiny in-memory sliding window limiter."""

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = {}

    def allow(self, key: str, limit: int, per_seconds: int) -> bool:
        now = time.time()
        window_start = now - per_seconds
        buf = self._hits.setdefault(key, deque())
        while buf and buf[0] < window_start:
            buf.popleft()
        if len(buf) >= limit:
            return False
        buf.append(now)
        return True


limiter = InMemoryRateLimiter()
