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
    """Receive a file using Go-Back-N ARQ."""
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
            sock.sendto(make_ack(seq), addr)

        else:
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
    """Transmit data using Go-Back-N pipelined ARQ."""
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
    start_time = time.monotonic()

    while nextseq < base + window and nextseq < total:
        sock.sendto(packets[nextseq], peer)
        stats["sent"] += 1
        nextseq += 1

    stats["seconds"] = time.monotonic() - start_time
    return stats
