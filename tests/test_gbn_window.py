"""
Tests for Go-Back-N (GBN) pure-logic SendWindow.

Verifies:
1. Invariant: nextseq - base <= window
2. can_send() goes False when in-flight count == W
3. next_seq() raises when full
4. Cumulative ACK slides base and returns correct step count
5. Stale ACK (ack < base) is ignored and returns 0
6. ACK for unsent packet is ignored and returns 0
7. is_empty() tracks base == nextseq
8. outstanding() returns the exact unacknowledged sequence list [base .. nextseq - 1]
"""

import pytest

from rdt.window import SendWindow


def test_window_init():
    w = SendWindow(window=4, start=0)
    assert w.window == 4
    assert w.base == 0
    assert w.nextseq == 0
    assert w.is_empty() is True
    assert w.can_send() is True
    assert w.outstanding() == []


def test_window_invalid_size():
    with pytest.raises(ValueError):
        SendWindow(window=0)
    with pytest.raises(ValueError):
        SendWindow(window=-5)


def test_can_send_fills_to_w():
    """Fill the window and confirm can_send goes False at exactly W."""
    W = 4
    w = SendWindow(window=W, start=0)

    for expected_seq in range(W):
        assert w.can_send() is True
        seq = w.next_seq()
        assert seq == expected_seq

    # Now window is full: nextseq - base == W
    assert w.can_send() is False
    assert w.is_empty() is False
    assert w.outstanding() == [0, 1, 2, 3]

    # Trying to send another must raise RuntimeError
    with pytest.raises(RuntimeError):
        w.next_seq()


def test_cumulative_ack_slides_base():
    """A cumulative ACK beyond base slides by the right amount."""
    w = SendWindow(window=5, start=0)
    # Send 4 packets: 0, 1, 2, 3
    for _ in range(4):
        w.next_seq()

    # ACK 1 arrives (acknowledging packets 0 and 1)
    moved = w.on_ack(1)
    assert moved == 2
    assert w.base == 2
    assert w.nextseq == 4
    assert w.can_send() is True
    assert w.outstanding() == [2, 3]


def test_stale_ack_ignored():
    """A stale ACK below base moves nothing and returns 0."""
    w = SendWindow(window=4, start=0)
    for _ in range(3):
        w.next_seq()

    # Move base to 2
    w.on_ack(1)
    assert w.base == 2

    # Duplicate or stale ACK 0 arrives
    moved = w.on_ack(0)
    assert moved == 0
    assert w.base == 2
    assert w.outstanding() == [2]

    # Stale ACK 1 arrives
    moved = w.on_ack(1)
    assert moved == 0
    assert w.base == 2


def test_ack_last_packet_empties_window():
    """ACK of the last outstanding packet empties the window."""
    w = SendWindow(window=3, start=10)
    assert w.is_empty() is True

    w.next_seq()  # 10
    w.next_seq()  # 11
    assert w.is_empty() is False

    moved = w.on_ack(11)
    assert moved == 2
    assert w.base == 12
    assert w.nextseq == 12
    assert w.is_empty() is True
    assert w.outstanding() == []
    assert w.can_send() is True


def test_outstanding_resend_list():
    """outstanding() returns the exact resend list after partial ACK."""
    w = SendWindow(window=8, start=1)
    for _ in range(6):  # sends 1, 2, 3, 4, 5, 6
        w.next_seq()

    assert w.outstanding() == [1, 2, 3, 4, 5, 6]

    # ACK 3 arrives
    w.on_ack(3)
    # What a GBN timeout resends: 4, 5, 6
    assert w.outstanding() == [4, 5, 6]
