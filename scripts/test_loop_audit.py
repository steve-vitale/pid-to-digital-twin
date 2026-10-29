"""Tests for scripts/loop_audit.py: the Tennessee Eastman loop list against the committed answer keys, plus the
partial / not-drawn / refused cases. Stdlib only.

Usage:  python -m unittest scripts/test_loop_audit.py      (or python scripts/test_loop_audit.py)
"""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_audit as la  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOOPS = ROOT / "examples" / "loop-audit" / "te_loops.csv"
KEY_D = ROOT / "data" / "te_pid" / "key.json"
KEY_A = ROOT / "data" / "te_pid" / "rev-a" / "key.json"
KEY_C = ROOT / "data" / "te_pid" / "rev-c" / "key.json"
TABLE = ROOT / "data" / "te_control_loops.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class LoopAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text_or_obj):
        path = self.dir / name
        text = text_or_obj if isinstance(text_or_obj, str) else json.dumps(text_or_obj)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def key_without(self, drop_edge=None, drop_symbol_text=None):
        """Revision D's key with one signal edge or one symbol removed (in a temp copy)."""
        key = copy.deepcopy(_load(KEY_D))
        for sheet in key["sheets"].values():
            if drop_edge:
                ids = {sid for sid, s in sheet["symbols"].items() if s.get("text") in drop_edge}
                sheet["signal_edges"] = [e for e in sheet["signal_edges"] if set(e) != ids]
            if drop_symbol_text:
                gone = {sid for sid, s in sheet["symbols"].items() if s.get("text") == drop_symbol_text}
                for sid in gone:
                    del sheet["symbols"][sid]
                sheet["signal_edges"] = [e for e in sheet["signal_edges"] if not gone & set(e)]
        return self.write("key.json", key)

    # --- the committed example reproduces the existing audit -------------------------------------------------
    def test_csv_matches_loop_table(self):
        loops, ignored = la.read_loops(LOOPS)
        table = [lp for lp in _load(TABLE)["loops"] if lp["runs"]]
        self.assertEqual(ignored, [])
        self.assertEqual([(l["controller"], l["measurement"], l["output"]) for l in loops],
                         [(t["controller_tag"], t["measurement"]["tag"], t["output"]["tag"]) for t in table])

    def test_revision_a_draws_none(self):
        r = la.run(LOOPS, KEY_A)
        self.assertEqual(r["totals"], {"loops": 19, "drawn": 0, "partly_drawn": 0, "not_drawn": 19})

    def test_revision_d_draws_all(self):
        r = la.run(LOOPS, KEY_D)
        self.assertEqual(r["totals"], {"loops": 19, "drawn": 19, "partly_drawn": 0, "not_drawn": 0})
        self.assertEqual(set(r["by_check"].values()), {19})

    def test_revision_c_controllers_drawn_but_measurements_tagged_as_indicators(self):
        r = la.run(LOOPS, KEY_C)
        self.assertEqual(r["totals"]["drawn"], 0)
        row = next(x for x in r["loops"] if x["controller"] == "FIC-101")
        self.assertEqual(row["status"], "partly_drawn")
        self.assertEqual(row["missing"], ["measurement symbol", "signal line measurement -> controller"])
        self.assertIn("FI 101", row["controller_signal_links"])

    # --- partial / not drawn ------------------------------------------------------------------------------
    def test_removed_signal_edge_is_partial(self):
        r = la.run(LOOPS, self.key_without(drop_edge={"FIC 101", "FV 101"}))
        row = next(x for x in r["loops"] if x["controller"] == "FIC-101")
        self.assertEqual(row["status"], "partly_drawn")
        self.assertEqual(row["missing"], ["signal line controller -> output"])
        self.assertEqual(r["totals"]["drawn"], 18)

    def test_removed_cross_sheet_flag_is_partial(self):
        # C17: LIC-108 on sheet 101 drives FIC-104 on sheet 103 through a pair of signal flags.
        key = _load(KEY_D)
        for sheet in key["sheets"].values():
            sheet["symbols"] = {k: v for k, v in sheet["symbols"].items() if v.get("signal_from") != "LIC-108"}
        r = la.run(LOOPS, self.write("key.json", key))
        row = next(x for x in r["loops"] if x["controller"] == "LIC-108")
        self.assertEqual(row["missing"], ["signal line controller -> output"])

    def test_missing_controller_is_not_drawn(self):
        r = la.run(LOOPS, self.key_without(drop_symbol_text="TIC 121"))
        row = next(x for x in r["loops"] if x["controller"] == "TIC-121")
        self.assertEqual(row["status"], "not_drawn")
        self.assertIn("controller symbol", row["missing"])
        # TIC-121 is also the inner loop of TIC-109's cascade: that loop loses its output, so it is partial.
        outer = next(x for x in r["loops"] if x["controller"] == "TIC-109")
        self.assertEqual(outer["status"], "partly_drawn")
        self.assertEqual(r["totals"], {"loops": 19, "drawn": 17, "partly_drawn": 1, "not_drawn": 1})

    # --- refused input -------------------------------------------------------------------------------------
    def assertRefused(self, csv_text, *fragments):
        with self.assertRaises(la.InputError) as ctx:
            la.read_loops(self.write("loops.csv", csv_text))
        for f in fragments:
            self.assertIn(f, str(ctx.exception))

    def test_a_combined_instrument_counts_its_own_measurement(self):
        loops = self.write("combined.csv", "controller,measurement,output\nFIC-101,FIC-101,FV-101\n")
        rows = la.run(loops, ROOT / "data" / "te_pid" / "key.json")["loops"]
        self.assertEqual(rows[0]["status"], "drawn")
        self.assertIn("combined", rows[0]["note"])

    def test_report_table_says_combined_not_yes_for_a_combined_instrument(self):
        # No signal line stands behind signal_in for a combined instrument: the cell must not read as a drawn line.
        loops = self.write("combined.csv", "controller,measurement,output\nFIC-101,FIC-101,FV-101\n"
                                           "FIC-102,FT-102,FV-102\n")
        md = la.markdown(la.run(loops, KEY_D))
        rows = {ln.split(" | ")[1]: ln for ln in md.splitlines() if ln.startswith("| 2 ") or ln.startswith("| 3 ")}
        combined_cells = rows["FIC-101"].split(" | ")[5:10]
        self.assertEqual(combined_cells, ["yes", "combined", "yes", "combined", "yes"])
        self.assertEqual(rows["FIC-102"].split(" | ")[5:10], ["yes"] * 5)
        self.assertIn("signal line measurement -> controller 2/2 (1 combined instrument, no line drawn)", md)

    def test_a_tag_on_no_symbol_gets_a_spelling_hint(self):
        loops = self.write("typo.csv", "controller,measurement,output\nFIC-101.PV,FT-101,FV-101\n")
        rows = la.run(loops, ROOT / "data" / "te_pid" / "key.json")["loops"]
        self.assertEqual(rows[0]["status"], "not_drawn")
        self.assertIn(".PV", rows[0]["hint"])

    def test_bad_rows_refused_with_line_number(self):
        head = "# exported 2026-10-29\ncontroller,measurement,output\nFIC-1,FT-1,FV-1\n"
        self.assertRefused(head + "FIC-2,,FV-2\n", "line 4", "empty measurement")
        self.assertRefused(head + "\n# note\nFIC-2,FT-2,FV-2,extra\n", "line 6", "4 fields")
        self.assertRefused(head + "FIC 1,FT-9,FV-9\n", "line 4", "already listed on line 3")
        self.assertRefused(head + "FIC-2,FT-2,FIC-2\n", "line 4", "names itself")
        self.assertRefused("controller,measurement\nFIC-1,FT-1\n", "line 1", "output")

    def test_cli_refuses_with_exit_2_and_writes_nothing(self):
        out = self.dir / "report"
        bad = self.write("loops.csv", "controller,measurement,output\nFIC-1,FT-1\n")
        with contextlib.redirect_stderr(io.StringIO()):
            code = la.main(["--loops", str(bad), "--drawing", str(KEY_D), "--out", str(out)])
        self.assertEqual(code, 2)
        self.assertFalse(out.with_suffix(".md").exists())

    def test_cli_writes_markdown_and_json(self):
        out = self.dir / "report"
        with contextlib.redirect_stdout(io.StringIO()):
            code = la.main(["--loops", str(LOOPS), "--drawing", str(KEY_D), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertIn("19 of 19 loops drawn", out.with_suffix(".md").read_text(encoding="utf-8"))
        self.assertEqual(_load(out.with_suffix(".json"))["totals"]["drawn"], 19)

    # --- plant_model.json: tags only ------------------------------------------------------------------------
    def test_plant_model_checks_tags_only(self):
        key = _load(KEY_D)
        texts = [s["text"] for sh in key["sheets"].values() for s in sh["symbols"].values()
                 if s.get("class") == "instrumentation"]
        model = {"instruments": [{"id": f"IN{i}", "tag": t} for i, t in enumerate(texts) if t != "FV 105"],
                 "final_elements": [], "line_items": [], "units": []}
        r = la.run(LOOPS, self.write("plant_model.json", model))
        self.assertFalse(r["signals_checked"])
        self.assertEqual(r["totals"], {"loops": 19, "tags_present": 18, "partly_drawn": 1, "not_drawn": 0})
        row = next(x for x in r["loops"] if x["controller"] == "FIC-105")
        self.assertEqual(row["missing"], ["output symbol"])
        self.assertIsNone(row["checks"]["signal_in"])

    def test_unplaced_items_and_underscore_tags_count_as_drawn(self):
        # From the DEXPI matrix: a valve on a line with open ends sits in "unplaced" (still on the drawing), and a tool
        # allowing one hyphen per tag writes P-4712.02 as P_4712.02.
        model = {"units": [], "instruments": [], "final_elements": [], "line_items": [],
                 "controllers": [{"id": "C1", "tag": "PICSA-P_4712.02"}, {"id": "C2", "tag": "FIC-04"}],
                 "unplaced": [{"tag": "FV-04"}, {"tag": "PT-P_4712.01"}, {"tag": "PV-P_4712.02"}]}
        loops = self.write("loops.csv", "controller,measurement,output\nPICSA P-4712.02,PT P-4712.01,PV P-4712.02\n"
                                        "FIC-04,FIC-04,FV-04\n")
        r = la.run(loops, self.write("plant_model.json", model))
        self.assertEqual(r["totals"]["tags_present"], 2, r["loops"])

    def test_plant_model_combined_instrument_does_not_claim_three_tags(self):
        model = {"instruments": [{"id": "I1", "tag": "PICSA 4712.02"}, {"id": "I2", "tag": "PV4712.02"}]}
        loops = self.write("c.csv", "controller,measurement,output\nPICSA 4712.02,PICSA 4712.02,PV4712.02\n")
        r = la.run(loops, self.write("plant_model.json", model))
        self.assertTrue(r["loops"][0]["combined"])
        self.assertNotIn("all three tags", la.headline(r))
        self.assertIn("1 combined instrument", la.headline(r))
        row = next(l for l in la.markdown(r).splitlines() if l.startswith("| 2 "))
        self.assertEqual(row.split(" | ")[5:8], ["yes", "combined", "yes"])

    def test_unknown_drawing_refused(self):
        with self.assertRaises(la.InputError):
            la.run(LOOPS, self.write("x.json", {"nodes": []}))


if __name__ == "__main__":
    unittest.main()
