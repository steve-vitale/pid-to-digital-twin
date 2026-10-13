"""Controls for the TE topology check (scripts/verify_te_topology.py) and the sourced unit purposes.

Needs the cached simulator source (python scripts/fetch_te_data.py) and the cached revised TE code
(python scripts/verify_te_topology.py downloads it). Never downloads anything itself; the "without the revised
code" case is simulated by passing None.
"""
import copy
import json
import re
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import verify_te_topology as vt

ROOT = Path(__file__).resolve().parents[1]
MODEL = json.loads((ROOT / "data/te_process_model.json").read_text(encoding="utf-8"))
PURPOSES = json.loads((ROOT / "data/te_unit_purposes.json").read_text(encoding="utf-8"))
TEPROB = vt.TEPROB.read_text(encoding="latin-1")
# Required: run_tests.py checks it is cached and checksum-verified before this script runs.
if not vt.REVISED_ZIP.exists():
    raise SystemExit("revised TE code not cached; run python scripts/verify_te_topology.py once (network)")
REVISED = zipfile.ZipFile(vt.REVISED_ZIP).read(vt.REVISED_MEMBER).decode("latin-1")


def NEEDS_REVISED(test):  # marker only: these cases use the second source
    return test


def rows(result):
    return {vt.ident(el): (status, fix, caveats) for g in ("units", "streams", "items")
            for el, status, _, caveats, fix in result[g]}


def run(model=MODEL, teprob=TEPROB, revised=REVISED):
    with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
        return vt.full_run(copy.deepcopy(model), teprob, revised)


def edit(model, key, ident, **changes):
    m = copy.deepcopy(model)
    group = m[key]
    target = next(x for x in group if x.get("tag", x.get("id")) == ident)
    target.update(changes)
    for k in ("verification", "topology_verification"):  # forget the recorded history so the check is fresh
        if isinstance(target.get(k), dict):
            target[k].pop("previous", None)
    return m


class SourceParsing(unittest.TestCase):
    def test_pinned_source(self):
        import hashlib
        self.assertEqual(hashlib.sha256(vt.TEPROB.read_bytes()).hexdigest(), vt.TEPROB_SHA256)

    def test_balances_are_read_from_the_code(self):
        src = vt.parse_source(TEPROB)
        self.assertEqual(src["holdup_offset"], {0: "reactor", 9: "separator", 18: "stripper", 27: "header"})
        self.assertEqual(src["balance"][9], {8: 1, 9: -1, 10: -1, 11: -1})   # separator: effluent in, 3 out
        self.assertEqual(src["balance"][27], {1: 1, 2: 1, 3: 1, 5: 1, 9: 1, 6: -1})  # feed header
        self.assertEqual(src["stripper_in"], [4, 11])
        self.assertEqual(src["alias"], {7: 6})

    def test_every_flow_has_a_one_way_driver(self):
        src = vt.parse_source(TEPROB)
        names, groups = vt.header_names(TEPROB)
        topo = vt.derive(src, names, groups)
        for n in topo["ends"]:
            if n in topo["internal"]:
                continue
            ok, why = vt.flow_direction_ok(src, topo, n)
            self.assertTrue(ok, f"FTM({n}): {why}")


class CommittedModelMatchesSource(unittest.TestCase):
    @NEEDS_REVISED
    def test_counts_and_known_results(self):
        result = run()
        self.assertEqual(vt.totals(result), {"confirmed": 51, "corrected": 4, "unresolvable": 1})
        r = rows(result)
        for ident in ("S9", "FI-110", "FV-206", "AI-129"):
            self.assertEqual(r[ident][0], "corrected", ident)
            self.assertIsNone(r[ident][1], ident + " still needs a fix: rerun verify_te_topology.py --write")
        self.assertEqual(r["PI-116"][0], "unresolvable")
        self.assertEqual(r["TI-122"][0], "confirmed")
        self.assertEqual(r["E-101"][0], "confirmed")

    def test_no_pending_fixes_and_recorded_results(self):
        result = run()
        pending = [vt.ident(el) for g in ("units", "streams", "items") for el, _, _, _, fix in result[g] if fix]
        self.assertEqual(pending, [])
        for u in MODEL["units"]:
            self.assertIn(u["verification"]["status"], ("confirmed", "corrected"), u["id"])
        for s in MODEL["streams"]:
            self.assertEqual(s.get("direction"), "forward", s["id"])
        s9 = next(s for s in MODEL["streams"] if s["id"] == "S9")
        self.assertEqual((s9["from"], s9["verification"]["previous"]), ("V-101", {"from": "K-101"}))
        ti122 = next(i for i in MODEL["instruments"] if i["tag"] == "TI-122")
        self.assertEqual(ti122["unit"], "E-101")
        self.assertNotIn("open_question", ti122)
        self.assertIn("resolved_question", ti122["topology_verification"])
        pi116 = next(i for i in MODEL["instruments"] if i["tag"] == "PI-116")
        self.assertEqual(pi116["topology_verification"]["status"], "unresolvable")

    def test_rerun_is_stable(self):
        model = copy.deepcopy(MODEL)
        first = run(model)
        vt.apply(model, first, "2000-01-01", REVISED is not None)
        self.assertEqual(vt.totals(run(model)), vt.totals(first))


