# Week 1 Plan · Shashank (Lane 2: Go-Back-N Window)

> **Goal:** `pytest tests/test_gbn_window.py` is green in CI, and your GBN sender FSM is committed as a diagram you drew from memory.
> No sockets this week.

## Overview & Architecture

### The Problem Stop-and-Wait Has
Atul's Stop-and-Wait sends one packet per round trip. At 10 ms RTT and 1 KB packets that is 100 KB/s, no matter how fast the link is. The link sits idle for almost the entire RTT while the sender waits. The fix is pipelining: keep several packets in flight at once. Go-Back-N is the simplest correct way to do that.

The cost of pipelining is bookkeeping. With one packet outstanding you know exactly which ACK belongs to which packet. With sixteen, you need a window.

### Three State Variables (Exactly Three)
```
base      oldest sequence number sent but not yet acknowledged
nextseq   the next sequence number to hand out
window    how many may be outstanding at once (W)

invariant:  nextseq - base <= window
```

```
  acked          in flight          usable          not yet
[.........][==================][............][..............]
           ^                   ^
         base               nextseq
         |<------- window = 8 ------->|
```

Most GBN bugs are a fourth variable somebody added because the code felt unclear. If you find yourself wanting one, the answer is almost always that `base` should have moved and did not. Resist.

### What "Cumulative" Means
ACK *n* means "I have received everything up to and including *n*". Not "I received *n*".
- A single ACK can slide the window by ten. If ACKs 3 through 11 are lost but ACK 12 arrives, the window jumps from base=3 to base=13 in one step and nothing is retransmitted. Lost ACKs are usually free in GBN.
- An ACK below `base` is stale. Ignore it. Do not move anything backwards.
- The receiver keeps one variable: `expectedseq`. In-order packet: deliver it, increment, ACK it. Anything else: discard it and re-ACK `expectedseq - 1`. No receive buffer.

### One Timer for Oldest Unacknowledged Packet
```
send, window was empty   -> start timer
base advances            -> restart timer (there is a new oldest packet)
window becomes empty     -> stop timer
timer fires              -> resend base .. nextseq-1, all of it, restart timer
```

### The Sequence Space Trap
GBN needs at least **W + 1** distinct sequence numbers.
Counterexample if sequence space = {0, 1, 2, 3} and W = 4:
1. Sender sends 0, 1, 2, 3. Receiver receives all 4, delivers, ACKs each.
2. All 4 ACKs lost in transit.
3. Sender times out, retransmits 0, 1, 2, 3.
4. Receiver expecting 0 again (wrapped) and accepts retransmitted 0 as brand new packet -> duplicate delivered -> file corrupted.

---

## Daily Breakdown

### Monday: Clone, Verify, Read
- Verify git identity:
  ```bash
  git config user.name "Shashank Shekhar Pandey"
  git config user.email "pandeyshashankshekar@gmail.com"
  git log -1 --format='%an <%ae>'
  ```
- Study Kurose 3.4.3 (two hours), including both FSM diagrams.

### Tuesday: `rdt/window.py`, Pure Functions Only
Branch `lane2/gbn-window`. No imports beyond standard library, no socket, no clock.
```python
class SendWindow:
    def __init__(self, window: int, start: int = 0): ...
    def can_send(self) -> bool: ...          # nextseq - base < window
    def next_seq(self) -> int: ...           # hand out and advance nextseq
    def on_ack(self, ack: int) -> int: ...   # cumulative; returns how far base moved
    def outstanding(self) -> list[int]: ...  # base .. nextseq-1, what a timeout resends
    def is_empty(self) -> bool: ...          # base == nextseq
```
*Note: Write `SendWindow` by hand. It is individually graded.*

### Wednesday: Tests That Can Actually Fail
Test suite in `tests/test_gbn_window.py`:
- Fill window and confirm `can_send()` becomes `False` at exactly `W`.
- Cumulative ACK beyond `base` slides by the right amount.
- Stale ACK below `base` moves nothing.
- ACK of the last outstanding packet empties the window (`is_empty() == True`).
- `outstanding()` returns exact resend list after partial ACK.

### Thursday & Friday: The FSM, From Memory
Draw GBN sender FSM from memory. Diff against Kurose 3.4.3. Commit as `docs/fsm-gbn.md` (Mermaid) with narrative for each transition.

### Saturday: Merged and Green
PR merged to `main`, CI green.

### Sunday: The Gate
30-minute live demo.
