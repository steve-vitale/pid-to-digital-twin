# Impact estimate (first draft): Pump moved from throttling to a variable speed drive, measured inputs only

> **FIRST-DRAFT ESTIMATE.** A screening figure for deciding whether better data is worth collecting. It is not a measured or verified saving, and not a basis for approving spend. Every assumption it rests on is listed below, each with the data that would replace it.

**Screening grade: 2 of 2 constants are public typical values, not your site's; the measured inputs are as entered and have not been checked.**

> **ILLUSTRATIVE INPUTS.** The measured values in this example are made up to show the method. They are not from any real plant.

ILLUSTRATIVE: the same made-up pump measurements with no site constants, to show --use-defaults. No demand kW reduction is given, because demand charges have no public default.

Spec: `examples/impact-estimate/pump_vfd_measured.json`. Defaults allowed: yes (--use-defaults).

## Result (per year, first-draft estimate)

| Quantity | Estimate |
|---|---|
| Electricity | 200,000 to 240,000 kWh |
| Cost | $17,000 to $20,400 |
| CO2e, Scope 2 location-based | 69.9 to 83.9 t |
| CO2e, total | 69.9 to 83.9 t |

Rounded to 3 significant figures; the working below carries more. A positive number is a saving; a negative one is an increase. t = metric tonnes.

## Constants used

| Constant | Value | Origin |
|---|---|---|
| electricity_price_per_kwh | 0.0851 $/kWh | PUBLIC TYPICAL VALUE, replace with your own: 0.0851 $/kWh (US EIA Electric Power Annual Table 2.4, industrial, 2025) |
| grid_kg_co2e_per_kwh | 0.3496671 kg CO2e/kWh | PUBLIC TYPICAL VALUE, replace with your own: 0.3496671 kg CO2e/kWh (US EPA eGRID2023 Summary Tables rev. 2, Table 1, U.S. total output CO2e rate, 2023) |

Public typical values are national or generic figures, not your plant's. Sources:

- US EIA, Electric Power Annual, Table 2.4 Average Price of Electricity to Ultimate Customers by End-Use Sectors, 2015 through 2025, row 2025, 'Total Electric Industry', column Industrial: 8.51 cents per kilowatthour. Data for 2025, released October 21, 2026. <https://www.eia.gov/electricity/annual/html/epa_02_04.html> (Public domain (EIA: 'U.S. government publications are in the public domain', https://www.eia.gov/about/copyrights_reuse.php)). An average revenue per kWh (energy, demand and fixed charges together) across all US industrial customers. Your marginal energy rate can differ a great deal by state, utility, tariff and time of day.
- US EPA, eGRID2023 Summary Tables (Revision 2), Table 1 Subregion Output Emission Rates, row 'U.S.', total output emission rate CO2e (sheet 'Table 1', cell G32). <https://www.epa.gov/system/files/documents/2025-06/summary_tables_rev2.xlsx> (Public domain (US federal government work)). Location-based Scope 2 (average emission rate of generation on the grid). Not a market-based factor and not a marginal (avoided-emissions) rate. Excludes transmission and distribution losses (eGRID lists a separate grid gross loss, 4.2% for the U.S.). Subregion total output CO2e rates in the same table run from 242.776 lb/MWh (NYUP, NPCC Upstate NY) to 1,248.582 lb/MWh (SRMW, SERC Midwest) in the contiguous US, about 5 times, and to 1,548.530 lb/MWh (PRMS, Puerto Rico Miscellaneous). Use your subregion, found by ZIP code in EPA's Power Profiler: https://www.epa.gov/egrid/power-profiler

## Assumptions

This estimate holds only if all of these are true:

1. Your electricity energy price equals the public typical value used (0.0851 $/kWh). National or generic figures can differ a great deal from a single site's.
2. Your grid emission factor equals the public typical value used (0.3496671 kg CO2e/kWh). National or generic figures can differ a great deal from a single site's.
3. Pump P-101 on a variable speed drive: the kW figures are the average load over the whole year's running, at the same production rate before and after, not a single spot reading.
4. Pump P-101 on a variable speed drive: the change applies for 8,000 h/yr.
5. Pump P-101 on a variable speed drive: one energy price applies to every kWh saved (no time-of-use periods, tiers or riders).
6. Pump P-101 on a variable speed drive: Scope 2 uses a grid average (location-based) factor; the generation that actually backs off at the margin can emit more or less.
7. Where a range is entered, the result carries both ends. That is the spread of what was entered, not a probability interval.

## To firm this up: data to collect

In this order: the public values first (they can be furthest from your site), then the measurements.

1. Replace the public electricity energy price. Your electricity bill and rate schedule: the energy charge per kWh in the hours the change applies (weight time-of-use periods by the hours saved in each). Not total bill / total kWh, which mixes in demand and fixed charges.
2. Replace the public grid emission factor. Location-based Scope 2: the EPA eGRID total output emission rate (CO2e) for your eGRID subregion; find the subregion by ZIP code in EPA's Power Profiler, then read the rate from the eGRID summary tables. Market-based Scope 2 instead uses your utility's published supplier-specific emission factor or your contract instruments (RECs, PPAs). Subregion rates differ about 5 times.
3. Confirm by measurement: Average electrical input kW before and after (or the kW reduction): a clamp-on three-phase power meter, the drive or MCC power reading, or the historian's motor kW tag, over a representative period at the same production rate. An estimate from curves (pump/fan curve and affinity laws) must say so.
4. Confirm by measurement: Operating hours per year the change applies: historian run status, the operating schedule, or maintenance records. Not 8,760 unless it really runs all year.
5. After the change, measure the same quantities again at the same production rate: that before/after pair, not this estimate, is the saving.

## Working

### Pump P-101 on a variable speed drive (electricity)

- Energy = (kW before - kW after) x hours = (75 kW - 45 to 50 kW) x 8,000 h/yr = **200,000 to 240,000 kWh/yr**
- Energy cost = kWh/yr x electricity price = 200,000 to 240,000 kWh/yr x 0.0851 $/kWh = **17,020 to 20,424 $/yr**
- CO2e (Scope 2, location-based) = kWh/yr x grid emission factor = 200,000 to 240,000 kWh/yr x 0.3496671 kg CO2e/kWh = **69,933.4 to 83,920.1 kg CO2e/yr**

## Limits

- An estimate from the inputs shown, not a measured or verified saving. It is only as good as the measured kW, flow and hours; a before/after measurement at the same production rate is the proof.
- Electricity cost uses one energy price per kWh. Tariffs vary (time-of-use, tiers, riders, power factor); demand charges count only when the reduction lowers the billing peak.
- Electricity CO2e is location-based Scope 2 (grid average factor given). Market-based Scope 2 uses your supplier's factor or contract instruments and can differ greatly; avoided emissions on the margin also differ.
- No savings come from a drawing alone: every quantity here was measured or supplied by the user.
