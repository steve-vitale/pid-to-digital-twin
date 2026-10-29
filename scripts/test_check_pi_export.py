"""Offline PI Builder convention check: the reference file is self-consistent, the committed exports give the
recorded findings, and each error class fires on a planted fault (positive controls). No PI runtime needed."""
import contextlib
import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

import check_pi_export as cpe
import generate

ROOT = Path(__file__).resolve().parents[1]
TE_CSV = ROOT / "out/pi/pi_builder_af.csv"
TWIN_CSV = ROOT / "out/twin/r2-tiles-trace/codex/pi/pi_builder_af.csv"


def sheet(rows, header=None):
    header = header or ["Selected(x)", "Parent", "Name", "ObjectType", "Description", "Template", "AttributeType",
                        "AttributeDefaultUOM", "AttributeDataReference", "AttributeConfigString"]
    stream = io.StringIO()
    csv.writer(stream, lineterminator="\n").writerows([header] + rows)
    return cpe.read_csv_text(stream.getvalue())


GOOD = [["x", "", "Plant", "Element", "", "", "", "", "", ""],
        ["x", "Plant", "U1", "Element", "", "", "", "", "", ""],
        ["x", "Plant\\U1", "Flow", "Attribute", "", "", "Double", "m3/h", "PI Point", "\\\\%Server%\\U1.FLOW.PV"]]


class ReferenceFileTests(unittest.TestCase):
    def test_every_citation_names_a_listed_source(self):
        ref = cpe.load_reference()
        keys = set(ref["sources"])
        cited = [e for v in ref["columns"].values() for e in v] + \
                [e for v in ref["attribute_types"].values() for e in v] + \
                [e for v in ref["object_types"].values() for e in v]
        for entry in cited:
            self.assertIn(entry.split()[0], keys, entry)
        self.assertEqual(ref["uom_sample"]["source"], "af_sdk_sample")

    def test_reference_records_the_header_mismatch_and_the_sample_limits(self):
        ref = cpe.load_reference()
        self.assertIn("AttributeType", ref["columns"])
        self.assertIn("AttributeValueType", ref["columns_not_documented"])
        self.assertIn("Description", ref["columns"])
        self.assertIn("AttributeDescription", ref["columns_unconfirmed"])
        self.assertIn("Int16", ref["attribute_types"])
        self.assertIn("subset", ref["uom_sample"]["note"])
        self.assertIn("not evidence", ref["status"])
        units = {(u["abbreviation"], u["class"]) for u in ref["uom_sample"]["units"]}
        self.assertIn(("°C", "Temperature"), units)
        self.assertIn(("%", "Ratio"), units)


class CommittedExportTests(unittest.TestCase):
    def test_te_seed_export_matches_the_documented_conventions(self):
        header, rows = cpe.read_csv_text(TE_CSV.read_text(encoding="utf-8"))
        report = cpe.check(header, rows, custom=cpe.read_custom_uoms(TE_CSV.with_name("custom_uoms.csv")))
        self.assertEqual(report["errors"], [])
        self.assertEqual({c: s for c, s in report["columns"].items() if s != "documented"}, {})
        self.assertNotIn("AttributeValueType", header)
        self.assertEqual(report["attribute_types"], {"Double": "documented"})
        status = {u: f["status"] for u, f in report["uoms"].items()}
        self.assertEqual(status, {"%": "in_vendor_sample", "kW": "in_vendor_sample", "m3/h": "in_vendor_sample",
                                  "°C": "in_vendor_sample", "kPa g": "custom_defined",
                                  "kg/h": "custom_defined", "kscmh": "custom_defined", "mol%": "custom_defined"})
        self.assertEqual(report["config_strings"], {"default_archive_substitution": 37})
        self.assertEqual(report["element_templates_referenced_not_defined"], [])
        self.assertEqual(report["object_types"]["ElementTemplate"], 6)
        self.assertIn("NOT import-tested", report["status"])
        # The only warning left is the instruction to create or map the custom units.
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("custom_uoms.csv", report["warnings"][0])

    def test_without_the_custom_unit_file_those_units_are_unknown_again(self):
        header, rows = cpe.read_csv_text(TE_CSV.read_text(encoding="utf-8"))
        report = cpe.check(header, rows)
        self.assertEqual({u for u, f in report["uoms"].items() if f["status"] == "not_in_vendor_sample"},
                         {"kPa g", "kg/h", "kscmh", "mol%"})

    def test_extracted_twin_export_is_placeholder_only_unit_less_and_unselected(self):
        header, rows = cpe.read_csv_text(TWIN_CSV.read_text(encoding="utf-8"))
        report = cpe.check(header, rows)
        self.assertEqual(report["errors"], [])
        attributes = report["object_types"]["Attribute"]
        self.assertEqual(report["uoms"], {"": {"status": "none", "note": "no default UOM", "rows": attributes}})
        self.assertEqual(set(report["config_strings"]), {"placeholder"})
        self.assertEqual(report["placeholder_rows_held_back"], report["config_strings"]["placeholder"])
        self.assertTrue(any("no default UOM" in w for w in report["warnings"]))
        self.assertTrue(any("will not publish" in w for w in report["warnings"]))

    def test_regenerated_exports_equal_the_committed_ones(self):
        def committed(path):  # a Windows checkout may have CRLF line endings
            return path.read_text(encoding="utf-8").replace("\r\n", "\n")
        model = json.loads((ROOT / "data/te_process_model.json").read_text(encoding="utf-8"))
        for name, text in generate.pi_bundle(generate.pi_af_rows(model)).items():
            self.assertEqual(text, committed(ROOT / "out" / name), name)
        twin = json.loads((TWIN_CSV.parent.parent / "plant_model.json").read_text(encoding="utf-8"))
        for name, text in generate.pi_bundle(generate.twin_pi_rows(twin)).items():
            self.assertEqual(text, committed(TWIN_CSV.parent.parent / name), name)


