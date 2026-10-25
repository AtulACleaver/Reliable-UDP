"""transfer.py: runs one file transfer and checks it arrived intact. Owner: Atul.

Given code. It wires sender -> channel -> receiver on this machine, runs the
protocol you pick, compares SHA-256 hashes and returns one result row.

    python transfer.py --protocol sr --window 32 --loss 0.05
"""

