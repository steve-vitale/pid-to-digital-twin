# What an impact estimate needs

For each question: what you must measure (never defaulted), and each site constant with where it comes from. A public typical value exists for some constants; the tool uses it only with `--use-defaults` and labels it in every output.

## E8: Is there a steam trap population large enough to justify a trap survey program?

Failed steam traps: steam lost per failed trap (lb/h, from the survey) x number failed, hours the steam is on, the energy per lb at those conditions, then fuel via boiler efficiency.

Estimate form: steam (see docs/IMPACT_ESTIMATE.md).

**Measure (yours only, never defaulted):**

- Steam flow saved or lost, lb/h: a steam flowmeter, or a survey estimate (for failed traps, the survey's orifice-based loss per trap; DOE Steam Tip Sheet #1 prints one such table).
- Operating hours per year the change applies: historian run status, the operating schedule, or maintenance records. Not 8,760 unless it really runs all year.
- Steam pressure (psig) and temperature at the point of loss, and the feedwater or makeup water temperature: gauges, the historian, the deaerator.
- Which fuel the boiler or heater fires (the tool will not assume natural gas).

**Site constants and where they come from:**

- **Energy per lb of steam** (Btu/lb): Steam tables: enthalpy of the steam at its line pressure and temperature minus the enthalpy of the water that replaces it (feedwater, or makeup water if the condensate is not returned). DOE Steam Tip Sheet #15 Table 1 tabulates saturated steam at 150, 450 and 600 psig. Public typical value (with `--use-defaults` only): DOE Steam Tip Sheet #15 Table 1 (needs your steam pressure and feedwater temperature). <https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/steam15_benchmark.pdf>
- **Boiler (or heater) efficiency** (fraction, fuel HHV in to useful heat out): Your boiler's efficiency test (fuel-to-steam, input-output or heat-loss method), a combustion analyzer reading plus shell and blowdown losses, or the boiler design datasheet. For heat that displaces a different heater, that heater's efficiency. Public typical value (with `--use-defaults` only): EPA GHG Emission Factors Hub (2025) Table 7 assumption, 80% thermal efficiency. <https://www.epa.gov/climateleadership/ghg-emission-factors-hub> <https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/steam15_benchmark.pdf>
- **Fuel price** ($/MMBtu (or $/therm, $/Mcf with heat content)): Your gas bill or fuel supply contract: commodity plus transport/delivery per unit, at the margin (the price of the next unit you would not buy). For gas billed per Mcf or ccf, the bill's heat content (Btu factor) converts it to MMBtu. Public typical value (with `--use-defaults` only): EIA US natural gas industrial price (2025), natural gas only. <https://www.eia.gov/dnav/ng/ng_pri_sum_dcu_nus_a.htm> <https://www.eia.gov/dnav/ng/ng_cons_heat_a_EPG0_VGTH_btucf_a.htm>
- **Fuel emission factor** (kg CO2e/MMBtu (HHV)): EPA GHG Emission Factors Hub, Table 1 Stationary Combustion: CO2, CH4 and N2O per MMBtu for your fuel, combined with the Hub's GWPs (AR5: CH4 28, N2O 265). If your supplier gives a measured carbon content or heat content, use it. Public typical value (with `--use-defaults` only): EPA GHG Emission Factors Hub (2025) Table 1. <https://www.epa.gov/climateleadership/ghg-emission-factors-hub>
