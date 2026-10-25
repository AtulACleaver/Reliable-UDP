"""rto.py: how long to wait before resending. Owner: Archit.

Every RTO object has the same four methods, so the protocols never care
which one they were given:

    value()               seconds to wait right now
    sample(rtt, resent)   an ACK came back after `rtt` seconds
    backoff()             a timer ran out
    forward()             an ACK moved the window forward
"""


class FixedRTO:
    def __init__(self, timeout=0.2):
        self.initial = timeout
        self.timeout = timeout

    def value(self):
        return self.timeout

    def sample(self, rtt, resent):
        pass

    def backoff(self):
        self.timeout = min(60.0, self.timeout * 2)

    def forward(self):
        self.timeout = self.initial


class AdaptiveRTO:
    """RFC 6298 Jacobson/Karels Adaptive Retransmission Timeout Estimator.

    Maintains smoothed round-trip time (SRTT) and RTT variation (RTTVAR):
        SRTT   <- (1 - alpha) * SRTT + alpha * RTT       (alpha = 1/8)
        RTTVAR <- (1 - beta) * RTTVAR + beta * |SRTT - RTT| (beta = 1/4)
        RTO    <- SRTT + 4 * RTTVAR
    Clamped within [min_rto, max_rto]. Supports Karn's algorithm toggle.
    """

    def __init__(self, initial=0.2, min_rto=0.05, max_rto=60.0, karn=True):
        self.initial = initial
        self.min_rto = min_rto
        self.max_rto = max_rto
        self.karn = karn
        self.srtt = None
        self.rttvar = None
        self.rto = initial
        self.trace = []

    def value(self):
        """Current timeout value in seconds."""
        return self.rto

    def sample(self, rtt, resent):
        """Update RTO estimator with an RTT sample.

        Karn's Algorithm (1987): If the packet was retransmitted and karn is True,
        ignore the sample to resolve RTT measurement ambiguity.
        """
        if self.karn and resent:
            return

        if self.srtt is None:
            self.srtt = rtt
            self.rttvar = rtt / 2.0
            self.rto = self.srtt + 4 * self.rttvar
        else:
            self.rttvar = 0.75 * self.rttvar + 0.25 * abs(self.srtt - rtt)
            self.srtt = 0.875 * self.srtt + 0.125 * rtt
            self.rto = self.srtt + 4 * self.rttvar

        if self.rto < self.min_rto:
            self.rto = self.min_rto
        elif self.rto > self.max_rto:
            self.rto = self.max_rto

        self.trace.append({
            "rtt": rtt,
            "srtt": self.srtt,
            "rttvar": self.rttvar,
            "rto": self.rto,
            "resent": resent,
        })

    def backoff(self):
        """Exponential backoff upon timeout: double RTO up to max_rto."""
        self.rto = min(self.max_rto, self.rto * 2)

    def forward(self):
        """Restore calculated Jacobson/Karels RTO when ACK advances window."""
        if self.srtt is not None:
            calc = self.srtt + 4 * self.rttvar
            if calc < self.min_rto:
                self.rto = self.min_rto
            elif calc > self.max_rto:
                self.rto = self.max_rto
            else:
                self.rto = calc
        else:
            self.rto = self.initial


Fixed = FixedRTO
Adaptive = AdaptiveRTO


def make_rto(spec: str):
    """'fixed:0.5' -> FixedRTO(0.5), 'adaptive' -> AdaptiveRTO(), 'adaptive-nokarn' -> AdaptiveRTO(karn=False)."""
    if spec.startswith("fixed:"):
        return FixedRTO(float(spec.split(":", 1)[1]))
    if spec == "adaptive":
        return AdaptiveRTO(karn=True)
    if spec == "adaptive-nokarn":
        return AdaptiveRTO(karn=False)
    raise ValueError(f"unknown rto {spec!r}: use fixed:<seconds>, adaptive or adaptive-nokarn")
