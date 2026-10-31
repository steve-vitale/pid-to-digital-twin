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

    def test_make_preserves_source_queue_drawing_overlay_and_companion_files(self):
        for i, source in enumerate((TWIN / 'review_queue.csv', DRAWINGS / '8.png', TWIN / 'svg/sheet_8.svg')):
            # Use private source copies so a failed guard cannot damage committed evidence.
            root = Path(self.tmp.name) / f'guard-{i}'
            twin, drawings, out = root / 'twin', root / 'drawings', root / 'out'
            (twin / 'svg').mkdir(parents=True)
            drawings.mkdir(); out.mkdir()
            for original, copied in ((TWIN / 'review_queue.csv', twin / 'review_queue.csv'),
                                     (DRAWINGS / '8.png', drawings / '8.png'),
                                     (TWIN / 'svg/sheet_8.svg', twin / 'svg/sheet_8.svg')):
                copied.write_bytes(original.read_bytes())
            copied = (twin / 'review_queue.csv', drawings / '8.png', twin / 'svg/sheet_8.svg')[i]
            (out / 'review_queue_sheet8.csv').hardlink_to(copied)
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(ValueError, 'aliases an input'):
                rk.make(twin, '8', out, drawings)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_packet(self):
        _, rows = rk.read_queue(self.kit / "review_queue_sheet8.csv")
        _, source = rk.read_queue(TWIN / "review_queue.csv")
        self.assertEqual(len(rows), sum(1 for r in source if r["sheet"] == "8"))
        self.assertTrue(all(not r[c] for r in rows for c in rk.OPS_COLUMNS))   # no prefilled decisions
        self.assertEqual(self.manifest["rows"], len(rows))
        self.assertNotIn(":", self.manifest["source_twin"])                    # no local drive path
        self.assertEqual(rk.read_timer(self.kit / "timer_log.csv"), [])

    def test_make_cannot_reset_existing_review_or_timer_history(self):
        rk.timer(self.kit, 'start', 'R1', now=T0)
        before = {p: p.read_bytes() for p in self.kit.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'retain review/timer history'):
            rk.make(TWIN, '8', self.kit, DRAWINGS)
        self.assertEqual(before, {p: p.read_bytes() for p in self.kit.rglob('*') if p.is_file()})

    def test_explicit_unstarted_refresh_is_repeatable_and_preserves_readme(self):
        (self.kit / 'README.md').write_text('Retained instructions', encoding='utf-8')
        before = {p: p.read_bytes() for p in self.kit.rglob('*') if p.is_file()}
        self.assertEqual(rk.make(TWIN, '8', self.kit, DRAWINGS, refresh_unstarted=True), self.manifest)
        self.assertEqual(before, {p: p.read_bytes() for p in self.kit.rglob('*') if p.is_file()})

    def test_unstarted_refresh_refuses_timer_queue_protocol_and_incomplete_or_extra_files(self):
        for kind in ('timer', 'queue', 'protocol', 'missing', 'extra', 'manifest'):
            with self.subTest(kind=kind):
                kit = Path(self.tmp.name) / ('edited-' + kind)
                shutil.copytree(self.kit, kit)
                if kind == 'timer':
                    rk.timer(kit, 'start', 'R1', now=T0)
                elif kind == 'queue':
                    p = kit / 'review_queue_sheet8.csv'
                    p.write_bytes(p.read_bytes() + b'changed')
                elif kind == 'protocol':
                    p = kit / 'protocol_draft.json'
                    p.write_text(p.read_text(encoding='utf-8').replace('"study_id": ""', '"study_id": "started"'), encoding='utf-8')
                elif kind == 'missing':
                    (kit / 'timer_log.csv').unlink()
                elif kind == 'extra':
                    (kit / 'notes.txt').write_text('Work begun', encoding='utf-8')
                else:
                    p = kit / 'manifest.json'
                    d = json.loads(p.read_bytes()); d['rows'] += 1
                    p.write_text(json.dumps(d), encoding='utf-8')
                before = {p: p.read_bytes() for p in kit.rglob('*') if p.is_file()}
                with self.assertRaises((ValueError, KeyError)):
                    rk.make(TWIN, '8', kit, DRAWINGS, refresh_unstarted=True)
                self.assertEqual(before, {p: p.read_bytes() for p in kit.rglob('*') if p.is_file()})

    def test_unstarted_refresh_carries_changed_source_rows_without_starting_a_timer(self):
        twin = Path(self.tmp.name) / 'changed-twin'
        (twin / 'svg').mkdir(parents=True)
        shutil.copyfile(TWIN / 'svg/sheet_8.svg', twin / 'svg/sheet_8.svg')
        fields, rows = rk.read_queue(TWIN / 'review_queue.csv')
        selected = next(r for r in rows if r['sheet'] == '8')
        selected['what_it_is'] = 'UPDATED-SOURCE-DESCRIPTION'
        with (twin / 'review_queue.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
        rk.make(twin, '8', self.kit, DRAWINGS, refresh_unstarted=True)
        _, refreshed = rk.read_queue(self.kit / 'review_queue_sheet8.csv')
        self.assertEqual(refreshed[0]['what_it_is'], 'UPDATED-SOURCE-DESCRIPTION')
        self.assertEqual(rk.read_timer(self.kit / 'timer_log.csv'), [])

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
