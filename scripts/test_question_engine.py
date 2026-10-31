"""The question engine: the catalog is well-formed and every question cites a known source or says it has none,
the committed opportunity-screen examples regenerate exactly, known findings appear and known false triggers stay
quiet, the three evidence states come out right, and no output carries a currency symbol or a computed figure.
Stdlib only."""
import io
import copy
import contextlib
import json
import os
import re
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import question_engine as qe  # noqa: E402
import graph_export as gx  # noqa: E402

EX = ROOT / "examples" / "opportunity-screen"
CAT = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
RUNS = {
    "te": ["--model", "data/te_process_model.json", "--loops", "examples/loop-audit/te_loops.csv"],
    "bayer": ["--model", "data/bayer_rt/process_model.json"],
    "open100": ["--model", "out/twin/r2-tiles-trace/codex/plant_model.json", "--schedule",
                "data/open100_equipment_schedule.json", "--schedule",
                "examples/opportunity-screen/open100_schedule_fields.json"],
    "food": ["--model", "examples/opportunity-screen/food_plant_model.json"],
    "millard/screen": ["--model", "examples/opportunity-screen/millard/model.json", "--question", "E30"],
}
ROLLUP = ["examples/opportunity-screen/food", "examples/opportunity-screen/bayer"]
# Refrigeration, oven, dryer and fryer questions (added 2026-10-29 from a food manufacturer's walkthrough)
NEW = {"E27", "E28", "E29", "E30", "E31", "E32", "H5", "H6", "C11", "C12"}
SELECTOR_KEYS = {"kind", "type", "type_text", "isa", "variable", "text", "text_all", "not_text", "tagged",
                 "control_valve", "fact_C_min", "fact_C_max", "schedule_field"}
CLAUSE_KEYS = {"select", "relation", "max_hops", "as", "twin_only", "hand_only", "anchor_kind"}
RELATIONS = {"same_unit", "same_stream", "same_unit_same_medium", "other_unit", "discharge_side", "near", "drives",
             "reads", "anywhere", "linked"}
PLACES = {"historian", "dcs", "nameplate", "vendor", "maintenance", "records", "bills", "walkdown", "text"}
CURRENCY = re.compile(r"[$€£¥]|\bUSD\b|\d[\d,.]*\s*(dollars?|cents?)\b", re.I)


def load(name):
    return json.loads((EX / name / "questions.json").read_text(encoding="utf-8"))


def finding(doc, fid):
    return next((f for f in doc["questions"] if f["id"] == fid), None)


def ids(doc):
    return {f["id"] for f in doc["questions"]}


def run(args, out):
    old = sys.stdout
    try:
        sys.stdout = open(Path(out) / "log.txt", "w", encoding="utf-8")
        rc = qe.main([*args, "--out", str(out)])
    finally:
        sys.stdout.close()
        sys.stdout = old
    return rc, json.loads((Path(out) / "questions.json").read_text(encoding="utf-8"))


class Catalog(unittest.TestCase):
    def test_questions_are_well_formed(self):
        seen = set()
        for q in CAT["questions"]:
            with self.subTest(q=q["id"]):
                self.assertNotIn(q["id"], seen)
                seen.add(q["id"])
                self.assertIn(q["family"], CAT["families"])
                for key in ("question", "applies_when", "evidence_fields", "data_requests", "decision_rule",
                            "typical_benefit"):
                    self.assertTrue(q.get(key), key)
                aw = q["applies_when"]
                anchors = aw["anchor"] if isinstance(aw["anchor"], list) else [aw["anchor"]]
                for sel in anchors:
                    self.assertLessEqual(set(sel), SELECTOR_KEYS)
                for part in ("with", "without", "also_show"):
                    for cl in aw.get(part, []):
                        self.assertLessEqual(set(cl), CLAUSE_KEYS)
                        self.assertLessEqual(set(cl["select"]), SELECTOR_KEYS)
                        self.assertIn(cl.get("relation", "same_unit"), RELATIONS)
                self.assertIn(aw.get("group_by", "unit"), ("unit", "item", "model"))
                for r in q["data_requests"]:
                    self.assertTrue(r["item"] and r["how"] and r["where"])
                    for pl in r["where"]:
                        self.assertIn(pl["place"], PLACES)

    def test_every_question_cites_a_known_source_or_says_none(self):
        for q in CAT["questions"]:
            tb = q["typical_benefit"]
            with self.subTest(q=q["id"]):
                for s in tb["source"]:
                    self.assertIn(s, CAT["sources"])
                if not tb["source"]:
                    self.assertRegex(tb["wording"].lower(), r"\bno\b.*\bsource\b")
        for key, s in CAT["sources"].items():
            self.assertTrue(s["title"] and s["url"].startswith("https://") and s["license"], key)

    def test_catalog_carries_no_currency(self):
        prose = [CAT["about"], CAT["source_notes"]]  # trigger regexes use $ as an anchor, so check the prose only
        for q in CAT["questions"]:
            prose += [q["question"], q["decision_rule"], q.get("limits") or "", q["typical_benefit"]["wording"],
                      q["typical_benefit"].get("arc") or ""]
            prose += [r["item"] + r["how"] + json.dumps(r["where"]) for r in q["data_requests"]]
        self.assertIsNone(CURRENCY.search("\n".join(prose)))

    def test_counts_by_family(self):
        fam = {}
        for q in CAT["questions"]:
            fam[q["family"]] = fam.get(q["family"], 0) + 1
        self.assertEqual(fam, {"energy": 30, "heat_grade": 6, "metering": 2, "controls": 8, "safety_question": 2,
                               "emissions": 2})

    def test_new_questions_quote_a_page_of_a_checked_source(self):
        """Each refrigeration / oven / dryer / fryer question quotes its source with a page, and the source records
        which file its quotes were checked against."""
        qs = {q["id"]: q for q in CAT["questions"]}
        self.assertEqual(NEW - set(qs), set())
        for qid in NEW:
            tb = qs[qid]["typical_benefit"]
            with self.subTest(q=qid):
                self.assertTrue(tb["source"])
                self.assertRegex(tb["wording"], r"p\. \d+")
                self.assertIn('"', tb["wording"])
                for s in tb["source"]:
                    self.assertIn("checked", CAT["sources"][s], s)


class Examples(unittest.TestCase):
    def test_committed_examples_regenerate_exactly(self):
        for name, args in RUNS.items():
            with self.subTest(model=name), tempfile.TemporaryDirectory() as tmp:
                run(args, tmp)
                for f in ("questions.json", "screen.md"):
                    self.assertEqual((Path(tmp) / f).read_text(encoding="utf-8"),
                                     (EX / name / f).read_text(encoding="utf-8"), f"{name}/{f}")

    def test_no_currency_no_local_path_and_benefits_quoted_verbatim(self):
        wording = {q["id"]: q["typical_benefit"]["wording"] for q in CAT["questions"]}
        for name in RUNS:
            doc = load(name)
            for f in ("questions.json", "screen.md"):
                text = (EX / name / f).read_text(encoding="utf-8")
                self.assertIsNone(CURRENCY.search(text), f"{name}/{f}")
                self.assertNotIn("Users/", text)
                self.assertNotIn("Users\\", text)
            for fd in doc["questions"]:
                self.assertEqual(fd["typical_benefit"]["wording"], wording[fd["question_id"]])
                self.assertEqual(fd["status"], "asked")

    def test_engine_adds_no_figures_of_its_own(self):
        """Strip every string the catalog supplies; what the engine wrote itself must carry no energy, money or
        savings figure (numbers in tags, sheet numbers and model facts are fine)."""
        figure = re.compile(r"\d[\d,.]*\s*(%|kWh|MWh|MMBtu|Btu|kW\b|hp\b|lb/hr|per year|/yr|years?\b|yr\b)", re.I)
        strings = []
        for q in CAT["questions"]:
            strings += [q["typical_benefit"]["wording"], q["decision_rule"], q.get("limits") or "",
                        q["typical_benefit"].get("arc") or ""]
        for name in RUNS:
            text = (EX / name / "screen.md").read_text(encoding="utf-8")
            for s in sorted(strings, key=len, reverse=True):
                if s:
                    text = text.replace(s, "")
            self.assertIsNone(figure.search(text), (name, figure.search(text) and figure.search(text).group(0)))

    def test_graph_export_accepts_each_questions_file(self):
        models = {"te": "data/te_process_model.json", "bayer": "data/bayer_rt/process_model.json",
                  "open100": "out/twin/r2-tiles-trace/codex/plant_model.json",
                  "food": "examples/opportunity-screen/food_plant_model.json"}
        for name, model in models.items():
            g = gx.build(ROOT / model, questions=EX / name / "questions.json")
            self.assertEqual(gx.problems(g), [], name)
            self.assertEqual(g["counts"]["questions"], len(load(name)["questions"]))


