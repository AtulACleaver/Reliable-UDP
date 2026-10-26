"""gbn.py: Go-Back-N reliable file transfer. Owner: Shashank."""

import socket
import time
from typing import TYPE_CHECKING

from packet import ACK, DATA, FIN, make_ack, make_data, receive, split_file

if TYPE_CHECKING:
    from rto import AdaptiveRTO, FixedRTO

LINGER = 2.0
IDLE = 30.0


def recv_file(sock: socket.socket, window: int) -> bytes:
    """
    Receive a file using Go-Back-N ARQ.

    Maintains zero receive buffer.
    - If arriving packet seq == expectedseq: accept payload, advance expectedseq, send cumulative ACK.
    - If arriving packet is out-of-order or corrupt: discard payload, re-ACK expectedseq - 1.

    Args:
        sock: Bound UDP socket to receive from.
        window: Window size (receiver ignores window size since GBN has W_r = 1).

    Returns:
        bytes: Complete reassembled file payload.
    """
    chunks = []
    expected = 0
    fin_seen = False

    while True:
        timeout = LINGER if fin_seen else IDLE
        pkt, addr = receive(sock, timeout)

        if pkt is None:
            break

        if not pkt["flags"] & DATA:
            continue

        seq = pkt["seq"]

        if seq == expected:
            chunks.append(pkt["payload"])
            expected += 1

            if pkt["flags"] & FIN:
                fin_seen = True

            sock.sendto(make_ack(seq), addr)

        elif seq < expected:
            # Duplicate old packet retransmitted: acknowledge it
            sock.sendto(make_ack(seq), addr)

        else:
            # Out-of-order packet (seq > expected): drop payload, re-ACK expected - 1
            if expected > 0:
                sock.sendto(make_ack(expected - 1), addr)

    return b"".join(chunks)


def send_file(
    sock: socket.socket,
    peer: tuple[str, int],
    data: bytes,
    window: int,
    rto: "FixedRTO | AdaptiveRTO",
) -> dict:
    """
    Transmit data using Go-Back-N pipelining ARQ.

    Maintains window invariant: nextseq - base <= window.
    Single timer runs for the oldest unacknowledged packet (`base`).
    Upon timeout, retransmits all outstanding packets [base .. nextseq - 1].

    Args:
        sock: Bound UDP socket to transmit from.
        peer: Destination (host, port) tuple.
        data: File bytes to transfer.
        window: Pipelined sender window capacity (W >= 1).
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

    base = 0
    nextseq = 0
    timer_deadline: float | None = None
    send_times: dict[int, float] = {}
    resent: set[int] = set()

    start_time = time.monotonic()

    while base < total:
        # Transmit all packets allowed by the window limit
        while nextseq < base + window and nextseq < total:
            now = time.monotonic()
            sock.sendto(packets[nextseq], peer)
            stats["sent"] += 1
            send_times[nextseq] = now

            # If window was empty, start timer for this oldest packet
            if base == nextseq:
                timer_deadline = now + rto.value()

            nextseq += 1

        # Wait for an ACK until the base packet timer deadline
        remaining = 0.0
        if timer_deadline is not None:
            remaining = max(0.0, timer_deadline - time.monotonic())

        pkt, _ = receive(sock, remaining)

        if pkt is None:
            # Timeout! Base packet was not acknowledged in time.
            stats["timeouts"] += 1
            rto.backoff()

            # Go-Back-N: Retransmit every unacknowledged packet in flight
            now = time.monotonic()
            for seq in range(base, nextseq):
                sock.sendto(packets[seq], peer)
                stats["sent"] += 1
                stats["retx"] += 1
                resent.add(seq)

            # Restart timer
            timer_deadline = now + rto.value()

        else:
            if not (pkt["flags"] & ACK):
                continue

            ack = pkt["ack"]

            if ack >= base:
                # Cumulative ACK advances the window base to ack + 1
                if ack in send_times:
                    is_resent = ack in resent
                    rtt = time.monotonic() - send_times[ack]
                    rto.sample(rtt, is_resent)

                base = ack + 1
                rto.forward()

                # If all outstanding packets are now ACKed, stop timer
                # Otherwise, restart timer for the new oldest unacknowledged packet
                if base == nextseq:
                    timer_deadline = None
                else:
                    timer_deadline = time.monotonic() + rto.value()

            else:
                # ack < base: duplicate or stale ACK
                stats["dup_acks"] += 1

    stats["seconds"] = time.monotonic() - start_time
    return stats
