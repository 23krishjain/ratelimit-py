# ratelimit-py

A small Python library of rate limiting algorithms, built to understand how they differ.

An API that lets every client send unlimited requests falls over when one client misbehaves. A rate limiter decides, per request, whether to let it through. The interesting part is the trade-offs between algorithms, so this repo implements a few and compares them.

## Status

Work in progress, one piece at a time.

- [x] Token bucket
- [x] Sliding window log
- [x] Thread safety (one lock per limiter)
- [x] Storage interface (groundwork for sharing state; only an in-memory backend so far)
- [x] Benchmark comparing the algorithms (`python benchmark.py`)

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

## Benchmark

`python benchmark.py` compares speed, memory and boundary behaviour. One run on my machine (numbers vary, read them as relative):

| | token bucket | sliding window log |
|---|---|---|
| allow() calls per second, one thread | about 1.9 million | about 2.9 million |
| memory after 100,000 allowed requests | about 316 bytes | about 3.2 MB |
| 10 requests just before a window edge, 10 just after (limit 10 per 10s) | 10 of 20 allowed | 10 of 20 allowed |

Takeaways: both are fast enough that speed is not the deciding factor. Memory is: the bucket holds two numbers, the log holds one timestamp per request. Both avoid the fixed-window problem, where the same pattern lets all 20 through. Speed is measured on the allowed path with an in-memory store, one thread, so it says nothing about a networked backend.

## Storage and per-client limits

`KeyedTokenBucket` keeps one bucket per key (user id, API key, IP) and stores the state in a `Storage` object instead of on the limiter.

```python
from ratelimit import KeyedTokenBucket

limiter = KeyedTokenBucket(capacity=5, rate=2)
if limiter.allow("user-42"):
    handle_request()
```

`Storage` has one method, `update(key, fn)`, which reads the state, runs `fn`, and writes the result as one atomic step. `MemoryStorage` is the only backend so far. A Redis backend would implement the same method, but it would need an atomic script on the Redis side, and that is not written. This step is groundwork: nothing here is shared across processes or servers yet.

## Limits

- Thread safe within one process: each limiter has a lock. It does not help across processes or machines.
- The only storage backend is in memory, so state lives in one process. The interface is there; a shared backend is not.
- Shared state across machines would also need a shared clock source. Each process's `time.monotonic` is its own.
- One limiter per client is up to the caller for now.

Design notes for each step are in `docs/`.
