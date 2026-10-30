# Impact estimate (first draft): Failed steam traps repaired, measured inputs only

> **FIRST-DRAFT ESTIMATE.** A screening figure for deciding whether better data is worth collecting. It is not a measured or verified saving, and not a basis for approving spend. Every assumption it rests on is listed below, each with the data that would replace it.

**Screening grade: 4 of 4 constants are public typical values, not your site's; the measured inputs are as entered and have not been checked.**

> **ILLUSTRATIVE INPUTS.** The measured values in this example are made up to show the method. They are not from any real plant.

ILLUSTRATIVE: the same made-up trap survey with no site constants, to show --use-defaults. The steam pressure, feedwater temperature and boiler fuel are the plant's own facts and are still given; only the constants are left out.

Spec: `examples/impact-estimate/steam_traps_measured.json`. Defaults allowed: yes (--use-defaults).

## Result (per year, first-draft estimate)

| Quantity | Estimate |
|---|---|
| Fuel (HHV) | 1,690 to 2,360 MMBtu |
| Cost | $8,520 to $11,900 |
| CO2e, Scope 1 combustion | 89.7 to 126 t |
| CO2e, total | 89.7 to 126 t |

Rounded to 3 significant figures; the working below carries more. A positive number is a saving; a negative one is an increase. t = metric tonnes.

## Constants used

