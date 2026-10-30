# Impact estimate: from a measured change to annual energy, cost and CO2e

**Why it matters:** the opportunity screen ([`OPPORTUNITY_SCREEN.md`](OPPORTUNITY_SCREEN.md)) lists questions and the
data to collect, and never computes a saving. Once you have measured something (a pump's average kW before and after,
steam lost through failed traps, run hours), `scripts/estimate_impact.py` turns it into an annual energy, cost and
greenhouse-gas figure, with the formula written out, units carried through, and the source of every constant shown.

```sh
python -S scripts/estimate_impact.py --needs E1                 # what to measure and which constants, with URLs
python -S scripts/estimate_impact.py --needs energy             # a whole family (or: all)
python -S scripts/estimate_impact.py --estimate my_spec.json --out out/impact-pump
python -S scripts/estimate_impact.py --estimate my_spec.json --use-defaults --out out/impact-pump
```

Stdlib only, offline. Worked examples, with a hand check of every number:
[`examples/impact-estimate/`](../examples/impact-estimate/README.md).

Before writing either report file, the CLI refuses paths that alias its active inputs or each other, including
directory links and existing hardlinks. Estimate mode protects the spec and constants file; needs mode protects
the question catalog. Use a separate output folder and keep the inputs stable while the command runs.

## What it does, and what it will not do

- It computes from **your** measurements. kW, kWh, hours, lb/h, Btu/h, MMBtu, the fuel the boiler burns, and the
  steam pressure and feedwater temperature are plant facts: they are never defaulted. A missing one is an error.
- A missing **site constant** (price, emission factor, boiler efficiency, energy per lb of steam) is refused, with
  where to get it, unless you pass `--use-defaults`. Then, and only where a published value exists, it is taken from
  [`data/impact_constants.json`](../data/impact_constants.json) and printed in every output as
  `PUBLIC TYPICAL VALUE, replace with your own: <value> (source, year)`.
- Demand charges have no default, ever. Neither do prices of fuels other than natural gas.
- Nothing comes from a drawing alone. The screen tells you what to measure; this tool prices the measurement.
- It is a sourced first draft, to help decide what is worth measuring properly. For detailed pump, fan, steam and
  compressed-air calculations, use the US Department of Energy's MEASUR tool (free and open source), which is built
  for that job.
