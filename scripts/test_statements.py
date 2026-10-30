"""Statement review: ids are stable, every statement carries a source or says it has none, every twin-graph-1 node kind
and edge type has a sentence, sampling is reproducible and stratified, the Wilson interval is right on known cases,
apply never changes a value and records who/when, the two verdicts never mix, and a non-graph file is refused.
Stdlib only (Pillow and the report PDF are not needed: crops and quotes are off here)."""
import copy
import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import graph_export as gx  # noqa: E402
import statements as stm  # noqa: E402

EX = ROOT / "examples" / "graph-export"
PILOT = ROOT / "examples" / "statement-review"
# Reviewed samples that hold statements a later fix withdrew (subject, predicate). They stay as drawn (they are what
# their review measured); only these may be missing from today's statements.
WITHDRAWN = {
    # r2 review: MSBV 1407's tag read as ISA letters (moisture); build_twin now reads MS... on an MSS sheet as a plant
    # tag, so its kind ("final element (valve)") and its variable statement are gone
    ("sheet0", "sample_60"): {("S0-IN034", "is_a")},
    ("sheet0", "sample_layers_r2"): {("S0-IN034", "variable")},
    # the first layered review: pipe statements about an actuator stem, an instrument leader and a nozzle stub
    ("sheet0", "sample_layers"): {("S0-TK002", "edge:piped_to"), ("S0-VL010", "edge:piped_to"),
                                  ("S0-VL023", "edge:piped_to"), ("S0-VL022", "edge:piped_to"),
                                  ("S0-IN027", "edge:piped_to")},
}


def graph(name):
    return json.loads((EX / name).read_text(encoding="utf-8"))


def every_kind_graph():
    """A small graph with one node of every twin-graph-1 kind and one edge of every type."""
    src = {"kind": "document", "document": "p. 1"}
    claim = lambda n, v: {"name": n, "value": v, "status": "unverified", "source": dict(src)}  # noqa: E731
    nodes = [{"id": "PLANT", "kind": "plant", "tag": "p", "name": "Test plant", "aliases": [], "status": "unverified",
              "attributes": []}]
    for k in gx.NODE_KINDS[1:]:
        nodes.append({"id": f"N-{k}", "kind": k, "tag": f"T-{k}" if k not in ("interlock", "limit") else None,
                      "name": f"a {k}", "aliases": [], "status": "unverified",
                      "attributes": [claim("description", f"the {k}")]})
    nodes[nodes.index(next(n for n in nodes if n["kind"] == "instrument"))]["attributes"].append(
        claim("variable", "flow"))
    ends = {"contains": ("PLANT", "N-equipment"), "connects": ("N-equipment", "N-boundary"),
            "measures": ("N-instrument", "N-equipment"), "controls": ("N-instrument", "N-controller"),
            "acts_on": ("N-interlock", "N-final_element"), "sets_point_of": ("N-controller", "N-controller"),
            "sits_on": ("N-manual_valve", "stream:S1"), "protects": ("N-relief_device", "N-equipment"),
            "trips": ("N-instrument", "N-interlock"), "applies_to": ("N-limit", "N-instrument"),
            "piped_to": ("N-junction", "N-equipment"), "on_network": ("N-equipment", "N-line_network"),
            "instrument_connection": ("N-instrument", "N-junction"), "actuated_by": ("N-final_element", "N-line_item"),
            "nozzle_of": ("N-line_item", "N-equipment")}
    edges = [{"id": f"E{n:05d}", "type": t, "from": ends[t][0], "to": ends[t][1], "status": "unverified",
              "direction": None, "source": dict(src)} for n, t in enumerate(gx.EDGE_TYPES, 1)]
    return {"schema": "twin-graph-1", "model_kind": "hand_built", "title": "t", "nodes": nodes, "edges": edges,
            "questions": [], "events": [], "not_exported": []}


