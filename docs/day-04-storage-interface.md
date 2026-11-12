# Day 4: storage interface and per-client limits

## What I built
- `ratelimit/storage.py`: a `Storage` base class with one method, `update(key, fn)`, and `MemoryStorage` (dict + lock).
- `ratelimit/keyed.py`: `KeyedTokenBucket`, a token bucket per key whose state (tokens, last refill time) lives in a `Storage`.
- `tests/test_storage.py`: 13 test cases, including a check that it behaves exactly like the plain `TokenBucket` on the same inputs.

## Why this shape
Day 3 showed the check and the update must be one atomic step. A lock on the limiter object only works inside one process. If the state is going to live somewhere else later (Redis, a database), the thing that owns atomicity has to be the storage, not the limiter. So the limiter hands the storage a function and the storage runs it atomically.

## Decisions worth explaining
- **One method, `update(key, fn)`, not `get` and `set`.** With separate get and set, two workers can both get, both decide, both set. A single read-modify-write call makes the race impossible to write by accident.
- **The limiter's logic is a pure function of (old state, now).** It does not touch any shared object. That is what lets a different backend run it, or translate it to a script.
- **Per-key buckets, created on first use.** A new key starts with a full bucket. A missing key arrives as `None`.
- **Plain tuples as state.** `(tokens, last_refill)` is easy to serialise later.
- **Matches the plain bucket.** A test runs both on the same time steps and compares answers, so the refactor cannot silently change behaviour.
- **Two limiters, one storage, one limit.** A test points two limiter objects at the same `MemoryStorage` and checks they share the limit. It simulates two workers but runs in one process.

## Known problems, left for later
- This is groundwork. There is no Redis or database backend, so nothing is actually shared across processes or servers yet.
- A Redis backend would need the read-modify-write to be atomic on the Redis side (a Lua script or similar). Wrapping a Python function around network calls would bring the race back.
- Different machines have different clocks. A shared backend needs a single time source, or the limiter has to take the time from the backend.
- `MemoryStorage` never deletes old keys, so memory grows with the number of distinct clients. Expiry is needed.
- Only the token bucket is keyed so far; the sliding window log is not.

## Questions to practise answering
1. Why is `update(key, fn)` safer than separate `get` and `set`?
2. Which part of this would break if the storage were Redis, and how would you fix it?
3. Why does clock choice matter once state is shared between machines?
4. How would you stop `MemoryStorage` growing forever?
