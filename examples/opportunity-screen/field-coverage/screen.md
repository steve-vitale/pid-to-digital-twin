# Opportunity screen: examples/opportunity-screen/field-coverage/model.json

Model: `examples/opportunity-screen/field-coverage/model.json`. Questions: `data/questions.json`.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Energy | 0 |
| Heat grade (high-grade heat for low-grade duty) | 1 |
| Metering | 0 |
| Controls and automation | 0 |
| Emissions | 0 |
| Safety questions to verify | 0 |

## Heat grade (high-grade heat for low-grade duty)

### H2: Is high-grade (or unknown-grade) steam doing a low-temperature job?

**About:** H-1  

**Evidence on the drawing / model**

- valve TV-101 reads "TV-101 Steam supply from independent header A" at H-1 (`final_elements[TV-101]`)
- valve TV-102 reads "TV-102 Steam supply from independent header B" at H-1 (`final_elements[TV-102]`)
- Equipment: equipment H-1 reads "H-1 Process water heater" (`units[H-1]`)
- On drawing: Steam supply pressure and temperature: TV-101 steam_pressure = 8 bar; header A (`final_elements[TV-101].facts.steam_pressure`)
- On drawing: Steam supply pressure and temperature: TV-102 steam_temperature_C = 140 (`final_elements[TV-102].facts.steam_temperature_C`)

**Data to collect**

- Steam supply pressure and temperature [not on drawing]. TV-101 (TV-101): supplied steam_pressure; still needed steam_temperature_C (absent). TV-102 (TV-102): supplied steam_temperature_C; still needed steam_pressure (absent). Remaining across subjects (including additional evidence): steam_pressure, steam_temperature_C. Where: a walkdown: pressure gauge and thermometer at the supply; then site records: steam header list. How: Record supply conditions; saturation temperature follows from pressure.
- Temperature the user actually needs [not on drawing]. Where: DCS/PLC configuration: the temperature setpoint. How: Note setpoint and normal range.
- A lower-grade heat source on site (a lower steam header, exhaust or waste heat) with spare capacity [not on drawing]. Where: site records: site steam balance; then a walkdown: headers and hot streams near this user. How: List sources whose temperature exceeds the need with a practical approach.

**How it is decided:** Worth a change only if a lower-grade source can meet the needed temperature with margin, for the hours the user runs; if the steam is already the lowest grade available, close it.

**What the source says (S19, S6):** Closest source wordings: pinch potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management" (S19, no % stated); for letdown to the lower pressure, S6's turbogenerator condition. No source gives a number for matching steam grade to duty.

**Limits:** Where the model does not state the steam grade, the question is first 'what grade is it?'.

## Sources cited above

- S6: Steam Tip #20, Replace Pressure-Reducing Valves with Backpressure Turbogenerators (DOE/GO-102012-3409). https://www.energy.gov/sites/prod/files/2014/05/f16/steam20_turbogenerators.pdf (license: Public domain)
- S19: Worrell & Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for Petroleum Refineries: An ENERGY STAR Guide (LBNL-56183, Feb 2005). https://www.osti.gov/servlets/purl/862119 (license: DOE-lab (contractor) report: unclear, but freely citable. Its tables quote older secondary sources, so figures are cited as reported in LBNL-56183)
