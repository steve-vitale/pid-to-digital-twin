"""Turn a measured energy change into an annual energy, cost and CO2e estimate, with every formula and constant shown.

    python -S scripts/estimate_impact.py --needs E1
    python -S scripts/estimate_impact.py --needs energy --out out/needs-energy
    python -S scripts/estimate_impact.py --estimate examples/impact-estimate/pump_vfd_site.json
    python -S scripts/estimate_impact.py --estimate my_spec.json --use-defaults --out out/impact-pump

--needs QUESTION_ID (or a family such as energy, or all) prints, for questions in data/questions.json, which measured
quantities and which site constants an estimate needs, and where each constant comes from, with URLs.

--estimate SPEC.json computes annual energy, cost and CO2e from what the engineer measured. A spec holds one or more
changes, each in one form: electricity (kW before/after or kW reduction x hours/year, or kWh/year; optional demand kW
reduction), fuel (MMBtu/year), steam (lb/h x hours x Btu/lb / boiler efficiency -> fuel) or heat (Btu/h x hours, or
MMBtu/year, / boiler efficiency -> fuel); plus the site constants (prices, emission factors, boiler efficiency). Any
number may be a range {"low": a, "high": b}; the result is then a range, computed by interval arithmetic.

It never invents a plant input. Measured quantities (kW, hours, lb/h, Btu/h, MMBtu) and the plant's fuel and steam
conditions must come from the user. A missing site constant is refused unless --use-defaults is given; then it is taken
from data/impact_constants.json and printed as "PUBLIC TYPICAL VALUE, replace with your own: <value> (source, year)".
Electricity CO2e is location-based Scope 2 at the grid factor given; fuel CO2e is Scope 1 combustion. Estimates only:
no savings come from a drawing alone. Writes impact.md and impact.json with --out. Stdlib only; no network.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTANTS = ROOT / "data" / "impact_constants.json"
CATALOG = ROOT / "data" / "questions.json"
DEFAULT_LABEL = "PUBLIC TYPICAL VALUE, replace with your own"

# ---------------------------------------------------------------------------------------------------------------
# Ranges: every number is an interval [lo, hi]; a point value has lo == hi.


class R:
    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi=None):
        hi = lo if hi is None else hi
        if lo > hi:
            raise ValueError(f"range low {lo} is above high {hi}")
        self.lo, self.hi = float(lo), float(hi)

    @property
    def point(self):
        return self.lo == self.hi

    def __add__(self, o):
        return R(self.lo + o.lo, self.hi + o.hi)

    def __sub__(self, o):
        return R(self.lo - o.hi, self.hi - o.lo)

    def __neg__(self):
        return R(-self.hi, -self.lo)

    def __mul__(self, o):
        o = o if isinstance(o, R) else R(o)
        p = (self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi)
        return R(min(p), max(p))

    def __truediv__(self, o):
        o = o if isinstance(o, R) else R(o)
        if o.lo <= 0 <= o.hi:
            raise ValueError("division by a range that includes zero")
        return self * R(1.0 / o.hi, 1.0 / o.lo)

    def as_json(self):
        return {"low": sig(self.lo, 7), "high": sig(self.hi, 7)} if not self.point else sig(self.lo, 7)


def sig(x, n=4):
    if x == 0 or not math.isfinite(x):
        return 0.0 if x == 0 else x
    v = round(x, n - 1 - int(math.floor(math.log10(abs(x)))))
    return int(v) if float(v).is_integer() and abs(v) >= 1 else v


def num(x, n=6):
    """A readable number: n significant figures, thousands separators, no trailing zeros."""
    v = sig(x, n)
    if isinstance(v, int):
        return f"{v:,}"
    s = f"{v:,.{max(0, n - 1 - int(math.floor(math.log10(abs(v)))))}f}" if v else "0"
    return s.rstrip("0").rstrip(".") if "." in s else s


def money(r, n=3):
    def m(x):
        return f"-${num(-x, n)}" if x < 0 else f"${num(x, n)}"
    return m(r.lo) if r.point else f"{m(r.lo)} to {m(r.hi)}"


def show(r, unit="", n=6):
    u = f" {unit}" if unit else ""
    return f"{num(r.lo, n)}{u}" if r.point else f"{num(r.lo, n)} to {num(r.hi, n)}{u}"


def parse_value(v, name):
    """A spec number: 12.5, {"low": 10, "high": 15} or [10, 15]."""
    if isinstance(v, bool) or v is None:
        raise SpecError(f"{name}: expected a number or a low/high range, got {v!r}")
    if isinstance(v, (int, float)):
        if not math.isfinite(v):
            raise SpecError(f"{name}: {v!r} is not a finite number")
        return R(v)
    if isinstance(v, dict) and set(v) >= {"low", "high"}:
        lo, hi = v["low"], v["high"]
    elif isinstance(v, list) and len(v) == 2:
        lo, hi = v
    else:
        raise SpecError(f"{name}: expected a number or a low/high range, got {v!r}")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (lo, hi)):
        raise SpecError(f"{name}: range ends must be numbers")
    if not all(math.isfinite(x) for x in (lo, hi)):
        raise SpecError(f"{name}: {v!r} is not a finite number")
    if lo > hi:
        raise SpecError(f"{name}: low {lo} is above high {hi}")
    return R(lo, hi)


# A value outside these bounds is a typo or a unit slip (85 for 85%, hours per week for hours per year), and the
# estimate would come out plausible-looking and wrong, so it is refused instead. Anything not listed must be >= 0.
BOUNDS = {"hours_per_year": (0, 8784, "a year has 8,760 hours, 8,784 in a leap year"),
          "demand_months": (0, 12, "a year has 12 billing months"),
          "boiler_efficiency": (0, 1, "a fraction: give 0.82, not 82"),
          "feedwater_temp_F": (32, 400, "feedwater between freezing and 400 F"),
          "steam_pressure_psig": (0, 3000, "a gauge pressure up to 3,000 psig"),
          "energy_btu_per_lb": (100, 1600, "steam carries roughly 900 to 1,500 Btu/lb from feedwater; check the unit")}


def bounded(r, name, key):
    lo, hi, why = BOUNDS.get(key, (0, None, "it can't be negative; mark a change that adds load with "
                                            "\"increase\": true instead"))
    if r.lo < lo or (hi is not None and r.hi > hi) or (key == "boiler_efficiency" and r.lo <= 0):
        rng = f"{lo} to {hi}" if hi is not None else f"at least {lo}"
        shown = show(r) if max(abs(r.lo), abs(r.hi)) < 1e12 else f"{r.lo:.3g}"
        raise SpecError(f"{name}: {shown} is outside {rng} ({why})")
    return r


class SpecError(Exception):
    pass


class Refusal(Exception):
    def __init__(self, missing):
        super().__init__("missing site constants")
        self.missing = missing


# ---------------------------------------------------------------------------------------------------------------
# What each constant is and where it comes from (shared by --needs and the refusal message).

URL = {
    "egrid_profiler": "https://www.epa.gov/egrid/power-profiler",
    "egrid_data": "https://www.epa.gov/egrid/summary-data",
    "ghg_hub": "https://www.epa.gov/climateleadership/ghg-emission-factors-hub",
    "eia_elec": "https://www.eia.gov/electricity/annual/html/epa_02_04.html",
    "eia_gas": "https://www.eia.gov/dnav/ng/ng_pri_sum_dcu_nus_a.htm",
    "eia_heat": "https://www.eia.gov/dnav/ng/ng_cons_heat_a_EPG0_VGTH_btucf_a.htm",
    "doe_steam15": "https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/steam15_benchmark.pdf",
    "doe_steam1": "https://www.energy.gov/sites/prod/files/2014/05/f16/steam1_traps.pdf",
    "doe_air3": "https://www.energy.gov/sites/prod/files/2014/05/f16/compressed_air3.pdf",
    "doe_air_book": "https://www.energy.gov/sites/default/files/2016/03/f30/Improving%20Compressed%20Air%20Sourcebook%20version%203.pdf",
    "doe_steam_book": "https://www.energy.gov/sites/prod/files/2014/05/f15/steamsourcebook.pdf",
}

CONST_INFO = {
    "electricity_price_per_kwh": {
        "name": "Electricity energy price", "unit": "$/kWh",
        "where": "Your electricity bill and rate schedule: the energy charge per kWh in the hours the change applies "
                 "(weight time-of-use periods by the hours saved in each). Not total bill / total kWh, which mixes in "
                 "demand and fixed charges.",
        "public": "EIA Electric Power Annual Table 2.4, US average industrial price (2025)",
        "urls": [URL["eia_elec"]], "default": "electricity_price_per_kwh"},
    "demand_charge_per_kw_month": {
        "name": "Demand charge (only to estimate a demand kW reduction)", "unit": "$/kW-month",
        "where": "Your electricity bill and rate schedule: the demand charge per kW per month, its billing interval "
                 "(often 15 minutes) and any ratchet clause. A kW reduction saves demand charges only if it lowers the "
                 "billing peak; check against interval meter data. Never defaulted.",
        "public": None, "urls": [], "default": None},
    "grid_kg_co2e_per_kwh": {
        "name": "Grid emission factor", "unit": "kg CO2e/kWh",
        "where": "Location-based Scope 2: the EPA eGRID total output emission rate (CO2e) for your eGRID subregion; "
                 "find the subregion by ZIP code in EPA's Power Profiler, then read the rate from the eGRID summary "
                 "tables. Market-based Scope 2 instead uses your utility's published supplier-specific emission "
                 "factor or your contract instruments (RECs, PPAs). Subregion rates differ about 5 times.",
        "public": "EPA eGRID2023 US total output CO2e rate",
        "urls": [URL["egrid_profiler"], URL["egrid_data"]], "default": "grid_kg_co2e_per_kwh"},
    "fuel_price": {
        "name": "Fuel price", "unit": "$/MMBtu (or $/therm, $/Mcf with heat content)",
        "where": "Your gas bill or fuel supply contract: commodity plus transport/delivery per unit, at the margin "
                 "(the price of the next unit you would not buy). For gas billed per Mcf or ccf, the bill's heat "
                 "content (Btu factor) converts it to MMBtu.",
        "public": "EIA US natural gas industrial price (2025), natural gas only",
        "urls": [URL["eia_gas"], URL["eia_heat"]], "default": "natural_gas_price_per_mmbtu"},
    "fuel_kg_co2e_per_mmbtu": {
        "name": "Fuel emission factor", "unit": "kg CO2e/MMBtu (HHV)",
        "where": "EPA GHG Emission Factors Hub, Table 1 Stationary Combustion: CO2, CH4 and N2O per MMBtu for your "
                 "fuel, combined with the Hub's GWPs (AR5: CH4 28, N2O 265). If your supplier gives a measured carbon "
                 "content or heat content, use it.",
        "public": "EPA GHG Emission Factors Hub (2025) Table 1",
        "urls": [URL["ghg_hub"]], "default": "fuel"},
    "boiler_efficiency": {
        "name": "Boiler (or heater) efficiency", "unit": "fraction, fuel HHV in to useful heat out",
        "where": "Your boiler's efficiency test (fuel-to-steam, input-output or heat-loss method), a combustion "
                 "analyzer reading plus shell and blowdown losses, or the boiler design datasheet. For heat that "
                 "displaces a different heater, that heater's efficiency.",
        "public": "EPA GHG Emission Factors Hub (2025) Table 7 assumption, 80% thermal efficiency",
        "urls": [URL["ghg_hub"], URL["doe_steam15"]], "default": "boiler_efficiency"},
    "steam_energy_btu_per_lb": {
        "name": "Energy per lb of steam", "unit": "Btu/lb",
        "where": "Steam tables: enthalpy of the steam at its line pressure and temperature minus the enthalpy of the "
                 "water that replaces it (feedwater, or makeup water if the condensate is not returned). DOE Steam Tip "
                 "Sheet #15 Table 1 tabulates saturated steam at 150, 450 and 600 psig.",
        "public": "DOE Steam Tip Sheet #15 Table 1 (needs your steam pressure and feedwater temperature)",
        "urls": [URL["doe_steam15"]], "default": "steam_energy_btu_per_lb"},
}

MEASURE_INFO = {
    "kw": "Average electrical input kW before and after (or the kW reduction): a clamp-on three-phase power meter, "
          "the drive or MCC power reading, or the historian's motor kW tag, over a representative period at the "
          "same production rate. An estimate from curves (pump/fan curve and affinity laws) must say so.",
    "hours": "Operating hours per year the change applies: historian run status, the operating schedule, or "
             "maintenance records. Not 8,760 unless it really runs all year.",
    "demand_kw": "Optional: the reduction in billing-peak kW (interval meter data at the billing interval) and "
                 "the months it applies.",
    "steam_lb_h": "Steam flow saved or lost, lb/h: a steam flowmeter, or a survey estimate (for failed traps, the "
                  "survey's orifice-based loss per trap; DOE Steam Tip Sheet #1 prints one such table).",
    "steam_conditions": "Steam pressure (psig) and temperature at the point of loss, and the feedwater or makeup "
                        "water temperature: gauges, the historian, the deaerator.",
    "heat_btu_h": "Useful heat saved or recovered, Btu/h: measured flow x specific heat x temperature change on the "
                  "stream, or a heat-loss calculation from surface and ambient temperatures (bare pipe, flanges).",
    "fuel_mmbtu": "Fuel use before and after, MMBtu/year (HHV): the fuel meter or gas bills at the same production "
                  "rate, corrected to the same hours.",
    "boiler_fuel": "Which fuel the boiler or heater fires (the tool will not assume natural gas).",
}

# Question id -> what to measure and which constants an estimate needs. Forms follow the --estimate spec types.
NEEDS = {
    "E1": {"forms": ["electricity"], "measure": ["kw", "hours", "demand_kw"],
           "note": "Pump on a variable speed drive: measured kW before and after. Before installing, the after kW can "
                   "only be estimated from the flow-duration curve, the pump curve and the static head; say so."},
    "E2": {"forms": ["electricity"], "measure": ["kw", "hours", "demand_kw"],
           "note": "Oversized pump (bypass open): kW before and after trimming the impeller or closing the bypass."},
    "E3": {"forms": ["electricity"], "measure": ["kw", "hours"],
           "note": "Continuous minimum-flow recirculation: pump kW with the recirculation open and closed (where it "
                   "is safe to close), and the hours it is open."},
    "E4": {"forms": ["electricity"], "measure": ["kw", "hours"],
           "note": "Oversized motor: measured input kW now, and the input kW a right-sized motor would draw at the "
                   "same shaft load (kW x present efficiency / new efficiency, from nameplates or the vendor)."},
    "E5": {"forms": ["electricity"], "measure": ["kw", "hours", "demand_kw"],
           "note": "Damper or inlet-vane control: fan kW before and after speed control."},
    "E6": {"forms": ["electricity", "steam"], "measure": ["kw", "hours"],
           "note": "Compressor recycle or blow-off: compressor kW before and after reducing recycle. If a steam "
                   "turbine drives it, the turbine's steam lb/h saved instead (steam form)."},
    "E7": {"forms": ["electricity", "steam"], "measure": ["kw", "hours", "steam_lb_h", "steam_conditions",
                                                           "boiler_fuel"],
           "note": "Backpressure turbogenerator across a pressure-reducing station: the kW it would generate x hours "
                   "(an electricity saving) AND the extra boiler fuel for the heat it extracts (steam lb/h x enthalpy "
                   "drop across the turbine, as a steam change marked increase: true)."},
    "E8": {"forms": ["steam"], "measure": ["steam_lb_h", "hours", "steam_conditions", "boiler_fuel"],
           "note": "Failed steam traps: steam lost per failed trap (lb/h, from the survey) x number failed, hours the "
                   "steam is on, the energy per lb at those conditions, then fuel via boiler efficiency."},
    "E9": {"forms": ["steam"], "measure": ["steam_lb_h", "hours", "steam_conditions", "boiler_fuel"],
           "note": "Condensate to drain: condensate lb/h not returned, its temperature and the makeup water "
                   "temperature; energy per lb is the enthalpy difference. Water and treatment chemicals not costed."},
    "E10": {"forms": ["steam"], "measure": ["steam_lb_h", "hours", "steam_conditions", "boiler_fuel"],
            "note": "Flash steam to atmosphere: flash steam lb/h that would displace low-pressure steam (flash "
                    "fraction from steam tables x condensate flow), hours."},
    "E11": {"forms": ["heat"], "measure": ["heat_btu_h", "hours", "boiler_fuel"],
            "note": "Bare hot line: heat loss Btu/h bare and insulated (surface and ambient temperature, pipe size "
                    "and length), hours."},
    "E12": {"forms": ["heat"], "measure": ["heat_btu_h", "hours", "boiler_fuel"],
            "note": "Bare valves and flanges: heat loss Btu/h per fitting bare and with removable covers, count, hours."},
    "E13": {"forms": ["heat", "steam"], "measure": ["heat_btu_h", "steam_lb_h", "hours", "boiler_fuel"],
            "note": "Manual blowdown: blowdown lb/h now and with automatic control, and the heat recoverable from it "
                    "(Btu/lb from steam tables), hours."},
    "E14": {"forms": ["fuel", "heat"], "measure": ["fuel_mmbtu", "heat_btu_h", "hours", "boiler_fuel"],
            "note": "Feedwater economizer: boiler fuel before and after, or the heat recovered into feedwater (Btu/h) "
                    "divided by boiler efficiency."},
    "E15": {"forms": ["heat"], "measure": ["heat_btu_h", "hours", "boiler_fuel"],
            "note": "Condensing economizer: heat recovered into the cold stream (Btu/h) and the hours the load exists."},
    "E16": {"forms": ["fuel"], "measure": ["fuel_mmbtu", "boiler_fuel"],
            "note": "O2 trim: fuel use before and after at the same steam load (or the combustion efficiency change "
                    "from flue O2 and stack temperature applied to annual fuel)."},
    "E17": {"forms": ["heat"], "measure": ["heat_btu_h", "hours", "boiler_fuel"],
            "note": "Flue gas heat recovery: heat recovered (Btu/h) that displaces fired heat, hours."},
    "E18": {"forms": ["heat", "steam"], "measure": ["heat_btu_h", "steam_lb_h", "hours", "boiler_fuel"],
            "note": "Heat integration: the duty of the new exchanger (Btu/h) or the steam it displaces (lb/h), hours "
                    "both streams run at once."},
    "E19": {"forms": ["electricity"], "measure": ["kw", "hours"],
            "note": "Compressed air header pressure: compressor kW before and after lowering the setpoint."},
    "E20": {"forms": ["electricity"], "measure": ["kw", "hours"],
            "note": "Compressed air leaks: compressor kW when loaded and when unloaded, and the leak load from a "
                    "no-production test (the kW drawn, or the fraction of time loaded, with all users off), hours "
                    "the system is pressurized. kW reduction = leak load kW actually shed by the compressor controls."},
    "E21": {"forms": ["electricity"], "measure": ["kw", "hours"],
            "note": "Inappropriate air use: the user's air flow (cfm) x the plant's measured kW per cfm, hours."},
    "E22": {"forms": ["electricity"], "measure": ["kw", "hours", "demand_kw"],
            "note": "Storage: compressor kW before and after adding storage or changing controls."},
    "E23": {"forms": ["heat", "electricity"], "measure": ["heat_btu_h", "hours", "boiler_fuel", "kw"],
            "note": "Compressor heat recovery: heat recovered (Btu/h) that displaces a fuel heater (heat form, with "
                    "that heater's efficiency) or an electric heater (electricity form), hours."},
    "H1": {"forms": ["electricity", "steam"], "measure": ["kw", "hours", "steam_lb_h", "steam_conditions",
                                                           "boiler_fuel"],
           "note": "High-grade steam let down: as E7 if a turbine recovers the pressure drop; or the steam lb/h "
                   "saved if a lower-grade source takes over."},
    "H2": {"forms": ["steam", "heat"], "measure": ["steam_lb_h", "hours", "steam_conditions", "boiler_fuel"],
           "note": "High-grade steam for a low-temperature job: the steam lb/h (or heat) the lower-grade source would "
                   "displace, hours."},
    "H3": {"forms": ["electricity", "heat"], "measure": ["kw", "hours", "heat_btu_h", "boiler_fuel"],
           "note": "Electric resistance heat: heater kW x hours avoided, and the replacement heat as a heat change "
                   "marked increase: true if it is fuel-fired (nothing if it is true waste heat)."},
    "H4": {"forms": ["heat", "electricity"], "measure": ["heat_btu_h", "hours", "boiler_fuel", "kw"],
           "note": "Heat to cooling water: heat recovered (Btu/h) into a user that now takes steam or fuel, hours; "
                   "optionally cooling water pump or tower fan kW saved."},
    "C5": {"forms": ["fuel"], "measure": ["fuel_mmbtu", "boiler_fuel"],
           "note": "Boiler O2 trim: fuel before and after at the same load (as E16). Three-element level control is "
                   "a controls question with no energy quantity of its own."},
    "C7": {"forms": ["electricity"], "measure": ["kw", "hours", "demand_kw"],
           "note": "Compressor sequencing: total compressor kW before and after a master sequencer, same air demand."},
    "C10": {"forms": ["steam"], "measure": ["steam_lb_h", "hours", "steam_conditions", "boiler_fuel"],
            "note": "Trap monitoring: steam lb/h lost by failures caught earlier x the hours sooner they are caught."},
}

# Questions with no measurable energy quantity of their own, and why.
NO_ENERGY = {
    "E24": "Cooling tower blowdown control saves water and treatment chemicals, not energy; this tool costs energy only.",
    "C1": "Metering enables measurement; it has no energy quantity of its own. Measure first, then estimate the change.",
    "C2": "A missing controller is a controls question; if closing the loop changes energy use, estimate that change "
          "with the form that fits (usually electricity or fuel).",
    "C3": "Valve position feedback is a controls question with no energy quantity of its own.",
    "C4": "A bypassed or oversized control valve is a controls question; if it throttles a pump, estimate it as E1/E2.",
    "C6": "Cascade control is a control-quality question with no energy quantity of its own.",
    "C8": "Alarm load is a safety question.",
    "C9": "Trips and interlocks are a safety question.",
    "E25": "Tank vapor recovery is product and emissions (vapor mass and composition), not combustion energy; its CO2e "
           "needs the vapor's composition, which this tool does not take.",
    "E26": "Metering relief and vent flows enables measurement; flared gas CO2e needs composition, not covered here.",
}

FORM_CONSTANTS = {
    "electricity": ["electricity_price_per_kwh", "grid_kg_co2e_per_kwh", "demand_charge_per_kw_month"],
    "fuel": ["fuel_price", "fuel_kg_co2e_per_mmbtu"],
    "steam": ["steam_energy_btu_per_lb", "boiler_efficiency", "fuel_price", "fuel_kg_co2e_per_mmbtu"],
    "heat": ["boiler_efficiency", "fuel_price", "fuel_kg_co2e_per_mmbtu"],
}


def load_catalog(path=CATALOG):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_constants(path=CONSTANTS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def needs_ids(arg, catalog):
    qs = catalog["questions"]
    if arg.lower() == "all":
        return [q["id"] for q in qs]
    if arg.lower() in {f.lower() for f in catalog["families"]}:
        return [q["id"] for q in qs if q["family"].lower() == arg.lower()]
    ids = [q["id"] for q in qs]
    hit = next((i for i in ids if i.lower() == arg.lower()), None)
    if not hit:
        raise SpecError(f"unknown question or family {arg!r}; try one of {', '.join(ids)}, a family "
                        f"({', '.join(catalog['families'])}) or all")
    return [hit]


def needs_doc(ids, catalog):
    qmap = {q["id"]: q for q in catalog["questions"]}
    out = []
    for qid in ids:
        q = qmap[qid]
        entry = {"question_id": qid, "question": q["question"], "family": q["family"]}
        if qid in NEEDS:
            n = NEEDS[qid]
            consts = []
            for form in n["forms"]:
                for c in FORM_CONSTANTS[form]:
                    if c not in consts:
                        consts.append(c)
            entry.update({
                "estimate_forms": n["forms"], "note": n["note"],
                "measure": [{"key": m, "what": MEASURE_INFO[m]} for m in n["measure"]],
                "constants": [{"key": c, "name": CONST_INFO[c]["name"], "unit": CONST_INFO[c]["unit"],
                               "where": CONST_INFO[c]["where"], "urls": CONST_INFO[c]["urls"],
                               "public_typical_value": CONST_INFO[c]["public"]} for c in consts]})
        else:
            entry["no_energy_quantity"] = NO_ENERGY[qid]
        out.append(entry)
    return {"about": "What to measure and which site constants an annual energy, cost and CO2e estimate needs, "
                     "per question, and where each constant comes from. Public typical values are used only with "
                     "--use-defaults and always labelled. See docs/IMPACT_ESTIMATE.md.",
            "questions": out}


def needs_md(doc):
    L = ["# What an impact estimate needs", "",
         "For each question: what you must measure (never defaulted), and each site constant with where it comes "
         "from. A public typical value exists for some constants; the tool uses it only with `--use-defaults` and "
         "labels it in every output.", ""]
    for e in doc["questions"]:
        L += [f"## {e['question_id']}: {e['question']}", ""]
        if "no_energy_quantity" in e:
            L += [f"No energy quantity to estimate. {e['no_energy_quantity']}", ""]
            continue
        L += [e["note"], "", f"Estimate form: {', '.join(e['estimate_forms'])} (see docs/IMPACT_ESTIMATE.md).", "",
              "**Measure (yours only, never defaulted):**", ""]
        L += [f"- {m['what']}" for m in e["measure"]]
        L += ["", "**Site constants and where they come from:**", ""]
        for c in e["constants"]:
            pub = (f" Public typical value (with `--use-defaults` only): {c['public_typical_value']}."
                   if c["public_typical_value"] else " No public default: you must supply it.")
            urls = "".join(f" <{u}>" for u in c["urls"])
            L.append(f"- **{c['name']}** ({c['unit']}): {c['where']}{pub}{urls}")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


# ---------------------------------------------------------------------------------------------------------------
# Estimate


def steam_table_value(consts, pressure, feed_t):
    t = consts["constants"]["steam_energy_btu_per_lb"]
    key = None
    for k in t["table"]:
        if abs(float(k) - pressure) < 1e-9:
            key = k
    temps = t["feedwater_temps_F"]
    if key is None or not (temps[0] <= feed_t <= temps[-1]):
        return None
    row = t["table"][key]
    for i in range(len(temps) - 1):
        if temps[i] <= feed_t <= temps[i + 1]:
            f = (feed_t - temps[i]) / (temps[i + 1] - temps[i])
            return row[i] + f * (row[i + 1] - row[i]), f not in (0.0, 1.0)
    return None


def default_entry(consts, key, value, unit, extra=""):
    c = consts["constants"][key]
    return {"value": value, "unit": unit, "origin": "public_default",
            "label": f"{DEFAULT_LABEL}: {show(value, unit, 7)} ({c['cite']}, {c['year']})",
            "source": c["source"], "url": c["url"], "year": c["year"], "license": c["license"],
            "note": (c.get("note") or c.get("accounting") or "") + extra}


def user_entry(v, name, unit, note=""):
    return {"value": bounded(parse_value(v, name), name, name.split(".")[-1]), "unit": unit, "origin": "user",
            "label": f"site value: {note}" if note else "site value (yours)"}


# Every field a spec may carry. A name outside these lists is refused (a typo such as "kw_befor" would otherwise be
# ignored and the estimate made without it), and every number is bounds-checked whether or not this run uses it.
SPEC_KEYS = {"title", "description", "illustrative", "fuel", "site", "site_notes", "changes", "change"}
CHANGE_NUMBERS = ("kw_before", "kw_after", "kw_reduction", "kwh_per_year", "hours_per_year", "demand_kw_reduction",
                  "demand_months", "steam_lb_per_h", "steam_pressure_psig", "feedwater_temp_F", "energy_btu_per_lb",
                  "heat_btu_per_h", "heat_mmbtu_per_year", "mmbtu_per_year")
CHANGE_TEXT = ("type", "label", "increase", "energy_note", "note", "notes", "source")
SITE_NUMBERS = ("electricity_price_per_kwh", "grid_kg_co2e_per_kwh", "demand_charge_per_kw_month",
                "fuel_price_per_mmbtu", "fuel_price_per_unit", "fuel_heat_content_mmbtu_per_unit",
                "fuel_kg_co2e_per_mmbtu", "boiler_efficiency")
SITE_TEXT = ("fuel_price_unit",)


def agree(a, b):
    return abs(a.lo - b.lo) <= 0.01 * max(abs(b.lo), 1) and abs(a.hi - b.hi) <= 0.01 * max(abs(b.hi), 1)


def check_spec(spec, changes, site):
    """Refuse a spec before anything is computed: unknown field names, out-of-bounds numbers anywhere, and any two
    supplied forms of the same quantity that disagree (kWh vs kW x hours vs kW before/after, annual heat vs rate x
    hours, a direct fuel price beside a per-unit one), so a contradictory input can never become an estimate."""
    extra = sorted(set(spec) - SPEC_KEYS)
    if extra:
        raise SpecError(f"unknown field(s) in the spec: {', '.join(extra)}")
    bad = sorted(set(site) - set(SITE_NUMBERS) - set(SITE_TEXT))
    if bad:
        raise SpecError(f"unknown site field(s): {', '.join(bad)}")
    for k in SITE_NUMBERS:
        if site.get(k) is not None:
            bounded(parse_value(site[k], f"site.{k}"), f"site.{k}", k)
    if site.get("fuel_price_per_mmbtu") is not None and site.get("fuel_price_per_unit") is not None:
        raise SpecError("site gives both fuel_price_per_mmbtu and fuel_price_per_unit: give one")
    for i, ch in enumerate(changes, 1):
        bad = sorted(set(ch) - set(CHANGE_NUMBERS) - set(CHANGE_TEXT))
        if bad:
            raise SpecError(f"change {i}: unknown field(s): {', '.join(bad)}")
        v = {k: bounded(parse_value(ch[k], f"change {i}: {k}"), f"change {i}: {k}", k)
             for k in CHANGE_NUMBERS if ch.get(k) is not None}
        # every complete form of the kW change must agree
        if "kw_before" in v and "kw_after" in v and "kw_reduction" in v and \
                not agree(v["kw_before"] - v["kw_after"], v["kw_reduction"]):
            raise SpecError(f"change {i}: kw_reduction {show(v['kw_reduction'], 'kW')} disagrees with kw_before - "
                            f"kw_after = {show(v['kw_before'] - v['kw_after'], 'kW')}; give one or make them agree")
        if "kwh_per_year" in v and "hours_per_year" in v:
            for what, kw in (("(kw_before - kw_after) x hours", v["kw_before"] - v["kw_after"]
                              if "kw_before" in v and "kw_after" in v else None),
                             ("kw_reduction x hours", v.get("kw_reduction"))):
                if kw is not None and not agree(kw * v["hours_per_year"], v["kwh_per_year"]):
                    raise SpecError(f"change {i}: kwh_per_year {show(v['kwh_per_year'], 'kWh/yr')} disagrees with "
                                    f"{what} = {show(kw * v['hours_per_year'], 'kWh/yr')}; give one or make them agree")
        if "heat_mmbtu_per_year" in v and "heat_btu_per_h" in v and "hours_per_year" in v:
            implied = v["heat_btu_per_h"] * v["hours_per_year"] / 1e6
            if not agree(implied, v["heat_mmbtu_per_year"]):
                raise SpecError(f"change {i}: heat_mmbtu_per_year {show(v['heat_mmbtu_per_year'], 'MMBtu/yr')} "
                                f"disagrees with heat_btu_per_h x hours = {show(implied, 'MMBtu/yr')}; give one or make "
                                "them agree")
        # the sign comes from the measurements; "increase" is only for a reduction figure that should count as load
        if ch.get("increase") and "kw_before" in v and "kw_after" in v and (v["kw_before"] - v["kw_after"]).lo < 0:
            raise SpecError(f"change {i}: kw_after can be at or above kw_before, so the measurements already carry "
                            "the sign; remove \"increase\": true (it is for a reduction figure that should count as "
                            "added load)")


def resolve(spec, consts, use_defaults):
    """Return (changes, constants dict, missing list). Raises SpecError on malformed input."""
    if not isinstance(spec, dict):
        raise SpecError("the spec must be a JSON object")
    changes = spec.get("changes") or ([spec["change"]] if "change" in spec else [])
    if not changes:
        raise SpecError("the spec needs 'changes': a list of at least one change")
    site = spec.get("site") or {}
    notes = spec.get("site_notes") or {}
    if not isinstance(site, dict) or not isinstance(notes, dict):
        raise SpecError("'site' and 'site_notes' must be objects")
    forms = []
    if not isinstance(changes, list):
        raise SpecError("'changes' must be a list of change objects")
    for i, ch in enumerate(changes):
        if not isinstance(ch, dict):
            raise SpecError(f"change {i + 1}: expected an object like {{\"type\": \"electricity\", ...}}, got {ch!r}")
        if "increase" in ch and not isinstance(ch["increase"], bool):
            raise SpecError(f"change {i + 1}: increase must be true or false (no quotes), got {ch['increase']!r}")
        t = ch.get("type")
        if not isinstance(t, str) or t not in FORM_CONSTANTS:
            raise SpecError(f"change {i + 1}: type must be one of {', '.join(FORM_CONSTANTS)}, got {t!r}")
        forms.append(t)
    check_spec(spec, changes, site)
    fuel_side = any(f in ("fuel", "steam", "heat") for f in forms)
    elec = "electricity" in forms
    C, missing = {}, []

    def need(key, unit, default_fn=None, why=""):
        if key in site and site[key] is not None:
            C[key] = user_entry(site[key], f"site.{key}", unit, notes.get(key, ""))
            return
        if use_defaults and default_fn:
            got = default_fn()
            if got:
                C[key] = got
                return
        missing.append({"key": key, "why": why, "info": CONST_INFO.get(INFO_KEY.get(key, key))})

    if elec:
        need("electricity_price_per_kwh", "$/kWh",
             lambda: default_entry(consts, "electricity_price_per_kwh",
                                   R(consts["constants"]["electricity_price_per_kwh"]["value"]), "$/kWh"),
             "an electricity change is priced at it")
        need("grid_kg_co2e_per_kwh", "kg CO2e/kWh",
             lambda: default_entry(consts, "grid_kg_co2e_per_kwh",
                                   R(consts["constants"]["grid_kg_co2e_per_kwh"]["value"]), "kg CO2e/kWh",
                                   " " + consts["constants"]["grid_kg_co2e_per_kwh"]["subregion_spread"]),
             "electricity CO2e uses it")
        if any(ch.get("type") == "electricity" and ch.get("demand_kw_reduction") is not None for ch in changes):
            need("demand_charge_per_kw_month", "$/kW-month", None,
                 "a demand kW reduction was given; demand charges have no public default")
    fuel = spec.get("fuel")
    if fuel_side:
        if not fuel:
            missing.append({"key": "fuel", "why": "fuel, steam and heat changes need the fuel the plant burns "
                                                  "(e.g. \"natural_gas\"); it is never assumed",
                            "info": None})
        fdef = consts["fuels"].get(fuel) if fuel else None

        def fuel_price_default():
            if fuel != "natural_gas":
                return None
            c = consts["constants"]["natural_gas_price_per_mmbtu"]
            return default_entry(consts, "natural_gas_price_per_mmbtu", R(c["value"]), "$/MMBtu")

        if "fuel_price_per_unit" in site and site["fuel_price_per_unit"] is not None:
            unit = site.get("fuel_price_unit")
            price = bounded(parse_value(site["fuel_price_per_unit"], "site.fuel_price_per_unit"),
                            "site.fuel_price_per_unit", "fuel_price_per_unit")
            per = {"mmbtu": R(1.0), "dekatherm": R(consts["unit_conversions"]["mmbtu_per_dekatherm"]["value"]),
                   "therm": R(consts["unit_conversions"]["mmbtu_per_therm"]["value"])}
            if unit in per:
                conv = per[unit]
                C["fuel_price_per_mmbtu"] = {
                    "value": price / conv, "unit": "$/MMBtu", "origin": "user",
                    "label": f"site value: {show(price, '$/' + unit, 7)} / {show(conv, 'MMBtu/' + unit, 7)} "
                             f"(exact unit definition)" + (f"; {notes['fuel_price_per_unit']}"
                                                          if notes.get("fuel_price_per_unit") else "")}
            elif unit:
                hc = site.get("fuel_heat_content_mmbtu_per_unit")
                if hc is not None:
                    hcv = parse_value(hc, "site.fuel_heat_content_mmbtu_per_unit")
                    if hcv.lo <= 0:
                        raise SpecError("site.fuel_heat_content_mmbtu_per_unit must be above zero")
                    hc_label, hc_default = "site value", None
                elif use_defaults and fuel == "natural_gas" and unit == "Mcf":
                    hcv = R(consts["constants"]["natural_gas_heat_content_mmbtu_per_mcf"]["value"])
                    hc_default = default_entry(consts, "natural_gas_heat_content_mmbtu_per_mcf", hcv, "MMBtu/Mcf")
                    hc_label = hc_default["label"]
                else:
                    hcv, hc_default = None, None
                    missing.append({"key": "fuel_heat_content_mmbtu_per_unit",
                                    "why": f"the fuel price is per {unit}; its heat content (MMBtu per {unit}) "
                                           "converts it to $/MMBtu", "info": CONST_INFO["fuel_price"]})
                if hcv is not None:
                    C["fuel_price_per_mmbtu"] = {
                        "value": price / hcv, "unit": "$/MMBtu", "origin": "user",
                        "label": f"site value: {show(price, '$/' + unit, 7)} / {show(hcv, 'MMBtu/' + unit, 7)} "
                                 f"({hc_label})"}
                    if hc_default:  # the price is the user's, its conversion is a public value: keep its source
                        C["fuel_price_per_mmbtu"]["uses_default"] = {
                            k: hc_default[k] for k in ("value", "unit", "source", "url", "year", "license", "note")}
            else:
                raise SpecError("site.fuel_price_per_unit needs site.fuel_price_unit (mmbtu, therm, dekatherm, or "
                                "a unit such as Mcf with site.fuel_heat_content_mmbtu_per_unit)")
        else:
            need("fuel_price_per_mmbtu", "$/MMBtu", fuel_price_default,
                 "fuel use is priced at it" + ("" if fuel == "natural_gas" else
                                               "; only natural gas has a public default"))

        def fuel_factor_default():
            if not fdef:
                return None
            return {"value": R(fdef["kg_co2e_per_mmbtu"]), "unit": "kg CO2e/MMBtu", "origin": "public_default",
                    "label": f"{DEFAULT_LABEL}: {num(fdef['kg_co2e_per_mmbtu'], 7)} kg CO2e/MMBtu "
                             f"({fdef['cite']}, {fdef['name']}, {fdef['year']}; {fdef['computed_as']})",
                    "source": fdef["source"], "url": fdef["url"], "year": fdef["year"], "license": fdef["license"],
                    "note": fdef.get("scope_note", "")}

        need("fuel_kg_co2e_per_mmbtu", "kg CO2e/MMBtu", fuel_factor_default, "fuel CO2e uses it")
        if any(f in ("steam", "heat") for f in forms):
            need("boiler_efficiency", "(fraction)",
                 lambda: default_entry(consts, "boiler_efficiency",
                                       R(consts["constants"]["boiler_efficiency"]["value"]), "(fraction)"),
                 "steam and heat become fuel through it")
    return changes, C, missing


INFO_KEY = {"fuel_price_per_mmbtu": "fuel_price"}


def steam_energy(ch, i, consts, use_defaults, missing):
    if ch.get("energy_btu_per_lb") is not None:
        return {"value": bounded(parse_value(ch["energy_btu_per_lb"], f"change {i}: energy_btu_per_lb"),
                                 f"change {i}: energy_btu_per_lb", "energy_btu_per_lb"), "unit": "Btu/lb",
                "origin": "user", "label": "site value: " + (ch.get("energy_note") or "your steam-table value")}
    p, t = ch.get("steam_pressure_psig"), ch.get("feedwater_temp_F")
    if use_defaults and isinstance(p, (int, float)) and isinstance(t, (int, float)):
        got = steam_table_value(consts, float(p), float(t))
        if got:
            v, interp = got
            c = consts["constants"]["steam_energy_btu_per_lb"]
            how = "linear interpolation in feedwater temperature" if interp else "table value"
            return {"value": R(v), "unit": "Btu/lb", "origin": "public_default",
                    "label": f"{DEFAULT_LABEL}: {num(v, 6)} Btu/lb at {num(p)} psig saturated, {num(t)} F feedwater "
                             f"({how}; US DOE Steam Tip Sheet #15 Table 1, {c['year']})",
                    "source": c["source"], "url": c["url"], "year": c["year"], "license": c["license"],
                    "note": c["note"]}
    why = ("each steam change needs energy_btu_per_lb (your steam-table value)")
    if use_defaults:
        why += ("; the public table covers only saturated steam at 150, 450 or 600 psig with feedwater 50-250 F, and "
                "needs steam_pressure_psig and feedwater_temp_F from your plant")
    missing.append({"key": f"changes[{i}].energy_btu_per_lb", "why": why,
                    "info": CONST_INFO["steam_energy_btu_per_lb"]})
    return None


def compute(spec, consts, use_defaults=False):
    changes, C, missing = resolve(spec, consts, use_defaults)
    steam_E = {}
    for i, ch in enumerate(changes, 1):
        if ch["type"] == "steam":
            steam_E[i] = steam_energy(ch, i, consts, use_defaults, missing)
    if missing:
        raise Refusal(missing)
    steps, rows = [], []
    tot = {"kwh": R(0), "fuel_mmbtu": R(0), "cost": R(0), "co2e_scope2_kg": R(0), "co2e_scope1_kg": R(0)}

    def g(ch, key, i, required=True):
        if ch.get(key) is None:
            if required:
                raise SpecError(f"change {i} ({ch['type']}): missing measured input {key!r}")
            return None
        return bounded(parse_value(ch[key], f"change {i}: {key}"), f"change {i}: {key}", key)

    for i, ch in enumerate(changes, 1):
        t, label = ch["type"], ch.get("label") or f"change {i}"
        sign = -1 if ch.get("increase") else 1
        S = []
        inputs = {}
        if t == "electricity":
            dkw = None
            if ch.get("kwh_per_year") is not None:
                kwh = g(ch, "kwh_per_year", i)
                # Every form supplied must agree with every other: annual kWh, (before - after) x hours, reduction x hours.
                implied = []
                if ch.get("hours_per_year") is not None:
                    h = g(ch, "hours_per_year", i)
                    if ch.get("kw_before") is not None and ch.get("kw_after") is not None:
                        implied.append(("(kw_before - kw_after) x hours", (g(ch, "kw_before", i) - g(ch, "kw_after", i)) * h))
                    if ch.get("kw_reduction") is not None:
                        implied.append(("kw_reduction x hours", g(ch, "kw_reduction", i) * h))
                for what, imp in implied:
                    if abs(imp.lo - kwh.lo) > 0.01 * max(abs(kwh.lo), 1) or \
                            abs(imp.hi - kwh.hi) > 0.01 * max(abs(kwh.hi), 1):
                        raise SpecError(f"change {i}: kwh_per_year {show(kwh, 'kWh/yr')} disagrees with {what} = "
                                        f"{show(imp, 'kWh/yr')}; give one or make them agree")
                inputs["kwh_per_year"] = kwh
                S.append(("Energy", "kWh/yr (measured)", f"{show(kwh, 'kWh/yr')}", kwh, "kWh/yr"))
            else:
                h = g(ch, "hours_per_year", i)
                if ch.get("kw_reduction") is not None:
                    dkw = g(ch, "kw_reduction", i)
                    if ch.get("kw_before") is not None and ch.get("kw_after") is not None:
                        both = g(ch, "kw_before", i) - g(ch, "kw_after", i)
                        if abs(both.lo - dkw.lo) > 0.01 * max(abs(dkw.lo), 1) or \
                                abs(both.hi - dkw.hi) > 0.01 * max(abs(dkw.hi), 1):
                            raise SpecError(f"change {i}: kw_reduction {show(dkw, 'kW')} disagrees with kw_before - "
                                            f"kw_after = {show(both, 'kW')}; give one or make them agree")
                    inputs.update(kw_reduction=dkw, hours_per_year=h)
                    expr = "kW reduction x hours"
                    sub = f"{show(dkw, 'kW')} x {show(h, 'h/yr')}"
                else:
                    kb, ka = g(ch, "kw_before", i), g(ch, "kw_after", i)
                    dkw = kb - ka
                    if ch.get("increase") and dkw.lo < 0:
                        # The measurements already show the load went up; flagging it as an increase as well would
                        # flip the sign twice and report a saving.
                        raise SpecError(f"change {i}: kw_after is above kw_before, so the measurements already show an "
                                        "increase; remove \"increase\": true (it is for a reduction figure that "
                                        "should count as added load)")
                    inputs.update(kw_before=kb, kw_after=ka, hours_per_year=h)
                    expr = "(kW before - kW after) x hours"
                    sub = f"({show(kb, 'kW')} - {show(ka, 'kW')}) x {show(h, 'h/yr')}"
                kwh = dkw * h
                S.append(("Energy", expr, sub, kwh, "kWh/yr"))
            kwh_s = kwh * sign
            price = C["electricity_price_per_kwh"]["value"]
            cost = kwh_s * price
            S.append(("Energy cost", "kWh/yr x electricity price", f"{show(kwh_s, 'kWh/yr')} x {show(price, '$/kWh', 7)}",
                      cost, "$/yr"))
            dem = R(0)
            if ch.get("demand_kw_reduction") is not None:
                dkwd = g(ch, "demand_kw_reduction", i)
                if dkw is not None and dkwd.hi > dkw.hi * 1.01:
                    inputs["demand_exceeds_average_reduction"] = dkw
                months = g(ch, "demand_months", i)
                inputs.update(demand_kw_reduction=dkwd, demand_months=months)
                dc = C["demand_charge_per_kw_month"]["value"]
                dem = dkwd * dc * months * sign
                S.append(("Demand cost", "billing-peak kW reduction x demand charge x months",
                          f"{show(dkwd, 'kW')} x {show(dc, '$/kW-month', 7)} x {show(months, 'months')}", dem, "$/yr"))
            gf = C["grid_kg_co2e_per_kwh"]["value"]
            co2 = kwh_s * gf
            S.append(("CO2e (Scope 2, location-based)", "kWh/yr x grid emission factor",
                      f"{show(kwh_s, 'kWh/yr')} x {show(gf, 'kg CO2e/kWh', 7)}", co2, "kg CO2e/yr"))
            tot["kwh"] = tot["kwh"] + kwh_s
            tot["cost"] = tot["cost"] + cost + dem
            tot["co2e_scope2_kg"] = tot["co2e_scope2_kg"] + co2
            row = {"kwh": kwh_s, "cost": cost + dem, "co2e_kg": co2}
        else:
            if t == "fuel":
                fuel = g(ch, "mmbtu_per_year", i)
                inputs["mmbtu_per_year"] = fuel
                S.append(("Fuel", "MMBtu/yr (measured, HHV)", show(fuel, "MMBtu/yr"), fuel, "MMBtu/yr"))
            else:
                if t == "steam":
                    lbh, h = g(ch, "steam_lb_per_h", i), g(ch, "hours_per_year", i)
                    e = steam_E[i]["value"]
                    inputs.update(steam_lb_per_h=lbh, hours_per_year=h)
                    for k in ("steam_pressure_psig", "feedwater_temp_F"):
                        if ch.get(k) is not None:
                            inputs[k] = parse_value(ch[k], k)
                    useful = lbh * h * e / 1e6
                    S.append(("Heat in the steam", "lb/h x hours x Btu/lb / 1,000,000 Btu/MMBtu",
                              f"{show(lbh, 'lb/h')} x {show(h, 'h/yr')} x {show(e, 'Btu/lb')} / 1,000,000",
                              useful, "MMBtu/yr"))
                else:
                    if ch.get("heat_mmbtu_per_year") is not None:
                        useful = g(ch, "heat_mmbtu_per_year", i)
                        inputs["heat_mmbtu_per_year"] = useful
                        S.append(("Useful heat", "MMBtu/yr (measured)", show(useful, "MMBtu/yr"), useful, "MMBtu/yr"))
                    else:
                        q, h = g(ch, "heat_btu_per_h", i), g(ch, "hours_per_year", i)
                        inputs.update(heat_btu_per_h=q, hours_per_year=h)
                        useful = q * h / 1e6
                        S.append(("Useful heat", "Btu/h x hours / 1,000,000 Btu/MMBtu",
                                  f"{show(q, 'Btu/h')} x {show(h, 'h/yr')} / 1,000,000", useful, "MMBtu/yr"))
                eff = C["boiler_efficiency"]["value"]
                fuel = useful / eff
                S.append(("Fuel", "useful heat / boiler efficiency", f"{show(useful, 'MMBtu/yr')} / {show(eff)}",
                          fuel, "MMBtu/yr"))
            fuel_s = fuel * sign
            price = C["fuel_price_per_mmbtu"]["value"]
            fpf = C["fuel_kg_co2e_per_mmbtu"]["value"]
            cost = fuel_s * price
            co2 = fuel_s * fpf
            S.append(("Fuel cost", "MMBtu/yr x fuel price", f"{show(fuel_s, 'MMBtu/yr')} x {show(price, '$/MMBtu', 7)}",
                      cost, "$/yr"))
            S.append(("CO2e (Scope 1, combustion)", "MMBtu/yr x fuel emission factor",
                      f"{show(fuel_s, 'MMBtu/yr')} x {show(fpf, 'kg CO2e/MMBtu', 7)}", co2, "kg CO2e/yr"))
            tot["fuel_mmbtu"] = tot["fuel_mmbtu"] + fuel_s
            tot["cost"] = tot["cost"] + cost
            tot["co2e_scope1_kg"] = tot["co2e_scope1_kg"] + co2
            row = {"fuel_mmbtu": fuel_s, "cost": cost, "co2e_kg": co2}
        steps.append({"change": label, "type": t, "increase": bool(ch.get("increase")), "inputs": inputs,
                      "steam_energy": steam_E.get(i), "lines": S, "result": row})
    tot["co2e_t"] = (tot["co2e_scope1_kg"] + tot["co2e_scope2_kg"]) * 0.001
    return {"changes": steps, "constants": C, "totals": tot}


DRAFT_BANNER = ("**FIRST-DRAFT ESTIMATE.** A screening figure for deciding whether better data is worth collecting. It "
                "is not a measured or verified saving, and not a basis for approving spend. Every assumption it rests "
                "on is listed below, each with the data that would replace it.")

# What to collect, per kind of input a change type uses (keys of MEASURE_INFO).
FORM_MEASURES = {"electricity": ["kw", "hours"], "steam": ["steam_lb_h", "steam_conditions", "hours"],
                 "heat": ["heat_btu_h", "hours"], "fuel": ["fuel_mmbtu"]}
CONST_INFO_KEY = {"fuel_price_per_mmbtu": "fuel_price", "fuel_kg_co2e_per_mmbtu": "fuel_kg_co2e_per_mmbtu"}


def draft_notes(res):
    """The estimate's grade, the assumptions it rests on and the data that would firm each one up, built from what
    this run actually used (public values, input forms, ranges), so the page can't claim more than it has."""
    consts = res["constants"]
    public = [(k, e) for k, e in consts.items() if e.get("origin") == "public_default"]
    public += [(f"{s['change']}: energy per lb", s["steam_energy"]) for s in res["changes"]
               if s["steam_energy"] and s["steam_energy"].get("origin") == "public_default"]
    public += [(f"{k}: heat content", e["uses_default"]) for k, e in consts.items() if e.get("uses_default")]
    n_const = len(consts) + sum(1 for s in res["changes"] if s["steam_energy"]) + \
        sum(1 for e in consts.values() if e.get("uses_default"))
    if public:
        grade = (f"Screening grade: {len(public)} of {n_const} constants are public typical values, not your site's; "
                 "the measured inputs are as entered and have not been checked.")
    else:
        grade = ("First draft on site constants: every constant is a site value, but the measured inputs are as entered "
                 "and have not been checked against a representative period.")
    A, F = [], []
    for k, e in public:
        info = CONST_INFO.get(CONST_INFO_KEY.get(k, k)) or {}
        if k.endswith(": heat content"):  # the public factor that turned a per-Mcf price into $/MMBtu
            A.append(f"Your gas has the public average heat content used to convert its price "
                     f"({show(e['value'], e['unit'], 7)}). Gas heat content varies by supplier and month.")
            F.append("Replace the public gas heat content. Your gas bill prints its heat content (a Btu or therm "
                     "factor per Mcf or ccf); use the one on the bills for the period you are pricing.")
            continue
        if k.endswith(": energy per lb"):  # a steam-table lookup, not a site constant
            A.append(f"{k[:-len(': energy per lb')]}: each pound of steam carries the public steam-table value used "
                     f"({show(e['value'], e['unit'], 7)}), read at the pressure and feedwater temperature entered.")
            F.append(f"Confirm the steam energy for {k[:-len(': energy per lb')]}. {MEASURE_INFO['steam_conditions']}")
            continue
        name = re.sub(r"\s*\([^)]*\)", "", info.get("name") or k.replace("_", " "))
        name = name[0].lower() + name[1:]
        A.append(f"Your {name} equals the public typical value used ({show(e['value'], e['unit'], 7)}). National or "
                 "generic figures can differ a great deal from a single site's.")
        F.append(f"Replace the public {name}. {info.get('where') or 'Use your own site value.'}")
    forms = {s["type"] for s in res["changes"]}
    for s in res["changes"]:
        inp, name = s["inputs"], s["change"]
        if s["type"] == "electricity":
            if "kwh_per_year" in inp:
                A.append(f"{name}: the annual kWh entered is a metered difference at the same production rate.")
            else:
                A.append(f"{name}: the kW figures are the average load over the whole year's running, at the same "
                         "production rate before and after, not a single spot reading.")
                A.append(f"{name}: the change applies for {show(inp['hours_per_year'], 'h/yr')}.")
            A.append(f"{name}: one energy price applies to every kWh saved (no time-of-use periods, tiers or riders).")
            if "demand_exceeds_average_reduction" in inp:
                A.append(f"{name}: the billing-peak reduction ({show(inp['demand_kw_reduction'], 'kW')}) is larger than "
                         f"the average load reduction ({show(inp['demand_exceeds_average_reduction'], 'kW')}). That "
                         "holds only if the change cuts the peak more than the average; check it against interval "
                         "meter data at the billing interval.")
            if "demand_kw_reduction" in inp:
                A.append(f"{name}: the demand reduction lowers the billing peak in each of "
                         f"{show(inp['demand_months'], 'months')}, which happens only if the load is reduced at the "
                         "time of the peak.")
            A.append(f"{name}: Scope 2 uses a grid average (location-based) factor; the generation that actually "
                     "backs off at the margin can emit more or less.")
        elif s["type"] in ("steam", "heat"):
            A.append(f"{name}: the {'steam' if s['type'] == 'steam' else 'heat'} rate entered holds for all "
                     f"{show(inp['hours_per_year'], 'h/yr') if 'hours_per_year' in inp else 'the stated year'}.")
            if s["type"] == "steam":
                A.append(f"{name}: each pound of steam carries the stated energy from feedwater to steam, and the steam "
                         "conditions do not change through the year.")
            A.append(f"{name}: boiler efficiency is constant at this load, and the fuel saved is priced at the margin.")
            A.append(f"{name}: Scope 1 covers combustion only (no upstream fuel supply); water, treatment chemicals and "
                     "pumping are not costed.")
        else:
            A.append(f"{name}: the MMBtu/yr entered is a metered difference (HHV) at the same production rate.")
            A.append(f"{name}: Scope 1 covers combustion only (no upstream fuel supply).")
    if any(isinstance(v, R) and not v.point for s in res["changes"] for v in s["inputs"].values()) or \
            any(isinstance(e.get("value"), R) and not e["value"].point for e in consts.values()):
        A.append("Where a range is entered, the result carries both ends. That is the spread of what was entered, not "
                 "a probability interval.")
    seen = set()
    if any(k.endswith(": energy per lb") for k, _ in public):
        seen.add("steam_conditions")
    for f in [x for x in ("electricity", "steam", "heat", "fuel") if x in forms]:
        for m in FORM_MEASURES[f]:
            if m not in seen:
                seen.add(m)
                F.append(f"Confirm by measurement: {MEASURE_INFO[m]}")
    if any("demand_kw_reduction" in s["inputs"] for s in res["changes"]):
        F.append(f"Confirm by measurement: {MEASURE_INFO['demand_kw']}")
    F.append("After the change, measure the same quantities again at the same production rate: that before/after "
             "pair, not this estimate, is the saving.")
    return grade, A, F


