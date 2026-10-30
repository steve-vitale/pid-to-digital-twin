"""The impact estimator: formulas on hand-computed cases, units carried, ranges by interval arithmetic, refusal when a
needed constant is missing without --use-defaults, defaults always labelled, every default cites its source and its
derived values recompute, --needs covers every question with a measurable energy quantity, and the committed examples
regenerate byte for byte and match a hand recomputation. Stdlib only."""
import io
import itertools
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import estimate_impact as ei  # noqa: E402

EX = ROOT / "examples" / "impact-estimate"
CONSTS = ei.load_constants()
CAT = ei.load_catalog()
RUNS = {
    "pump-vfd-site": ("pump_vfd_site.json", False),
    "pump-vfd-defaults": ("pump_vfd_measured.json", True),
    "steam-traps-site": ("steam_traps_site.json", False),
    "steam-traps-defaults": ("steam_traps_measured.json", True),
}


def elec(**kw):
    ch = {"type": "electricity", "kw_before": 100, "kw_after": 60, "hours_per_year": 5000}
    ch.update(kw)
    return ch


SITE_E = {"electricity_price_per_kwh": 0.10, "grid_kg_co2e_per_kwh": 0.5}
SITE_F = {"fuel_price_per_mmbtu": 4.0, "fuel_kg_co2e_per_mmbtu": 50.0, "boiler_efficiency": 0.8}


def run(spec, defaults=False):
    return ei.compute(spec, CONSTS, defaults)


def lohi(r):
    return (round(r.lo, 6), round(r.hi, 6))


