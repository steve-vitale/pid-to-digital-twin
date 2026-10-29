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


if __name__ == "__main__":
    unittest.main()
