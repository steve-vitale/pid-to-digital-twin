# Opportunity screen: Bayer CropScience methomyl residue treater (Institute, West Virginia), as described by the CSB

Model: `data/bayer_rt/process_model.json`. Questions: `data/questions.json`.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Energy | 4 |
| Heat grade (high-grade heat for low-grade duty) | 2 |
| Metering | 1 |
| Controls and automation | 3 |
| Emissions | 1 |
| Safety questions to verify | 1 |

## Energy

### E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

**About:** P-1  

**Evidence on the drawing / model**

- equipment P-1 reads "P-1 Recirculation pump" (`units[P-1]`)
- Control valve on the discharge: valve LV-102 reads "LV-102 Discharge control valve to the alternate fuel tank" at RT-1 (`final_elements[LV-102]`)
- Other control valve on the discharge: valve TV-104A reads "TV-104A Recirculation valve, heater leg" at E-2 (`final_elements[TV-104A]`)
- Other control valve on the discharge: valve TV-104B reads "TV-104B Recirculation valve, cooler leg" at E-3 (`final_elements[TV-104B]`)
- Flow measurement: instrument FT-103 reads "FT-103 Recirculation flow" at P-1 (`instruments[FT-103]`)
- Checked, none found: no speed control (SC, SIC, SY tag, VFD or VSD) on or next to the pump (`applies_when.without`)

**Data to collect**

