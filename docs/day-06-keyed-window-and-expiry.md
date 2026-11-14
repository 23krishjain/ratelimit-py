# Day 6: keyed sliding window, and forgetting idle keys

## What I built
- `KeyedSlidingWindowLog`: the sliding window log with one window per key and state in a `Storage`, matching how `KeyedTokenBucket` works.
- `MemoryStorage(ttl=...)`: keys untouched for longer than `ttl` seconds are forgotten. Without it, every key ever seen stayed in the dict forever - a real memory leak for a long-running process whose keys are user ids or IPs.

## Decisions
- **State per key is a plain list of timestamps, not a deque.** `SlidingWindowLog` uses a deque because it lives in memory. The keyed version's state goes through `Storage`, and a future networked backend has to serialise the state; a list serialises, a deque does not. The cost is O(n) pruning by slicing instead of popleft, which is fine at these sizes.
- **Expiry is checked on access, not by a background thread or timer.** The store is a dict plus one lock; adding a sweeper thread would add a lifecycle to manage and a new way to break. The trade-off: a fully idle process holds its keys until the next call. For a rate limiter that is acceptable - memory only grows while traffic exists.
- **ttl is opt-in.** The default stays "keep everything", so existing behaviour does not change under someone's feet.
- **Touching any key triggers the sweep of all keys.** Simpler than tracking per-key deadlines in a heap, and the sweep is O(number of keys), same order of work the caller already pays per request in the common case.

## Known limits
- Still one process. `MemoryStorage` is the only backend; nothing is shared across processes or machines.
- Expiry is lazy (checked on access). Memory is reclaimed on the next call, not at the moment the ttl passes.
- The sliding window log keeps one timestamp per allowed request per key, so memory is O(total requests inside the window across all keys). The ttl bounds the number of keys, not the hits per active key.

## Questions to practise answering
1. Why store the keyed window's hits as a list instead of a deque? (Serialisation for a future shared backend.)
2. Why is expiry lazy? What breaks if the process is idle for an hour - and does anything break?
3. A colleague says "just add a cleanup thread". What do you weigh before agreeing?
4. What does ttl bound, and what does it not bound?