class ExpectedFindings(unittest.TestCase):
    def test_tennessee_eastman(self):
        doc = load("te")
        e6 = finding(doc, "E6@K-101")
        self.assertIn("FV-105", {a["id"] for a in e6["assets"]})
        e18 = finding(doc, "E18@model")
        self.assertTrue({"TV-121", "FV-117", "FV-119"} <= {a["id"] for a in e18["assets"]})
        self.assertIn("TT-122", {a["id"] for a in finding(doc, "H4@E-101")["assets"]})
        self.assertIn("FT-119", {a["id"] for a in finding(doc, "E18@model")["assets"]})
        self.assertIsNotNone(finding(doc, "H2@C-101"))
        # stripper steam is metered (FT-119); condenser and reactor cooling water are not
        self.assertNotIn("C1@C-101", ids(doc))
        self.assertEqual({"C1@R-101", "C1@E-101"}, {i for i in ids(doc) if i.startswith("C1@")})
        # no pumps in this model: no pump questions; a process recycle compressor is not an air compressor
        for q in ("E1", "E2", "E3", "E4", "E19", "E20", "E21", "E22", "E23", "C7"):
            self.assertIn(q, doc["did_not_fire"])
        # loop list read: the uncontrolled measurements are exactly the eight without a loop
        c2 = finding(doc, "C2@model")
        self.assertEqual({a["id"] for a in c2["assets"]},
                         {"FT-106", "PT-107", "TT-111", "PT-113", "FT-114", "PT-116", "JT-120", "TT-122"})
        # historian names come from the model's recorded-signal index
        e6_text = json.dumps(e6)
        self.assertIn("XMV(5)", e6_text)

    def test_bayer(self):
        doc = load("bayer")
        e18 = {a["id"] for a in finding(doc, "E18@model")["assets"]}
        self.assertTrue({"stream:U1", "stream:U2"} <= e18)
        h4 = finding(doc, "H4@E-3")
        self.assertTrue(any(e["role"] == "on drawing" and "cooling_water_C = 80" in e["text"] for e in h4["evidence"]))
        self.assertIn("TIC-104", {a["id"] for a in finding(doc, "C6@TV-104C")["assets"]})
        self.assertIsNotNone(finding(doc, "E1@P-1"))
        # named false triggers: the recirculation loop is the process loop, not a pump bypass or minimum-flow
        # line; "alternate fuel tank" is not a fuel supply
        self.assertNotIn("E2@P-1", ids(doc))
        self.assertNotIn("E3@P-1", ids(doc))
        self.assertNotIn("C1@RT-1", ids(doc))
        # the steam heater is metered (FT-106); the 80 C water cooler is not
        self.assertEqual({i for i in ids(doc) if i.startswith("C1@")}, {"C1@E-3"})

    def test_open100(self):
        doc = load("open100")
        h1 = finding(doc, "H1@S4-TK001")
        tags = {a["tag"] for a in h1["assets"]}
        self.assertTrue({"ESS-HTR-180", "PCV-14011", "TCV-16013"} <= tags)
        self.assertIn("MSBV-1407", {a["tag"] for a in finding(doc, "H1@S0-OP005")["assets"]})
        self.assertIsNotNone(finding(doc, "H2@S4-OP005"))
        # blank schedule fields become data requests naming the field and sheet
        e4 = finding(doc, "E4@S2-PU001")
        req = e4["data_requests"][0]
        self.assertEqual(req["state"], "blank_on_drawing")
        self.assertIn("the blank HP field on the sheet 2 equipment schedule, entry CND-PU-162", req["where"])
        # named false triggers: a superheater is not a desuperheater; the ACC pumps reach LCV-1501 only through
        # the air-cooled condenser (they are vacuum pumps on the drawing); a drains blowdown tank vent is not boiler
        # blowdown; the pressurizer electric heater has no stated low temperature and is excluded anyway
        self.assertNotIn("H1@S0-TK001", ids(doc))
        for pump in ("S1-PU013", "S1-PU014", "S1-PU015"):
            self.assertNotIn(f"E1@{pump}", ids(doc))
        self.assertIn("E13", doc["did_not_fire"])
        self.assertIn("H3", doc["did_not_fire"])
        self.assertIn("RCS-EX-105", sum(doc["left_out"].values(), []))
        # no controller list in an extracted drawing: controller questions are reported as not checked
        self.assertEqual({n["question_id"] for n in doc["not_checked"]}, {"C2", "C6"})

    def test_new_questions_stay_quiet_on_the_chemical_and_power_examples(self):
        """No refrigerant, oven, dryer or fryer is drawn in TE, Bayer or OPEN100: TE's recycle compressor K-101, its
        condenser E-101, Bayer's vent condenser E-1 and OPEN100's air-cooled condenser must not read as
        refrigeration plant."""
        for name in ("te", "bayer", "open100"):
            doc = load(name)
            with self.subTest(model=name):
                self.assertEqual(NEW - set(doc["did_not_fire"]), set())
                self.assertFalse({f["question_id"] for f in doc["questions"]} & NEW)

    def test_food_plant(self):
        doc = load("food")
        found = ids(doc)
        for fid in ("E27@C-201", "E28@model", "E29@K-201", "E29@K-202", "E30@EV-201", "H5@model", "C12@model",
                    "E31@D-301", "E31@O-302", "E32@D-301", "E32@F-303", "C11@D-301", "C11@O-302", "H6@D-301",
                    "H6@O-302"):
            self.assertIn(fid, found)
        # anti-triggers, each drawn on purpose: K-203 has a drive; EV-202 defrosts on demand (coil dP); the oven has
        # a flue O2 analyser; the fryer's exhaust goes to a vapour condenser heat recovery exchanger.
        # K-201's stated power reading remains a candidate; actual real-input suitability stays open.
        for fid in ("E29@K-203", "E30@EV-202", "E32@O-302", "E31@F-303", "H6@F-303"):
            self.assertNotIn(fid, found)
        c12 = {a["id"] for a in finding(doc, "C12@model")["assets"]}
        self.assertEqual(c12 & {"K-201", "K-202", "K-203"}, {"K-201", "K-202", "K-203"})
        self.assertIn("JT-201", c12)
        # the instrument air compressor and its refrigerated air dryer are not refrigeration plant or a process dryer
        for f in doc["questions"]:
            if f["question_id"] in NEW:
                self.assertFalse({a["id"] for a in f["assets"]} & {"AC-501", "AD-502"}, f["id"])
        self.assertIn("E19@AC-501", found)  # ...while the compressed air questions do ask about the air compressor
        self.assertFalse({i for i in found if i.split("@")[0] in ("E19", "E20", "E21", "E22", "E23") and
                          i.split("@")[1].startswith("K-")})
        # data requests name the quantities and where they live
        e27 = {r["item"]: r for r in finding(doc, "E27@C-201")["data_requests"]}
        head = next(r for k, r in e27.items() if k.startswith("Head (discharge) pressure"))
        self.assertIn("PT-203", " ".join(head["where"]))
        self.assertTrue(any("head pressure setpoint" in w for w in head["where"]))
        e30 = " ".join(json.dumps(r) for r in finding(doc, "E30@EV-201")["data_requests"])
        self.assertIn("defrost", e30.lower())
        e31 = {r["item"]: r for r in finding(doc, "E31@D-301")["data_requests"]}
        self.assertIn("TT-304", " ".join(e31["Exhaust temperature and flow"]["where"]))

    def test_new_triggers_ignore_look_alikes(self):
        """A process condenser on cooling water, a recycle gas compressor, an instrument air compressor, a
        refrigerated compressed air dryer, a desiccant air dryer and a nuclear steam dryer are not refrigeration
        plant, ovens or dryers."""
        with tempfile.TemporaryDirectory() as tmp:
            m = {"meta": {"title": "look-alikes"}, "instruments": [], "final_elements": [],
                 "units": [{"id": "E-1", "name": "Overhead condenser (cooling water)", "type": "condenser"},
                           {"id": "K-1", "name": "Recycle gas compressor", "type": "compressor"},
                           {"id": "K-2", "name": "Instrument air compressor", "type": "compressor"},
                           {"id": "D-1", "name": "Refrigerated compressed air dryer", "type": "dryer"},
                           {"id": "D-2", "name": "Desiccant air dryer", "type": "dryer"},
                           {"id": "D-3", "name": "Steam dryer", "type": "dryer"},
                           {"id": "W-1", "name": "Hot water heater for CIP", "type": "heater"}],
                 "streams": [{"id": "U1", "name": "Natural gas", "from": "BL", "to": "W-1", "utility": True}]}
            (Path(tmp) / "m.json").write_text(json.dumps(m), encoding="utf-8")
            _, doc = run(["--model", str(Path(tmp) / "m.json")], tmp)
        self.assertFalse({f["question_id"] for f in doc["questions"]} & NEW, ids(doc))
        # tightened with them: an air dryer is not an air compressor (E19-E23 fired on it as "compressed air")
        self.assertEqual({i for i in ids(doc) if i.startswith(("E19@", "E22@", "E23@"))},
                         {"E19@K-2", "E22@K-2", "E23@K-2"} & ids(doc))
        self.assertIn("E23@K-2", ids(doc))

    def test_a_linked_heat_recovery_exchanger_only_suppresses_its_own_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = {"meta": {"title": "two dryers"}, "instruments": [], "final_elements": [],
                 "units": [{"id": "D-1", "name": "Product dryer", "type": "dryer"},
                           {"id": "D-2", "name": "Product dryer", "type": "dryer"},
                           {"id": "HX-1", "name": "Exhaust air heat recovery exchanger", "type": "heat_exchanger"}],
                 "streams": [{"id": "S1", "name": "Dryer exhaust", "from": "D-1", "to": "HX-1"},
                             {"id": "S2", "name": "Dryer exhaust to atmosphere", "from": "D-2", "to": "ATM"}]}
            (Path(tmp) / "m.json").write_text(json.dumps(m), encoding="utf-8")
            _, doc = run(["--model", str(Path(tmp) / "m.json"), "--question", "E31"], tmp)
        self.assertEqual(ids(doc), {"E31@D-2"})


class Rollup(unittest.TestCase):
    def roll(self, dirs, out):
        old = sys.stdout
        try:
            sys.stdout = open(Path(out) / "log.txt", "w", encoding="utf-8")
            rc = qe.main([*sum((["--rollup", d] for d in dirs), []), "--out", str(out)])
        finally:
            sys.stdout.close()
            sys.stdout = old
        return rc

    def test_committed_rollup_regenerates_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.roll(ROLLUP, tmp), 0)
            for f in ("rollup.json", "rollup.md"):
                self.assertEqual((Path(tmp) / f).read_text(encoding="utf-8"),
                                 (EX / "rollup-food-bayer" / f).read_text(encoding="utf-8"), f)

    def test_rollup_content(self):
        doc = json.loads((EX / "rollup-food-bayer" / "rollup.json").read_text(encoding="utf-8"))
        self.assertEqual([s["site"] for s in doc["sites"]], ["food", "bayer"])
        by = {q["question_id"]: q for q in doc["questions"]}
        # every finding of every site is accounted for, once
        for site in ("food", "bayer"):
            src = load(site)
            got = sorted(f["finding_id"] for q in doc["questions"] for s in q["sites"] if s["site"] == site
                         for f in s["findings"])
            self.assertEqual(got, sorted(f["id"] for f in src["questions"]), site)
        # a question asked at both sites lists both, with the assets, and comes before single-site questions
        c9 = by["C9"]
        self.assertEqual([s["site"] for s in c9["sites"]], ["food", "bayer"])
        self.assertIn("P-1", {a["tag"] for s in c9["sites"] for f in s["findings"] for a in f["assets"]})
        order = [len(q["sites"]) for q in doc["questions"]]
        self.assertEqual(order, sorted(order, reverse=True))
        # data requests are combined by item: one entry per item, each site's places kept and deduplicated
        for q in doc["questions"]:
            items = [r["item"] for r in q["data_requests"]]
            self.assertEqual(len(items), len(set(items)), q["question_id"])
            for r in q["data_requests"]:
                for s in r["sites"]:
                    places = s["where"] + [w for b in s["where_by_finding"] for w in b["where"]]
                    self.assertTrue(places)
                    self.assertEqual(len(s["where"]), len(set(s["where"])))
                    for b in s["where_by_finding"]:
                        self.assertFalse(set(b["where"]) & set(s["where"]))
        # places shared by a site's findings are listed once; each meter-less valve stays with its own finding
        c1 = {r["item"]: r for r in by["C1"]["data_requests"]}["Utility flow to this user"]
        food = next(s for s in c1["sites"] if s["site"] == "food")
        self.assertTrue(any(w.startswith("a walkdown: clamp-on") for w in food["where"]))
        self.assertEqual({b["finding_id"] for b in food["where_by_finding"]}, {"C1@O-302", "C1@F-303", "C1@WH-401"})
        self.assertEqual([s["site"] for s in by["E27"]["sites"]], ["food"])
        self.assertIn("bayer", by["E27"]["quiet_at"])
        text = (EX / "rollup-food-bayer" / "rollup.md").read_text(encoding="utf-8")
        self.assertIsNone(CURRENCY.search(text))
        self.assertIsNone(CURRENCY.search(json.dumps(doc)))
        self.assertNotIn("Users/", text)

    def test_rollup_refuses_bad_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            err, old = io.StringIO(), sys.stderr
            sys.stderr = err
            try:
                rc = qe.main(["--rollup", str(Path(tmp) / "nope"), "--rollup", ROLLUP[0], "--out", tmp])
                self.assertEqual(rc, 2)
                self.assertIn("no questions.json", err.getvalue())
                (Path(tmp) / "x").mkdir()
                (Path(tmp) / "x" / "questions.json").write_text('{"schema": "other"}', encoding="utf-8")
                rc = qe.main(["--rollup", str(Path(tmp) / "x"), "--rollup", ROLLUP[0], "--out", tmp])
                self.assertEqual(rc, 2)
                self.assertIn("not an opportunity screen", err.getvalue())
                rc = qe.main(["--rollup", ROLLUP[0], "--rollup", ROLLUP[0], "--out", tmp])
                self.assertEqual(rc, 2)
                self.assertIn("named twice", err.getvalue())
            finally:
                sys.stderr = old


class EvidenceStates(unittest.TestCase):
    def tiny_twin(self, tmp, fields):
        def prov(sheet):
            return [{"sheet": sheet}]
        model = {"meta": {"model_kind": "extracted_twin", "title": "tiny"},
                 "systems": [{"id": "SYS-1", "system_code": "CWS"}],
                 "units": [{"id": "S1-PU001", "tag": "P�9", "class": "pump", "sheets": ["1"], "system": "SYS-1"}],
                 "instruments": [{"id": "S1-IN001", "tag": "FCV 9", "isa_letters": "FCV", "parent": "S1-VL001",
                                  "instrument_kind": "final element (valve)", "provenance": prov("1"),
                                  "system": "SYS-1"}],
                 "line_items": [{"id": "S1-VL001", "class": "valve", "provenance": prov("1"), "system": "SYS-1"}],
                 "offpage_connectors": [],
                 "streams": [{"id": "L1", "from": "S1-PU001", "to": "S1-VL001", "direction": "unknown"}]}
        sched = {"sheets": {"1": [{"tag": "P-9", "service": "WATER PUMP", "fields": fields}]}}
        (Path(tmp) / "m.json").write_text(json.dumps(model), encoding="utf-8")
        (Path(tmp) / "s.json").write_text(json.dumps(sched), encoding="utf-8")
        return ["--model", str(Path(tmp) / "m.json"), "--schedule", str(Path(tmp) / "s.json")]

    def test_three_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.tiny_twin(tmp, {"CAPACITY": None, "DISCHARGE": "XXX", "RPM": "1780", "HP": "40"})
            _, doc = run(args, tmp)
            e1 = finding(doc, "E1@S1-PU001")
            reqs = {r["item"]: r for r in e1["data_requests"]}
            rated = reqs["Pump rated flow and head"]
            self.assertEqual(rated["state"], "blank_on_drawing")
            self.assertIn("the blank CAPACITY field on the sheet 1 equipment schedule, entry P-9", rated["where"])
            self.assertTrue(any("DISCHARGE field (printed as 'XXX')" in w for w in rated["where"]))
            # both motor fields are filled in: quoted as evidence, no request
            self.assertNotIn("Motor rating and speed", reqs)
            on = [e["text"] for e in e1["evidence"] if e["role"] == "on drawing"]
            self.assertTrue(any("HP = 40" in t for t in on) and any("RPM = 1780" in t for t in on))
            # not on the drawing at all: the request names where it lives instead
            self.assertEqual(reqs["Static head versus friction head"]["state"], "not_on_drawing")
            self.assertTrue(reqs["Static head versus friction head"]["where"][0].startswith("a walkdown"))

    def test_speed_control_suppresses_the_drive_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.tiny_twin(tmp, {"HP": None})
            m = json.loads((Path(tmp) / "m.json").read_text(encoding="utf-8"))
            m["instruments"].append({"id": "S1-IN002", "tag": "SC 9", "isa_letters": "SC", "parent": "S1-PU001",
                                     "instrument_kind": "measurement / control", "provenance": [{"sheet": "1"}]})
            (Path(tmp) / "m.json").write_text(json.dumps(m), encoding="utf-8")
            _, doc = run(args, tmp)
            self.assertNotIn("E1@S1-PU001", ids(doc))
            self.assertIn("E4@S1-PU001", ids(doc))

    def test_model_with_no_pumps_gets_no_pump_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = {"meta": {"title": "no pumps"}, "units": [{"id": "T-1", "name": "Tank", "type": "tank"}],
                 "streams": [], "instruments": [{"tag": "LT-1", "unit": "T-1", "variable": "level"}],
                 "final_elements": [{"tag": "LV-1", "unit": "T-1"}], "controllers": []}
            (Path(tmp) / "m.json").write_text(json.dumps(m), encoding="utf-8")
            _, doc = run(["--model", str(Path(tmp) / "m.json")], tmp)
            pump_qs = {"E1", "E2", "E3", "E4"}
            self.assertFalse({f["question_id"] for f in doc["questions"]} & pump_qs)

    def test_electric_heat_needs_a_stated_low_temperature(self):
        with tempfile.TemporaryDirectory() as tmp:
            def screen(facts):
                m = {"meta": {"title": "heater"}, "streams": [], "instruments": [], "final_elements": [],
                     "units": [{"id": "EH-1", "name": "Electric heater, tank warming", "type": "heater",
                                "facts": facts}]}
                (Path(tmp) / "m.json").write_text(json.dumps(m), encoding="utf-8")
                return run(["--model", str(Path(tmp) / "m.json"), "--question", "H3"], tmp)[1]
            self.assertEqual(ids(screen({"load_temperature_C": 60})), {"H3@EH-1"})
            self.assertEqual(ids(screen({})), set())
            self.assertEqual(ids(screen({"load_temperature_C": 340})), set())

    def test_a_request_stays_open_for_the_fields_not_on_the_drawing(self):
        """Review fix 2: a value found for one part of a multi-part request must not close the whole request."""
        with tempfile.TemporaryDirectory() as tmp:
            args = self.tiny_twin(tmp, {"HP": "40"})  # the schedule prints HP only; RPM is nowhere on the drawing
            _, doc = run(args, tmp)
            reqs = {r["item"]: r for r in finding(doc, "E1@S1-PU001")["data_requests"]}
            motor = reqs["Motor rating and speed"]
            self.assertEqual(motor["already_on_drawing"], ["HP"])
            self.assertEqual(motor["still_needed"], ["RPM"])
            self.assertEqual(motor["state"], "not_on_drawing")


