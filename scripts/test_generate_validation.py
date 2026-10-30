"""Stdlib-only fail-before-write controls for seed and extracted-twin exports."""
import copy
import csv
import io
import json
import os
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
    def test_instance_units_survive_beside_review_status_without_changing_shared_template(self):
        model = twin_fixture()
        a = model["instruments"][0]
        a.update(uom="bar", instrument_kind="measurement / control", ops_review={"status": "corrected"})
        b = copy.deepcopy(a)
        b.update(id="I-2", uom="kg/h", ops_review={"status": "unverified"})
        b["provenance"][0]["symbol"] = "s4"
        model["instruments"].append(b)
        tags = generate.twin_ignition(model)
        found = {}
        def walk(node):
            if node.get("tagType") == "UdtInstance":
                found[node["parameters"]["AssetId"]["value"]] = node
            for child in node.get("tags", []):
                walk(child)
        walk(tags)
        for identity, unit in (("I-1", "bar"), ("I-2", "kg/h")):
            members = {x["name"]: x for x in found[identity]["tags"]}
            self.assertEqual(members["PV"]["engUnit"], unit)
        self.assertEqual(next(x for x in found["I-1"]["tags"] if x["name"] == "ReviewStatus")["value"], "corrected")
        self.assertEqual(found["I-1"]["typeId"], found["I-2"]["typeId"])
        shared = next(x for x in tags["tags"][0]["tags"] if x["name"] == found["I-1"]["typeId"])
        pv = next(x for x in shared["tags"] if x["name"] == "PV")
        self.assertNotIn("engUnit", pv)
        self.assertTrue(pv["readOnly"])

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
        # A unit with no name fails in the SVG renderer. (A missing verification no longer does: it now reads as
        # "unverified", the conservative default, so any hand-built model in the same schema can export.)
        model = copy.deepcopy(self.seed)
        del model["units"][0]["name"]
        self.assert_blocked(model, generate.export_seed, "name")
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

    def test_instrument_udts_are_templates_by_kind_and_carry_review_and_risk(self):
        """Extracted-twin instrument UDTs are keyed on instrument_kind (and Relief for marked relief devices), not
        on tag letters; instance documentation and PI descriptions carry review status and risk tier."""
        base = self.twin["instruments"][0]
        cases = [("I-1", "FIT", "measurement / control", None, "Instrument_Measurement"),
                 ("I-2", "MSBV", "valve (plant-coded tag)", None, "Instrument_Valve"),
                 ("I-3", "AORV", "operated valve", {"function": "relief device", "basis": "x"}, "Instrument_Relief"),
                 ("I-4", "FCV", "final element (valve)", None, "Instrument_ControlValve"),
                 ("I-5", "MOV", "operated valve", None, "Instrument_OperatedValve"),
                 ("I-6", None, None, None, "Instrument_Unknown")]
        insts = []
        for n, (ident, letters, kind, safety, _) in enumerate(cases):
            x = dict(copy.deepcopy(base), id=ident, isa_letters=letters, instrument_kind=kind,
                     tag=f"{letters or 'X'} {n}", tag_status="as_extracted")
            x["provenance"] = [dict(x["provenance"][0], symbol=f"i{n}")]
            if safety:
                x["safety"] = safety
                x["risk"] = {"risk_score": 0.01, "tier": "amber", "why": "w", "tier_before_floor": "green"}
            insts.append(x)
        insts[0]["risk"] = {"risk_score": 0.6, "tier": "red", "why": "w"}
        insts[0]["ops_review"] = {"status": "corrected"}
        self.twin["instruments"] = insts
        tags = generate.twin_ignition(self.twin)
        types = {t["name"] for t in tags["tags"][0]["tags"]}
        self.assertEqual({t for t in types if t.startswith("Instrument_")}, {c[4] for c in cases})
        found = {}

        def walk(node):
            for t in node.get("tags", []):
                if t["tagType"] == "UdtInstance":
                    found[t["parameters"]["AssetId"]["value"]] = t
                walk(t)
        walk(tags["tags"][1])
        for ident, *_, type_name in cases:
            self.assertEqual(found[ident]["typeId"], type_name, ident)
        self.assertTrue(found["I-1"]["documentation"].endswith("review: CORRECTED | risk tier: red"))
        self.assertTrue(found["I-3"]["documentation"].endswith(
            "review: UNVERIFIED | risk tier: amber (safety floor) | safety-relevant: relief device"))
        self.assertTrue(found["I-5"]["documentation"].endswith("review: UNVERIFIED | risk tier: not rated"))
        self.assertTrue(found["U-1"]["documentation"].endswith("review: UNVERIFIED | risk tier: not rated"))
        rows = generate.twin_pi_rows(self.twin)
        attr = next(r for r in rows if r[3] == "Attribute" and r[4].startswith("I-1 |"))
        self.assertTrue(attr[4].endswith("review: CORRECTED | risk tier: red"))
        queue = generate.twin_review_rows(self.twin)
        col = generate.TWIN_REVIEW_COLS.index("why_check_this")
        row = next(r for r in queue if r[generate.TWIN_REVIEW_COLS.index("item_id")] == "I-3")
        self.assertIn("safety-relevant relief device (x): check whatever the tier", row[col])

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


