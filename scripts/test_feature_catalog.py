"""The feature catalog: the registry is consistent, docs/FEATURES.md and the README's use matrix are current, every tool
belongs to a feature, and a review stops counting when the output it reviewed changes. Stdlib only."""
import copy
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import feature_catalog as fc  # noqa: E402


class Catalog(unittest.TestCase):
    def test_catalog_and_readme_are_current(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "feature_catalog.py"), "--check"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_tool_without_a_feature_is_refused(self):
        feats, reviews, tools = fc.load()
        tools = dict(tools, **{"scripts/new_tool.py": {"kind": "tool"}})
        self.assertTrue(any("belongs to no feature" in p for p in fc.problems(feats, reviews, tools)))

    def test_a_review_goes_stale_when_its_output_changes(self):
        feats, _, _ = fc.load()
        f = next(x for x in feats["features"] if x["example_outputs"])
        good = {"feature": f["id"], "reviewer": "test", "date": "2026-01-01", "verdict": "pass",
                "files": {p: fc.file_hash(p) for p in f["example_outputs"]}}
        self.assertEqual(fc.review_state(f, [good])[0], "proven")
        stale = copy.deepcopy(good)
        stale["files"][f["example_outputs"][0]] = "0" * 64
        self.assertEqual(fc.review_state(f, [stale])[0], "stale review")
        self.assertEqual(fc.review_state(f, [])[0], "needs review")
        found = dict(good, verdict="findings")
        self.assertEqual(fc.review_state(f, [found])[0], "findings open")

    def test_no_example_output_is_never_proven(self):
        f = {"id": "x", "example_outputs": [], "tests": ["t"]}
        self.assertEqual(fc.review_state(f, [])[0], "no example output")
        self.assertIn("no committed example output", fc.gaps(f, "no example output"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
