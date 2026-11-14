import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Hashable, Optional, Tuple


class Storage(ABC):
    """Where limiter state lives.

    The only operation is `update`: read the state for a key, run a function
    on it, and write the result back as ONE atomic step. A limiter's
    check-then-update must never be split, so the storage owns atomicity.

    `fn` receives the stored state (None if the key is new) and returns
    `(new_state, result)`. `update` stores `new_state` and returns `result`.
    """

    @abstractmethod
    def update(self, key: Hashable, fn: Callable[[Optional[Any]], Tuple[Any, Any]]) -> Any:
        ...


class MemoryStorage(Storage):
    """Dict plus one lock. Atomic inside one process only.

    Pass `ttl` (seconds) to forget keys that have not been touched for that
    long. Without a ttl nothing is ever removed: a key seen once stays
    forever, which leaks memory in a long-running process when keys are
    user ids or IPs. Expiry is checked when a key is accessed, so a fully
    idle process holds its keys until the next call.
    """

    def __init__(self, ttl: float = None, clock: Callable[[], float] = time.monotonic):
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive")
        self.ttl = ttl
        self._clock = clock
        self._data: Dict[Hashable, Any] = {}
        self._touched: Dict[Hashable, float] = {}
        self._lock = threading.Lock()

    def update(self, key, fn):
        with self._lock:
            now = self._clock()
            if self.ttl is not None:
                self._drop_idle(now)
            new_state, result = fn(self._data.get(key))
            self._data[key] = new_state
            if self.ttl is not None:
                self._touched[key] = self._clock()
            return result

    def _drop_idle(self, now: float) -> None:
        idle = [k for k, t in self._touched.items() if now - t >= self.ttl]
        for k in idle:
            del self._touched[k]
            self._data.pop(k, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
