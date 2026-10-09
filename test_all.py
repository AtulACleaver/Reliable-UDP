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
import gbn
import channel
import rto
import sr
from channel import Channel, damage
from rto import FixedRTO, AdaptiveRTO


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

    if protocol == "gbn":
        orig_linger = gbn.LINGER
        gbn.LINGER = 0.05
        try:
            recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            recv_sock.bind(("127.0.0.1", 0))
            r_addr = recv_sock.getsockname()

            send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            send_sock.bind(("127.0.0.1", 0))

            res = []
            rt = threading.Thread(target=lambda: res.append(gbn.recv_file(recv_sock, 4)))
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
                        except TimeoutError:
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

                stats = gbn.send_file(send_sock, p_addr, data, 4, SimpleFixedRTO(0.04))
                pt.join(timeout=1.0)
                proxy_sock.close()
            else:
                stats = gbn.send_file(send_sock, r_addr, data, 4, SimpleFixedRTO(0.04))

            rt.join(timeout=1.0)
            recv_sock.close()
            send_sock.close()

            received_data = res[0] if res else b""
            stats["sha256_ok"] = (
                hashlib.sha256(received_data).digest() == hashlib.sha256(data).digest()
            )
            return stats
        finally:
            gbn.LINGER = orig_linger

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


def test_rto_adaptive():
    rto_inst = AdaptiveRTO(initial=0.2, min_rto=0.05, max_rto=10.0)
    assert abs(rto_inst.value() - 0.2) < 1e-6

    rto_inst.sample(0.1, False)
    assert rto_inst.srtt == 0.1
    assert rto_inst.rttvar == 0.05
    assert abs(rto_inst.value() - 0.3) < 1e-6

    rto_inst.sample(0.2, True)
    assert rto_inst.srtt == 0.1

    rto_inst.backoff()
    assert abs(rto_inst.value() - 0.6) < 1e-6

    rto_inst.forward()
    assert abs(rto_inst.value() - 0.3) < 1e-6


def test_rto_adaptive_first_sample():
    # RFC 6298 Section 2.2: SRTT <- R, RTTVAR <- R/2, RTO <- SRTT + 4 * RTTVAR = 3 * R
    rto = AdaptiveRTO(initial=1.0, min_rto=0.01, max_rto=10.0)
    rto.sample(0.08, False)
    assert abs(rto.srtt - 0.08) < 1e-6
    assert abs(rto.rttvar - 0.04) < 1e-6
    assert abs(rto.value() - 0.24) < 1e-6


def test_rto_adaptive_clamping():
    # Clamping against min_rto and max_rto
    rto = AdaptiveRTO(initial=0.2, min_rto=0.05, max_rto=2.0)
    rto.sample(0.001, False)
    assert rto.value() >= 0.05
    for _ in range(10):
        rto.backoff()
    assert rto.value() <= 2.0


def test_rto_adaptive_backoff_and_forward():
    rto = AdaptiveRTO(initial=0.2, min_rto=0.05, max_rto=5.0)
    rto.sample(0.1, False)
    assert abs(rto.value() - 0.3) < 1e-6
    rto.backoff()
    assert abs(rto.value() - 0.6) < 1e-6
    rto.backoff()
    assert abs(rto.value() - 1.2) < 1e-6
    rto.forward()
    assert abs(rto.value() - 0.3) < 1e-6


def test_rto_adaptive_variance_tracking():
    # Steady samples reduce variance; a spike immediately increases RTTVAR
    rto = AdaptiveRTO(initial=0.2, min_rto=0.01, max_rto=10.0)
    for _ in range(8):
        rto.sample(0.1, False)
    steady_var = rto.rttvar

    rto.sample(0.3, False)
    assert rto.rttvar > steady_var


def test_rto_karn_toggle():
    rto_inst = AdaptiveRTO(initial=0.2, karn=False)
    rto_inst.sample(0.1, False)
    assert rto_inst.srtt == 0.1
    rto_inst.sample(0.2, True)
    assert rto_inst.srtt != 0.1
    assert len(rto_inst.trace) == 2