def doc_json(spec, res, spec_name, use_defaults):
    def rj(x):  # a range anywhere, including inside a nested record such as a constant's uses_default
        if isinstance(x, R):
            return x.as_json()
        if isinstance(x, dict):
            return {k: rj(v) for k, v in x.items()}
        if isinstance(x, list):
            return [rj(v) for v in x]
        return x

    def ent(e):
        return {k: rj(v) for k, v in e.items()} if e else e

    return {
        "tool": "scripts/estimate_impact.py", "spec": spec_name, "title": spec.get("title", ""),
        "status": "first_draft_estimate", "grade": draft_notes(res)[0], "assumptions": draft_notes(res)[1],
        "to_firm_up": draft_notes(res)[2],
        "illustrative": bool(spec.get("illustrative")), "use_defaults": use_defaults,
        "constants": {k: ent(v) for k, v in res["constants"].items()},
        "changes": [{"change": s["change"], "type": s["type"], "increase": s["increase"],
                     "inputs": {k: rj(v) for k, v in s["inputs"].items()}, "steam_energy": ent(s["steam_energy"]),
                     "steps": [{"quantity": a, "formula": b, "substituted": c, "result": rj(d), "unit": u}
                               for a, b, c, d, u in s["lines"]],
                     "result": {k: rj(v) for k, v in s["result"].items()}} for s in res["changes"]],
        "totals": {"electricity_kwh_per_year": rj(res["totals"]["kwh"]),
                   "fuel_mmbtu_per_year": rj(res["totals"]["fuel_mmbtu"]),
                   "cost_per_year": rj(res["totals"]["cost"]),
                   "co2e_scope2_location_based_kg_per_year": rj(res["totals"]["co2e_scope2_kg"]),
                   "co2e_scope1_kg_per_year": rj(res["totals"]["co2e_scope1_kg"]),
                   "co2e_t_per_year": rj(res["totals"]["co2e_t"])},
        "limits": limits_for(res),
    }