| Constant | Value | Origin |
|---|---|---|
| fuel_price_per_mmbtu | 5.048263 $/MMBtu | PUBLIC TYPICAL VALUE, replace with your own: 5.048263 $/MMBtu (US EIA natural gas industrial price, U.S., / EIA heat content, 2025) |
| fuel_kg_co2e_per_mmbtu | 53.1145 kg CO2e/MMBtu | PUBLIC TYPICAL VALUE, replace with your own: 53.1145 kg CO2e/MMBtu (US EPA GHG Emission Factors Hub, Table 1 Stationary Combustion, Natural gas (pipeline quality), 2025; kg CO2e = kg CO2 + (g CH4 x 28 + g N2O x 265) / 1000, AR5 GWPs) |
| boiler_efficiency | 0.8 (fraction) | PUBLIC TYPICAL VALUE, replace with your own: 0.8 (fraction) (US EPA GHG Emission Factors Hub, Table 7 note, 2025) |
| Failed steam traps on the 150 psig main: energy per lb | 1,028 Btu/lb | PUBLIC TYPICAL VALUE, replace with your own: 1,028 Btu/lb at 150 psig saturated, 200 F feedwater (table value; US DOE Steam Tip Sheet #15 Table 1, 2012) |

Public typical values are national or generic figures, not your plant's. Sources:

- US EIA, Natural Gas Prices (annual), U.S., 'Industrial Price', 2025: 5.23 dollars per thousand cubic feet (page release date 9/30/2026); divided by the EIA 2025 US heat content of gas delivered to consumers (1,036 Btu/cf). <https://www.eia.gov/dnav/ng/ng_pri_sum_dcu_nus_a.htm> (Public domain (EIA: https://www.eia.gov/about/copyrights_reuse.php)). EIA's industrial price covers only gas sold by local distribution companies: the same table gives 13.4% as the share of total industrial deliveries included in the 2025 price. Most industrial gas is bought from marketers under contracts, so your delivered price (commodity plus transport) may differ widely.
- US EPA, GHG Emission Factors Hub (2025), Table 1 Stationary Combustion, row 'Natural Gas' (Last Modified: January 15, 2025). The Hub cites 40 CFR Part 98 Tables C-1 and C-2. <https://www.epa.gov/system/files/other-files/2025-01/ghg-emission-factors-hub-2025.xlsx> (Public domain (US federal government work)). Combustion emissions only (the Hub: 'do not represent upstream emissions'). Higher heating value basis. The Hub page, fetched 2026-10-29, listed the 2025 edition as the latest.
- US EPA, GHG Emission Factors Hub (2025), Table 7 Steam and Heat, note: 'These factors assume natural gas fuel is used to generate steam or heat at 80 percent thermal efficiency.' <https://www.epa.gov/system/files/other-files/2025-01/ghg-emission-factors-hub-2025.xlsx> (Public domain (US federal government work)). An inventory assumption, not a measured boiler. DOE Steam Tip Sheet #15 Table 2 instead lists 85.7% COMBUSTION efficiency for natural gas, for boilers with economizers or air preheaters and 3% flue O2; combustion efficiency excludes shell and blowdown losses, so it is not the same quantity. Use your own boiler's tested fuel-to-steam efficiency.
- US DOE Advanced Manufacturing Office, Energy Tips: STEAM, Steam Tip Sheet #15 'Benchmark the Fuel Cost of Steam Generation', Table 1 'Energy Required to Produce One Pound of Saturated Steam, Btu' ('Calculated from steam tables based on the difference between the enthalpies of saturated steam and feedwater'). DOE/GO-102012-3391, January 2012. <https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/steam15_benchmark.pdf> (Public domain (US federal government work)). Saturated steam only. Superheated steam, steam lost at a pressure not tabulated, or makeup water colder or warmer than the feedwater temperature you name all need your own steam-table value.

## Assumptions

This estimate holds only if all of these are true:

1. Your fuel price equals the public typical value used (5.048263 $/MMBtu). National or generic figures can differ a great deal from a single site's.
2. Your fuel emission factor equals the public typical value used (53.1145 kg CO2e/MMBtu). National or generic figures can differ a great deal from a single site's.
3. Your boiler efficiency equals the public typical value used (0.8 (fraction)). National or generic figures can differ a great deal from a single site's.
4. Failed steam traps on the 150 psig main: each pound of steam carries the public steam-table value used (1,028 Btu/lb), read at the pressure and feedwater temperature entered.
5. Failed steam traps on the 150 psig main: the steam rate entered holds for all 8,760 h/yr.
6. Failed steam traps on the 150 psig main: each pound carries the stated enthalpy difference at the measured boundary, and those conditions do not change through the year.
7. Failed steam traps on the 150 psig main: boiler efficiency is constant at this load, and the fuel saved is priced at the margin.
8. Failed steam traps on the 150 psig main: Scope 1 covers combustion only (no upstream fuel supply); water, treatment chemicals and pumping are not costed.
9. Where a range is entered, the result carries both ends. That is the spread of what was entered, not a probability interval.

## To firm this up: data to collect

In this order: the public values first (they can be furthest from your site), then the measurements.

1. Replace the public fuel price. Your gas bill or fuel supply contract: commodity plus transport/delivery per unit, at the margin (the price of the next unit you would not buy). For gas billed per Mcf or ccf, the bill's heat content (Btu factor) converts it to MMBtu.
2. Replace the public fuel emission factor. EPA GHG Emission Factors Hub, Table 1 Stationary Combustion: CO2, CH4 and N2O per MMBtu for your fuel, combined with the Hub's GWPs (AR5: CH4 28, N2O 265). If your supplier gives a measured carbon content or heat content, use it.
3. Replace the public boiler efficiency. Your boiler's efficiency test (fuel-to-steam, input-output or heat-loss method), a combustion analyzer reading plus shell and blowdown losses, or the boiler design datasheet. For heat that displaces a different heater, that heater's efficiency.
4. Confirm the steam energy for Failed steam traps on the 150 psig main. Steam pressure (psig) and temperature at the point of loss, and the feedwater or makeup water temperature: gauges, the historian, the deaerator.
5. Confirm by measurement: Steam flow saved or lost, lb/h: a steam flowmeter, or a survey estimate (for failed traps, the survey's orifice-based loss per trap; DOE Steam Tip Sheet #1 prints one such table).
6. Confirm by measurement: Operating hours per year the change applies: historian run status, the operating schedule, or maintenance records. Not 8,760 unless it really runs all year.
7. After the change, measure the same quantities again at the same production rate: that before/after pair, not this estimate, is the saving.

## Working

### Failed steam traps on the 150 psig main (steam)

- Heat in the steam = lb/h x hours x Btu/lb / 1,000,000 Btu/MMBtu = 150 to 210 lb/h x 8,760 h/yr x 1,028 Btu/lb / 1,000,000 = **1,350.79 to 1,891.11 MMBtu/yr**
- Fuel = useful heat / boiler efficiency = 1,350.79 to 1,891.11 MMBtu/yr / 0.8 = **1,688.49 to 2,363.89 MMBtu/yr**
- Fuel cost = MMBtu/yr x fuel price = 1,688.49 to 2,363.89 MMBtu/yr x 5.048263 $/MMBtu = **8,523.94 to 11,933.5 $/yr**
- CO2e (Scope 1, combustion) = MMBtu/yr x fuel emission factor = 1,688.49 to 2,363.89 MMBtu/yr x 53.1145 kg CO2e/MMBtu = **89,683.3 to 125,557 kg CO2e/yr**

## Limits

- An estimate from the inputs shown, not a measured or verified saving. It is only as good as the measured kW, flow and hours; a before/after measurement at the same production rate is the proof.
- Fuel CO2e is Scope 1 combustion only (no upstream). Steam and heat become fuel through the boiler efficiency given; water, treatment chemicals, maintenance and pumping are not costed.
- No savings come from a drawing alone: every quantity here was measured or supplied by the user.
