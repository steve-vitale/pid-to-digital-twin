"""Tests for scripts/csv_normal_bands.py and scripts/csv_replay_server.py on synthetic CSVs; when the TE cache and
the committed TE outputs are present, also that the example CSV export reproduces the TE scripts' fault-6 results
(with --method level, the TE scripts' own method) and that the committed example output is the default method's.

The OPC UA part runs the replay server in-process on a free 127.0.0.1 port (a few seconds) and stops it; it is
skipped, with a SKIP line, when asyncua is not installed. No process is left running.
"""
import asyncio
import csv
import importlib.util
import json
import math
import random
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import csv_normal_bands as cnb  # noqa: E402

EXAMPLE = ROOT / "examples" / "historian-csv"
HAVE_ASYNCUA = importlib.util.find_spec("asyncua") is not None


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def synthetic(step_at=None, n=200, step=5.0):
    """Two tags with deterministic small wiggle; tag B steps by `step` at row step_at."""
    rows = []
    for i in range(n):
        a = 10 + 0.1 * ((i * 7) % 11 - 5) / 5
        b = 50 + 0.2 * ((i * 5) % 13 - 6) / 6 + (step if step_at is not None and i >= step_at else 0)
        rows.append([i, f"{a:.5f}", f"{b:.5f}"])
    return rows


def drifting(start, n, step_at=None, step=10.0):
    """Normal running that drifts slowly, as a real plant does: tag A ramps 0.002 per sample (1 unit per 500
    samples) with a small deterministic wiggle; tag B is steady. Rows start at sample `start`, so a later export
    is further along the same ramp. A steps by `step` at sample step_at (a sample number, not a row)."""
    rows = []
    for i in range(start, start + n):
        a = 100 + 0.002 * i + 0.05 * ((i * 7) % 11 - 5) / 5 + (step if step_at is not None and i >= step_at else 0)
        b = 50 + 0.2 * ((i * 5) % 13 - 6) / 6
        rows.append([i, f"{a:.5f}", f"{b:.5f}"])
    return rows


def percent_noise(level, start, n, step_at=None, step=0.0):
    """Tag A at `level` with 1% gaussian noise (seeded, so deterministic): noise in proportion to the reading, as a
    flowmeter's; tag B steady. A steps by `step` at sample step_at."""
    rng = random.Random(start)
    rows = []
    for i in range(start, start + n):
        a = level * (1 + 0.01 * rng.gauss(0, 1)) + (step if step_at is not None and i >= step_at else 0)
        b = 50 + 0.2 * ((i * 5) % 13 - 6) / 6
        rows.append([i, f"{a:.5f}", f"{b:.5f}"])
    return rows


def daily(start_day, days, step_at=None, step=0.0, spike_at=None):
    """5-minute samples with a strong daily cycle, as a water network's demand: tag A = 50 + 20 sin(time of day)
    with 0.3 gaussian noise (seeded, deterministic), tag B = 30 + 5 sin(...) with 0.1 noise. Timestamps from
    2026-01-01 + start_day. A steps by `step` from row step_at (a row of this export); spike_at puts a single-row
    spike of +40 in A."""
    rng = random.Random(start_day)
    t0 = datetime(2026, 1, 1) + timedelta(days=start_day)
    rows = []
    for i in range(days * 288):
        t = t0 + timedelta(minutes=5 * i)
        ph = 2 * math.pi * (t.hour * 60 + t.minute) / 1440
        a = 50 + 20 * math.sin(ph) + rng.gauss(0, 0.3) + (step if step_at is not None and i >= step_at else 0)
        if spike_at is not None and i == spike_at:
            a += 40
        b = 30 + 5 * math.sin(ph + 1) + rng.gauss(0, 0.1)
        rows.append([f"{t:%Y-%m-%d %H:%M:%S}", f"{a:.4f}", f"{b:.4f}"])
    return rows


