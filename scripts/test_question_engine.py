"""The question engine: the catalog is well-formed and every question cites a known source or says it has none,
the committed opportunity-screen examples regenerate exactly, known findings appear and known false triggers stay
quiet, the three evidence states come out right, and no output carries a currency symbol or a computed figure.
Stdlib only."""
import io
import json
import re
import sys
import tempfile
import unittest
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
}
SELECTOR_KEYS = {"kind", "type", "type_text", "isa", "variable", "text", "text_all", "not_text", "tagged",
                 "control_valve", "fact_C_min", "fact_C_max", "schedule_field"}
CLAUSE_KEYS = {"select", "relation", "max_hops", "as", "twin_only", "hand_only", "anchor_kind"}
RELATIONS = {"same_unit", "same_stream", "same_unit_same_medium", "other_unit", "discharge_side", "near", "drives",
             "reads", "anywhere"}
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
        self.assertEqual(fam, {"energy": 24, "heat_grade": 4, "metering": 1, "controls": 7, "safety_question": 2,
                               "emissions": 2})


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
                  "open100": "out/twin/r2-tiles-trace/codex/plant_model.json"}
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


if __name__ == "__main__":
    unittest.main()
