"""Ordered drawing evidence survives graph export, statement review and snapshot/context access without implying truth."""
import copy
import csv
import io
import json
import tempfile
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import context_register as context
import graph_export as gx
import serve_snapshot as snapshot
import statements as stm


def appearances():
    first = {"sheet": "2", "box_0_1000": [10, 20, 40, 60], "tag_as_extracted": "P-1",
             "symbol": "s1", "tool": "illustrative", "extra": {"status": "draft", "context": ["keep"]}}
    return [first, {"sheet": "3", "box_0_1000": [110, 120, 140, 160], "tag_as_extracted": "P-1"},
            copy.deepcopy(first), {}]


def model():
    return {"meta": {"model_id": "test", "title": "Illustrative evidence controls", "source_document": "test"},
            "units": [{"id": "P-1", "provenance": appearances()}], "streams": []}


def graph(value=None):
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "model.json"
        path.write_text(json.dumps(model() if value is None else value), encoding="utf-8")
        return gx.build(path)


class Provenance(unittest.TestCase):
    def test_public_source_regression_packet_runs_offline(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, '-S',
            str(root / 'examples/graph-export/multi-appearance/check_packet.py')], cwd=root,
            capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('3 ordered appearances', result.stdout)
    def test_empty_attribute_node_retains_order_duplicates_unknown_fields_and_absent_locators(self):
        value = model()
        node = gx.node("P-1", "equipment", value["units"][0], "test")
        self.assertEqual(node["attributes"], [])
        self.assertEqual(node["provenance"], appearances())
        self.assertEqual(node["source"]["sheet"], "2")
        node["provenance"][0]["extra"]["context"].append("changed")
        self.assertEqual(value["units"][0]["provenance"], appearances())

    def test_sources_overrides_and_review_remain_separate_from_original_appearances(self):
        item = model()["units"][0]
        item.update({"source": "original drawing index", "sources": ["vendor register"], "class": "pump",
                     "spec": {"value": 2, "source": "datasheet p. 4"},
                     "ops_review": {"status": "corrected", "history": [
                         {"by": "Fictional reviewer", "on": "2026-10-30", "changes": {"class": ["tank", "pump"]}}]}})
        node = gx.node("P-1", "equipment", item, "test")
        attrs = {a["name"]: a for a in node["attributes"]}
        self.assertEqual(attrs["class"]["source"]["kind"], "review")
        self.assertEqual(attrs["spec.value"]["source"]["document"], "datasheet p. 4")
        self.assertEqual(node["source"]["kind"], "drawing")
        self.assertEqual(node["citations"], {k: item[k] for k in ("source", "sources")})
        statements, _, _ = stm.build({"nodes": [node], "edges": []})
        identity = next(s for s in statements if s["predicate"] == "kind")
        reviewed = next(s for s in statements if s["predicate"] != "kind" and s["source_kind"] == "review")
        self.assertEqual(identity["source"]["kind"], "drawing")
        self.assertEqual(reviewed["source_kind"], "review")
        self.assertEqual(reviewed["item_evidence"]["provenance"], appearances())
        self.assertIn("not per-claim verification", reviewed["source_pointer"])

    def test_full_and_core_preserve_node_and_edge_appearance_records_without_new_claims(self):
        value = model()
        value["units"].append({"id": "P-2"})
        value["streams"] = [{"id": "S-1", "from": "P-1", "to": "P-2", "provenance": appearances()}]
        full = graph(value)
        for result in (full, gx.apply_profile(full, "core")):
            self.assertEqual(gx.problems(result), [])
            self.assertEqual(next(n for n in result["nodes"] if n["id"] == "P-1")["provenance"], appearances())
            self.assertEqual(next(e for e in result["edges"] if e["id"] == "S-1")["provenance"], appearances())
        without = copy.deepcopy(value)
        del without["units"][0]["provenance"]
        del without["streams"][0]["provenance"]
        self.assertEqual(full["counts"], graph(without)["counts"])

    def test_malformed_later_appearance_refuses_before_replacing_output(self):
        invalid = ["not an object", {"sheet": []}, {"sheet": True}, {"box_0_1000": "1,2,3,4"}]
        invalid += [{"box_0_1000": b} for b in ([1, 2, True, 4], [1, 2, 3], [3, 2, 1, 4],
                    [-1, 2, 3, 4], [1, 2, 1001, 4], [1, 2, float("nan"), 4], [1, 2, 10**1000, 4])]
        invalid += [{"extra": {"value": float("inf")}}]
        for bad in invalid:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as d:
                value = model()
                value["units"][0]["provenance"][1] = bad
                inp, out = Path(d) / "model.json", Path(d) / "graph.json"
                inp.write_text(json.dumps(value), encoding="utf-8")
                out.write_bytes(b"retain previous output")
                original = inp.read_bytes()
                error = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(error):
                    code = gx.main([str(inp), "--out", str(out)])
                self.assertEqual(code, 1, error.getvalue())
                self.assertIn("provenance", error.getvalue())
                self.assertEqual(out.read_bytes(), b"retain previous output")
                self.assertEqual(inp.read_bytes(), original)
        for bad in ({"sheet": "2"}, "text"):
            with self.assertRaisesRegex(ValueError, "list of appearance objects"):
                gx.source_of({"provenance": bad}, "test")

    def test_snapshot_and_context_retain_raw_evidence_and_detect_a_later_locator_change(self):
        value = graph()
        with tempfile.TemporaryDirectory() as d:
            path, questions = Path(d) / "graph.json", Path(d) / "questions.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            questions.write_text(json.dumps({"questions": [{"id": "Q1", "question": "What is recorded?",
                                                            "assets": [{"id": "P-1"}]}]}), encoding="utf-8")
            packet = snapshot.Snapshot(path)
            original = packet.asset("P-1")["result"]
            self.assertEqual(original["provenance"], appearances())
            original["provenance"][1]["sheet"] = "changed"
            self.assertEqual(packet.asset("P-1")["result"]["provenance"], appearances())
            _, _, before = context.load_inputs(path, questions)
            content = before["Q1"]["assets"][0]["content"]
            self.assertEqual(content["provenance"], appearances())
            changed = copy.deepcopy(value)
            next(n for n in changed["nodes"] if n["id"] == "P-1")["provenance"][1]["box_0_1000"][0] += 1
            path.write_text(json.dumps(changed), encoding="utf-8")
            _, _, after = context.load_inputs(path, questions)
            self.assertNotEqual(before["Q1"], after["Q1"])
            malformed = copy.deepcopy(changed)
            next(n for n in malformed["nodes"] if n["id"] == "P-1")["provenance"][1] = {"box_0_1000": [1, True, 3, 4]}
            self.assertTrue(any("provenance[1]" in p for p in gx.problems(malformed)))
            path.write_text(json.dumps(malformed), encoding="utf-8")
            with self.assertRaises(snapshot.InputError):
                snapshot.Snapshot(path)

    def test_statement_evidence_csv_html_and_fingerprints_keep_all_appearances(self):
        value = graph()
        statements, _, gr = stm.build(value)
        item = next(s for s in statements if s["subject"] == "P-1")
        statement_count = len(statements)

        class Crops:
            def crop(self, sheet, boxes):
                return "evidence/sheet2.jpg" if str(sheet) == "2" else None

        stm.add_evidence(statements, gr, Crops(), None)
        self.assertEqual(len(statements), statement_count)
        evidence = item["evidence"]["item_appearances"]
        self.assertEqual([e["record"] for e in evidence], appearances())
        self.assertEqual(len(evidence), 4)
        self.assertIn("no sheet image", evidence[1]["note"])
        self.assertIn("no usable sheet and box", evidence[3]["note"])
        self.assertEqual(stm.evidence_refs([item]), [Path("evidence/sheet2.jpg")])
        rendered = stm.html_page("Test", [item])
        self.assertIn("Recorded item appearances", rendered)
        self.assertIn("do not establish", rendered)
        self.assertIn("drawing sheet 3", rendered)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "review.csv"
            stm.write_sheet(path, [item])
            with path.open(encoding="utf-8", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertIn("drawing sheet 2", row["source"])
            self.assertIn("drawing sheet 3", row["source"])
            self.assertIn("Complete extraction records", row["source"])
        altered = copy.deepcopy(item)
        altered["item_evidence"]["provenance"][1]["extra"] = "later edit"
        self.assertEqual(item["id"], altered["id"])
        self.assertNotEqual(stm.review_fingerprint(item, {}), stm.review_fingerprint(altered, {}))
        changed = copy.deepcopy(item)
        changed["evidence"]["item_appearances"][1]["image"] = "../source.json"
        with self.assertRaisesRegex(ValueError, "relative paths"):
            stm.evidence_refs([changed])

    def test_legacy_graphs_keep_their_original_statement_shape(self):
        value = graph()
        for record in [*value["nodes"], *value["edges"]]:
            for key in ("provenance", "citations"):
                record.pop(key, None)
        for node in value["nodes"]:
            node.pop("source", None)
        statements, _, _ = stm.build(value)
        self.assertTrue(all("item_evidence" not in s for s in statements))

    def test_parallel_relations_with_distinct_evidence_keep_separate_verdict_targets(self):
        value = graph()
        other = copy.deepcopy(next(n for n in value["nodes"] if n["id"] == "P-1"))
        other["id"] = "P-2"
        value["nodes"].append(other)
        first = {"id": "E1", "from": "P-1", "to": "P-2", "type": "piped_to",
                 "status": "unverified", "source": {"kind": "model"}, "provenance": appearances()}
        second = copy.deepcopy(first)
        second["id"] = "E2"
        second["provenance"][0]["sheet"] = "different sheet"
        value["edges"] = [first, second]
        relations = [s for s in stm.build(value)[0] if s["predicate"] == "edge:piped_to"]
        self.assertEqual(len(relations), 2)
        self.assertNotEqual(relations[0]["id"], relations[1]["id"])
        self.assertEqual([s["targets"] for s in relations], [[["edge", "E1"]], [["edge", "E2"]]])
        self.assertEqual([s["item_evidence"]["provenance"] for s in relations],
                         [first["provenance"], second["provenance"]])
        # Equal records can still coalesce without losing a source or changing legacy target behavior.
        second["provenance"] = copy.deepcopy(first["provenance"])
        relations = [s for s in stm.build(value)[0] if s["predicate"] == "edge:piped_to"]
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]["targets"], [["edge", "E1"], ["edge", "E2"]])
        second["source"] = {"kind": "document", "document": "different source"}
        self.assertEqual(len([s for s in stm.build(value)[0] if s["predicate"] == "edge:piped_to"]), 2)

    def test_missing_sheet_never_selects_an_image_named_none(self):
        value = model()
        value["units"][0]["provenance"] = [{"box_0_1000": [1, 2, 3, 4]}]
        statements, _, gr = stm.build(graph(value))

        class Crops:
            def crop(self, sheet, boxes):
                raise AssertionError("a missing sheet must never select a supplied image")

        stm.add_evidence(statements, gr, Crops(), None)
        item = next(s for s in statements if s["subject"] == "P-1")
        self.assertIsNone(item["evidence"]["image"])
        self.assertIn("no usable sheet and box", item["evidence"]["note"])
        self.assertIsNone(item["evidence"]["item_appearances"][0]["image"])

    def test_equal_attribute_wording_keeps_distinct_claim_sources_and_targets(self):
        value = graph()
        node = next(n for n in value["nodes"] if n["id"] == "P-1")
        node["attributes"] = [
            {"name": "class", "value": "tank", "status": "unverified",
             "source": {"kind": "document", "document": "datasheet p. 4"}},
            {"name": "type", "value": "tank", "status": "unverified",
             "source": {"kind": "review", "by": "Fictional reviewer", "on": "2026-10-30"}}]
        claims = [s for s in stm.build(value)[0] if s["subject"] == "P-1" and s["predicate"] == "is_a"]
        self.assertEqual(len(claims), 2)
        self.assertEqual([s["source_kind"] for s in claims], ["document", "review"])
        self.assertEqual([s["targets"] for s in claims],
                         [[["claim", "P-1", "class"]], [["claim", "P-1", "type"]]])
        node["attributes"][1]["source"] = copy.deepcopy(node["attributes"][0]["source"])
        claims = [s for s in stm.build(value)[0] if s["subject"] == "P-1" and s["predicate"] == "is_a"]
        self.assertEqual(len(claims), 1)
        self.assertEqual(len(claims[0]["targets"]), 2)

    def test_extraction_priority_is_retained_as_metadata_not_a_plant_statement(self):
        value = model()
        value["units"][0]["risk"] = {"risk_score": 0.0395, "tier": "green", "why": "no strong warning signs",
                                    "tier_before_floor": "green"}
        authored, _, _ = stm.build(graph(value))
        self.assertEqual(len([s for s in authored if s["predicate"].startswith("risk.")]), 4)
        value["meta"]["model_kind"] = "extracted_twin"
        value["units"][0]["risk"]["separate_authored_fact"] = "retained"
        exported = graph(value)
        statements, skipped, gr = stm.build(exported)
        self.assertEqual([s["predicate"] for s in statements if s["predicate"].startswith("risk.")],
                         ["risk.separate_authored_fact"])
        self.assertEqual(skipped["internal field: risk.*"], 4)
        self.assertEqual(len([a for n in exported["nodes"] for a in n["attributes"] if a["name"].startswith("risk.")]), 5)
        stm.add_evidence(statements, gr, None, None)
        counts = stm.summary(statements)["evidence_availability"]
        self.assertEqual(counts["primary_images"], 0)
        self.assertEqual(counts["item_appearance_images"], 0)
        self.assertGreater(counts["item_appearances"], 0)

    def test_combined_values_with_distinct_sources_keep_each_constituent_visible(self):
        for kind, fields, merged_predicate in (
                ("controller", [("setpoint.value", 10), ("setpoint.uom", "kPa")], "setpoint"),
                ("limit", [("what", "pressure limit"), ("value", 10), ("uom", "kPa")], "limit_value")):
            with self.subTest(kind=kind):
                value = graph()
                node = next(n for n in value["nodes"] if n["id"] == "P-1")
                node["kind"] = kind
                node["attributes"] = [{"name": name, "value": v, "status": "unverified",
                    "source": {"kind": "document", "document": "datasheet p. 4"}} for name, v in fields]
                node["attributes"][0]["source"] = {"kind": "review", "by": "Fictional reviewer"}
                statements = [s for s in stm.build(value)[0] if s["subject"] == "P-1" and s["type"] == "attribute"]
                self.assertEqual([s["predicate"] for s in statements], [name for name, _ in fields])
                self.assertEqual([s["source"] for s in statements], [a["source"] for a in node["attributes"]])
                self.assertEqual([s["targets"] for s in statements],
                                 [[["claim", "P-1", name]] for name, _ in fields])
                for a in node["attributes"]:
                    a["source"] = {"kind": "document", "document": "same source"}
                statements = [s for s in stm.build(value)[0] if s["subject"] == "P-1" and s["type"] == "attribute"]
                self.assertEqual([s["predicate"] for s in statements], [merged_predicate])
                self.assertEqual(len(statements[0]["targets"]), len(fields))


if __name__ == "__main__":
    unittest.main()