class BandsTest(unittest.TestCase):
    def test_both_csv_inputs_and_both_report_names_are_protected(self):
        for role in ("normal", "score"):
            for extension in ("md", "json"):
                with self.subTest(role=role, extension=extension):
                    out = self.d / f"{role}-{extension}"
                    out.mkdir()
                    normal = write_csv(out / "normal.csv", ["sample", "A", "B"], synthetic())
                    score = write_csv(out / "score.csv", ["sample", "A", "B"], synthetic(step_at=120))
                    source = normal if role == "normal" else score
                    target = out / f"csv_normal_bands.{extension}"
                    target.hardlink_to(source)
                    companion = out / f"csv_normal_bands.{'md' if extension == 'json' else 'json'}"
                    companion.write_bytes(b"keep companion")
                    before = {p: p.read_bytes() for p in (normal, score, target, companion)}
                    with self.assertRaisesRegex(SystemExit, "output aliases an input"):
                        cnb.main(["--normal", str(normal), "--score", str(score), "--out", str(out)])
                    self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_exact_csv_collision_and_sibling_aliases_are_refused(self):
        normal = write_csv(self.d / "csv_normal_bands.json", ["sample", "A", "B"], synthetic())
        before = normal.read_bytes()
        with self.assertRaisesRegex(SystemExit, "output aliases an input"):
            cnb.main(["--normal", str(normal), "--out", str(self.d)])
        self.assertEqual(normal.read_bytes(), before)
        self.assertFalse((self.d / "csv_normal_bands.md").exists())
        out = self.d / "out"
        out.mkdir()
        md = out / "csv_normal_bands.md"
        md.write_bytes(b"retain outputs")
        (out / "csv_normal_bands.json").hardlink_to(md)
        with self.assertRaisesRegex(SystemExit, "files alias each other"):
            cnb.main(["--normal", str(normal), "--out", str(out)])
        self.assertEqual(md.read_bytes(), b"retain outputs")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_step_detected_at_the_right_sample(self):
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], synthetic())
        fault = write_csv(self.d / "f.csv", ["sample", "A", "B"], synthetic(step_at=120))
        r = cnb.run(normal, fault, fault_start=100, method="level")
        f = r["scored"]["fault"]
        self.assertEqual(r["scored"]["per_tag"]["B"]["first_outside_row"], 120)
        self.assertIsNone(r["scored"]["per_tag"]["A"]["first_outside_row"])
        self.assertEqual(f["first_flag_row"], 120)
        self.assertEqual(f["first_flag_delay"], 20)  # sample index column: delay in samples
        self.assertEqual(f["detection_run3_row"], 120)
        self.assertEqual(f["false_alarms_before_fault"]["flagged_samples"], 0)
        self.assertEqual(r["held_out_normal"]["flagged_samples_any_tag"], 0)
        self.assertEqual(r["k"], 3)  # this wiggle is bounded, so the smallest K already has no held-out flags

    def test_false_alarm_before_fault_is_counted(self):
        rows = synthetic(step_at=120)
        rows[30][1] = "99"  # one spike in A, before the labelled fault
        fault = write_csv(self.d / "f.csv", ["sample", "A", "B"], rows)
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], synthetic())
        fa = cnb.run(normal, fault, fault_start=100, method="level")["scored"]["fault"]["false_alarms_before_fault"]
        self.assertEqual((fa["flagged_samples"], fa["alarm_events_run3"], fa["tags"]), (1, 0, ["A"]))

    def test_timestamps_and_fault_start_by_time(self):
        base = [r[:] for r in synthetic(step_at=120)]
        for i, r in enumerate(base):
            r[0] = f"2026-10-01 {8 + i // 60:02d}:{i % 60:02d}:00"
        normal = write_csv(self.d / "n.csv", ["Time", "A", "B"], synthetic())
        fault = write_csv(self.d / "f.csv", ["Time", "A", "B"], base)
        f = cnb.run(normal, fault, fault_start="2026-10-01 09:40:00", method="level")["scored"]["fault"]
        self.assertEqual((f["fault_start_row"], f["first_flag_row"], f["first_flag_delay"]), (100, 120, 1200.0))

    def test_blank_and_text_cells_are_bad_not_zero(self):
        rows = synthetic()
        rows[5][1], rows[6][1], rows[7][2] = "", "Bad", "nan"
        p = write_csv(self.d / "g.csv", ["sample", "A", "B"], rows)
        _, tags, _, parsed = cnb.read_historian_csv(p)
        self.assertEqual((parsed[5][0], parsed[6][0], parsed[7][1]), (None, None, None))
        self.assertNotIn(0.0, [v for r in parsed for v in r])
        # Bad cells are left out of the fit (a zero would drag the mean of A from 10 towards 0) and never flagged.
        r = cnb.run(p, p, fault_start=0)
        self.assertEqual(r["bands"]["A"]["fit_bad"], 2)
        self.assertAlmostEqual(r["bands"]["A"]["mean"], 10, delta=0.05)
        self.assertEqual(r["scored"]["per_tag"]["A"]["bad_samples"], 2)
        self.assertEqual(r["scored"]["per_tag"]["A"]["flagged_samples"], 0)

    def test_malformed_header_refused_with_a_clear_message(self):
        cases = {
            "missing header": (["0", "1.0", "2.0"], "is a number (is the header row missing?)"),
            "duplicate": (["t", "A", "A"], "duplicate tag names: A"),
            "empty name": (["t", "A", ""], "column 3 has an empty tag name"),
            "one column": (["t"], "expected a time/index column followed by at least one tag column"),
        }
        for name, (header, msg) in cases.items():
            with self.subTest(name):
                p = write_csv(self.d / "bad.csv", header, [[0] + [1.0] * (len(header) - 1)])
                with self.assertRaises(cnb.CsvFormatError) as e:
                    cnb.read_historian_csv(p)
                self.assertIn(msg, str(e.exception))
                self.assertIn("malformed header" if name != "one column" else "header has", str(e.exception))

    def test_ragged_row_and_bad_time_refused(self):
        p = write_csv(self.d / "r.csv", ["t", "A"], [[0, 1.0], [1, 1.0, 2.0]])
        with self.assertRaisesRegex(cnb.CsvFormatError, "line 3 has 3 cells, the header has 2"):
            cnb.read_historian_csv(p)

    def test_nonfinite_time_cells_are_refused_with_their_line(self):
        for value in ("nan", "NaN", "inf", "-inf", "1e999"):
            with self.subTest(value):
                p = write_csv(self.d / "nonfinite.csv", ["t", "A"], [[0, 1], [value, 2]])
                with self.assertRaisesRegex(cnb.CsvFormatError, "line 3:.*numeric times must be finite"):
                    cnb.read_historian_csv(p)
                with self.assertRaises(ValueError):
                    cnb.parse_time(value)
        p = write_csv(self.d / "t.csv", ["t", "A"], [["yesterday", 1.0]])
        with self.assertRaisesRegex(cnb.CsvFormatError, "neither a number nor an ISO 8601 timestamp"):
            cnb.read_historian_csv(p)
        p = write_csv(self.d / "z.csv", ["t", "A"], [["2026-10-01T08:00:00Z", 1.0], ["2026-10-01T08:01:00", 1.0]])
        with self.assertRaisesRegex(cnb.CsvFormatError, "line 3: .*time zone"):
            cnb.read_historian_csv(p)

    def test_nonincreasing_times_are_refused(self):
        cases = ([2, 1], [0, 2, 1], [0, 0], [0, "0.0"],
                 ["2026-10-01T08:00:01", "2026-10-01T08:00:00"],
                 ["2026-10-01T08:00:00Z", "2026-10-01T08:00:00+00:00"],
                 ["2026-10-01T08:00:00Z", "2026-10-01T09:00:00+01:00"],
                 ["2026-10-01T08:00:00Z", "2026-10-01T08:30:00+01:00"])
        for times in cases:
            with self.subTest(times):
                p = write_csv(self.d / "order.csv", ["time", "A"], [[t, i] for i, t in enumerate(times)])
                before = p.read_bytes()
                with self.assertRaisesRegex(cnb.CsvFormatError, "time/index must be strictly increasing") as e:
                    cnb.read_historian_csv(p, with_text=True)
                self.assertIn("at line", str(e.exception))
                self.assertEqual(p.read_bytes(), before)

    def test_order_uses_parsed_instants_and_preserves_uneven_samples(self):
        texts = ["2026-10-01T09:00:00+01:00", "2026-10-01T08:30:00Z", "2026-10-01T10:45:00+01:00"]
        p = write_csv(self.d / "offsets.csv", ["time", "A"], [[t, v] for t, v in zip(texts, [2, "Bad", 4])])
        _, tags, times, rows, read_texts = cnb.read_historian_csv(p, with_text=True)
        self.assertEqual((tags, rows, read_texts), (["A"], [[2.0], [None], [4.0]], texts))
        self.assertEqual(cnb.elapsed(times, 0, 1), 1800)
        self.assertEqual(cnb.elapsed(times, 1, 2), 4500)
        normal = write_csv(self.d / "normal.csv", ["time", "A"], [[i, 0] for i in range(80)])
        score = write_csv(self.d / "uneven.csv", ["time", "A"],
                          [[t, 0 if i < 3 else 10] for i, t in enumerate([0, 1, 2.5, 7, 10, 12])])
        f = cnb.run(normal, score, fault_start="2.5", method="level")["scored"]["fault"]
        self.assertEqual((f["fault_start_row"], f["first_flag_row"], f["detection_run3_row"]), (2, 3, 3))
        self.assertEqual((f["first_flag_delay"], f["detection_run3_delay"]), (4.5, 4.5))

    def test_error_locations_are_physical_csv_record_spans(self):
        p = self.d / "physical.csv"
        # Header at 2-3, first data record at 5-6, next data record at 8-9.
        p.write_text('\n time,"A\nB"\n\n0,"Bad\nvalue"\n\n-1,"also\nbad"\n', encoding="utf-8")
        with self.assertRaisesRegex(cnb.CsvFormatError, "lines 8-9:.*strictly increasing.*at lines 5-6"):
            cnb.read_historian_csv(p)
        # Other existing data errors must also locate the physical record after skipped/multiline rows.
        for row, message in (("yesterday,2", "line 6:.*neither a number"),
                             ("1,2,3", "line 6 has 3 cells"),
                             ("2026-10-01T08:00:00,2", "line 6:.*mixes timestamps and numbers")):
            with self.subTest(row):
                p.write_text('time,A\n\n0,"Bad\nvalue"\n\n' + row + '\n', encoding="utf-8")
                with self.assertRaisesRegex(cnb.CsvFormatError, message):
                    cnb.read_historian_csv(p)

    def test_band_cli_refuses_bad_order_before_any_output_write(self):
        normal = write_csv(self.d / "normal.csv", ["time", "A"], [[i, 0] for i in range(80)])
        bad = write_csv(self.d / "bad.csv", ["time", "A"], [[0, 0], [100, 0], [20, 10], [30, 10], [40, 10]])
        originals = {p: p.read_bytes() for p in (normal, bad)}
        for method in cnb.METHODS:
            for role in ("normal", "score"):
                for existing in (False, True):
                    with self.subTest(method=method, role=role, existing=existing):
                        out = self.d / f"{method}-{role}-{existing}"
                        before = {}
                        if existing:
                            out.mkdir()
                            before = {"csv_normal_bands.json": b"previous JSON", "csv_normal_bands.md": b"previous report",
                                      "authored-note.txt": b"retain this note"}
                            for name, data in before.items():
                                (out / name).write_bytes(data)
                        args = [sys.executable, "-S", str(ROOT / "scripts/csv_normal_bands.py"),
                                "--normal", str(bad if role == "normal" else normal), "--score", str(bad),
                                "--fault-start", "20.0", "--method", method, "--out", str(out)]
                        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=30)
                        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                        self.assertIn("strictly increasing", r.stderr)
                        self.assertIn("line 4", r.stderr)
                        self.assertNotIn("Traceback", r.stderr)
                        self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()} if out.exists() else {}, before)
                        if not existing:
                            self.assertFalse(out.exists())
        self.assertTrue(all(p.read_bytes() == data for p, data in originals.items()))

    def test_bad_fault_start_says_which_formats_are_accepted(self):
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], synthetic())
        for bad in ("abc", "2026-10-01 09:40:00"):  # not a time at all; a timestamp on a numeric first column
            with self.subTest(bad):
                with self.assertRaises(SystemExit) as e:
                    cnb.main(["--normal", str(normal), "--score", str(normal), "--fault-start", bad,
                              "--out", str(self.d / "o")])
                msg = str(e.exception.code)
                self.assertNotIn("isoformat", msg)
                for part in ("0-based data-row number", "160", "480.0", "ISO 8601", "2026-10-01 09:40:00"):
                    self.assertIn(part, msg)

    def test_small_sample_warned_in_json_and_markdown(self):
        rows = synthetic(n=8)  # 4 fit rows, 4 held-out rows
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], rows)
        r = cnb.run(normal)
        self.assertTrue(r["warnings"])
        joined = " ".join(r["warnings"])
        self.assertIn("4 fit rows", joined)
        self.assertIn("4 held-out rows", joined)
        self.assertIn(str(cnb.MIN_ROWS), joined)
        md = cnb.markdown(r, "samples")
        self.assertIn("Warning", md)
        self.assertIn("4 fit rows", md)
        # A large enough export carries no warning key at all (committed outputs stay byte-identical).
        big = write_csv(self.d / "b.csv", ["sample", "A", "B"], synthetic(n=600))
        self.assertNotIn("warnings", cnb.run(big))

    def test_drifting_normal_flagged_by_level_bands_not_by_drift_method(self):
        # The PRONTO / SKAB / HAI failure in miniature: bands fitted on a short window of slowly drifting normal
        # running, scored on a later export of the same normal running further along the drift.
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], drifting(0, 1200))
        later = write_csv(self.d / "l.csv", ["sample", "A", "B"], drifting(3000, 1200))
        old = cnb.run(normal, later, fault_start=1000, method="level")["scored"]["fault"]
        self.assertGreater(old["false_alarms_before_fault"]["flagged_samples"], 900)  # level bands: nearly every row
        r = cnb.run(normal, later, fault_start=1000)
        self.assertEqual(r["method_name"], "drift")  # the default
        new = r["scored"]["fault"]
        self.assertEqual(new["false_alarms_before_fault"]["flagged_samples"], 0)
        self.assertIsNone(new["detection_run3_row"])  # and nothing after the 'fault' either: there is none

    def test_step_on_drifting_normal_detected_by_both_methods(self):
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], drifting(0, 1200))
        fault = write_csv(self.d / "f.csv", ["sample", "A", "B"], drifting(3000, 1200, step_at=3900))
        for method in ("level", "drift"):
            with self.subTest(method):
                f = cnb.run(normal, fault, fault_start=900, method=method)["scored"]["fault"]
                self.assertIsNotNone(f["detection_run3_row"])
                self.assertLessEqual(f["detection_run3_row"] - 900, 5)
        new = cnb.run(normal, fault, fault_start=900)["scored"]
        self.assertEqual(new["fault"]["false_alarms_before_fault"]["flagged_samples"], 0)
        self.assertEqual(new["fault"]["first_tags"][0]["tag"], "A")
        self.assertIsNone(new["per_tag"]["B"]["first_outside_row"])

    def test_band_follows_a_lower_reading_down_to_half(self):
        # SKAB's valve runs in miniature: the normal export runs at 100, the scored one at 25 with proportionally less
        # noise; a 6%-of-reading drop is buried under a band sized for 100 unless the band follows the reading.
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], percent_noise(100, 0, 2000))
        fault = write_csv(self.d / "f.csv", ["sample", "A", "B"], percent_noise(25, 5000, 2000, step_at=6000,
                                                                            step=-1.5))
        f = cnb.run(normal, fault, fault_start=1000)["scored"]["fault"]
        self.assertEqual(f["false_alarms_before_fault"]["flagged_samples"], 0)
        self.assertIsNotNone(f["detection_run3_row"])
        self.assertLess(f["detection_run3_row"] - 1000, 20)
        self.assertEqual([cnb.level_scale(x, 100) for x in (25, 50, 80, 100, 400)], [0.5, 0.5, 0.8, 1.0, 1.0])
        self.assertEqual(cnb.level_scale(3.0, 0.0), 1.0)
        old = cnb.DRIFT_SCALE_MIN
        try:  # the unscaled band (round-1 drift method) misses it
            cnb.DRIFT_SCALE_MIN = 1.0
            self.assertIsNone(cnb.run(normal, fault, fault_start=1000)["scored"]["fault"]["detection_run3_row"])
        finally:
            cnb.DRIFT_SCALE_MIN = old

    def test_drift_band_floor_and_k(self):
        # Half-width = max(K x spread of the residual, FLOOR x |normal mean|); K from DRIFT_KS on held-out rows.
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], drifting(0, 1200))
        r = cnb.run(normal)
        self.assertIn(r["k"], cnb.DRIFT_KS)
        a = r["bands"]["A"]
        self.assertAlmostEqual(a["floor"], cnb.DRIFT_FLOOR * abs(a["mean"]), places=5)
        self.assertAlmostEqual(a["half_width"], max(r["k"] * a["resid_sd"], a["floor"]), places=5)
        self.assertEqual(r["held_out_normal"]["flagged_samples_any_tag"], 0)
        with self.assertRaises(SystemExit):
            cnb.main(["--normal", str(normal), "--method", "nope", "--out", str(self.d / "o")])

    # ---------------------------------------------------------------- cyclic method and the automatic choice

    def test_daily_cycle_chosen_automatically_and_step_found(self):
        # BattLeDIM in miniature: a daily swing of +/-20 hides a step of 2 (a leak) from the drift method, whose
        # 10-vs-600-sample gap swings with the day; against the time-of-day profile the step stands out.
        normal = write_csv(self.d / "n.csv", ["Time", "A", "B"], daily(0, 6))
        fault = write_csv(self.d / "f.csv", ["Time", "A", "B"], daily(20, 4, step_at=600, step=2.0))
        r = cnb.run(normal, fault, fault_start=600)
        self.assertEqual(r["method_name"], "cyclic")
        self.assertEqual(r["method_choice"]["requested"], "auto")
        self.assertGreaterEqual(r["method_choice"]["daily_profile_r2"], cnb.CYCLIC_MIN_R2)
        f = r["scored"]["fault"]
        self.assertEqual(f["false_alarms_before_fault"]["flagged_samples"], 0)
        self.assertIsNotNone(f["detection_run3_row"])
        self.assertLess(f["detection_run3_row"] - 600, 30)
        self.assertEqual(f["first_tags"][0]["tag"], "A")
        drift = cnb.run(normal, fault, fault_start=600, method="drift")["scored"]["fault"]
        self.assertIsNone(drift["detection_run3_row"])  # the swing sets the drift band far wider than the step
        md = cnb.markdown(r, "seconds")
        self.assertIn("cyclic", md)
        self.assertIn("time of day", md)

    def test_cyclic_profile_slots(self):
        # 48 slots of 30 minutes; a slot with fewer than CYCLIC_MIN_SLOT fit values falls back to the tag's mean.
        self.assertEqual(cnb.CYCLIC_SLOTS, 48)
        times = [datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 1, 0, 29), datetime(2026, 1, 1, 0, 30),
                 datetime(2026, 1, 1, 23, 59)]
        self.assertEqual([cnb.day_slot(t) for t in times], [0, 0, 1, 47])
        rows = [[1.0], [3.0], [5.0], [None]] + [[2.0]] * 3
        slots = [0, 0, 0, 0, 5, 5, 5]
        prof = cnb.slot_profile(["A"], rows, slots)["A"]
        self.assertEqual(prof["slots"][0], 3.0)  # bad cell left out
        self.assertEqual(prof["slots"][5], 2.0)
        self.assertNotIn(7, prof["slots"])
        self.assertAlmostEqual(cnb.profile_value(prof, 7), prof["mean"])
        thin = cnb.slot_profile(["A"], [[1.0], [9.0]], [3, 3])["A"]
        self.assertNotIn(3, thin["slots"])  # 2 values < CYCLIC_MIN_SLOT

    def test_single_row_spike_ignored_by_cyclic_method(self):
        normal = write_csv(self.d / "n.csv", ["Time", "A", "B"], daily(0, 6))
        fault = write_csv(self.d / "f.csv", ["Time", "A", "B"], daily(20, 4, spike_at=300, step_at=900, step=2.0))
        f = cnb.run(normal, fault, fault_start=900, method="cyclic")["scored"]["fault"]
        self.assertEqual(f["false_alarms_before_fault"]["flagged_samples"], 0)  # median of 3 removes a 1-row spike
        self.assertIsNotNone(f["detection_run3_row"])
        self.assertEqual(cnb.median3([1.0, None, 9.0, 1.0, 1.0, 5.0]), [1.0, None, 9.0, 1.0, 1.0, 1.0])

    def test_auto_keeps_drift_without_a_daily_cycle(self):
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], drifting(0, 1200))
        fault = write_csv(self.d / "f.csv", ["sample", "A", "B"], drifting(3000, 1200, step_at=3900))
        auto = cnb.run(normal, fault, fault_start=900)
        drift = cnb.run(normal, fault, fault_start=900, method="drift")
        self.assertEqual(auto["method_name"], "drift")
        self.assertIn("not a timestamp", auto["method_choice"]["why"])
        for key in ("k", "bands", "scored", "held_out_normal"):
            self.assertEqual(auto[key], drift[key])
        # Timestamps over enough days but no daily pattern: still drift.
        rng = random.Random(1)
        t0 = datetime(2026, 1, 1)
        flat = [[f"{t0 + timedelta(minutes=5 * i):%Y-%m-%d %H:%M:%S}", f"{50 + rng.gauss(0, 1):.4f}"]
                for i in range(6 * 288)]
        r = cnb.run(write_csv(self.d / "flat.csv", ["Time", "A"], flat))
        self.assertEqual(r["method_name"], "drift")
        self.assertLess(r["method_choice"]["daily_profile_r2"], cnb.CYCLIC_MIN_R2)
        short = cnb.run(write_csv(self.d / "short.csv", ["Time", "A", "B"], daily(0, 3)))  # fit 1.5 days
        self.assertEqual(short["method_name"], "drift")
        self.assertIn("days", short["method_choice"]["why"])

    def test_cyclic_requested_without_timestamps_uses_a_flat_profile(self):
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], drifting(0, 1200))
        r = cnb.run(normal, method="cyclic")
        self.assertEqual(r["method_name"], "cyclic")
        self.assertEqual(r["cyclic_profile"], "flat")
        self.assertTrue(any("no time-of-day profile" in w for w in r["warnings"]))

    def test_score_flags_reproduce_run(self):
        # The per-row flags a caller needs (the matrix's HAI attack events) for every method, from one function.
        normal = write_csv(self.d / "n.csv", ["Time", "A", "B"], daily(0, 6))
        fault = write_csv(self.d / "f.csv", ["Time", "A", "B"], daily(20, 4, step_at=600, step=2.0))
        for method in ("cyclic", "drift", "level"):
            with self.subTest(method):
                r = cnb.run(normal, fault, fault_start=600, method=method)
                flags = cnb.score_flags(normal, fault, r["k"], r["method_name"])
                self.assertEqual(cnb.first_run(flags, 600), r["scored"]["fault"]["detection_run3_row"])
                self.assertEqual(sum(flags), r["scored"]["flagged_samples_any_tag"])

    def test_cli_refuses_malformed_header_without_traceback(self):
        p = write_csv(self.d / "bad.csv", ["t", "A", "A"], [[0, 1, 2]])
        with self.assertRaises(SystemExit) as e:
            cnb.main(["--normal", str(p), "--out", str(self.d / "o")])
        self.assertIn("duplicate tag names", str(e.exception.code))


