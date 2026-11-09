# ratelimit-py

A small Python library of rate limiting algorithms, built to understand how they differ.

An API that lets every client send unlimited requests falls over when one client misbehaves. A rate limiter decides, per request, whether to let it through. The interesting part is the trade-offs between algorithms, so this repo implements a few and compares them.

## Status

Work in progress, one piece at a time.

- [x] Token bucket
- [ ] Sliding window
- [ ] Storage interface so limiters can be shared across processes
- [ ] Benchmark comparing the algorithms

## Try it

```
python demo.py
python -m pytest
```

`demo.py` fires 12 requests at a bucket with a burst of 5 and a refill of 2 tokens per second. The first 5 pass, the rest are blocked, and after a one second wait another one passes.

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

## Limits

- Not thread safe yet. Two threads calling `allow()` at the same time can both take the last token.
- State lives in memory in one process.
- One bucket per client is up to the caller for now.

Design notes for each step are in `docs/`.
