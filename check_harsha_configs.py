"""Focused local checks, not a replacement for test_all.py."""
import unittest
from collections import Counter
from itertools import product
from experiments import configs


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.rows = configs()

    def test_01_shape_and_types(self):
        self.assertIsInstance(self.rows, list)
        self.assertEqual(len(self.rows), 46)
        keys = {"sweep", "protocol", "window", "rto", "loss", "reorder"}
        for row in self.rows:
            self.assertEqual(set(row), keys)
            self.assertIsInstance(row["window"], int)
            self.assertIsInstance(row["loss"], float)
            self.assertIsInstance(row["reorder"], float)
            for key in ("sweep", "protocol", "rto"):
                self.assertIsInstance(row[key], str)

    def test_02_counts(self):
        self.assertEqual(Counter(r["sweep"] for r in self.rows),
                         {"loss": 18, "window": 12, "reorder": 10, "rto": 6})

    def test_03_loss_grid_and_controls(self):
        rows = [r for r in self.rows if r["sweep"] == "loss"]
        expected = set(product(("sw", "gbn", "sr"),
                               (0.0, 0.01, 0.02, 0.05, 0.1, 0.2)))
        self.assertEqual({(r["protocol"], r["loss"]) for r in rows}, expected)
        for r in rows:
            self.assertEqual(r["window"], 1 if r["protocol"] == "sw" else 32)
            self.assertEqual((r["rto"], r["reorder"]), ("adaptive", 0.0))

    def test_04_window_grid_and_controls(self):
        rows = [r for r in self.rows if r["sweep"] == "window"]
        expected = set(product(("gbn", "sr"), (1, 4, 16, 32, 64, 128)))
        self.assertEqual({(r["protocol"], r["window"]) for r in rows}, expected)
        for r in rows:
            self.assertEqual((r["rto"], r["loss"], r["reorder"]),
                             ("adaptive", 0.05, 0.0))

    def test_05_reorder_grid_and_controls(self):
        rows = [r for r in self.rows if r["sweep"] == "reorder"]
        expected = set(product(("gbn", "sr"), (0.0, 0.01, 0.05, 0.1, 0.2)))
        self.assertEqual({(r["protocol"], r["reorder"]) for r in rows}, expected)
        for r in rows:
            self.assertEqual((r["window"], r["rto"], r["loss"]),
                             (32, "adaptive", 0.0))

    def test_06_rto_grid_and_controls(self):
        rows = [r for r in self.rows if r["sweep"] == "rto"]
        expected = set(product(("gbn", "sr"),
                               ("fixed:0.5", "adaptive", "adaptive-nokarn")))
        self.assertEqual({(r["protocol"], r["rto"]) for r in rows}, expected)
        for r in rows:
            self.assertEqual((r["window"], r["loss"], r["reorder"]),
                             (32, 0.05, 0.0))

    def test_07_unique_within_sweep(self):
        identities = [tuple(sorted(r.items())) for r in self.rows]
        self.assertEqual(len(set(identities)), 46)

    def test_08_stable_order(self):
        self.assertEqual(self.rows, configs())
        self.assertEqual(self.rows[0], {
            "sweep": "loss", "protocol": "sw", "window": 1,
            "rto": "adaptive", "loss": 0.0, "reorder": 0.0})
        self.assertEqual(self.rows[18]["sweep"], "window")
        self.assertEqual(self.rows[30]["sweep"], "reorder")
        self.assertEqual(self.rows[-1], {
            "sweep": "rto", "protocol": "sr", "window": 32,
            "rto": "adaptive-nokarn", "loss": 0.05, "reorder": 0.0})

    def test_09_distinct_row_objects(self):
        self.assertEqual(len({id(r) for r in self.rows}), 46)
        self.rows[0]["loss"] = 0.99
        self.assertEqual(self.rows[1]["loss"], 0.01)

    def test_10_fresh_call(self):
        self.rows[0]["loss"] = 0.99
        self.assertEqual(configs()[0]["loss"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
