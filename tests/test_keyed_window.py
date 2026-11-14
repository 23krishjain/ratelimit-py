import pytest

from ratelimit import KeyedSlidingWindowLog, MemoryStorage, SlidingWindowLog


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make(limit=3, window=10, storage=None):
    clock = FakeClock()
    return KeyedSlidingWindowLog(limit, window, storage, clock), clock


def test_each_key_has_its_own_window():
    limiter, _ = make(limit=2)
    assert limiter.allow("alice") and limiter.allow("alice")
    assert not limiter.allow("alice")
    assert limiter.allow("bob")  # alice being blocked does not affect bob


def test_hits_age_out_per_key():
    limiter, clock = make(limit=2, window=10)
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    clock.advance(10)  # both hits are now exactly window seconds old: expired
    assert limiter.allow("a")


def test_matches_plain_sliding_window_on_the_same_sequence():
    # Same inputs, same answers: the storage layer must not change behaviour.
    c1, c2 = FakeClock(), FakeClock()
    plain = SlidingWindowLog(3, 10, c1)
    keyed = KeyedSlidingWindowLog(3, 10, clock=c2)
    for dt in [0, 0, 1, 0, 2, 5, 0, 4, 1, 0, 3]:
        c1.advance(dt)
        c2.advance(dt)
        assert plain.allow() == keyed.allow("k")
        assert plain.retry_after() == pytest.approx(keyed.retry_after("k"))


def test_blocked_request_is_not_recorded():
    limiter, clock = make(limit=1, window=10)
    assert limiter.allow("a")
    assert not limiter.allow("a")  # blocked, so not logged
    assert not limiter.allow("a")  # still blocked, and did not push the wait out
    assert limiter.retry_after("a") == pytest.approx(10)


def test_retry_after_counts_down_to_oldest_hit():
    limiter, clock = make(limit=1, window=10)
    assert limiter.allow("a")
    clock.advance(4)
    assert limiter.retry_after("a") == pytest.approx(6)
    clock.advance(6)
    assert limiter.retry_after("a") == 0.0
    assert limiter.allow("a")


def test_two_limiters_sharing_one_storage_share_the_limit():
    # Stand-in for two workers pointed at the same backend: 2 in total, not 2 each.
    storage = MemoryStorage()
    clock = FakeClock()
    w1 = KeyedSlidingWindowLog(2, 10, storage, clock)
    w2 = KeyedSlidingWindowLog(2, 10, storage, clock)
    results = [w1.allow("u"), w2.allow("u"), w1.allow("u")]
    assert results == [True, True, False]


def test_idle_keys_expire_with_ttl():
    clock = FakeClock()
    storage = MemoryStorage(ttl=60, clock=clock)
    limiter = KeyedSlidingWindowLog(1, 10, storage, clock)
    limiter.allow("stale")
    limiter.allow("fresh")
    assert len(storage) == 2
    clock.advance(61)
    limiter.allow("fresh")  # touching any key triggers the sweep
    assert len(storage) == 1


def test_ttl_shorter_than_window_is_rejected():
    with pytest.raises(ValueError, match="recovery period"):
        KeyedSlidingWindowLog(1, 100, MemoryStorage(ttl=60))


def test_ttl_equal_to_window_is_safe_at_boundary():
    clock = FakeClock()
    storage = MemoryStorage(ttl=10, clock=clock)
    limiter = KeyedSlidingWindowLog(1, 10, storage, clock)
    assert limiter.allow("a")
    clock.advance(9)
    assert not limiter.allow("a")
    clock.advance(10)
    assert limiter.allow("a")


def test_key_touched_inside_ttl_is_kept():
    clock = FakeClock()
    storage = MemoryStorage(ttl=60, clock=clock)
    limiter = KeyedSlidingWindowLog(2, 10, storage, clock)
    limiter.allow("a")
    clock.advance(30)
    limiter.allow("a")  # resets the idle clock for "a"
    clock.advance(45)   # 75s since first touch, 45s since last
    limiter.allow("b")
    assert len(storage) == 2  # "a" survived because it was active 45s ago


def test_no_ttl_keeps_keys_forever():
    clock = FakeClock()
    storage = MemoryStorage(clock=clock)  # default: no expiry
    limiter = KeyedSlidingWindowLog(1, 10, storage, clock)
    limiter.allow("a")
    clock.advance(10_000)
    limiter.allow("b")
    assert len(storage) == 2


@pytest.mark.parametrize("limit,window", [(0, 1), (1, 0), (-1, 1)])
def test_rejects_bad_config(limit, window):
    with pytest.raises(ValueError):
        KeyedSlidingWindowLog(limit, window)


def test_rejects_bad_ttl():
    with pytest.raises(ValueError):
        MemoryStorage(ttl=0)


def test_token_bucket_rejects_ttl_shorter_than_full_refill():
    from ratelimit import KeyedTokenBucket
    with pytest.raises(ValueError, match="recovery period"):
        KeyedTokenBucket(10, 2, MemoryStorage(ttl=4))
    KeyedTokenBucket(10, 2, MemoryStorage(ttl=5))


@pytest.mark.parametrize("kind", ["window", "bucket"])
def test_clock_is_sampled_inside_atomic_update(kind):
    from ratelimit import KeyedTokenBucket, Storage

    clock = FakeClock()

    class DelayedStorage(Storage):
        def __init__(self):
            self.inner = MemoryStorage()

        def update(self, key, fn):
            # Simulate time spent waiting to enter a storage critical section.
            clock.advance(1)
            return self.inner.update(key, fn)

    storage = DelayedStorage()
    limiter = (KeyedSlidingWindowLog(1, 10, storage, clock) if kind == "window"
               else KeyedTokenBucket(1, 0.1, storage, clock))
    assert limiter.allow("a")  # recorded at t=1, not t=0
    recorded = storage.inner.update("a", lambda state: (state, state))
    assert (recorded[0] if kind == "window" else recorded[1]) == 1


@pytest.mark.parametrize("cost", [0, -1])
def test_keyed_bucket_retry_rejects_nonpositive_cost(cost):
    from ratelimit import KeyedTokenBucket
    with pytest.raises(ValueError):
        KeyedTokenBucket(1, 1).retry_after("a", cost)


def test_keyed_window_threads_share_one_limit():
    from concurrent.futures import ThreadPoolExecutor
    limiter = KeyedSlidingWindowLog(20, 10, clock=lambda: 0.0)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: limiter.allow("a"), range(200)))
    assert sum(results) == 20
    assert limiter.allow("b")
