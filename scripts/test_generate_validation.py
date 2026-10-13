"""Stdlib-only fail-before-write controls for seed and extracted-twin exports."""
import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import generate

ROOT = Path(__file__).resolve().parents[1]


def twin_fixture():
    def asset(identity, cls, symbol):
        return {"id": identity, "tag": None, "tag_status": "missing", "class": cls,
                "confidence": None, "system": "SYS-0", "sheets": ["0"],
                "provenance": [{"sheet": "0", "symbol": symbol, "confidence": None,
                                "box_0_1000": [10, 20, 30, 40]}]}
    unit = asset("U-1", "tank", "s1")
    valve = dict(asset("V-1", "valve", "s2"), unit="U-1", unit_method="connection_path")
    instrument = dict(asset("I-1", "instrumentation", "s3"), unit=None, parent=None,
                      parent_method="no_candidate", isa_letters=None, variable=None, uom="")
    return {"meta": {"model_kind": "extracted_twin", "model_id": "fixture", "title": "Test twin"},
            "site": {"name": "Test site"},
            "systems": [{"id": "SYS-0", "sheet": "0", "name": "Test system"}],
            "units": [unit], "line_items": [valve], "instruments": [instrument],
            "offpage_connectors": [], "streams": []}


def snapshot(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


class GenerationValidationTests(unittest.TestCase):
    def setUp(self):
        self.seed = json.loads((ROOT / "data/te_process_model.json").read_text(encoding="utf-8"))
        self.twin = twin_fixture()

    def assert_blocked(self, model, exporter, expected):
        original = copy.deepcopy(model)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "exports"
            with self.assertRaisesRegex(generate.ModelValidationError, expected):
                exporter(model, output)
            self.assertFalse(output.exists(), "Invalid model created an output directory")
            exporter(self.seed if exporter is generate.export_seed else self.twin, output)
            stale = output / "svg" / "sheet_stale.svg"
            stale.write_text("preserve this previous export", encoding="utf-8")
            before = snapshot(output)
            with self.assertRaisesRegex(generate.ModelValidationError, expected):
                exporter(model, output)
            self.assertEqual(snapshot(output), before, "Invalid model changed existing exports")
            self.assertEqual(model, original, "Validation modified the source model")

    def test_seed_reference_and_identity_failures(self):
        for key, field, value, message in [
                ("instruments", "unit", "MISSING", "unknown unit"),
                ("instruments", "stream", "MISSING", "unknown stream"),
                ("streams", "from", "MISSING", "unknown endpoint"),
                ("units", "id", "../escape", "unsafe output filename"),
                ("units", "type", "unsupported", "unsupported symbol type"),
                ("units", "layout", {"x": float("inf"), "y": 2}, "finite x and y")]:
            with self.subTest(field=field):
                model = copy.deepcopy(self.seed)
                model[key][0][field] = value
                self.assert_blocked(model, generate.export_seed, message)
        for key in ("units", "streams", "instruments", "final_elements"):
            with self.subTest(duplicate=key):
                model = copy.deepcopy(self.seed)
                model[key].append(copy.deepcopy(model[key][0]))
                self.assert_blocked(model, generate.export_seed, "duplicate")

    def test_twin_reference_and_shape_failures(self):
        mutations = [
            (lambda m: m["instruments"][0].update(parent="MISSING"), "unknown parent"),
            (lambda m: m["instruments"][0].update(unit="V-1"), "unknown unit"),
            (lambda m: m["units"][0].update(system="MISSING"), "unknown system"),
            (lambda m: m["units"][0].update(provenance=[]), "provenance"),
            (lambda m: m["units"][0]["provenance"][0].update(box_0_1000=[1, 2, 0, 4]), "box_0_1000"),
            (lambda m: m["units"][0]["provenance"][0].update(sheet="missing"), "unknown sheet"),
            (lambda m: m["systems"][0].update(sheet="../escape"), "safe nonempty"),
            (lambda m: m["systems"][0].update(image_size_px=[0, 100]), "dimensions"),
            (lambda m: m["systems"].append(copy.deepcopy(m["systems"][0])), "duplicate"),
            (lambda m: m["systems"].append(dict(m["systems"][0], id="SYS-2")), "duplicate system sheet"),
            (lambda m: m["instruments"][0].update(id="U-1"), "duplicate asset"),
            (lambda m: m["streams"].append({"id": "L1", "from": "U-1", "to": "MISSING"}), "unknown endpoint"),
        ]
        for mutate, message in mutations:
            with self.subTest(message=message):
                model = copy.deepcopy(self.twin)
                mutate(model)
                self.assert_blocked(model, generate.export_twin, message)

    def test_render_errors_before_any_writes(self):
        # These fail in later renderers, after SVGs could already have been overwritten previously.
        model = copy.deepcopy(self.seed)
        del model["units"][0]["verification"]
        self.assert_blocked(model, generate.export_seed, "verification")
        model = copy.deepcopy(self.twin)
        del model["instruments"][0]["parent_method"]
        self.assert_blocked(model, generate.export_twin, "parent_method")

    def test_missing_and_malformed_containers(self):
        for exporter, model in ((generate.export_seed, self.seed), (generate.export_twin, self.twin)):
            for bad in (None, [], {}, dict(model, units=None), dict(model, instruments=[42])):
                with self.subTest(exporter=exporter.__name__, bad=type(bad).__name__):
                    self.assert_blocked(bad, exporter, "must be")

    def test_valid_modes_and_unknowns_remain_unchanged(self):
        for exporter, model, review in ((generate.export_seed, self.seed, "ops_review_sheet.csv"),
                                       (generate.export_twin, self.twin, "review_queue.csv")):
            with tempfile.TemporaryDirectory() as tmp:
                model["future_extension"] = {"unknown": None}
                before = copy.deepcopy(model)
                exporter(model, Path(tmp))
                self.assertEqual(model, before)
                self.assertTrue((Path(tmp) / review).read_bytes().startswith(b"\xef\xbb\xbf"))
                self.assertTrue(list((Path(tmp) / "svg").glob("*.svg")))
                if exporter is generate.export_twin:
                    rows = list(csv.DictReader(io.StringIO((Path(tmp) / "pi/pi_builder_af.csv").read_text(encoding="utf-8-sig"))))
                    pv = next(r for r in rows if r["ObjectType"] == "Attribute")
                    descriptions = list(csv.DictReader(io.StringIO((Path(tmp) / "pi/attribute_descriptions.csv")
                                                                   .read_text(encoding="utf-8-sig"))))
                    self.assertIn("unknown variable", descriptions[0]["description"])
                    self.assertEqual(pv["Description"], "")
                    self.assertIn("PLACEHOLDER", pv["AttributeConfigString"])
                    self.assertEqual(pv["Selected(x)"], "")
                    self.assertEqual(pv["AttributeDefaultUOM"], "")

    def test_valve_callouts_stay_metadata_only(self):
        self.twin["instruments"][0]["reviewed_valve_association"] = "V-1"
        with tempfile.TemporaryDirectory() as tmp:
            generate.export_twin(self.twin, tmp)
            tags = json.loads((Path(tmp) / "ignition/tags.json").read_text())
            callout = next(t for t in tags["tags"][0]["tags"] if t["name"] == "Callout_Valve")
            self.assertEqual([t["name"] for t in callout["tags"]], ["ReviewStatus"])
            rows = list(csv.DictReader((Path(tmp) / "pi/pi_builder_af.csv").read_text(encoding="utf-8-sig").splitlines()))
            pv = next(r for r in rows if r["ObjectType"] == "Attribute")
            self.assertEqual((pv["AttributeDataReference"], pv["AttributeConfigString"]), ("", ""))
            descriptions = (Path(tmp) / "pi/attribute_descriptions.csv").read_text(encoding="utf-8-sig")
            self.assertIn("function/signal unknown", descriptions)

    def test_cli_failure_is_nonzero_without_success_or_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "model.json"
            for content in ('{', '[]', json.dumps(dict(self.twin, units=None)),
                            json.dumps(dict(self.seed, units=None))):
                model.write_text(content, encoding="utf-8")
                result = subprocess.run([sys.executable, str(ROOT / "scripts/generate.py"), str(model)],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Generation failed", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("wrote", result.stdout)
                self.assertEqual(set(snapshot(Path(tmp))), {"model.json"})

    def test_main_success_for_both_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for model in (self.seed, self.twin):
                path = Path(tmp) / "model.json"
                path.write_text(json.dumps(model), encoding="utf-8")
                with patch.object(sys, "argv", ["generate.py", str(path)]), patch.object(generate, "OUT", Path(tmp) / "seed"):
                    self.assertEqual(generate.main(), 0)


if __name__ == "__main__":
    unittest.main()