TE_FILES = (ROOT / "data/external/te-braatz/d06_te.dat", ROOT / "out/ignition/normal_bands.json",
            ROOT / "out/fault_detection/fault_detection.json", EXAMPLE / "te_normal_d00.csv")


@unittest.skipUnless(all(p.exists() for p in TE_FILES), "TE cache or committed TE outputs not present")
class TeAgreementTest(unittest.TestCase):
    """The CSV route on the example export agrees with normal_bands.py / fault_detection_eval.py for fault 6."""

    @classmethod
    def setUpClass(cls):
        cls.r = cnb.run(EXAMPLE / "te_normal_d00.csv", EXAMPLE / "te_fault6_d06.csv", fault_start=160, method="level")
        cls.nb = json.loads(TE_FILES[1].read_text(encoding="utf-8"))
        cls.fd = json.loads(TE_FILES[2].read_text(encoding="utf-8"))["methods"]["shipped_bands"]["faults"]["6"]

    def test_same_k_and_bands(self):
        self.assertNotIn("warnings", self.r)  # 480 fit / 480 held-out rows: no small-sample warning
        self.assertEqual(self.r["k"], self.nb["k"])
        for t, b in self.r["bands"].items():
            o = self.nb["bands"][t]
            for key, places in (("mean", 4), ("lo", 4), ("hi", 4), ("sd", 5)):  # normal_bands.json rounding
                self.assertAlmostEqual(b[key], o[key], delta=0.6 * 10 ** -places, msg=f"{t} {key}")

    def test_same_fault6_first_flags(self):
        mine = {x["tag"]: x["row"] for x in self.r["scored"]["fault"]["first_tags"]}
        theirs = {x["tag"]: x["sample"] for x in self.nb["fault6"]["first_flags"] if x["tag"] in self.r["tags"]}
        self.assertTrue(theirs)
        for t, s in theirs.items():
            self.assertEqual(mine.get(t), s, t)
        # fault_detection_eval.py (shipped bands, 52 channels): detected at 0 min, no pre-onset flags.
        f = self.r["scored"]["fault"]
        self.assertEqual(f["detection_run3_delay"], self.fd["delay_min"])
        self.assertEqual(f["false_alarms_before_fault"]["flagged_samples"], 0)
        self.assertEqual(self.fd["pre_onset_flag_rate"], 0.0)

    def test_every_tag_first_flag_matches_te_bands_on_the_raw_file(self):
        # Independent of the CSV export: score d06_te.dat with the committed TE bands, column by column.
        raw = [list(map(float, l.split())) for l in TE_FILES[0].read_text().splitlines() if l.strip()]
        for j, t in enumerate(self.r["tags"]):
            o = self.nb["bands"][t]
            first = next((i for i in range(160, len(raw)) if raw[i][j] < o["lo"] or raw[i][j] > o["hi"]), None)
            self.assertEqual(self.r["scored"]["per_tag"][t]["first_outside_row"], first, t)


