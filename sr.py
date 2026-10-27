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


def recv_file(sock: socket.socket, window: int) -> bytes:
    """
    Receive a file using Selective Repeat ARQ.

    Maintains a receive buffer of capacity `window`.
    - If arriving packet seq in [recv_base .. recv_base + window - 1]:
      Send individual ACK for seq, buffer payload.
      If seq == recv_base: advance recv_base and flush contiguous buffered packets.
    - If arriving packet seq in [recv_base - window .. recv_base - 1] (or seq < recv_base):
      Re-ACK seq so sender knows it arrived even if earlier ACK was lost.
    - Otherwise: ignore out-of-window packet.

    Args:
        sock: Bound UDP socket to receive from.
        window: Receive window capacity.

    Returns:
        bytes: Complete reassembled file payload.
    """
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

            if seq == recv_base:
                while recv_base in buffered:
                    payload = buffered.pop(recv_base)
                    chunks.append(payload)
                    if fin_seq is not None and recv_base == fin_seq:
                        fin_seen = True
                    recv_base += 1

        elif seq < recv_base:
            sock.sendto(make_ack(seq), addr)

    return b"".join(chunks)


def send_file(
    sock: socket.socket,
    peer: tuple[str, int],
    data: bytes,
    window: int,
    rto: "FixedRTO | AdaptiveRTO",
) -> dict:
    """
    Transmit data using Selective Repeat pipelined ARQ with individual packet timers.

    Maintains window invariant: nextseq - send_base <= window.
    Maintains independent timer per in-flight unacknowledged packet using TimerHeap.
    Upon timeout of any packet, resends ONLY that packet.

    Args:
        sock: Bound UDP socket to transmit from.
        peer: Destination (host, port) tuple.
        data: File bytes to transfer.
        window: Sender window capacity.
        rto: Retransmission timeout estimator.

    Returns:
        dict: Stats mapping with keys: packets, sent, retx, timeouts, dup_acks, seconds.
    """
    window = max(window, 1)
    chunks = split_file(data)
    total = len(chunks)
    packets = [make_data(i, chunks[i], i == total - 1) for i in range(total)]

    stats = {
        "packets": total,
        "sent": 0,
        "retx": 0,
        "timeouts": 0,
        "dup_acks": 0,
        "seconds": 0.0,
    }

    send_base = 0
    nextseq = 0
    acked: set[int] = set()
    timer_heap = TimerHeap()
    send_times: dict[int, float] = {}
    resent: set[int] = set()

    start_time = time.monotonic()

    while send_base < total:
        while nextseq < send_base + window and nextseq < total:
            sock.sendto(packets[nextseq], peer)
            stats["sent"] += 1
            now = time.monotonic()
            send_times[nextseq] = now
            timer_heap.schedule(nextseq, rto.value())
            nextseq += 1

        remaining = timer_heap.time_to_next_deadline()
        if remaining is None:
            remaining = rto.value()

        pkt, _ = receive(sock, remaining)

        now = time.monotonic()
        expired = timer_heap.pop_expired(now + 0.0005 if pkt is None else now)

        if expired:
            stats["timeouts"] += len(expired)
            rto.backoff()
            for seq in expired:
                if seq not in acked and seq < total:
                    sock.sendto(packets[seq], peer)
                    stats["sent"] += 1
                    stats["retx"] += 1
                    resent.add(seq)
                    timer_heap.schedule(seq, rto.value())

        if pkt is not None:
            if not (pkt["flags"] & ACK):
                continue

            ack = pkt["ack"]

            if ack < send_base:
                stats["dup_acks"] += 1
            elif ack in acked:
                stats["dup_acks"] += 1
            elif send_base <= ack < nextseq:
                acked.add(ack)
                timer_heap.cancel(ack)

                if ack in send_times:
                    is_resent = ack in resent
                    rtt = time.monotonic() - send_times[ack]
                    rto.sample(rtt, is_resent)

                rto.forward()

                if ack == send_base:
                    while send_base in acked:
                        send_base += 1

    stats["seconds"] = time.monotonic() - start_time
    return stats
