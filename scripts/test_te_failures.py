"""Tests for the single-instrument failures injected into the TE replay (scripts/ignition/te_failures.py). Stdlib only."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "ignition"))
from te_failures import FailureError, Injector, parse  # noqa: E402

TAGS = {"PT-107", "LT-108", "TT-109", "FT-114", "TT-121", "LT-112"}


class Parse(unittest.TestCase):
    def test_every_kind_parses(self):
        got = parse(["freeze PT-107", "fixed LT-108 100", "drift TT-109 0.05", "noise FT-114 2",
                     "bad TT-121", "stale LT-112  # comment"], TAGS)
        self.assertEqual(got["LT-108"], ("fixed", 100.0))
        self.assertEqual(got["LT-112"], ("stale", None))
        self.assertEqual(len(got), 6)

    def test_bad_lines_are_refused_not_ignored(self):
        for lines, msg in ((["melt PT-107"], "unknown failure"), (["freeze XX-999"], "no tag"),
                           (["fixed LT-108"], "takes a tag and a number"), (["fixed LT-108 high"], "not a number"),
                           (["freeze PT-107", "bad PT-107"], "already has a failure")):
            with self.assertRaisesRegex(FailureError, msg):
                parse(lines, TAGS)

    def test_blank_and_comment_lines_clear_nothing(self):
        self.assertEqual(parse(["", "# nothing"], TAGS), {})


class Apply(unittest.TestCase):
    def test_no_failure_passes_the_recorded_value_through(self):
        self.assertEqual(Injector().apply("PT-107", 2700.0), ("write", 2700.0, True))

    def test_freeze_holds_the_value_from_when_it_started_and_stays_good(self):
        inj = Injector()
        inj.set({"PT-107": ("freeze", None)})
        self.assertEqual(inj.apply("PT-107", 2700.0), ("write", 2700.0, True))
        self.assertEqual(inj.apply("PT-107", 2950.0), ("write", 2700.0, True))

    def test_drift_is_cumulative(self):
        inj = Injector()
        inj.set({"TT-109": ("drift", 0.5)})
        self.assertEqual([inj.apply("TT-109", 120.0)[1] for _ in range(3)], [120.5, 121.0, 121.5])

    def test_noise_is_repeatable_with_the_same_seed(self):
        a, b = Injector(seed=1), Injector(seed=1)
        for inj in (a, b):
            inj.set({"FT-114": ("noise", 2.0)})
        self.assertEqual([a.apply("FT-114", 25.0)[1] for _ in range(5)], [b.apply("FT-114", 25.0)[1] for _ in range(5)])

    def test_bad_and_stale_differ(self):
        inj = Injector()
        inj.set({"TT-121": ("bad", None), "LT-112": ("stale", None)})
        self.assertEqual(inj.apply("TT-121", 37.0), ("write", None, False))
        self.assertEqual(inj.apply("LT-112", 50.0), ("skip", None, None))

    def test_a_continuing_failure_keeps_its_state_and_a_changed_one_restarts(self):
        inj = Injector()
        inj.set({"PT-107": ("freeze", None)})
        inj.apply("PT-107", 2700.0)
        inj.set({"PT-107": ("freeze", None), "LT-108": ("fixed", 100.0)})  # another line added: PT-107 still frozen
        self.assertEqual(inj.apply("PT-107", 2900.0)[1], 2700.0)
        inj.set({})
        inj.set({"PT-107": ("freeze", None)})  # cleared, then set again: freezes at the new value
        self.assertEqual(inj.apply("PT-107", 2900.0)[1], 2900.0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
