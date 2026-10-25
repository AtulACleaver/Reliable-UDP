"""stopwait.py: Stop-and-Wait reliable file transfer. Owner: Atul."""

import socket
import time
from typing import TYPE_CHECKING

from packet import ACK, DATA, FIN, make_ack, make_data, receive, split_file

if TYPE_CHECKING:
    from rto import AdaptiveRTO, FixedRTO

LINGER = 2.0
IDLE = 30.0


def recv_file(sock: socket.socket, window: int) -> bytes:
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

    return b"".join(chunks)


def send_file(
    sock: socket.socket,
    peer: tuple[str, int],
    data: bytes,
    window: int,
    rto: "FixedRTO | AdaptiveRTO",
) -> dict:
    chunks = split_file(data)

    stats = {
        "packets": len(chunks),
        "sent": 0,
        "retx": 0,
        "timeouts": 0,
        "dup_acks": 0,
        "seconds": 0.0,
    }

    start = time.monotonic()

    for seq, payload in enumerate(chunks):
        packet = make_data(seq, payload, seq == len(chunks) - 1)
        attempts = 0

        while True:
            sent_at = time.monotonic()
            sock.sendto(packet, peer)

            stats["sent"] += 1

            if attempts > 0:
                stats["retx"] += 1

            attempts += 1
            deadline = sent_at + rto.value()

            while True:
                remaining = deadline - time.monotonic()
                pkt, _ = receive(sock, remaining)

                if pkt is None:
                    stats["timeouts"] += 1
                    rto.backoff()
                    break

                if not pkt["flags"] & ACK:
                    continue

                if pkt["ack"] != seq:
                    stats["dup_acks"] += 1
                    continue

                rto.sample(
                    time.monotonic() - sent_at,
                    resent=attempts > 1,
                )
                rto.forward()
                break

            if pkt is not None:
                break

    stats["seconds"] = time.monotonic() - start
    return stats