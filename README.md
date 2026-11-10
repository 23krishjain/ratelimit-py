# ratelimit-py

A small Python library of rate limiting algorithms, built to understand how they differ.

An API that lets every client send unlimited requests falls over when one client misbehaves. A rate limiter decides, per request, whether to let it through. The interesting part is the trade-offs between algorithms, so this repo implements a few and compares them.

## Status

Work in progress, one piece at a time.

- [x] Token bucket
- [x] Sliding window log
- [ ] Storage interface so limiters can be shared across processes
- [ ] Benchmark comparing the algorithms

## Try it

```
python demo.py
python -m pytest
```

`demo.py` fires 12 requests at a bucket with a burst of 5 and a refill of 2 tokens per second. The first 5 pass, the rest are blocked, and after a one second wait another one passes. It then fires 7 requests at a sliding window of 5 per 2 seconds: 5 pass, 2 are blocked, and the oldest request ageing out frees a slot.

## Token bucket

The bucket holds up to `capacity` tokens and gains `rate` tokens per second. Each request takes tokens. No tokens, no request.

```python
from ratelimit import TokenBucket

bucket = TokenBucket(capacity=5, rate=2)
if bucket.allow():
    handle_request()
else:
    wait = bucket.retry_after()   # seconds until the next request would pass
```

Good for: allowing short bursts while capping the long-run average.
Weak at: the burst. A client can use all `capacity` tokens at once.

## Sliding window log

Keeps the timestamp of every allowed request. A request passes if fewer than `limit` requests happened in the last `window` seconds.

```python
from ratelimit import SlidingWindowLog

window = SlidingWindowLog(limit=100, window=60)   # 100 requests per minute
if window.allow():
    handle_request()
else:
    wait = window.retry_after()   # seconds until the oldest request ages out
```

Good for: exactness. No fixed-window boundary trick, where a client fires `limit` requests at the end of one window and `limit` more at the start of the next.
Weak at: memory. It stores one timestamp per allowed request, so a limit of a million means a million entries.

## Limits

- Not thread safe yet. Two threads calling `allow()` at the same time can both take the last slot.
- State lives in memory in one process.
- One limiter per client is up to the caller for now.

Design notes for each step are in `docs/`.
