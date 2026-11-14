import time
from typing import Callable, Hashable

from .storage import MemoryStorage, Storage


class KeyedTokenBucket:
    """A token bucket per key (user id, API key, IP...), with state in a Storage.

    Same rules as `TokenBucket`. The difference is that nothing lives on the
    limiter itself: tokens and last-refill time are kept in `storage`, so the
    state can be swapped for something other code can share.
    """

    def __init__(self, capacity: float, rate: float, storage: Storage = None,
                 clock: Callable[[], float] = time.monotonic):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.capacity = float(capacity)
        self.rate = float(rate)
        self.storage = storage if storage is not None else MemoryStorage()
        if (isinstance(self.storage, MemoryStorage) and self.storage.ttl is not None
                and self.storage.ttl < self.capacity / self.rate):
            raise ValueError("storage ttl must cover the full limiter recovery period")
        self._clock = clock

    def _refilled(self, state, now):
        if state is None:
            return self.capacity, now
        tokens, last = state
        elapsed = max(0.0, now - last)
        return min(self.capacity, tokens + elapsed * self.rate), now

    def allow(self, key: Hashable, cost: float = 1.0) -> bool:
        if cost <= 0:
            raise ValueError("cost must be positive")
        if cost > self.capacity:
            return False
        def step(state):
            now = self._clock()
            tokens, last = self._refilled(state, now)
            if tokens >= cost:
                return (tokens - cost, last), True
            return (tokens, last), False

        return self.storage.update(key, step)

    def retry_after(self, key: Hashable, cost: float = 1.0) -> float:
        if cost <= 0:
            raise ValueError("cost must be positive")
        if cost > self.capacity:
            return float("inf")
        def step(state):
            now = self._clock()
            tokens, last = self._refilled(state, now)
            missing = cost - tokens
            return (tokens, last), (0.0 if missing <= 0 else missing / self.rate)

        return self.storage.update(key, step)