class FieldSubjects(unittest.TestCase):
    """Independent supplies must not answer each other's missing fields."""

    def model(self, supplies):
        return {"meta": {"name": "Fictional independent supplies"},
                "units": [{"id": "H-1", "type": "heater", "name": "Process water heater"}],
                "streams": [], "instruments": [], "controllers": [],
                "final_elements": [{"tag": f"TV-{101 + i}", "unit": "H-1",
                                    "description": f"Steam supply from independent header {i + 1}", "facts": facts}
                                   for i, facts in enumerate(supplies)]}

    def screen(self, model, tmp, catalog=None):
        path = Path(tmp) / "model.json"
        path.write_text(json.dumps(model), encoding="utf-8")
        args = ["--model", str(path), "--question", "H2"]
        if catalog:
            cp = Path(tmp) / "catalog.json"
            cp.write_text(json.dumps(catalog), encoding="utf-8")
            args += ["--catalog", str(cp)]
        doc = run(args, tmp)[1]
        f = finding(doc, "H2@H-1")
        request = next((r for r in f["data_requests"] if r["item"] == "Steam supply pressure and temperature"), None)
        return doc, request

    def test_split_values_and_unknown_siblings_stay_open_with_each_obligation(self):
        p, t = "steam_pressure", "steam_temperature_C"
        cases = [([{p: "8 bar"}, {t: 140}], [[t], [p]]),
                 ([{p: "8 bar", t: 140}, {}], [[], [p, t]]),
                 ([{p: None}, {p: "8 bar", t: 140}], [[p, t], []]),
                 ([{}, {}], [[p, t], [p, t]])]
        for supplies, needed in cases:
            for reverse in (False, True):
                with self.subTest(supplies=supplies, reverse=reverse), tempfile.TemporaryDirectory() as tmp:
                    model = self.model(supplies)
                    if reverse:
                        model["final_elements"].reverse()
                    _, req = self.screen(model, tmp)
                    self.assertIsNotNone(req)
                    self.assertEqual(req["field_scope"], "anchors")
                    by_id = {s["id"]: s for s in req["field_coverage"]}
                    for i, missing in enumerate(needed):
                        self.assertEqual(by_id[f"TV-{101 + i}"]["still_needed"], missing)
                    self.assertEqual(set(req["still_needed"]), set(f for fs in needed for f in fs))
                    md = (Path(tmp) / "screen.md").read_text(encoding="utf-8")
                    for i in range(2):
                        self.assertIn(f"TV-{101 + i} (TV-{101 + i}): supplied", md)

    def test_context_cannot_complete_a_supply_but_is_not_an_extra_subject(self):
        p, t = "steam_pressure", "steam_temperature_C"
        with tempfile.TemporaryDirectory() as tmp:
            model = self.model([{p: "8 bar"}])
            model["units"][0]["facts"] = {t: 140}
            model["instruments"] = [{"tag": "TT-1", "unit": "H-1", "variable": "temperature",
                                      "description": "Process outlet temperature", "facts": {t: 140}}]
            _, req = self.screen(model, tmp)
            self.assertEqual(req["still_needed"], [t])
            self.assertEqual([s["id"] for s in req["field_coverage"]], ["TV-101"])
            model["final_elements"][0]["facts"][t] = 140
            self.assertIsNone(self.screen(model, tmp)[1])

    def test_complete_subjects_zero_false_and_case_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            complete = {"STEAM_PRESSURE": 0, "Steam_Temperature_C": False}
            doc, req = self.screen(self.model([complete, complete]), tmp)
            self.assertIsNone(req)
            evidence = finding(doc, "H2@H-1")["evidence"]
            fields = {e["field"] for e in evidence if e["role"] == "on drawing"}
            self.assertEqual(len(fields), 4)
            self.assertTrue(any(" = False" in e["text"] for e in evidence))

    def test_schedule_empty_strings_are_blank_without_losing_zero_false(self):
        for value in (None, "", "  ", "XXX", 0, False):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                args = EvidenceStates().tiny_twin(tmp, {"hp": value, "rpm": 1780})
                _, doc = run(args, tmp)
                f = finding(doc, "E1@S1-PU001")
                req = next((r for r in f["data_requests"] if r["item"] == "Motor rating and speed"), None)
                if value is False or value == 0:
                    self.assertIsNone(req)
                else:
                    self.assertEqual(req["state"], "blank_on_drawing")
                    self.assertEqual(req["still_needed"], ["HP"])

    def test_unit_scope_requires_actual_group_owner_and_also_needs_remains_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = copy.deepcopy(CAT)
            q = next(q for q in catalog["questions"] if q["id"] == "H2")
            r = q["data_requests"][0]
            r["field_scope"] = "unit"
            model = self.model([{}, {}])
            model["units"][0]["facts"] = {"steam_pressure": "8 bar", "steam_temperature_C": 140}
            self.assertIsNone(self.screen(model, tmp, catalog)[1])
            r["also_needs"] = ["Operating hours"]
            _, req = self.screen(model, tmp, catalog)
            self.assertEqual(req["still_needed"], ["Operating hours"])
            # Item grouping has no selected owning unit: proximity is not an ownership contract.
            q["applies_when"]["group_by"] = "item"
            path = Path(tmp) / "catalog.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            _, doc = run(["--model", str(Path(tmp) / "model.json"), "--question", "H2", "--catalog", str(path)], tmp)
            for f in doc["questions"]:
                req = f["data_requests"][0]
                self.assertEqual(req["field_coverage"], [])
                self.assertEqual(req["still_needed"], r["fields"] + ["Operating hours"])
                self.assertIn("No owning equipment unit", req["scope_note"])

    def test_rollup_keeps_scope_and_missing_fields_per_site_and_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            site = base / "site"
            site.mkdir()
            _, req = self.screen(self.model([{"steam_pressure": "8 bar"}, {"steam_temperature_C": 140}]), site)
            doc = qe.rollup([f"A={site}", f"B={site}"], CAT)
            r = doc["questions"][0]["data_requests"][0]
            for s in r["sites"]:
                detail = s["coverage_by_finding"][0]
                self.assertEqual(detail["field_coverage"], req["field_coverage"])
                self.assertEqual(detail["field_scope"], "anchors")
            md = qe.render_rollup_md(doc, CAT)
            self.assertEqual(md.count("TV-101 (TV-101): supplied steam_pressure; still needed steam_temperature_C (absent)"), 2)
            graph = gx.build(site / "model.json", questions=site / "questions.json")
            self.assertIn("field_coverage", json.dumps(graph))

    def test_scope_and_coverage_conflicts_refuse_before_replacing_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            site = base / "site"
            site.mkdir()
            self.screen(self.model([{}, {}]), site)
            catalog = copy.deepcopy(CAT)
            request = next(q for q in catalog["questions"] if q["id"] == "H2")["data_requests"][0]
            catalog_path = base / "catalog.json"
            out = base / "reports"
            out.mkdir()
            (out / "rollup.json").write_text("prior JSON", encoding="utf-8")
            (out / "rollup.md").write_text("prior Markdown", encoding="utf-8")
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            for scope, message in (("unit", "field_scope"), ("pool", "field_scope must be")):
                request["field_scope"] = scope
                catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(qe.main(["--rollup", str(site), "--catalog", str(catalog_path), "--out", str(out)]), 2)
                self.assertIn(message, err.getvalue())
                self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)
            doc = json.loads((site / "questions.json").read_text(encoding="utf-8"))
            doc["questions"][0]["data_requests"][0]["field_coverage"][0]["still_needed"] = []
            (site / "questions.json").write_text(json.dumps(doc), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(qe.main(["--rollup", str(site), "--out", str(out)]), 2)
            self.assertIn("field_coverage", err.getvalue())
            self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)

    def test_committed_split_supply_example_reproduces(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(["--model", str(EX / "field-coverage/model.json"), "--question", "H2"], tmp)
            for name in ("questions.json", "screen.md"):
                self.assertEqual((Path(tmp) / name).read_text(encoding="utf-8"),
                                 (EX / "field-coverage" / name).read_text(encoding="utf-8"))

    def test_rollup_rejects_incomplete_or_invented_subject_coverage(self):
        def missing_coverage(r):
            del r["field_coverage"]

        def unknown_subject(r):
            r["field_coverage"][0]["id"] = "NOT-AN-ASSET"

        def missing_value(r):
            del r["field_coverage"][0]["fields"][0]["value"]

        def missing_locator(r):
            del r["field_coverage"][0]["fields"][0]["where"]

        changes = [missing_coverage, unknown_subject, missing_value, missing_locator,
                   lambda r: r.update(field_coverage=[]), lambda r: r.update(already_on_drawing=17),
                   lambda r: r["field_coverage"][0]["fields"][0].update(value=None)]
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            original, _ = self.screen(self.model([{"steam_pressure": "8 bar"}, {"steam_temperature_C": 140}]), tmp)
            for change in changes:
                with self.subTest(change=change.__name__):
                    doc = copy.deepcopy(original)
                    change(doc["questions"][0]["data_requests"][0])
                    (site / "questions.json").write_text(json.dumps(doc), encoding="utf-8")
                    with self.assertRaisesRegex(qe.InputError, "field_coverage"):
                        qe.rollup([str(site)], CAT)

    def test_rollup_cannot_erase_a_known_unit_or_dereference_a_scalar_subject(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            original = copy.deepcopy(load("bayer"))
            for coverage in ([], [None], [17], ["subject"], [[]]):
                with self.subTest(coverage=coverage):
                    doc = copy.deepcopy(original)
                    request = next(r for r in finding(doc, "H4@E-3")["data_requests"] if r["item"] == "Cooler duty")
                    request["field_coverage"] = coverage
                    request["scope_note"] = "No owning equipment unit is identified."
                    (site / "questions.json").write_text(json.dumps(doc), encoding="utf-8")
                    with self.assertRaisesRegex(qe.InputError, "field_coverage"):
                        qe.rollup([str(site)], CAT)


class CollectionContractRepairs(unittest.TestCase):
    """Actual CLI regressions for ratings, source-scoped questions and ambiguous field intake."""

    example = EX / "pump-motor-basis"
    source_example = EX / "source-investigation"

    def cli(self, args, expected=0):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/question_engine.py"), *map(str, args)],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def test_pump_motor_and_duty_example_reproduces(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.cli(["--model", self.example / "model.json", "--question", "E1", "--question", "E2",
                      "--question", "E4", "--question", "H4", "--out", tmp])
            for name in ("questions.json", "screen.md"):
                self.assertEqual((Path(tmp) / name).read_text(encoding="utf-8"),
                                 (self.example / name).read_text(encoding="utf-8"))

    def test_scalar_and_document_candidates_cannot_close_larger_tasks(self):
        cases = [{}, {"pump_curve": True}, {"pump_curve_uri": "other.pdf", "pump_curve_asset": "P-901",
                                          "pump_curve_readable": False},
                 {"BEP_flow": 100, "BEP_head": 90, "motor_efficiency": 0.9, "full_load_efficiency": 0.9,
                  "input_power_kW": 0, "operating_hours": 8000, "heat_duty_kW": 100}]
        tasks = {"E1@P-900": {"Matched pump curve, rated duty and system operating points",
                              "Motor nameplate, efficiency and drive basis"},
                 "E2@P-900": {"Matched pump curve and best-efficiency-point (BEP) duty"},
                 "E4@P-900": {"Motor nameplate, rated output and full-load efficiency",
                              "Measured input power or current at normal load"},
                 "H4@E-900": {"Cooler duty"}}
        for values in cases:
            with self.subTest(values=values), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model = json.loads((self.example / "model.json").read_text(encoding="utf-8"))
                for unit in model["units"]:
                    unit["facts"].update(values)
                path = base / "model.json"
                path.write_text(json.dumps(model), encoding="utf-8")
                self.cli(["--model", path, "--out", base])
                doc = json.loads((base / "questions.json").read_text(encoding="utf-8"))
                for fid, required in tasks.items():
                    actual = {r["item"]: r for r in finding(doc, fid)["data_requests"]}
                    self.assertLessEqual(required, actual.keys())
                    for name in required:
                        self.assertIn("candidate_facts", actual[name])
                        self.assertNotIn("already_on_drawing", actual[name])
                cooler = next(r for r in finding(doc, "H4@E-900")["data_requests"] if r["item"] == "Cooler duty")
                self.assertEqual(cooler["candidate_scope"], "unit")
                self.assertTrue(any(f["name"] == "CAPACITY" and f["value"] == "100 gpm"
                                    for f in cooler["candidate_facts"]))
                self.assertEqual(gx.build(path, questions=base / "questions.json")["questions"], doc["questions"])
                qe.rollup([str(base)], CAT)

    def test_source_scoped_catalog_reproduces_and_retains_historical_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.cli(["--model", ROOT / "examples/from-description/mgpi/model-expanded-source.json",
                      "--catalog", self.source_example / "catalog.json", "--out", base])
            for name in ("questions.json", "screen.md"):
                self.assertEqual((base / name).read_text(encoding="utf-8"),
                                 (self.source_example / name).read_text(encoding="utf-8"))
            doc = json.loads((base / "questions.json").read_text(encoding="utf-8"))
            self.assertEqual(len(doc["questions"]), 2)
            self.assertTrue(all(q["data_requests"] for q in doc["questions"]))
            notify = finding(doc, "MGPI-NOTIFY@HYPO_BULK")
            endpoint = finding(doc, "MGPI-ENDPOINT@HYPO_BULK")
            self.assertIn("not configured to shut the transfer automatically", notify["limits"])
            self.assertIn("likely", notify["limits"])
            self.assertIn("not unloading-to-bulk flow", endpoint["limits"])
            self.assertIn("historical question", notify["decision_rule"])
            catalog = json.loads((self.source_example / "catalog.json").read_text(encoding="utf-8"))
            rolled = qe.rollup([str(base)], catalog)
            self.assertIn("MGPI", qe.render_rollup_md(rolled, catalog))

    def test_source_recipe_does_not_become_a_generic_level_checklist(self):
        models = [ROOT / "data/te_process_model.json", ROOT / "data/bayer_rt/process_model.json",
                  EX / "food_plant_model.json"]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for n, path in enumerate(models):
                self.cli(["--model", path, "--catalog", self.source_example / "catalog.json", "--out", base / str(n)])
                doc = json.loads((base / str(n) / "questions.json").read_text(encoding="utf-8"))
                self.assertEqual(doc["questions"], [])
            # Default remains an honest zero; this authored recipe is not a generalization improvement.
            self.cli(["--model", ROOT / "examples/from-description/mgpi/model-expanded-source.json",
                      "--out", base / "default"])
            self.assertEqual(json.loads((base / "default/questions.json").read_text(encoding="utf-8"))["questions"], [])

    def intake(self, base, facts=None):
        model = {"meta": {"model_kind": "extracted_twin", "title": "fictional field intake"},
                 "units": [{"id": "P1", "tag": "P-1", "class": "pump", "sheets": ["1"],
                            "facts": facts or {}}], "instruments": [], "streams": []}
        path = base / "model.json"
        path.write_text(json.dumps(model), encoding="utf-8")
        return path

    def schedule(self, base, name, fields):
        path = base / name
        path.write_text(json.dumps({"sheets": {"1": [{"tag": "P-1", "service": "Water pump", "fields": fields}]}}),
                        encoding="utf-8")
        return path

    def test_disjoint_schedule_fields_merge_with_per_field_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model = self.intake(base)
            first = self.schedule(base, "first.json", {"HP": 10, "RPM": 1750})
            second = self.schedule(base, "second.json", {"CAPACITY": "100 gpm"})
            third = self.schedule(base, "third.json", {"DISCHARGE": "90 ft"})
            self.cli(["--model", model, "--schedule", first, "--schedule", second, "--schedule", third,
                      "--out", base / "reports"])
            doc = json.loads((base / "reports/questions.json").read_text(encoding="utf-8"))
            self.assertEqual(doc["schedules"], ["first.json", "second.json", "third.json"])
            motor = finding(doc, "E4@P1")
            evidence = next(e for e in motor["evidence"] if "HP = 10" in e["text"])
            self.assertIn("first.json", evidence["field"])
            loaded = qe.Model(model, schedule_paths=[third, second, first])
            self.assertEqual(qe.field_state(loaded.by_id["P1"], "HP")[1], 10)

    def test_ambiguous_inputs_refuse_before_overwriting_reports(self):
        cases = [("facts", {"HP": 10, "hp": 20}, None, None, "case-variant"),
                 ("fields", None, {"HP": 10, "hp": 20}, None, "case-variant"),
                 ("scheduleconflict", None, {"HP": 10}, {"hp": 20}, "conflicting schedule"),
                 ("typedconflict", None, {"HP": False}, {"hp": 0}, "conflicting schedule"),
                 ("factconflict", {"HP": 10}, {"hp": 20}, None, "conflicting model fact"),
                 ("whitespace", {" HP ": 10}, None, None, "surrounding whitespace")]
        for name, facts, fields, later, diagnostic in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model = self.intake(base, facts)
                out = base / "reports"
                out.mkdir()
                (out / "questions.json").write_text("prior JSON", encoding="utf-8")
                (out / "screen.md").write_text("prior report", encoding="utf-8")
                before = {p.name: p.read_bytes() for p in out.iterdir()}
                args = ["--model", model, "--out", out]
                if fields is not None:
                    args += ["--schedule", self.schedule(base, "first.json", fields)]
                if later is not None:
                    args += ["--schedule", self.schedule(base, "second.json", later)]
                result = self.cli(args, 2)
                self.assertIn(diagnostic, result.stderr)
                self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)

    def test_duplicate_and_nonfinite_json_refuse(self):
        for raw in ['{"units":[],"units":[]}', '{"units":[],"value":NaN}', '{"units":[],"value":1e999}']:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                path = base / "model.json"
                path.write_text(raw, encoding="utf-8")
                result = self.cli(["--model", path, "--out", base / "reports"], 2)
                self.assertIn("not valid JSON", result.stderr)
                self.assertFalse((base / "reports").exists())

    def test_identical_fields_and_opaque_qualifiers_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model = self.intake(base, {"HP": {"value": 10, "basis": "unknown", "source": {"revision": "A"}}})
            first = self.schedule(base, "first.json", {"hp": {"value": 10, "basis": "unknown", "source": {"revision": "A"}}})
            self.cli(["--model", model, "--schedule", first, "--out", base / "reports"])
            loaded = qe.Model(model, schedule_paths=[first])
            self.assertEqual(qe.field_state(loaded.by_id["P1"], "HP")[1],
                             {"value": 10, "basis": "unknown", "source": {"revision": "A"}})

    def test_native_schedule_is_refused_instead_of_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = self.schedule(base, "schedule.json", {"HP": 10})
            result = self.cli(["--model", self.example / "model.json", "--schedule", path,
                               "--out", base / "reports"], 2)
            self.assertIn("only to extracted twins", result.stderr)
            self.assertFalse((base / "reports").exists())


