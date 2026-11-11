# Day 3: thread safety

## What I built
A `threading.Lock` inside `TokenBucket` and `SlidingWindowLog`, and `tests/test_threads.py` (2 tests that hammer each limiter from 16 threads).

## The problem
`allow()` is check-then-act: read the token count, compare, subtract. Two threads can both read "1 token left", both pass the check, and both take it. The limiter then lets through more than its limit. Python's GIL does not prevent this, because a thread switch can happen between any two bytecodes.

## Decisions worth explaining
- **One lock per limiter, held for the whole of `allow()`.** The check and the update must be one unit. A lock around only the update would still let two threads pass the check.
- **`retry_after()` takes the lock too.** It refills the bucket / evicts old hits, so it changes state. Reading while another thread is mid-update could give a wrong number.
- **Per-limiter, not global.** Clients with their own limiter do not wait on each other.
- **How the test works.** The clock is frozen, so nothing refills or expires. With room for exactly 1000 requests and 8000 attempts, exactly 1000 must pass. Any other number means a race. I also set the thread switch interval to 1 microsecond so threads interleave far more than normal.
- **I checked the test can fail.** With the locks removed, the tests failed in every run I tried (token bucket every time, sliding window in some runs). With the locks they passed on repeated runs. A race test that never fails proves nothing, so this check matters.

## Known problems, left for later
- A race test cannot prove there is no race, only that it did not show up here.
- A lock only covers one process. Several server processes each have their own limiter, so the real limit becomes limit x processes. That is what the storage interface (next) is for.
- Lock contention: under heavy load all threads queue on one lock.

## Questions to practise answering
1. The GIL exists. Why is this still a race?
2. Why must the check and the update be inside the same lock?
3. How would you test for a race condition, and what are the limits of that test?
4. What would change in a multi-process setup? (Redis, atomic Lua script or INCR.)
