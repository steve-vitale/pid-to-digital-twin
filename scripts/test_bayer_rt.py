"""Bayer CropScience residue treater: the sourced process model and the digitized Figure 11 (committed files only).
python scripts/test_bayer_rt.py

Stdlib only; no network, no PDF. The digitizer itself (scripts/digitize_bayer_fig11.py) needs the report and
PyMuPDF; these tests guard what it committed and what the model claims.
"""
import csv
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import digitize_bayer_fig11 as dg  # noqa: E402  (stdlib at import; PyMuPDF only inside figure_pixels)

ROOT = Path(__file__).resolve().parent.parent
MODEL = json.loads((ROOT / "data" / "bayer_rt" / "process_model.json").read_text(encoding="utf-8"))
CAL = json.loads(dg.CAL.read_text(encoding="utf-8"))


class ProcessModel(unittest.TestCase):
    def items(self):
        for key in ("units", "streams", "instruments", "final_elements", "manual_valves", "relief_devices",
                    "controllers", "interlocks", "limits", "events_2008_08_28"):
            for it in MODEL[key]:
                yield key, it

    def test_every_item_cites_the_report(self):
        missing = [(k, it.get("tag") or it.get("id") or it.get("what")) for k, it in self.items() if not it.get("source")]
        self.assertEqual(missing, [])

    def test_every_tag_is_marked_assigned(self):
        # The report gives no tag numbers for the residue treater; nothing may pass as the plant's own numbering.
        for key in ("units", "instruments", "final_elements", "manual_valves", "relief_devices"):
            for it in MODEL[key]:
                self.assertIs(it.get("assigned_tag"), True, it.get("tag") or it.get("id"))

    def test_tags_are_unique(self):
        tags = [it["tag"] for k in ("instruments", "final_elements", "manual_valves", "relief_devices", "controllers")
                for it in MODEL[k]]
        self.assertEqual(len(tags), len(set(tags)))

    def test_controllers_and_interlocks_name_real_items(self):
        known = {it["tag"] for k in ("instruments", "final_elements") for it in MODEL[k]}
        for c in MODEL["controllers"]:
            self.assertIn(c["measurement"], known)
            outs = c["output"].get("split_range") or [c["output"]["final_element"]]
            self.assertTrue(set(outs) <= known, c["tag"])
        for il in MODEL["interlocks"]:
            self.assertTrue(any(t in il["cause"] for t in known), il["id"])
            self.assertIn("FV-107", il["effect"])

    def test_streams_join_real_units(self):
        units = {u["id"] for u in MODEL["units"]} | {"BL"}
        for s in MODEL["streams"]:
            self.assertIn(s["from"], units, s["id"])
            self.assertIn(s["to"], units, s["id"])

    def test_figure11_series_each_have_one_instrument(self):
        series = [i["fig11_series"] for i in MODEL["instruments"] if i.get("fig11_series")]
        self.assertEqual(sorted(series), sorted(CAL["series"]))