class CatchesWrongModels(unittest.TestCase):
    """Each control plants one mistake a hand-built seed could contain and checks the source rejects it."""

    def test_reversed_stream(self):
        r = rows(run(edit(MODEL, "streams", "S6", **{"from": "R-101", "to": "U-100"})))
        self.assertEqual(r["S6"][:2], ("corrected", {"from": "U-100", "to": "R-101"}))

    def test_wrong_endpoint(self):
        r = rows(run(edit(MODEL, "streams", "S10", to="R-101")))
        self.assertEqual(r["S10"][:2], ("corrected", {"to": "C-101"}))

    def test_purge_back_on_compressor(self):
        m = edit(MODEL, "streams", "S9", **{"from": "K-101"})
        m = edit(m, "instruments", "FI-110", unit="K-101")
        r = rows(run(m))
        self.assertEqual(r["S9"][:2], ("corrected", {"from": "V-101"}))
        self.assertEqual(r["FI-110"][:2], ("corrected", {"unit": "V-101"}))

    def test_unit_tag_on_wrong_unit(self):
        r = rows(run(edit(MODEL, "instruments", "PI-107", unit="V-101")))
        self.assertEqual(r["PI-107"][:2], ("corrected", {"unit": "R-101"}))

    def test_valve_on_wrong_unit(self):
        r = rows(run(edit(MODEL, "final_elements", "TV-210", unit="C-101")))
        self.assertEqual(r["TV-210"][:2], ("corrected", {"unit": "R-101"}))

    def test_wrong_stream_on_instrument(self):
        r = rows(run(edit(MODEL, "instruments", "FI-114", stream="S11")))
        self.assertEqual(r["FI-114"][0], "unresolvable")


class ReadsTheCodeNotATable(unittest.TestCase):
    """Change the simulator text and the conclusions must follow it."""

    def test_condenser_heat_term_moved(self):
        text = TEPROB.replace("QUS=UAS*(TWS-TST(8))", "QUS=UAS*(TWS-TST(6))")
        self.assertNotEqual(text, TEPROB)
        r = rows(run(teprob=text))
        self.assertEqual(r["E-101"][0], "unresolvable")
        self.assertNotEqual(r["TI-122"][:2], ("confirmed", None))

    def test_purge_direction_reversed(self):
        text = TEPROB.replace("DLP=PTS-760.0", "DLP=760.0-PTS")
        self.assertNotEqual(text, TEPROB)
        self.assertEqual(rows(run(teprob=text))["S9"][0], "unresolvable")

    def test_purge_drawn_from_header_balance(self):
        text = (TEPROB.replace("YP(I+9)=FCM(I,8)-FCM(I,9)-\n     .FCM(I,10)-FCM(I,11)",
                               "YP(I+9)=FCM(I,8)-FCM(I,9)-\n     .FCM(I,11)")
                .replace(".FCM(I,9)-FCM(I,6)", ".FCM(I,9)-FCM(I,6)-FCM(I,10)"))
        self.assertNotEqual(text, TEPROB)
        # The balances now say the purge leaves the header while its flow is still driven by separator pressure:
        # two code facts disagree, so the check must refuse to confirm or correct.
        self.assertEqual(rows(run(teprob=text))["S9"][:2], ("unresolvable", None))
        both = text.replace("DLP=PTS-760.0", "DLP=PTV-760.0")
        self.assertEqual(rows(run(teprob=both))["S9"][:2], ("corrected", {"from": "U-100"}))

    def test_without_revised_code_only_the_unnumbered_streams_fall_back(self):
        r = rows(run(revised=None))
        for ident in ("S5", "S7", "S7b"):
            self.assertEqual(r[ident][0], "unresolvable", ident)
        self.assertEqual(r["TI-122"][0], "confirmed")  # still 2 condenser names vs 1 separator in teprob.f alone
        self.assertEqual(r["PI-116"][0], "unresolvable")
        self.assertEqual(r["S9"][0], "corrected")

    @NEEDS_REVISED
    def test_revised_code_agrees(self):
        cross = run()["cross_check"]
        self.assertTrue(cross["ran"] and cross["ok"], cross["notes"])
        self.assertEqual(cross["inferred_numbers"], {5: 5, 8: 7})


class UnitPurposes(unittest.TestCase):
    def test_one_sourced_sentence_per_unit(self):
        self.assertEqual(set(PURPOSES["units"]), {u["id"] for u in MODEL["units"]})
        self.assertEqual(PURPOSES["sources"]["teprob"]["sha256"], vt.TEPROB_SHA256)
        for uid, entry in PURPOSES["units"].items():
            text = entry["purpose"]
            self.assertEqual(len(re.findall(r"[.!?](\s|$)", text)), 1, uid + ": one sentence")
            self.assertTrue(any(c["source"] == "teprob" for c in entry["citations"]), uid)

    def test_every_cited_line_still_says_what_is_quoted(self):
        lines = TEPROB.splitlines()
        for uid, entry in PURPOSES["units"].items():
            for c in entry["citations"]:
                if c["source"] != "teprob":
                    continue
                self.assertEqual(re.sub(r"\s", "", lines[c["line"] - 1]), c["code"], f"{uid} line {c['line']}")

    @NEEDS_REVISED
    def test_revised_quotes_exist(self):
        flat = re.sub(r"\s+", " ", REVISED).lower()
        quotes = {"U-100": "vapor phase of header (stream 6)", "E-101": "condenser cooling water outlet temperature",
                  "K-101": "recycle flow to reactor from separator (stream 8)"}
        for uid, quote in quotes.items():
            self.assertIn(quote, flat, uid)
            self.assertTrue(any(c["source"] == "revised" for c in PURPOSES["units"][uid]["citations"]), uid)


if __name__ == "__main__":
    unittest.main()