class Formulas(unittest.TestCase):
    def test_measurement_provenance_survives_json_and_markdown(self):
        notes = {"source": "meter certificate A123", "note": "matched throughput, October survey",
                 "notes": "logged over three shifts"}
        spec = {"site": SITE_E, "changes": [dict(type="electricity", kwh_per_year=3000, **notes)]}
        result = run(spec)
        machine = ei.doc_json(spec, result, "survey.json", False)
        self.assertEqual(machine["changes"][0]["provenance"], notes)
        page = ei.doc_md(spec, result, "survey.json", False)
        for value in notes.values():
            self.assertIn(value, page)

    def test_partial_before_and_added_load_is_refused_as_ambiguous(self):
        with self.assertRaisesRegex(ei.SpecError, "ambiguous.*actual kw_before/kw_after"):
            run({"site": SITE_E, "changes": [dict(type="electricity", kw_before=10, kw_reduction=30,
                                                   hours_per_year=100, increase=True)]})
        for change in (dict(type="electricity", kw_before=10, kw_after=40, hours_per_year=100),
                       dict(type="electricity", kw_reduction=30, hours_per_year=100, increase=True)):
            self.assertEqual(lohi(run({"site": SITE_E, "changes": [change]})["totals"]["kwh"]), (-3000, -3000))

    def test_small_incremental_steam_enthalpy_matches_the_heat_form(self):
        # A condensate-return delta is not the gross enthalpy needed to make steam from feedwater.
        for delta in (0, 0.1, 50, {"low": 25, "high": 75}):
            steam = {"type": "steam", "steam_lb_per_h": 1000, "hours_per_year": 1000,
                     "energy_btu_per_lb": delta}
            value = ei.parse_value(delta, "delta") * 1000
            heat = {"type": "heat", "hours_per_year": 1000, "heat_btu_per_h": value.as_json()}
            a = run({"fuel": "natural_gas", "site": SITE_F, "changes": [steam]})
            b = run({"fuel": "natural_gas", "site": SITE_F, "changes": [heat]})
            for key in ("fuel_mmbtu", "cost", "co2e_scope1_kg"):
                self.assertEqual(lohi(a["totals"][key]), lohi(b["totals"][key]), (delta, key))

    def test_electricity_kw_before_after(self):
        res = run({"changes": [elec()], "site": SITE_E})
        t = res["totals"]
        self.assertEqual(lohi(t["kwh"]), (200000.0, 200000.0))          # (100-60) kW x 5,000 h
        self.assertEqual(lohi(t["cost"]), (20000.0, 20000.0))           # x $0.10/kWh
        self.assertEqual(lohi(t["co2e_scope2_kg"]), (100000.0, 100000.0))  # x 0.5 kg/kWh
        self.assertEqual(lohi(t["co2e_t"]), (100.0, 100.0))
        self.assertEqual(lohi(t["fuel_mmbtu"]), (0.0, 0.0))

    def test_electricity_other_forms_and_demand(self):
        a = run({"changes": [{"type": "electricity", "kw_reduction": 40, "hours_per_year": 5000}], "site": SITE_E})
        b = run({"changes": [{"type": "electricity", "kwh_per_year": 200000}], "site": SITE_E})
        self.assertEqual(lohi(a["totals"]["kwh"]), lohi(b["totals"]["kwh"]))
        c = run({"changes": [elec(demand_kw_reduction=10, demand_months=12)],
                 "site": dict(SITE_E, demand_charge_per_kw_month=12.0)})
        self.assertEqual(lohi(c["totals"]["cost"]), (21440.0, 21440.0))  # 20,000 + 10 kW x $12 x 12

    def test_steam_heat_fuel(self):
        s = run({"fuel": "natural_gas", "site": SITE_F, "changes": [
            {"type": "steam", "steam_lb_per_h": 100, "hours_per_year": 1000, "energy_btu_per_lb": 1000}]})
        # 100 lb/h x 1,000 h x 1,000 Btu/lb = 100 MMBtu useful; / 0.8 = 125 MMBtu fuel; x $4 = $500; x 50 = 6,250 kg
        self.assertEqual(lohi(s["totals"]["fuel_mmbtu"]), (125.0, 125.0))
        self.assertEqual(lohi(s["totals"]["cost"]), (500.0, 500.0))
        self.assertEqual(lohi(s["totals"]["co2e_scope1_kg"]), (6250.0, 6250.0))
        h = run({"fuel": "natural_gas", "site": SITE_F, "changes": [
            {"type": "heat", "heat_btu_per_h": 500000, "hours_per_year": 2000}]})
        self.assertEqual(lohi(h["totals"]["fuel_mmbtu"]), (1250.0, 1250.0))  # 1,000 MMBtu / 0.8
        h2 = run({"fuel": "natural_gas", "site": SITE_F, "changes": [{"type": "heat", "heat_mmbtu_per_year": 1000}]})
        self.assertEqual(lohi(h2["totals"]["fuel_mmbtu"]), (1250.0, 1250.0))
        f = run({"fuel": "natural_gas", "site": SITE_F, "changes": [{"type": "fuel", "mmbtu_per_year": 300}]})
        self.assertEqual(lohi(f["totals"]["cost"]), (1200.0, 1200.0))
        self.assertEqual(lohi(f["totals"]["co2e_scope1_kg"]), (15000.0, 15000.0))

    def test_increase_is_negative_and_mixed_changes_sum(self):
        res = run({"fuel": "natural_gas", "site": dict(SITE_E, **SITE_F), "changes": [
            elec(), {"type": "fuel", "mmbtu_per_year": 300, "increase": True}]})
        self.assertEqual(lohi(res["totals"]["fuel_mmbtu"]), (-300.0, -300.0))
        self.assertEqual(lohi(res["totals"]["cost"]), (18800.0, 18800.0))  # 20,000 - 1,200
        self.assertEqual(lohi(res["totals"]["co2e_t"]), (85.0, 85.0))        # 100 t - 15 t

    def test_units_carried_in_every_step(self):
        res = run({"fuel": "natural_gas", "site": dict(SITE_E, **SITE_F), "changes": [
            elec(), {"type": "steam", "steam_lb_per_h": 100, "hours_per_year": 1000, "energy_btu_per_lb": 1000}]})
        units = [ln[4] for s in res["changes"] for ln in s["lines"]]
        self.assertEqual(units, ["kWh/yr", "$/yr", "kg CO2e/yr", "MMBtu/yr", "MMBtu/yr", "$/yr", "kg CO2e/yr"])
        subs = [ln[2] for s in res["changes"] for ln in s["lines"]]
        self.assertIn("(100 kW - 60 kW) x 5,000 h/yr", subs)
        self.assertIn("100 lb/h x 1,000 h/yr x 1,000 Btu/lb / 1,000,000", subs)

    def test_fuel_price_unit_conversions(self):
        base = {"fuel": "natural_gas", "changes": [{"type": "fuel", "mmbtu_per_year": 100}],
                "site": {"fuel_kg_co2e_per_mmbtu": 50.0}}
        t = run(dict(base, site=dict(base["site"], fuel_price_per_unit=0.55, fuel_price_unit="therm")))
        self.assertAlmostEqual(t["totals"]["cost"].lo, 550.0)  # $0.55/therm = $5.50/MMBtu (1 therm = 0.1 MMBtu)
        m = run(dict(base, site=dict(base["site"], fuel_price_per_unit=5.18, fuel_price_unit="Mcf",
                                     fuel_heat_content_mmbtu_per_unit=1.036)))
        self.assertAlmostEqual(m["totals"]["cost"].lo, 500.0)
        with self.assertRaises(ei.Refusal) as cm:
            run(dict(base, site=dict(base["site"], fuel_price_per_unit=5.18, fuel_price_unit="Mcf")))
        self.assertEqual([x["key"] for x in cm.exception.missing], ["fuel_heat_content_mmbtu_per_unit"])
        d = run(dict(base, site=dict(base["site"], fuel_price_per_unit=5.18, fuel_price_unit="Mcf")), True)
        self.assertAlmostEqual(d["totals"]["cost"].lo, 500.0)  # EIA 1.036 MMBtu/Mcf default
        self.assertIn(ei.DEFAULT_LABEL, d["constants"]["fuel_price_per_mmbtu"]["label"])

    def test_custom_heat_content_keeps_both_site_sources_in_both_outputs(self):
        spec = {"fuel": "natural_gas", "changes": [{"type": "fuel", "mmbtu_per_year": 100}],
                "site": {"fuel_price_per_unit": 5.18, "fuel_price_unit": "Mcf",
                         "fuel_heat_content_mmbtu_per_unit": 1.036, "fuel_kg_co2e_per_mmbtu": 50},
                "site_notes": {"fuel_price_per_unit": "October commodity and delivery invoice",
                               "fuel_heat_content_mmbtu_per_unit": "October invoice Btu factor"}}
        res = run(spec)
        self.assertAlmostEqual(res["totals"]["cost"].lo, 500)
        md = ei.doc_md(spec, res, "site.json", False)
        js = ei.doc_json(spec, res, "site.json", False)
        for note in spec["site_notes"].values():
            self.assertIn(note, md)
            self.assertIn(note, js["constants"]["fuel_price_per_mmbtu"]["label"])
        self.assertNotIn("uses_default", res["constants"]["fuel_price_per_mmbtu"])
        # A site price's source also survives when only its heat-content conversion is public.
        spec["site"].pop("fuel_heat_content_mmbtu_per_unit")
        spec["site_notes"].pop("fuel_heat_content_mmbtu_per_unit")
        res = run(spec, True)
        self.assertIn("October commodity and delivery invoice", res["constants"]["fuel_price_per_mmbtu"]["label"])
        self.assertIn("uses_default", res["constants"]["fuel_price_per_mmbtu"])


