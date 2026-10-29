# Impact estimate (first draft): Pump moved from throttling to a variable speed drive, with site constants

> **FIRST-DRAFT ESTIMATE.** A screening figure for deciding whether better data is worth collecting. It is not a measured or verified saving, and not a basis for approving spend. Every assumption it rests on is listed below, each with the data that would replace it.

**First draft on site constants: every constant is a site value, but the measured inputs are as entered and have not been checked against a representative period.**

> **ILLUSTRATIVE INPUTS.** The measured values in this example are made up to show the method. They are not from any real plant.

ILLUSTRATIVE: a centrifugal pump that was throttled by a discharge control valve now runs on a variable speed drive. kW before is a measured average; kW after is a range because the after-measurement month had two production rates. All numbers, including the site constants, are made up for this example.

Spec: `examples/impact-estimate/pump_vfd_site.json`. Defaults allowed: no.

## Result (per year, first-draft estimate)

| Quantity | Estimate |
|---|---|
| Electricity | 200,000 to 240,000 kWh |
| Cost | $22,800 to $26,400 |
| CO2e, Scope 2 location-based | 84 to 101 t |
| CO2e, total | 84 to 101 t |

Rounded to 3 significant figures; the working below carries more. A positive number is a saving; a negative one is an increase. t = metric tonnes.

## Constants used

| Constant | Value | Origin |
|---|---|---|
| electricity_price_per_kwh | 0.092 $/kWh | site value: ILLUSTRATIVE energy charge from a made-up rate schedule |
| grid_kg_co2e_per_kwh | 0.42 kg CO2e/kWh | site value: ILLUSTRATIVE subregion factor (look yours up in EPA Power Profiler) |
| demand_charge_per_kw_month | 14.5 $/kW-month | site value: ILLUSTRATIVE demand charge from the same made-up rate schedule |

## Assumptions

This estimate holds only if all of these are true:

1. Pump P-101 on a variable speed drive: the kW figures are the average load over the whole year's running, at the same production rate before and after, not a single spot reading.
2. Pump P-101 on a variable speed drive: the change applies for 8,000 h/yr.
3. Pump P-101 on a variable speed drive: one energy price applies to every kWh saved (no time-of-use periods, tiers or riders).
4. Pump P-101 on a variable speed drive: the demand reduction lowers the billing peak in each of 12 months, which happens only if the load is reduced at the time of the peak.
5. Pump P-101 on a variable speed drive: Scope 2 uses a grid average (location-based) factor; the generation that actually backs off at the margin can emit more or less.
6. Where a range is entered, the result carries both ends. That is the spread of what was entered, not a probability interval.

## To firm this up: data to collect

1. Confirm by measurement: Average electrical input kW before and after (or the kW reduction): a clamp-on three-phase power meter, the drive or MCC power reading, or the historian's motor kW tag, over a representative period at the same production rate. An estimate from curves (pump/fan curve and affinity laws) must say so.
2. Confirm by measurement: Operating hours per year the change applies: historian run status, the operating schedule, or maintenance records. Not 8,760 unless it really runs all year.
3. Confirm by measurement: Optional: the reduction in billing-peak kW (interval meter data at the billing interval) and the months it applies.
4. After the change, measure the same quantities again at the same production rate: that before/after pair, not this estimate, is the saving.

## Working

### Pump P-101 on a variable speed drive (electricity)

- Energy = (kW before - kW after) x hours = (75 kW - 45 to 50 kW) x 8,000 h/yr = **200,000 to 240,000 kWh/yr**
- Energy cost = kWh/yr x electricity price = 200,000 to 240,000 kWh/yr x 0.092 $/kWh = **18,400 to 22,080 $/yr**
- Demand cost = billing-peak kW reduction x demand charge x months = 25 kW x 14.5 $/kW-month x 12 months = **4,350 $/yr**
- CO2e (Scope 2, location-based) = kWh/yr x grid emission factor = 200,000 to 240,000 kWh/yr x 0.42 kg CO2e/kWh = **84,000 to 100,800 kg CO2e/yr**

## Limits

- An estimate from the inputs shown, not a measured or verified saving. It is only as good as the measured kW, flow and hours; a before/after measurement at the same production rate is the proof.
- Electricity cost uses one energy price per kWh. Tariffs vary (time-of-use, tiers, riders, power factor); demand charges count only when the reduction lowers the billing peak.
- Electricity CO2e is location-based Scope 2 (grid average factor given). Market-based Scope 2 uses your supplier's factor or contract instruments and can differ greatly; avoided emissions on the margin also differ.
- No savings come from a drawing alone: every quantity here was measured or supplied by the user.
