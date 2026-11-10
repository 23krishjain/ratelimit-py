import pytest

from ratelimit import SlidingWindowLog


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make(limit=5, window=10, clock=None):
    clock = clock or FakeClock()
    return SlidingWindowLog(limit, window, clock), clock


def test_allows_up_to_limit_then_blocks():
    limiter, _ = make(limit=3)
    assert [limiter.allow() for _ in range(4)] == [True, True, True, False]


def test_allows_again_once_the_window_passes():
    limiter, clock = make(limit=2, window=10)
    assert limiter.allow()
    assert limiter.allow()
    assert not limiter.allow()
    clock.advance(10)
    assert limiter.allow()


def test_window_slides_continuously_instead_of_resetting():
    # With a fixed window, requests at t=0 and t=5 would both count against
    # the same slot and the whole count would reset at t=10. A sliding window
    # frees each slot exactly when its own request ages out.
    limiter, clock = make(limit=2, window=10)
    assert limiter.allow()       # t=0
    clock.advance(5)
    assert limiter.allow()       # t=5
    clock.advance(4)
    assert not limiter.allow()   # t=9: both hits still inside the last 10s
    clock.advance(2)
    assert limiter.allow()       # t=11: the t=0 hit expired, one slot free
    assert not limiter.allow()   # the t=5 hit still counts


def test_hit_exactly_window_old_is_expired():
    limiter, clock = make(limit=1, window=10)
    assert limiter.allow()
    clock.advance(10)
    assert limiter.allow()


def test_failed_request_is_not_recorded():
    # If blocked requests were logged, a client hammering the limiter would
    # push its own recovery time further and further out.
    limiter, clock = make(limit=1, window=10)
    assert limiter.allow()
    for _ in range(5):
        assert not limiter.allow()
    clock.advance(10)
    assert limiter.allow()


def test_retry_after_is_zero_when_under_limit():
    limiter, _ = make(limit=2)
    assert limiter.retry_after() == 0.0
    limiter.allow()
    assert limiter.retry_after() == 0.0


def test_retry_after_counts_down_to_the_oldest_hit():
    limiter, clock = make(limit=2, window=10)
    limiter.allow()              # t=0
    clock.advance(4)
    limiter.allow()              # t=4
    assert limiter.retry_after() == pytest.approx(6)   # oldest hit (t=0) expires at t=10
    clock.advance(6)
    assert limiter.retry_after() == 0.0
    assert limiter.allow()


def test_spaced_requests_are_never_blocked():
    # One request every 6 seconds with limit 2 per 10s: each request lands
    # after the previous-but-one has expired.
    limiter, clock = make(limit=2, window=10)
    for _ in range(5):
        assert limiter.allow()
        clock.advance(6)


def test_expired_hits_are_forgotten():
    limiter, clock = make(limit=3, window=10)
    for _ in range(3):
        limiter.allow()
    clock.advance(11)
    limiter.allow()  # triggers eviction
    assert len(limiter._hits) == 1


def test_clock_going_backwards_does_not_free_slots():
    limiter, clock = make(limit=1, window=10)
    clock.advance(5)
    assert limiter.allow()       # t=5
    clock.advance(-5)            # clock jumps back to 0
    assert not limiter.allow()


@pytest.mark.parametrize("limit,window", [(0, 10), (-1, 10), (1, 0), (1, -5)])
def test_rejects_bad_config(limit, window):
    with pytest.raises(ValueError):
        SlidingWindowLog(limit, window)
