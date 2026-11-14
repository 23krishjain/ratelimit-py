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


def test_expired_key_starts_with_a_fresh_window():
    clock = FakeClock()
    storage = MemoryStorage(ttl=60, clock=clock)
    limiter = KeyedSlidingWindowLog(1, 100, storage, clock)
    assert limiter.allow("a")
    assert not limiter.allow("a")  # hit is still inside the 100s window
    clock.advance(61)  # past the ttl: the key, and its hit, are forgotten
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
