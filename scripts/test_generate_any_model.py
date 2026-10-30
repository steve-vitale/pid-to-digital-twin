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

    def test_project_aliases_and_multiple_hyphens_preserve_export_identity(self):
        model = {'meta': {'model_id': 'identifier-case', 'title': 'Identifier regression',
                          'source_document': 'authored regression fixture'},
                 'units': [{'id': 'P1', 'name': 'Illustrative pump', 'type': 'pump'}],
                 'streams': [{'id': 'S1', 'name': 'In', 'from': 'BL', 'to': 'P1'},
                             {'id': 'S2', 'name': 'Out', 'from': 'P1', 'to': 'BL'}],
                 'instruments': [{'tag': 'LI_HYPO', 'unit': 'P1', 'variable': 'level',
                                  'uom': '', 'description': 'Level indication', 'source': 'fixture'}],
                 'final_elements': [{'tag': 'FV-AREA-101', 'unit': 'P1', 'stream': 'S2',
                                     'uom': '', 'description': 'Discharge valve', 'source': 'fixture'}]}
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / 'model.json'
            path.write_text(json.dumps(model), encoding='utf-8')
            before = path.read_bytes()
            out = folder / 'out'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/generate.py'), str(path),
                                     '--out', str(out)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.read_bytes(), before)
            tree = ET.parse(out / 'svg/P1.svg')
            for tag in ('LI_HYPO', 'FV-AREA-101'):
                groups = [n for n in tree.iter() if n.get('data-tag') == tag]
                self.assertEqual(len(groups), 1, tag)
                self.assertEqual(groups[0].get('id'), tag)
                self.assertIn(tag, ''.join(groups[0].itertext()))
                self.assertIn(tag, (out / 'ignition/tags.json').read_text(encoding='utf-8'))
                self.assertIn(tag, (out / 'pi/pi_builder_af.csv').read_text(encoding='utf-8'))
            alias = next(n for n in tree.iter() if n.get('data-tag') == 'LI_HYPO')
            self.assertFalse(any(n.tag.endswith('line') and n.get('x1') == '-17'
                                 and n.get('y1') == '0' for n in alias.iter()))

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


def two_temperatures(tag_a="TI-101", tag_b="TI-102"):
    """Two instruments whose descriptions share their first 40 name characters (member names are cut at 40)."""
    return {"meta": {"model_id": "member-names", "title": "Member name collision"},
            "units": [{"id": "RT-1", "name": "Residue treater", "type": "pressure_vessel"}],
            "streams": [{"id": "S1", "from": "BL", "to": "RT-1"}],
            "instruments": [
                {"tag": tag_a, "unit": "RT-1", "variable": "temperature", "uom": "degC", "source": "test",
                 "description": "Residue treater temperature measured at the upper nozzle location A"},
                {"tag": tag_b, "unit": "RT-1", "variable": "temperature", "uom": "degC", "source": "test",
                 "description": "Residue treater temperature measured at the upper nozzle location B"}],
            "final_elements": []}


class FieldMessages(unittest.TestCase):
    def test_a_missing_field_is_named_with_its_item(self):
        for mutate, expected in ((lambda m: m["units"][0].pop("name"), "unit RT-1: missing name"),
                                 (lambda m: m["instruments"][0].pop("description"), "TI-101: missing description"),
                                 (lambda m: m["instruments"][1].pop("uom"), "TI-102: missing uom")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                model = two_temperatures()
                mutate(model)
                path = Path(tmp) / "model.json"
                path.write_text(json.dumps(model), encoding="utf-8")
                r = subprocess.run([sys.executable, str(ROOT / "scripts" / "generate.py"), str(path), "--out",
                                    str(Path(tmp) / "out")], capture_output=True, text=True, timeout=120)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(expected, r.stderr)
                self.assertNotIn("KeyError", r.stderr)


class DrawRefusals(unittest.TestCase):
    """scripts/draw_pid_from_model.py: bad inputs are refused with a message, never a traceback."""

    def draw(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "draw_pid_from_model.py"), "--check", *args],
                              capture_output=True, text=True, timeout=300)

    def test_missing_files_are_refused(self):
        for flag in ("--model", "--layout"):
            with self.subTest(flag=flag):
                r = self.draw(flag, "no/such/file.json")
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("refused:", r.stderr)
                self.assertIn("file.json", r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_drawing_another_model_never_overwrites_the_te_register(self):
        te_register = ROOT / "data" / "sheet_registers" / "te_generated.csv"
        before = te_register.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "draw_pid_from_model.py"),
                                "--model", "data/bayer_rt/process_model.json", "--layout", "data/bayer_rt/pid_layout.json",
                                "--out", tmp], capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(tmp) / "sheet_register.csv").exists())  # the register goes with the drawing
        self.assertEqual(te_register.read_bytes(), before)  # the old default wrote Bayer rows into the TE register

    def test_an_empty_description_is_refused(self):
        model = json.loads(BAYER.read_text(encoding="utf-8"))
        model["instruments"][0]["description"] = " -- "
        problems = generate.validate(model)
        self.assertTrue(any("no letters or digits" in p for p in problems), problems)

    def test_a_unit_with_no_name_is_refused_by_field(self):
        model = json.loads((ROOT / "data" / "te_process_model.json").read_text(encoding="utf-8"))
        del model["units"][0]["name"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.json"
            path.write_text(json.dumps(model), encoding="utf-8")
            r = self.draw("--model", str(path))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("refused:", r.stderr)
        self.assertIn(f"unit {model['units'][0]['id']}: missing name", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class MemberNames(unittest.TestCase):
    """A UDT (Ignition) or AF element (PI) cannot hold two members with one name: the second would overwrite or
    fail on import while structural validation said OK."""

    def test_shared_40_char_prefix_gets_distinct_member_names(self):
        model = generate._auto_layout(generate._mark_finals(two_temperatures()))
        self.assertEqual(generate.validate(model), [])
        udt = generate.ignition_tags(model)["tags"][0]["tags"][0]
        names = [m["name"] for m in udt["tags"]]
        self.assertEqual(len(set(names)), 2, names)
        self.assertTrue(all("TI_101" in n or "TI_102" in n for n in names), names)
        attrs = [r[2] for r in generate.pi_af_rows(model) if r[3] == "Attribute"]
        self.assertEqual(attrs, names)   # PI attribute names match the Ignition member names

    def test_names_without_a_collision_are_unchanged(self):
        model = generate._auto_layout(generate._mark_finals(two_temperatures()))
        model["instruments"][1]["description"] = "Residue treater pressure"
        names = [m["name"] for m in generate.ignition_tags(model)["tags"][0]["tags"][0]["tags"]]
        self.assertEqual(names, [generate.member_name(i["description"]) for i in model["instruments"]])

    def test_validation_refuses_member_names_that_still_collide(self):
        # Tags that differ only in punctuation give the same suffix: the backstop must refuse, not print OK.
        model = generate._auto_layout(generate._mark_finals(two_temperatures("TI-101", "TI.101")))
        problems = generate.validate(model)
        self.assertTrue(any("duplicate member name" in p and "RT-1" in p for p in problems), problems)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.json"
            path.write_text(json.dumps(two_temperatures("TI-101", "TI.101")), encoding="utf-8")
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "generate.py"), str(path), "--out",
                                str(Path(tmp) / "out")], capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("duplicate member name", r.stderr)
            self.assertNotIn("structural validation: OK", r.stdout)
            self.assertFalse((Path(tmp) / "out").exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)
