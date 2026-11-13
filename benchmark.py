"""Compare the limiters on speed, memory and behaviour.

Run: python benchmark.py
Numbers depend on your machine. Treat them as relative, not absolute.
"""
import time
import tracemalloc

from ratelimit import KeyedTokenBucket, SlidingWindowLog, TokenBucket

N = 200_000


def speed(name, make_call):
    call = make_call()
    start = time.perf_counter()
    for _ in range(N):
        call()
    elapsed = time.perf_counter() - start
    print(f"  {name:<28} {N / elapsed:>12,.0f} calls/s")


def bench_speed():
    print(f"speed: {N:,} allow() calls each, one thread, real clock")
    # Huge limits so the limiter mostly says yes: measures the allowed path.
    speed("token bucket", lambda: TokenBucket(10**9, 10**9).allow)
    speed("sliding window log", lambda: SlidingWindowLog(10**9, 60).allow)
    keyed = KeyedTokenBucket(10**9, 10**9)
    speed("keyed token bucket (1 key)", lambda: (lambda: keyed.allow("k")))


def bench_memory():
    print("\nmemory: bytes held after N allowed requests (clock never expires them)")
    print(f"  {'requests':>10}  {'token bucket':>14}  {'sliding log':>14}")
    for n in (1_000, 10_000, 100_000):
        tracemalloc.start()
        bucket = TokenBucket(10**9, 1)
        for _ in range(n):
            bucket.allow()
        b = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()

        tracemalloc.start()
        log = SlidingWindowLog(10**9, 10**6)
        for _ in range(n):
            log.allow()
        l = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()
        print(f"  {n:>10,}  {b:>12,} B  {l:>12,} B")


def bench_boundary():
    """A client sends requests right before and right after a window edge.

    Limit is 10 per 10 seconds. The client sends 10 at t=9.9 and 10 at t=10.1.
    A fixed window (resets at t=10) would allow all 20 in 0.2 seconds.
    """
    print("\nboundary burst: limit 10 per 10s, client sends 10 at t=9.9 and 10 at t=10.1")
    now = [0.0]
    clock = lambda: now[0]

    def fixed_window_allowed():
        # Tiny reference fixed-window counter, only here to show the problem.
        count, window_start, allowed = 0, 0.0, 0
        for t in [9.9] * 10 + [10.1] * 10:
            if t - window_start >= 10:
                count, window_start = 0, 10.0 * int(t // 10)
            if count < 10:
                count += 1
                allowed += 1
        return allowed

    def run(limiter):
        allowed = 0
        for t in [9.9] * 10 + [10.1] * 10:
            now[0] = t
            allowed += limiter.allow()
        return allowed

    print(f"  fixed window (reference)     allowed {fixed_window_allowed()}/20")
    print(f"  sliding window log           allowed {run(SlidingWindowLog(10, 10, clock))}/20")
    print(f"  token bucket (cap 10, 1/s)   allowed {run(TokenBucket(10, 1, clock))}/20")


if __name__ == "__main__":
    bench_speed()
    bench_memory()
    bench_boundary()
