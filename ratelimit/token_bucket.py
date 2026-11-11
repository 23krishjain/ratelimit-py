import threading
import time
from typing import Callable


class TokenBucket:
    """Allow bursts up to `capacity`, then refill at `rate` tokens per second.

    The clock is passed in so tests can control time instead of sleeping.
    """

    def __init__(self, capacity: float, rate: float, clock: Callable[[], float] = time.monotonic):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.capacity = float(capacity)
        self.rate = float(rate)
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last)  # guard against a clock that goes backwards
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last = now

    def allow(self, cost: float = 1.0) -> bool:
        """Take `cost` tokens if available. Returns False without taking any if not."""
        if cost <= 0:
            raise ValueError("cost must be positive")
        if cost > self.capacity:
            return False  # can never be satisfied, so don't pretend it might be
        with self._lock:
            self._refill()
            if self._tokens >= cost:
                self._tokens -= cost
                return True
            return False

    def retry_after(self, cost: float = 1.0) -> float:
        """Seconds until `cost` tokens will be available (0 if available now)."""
        if cost > self.capacity:
            return float("inf")
        with self._lock:
            self._refill()
            missing = cost - self._tokens
            return 0.0 if missing <= 0 else missing / self.rate
