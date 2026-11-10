"""Two small demos showing the limiters blocking real requests.

1. Token bucket: send 12 requests as fast as possible at a bucket that
   allows a burst of 5, then refills 2 tokens a second.
2. Sliding window log: send 7 requests at a limit of 5 per 2 seconds,
   then watch a blocked request succeed once the oldest one ages out.
"""
import time

from ratelimit import SlidingWindowLog, TokenBucket

print("token bucket: burst 5, refill 2/second")
bucket = TokenBucket(capacity=5, rate=2)
start = time.monotonic()

for i in range(1, 13):
    ok = bucket.allow()
    t = time.monotonic() - start
    if ok:
        print(f"request {i:2d} at {t:4.2f}s  allowed")
    else:
        print(f"request {i:2d} at {t:4.2f}s  BLOCKED, retry in {bucket.retry_after():.2f}s")

print("\nwaiting 1 second...")
time.sleep(1)
print("after waiting:", "allowed" if bucket.allow() else "blocked")

print("\nsliding window log: 5 requests in any 2 seconds")
window = SlidingWindowLog(limit=5, window=2)
start = time.monotonic()

for i in range(1, 8):
    ok = window.allow()
    t = time.monotonic() - start
    if ok:
        print(f"request {i:2d} at {t:4.2f}s  allowed")
    else:
        print(f"request {i:2d} at {t:4.2f}s  BLOCKED, retry in {window.retry_after():.2f}s")

print("\nwaiting 2 seconds for the oldest request to age out...")
time.sleep(2)
print("after waiting:", "allowed" if window.allow() else "blocked")