class Digitized(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = dg.load_rows()

    def test_time_axis_reproduces_the_failure_line(self):
        t, s_per_px = dg.time_of(CAL["failure_line_x"], CAL)
        target = datetime.fromisoformat(f"{CAL['date']}T22:33:00")
        self.assertLess(abs((t - target).total_seconds()), 60)
        self.assertAlmostEqual(s_per_px, 31.66, delta=0.2)

    def test_rows_cover_the_plot_in_order(self):
        x0, x1 = CAL["plot_frame_x"]
        self.assertEqual(len(self.rows), x1 - x0 - 1)
        times = [r["time"] for r in self.rows]
        self.assertEqual(times, sorted(times))

    def test_values_stay_on_their_axes(self):
        for r in self.rows:
            for name, top in (("temperature_C", 160), ("level_pct", 160), ("recirc_flow_klbh", 160),
                              ("pressure_psig", 60)):
                if r[name] != "":
                    self.assertTrue(-1 <= float(r[name]) <= top + 1, (r["time"], name, r[name]))

    def test_check_report_records_every_disagreement(self):
        text = (ROOT / "out" / "bayer_rt" / "fig11_check.md").read_text(encoding="utf-8")
        failed = [ln.split("|")[1].strip() for ln in text.splitlines() if ln.endswith("| FAIL |")]
        self.assertIn("**8 of 11 checks pass.**", text)
        for name in failed:
            self.assertIn(f"- **{name}.**", text)   # every failed check is explained, none tuned away
        self.assertNotIn("No explanation recorded yet", text)


class TraceIntegrity(unittest.TestCase):
    """No series may jump away and straight back in one column: that is stray pixels (text fringes), not process."""

    def test_no_single_column_spikes_before_the_failure(self):
        rows = [r for r in dg.load_rows() if r["time"] <= "22:33:00"]
        for name in CAL["series"]:
            v = [float(r[name]) for r in rows if r[name] != ""]
            spikes = [i for i in range(1, len(v) - 1)
                      if abs(v[i] - v[i - 1]) > 8 and abs(v[i] - v[i + 1]) > 8 and abs(v[i - 1] - v[i + 1]) < 8]
            self.assertEqual(spikes, [], name)


class Replay(unittest.TestCase):
    """The trend run through the cited interlock and limit rules, and checked against the report's statements."""

    @classmethod
    def setUpClass(cls):
        import bayer_replay as br
        cls.br = br
        cls.rules = json.loads(br.RULES.read_text(encoding="utf-8"))
        cls.rows = br.derive(cls.rules)

    def test_committed_outputs_are_current(self):
        res = self.br.summarize(self.rules, self.rows)
        self.assertEqual((ROOT / "out" / "bayer_rt" / "replay_states.md").read_text(encoding="utf-8"),
                         self.br.render(self.rules, res))
        self.assertEqual(self.br.REPLAY.read_text(encoding="utf-8"), self.br.write_csv(self.rules, self.rows))

    def test_agrees_with_every_report_statement(self):
        res = self.br.summarize(self.rules, self.rows)
        self.assertEqual([c["id"] for c in res["checks"] if not c["ok"]], [])

    def test_stops_at_the_failure(self):
        self.assertLessEqual(self.rows[-1]["time"], "22:33:00")

    def test_a_straddling_bound_is_never_called(self):
        il1 = next(il for il in self.rules["interlocks"] if il["id"] == "IL-1")
        row = {"TI-104_lo": 129.0, "TI-104_hi": 131.0}
        self.assertEqual(self.br.interlock_state(il1, row), self.br.UNSURE)
        row = {"TI-104_lo": 131.0, "TI-104_hi": 134.0}      # inside the gap where the setpoint lies
        self.assertEqual(self.br.interlock_state(il1, row), self.br.UNSURE)

    def test_every_rule_cites_the_report(self):
        for il in self.rules["interlocks"]:
            self.assertRegex(il["why_these_bounds"], r"p\. \d+")
            self.assertIs(il["setpoint_published"], False)
        for lim in self.rules["limits"]:
            self.assertRegex(lim["source"], r"p\. \d+")

    def test_catches_a_flow_loss_at_the_wrong_time(self):
        rows = json.loads(json.dumps(self.rows))
        for r in rows:                                   # pretend the flow held until 22:30
            if "22:21:00" <= r["time"] < "22:30:00":
                r["IL-3"] = self.br.CLEAR
        k2 = next(s for s in self.rules["report_statements"] if s["id"] == "K2")
        self.assertFalse(self.br.check(k2, rows)["ok"])


class Walkthrough(unittest.TestCase):
    """The report's timed events beside the replayed screen: every check placed once, every state change accounted."""

    @classmethod
    def setUpClass(cls):
        import bayer_walkthrough as bw
        cls.bw = bw
        cls.w, cls.fig11, cls.kchecks, cls.events = bw.build()

    def test_committed_outputs_are_current(self):
        self.assertEqual(json.loads(self.bw.OUT_JSON.read_text(encoding="utf-8")), json.loads(json.dumps(self.w)))
        self.assertEqual(self.bw.OUT_MD.read_text(encoding="utf-8"), self.bw.render(self.w))

    def test_fig11_json_matches_its_markdown(self):
        md = (ROOT / "out" / "bayer_rt" / "fig11_check.md").read_text(encoding="utf-8")
        for name, c in self.fig11.items():
            self.assertIn(f"| {name} | {c['source']} | {c['stated']} | {c['digitized']} |", md)

    def test_every_check_and_event_placed_exactly_once(self):
        self.assertEqual(self.bw.problems(self.w, self.fig11, self.kchecks, self.events), [])

    def test_disagreements_are_exactly_the_failed_checks(self):
        failed = sorted([n for n, c in self.fig11.items() if not c["ok"]] +
                        [k for k, c in self.kchecks.items() if not c["ok"]])
        self.assertEqual(sorted(d["id"] for d in self.w["disagreements"]), failed)
        self.assertTrue(all(d["note"] for d in self.w["disagreements"]), "every disagreement carries its explanation")

    def test_every_state_change_is_listed(self):
        states = json.loads(self.bw.STATES.read_text(encoding="utf-8"))
        n = sum(1 for g in ("interlocks", "limits") for runs in states[g].values()
                for a, _ in zip(runs, runs[1:]) if a["state"] != "no reading")
        self.assertEqual(len(self.w["unstated_changes"]), n)
        self.assertEqual(self.w["counts"]["state_changes_tested"], 3)   # K1, K2, K3 land on a change

    def test_planted_unplaced_check_is_caught(self):
        w = json.loads(json.dumps(self.w))
        w["steps"][0]["checks"] = w["steps"][0]["checks"][1:]
        self.assertTrue(any("placed under 0" in p for p in self.bw.problems(w, self.fig11, self.kchecks, self.events)))

    def test_planted_far_screen_time_is_caught(self):
        w = json.loads(json.dumps(self.w))
        w["steps"][1]["seconds_from_event"] = 300
        self.assertTrue(any("over a minute" in p for p in self.bw.problems(w, self.fig11, self.kchecks, self.events)))


class Figure10(unittest.TestCase):
    """The model and the generated drawing against the report's own drawing, and that the check can fail."""

    @classmethod
    def setUpClass(cls):
        import compare_bayer_fig10 as cf
        cls.cf = cf
        cls.fig = json.loads(cf.FIG.read_text(encoding="utf-8"))
        cls.key = json.loads((ROOT / "data" / "bayer_rt" / "pid" / "key.json").read_text(encoding="utf-8"))

    def model(self):
        return json.loads(json.dumps(MODEL))

    def test_committed_comparison_is_current(self):
        res = self.cf.compare(self.fig, MODEL)
        res["drawing"] = self.cf.compare_drawing(self.fig, MODEL, self.key)
        self.assertEqual((ROOT / "out" / "bayer_rt" / "fig10_compare.md").read_text(encoding="utf-8"),
                         self.cf.render(res))

    def test_model_differs_only_by_the_unexplained_nozzle(self):
        res = self.cf.compare(self.fig, MODEL)
        self.assertEqual((res["passed"], res["total"]), (20, 21))
        self.assertEqual(len(res["differences"]), 1)
        self.assertIn("nozzle", res["differences"][0])

    def test_every_figure_line_is_drawn(self):
        res = self.cf.compare_drawing(self.fig, MODEL, self.key)
        self.assertEqual((res["passed"], res["total"]), (15, 15), res["differences"])

    def test_catches_a_transmitter_on_the_wrong_line(self):
        m = self.model()
        next(i for i in m["instruments"] if i["tag"] == "FI-103")["stream"] = "S3"   # the first, wrong reading
        diffs = " ".join(self.cf.compare(self.fig, m)["differences"])
        self.assertIn("Line L3 / S3", diffs)
        self.assertIn("Line L6 / S10", diffs)

    def test_catches_a_branch_taken_from_the_wrong_place(self):
        m = self.model()
        s6 = next(s for s in m["streams"] if s["id"] == "S6")
        s6.pop("branches_from")
        s6["from"] = "RT-1"
        self.assertTrue(any(d.startswith("Line L7:") for d in self.cf.compare(self.fig, m)["differences"]))

    def test_catches_a_cut_line_in_the_drawing(self):
        k = json.loads(json.dumps(self.key))
        sh = k["sheets"]["RT1"]
        psv = next(n for n, v in sh["symbols"].items() if v.get("model_ref") == "PSV-101" and v["class"] == "valve")
        sh["edges"] = [e for e in sh["edges"] if psv not in e]
        res = self.cf.compare_drawing(self.fig, MODEL, k)
        self.assertIn("Line L10: no drawn line joins residue_treater and vent_header.", res["differences"])

    def test_catches_a_wrong_valve_type_in_the_drawing(self):
        k = json.loads(json.dumps(self.key))
        lv = next(v for v in k["sheets"]["RT1"]["symbols"].values()
                  if v.get("model_ref") == "LV-102" and v["class"] == "valve")
        lv["model_kind"] = "manual_valve"
        res = self.cf.compare_drawing(self.fig, MODEL, k)
        self.assertTrue(any(d.startswith("Line L7:") for d in res["differences"]))

    def test_interlocks_name_their_measurement_and_valve(self):
        known = {it["tag"] for k in ("instruments", "final_elements") for it in MODEL[k]}
        for il in MODEL["interlocks"]:
            self.assertIn(il["measurement"], known)
            self.assertIn(il["measurement"], il["cause"])
            self.assertEqual(il["final_element"], "FV-107")


if __name__ == "__main__":
    unittest.main()
