"""Controls for scripts/evaluate_vendor.py: known answers must score as known, and a fooled scorer must fail loudly.

Uses the committed OPEN100 answer keys; skips cleanly if they are absent. No model results are needed.
Run: python scripts/test_evaluate_vendor.py
"""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_vendor as ev  # noqa: E402
import score_pid2graph as sc  # noqa: E402

KEYS = Path(__file__).resolve().parent.parent / "data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100"
HAVE_KEYS = (KEYS / "8.graphml").exists() and (KEYS / "8.png").exists() and (KEYS / "6.graphml").exists()
SHEETS = ["6", "8"]  # 6 is the repetitive sheet with the shifted-box chance floor; 8 is the smallest key


def write(folder, sheet, obj):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{sheet}.json").write_text(json.dumps(obj), encoding="utf-8")


def perfect(sheet):
    return ev.perfect_prediction(KEYS / f"{sheet}.graphml", KEYS / f"{sheet}.png")


def quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
        code = ev.main(argv)
    return code, err.getvalue()


class Interpretation(unittest.TestCase):
    """Interpretation controls run from the committed receipt without cached keys or model calls."""
    def setUp(self):
        self.record = json.loads((Path(__file__).resolve().parents[1] /
                                 "examples/vendor-evaluation/report.json").read_text(encoding="utf-8"))

    def test_counts_are_not_presented_as_measured_labor(self):
        before = copy.deepcopy(self.record)
        text = ev.markdown(self.record)
        self.assertIn("100 equals the empty-answer count", text)
        self.assertIn("not measured review time, effort or labor savings", text)
        self.assertNotIn("same work as starting from nothing", text)
        self.assertEqual(self.record, before)

    def test_overlapping_individual_intervals_do_not_establish_a_tie(self):
        first, second = [0, 1, 2, 3, 4], [2.5, 3.5, 4.5, 5.5, 6.5]
        a, b = ev.rs.run_interval(first), ev.rs.run_interval(second)
        self.assertLess(b["lo"], a["hi"])
        self.assertLess(ev.rs.welch(first, second)["hi"], 0)
        text = ev.markdown(self.record)
        self.assertIn("Overlap alone does not establish a tie, equivalence or absence of a difference", text)
        self.assertIn("does not perform a between-vendor comparison test", text)

    def test_intervals_and_geometry_keep_their_actual_scope(self):
        text = ev.markdown(self.record)
        for qualification in ("mean score on these fixed sheets", "not a prediction interval",
                              "resamples only the observed sheets", "one observed run per sampled sheet",
                              "Neither threshold establishes CAD precision or drawing readiness",
                              "does not verify direct pipe adjacency"):
            self.assertIn(qualification, text)
        self.assertNotIn("precise enough to draw from", text)