class SeedReviewRefreshTests(unittest.TestCase):
    """Fictional maintenance controls; no platform or plant acceptance."""

    def setUp(self):
        self.model = json.loads((ROOT / "data/te_process_model.json").read_text(encoding="utf-8"))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "output"

    def reject(self, section, identity):
        item = next(r for r in self.model[section] if (r.get("id") or r.get("tag")) == identity)
        item["ops_review"] = {"status": "rejected", "by": "Illustrative control", "on": "2026-10-30",
                              "history": [{"status": "unverified"}]}

    def export(self):
        original = copy.deepcopy(self.model)
        generate.export_seed(self.model, self.out)
        self.assertEqual(self.model, original)

    def blocked(self, message):
        before = snapshot(self.out)
        with self.assertRaisesRegex(generate.ModelValidationError, message):
            self.export()
        self.assertEqual(snapshot(self.out), before)

    def test_actual_review_generation_and_reconfirmation_cli_packet(self):
        path = ROOT / "examples/review-and-mapping/seed-refresh/demonstrate.py"
        p = subprocess.run([sys.executable, "-S", str(path)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_name_allocations_do_not_change_after_rejecting_competitors(self):
        self.model = {"meta": {"model_id": "illustrative-pumps", "title": "Invented pumps",
                               "source_document": "ILLUSTRATIVE test fixture"},
                      "units": [{"id": "P-1", "name": "First pump", "type": "pump", "layout": {"x": 150, "y": 150}},
                                {"id": "P-2", "name": "Second pump", "type": "pump", "layout": {"x": 550, "y": 150}}],
                      "streams": [], "final_elements": [],
                      "instruments": [{"tag": f"TT-{n}", "unit": "P-2", "uom": "degC", "variable": "temperature",
                                       "description": "A very long identical description before suffix " + str(n)}
                                      for n in (101, 102)]}
        types, names, _ = generate.seed_names(self.model)
        self.assertEqual(types["P-2"], "Pump_P2")
        self.assertTrue(names["TT-102"].endswith("_TT_102"))
        self.reject("units", "P-1")
        self.reject("instruments", "TT-101")
        tags = generate.ignition_tags(self.model)
        self.assertEqual(tags["tags"][1]["tags"][0]["typeId"], types["P-2"])
        self.assertEqual(tags["tags"][0]["tags"][0]["tags"][0]["name"], names["TT-102"])
        pi = generate.pi_af_rows(self.model)
        self.assertEqual(next(r[2] for r in pi if r[3] == "Attribute"), names["TT-102"])

    def test_all_units_rejected_retains_every_independently_eligible_signal(self):
        for u in self.model["units"]:
            self.reject("units", u["id"])
        self.export()
        tags = json.loads((self.out / "ignition/te_tags.json").read_text())
        self.assertEqual(tags["tags"][0]["tags"], [])
        container = tags["tags"][1]["tags"][0]
        self.assertEqual((container["name"], container["tagType"]), ("_Unassigned", "Folder"))
        self.assertEqual(len(container["tags"]), 37)
        self.assertTrue(all(isinstance(t["opcItemPath"], str) and t["readOnly"] for t in container["tags"]))
        self.assertEqual(len(list((self.out / "svg").glob("*.svg"))), 2)
        self.assertFalse(json.loads((self.out / "seed_review_projection.json").read_text())["relocated"][0]["owning_unit"])

    def test_two_rejected_owners_keep_distinct_source_addresses(self):
        self.reject("units", "U-100")
        self.reject("units", "R-101")
        self.export()
        projection = json.loads((self.out / "seed_review_projection.json").read_text())
        owners = {r["previous_declared_owner"] for r in projection["relocated"]}
        self.assertEqual(owners, {"U-100", "R-101"})
        for r in projection["relocated"]:
            self.assertEqual(r["opc_item_path_claim"], f"ns=1;s=TE.{r['previous_declared_owner']}.{r['tag']}")
            self.assertEqual(r["pi_point_claim"], f"\\\\%Server%\\TE.{r['tag']}.PV")

    def test_removed_source_unit_retires_only_its_managed_svg(self):
        self.export()
        (self.out / "my-notes.md").write_text("authored notes")
        self.model["units"] = [u for u in self.model["units"] if u["id"] != "U-100"]
        for sec in ("instruments", "final_elements"):
            self.model[sec] = [i for i in self.model[sec] if i["unit"] != "U-100"]
        self.model["streams"] = [s for s in self.model["streams"] if "U-100" not in (s["from"], s["to"])]
        remaining = {s["id"] for s in self.model["streams"]}
        for sec in ("instruments", "final_elements"):
            for item in self.model[sec]:
                if item.get("stream") and item["stream"] not in remaining:
                    item.pop("stream")  # Explicit fictional source revision, not inferred by the exporter.
        self.export()
        self.assertFalse((self.out / "svg/U-100.svg").exists())
        self.assertEqual(len(list((self.out / "svg").glob("*.svg"))), 6)
        self.assertEqual((self.out / "my-notes.md").read_text(), "authored notes")

    def test_missing_and_nonrejected_review_stays_eligible(self):
        baseline = generate.ignition_tags(self.model)
        for state in (None, {}, {"status": "unverified"}, {"status": "confirmed"}, {"status": "corrected"}):
            with self.subTest(state=state):
                self.model["units"][0]["ops_review"] = state
                current = generate.ignition_tags(self.model)
                self.assertEqual([n["name"] for n in current["tags"][1]["tags"]],
                                 [n["name"] for n in baseline["tags"][1]["tags"]])

    def test_malformed_seed_review_refuses_before_writing(self):
        self.export()
        for value in ([], "rejected", {"status": "reject"}, {"status": []}, {"by": 2}, {"notes": []}):
            with self.subTest(value=value):
                self.model["units"][0]["ops_review"] = value
                self.blocked("ops_review")

    def test_modified_stale_svg_is_not_deleted(self):
        self.export()
        self.reject("units", "U-100")
        (self.out / "svg/U-100.svg").write_text("manually authored annotation")
        self.blocked("differs from its inventory")

    def test_modified_existing_pi_file_is_not_overwritten(self):
        self.export()
        (self.out / "pi/pi_builder_af.csv").write_text("manually authored PI change")
        self.blocked("differs from its inventory")

    def test_foreign_svg_without_inventory_is_preserved_and_refused(self):
        self.out.mkdir()
        (self.out / "svg").mkdir()
        (self.out / "svg/author.svg").write_text("author's diagram")
        self.blocked("Unmanaged SVG")

    def test_inventory_rejects_escape_paths_or_other_model_identity(self):
        self.export()
        path = self.out / "seed_export_manifest.json"
        original = json.loads(path.read_text())
        for mutate in (lambda m: m.update(model_id="another-model"),
                       lambda m: m["files"].update({"../input.json": "0" * 64}),
                       lambda m: m["files"].update({"svg/../../input.svg": "0" * 64}),
                       lambda m: m["files"].update({"notes.md": "0" * 64})):
            value = copy.deepcopy(original)
            mutate(value)
            path.write_text(json.dumps(value))
            self.blocked("inventory")

    def test_matching_legacy_bundle_bootstraps_inventory(self):
        self.export()
        (self.out / "seed_export_manifest.json").unlink()
        (self.out / "seed_review_projection.json").unlink()
        before = snapshot(self.out)
        self.export()
        self.assertTrue(all(snapshot(self.out)[name] == data for name, data in before.items()))
        self.assertTrue((self.out / "seed_export_manifest.json").exists())

    def test_crlf_checkout_of_managed_text_can_refresh(self):
        self.export()
        for path in self.out.rglob("*"):
            if path.is_file():
                path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.reject("instruments", "FT-101")
        self.export()
        self.assertNotIn("FT-101 |", (self.out / "ignition/te_tags.json").read_text())

    def test_changed_legacy_bundle_needs_fresh_directory(self):
        self.export()
        (self.out / "seed_export_manifest.json").unlink()
        self.reject("units", "U-100")
        self.blocked("legacy baseline|Unmanaged")

    def test_unassigned_container_collision_refuses_before_changes(self):
        self.export()
        self.model["units"][1]["id"] = "_Unassigned"
        for sec in ("instruments", "final_elements"):
            for i in self.model[sec]:
                if i["unit"] == "R-101":
                    i["unit"] = "_Unassigned"
        for stream in self.model["streams"]:
            for field in ("from", "to"):
                if stream[field] == "R-101":
                    stream[field] = "_Unassigned"
        self.reject("units", "U-100")
        self.blocked("_Unassigned is reserved")

    def test_hardlinked_managed_artifact_or_inventory_refuses(self):
        self.export()
        for name in ("ignition/te_tags.json", "seed_export_manifest.json"):
            with self.subTest(name=name):
                backup = Path(self.tmp.name) / "unrelated-backup.json"
                os.link(self.out / name, backup)
                before = backup.read_bytes()
                self.reject("instruments", "FT-101")
                self.blocked("hard-linked")
                self.assertEqual(backup.read_bytes(), before)
                backup.unlink()

    def test_known_parent_file_conflict_refuses_before_any_output(self):
        self.out.mkdir()
        (self.out / "pi").write_text("an unrelated ordinary file")
        self.blocked("directory|inspect")

    def test_root_or_ancestor_directory_alias_refuses(self):
        # Actual Windows junction or POSIX directory symlink, with both ends inside the disposable workspace.
        self.export()
        for ancestor in (False, True):
            with self.subTest(ancestor=ancestor):
                link = Path(self.tmp.name) / ("ancestor-alias" if ancestor else "root-alias")
                if os.name == "nt":
                    p = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.out)],
                                       capture_output=True, text=True)
                    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                else:
                    os.symlink(self.out, link, target_is_directory=True)
                before = snapshot(self.out)
                target = link / "fresh-child" if ancestor else link
                with self.assertRaisesRegex(generate.ModelValidationError, "symlink|reparse"):
                    generate.export_seed(self.model, target)
                self.assertEqual(snapshot(self.out), before)

    def test_actual_cli_source_model_cannot_be_overwritten_by_inventory_or_report(self):
        self.export()
        for name in ("seed_review_projection.json", "seed_export_manifest.json"):
            with self.subTest(name=name):
                path = self.out / name
                old = path.read_bytes()
                value = {**self.model, **json.loads(old)}
                path.write_text(json.dumps(value))
                before = snapshot(self.out)
                p = subprocess.run([sys.executable, "-S", str(ROOT / "scripts/generate.py"), str(path),
                                    "--out", str(self.out)], capture_output=True, text=True)
                self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
                self.assertIn("Source model collides", p.stderr)
                self.assertEqual(snapshot(self.out), before)
                self.assertEqual(len(json.loads(path.read_text())["units"]), 6)
                path.write_bytes(old)

    def test_inventory_case_alias_cannot_retire_a_live_file(self):
        self.export()
        path = self.out / "seed_export_manifest.json"
        original = json.loads(path.read_text())
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                inventory = copy.deepcopy(original)
                inventory["files"]["svg/u-100.svg"] = inventory["files"]["svg/U-100.svg"]
                if not duplicate:
                    del inventory["files"]["svg/U-100.svg"]
                path.write_text(json.dumps(inventory))
                self.blocked("alias|same file")
                self.assertTrue((self.out / "svg/U-100.svg").exists())


if __name__ == "__main__":
    unittest.main()
