# What an impact estimate needs

For each question: what you must measure (never defaulted), and each site constant with where it comes from. A public typical value exists for some constants; the tool uses it only with `--use-defaults` and labels it in every output.

## E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

Pump on a variable speed drive: measured kW before and after. Before installing, the after kW can only be estimated from the flow-duration curve, the pump curve and the static head; say so.

Estimate form: electricity (see docs/IMPACT_ESTIMATE.md).

**Measure (yours only, never defaulted):**

- Average electrical input kW before and after (or the kW reduction): a clamp-on three-phase power meter, the drive or MCC power reading, or the historian's motor kW tag, over a representative period at the same production rate. An estimate from curves (pump/fan curve and affinity laws) must say so.
- Operating hours per year the change applies: historian run status, the operating schedule, or maintenance records. Not 8,760 unless it really runs all year.
- Optional: the reduction in billing-peak kW (interval meter data at the billing interval) and the months it applies.

**Site constants and where they come from:**

- **Electricity energy price** ($/kWh): Your electricity bill and rate schedule: the energy charge per kWh in the hours the change applies (weight time-of-use periods by the hours saved in each). Not total bill / total kWh, which mixes in demand and fixed charges. Public typical value (with `--use-defaults` only): EIA Electric Power Annual Table 2.4, US average industrial price (2025). <https://www.eia.gov/electricity/annual/html/epa_02_04.html>
- **Grid emission factor** (kg CO2e/kWh): Location-based Scope 2: the EPA eGRID total output emission rate (CO2e) for your eGRID subregion; find the subregion by ZIP code in EPA's Power Profiler, then read the rate from the eGRID summary tables. Market-based Scope 2 instead uses your utility's published supplier-specific emission factor or your contract instruments (RECs, PPAs). Subregion rates differ about 5 times. Public typical value (with `--use-defaults` only): EPA eGRID2023 US total output CO2e rate. <https://www.epa.gov/egrid/power-profiler> <https://www.epa.gov/egrid/summary-data>
- **Demand charge (only to estimate a demand kW reduction)** ($/kW-month): Your electricity bill and rate schedule: the demand charge per kW per month, its billing interval (often 15 minutes) and any ratchet clause. A kW reduction saves demand charges only if it lowers the billing peak; check against interval meter data. Never defaulted. No public default: you must supply it.
