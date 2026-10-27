"""transfer.py: runs one file transfer and checks it arrived intact. Owner: Atul.

Wires sender -> channel -> receiver on loopback, executes the selected ARQ
protocol, verifies SHA-256 data integrity, and outputs transfer statistics.

Usage:
    python transfer.py --protocol sr --window 32 --loss 0.05
    python transfer.py --protocol gbn --window 16 --loss 0.02 --rto adaptive
    python transfer.py --protocol sw --loss 0.01
"""

import argparse
import json
import sys

from experiments import run_transfer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute a single reliable file transfer across an emulated channel."
    )
    parser.add_argument(
        "--protocol",
        choices=["sw", "gbn", "sr"],
        default="gbn",
        help="ARQ protocol: 'sw' (Stop-and-Wait), 'gbn' (Go-Back-N), or 'sr' (Selective Repeat)",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=32,
        help="Sender window size in packets (default: 32; forced to 1 for sw)",
    )
    parser.add_argument(
        "--rto",
        default="adaptive",
        help="RTO estimator policy: 'adaptive' (RFC 6298 with Karn), 'adaptive-nokarn', or 'fixed:<seconds>' (e.g. fixed:0.5)",
    )
    parser.add_argument(
        "--loss",
        type=float,
        default=0.0,
        help="Channel packet loss rate between 0.0 and 1.0 (default: 0.0)",
    )
    parser.add_argument(
        "--reorder",
        type=float,
        default=0.0,
        help="Channel packet reordering probability (default: 0.0)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.002,
        help="One-way propagation delay in seconds (default: 0.002 = 2ms)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Pseudorandom seed for deterministic channel impairments (default: 1)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=65536,
        help="Payload file size in bytes to generate and transfer (default: 65536 = 64 KB)",
    )

    args = parser.parse_args()
    win = 1 if args.protocol == "sw" else args.window

    stats, _ = run_transfer(
        protocol=args.protocol,
        window=win,
        rto_spec=args.rto,
        loss=args.loss,
        reorder=args.reorder,
        seed=args.seed,
        file_size=args.size,
        delay=args.delay,
    )

    result = {
        "protocol": args.protocol,
        "window": win,
        "rto": args.rto,
        "loss": args.loss,
        "reorder": args.reorder,
        "seed": args.seed,
        "file_size": args.size,
        **stats,
    }

    print(json.dumps(result))
    sys.exit(0 if result.get("sha256_ok") else 1)


if __name__ == "__main__":
    main()
