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


Fixed = FixedRTO
