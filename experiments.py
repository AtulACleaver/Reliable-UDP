"""experiments.py: runs every experiment and writes results.csv. Owner: Harsha.

    python experiments.py --quick     one seed, 64 KB, writes quick.csv: checks everything runs
    python experiments.py             the real run: 46 configs x 3 seeds on 1 MB

If it stops halfway, run the same command again: rows already in the CSV
with sha256_ok True are skipped.
"""

