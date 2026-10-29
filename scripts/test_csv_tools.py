"""Tests for scripts/csv_normal_bands.py and scripts/csv_replay_server.py on synthetic CSVs; when the TE cache and
the committed TE outputs are present, also that the example CSV export reproduces the TE scripts' fault-6 results.

The OPC UA part runs the replay server in-process on a free 127.0.0.1 port (a few seconds) and stops it; it is
skipped, with a SKIP line, when asyncua is not installed. No process is left running.
"""
import asyncio
import csv
import importlib.util
import json
import socket
import sys
import tempfile
import unittest
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


class BandsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_step_detected_at_the_right_sample(self):
        normal = write_csv(self.d / "n.csv", ["sample", "A", "B"], synthetic())
        fault = write_csv(self.d / "f.csv", ["sample", "A", "B"], synthetic(step_at=120))
        r = cnb.run(normal, fault, fault_start=100)
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
        fa = cnb.run(normal, fault, fault_start=100)["scored"]["fault"]["false_alarms_before_fault"]
        self.assertEqual((fa["flagged_samples"], fa["alarm_events_run3"], fa["tags"]), (1, 0, ["A"]))

    def test_timestamps_and_fault_start_by_time(self):
        base = [r[:] for r in synthetic(step_at=120)]
        for i, r in enumerate(base):
            r[0] = f"2026-10-01 {8 + i // 60:02d}:{i % 60:02d}:00"
        normal = write_csv(self.d / "n.csv", ["Time", "A", "B"], synthetic())
        fault = write_csv(self.d / "f.csv", ["Time", "A", "B"], base)
        f = cnb.run(normal, fault, fault_start="2026-10-01 09:40:00")["scored"]["fault"]
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
        p = write_csv(self.d / "t.csv", ["t", "A"], [["yesterday", 1.0]])
        with self.assertRaisesRegex(cnb.CsvFormatError, "neither a number nor an ISO 8601 timestamp"):
            cnb.read_historian_csv(p)
        p = write_csv(self.d / "z.csv", ["t", "A"], [["2026-10-01T08:00:00Z", 1.0], ["2026-10-01T08:01:00", 1.0]])
        with self.assertRaisesRegex(cnb.CsvFormatError, "line 3: .*time zone"):
            cnb.read_historian_csv(p)

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
        cls.r = cnb.run(EXAMPLE / "te_normal_d00.csv", EXAMPLE / "te_fault6_d06.csv", fault_start=160)
        cls.nb = json.loads(TE_FILES[1].read_text(encoding="utf-8"))
        cls.fd = json.loads(TE_FILES[2].read_text(encoding="utf-8"))["methods"]["shipped_bands"]["faults"]["6"]

    def test_same_k_and_bands(self):
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
            rows[1][2] = ""  # B blank on row 1
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
        by_sample = {dv[0].Value.Value: dv for dv in seen}
        self.assertEqual(len(by_sample), 2, "the _sample node should move between reads")
        self.assertIn(1, by_sample, "replay should start at --start 1")
        bad = by_sample[1][2]
        self.assertFalse(bad.StatusCode.is_good())
        self.assertEqual(bad.StatusCode.name, "BadNoData")
        self.assertIsNone(bad.Value.Value)
        later = by_sample[max(by_sample)]
        self.assertTrue(later[2].StatusCode.is_good())
        self.assertAlmostEqual(later[1].Value.Value, float(rows[max(by_sample)][1]))
        self.assertNotEqual(by_sample[1][1].Value.Value, later[1].Value.Value)

    def test_reserved_tag_name_refused(self):
        import csv_replay_server as srv
        with tempfile.TemporaryDirectory() as d:
            p = write_csv(Path(d) / "r.csv", ["t", "_sample"], [[0, 1.0]])
            with self.assertRaisesRegex(cnb.CsvFormatError, "reserved"):
                srv.load(p)


if __name__ == "__main__":
    if not HAVE_ASYNCUA:
        print("SKIP asyncua not installed: OPC UA replay smoke not run")
    unittest.main(verbosity=2)
