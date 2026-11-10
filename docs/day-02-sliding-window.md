# Day 2: sliding window log

## What I built
`SlidingWindowLog` in `ratelimit/sliding_window.py`, 14 test cases, and a second section in `demo.py` that shows requests being blocked until the oldest one ages out.

## Why sliding window next
It is the natural comparison point for the token bucket: same job, opposite trade-off. The bucket is cheap on memory but lets a client burst; the log is exact about "N requests in the last W seconds" but remembers every request.

## Decisions worth explaining
- **It stores timestamps, not counters.** This is the "sliding window log" variant. The cheaper "sliding window counter" keeps two fixed-window counts and weights them, which is approximate. I wanted the exact one first; the counter can come later as an optimisation.
- **A deque with lazy eviction.** Old timestamps are dropped from the front on each call, so there is no background thread or timer. Each timestamp is removed at most once, so cleanup is amortised O(1) per request.
- **A hit exactly `window` seconds old is expired.** "5 requests in the last 10 seconds" here means the last 10 seconds, not counting the instant 10 seconds ago. Documented in the code because the boundary is a convention, not a fact.
- **No `cost` parameter, unlike the bucket.** A log counts discrete events; "this request costs 2.5" does not map onto a list of timestamps. Keeping the API honest beats keeping it identical.
- **`retry_after` watches the oldest hit.** With a bucket the wait is a refill-rate calculation. With a log the wait is "when does the oldest request leave the window", which is a real timestamp. That makes it exact too.
- **Blocked requests are not recorded.** Otherwise a client hammering the limiter would keep pushing its own recovery time out.

## Known problems, left for later
- Memory grows with `limit`. A limit of 1000 is fine; a limit of a million is a million deque entries. The sliding window counter exists for exactly this case.
- Still not thread safe; still single process.

## Questions to practise answering
1. A fixed-window counter allows a burst of 2x the limit at a window boundary. Why can't the sliding log have that problem?
2. Sliding window log vs sliding window counter: what do you give up for the memory saving?
3. How would you store the log in Redis? (Sorted set, score = timestamp, trim with ZREMRANGEBYSCORE.)
4. What happens to memory if the limit is 10 million requests per second? What would you change?
