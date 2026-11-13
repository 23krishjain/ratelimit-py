# Day 5: benchmark

## What I built
`benchmark.py`: three small measurements you can run with `python benchmark.py`: speed, memory, and what happens at a window boundary.

## What I measured (one run, my machine)
- **Speed:** token bucket about 1.9M calls/s, sliding log about 2.9M, keyed bucket (goes through the storage layer) about 1.3M. Two runs agreed to within a few percent.
- **Memory:** after 100,000 allowed requests the bucket held about 316 bytes, the log about 3.2 MB. The bucket stays flat, the log grows with each request.
- **Boundary:** limit 10 per 10s, 10 requests just before the edge and 10 just after. A fixed-window counter lets all 20 through. Sliding log and token bucket both allow 10.

## Things worth explaining
- **The sliding log was faster than the token bucket, which I did not expect.** My explanation is that the bucket does float arithmetic on every call and the log mostly does a comparison and a deque append when nothing has expired. I did not profile it, so treat that as a guess. The honest conclusion is that speed does not separate them.
- **Memory is the real difference.** That matches the design: counters versus a log.
- **The keyed bucket is slower** because each call builds a closure and goes through `Storage.update` plus a lock. That cost buys a swappable backend.
- **The fixed-window counter in the benchmark is a tiny reference, not a feature of the library.** It is there to show the problem the other two avoid.

## Limits of this benchmark
- One machine, one thread, one run of each, no warm-up control. Absolute numbers mean little.
- It measures the allowed path with huge limits. Behaviour when mostly blocking is not measured.
- Memory uses `tracemalloc` on one workload. It counts Python allocations, not process memory.
- No concurrency or network storage numbers.

## Questions to practise answering
1. Why can a fixed window allow twice the limit around its edge, and why can't the log?
2. Memory for the log is O(limit). When does that become a problem, and what would you use instead?
3. If someone claims "algorithm A is 50% faster", what would you check before believing it?
4. Why does the keyed bucket cost more per call, and when is that worth it?
