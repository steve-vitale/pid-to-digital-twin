"""The attempts ledger (data/attempts.json) passes scripts/attempts_ledger.py --check, docs/TRIED.md is current, and the
check refuses a bad verdict, a repeated id, an unknown function, a missing field and a source file that doesn't
exist. Stdlib only."""
import copy
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "attempts_ledger.py"
spec = importlib.util.spec_from_file_location("attempts_ledger", SCRIPT)
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)


class AttemptsLedger(unittest.TestCase):
    def setUp(self):
        self.led = ledger.load()

    def test_ledger_passes_check_and_page_is_current(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_committed_ledger_has_no_problems(self):
        self.assertEqual(ledger.problems(self.led), [])

    def refused(self, led, needle):
        found = ledger.problems(led)
        self.assertTrue(any(needle in p for p in found), f"expected a problem containing {needle!r}, got {found}")

    def test_bad_verdict_refused(self):
        led = copy.deepcopy(self.led)
        led["attempts"][0]["verdict"] = "promising"
        self.refused(led, "verdict 'promising'")

    def test_duplicate_id_refused(self):
        led = copy.deepcopy(self.led)
        led["attempts"][1]["id"] = led["attempts"][0]["id"]
        self.refused(led, f"id {led['attempts'][0]['id']} is used 2 times")

    def test_unknown_function_refused(self):
        led = copy.deepcopy(self.led)
        led["not_tried"][0]["function"] = "vibes"
        self.refused(led, "unknown function 'vibes'")

    def test_missing_source_file_refused(self):
        led = copy.deepcopy(self.led)
        led["attempts"][0]["source"] = ["docs/NO_SUCH_FILE.md#intro"]
        self.refused(led, "source file docs/NO_SUCH_FILE.md does not exist")

    def test_missing_heading_anchor_refused(self):
        led = copy.deepcopy(self.led)
        led["attempts"][0]["source"] = ["docs/JOURNAL.md#999-no-such-entry"]
        self.refused(led, "no heading in docs/JOURNAL.md")

    def test_missing_field_refused(self):
        led = copy.deepcopy(self.led)
        del led["attempts"][0]["evidence"]
        self.refused(led, "missing evidence")

    def test_absolute_source_refused(self):
        led = copy.deepcopy(self.led)
        led["attempts"][0]["source"] = ["/etc/passwd"]
        self.refused(led, "must be relative")

    def test_single_runs_are_flagged(self):
        self.assertTrue(ledger.single_run("1"))
        self.assertTrue(ledger.single_run("1 per tool"))
        self.assertFalse(ledger.single_run("5 per model"))
        self.assertFalse(ledger.single_run("12"))
        self.assertIn("(single run)", ledger.render(self.led))

    def test_slug_matches_github_style(self):
        self.assertEqual(ledger.slug("44. One plant, end to end: draw the TE model"),
                         "44-one-plant-end-to-end-draw-the-te-model")
        self.assertEqual(ledger.slug("Conversion (scripts/adapt_dexpi.py, rules)"),
                         "conversion-scriptsadapt_dexpipy-rules")


if __name__ == "__main__":
    unittest.main(verbosity=1)
