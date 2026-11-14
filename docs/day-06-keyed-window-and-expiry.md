# Day 6: keyed sliding window and idle-key expiry

## What changed
- Added KeyedSlidingWindowLog, with allow(key) and retry_after(key).
- Added opt-in MemoryStorage(ttl=...) with lazy idle-key cleanup.
- Added tests for key isolation, boundary expiry, parity with the plain log,
  shared storage, safe TTL configuration and clock sampling inside update.
- Moved keyed limiter clock sampling inside the atomic callback to avoid
  threads appending stale timestamps after newer ones.
- Fixed nonpositive costs in KeyedTokenBucket.retry_after.

## Decisions and trade-offs
State is a plain list of timestamps. It is directly JSON-serialisable, unlike
an unconverted deque. That is a convenience, not a shared backend. Each update
copies the list, so it costs O(hits in that key's window), even when blocking.

TTL is opt-in. An expired key starts fresh. That is safe only after its limit
has naturally recovered: a full window for the log, capacity/rate for a bucket.
The built-in keyed limiters reject a shorter MemoryStorage TTL. Use the same
monotonic clock for store and limiter, and do not change TTL after construction.
A custom storage backend must preserve equivalent safety itself.

Cleanup runs on each update under the storage lock. It scans all keys, costing
O(number of keys), unlike the old O(1) dictionary update. This simple version
is for small single-process use, not large client populations. There is no
background thread: a fully idle process retains entries until the next call.
TTL removes idle keys, but does not impose a hard capacity limit on active keys.

## Review corrections
The first passing suite allowed a TTL shorter than a live window. A review
caught that this would reset the limit early; validation and regression tests
now cover it. Passing the first suite did not prove correctness.

## Limits
Only MemoryStorage exists. Shared objects in one process are tested, not
multiple processes or servers. Storage key namespaces must be dedicated to
compatible limiter configurations; mixing bucket and log state is invalid.
The clock must be monotonic. No high-cardinality performance claim is made.

## Interview questions
1. Why can evicting state too early bypass a limit?
2. Why must clock sampling happen inside the atomic update?
3. What does an O(number of keys) sweep cost on every request?
4. When would a deque or an expiry heap be a better choice?
5. Why do page-like data structures being serialisable not make a backend distributed?
