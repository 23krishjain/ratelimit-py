import time
from typing import Callable, Hashable, List, Optional

from .storage import MemoryStorage, Storage


class KeyedSlidingWindowLog:
    """A sliding window log per key, with state in a Storage.

    Same rules as `SlidingWindowLog`: at most `limit` requests in any
    `window`-second span. The difference is that each key (user id, API
    key, IP) gets its own window, and the hits live in `storage`, not on
    the limiter, so the state can be swapped for a shared backend.

    State per key is a list of timestamps, oldest first. A plain list,
    not a deque, because a deque cannot be serialised for a networked
    backend and a list can.
    """

    def __init__(self, limit: int, window: float, storage: Storage = None,
                 clock: Callable[[], float] = time.monotonic):
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window <= 0:
            raise ValueError("window must be positive")
        self.limit = int(limit)
        self.window = float(window)
        self.storage = storage if storage is not None else MemoryStorage()
        self._clock = clock

    def _unexpired(self, hits: Optional[List[float]], now: float) -> List[float]:
        # A hit exactly `window` seconds old counts as expired.
        cutoff = now - self.window
        keep = 0
        for ts in hits or []:
            if ts <= cutoff:
                keep += 1
            else:
                break
        return (hits or [])[keep:]

    def allow(self, key: Hashable) -> bool:
        """Record one request for this key if its window has room."""
        now = self._clock()

        def step(state):
            hits = self._unexpired(state, now)
            if len(hits) >= self.limit:
                return hits, False
            return hits + [now], True

        return self.storage.update(key, step)

    def retry_after(self, key: Hashable) -> float:
        """Seconds until this key's next request would pass (0 if one would pass now)."""
        now = self._clock()

        def step(state):
            hits = self._unexpired(state, now)
            if len(hits) < self.limit:
                return hits, 0.0
            return hits, max(0.0, hits[0] + self.window - now)

        return self.storage.update(key, step)