def limits_for(res):
    """The limits that apply to this run: the electricity ones only with an electricity change, the fuel one only with
    a fuel, steam or heat change."""
    forms = {s["type"] for s in res["changes"]}
    elec, fuel = "electricity" in forms, bool(forms - {"electricity"})
    return [x for i, x in enumerate(LIMITS) if (i not in (1, 2) or elec) and (i != 3 or fuel)]


LIMITS = [
    "An estimate from the inputs shown, not a measured or verified saving. It is only as good as the measured kW, "
    "flow and hours; a before/after measurement at the same production rate is the proof.",
    "Electricity cost uses one energy price per kWh. Tariffs vary (time-of-use, tiers, riders, power factor); "
    "demand charges count only when the reduction lowers the billing peak.",
    "Electricity CO2e is location-based Scope 2 (grid average factor given). Market-based Scope 2 uses your "
    "supplier's factor or contract instruments and can differ greatly; avoided emissions on the margin also differ.",
    "Fuel CO2e is Scope 1 combustion only (no upstream). Steam and heat become fuel through the boiler efficiency "
    "given; water, treatment chemicals, maintenance and pumping are not costed.",
    "No savings come from a drawing alone: every quantity here was measured or supplied by the user.",
]


def doc_md(spec, res, spec_name, use_defaults):
    grade, assumptions, firm_up = draft_notes(res)
    L = [f"# Impact estimate (first draft): {spec.get('title') or spec_name}", "", f"> {DRAFT_BANNER}", "",
         f"**{grade}**", ""]
    if spec.get("illustrative"):
        L += ["> **ILLUSTRATIVE INPUTS.** The measured values in this example are made up to show the method. They "
              "are not from any real plant.", ""]
    if spec.get("description"):
        L += [spec["description"], ""]
    L += [f"Spec: `{spec_name}`. Defaults allowed: {'yes (--use-defaults)' if use_defaults else 'no'}.", ""]
    T = res["totals"]
    L += ["## Result (per year, first-draft estimate)", "", "| Quantity | Estimate |", "|---|---|"]
    if any(s["type"] == "electricity" for s in res["changes"]):
        L.append(f"| Electricity | {show(T['kwh'], 'kWh', 3)} |")
    if any(s["type"] != "electricity" for s in res["changes"]):
        L.append(f"| Fuel (HHV) | {show(T['fuel_mmbtu'], 'MMBtu', 3)} |")
    L.append(f"| Cost | {money(T['cost'])} |")
    if any(s["type"] == "electricity" for s in res["changes"]):
        L.append(f"| CO2e, Scope 2 location-based | {show(T['co2e_scope2_kg'] * 0.001, 't', 3)} |")
    if any(s["type"] != "electricity" for s in res["changes"]):
        L.append(f"| CO2e, Scope 1 combustion | {show(T['co2e_scope1_kg'] * 0.001, 't', 3)} |")
    L.append(f"| CO2e, total | {show(T['co2e_t'], 't', 3)} |")
    L += ["", "Rounded to 3 significant figures; the working below carries more. A positive number is a saving; a "
              "negative one is an increase. t = metric tonnes.", ""]
    L += ["## Constants used", "", "| Constant | Value | Origin |", "|---|---|---|"]
    for k, e in res["constants"].items():
        L.append(f"| {k} | {show(e['value'], e['unit'], 7)} | {e['label']} |")
    for s in res["changes"]:
        if s["steam_energy"]:
            e = s["steam_energy"]
            L.append(f"| {s['change']}: energy per lb | {show(e['value'], e['unit'], 7)} | {e['label']} |")
    defaults = [e for e in list(res["constants"].values()) + [s["steam_energy"] for s in res["changes"]]
                if e and e.get("origin") == "public_default"]
    defaults += [e["uses_default"] for e in res["constants"].values() if e.get("uses_default")]
    if defaults:
        L += ["", "Public typical values are national or generic figures, not your plant's. Sources:", ""]
        seen = set()
        for e in defaults:
            if e["source"] in seen:
                continue
            seen.add(e["source"])
            L.append(f"- {e['source']} <{e['url']}> ({e['license']}).{' ' + e['note'] if e.get('note') else ''}")
    L += ["", "## Assumptions", "", "This estimate holds only if all of these are true:", ""]
    L += [f"{n}. {x}" for n, x in enumerate(assumptions, 1)]
    L += ["", "## To firm this up: data to collect", ""]
    if any(x.startswith(("Replace the public", "Confirm the steam energy")) for x in firm_up):
        L += ["In this order: the public values first (they can be furthest from your site), then the measurements.",
              ""]
    L += [f"{n}. {x}" for n, x in enumerate(firm_up, 1)]
    L += ["", "## Working", ""]
    for s in res["changes"]:
        L += [f"### {s['change']} ({s['type']}{', an increase' if s['increase'] else ''})", ""]
        for a, b, c, d, u in s["lines"]:
            L.append(f"- {a} = {b} = {c} = **{show(d, u)}**")
        L.append("")
    L += ["## Limits", ""] + [f"- {x}" for x in limits_for(res)]
    return "\n".join(L).rstrip() + "\n"


