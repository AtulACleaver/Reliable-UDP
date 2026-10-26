"""experiments.py: runs every experiment and writes results.csv. Owner: Harsha.

    python experiments.py --quick     one seed, 64 KB, writes quick.csv: checks everything runs
    python experiments.py             the real run: 46 configs x 3 seeds on 1 MB

If it stops halfway, run the same command again: rows already in the CSV
with sha256_ok True are skipped.
"""


def configs() -> list[dict]:
    """Return the 46 experiment settings, without running a transfer."""
    out = []
    for protocol in ("sw", "gbn", "sr"):
        for loss in (0.0, 0.01, 0.02, 0.05, 0.1, 0.2):
            out.append({
                "sweep": "loss", "protocol": protocol,
                "window": 1 if protocol == "sw" else 32,
                "rto": "adaptive", "loss": loss, "reorder": 0.0,
            })
    for protocol in ("gbn", "sr"):
        for window in (1, 4, 16, 32, 64, 128):
            out.append({
                "sweep": "window", "protocol": protocol, "window": window,
                "rto": "adaptive", "loss": 0.05, "reorder": 0.0,
            })
    for protocol in ("gbn", "sr"):
        for reorder in (0.0, 0.01, 0.05, 0.1, 0.2):
            out.append({
                "sweep": "reorder", "protocol": protocol, "window": 32,
                "rto": "adaptive", "loss": 0.0, "reorder": reorder,
            })
    for protocol in ("gbn", "sr"):
        for rto in ("fixed:0.5", "adaptive", "adaptive-nokarn"):
            out.append({
                "sweep": "rto", "protocol": protocol, "window": 32,
                "rto": rto, "loss": 0.05, "reorder": 0.0,
            })
    return out