class PositiveControlTests(unittest.TestCase):
    def assertError(self, rows, fragment, header=None):
        report = cpe.check(*sheet(rows, header))
        self.assertTrue(any(fragment in e for e in report["errors"]), report["errors"])

    def test_placeholder_rows_must_not_be_selected(self):
        rows = GOOD + [["x", "Plant\\U1", "Spare", "Attribute", "", "", "Double", "", "PI Point",
                        "\\\\%Server%\\PLACEHOLDER.X.PV"]]
        self.assertError(rows, "placeholder PI point reference is selected")
        rows[-1][0] = ""
        self.assertEqual(cpe.check(*sheet(rows))["errors"], [])

    def test_element_templates_have_no_parent_and_come_first(self):
        template = ["x", "", "Unit", "ElementTemplate", "", "", "", "", "", ""]
        self.assertError(GOOD + [["x", "Plant", "Unit", "ElementTemplate", "", "", "", "", "", ""]], "empty Parent")
        late = [GOOD[0], ["x", "Plant", "U2", "Element", "", "Unit", "", "", "", ""], template]
        report = cpe.check(*sheet(late))
        self.assertTrue(any("defined after" in w for w in report["warnings"]))
        report = cpe.check(*sheet([template] + late[:2]))
        self.assertFalse(any("defined after" in w for w in report["warnings"]))
        self.assertEqual(report["element_templates_referenced_not_defined"], [])

    def test_attribute_description_in_the_sheet_is_flagged(self):
        rows = GOOD[:2] + [["x", "Plant\\U1", "Flow", "Attribute", "a description", "", "Double", "m3/h",
                             "PI Point", "\\\\A\\B"]]
        self.assertTrue(any("attribute description" in w for w in cpe.check(*sheet(rows))["warnings"]))

    def test_clean_sheet_has_no_errors_or_uom_warnings(self):
        report = cpe.check(*sheet(GOOD))
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["uoms"]["m3/h"]["status"], "in_vendor_sample")

    def test_planted_faults_are_errors(self):
        self.assertError(GOOD + [GOOD[2]], "rows share Parent")
        self.assertError(GOOD + [["x", "Plant\\Missing", "T", "Attribute", "", "", "Double", "", "PI Point", "\\\\A\\B"]],
                         "is not an element in this file")
        self.assertError(GOOD + [["x", "Plant", "U2", "Element", "", "", "Double", "", "", ""]], "Element row carries")
        self.assertError(GOOD + [["x", "Plant\\U1", "T", "Attribute", "", "", "Double", "", "PI Point", ""]],
                         "no config string")
        self.assertError(GOOD + [["x", "Plant", "U3", "Asset", "", "", "", "", "", ""]], "ObjectType 'Asset'")
        self.assertError(GOOD, "required column ObjectType missing",
                         header=["Selected(x)", "Parent", "Name", "Type", "Description", "Template", "AttributeType",
                                 "AttributeDefaultUOM", "AttributeDataReference", "AttributeConfigString"])

    def test_unevidenced_types_and_units_are_warnings_not_silence(self):
        rows = GOOD + [["x", "Plant\\U1", "Count", "Attribute", "", "", "Int32", "widgets", "PI Point", "\\\\A\\B"]]
        report = cpe.check(*sheet(rows))
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["attribute_types"]["Int32"].startswith("repo_allowlist_only"))
        self.assertEqual(report["uoms"]["widgets"]["status"], "not_in_vendor_sample")
        self.assertTrue(any("'widgets'" in w for w in report["warnings"]))

    def test_an_unknown_unit_is_called_unrecognised_in_plain_words(self):
        # Kept a warning: the vendor UOM list here is a sample of AF's default database, so absence is not proof.
        rows = GOOD + [["x", "Plant\\U1", "Length", "Attribute", "", "", "Double", "furlongs", "PI Point", "\\\\A\\B"]]
        report = cpe.check(*sheet(rows))
        self.assertEqual(report["errors"], [])
        warning = next(w for w in report["warnings"] if "'furlongs'" in w)
        self.assertIn("not recognised", warning)
        self.assertNotIn("not_in_vendor_sample", warning)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sheet.csv"
            stream = io.StringIO()
            csv.writer(stream, lineterminator="\n").writerows(
                [["Selected(x)", "Parent", "Name", "ObjectType", "Description", "Template", "AttributeType",
                  "AttributeDefaultUOM", "AttributeDataReference", "AttributeConfigString"]] + rows)
            path.write_text(stream.getvalue(), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(cpe.main([str(path)]), 0)
        self.assertIn("not recognised", out.getvalue())
        self.assertIn("no errors, 1 warning to review", out.getvalue())


class ImportTagsRefusals(unittest.TestCase):
    """scripts/ignition/import_tags.py: a bad file is refused before any gateway is contacted."""

    def run_import(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("IGNITION_")}
        env["IGNITION_URL"] = "https://127.0.0.1:9"   # nothing listens; the refusal must come first
        env["IGNITION_API_TOKEN"] = "unused:unused"
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "ignition" / "import_tags.py"), *args],
                              capture_output=True, text=True, timeout=60, env=env)

    def test_missing_file_is_refused_with_a_message(self):
        r = self.run_import("no/such/provider.json", "--provider", "Twin")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("refused:", r.stderr)
        self.assertIn("provider.json", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_a_file_that_is_not_json_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "tags.json"
            bad.write_text("not json", encoding="utf-8")
            r = self.run_import(str(bad))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("not valid JSON", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