class SteamCollectionContracts(unittest.TestCase):
    """Public-model copies expose wrong units/basis without treating field presence as suitability."""

    cli = CollectionContractRepairs.cli
    ids_by_question = {"E11": "E11@stream:U1", "H1": "H1@S4-TK001", "H2": "H2@E-2"}
    tasks = {"E11": "Applicable surface-temperature and insulation evidence",
             "H1": "Matched station steam-throughput rating and conditions",
             "H2": "Applicable steam-supply conditions and operating basis"}

    def copied_model(self, qid, facts):
        relative = ("out/twin/r2-tiles-trace/codex/plant_model.json" if qid == "H1"
                    else "data/bayer_rt/process_model.json")
        model = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        target = (next(u for u in model["units"] if u["id"] == "S4-TK001") if qid == "H1"
                  else next(s for s in model["streams"] if s["id"] == "U1"))
        target["facts"] = copy.deepcopy(facts)
        if qid == "H2":
            next(v for v in model["final_elements"] if v["tag"] == "TV-104C")["facts"] = copy.deepcopy(facts)
        model.setdefault("meta", {})["audit_fixture"] = "Fictional software mutation of a public development model"
        return model

    def generate(self, base, qid, facts):
        path = base / "model.json"
        path.write_text(json.dumps(self.copied_model(qid, facts)), encoding="utf-8")
        before = path.read_bytes()
        args = ["--model", path, "--question", qid, "--out", base]
        if qid == "H1":
            args += ["--schedule", ROOT / "data/open100_equipment_schedule.json"]
        self.cli(args)
        self.assertEqual(path.read_bytes(), before)
        return json.loads((base / "questions.json").read_text(encoding="utf-8"))

    def test_wrong_basis_units_flags_and_rich_candidates_keep_review_tasks_open(self):
        cases = {
            "E11": [{}, {"normal_temperature_C": False}, {"normal_temperature_C": 0},
                    {"normal_temperature_C": None},
                    {"normal_temperature_C": {"value": 150, "basis": "design fluid; surface unknown", "status": "draft"}},
                    {"normal_temperature_C": 150, "insulation_survey": "wrong-asset.pdf",
                     "insulation_survey_asset": "OTHER", "insulation_survey_readable": False},
                    {"normal_temperature_C": 150, "surface_temperature_C": 75,
                     "surface_temperature_basis": {"source": "survey", "period": "example", "status": "unreviewed"},
                     "insulation_condition": "bare? draft observation"}],
            "H1": [{}, {"CAPACITY": False}, {"CAPACITY": 0}, {"CAPACITY": None},
                   {"CAPACITY": "500 gal internal volume"},
                   {"CAPACITY": "500 gal", "rating_document": "wrong-asset.pdf", "rating_asset": "OTHER",
                    "rating_document_readable": False},
                   {"CAPACITY": "3000 lb/hr", "rated_steam_flow": 3000, "rated_steam_flow_uom": "lb/hr",
                    "rating_conditions": {"basis": "vendor rating; actual duration unknown", "status": "unreviewed"}}],
            "H2": [{}, {"steam_pressure": False, "steam_temperature_C": False},
                   {"steam_pressure": 0, "steam_temperature_C": 0},
                   {"steam_pressure": None, "steam_temperature_C": "  "},
                   {"steam_pressure": {"value": 10, "units": "bar", "reference": "unknown", "basis": "design"},
                    "steam_temperature_C": {"value": 300, "basis": "different time/location", "status": "draft"}},
                   {"steam_pressure": "10 bar", "steam_temperature_C": 300, "steam_supply_asset": "OTHER",
                    "steam_conditions_source": "unreadable.pdf", "steam_conditions_readable": False},
                   {"steam_pressure": "10 bar", "steam_temperature_C": 300, "steam_state": "superheated candidate",
                    "steam_pressure_reference": "absolute", "steam_conditions_period": {"period": "example", "status": "unreviewed"}}]}
        for qid, variants in cases.items():
            for facts in variants:
                with self.subTest(question=qid, facts=facts), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    doc = self.generate(base, qid, facts)
                    selected = finding(doc, self.ids_by_question[qid])
                    task = next(r for r in selected["data_requests"] if r["item"] == self.tasks[qid])
                    self.assertIn("candidate_facts", task)
                    self.assertNotIn("already_on_drawing", task)
                    self.assertNotIn("still_needed", task)
                    for fact in task["candidate_facts"]:
                        self.assertEqual(fact["value"], facts[fact["name"]])
                        self.assertIn(".facts.", fact["where"])
                    graph = gx.build(base / "model.json", questions=base / "questions.json")
                    self.assertEqual(graph["questions"], doc["questions"])
                    qe.rollup([str(base)], CAT)
                    self.assertIn("collection/review request remains open", (base / "screen.md").read_text(encoding="utf-8"))

    def test_missing_new_review_tasks_refuse_rollup_without_changing_reports(self):
        for qid in self.tasks:
            with self.subTest(question=qid), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                doc = self.generate(base, qid, {})
                selected = finding(doc, self.ids_by_question[qid])
                selected["data_requests"] = [r for r in selected["data_requests"] if r["item"] != self.tasks[qid]]
                (base / "questions.json").write_text(json.dumps(doc), encoding="utf-8")
                out = base / "rollup"
                out.mkdir()
                (out / "rollup.json").write_text("prior JSON", encoding="utf-8")
                (out / "rollup.md").write_text("prior Markdown", encoding="utf-8")
                before = {p.name: p.read_bytes() for p in out.iterdir()}
                result = self.cli(["--rollup", base, "--out", out], 2)
                self.assertIn("missing_required", result.stderr)
                self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)

    def test_stated_field_accounting_does_not_claim_semantic_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            doc = self.generate(base, "H1", {"CAPACITY": "500 gal internal volume"})
            selected = finding(doc, self.ids_by_question["H1"])
            self.assertNotIn("Stated station capacity", {r["item"] for r in selected["data_requests"]})
            self.assertIn(self.tasks["H1"], {r["item"] for r in selected["data_requests"]})
            self.assertTrue(any("500 gal internal volume" in e["text"] for e in selected["evidence"]))
            self.assertIn("not actual flow-duration", next(r for r in selected["data_requests"]
                                                         if r["item"] == self.tasks["H1"])["how"])