def test_rto_karn_retransmission_ignored():
    # When karn=True (default), samples for resent packets are discarded
    rto = AdaptiveRTO(initial=0.2, karn=True)
    rto.sample(0.1, False)
    srtt_before = rto.srtt
    rttvar_before = rto.rttvar
    rto_val_before = rto.value()

    rto.sample(0.5, True)  # resent=True should be ignored
    assert rto.srtt == srtt_before
    assert rto.rttvar == rttvar_before
    assert rto.value() == rto_val_before
    assert len(rto.trace) == 1


def test_rto_trace_logging():
    # Verify trace entries have complete metrics for plotting and analysis
    rto = AdaptiveRTO(initial=0.2)
    rto.sample(0.08, False)
    assert len(rto.trace) == 1
    entry = rto.trace[0]
    for key in ["rtt", "srtt", "rttvar", "rto", "resent"]:
        assert key in entry
    assert entry["resent"] is False
    assert abs(entry["rtt"] - 0.08) < 1e-6


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


def test_channel_determinism():
    ch1 = Channel(loss=0.5, corrupt=0.2, seed=12345)
    ch2 = Channel(loss=0.5, corrupt=0.2, seed=12345)
    p1 = [ch1.damage(b"\x00\x00\x00\x01data") for _ in range(10)]
    p2 = [ch2.damage(b"\x00\x00\x00\x01data") for _ in range(10)]
    assert p1 == p2


def test_channel_determinism_seed_divergence():
    # Different seeds must produce different impairment outcomes
    ch1 = Channel(loss=0.5, corrupt=0.2, seed=11111)
    ch2 = Channel(loss=0.5, corrupt=0.2, seed=99999)
    p1 = [ch1.damage(b"\x00\x00\x00\x01data") for _ in range(20)]
    p2 = [ch2.damage(b"\x00\x00\x00\x01data") for _ in range(20)]
    assert p1 != p2


def test_channel_attempt_tracking():
    # Retransmissions of the same seq advance the attempt counter
    ch = Channel(loss=0.0, corrupt=0.0, seed=42)
    pkt = b"\x00\x00\x00\x07payload"
    ch.damage(pkt)
    assert ch.attempts.get(7) == 1
    ch.damage(pkt)
    assert ch.attempts.get(7) == 2


def test_channel_determinism_drill():
    # Determinism drill: Two independent channel instances with identical seed yield exact decisions
    ch1 = Channel(loss=0.25, corrupt=0.1, dup=0.1, reorder=0.1, seed=98765)
    ch2 = Channel(loss=0.25, corrupt=0.1, dup=0.1, reorder=0.1, seed=98765)

    stream1 = [ch1.damage(f"packet_{i}".encode()) for i in range(50)]
    stream2 = [ch2.damage(f"packet_{i}".encode()) for i in range(50)]
    assert stream1 == stream2


def test_channel_rate_limit():
    ch = Channel(rate=10000, seed=42)
    ch.tokens = 0
    start = time.monotonic()
    ch.damage(b"a" * 100)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.005


def test_channel_rate_limit_burst_capacity():
    # When tokens are full, initial packet passes without throttling
    ch = Channel(rate=50000, seed=42)
    start = time.monotonic()
    ch.damage(b"b" * 1024)
    elapsed = time.monotonic() - start
    assert elapsed < 0.01


def test_channel_rate_limit_replenishment():
    # Tokens replenish over elapsed time up to bucket_size
    ch = Channel(rate=20000, seed=42)
    ch.tokens = 0
    ch.last_time = time.monotonic() - 0.1
    now = time.monotonic()
    elapsed = now - ch.last_time
    ch.tokens = min(ch.bucket_size, ch.tokens + elapsed * ch.rate)
    assert ch.tokens >= 1500


