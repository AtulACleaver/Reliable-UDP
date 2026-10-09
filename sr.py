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
    """Min-heap of per-packet retransmission deadlines with lazy cancellation."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.heap: list[tuple[float, int, int]] = []
        self.live: dict[int, int] = {}
        self._epoch = 0

    def schedule(self, seq: int, rto: float) -> None:
        self._epoch += 1
        self.live[seq] = self._epoch
        heapq.heappush(self.heap, (self.clock() + rto, seq, self._epoch))

    def start(self, seq: int, deadline: float) -> None:
        self._epoch += 1
        self.live[seq] = self._epoch
        heapq.heappush(self.heap, (deadline, seq, self._epoch))

    def cancel(self, seq: int) -> None:
        self.live.pop(seq, None)

    def is_active(self, seq: int) -> bool:
        return seq in self.live

    def next_deadline(self) -> float | None:
        while self.heap:
            deadline, seq, epoch = self.heap[0]
            if self.live.get(seq) == epoch:
                return deadline
            heapq.heappop(self.heap)
        return None

    def time_to_next_deadline(self) -> float | None:
        nxt = self.next_deadline()
        return max(0.0, nxt - self.clock()) if nxt is not None else None

    def pop_expired(self, now: float | None = None) -> list[int]:
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
