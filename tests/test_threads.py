"""Hammer each limiter from many threads at once.

The clock is frozen, so nothing refills or expires during the test. That
makes the answer exact: with room for N requests, exactly N must be allowed
no matter how the threads interleave.
"""
import sys
import threading

import pytest

from ratelimit import SlidingWindowLog, TokenBucket

THREADS = 16
CALLS_PER_THREAD = 500
ROOM = 1000


@pytest.fixture(autouse=True)
def switch_threads_often():
    # Default is a switch every 5ms, which hides races. Force far more switches.
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    yield
    sys.setswitchinterval(old)


def hammer(limiter):
    allowed = []
    barrier = threading.Barrier(THREADS)

    def worker():
        count = 0
        barrier.wait()
        for _ in range(CALLS_PER_THREAD):
            if limiter.allow():
                count += 1
        allowed.append(count)

    threads = [threading.Thread(target=worker) for _ in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return sum(allowed)


def test_token_bucket_never_over_allows_under_threads():
    bucket = TokenBucket(capacity=ROOM, rate=1, clock=lambda: 0.0)
    assert hammer(bucket) == ROOM


def test_sliding_window_never_over_allows_under_threads():
    window = SlidingWindowLog(limit=ROOM, window=60, clock=lambda: 0.0)
    assert hammer(window) == ROOM
