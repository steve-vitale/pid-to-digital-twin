"""Control-loop table, data check and drawing audit (scripts/te_control_loops.py):
python scripts/test_te_control_loops.py

Needs the cached temain_mod.f and d00_te.dat (scripts/fetch_te_data.py). No network, model calls or gateway.
The audit tests are the grader's controls: before its 0/19 on the generated sheets means anything, it has to pass
a correctly drawn loop and fail each specific way a loop can be drawn wrong.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import te_control_loops as tcl  # noqa: E402


def sym(text, cls="instrumentation"):
    return {"class": cls, "box": [0, 0, 10, 10], "text": text}


def key(symbols, edges=(), signal_edges=()):
    return {"sheets": {"1": {"drawing": "T-1", "symbols": symbols, "edges": [list(e) for e in edges],
                             "signal_edges": [list(e) for e in signal_edges]}}}


class TableFromSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = tcl.build()
        cls.loops = {lp["id"]: lp for lp in cls.table["loops"]}

    def test_committed_table_matches_source(self):
        committed = json.loads(tcl.LOOPS.read_text(encoding="utf-8"))
        self.assertEqual(committed, json.loads(json.dumps(self.table)))

    def test_counts(self):
        self.assertEqual(self.table["summary"], {"running": 19, "valve_loops": 11, "cascades": 8,
                                                 "defined_not_called": ["C22"]})

    def test_pairings_come_from_code_not_comments(self):
        # temain_mod.f labels CONTRL6 and CONTRL10 "Stripper Level Controller"; the code says otherwise.
        self.assertEqual((self.loops["C6"]["measurement"]["tag"], self.loops["C6"]["output"]["tag"]),
                         ("FI-110", "FV-206"))
        self.assertEqual((self.loops["C10"]["measurement"]["tag"], self.loops["C10"]["output"]["tag"]),
                         ("TI-121", "TV-210"))
        self.assertEqual((self.loops["C11"]["measurement"]["tag"], self.loops["C11"]["output"]["tag"]),
                         ("FI-117", "TV-211"))

    def test_cascades_name_their_inner_loop(self):
        inner = {i: lp["output"]["inner_loop"] for i, lp in self.loops.items() if lp["output"]["kind"] == "setpoint"}
        self.assertEqual(inner, {"C13": "C3", "C14": "C1", "C15": "C2", "C16": "C9", "C17": "C4",
                                 "C18": "C10", "C19": "C6", "C20": "C16"})
        self.assertEqual(self.loops["C14"]["measurement"]["component"], "D")

    def test_scan_periods(self):
        self.assertEqual(self.loops["C1"]["scan_s"], 3)
        self.assertEqual(self.loops["C13"]["scan_s"], 360)
        self.assertEqual(self.loops["C20"]["scan_s"], 900)
        self.assertIsNone(self.loops["C22"]["scan_s"])

    def test_purge_override_is_on_separator_pressure(self):
        trips = [(o["condition"], o["forces_output_to"]) for o in self.table["overrides"] if not o["only_after_trip"]]
        self.assertEqual(trips, [(">= 2950", 100.0), ("<= 2300", 0.0)])
        self.assertEqual({o["tag"] for o in self.table["overrides"]}, {"PI-113"})

    def test_wrong_checksum_refused(self):
        bad = Path(tcl.ROOT / "out" / "_tmp_temain.f")
        bad.parent.mkdir(exist_ok=True)
        try:
            bad.write_bytes(tcl.SOURCE.read_bytes() + b"\n")
            with self.assertRaises(SystemExit):
                tcl.build(bad)
        finally:
            bad.unlink(missing_ok=True)


class DataCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = tcl.build()

    def test_every_controlled_variable_sits_on_its_setpoint(self):
        rows = tcl.data_check(self.table)["rows"]
        self.assertEqual(len(rows), 19)
        self.assertLess(max(r["dev_sd"] for r in rows), 0.5)

    def test_check_rejects_a_wrong_pairing(self):
        # Negative control: rotate the measurements one place. Most loops should now miss their setpoint badly.
        shuffled = copy.deepcopy(self.table)
        running = [lp for lp in shuffled["loops"] if lp["runs"]]
        indices = [lp["measurement"]["xmeas"] for lp in running]
        for lp, xmeas in zip(running, indices[1:] + indices[:1]):
            lp["measurement"]["xmeas"] = xmeas
        misses = [r for r in tcl.data_check(shuffled)["rows"] if r["dev_sd"] > 3]
        self.assertGreaterEqual(len(misses), 15)


class AuditControls(unittest.TestCase):
    """A two-loop table with matching numbers: C1 (FI-102 -> FV-102) and cascade C14 (AI-123 -> C1)."""

    def setUp(self):
        self.table = {"loops": [
            {"id": "C1", "runs": True, "measurement": {"tag": "FI-102"},
             "output": {"kind": "final_element", "tag": "FV-102"}},
            {"id": "C14", "runs": True, "measurement": {"tag": "AI-123"},
             "output": {"kind": "setpoint", "inner_loop": "C1"}},
        ]}
        self.symbols = {"m": sym("FI 102"), "c": sym("FIC 102"), "v": sym("FV 102", "valve"),
                        "a": sym("AI 123"), "ac": sym("AIC 123")}
        self.signals = [("m", "c"), ("c", "v"), ("a", "ac"), ("ac", "c")]

    def score(self, symbols=None, edges=(), signals=None):
        result = tcl.audit(self.table, key(symbols or self.symbols, edges,
                                           self.signals if signals is None else signals))
        return {r["loop"]: r["checks"] for r in result["rows"]}

    def test_correct_drawing_passes(self):
        scores = self.score()
        self.assertTrue(all(scores["C1"].values()), scores["C1"])
        self.assertTrue(all(scores["C14"].values()), scores["C14"])

    def test_process_lines_are_not_signals(self):
        scores = self.score(edges=self.signals, signals=[])
        self.assertFalse(scores["C1"]["controller"])
        self.assertFalse(scores["C1"]["signal"])

    def test_missing_controller_to_valve_signal(self):
        scores = self.score(signals=[("m", "c"), ("a", "ac"), ("ac", "c")])
        self.assertTrue(scores["C1"]["controller"])
        self.assertFalse(scores["C1"]["signal"])
        self.assertTrue(scores["C14"]["signal"])

    def test_mismatched_loop_number(self):
        symbols = dict(self.symbols, v=sym("FV 201", "valve"))
        table_valve = copy.deepcopy(self.table)
        table_valve["loops"][0]["output"]["tag"] = "FV-201"
        self.table = table_valve
        scores = self.score(symbols=symbols)
        self.assertTrue(scores["C1"]["signal"])
        self.assertFalse(scores["C1"]["numbering"])

    def test_controller_letter_must_match_measurement(self):
        symbols = dict(self.symbols, c=sym("TIC 102"))
        self.assertFalse(self.score(symbols=symbols)["C1"]["controller"])

    def test_indicator_printed_with_hyphen_or_space(self):
        symbols = dict(self.symbols, m=sym("FI-102"))
        self.assertTrue(self.score(symbols=symbols)["C1"]["measured"])


class GeneratedSheetsBaseline(unittest.TestCase):
    def test_current_sheets_draw_no_loops(self):
        # Pins the starting point. When the generator draws controllers and signals, update this to the new score.
        result = tcl.audit(tcl.build(), json.loads(tcl.KEY.read_text(encoding="utf-8")))
        self.assertEqual((result["correct"], result["by_check"]),
                         (0, {"measured": 19, "controller": 0, "signal": 0, "numbering": 0}))

    def test_naming_findings(self):
        findings = tcl.naming_findings(tcl.build())
        self.assertEqual(sum("different loop numbers" in f for f in findings), 11)
        self.assertEqual(sorted(f.split("'")[0] for f in findings if "first letter" in f), ["HV-205", "TV-211"])


if __name__ == "__main__":
    unittest.main()
