# Day 1: token bucket

## What I built
`TokenBucket` in `ratelimit/token_bucket.py`, 12 test cases, and `demo.py`.

## Why a token bucket first
It is the simplest algorithm that handles bursts properly, and most of the others are easier to explain next to it.

## Decisions worth explaining
- **The clock is injected.** Tests pass a fake clock and move time by hand, so they run instantly and never flake. Using `time.sleep` in tests would be slow and unreliable.
- **Tokens are refilled lazily.** There is no background thread. When `allow()` is called I work out how much time passed and add tokens then. This is cheaper and has no timer to manage.
- **`time.monotonic`, not `time.time`.** The wall clock can jump (NTP, manual changes). The monotonic clock cannot go backwards. I also clamp negative elapsed time to zero as a second guard, with a test.
- **A failed request takes no tokens.** Otherwise a blocked client would drain its own bucket by retrying.
- **Cost bigger than capacity is rejected right away.** It could never succeed, so `retry_after` returns infinity rather than a misleading number.
- **Floats for tokens.** At a rate of 2 per second, waiting 0.25s should earn half a token. Integers would lose that.

## Known problems, left for later
- Not thread safe (race on the token count). Needs a lock, or an atomic store.
- Single process only.

## Questions to practise answering
1. Token bucket vs leaky bucket: what is the difference in behaviour?
2. Why inject the clock?
3. What happens if two threads call `allow()` at the same moment?
4. What would you change to limit per user instead of globally?