@unittest.skipUnless((EXAMPLE / "te_fault6_d06.csv").exists(), "example CSVs not present")
class TeDefaultMethodTest(unittest.TestCase):
    """The committed example output is the default (drift) method's; on fault 6 it detects with no flag before the
    fault. Written expecting the level method's 0-minute delay; the drift method's 10-sample average needs 7 TE
    samples (21 min) for FT-101 to clear its band, so the bound is 10 samples (30 min) and the README says why."""

    def test_committed_example_is_the_default_and_regenerates(self):
        r = cnb.run(EXAMPLE / "te_normal_d00.csv", EXAMPLE / "te_fault6_d06.csv", fault_start=160)
        self.assertEqual(r["method_name"], "drift")
        committed = json.loads((EXAMPLE / "results" / "csv_normal_bands.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(json.dumps(r)), committed)
        f = r["scored"]["fault"]
        self.assertEqual(f["false_alarms_before_fault"]["flagged_samples"], 0)
        self.assertLessEqual(f["detection_run3_delay"], 30)
        self.assertEqual(f["first_tags"][0]["tag"], "FT-101")
        level = cnb.run(EXAMPLE / "te_normal_d00.csv", EXAMPLE / "te_fault6_d06.csv", fault_start=160,
                        method="level")["scored"]["fault"]
        self.assertEqual(level["detection_run3_delay"], 0)  # the TE scripts' method, as before


class HistorianAdaptersTest(unittest.TestCase):
    """scripts/historian_adapters.py on tiny synthetic inputs shaped like the real files."""

    def setUp(self):
        import historian_adapters as ha
        self.ha = ha
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_uci_cycle_means_and_first_worse_cycle(self):
        ha = self.ha
        self.assertEqual(ha.uci_cycle_means(["1\t2\t3\n", "4\t4\n"]), [2.0, 4.0])
        prof = ([(100, 100, 0, 90, 0)] * 2200)
        prof[100:110] = [(100, 100, 0, 130, 1)] * 10  # a repair (accumulator 90 -> 130 bar) is not a fault
        prof[110] = (100, 100, 2, 130, 1)             # pump to severe leakage is
        means = {s: [float(i) for i in range(2205)] for s in ha.UCI_SENSORS}
        old = ha.UCI_SECTIONS
        try:
            ha.UCI_SECTIONS = ((1, 300),)
            run = ha.uci_runs_from(means, prof + [prof[-1]] * 5, self.d)[0]
        finally:
            ha.UCI_SECTIONS = old
        self.assertEqual((run["fault_cycle"], run["fault_start_row"]), (111, 10))
        _, tags, times, rows = cnb.read_historian_csv(run["score"])
        self.assertEqual((tags[0], times[0], rows[0][0], len(rows)), ("PS1", 6000.0, 100.0, 200))
        self.assertEqual(len(cnb.read_historian_csv(run["normal"])[3]), ha.UCI_NORMAL_CYCLES)

    def test_metropt_windows_and_analogue_columns_only(self):
        ha = self.ha
        head = ["", "timestamp"] + list(ha.METROPT_ANALOGUE) + ["COMP", "MPG"]
        rows = [head]
        t = datetime(2020, 2, 1)
        for k in range(10):  # normal week
            rows.append([str(k), f"{t + timedelta(hours=k):%Y-%m-%d %H:%M:%S}"] + ["1.5"] * 7 + ["1.0", "0.0"])
        for a, b, _ in ha.METROPT_FAILURES:  # one row 25 h before, one 1 h before, one at the start, one at the end
            s, e = datetime.fromisoformat(a), datetime.fromisoformat(b)
            for x in (s - timedelta(hours=25), s - timedelta(hours=1), s, e):
                rows.append(["0", f"{x:%Y-%m-%d %H:%M:%S}"] + ["2.5"] * 7 + ["1.0", "0.0"])
        runs = ha.metropt_runs_from(rows, self.d)
        self.assertEqual(len(runs), 4)
        for r in runs:
            self.assertEqual((r["fault_start_row"], r["rows"]), (1, 3))
        _, tags, _, normal = cnb.read_historian_csv(runs[0]["normal"])
        self.assertEqual((tags, len(normal)), (list(ha.METROPT_ANALOGUE), 10))

    def test_battledim_decimal_comma_join_and_leak_windows(self):
        ha = self.ha
        times = [datetime(2018, 1, 1) + timedelta(minutes=5 * i) for i in range(4000)]
        p = [["Timestamp", "n1", "n4"]] + [[f"{t:%Y-%m-%d %H:%M:%S}", "28,92", "33,1"] for t in times]
        f = [["Timestamp", "p1"]] + [[f"{t:%Y-%m-%d %H:%M:%S}", "75,5"] for t in times]
        config = ("times:\n  StartTime: 2018-01-01 00:00\nleakages:\n"
                  "- # linkID, startTime, endTime, leakDiameter (m), leakType, peakTime\n"
                  "- p9, 2018-01-08 13:30, 2018-01-09 00:00, 0.01, abrupt, 2018-01-08 13:30\n"
                  "- p7, 2019-01-08 13:30, 2019-01-09 00:00, 0.01, abrupt, 2019-01-08 13:30\n"
                  "sensors:\n")
        runs = ha.battledim_runs_from([p, f], config, self.d)
        self.assertEqual([r["name"] for r in runs], ["p9"])  # 2018 leaks only
        _, tags, _, normal = cnb.read_historian_csv(runs[0]["normal"])
        self.assertEqual((tags, normal[0]), (["n1", "n4", "p1"], [28.92, 33.1, 75.5]))
        self.assertEqual(len(normal), 7 * 288 + 162)  # up to 2018-01-08 13:25
        r = runs[0]
        _, _, st, _ = cnb.read_historian_csv(r["score"])
        self.assertEqual(st[r["fault_start_row"]], datetime(2018, 1, 8, 13, 30))
        self.assertEqual((st[0], st[-1]), (datetime(2018, 1, 6, 13, 30), datetime(2018, 1, 9, 0, 0)))
        bad = [p, f[:-1]]
        with self.assertRaisesRegex(ValueError, "row counts"):
            ha.battledim_runs_from(bad, config, self.d)

    def test_battledim_2019_year_mapping(self):
        # A178: normal = the year's start up to the first leak STARTING that year (leaks running on from 2018 are
        # part of normal); one run per leak starting in 2019; file names carry the year.
        ha = self.ha
        times = [datetime(2019, 1, 1) + timedelta(minutes=5 * i) for i in range(8000)]
        p = [["Timestamp", "n1"]] + [[f"{t:%Y-%m-%d %H:%M:%S}", "28,92"] for t in times]
        config = ("leakages:\n- # linkID, startTime, endTime, leakDiameter (m), leakType, peakTime\n"
                  "- p1, 2018-01-08 13:30, 2019-12-31 23:55, 0.01, incipient, 2018-01-25 08:30\n"
                  "- p7, 2019-01-15 23:00, 2019-01-17 00:00, 0.01, abrupt, 2019-01-15 23:00\n"
                  "- p8, 2019-01-18 10:00, 2019-12-31 23:55, 0.01, abrupt, 2019-01-18 10:00\n")
        runs = ha.battledim_runs_from([p], config, self.d, year=2019)
        self.assertEqual([r["name"] for r in runs], ["p7", "p8"])
        _, _, nt, normal = cnb.read_historian_csv(runs[0]["normal"])
        self.assertEqual((nt[0], nt[-1]), (datetime(2019, 1, 1), datetime(2019, 1, 15, 22, 55)))
        self.assertTrue(str(runs[0]["normal"]).endswith("battledim2019_normal.csv"))
        r = runs[1]
        _, _, st, _ = cnb.read_historian_csv(r["score"])
        self.assertEqual(st[r["fault_start_row"]], datetime(2019, 1, 18, 10, 0))
        self.assertEqual((st[0], st[-1]), (datetime(2019, 1, 16, 10, 0), datetime(2019, 1, 25, 10, 0)))
        self.assertEqual(ha.battledim_files(2019), ("2019_SCADA_Pressures.csv", "2019_SCADA_Flows.csv",
                                                    "2019_SCADA_Levels.csv"))
        self.assertEqual(ha.battledim_files(2018), ha.BATTLEDIM_FILES)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(HAVE_ASYNCUA, "asyncua not installed")
class ReplayServerTest(unittest.TestCase):
    def test_serves_values_that_move_and_bad_for_blank(self):
        from asyncua import Client
        import csv_replay_server as srv
        with tempfile.TemporaryDirectory() as d:
            rows = synthetic(n=6)
            for r in range(1, 6):  # B blank on every row the replay can serve (it starts at 1 and does not loop),
                rows[r][2] = ""   # so every read lands on a blank whatever the timing; A carries the good path
            p = write_csv(Path(d) / "s.csv", ["sample", "A", "B"], rows)
            port = free_port()
            args = srv.parse_args(["--csv", str(p), "--port", str(port), "--host", "127.0.0.1", "--rate", "0.5",
                                   "--start", "1", "--folder", "Plant"])

            async def go():
                stop = asyncio.Event()
                task = asyncio.create_task(srv.serve(args, stop))
                try:
                    client = Client(f"opc.tcp://127.0.0.1:{port}/csv-replay")
                    for _ in range(60):
                        try:
                            await client.connect()
                            break
                        except Exception:
                            if task.done():
                                task.result()
                            await asyncio.sleep(0.1)
                    else:
                        self.fail("server did not start")
                    try:
                        ns = await client.get_namespace_index("urn:pid-digital-twin:csv-replay")
                        nodes = [client.get_node(f"ns={ns};s=Plant/{n}") for n in ("_sample", "A", "B")]
                        seen = []
                        for _ in range(2):
                            seen.append(await client.read_attributes(nodes))
                            await asyncio.sleep(0.6)
                        with self.assertRaises(Exception):  # read-only from the client side
                            await nodes[1].write_value(1.0)
                        return seen
                    finally:
                        await client.disconnect()
                finally:
                    stop.set()
                    await asyncio.wait_for(task, 5)

            seen = asyncio.run(go())
        # Timing-free: whichever rows the two reads land on (a slow connect can skip some), each value must be
        # that row's value, and a blank cell must read Bad with no value, never a number.
        by_sample = {dv[0].Value.Value: dv for dv in seen}
        self.assertEqual(len(by_sample), 2, "the _sample node should move between reads")
        self.assertTrue(all(s >= 1 for s in by_sample), "replay should start at --start 1")
        for s, dv in by_sample.items():
            self.assertTrue(dv[1].StatusCode.is_good())
            self.assertAlmostEqual(dv[1].Value.Value, float(rows[s][1]))
            self.assertEqual(rows[s][2], "")
            self.assertEqual(dv[2].StatusCode.name, "BadNoData")
            self.assertIsNone(dv[2].Value.Value)

    def test_missing_csv_is_a_clear_error_not_a_traceback(self):
        import csv_replay_server as srv
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d) / "missing.csv"
            with self.assertRaises(SystemExit) as e:
                srv.main(["--csv", str(missing), "--host", "127.0.0.1", "--port", str(free_port())])
        msg = str(e.exception.code)
        self.assertTrue(msg.startswith("error: can't read"), msg)
        self.assertIn("missing.csv", msg)

    def test_reserved_tag_name_refused(self):
        import csv_replay_server as srv
        with tempfile.TemporaryDirectory() as d:
            p = write_csv(Path(d) / "r.csv", ["t", "_sample"], [[0, 1.0]])
            with self.assertRaisesRegex(cnb.CsvFormatError, "reserved"):
                srv.load(p)

    def test_nonincreasing_times_refused_before_replay_server_initialization(self):
        import csv_replay_server as srv
        with tempfile.TemporaryDirectory() as d:
            for times in ([2, 1], [0, 0], [0, 3, 2],
                          ["2026-10-01T08:00:00Z", "2026-10-01T09:00:00+01:00"]):
                with self.subTest(times):
                    p = write_csv(Path(d) / "bad.csv", ["time", "A"], [[t, i] for i, t in enumerate(times)])
                    before = p.read_bytes()
                    args = srv.parse_args(["--csv", str(p), "--host", "127.0.0.1", "--port", str(free_port())])
                    with mock.patch.object(srv, "Server") as constructor:
                        with self.assertRaisesRegex(cnb.CsvFormatError, "strictly increasing"):
                            asyncio.run(srv.serve(args))
                        constructor.assert_not_called()
                    result = subprocess.run([sys.executable, str(ROOT / "scripts/csv_replay_server.py"),
                                             "--csv", str(p), "--host", "127.0.0.1", "--port", str(args.port)],
                                            capture_output=True, text=True, encoding="utf-8", timeout=10)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("strictly increasing", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertNotIn("CSV replay", result.stdout)
                    self.assertEqual(p.read_bytes(), before)


if __name__ == "__main__":
    if not HAVE_ASYNCUA:
        print("SKIP asyncua not installed: OPC UA replay smoke not run")
    unittest.main(verbosity=2)
