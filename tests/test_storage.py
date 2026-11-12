import sys
import threading

import pytest

from ratelimit import KeyedTokenBucket, MemoryStorage, Storage, TokenBucket


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make(capacity=3, rate=1, storage=None):
    clock = FakeClock()
    return KeyedTokenBucket(capacity, rate, storage, clock), clock


def test_each_key_has_its_own_bucket():
    limiter, _ = make(capacity=2)
    assert limiter.allow("alice") and limiter.allow("alice")
    assert not limiter.allow("alice")
    assert limiter.allow("bob")  # alice being blocked does not affect bob


def test_refills_per_key():
    limiter, clock = make(capacity=1, rate=1)
    assert limiter.allow("a")
    assert not limiter.allow("a")
    clock.advance(1)
    assert limiter.allow("a")


def test_matches_plain_token_bucket_on_the_same_sequence():
    # Same inputs, same answers: the storage layer must not change behaviour.
    c1, c2 = FakeClock(), FakeClock()
    plain = TokenBucket(4, 2, c1)
    keyed = KeyedTokenBucket(4, 2, clock=c2)
    steps = [0, 0, 0.1, 0.3, 0, 0.5, 1.0, 0, 0, 0]
    for dt in steps:
        c1.advance(dt)
        c2.advance(dt)
        assert plain.allow() == keyed.allow("k")
        assert plain.retry_after() == pytest.approx(keyed.retry_after("k"))


def test_blocked_request_takes_no_tokens():
    limiter, _ = make(capacity=3)
    assert limiter.allow("a", cost=2)
    assert not limiter.allow("a", cost=2)
    assert limiter.allow("a", cost=1)


def test_cost_larger_than_capacity_never_allowed():
    limiter, _ = make(capacity=2)
    assert not limiter.allow("a", cost=3)
    assert limiter.retry_after("a", cost=3) == float("inf")


def test_two_limiters_sharing_one_storage_share_the_limit():
    # Stand-in for two workers pointed at the same backend. The limit is
    # 3 in total, not 3 each.
    storage = MemoryStorage()
    clock = FakeClock()
    w1 = KeyedTokenBucket(3, 1, storage, clock)
    w2 = KeyedTokenBucket(3, 1, storage, clock)
    results = [w1.allow("u"), w2.allow("u"), w1.allow("u"), w2.allow("u")]
    assert results == [True, True, True, False]


def test_custom_storage_backend_can_be_plugged_in():
    class LoggingStorage(Storage):
        def __init__(self):
            self.inner = MemoryStorage()
            self.calls = []

        def update(self, key, fn):
            self.calls.append(key)
            return self.inner.update(key, fn)

    storage = LoggingStorage()
    limiter, _ = make(storage=storage)
    limiter.allow("x")
    limiter.retry_after("y")
    assert storage.calls == ["x", "y"]


def test_memory_storage_update_returns_result_and_stores_state():
    s = MemoryStorage()
    assert s.update("k", lambda st: (1, "first")) == "first"
    assert s.update("k", lambda st: (st + 1, st)) == 1
    assert s.update("k", lambda st: (st, st)) == 2


def test_missing_key_is_passed_as_none():
    seen = []
    MemoryStorage().update("new", lambda st: (seen.append(st) or 0, None))
    assert seen == [None]


def test_threads_never_over_allow_through_storage():
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        limiter = KeyedTokenBucket(1000, 1, clock=lambda: 0.0)
        counts = []
        barrier = threading.Barrier(16)

        def worker():
            n = 0
            barrier.wait()
            for _ in range(500):
                if limiter.allow("shared"):
                    n += 1
            counts.append(n)

        ts = [threading.Thread(target=worker) for _ in range(16)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert sum(counts) == 1000
    finally:
        sys.setswitchinterval(old)


@pytest.mark.parametrize("capacity,rate", [(0, 1), (1, 0), (-1, 1)])
def test_rejects_bad_config(capacity, rate):
    with pytest.raises(ValueError):
        KeyedTokenBucket(capacity, rate)