class Ranges(unittest.TestCase):
    def test_interval_arithmetic(self):
        R = ei.R
        self.assertEqual(lohi(R(75) - R(45, 50)), (25.0, 30.0))
        self.assertEqual(lohi(R(2, 3) * R(-1, 4)), (-3.0, 12.0))
        self.assertEqual(lohi(R(100) / R(0.8, 1.0)), (100.0, 125.0))
        with self.assertRaises(ValueError):
            R(1) / R(-1, 1)

    def test_range_inputs_give_bounds(self):
        res = run({"changes": [elec(kw_after={"low": 55, "high": 65}, hours_per_year=[4000, 6000])], "site": SITE_E})
        self.assertEqual(lohi(res["totals"]["kwh"]), (140000.0, 270000.0))  # 35x4000 .. 45x6000
        s = run({"fuel": "natural_gas", "site": dict(SITE_F, boiler_efficiency={"low": 0.75, "high": 0.8}),
                 "changes": [{"type": "heat", "heat_mmbtu_per_year": 600}]})
        self.assertEqual(lohi(s["totals"]["fuel_mmbtu"]), (750.0, 800.0))  # low uses the HIGH efficiency

    def test_bad_ranges_and_values_rejected(self):
        for bad in ({"low": 5, "high": 1}, "12", None, True, [1, 2, 3], 10 ** 400, [1, 10 ** 400]):
            with self.assertRaises(ei.SpecError):
                ei.parse_value(bad, "x")

    def test_finite_inputs_cannot_overflow_into_an_invalid_report(self):
        with self.assertRaisesRegex(ei.SpecError, "finite numeric range"):
            run({"changes": [{"type": "electricity", "kw_reduction": 1e308, "hours_per_year": 100}],
                 "site": SITE_E})

    def test_complete_power_ranges_and_partial_physical_bounds(self):
        # This interval difference is complete: 10..20 - 0..5 = 5..20. Comparing reduction.high to before.low
        # would reject it even though the full before/after calculation supplies exactly the same range.
        complete = {"type": "electricity", "kw_before": [10, 20], "kw_after": [0, 5],
                    "kw_reduction": [5, 20], "hours_per_year": [100, 200]}
        for annual in ({}, {"kwh_per_year": [500, 4000]}):
            res = run({"changes": [dict(complete, **annual)], "site": SITE_E})
            self.assertEqual(lohi(res["totals"]["kwh"]), (500, 4000))
            self.assertEqual(set(res["changes"][0]["inputs"]), set(complete) - {"type"} | set(annual))
        partial = {k: v for k, v in complete.items() if k != "kw_after"}
        with self.assertRaisesRegex(ei.SpecError, "can't fall below zero"):
            run({"changes": [partial], "site": SITE_E})
        # With no after range, every independent combination must be feasible. Equality is allowed, one ulp over
        # the minimum before load is not. A complete form also rejects a reduction above every possible before.
        for reduction, accepted in (([5, 10], True), ([5, 10.000000000000002], False)):
            ch = dict(partial, kw_reduction=reduction)
            if accepted:
                self.assertEqual(lohi(run({"changes": [ch], "site": SITE_E})["totals"]["kwh"]), (500, 2000))
            else:
                with self.assertRaisesRegex(ei.SpecError, "can't fall below zero"):
                    run({"changes": [ch], "site": SITE_E})
        with self.assertRaisesRegex(ei.SpecError, "can't fall below zero"):
            run({"changes": [{"type": "electricity", "kw_before": 0, "kw_after": 0,
                               "kw_reduction": 0.001, "hours_per_year": 100}], "site": SITE_E})

    def test_redundant_range_ends_and_rounding_tolerance(self):
        # Overlap is insufficient: both ends describe the same annual quantity and must agree within 1%.
        ch = {"type": "electricity", "kw_before": 100, "kw_after": [55, 65],
              "hours_per_year": 100, "kwh_per_year": [3500, 4500]}
        self.assertEqual(lohi(run({"changes": [ch], "site": SITE_E})["totals"]["kwh"]), (3500, 4500))
        for annual in ([3500, 4600], [3400, 4500]):
            with self.assertRaisesRegex(ei.SpecError, "disagrees"):
                run({"changes": [dict(ch, kwh_per_year=annual)], "site": SITE_E})
        # The tolerance is anchored to the annual figure actually reported, not to an unused peer value.
        for reduction, accepted in ((40.4, True), (40.40001, False)):
            spec = {"changes": [{"type": "electricity", "kwh_per_year": 4000,
                                  "kw_reduction": reduction, "hours_per_year": 100}], "site": SITE_E}
            if accepted:
                self.assertEqual(lohi(run(spec)["totals"]["kwh"]), (4000, 4000))
            else:
                with self.assertRaisesRegex(ei.SpecError, "disagrees"):
                    run(spec)