- Control valve position (% open) over normal operation [not on drawing]. Where: historian or DCS trend for LV-102 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the valve's controller output; then a walkdown: read the positioner stroke indicator at several rates. How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
- Flow over the same period (a flow-duration curve) [not on drawing]. Where: historian / recorded data: FT-103: digitized series 'recirc_flow_klbh' (from the source report's Fig 11); then site records: production rate records. How: Bin the flow into ranges and count the hours in each.
- Pump rated flow and head [not on drawing]. Where: the vendor datasheet: pump curve and rated duty point; then the pump nameplate on P-1. How: Copy the stated rated flow/head and units. These scalar fields do not establish a matching performance curve or actual operating duty.
- Motor rating and speed [not on drawing]. Where: the motor nameplate on P-1; then maintenance records: motor record card. How: Copy stated rated output and speed in their original units. Efficiency, identity and drive basis are separate review tasks.
- Static head versus friction head [not on drawing]. Where: a walkdown: elevations and pressures at the suction source and the delivery point; then site records: line list or isometrics for pipe lengths and sizes. How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.
- Matched pump curve, rated duty and system operating points [not on drawing]. Candidate scope: anchors. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: the vendor datasheet: pump curve and rated duty point; then the pump nameplate on P-1. How: Retain supplied ratings as unverified candidates. Review the curve against pump identity, installed impeller, speed, fluid, axes/units and revision; distinguish rated duty, BEP and actual operating points. A rating, URI or readability flag does not establish a matching curve or system suitability.
- Motor nameplate, efficiency and drive basis [not on drawing]. Candidate scope: anchors. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: the motor nameplate on P-1; then maintenance records: motor record card. How: Review existing nameplate or motor records for identity, rated shaft output in original units, speed, full-load efficiency and drive/bypass basis. HP/RPM alone do not establish efficiency or measured electrical input; retain missing or ambiguous evidence.

**How it is decided:** Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

**What the source says (S15, S24):** "With rotodynamic pump installations, savings of between 30% and 50% have been achieved in many installations by installing VSDs." Also: "It is estimated that 75% of pump systems are oversized, many by more than 20%."
IAC/ITAC recommendation code: 2.4146 (IAC/ITAC browse page: 5,227 recommendations, 3.0 yr average payback, 31.4% implemented; average dollar figure omitted).

**Limits:** On a hand-built model the valve sits on a stream leaving the pump. On an extracted drawing the links have no direction, so the rule takes a control valve within four drawn links that do not pass through other equipment; it may still be on a branch or the suction side, so check the drawing. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E11: Is this hot line insulated?

**About:** S1  

**Evidence on the drawing / model**

- stream S1 (asset stream:S1) reads "Flasher bottoms feed (methomyl-solvent liquid)" (`streams[S1]`)
- Checked, none found: no insulation code recorded for the line (`applies_when.without`)
- On drawing: Stated line/process temperature: S1 normal_temperature_C = 80 (`streams[S1].facts.normal_temperature_C`)
- On drawing: Supplied candidate fact, basis unverified: S1 normal_temperature_C = 80 (`streams[S1].facts.normal_temperature_C`)

**Data to collect**

- Insulation condition and length of bare pipe [not on drawing]. Where: site records: approved existing line list, insulation survey and inspection records. How: Retain the identified line/location, survey date/revision, condition, length and pipe-size basis. Missing insulation metadata does not establish a bare line. Record unavailable or unsuitable evidence; new observations require the receiving organization's approved process.
- Applicable surface-temperature and insulation evidence [not on drawing]. Candidate scope: anchors. Supplied candidate facts (meaning and suitability unverified): S1 (stream:S1) normal_temperature_C = 80 [streams[S1].facts.normal_temperature_C]. The collection/review request remains open; supplied values or document references do not settle it. Where: site records: approved existing surface/insulation records or suitable documented analysis for this line. How: Review line identity/location, source revision/date, surface versus fluid/design meaning, geometry and operating/ambient/time basis. Retain unreadable, wrong-asset, Boolean and unknown candidates without treating them as applicable evidence. Identify deliberate cooling or process constraints; no new live inspection, insulation installation or saving is established.

**How it is decided:** Refer for engineering investigation when applicable evidence shows bare or damaged insulation on a hot line and no deliberate cooling or process constraint rules it out. The cited surface-temperature criterion is a source screening reference, not an automatic site instruction. Close only the bounded investigation when reviewed evidence settles its scope; this screen does not authorize insulation work.

**What the source says (S1, S19, S24):** "Insulation can typically reduce energy losses by 90%." "Any surface over 120°F should be insulated." LBNL (as reported in LBNL-56183): insulation 3-13%, 1.1 yr.
IAC/ITAC recommendation code: 2.2136 (IAC/ITAC browse page: 1,647 recommendations, 2.2 yr average payback, 61.5% implemented; average dollar figure omitted).

**Limits:** Many models and P&IDs never record insulation: a finding means not recorded, not bare. Stated process/design temperature is not surface evidence. Collection and source applicability need review. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E11: Is this hot line insulated?

**About:** U1  

**Evidence on the drawing / model**

- stream U1 (asset stream:U1) reads "Steam supply to the heater" at E-2 (`streams[U1]`)
- Checked, none found: no insulation code recorded for the line (`applies_when.without`)

**Data to collect**

- Insulation condition and length of bare pipe [not on drawing]. Where: site records: approved existing line list, insulation survey and inspection records. How: Retain the identified line/location, survey date/revision, condition, length and pipe-size basis. Missing insulation metadata does not establish a bare line. Record unavailable or unsuitable evidence; new observations require the receiving organization's approved process.
- Stated line/process temperature [not on drawing]. Where: site records: identified source temperature field and its stated basis. How: Retain the stated temperature and original source/basis. A process-fluid or design temperature is not an actual surface-temperature measurement or a completed insulation evaluation.
- Applicable surface-temperature and insulation evidence [not on drawing]. Candidate scope: anchors. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: site records: approved existing surface/insulation records or suitable documented analysis for this line. How: Review line identity/location, source revision/date, surface versus fluid/design meaning, geometry and operating/ambient/time basis. Retain unreadable, wrong-asset, Boolean and unknown candidates without treating them as applicable evidence. Identify deliberate cooling or process constraints; no new live inspection, insulation installation or saving is established.

**How it is decided:** Refer for engineering investigation when applicable evidence shows bare or damaged insulation on a hot line and no deliberate cooling or process constraint rules it out. The cited surface-temperature criterion is a source screening reference, not an automatic site instruction. Close only the bounded investigation when reviewed evidence settles its scope; this screen does not authorize insulation work.

**What the source says (S1, S19, S24):** "Insulation can typically reduce energy losses by 90%." "Any surface over 120°F should be insulated." LBNL (as reported in LBNL-56183): insulation 3-13%, 1.1 yr.
IAC/ITAC recommendation code: 2.2136 (IAC/ITAC browse page: 1,647 recommendations, 2.2 yr average payback, 61.5% implemented; average dollar figure omitted).

**Limits:** Many models and P&IDs never record insulation: a finding means not recorded, not bare. Stated process/design temperature is not surface evidence. Collection and source applicability need review. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E18: Is heat rejected to cooling water in one place while steam heats a colder stream in another (a heat-integration question)?

**About:** U2, HV-112  

**Evidence on the drawing / model**

- stream U2 (asset stream:U2) reads "Cooling water (80 C) supply to the cooler" at E-3 (`streams[U2]`)
- hand valve HV-112 reads "HV-112 Cooling water supply valve" at E-3 (`manual_valves[HV-112]`)
- Steam-heated user: stream U1 (asset stream:U1) reads "Steam supply to the heater" at E-2 (`streams[U1]`)
- Steam-heated user: instrument FT-106 reads "FT-106 Indicated steam flow to the heater" at E-2 (`instruments[FT-106]`)
- Steam-heated user: valve TV-104C reads "TV-104C Steam flow valve to the heater (Fig 10: Temperature Control Valve)" at E-2 (`final_elements[TV-104C]`)
- Steam-heated user: hand valve HV-108 reads "HV-108 Steam block valve, heater steam supply" at E-2 (`manual_valves[HV-108]`)

**Data to collect**

- Temperatures and duties of the cooled and the heated streams [not on drawing]. Where: only a valve (HV-112) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then historian or DCS trend for FT-106 (no historian tag is mapped in this model for these); then site records: heat and material balance. How: For each stream: supply and target temperature and duty.
- Whether the duties overlap in time [not on drawing]. Where: site records: operating sequence: are both duties needed at the same time?. How: Mark each duty continuous, batch or startup-only.
- Layout distance and fouling [not on drawing]. Where: a walkdown: distance between the two exchangers; then maintenance records: cleaning history. How: Note pipe run and fouling service.

**How it is decided:** Worth a pinch or exchanger study only when the hot stream's temperature range sits above the cold stream's with a practical approach, both run at the same time for long hours, and they are close enough to connect. Otherwise close it.

**What the source says (S19, S24):** Pinch potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management." No % stated in that section.
IAC/ITAC recommendation code: 2.243x; 2.244x (IAC/ITAC browse page: 2.243x: 3,673 recommendations, 1.4 yr average payback, 31.2% implemented; 2.244x: 1,466 recommendations, 1.7 yr, 28.6%; average dollar figure omitted).

**Limits:** A screen pairs any cooling-water-cooled item with any steam-heated item; the temperatures decide. On a reactive system any heat-integration change needs a hazard review first. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

## Heat grade (high-grade heat for low-grade duty)

### H2: Is high-grade (or unknown-grade) steam doing a low-temperature job?

**About:** E-2  

**Evidence on the drawing / model**

- stream U1 (asset stream:U1) reads "Steam supply to the heater" at E-2 (`streams[U1]`)
- valve TV-104C reads "TV-104C Steam flow valve to the heater (Fig 10: Temperature Control Valve)" at E-2 (`final_elements[TV-104C]`)
- Controller: controller TIC-104 reads "TIC-104 Split-range temperature control: heats through the heater (steam valve and heater-leg valve) during startup; at the setpoint it closes the steam valve and moves recirculation from the heater to the cooler (setpoint 135 C)" As found: incorrectly programmed: changing from heating to cooling closed the recirculation valves to both the heater and the cooler, blocking all recirculation flow (p. 39, footnote 29; CSB: not causal). (`controllers[TIC-104]`)
- Equipment: equipment E-2 reads "E-2 Recirculation heater (steam)" (`units[E-2]`)

**Data to collect**

- Steam supply pressure and temperature [not on drawing]. U1 (stream:U1): supplied none; still needed steam_pressure (absent), steam_temperature_C (absent). TV-104C (TV-104C): supplied none; still needed steam_pressure (absent), steam_temperature_C (absent). Remaining across subjects (including additional evidence): steam_pressure, steam_temperature_C. Where: site records: approved supply/header list and existing pressure/temperature records. How: Retain the stated pressure/temperature fields and exact source basis. Their presence does not establish representative actual supply conditions; pressure reference, steam state and operating applicability remain separate review tasks.
- Temperature the user actually needs [not on drawing]. Where: DCS/PLC configuration: the temperature setpoint. How: Note setpoint and normal range.
- A lower-grade heat source on site (a lower steam header, exhaust or waste heat) with spare capacity [not on drawing]. Where: site records: site steam balance; then a walkdown: headers and hot streams near this user. How: List sources whose temperature exceeds the need with a practical approach.
- Applicable steam-supply conditions and operating basis [not on drawing]. Candidate scope: anchors. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: site records: approved existing supply/user configuration and coincident operating-condition records. How: Review supply/user identity and location, source revision, pressure units and gauge/absolute reference, steam condition, coincident period/mode and design-versus-actual basis. Unknown, Boolean, wrong-asset or noncoincident candidates remain unresolved. Saturation temperature is only a conditional reference after the pressure basis/state are established; never infer actual superheated temperature from pressure alone. No new live measurement or change is instructed.

**How it is decided:** Worth a change only if a lower-grade source can meet the needed temperature with margin, for the hours the user runs; if the steam is already the lowest grade available, close it.

**What the source says (S19, S6):** Closest source wordings: pinch potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management" (S19, no % stated); for letdown to the lower pressure, S6's turbogenerator condition. No source gives a number for matching steam grade to duty.

**Limits:** Where the model does not state the steam grade, first identify its source and applicable conditions. Design limits and generic named fields do not establish coincident operation, current user demand or an available alternative source. Supplied candidates need explicit suitability review; no default state, pressure conversion or change recommendation is inferred.

### H4: Is heat rejected to cooling water at a temperature another user could use?

**About:** E-3  

**Evidence on the drawing / model**

- equipment E-3 reads "E-3 Recirculation cooler (80 C water)" (`units[E-3]`)
- stream U2 (asset stream:U2) reads "Cooling water (80 C) supply to the cooler" at E-3 (`streams[U2]`)
- hand valve HV-112 reads "HV-112 Cooling water supply valve" at E-3 (`manual_valves[HV-112]`)
- On drawing: Cooling water supply temperature: E-3 cooling_water_C = 80 (`units[E-3].facts.cooling_water_C`)

**Data to collect**

- Cooling water return temperature [not on drawing]. Where: a walkdown: thermometer on the return. How: Record at normal operation; the return temperature is the grade of the heat on offer.
- Temperature of the stream being cooled (in and out) [not on drawing]. Where: site records: heat and material balance. How: Record at normal operation.
- Cooler duty [not on drawing]. Candidate scope: unit. No candidate values found in the selected model records. The collection/review request remains open; supplied values or document references do not settle it. Where: the vendor datasheet: exchanger datasheet; then site records: heat and material balance. How: Review exchanger identity, units and rated-versus-actual basis. A generic CAPACITY may denote flow or design capacity, not heat duty. Retain coincident flow, heat-capacity basis and inlet/return temperatures over a stated period, or a documented heat balance; supplied scalars do not establish usable recovered heat.
- A heat user that needs heat below the return temperature [not on drawing]. Where: site records: list of heating duties with temperatures; then a walkdown: users nearby. How: Match by temperature, hours and distance.

**How it is decided:** Worth a study only if the heat leaves hotter than a nearby user needs, for overlapping hours; cooling water returning only a few degrees above ambient closes it.

**What the source says (S19, S11):** Closest source wording (S19, pinch): potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management." No % stated. For air compressors S11 says recovery "anywhere from 50 to 90 percent" of the heat, which applies to compressors only.
IAC/ITAC recommendation code: 2.243x (by description).

**Limits:** Does not fire on equipment that cools the cooling water itself (a cooling water cooler, air-cooled exchanger or cooling tower): that equipment rejects the loop's heat, it does not receive process heat.

## Metering

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** E-3  

**Evidence on the drawing / model**

- stream U2 (asset stream:U2) reads "Cooling water (80 C) supply to the cooler" at E-3 (`streams[U2]`)
- hand valve HV-112 reads "HV-112 Cooling water supply valve" at E-3 (`manual_valves[HV-112]`)
- Equipment: equipment E-3 reads "E-3 Recirculation cooler (80 C water)" (`units[E-3]`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: only a valve (HV-112) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

## Controls and automation

### C2: Which measurements have no controller (read by people, or by nothing)?

**About:** PT-101, FT-103, TT-105, FT-106  

**Evidence on the drawing / model**

- instrument PT-101 reads "PT-101 Residue treater pressure" at RT-1 (`instruments[PT-101]`)
- instrument FT-103 reads "FT-103 Recirculation flow" at P-1 (`instruments[FT-103]`)
- instrument TT-105 reads "TT-105 Second temperature measurement (bulk liquid or recirculation loop; see TT-104)" at RT-1 (`instruments[TT-105]`)
- instrument FT-106 reads "FT-106 Indicated steam flow to the heater" at E-2 (`instruments[FT-106]`)
- Interlock that reads it: interlock IL-2 reads "IL-2 PT-101 at or above the maximum pressure setpoint FV-107 held closed" (`interlocks[IL-2]`)
- Interlock that reads it: interlock IL-3 reads "IL-3 FT-103 recirculation flow not established FV-107 held closed" (`interlocks[IL-3]`)
- Checked, none found: no controller in the model or loop list reads these measurements (`applies_when.without`)

**Data to collect**

- Whether operators adjust anything by hand from these readings [not on drawing]. Where: site records: operator logs and round sheets; then ask the operators which of these they act on, and how often. How: Note manual adjustments per shift tied to each reading.
- The control system's own loop list [not on drawing]. Where: DCS/PLC configuration: export the loop and point list. How: Confirm the reading is indication-only and not read by logic the model lacks.

**How it is decided:** Worth automating a reading that operators adjust by hand often, on a service where steadier control saves energy or quality; indication-only readings nobody acts on close the question.

**What the source says (S19):** "energy and cost savings are around 5% or more for many industrial applications of process control systems" (for plants without updated controls). Process control: "Typically 2-18% savings." The source says these figures "cannot be added".

**Limits:** The model or loop list may be incomplete; an uncontrolled reading may be read by logic not in the model.

### C3: Do these control valves lack position feedback?

**About:** FV-107, LV-102, TV-104A, TV-104B, TV-104C  

**Evidence on the drawing / model**

- valve FV-107 reads "FV-107 Feed control valve (flasher bottoms)" at RT-1 (`final_elements[FV-107]`)
- valve LV-102 reads "LV-102 Discharge control valve to the alternate fuel tank" at RT-1 (`final_elements[LV-102]`)
- valve TV-104A reads "TV-104A Recirculation valve, heater leg" at E-2 (`final_elements[TV-104A]`)
- valve TV-104B reads "TV-104B Recirculation valve, cooler leg" at E-3 (`final_elements[TV-104B]`)
- valve TV-104C reads "TV-104C Steam flow valve to the heater (Fig 10: Temperature Control Valve)" at E-2 (`final_elements[TV-104C]`)
- Checked, none found: no position transmitter or indicator (ZT, ZI) drawn on these valves (`applies_when.without`)

**Data to collect**

- Positioner type and diagnostics available [not on drawing]. Where: DCS/PLC configuration: valve positioner configuration (smart positioner? HART/fieldbus diagnostics?); then maintenance records: valve records. How: List which valves report position.
- Valve stiction or backlash [not on drawing]. Where: historian or DCS trend for FV-107, LV-102, TV-104A, TV-104B, TV-104C (no historian tag is mapped in this model for these); then a walkdown: a small step test on each loop in manual. How: Compare controller output with measured response.

**How it is decided:** Add feedback or diagnostics first on valves in energy- or safety-significant loops that show stiction or hunting.

**What the source says (S13):** "Control valve backlash and stiction... are major contributors to process variability." No % stated.

**Limits:** P&IDs often omit positioners; the model saying 'none drawn' does not mean none fitted.

### C6: Does a temperature controller write straight to a steam valve with no flow controller underneath (a cascade candidate)?

**About:** TV-104C  

**Evidence on the drawing / model**

- valve TV-104C reads "TV-104C Steam flow valve to the heater (Fig 10: Temperature Control Valve)" at E-2 (`final_elements[TV-104C]`)
- Temperature controller: controller TIC-104 reads "TIC-104 Split-range temperature control: heats through the heater (steam valve and heater-leg valve) during startup; at the setpoint it closes the steam valve and moves recirculation from the heater to the cooler (setpoint 135 C)" As found: incorrectly programmed: changing from heating to cooling closed the recirculation valves to both the heater and the cooler, blocking all recirculation flow (p. 39, footnote 29; CSB: not causal). (`controllers[TIC-104]`)
- Steam flow measurement: instrument FT-106 reads "FT-106 Indicated steam flow to the heater" at E-2 (`instruments[FT-106]`)
- Checked, none found: no flow controller between the temperature controller and the valve (`applies_when.without`)

**Data to collect**

- Loop behaviour [not on drawing]. Where: DCS/PLC configuration: controller tuning and output history. How: Look for oscillation or slow recovery after steam pressure changes.
- Steam header pressure swings [not on drawing]. Where: site records: steam header pressure trend. How: Note how often supply pressure moves.

**How it is decided:** A flow slave helps when steam supply pressure swings disturb the temperature; a steady header and a well-behaved loop close it.

**What the source says (no source):** No public numeric source found. Report as qualitative only.

**Limits:** Also covers heating and cooling valves on one exchanger with separate controllers that could fight; that pattern is not detected automatically yet.

## Emissions

### E26: Are relief and vent flows to the flare or atmosphere unmetered?

**About:** S8, S9, S11  

**Evidence on the drawing / model**

- stream S8 (asset stream:S8) reads "Condenser vent to the process vent (flare)" (`streams[S8]`)
- stream S9 (asset stream:S9) reads "Relief to the vent header" (`streams[S9]`)
- stream S11 (asset stream:S11) reads "Condenser relief to the vent header (joins S9)" (`streams[S11]`)
- Relief device: relief PSV-101 reads "PSV-101 Residue treater relief valve" at RT-1 (`relief_devices[PSV-101]`)
- Relief device: relief PSV-102 reads "PSV-102 Vent condenser relief valve" at E-1 (`relief_devices[PSV-102]`)
- Checked, none found: no flow measurement on these streams (`applies_when.without`)

**Data to collect**

- Flare or vent flow and composition [not on drawing]. Where: a walkdown: ultrasonic flare-gas meter or a temporary vent flow measurement; then site records: relief valve lift records. How: Separate continuous (background) flow from relief events.

**How it is decided:** Worth metering when background flow is continuous; relief-only lines that seldom lift close the question.

**What the source says (S19):** Background flaring "can be as much as 50% of all flared gases (Miles, 2001)." In refineries it "will generally be less than 50%." No recovery % stated.

**Limits:** Relief paths are safety systems; metering or recovery changes go through a hazard review.

## Safety questions to verify

### C9: Is a trip or interlock shown for this rotating or fired equipment?

**About:** P-1  

**Evidence on the drawing / model**

- equipment P-1 reads "P-1 Recirculation pump" (`units[P-1]`)
- Checked, none found: no safety switch (xSLL, xSHH...), burner management or trip interlock drawn for this equipment (`applies_when.without`)

**Data to collect**

- Cause-and-effect matrix and HAZOP/LOPA records [not on drawing]. Where: site records: cause-and-effect matrix, HAZOP and LOPA reports; then DCS/PLC configuration: safety system configuration. How: Confirm what protects each machine and that it is tested.

**How it is decided:** This is a question to verify, not a finding: close it once the protection is found in the cause-and-effect matrix or safety system.

**What the source says (no source):** Safety benefit; no energy source. Present it as a question to verify, not a finding.

**Limits:** P&IDs often leave trips to the cause-and-effect matrix; 'none drawn' is common and not by itself a gap.

## Questions that found nothing to ask here

No item in this model matched these questions' triggers. That is not a clean bill of health: the model may simply not show what the question looks for. E2, E3, E4, E5, E6, E7, E8, E9, E10, E12, E13, E14, E15, E16, E17, E19, E20, E21, E22, E23, E24, H1, H3, C4, C5, C7, C10, C8, E25, E27, E28, E29, E30, E31, E32, H5, H6, C11, C12.

## Sources cited above

- S1: DOE AMO Steam Tip Sheet #2, Insulate Steam Distribution and Condensate Return Lines (DOE/GO-102012-3404, Jan 2012). https://www.energy.gov/sites/default/files/2014/05/f16/steam2_insulate.pdf (license: Public domain (US federal))
- S6: Steam Tip #20, Replace Pressure-Reducing Valves with Backpressure Turbogenerators (DOE/GO-102012-3409). https://www.energy.gov/sites/prod/files/2014/05/f16/steam20_turbogenerators.pdf (license: Public domain)
- S11: Improving Compressed Air System Performance: A Sourcebook for Industry, 3rd ed. (DOE + Compressed Air Challenge). https://www.energy.gov/sites/default/files/2016/03/f30/Improving%20Compressed%20Air%20Sourcebook%20version%203.pdf (license: DOE publication co-produced with CAC; mostly federal, reuse of CAC content unclear)
- S13: Improving Pumping System Performance: A Sourcebook for Industry, 2nd ed. (DOE + Hydraulic Institute; DOE/GO-102006-2079). https://www.energy.gov/sites/prod/files/2014/05/f16/pump.pdf (license: Federal, co-developed with HI: unclear for HI content)
- S15: Variable Speed Pumping: A Guide to Successful Applications, Executive Summary (DOE ITP with Europump/HI, DOE/GO-102004-1913, May 2004). https://www.energy.gov/sites/prod/files/2014/05/f16/variable_speed_pumping.pdf (license: Unclear (joint with Europump/HI))
- S19: Worrell & Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for Petroleum Refineries: An ENERGY STAR Guide (LBNL-56183, Feb 2005). https://www.osti.gov/servlets/purl/862119 (license: DOE-lab (contractor) report: unclear, but freely citable. Its tables quote older secondary sources, so figures are cited as reported in LBNL-56183)
- S22: FEMP Metering Best Practices: A Guide to Achieving Utility Resource Efficiency, Release 3.0 (PNNL-23892, Mar 2015). https://www.wbdg.org/FFC/DOE/NLCRIT/mbpg_2015.pdf (license: Contractor-prepared federal guide: unclear. Its savings figures are buildings-focused)
- S24: DOE IAC/ITAC database: browse pages, download, schema document. https://itac.university/index/arc/2. (license: No license or terms stated: unclear)
