"""Generated TE P&ID regressions (drawing generator, key, round-trip scorer, reviewer diff):
python scripts/test_te_pid_roundtrip.py

Needs Pillow, numpy and OpenCV (full suite). No model calls, network or gateway.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draw_pid_from_model as draw  # noqa: E402
import score_pid2graph as sc  # noqa: E402
import score_te_roundtrip as rt  # noqa: E402
import te_model_diff as tdiff  # noqa: E402
import trace_connections as tc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "te_process_model.json"
LAYOUT = ROOT / "data" / "te_pid_layout.json"
COMMITTED = ROOT / "data" / "te_pid"


def write_layout(tmp, mutate):
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    mutate(layout)
    p = Path(tmp) / "layout.json"
    p.write_text(json.dumps(layout), encoding="utf-8")
    return p


class GeneratorTests(unittest.TestCase):
    def test_committed_layout_draws_every_model_item_exactly_once(self):
        sheets = draw.generate(MODEL, LAYOUT, None, write=False)
        model = json.loads(MODEL.read_text(encoding="utf-8"))
        refs = [n["model_ref"] for sh in sheets for n in sh.nodes.values() if n["model_ref"]]
        tags = {i["tag"] for i in model["instruments"] + model["final_elements"]}
        # every tag once as a bubble; final elements on a line also once as a valve; every controller once
        bubbles = [n["model_ref"] for sh in sheets for n in sh.nodes.values() if n["class"] == "instrumentation"
                   and n["model_kind"] != "controller"]
        self.assertEqual(sorted(bubbles), sorted(tags))
        ctrls = [n["model_ref"] for sh in sheets for n in sh.nodes.values() if n["model_kind"] == "controller"]
        self.assertEqual(sorted(ctrls), sorted(c["tag"] for c in model["controllers"]))
        self.assertEqual(sorted(r for r in refs if r.startswith("unit:")), sorted(f"unit:{u['id']}" for u in model["units"]))

    def test_layout_that_drops_an_item_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            def drop(layout):
                del layout["sheets"][0]["units"]["R-101"]["mount"]["PI-107"]
            with self.assertRaisesRegex(ValueError, "PI-107: drawn 0 times"):
                draw.generate(MODEL, write_layout(tmp, drop), None, write=False)

    def test_layout_cannot_invent_a_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            def invent(layout):
                layout["sheets"][0]["units"]["R-101"]["mount"]["XI-999"] = [2300, 1100]
            with self.assertRaisesRegex(ValueError, "XI-999 is not in the model"):
                draw.generate(MODEL, write_layout(tmp, invent), None, write=False)

    def test_layout_cannot_draw_an_item_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            def twice(layout):
                layout["sheets"][2]["units"]["C-101"]["mount"]["PI-107"] = [1610, 1100]
            with self.assertRaisesRegex(ValueError, "PI-107: drawn 2 times"):
                draw.generate(MODEL, write_layout(tmp, twice), None, write=False)

    def test_a_missing_signal_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            def drop(layout):
                layout["sheets"][0]["signals"] = [s for s in layout["sheets"][0]["signals"]
                                                  if (s["from"], s["to"]) != ("FIC-101", "FV-101")]
            with self.assertRaisesRegex(ValueError, "signal FIC-101 -> FV-101: drawn 0 times"):
                draw.generate(MODEL, write_layout(tmp, drop), None, write=False)

    def test_a_signal_the_model_does_not_have_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            def invent(layout):  # TI-109 does not feed the level controller
                layout["sheets"][0]["signals"].append({"from": "TI-109", "to": "LIC-108",
                                                       "via": [[2100, 1140], [2100, 1030]]})
            with self.assertRaisesRegex(ValueError, "signal TI-109 -> LIC-108 is not in the model"):
                draw.generate(MODEL, write_layout(tmp, invent), None, write=False)

    def test_a_signal_through_a_symbol_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            def through(layout):  # into FIC-101 from below, along y=280: straight through FI-101's bubble
                for s in layout["sheets"][0]["signals"]:
                    if (s["from"], s["to"]) == ("AIC-123A", "FIC-101"):
                        s["via"] = [[1250, 280], [915, 280]]
            with self.assertRaisesRegex(ValueError, "AIC-123A -> FIC-101: .* runs through FI 101"):
                draw.generate(MODEL, write_layout(tmp, through), None, write=False)

    def test_a_diagonal_signal_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            def diagonal(layout):
                for s in layout["sheets"][1]["signals"]:
                    if (s["from"], s["to"]) == ("LIC-112", "LV-112"):
                        s["via"] = [[2000, 1300]]
            with self.assertRaisesRegex(ValueError, "is not horizontal or vertical"):
                draw.generate(MODEL, write_layout(tmp, diagonal), None, write=False)

    def test_regenerated_keys_match_the_committed_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            draw.generate(MODEL, LAYOUT, Path(tmp))
            self.assertEqual((Path(tmp) / "sheet_register.csv").read_bytes(),
                             (ROOT / "data" / "sheet_registers" / "te_generated.csv").read_bytes())
            for name in ("101.graphml", "102.graphml", "103.graphml"):
                self.assertEqual((Path(tmp) / name).read_bytes(), (COMMITTED / name).read_bytes(), name)
            k_new = json.loads((Path(tmp) / "key.json").read_text(encoding="utf-8"))
            k_old = json.loads((COMMITTED / "key.json").read_text(encoding="utf-8"))
            self.assertEqual(k_new["sheets"], k_old["sheets"])

    def test_the_line_tracer_independently_recovers_every_key_link(self):
        # The key's links come from the layout's line networks; the tracer only sees the pixels. They must agree,
        # or the key does not describe the drawing.
        for sheet in ("101", "102", "103"):
            w, h = sc.png_size(COMMITTED / f"{sheet}.png")
            nodes, adj = sc.load_key(COMMITTED / f"{sheet}.graphml", w, h)
            syms = [{"id": k, "class": v["class"], "box": v["box"]} for k, v in nodes.items() if v["class"] in sc.SCORED]
            key_links = {frozenset(x) for x in sc.asset_links(nodes, adj)}
            traced = {frozenset((c["from"], c["to"])) for c in tc.trace(COMMITTED / f"{sheet}.png", syms)}
            self.assertEqual(traced, key_links, sheet)


class RoundTripScorerTests(unittest.TestCase):
    def setUp(self):
        self.key = json.loads((COMMITTED / "key.json").read_text(encoding="utf-8"))

    def perfect(self, sheet):
        w, h = sc.png_size(COMMITTED / f"{sheet}.png")
        nodes, adj = sc.load_key(COMMITTED / f"{sheet}.graphml", w, h)
        syms = self.key["sheets"][sheet]["symbols"]
        return {"prediction": {
            "symbols": [{"id": k, "class": v["class"], "tag": syms[k]["text"], "box": v["box"]}
                        for k, v in nodes.items() if v["class"] in sc.SCORED],
            "connections": [{"from": a, "to": b} for a, b in map(tuple, sc.asset_links(nodes, adj))]}}

    def test_tag_normalization(self):
        self.assertEqual(rt.norm("FI-101"), rt.norm("fi 101"))
        self.assertEqual(rt.norm("FI\n101"), "FI101")
        self.assertNotEqual(rt.norm("FI-101"), rt.norm("FI-107"))

    def test_perfect_reader_scores_perfectly(self):
        s, tags, refs = rt.score_sheet("101", self.perfect("101"), self.key)
        self.assertEqual(s["review_load"]["corrections"], 0)
        self.assertTrue(tags and all(t["read"] for t in tags))
        self.assertTrue(refs and all(r["read"] for r in refs))

    def test_a_misread_tag_and_a_missing_symbol_both_count_against_tag_reading(self):
        rec = self.perfect("101")
        syms = rec["prediction"]["symbols"]
        misread = next(s for s in syms if s["tag"] == "FI 101")
        misread["tag"] = "FI 107"
        dropped = next(s for s in syms if s["tag"] == "PI 107")
        syms.remove(dropped)
        _, tags, _ = rt.score_sheet("101", rec, self.key)
        bad = {t["printed"]: t for t in tags if not t["read"]}
        self.assertEqual(set(bad), {"FI 101", "PI 107"})
        self.assertTrue(bad["FI 101"]["found"])
        self.assertFalse(bad["PI 107"]["found"])

    def test_missing_run_counts_as_zero_output(self):
        r = rt.run_scores("te-does-not-exist", "nobody", self.key)
        self.assertEqual(r["missing_sheets"], ["101", "102", "103"])
        self.assertEqual(r["tags_read"], 0.0)

    def test_interval_summary(self):
        s = rt.summarize([10.0, 12.0, 14.0])
        self.assertEqual((s["mean"], s["min"], s["max"]), (12.0, 10.0, 14.0))
        self.assertLess(s["ci95"][0], 10.0)
        self.assertGreater(s["ci95"][1], 14.0)


class DiffTests(unittest.TestCase):
    def twin(self):
        u = lambda i, tag, cls="tank": {"id": i, "tag": tag, "class": cls}  # noqa: E731
        t = {"units": [u("T1", "R-101"), u("T2", "E-101")],
                "line_items": [], "offpage_connectors": [], "offpage_pairs": [],
                "instruments": [{"id": "I1", "tag": "PI 107", "unit": "T1", "instrument_kind": "measurement / control",
                                 "variable": "pressure", "unit_method": "connection_path"},
                                {"id": "I2", "tag": "TI 109", "unit": "T2", "instrument_kind": "measurement / control",
                                 "variable": "temperature", "unit_method": "connection_path"},
                                {"id": "I3", "tag": "XI 999", "unit": "T1", "instrument_kind": "measurement / control",
                                 "variable": None, "unit_method": "connection_path"}],
                "streams": [{"from": "T1", "to": "T2"}]}
        for i in t["instruments"]:
            i["class"] = "instrumentation"
        return t

    def verified(self):
        return {"units": [{"id": "R-101", "name": "Reactor", "type": "reactor"},
                          {"id": "E-101", "name": "Condenser", "type": "condenser"}],
                "instruments": [{"tag": "PI-107", "unit": "R-101", "variable": "pressure", "description": "p"},
                                {"tag": "TI-109", "unit": "R-101", "variable": "temperature", "description": "t"},
                                {"tag": "LI-108", "unit": "R-101", "variable": "level", "description": "l"}],
                "final_elements": [], "streams": [{"from": "R-101", "to": "E-101"}]}

    def test_reviewer_corrections(self):
        d = tdiff.diff(self.twin(), self.verified())
        c = "\n".join(d["corrections"])
        self.assertIn("ADD LI-108", c)
        self.assertIn("SET unit of TI-109: E-101 -> R-101", c)
        self.assertIn("DELETE or explain I3 'XI 999'", c)
        self.assertNotIn("PI-107", c)
        self.assertEqual(d["topology"]["matched"], 1)

    def test_analysis_is_the_same_variable_as_composition(self):
        twin, ver = self.twin(), self.verified()
        twin["instruments"][0].update(tag="AI 123", variable="analysis")
        ver["instruments"][0].update(tag="AI-123", variable="composition")
        rows = {r["tag"]: r for r in tdiff.diff(twin, ver)["rows"]}
        self.assertEqual(rows["AI-123"]["status"], "ok")

    def test_diff_does_not_mutate_inputs(self):
        twin, ver = self.twin(), self.verified()
        t0, v0 = copy.deepcopy(twin), copy.deepcopy(ver)
        tdiff.diff(twin, ver)
        self.assertEqual((twin, ver), (t0, v0))


if __name__ == "__main__":
    unittest.main()
