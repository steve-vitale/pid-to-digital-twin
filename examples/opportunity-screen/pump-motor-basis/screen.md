# Opportunity screen: Fictional pump, motor and cooler collection controls

Model: `examples/opportunity-screen/pump-motor-basis/model.json`. Questions: `data/questions.json`.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Energy | 3 |
| Heat grade (high-grade heat for low-grade duty) | 1 |
| Metering | 0 |
| Controls and automation | 0 |
| Emissions | 0 |
| Safety questions to verify | 0 |

## Energy

### E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

**About:** P-900  

**Evidence on the drawing / model**

- equipment P-900 reads "P-900 Water transfer pump" (`units[P-900]`)
- Control valve on the discharge: valve FV-900 reads "FV-900 Discharge flow control valve" at P-900 (`final_elements[FV-900]`)
- Checked, none found: no speed control (SC, SIC, SY tag, VFD or VSD) on or next to the pump (`applies_when.without`)
- On drawing: Pump rated flow and head: P-900 CAPACITY = 100 gpm (`units[P-900].facts.CAPACITY`)
- On drawing: Pump rated flow and head: P-900 DISCHARGE = 90 ft (`units[P-900].facts.DISCHARGE`)
- On drawing: Motor rating and speed: P-900 HP = 10 (`units[P-900].facts.HP`)
- On drawing: Motor rating and speed: P-900 RPM = 1750 (`units[P-900].facts.RPM`)
- On drawing: Supplied candidate fact, basis unverified: P-900 pump_curve_uri = P-901-curve.pdf (`units[P-900].facts.pump_curve_uri`)
- On drawing: Supplied candidate fact, basis unverified: P-900 pump_curve_asset = P-901 (`units[P-900].facts.pump_curve_asset`)
- On drawing: Supplied candidate fact, basis unverified: P-900 pump_curve_readable = False (`units[P-900].facts.pump_curve_readable`)
- On drawing: Supplied candidate fact, basis unverified: P-900 motor_efficiency = {'value': 0.9, 'basis': 'unreviewed nameplate transcription; motor identity unknown'} (`units[P-900].facts.motor_efficiency`)

**Data to collect**

- Control valve position (% open) over normal operation [not on drawing]. Where: historian or DCS trend for FV-900 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the valve's controller output; then a walkdown: read the positioner stroke indicator at several rates. How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
- Flow over the same period (a flow-duration curve) [not on drawing]. Where: site records: production rate records. How: Bin the flow into ranges and count the hours in each.
- Static head versus friction head [not on drawing]. Where: a walkdown: elevations and pressures at the suction source and the delivery point; then site records: line list or isometrics for pipe lengths and sizes. How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.
- Matched pump curve, rated duty and system operating points [not on drawing]. Candidate scope: anchors. Supplied candidate facts (meaning and suitability unverified): P-900 (P-900) pump_curve_uri = "P-901-curve.pdf" [units[P-900].facts.pump_curve_uri]; P-900 (P-900) pump_curve_asset = "P-901" [units[P-900].facts.pump_curve_asset]; P-900 (P-900) pump_curve_readable = false [units[P-900].facts.pump_curve_readable]. The collection/review request remains open; supplied values or document references do not settle it. Where: the vendor datasheet: pump curve and rated duty point; then the pump nameplate on P-900. How: Retain supplied ratings as unverified candidates. Review the curve against pump identity, installed impeller, speed, fluid, axes/units and revision; distinguish rated duty, BEP and actual operating points. A rating, URI or readability flag does not establish a matching curve or system suitability.
- Motor nameplate, efficiency and drive basis [not on drawing]. Candidate scope: anchors. Supplied candidate facts (meaning and suitability unverified): P-900 (P-900) motor_efficiency = {"value": 0.9, "basis": "unreviewed nameplate transcription; motor identity unknown"} [units[P-900].facts.motor_efficiency]. The collection/review request remains open; supplied values or document references do not settle it. Where: the motor nameplate on P-900; then maintenance records: motor record card. How: Review existing nameplate or motor records for identity, rated shaft output in original units, speed, full-load efficiency and drive/bypass basis. HP/RPM alone do not establish efficiency or measured electrical input; retain missing or ambiguous evidence.

**How it is decided:** Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

**What the source says (S15, S24):** "With rotodynamic pump installations, savings of between 30% and 50% have been achieved in many installations by installing VSDs." Also: "It is estimated that 75% of pump systems are oversized, many by more than 20%."
IAC/ITAC recommendation code: 2.4146 (IAC/ITAC browse page: 5,227 recommendations, 3.0 yr average payback, 31.4% implemented; average dollar figure omitted).

