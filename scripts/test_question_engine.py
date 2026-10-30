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
        # a flue O2 analyser; the fryer's exhaust goes to a vapour condenser heat recovery exchanger; K-201's power
        # is metered
        for fid in ("E29@K-203", "E30@EV-202", "E32@O-302", "E31@F-303", "H6@F-303"):
            self.assertNotIn(fid, found)
        c12 = {a["id"] for a in finding(doc, "C12@model")["assets"]}
        self.assertEqual(c12 & {"K-201", "K-202", "K-203"}, {"K-202", "K-203"})
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
            model = self.model(base)
            first, second = base / "screen.md", base / "later.json"
            first.write_text(json.dumps({"sheets": {"0": [{"tag": "P-1", "service": "earlier"}]}}),
                             encoding="utf-8")
            second.write_text(json.dumps({"sheets": {"0": [{"tag": "P-1", "service": "later"}]}}),
                              encoding="utf-8")
            (base / "questions.json").write_text("prior JSON", encoding="utf-8")
            self.refuse_unchanged(base, ["--model", model, "--schedule", first, "--schedule", second,
                                         "--out", base])

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


if __name__ == "__main__":
    unittest.main()