@unittest.skipUnless(HAVE_KEYS, "cached OPEN100 answer keys not present")
class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        empty = Path(cls.tmp.name) / "empty"
        for s in sorted(p.stem for p in KEYS.glob("*.graphml")):
            write(empty, s, {"symbols": [], "connections": []})
        # Every committed key, so a scorer change that lets a wrong answer through on any sheet is caught.
        cls.all = ev.evaluate(KEYS, [empty])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_perfect_control_scores_perfect(self):
        c = self.all["controls"]["perfect"]
        self.assertEqual(c["review_load_per_100"], 0)
        for m in ("symbol_f1_rough_classified", "symbol_f1_strict_classified", "connection_f1"):
            self.assertEqual(c[m], 1, m)
        for s, d in self.all["per_sheet"].items():
            self.assertEqual(d["controls"]["perfect"]["review_load_per_100"], 0, f"sheet {s}")

    def test_wrong_controls_score_near_zero(self):
        """The point of the kit. If this fails, the scorer is being fooled and no vendor number is trustworthy."""
        for name in ("wrong_class", "shifted"):
            agg = self.all["controls"][name]["symbol_f1_rough_classified"]
            self.assertLessEqual(agg, ev.WRONG_MAX_F1,
                                 f"SCORER FOOLED: the deliberately wrong '{name}' answer earned symbol F1 {agg:.3f} "
                                 f"across all keys (limit {ev.WRONG_MAX_F1}). Do not trust any score until fixed.")
            for s, d in self.all["per_sheet"].items():
                v = d["controls"][name]["symbol_f1_rough_classified"]
                self.assertLessEqual(v, ev.WRONG_MAX_F1,
                                     f"SCORER FOOLED on sheet {s}: '{name}' earned symbol F1 {v:.3f}.")
                self.assertGreaterEqual(d["controls"][name]["review_load_per_100"], 90, f"{name} sheet {s}")
        self.assertTrue(self.all["controls_ok"], self.all["control_failures"])

    def test_empty_answer_scores_zero(self):
        rep = self.all["replicates"]
        self.assertEqual(rep["review_load_per_100"]["mean"], 100)
        self.assertEqual(rep["symbol_f1_rough_classified"]["mean"], 0)
        self.assertEqual(rep["connection_f1"]["mean"], 0)
        self.assertEqual(self.all["controls"]["empty"]["review_load_per_100"], 100)

    def test_a_fooled_scorer_fails_the_run_loudly(self):
        """Simulate the journal-entry-7 failure: a scorer that ignores the class. The run must exit 2 and say so."""
        real_match = sc.match
        with tempfile.TemporaryDirectory() as t, \
                mock.patch.object(sc, "match", lambda p, k, need_class, thr: real_match(p, k, False, thr)):
            for s in SHEETS:
                write(Path(t) / "run1", s, perfect(s))
            code, err = quiet_main(["--keys", str(KEYS), "--sheets", ",".join(SHEETS),
                                    "--predictions", str(Path(t) / "run1"), "--out", str(Path(t) / "r")])
            md = (Path(t) / "r.md").read_text(encoding="utf-8")
        self.assertEqual(code, 2)
        self.assertIn("CONTROLS FAILED", err)
        self.assertIn("CONTROLS FAILED. Do not use the vendor numbers", md)


