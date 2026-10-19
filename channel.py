"""channel.py: the middleman that damages traffic on purpose. Owner: Archit.

The sender and receiver never talk directly. Every packet goes through the
channel, which decides what happens to it: dropped, corrupted, duplicated,
delayed, or held back so later packets overtake it.

Why userspace instead of Linux tc netem?
Linux tc netem requires root/kernel privileges and is platform-specific.
Building an impairment emulator in userspace using Blake2b cryptographic hashes
guarantees cross-platform portability (Windows/macOS/Linux) and deterministic
repeatability across multi-protocol evaluations.
"""

import hashlib
import random
import struct
import time


class Channel:
    def __init__(self, loss=0.0, corrupt=0.0, dup=0.0, delay=0.0, jitter=0.0, reorder=0.0, rate=0.0, seed=None):
        self.loss = loss
        self.corrupt = corrupt
        self.dup = dup
        self.delay = delay
        self.jitter = jitter
        self.reorder = reorder
        self.rate = rate
        self.seed = seed
        self.rng = random.Random(seed)
        self.held = None
        self.tokens = 64 * 1024
        self.bucket_size = 64 * 1024
        self.last_time = time.monotonic()
        self.attempts = {}

    def _decide(self, salt, seq, attempt, p):
        """Hash-seeded impairment decision function.

        Derives impairment decisions from a cryptographic hash of packet identity:
            key = f"{seed}|{salt}|{seq}|{attempt}"
            hash = blake2b(key, 8 bytes)
            probability = int(hash) / 2**64 < p

        Eliminates stream-position dependency so Stop-and-Wait, Go-Back-N, and
        Selective Repeat encounter identical loss/damage patterns under the same seed.
        """
        if self.seed is None:
            return self.rng.random() < p
        key = f"{self.seed}|{salt}|{seq}|{attempt}".encode()
        h = hashlib.blake2b(key, digest_size=8).digest()
        val = int.from_bytes(h, "big") / (2**64)
        return val < p

    def damage(self, raw: bytes, direction: str = "to_receiver"):
        data = raw
        if not data:
            return []

        seq = 0
        if len(data) >= 4:
            seq = struct.unpack("!I", data[:4])[0]
        attempt = self.attempts.get(seq, 0) + 1
        self.attempts[seq] = attempt

        if self.loss > 0 and self._decide("loss", seq, attempt, self.loss):
            return []

        pkt = bytearray(data)
        if self.corrupt > 0 and len(pkt) > 0 and self._decide("corrupt", seq, attempt, self.corrupt):
            idx = self.rng.randint(0, len(pkt) - 1)
            pkt[idx] ^= 0xFF

        res = [bytes(pkt)]
        if self.dup > 0 and self._decide("dup", seq, attempt, self.dup):
            res.append(bytes(pkt))

        # Token-bucket rate limiter: bounds throughput to emulate link capacity (bytes/sec)
        if self.rate > 0:
            now = time.monotonic()
            elapsed = now - self.last_time
            self.tokens = min(self.bucket_size, self.tokens + elapsed * self.rate)
            self.last_time = now

            cost = len(data)
            if self.tokens < cost:
                wait_time = (cost - self.tokens) / self.rate
                time.sleep(wait_time)
                self.tokens = 0
                self.last_time = time.monotonic()
            else:
                self.tokens -= cost

        if self.delay > 0:
            d = self.delay
            if self.jitter > 0:
                d += self.rng.uniform(-self.jitter, self.jitter)
            if d > 0:
                time.sleep(d)

        if self.reorder > 0 and self._decide("reorder", seq, attempt, self.reorder):
            if self.held is None:
                self.held = res
                return []
            else:
                out = res + self.held
                self.held = None
                return out
        elif self.held is not None:
            out = res + self.held
            self.held = None
            return out

        return res


def damage(data, loss=0.0, corrupt=0.0, dup=0.0, delay=0.0, jitter=0.0, reorder=0.0, rate=0.0, seed=None):
    c = Channel(loss=loss, corrupt=corrupt, dup=dup, delay=delay, jitter=jitter, reorder=reorder, rate=rate, seed=seed)
    return c.damage(data)
