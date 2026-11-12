import threading
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
    """Dict plus one lock. Atomic inside one process only."""

    def __init__(self):
        self._data: Dict[Hashable, Any] = {}
        self._lock = threading.Lock()

    def update(self, key, fn):
        with self._lock:
            new_state, result = fn(self._data.get(key))
            self._data[key] = new_state
            return result
