"""sr.py: Selective Repeat reliable file transfer. Owner: Aqifa."""

import heapq
import socket
import time
from typing import TYPE_CHECKING, Callable

from packet import ACK, DATA, FIN, make_ack, make_data, receive, split_file

if TYPE_CHECKING:
    from rto import AdaptiveRTO, FixedRTO

LINGER = 2.0
IDLE = 30.0


class TimerHeap:
    """
    Min-heap of per-packet retransmission deadlines with lazy cancellation.

    Supports clock injection for deterministic, socket-free unit testing.
    Uses an epoch counter to guarantee that rescheduled or cancelled timers
    never trigger spuriously when popped.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.heap: list[tuple[float, int, int]] = []  # (deadline, seq, epoch)
        self.live: dict[int, int] = {}  # seq -> epoch
        self._epoch_counter = 0

    def schedule(self, seq: int, rto: float) -> None:
        """Schedule or reschedule a deadline for sequence number `seq`."""
        self._epoch_counter += 1
        epoch = self._epoch_counter
        self.live[seq] = epoch
        deadline = self.clock() + rto
        heapq.heappush(self.heap, (deadline, seq, epoch))

    def start(self, seq: int, deadline: float) -> None:
        """Schedule with an absolute deadline."""
        self._epoch_counter += 1
        epoch = self._epoch_counter
        self.live[seq] = epoch
        heapq.heappush(self.heap, (deadline, seq, epoch))

    def cancel(self, seq: int) -> None:
        """Cancel the active timer for sequence `seq` via lazy deletion."""
        self.live.pop(seq, None)

    def is_active(self, seq: int) -> bool:
        """Check if sequence `seq` currently has an active timer."""
        return seq in self.live

    def next_deadline(self) -> float | None:
        """Return earliest active deadline, discarding stale/cancelled entries."""
        while self.heap:
            deadline, seq, epoch = self.heap[0]
            if self.live.get(seq) == epoch:
                return deadline
            heapq.heappop(self.heap)
        return None

    def time_to_next_deadline(self) -> float | None:
        """Return remaining seconds until next deadline, or None if heap is empty."""
        nxt = self.next_deadline()
        if nxt is None:
            return None
        return max(0.0, nxt - self.clock())

    def pop_expired(self, now: float | None = None) -> list[int]:
        """Pop and return all sequence numbers whose deadlines have expired by `now`."""
        if now is None:
            now = self.clock()
        expired: list[int] = []
        while self.heap:
            deadline, seq, epoch = self.heap[0]
            if deadline > now:
                break
            heapq.heappop(self.heap)
            if self.live.get(seq) == epoch:
                del self.live[seq]
                expired.append(seq)
        return expired
