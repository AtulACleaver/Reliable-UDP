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


def recv_file(sock: socket.socket, window: int) -> bytes:
    """Receive a file using Selective Repeat ARQ with out-of-order buffering."""
    window = max(window, 1)
    recv_base = 0
    buffered: dict[int, bytes] = {}
    fin_seq: int | None = None
    fin_seen = False
    chunks: list[bytes] = []

    while True:
        timeout = LINGER if fin_seen else IDLE
        pkt, addr = receive(sock, timeout)
        if pkt is None:
            break

        if not (pkt["flags"] & DATA):
            continue

        seq = pkt["seq"]
        if pkt["flags"] & FIN:
            fin_seq = seq

        if recv_base <= seq < recv_base + window:
            sock.sendto(make_ack(seq), addr)
            buffered[seq] = pkt["payload"]

            while recv_base in buffered:
                chunks.append(buffered.pop(recv_base))
                if fin_seq is not None and recv_base == fin_seq:
                    fin_seen = True
                recv_base += 1

        elif seq < recv_base:
            # Re-ACK delivered packet if earlier ACK was dropped
            sock.sendto(make_ack(seq), addr)

    return b"".join(chunks)
