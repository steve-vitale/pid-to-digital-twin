# Impact estimate (first draft): Failed steam traps repaired, with site constants

> **FIRST-DRAFT ESTIMATE.** A screening figure for deciding whether better data is worth collecting. It is not a measured or verified saving, and not a basis for approving spend. Every assumption it rests on is listed below, each with the data that would replace it.

**First draft on site constants: every constant is a site value, but the measured inputs are as entered and have not been checked against a representative period.**

> **ILLUSTRATIVE INPUTS.** The measured values in this example are made up to show the method. They are not from any real plant.

ILLUSTRATIVE: a trap survey found failed-open traps on a 150 psig saturated steam main losing 150 to 210 lb/h in total (the range reflects the survey's orifice estimates). Steam is on all year. All numbers, including the site constants, are made up for this example.

Spec: `examples/impact-estimate/steam_traps_site.json`. Defaults allowed: no.

## Result (per year, first-draft estimate)

| Quantity | Estimate |
|---|---|
| Fuel (HHV) | 1,600 to 2,360 MMBtu |
| Cost | $8,810 to $13,000 |
| CO2e, Scope 1 combustion | 85.1 to 125 t |
| CO2e, total | 85.1 to 125 t |

Rounded to 3 significant figures; the working below carries more. A positive number is a saving; a negative one is an increase. t = metric tonnes.

## Constants used

| Constant | Value | Origin |
|---|---|---|
| fuel_price_per_mmbtu | 5.5 $/MMBtu | site value: 0.55 $/therm / 0.1 MMBtu/therm (exact unit definition); ILLUSTRATIVE delivered gas price from a made-up gas bill |
| fuel_kg_co2e_per_mmbtu | 53.11 kg CO2e/MMBtu | site value: ILLUSTRATIVE, rounded from the EPA Hub natural gas factor |
| boiler_efficiency | 0.78 to 0.82 (fraction) | site value: ILLUSTRATIVE range from a made-up boiler test |
| Failed steam traps on the 150 psig main: energy per lb | 1,000 Btu/lb | site value: ILLUSTRATIVE steam-table value (steam enthalpy minus feedwater enthalpy) |

## Assumptions

This estimate holds only if all of these are true:

1. Failed steam traps on the 150 psig main: the steam rate entered holds for all 8,760 h/yr.
2. Failed steam traps on the 150 psig main: each pound carries the stated enthalpy difference at the measured boundary, and those conditions do not change through the year.
3. Failed steam traps on the 150 psig main: boiler efficiency is constant at this load, and the fuel saved is priced at the margin.
4. Failed steam traps on the 150 psig main: Scope 1 covers combustion only (no upstream fuel supply); water, treatment chemicals and pumping are not costed.
5. Where a range is entered, the result carries both ends. That is the spread of what was entered, not a probability interval.

## To firm this up: data to collect

1. Confirm by measurement: Steam flow saved or lost, lb/h: a steam flowmeter, or a survey estimate (for failed traps, the survey's orifice-based loss per trap; DOE Steam Tip Sheet #1 prints one such table).
2. Confirm by measurement: Steam pressure (psig) and temperature at the point of loss, and the feedwater or makeup water temperature: gauges, the historian, the deaerator.
3. Confirm by measurement: Operating hours per year the change applies: historian run status, the operating schedule, or maintenance records. Not 8,760 unless it really runs all year.
4. After the change, measure the same quantities again at the same production rate: that before/after pair, not this estimate, is the saving.

## Working

### Failed steam traps on the 150 psig main (steam)

- Heat in the steam = lb/h x hours x Btu/lb / 1,000,000 Btu/MMBtu = 150 to 210 lb/h x 8,760 h/yr x 1,000 Btu/lb / 1,000,000 = **1,314 to 1,839.6 MMBtu/yr**
- Fuel = useful heat / boiler efficiency = 1,314 to 1,839.6 MMBtu/yr / 0.78 to 0.82 = **1,602.44 to 2,358.46 MMBtu/yr**
- Fuel cost = MMBtu/yr x fuel price = 1,602.44 to 2,358.46 MMBtu/yr x 5.5 $/MMBtu = **8,813.41 to 12,971.5 $/yr**
- CO2e (Scope 1, combustion) = MMBtu/yr x fuel emission factor = 1,602.44 to 2,358.46 MMBtu/yr x 53.11 kg CO2e/MMBtu = **85,105.5 to 125,258 kg CO2e/yr**

## Limits

- An estimate from the inputs shown, not a measured or verified saving. It is only as good as the measured kW, flow and hours; a before/after measurement at the same production rate is the proof.
- Fuel CO2e is Scope 1 combustion only (no upstream). Steam and heat become fuel through the boiler efficiency given; water, treatment chemicals, maintenance and pumping are not costed.
- No savings come from a drawing alone: every quantity here was measured or supplied by the user.