class QuantityDependencies(unittest.TestCase):
    def test_every_combination_requires_a_path_to_the_annual_quantity(self):
        # Enumerate the input schema, rather than another individual reproducer. These are the nine complete,
        # useful combinations; all other subsets have either a missing calculation or disconnected redundancy.
        fields = {"kwh_per_year": 4000, "kw_before": 100, "kw_after": 60,
                  "kw_reduction": 40, "hours_per_year": 100}
        valid = [
            {"kwh_per_year"},
            {"kw_reduction", "hours_per_year"},
            {"kw_before", "kw_reduction", "hours_per_year"},
            {"kw_before", "kw_after", "hours_per_year"},
            {"kw_before", "kw_after", "kw_reduction", "hours_per_year"},
            {"kwh_per_year", "kw_reduction", "hours_per_year"},
            {"kwh_per_year", "kw_before", "kw_reduction", "hours_per_year"},
            {"kwh_per_year", "kw_before", "kw_after", "hours_per_year"},
            set(fields),
        ]
        for size in range(len(fields) + 1):
            for keys in itertools.combinations(fields, size):
                with self.subTest(keys=keys):
                    ch = dict(type="electricity", **{k: fields[k] for k in keys})
                    if set(keys) in valid:
                        res = run({"changes": [ch], "site": SITE_E})
                        self.assertEqual(lohi(res["totals"]["kwh"]), (4000, 4000))
                        # The output retains each input that constrained the answer, including checked forms.
                        self.assertEqual(set(res["changes"][0]["inputs"]), set(keys))
                    else:
                        with self.assertRaises(ei.SpecError):
                            run({"changes": [ch], "site": SITE_E})

    def test_no_supplied_complete_form_can_disagree_even_with_zero_hours(self):
        base = {"type": "electricity", "kw_before": 100, "kw_after": 60, "kw_reduction": 40,
                "hours_per_year": 100, "kwh_per_year": 4000}
        for field, changed in (("kw_before", 102), ("kw_after", 62), ("kw_reduction", 42),
                               ("hours_per_year", 102), ("kwh_per_year", 4200)):
            with self.subTest(field=field), self.assertRaisesRegex(ei.SpecError, "disagrees"):
                run({"changes": [dict(base, **{field: changed})], "site": SITE_E})
        # Multiplication by zero must not hide a contradictory instantaneous measurement.
        with self.assertRaisesRegex(ei.SpecError, "kw_reduction.*disagrees"):
            run({"changes": [dict(base, hours_per_year=0, kwh_per_year=0, kw_reduction=42)], "site": SITE_E})
        self.assertEqual(lohi(run({"changes": [dict(base, hours_per_year=0, kwh_per_year=0)],
                                  "site": SITE_E})["totals"]["kwh"]), (0, 0))

    def test_heat_redundancy_is_checked_against_the_annual_quantity(self):
        ch = {"type": "heat", "heat_mmbtu_per_year": [1, 2],
              "heat_btu_per_h": [10000, 20000], "hours_per_year": 100}
        spec = {"fuel": "natural_gas", "site": SITE_F, "changes": [ch]}
        res = run(spec)
        self.assertEqual(lohi(res["totals"]["fuel_mmbtu"]), (1.25, 2.5))
        self.assertEqual(set(res["changes"][0]["inputs"]), set(ch) - {"type"})
        for missing in ("heat_btu_per_h", "hours_per_year"):
            with self.subTest(missing=missing), self.assertRaisesRegex(ei.SpecError, "would be ignored"):
                run(dict(spec, changes=[{k: v for k, v in ch.items() if k != missing}]))
        with self.assertRaisesRegex(ei.SpecError, "disagrees"):
            run(dict(spec, changes=[dict(ch, heat_mmbtu_per_year=[1, 3])]))


