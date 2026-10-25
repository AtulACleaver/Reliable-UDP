"""rto.py: how long to wait before resending. Owner: Archit.

Every RTO object has the same four methods, so the protocols never care
which one they were given:

    value()               seconds to wait right now
    sample(rtt, resent)   an ACK came back after `rtt` seconds
    backoff()             a timer ran out
    forward()             an ACK moved the window forward
"""
