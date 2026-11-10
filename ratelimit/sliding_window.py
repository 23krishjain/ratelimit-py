import time
from collections import deque
from typing import Callable


class SlidingWindowLog:
    """Allow at most `limit` requests in any `window`-second span.

    Stores the timestamp of every allowed request and forgets the ones
    that fall out of the window. Exact, at the cost of one deque entry
    per request currently inside the window.
    """

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window <= 0:
            raise ValueError("window must be positive")
        self.limit = int(limit)
        self.window = float(window)
        self._clock = clock
        self._hits = deque()

    def _drop_expired(self, now: float) -> None:
        # A hit exactly `window` seconds old counts as expired.
        cutoff = now - self.window
        while self._hits and self._hits[0] <= cutoff:
            self._hits.popleft()

    def allow(self) -> bool:
        """Record one request if the window has room. Returns False without recording if not."""
        now = self._clock()
        self._drop_expired(now)
        if len(self._hits) >= self.limit:
            return False
        self._hits.append(now)
        return True

    def retry_after(self) -> float:
        """Seconds until the next request would pass (0 if one would pass now).

        The wait is set by the oldest hit in the window: once it expires,
        a slot frees up.
        """
        now = self._clock()
        self._drop_expired(now)
        if len(self._hits) < self.limit:
            return 0.0
        return max(0.0, self._hits[0] + self.window - now)
