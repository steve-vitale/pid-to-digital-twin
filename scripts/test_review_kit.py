"""Controls for the timed-review kit (scripts/review_kit.py). Synthetic timestamps only; no measured reviews."""
import csv
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import review_kit as rk
import review_effort

ROOT = Path(__file__).resolve().parent.parent
TWIN = ROOT / "out/twin/r2-tiles-trace/codex"
DRAWINGS = ROOT / "data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100"
T0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


class Kit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kit = Path(self.tmp.name) / "kit"
        self.manifest = rk.make(TWIN, "8", self.kit, DRAWINGS)

    def tearDown(self):
        self.tmp.cleanup()

    def test_packet(self):
        _, rows = rk.read_queue(self.kit / "review_queue_sheet8.csv")
        _, source = rk.read_queue(TWIN / "review_queue.csv")
        self.assertEqual(len(rows), sum(1 for r in source if r["sheet"] == "8"))
        self.assertTrue(all(not r[c] for r in rows for c in rk.OPS_COLUMNS))   # no prefilled decisions
        self.assertEqual(self.manifest["rows"], len(rows))
        self.assertNotIn(":", self.manifest["source_twin"])                    # no local drive path
        self.assertEqual(rk.read_timer(self.kit / "timer_log.csv"), [])

    def test_committed_packet_matches_generator(self):
        committed = ROOT / "out/review_kit/sheet-8/manifest.json"
        if committed.exists():
            self.assertEqual(json.loads(committed.read_text(encoding="utf-8"))["files"], self.manifest["files"])

    def test_protocol_draft_refused_until_completed(self):
        draft = json.loads((self.kit / "protocol_draft.json").read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            review_effort.validate_protocol(draft)

    def tick(self, event, minutes):
        return rk.timer(self.kit, event, "R1", now=T0 + timedelta(minutes=minutes))

    def test_timer_excludes_pauses(self):
        self.tick("start", 0); self.tick("pause", 20); self.tick("resume", 35); self.tick("stop", 50)
        self.assertEqual(rk.active_minutes(rk.read_timer(self.kit / "timer_log.csv")), (35.0, 1))

    def test_timer_order_enforced(self):
        with self.assertRaises(ValueError):
            self.tick("pause", 0)
        self.tick("start", 0)
        with self.assertRaises(ValueError):
            self.tick("start", 1)
        self.tick("stop", 5)
        with self.assertRaises(ValueError):
            self.tick("resume", 6)

    def test_unfinished_log_refused(self):
        self.tick("start", 0)
        with self.assertRaises(ValueError):
            rk.summarize(self.kit, self.kit / "review_queue_sheet8.csv")

    def test_summary_counts_unanswered(self):
        self.tick("start", 0); self.tick("stop", 44)
        fields, rows = rk.read_queue(self.kit / "review_queue_sheet8.csv")
        rows[0]["OPS_confirm_or_correct"] = "confirm"
        rows[1]["OPS_confirm_or_correct"] = "correct"
        rows[2]["OPS_confirm_or_correct"] = "reject"
        rows[3]["OPS_confirm_or_correct"] = "maybe"
        filled = self.kit / "filled.csv"
        with open(filled, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
        s = rk.summarize(self.kit, filled)
        self.assertEqual(s["decided"], 3)
        self.assertEqual(s["unreadable_decisions"], 1)
        self.assertEqual(s["unanswered"], len(rows) - 4)
        self.assertEqual(s["minutes_per_correction_or_rejection"], 22.0)
        self.assertIn("PILOT", s["label"])

    def test_reordered_queue_refused(self):
        self.tick("start", 0); self.tick("stop", 1)
        fields, rows = rk.read_queue(self.kit / "review_queue_sheet8.csv")
        filled = self.kit / "filled.csv"
        with open(filled, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows[::-1])
        with self.assertRaises(ValueError):
            rk.summarize(self.kit, filled)


if __name__ == "__main__":
    unittest.main()