@unittest.skipUnless(HAVE_KEYS, "cached OPEN100 answer keys not present")
class Vendor(unittest.TestCase):
    @unittest.skipUnless(HAVE_KEYS, 'committed drawing/key required')
    def test_reports_preserve_predictions_keys_images_and_existing_companions(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            keys, preds = folder / 'keys', folder / 'preds'
            keys.mkdir(); preds.mkdir()
            for ext in ('png', 'graphml'):
                shutil.copyfile(KEYS / ('8.' + ext), keys / ('8.' + ext))
            source = preds / '8.json'
            source.write_text(json.dumps({'symbols': [], 'connections': []}), encoding='utf-8')
            for i, consumed in enumerate((source, keys / '8.png', keys / '8.graphml')):
                for ext in ('json', 'md'):
                    out = folder / f'out-{i}-{ext}'
                    target, companion = out.with_suffix('.' + ext), out.with_suffix('.md' if ext == 'json' else '.json')
                    target.hardlink_to(consumed)
                    companion.write_bytes(b'retain report')
                    before = {p: p.read_bytes() for p in (source, keys / '8.png', keys / '8.graphml', target, companion)}
                    code, errors = quiet_main(['--keys', str(keys), '--predictions', str(preds), '--out', str(out)])
                    self.assertEqual(code, 1)
                    self.assertIn('aliases an input', errors)
                    self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_perfect_vendor_file_and_run_record_both_load(self):
        with tempfile.TemporaryDirectory() as t:
            write(Path(t) / "contract", "6", perfect("6"))
            write(Path(t) / "contract", "8", perfect("8"))
            write(Path(t) / "record", "6", {"model": "m-1", "error": None, "prediction": perfect("6")})
            write(Path(t) / "record", "8", {"model": "m-1", "error": None, "prediction": perfect("8")})
            r = ev.evaluate(KEYS, [Path(t) / "contract", Path(t) / "record"], SHEETS, "test")
        self.assertEqual(r["missing_or_failed"], [])
        self.assertEqual(r["replicates"]["review_load_per_100"]["max"], 0)
        self.assertEqual(r["runs"][1]["models_in_records"], ["m-1"])
        self.assertEqual(r["replicates"]["review_load_per_100"]["runs_95"], [0, 0])

    def test_missing_and_failed_sheets_are_reported_and_scored_empty(self):
        with tempfile.TemporaryDirectory() as t:
            write(Path(t) / "run1", "6", perfect("6"))                      # sheet 8 missing
            write(Path(t) / "run2", "6", perfect("6"))
            write(Path(t) / "run2", "8", {"model": "m", "error": "timeout", "prediction": None})  # failed
            code, err = quiet_main(["--keys", str(KEYS), "--sheets", ",".join(SHEETS),
                                    "--predictions", str(Path(t) / "run1"), str(Path(t) / "run2"),
                                    "--out", str(Path(t) / "r")])
            r = json.loads((Path(t) / "r.json").read_text(encoding="utf-8"))
            md = (Path(t) / "r.md").read_text(encoding="utf-8")
        self.assertEqual(code, 0)  # controls behaved; the gap is reported, not fatal
        self.assertEqual({(p["run"].split("/")[-1], p["sheet"], p["status"]) for p in r["missing_or_failed"]},
                         {("run1", "8", "missing"), ("run2", "8", "failed")})
        self.assertIn("sheet 8: missing", md)
        self.assertIn("sheet 8: failed (timeout)", md)
        self.assertIn("WARNING", err)
        runs = r["per_sheet"]["8"]["vendor_runs"]
        self.assertEqual([x["review_load_per_100"] for x in runs], [100, 100])  # scored as empty, not skipped
        self.assertEqual(r["per_sheet"]["6"]["vendor_mean"]["review_load_per_100"], 0)
        self.assertGreater(r["replicates"]["review_load_per_100"]["mean"], 0)

    def test_malformed_files_fail_that_sheet_not_the_run(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "run1").mkdir()
            (Path(t) / "run1" / "6.json").write_text("{not json", encoding="utf-8")
            write(Path(t) / "run1", "8", {"symbols": ["x", {"id": 1}], "connections": [3]})
            r = ev.evaluate(KEYS, [Path(t) / "run1"], SHEETS, "test")
        self.assertEqual([(p["sheet"], p["status"]) for p in r["missing_or_failed"]], [("6", "failed"), ("8", "failed")])
        self.assertEqual(r["replicates"]["review_load_per_100"]["mean"], 100)

    def test_vendor_score_never_printed_without_controls(self):
        with tempfile.TemporaryDirectory() as t:
            write(Path(t) / "run1", "8", perfect("8"))
            r = ev.evaluate(KEYS, [Path(t) / "run1"], ["8"], "Vendor Q")
        md = ev.markdown(r)
        headline = md.split("## Vendor beside the controls")[1].split("##")[0]
        self.assertIn("**Vendor Q**", headline)
        for label in ev.CONTROL_LABELS.values():
            self.assertIn(label, headline)
        self.assertLess(md.index("Control: perfect answer"), md.index("## Per sheet"))
        self.assertNotIn(str(Path(t).parent), md)  # no local absolute paths in the report

    def test_bad_input_exits_1(self):
        with tempfile.TemporaryDirectory() as t:
            code, err = quiet_main(["--keys", str(KEYS), "--sheets", "no-such-sheet",
                                    "--predictions", t, "--out", str(Path(t) / "r")])
        self.assertEqual(code, 1)
        self.assertIn("no answer key", err)


if __name__ == "__main__":
    unittest.main()
