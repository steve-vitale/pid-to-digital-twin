"""Controls for scripts/rescore.py: the committed predictions hold no raw model text, round-trip exactly, and re-score
a committed scorecard byte for byte; a changed prediction is caught. Stdlib only, offline."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import rescore

ALLOWED = set(rescore.META_KEYS) | {"schema", "tiling", "tracer", "prediction"}


class Format(unittest.TestCase):
    def test_recovered_exports_match_their_manifest(self):
        receipt = json.loads((rescore.PREDICTIONS / "RECOVERY.json").read_text(encoding="utf-8"))
        self.assertEqual(len(receipt["records"]), 391)
        names = set()
        for record in receipt["records"]:
            self.assertNotIn(record["prediction"], names)
            names.add(record["prediction"])
            path = rescore.PREDICTIONS / record["prediction"]
            self.assertEqual(hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                             record["prediction_sha256"], record["prediction"])
            self.assertRegex(record["source_sha256"], r"^[a-f0-9]{64}$")
        self.assertIn("r5-hA-rep1-trace/codex/6.json", names)
        self.assertIn("te-clean-trace-r1/codex/101.json", names)

    def test_slim_drops_raw_text_and_keeps_what_scorers_read(self):
        rec = {"tool": "codex", "drawing": "6", "label": "x", "model": "m", "seconds": 1.5, "cost_usd": None,
               "raw_text": "SECRET model text", "usage": {"total_tokens": 9}, "tiles": [{"raw_text": "t"}],
               "tiling": {"grid": "2x2", "merge_stats": {"a": 1}, "tiles_failed": 0},
               "tracer": {"script": "s", "stats": {"n": 3}, "seconds": 2.0},
               "prediction": {"symbols": [{"id": "s1", "class": "valve", "bbox": {"x_min": 1, "y_min": 2,
                                           "x_max": 3, "y_max": 4}, "tag": "FV-1", "confidence": 0.9,
                                           "merged_from": [1, 2], "tiles_seen": 2}],
                              "connections": [{"from": "s1", "to": "s2"}]}}
        out = rescore.slim(rec)
        text = rescore.dumps(out)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("merged_from", text)
        self.assertNotIn("total_tokens", text)
        self.assertEqual(out["tiling"], {"grid": "2x2", "tiles_failed": 0})
        self.assertEqual(out["tracer"], {"script": "s", "seconds": 2.0})
        self.assertEqual(out["prediction"]["symbols"][0]["tag"], "FV-1")
        self.assertEqual(json.loads(text), out)

    def test_failed_run_keeps_null_prediction(self):
        out = rescore.slim({"tool": "gemini", "drawing": "3", "error": "TimeoutError", "prediction": None})
        self.assertIsNone(json.loads(rescore.dumps(out))["prediction"])

    def test_committed_files_hold_only_allowed_fields(self):
        files = sorted(rescore.PREDICTIONS.glob("*/*/*.json"))
        self.assertTrue(files, "no committed predictions")
        for f in files:
            rec = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(rec.get("schema"), rescore.SCHEMA, f)
            self.assertLessEqual(set(rec), ALLOWED, f)
            pred = rec["prediction"]
            if isinstance(pred, dict):
                self.assertLessEqual(set(pred), {"symbols", "connections"}, f)
                for s in pred.get("symbols") or []:
                    if isinstance(s, dict):
                        self.assertLessEqual(set(s), set(rescore.SYMBOL_KEYS), f)


class Jobs(unittest.TestCase):
    def test_every_missing_table_has_a_recorded_reason(self):
        for job in rescore.jobs():
            missing = [lb for lb in job["labels"] if not (rescore.PREDICTIONS / lb).is_dir()]
            if missing or rescore.short_drawings(job):
                self.assertIn(job["name"], rescore.KNOWN_GAPS, job["name"])

    def test_scan_and_holdout_b_keys(self):
        job = rescore.scorecard_job(rescore.ROOT / Path("out/scorecard_r4-scan-L2-trace_holdout-a.md"))
        self.assertEqual((job["labels"], job["split"], job["dataset"]),
                         (["r4-scan-L2-trace"], "holdout-a", "PID2Graph OPEN100 scan-L2"))
        self.assertEqual(rescore.scorecard_job(rescore.ROOT / Path("out/scorecard_hb-v2.md"))["dataset"], "Dataset PID")
        clean = rescore.scorecard_job(rescore.ROOT / Path("out/scorecard_r4-scan-L3-symbols-clean-trace_holdout-a.md"))
        self.assertEqual(clean["dataset"], "PID2Graph OPEN100")


class Rescore(unittest.TestCase):
    NAME = "out/scorecard_r2-trace_holdout-a"

    def job(self):
        return next(j for j in rescore.jobs() if j["name"] == self.NAME)

    def test_committed_scorecard_regenerates_byte_for_byte(self):
        state, details = rescore.check_job(self.job())
        self.assertEqual(state, "MATCH", details)

    def test_changed_prediction_is_a_difference(self):
        real = rescore.PREDICTIONS
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "predictions"
            shutil.copytree(real / "r2-trace", copy / "r2-trace")
            f = copy / "r2-trace" / "codex" / "6.json"
            rec = json.loads(f.read_text(encoding="utf-8"))
            rec["prediction"]["connections"] = rec["prediction"]["connections"][1:]  # drop one link
            f.write_text(rescore.dumps(rec), encoding="utf-8")
            rescore.PREDICTIONS = copy
            try:
                state, details = rescore.check_job(self.job())
            finally:
                rescore.PREDICTIONS = real
        self.assertEqual(state, "DIFF", details)

    def test_missing_keys_skip_not_pass(self):
        job = dict(self.job(), keys_dir=rescore.ROOT / "no-such-dir")
        self.assertEqual(rescore.check_job(job)[0], "SKIP")

    def test_old_format_strip(self):
        md = ("# Extraction scorecard: `x` (split: all)\n\n| Tool | Model | Drawings (failed) | **Review load** "
              "(per 100, lower=better) | Rough |\n|---|---|---|---|---|\n| claude | m | 1 (0) | **15.4** | 0.90 |\n")
        self.assertEqual(rescore.without_review_load("a.md", md.encode()).decode(),
                         "# Extraction scorecard: `x`\n\n| Tool | Model | Drawings (failed) | Rough |\n"
                         "|---|---|---|---|\n| claude | m | 1 (0) | 0.90 |\n")


if __name__ == "__main__":
    unittest.main()
