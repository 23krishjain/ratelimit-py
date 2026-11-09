import pytest

from ratelimit import TokenBucket


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make(capacity=5, rate=1, clock=None):
    clock = clock or FakeClock()
    return TokenBucket(capacity, rate, clock), clock


def test_allows_a_burst_up_to_capacity_then_blocks():
    bucket, _ = make(capacity=3)
    assert [bucket.allow() for _ in range(4)] == [True, True, True, False]


def test_refills_over_time():
    bucket, clock = make(capacity=2, rate=1)
    bucket.allow(); bucket.allow()
    assert not bucket.allow()
    clock.advance(1)
    assert bucket.allow()
    assert not bucket.allow()


def test_refill_is_capped_at_capacity():
    bucket, clock = make(capacity=2, rate=10)
    clock.advance(100)
    assert [bucket.allow() for _ in range(3)] == [True, True, False]


def test_fractional_refill_accumulates():
    bucket, clock = make(capacity=1, rate=2)
    bucket.allow()
    clock.advance(0.25)
    assert not bucket.allow()
    clock.advance(0.25)
    assert bucket.allow()


def test_failed_request_does_not_consume_tokens():
    bucket, clock = make(capacity=3, rate=1)
    assert bucket.allow(cost=2)
    assert not bucket.allow(cost=2)  # only 1 left
    assert bucket.allow(cost=1)      # that 1 is still there


def test_cost_larger_than_capacity_is_never_allowed():
    bucket, clock = make(capacity=2)
    clock.advance(1000)
    assert not bucket.allow(cost=3)
    assert bucket.retry_after(cost=3) == float("inf")


def test_retry_after():
    bucket, clock = make(capacity=1, rate=2)
    bucket.allow()
    assert bucket.retry_after() == pytest.approx(0.5)
    clock.advance(0.25)
    assert bucket.retry_after() == pytest.approx(0.25)
    clock.advance(0.25)
    assert bucket.retry_after() == 0.0


def test_clock_going_backwards_does_not_add_tokens():
    bucket, clock = make(capacity=1, rate=1)
    bucket.allow()
    clock.advance(-5)
    assert not bucket.allow()


@pytest.mark.parametrize("capacity,rate", [(0, 1), (-1, 1), (1, 0), (1, -2)])
def test_rejects_bad_config(capacity, rate):
    with pytest.raises(ValueError):
        TokenBucket(capacity, rate)
