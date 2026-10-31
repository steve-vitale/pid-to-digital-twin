"""The twin graph export: committed examples regenerate exactly and validate, every claim is sourced, aliases carry
former tags, controller edges follow the model, and a malformed graph is refused. Stdlib only."""
import contextlib
import copy
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import graph_export as gx  # noqa: E402

EX = ROOT / "examples" / "graph-export"


def build_from(model, **kw):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "m.json"
        f.write_text(json.dumps(model), encoding="utf-8")
        return gx.build(f, **kw)


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = gx.main([str(a) for a in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue() + err.getvalue()


def hand_built(**sections):
    m = {"meta": {"model_id": "x", "title": "x", "source_document": "doc"}, "units": [], "streams": []}
    m.update(sections)
    return m


class GraphExport(unittest.TestCase):
    def test_actual_cli_refuses_bound_question_packets_before_full_or_core_writes(self):
        # This is a valid complete packet with historical answers, not a fabricated binding. Re-exporting its
        # questions against a changed model would inherit currentness without validating the old decisions.
        import context_register
        packet = ROOT / "examples/context-register/illustrative"
        questions = packet / "expected/enriched_questions.json"
        graph = packet / "expected/enriched_graph.json"
        register = packet / "expected/context.json"
        context_register.validate_export(json.loads(graph.read_text(encoding="utf-8")),
                                         json.loads(register.read_text(encoding="utf-8")))
        originals = {p: p.read_bytes() for p in (questions, graph, register, packet / "model.json")}
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            model = json.loads(originals[packet / "model.json"])
            model["units"][1]["service"] = "ILLUSTRATIVE changed service; requires new review"
            model_path = folder / "model.json"
            model_path.write_text(json.dumps(model), encoding="utf-8")
            for profile in ("full", "core"):
                for exists in (False, True):
                    with self.subTest(profile=profile, existing_destination=exists):
                        out = folder / f"{profile}-{exists}.json"
                        if exists:
                            out.write_bytes(b"preserve prior artifact\n")
                        before = out.read_bytes() if exists else None
                        result = subprocess.run([sys.executable, "-S", str(ROOT / "scripts/graph_export.py"),
                                                 str(model_path), "--questions", str(questions),
                                                 "--profile", profile, "--out", str(out)],
                                                cwd=ROOT, capture_output=True, encoding="utf-8", timeout=30)
                        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                        self.assertIn("bound enriched questions", result.stderr)
                        self.assertIn("preserved register", result.stderr)
                        self.assertIn("cannot rebind decisions", result.stderr)
                        self.assertEqual(out.read_bytes() if out.exists() else None, before)
            self.assertEqual(json.loads(model_path.read_text(encoding="utf-8")), model)
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})

    def test_actual_cli_ordinary_questions_keep_complete_supplied_content_in_both_profiles(self):
        model = hand_built(units=[{"id": "P-1", "type": "pump", "name": "ILLUSTRATIVE pump"}])
        question = {"id": "Q@P-1", "question": "Which source supports this historical interpretation?",
                    "assets": [{"id": "P-1"}], "evidence": [{"id": "P-1", "status": "draft",
                    "basis": "Historical source only; no current observation.", "qualifiers": {
                        "observed": False, "value": 0, "unknown": None, "text": "supplied °C"}}],
                    "data_requests": [{"item": "Applicable evidence", "where": ["original source"],
                                       "how": "Keep attribution and uncertainty."}]}
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            model_path, questions = folder / "model.json", folder / "questions.json"
            model_path.write_text(json.dumps(model), encoding="utf-8")
            questions.write_text(json.dumps({"questions": [question]}), encoding="utf-8")
            before = {p: p.read_bytes() for p in (model_path, questions)}
            for profile in ("full", "core"):
                with self.subTest(profile=profile):
                    out = folder / f"{profile}.json"
                    result = subprocess.run([sys.executable, "-S", str(ROOT / "scripts/graph_export.py"),
                                             str(model_path), "--questions", str(questions),
                                             "--profile", profile, "--out", str(out)],
                                            cwd=ROOT, capture_output=True, encoding="utf-8", timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    exported = json.loads(out.read_text(encoding="utf-8"))
                    self.assertEqual(exported["questions"], [question])
                    self.assertNotIn("context_register", exported)
                    self.assertEqual(gx.problems(exported), [])
            self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_cli_preserves_every_consumed_input_on_output_collision(self):
        for source in ("model", "questions", "review"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as d:
                folder = Path(d)
                model, questions, review = (folder / name for name in ("model.json", "questions.json", "review.json"))
                model.write_text(json.dumps(hand_built()), encoding="utf-8")
                questions.write_text('{"questions": []}', encoding="utf-8")
                review.write_text('{"applied": []}', encoding="utf-8")
                # Keep only the actual review in the review glob.
                reviews = folder / "reviews"
                reviews.mkdir()
                review = review.rename(reviews / review.name)
                paths = {"model": model, "questions": questions, "review": review}
                before = {p: p.read_bytes() for p in paths.values()}
                code, text = run_cli(model, "--questions", questions, "--reviews", reviews, "--out", paths[source])
                self.assertEqual(code, 1, text)
                self.assertIn("output aliases an input", text)
                self.assertEqual(before, {p: p.read_bytes() for p in paths.values()})

    def test_check_mode_does_not_write_even_with_an_output_argument(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "untouched.json"
            out.write_bytes(b"keep this")
            code, text = run_cli("--check", EX / "bayer_graph.json", "--out", out)
            self.assertEqual(code, 0, text)
            self.assertEqual(out.read_bytes(), b"keep this")

    def test_validator_rejects_bad_ids_statuses_and_dangling_stream_refs(self):
        graph = json.loads((EX / "bayer_graph.json").read_text(encoding="utf-8"))
        self.assertEqual(gx.problems(graph), [])
        def dangling(g):
            next(e for e in g["edges"] if e["type"] == "sits_on")["to"] = "stream:DOES_NOT_EXIST"
        for mutate, message in (
            (lambda g: g["edges"].append(copy.deepcopy(g["edges"][0])), "edge id"),
            (lambda g: g["edges"][0].update(status="NOT_A_STATUS"), "unknown status"),
            (lambda g: g["nodes"][0].update(status="NOT_A_STATUS"), "unknown status"),
            (dangling, "DOES_NOT_EXIST"),
        ):
            bad = copy.deepcopy(graph)
            mutate(bad)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "bad.json"
                path.write_text(json.dumps(bad), encoding="utf-8")
                code, text = run_cli("--check", path)
            self.assertEqual(code, 1, text)
            self.assertIn(message, text)

    def test_no_text_in_a_hand_built_model_is_silently_dropped(self):
        # Round 4 review: verification caveats, a second check's evidence, an item's own citation and the model's
        # meta notes were dropped from the TE export. Every sentence-length value must reach the graph, except the
        # sections the export declares it leaves out (not_exported).
        for model in ("data/te_process_model.json", "data/bayer_rt/process_model.json"):
            g = gx.build(ROOT / model)
            text = json.dumps(g, ensure_ascii=False)
            declared = {s["section"] for s in g["not_exported"]}
            m = json.loads((ROOT / model).read_text(encoding="utf-8"))
            missing = []

            def walk(v, path):
                if isinstance(v, dict):
                    for k, x in v.items():
                        walk(x, path + [k])
                elif isinstance(v, list):
                    for i, x in enumerate(v):
                        walk(x, path + [i])
                elif isinstance(v, str) and len(v) > 25 and path[0] not in declared \
                        and json.dumps(v, ensure_ascii=False)[1:-1] not in text:
                    missing.append("/".join(map(str, path)))
            walk(m, [])
            self.assertEqual(missing, [], model)

    def test_hand_built_examples_regenerate_exactly(self):
        for model, out in (("data/te_process_model.json", "te_graph.json"),
                           ("data/bayer_rt/process_model.json", "bayer_graph.json")):
            fresh = json.dumps(gx.build(ROOT / model), indent=1, ensure_ascii=False) + "\n"
            self.assertEqual(fresh, (EX / out).read_text(encoding="utf-8"), out)

    def test_actual_unplaced_dexpi_packet_runs_offline_with_stdlib(self):
        result = subprocess.run([sys.executable, "-S", str(EX / "unplaced-dexpi/check_packet.py")],
                                cwd=ROOT, capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2 complete derived models", result.stdout)
        self.assertIn("NOT CHECKED: original XML", result.stdout)

    def test_every_example_validates_and_has_no_local_path(self):
        for f in sorted(EX.glob("*.json")):
            g = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(gx.problems(g), [], f.name)
            text = f.read_text(encoding="utf-8")
            self.assertNotIn("Users/", text, f.name)
            self.assertNotIn("\\\\Users", text, f.name)

    def test_te_graph_matches_the_model(self):
        g = json.loads((EX / "te_graph.json").read_text(encoding="utf-8"))
        m = json.loads((ROOT / "data" / "te_process_model.json").read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in g["nodes"]}
        self.assertIn("FI-101", nodes["FT-101"]["aliases"])
        edges = {(e["type"], e["from"], e["to"]) for e in g["edges"]}
        for c in m["controllers"]:
            self.assertIn(("controls", c["measurement"], c["tag"]), edges, c["tag"])
        self.assertEqual(sum(1 for e in g["edges"] if e["type"] == "connects"), len(m["streams"]))

    def test_nested_and_list_content_is_exported_not_dropped(self):
        g = json.loads((EX / "bayer_graph.json").read_text(encoding="utf-8"))
        m = json.loads((ROOT / "data" / "bayer_rt" / "process_model.json").read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in g["nodes"]}
        sp = {a["name"]: a for a in nodes["TIC-104"]["attributes"]}
        self.assertEqual(sp["setpoint.value"]["value"], 135)
        self.assertIn("p. 29", sp["setpoint.value"]["source"]["document"])
        edges = {(e["type"], e["from"], e["to"]) for e in g["edges"]}
        for v in ("TV-104A", "TV-104B", "TV-104C"):
            self.assertIn(("controls", "TIC-104", v), edges)
        for kind, section in (("manual_valve", "manual_valves"), ("relief_device", "relief_devices"),
                              ("interlock", "interlocks"), ("limit", "limits")):
            self.assertEqual(sum(n["kind"] == kind for n in g["nodes"]), len(m[section]), kind)
        self.assertIn(("protects", "PSV-101", "RT-1"), edges)
        self.assertEqual({s["section"] for s in g["not_exported"]}, {"events_2008_08_28", "people"})

    def test_a_line_carries_its_own_data(self):
        g = json.loads((EX / "bayer_graph.json").read_text(encoding="utf-8"))
        s1 = next(e for e in g["edges"] if e["type"] == "connects" and e["id"] == "S1")
        self.assertIn(("normal_temperature_C", 80), [(c["name"], c["value"]) for c in s1["attributes"]])
        self.assertFalse(any(c["name"] in ("from", "to") for c in s1["attributes"]))

    def test_an_item_with_no_unit_is_a_node_not_dropped(self):
        m = {"meta": {"model_id": "x", "title": "x", "source_document": "x"}, "units": [], "streams":
             [{"id": "L1", "name": "line", "from": "BL", "to": "BL", "source": "drawing"}],
             "instruments": [], "final_elements": [],
             "unplaced": [{"tag": "ESV-1", "dexpi_class": "OperatedValve", "stream": "L1", "description": "valve",
                           "unit_basis": "no unit reachable through the piping", "source": "XML OperatedValve-1"}]}
        g = build_from(m)
        n = next(x for x in g["nodes"] if x["id"] == "ESV-1")
        self.assertEqual(n["kind"], "final_element")
        self.assertIn("no unit", n["placement"])
        self.assertEqual(g["not_exported"], [])

    def test_an_item_without_its_own_source_says_so(self):
        item = {"tag": "FT-1", "unit": "U-1", "description": "x"}
        c = gx.claims(item, "the model's document")[0]
        self.assertEqual(c["source"]["kind"], "model")
        self.assertIn("no source of its own", c["source"]["note"])

    def test_unplaced_roles_and_control_paths_survive_without_inventing_units(self):
        c = {"tag": "FIC-04", "measurement_unplaced": "FT-04", "output_unplaced": ["FV-04", "FV-05"],
             "source": "XML InformationFlow-1; interpreted by reader", "verification": {"status": "unverified"}}
        unplaced = [{"tag": tag, "kind": kind, "unit": None, "unit_basis": "no reachable equipment",
                     "source": "XML " + tag} for tag, kind in
                    (("FT-04", "instrument"), ("FV-04", "final_element"), ("FV-05", "final_element"),
                     ("HV-1", "manual_valve"), ("PSV-1", "relief_device"), ("UNK-1", "future_role"))]
        g = build_from(hand_built(controllers=[c], unplaced=unplaced))
        self.assertEqual(gx.problems(g), [])
        nodes = {n["id"]: n for n in g["nodes"]}
        for item in unplaced:
            nd = nodes[item["tag"]]
            self.assertEqual(nd["kind"], "line_item" if item["tag"] == "UNK-1" else item["kind"])
            self.assertEqual(nd["placement"], item["unit_basis"])
            self.assertEqual(nd["status"], "unverified")
            self.assertEqual({a["name"]: a["value"] for a in nd["attributes"]}["kind"], item["kind"])
        self.assertEqual([(e["type"], e["from"], e["to"]) for e in g["edges"]],
                         [("controls", "FT-04", "FIC-04"), ("controls", "FIC-04", "FV-04"),
                          ("controls", "FIC-04", "FV-05")])
        for e in g["edges"]:
            self.assertEqual(e["status"], "unverified")
            self.assertEqual(e["source"]["document"], c["source"])
        attrs = {a["name"]: a["value"] for a in nodes["FIC-04"]["attributes"]}
        self.assertEqual(attrs["measurement_unplaced"], "FT-04")
        self.assertEqual(attrs["output_unplaced"], ["FV-04", "FV-05"])
        # Scalar output and duplicate references agree with the same typed path, without parallel duplicates.
        c["output_unplaced"] = "FV-04"
        c["measurement_unplaced"] = ["FT-04", "FT-04"]
        g = build_from(hand_built(controllers=[c], unplaced=unplaced))
        self.assertEqual(len(g["edges"]), 2)

    def test_unplaced_reference_errors_refuse_before_overwriting_graph(self):
        for target in ("MISSING", "HV-1", ["FV-1", "MISSING"], ["FV-1", None], {"tag": "FV-1"}, 1):
            m = hand_built(controllers=[{"tag": "FIC-1", "output_unplaced": target}],
                           unplaced=[{"tag": "FV-1", "kind": "final_element"},
                                     {"tag": "HV-1", "kind": "manual_valve"}])
            with tempfile.TemporaryDirectory() as folder:
                inp, out = Path(folder) / "model.json", Path(folder) / "graph.json"
                inp.write_text(json.dumps(m), encoding="utf-8")
                out.write_bytes(b"existing graph must survive")
                before = {p.name: p.read_bytes() for p in Path(folder).iterdir()}
                code, text = run_cli(inp, "--out", out)
                self.assertEqual(code, 1, text)
                self.assertIn("output_unplaced", text)
                self.assertEqual({p.name: p.read_bytes() for p in Path(folder).iterdir()}, before)
        # A valve cannot be silently reinterpreted as the controller's measurement.
        with self.assertRaisesRegex(ValueError, "measurement_unplaced.*instrument"):
            build_from(hand_built(controllers=[{"tag": "FIC-1", "measurement_unplaced": "FV-1"}],
                                  unplaced=[{"tag": "FV-1", "kind": "final_element"}]))

    def test_explicit_unknown_unplaced_role_is_not_inferred_from_legacy_class(self):
        m = hand_built(unplaced=[{"tag": "X", "kind": "unknown", "dexpi_class": "OperatedValve"},
                                {"tag": "Y", "actuated": True}])
        nodes = {n["id"]: n for n in build_from(m)["nodes"]}
        self.assertEqual(nodes["X"]["kind"], "line_item")
        self.assertEqual(nodes["Y"]["kind"], "final_element")

    def test_extracted_example_keeps_drawing_provenance(self):
        g = json.loads((EX / "sheet0_graph.json").read_text(encoding="utf-8"))
        inst = next(n for n in g["nodes"] if n["kind"] == "instrument")
        self.assertEqual(inst["attributes"][0]["source"]["kind"], "drawing")
        self.assertTrue(all(e["direction"] == "unknown" for e in g["edges"] if e["type"] == "connects"))

    def test_a_persons_review_outranks_the_extraction(self):
        g = json.loads((ROOT / "examples" / "review-and-mapping" / "graph_after_review.json").read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in g["nodes"]}
        self.assertEqual(nodes["S0-IN003"]["status"], "rejected")
        self.assertEqual(nodes["S0-TK001"]["status"], "confirmed")
        self.assertEqual(nodes["S0-VL020"]["status"], "corrected")
        self.assertIn("MSCV-XXX", nodes["S0-VL020"]["aliases"])  # the tag before the correction still joins
        self.assertEqual({e["item"] for e in g["events"]}, {"S0-IN003", "S0-TK001", "S0-VL020", "S0-IN002"})
        self.assertEqual(gx.problems(g), [])

    def test_core_profile_keeps_the_governed_set_and_counts_what_it_drops(self):
        full = json.loads((EX / "sheet0_graph.json").read_text(encoding="utf-8"))
        core = gx.apply_profile(full, "core")
        self.assertEqual(json.dumps(core, indent=1, ensure_ascii=False) + "\n",
                         (EX / "sheet0_graph_core.json").read_text(encoding="utf-8"))  # the committed example
        self.assertEqual(gx.problems(core), [])
        p = core["profile"]
        self.assertEqual(core["counts"]["claims"] + sum(p["dropped_claims"].values()) + p["claims_on_dropped_edges"],
                         full["counts"]["claims"])  # every claim is either kept or counted as dropped
        self.assertFalse(any(e["type"] == "connects" and e.get("layer") == "network_pair" for e in core["edges"]))
        kept = {e["type"] for e in core["edges"]}
        self.assertTrue({"piped_to", "on_network", "contains"} <= kept)
        names = {a["name"] for n in core["nodes"] for a in n["attributes"]}
        self.assertTrue({"unit", "uom", "description"} <= names)
        self.assertFalse(any(n.endswith("_method") or "sha256" in n for n in names))
        self.assertTrue(all("source" in a for n in core["nodes"] for a in n["attributes"]))
        for model in ("data/te_process_model.json", "data/bayer_rt/process_model.json"):  # nothing extracted to drop
            g = gx.build(ROOT / model)
            c = gx.apply_profile(g, "core")
            self.assertEqual((c["counts"], c["profile"]["dropped_claims"]), (g["counts"], {}))
        with self.assertRaises(ValueError):
            gx.apply_profile(full, "tiny")

    def test_malformed_graphs_are_refused(self):
        g = json.loads((EX / "bayer_graph.json").read_text(encoding="utf-8"))
        for mutate, msg in ((lambda x: x["nodes"].append(copy.deepcopy(x["nodes"][2])), "more than once"),
                            (lambda x: x["edges"][0].update(type="feeds"), "unknown type"),
                            (lambda x: x["edges"][0].update(to="NOPE"), "is not a node"),
                            (lambda x: x["nodes"][2]["attributes"][0].update(status="probably"), "status"),
                            (lambda x: x["nodes"][2]["attributes"][0].pop("source"), "no source")):
            bad = copy.deepcopy(g)
            mutate(bad)
            self.assertTrue(any(msg in p for p in gx.problems(bad)), msg)


    def test_nested_content_at_any_depth_becomes_claims(self):
        unit = {"id": "U1", "ratings": [{"case": "a", "psig": 50}, {"case": "b", "psig": 60}],
                "design": {"p": {"v": 1, "uom": "bar"}, "t": 5}, "aliases": ["x", "y"],
                "facts": {"duty": {"value": 3, "uom": "MW"}, "service": "feed"},
                "spec": {"source": "datasheet p. 4", "limits": {"max": 9}}, "layout": {"x": 1}}
        g = build_from(hand_built(units=[unit]))
        attrs = {c["name"]: c for c in next(n for n in g["nodes"] if n["id"] == "U1")["attributes"]}
        want = {"ratings[0].case": "a", "ratings[0].psig": 50, "ratings[1].case": "b", "ratings[1].psig": 60,
                "design.p.v": 1, "design.p.uom": "bar", "design.t": 5, "aliases": ["x", "y"], "duty.value": 3,
                "duty.uom": "MW", "service": "feed", "spec.limits.max": 9}
        self.assertEqual({k: c["value"] for k, c in attrs.items()}, want)
        self.assertEqual(attrs["spec.limits.max"]["source"]["document"], "datasheet p. 4")  # a record's own source
        self.assertEqual(g["not_exported"], [])
        self.assertEqual(gx.problems(g), [])

    def test_a_list_of_lists_is_indexed_not_dropped(self):
        g = build_from(hand_built(units=[{"id": "U1", "curve": [[0, 1], [2, 3]], "mixed": [1, {"a": 2}]}]))
        attrs = {c["name"]: c["value"] for c in next(n for n in g["nodes"] if n["id"] == "U1")["attributes"]}
        self.assertEqual(attrs, {"curve[0]": [0, 1], "curve[1]": [2, 3], "mixed[0]": 1, "mixed[1].a": 2})

    def test_sheet0_lines_keep_the_drawing_they_came_from(self):
        g = json.loads((EX / "sheet0_graph.json").read_text(encoding="utf-8"))
        lines = [e for e in g["edges"] if e["type"] == "connects"]
        self.assertTrue(lines)
        for e in lines:
            a = {c["name"]: c["value"] for c in e["attributes"]}
            self.assertEqual(a.get("source_evidence.source_drawing.drawing_id"), "OPEN100-0", e["id"])
            self.assertIn("source_evidence.source_drawing.page", a, e["id"])

    def test_a_cascade_controller_sets_the_point_of_its_slave(self):
        m = json.loads((ROOT / "data" / "te_process_model.json").read_text(encoding="utf-8"))
        g = json.loads((EX / "te_graph.json").read_text(encoding="utf-8"))
        edges = {(e["type"], e["from"], e["to"]) for e in g["edges"]}
        cascades = [c for c in m["controllers"] if (c.get("output") or {}).get("setpoint_of")]
        self.assertTrue(cascades)
        for c in cascades:
            self.assertIn(("sets_point_of", c["tag"], c["output"]["setpoint_of"]), edges, c["tag"])

    def test_an_output_key_with_no_edge_rule_is_a_claim(self):
        ctl = {"tag": "TIC-1", "measurement": "TT-1", "output": {"final_element": "TV-1", "action": "reverse"}}
        g = build_from(hand_built(controllers=[ctl]))
        attrs = {c["name"]: c["value"] for c in next(n for n in g["nodes"] if n["id"] == "TIC-1")["attributes"]}
        self.assertEqual(attrs, {"output.action": "reverse"})  # measurement and final_element are edges

    def test_a_claim_value_must_be_a_plain_value(self):
        g = json.loads((EX / "bayer_graph.json").read_text(encoding="utf-8"))
        g["nodes"][2]["attributes"][0]["value"] = {"nested": 1}
        self.assertTrue(any("not a plain value" in p for p in gx.problems(g)))

    def test_check_refuses_a_missing_empty_or_non_graph_file_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            empty, arr = Path(d) / "empty.json", Path(d) / "arr.json"
            empty.write_text("", encoding="utf-8")
            arr.write_text("[]", encoding="utf-8")
            for f, msg in ((Path(d) / "missing.json", "can't read"), (empty, "not JSON"), (arr, "not a graph")):
                code, text = run_cli("--check", f)
                self.assertEqual(code, 1, f.name)
                self.assertIn(msg, text, f.name)
                self.assertNotIn("Traceback", text, f.name)

    def test_sheet0_layers_pipe_network_and_pairwise(self):
        """The pairwise links stay exactly the tracer's, typed as network co-membership and derivable from the
        network layer; the pipe layer is a separate edge type between items and junctions."""
        g = json.loads((EX / "sheet0_graph.json").read_text(encoding="utf-8"))
        kind = {n["id"]: n["kind"] for n in g["nodes"]}
        pairs = [e for e in g["edges"] if e["type"] == "connects"]
        self.assertEqual(len(pairs), 345)
        self.assertEqual({e["layer"] for e in pairs}, {"network_pair"})
        members = {}
        for e in g["edges"]:
            if e["type"] == "on_network" and kind[e["from"]] != "junction":
                members.setdefault(e["to"], set()).add(e["from"])
        derived = {frozenset((a, b)) for ms in members.values() for a in ms for b in ms if a < b}
        self.assertEqual({frozenset((e["from"], e["to"])) for e in pairs}, derived)
        piped = [e for e in g["edges"] if e["type"] == "piped_to"]
        self.assertTrue(piped)
        self.assertTrue(all(kind[x] not in ("line_network", "plant", "system") for e in piped for x in (e["from"], e["to"])))
        junctions = [n for n in g["nodes"] if n["kind"] == "junction"]
        self.assertTrue(junctions)
        attrs = {c["name"]: c for c in junctions[0]["attributes"]}
        self.assertGreaterEqual(attrs["arms"]["value"], 3)
        self.assertEqual(attrs["arms"]["source"]["kind"], "drawing")  # a reviewer gets a crop of the junction
        # fewer item-to-item pipe segments than pairwise links: most pairs are not piped to each other
        ii = [e for e in piped if kind[e["from"]] != "junction" and kind[e["to"]] != "junction"]
        self.assertLess(len(ii), len(pairs) / 4)

    def test_hand_built_and_dexpi_layers(self):
        for name in ("te_graph.json", "bayer_graph.json"):
            g = json.loads((EX / name).read_text(encoding="utf-8"))
            self.assertEqual({e["layer"] for e in g["edges"] if e["type"] == "connects"}, {"stream"}, name)
        g = json.loads((ROOT / "examples" / "from-dexpi-xml" / "dexpi-c01.graph.json").read_text(encoding="utf-8"))
        self.assertEqual(gx.problems(g), [])
        tees = [n for n in g["nodes"] if n["kind"] == "junction"]
        self.assertEqual(len(tees), 5)
        self.assertTrue(all(any(c["name"] == "dexpi_id" and c["value"].startswith("PipeTee") for c in n["attributes"])
                            for n in tees))
        self.assertTrue(any(e["type"] == "piped_to" for e in g["edges"]))

    def test_layer_types_are_validated(self):
        g = json.loads((EX / "sheet0_graph.json").read_text(encoding="utf-8"))
        self.assertEqual(gx.problems(g), [])
        net = next(n["id"] for n in g["nodes"] if n["kind"] == "line_network")
        jn = next(n["id"] for n in g["nodes"] if n["kind"] == "junction")
        pi = next(i for i, e in enumerate(g["edges"]) if e["type"] == "piped_to")
        on = next(i for i, e in enumerate(g["edges"]) if e["type"] == "on_network" and e["from"] == jn)
        cn = next(i for i, e in enumerate(g["edges"]) if e["type"] == "connects")
        for mutate, msg in ((lambda x: x["edges"][pi].update(to=net), "must be an item or a junction"),
                            (lambda x: x["edges"][pi].update(to=x["edges"][pi]["from"]), "to itself"),
                            (lambda x: x["edges"][on].update(to="PLANT"), "must end at a line_network"),
                            (lambda x: x["edges"].pop(on), "exactly one line network"),
                            (lambda x: x["edges"][cn].update(layer="adjacent"), "unknown connects layer"),
                            (lambda x: x["edges"][cn].update(network=net if x["edges"][cn]["network"] != net
                                                             else "S0-NET002"), "derivable from on_network"),
                            (lambda x: x["nodes"].append({"id": "J-X", "kind": "junction", "tag": None, "name": "j",
                                                          "aliases": [], "status": "unverified", "attributes": []}),
                             "a pipe tee with no piped_to edge")):
            bad = copy.deepcopy(g)
            mutate(bad)
            self.assertTrue(any(msg in p for p in gx.problems(bad)), msg)

    def test_sheet0_lines_that_are_not_pipe_have_their_own_edges(self):
        """An actuator stem, an instrument leader and a nozzle stub are not pipe: each has its own edge type, an
        instrument tap sits on the pipe it taps (not splitting it), and the pairwise links stay the tracer's."""
        g = json.loads((EX / "sheet0_graph.json").read_text(encoding="utf-8"))
        kind = {n["id"]: n["kind"] for n in g["nodes"]}
        by = {}
        for e in g["edges"]:
            by.setdefault(e["type"], []).append(e)
        self.assertEqual({(e["from"], e["to"]) for e in by["actuated_by"]},
                         {("S0-VL022", "S0-GN010"), ("S0-VL023", "S0-GN011")})
        self.assertEqual({(e["from"], e["to"]) for e in by["nozzle_of"]},
                         {("S0-GN002", "S0-TK001"), ("S0-GN014", "S0-TK002")})
        self.assertTrue(all(kind[e["from"]] == "instrument" for e in by["instrument_connection"]))
        self.assertFalse([e for e in by["piped_to"] if "instrument" in (kind[e["from"]], kind[e["to"]])])
        attrs = {n["id"]: {c["name"]: c["value"] for c in n["attributes"]} for n in g["nodes"]}
        taps = {n for n, a in attrs.items() if a.get("junction_kind") == "instrument_tap"}
        self.assertEqual(len(taps), 10)
        pipes = {e["id"]: e for e in by["piped_to"]}
        for t in taps:
            self.assertIn(attrs[t]["on_segment"], pipes)
            self.assertFalse([e for e in by["piped_to"] if t in (e["from"], e["to"])])  # the pipe passes the tap
        tee = "S0-JN-537-274"  # where the drop from MS 14010 meets the main line, beside MSCV-XXX's box
        self.assertEqual({x for e in by["piped_to"] if tee in (e["from"], e["to"]) for x in (e["from"], e["to"])}
                         - {tee}, {"S0-VL013", "S0-GN007", "S0-VL020"})
        self.assertEqual(len(by["connects"]), 345)
        self.assertEqual(gx.problems(g), [])
        tap = next(iter(sorted(taps)))
        act = next(i for i, e in enumerate(g["edges"]) if e["type"] == "actuated_by")
        for mutate, msg in ((lambda x: next(c for n in x["nodes"] if n["id"] == tap for c in n["attributes"]
                                            if c["name"] == "on_segment").update(value="S0-XX999"),
                             "must sit on a piped_to edge"),
                            (lambda x: x["edges"][act].update(to=tap), "must join two items")):
            bad = copy.deepcopy(g)
            mutate(bad)
            self.assertTrue(any(msg in p for p in gx.problems(bad)), msg)

    def test_a_missing_reviews_folder_is_refused(self):
        code, text = run_cli("data/bayer_rt/process_model.json", "--reviews", ROOT / "no-such-review-folder")
        self.assertEqual(code, 1)
        self.assertIn("no-such-review-folder", text)
        self.assertIn("not a folder", text)

    def test_a_model_missing_what_the_export_needs_says_what(self):
        meta = {"model_id": "x", "title": "x", "source_document": "x"}
        for model, msg in (({"meta": meta}, "no 'units' section"),
                           (hand_built(units=[{"name": "pump"}]), "units[0] has no 'id'"),
                           (hand_built(streams=[{"id": "S1", "from": "BL"}]), "streams[0] (S1) has no 'to'"),
                           (hand_built(instruments=[{"tag": "FT-1"}]), "instruments[0] (FT-1) has no 'unit'")):
            with tempfile.TemporaryDirectory() as d:
                f = Path(d) / "m.json"
                f.write_text(json.dumps(model), encoding="utf-8")
                code, text = run_cli(f)
            self.assertEqual(code, 1, msg)
            self.assertIn(msg, text)

    def test_the_guide_snippets_run_and_print_what_the_guide_shows(self):
        doc = (ROOT / "docs" / "GRAPH_EXPORT.md").read_text(encoding="utf-8")
        pairs = re.findall(r"```python\n(.*?)```\n+Output:\n+```text\n(.*?)```", doc, re.S)
        self.assertEqual(len(pairs), 2)
        for code, shown in pairs:
            run = subprocess.run([sys.executable, "-S", "-c", code], cwd=ROOT, capture_output=True, text=True,
                                 encoding="utf-8", check=True)
            self.assertEqual(run.stdout, shown)


class OutputPaths(unittest.TestCase):
    def test_spelling_hardlinks_and_sibling_aliases(self):
        from output_paths import protect_outputs
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            source = folder / "source.json"
            source.write_bytes(b"original")
            sub = folder / "sub"
            sub.mkdir()
            for target in (source, sub / ".." / source.name):
                with self.assertRaisesRegex(ValueError, "output aliases an input"):
                    protect_outputs([target], [source])
            linked = folder / "hardlink.json"
            linked.hardlink_to(source)
            with self.assertRaisesRegex(ValueError, "output aliases an input"):
                protect_outputs([linked], [source])
            with self.assertRaisesRegex(ValueError, "files alias each other"):
                protect_outputs([source, linked], [])
            self.assertEqual(source.read_bytes(), b"original")

    def test_symlink_aliases(self):
        from output_paths import protect_outputs
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            source = folder / "source.json"
            source.write_bytes(b"original")
            linked = folder / "link.json"
            try:
                linked.symlink_to(source)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"file symlinks unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "output aliases an input"):
                protect_outputs([linked], [source])
            parent_link = folder / "dir-link"
            parent_link.symlink_to(folder, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "output aliases an input"):
                protect_outputs([parent_link / source.name], [source])
            self.assertEqual(source.read_bytes(), b"original")

    def test_native_case_alias(self):
        from output_paths import protect_outputs
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source.json"
            source.write_bytes(b"original")
            alias = source.with_name("SOURCE.JSON")
            if not alias.exists():
                self.skipTest("filesystem has case-sensitive names")
            with self.assertRaisesRegex(ValueError, "output aliases an input"):
                protect_outputs([alias], [source])
            self.assertEqual(source.read_bytes(), b"original")

    def test_all_destinations_checked_without_creating_anything(self):
        from output_paths import protect_outputs
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            blocked = folder / "blocked"
            blocked.write_bytes(b"not a directory")
            fresh = folder / "new" / "output.json"
            for bad in (folder, blocked / "child.json"):
                # POSIX can raise ENOTDIR during stat before the explicit parent-kind check.
                with self.assertRaisesRegex(ValueError, "not a (regular file|directory)|cannot check output paths"):
                    protect_outputs([fresh, bad], [])
                self.assertFalse(fresh.parent.exists())
            protect_outputs([fresh], [blocked])
            self.assertFalse(fresh.parent.exists())
            self.assertEqual(blocked.read_bytes(), b"not a directory")

    def test_filesystem_check_errors_refuse(self):
        from output_paths import protect_outputs
        with mock.patch.object(Path, "resolve", side_effect=PermissionError("cannot inspect")):
            with self.assertRaisesRegex(ValueError, "cannot check output paths"):
                protect_outputs(["out.json"], ["source.json"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
