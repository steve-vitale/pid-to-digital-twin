"""The client report (scripts/deliverable_report.py) must refuse a review sheet that doesn't describe the model,
drop decided items from the to-check list, and the review-and-mapping example must reproduce from its README.

Builds the own-drawing example bundle once into a temporary folder (offline, stdlib + the repository's scripts).
"""
import csv
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
EXAMPLE = ROOT / "examples" / "review-and-mapping"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def py(*args, cwd=None):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                          cwd=cwd, env=ENV, timeout=300)


def report(bundle, out):
    return py(SCRIPTS / "deliverable_report.py", bundle, "--out", out)


def read_queue(bundle):
    with open(bundle / "review_queue.csv", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_queue(bundle, fields, rows):
    with open(bundle / "review_queue.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


class ClientReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name) / "base"
        r = py("-S", SCRIPTS / "import_site_drawing.py", "--manifest", ROOT / "examples" / "own-drawing" /
               "manifest.json", "--out", cls.base)
        assert r.returncode == 0, r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copy(self, name):
        dest = Path(self.tmp.name) / name
        shutil.copytree(self.base, dest)
        return dest

    def test_the_fresh_bundle_reports(self):
        r = report(self.base, Path(self.tmp.name) / "fresh.html")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_outputs_preserve_bundle_inputs_and_originals_through_hardlinks(self):
        b = self.copy("source-output-collisions")
        companion = b / "REPORT.html"
        companion.write_bytes(b"retain earlier report")
        inputs = [b / p for p in ("plant_model.json", "intake_manifest.json", "review_queue.csv", "READ_ME.txt")]
        inputs += sorted(p for p in (b / "source").rglob("*") if p.is_file())
        before = {p: p.read_bytes() for p in inputs + [companion]}
        for i, source in enumerate(inputs):
            linked = b / f"alias-{i}.html"
            linked.hardlink_to(source)
            for out in (source, linked):
                with self.subTest(source=source.name, out=out.name):
                    r = report(b, out)
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                    self.assertIn("output aliases an input", r.stderr)
                    self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_normal_report_replacement_remains_allowed(self):
        out = Path(self.tmp.name) / "replace-report.html"
        self.assertEqual(report(self.base, out).returncode, 0)
        before = out.read_bytes()
        self.assertEqual(report(self.base, out).returncode, 0)
        self.assertEqual(out.read_bytes(), before)

    def test_an_edited_reason_is_refused(self):
        # Probe A: same ids, every reason rewritten to "routine check" -> was "0 to check first", exit 0.
        b = self.copy("edited-why")
        fields, rows = read_queue(b)
        for row in rows:
            row["why_check_this"] = "routine check"
        write_queue(b, fields, rows)
        r = report(b, b / "R.html")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("why_check_this", r.stderr)
        self.assertIn("regenerate the exports", r.stderr)
        self.assertFalse((b / "R.html").exists())

    def test_a_model_changed_after_the_sheet_is_refused(self):
        # Probe B: instruments[0].tag changed in plant_model.json after the queue was written.
        b = self.copy("changed-tag")
        model = json.loads((b / "plant_model.json").read_text(encoding="utf-8"))
        model["instruments"][0]["tag"] = "XX 9999"
        (b / "plant_model.json").write_text(json.dumps(model, indent=1), encoding="utf-8")
        r = report(b, b / "R.html")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(model["instruments"][0]["id"], r.stderr)
        self.assertIn("XX 9999", r.stderr)

    def test_a_duplicated_row_is_refused(self):
        # Round 4: a copied row was accepted and every headline count went up by one.
        b = self.copy("dup-row")
        fields, rows = read_queue(b)
        write_queue(b, fields, rows + [rows[2]])
        r = report(b, b / "R.html")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("more than once", r.stderr)
        self.assertIn(rows[2]["item_id"], r.stderr)

    def test_a_missing_column_is_named_in_plain_words(self):
        b = self.copy("no-why")
        fields, rows = read_queue(b)
        fields = [f for f in fields if f != "why_check_this"]
        write_queue(b, fields, [{k: v for k, v in row.items() if k in fields} for row in rows])
        r = report(b, b / "R.html")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("review_queue.csv has no why_check_this column", r.stderr)
        self.assertNotIn("KeyError", r.stderr)

    def test_decided_items_leave_the_to_check_list(self):
        b = self.copy("reviewed")
        r = py(SCRIPTS / "apply_review.py", b / "plant_model.json", EXAMPLE / "reviewed_sheet0.csv", "--reviewer",
               "Test", "--date", "2026-10-29", "--record-dir", Path(self.tmp.name) / "rec")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(py(SCRIPTS / "generate.py", b / "plant_model.json").returncode, 0)
        out = b / "R.html"
        r = report(b, out)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = out.read_text(encoding="utf-8")
        _, rows = read_queue(b)
        decided = {row["item_id"] for row in rows if row["model_status"] != "unverified"}
        self.assertEqual(decided, {"S0-VL020", "S0-IN003", "S0-IN002", "S0-TK001"})
        flagged_open = [row for row in rows if row["item_id"] not in decided
                        and not row["why_check_this"].startswith(("routine check", "check the line exists"))]
        tile = re.search(r"<b>([\d,]+)</b><span>to check first", page)
        self.assertEqual(tile and tile.group(1), f"{len(flagged_open):,}")
        to_check = page.split("<h2>Check these first", 1)[1].split("<h2>", 1)[0]
        for item in decided:
            self.assertNotIn(f"<td>{item}</td>", to_check, item)
        reviewed = page.split("<h2>Reviewed so far", 1)[1].split("<h2>", 1)[0]
        self.assertTrue("<td>S0-VL020</td><td>MSCV-1401</td><td>corrected</td>" in reviewed, reviewed[:2000])
        # A corrected placeholder tag is no longer called a placeholder (apply_review updates tag_status).
        vl020 = next(row for row in rows if row["item_id"] == "S0-VL020")
        self.assertNotIn("placeholder", vl020["why_check_this"])
        self.assertFalse("placeholder (&quot;MSCV-1401&quot;)" in page)


class ReviewAndMappingReadme(unittest.TestCase):
    """The extracted README reproduces its outputs; seed/native sub-examples have separate CLI controls."""

    def test_the_readme_commands_reproduce_the_committed_outputs(self):
        text = (EXAMPLE / "README.md").read_text(encoding="utf-8")
        block = re.search(r"## Reproduce it.*?```sh\n(.*?)```", text, re.S).group(1)
        commands = [ln for ln in block.splitlines() if ln.strip()]
        self.assertTrue(commands)
        with tempfile.TemporaryDirectory() as tmp:
            produced = {}
            for line in commands:
                line, _, target = line.partition(" > ")
                args = shlex.split(line)
                self.assertEqual(args[0], "python", line)
                args = [str(ROOT / a) if a.startswith(("scripts/", "examples/", "data/")) else a for a in args[1:]]
                r = subprocess.run([sys.executable, *args], capture_output=True, cwd=tmp, env=ENV, timeout=300)
                self.assertEqual(r.returncode, 0, (line, r.stderr.decode("utf-8", "replace")))
                if target:
                    (Path(tmp) / target.strip()).write_bytes(r.stdout)
                    produced[Path(target.strip()).name] = Path(tmp) / target.strip()
            out = Path(tmp) / "my-review"
            for p in out.rglob("*"):
                if p.is_file():
                    produced.setdefault(p.relative_to(out).as_posix(), p)
            committed = sorted(p.relative_to(EXAMPLE).as_posix() for p in EXAMPLE.rglob("*") if p.is_file()
                               and p.relative_to(EXAMPLE).parts[0] not in ("seed-refresh", "native-identity")
                               and p.name not in ("README.md", "reviewed_sheet0.csv", "reviewed_pi_sheet0.csv"))
            self.assertEqual(sorted(produced), committed)
            for name in committed:
                with self.subTest(name=name):
                    want = (EXAMPLE / name).read_bytes()
                    self.assertNotIn(b"\r\n", want, f"{name} is committed with CRLF")
                    got = produced[name].read_bytes()
                    self.assertEqual(got, want, name)


if __name__ == "__main__":
    unittest.main(verbosity=1)
