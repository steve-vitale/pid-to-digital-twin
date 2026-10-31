# Opportunity screen: Fictional fan and heater collection controls

Model: `examples/opportunity-screen/collection-basis/model.json`. Questions: `data/questions.json`.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Energy | 1 |
| Heat grade (high-grade heat for low-grade duty) | 1 |
| Metering | 0 |
| Controls and automation | 0 |
| Emissions | 0 |
| Safety questions to verify | 0 |

## Energy

### E5: Is fan airflow controlled by a damper or inlet vanes instead of speed?

**About:** F-1  

**Evidence on the drawing / model**

- equipment F-1 reads "F-1 Ventilation fan" (`units[F-1]`)
- Damper: final element DMP-1 reads "DMP-1 Fan discharge damper" at F-1 (`final_elements[DMP-1]`)
- Checked, none found: no speed control on or next to the fan (`applies_when.without`)
- On drawing: Supplied candidate fact, basis unverified: F-1 HP = 15 (`units[F-1].facts.HP`)
- On drawing: Supplied candidate fact, basis unverified: F-1 RPM = 1780 (`units[F-1].facts.RPM`)

**Data to collect**

- Damper position, control mode and operating period [not on drawing]. Candidate scope: anchors. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: historian or DCS trend for DMP-1 (no historian tag is mapped in this model for these); then site records: existing control narratives, drive settings and operating logs. How: Use approved existing records. Identify damper/vanes type, fixed or variable speed, bypass/manual modes and representative dates/hours; retain unknown modes and gaps. A drawn device does not establish how it is used.
- Matched fan curves and system operating points [not on drawing]. Candidate scope: anchors. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: the vendor datasheet: fan pressure/flow and available power/efficiency curves for the installed configuration; then site records: system resistance or required airflow/pressure, operating points and process constraints. How: Review the document itself against fan identity/size, speed, gas conditions, axes/units and static/total pressure basis. Retain source revision, locator and suitability gaps; a URI or present/readable flag does not establish a usable matching curve.
- Motor nameplate rating and drive basis [not on drawing]. Candidate scope: anchors. Supplied candidate facts (meaning and suitability unverified): F-1 (F-1) HP = 15 [units[F-1].facts.HP]; F-1 (F-1) RPM = 1780 [units[F-1].facts.RPM]. The collection/review request remains open; supplied values or document references do not settle it. Where: site records: existing motor nameplate/datasheet and drive/bypass configuration. How: Retain original power units, rated speed, asset identity, source and rating basis. Review whether power denotes rated shaft output or electrical input. Do not demand a second unit representation or treat a conversion as measured input.
- Fan electrical-input and load history [not on drawing]. Candidate scope: anchors. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: site records: approved existing electrical-input metering and representative fan/process operating records. How: Retain period/coverage and coincident airflow, pressure, actual speed/control mode and load timing where available. Distinguish measured electrical input, stated motor output, energy over a period and assumed hours. Record unavailable evidence; this request does not instruct live measurements.

**How it is decided:** Worth further study when representative records show sustained part-load control and required airflow/pressure can be maintained. A drive quote needs reviewed fan/system curves, operating constraints and electrical-input/load history; the cube-speed relationship alone is not a site estimate.

**What the source says (S17):** Dampers "remain closed so often that they can be found rusted or locked in a restrictive position... the system continually operates against an unnecessary load." Fan "power is related to the cube of fan speed." No % stated.
IAC/ITAC recommendation code: 2.4146 (by description).

**Limits:** Damper or drive presence does not establish actual control mode. Fan/system conditions and process requirements need qualified review. Similarity relationships are conditional, not a universal drive recommendation or a quantified benefit for this plant.

## Heat grade (high-grade heat for low-grade duty)

### H3: Is electric resistance heat serving a low-temperature load another heat source could carry?

**About:** EH-1  

**Evidence on the drawing / model**

- equipment EH-1 reads "EH-1 Electric heater, tank warming" (`units[EH-1]`)
- On drawing: Supplied candidate fact, basis unverified: EH-1 kW = 20 (`units[EH-1].facts.kW`)
- On drawing: Supplied candidate fact, basis unverified: EH-1 HP = 26.8 (`units[EH-1].facts.HP`)
- On drawing: Supplied candidate fact, basis unverified: EH-1 load_temperature_C = 60 (`units[EH-1].facts.load_temperature_C`)

**Data to collect**

- Heater nameplate/design rating and basis [not on drawing]. Candidate scope: anchors. Supplied candidate facts (meaning and suitability unverified): EH-1 (EH-1) kW = 20 [units[EH-1].facts.kW]; EH-1 (EH-1) HP = 26.8 [units[EH-1].facts.HP]. The collection/review request remains open; supplied values or document references do not settle it. Where: site records: existing heater nameplate or design/vendor record. How: Identify heater/service and confirm the heating method. Retain stated rating in original units, source/locator and whether it denotes electrical input or delivered heat. Generic kW/HP fields remain candidates; ambiguous HP or a unit conversion does not establish rated electrical input.
- Heater operating hours and load history [not on drawing]. Candidate scope: anchors. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: site records: approved existing heater energization, power/energy and production/load records. How: State the representative period, coverage and load/stage/cycling basis. Distinguish enabled, energized, full-load-equivalent and calendar hours, and measured versus estimated values. Retain missing periods/gaps; nameplate rating or a bare hours scalar does not establish actual consumption. No live measurement is requested.
- Waste or low-grade heat nearby [not on drawing]. Candidate scope: anchors. Supplied candidate facts (meaning and suitability unverified): EH-1 (EH-1) load_temperature_C = 60 [units[EH-1].facts.load_temperature_C]. The collection/review request remains open; supplied values or document references do not settle it. Where: site records: documented process demand and candidate source conditions/availability; then a walkdown: approved observations of candidate sources and distance; no equipment changes. How: Review required load temperature/range and demand timing alongside source temperature, available quantity/flow, timing overlap, medium/contamination and distance. Keep unknown availability and compatibility explicit; nearby heat alone does not establish a usable match.

**How it is decided:** Worth a look when the heater runs long hours and a lower-grade source above the load temperature is close by.

**What the source says (no source):** No source in the reviewed set gives wording or a number for replacing electric heat with recovered heat.

**Limits:** Fires only when the model states a load temperature at or below 150 C, a catalog screening heuristic rather than a validated feasibility cutoff. Without a stated temperature the load remains unknown and this question does not fire. Rated power, actual operation and source compatibility need separate review; no recovered energy or saving is established.

## Sources cited above

- S17: Improving Fan System Performance: A Sourcebook for Industry (DOE/GO-102003-1294). https://www.energy.gov/sites/prod/files/2014/05/f16/fan_sourcebook.pdf (license: Public domain / federal (co-produced with AMCA; unclear for AMCA content))
