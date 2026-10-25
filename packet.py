"""packet.py: the packet format every protocol uses. Owner: Atul.

Header, 13 bytes, network byte order (big-endian):

    seq       4 bytes   number of this chunk (DATA packets)
    ack       4 bytes   number of the chunk being acknowledged (ACK packets)
    flags     1 byte    DATA = 1, ACK = 2, FIN = 4 (FIN marks the last chunk)
    length    2 bytes   payload length in bytes
    checksum  2 bytes   RFC 1071 checksum of the whole packet, computed with this field set to 0
"""

import socket
import struct
import time

HEADER = struct.Struct("!IIBHH")
HEADER_SIZE = HEADER.size
CHUNK_SIZE = 1024

DATA = 0x01
ACK = 0x02
FIN = 0x04


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"

    total = 0

    for i in range(0, len(data), 2):
        total += (data[i] << 8) | data[i + 1]

    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


def make_packet(seq: int, ack: int, flags: int,
                payload: bytes = b"") -> bytes:
    payload = bytes(payload)

    if len(payload) > CHUNK_SIZE:
        raise ValueError("Payload exceeds 1024 bytes")

    header = HEADER.pack(seq, ack, flags, len(payload), 0)
    check = checksum(header + payload)

    return HEADER.pack(seq, ack, flags, len(payload), check) + payload


def parse_packet(raw: bytes) -> dict | None:
    if len(raw) < HEADER_SIZE:
        return None

    seq, ack, flags, length, received_check = HEADER.unpack_from(raw)

    if length > CHUNK_SIZE or len(raw) != HEADER_SIZE + length:
        return None

    raw_without_check = raw[:11] + b"\x00\x00" + raw[13:]

    if checksum(raw_without_check) != received_check:
        return None

    return {
        "seq": seq,
        "ack": ack,
        "flags": flags,
        "payload": raw[HEADER_SIZE:],
    }


def split_file(data: bytes) -> list[bytes]:
    if not data:
        return [b""]

    return [
        data[i:i + CHUNK_SIZE]
        for i in range(0, len(data), CHUNK_SIZE)
    ]


def make_data(seq: int, payload: bytes, last: bool) -> bytes:
    flags = DATA | FIN if last else DATA
    return make_packet(seq, 0, flags, payload)


def make_ack(n: int) -> bytes:
    return make_packet(0, n, ACK)


def receive(sock: socket.socket, timeout: float):
    end_time = time.monotonic() + timeout

    while True:
        remaining = end_time - time.monotonic()

        if remaining <= 0:
            return None, None

        sock.settimeout(remaining)

        try:
            raw, addr = sock.recvfrom(65535)
        except (socket.timeout, TimeoutError):
            return None, None
        except ConnectionResetError:
            continue

        pkt = parse_packet(raw)

        if pkt is not None:
            return pkt, addr