def test_channel_reorder_damage_flow():
    # Reordering holds first packet and flushes inverted when second packet arrives
    ch = Channel(reorder=1.0, seed=42)
    p1 = packet.make_data(0, b"packet_zero", False)
    p2 = packet.make_data(1, b"packet_one", True)

    assert ch.damage(p1) == []
    flushed = ch.damage(p2)
    assert len(flushed) == 2
    assert flushed[0] == p2
    assert flushed[1] == p1


def test_channel_jitter_bounds():
    # Ensure jitter stays strictly bounded within [-jitter, +jitter]
    ch = Channel(delay=0.01, jitter=0.005, seed=42)
    for _ in range(20):
        d = ch.delay + ch.rng.uniform(-ch.jitter, ch.jitter)
        assert 0.005 <= d <= 0.015


def test_channel_corrupt_packet_checksum_failure():
    # Bit-corrupted packets produced by Channel.damage must fail packet.parse_packet checksum
    orig_pkt = packet.make_data(0, b"critical data chunk", True)
    assert packet.parse_packet(orig_pkt) is not None

    ch = Channel(corrupt=1.0, seed=42)
    damaged = ch.damage(orig_pkt)
    assert len(damaged) == 1
    assert packet.parse_packet(damaged[0]) is None


def test_channel_end_to_end_adaptive_rto_transfer():
    # Full end-to-end integration: file transfer through Channel with loss and AdaptiveRTO
    orig_linger = stopwait.LINGER
    stopwait.LINGER = 0.05
    try:
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.bind(("127.0.0.1", 0))
        r_addr = recv_sock.getsockname()

        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_sock.bind(("127.0.0.1", 0))

        test_data = b"Reliable-UDP Channel & AdaptiveRTO end-to-end integration payload" * 15
        received = []
        rt = threading.Thread(target=lambda: received.append(stopwait.recv_file(recv_sock, 1)))
        rt.start()

        ch = Channel(loss=0.1, corrupt=0.0, dup=0.0, delay=0.002, seed=123)
        proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        proxy_sock.bind(("127.0.0.1", 0))
        p_addr = proxy_sock.getsockname()

        def proxy():
            client_addr = None
            proxy_sock.settimeout(0.6)
            while True:
                try:
                    raw, addr = proxy_sock.recvfrom(65535)
                except (socket.timeout, TimeoutError):
                    break
                if addr == r_addr:
                    if client_addr:
                        for pkt in ch.damage(raw):
                            proxy_sock.sendto(pkt, client_addr)
                else:
                    client_addr = addr
                    for pkt in ch.damage(raw):
                        proxy_sock.sendto(pkt, r_addr)

        pt = threading.Thread(target=proxy)
        pt.start()

        adaptive_rto = AdaptiveRTO(initial=0.08, min_rto=0.02, max_rto=5.0)
        stats = stopwait.send_file(send_sock, p_addr, test_data, 1, adaptive_rto)

        pt.join(timeout=1.5)
        rt.join(timeout=1.5)
        proxy_sock.close()
        recv_sock.close()
        send_sock.close()

        assert received and hashlib.sha256(received[0]).digest() == hashlib.sha256(test_data).digest()
        assert stats["sent"] >= stats["packets"]
        assert len(adaptive_rto.trace) > 0
    finally:
        stopwait.LINGER = orig_linger


def test_rto_sub_millisecond_resolution():
    # Verify AdaptiveRTO handles sub-millisecond samples smoothly without underflow
    rto = AdaptiveRTO(initial=0.01, min_rto=0.001, max_rto=1.0)
    for _ in range(10):
        rto.sample(0.0004, False)
    assert rto.value() >= 0.001
    assert rto.srtt is not None and rto.srtt > 0


def test_channel_variable_payload_corruption():
    # Corruption preserves exact byte length across various packet sizes
    ch = Channel(corrupt=1.0, seed=42)
    for size in [1, 13, 100, 512, 1024]:
        raw = b"x" * size
        corrupted = ch.damage(raw)
        assert len(corrupted) == 1
        assert len(corrupted[0]) == size
        assert corrupted[0] != raw