**Limits:** On a hand-built model the valve sits on a stream leaving the pump. On an extracted drawing the links have no direction, so the rule takes a control valve within four drawn links that do not pass through other equipment; it may still be on a branch or the suction side, so check the drawing. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E2: Is this pump oversized, given a bypass line around it or its valve?

**About:** P-900  

**Evidence on the drawing / model**

- equipment P-900 reads "P-900 Water transfer pump" (`units[P-900]`)
- Bypass: hand valve HV-900 reads "HV-900 Pump bypass valve" at P-900 (`manual_valves[HV-900]`)
- On drawing: Pump stated rated flow and head: P-900 CAPACITY = 100 gpm (`units[P-900].facts.CAPACITY`)
- On drawing: Pump stated rated flow and head: P-900 DISCHARGE = 90 ft (`units[P-900].facts.DISCHARGE`)
- On drawing: Supplied candidate fact, basis unverified: P-900 pump_curve_uri = P-901-curve.pdf (`units[P-900].facts.pump_curve_uri`)
- On drawing: Supplied candidate fact, basis unverified: P-900 pump_curve_asset = P-901 (`units[P-900].facts.pump_curve_asset`)
- On drawing: Supplied candidate fact, basis unverified: P-900 pump_curve_readable = False (`units[P-900].facts.pump_curve_readable`)

**Data to collect**

- Measured flow and head at normal operation [not on drawing]. Where: a walkdown: suction and discharge pressure gauges plus a clamp-on ultrasonic flow meter. How: Read flow and suction and discharge pressure at steady operation.
- How often the bypass is open [not on drawing]. Where: a walkdown: valve position and line temperature; then site records: operator logs. How: Record bypass position over several shifts.
- Matched pump curve and best-efficiency-point (BEP) duty [not on drawing]. Candidate scope: anchors. Supplied candidate facts (meaning and suitability unverified): P-900 (P-900) pump_curve_uri = "P-901-curve.pdf" [units[P-900].facts.pump_curve_uri]; P-900 (P-900) pump_curve_asset = "P-901" [units[P-900].facts.pump_curve_asset]; P-900 (P-900) pump_curve_readable = false [units[P-900].facts.pump_curve_readable]. The collection/review request remains open; supplied values or document references do not settle it. Where: the vendor datasheet: pump curve. How: Review the matching curve for installed impeller, speed, fluid and units, then identify its BEP flow/head with source revision and locator. Keep generic CAPACITY/DISCHARGE as rated candidates, not BEP. Retain unknown or unsuitable curve evidence and compare with representative measured operation.

**How it is decided:** Prioritize the pump if it runs at a flow 30% or more away from BEP or the bypass is used routinely; otherwise close it.

**What the source says (S13, S14):** Five indications: "excessive flow noise, highly throttled flow control valves, heavy use of bypass lines, frequent replacements of bearings and seals, and intermittent pump operation." Prioritize pumps "with flow rates of 30% or more from the BEP flow rates, or with system imbalances greater than 20%." No % saving stated.

**Limits:** A drawn bypass may be normally closed; the drawing cannot show how it is used.

### E4: Is this motor oversized for its load?

**About:** P-900  

**Evidence on the drawing / model**

- equipment P-900 reads "P-900 Water transfer pump" (`units[P-900]`)
- On drawing: Motor rated power: P-900 HP = 10 (`units[P-900].facts.HP`)
- On drawing: Supplied candidate fact, basis unverified: P-900 RPM = 1750 (`units[P-900].facts.RPM`)
- On drawing: Supplied candidate fact, basis unverified: P-900 motor_efficiency = {'value': 0.9, 'basis': 'unreviewed nameplate transcription; motor identity unknown'} (`units[P-900].facts.motor_efficiency`)

**Data to collect**

- Measured input power or current at normal load [not on drawing]. Candidate scope: anchors. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: site records: approved existing motor input-power and representative load/production records. How: Retain representative period, coverage, load timing and measurement basis. Prefer documented input kW; three-phase watts derived from voltage/current also need power factor and phase basis. Current alone is unreliable at low load. No new live measurements are instructed; record unavailable evidence.
- Motor nameplate, rated output and full-load efficiency [not on drawing]. Candidate scope: anchors. Supplied candidate facts (meaning and suitability unverified): P-900 (P-900) RPM = 1750 [units[P-900].facts.RPM]; P-900 (P-900) motor_efficiency = {"value": 0.9, "basis": "unreviewed nameplate transcription; motor identity unknown"} [units[P-900].facts.motor_efficiency]. The collection/review request remains open; supplied values or document references do not settle it. Where: the motor nameplate on P-900; then maintenance records: motor record card. How: Review identity, rated shaft output in original units, full-load efficiency, rated speed/current and source revision. HP alone cannot settle the efficiency needed by the load calculation. Stated output is not measured electrical input; retain unknown efficiency rather than supplying a default.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

