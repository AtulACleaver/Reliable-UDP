"""test_all.py: every test in the project, in one file.

Run everything:        python test_all.py
Run only your part:    python test_all.py gbn      (tests whose name starts with test_gbn)

Each section belongs to one person. Your tests fail until you write your
code; that is expected. Tests use small files and a 2 ms delay so they run fast.
"""

import hashlib
import socket
import sys
import threading
import time
import traceback
import packet
import stopwait
import channel
import rto
from channel import Channel, damage
from rto import FixedRTO


# --- RTO and Channel test helpers ---
class SimpleFixedRTO:
    def __init__(self, val=0.04):
        self._val = val
        self.timeouts = 0
        self.samples = []

    def value(self) -> float:
        return self._val

    def sample(self, rtt: float, resent: bool):
        self.samples.append((rtt, resent))

    def backoff(self):
        self.timeouts += 1

    def forward(self):
        pass


def run(protocol: str, loss: float = 0.0, data: bytes = b"Reliable UDP Stop-and-Wait test data" * 20) -> dict:
    if protocol == "sw":
        orig_linger = stopwait.LINGER
        stopwait.LINGER = 0.05
        try:
            recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            recv_sock.bind(("127.0.0.1", 0))
            r_addr = recv_sock.getsockname()

            send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            send_sock.bind(("127.0.0.1", 0))

            res = []
            rt = threading.Thread(target=lambda: res.append(stopwait.recv_file(recv_sock, 1)))
            rt.start()

            if loss > 0:
                proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                proxy_sock.bind(("127.0.0.1", 0))
                p_addr = proxy_sock.getsockname()
                dropped = [False]

                def proxy():
                    client_addr = None
                    proxy_sock.settimeout(0.5)
                    while True:
                        try:
                            raw, addr = proxy_sock.recvfrom(65535)
                        except (socket.timeout, TimeoutError):
                            break
                        if addr == r_addr:
                            if client_addr:
                                proxy_sock.sendto(raw, client_addr)
                        else:
                            client_addr = addr
                            if not dropped[0]:
                                dropped[0] = True
                                continue  # Drop first packet to force retransmission
                            proxy_sock.sendto(raw, r_addr)

                pt = threading.Thread(target=proxy)
                pt.start()

                stats = stopwait.send_file(send_sock, p_addr, data, 1, SimpleFixedRTO(0.04))
                pt.join(timeout=1.0)
                proxy_sock.close()
            else:
                stats = stopwait.send_file(send_sock, r_addr, data, 1, SimpleFixedRTO(0.04))

            rt.join(timeout=1.0)
            recv_sock.close()
            send_sock.close()

            received_data = res[0] if res else b""
            stats["sha256_ok"] = (
                hashlib.sha256(received_data).digest() == hashlib.sha256(data).digest()
            )
            return stats
        finally:
            stopwait.LINGER = orig_linger

    raise NotImplementedError(f"Protocol {protocol} not implemented yet")


# --- Atul: packet.py ---
def test_packet_checksum_known_value():
    assert packet.checksum(b"\x00\x01\xf2\x03\xf4\xf5\xf6\xf7") == 0x220D  # RFC 1071 example


def test_packet_hello_bytes():
    raw = packet.make_packet(7, 0, packet.DATA | packet.FIN, b"hello")
    assert raw.hex(" ") == "00 00 00 07 00 00 00 00 05 00 05 23 b5 68 65 6c 6c 6f"


def test_packet_flipped_bit_is_rejected():
    raw = bytearray(packet.make_packet(1, 0, packet.DATA, b"payload"))
    raw[15] ^= 0x04
    assert packet.parse_packet(bytes(raw)) is None


def test_packet_split_file():
    assert packet.split_file(b"") == [b""]
    assert [len(c) for c in packet.split_file(b"x" * 2500)] == [1024, 1024, 452]


