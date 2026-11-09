"""Send 12 requests as fast as possible at a bucket that allows a burst of 5,
then refills 2 tokens a second. Shows which requests get through."""
import time

from ratelimit import TokenBucket

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