def test_rto_min_max_boundary_invariance():
    # Extreme samples must never violate [min_rto, max_rto] invariant
    rto = AdaptiveRTO(initial=0.2, min_rto=0.05, max_rto=1.5)
    rto.sample(1e-9, False)
    assert rto.value() >= 0.05
    rto.sample(100.0, False)
# --- Shashank: gbn.py ---
def test_gbn_clean():
    """Verify clean file transfer with GBN (no loss) and matching SHA-256."""
    res = run("gbn")
    assert res["retx"] == 0
    assert res["sha256_ok"] is True
    assert res["timeouts"] == 0


def test_gbn_empty_file_transfer():
    """Verify GBN correctly handles empty file transfer (single FIN packet)."""
    res = run("gbn", data=b"")
    assert res["packets"] == 1
    assert res["sent"] == 1
    assert res["retx"] == 0
    assert res["sha256_ok"] is True


def test_gbn_loss():
    """Verify GBN recovers from dropped packets via Go-Back-N retransmission."""
    res = run("gbn", loss=0.1)
    assert res["retx"] > 0
    assert res["sha256_ok"] is True


def test_gbn_sender_stats_fields():
    """Verify all stats keys are populated accurately in GBN sender."""
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
    stats = gbn.send_file(sender_sock, resp_addr, b"testing gbn stats", 4, rto)
    t.join(timeout=1.0)
    sender_sock.close()
    responder_sock.close()

    for k in ["packets", "sent", "retx", "timeouts", "dup_acks", "seconds"]:
        assert k in stats, f"Missing key in stats: {k}"
    assert stats["packets"] == 1
    assert stats["sent"] == 1
    assert stats["retx"] == 0


def test_gbn_receiver_drops_out_of_order_and_re_acks():
    """GBN receiver must drop out-of-order packets and re-ACK expected - 1."""
    orig_linger = gbn.LINGER
    gbn.LINGER = 0.05
    try:
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.bind(("127.0.0.1", 0))
        r_port = recv_sock.getsockname()[1]
        received = []

        t = threading.Thread(target=lambda: received.append(gbn.recv_file(recv_sock, 4)))
        t.start()

        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(0.5)

        # Send packet 0 (expected)
        client.sendto(packet.make_data(0, b"part0", False), ("127.0.0.1", r_port))
        ack0_raw, _ = client.recvfrom(1024)
        ack0 = packet.parse_packet(ack0_raw)
        assert ack0 is not None and ack0["ack"] == 0

        # Send packet 2 (out of order! skipping packet 1)
        client.sendto(packet.make_data(2, b"part2", False), ("127.0.0.1", r_port))
        # Receiver drops packet 2 and re-ACKs 0 (expected - 1)
        re_ack0_raw, _ = client.recvfrom(1024)
        re_ack0 = packet.parse_packet(re_ack0_raw)
        assert re_ack0 is not None and re_ack0["ack"] == 0

        # Send missing packet 1
        client.sendto(packet.make_data(1, b"part1", False), ("127.0.0.1", r_port))
        ack1_raw, _ = client.recvfrom(1024)
        ack1 = packet.parse_packet(ack1_raw)
        assert ack1 is not None and ack1["ack"] == 1

        # Now send packet 2 with FIN
        client.sendto(packet.make_data(2, b"part2", True), ("127.0.0.1", r_port))
        ack2_raw, _ = client.recvfrom(1024)
        ack2 = packet.parse_packet(ack2_raw)
        assert ack2 is not None and ack2["ack"] == 2

        t.join(timeout=1.0)
        recv_sock.close()
        client.close()

        assert received[0] == b"part0part1part2"
    finally:
        gbn.LINGER = orig_linger


