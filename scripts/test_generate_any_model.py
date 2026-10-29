"""scripts/generate.py on a hand-built model that isn't Tennessee Eastman (the Bayer residue treater): it must export,
draw valves as valves, place units it has no positions for and say so, and write only where --out points.
Stdlib only."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import generate  # noqa: E402

BAYER = ROOT / "data" / "bayer_rt" / "process_model.json"


class AnyHandBuiltModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "exports"
        cls.result = subprocess.run([sys.executable, str(ROOT / "scripts" / "generate.py"), str(BAYER), "--out", str(cls.out)],
                                 capture_output=True, text=True, timeout=300)
        cls.model = json.loads(BAYER.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_it_exports_to_the_folder_given(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        for rel in ("ignition/tags.json", "pi/pi_builder_af.csv", "svg/overview.svg", "ops_review_sheet.csv"):
            self.assertTrue((self.out / rel).is_file(), rel)
        self.assertFalse((self.out / "ignition" / "te_tags.json").exists())

    def test_every_model_item_is_in_the_tag_export(self):
        tags = (self.out / "ignition" / "tags.json").read_text(encoding="utf-8")
        for item in self.model["instruments"] + self.model["final_elements"]:
            self.assertIn(item["tag"], tags)

    def test_valves_are_drawn_as_valves_and_rows_say_so(self):
        svg = (self.out / "svg" / "overview.svg").read_text(encoding="utf-8")
        for fe in self.model["final_elements"]:
            start = svg.index(f'data-tag="{fe["tag"]}"')
            self.assertIn("M-14 -8 L14 8", svg[start:start + 600], fe["tag"])  # the bowtie
        rows = (self.out / "ops_review_sheet.csv").read_text(encoding="utf-8-sig")
        self.assertEqual(rows.count("control valve / output"), len(self.model["final_elements"]))

    def test_auto_placement_is_disclosed_and_fits(self):
        svg = (self.out / "svg" / "overview.svg").read_text(encoding="utf-8")
        self.assertIn("Positions placed in flow order; links are logical, not pipe routes.", svg)
        placed = generate._auto_layout(generate._mark_finals(self.model))
        xs = [u["layout"]["x"] for u in placed["units"]]
        self.assertEqual(min(xs), 160)  # the main feed's unit starts the first column
        self.assertEqual(placed["units"][0]["layout"]["x"], 160)

    def test_pi_root_and_point_prefix_come_from_the_model(self):
        sheet = (self.out / "pi" / "pi_builder_af.csv").read_text(encoding="utf-8-sig")
        self.assertIn(self.model["meta"]["model_id"], sheet)
        self.assertNotIn("TE Plant", sheet)

    def test_a_valve_unit_is_blank_not_invented(self):
        marked = generate._mark_finals(self.model)
        self.assertTrue(all(fe["uom"] == "" for fe in marked["final_elements"] if "uom" not in
                            next(f for f in self.model["final_elements"] if f["tag"] == fe["tag"])))

    def test_the_te_model_keeps_its_hand_placed_layout(self):
        te = json.loads((ROOT / "data" / "te_process_model.json").read_text(encoding="utf-8"))
        self.assertIs(generate._auto_layout(te), te)


if __name__ == "__main__":
    unittest.main(verbosity=1)
