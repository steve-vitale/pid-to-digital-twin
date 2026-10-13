"""Controls for scripts/replicate_stats.py interval arithmetic. Synthetic counts only; no model results."""
import random
import statistics
import unittest

import replicate_stats as rs


def counts(corrections, key_items=100):
    c = dict.fromkeys(rs.COUNT_KEYS, 0)
    c.update(corrections=corrections, key_items=key_items)
    return c


class Intervals(unittest.TestCase):
    def test_t_table(self):
        self.assertEqual(rs.t975(4), 2.776)
        self.assertEqual(rs.t975(22), 2.086)     # falls back to the next lower tabulated df (conservative)
        self.assertEqual(rs.t975(200), 1.96)

    def test_run_interval(self):
        r = rs.run_interval([10.0, 12.0, 14.0, 16.0, 18.0])
        self.assertAlmostEqual(r["mean"], 14.0)
        half = 2.776 * statistics.stdev([10, 12, 14, 16, 18]) / 5 ** 0.5
        self.assertAlmostEqual(r["hi"] - r["mean"], half)
        self.assertIsNone(rs.run_interval([3.0])["lo"])

    def test_welch(self):
        self.assertIsNone(rs.welch([1.0], [2.0])["lo"])
        w = rs.welch([10.0, 11.0, 12.0], [20.0, 21.0, 22.0])
        self.assertTrue(w["hi"] < 0)
        flat = rs.welch([0.9, 0.9, 0.9], [0.8, 0.8, 0.8])
        self.assertEqual(flat["lo"], flat["hi"])   # zero width: reported as no run variation, not a difference
        same = rs.welch([10.0, 12.0, 11.0], [11.0, 10.0, 12.0])
        self.assertTrue(same["lo"] <= 0 <= same["hi"])

    def test_percentile(self):
        self.assertEqual(rs.percentile([1, 2, 3, 4, 5], 0.5), 3)
        self.assertAlmostEqual(rs.percentile([0, 10], 0.25), 2.5)


class Bootstrap(unittest.TestCase):
    def test_identical_tools_tie_and_fixed_seed(self):
        reps = [{d: counts(20 + d + k) for d in range(6)} for k in range(5)]
        a = rs.bootstrap(reps, "review_load_per_100", random.Random(1), other=reps)
        b = rs.bootstrap(reps, "review_load_per_100", random.Random(1), other=reps)
        self.assertEqual(a, b)
        self.assertTrue(rs.percentile(a, 0.025) <= 0 <= rs.percentile(a, 0.975))

    def test_clear_gap_is_different(self):
        low = [{d: counts(10) for d in range(6)} for _ in range(5)]
        high = [{d: counts(40) for d in range(6)} for _ in range(5)]
        diff = rs.bootstrap(high, "review_load_per_100", random.Random(2), other=low)
        self.assertAlmostEqual(rs.percentile(diff, 0.025), 30.0)

    def test_micro_average(self):
        t = rs.total([counts(10, 50), counts(30, 150)])
        self.assertAlmostEqual(rs.METRICS["review_load_per_100"](t), 20.0)


if __name__ == "__main__":
    unittest.main()