class Statements(unittest.TestCase):
    def test_ids_are_stable_and_ignore_status_and_source(self):
        g = graph("bayer_graph.json")
        a, _, _ = stm.build(g)
        b, _, _ = stm.build(copy.deepcopy(g))
        self.assertEqual([s["id"] for s in a], [s["id"] for s in b])
        self.assertEqual(len({s["id"] for s in a}), len(a))
        g2 = copy.deepcopy(g)
        for n in g2["nodes"]:
            n["status"] = "confirmed"
            for c in n["attributes"]:
                c["status"], c["source"] = "confirmed", {"kind": "review", "by": "x", "on": "y", "was": None}
        c, _, _ = stm.build(g2)
        self.assertEqual({s["id"] for s in a}, {s["id"] for s in c})
        self.assertEqual(stm.sid("PT-101", "uom", "psig"), stm.sid("PT-101", "uom", "psig"))
        self.assertNotEqual(stm.sid("PT-101", "uom", "psig"), stm.sid("PT-101", "uom", "kPa"))

    def test_every_statement_has_a_source_or_says_it_has_none(self):
        for name in ("bayer_graph.json", "sheet0_graph.json", "te_graph.json"):
            g = graph(name)
            sts, _, gr = stm.build(g)
            # every edge is its own statement (two streams between the same ends are not merged)
            self.assertEqual(sum(s["type"] == "relation" for s in sts), len(g["edges"]), name)
            self.assertEqual(sum(s["type"] == "identity" and s["predicate"] == "kind" for s in sts),
                             len(g["nodes"]), name)
            stm.add_evidence(sts, gr, None, stm.Report(None))
            for s in sts:
                self.assertTrue(s["source_pointer"], s["id"])
                if s["source_kind"] == "model":
                    self.assertTrue(s["source_pointer"].startswith("no source of its own"), s["text"])
                    self.assertIn("no source of its own", s["evidence"]["note"])
                else:
                    self.assertIn(s["source_kind"], ("drawing", "document", "review"))
                self.assertTrue(s["targets"], s["id"])
                self.assertIn(s["rank"], stm.RANKS)
                self.assertTrue(s["text"][0].isupper() and s["text"].endswith("."), s["text"])

    def test_templates_cover_every_node_kind_and_edge_type(self):
        self.assertEqual(set(stm.KIND_WORDS), set(gx.NODE_KINDS))
        self.assertEqual(set(stm.EDGE_RANK), set(gx.EDGE_TYPES))
        g = every_kind_graph()
        sts, _, _ = stm.build(g)
        kinds = {s["subject_kind"] for s in sts if s["type"] == "identity"}
        self.assertEqual(kinds, set(gx.NODE_KINDS))
        rel = {s["predicate"] for s in sts if s["type"] == "relation"}
        self.assertEqual(rel, {"edge:" + t for t in gx.EDGE_TYPES})
        for s in sts:
            self.assertNotIn("None", s["text"], s["text"])
        g["edges"].append({"id": "X", "type": "invented", "from": "PLANT", "to": "PLANT", "source": {}})
        with self.assertRaises(ValueError):
            stm.build(g)

    def test_sentences_say_what_the_graph_says(self):
        sts, _, _ = stm.build(graph("bayer_graph.json"))
        text = {s["text"] for s in sts}
        for want in ("PSV-101 protects the residue treater RT-1 against overpressure.",
                     "LT-102 is read by controller LIC-102.", "Controller TIC-104 moves TV-104C.",
                     "TIC-104 is set to hold 135 C (its setpoint).", "PT-101 measures pressure for the residue "
                     "treater RT-1.", "PT-101 was also tagged PI-101 (an earlier tag)."):
            self.assertIn(want, text)
        rank = {s["text"]: s["rank"] for s in sts}
        self.assertEqual(rank["PSV-101 protects the residue treater RT-1 against overpressure."], 1)
        self.assertEqual(rank["Interlock IL-1, when it trips, acts on FV-107."], 1)
        s0, skipped, _ = stm.build(graph("sheet0_graph.json"))
        t0 = {s["text"] for s in s0}
        self.assertIn("FT 1401 (S0-IN002) measures flow.", t0)
        self.assertIn("TCV 1401 is a valve in a temperature loop.", t0)  # a valve does not "measure"
        self.assertGreater(skipped.get("internal field: extraction_confidence", 0), 0)
        self.assertFalse([s for s in s0 if s["predicate"] in ("extraction_confidence", "layout", "id")])

    def test_sampling_is_reproducible_and_stratified(self):
        sts, _, _ = stm.build(graph("bayer_graph.json"))
        a, strata = stm.draw_sample(sts, 60, 7)
        b, _ = stm.draw_sample(list(reversed(sts)), 60, 7)
        self.assertEqual(sorted(s["id"] for s in a), sorted(s["id"] for s in b))
        c, _ = stm.draw_sample(sts, 60, 8)
        self.assertNotEqual(sorted(s["id"] for s in a), sorted(s["id"] for s in c))
        self.assertEqual(len(a), 60)
        self.assertEqual(len({s["id"] for s in a}), 60)
        pop = {}
        for s in sts:
            pop[s["stratum"]] = pop.get(s["stratum"], 0) + 1
        self.assertEqual({x["stratum"] for x in strata}, set(pop))
        for x in strata:
            self.assertEqual(x["population"], pop[x["stratum"]])
            self.assertGreaterEqual(x["sampled"], min(2, x["population"]))
            self.assertEqual(x["sampled"], sum(s["stratum"] == x["stratum"] for s in a))
        self.assertEqual(stm.allocate({"a": 100, "b": 3, "c": 1}, 10), {"a": 7, "b": 2, "c": 1})
        self.assertEqual(sum(stm.allocate({"a": 5, "b": 5}, 50).values()), 10)

    def test_wilson_interval_known_cases(self):
        lo, hi = stm.wilson(0, 10)
        self.assertAlmostEqual(lo, 0.0, places=6)
        self.assertAlmostEqual(hi, 0.2775, places=4)
        lo, hi = stm.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.2366, places=4)
        self.assertAlmostEqual(hi, 0.7634, places=4)
        lo, hi = stm.wilson(1, 60)
        self.assertAlmostEqual(lo, 0.00295, places=4)
        self.assertAlmostEqual(hi, 0.0886, places=3)
        self.assertEqual(stm.wilson(0, 0), (None, None))

    def test_score_keeps_the_two_verdicts_apart(self):
        rows = [{"statement_id": "a", "stratum": "x|1", "source_match": "match", "plant_truth": "confirmed"},
                {"statement_id": "b", "stratum": "x|1", "source_match": "mismatch", "plant_truth": "wrong"},
                {"statement_id": "c", "stratum": "y|2", "source_match": "unclear", "plant_truth": ""},
                {"statement_id": "d", "stratum": "y|2", "source_match": "match", "plant_truth": ""},
                {"statement_id": "e", "stratum": "y|2", "source_match": "", "plant_truth": ""}]
        r = stm.score(rows)
        o = r["source_match"]["overall"]
        self.assertEqual((o["mismatch"], o["checked"], o["unclear"], o["not_reviewed"]), (1, 3, 1, 1))
        self.assertAlmostEqual(o["error_rate"], 1 / 3, places=4)
        self.assertEqual(r["plant_truth"], {"confirmed": 1, "not given": 1})
        self.assertEqual(r["ignored_plant_verdicts"], ["b"])
        self.assertEqual(r["source_match"]["by_stratum"]["x|1"]["error_rate"], 0.5)

    def test_each_layer_says_what_it_means(self):
        """Sheet 0 carries three relationship layers; each sentence says exactly which fact it states."""
        sts, _, _ = stm.build(graph("sheet0_graph.json"))
        by = {}
        for s in sts:
            by.setdefault(s["layer"], []).append(s)
        self.assertEqual(set(by), {"item", "pipe", "non_pipe", "network", "network_pair"})
        pair = [s for s in by["network_pair"] if s["predicate"] == "edge:connects"]
        self.assertTrue(pair and all("are on the same drawn line network" in s["text"]
                                     and "does not say a pipe runs directly" in s["text"] for s in pair))
        self.assertFalse([s for s in sts if "joined by a line" in s["text"]])  # the old, misread wording is gone
        piped = [s for s in by["pipe"] if s["predicate"] == "edge:piped_to"]
        touching = {e["id"] for e in graph("sheet0_graph.json")["edges"]
                    if e["type"] == "piped_to" and stm.edge_attr(e, "touching") is True}
        drawn = [s for s in piped if s["targets"][0][1] not in touching]
        self.assertTrue(drawn and all(s["text"].startswith("A pipe runs directly from") and (
            "with no junction or other item between" in s["text"] or "with no pipe tee or other item between"
            in s["text"]) for s in drawn))  # every drawn line that is pipe, and only those
        self.assertTrue(all("arms meet (a pipe tee or branch)" in s["text"] for s in by["pipe"]
                            if s["predicate"] == "kind"))
        self.assertTrue(all(s["text"].startswith(("Junction", "Untagged", "Line network")) or "attached to drawn line "
                            "network" in s["text"] or " is on drawn line network" in s["text"]
                            for s in by["network"] if s["predicate"] == "edge:on_network"))
        # a hand-built model's streams are pipe-level: they keep their stream wording and their own layer
        bay, _, _ = stm.build(graph("bayer_graph.json"))
        self.assertEqual({s["layer"] for s in bay if s["predicate"] == "edge:connects"}, {"stream"})

    def test_touching_process_items_do_not_claim_a_drawn_pipe(self):
        """Contact is a pipe-layer inference, not a line visible between the two items."""
        g = every_kind_graph()
        e = next(e for e in g["edges"] if e["type"] == "piped_to")
        e["from"], e["to"] = "N-equipment", "N-line_item"
        ordinary, _, _ = stm.build(g)
        before = next(s for s in ordinary if s["targets"] == [["edge", e["id"]]])
        self.assertTrue(before["text"].startswith("A pipe runs directly from"))
        e["attributes"] = [{"name": "touching", "value": True, "status": "unverified", "source": e["source"]}]
        contact, _, _ = stm.build(g)
        after = next(s for s in contact if s["targets"] == [["edge", e["id"]]])
        self.assertIn("are drawn against each other, with no line between them", after["text"])
        self.assertIn("the pipe layer treats them as consecutive process items", after["text"])
        self.assertNotIn("pipe runs", after["text"])
        self.assertEqual((after["id"], after["layer"], after["rank"], after["source"]),
                         (before["id"], "pipe", 2, before["source"]))
        # Both contact segments in the committed drawing get that wording too.
        sheet = graph("sheet0_graph.json")
        touching = {e["id"] for e in sheet["edges"]
                    if e["type"] == "piped_to" and stm.edge_attr(e, "touching") is True}
        self.assertEqual(len(touching), 2)
        statements, _, _ = stm.build(sheet)
        contacts = [s for s in statements if s["type"] == "relation" and s["targets"][0][1] in touching]
        self.assertEqual(len(contacts), len(touching))
        self.assertTrue(all("are drawn against each other" in s["text"] and "pipe runs" not in s["text"]
                            for s in contacts))

    def test_safety_screening_notes_are_explicitly_unverified_inferences(self):
        statements, _, _ = stm.build(graph("sheet0_graph.json"))
        notes = [s for s in statements if s["predicate"].startswith("safety.")]
        self.assertEqual(len(notes), 12)
        for s in notes:
            self.assertIn("tag-derived", s["text"].lower())
            self.assertIn("review", s["text"])
            if s["predicate"] == "safety.function":
                self.assertIn("function is unverified", s["text"])

    def test_all_te_cascades_match_their_actual_model_field(self):
        g = graph("te_graph.json")
        gr = stm.Graph(g)
        model = json.loads((ROOT / "data/te_process_model.json").read_text(encoding="utf-8"))
        cascades = [e for e in g["edges"] if e["type"] == "sets_point_of"]
        self.assertEqual(len(cascades), 8)
        for e in cascades:
            matches, field = stm.edge_in_model(model, gr, e, {})
            self.assertTrue(matches, (e, field))
            self.assertTrue(field.endswith(".output.setpoint_of"))
            bad = dict(e, to="NONEXISTENT-CONTROLLER")
            self.assertFalse(stm.edge_in_model(model, gr, bad, {})[0])

    def test_nested_model_fields_and_retained_citations_match_without_hiding_errors(self):
        item = {"source": "original report", "verification": {"previous": {"description": "old"}},
                "ratings": [{"psig": 150}], "literal.key": 7}
        for field, expected in (("cited_source", "original report"), ("verification.previous.description", "old"),
                                ("ratings[0].psig", 150), ("literal.key", 7)):
            self.assertEqual(stm.model_field(item, field), (True, expected))
        for field in ("ratings[1].psig", "verification.missing.description", "ratings[0].absent"):
            self.assertEqual(stm.model_field(item, field), (False, None))
        g = graph("te_graph.json")
        statements, _, _ = stm.build(g)
        model = json.loads((ROOT / "data/te_process_model.json").read_text(encoding="utf-8"))
        stm.machine_check(statements, g, model, "te model")
        self.assertFalse([s for s in statements if s["machine_check"]["result"] == "differs from its model field"])
        changed = next(s for s in statements if s["predicate"] == "cited_source")
        target = changed["targets"][0]
        node = next(n for n in g["nodes"] if n["id"] == target[1])
        next(c for c in node["attributes"] if c["name"] == target[2])["value"] = "WRONG SOURCE"
        stm.machine_check([changed], g, model, "te model")
        self.assertEqual(changed["machine_check"]["result"], "differs from its model field")

    def test_lines_that_are_not_pipe_are_said_as_what_they_are(self):
        """Independent review of the layered sheet-0 sample (2026-10-29): 3 of 15 pipe statements were wrong because
        an actuator stem and an instrument leader were said to be pipes, taps were worded as tees, and a nozzle stub
        on its own vessel was a "pipe". Each is now its own statement in its own layer, worded as what it is."""
        sts, _, gr = stm.build(graph("sheet0_graph.json"))
        text = {s["text"]: s for s in sts}
        for want, layer in (
                ("M is the actuator drawn on untagged valve S0-VL023: the short line between them is its stem, not a "
                 "pipe.", "non_pipe"),
                ("H is the actuator drawn on untagged valve S0-VL022: the short line between them is its stem, not a "
                 "pipe.", "non_pipe"),
                ("An instrument line, not a pipe, runs directly from MSV 1404 to untagged valve S0-VL022, with no "
                 "junction or other item between.", "non_pipe"),
                ("N2 is a nozzle on RCS-SG-100 (classed as a tank by the extraction): the short stub between them is "
                 "part of the vessel, not a pipe.", "non_pipe"),
                ("Instrument tap S0-JN-345-276 is the point on the drawing where PT 14085's instrument line meets a "
                 "pipe, which carries on through it (an instrument tap, not a pipe tee).", "non_pipe"),
                ("A pipe runs directly from pipe tee S0-JN-537-274 to untagged valve S0-VL013, with no junction or other "
                 "item between.", "pipe")):
            self.assertIn(want, text)
            self.assertEqual(text[want]["layer"], layer, want)
        bad = [s["text"] for s in sts if s["predicate"] == "edge:piped_to" and any(
            gr.nodes[x]["kind"] == "instrument" or x in ("S0-GN010", "S0-GN011") for x in (s["subject"], s["object"]))]
        self.assertEqual(bad, [])  # no instrument line or actuator stem is a pipe
        self.assertFalse([s for s in sts if "S0-VL013 to MSCV-XXX" in s["text"] or "S0-GN007 to MSCV-XXX" in s["text"]])
        self.assertFalse([s for s in sts if "(assigned by tracing the lines)" in s["text"] or "tank RCS" in s["text"]
                          or "tank MSS" in s["text"]])
        self.assertIn("The extraction attributes PT 14088 to MSS-XSS-140 (classed as a tank by the extraction) by "
                      "tracing the lines.", text)
        net = next(s["text"] for s in sts if s["subject"] == "S0-NET019" and s["predicate"] == "kind")
        self.assertIn("its lines meet only at the edge of untagged valve S0-VL023", net)
        self.assertIn("it holds no pipe", net)
        pair = next(s["text"] for s in sts if s["predicate"] == "edge:connects" and {s["subject"], s["object"]} ==
                    {"S0-IN028", "S0-GN011"})
        self.assertIn("joined through that item, not by line alone", pair)
        taps = [s for s in sts if s["predicate"] == "kind" and s["subject"].startswith("S0-JN") and
                s["layer"] == "non_pipe"]
        self.assertEqual(len(taps), 10)

    def test_kind_and_attribution_are_worded_as_what_made_them(self):
        """Independent review r2 (2026-10-29): an instrument kind was said as the extraction's class though it comes
        from the tag letters, a PSV was called a final element, and "by tracing the lines" was said of items attached
        by nearest position. The kind is said as the tag letters' reading; the "by ..." follows parent_method /
        unit_method."""
        src = {"kind": "drawing", "sheet": "0", "box_0_1000": [0, 0, 10, 10]}

        def nd(i, kind, tag, **at):
            return {"id": i, "kind": kind, "tag": tag, "name": tag or f"untagged {at.get('class', kind)}",
                    "aliases": [], "status": "unverified",
                    "attributes": [{"name": k, "value": v, "status": "unverified", "source": dict(src)}
                                   for k, v in at.items()]}
        inst = dict(**{"class": "instrumentation"})
        nodes = [nd("PLANT", "plant", None), nd("E", "equipment", "EQ-TK-1", **{"class": "tank"}),
                 nd("V", "line_item", None, **{"class": "valve", "unit": "E", "unit_method": "connection_path"}),
                 nd("I1", "instrument", "PSV 1", **inst, instrument_kind="final element (valve)", isa_letters="PSV",
                    variable="pressure", parent="E", parent_method="linked", unit="E", unit_method="self"),
                 nd("I2", "instrument", "TCV 2", **inst, instrument_kind="final element (valve)", isa_letters="TCV",
                    variable="temperature", parent="V", parent_method="geometry_nearest", unit="E",
                    unit_method="connection_path"),
                 nd("I3", "instrument", "MSBV 3", **inst, instrument_kind="valve (plant-coded tag)",
                    isa_letters="MSBV", parent="E", parent_method="geometry_nearest", unit="E", unit_method="self",
                    variable_method="none: plant tag, its leading letters MS match system code MSS seen on this "
                                    "sheet, so not read as ISA-5.1 letters"),
                 nd("I4", "instrument", "AORV 4", **inst, instrument_kind="operated valve", isa_letters="AORV",
                    parent="V", parent_method="linked", unit="E", unit_method="connection_path")]
        edges = [{"id": f"E{n}", "type": "contains", "from": a, "to": b, "status": "unverified", "direction": None,
                  "source": dict(src)} for n, (a, b) in enumerate((("PLANT", "E"), ("E", "V"), ("E", "I1"),
                                                                    ("V", "I2"), ("E", "I3"), ("V", "I4")))]
        g = {"schema": "twin-graph-1", "model_kind": "extracted_twin", "title": "t", "nodes": nodes, "edges": edges,
             "questions": [], "events": [], "not_exported": []}
        text = {s["text"] for s in stm.build(g)[0]}
        bubble = "; the extraction classed the symbol as an instrument bubble."
        eq = "EQ-TK-1 (classed as a tank by the extraction)"
        for want in ("PSV 1's tag letters read as a valve (PSV: pressure safety valve)" + bubble,
                     "TCV 2's tag letters read as a valve (TCV: temperature control valve)" + bubble,
                     "MSBV 3's tag letters read as a valve (MSBV: a plant tag led by system code MSS, so only its last "
                     "letter is read)" + bubble,
                     "AORV 4's tag letters read as an operated valve (AORV: air-operated relief valve)" + bubble,
                     f"The extraction attributes PSV 1 to {eq} by tracing the lines.",
                     f"The extraction attributes MSBV 3 to {eq} by nearest position on the drawing.",
                     "The extraction attaches TCV 2 to untagged valve V, the nearest item by position on the drawing.",
                     f"The extraction attributes TCV 2 to {eq} by nearest position on the drawing (to untagged valve "
                     "V), then by tracing the lines from it.",
                     f"The extraction attributes AORV 4 to {eq} by tracing the lines."):
            self.assertIn(want, text)
        self.assertFalse([t for t in text if "final element" in t or "by the extraction." in t and "tag letters" in t])
        # the committed sheet-0 graph: no kind is called the extraction's class, no final element, and every
        # attribution of an item placed by position says so
        sts, _, gr = stm.build(graph("sheet0_graph.json"))
        self.assertFalse([s["text"] for s in sts if "final element" in s["text"]])
        self.assertFalse([s["text"] for s in sts if s["predicate"] == "is_a" and
                          gr.nodes[s["subject"]]["kind"] == "instrument" and "by the extraction" in s["text"]])
        near = {n for n in gr.nodes if gr.attr(n, "parent_method") == "geometry_nearest"}
        self.assertTrue(near)
        for s in sts:
            about = s["object"] if s["predicate"] == "edge:contains" else s["subject"]
            if about in near and "The extraction attributes" in s["text"]:
                self.assertIn("by nearest position on the drawing", s["text"])
        self.assertFalse([s["text"] for s in sts if "moisture" in s["text"]])

    def test_score_reports_each_layer_and_never_a_blend(self):
        rows = [{"statement_id": "p1", "stratum": "pipe", "layer": "pipe", "source_match": "mismatch"},
                {"statement_id": "p2", "stratum": "pipe", "layer": "pipe", "source_match": "match"},
                {"statement_id": "n1", "stratum": "network_pair", "layer": "network_pair", "source_match": "match"},
                {"statement_id": "n2", "stratum": "network_pair", "layer": "network_pair", "source_match": "match"},
                {"statement_id": "n3", "stratum": "network_pair", "layer": "", "source_match": "match"}]
        r = stm.score(rows, layer_of_id={"n3": "network_pair"})
        sm = r["source_match"]
        self.assertIsNone(sm["overall"])
        self.assertIn("2 relationship layers", sm["overall_note"])
        self.assertEqual(sm["by_layer"]["pipe"]["overall"]["error_rate"], 0.5)
        self.assertEqual(sm["by_layer"]["network_pair"]["overall"]["checked"], 3)  # the layer came from the lookup
        self.assertEqual(sm["by_layer"]["network_pair"]["overall"]["error_rate"], 0.0)
        r = stm.score(rows, {"pipe": 160, "network_pair": 345}, {"n3": "network_pair"})
        self.assertEqual(r["source_match"]["by_layer"]["pipe"]["weighted_by_population"], 0.5)
        one = stm.score(rows[:2])  # one layer: its numbers are the sheet's numbers
        self.assertEqual(one["source_match"]["overall"]["error_rate"], 0.5)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "sheet.csv"
            with open(f, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=stm.SHEET_COLUMNS)
                w.writeheader()
                for row in rows:
                    w.writerow({k: row.get(k, "") for k in stm.SHEET_COLUMNS})
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(stm.main(["score", str(f)]), 0)
            self.assertIn("[pipe]", out.getvalue())
            self.assertIn("no blended rate", out.getvalue())

    def test_layered_sample_gives_every_layer_its_own_stratum(self):
        sts, _, _ = stm.build(graph("sheet0_graph.json"))
        pool = [dict(s, stratum=s["layer"]) for s in sts]
        picked, strata = stm.draw_sample(pool, 75, 1031, 15)  # five layers, 15 each (sample_layers_r2)
        self.assertEqual({x["stratum"]: x["sampled"] for x in strata},
                         {"item": 15, "network": 15, "network_pair": 15, "pipe": 15, "non_pipe": 15})
        self.assertTrue(all(x["rank"] is None and x["rank_label"] == stm.LAYERS[x["stratum"]] for x in strata))

    def test_apply_never_changes_a_value_and_records_events(self):
        g = graph("bayer_graph.json")
        sts, _, _ = stm.build(g)
        by = {s["text"]: s for s in sts}
        sp = by["TIC-104 is set to hold 135 C (its setpoint)."]
        psv = by["PSV-101 protects the residue treater RT-1 against overpressure."]
        uom = by["PT-101 reads in psig."]
        rows = [{"statement_id": sp["id"], "source_match": "mismatch", "plant_truth": "", "reviewer": "R1"},
                {"statement_id": psv["id"], "source_match": "match", "plant_truth": "confirmed", "reviewer": ""},
                {"statement_id": uom["id"], "source_match": "match", "plant_truth": "", "reviewer": "R2"},
                {"statement_id": by["PT-101 is an instrument."]["id"], "source_match": "unclear",
                 "plant_truth": "confirmed", "reviewer": "R1"},
                {"statement_id": "st-000000000000", "source_match": "match", "plant_truth": "", "reviewer": "R1"}]
        out, applied, refused = stm.apply(g, rows, reviewer="R9", date="2026-10-29", record="sheet.csv")
        self.assertEqual(len(applied), 3)
        self.assertEqual(len(refused), 2)
        self.assertEqual(gx.problems(out), [])
        before = {(n["id"], c["name"]): c["value"] for n in g["nodes"] for c in n["attributes"]}
        after = {(n["id"], c["name"]): c["value"] for n in out["nodes"] for c in n["attributes"]}
        self.assertEqual(before, after)
        self.assertEqual([(e["from"], e["to"], e["type"]) for e in g["edges"]],
                         [(e["from"], e["to"], e["type"]) for e in out["edges"]])
        nodes = {n["id"]: n for n in out["nodes"]}
        tic = {c["name"]: c for c in nodes["TIC-104"]["attributes"]}
        self.assertEqual(tic["setpoint.value"]["status"], "rejected")
        self.assertEqual(tic["setpoint.uom"]["status"], "rejected")
        pt = {c["name"]: c for c in nodes["PT-101"]["attributes"]}
        self.assertEqual(pt["uom"]["status"], "unverified")  # a source match alone confirms nothing in the plant
        self.assertEqual(pt["uom"]["checks"][0]["source_match"], "match")
        edge = next(e for e in out["edges"] if e["type"] == "protects" and e["from"] == "PSV-101")
        self.assertEqual(edge["status"], "confirmed")
        ev = [e for e in out["events"] if e["type"] == "statement_review"]
        self.assertEqual(len(ev), 3)
        self.assertEqual({e["by"] for e in ev}, {"R1", "R2", "R9"})
        self.assertTrue(all(e["on"] == "2026-10-29" for e in ev))
        self.assertEqual(g["events"], [])  # the input graph is untouched

    def test_render_refuses_a_non_graph_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "model.json"
            bad.write_text(json.dumps({"meta": {}, "units": []}), encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = stm.main(["render", str(bad), "--out", str(Path(d) / "out")])
            self.assertEqual(rc, 2)
            self.assertIn("not a twin-graph-1 graph", err.getvalue())
            self.assertFalse((Path(d) / "out" / "statements.json").exists())

    def test_render_sample_score_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(stm.main(["render", str(EX / "bayer_graph.json"), "--out", str(out)]), 0)
                self.assertEqual(stm.main(["sample", str(out / "statements.json"), "--n", "20", "--seed", "3",
                                           "--out", str(Path(d) / "s" / "sample.json")]), 0)
            doc = json.loads((out / "statements.json").read_text(encoding="utf-8"))
            self.assertTrue(all(s["machine_check"]["result"] in ("matches its model field", "not checked")
                                for s in doc["statements"]))
            self.assertNotIn("Users/", (out / "statements.json").read_text(encoding="utf-8"))
            with open(Path(d) / "s" / "sample.csv", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 20)
            self.assertEqual(tuple(rows[0].keys()), stm.SHEET_COLUMNS)
            self.assertTrue(all(r["source_match"] == "" and r["plant_truth"] == "" for r in rows))

    def test_committed_pilot_is_unreviewed_and_sampled_as_stated(self):
        for sub in ("sheet0", "bayer"):
            d = PILOT / sub
            if not d.exists():
                self.skipTest("pilot not committed")
            doc = json.loads((d / "statements.json").read_text(encoding="utf-8"))
            ids = {x["id"] for x in doc["statements"]}
            s = json.loads((d / "sample_60.json").read_text(encoding="utf-8"))
            # sample_60 measured the version before the line layers existed; it is never redrawn. Its population
            # is today's item and network_pair statements (statement ids don't depend on wording), until a fix
            # withdraws a statement it holds: then it stays as drawn, and only the withdrawn ones may be missing.
            old = [x for x in doc["statements"] if x.get("layer") in ("item", "network_pair", "stream")]
            # The model's own meta notes became plant claims after sample_60 was drawn (graph_export, round 4):
            # they were not in its population, so they are left out of the redraw.
            old = [x for x in old if not (x["subject"] == "PLANT" and x["type"] == "attribute")]
            if (sub, "sample_60") in WITHDRAWN:
                self.assertEqual({(x["subject"], x["predicate"]) for x in s["statements"] if x["id"] not in ids},
                                 WITHDRAWN[(sub, "sample_60")])
            else:
                again, strata = stm.draw_sample(old, 60, s["seed"])
                self.assertEqual(sorted(x["id"] for x in again), sorted(x["id"] for x in s["statements"]))
                self.assertEqual(strata, s["strata"])
            fresh, _, _ = stm.build(graph(Path(doc["graph"]).name))
            self.assertEqual([x["id"] for x in fresh], [x["id"] for x in doc["statements"]])
            with open(d / "sample_60.csv", encoding="utf-8", newline="") as f:
                self.assertTrue(all(r["source_match"] == "" and r["plant_truth"] == "" for r in csv.DictReader(f)))
            for x in s["statements"]:
                for rel in ([x["evidence"]["image"]] if x["evidence"].get("image") else []):
                    self.assertTrue((d / rel).exists(), rel)
            # sample_layers (seed 1030) is what the 2026-10-29 layered review measured: kept as drawn, from the
            # statements of that day. sample_layers_r2 (seed 1031) is what the r2 review measured; the fixes it led
            # to withdrew one of its statements, so it too is kept as drawn now.
            for name, today in (("sample_layers", False), ("sample_layers_r2", (sub, "sample_layers_r2") not in
                                                                                 WITHDRAWN)):
                lay = d / f"{name}.json"
                if not lay.exists():
                    continue
                s = json.loads(lay.read_text(encoding="utf-8"))
                self.assertEqual(len(s["statements"]), s["n"])
                if (sub, name) in WITHDRAWN:
                    self.assertEqual({(x["subject"], x["predicate"]) for x in s["statements"] if x["id"] not in ids},
                                     WITHDRAWN[(sub, name)])
                if today:
                    pool = [dict(x, stratum=x["layer"]) for x in doc["statements"]]
                    again, strata = stm.draw_sample(pool, s["n"], s["seed"], s["floor"])
                    self.assertEqual(sorted(x["id"] for x in again), sorted(x["id"] for x in s["statements"]))
                    self.assertEqual(strata, s["strata"])
                with open(d / f"{name}.csv", encoding="utf-8", newline="") as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(sorted(r["statement_id"] for r in rows), sorted(x["id"] for x in s["statements"]))
                self.assertTrue(all(r["source_match"] == "" and r["plant_truth"] == "" and r["layer"] for r in rows))
                for x in s["statements"]:
                    for rel in ([x["evidence"]["image"]] if x["evidence"].get("image") else []):
                        self.assertTrue((d / rel).exists(), rel)


if __name__ == "__main__":
    unittest.main()
