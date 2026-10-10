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
    raise NotImplementedError("Sender implementation in progress")