def test_gbn_cumulative_ack_slides_multiple():
    """Verify sender handles a cumulative ACK jumping across multiple in-flight packets."""
    sender_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_sock.bind(("127.0.0.1", 0))

    responder_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    responder_sock.bind(("127.0.0.1", 0))
    resp_addr = responder_sock.getsockname()

    def respond():
        # Receive packet 0
        _raw0, addr = responder_sock.recvfrom(2048)
        # Receive packet 1
        _raw1, addr = responder_sock.recvfrom(2048)
        # Receive packet 2
        _raw2, addr = responder_sock.recvfrom(2048)
        # Send cumulative ACK 2 directly (acknowledges 0, 1, 2 all at once)
        responder_sock.sendto(packet.make_ack(2), addr)

    t = threading.Thread(target=respond)
    t.start()

    # 3 chunks of data (total 3 packets)
    data = b"x" * 2500
    rto = SimpleFixedRTO(0.2)
    stats = gbn.send_file(sender_sock, resp_addr, data, 4, rto)
    t.join(timeout=1.0)
    sender_sock.close()
    responder_sock.close()

    assert stats["packets"] == 3
    assert stats["sent"] == 3
    assert stats["retx"] == 0
    assert stats["timeouts"] == 0


# --- Aqifa: sr.py ---
def test_sr_timer_heap_ordering():
    """Verify TimerHeap pops earlier deadlines first regardless of insertion order."""
    class FakeClock:
        def __init__(self):
            self.t = 100.0

        def __call__(self):
            return self.t

    clk = FakeClock()
    heap = sr.TimerHeap(clock=clk)
    heap.schedule(seq=2, rto=1.0)  # deadline 101.0
    heap.schedule(seq=1, rto=0.5)  # deadline 100.5
    heap.schedule(seq=3, rto=2.0)  # deadline 102.0

    assert heap.next_deadline() == 100.5
    assert heap.time_to_next_deadline() == 0.5

    clk.t = 100.8
    expired = heap.pop_expired()
    assert expired == [1]

    clk.t = 102.5
    expired = heap.pop_expired()
    assert expired == [2, 3]


def test_sr_timer_heap_cancellation():
    """Verify cancelling a timer via lazy deletion prevents it from expiring."""
    class FakeClock:
        def __init__(self):
            self.t = 10.0

        def __call__(self):
            return self.t

    clk = FakeClock()
    heap = sr.TimerHeap(clock=clk)
    heap.schedule(seq=10, rto=1.0)
    heap.schedule(seq=11, rto=2.0)

    # Cancel seq 10 before it expires
    heap.cancel(10)
    assert not heap.is_active(10)
    assert heap.is_active(11)
    # The next active deadline should skip 10 and return 11's deadline
    assert heap.next_deadline() == 12.0

    clk.t = 15.0
    expired = heap.pop_expired()
    assert expired == [11]


def test_sr_timer_heap_reschedule_epoch():
    """Verify epoch protection: rescheduling ignores stale earlier deadline."""
    class FakeClock:
        def __init__(self):
            self.t = 50.0

        def __call__(self):
            return self.t

    clk = FakeClock()
    heap = sr.TimerHeap(clock=clk)
    # Schedule seq 5 with short rto
    heap.schedule(seq=5, rto=1.0)  # deadline 51.0 (epoch 1)
    # Reschedule seq 5 with longer rto
    clk.t = 50.5
    heap.schedule(seq=5, rto=2.0)  # deadline 52.5 (epoch 2)

    # Advance clock past old deadline (51.0) but before new deadline (52.5)
    clk.t = 51.5
    expired = heap.pop_expired()
    assert expired == []  # Old epoch must NOT fire

    # Advance clock past new deadline
    clk.t = 53.0
    expired = heap.pop_expired()
    assert expired == [5]


def test_sr_timer_heap_pop_multiple():
    """Verify multiple timers expiring at the same time are all returned."""
    class FakeClock:
        def __init__(self):
            self.t = 0.0

        def __call__(self):
            return self.t

    clk = FakeClock()
    heap = sr.TimerHeap(clock=clk)
    heap.schedule(seq=1, rto=1.0)
    heap.schedule(seq=2, rto=1.0)
    heap.schedule(seq=3, rto=1.5)

    clk.t = 1.0
    expired = heap.pop_expired()
    assert sorted(expired) == [1, 2]
    assert heap.next_deadline() == 1.5


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