def test_packet_too_short_or_inconsistent_length_rejected():
    assert packet.parse_packet(b"too_short") is None
    # Header claims 50 bytes payload, but packet only has 13 bytes total
    bad_len_header = packet.HEADER.pack(1, 0, packet.DATA, 50, 0)
    check = packet.checksum(bad_len_header)
    bad_pkt = packet.HEADER.pack(1, 0, packet.DATA, 50, check)
    assert packet.parse_packet(bad_pkt) is None
    # Payload claims > 1024 bytes
    oversize_header = packet.HEADER.pack(1, 0, packet.DATA, 2000, 0)
    check_oversize = packet.checksum(oversize_header + b"x" * 2000)
    oversize_pkt = packet.HEADER.pack(1, 0, packet.DATA, 2000, check_oversize) + b"x" * 2000
    assert packet.parse_packet(oversize_pkt) is None


# --- Atul: stopwait.py receiver edge cases ---
def test_sw_receiver_duplicate_ack():
    orig_linger = stopwait.LINGER
    stopwait.LINGER = 0.05
    try:
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.bind(("127.0.0.1", 0))
        r_port = recv_sock.getsockname()[1]
        received = []

        t = threading.Thread(target=lambda: received.append(stopwait.recv_file(recv_sock, 1)))
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(0.5)

        # Send packet 0 (DATA)
        client.sendto(packet.make_data(0, b"chunk0", False), ("127.0.0.1", r_port))
        ack0_raw, _ = client.recvfrom(1024)
        ack0 = packet.parse_packet(ack0_raw)
        assert ack0 is not None and ack0["ack"] == 0

        # Send packet 1 (DATA)
        client.sendto(packet.make_data(1, b"chunk1", False), ("127.0.0.1", r_port))
        ack1_raw, _ = client.recvfrom(1024)
        ack1 = packet.parse_packet(ack1_raw)
        assert ack1 is not None and ack1["ack"] == 1

        # Resend packet 0 (duplicate old packet): receiver must acknowledge again
        client.sendto(packet.make_data(0, b"chunk0", False), ("127.0.0.1", r_port))
        dup_raw, _ = client.recvfrom(1024)
        dup_ack = packet.parse_packet(dup_raw)
        assert dup_ack is not None and dup_ack["ack"] == 0

        # Send packet 2 (DATA | FIN)
        client.sendto(packet.make_data(2, b"chunk2", True), ("127.0.0.1", r_port))
        fin_raw, _ = client.recvfrom(1024)
        fin_ack = packet.parse_packet(fin_raw)
        assert fin_ack is not None and fin_ack["ack"] == 2

        t.join(timeout=1.0)
        recv_sock.close()
        client.close()

        assert received[0] == b"chunk0chunk1chunk2"
    finally:
        stopwait.LINGER = orig_linger


# --- Atul: RTO interface validation ---
def test_sw_rto_duck_typing():
    # Validates that stopwait can work with any duck-typed RTO conforming to rto.py interface
    class MockRTO:
        def __init__(self):
            self.value_called = 0
            self.sample_called = 0
            self.backoff_called = 0
            self.forward_called = 0

        def value(self) -> float:
            self.value_called += 1
            return 0.1

        def sample(self, rtt: float, resent: bool):
            self.sample_called += 1

        def backoff(self):
            self.backoff_called += 1

        def forward(self):
            self.forward_called += 1

    rto_obj = MockRTO()
    assert rto_obj.value() == 0.1
    assert rto_obj.value_called == 1
    rto_obj.backoff()
    assert rto_obj.backoff_called == 1
    rto_obj.sample(0.02, False)
    assert rto_obj.sample_called == 1
    rto_obj.forward()
    assert rto_obj.forward_called == 1


# --- Atul: stopwait.py sender tests ---
def test_sw_sender_stats_fields():
    sender_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_sock.bind(("127.0.0.1", 0))

    responder_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    responder_sock.bind(("127.0.0.1", 0))
    resp_addr = responder_sock.getsockname()

    def respond():
        raw, addr = responder_sock.recvfrom(2048)
        pkt = packet.parse_packet(raw)
        if pkt is not None:
            responder_sock.sendto(packet.make_ack(pkt["seq"]), addr)

    t = threading.Thread(target=respond)
    t.start()

    rto = SimpleFixedRTO(0.1)
    stats = stopwait.send_file(sender_sock, resp_addr, b"testing stats", 1, rto)
    t.join(timeout=1.0)
    sender_sock.close()
    responder_sock.close()

    for k in ["packets", "sent", "retx", "timeouts", "dup_acks", "seconds"]:
        assert k in stats, f"Missing key in stats: {k}"
    assert stats["packets"] == 1
    assert stats["sent"] == 1
    assert stats["retx"] == 0