def refusal_text(missing, use_defaults):
    L = ["REFUSED: the estimate needs site constants that were not supplied." +
         ("" if use_defaults else " Supply them in the spec's \"site\" block, or rerun with --use-defaults to use "
                                  "labelled public typical values where one exists."), ""]
    for m in missing:
        L.append(f"- {m['key']}: {m['why']}")
        info = m.get("info")
        if info:
            L.append(f"    where: {info['where']}")
            for u in info["urls"]:
                L.append(f"    {u}")
            if not info["public"]:
                L.append("    no public default exists for this one")
    return "\n".join(L) + "\n"


def spec_display_name(path):
    p = Path(path).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.name


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--needs", help="question id (E1), family (energy) or all")
    ap.add_argument("--estimate", help="spec JSON of the measured change and site constants")
    ap.add_argument("--use-defaults", action="store_true",
                    help="fill missing site constants from data/impact_constants.json, labelled as public typical")
    ap.add_argument("--out", help="folder to write impact.md + impact.json (or needs.md + needs.json)")
    ap.add_argument("--constants", default=str(CONSTANTS))
    ap.add_argument("--catalog", default=str(CATALOG))
    a = ap.parse_args(argv)
    if bool(a.needs) == bool(a.estimate):
        ap.error("give exactly one of --needs or --estimate")
    try:
        if a.needs:
            cat = load_catalog(a.catalog)
            doc = needs_doc(needs_ids(a.needs, cat), cat)
            md, js, stem = needs_md(doc), doc, "needs"
        else:
            try:
                spec = json.loads(Path(a.estimate).read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise SpecError(f"{spec_display_name(a.estimate)} is not valid JSON ({e})")
            consts = load_constants(a.constants)
            res = compute(spec, consts, a.use_defaults)
            name = spec_display_name(a.estimate)
            md, js, stem = doc_md(spec, res, name, a.use_defaults), doc_json(spec, res, name, a.use_defaults), "impact"
    except Refusal as r:
        sys.stderr.write(refusal_text(r.missing, a.use_defaults))
        return 2
    except OverflowError:
        sys.stderr.write("ERROR: a value is too large to compute with (check the units and magnitudes in the spec)\n")
        return 2
    except (SpecError, ValueError, json.JSONDecodeError, OSError) as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{stem}.md").write_text(md, encoding="utf-8", newline="\n")
        (out / f"{stem}.json").write_text(json.dumps(js, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                                          newline="\n")
        print(f"wrote {(out / (stem + '.md')).as_posix()} and {stem}.json")
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
