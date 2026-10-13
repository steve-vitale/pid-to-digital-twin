"""Offline PI Builder convention check: the reference file is self-consistent, the committed exports give the
recorded findings, and each error class fires on a planted fault (positive controls). No PI runtime needed."""
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import check_pi_export as cpe
import generate
from test_generate_validation import twin_fixture

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
        self.assertIn("subset", ref["uom_sample"]["note"])
        self.assertIn("not evidence", ref["status"])
        units = {(u["abbreviation"], u["class"]) for u in ref["uom_sample"]["units"]}
        self.assertIn(("°C", "Temperature"), units)
        self.assertIn(("%", "Ratio"), units)


class CommittedExportTests(unittest.TestCase):
    def test_te_seed_export_findings_are_the_recorded_ones(self):
        header, rows = cpe.read_csv_text(TE_CSV.read_text(encoding="utf-8"))
        report = cpe.check(header, rows)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["columns"]["AttributeValueType"], "not_documented")
        self.assertEqual(report["attribute_types"], {"Double": "documented"})
        status = {u: f["status"] for u, f in report["uoms"].items()}
        self.assertEqual(status, {"%": "in_vendor_sample", "kW": "in_vendor_sample", "m3/h": "in_vendor_sample",
                                  "degC": "spelling_differs", "kPa g": "not_in_vendor_sample",
                                  "kg/h": "not_in_vendor_sample", "kscmh": "not_in_vendor_sample",
                                  "mol%": "not_in_vendor_sample"})
        self.assertEqual(report["uoms"]["degC"]["vendor_abbreviation"], "°C")
        self.assertEqual(report["config_strings"], {"default_archive_substitution": 37})
        self.assertEqual(report["element_templates_referenced_not_defined"],
                         ["Compressor", "Condenser", "FeedHeader", "Reactor", "Separator", "Stripper"])

    def test_extracted_twin_export_is_all_placeholders_without_uoms(self):
        header, rows = cpe.read_csv_text(TWIN_CSV.read_text(encoding="utf-8"))
        report = cpe.check(header, rows)
        self.assertEqual(report["errors"], [])
        attributes = report["object_types"]["Attribute"]
        self.assertEqual(report["uoms"], {"": {"status": "none", "note": "no default UOM", "rows": attributes}})
        self.assertEqual(set(report["config_strings"]), {"placeholder"})

    def test_generated_candidate_uses_only_documented_headers_apart_from_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate.export_twin(twin_fixture(), tmp)
            header, rows = cpe.read_csv_text((Path(tmp) / "pi/pi_builder_UNVALIDATED_candidate_v1.csv")
                                             .read_text(encoding="utf-8"))
        report = cpe.check(header, rows)
        self.assertEqual(report["errors"], [])
        self.assertEqual({c for c, s in report["columns"].items() if s != "documented"}, {"Description"})


class PositiveControlTests(unittest.TestCase):
    def assertError(self, rows, fragment, header=None):
        report = cpe.check(*sheet(rows, header))
        self.assertTrue(any(fragment in e for e in report["errors"]), report["errors"])

    def test_clean_sheet_has_no_errors_or_uom_warnings(self):
        report = cpe.check(*sheet(GOOD))
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["uoms"]["m3/h"]["status"], "in_vendor_sample")

    def test_planted_faults_are_errors(self):
        self.assertError(GOOD + [GOOD[2]], "rows share Parent")
        self.assertError(GOOD + [["x", "Plant\\Missing", "T", "Attribute", "", "", "Double", "", "PI Point", "\\\\A\\B"]],
                         "is not an element in this file")
        self.assertError(GOOD + [["x", "Plant", "U2", "Element", "", "", "Double", "", "", ""]], "element row carries")
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


if __name__ == "__main__":
    unittest.main()
