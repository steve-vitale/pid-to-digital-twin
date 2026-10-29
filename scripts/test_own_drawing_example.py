"""The runbook's worked example (examples/own-drawing) must run from a clean clone and produce what its README says.

Runs scripts/import_site_drawing.py on the committed manifest and extraction into a temporary folder, then checks the
bundle's files and the counts the runbook quotes. Stdlib only, no network, no model.
"""
import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "own-drawing"


def run(*args):
    return subprocess.run([sys.executable, "-S", str(ROOT / "scripts" / "import_site_drawing.py"),
                           "--manifest", str(EXAMPLE / "manifest.json"), *args],
                          capture_output=True, text=True, timeout=300)


class WorkedExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "my-bundle"
        cls.check = run("--out", str(cls.out), "--check-only")
        cls.build = run("--out", str(cls.out))
        cls.readme = " ".join((EXAMPLE / "README.md").read_text(encoding="utf-8").split())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_both_commands_succeed(self):
        self.assertEqual(self.check.returncode, 0, self.check.stderr)
        self.assertEqual(self.build.returncode, 0, self.build.stderr)
        self.assertTrue(json.loads(self.build.stdout)["exports_written"])

    def test_the_bundle_has_the_files_the_runbook_lists(self):
        for rel in ("review_queue.csv", "plant_model.json", "svg/sheet_0.svg", "ignition/tags.json", "READ_ME.txt"):
            self.assertTrue((self.out / rel).is_file(), rel)
        self.assertTrue(any((self.out / "pi").iterdir()))

    def test_the_counts_the_runbook_quotes(self):
        summary = json.loads(self.build.stdout)["summary"]
        with open(self.out / "review_queue.csv", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        quoted = {"rows": len(rows), "equipment": summary["equipment"], "instruments": summary["instruments"],
                  "line items": summary["line_items"], "off-page connectors": summary["offpage_connectors"],
                  "links": summary["streams_extracted"]}
        for words, n in quoted.items():
            self.assertRegex(self.readme, rf"\b{n:,}\b {re.escape(words)}" if words != "rows" else rf"\b{n:,} rows\b",
                             f"the runbook should say {n} {words}")

    def test_no_risk_tier_is_claimed_for_an_unseen_drawing(self):
        with open(self.out / "review_queue.csv", encoding="utf-8-sig", newline="") as f:
            self.assertEqual({r["tier"] for r in csv.DictReader(f)}, {""})

    def test_the_client_report_builds_from_the_bundle_and_quotes_its_counts(self):
        out = Path(self.tmp.name) / "REPORT.html"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "deliverable_report.py"), str(self.out),
                            "--out", str(out)], capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = out.read_text(encoding="utf-8")
        summary = json.loads(self.build.stdout)["summary"]
        self.assertIn(f"<b>{summary['instruments']:,}</b><span>instruments", page)
        self.assertIn(f"<b>{summary['streams_extracted']:,}</b><span>links between items", page)
        self.assertIn("Draft, unverified.", page)
        self.assertIn("2x2 tiles", page)  # the producer is named, not "not stated"
        self.assertEqual(page.count("<rect x="), sum(summary[k] for k in ("equipment", "instruments", "line_items",
                                                                          "offpage_connectors")))

    def test_the_extraction_is_the_recorded_run_of_this_sheet(self):
        record = json.loads((EXAMPLE / "extraction_sheet0.json").read_text(encoding="utf-8"))
        self.assertEqual((record["tool"], record["drawing"], record["label"]), ("codex", "0", "r2-tiles-trace"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
