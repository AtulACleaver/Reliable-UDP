---
name: rdt-review
description: Reviews a pull request on the CS30003 RDT project before a human reviewer sees it. Use when asked to review a branch, a diff, or another teammate's lane.
---

# Reviewing an RDT pull request

Check in this order and report findings as a numbered list, worst first.

1. **Contracts.** Does the diff touch contracts/? If yes, that is a blocking
   finding regardless of everything else.

2. **Cross-lane imports.** Does any file import another lane's module instead of
   contracts/? Blocking.

3. **Banned primitives.** time.sleep, threading, os.fork, time.time for
   intervals, hardcoded ports, SO_REUSEPORT, third-party imports in rdt/ or
   channel/.

4. **Stats keys.** Any key written or read that is not in contracts/stats.md.

5. **Determinism.** Any randomness not derived from the hash of (seed,
   direction, seq, attempt).

6. **Correctness against the protocol.** For GBN: exactly one timer, restarted
   when base advances, stopped when the window empties, three state variables
   only. For SR: per-packet timers cancelled on ACK, receiver buffers
   out-of-order and flushes in order, window at most half the sequence space.

7. **Tests.** Does every behaviour change have a test that would fail without
   it? Does every integration test end in a SHA-256 comparison?

8. **Edge cases.** 0-byte file, 1-byte file, exactly one chunk, one chunk plus
   one byte.

End with the two or three questions a viva examiner would ask about this diff.