class Refusals(unittest.TestCase):
    def test_missing_constant_refused_without_defaults(self):
        with self.assertRaises(ei.Refusal) as cm:
            run({"changes": [elec()], "site": {"electricity_price_per_kwh": 0.1}})
        self.assertEqual([m["key"] for m in cm.exception.missing], ["grid_kg_co2e_per_kwh"])
        text = ei.refusal_text(cm.exception.missing, False)
        self.assertIn("https://www.epa.gov/egrid/power-profiler", text)
        self.assertIn("--use-defaults", text)

    def test_cli_refusal_exit_2_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "s.json"
            spec.write_text(json.dumps({"fuel": "natural_gas", "changes": [
                {"type": "steam", "steam_lb_per_h": 100, "hours_per_year": 1000}]}), encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = ei.main(["--estimate", str(spec), "--out", str(Path(d) / "out")])
            self.assertEqual(rc, 2)
            self.assertFalse((Path(d) / "out").exists())
            for key in ("fuel_price_per_mmbtu", "fuel_kg_co2e_per_mmbtu", "boiler_efficiency",
                        "changes[1].energy_btu_per_lb"):
                self.assertIn(key, err.getvalue())

    def test_impossible_inputs_refused_not_estimated(self):
        # Found in the second review round: each of these produced a plausible-looking estimate with exit 0.
        steam = {"type": "steam", "steam_lb_per_h": 100, "hours_per_year": 1000, "energy_btu_per_lb": 1000}
        cases = (
            ({"changes": [elec(hours_per_year=-5)], "site": SITE_E}, "hours_per_year"),
            ({"changes": [elec(hours_per_year=9000)], "site": SITE_E}, "8,760"),
            ({"changes": [elec()], "site": dict(SITE_E, electricity_price_per_kwh=-1)}, "can't be negative"),
            ({"fuel": "natural_gas", "changes": [steam], "site": dict(SITE_F, boiler_efficiency=80)}, "0.82, not 82"),
            ({"fuel": "natural_gas", "changes": [steam], "site": dict(SITE_F, boiler_efficiency=0)}, "boiler_efficiency"),
            ({"fuel": "natural_gas", "changes": [dict(steam, increase="false")], "site": SITE_F}, "true or false"),
            ({"changes": [None]}, "expected an object"),
            ({"changes": [elec(kw_reduction=10)], "site": SITE_E}, "disagrees"),
            ({"changes": [{"type": "electricity", "kwh_per_year": float("inf")}], "site": SITE_E}, "finite"),
            # round 3
            ({"fuel": "natural_gas", "changes": [dict(steam, energy_btu_per_lb=-5)], "site": SITE_F}, "energy_btu_per_lb"),
            ({"fuel": "natural_gas", "changes": [dict(steam, energy_btu_per_lb=50000)], "site": SITE_F}, "1,500 Btu/lb"),
            ({"changes": [elec(kwh_per_year=9999)], "site": SITE_E}, "disagrees"),
            # round 4: kWh against a kW reduction x hours is checked too
            ({"changes": [{"type": "electricity", "kw_reduction": 5, "hours_per_year": 100, "kwh_per_year": 9999}],
              "site": SITE_E}, "disagrees"),
            # round 5 (Codex): with every form given, a contradictory reduction slipped past the kWh check
            ({"changes": [{"type": "electricity", "kw_before": 75, "kw_after": 45, "kw_reduction": 5,
                           "hours_per_year": 100, "kwh_per_year": 3000}], "site": SITE_E}, "disagrees"),
            # round 6 (Codex): one validation pass at the door now covers this whole class
            ({"changes": [{"type": "electricity", "kw_before": 75, "kw_after": [75, 100], "hours_per_year": 100,
                           "increase": True}], "site": SITE_E}, "already carry the sign"),
            ({"changes": [{"type": "electricity", "kw_before": 75, "kw_after": 45, "kw_reduction": 5,
                           "kwh_per_year": 3000}], "site": SITE_E}, "kw_reduction 5 kW disagrees"),
            ({"fuel": "natural_gas", "changes": [{"type": "heat", "heat_mmbtu_per_year": 1000,
                                                  "heat_btu_per_h": 1000000, "hours_per_year": 1}], "site": SITE_F},
             "heat_mmbtu_per_year"),
            ({"fuel": "natural_gas", "changes": [{"type": "fuel", "mmbtu_per_year": 1000}],
              "site": {"fuel_price_per_mmbtu": 1, "fuel_price_per_unit": 1, "fuel_price_unit": "therm",
                       "fuel_kg_co2e_per_mmbtu": 50}}, "give one"),
            ({"fuel": "natural_gas", "changes": [dict(steam, steam_pressure_psig=-100)], "site": SITE_F},
             "steam_pressure_psig"),
            ({"fuel": "natural_gas", "changes": [dict(steam, feedwater_temp_F=-500)], "site": SITE_F},
             "feedwater_temp_F"),
            ({"changes": [elec(kw_befor=10)], "site": SITE_E}, "unknown field(s): kw_befor"),  # a typo is not ignored
            ({"changes": [elec()], "site": dict(SITE_E, electricty_price_per_kwh=0.1)}, "unknown site field"),
            # round 7 (Codex): a strict schema closes the class
            ({"changes": [{"type": "electricity", "kw_before": 10, "kw_reduction": 30, "hours_per_year": 100}],
              "site": SITE_E}, "can't fall below zero"),
            ({"fuel": "natural_gas", "changes": [{"type": "fuel", "mmbtu_per_year": 1000}],
              "site": {"fuel_price_per_unit": 1, "fuel_price_unit": "therm", "fuel_heat_content_mmbtu_per_unit": 1,
                       "fuel_kg_co2e_per_mmbtu": 50}}, "by definition"),
            ({"fuel": "natural_gas", "changes": [dict(steam, heat_mmbtu_per_year=1000)], "site": SITE_F},
             "can't be used in a steam change"),
            ({"changes": [elec()], "change": elec(), "site": SITE_E}, "both 'change' and 'changes'"),
            ({"changes": [elec(kw_reduction={"low": 25, "high": 30, "unit": "MW"}, kw_before=None, kw_after=None)],
              "site": SITE_E}, "nothing else"),
            ({"changes": [elec()], "site": [], "fuel": "natural_gas"}, "'site' must be"),
            ({"fuel": True, "changes": [{"type": "fuel", "mmbtu_per_year": 1000}], "site": SITE_F}, "'fuel' must be"),
            ({"illustrative": "false", "changes": [elec()], "site": SITE_E}, "'illustrative' must be"),
            # round 8 (Codex): every supplied number feeds the result or a check, or it is refused
            ({"changes": [{"type": "electricity", "kwh_per_year": 3000, "hours_per_year": 0}], "site": SITE_E},
             "hours_per_year would be ignored"),
            ({"changes": [{"type": "electricity", "kwh_per_year": 3000, "demand_months": 12}], "site": SITE_E},
             "demand_months would be ignored"),
            ({"changes": [{"type": "electricity", "kw_before": 10, "kw_reduction": [5, 30], "hours_per_year": 100}],
              "site": SITE_E}, "can be more than kw_before"),
            ({"changes": [{"type": "electricity", "kw_before": 75, "kw_after": 100, "kwh_per_year": 3000}],
              "site": SITE_E}, "would be ignored"),
            ({"fuel": "natural_gas", "changes": [{"type": "fuel", "mmbtu_per_year": 1000}],
              "site": dict(SITE_F, fuel_price_unit=42)}, "fuel_price_unit must be text"),
            ({"fuel": "natural_gas", "changes": [{"type": "fuel", "mmbtu_per_year": 1000}],
              "site": dict(SITE_F, fuel_price_unit="therm")}, "without site.fuel_price_per_unit"),
            ({"changes": [elec()], "site": SITE_E, "site_notes": {"electricty_price_per_kwh": "bill"}},
             "site_notes names field"),
            ({"changes": [elec(label={"bad": "object"})], "site": SITE_E}, "label must be text"),
        )
        for spec, msg in cases:
            with self.assertRaises(ei.SpecError, msg=msg) as cm:
                run(spec)
            self.assertIn(msg, str(cm.exception))
        ok = run({"changes": [elec(kw_reduction=40)], "site": SITE_E})  # agrees with 100 - 60
        self.assertEqual(lohi(ok["totals"]["kwh"]), (200000.0, 200000.0))
        # Round 4: a billing-peak cut larger than the average-load cut is possible (a drive that trims the peaks most),
        # so it is not refused; it becomes a stated assumption to check against interval data.
        peak = run({"changes": [elec(demand_kw_reduction=100, demand_months=12)],
                    "site": dict(SITE_E, demand_charge_per_kw_month=10)})
        self.assertTrue(any("interval meter data" in a for a in ei.draft_notes(peak)[1]))

    def test_a_public_conversion_keeps_its_source(self):
        d = run({"fuel": "natural_gas", "changes": [{"type": "fuel", "mmbtu_per_year": 100}],
                 "site": {"fuel_price_per_unit": 5.18, "fuel_price_unit": "Mcf", "fuel_kg_co2e_per_mmbtu": 50}}, True)
        used = d["constants"]["fuel_price_per_mmbtu"]["uses_default"]
        self.assertIn("eia.gov", used["url"])
        self.assertIn(used["source"], ei.doc_md({"changes": []}, d, "s.json", True))

    def test_a_key_written_twice_is_refused(self):
        # Round 7 (Codex): the second value silently replaced the first.
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "dup.json"
            spec.write_text('{"changes":[{"type":"electricity","kwh_per_year":3000,"kwh_per_year":3000000}],'
                            '"site":{"electricity_price_per_kwh":0.1,"grid_kg_co2e_per_kwh":0.5}}', encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = ei.main(["--estimate", str(spec)])
            self.assertEqual(rc, 2)
            self.assertIn("appears twice", err.getvalue())

    def test_an_empty_spec_file_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "empty.json"
            spec.write_text("", encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = ei.main(["--estimate", str(spec)])
            self.assertEqual(rc, 2)
            self.assertIn("empty.json is not valid JSON", err.getvalue())

    def test_plant_facts_never_defaulted(self):
        # No fuel named: refused even with defaults (natural gas is never assumed).
        with self.assertRaises(ei.Refusal) as cm:
            run({"changes": [{"type": "fuel", "mmbtu_per_year": 10}]}, True)
        self.assertIn("fuel", [m["key"] for m in cm.exception.missing])
        # Steam with no pressure / feedwater temperature: no steam-table default.
        with self.assertRaises(ei.Refusal):
            run({"fuel": "natural_gas", "changes": [{"type": "steam", "steam_lb_per_h": 1, "hours_per_year": 1}]},
                True)
        # A pressure the public table does not cover.
        with self.assertRaises(ei.Refusal):
            run({"fuel": "natural_gas", "changes": [{"type": "steam", "steam_lb_per_h": 1, "hours_per_year": 1,
                                                     "steam_pressure_psig": 300, "feedwater_temp_F": 200}]}, True)
        # A measured input missing is an error, never filled in.
        with self.assertRaises(ei.SpecError):
            run({"changes": [{"type": "electricity", "kw_before": 10, "kw_after": 5}], "site": SITE_E}, True)
        # A demand kW reduction needs the user's demand charge: no public default exists.
        with self.assertRaises(ei.Refusal) as cm:
            run({"changes": [elec(demand_kw_reduction=5, demand_months=12)]}, True)
        self.assertEqual([m["key"] for m in cm.exception.missing], ["demand_charge_per_kw_month"])
        # Non-gas fuels have an emission factor default but no price default.
        with self.assertRaises(ei.Refusal) as cm:
            run({"fuel": "propane", "changes": [{"type": "fuel", "mmbtu_per_year": 10}]}, True)
        self.assertEqual([m["key"] for m in cm.exception.missing], ["fuel_price_per_mmbtu"])

    def test_steam_table_lookup_and_interpolation(self):
        self.assertEqual(ei.steam_table_value(CONSTS, 150, 200), (1028, False))
        v, interp = ei.steam_table_value(CONSTS, 450, 230)  # DOE's own worked example uses 1,006 Btu/lb
        self.assertTrue(interp)
        self.assertAlmostEqual(v, 1037 + 0.6 * (986 - 1037))
        self.assertEqual(round(v), 1006)
        self.assertIsNone(ei.steam_table_value(CONSTS, 450, 260))


class Defaults(unittest.TestCase):
    def test_defaults_always_labelled(self):
        res = run({"fuel": "natural_gas", "changes": [elec(), {"type": "steam", "steam_lb_per_h": 100,
                   "hours_per_year": 1000, "steam_pressure_psig": 600, "feedwater_temp_F": 100}]}, True)
        entries = list(res["constants"].values()) + [s["steam_energy"] for s in res["changes"] if s["steam_energy"]]
        self.assertEqual(len(entries), 6)
        for e in entries:
            self.assertEqual(e["origin"], "public_default")
            self.assertTrue(e["label"].startswith(ei.DEFAULT_LABEL + ": "), e["label"])
            self.assertRegex(e["label"], r"\(.+, (19|20)\d\d[;)]")
            self.assertTrue(e["source"] and e["url"].startswith("https://") and e["license"])
        md = ei.doc_md({"title": "t"}, res, "t.json", True)
        self.assertEqual(md.count(ei.DEFAULT_LABEL), 6)

    def test_user_values_win_over_defaults(self):
        res = run({"changes": [elec()], "site": SITE_E}, True)
        self.assertTrue(all(e["origin"] == "user" for e in res["constants"].values()))

    def test_every_default_cites_a_source_and_derived_values_recompute(self):
        allowed = ("www.epa.gov", "www.eia.gov", "www.energy.gov", "www1.eere.energy.gov")
        entries = list(CONSTS["constants"].items()) + list(CONSTS["fuels"].items())
        for name, e in entries:
            for k in ("source", "url", "year", "license", "cite"):
                self.assertTrue(e.get(k), f"{name} lacks {k}")
            self.assertTrue(e["url"].split("/")[2] in allowed, e["url"])
        g = CONSTS["gwp"]
        self.assertEqual((g["CH4"], g["N2O"]), (28, 265))
        for name, f in CONSTS["fuels"].items():
            calc = f["kg_co2_per_mmbtu"] + (f["g_ch4_per_mmbtu"] * g["CH4"] + f["g_n2o_per_mmbtu"] * g["N2O"]) / 1000
            self.assertAlmostEqual(calc, f["kg_co2e_per_mmbtu"], places=6, msg=name)
        ng = CONSTS["fuels"]["natural_gas"]
        self.assertAlmostEqual(ng["kg_co2_per_scf"] + (ng["g_ch4_per_scf"] * 28 + ng["g_n2o_per_scf"] * 265) / 1000,
                               ng["kg_co2e_per_scf"], places=9)
        self.assertAlmostEqual(ng["hhv_mmbtu_per_scf"] * ng["kg_co2_per_mmbtu"], ng["kg_co2_per_scf"], places=4)
        c = CONSTS["constants"]
        kg_lb = CONSTS["unit_conversions"]["kg_per_lb"]["value"]
        self.assertAlmostEqual(c["grid_kg_co2e_per_kwh"]["derived_from"]["lb_co2e_per_mwh"] * kg_lb / 1000,
                               c["grid_kg_co2e_per_kwh"]["value"], places=7)
        p = c["natural_gas_price_per_mmbtu"]["derived_from"]
        self.assertAlmostEqual(p["dollars_per_mcf"] / p["mmbtu_per_mcf"], c["natural_gas_price_per_mmbtu"]["value"],
                               places=6)
        self.assertEqual(p["mmbtu_per_mcf"], c["natural_gas_heat_content_mmbtu_per_mcf"]["value"])
        for row in c["steam_energy_btu_per_lb"]["table"].values():
            self.assertEqual(len(row), len(c["steam_energy_btu_per_lb"]["feedwater_temps_F"]))
        self.assertTrue(CONSTS["not_included"])


class Needs(unittest.TestCase):
    def test_every_question_is_covered_or_excluded_with_a_reason(self):
        ids = [q["id"] for q in CAT["questions"]]
        self.assertEqual(set(ei.NEEDS) & set(ei.NO_ENERGY), set())
        self.assertEqual(set(ei.NEEDS) | set(ei.NO_ENERGY), set(ids))
        energy = {q["id"] for q in CAT["questions"] if q["family"] in ("energy", "heat_grade")}
        self.assertEqual(energy - set(ei.NEEDS), {"E24"})  # water and chemicals, not energy
        for qid, n in ei.NEEDS.items():
            self.assertTrue(set(n["forms"]) <= set(ei.FORM_CONSTANTS), qid)
            self.assertTrue(set(n["measure"]) <= set(ei.MEASURE_INFO), qid)
            self.assertIn("hours" if qid not in ("E16", "C5", "E32") else "fuel_mmbtu", n["measure"], qid)
        for qid, why in ei.NO_ENERGY.items():
            self.assertGreater(len(why), 20, qid)

    def test_needs_output_names_measurements_constants_and_urls(self):
        doc = ei.needs_doc(["E1", "E8", "E20", "C8"], CAT)
        e1, e8, e20, c8 = doc["questions"]
        self.assertEqual([m["key"] for m in e1["measure"]][:2], ["kw", "hours"])
        self.assertEqual({c["key"] for c in e1["constants"]},
                         {"electricity_price_per_kwh", "grid_kg_co2e_per_kwh", "demand_charge_per_kw_month"})
        self.assertEqual({c["key"] for c in e8["constants"]},
                         {"steam_energy_btu_per_lb", "boiler_efficiency", "fuel_price", "fuel_kg_co2e_per_mmbtu"})
        self.assertIn("unload", e20["note"])
        self.assertIn("no_energy_quantity", c8)
        md = ei.needs_md(doc)
        for url in ("https://www.epa.gov/egrid/power-profiler", "https://www.epa.gov/climateleadership/ghg-emission-"
                    "factors-hub", "https://www.eia.gov/electricity/annual/html/epa_02_04.html"):
            self.assertIn(url, md)
        self.assertEqual(ei.needs_ids("energy", CAT)[0], "E1")
        self.assertEqual(len(ei.needs_ids("all", CAT)), len(CAT["questions"]))
        with self.assertRaises(ei.SpecError):
            ei.needs_ids("Z9", CAT)


class Examples(unittest.TestCase):
    def regen(self, args, d):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ei.main([*args, "--out", d]), 0)

    def test_examples_regenerate_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as d:
            for folder, (spec, defaults) in RUNS.items():
                out = Path(d) / folder
                self.regen(["--estimate", str(EX / spec)] + (["--use-defaults"] if defaults else []), str(out))
                for f in ("impact.md", "impact.json"):
                    self.assertEqual((out / f).read_bytes(), (EX / folder / f).read_bytes(), f"{folder}/{f}")
            for q in ("E1", "E8"):
                out = Path(d) / f"needs-{q}"
                self.regen(["--needs", q], str(out))
                for f in ("needs.md", "needs.json"):
                    self.assertEqual((out / f).read_bytes(), (EX / f"needs-{q}" / f).read_bytes(), f"needs-{q}/{f}")

    def test_examples_are_labelled_illustrative_and_carry_no_local_paths(self):
        for spec, _ in RUNS.values():
            s = json.loads((EX / spec).read_text(encoding="utf-8"))
            self.assertTrue(s["illustrative"])
            self.assertIn("ILLUSTRATIVE", s["description"])
        for p in EX.rglob("*"):
            if p.is_file():
                text = p.read_text(encoding="utf-8")
                self.assertIsNone(re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/", text), p.name)
        for folder in RUNS:
            self.assertIn("ILLUSTRATIVE INPUTS", (EX / folder / "impact.md").read_text(encoding="utf-8"))

    def test_every_estimate_is_marked_a_first_draft_with_its_assumptions_and_next_data(self):
        for folder in RUNS:
            md = (EX / folder / "impact.md").read_text(encoding="utf-8")
            js = json.loads((EX / folder / "impact.json").read_text(encoding="utf-8"))
            self.assertIn("FIRST-DRAFT ESTIMATE", md.split("## Result")[0], folder)  # marked before the numbers
            self.assertIn("## Assumptions", md)
            self.assertIn("## To firm this up", md)
            self.assertEqual(js["status"], "first_draft_estimate")
            self.assertTrue(js["assumptions"] and js["to_firm_up"])
            public = [k for k, e in js["constants"].items() if e and e.get("origin") == "public_default"]
            self.assertEqual(sum("public typical value" in a for a in js["assumptions"]), len(public), folder)
            self.assertEqual(sum(x.startswith("Replace the public") for x in js["to_firm_up"]), len(public), folder)
            self.assertIn("before/after pair", js["to_firm_up"][-1])
            self.assertIn(("Screening grade" if public else "First draft on site constants"), js["grade"])

    def test_a_public_conversion_is_an_assumption_too(self):
        # Round 4: the public Mcf heat content behind a site price per Mcf was missing from the draft notes.
        res = run({"fuel": "natural_gas", "changes": [{"type": "fuel", "mmbtu_per_year": 1000}],
                   "site": {"fuel_price_per_unit": 5.23, "fuel_price_unit": "Mcf", "fuel_kg_co2e_per_mmbtu": 53.1}}, True)
        grade, A, F = ei.draft_notes(res)
        self.assertTrue(any("heat content" in a for a in A), A)
        self.assertTrue(any(f.startswith("Replace the public gas heat content") for f in F), F)
        self.assertIn("1 of 3 constants", grade)  # price and factor are the site's; the conversion is public
        # Round 5: the same run crashed writing impact.json (a range nested in uses_default). Go through the writer.
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "mcf.json"
            spec.write_text(json.dumps({"fuel": "natural_gas", "changes": [{"type": "fuel", "mmbtu_per_year": 1000}],
                                        "site": {"fuel_price_per_unit": 5.23, "fuel_price_unit": "Mcf",
                                                 "fuel_kg_co2e_per_mmbtu": 53.1}}), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = ei.main(["--estimate", str(spec), "--use-defaults", "--out", str(Path(d) / "out")])
            self.assertEqual(rc, 0)
            js = json.loads((Path(d) / "out" / "impact.json").read_text(encoding="utf-8"))
            self.assertEqual(js["constants"]["fuel_price_per_mmbtu"]["uses_default"]["value"], 1.036)

    def test_examples_match_hand_recomputation(self):
        """Independent arithmetic, written out, against the committed totals."""
        def tot(folder):
            return json.loads((EX / folder / "impact.json").read_text(encoding="utf-8"))["totals"]

        def close(got, lo, hi):
            got = got if isinstance(got, dict) else {"low": got, "high": got}
            self.assertAlmostEqual(got["low"], lo, delta=abs(lo) * 1e-6 + 1e-6)
            self.assertAlmostEqual(got["high"], hi, delta=abs(hi) * 1e-6 + 1e-6)

        # Pump, site constants: (75 - 50..45) kW x 8,000 h = 200,000..240,000 kWh
        t = tot("pump-vfd-site")
        close(t["electricity_kwh_per_year"], 200000, 240000)
        close(t["cost_per_year"], 200000 * 0.092 + 25 * 14.5 * 12, 240000 * 0.092 + 25 * 14.5 * 12)  # 22,750..26,430
        close(t["co2e_t_per_year"], 84.0, 100.8)
        # Pump, defaults: EIA 8.51 c/kWh; eGRID 770.884 lb/MWh x 0.45359237 / 1000
        t = tot("pump-vfd-defaults")
        close(t["cost_per_year"], 17020.0, 20424.0)
        g = 770.884 * 0.45359237 / 1000
        close(t["co2e_t_per_year"], round(g, 7) * 200, round(g, 7) * 240)  # ~69.93..83.92 t
        # Steam traps, site: 150..210 lb/h x 8,760 h x 1,000 Btu/lb = 1,314..1,839.6 MMBtu; / 0.82..0.78
        t = tot("steam-traps-site")
        close(t["fuel_mmbtu_per_year"], 1314 / 0.82, 1839.6 / 0.78)
        close(t["cost_per_year"], 1314 / 0.82 * 5.5, 1839.6 / 0.78 * 5.5)       # $0.55/therm = $5.50/MMBtu
        close(t["co2e_scope1_kg_per_year"], 1314 / 0.82 * 53.11, 1839.6 / 0.78 * 53.11)
        # Steam traps, defaults: DOE 1,028 Btu/lb (150 psig, 200 F), EPA 80%, EIA $5.23/Mcf / 1.036, EPA 53.1145
        t = tot("steam-traps-defaults")
        lo, hi = 150 * 8760 * 1028 / 1e6 / 0.8, 210 * 8760 * 1028 / 1e6 / 0.8  # 1,688.49..2,363.886 MMBtu
        close(t["fuel_mmbtu_per_year"], lo, hi)
        close(t["cost_per_year"], lo * round(5.23 / 1.036, 6), hi * round(5.23 / 1.036, 6))
        close(t["co2e_scope1_kg_per_year"], lo * 53.1145, hi * 53.1145)


class OutputPreservation(unittest.TestCase):
    def test_all_active_inputs_and_both_outputs_are_protected_before_any_write(self):
        for mode, role, stem in (("estimate", "spec", "impact"), ("estimate", "constants", "impact"),
                                 ("needs", "catalog", "needs")):
            for extension in ("md", "json"):
                with self.subTest(mode=mode, role=role, extension=extension), tempfile.TemporaryDirectory() as d:
                    folder = Path(d)
                    spec, constants, catalog = (folder / name for name in ("spec.json", "constants.json", "catalog.json"))
                    spec.write_bytes((EX / "pump_vfd_site.json").read_bytes())
                    constants.write_bytes(ei.CONSTANTS.read_bytes())
                    catalog.write_bytes(ei.CATALOG.read_bytes())
                    source = {"spec": spec, "constants": constants, "catalog": catalog}[role]
                    out = folder / "out"
                    out.mkdir()
                    target = out / f"{stem}.{extension}"
                    target.hardlink_to(source)
                    companion = out / f"{stem}.{'json' if extension == 'md' else 'md'}"
                    companion.write_bytes(b"retain companion too")
                    before = {p: p.read_bytes() for p in (spec, constants, catalog, target, companion)}
                    args = (["--estimate", str(spec), "--constants", str(constants)] if mode == "estimate" else
                            ["--needs", "all", "--catalog", str(catalog)])
                    err = io.StringIO()
                    with redirect_stdout(io.StringIO()), redirect_stderr(err):
                        code = ei.main(args + ["--out", str(out)])
                    self.assertEqual(code, 2, err.getvalue())
                    self.assertIn("output aliases an input", err.getvalue())
                    self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_exact_spec_collision_and_aliased_outputs_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            spec = folder / "impact.json"
            spec.write_bytes((EX / "pump_vfd_site.json").read_bytes())
            before = spec.read_bytes()
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                code = ei.main(["--estimate", str(spec), "--out", str(folder)])
            self.assertEqual(code, 2)
            self.assertEqual(spec.read_bytes(), before)
            self.assertFalse((folder / "impact.md").exists())
            out = folder / "out"
            out.mkdir()
            md = out / "impact.md"
            md.write_bytes(b"retain both")
            (out / "impact.json").hardlink_to(md)
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                code = ei.main(["--estimate", str(spec), "--out", str(out)])
            self.assertEqual(code, 2)
            self.assertIn("files alias each other", err.getvalue())
            self.assertEqual(md.read_bytes(), b"retain both")


if __name__ == "__main__":
    unittest.main(verbosity=1)
