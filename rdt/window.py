"""
Pure-logic sliding window for Go-Back-N (GBN) ARQ.

Maintains the sender window state:
- base: oldest unacknowledged sequence number
- nextseq: next sequence number to send
- window: maximum number of packets in flight (W)

Invariant:
    nextseq - base <= window
"""


class SendWindow:
    """
    Go-Back-N sender-side sliding window.

    Tracks transmitted sequence numbers, in-flight frames, and cumulative ACKs.
    No sockets, no I/O, no time dependencies.
    """

    def __init__(self, window: int, start: int = 0) -> None:
        """
        Initialize the GBN sender window.

        Args:
            window: Maximum window size (W >= 1).
            start: Initial sequence number (default 0).
        """
        if window <= 0:
            raise ValueError(f"Window size must be positive, got {window}")
        self.window: int = window
        self.base: int = start
        self.nextseq: int = start

    def can_send(self) -> bool:
        """
        Check if a new packet can be transmitted under the window invariant.

        Returns:
            bool: True if nextseq - base < window, False otherwise.
        """
        return (self.nextseq - self.base) < self.window

    def next_seq(self) -> int:
        """
        Allocate and return the next sequence number, advancing nextseq.

        Returns:
            int: The allocated sequence number.

        Raises:
            RuntimeError: If the window is currently full.
        """
        if not self.can_send():
            raise RuntimeError(
                f"Window full: in flight {self.nextseq - self.base} >= {self.window}"
            )
        seq = self.nextseq
        self.nextseq += 1
        return seq

    def on_ack(self, ack: int) -> int:
        """
        Process a cumulative ACK.

        In GBN, an ACK for sequence number n confirms receipt of all packets
        up to and including n.

        - If ack is within [base, nextseq - 1], advances base to ack + 1
          and returns how many positions the window moved.
        - If ack < base, it is a stale ACK: ignored, returns 0.
        - If ack >= nextseq, it is an invalid ACK (acknowledging unsent data):
          ignored, returns 0.

        Args:
            ack: The cumulative acknowledged sequence number.

        Returns:
            int: The number of sequence slots the window advanced (>= 0).
        """
        if ack < self.base or ack >= self.nextseq:
            return 0

        moved = (ack + 1) - self.base
        self.base = ack + 1
        return moved

    def outstanding(self) -> list[int]:
        """
        Return the list of sequence numbers currently in flight [base .. nextseq - 1].
        This is the exact list of packets that a GBN timeout resends.

        Returns:
            list[int]: Sequence numbers sent but not yet acknowledged.
        """
        return list(range(self.base, self.nextseq))

    def is_empty(self) -> bool:
        """
        Check if all transmitted packets have been cumulatively acknowledged.

        Returns:
            bool: True if base == nextseq, False if there are packets in flight.
        """
        return self.base == self.nextseq