class RefrigerationCollectionContracts(unittest.TestCase):
    """Source-informed development controls: quantity labels and unrelated trains cannot settle collection."""

    cli = CollectionContractRepairs.cli
    tasks = {"C12": "Applicable real-input-power and coincident operating basis",
             "E28": "Suction-level membership and reset coverage",
             "H5": "Recovery coverage by refrigeration train and heating duty"}

    def model(self):
        model = json.loads((EX / "food_plant_model.json").read_text(encoding="utf-8"))
        model["meta"]["audit_fixture"] = "Fictional mutation of the illustrative food model; no new observation"
        return model

    def screen(self, base, model, qid):
        source = base / "model.json"
        source.write_text(json.dumps(model), encoding="utf-8")
        before = source.read_bytes()
        self.cli(["--model", source, "--question", qid, "--out", base / "screen"])
        self.assertEqual(source.read_bytes(), before)
        doc = json.loads((base / "screen/questions.json").read_text(encoding="utf-8"))
        return doc, finding(doc, qid + "@model")

    def assert_open(self, selected, qid):
        task = next(r for r in selected["data_requests"] if r["item"] == self.tasks[qid])
        self.assertNotIn("already_on_drawing", task)
        self.assertNotIn("still_needed", task)
        self.assertIn("K-201", {a["id"] for a in selected["assets"]})
        return task

    def test_electrical_quantities_and_claims_retain_actual_real_input_basis(self):
        # DOE motor-input basis requires more than amperes, volts, or a supplied power label.
        # Even an explicitly real-kW-labelled candidate is not authenticated, representative operating data.
        cases = [("IT-201", "current", "A", "current only"),
                 ("ET-201", "voltage", "V", "voltage only"),
                 ("EQ-201", "energy", "kWh", "cumulative energy without interval"),
                 ("JT-201", "power", "kVA", "apparent power"),
                 ("JT-201", "power", "kvar", "reactive power"),
                 ("JT-201", "power", "unknown", "unverified quantity"),
                 ("OTHER-201", "power", "kW", "supplied real input power"),
                 ("JT-201", "unknown", "kW", "typed claim with unknown quantity"),
                 ("JT-201", "power", "kW", "average real power from supplied matching energy delta and interval")]
        for tag, variable, uom, meaning in cases:
            with self.subTest(quantity=meaning), tempfile.TemporaryDirectory() as tmp:
                base, model = Path(tmp), self.model()
                reading = next(i for i in model["instruments"] if i["tag"] == "JT-201")
                reading.update(tag=tag, variable=variable, uom=uom,
                               description=meaning + " (" + uom + ")",
                               facts={"reading_basis": {"value": 0, "uom": uom, "status": "draft",
                                                        "readable": False, "period": None}})
                doc, selected = self.screen(base, model, "C12")
                self.assert_open(selected, "C12")
                self.assertIn(tag, {a["id"] for a in selected["assets"]})
                self.assertTrue(any(meaning in e["text"] for e in selected["evidence"]))
                self.assertNotIn("no power measurement", json.dumps(selected))
                graph = gx.build(base / "model.json", questions=base / "screen/questions.json")
                self.assertEqual(graph["questions"], doc["questions"])
                self.assertIn("reading_basis", json.dumps(graph))
                self.assertIn(uom, json.dumps(graph))

    def test_reset_and_recovery_candidates_cannot_hide_other_trains(self):
        for case in ("unrelated_reset", "own_reset", "owned_reset", "unrelated_recovery", "local_recovery"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                base, model = Path(tmp), self.model()
                qid = "E28" if "reset" in case else "H5"
                if case == "unrelated_reset":
                    model["units"].append({"id": "K-999", "type": "compressor",
                                           "name": "Ammonia compressor, floating suction on disconnected train"})
                elif case == "own_reset":
                    model["units"][0]["name"] += "; floating suction on K-201 only"
                elif case == "owned_reset":
                    model["controllers"].append({"tag": "PIC-999", "unit": "K-201", "measurement": "PT-201",
                                                  "description": "Floating suction for K-201 only"})
                else:
                    model["units"].append({"id": "HX-999", "type": "heat_exchanger",
                                           "name": "Ammonia heat recovery, supplied coverage unverified"})
                    if case == "local_recovery":
                        model["streams"].append({"id": "R999", "from": "K-201", "to": "HX-999",
                                                 "name": "Supplied discharge connection, coverage unverified"})
                # Unequal approaches mean even a generic 'coldest room governs' shortcut is insufficient.
                for uid, required, approach in [("EV-201", -20, 1), ("EV-202", 4, 30)]:
                    next(u for u in model["units"] if u["id"] == uid)["facts"] = {
                        "required_temperature_C": required, "approach_K": approach,
                        "served_suction_level": "unverified", "status": "draft"}
                _, selected = self.screen(base, model, qid)
                self.assert_open(selected, qid)
                self.assertLessEqual({"K-201", "K-202", "K-203"}, {a["id"] for a in selected["assets"]})
                if qid == "E28":
                    self.assertNotIn("warmest load on a suction level", json.dumps(selected))
                    self.assertIn("every coincident load", json.dumps(selected).lower())
                    self.assertIn("approach", json.dumps(selected).lower())
                else:
                    self.assertIn("HX-999", {a["id"] for a in selected["assets"]})
                    self.assertNotIn("no desuperheater or refrigeration heat recovery exchanger anywhere",
                                     json.dumps(selected))

    def test_new_basis_tasks_survive_context_and_omission_is_refused(self):
        for qid in self.tasks:
            with self.subTest(question=qid), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                doc, selected = self.screen(base, self.model(), qid)
                self.assert_open(selected, qid)
                sources = base / "sources.json"
                sources.write_text(json.dumps({"schema": "context-sources-1", "documents": []}), encoding="utf-8")
                result = subprocess.run([sys.executable, str(ROOT / "scripts/context_register.py"), "prepare",
                                         "--model", str(base / "model.json"), "--questions",
                                         str(base / "screen/questions.json"), "--sources", str(sources),
                                         "--out", str(base / "context")], cwd=ROOT, capture_output=True,
                                        text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                enriched = json.loads((base / "context/enriched_questions.json").read_text(encoding="utf-8"))
                self.assertEqual([{k: v for k, v in f.items() if k != "context"}
                                  for f in enriched["questions"]], doc["questions"])
                selected["data_requests"] = [r for r in selected["data_requests"] if r["item"] != self.tasks[qid]]
                (base / "screen/questions.json").write_text(json.dumps(doc), encoding="utf-8")
                refused = self.cli(["--rollup", base / "screen", "--out", base / "rollup"], 2)
                self.assertIn("missing_required", refused.stderr)
                self.assertFalse((base / "rollup").exists())


class ServiceReconciliation(unittest.TestCase):
    """Exact imported service choices replace input-order selection, without claiming approval."""

    cli = CollectionContractRepairs.cli
    intake = CollectionContractRepairs.intake
    schedule = CollectionContractRepairs.schedule

    def sources(self, base):
        model = self.intake(base)
        first = self.schedule(base, "water.json", {"HP": 10})
        second = self.schedule(base, "refrigeration.json", {"HP": 10})
        value = json.loads(second.read_text(encoding="utf-8"))
        value["sheets"]["1"][0]["service"] = "Ammonia refrigeration compressor"
        second.write_text(json.dumps(value), encoding="utf-8")
        return model, first, second

    def declaration(self, first="water.json", second="refrigeration.json", selected=0):
        candidates = [{"file": first, "row": 1, "service": "Water pump"},
                      {"file": second, "row": 1, "service": "Ammonia refrigeration compressor"}]
        return {"candidates": candidates, "selected": candidates[selected],
                "basis": "Fictional imported service choice; needs source review", "status": "draft"}

    def attach(self, path, resolution):
        value = json.loads(path.read_text(encoding="utf-8"))
        value["sheets"]["1"][0]["service_resolution"] = resolution
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_conflicting_services_refuse_in_both_orders_before_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model, first, second = self.sources(base)
            out = base / "reports"
            out.mkdir()
            (out / "questions.json").write_text("previous JSON", encoding="utf-8")
            (out / "screen.md").write_text("previous Markdown", encoding="utf-8")
            prior = {p.name: p.read_bytes() for p in out.iterdir()}
            for a, b in ((first, second), (second, first)):
                result = self.cli(["--model", model, "--schedule", a, "--schedule", b, "--out", out], 2)
                self.assertIn("conflicting schedule service", result.stderr)
                self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, prior)

    def test_exact_draft_choice_is_order_independent_and_retained_in_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model, first, second = self.sources(base)
            self.attach(second, self.declaration())
            packets = []
            for n, (a, b) in enumerate(((first, second), (second, first))):
                out = base / str(n)
                self.cli(["--model", model, "--schedule", a, "--schedule", b, "--out", out])
                doc = json.loads((out / "questions.json").read_text(encoding="utf-8"))
                self.assertEqual(ids(doc), {"E4@P1", "C9@model"})
                resolution = doc["service_reconciliations"][0]
                self.assertEqual({r["service"] for r in resolution["candidates"]},
                                 {"Water pump", "Ammonia refrigeration compressor"})
                self.assertIn("unverified", resolution["authority"])
                self.assertEqual(resolution["declarations"][0]["status"], "draft")
                self.assertTrue(any(e.get("service_reconciliation") == resolution
                                    for q in doc["questions"] for e in q["evidence"]))
                self.assertEqual(gx.build(model, questions=out / "questions.json")["questions"], doc["questions"])
                self.assertIn("Supplied service choice, unverified", (out / "screen.md").read_text(encoding="utf-8"))
                packets.append({p.name: p.read_bytes() for p in out.iterdir()})
            self.assertEqual(packets[0], packets[1])

    def test_stale_unknown_and_malformed_declarations_refuse(self):
        good = self.declaration()
        def duplicate(value):
            value["candidates"].append(copy.deepcopy(value["candidates"][0]))
        mutations = [lambda value: value.update(basis="  "), lambda value: value.update(status="accepted"),
                     lambda value: value.update(status=[]), lambda value: value.update(selected={}),
                     lambda value: value["selected"].update(file="missing.json"), duplicate,
                     lambda value: value["candidates"][0].update(row=2),
                     lambda value: value["candidates"][0].update(service="different source text"),
                     lambda value: value.pop("basis"), lambda value: value.update(extra="ignored?")]
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model, first, second = self.sources(base)
                resolution = copy.deepcopy(good)
                mutate(resolution)
                self.attach(second, resolution)
                result = self.cli(["--model", model, "--schedule", first, "--schedule", second,
                                   "--out", base / "reports"], 2)
                self.assertIn("service_resolution", result.stderr)
                self.assertFalse((base / "reports").exists())

    def test_multiple_declarations_are_retained_but_conflicting_choices_refuse(self):
        for selected in (0, 1):
            with self.subTest(selected=selected), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model, first, second = self.sources(base)
                self.attach(first, self.declaration())
                other = self.declaration(selected=selected)
                other.update(status="reviewed", basis="Another supplied declaration; no authenticated approval")
                self.attach(second, other)
                result = self.cli(["--model", model, "--schedule", first, "--schedule", second,
                                   "--out", base / "reports"], 2 if selected else 0)
                if selected:
                    self.assertIn("conflicting service_resolution", result.stderr)
                else:
                    doc = json.loads((base / "reports/questions.json").read_text(encoding="utf-8"))
                    resolution = doc["service_reconciliations"][0]
                    self.assertEqual(len(resolution["declarations"]), 2)
                    self.assertEqual({r["status"] for r in resolution["declarations"]}, {"draft", "reviewed"})
                    self.assertIn("organizational approval unverified", resolution["authority"])

    def test_identical_and_blank_services_do_not_create_conflicts(self):
        for value in (None, "", "  ", "Water pump"):
            with self.subTest(service=value), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model, first, second = self.sources(base)
                data = json.loads(second.read_text(encoding="utf-8"))
                data["sheets"]["1"][0]["service"] = value
                second.write_text(json.dumps(data), encoding="utf-8")
                for n, (a, b) in enumerate(((first, second), (second, first))):
                    out = base / str(n)
                    self.cli(["--model", model, "--schedule", a, "--schedule", b, "--out", out])
                    doc = json.loads((out / "questions.json").read_text(encoding="utf-8"))
                    self.assertEqual(ids(doc), {"E4@P1", "C9@model"})
                    self.assertNotIn("service_reconciliations", doc)

    def test_changed_source_set_or_asset_identity_cannot_reuse_a_declaration(self):
        for changed in ("missing_source", "identity", "text", "row"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model, first, second = self.sources(base)
                self.attach(second, self.declaration())
                data = json.loads(first.read_text(encoding="utf-8"))
                if changed == "identity":
                    data["sheets"]["1"][0]["tag"] = "P-OTHER"
                elif changed == "text":
                    data["sheets"]["1"][0]["service"] = "Changed description"
                elif changed == "row":
                    data["sheets"]["1"].insert(0, {"tag": "P-OTHER", "service": "Other pump"})
                first.write_text(json.dumps(data), encoding="utf-8")
                args = ["--model", model, "--schedule", second, "--out", base / "reports"]
                if changed != "missing_source":
                    args += ["--schedule", first]
                result = self.cli(args, 2)
                self.assertIn("stale or mismatched service_resolution", result.stderr)
                self.assertFalse((base / "reports").exists())

    def test_unmatched_asset_declarations_and_nontext_services_do_not_escape_validation(self):
        for service in (False, 23, [], {}, "Water pump"):
            with self.subTest(service=service), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model = self.intake(base)
                schedule = self.schedule(base, "other.json", {})
                value = json.loads(schedule.read_text(encoding="utf-8"))
                value["sheets"]["1"][0].update(tag="unmatched", service=service)
                if service == "Water pump":
                    value["sheets"]["1"][0]["service_resolution"] = {}
                schedule.write_text(json.dumps(value), encoding="utf-8")
                result = self.cli(["--model", model, "--schedule", schedule, "--out", base / "reports"], 2)
                self.assertIn("service", result.stderr)

    def test_open100_resolutions_are_explicit_and_original_transcriptions_remain(self):
        paths = ["data/open100_equipment_schedule.json", "examples/opportunity-screen/open100_schedule_fields.json"]
        original = json.loads((ROOT / paths[0]).read_text(encoding="utf-8"))
        supplements = json.loads((ROOT / paths[1]).read_text(encoding="utf-8"))
        self.assertEqual(sum("service_resolution" in r for rows in supplements["sheets"].values() for r in rows), 3)
        entries = qe.load_schedule([ROOT / p for p in paths])
        reversed_entries = qe.load_schedule([ROOT / p for p in reversed(paths)])
        for sheet in ("2", "3", "4"):
            row = next(r for r in original["sheets"][sheet] if r["tag"] == "CND-TK-165")
            self.assertIn(row["service"], {"DEAREATOR STORAGE TANK", "DEAREATER STORAGE TANK"})
            resolution = entries[(sheet, "CND-TK-165")]["service_reconciliation"]
            self.assertEqual(resolution, reversed_entries[(sheet, "CND-TK-165")]["service_reconciliation"])
            self.assertEqual(resolution["selected"]["service"], "DEAERATOR STORAGE TANK")
            self.assertEqual(resolution["declarations"][0]["status"], "draft")

    def test_resolution_inputs_are_protected_from_output_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model, first, second = self.sources(base)
            target = base / "screen.md"
            first.rename(target)
            self.attach(second, self.declaration(first="screen.md"))
            (base / "questions.json").write_text("previous JSON", encoding="utf-8")
            prior = {p.name: p.read_bytes() for p in base.iterdir() if p.is_file()}
            result = self.cli(["--model", model, "--schedule", target, "--schedule", second, "--out", base], 2)
            self.assertIn("overlaps input", result.stderr)
            self.assertEqual({p.name: p.read_bytes() for p in base.iterdir() if p.is_file()}, prior)


class CollectionBasis(unittest.TestCase):
    """Scalar candidates cannot stand in for performance documents or representative operating records."""

    example = EX / "collection-basis"

    def screen(self, facts=None):
        model = json.loads((self.example / "model.json").read_text(encoding="utf-8"))
        if facts:
            for unit in model["units"]:
                unit["facts"].update(facts)
        return model

    def generate(self, tmp, facts=None, catalog=None):
        model = self.screen(facts)
        path = Path(tmp) / "model.json"
        path.write_text(json.dumps(model), encoding="utf-8")
        args = ["--model", str(path), "--question", "E5", "--question", "H3"]
        if catalog:
            cp = Path(tmp) / "catalog.json"
            cp.write_text(json.dumps(catalog), encoding="utf-8")
            args += ["--catalog", str(cp)]
        return run(args, tmp)[1]

    def test_nameplate_and_rich_raw_candidates_keep_collection_review_open(self):
        cases = [None, {"input_power_kW": 10}, {"operating_hours": 8000},
                 {"fan_curve_uri": "F-2-curve.pdf", "fan_curve_asset": "F-2", "fan_curve_readable": False},
                 {"fan_curve": True, "fan_curve_uri": "F-1-curve.pdf", "input_power_kW": 10,
                  "operating_hours": 8000, "energy_kWh": 80000, "control_mode": "mixed manual/bypass"}]
        for values in cases:
            with self.subTest(values=values), tempfile.TemporaryDirectory() as tmp:
                doc = self.generate(tmp, values)
                fan, heater = finding(doc, "E5@F-1"), finding(doc, "H3@EH-1")
                self.assertEqual(len(fan["data_requests"]), 4)
                self.assertEqual(len(heater["data_requests"]), 3)
                self.assertTrue(all(r["state"] == "not_on_drawing" for f in (fan, heater) for r in f["data_requests"]))
                self.assertFalse(any("still_needed" in r or "already_on_drawing" in r
                                     for f in (fan, heater) for r in f["data_requests"]))
                facts = [v for f in (fan, heater) for r in f["data_requests"] for v in r.get("candidate_facts", [])]
                self.assertTrue(any(v["name"] == "HP" and v["id"] == "F-1" and v["value"] == 15 for v in facts))
                if values and "fan_curve_readable" in values:
                    self.assertTrue(any(v["name"] == "fan_curve_readable" and v["value"] is False for v in facts))
                md = (Path(tmp) / "screen.md").read_text(encoding="utf-8")
                self.assertIn("collection/review request remains open", md)
                self.assertIn("representative period", md)
                self.assertIn("a URI or present/readable flag", md)
                self.assertIn("original units", md)

    def test_candidate_values_case_and_locator_survive_rollup_and_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = self.generate(tmp, {"INPUT_POWER_KW": 0, "fan_curve_readable": False})
            r = next(r for r in finding(doc, "E5@F-1")["data_requests"] if r["item"] == "Fan electrical-input and load history")
            fact = next(f for f in r["candidate_facts"] if f["name"] == "input_power_kW")
            self.assertEqual(fact["value"], 0)
            self.assertEqual(fact["where"], "units[F-1].facts.INPUT_POWER_KW")
            graph = gx.build(Path(tmp) / "model.json", questions=Path(tmp) / "questions.json")
            self.assertEqual(graph["questions"], doc["questions"])
            rolled = qe.rollup(["A=" + tmp, "B=" + tmp], CAT)
            rr = next(q for q in rolled["questions"] if q["question_id"] == "E5")
            request = next(x for x in rr["data_requests"] if x["item"] == r["item"])
            for site in request["sites"]:
                self.assertEqual(site["coverage_by_finding"][0]["candidate_facts"], r["candidate_facts"])
            self.assertEqual(qe.render_rollup_md(rolled, CAT).count("units[F-1].facts.INPUT_POWER_KW"), 2)

    def test_supplied_facts_never_count_toward_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = copy.deepcopy(CAT)
            r = next(q for q in catalog["questions"] if q["id"] == "E5")["data_requests"][0]
            r["fields"] = ["reviewed_period"]
            doc = self.generate(tmp, {"damper_position": 40}, catalog)
            request = finding(doc, "E5@F-1")["data_requests"][0]
            self.assertEqual(request["still_needed"], ["reviewed_period"])
            self.assertNotIn("already_on_drawing", request)
            self.assertEqual(request["candidate_facts"][0]["value"], 40)

    def test_committed_collection_reports_reproduce(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(["--model", str(self.example / "model.json"), "--question", "E5", "--question", "H3"], tmp)
            for name in ("questions.json", "screen.md"):
                self.assertEqual((Path(tmp) / name).read_text(encoding="utf-8"),
                                 (self.example / name).read_text(encoding="utf-8"))

    def test_rollup_cannot_erase_always_open_collection_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = self.generate(tmp)
            for requests in ([], original["questions"][0]["data_requests"][1:]):
                with self.subTest(count=len(requests)):
                    doc = copy.deepcopy(original)
                    doc["questions"][0]["data_requests"] = requests
                    (Path(tmp) / "questions.json").write_text(json.dumps(doc), encoding="utf-8")
                    with self.assertRaisesRegex(qe.InputError, "missing_required"):
                        qe.rollup([tmp], CAT)

    def test_evidence_only_unit_request_explains_missing_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = copy.deepcopy(CAT)
            next(q for q in catalog["questions"] if q["id"] == "H3")["data_requests"][0]["field_scope"] = "unit"
            doc = self.generate(tmp, catalog=catalog)
            request = finding(doc, "H3@EH-1")["data_requests"][0]
            self.assertEqual(request["candidate_scope"], "unit")
            self.assertEqual(request["candidate_facts"], [])
            self.assertIn("No owning equipment unit", request["scope_note"])
            self.assertIn("No owning equipment unit", (Path(tmp) / "screen.md").read_text(encoding="utf-8"))
            rolled = qe.rollup([tmp], catalog)
            self.assertIn("No owning equipment unit", qe.render_rollup_md(rolled, catalog))

    def test_invalid_show_fields_refuse_without_replacing_existing_reports(self):
        for show in (None, "HP", [], ["HP", "hp"], [""], [False]):
            with self.subTest(show=show), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                self.generate(tmp)
                before = {name: (base / name).read_bytes() for name in ("questions.json", "screen.md")}
                catalog = copy.deepcopy(CAT)
                next(q for q in catalog["questions"] if q["id"] == "E5")["data_requests"][0]["show_fields"] = show
                cp = base / "catalog.json"
                cp.write_text(json.dumps(catalog), encoding="utf-8")
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    code = qe.main(["--model", str(base / "model.json"), "--catalog", str(cp), "--out", str(base)])
                self.assertEqual(code, 2)
                self.assertIn("show_fields", err.getvalue())
                self.assertEqual({name: (base / name).read_bytes() for name in before}, before)

    def test_malformed_candidate_metadata_refuses_before_rollup_publication(self):
        def duplicate(r):
            r["candidate_facts"].append(copy.deepcopy(r["candidate_facts"][0]))

        changes = [duplicate, lambda r: r.update(candidate_facts=17),
                   lambda r: r.pop("candidate_facts"), lambda r: r.update(candidate_scope="unit"),
                   lambda r: r["candidate_facts"][0].update(id="OUTSIDE"),
                   lambda r: r["candidate_facts"][0].update(label=""),
                   lambda r: r["candidate_facts"][0].update(name="UNLISTED"),
                   lambda r: r["candidate_facts"][0].update(value=None),
                   lambda r: r["candidate_facts"][0].update(where="")]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            original = self.generate(tmp)
            out = base / "rollup"
            out.mkdir()
            for name in ("rollup.json", "rollup.md"):
                (out / name).write_text("previous report", encoding="utf-8")
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            for change in changes:
                with self.subTest(change=change.__name__):
                    doc = copy.deepcopy(original)
                    change(finding(doc, "E5@F-1")["data_requests"][2])
                    (base / "questions.json").write_text(json.dumps(doc), encoding="utf-8")
                    with contextlib.redirect_stderr(io.StringIO()) as err:
                        code = qe.main(["--rollup", str(base), "--out", str(out)])
                    self.assertEqual(code, 2)
                    self.assertIn("candidate_facts", err.getvalue())
                    self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)


class ReviewFixes(unittest.TestCase):
    """One regression test per finding of the two independent reviews (2026-10-29)."""

    def test_h4_never_fires_on_a_cooler_of_the_cooling_water_itself(self):
        self.assertNotIn("H4@S7-TK002", ids(load("open100")))  # ACW-AXC-210, AUX COOLING WATER COOLER (to air)
        with tempfile.TemporaryDirectory() as tmp:
            m = {"meta": {"title": "cw loop"}, "streams": [], "instruments": [], "final_elements": [],
                 "units": [{"id": "X-1", "name": "Cooling water cooler (air cooled)", "type": "heat_exchanger"},
                           {"id": "X-2", "name": "Cooling tower water exchanger", "type": "heat_exchanger"},
                           {"id": "X-3", "name": "Product cooler (cooling water)", "type": "heat_exchanger"}]}
            (Path(tmp) / "m.json").write_text(json.dumps(m), encoding="utf-8")
            _, doc = run(["--model", str(Path(tmp) / "m.json"), "--question", "H4"], tmp)
            self.assertEqual(ids(doc), {"H4@X-3"})
        # The unit decides, whichever item triggered it: a cooling-water line or valve on the air cooler is not
        # heat rejected to cooling water (second review round found this on a renamed Bayer E-3)
        with tempfile.TemporaryDirectory() as tmp:
            m = {"meta": {"title": "cw loop"}, "instruments": [],
                 "units": [{"id": "X-1", "name": "Aux cooling water air-cooled exchanger", "type": "heat_exchanger"}],
                 "streams": [{"id": "U1", "name": "Cooling water supply to the cooler", "from": "BL", "to": "X-1"}],
                 "final_elements": [{"tag": "HV-1", "unit": "X-1", "description": "cooling water hand valve"}]}
            (Path(tmp) / "m.json").write_text(json.dumps(m), encoding="utf-8")
            _, doc = run(["--model", str(Path(tmp) / "m.json"), "--question", "H4"], tmp)
            self.assertEqual(ids(doc), set())

    def test_a_null_fact_is_not_a_known_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = {"meta": {"title": "x"}, "streams": [], "instruments": [], "final_elements": [],
                 "units": [{"id": "E-3", "type": "heat_exchanger", "name": "Product cooler (cooling water)",
                            "facts": {"cooling_water_C": None}}]}
            (Path(tmp) / "m.json").write_text(json.dumps(m), encoding="utf-8")
            _, doc = run(["--model", str(Path(tmp) / "m.json"), "--question", "H4"], tmp)
        reqs = {r["item"] for r in finding(doc, "H4@E-3")["data_requests"]}
        self.assertIn("Cooling water supply temperature", reqs)

    def test_h4_process_temperature_is_never_the_cooling_water_side(self):
        h4 = finding(load("te"), "H4@E-101")
        req = next(r for r in h4["data_requests"] if r["item"].startswith("Temperature of the stream being cooled"))
        self.assertNotIn("XMEAS(22)", " ".join(req["where"]))  # TT-122 is the separator cooling water outlet

    def test_bayer_h4_requests_the_return_temperature(self):
        h4 = finding(load("bayer"), "H4@E-3")
        reqs = {r["item"]: r for r in h4["data_requests"]}
        self.assertNotIn("Cooling water supply temperature", reqs)  # the model holds it: 80 C on the supply
        self.assertEqual(reqs["Cooling water return temperature"]["state"], "not_on_drawing")
        self.assertTrue(any("cooling_water_C = 80" in e["text"] for e in h4["evidence"]))

    def test_flow_requests_never_cite_a_valve_position(self):
        pos = re.compile(r"_POS\b|XMV\(")
        for name in RUNS:
            for f in load(name)["questions"]:
                for r in f["data_requests"]:
                    if "flow" not in r["item"].lower() or "position" in r["item"].lower():
                        continue
                    for w in r["where"]:
                        offered = w.split("only the valve position is recorded")[0]
                        self.assertIsNone(pos.search(offered), (name, f["id"], r["item"], w))
        c1 = {r["item"]: r for r in finding(load("te"), "C1@R-101")["data_requests"]}["Utility flow to this user"]
        self.assertTrue(c1["where"][0].startswith("only the valve position is recorded (TV-121: recorded signal "
                                                  "XMV(10)"))
        self.assertIn("flow needs a meter or a calibrated valve curve", c1["where"][0])
        h1 = {r["item"]: r for r in finding(load("open100"), "H1@S0-OP005")["data_requests"]}
        self.assertTrue(h1["Steam flow through the station, with hours"]["where"][0].startswith(
            "only the valve position is recorded"))
        # a cooling water outlet temperature is not offered for the supply temperature
        h4 = {r["item"]: r for r in finding(load("te"), "H4@R-101")["data_requests"]}
        self.assertNotIn("TT-121", " ".join(h4["Cooling water supply temperature"]["where"]))
        self.assertIn("TT-121", " ".join(h4["Cooling water return temperature"]["where"]))

    def test_a_drawn_flow_meter_is_not_contradicted_by_the_valve_beside_it(self):
        """2026-10-29: a flow request said 'only a valve is drawn on this line, with no flow measurement' next to the
        flow meter on the same line (TE FT-119 with FV-119, the food dryer's FT-301 with TV-301)."""
        e18 = {r["item"]: r for r in finding(load("te"), "E18@model")["data_requests"]}
        where = " ".join(e18["Temperatures and duties of the cooled and the heated streams"]["where"])
        self.assertIn("FT-119", where)
        self.assertNotIn("XMV(9)", where)
        self.assertIn("XMV(10)", where)  # the unmetered cooling water side keeps its caveat
        e31 = {r["item"]: r for r in finding(load("food"), "E31@D-301")["data_requests"]}
        fuel = " ".join(e31["Fuel or heat input and operating hours"]["where"])
        self.assertIn("FT-301", fuel)
        self.assertNotIn("only a valve", fuel)

    def test_every_source_named_in_a_wording_is_in_its_source_list(self):
        for q in CAT["questions"]:
            named = set(re.findall(r"\bS\d+\b", q["typical_benefit"]["wording"]))
            self.assertLessEqual(named, set(q["typical_benefit"]["source"]), q["id"])
        self.assertIn("S11", finding(load("te"), "H4@R-101")["typical_benefit"]["source"])

    def test_controller_evidence_quotes_as_found_and_formats_the_setpoint(self):
        c6 = finding(load("bayer"), "C6@TV-104C")
        tic = next(e for e in c6["evidence"] if e.get("id") == "TIC-104")["text"]
        self.assertIn("to the cooler (setpoint 135 C)", tic)
        self.assertIn("As found: incorrectly programmed", tic)
        self.assertIn("footnote 29", tic)

    def test_bad_inputs_are_refused_clearly(self):
        def refuse(files, extra=()):
            with tempfile.TemporaryDirectory() as tmp:
                for name, text in files.items():
                    (Path(tmp) / name).write_text(text, encoding="utf-8")
                err, old = io.StringIO(), sys.stderr
                sys.stderr = err
                try:
                    rc = qe.main(["--model", str(Path(tmp) / "m.json"), *[a.replace("TMP", tmp) for a in extra]])
                finally:
                    sys.stderr = old
                return rc, err.getvalue()
        good = json.dumps({"meta": {}, "units": [{"id": "T-1", "type": "tank"}]})
        for files, expect in (({"m.json": "{}"}, "has no units or instruments"),
                              ({"m.json": json.dumps({"units": []})}, "is this the right file?"),
                              ({"m.json": "not json at all"}, "is not valid JSON"),
                              ({"m.json": ""}, "is not valid JSON"),
                              ({"m.json": "[1, 2]"}, "not a JSON object"),
                              ({}, "cannot read the model")):
            rc, msg = refuse(files)
            self.assertEqual(rc, 2, msg)
            self.assertIn(expect, msg)
        rc, msg = refuse({"m.json": good, "l.csv": "loop,pv,mv\nFIC-1,FT-1,FV-1\n"}, ["--loops", "TMP/l.csv"])
        self.assertEqual(rc, 2)
        self.assertIn("has no column(s) controller, measurement, output", msg)
        rc, msg = refuse({"m.json": good, "l.csv": "controller,measurement,output\nXIC-1,XT-1,XV-1\n"},
                         ["--loops", "TMP/l.csv"])
        self.assertEqual((rc, "names a tag in the model" in msg), (2, True))  # a typo'd list isn't silently used
        bayer = json.loads((ROOT / "data" / "bayer_rt" / "process_model.json").read_text(encoding="utf-8"))
        for mutate, expect in (  # round-3 review: each of these was a traceback
                (lambda m: m["units"][0].update(id={}), "units[0].id must be text"),
                (lambda m: m["instruments"][0].update(unit=["x"]), "instruments[0].unit must be text"),
                (lambda m: m["units"][0].update(type=5), "units[0].type must be text"),
                (lambda m: m["units"][0].update(facts="x"), "units[0].facts must be an object"),
                (lambda m: m.update(controllers={}), "'controllers' must be a list"),
                (lambda m: m["units"].append(dict(m["units"][0])), "appears more than once"),
                # round 4 (Codex): a split range written as one tag string was split into characters
                (lambda m: m["controllers"][1]["output"].update(split_range="TV-104C"),
                 "output.split_range must be a list of tags")):
            bad = json.loads(json.dumps(bayer))
            mutate(bad)
            rc, msg = refuse({"m.json": json.dumps(bad)})
            self.assertEqual((rc, expect in msg), (2, True), msg)
        nullmeta = json.loads(json.dumps(bayer))
        nullmeta["meta"] = None  # round 4 (Codex): crashed while rendering; an empty meta is no meta
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "m.json").write_text(json.dumps(nullmeta), encoding="utf-8")
            rc, _ = run(["--model", str(Path(tmp) / "m.json")], tmp)
        self.assertEqual(rc, 0)
        rc, msg = refuse({"m.json": json.dumps({"units": [{}]})})
        self.assertEqual((rc, "has no 'id' field" in msg), (2, True))  # a nested record, not just the top level
        rc, msg = refuse({"m.json": good, "s.json": json.dumps({"sheets": {"2": [{}]}})}, ["--schedule", "TMP/s.json"])
        self.assertEqual(rc, 2, msg)
        rc, msg = refuse({"m.json": good}, ["--loops", "TMP/missing.csv"])
        self.assertEqual((rc, "cannot read the loop list" in msg), (2, True))
        rc, msg = refuse({"m.json": good, "s.json": "{}"}, ["--schedule", "TMP/s.json"])
        self.assertEqual((rc, "has no 'sheets' object" in msg), (2, True))

    def test_placeholder_tags_are_marked(self):
        c3 = finding(load("open100"), "C3@model")
        xxx = [e for e in c3["evidence"] if (e.get("tag") or "").endswith("-XXX")]
        self.assertEqual(len(xxx), 6)
        self.assertTrue(all("[placeholder tag on the drawing]" in e["text"] for e in xxx))
        self.assertFalse(any("placeholder" in e["text"] for e in c3["evidence"] if e.get("tag") == "LCV-1501"))

    def test_synthetic_demo_points_are_labelled(self):
        text = (EX / "open100" / "screen.md").read_text(encoding="utf-8")
        self.assertGreater(text.count("mapped data point"), 0)
        self.assertEqual(text.count("mapped data point"), text.count("SYNTHETIC mapped data point"))
        self.assertIn("synthetic demo point", text)


class ReviewRefresh(unittest.TestCase):
    """Fictional review controls, not a review of any plant's engineering facts."""

    def load_model(self, source, loops=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "model.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        loop_path = None
        if loops:
            loop_path = path.with_suffix(".csv")
            loop_path.write_text(loops, encoding="utf-8")
        before = path.read_bytes()
        model = qe.Model(path, loop_path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(model.m, source)
        return model

    def food(self):
        return json.loads((EX / "food_plant_model.json").read_text(encoding="utf-8"))

    def test_actual_cli_review_refresh_and_reconfirmation_packet(self):
        p = subprocess.run([sys.executable, "-S", str(EX / "review-refresh" / "demonstrate.py")], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_each_supported_hand_collection_excludes_rejected_record(self):
        records = {"units": {"id": "P-1", "type": "pump"},
                   "streams": {"id": "S1", "from": "P-1", "to": "BL", "name": "Cooling water", "utility": True},
                   "instruments": {"tag": "FT-1", "unit": "P-1"},
                   "final_elements": {"tag": "FV-1", "unit": "P-1"},
                   "manual_valves": {"tag": "HV-1", "unit": "P-1"},
                   "relief_devices": {"tag": "PSV-1", "unit": "P-1"},
                   "controllers": {"tag": "FIC-1", "measurement": "FT-1", "output": {"final_element": "FV-1"}},
                   "interlocks": {"id": "I-1", "measurement": "FT-1", "final_element": "FV-1"}}
        for section, record in records.items():
            with self.subTest(section=section):
                source = {sec: [copy.deepcopy(r)] for sec, r in records.items()}
                source[section][0]["ops_review"] = {"status": "rejected", "notes": "Fictional control"}
                model = self.load_model(source)
                key = record.get("id") or record.get("tag")
                normalized_key = "stream:" + key if section == "streams" else key
                self.assertNotIn(normalized_key, model.by_id)
                self.assertEqual([r["id"] for r in model.review_exclusions], [key])

    def test_missing_and_nonrejected_reviews_remain_eligible(self):
        base = self.food()
        expected = qe.screen(self.load_model(base), CAT)[0]
        for status in (None, "unverified", "confirmed", "corrected"):
            with self.subTest(status=status):
                source = copy.deepcopy(base)
                source["instruments"][1]["ops_review"] = None if status is None else {"status": status}
                model = self.load_model(source)
                self.assertIn("JT-201", model.by_id)
                self.assertEqual(qe.screen(model, CAT)[0], expected)

    def test_rejected_anchor_cannot_supply_evidence_or_data_locations(self):
        source = self.food()
        source["instruments"][0]["ops_review"] = {"status": "rejected"}
        found = qe.screen(self.load_model(source), CAT)[0]
        content = json.dumps(found)
        self.assertNotIn("PT-201", content)
        self.assertTrue(any(f["question_id"] == "C2" for f in found))

    def test_rejected_unit_does_not_reject_or_group_its_children(self):
        source = self.food()
        source["units"][0]["ops_review"] = {"status": "rejected"}
        model = self.load_model(source)
        self.assertNotIn("K-201", model.by_id)
        self.assertIn("PT-201", model.by_id)
        self.assertIsNone(model.by_id["PT-201"].get("unit"))
        self.assertIsNone(model.by_id["stream:R1"].get("dst"))
        self.assertNotIn('"id": "K-201"', json.dumps(qe.screen(model, CAT)[0]))

    def test_rejected_stream_no_longer_links_heat_recovery(self):
        source = self.food()
        next(s for s in source["streams"] if s["id"] == "S3")["ops_review"] = {"status": "rejected"}
        model = self.load_model(source)
        found = {f["id"] for f in qe.screen(model, CAT)[0]}
        self.assertTrue({"E31@F-303", "H6@F-303"} <= found)
        self.assertIn("HX-303", model.by_id)

    def twin(self):
        return {"meta": {"model_kind": "extracted_twin"},
                "units": [{"id": "P", "tag": "P-1", "name": "Pump", "class": "pump", "sheets": [0]}],
                "line_items": [{"id": "L", "class": "line", "unit": "P"}],
                "instruments": [{"id": "FT", "tag": "FT-1", "parent": "L", "unit": "P"}],
                "streams": [{"id": "s", "from": "P", "to": "L"}]}

    def test_twin_rejected_parent_is_not_a_path_but_child_survives(self):
        source = self.twin()
        source["line_items"][0]["ops_review"] = {"status": "rejected"}
        model = self.load_model(source)
        self.assertIn("FT", model.by_id)
        self.assertIsNone(model.by_id["FT"].get("parent"))
        self.assertNotIn("L", model.near("P", 5, "0"))
        self.assertNotIn("FT", model.near("P", 5, "0"))

    def test_twin_rejected_edge_is_not_a_path(self):
        source = self.twin()
        source["streams"][0]["ops_review"] = {"status": "rejected"}
        model = self.load_model(source)
        self.assertNotIn("L", model.near("P", 5, "0"))
        self.assertIn("FT", model.near("L", 5, "0"))

    def test_twin_rejected_instrument_and_connector_are_excluded(self):
        source = self.twin()
        source["instruments"][0]["ops_review"] = {"status": "rejected"}
        source["offpage_connectors"] = [{"id": "O", "text": "Steam", "ops_review": {"status": "rejected"}}]
        model = self.load_model(source)
        self.assertNotIn("FT", model.by_id)
        self.assertNotIn("O", model.by_id)

    def test_rejected_controller_does_not_satisfy_needs_model(self):
        source = self.food()
        for c in source["controllers"]:
            c["ops_review"] = {"status": "rejected"}
        model = self.load_model(source)
        found, nc, *_ = qe.screen(model, CAT, ["C2"])
        self.assertFalse(found)
        self.assertEqual([n["question_id"] for n in nc], ["C2"])

    def test_loop_list_cannot_reinstate_rejected_hand_controller(self):
        source = self.food()
        source["controllers"][0]["ops_review"] = {"status": "rejected"}
        model = self.load_model(source, "controller,measurement,output\nPIC-202,PT-202,SC-203\n")
        self.assertNotIn("PIC-202", model.by_id)
        self.assertEqual(model.loop_rejected, ["PIC-202"])
        c2 = next(f for f in qe.screen(model, CAT)[0] if f["id"] == "C2@model")
        self.assertIn("PT-202", {a["id"] for a in c2["assets"]})

    def test_loop_list_cannot_reinstate_rejected_twin_bubble(self):
        source = self.twin()
        source["instruments"].append({"id": "FIC", "tag": "FIC-1", "ops_review": {"status": "rejected"}})
        model = self.load_model(source, "controller,measurement,output\nFIC-1,FT-1,FV-1\n")
        self.assertNotIn("FIC-1", model.by_id)
        self.assertEqual(model.loop_rejected, ["FIC-1"])

    def test_loop_list_cannot_reclassify_other_rejected_assets_as_controllers(self):
        source = self.food()
        source["final_elements"][0]["ops_review"] = {"status": "rejected"}
        model = self.load_model(source, "controller,measurement,output\nsc_203,JT-201,TV-303\n")
        self.assertNotIn("sc_203", model.by_id)
        self.assertNotIn("SC-203", model.by_id)
        self.assertEqual(model.loop_rejected, ["sc_203"])
        c2 = next(f for f in qe.screen(model, CAT)[0] if f["id"] == "C2@model")
        self.assertIn("JT-201", {a["id"] for a in c2["assets"]})

    def test_live_duplicate_tag_is_not_blanket_rejected(self):
        source = self.twin()
        source["instruments"].extend([{"id": "bad", "tag": "FIC-1", "ops_review": {"status": "rejected"}},
                                       {"id": "live", "tag": "FIC-1"}])
        model = self.load_model(source, "controller,measurement,output\nFIC-1,FT-1,FV-1\n")
        self.assertIn("live", model.by_id)
        self.assertIn("FIC-1", model.by_id)
        self.assertEqual(model.loop_rejected, [])

    def test_ordinary_unresolved_references_are_retained(self):
        source = self.twin()
        source["instruments"][0].update(unit="unresolved-unit", parent="unresolved-parent")
        model = self.load_model(source)
        self.assertEqual(model.by_id["FT"]["unit"], "unresolved-unit")
        self.assertEqual(model.by_id["FT"]["parent"], "unresolved-parent")

    def test_malformed_reviews_refuse_before_output_changes(self):
        for review in ([], "rejected", {"status": "reject"}, {"status": []}, {"by": 2}, {"on": []}, {"notes": {}}):
            with self.subTest(review=review), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                path = base / "model.json"
                source = self.food()
                source["instruments"][0]["ops_review"] = review
                path.write_text(json.dumps(source), encoding="utf-8")
                (base / "questions.json").write_text("existing packet", encoding="utf-8")
                (base / "screen.md").write_text("existing report", encoding="utf-8")
                prior = {p.name: p.read_bytes() for p in base.iterdir()}
                err, old = io.StringIO(), sys.stderr
                sys.stderr = err
                try:
                    self.assertEqual(qe.main(["--model", str(path), "--out", str(base)]), 2)
                finally:
                    sys.stderr = old
                self.assertIn("ops_review", err.getvalue())
                self.assertEqual({p.name: p.read_bytes() for p in base.iterdir()}, prior)


class OutputPublication(unittest.TestCase):
    """Reports may refresh, but must never replace any of their inputs."""

    def call(self, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            rc = qe.main([str(a) for a in args])
        return rc, err.getvalue()

    def snapshot(self, folder):
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}

    def model(self, folder, name="model.json"):
        path = folder / name
        path.write_bytes((ROOT / "data/bayer_rt/process_model.json").read_bytes())
        return path

    def refuse_unchanged(self, folder, args):
        before = self.snapshot(folder)
        rc, err = self.call(args)
        self.assertEqual(rc, 2, err)
        self.assertTrue(err.startswith("error:"), err)
        self.assertEqual(self.snapshot(folder), before)

    def test_model_overlap_preserves_both_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model = self.model(base, "questions.json")
            (base / "screen.md").write_text("prior report", encoding="utf-8")
            self.refuse_unchanged(base, ["--model", model, "--out", base])

    def test_catalog_and_loop_inputs_are_protected(self):
        for role in ("catalog", "loops"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model = self.model(base)
                target = base / "screen.md"
                target.write_text(json.dumps(CAT) if role == "catalog" else "controller,measurement,output\n",
                                  encoding="utf-8")
                (base / "questions.json").write_text("prior JSON", encoding="utf-8")
                self.refuse_unchanged(base, ["--model", model, "--" + role, target, "--out", base])

    def test_every_schedule_is_protected_even_when_later_entries_replace_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model = base / "model.json"
            model.write_text(json.dumps({"meta": {"model_kind": "extracted_twin"},
                                         "units": [{"id": "P1", "tag": "P-1", "class": "pump", "sheets": ["0"]}],
                                         "instruments": [], "streams": []}), encoding="utf-8")
            first, second = base / "screen.md", base / "later.json"
            first.write_text(json.dumps({"sheets": {"0": [{"tag": "P-1", "service": "Water pump"}]}}),
                             encoding="utf-8")
            second.write_text(json.dumps({"sheets": {"0": [{"tag": "P-1", "service": "Water pump"}]}}),
                              encoding="utf-8")
            (base / "questions.json").write_text("prior JSON", encoding="utf-8")
            self.refuse_unchanged(base, ["--model", model, "--schedule", first, "--schedule", second,
                                         "--out", base])
            rc, err = self.call(["--model", model, "--schedule", first, "--schedule", second, "--out", base])
            self.assertEqual(rc, 2)
            self.assertIn("overlaps input", err)

    def test_rollup_direct_file_and_catalog_inputs_are_protected(self):
        for role in ("screen", "catalog"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                screen = base / ("rollup.json" if role == "screen" else "questions.json")
                screen.write_bytes((EX / "bayer/questions.json").read_bytes())
                args = ["--rollup", "site=" + str(screen if role == "screen" else base)]
                if role == "catalog":
                    catalog = base / "rollup.md"
                    catalog.write_text(json.dumps(CAT), encoding="utf-8")
                    (base / "rollup.json").write_text("prior JSON", encoding="utf-8")
                    args += ["--catalog", catalog]
                else:
                    (base / "rollup.md").write_text("prior report", encoding="utf-8")
                self.refuse_unchanged(base, [*args, "--out", base])

    def test_hardlink_alias_to_source_or_other_output_is_refused(self):
        for alias in ("source", "output"):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model = self.model(base)
                first, second = base / "questions.json", base / "screen.md"
                if alias == "source":
                    os.link(model, first)
                    second.write_text("prior report", encoding="utf-8")
                else:
                    first.write_text("prior JSON", encoding="utf-8")
                    os.link(first, second)
                self.refuse_unchanged(base, ["--model", model, "--out", base])

    def test_symlink_source_alias_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model = self.model(base)
            try:
                (base / "questions.json").symlink_to(model)
            except OSError as exc:
                self.skipTest(f"file symlinks unavailable: {exc}")
            self.refuse_unchanged(base, ["--model", model, "--out", base])

    def test_invalid_second_target_or_parent_preserves_existing_report(self):
        for kind in ("second target directory", "parent file"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                model = self.model(base)
                (base / "questions.json").write_text("prior JSON", encoding="utf-8")
                if kind == "second target directory":
                    (base / "screen.md").mkdir()
                    out = base
                else:
                    out = base / "questions.json" / "reports"
                self.refuse_unchanged(base, ["--model", model, "--out", out])

    def test_implicit_io_list_is_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "data/io_lists/io.csv"
            source.parent.mkdir(parents=True)
            source.write_text("point,description\nPT-1,synthetic fixture\n", encoding="utf-8")
            model = base / "model.json"
            model.write_text(json.dumps({"meta": {"model_kind": "extracted_twin"}, "units": [],
                "instruments": [{"id": "PT-1", "tag": "PT-1", "data_point":
                                 {"point": "PT-1", "source": "io.csv row 2"}}]}), encoding="utf-8")
            os.link(source, base / "questions.json")
            with patch.object(qe, "ROOT", base):
                self.refuse_unchanged(base, ["--model", model, "--out", base])

    def test_same_directory_generation_and_repeated_refresh_remain_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model = self.model(base)
            original = model.read_bytes()
            for args in (["--model", model], ["--rollup", "site=" + str(base)]):
                self.assertEqual(self.call([*args, "--out", base])[0], 0)
                before = self.snapshot(base)
                self.assertEqual(self.call([*args, "--out", base])[0], 0)
                self.assertEqual(self.snapshot(base), before)
            self.assertEqual(model.read_bytes(), original)

    def test_render_failure_leaves_existing_pairs_untouched(self):
        for renderer, args, names in (
                ("render_md", ["--model", ROOT / "data/bayer_rt/process_model.json"],
                 ("questions.json", "screen.md")),
                ("render_rollup_md", ["--rollup", EX / "bayer"], ("rollup.json", "rollup.md"))):
            with self.subTest(renderer=renderer), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                for name in names:
                    (base / name).write_text("prior report", encoding="utf-8")
                before = self.snapshot(base)
                with patch.object(qe, renderer, side_effect=ValueError("render control")):
                    with self.assertRaisesRegex(ValueError, "render control"):
                        self.call([*args, "--out", base])
                self.assertEqual(self.snapshot(base), before)


class CatalogHandoff(unittest.TestCase):
    """A source label must name the selected catalog; a shared ID must not hide a visible definition conflict."""

    def cli(self, args):
        result = subprocess.run([sys.executable, "-S", str(ROOT / "scripts/question_engine.py"),
                                 *map(str, args)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def refuse(self, base, doc, catalog=None, message="conflicts with catalog question E18"):
        source = base / "questions.json"
        source.write_text(json.dumps(doc), encoding="utf-8")
        out = base / "reports"
        out.mkdir()
        for name in ("rollup.json", "rollup.md"):
            (out / name).write_text("prior report", encoding="utf-8")
        before = OutputPublication.snapshot(self, base)
        args = ["--rollup", "fixture=" + str(base), "--out", str(out)]
        if catalog:
            args += ["--catalog", str(catalog)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(qe.main(args), 2)
        self.assertIn(message, err.getvalue())
        self.assertEqual(OutputPublication.snapshot(self, base), before)

    def test_custom_catalog_is_identified_in_both_file_and_stdout_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            catalog = copy.deepcopy(CAT)
            q = next(q for q in catalog["questions"] if q["id"] == "E18")
            q["question"] = "Fictional custom question: " + q["question"]
            path = base / "company-questions.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            site = base / "site"
            args = ["--model", ROOT / "data/bayer_rt/process_model.json", "--question", "E18",
                    "--catalog", path]
            self.cli([*args, "--out", site])
            doc = json.loads((site / "questions.json").read_text(encoding="utf-8"))
            self.assertEqual(doc["catalog"], path.name)
            self.assertEqual(doc["questions"][0]["question"], q["question"])
            for text in ((site / "screen.md").read_text(encoding="utf-8"), self.cli(args)):
                self.assertIn(f"Questions: `{path.name}`", text)
                self.assertIn(q["question"], text)
                self.assertNotIn(str(base), text)
            roll_args = ["--rollup", "fixture=" + str(site), "--catalog", path]
            self.cli([*roll_args, "--out", base / "combined"])
            rolled = json.loads((base / "combined/rollup.json").read_text(encoding="utf-8"))
            self.assertEqual(rolled["catalog"], path.name)
            self.assertEqual(rolled["questions"][0]["question"], q["question"])
            for text in ((base / "combined/rollup.md").read_text(encoding="utf-8"), self.cli(roll_args)):
                self.assertIn(f"Questions: `{path.name}`", text)
                self.assertNotIn(str(base), text)

    def test_rollup_refuses_visible_definition_conflicts_without_replacing_reports(self):
        changes = [("question", "Fictional other question"), ("family", "controls"),
                   ("decision_rule", "Fictional other rule"), ("limits", "Fictional other limit"),
                   ("typical_benefit.wording", "Fictional other wording"),
                   ("typical_benefit.source_titles", ["Fictional other title"]),
                   ("data_requests.how", "Fictional other collection instruction"),
                   ("data_requests.item", "Fictional other collection item")]
        for field, value in changes:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                doc = copy.deepcopy(load("bayer"))
                f = finding(doc, "E18@model")
                parts = field.split(".")
                if parts[0] == "data_requests":
                    f["data_requests"][0][parts[1]] = value
                elif len(parts) == 2:
                    f[parts[0]][parts[1]] = value
                else:
                    f[field] = value
                self.refuse(Path(tmp), doc)

    def test_malformed_findings_and_request_shapes_refuse_clearly(self):
        for bad in (None, {}, "requests", ["request"], [{"item": [], "how": "collect"}]):
            with self.subTest(requests=bad), tempfile.TemporaryDirectory() as tmp:
                doc = copy.deepcopy(load("bayer"))
                finding(doc, "E18@model")["data_requests"] = bad
                self.refuse(Path(tmp), doc)
        for bad in (None, "finding", {"question_id": []}):
            with self.subTest(finding=bad), tempfile.TemporaryDirectory() as tmp:
                doc = copy.deepcopy(load("bayer"))
                doc["questions"] = [bad]
                self.refuse(Path(tmp), doc, message="without a string question_id")

    def test_compatible_catalog_copy_does_not_require_the_same_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base / "reviewed-copy.json"
            path.write_text(json.dumps(CAT), encoding="utf-8")
            self.cli(["--rollup", "fixture=" + str(EX / "bayer"), "--catalog", path, "--out", base / "reports"])
            doc = json.loads((base / "reports/rollup.json").read_text(encoding="utf-8"))
            self.assertEqual(doc["catalog"], path.name)
            self.assertEqual(doc["counts"]["findings"], len(load("bayer")["questions"]))

    def test_ambiguous_catalog_request_instructions_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            catalog = copy.deepcopy(CAT)
            q = next(q for q in catalog["questions"] if q["id"] == "E18")
            q["data_requests"].append(dict(q["data_requests"][0], how="Fictional conflicting instruction"))
            path = base / "catalog.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            self.refuse(base, load("bayer"), catalog=path, message="conflicting instructions for the same request item")


if __name__ == "__main__":
    unittest.main()