## Heat grade (high-grade heat for low-grade duty)

### H4: Is heat rejected to cooling water at a temperature another user could use?

**About:** E-900  

**Evidence on the drawing / model**

- equipment E-900 reads "E-900 Process cooler with cooling water" (`units[E-900]`)
- On drawing: Cooling water supply temperature: E-900 cooling_water_C = 20 (`units[E-900].facts.cooling_water_C`)
- On drawing: Supplied candidate fact, basis unverified: E-900 CAPACITY = 100 gpm (`units[E-900].facts.CAPACITY`)

**Data to collect**

- Cooling water return temperature [not on drawing]. Where: a walkdown: thermometer on the return. How: Record at normal operation; the return temperature is the grade of the heat on offer.
- Temperature of the stream being cooled (in and out) [not on drawing]. Where: site records: heat and material balance. How: Record at normal operation.
- Cooler duty [not on drawing]. Candidate scope: unit. Supplied candidate facts (meaning and suitability unverified): E-900 (E-900) CAPACITY = "100 gpm" [units[E-900].facts.CAPACITY]. The collection/review request remains open; supplied values or document references do not settle it. Where: the vendor datasheet: exchanger datasheet; then site records: heat and material balance. How: Review exchanger identity, units and rated-versus-actual basis. A generic CAPACITY may denote flow or design capacity, not heat duty. Retain coincident flow, heat-capacity basis and inlet/return temperatures over a stated period, or a documented heat balance; supplied scalars do not establish usable recovered heat.
- A heat user that needs heat below the return temperature [not on drawing]. Where: site records: list of heating duties with temperatures; then a walkdown: users nearby. How: Match by temperature, hours and distance.

**How it is decided:** Worth a study only if the heat leaves hotter than a nearby user needs, for overlapping hours; cooling water returning only a few degrees above ambient closes it.

**What the source says (S19, S11):** Closest source wording (S19, pinch): potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management." No % stated. For air compressors S11 says recovery "anywhere from 50 to 90 percent" of the heat, which applies to compressors only.
IAC/ITAC recommendation code: 2.243x (by description).

**Limits:** Does not fire on equipment that cools the cooling water itself (a cooling water cooler, air-cooled exchanger or cooling tower): that equipment rejects the loop's heat, it does not receive process heat.

## Sources cited above

- S11: Improving Compressed Air System Performance: A Sourcebook for Industry, 3rd ed. (DOE + Compressed Air Challenge). https://www.energy.gov/sites/default/files/2016/03/f30/Improving%20Compressed%20Air%20Sourcebook%20version%203.pdf (license: DOE publication co-produced with CAC; mostly federal, reuse of CAC content unclear)
- S13: Improving Pumping System Performance: A Sourcebook for Industry, 2nd ed. (DOE + Hydraulic Institute; DOE/GO-102006-2079). https://www.energy.gov/sites/prod/files/2014/05/f16/pump.pdf (license: Federal, co-developed with HI: unclear for HI content)
- S14: Pumping Systems Tip #6, Match Pumps to System Requirements (DOE/GO-102005-2160). https://www.energy.gov/sites/prod/files/2014/05/f16/match_pumps_to_system.pdf (license: Public domain)
- S15: Variable Speed Pumping: A Guide to Successful Applications, Executive Summary (DOE ITP with Europump/HI, DOE/GO-102004-1913, May 2004). https://www.energy.gov/sites/prod/files/2014/05/f16/variable_speed_pumping.pdf (license: Unclear (joint with Europump/HI))
- S16: Improving Motor and Drive System Performance: A Sourcebook for Industry (DOE/GO-102014-4356, Feb 2014; prepared by WSU Energy Program + NREL). https://www.energy.gov/sites/prod/files/2014/04/f15/amo_motors_sourcebook_web.pdf (license: Federal publication; contractor-prepared, so unclear but citable)
- S19: Worrell & Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for Petroleum Refineries: An ENERGY STAR Guide (LBNL-56183, Feb 2005). https://www.osti.gov/servlets/purl/862119 (license: DOE-lab (contractor) report: unclear, but freely citable. Its tables quote older secondary sources, so figures are cited as reported in LBNL-56183)
- S24: DOE IAC/ITAC database: browse pages, download, schema document. https://itac.university/index/arc/2. (license: No license or terms stated: unclear)