- The input is a JSON spec ([below](#the-spec)). There is no CSV input yet.

## The spec

```json
{
  "title": "Pump P-101 on a variable speed drive",
  "fuel": "natural_gas",
  "changes": [
    {"type": "electricity", "kw_before": 75.0, "kw_after": {"low": 45.0, "high": 50.0}, "hours_per_year": 8000,
     "demand_kw_reduction": 25.0, "demand_months": 12}
  ],
  "site": {"electricity_price_per_kwh": 0.092, "demand_charge_per_kw_month": 14.5, "grid_kg_co2e_per_kwh": 0.42},
  "site_notes": {"grid_kg_co2e_per_kwh": "your eGRID subregion rate (subregion found in Power Profiler)"}
}
```

Any number may be a range, `{"low": a, "high": b}` or `[a, b]`, except the steam pressure and feedwater temperature used to look up steam energy from the public table, which must be single values (give `energy_btu_per_lb` as a range instead). The spec is checked strictly before anything is computed: an unknown field name, a field that doesn't belong to the change's type, a range with anything but `low` and `high`, a field written twice, two forms of the same quantity that disagree, or a number that would neither feed the result nor be checked against it (for example hours beside an annual kWh with nothing to compare them to) are all refused with the reason, so nothing you wrote is ever silently ignored; results are then ranges, by interval arithmetic
(each bound takes the worst and best combination, so the range is wide, never falsely narrow). `"increase": true` on a
change makes it count against the saving (for example the extra boiler fuel a backpressure turbogenerator takes).
Several changes in one spec are summed. `site_notes` text is printed next to each site value, so say where it came from.
Each change can also carry `source`, `note` and `notes`; these travel into both output files as measurement provenance.
For added electrical load, use actual `kw_before` / `kw_after` without `increase`, or an increment in `kw_reduction`
with `increase: true`. A partial `kw_before` beside that flag is ambiguous and is refused with those two alternatives.

When you supply more than one electricity form, each must reach the annual quantity: kW figures beside measured annual
kWh need `hours_per_year`. Agreement between `kw_before`, `kw_after` and `kw_reduction` alone cannot check annual kWh.
Complete alternate calculations must match both range ends within 1% of the reported form (or 0.01 for an end whose absolute value is below 1),
allowing rounding; overlapping ranges alone do not establish agreement. Every input that passes a cross-check is
retained in the output's `inputs`.

A complete before/after range is compared with the reduction it calculates: for example, `kw_before: [10,20]` and
`kw_after: [0,5]` give `kw_reduction: [5,20]`. With only before and reduction supplied, the reduction's high end must
not exceed the before-load's low end, so no independent combination implies a negative after load. Add the measured
after range when those quantities are related. These are interval calculations; the tool does not model correlations.

| Change type | Measured inputs | Becomes |
|---|---|---|
| `electricity` | `kw_before` + `kw_after`, or `kw_reduction`, with `hours_per_year`; or `kwh_per_year`. Optional `demand_kw_reduction` + `demand_months` | kWh/yr, then cost and Scope 2 CO2e |
| `fuel` | `mmbtu_per_year` (HHV) | cost and Scope 1 CO2e |
| `steam` | `steam_lb_per_h`, `hours_per_year`, and `energy_btu_per_lb` (or, with `--use-defaults`, `steam_pressure_psig` + `feedwater_temp_F` for the DOE table) | useful heat, fuel via boiler efficiency, then cost and Scope 1 CO2e |
| `heat` | `heat_btu_per_h` + `hours_per_year`, or `heat_mmbtu_per_year` | fuel via boiler (or heater) efficiency, then cost and CO2e |

For an explicit `energy_btu_per_lb`, use the enthalpy difference at the boundary you measured. Condensate-return
heat can be below 100 Btu/lb; it is not the gross energy needed to make steam from feedwater. The public steam-table
default covers that gross production duty only. Turbine generation belongs in an `electricity` change, with any
additional boiler fuel as a separate `increase: true` change; enthalpy extracted as shaft work is not fuel saved.

Site constants (`site` block): `electricity_price_per_kwh`, `demand_charge_per_kw_month`, `grid_kg_co2e_per_kwh`,
`fuel_price_per_mmbtu` (or `fuel_price_per_unit` + `fuel_price_unit`: `mmbtu`, `therm`, `dekatherm`, or any unit such
as `Mcf` with `fuel_heat_content_mmbtu_per_unit`), `fuel_kg_co2e_per_mmbtu`, `boiler_efficiency` (a fraction). The
top-level `fuel` names what the boiler or heater burns (`natural_gas`, `distillate_fuel_oil_no2`,
`residual_fuel_oil_no6`, `propane`, or any name if you supply its factor and price).

## The formulas

```text
Electricity   kWh/yr        = (kW before - kW after) x hours/yr          (or kW reduction x hours, or measured kWh/yr)
              energy $/yr   = kWh/yr x electricity price ($/kWh)
              demand $/yr   = billing-peak kW reduction x demand charge ($/kW-month) x months
              CO2e kg/yr    = kWh/yr x grid factor (kg CO2e/kWh)                         -> Scope 2, location-based
Steam         MMBtu/yr      = lb/h x hours/yr x Btu/lb / 1,000,000                 (useful heat in the steam)
Heat          MMBtu/yr      = Btu/h x hours/yr / 1,000,000                         (or measured MMBtu/yr)
Fuel          MMBtu/yr      = useful heat MMBtu/yr / boiler efficiency             (or measured fuel MMBtu/yr, HHV)
              fuel $/yr     = fuel MMBtu/yr x fuel price ($/MMBtu)
              CO2e kg/yr    = fuel MMBtu/yr x fuel factor (kg CO2e/MMBtu)                -> Scope 1, combustion
Fuel factor   kg CO2e/MMBtu = kg CO2 + (g CH4 x 28 + g N2O x 265) / 1000                  (IPCC AR5 GWPs)
```

Each output shows each line with your numbers substituted and the unit of every term.

## Where each constant comes from

| Constant | Your own value: where it lives | Public typical value (`--use-defaults` only) |
|---|---|---|
| Electricity price, $/kWh | The energy charge on your electricity bill and rate schedule, in the hours the change applies (weight time-of-use periods). Not total bill / total kWh. | 0.0851 $/kWh: US average price to industrial customers, 2025 (8.51 cents/kWh), EIA [Electric Power Annual Table 2.4](https://www.eia.gov/electricity/annual/html/epa_02_04.html), released Oct 21, 2026. An average of all charges; your marginal energy rate can differ a lot. |
| Demand charge, $/kW-month | Your bill and rate schedule (charge, billing interval, ratchet). Counts only if the reduction lowers the billing peak: check interval meter data. | None. Never defaulted. |
| Grid factor, kg CO2e/kWh | Location-based: the eGRID total output CO2e rate for your eGRID subregion (find it by ZIP in [Power Profiler](https://www.epa.gov/egrid/power-profiler), rates in [eGRID summary data](https://www.epa.gov/egrid/summary-data)). Market-based: your utility's published supplier-specific factor or your contract instruments. | 0.3496671 kg CO2e/kWh: eGRID2023 U.S. total output rate, 770.884 lb CO2e/MWh ([summary tables rev. 2](https://www.epa.gov/system/files/documents/2025-06/summary_tables_rev2.xlsx), Table 1, row U.S.), AR5 GWPs. Subregions run from 242.776 (NYUP) to 1,248.582 lb/MWh (SRMW) in the contiguous US, about 5 times, so use yours. |
| Fuel price, $/MMBtu | Your gas bill or supply contract: commodity plus transport/delivery, at the margin. The bill's heat content (Btu factor) converts $/Mcf or $/ccf to $/MMBtu. | Natural gas only: $5.048263/MMBtu = EIA 2025 US industrial price $5.23/Mcf ([EIA](https://www.eia.gov/dnav/ng/ng_pri_sum_dcu_nus_a.htm)) / 1.036 MMBtu/Mcf (EIA 2025 [heat content of gas delivered to consumers](https://www.eia.gov/dnav/ng/ng_cons_heat_a_EPG0_VGTH_btucf_a.htm)). EIA's industrial price covers only the 13.4% of industrial gas sold by distribution utilities, so contract prices can differ widely. |
| Fuel factor, kg CO2e/MMBtu | [EPA GHG Emission Factors Hub](https://www.epa.gov/climateleadership/ghg-emission-factors-hub), Table 1, for your fuel; your supplier's measured heat or carbon content if you have it. | Natural gas 53.1145 (53.06 kg CO2 + 1 g CH4 + 0.1 g N2O per MMBtu; per scf 0.05449534 kg CO2e, HHV 0.001026 MMBtu/scf); distillate No. 2 74.203; residual No. 6 75.343; propane 63.113. Hub 2025 edition (Jan 15, 2025), AR5 GWPs, combustion only. |
| Boiler efficiency, fraction | Your boiler's tested fuel-to-steam efficiency (input-output or heat-loss method), or a combustion analyzer reading plus shell and blowdown losses, or the design datasheet. | 0.80: the thermal efficiency EPA assumes for gas-fired steam or heat (Hub 2025, Table 7 note). An inventory assumption, not a boiler. DOE's 85.7% (Steam Tip Sheet #15, Table 2) is combustion efficiency, a different quantity, and is not used. |
| Energy per lb of steam, Btu/lb | Steam tables: enthalpy of the steam at its pressure and temperature minus the enthalpy of the water that replaces it (feedwater, or makeup if the condensate is lost). | Saturated steam at 150, 450 or 600 psig with feedwater 50 to 250 F only, from [DOE Steam Tip Sheet #15](https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/steam15_benchmark.pdf) Table 1 (Jan 2012), linear in feedwater temperature between tabulated points. Anything else: your steam-table value. |

Every public value was read from the official file (the EPA and eGRID spreadsheets were downloaded and their cells
read; the EIA tables and the DOE tip sheet were read from the pages and PDF linked above) on 2026-10-29. Each entry in
`data/impact_constants.json` holds the source, URL, table, year and license (all US federal works, public domain), and
the test recomputes every derived value from its published inputs. What could not be confirmed is listed there under
`not_included`, with the reason: demand charges, steam at other conditions, non-gas fuel prices, marginal grid rates,
and per-orifice trap and leak rates (those are measurements).

## What to measure, per question

`--needs` maps every question in [`data/questions.json`](../data/questions.json) to the measurements and constants
an estimate needs (for example E1 pump on a drive: kW before and after, hours; E8 steam traps: steam lb/h lost, hours,
steam conditions, boiler fuel, then energy per lb, boiler efficiency, fuel price and factor; E20 air leaks: compressor
kW loaded and unloaded, the leak load from a no-production test, hours). Questions with no energy quantity of their
own (metering, controls quality, safety, cooling-tower water, vapor recovery, flare metering) say so and why. The test
fails if a question is added to the catalog without either a `--needs` entry or a stated reason.

## Outputs

**Every estimate is a first draft, and says so before it shows a number.** The page opens with a FIRST-DRAFT ESTIMATE
banner and a grade line:
- *Screening grade:* some constants are public typical values, not your site's.
- *First draft on site constants:* every constant is yours, but the measured inputs haven't been checked over a
  representative period.

After the numbers come two sections built from what this run actually used:
- **Assumptions:** what must be true for the figure to hold. Each public value the run used is one of them, along
  with "the kW are an annual average at the same production" and "one flat energy price".
- **To firm this up:** the data that would replace each assumption, and where to get it. The public values come
  first, because they can be furthest from your site. It ends with the only real proof: measure again after the
  change, at the same production rate.

The point is to send you out to collect better data, not to stop at the estimate.

- `impact.md`: the result table (rounded to 3 significant figures), every constant with its origin (`site value: ...`
  or the `PUBLIC TYPICAL VALUE` label with source and year), the source list for any public value used, the working
  line by line, and the limits.
- `impact.json`: the same as data: inputs, constants (value, unit, origin, label, source, URL, license), each step
  (quantity, formula, substituted numbers, result, unit) and totals (electricity kWh, fuel MMBtu, cost, Scope 2 and
  Scope 1 CO2e in kg, total CO2e in t). A range is `{"low": a, "high": b}`.
- `needs.md` / `needs.json` for `--needs`.

Exit codes: 0 written; 2 refused, nothing written: a missing constant, a malformed spec, or a value outside the supported bounds (hours outside 0 to 8,784, the hours in a leap year; a boiler efficiency of 85 instead of 0.85; a negative quantity or price; steam enthalpy difference outside 0 to 1,600 Btu/lb; inputs that disagree with each other). A billing-peak reduction larger than the average load reduction is not refused, because a change can cut the peak more than the average; it is listed as an assumption to check against interval meter data. The message says which value and why.

## Limits

- **An estimate, not a verified saving.** It is as good as the measured kW, flow and hours. The proof is a before and
  after measurement at the same production rate (IPMVP-style measurement and verification is the formal route).
- **Tariffs vary.** One energy price per kWh is used. Time-of-use periods, tiers, riders, power factor and ratchets
  are yours to resolve into that price; demand charges save money only if the billing peak falls.
- **Scope 2 here is location-based.** The grid factor is an average emission rate for the grid region. Market-based
  Scope 2 (GHG Protocol Scope 2 Guidance) uses your supplier's factor or contract instruments and can be very
  different, even zero. Neither is the marginal (avoided) emission of a saved kWh; EPA's AVERT tool addresses that.
  eGRID rates also exclude transmission and distribution losses.
- **Scope 1 here is combustion only.** No upstream (extraction, pipeline methane). Steam and heat become fuel through
  the boiler efficiency given; makeup water, treatment chemicals, pumping and maintenance are not costed.
- **One fuel per spec.** Mixed-fuel boilers need one spec per fuel, or a blended price and factor you supply.
- **No savings from the drawing alone.** The opportunity screen finds questions; this tool prices measured answers.