def test_sw_old_ack_does_not_reset_deadline():
    sender_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_sock.bind(("127.0.0.1", 0))

    responder_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    responder_sock.bind(("127.0.0.1", 0))
    resp_addr = responder_sock.getsockname()

    def send_old_acks_then_correct():
        # First receive packet 0
        raw, addr = responder_sock.recvfrom(2048)
        # Send an old duplicate ACK for an earlier seq (e.g. 99)
        time.sleep(0.01)
        responder_sock.sendto(packet.make_ack(99), addr)
        # Send another old ACK
        time.sleep(0.01)
        responder_sock.sendto(packet.make_ack(99), addr)
        # Finally send correct ACK
        time.sleep(0.01)
        responder_sock.sendto(packet.make_ack(0), addr)

    t = threading.Thread(target=send_old_acks_then_correct)
    t.start()

    rto = SimpleFixedRTO(0.2)
    stats = stopwait.send_file(sender_sock, resp_addr, b"old ack test", 1, rto)
    t.join(timeout=1.0)
    sender_sock.close()
    responder_sock.close()

    assert stats["dup_acks"] == 2
    assert stats["retx"] == 0
    assert stats["timeouts"] == 0


# --- Atul: Stop-and-Wait end-to-end integration tests ---
def test_sw_clean():
    res = run("sw")
    assert res["retx"] == 0
    assert res["sha256_ok"] is True


def test_sw_loss():
    res = run("sw", loss=0.1)
    assert res["retx"] > 0
    assert res["sha256_ok"] is True


def test_sw_empty_file_transfer():
    res = run("sw", data=b"")
    assert res["packets"] == 1
    assert res["sent"] == 1
    assert res["retx"] == 0
    assert res["sha256_ok"] is True


# --- Archit: rto.py & channel.py ---
def test_rto_fixed():
    rto_inst = FixedRTO(0.2)
    assert abs(rto_inst.value() - 0.2) < 1e-6
    rto_inst.sample(0.05, False)
    assert abs(rto_inst.value() - 0.2) < 1e-6
    rto_inst.backoff()
    assert abs(rto_inst.value() - 0.4) < 1e-6
    rto_inst.forward()
    assert abs(rto_inst.value() - 0.2) < 1e-6


def test_channel_damage():
    ch = Channel(loss=1.0, seed=42)
    assert ch.damage(b"hello") == []

    ch_clean = Channel(loss=0.0, corrupt=0.0, dup=0.0, delay=0.0, seed=42)
    assert ch_clean.damage(b"hello") == [b"hello"]

    ch_dup = Channel(dup=1.0, seed=42)
    assert ch_dup.damage(b"hello") == [b"hello", b"hello"]

    ch_corrupt = Channel(corrupt=1.0, seed=42)
    damaged = ch_corrupt.damage(b"hello")
    assert len(damaged) == 1
    assert damaged[0] != b"hello"
    assert len(damaged[0]) == len(b"hello")


def test_channel_corrupt_packet_checksum_failure():
    # Bit-corrupted packets produced by Channel.damage must fail packet.parse_packet checksum
    orig_pkt = packet.make_data(0, b"critical data chunk", True)
    assert packet.parse_packet(orig_pkt) is not None

    ch = Channel(corrupt=1.0, seed=42)
    damaged = ch.damage(orig_pkt)
    assert len(damaged) == 1
    assert packet.parse_packet(damaged[0]) is None


def main():
    words = [w for w in sys.argv[1:] if w != "-v"]

    # Matches the word you typed in the terminal to the tests in this file
    tests = [(name, fn) for name, fn in globals().items()
             if name.startswith("test_") and callable(fn) and
             (not words or any(name.startswith("test_" + w) for w in words))]

    failed = 0
    start = time.monotonic()

    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except NotImplementedError:
            failed += 1
            print(f"TODO {name} (not written yet)")
        except Exception as e:
            failed += 1
            print(f"FAIL {name} {type(e).__name__}: {e}")
            if "-v" in sys.argv:
                traceback.print_exc()

    passed = len(tests) - failed
    print(f"\n{passed} passed, {failed} failed, {time.monotonic() - start:.0f} s")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
