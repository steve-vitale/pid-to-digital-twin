# Opportunity screen: Tennessee Eastman Challenge Process

Model: `data/te_process_model.json`. Questions: `data/questions.json`. Loop list: `examples/loop-audit/te_loops.csv`.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Energy | 2 |
| Heat grade (high-grade heat for low-grade duty) | 3 |
| Metering | 2 |
| Controls and automation | 2 |
| Emissions | 0 |
| Safety questions to verify | 1 |

## Energy

### E6: Is this compressor spilling flow back (recycle or blow-off) more than surge protection needs?

**About:** K-101  

**Evidence on the drawing / model**

- equipment K-101 reads "K-101 Recycle Compressor" (`units[K-101]`)
- Recycle valve: valve FV-105 reads "FV-105 Compressor recycle valve" at K-101 (`final_elements[FV-105]`)
- Compressor power: instrument JT-120 reads "JT-120 Compressor work" at K-101 (`instruments[JT-120]`)

**Data to collect**

- Recycle (or blow-off) valve opening over normal operation [not on drawing]. Where: historian / recorded data: FV-105: recorded signal XMV(5) in the TE data files; then DCS/PLC configuration: anti-surge or recycle controller output. How: Take a month or more of valve position; note the hours it is open at normal throughput.
- Surge margin at normal operation [not on drawing]. Where: the vendor datasheet: compressor map with the surge line; then DCS/PLC configuration: the anti-surge controller's surge-line settings. How: Compare the normal operating point with the surge line plus the controller's margin.
- Compressor power [not on drawing]. Where: historian / recorded data: JT-120: recorded signal XMEAS(20) in the TE data files; then a walkdown: power meter at the drive. How: Record power with the valve at its normal opening.

**How it is decided:** Worth a look when the recycle or blow-off valve is open at normal throughput, or the controller margin is wider than the vendor map needs. If it only opens during upsets or turndown, close it.

**What the source says (S11):** Blow-off "is a waste of energy and should be used only where necessary to avoid surge." Inlet throttling: "Capacity can typically be reduced from 100 percent capacity to about 70-80 percent with reasonable energy reduction." No % saving stated.

**Limits:** Surge protection is a machine-protection function: any change goes through the compressor vendor and a change review.

### E18: Is heat rejected to cooling water in one place while steam heats a colder stream in another (a heat-integration question)?

**About:** TT-121, TT-122, TV-121, FV-117  

**Evidence on the drawing / model**

- instrument TT-121 reads "TT-121 Reactor cooling water outlet temperature" at R-101 (`instruments[TT-121]`)
- instrument TT-122 reads "TT-122 Separator Cooling Water Outlet Temp" at E-101 (`instruments[TT-122]`)
- valve TV-121 reads "TV-121 Reactor cooling water flow valve" at R-101 (`final_elements[TV-121]`)
- valve FV-117 reads "FV-117 Condenser cooling water flow valve" at E-101 (`final_elements[FV-117]`)
- Steam-heated user: instrument FT-119 reads "FT-119 Stripper steam flow" at C-101 (`instruments[FT-119]`)
- Steam-heated user: valve FV-119 reads "FV-119 Stripper steam valve" at C-101 (`final_elements[FV-119]`)

**Data to collect**

- Temperatures and duties of the cooled and the heated streams [not on drawing]. Where: historian / recorded data: TT-121: recorded signal XMEAS(21) in the TE data files; TT-122: recorded signal XMEAS(22) in the TE data files; only the valve position is recorded (FV-117: recorded signal XMV(11) in the TE data files; TV-121: recorded signal XMV(10) in the TE data files); flow needs a meter or a calibrated valve curve; then historian / recorded data: FT-119: recorded signal XMEAS(19) in the TE data files; only the valve position is recorded (FV-119: recorded signal XMV(9) in the TE data files); flow needs a meter or a calibrated valve curve; then site records: heat and material balance. How: For each stream: supply and target temperature and duty.
- Whether the duties overlap in time [not on drawing]. Where: site records: operating sequence: are both duties needed at the same time?. How: Mark each duty continuous, batch or startup-only.
- Layout distance and fouling [not on drawing]. Where: a walkdown: distance between the two exchangers; then maintenance records: cleaning history. How: Note pipe run and fouling service.

**How it is decided:** Worth a pinch or exchanger study only when the hot stream's temperature range sits above the cold stream's with a practical approach, both run at the same time for long hours, and they are close enough to connect. Otherwise close it.

**What the source says (S19, S24):** Pinch potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management." No % stated in that section.
IAC/ITAC recommendation code: 2.243x; 2.244x (IAC/ITAC browse page: 2.243x: 3,673 recommendations, 1.4 yr average payback, 31.2% implemented; 2.244x: 1,466 recommendations, 1.7 yr, 28.6%; average dollar figure omitted).

**Limits:** A screen pairs any cooling-water-cooled item with any steam-heated item; the temperatures decide. On a reactive system any heat-integration change needs a hazard review first. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

## Heat grade (high-grade heat for low-grade duty)

### H2: Is high-grade (or unknown-grade) steam doing a low-temperature job?

**About:** C-101  

**Evidence on the drawing / model**

- valve FV-119 reads "FV-119 Stripper steam valve" at C-101 (`final_elements[FV-119]`)
- Temperature measurement at the user: instrument TT-118 reads "TT-118 Stripper temperature" at C-101 (`instruments[TT-118]`)
- Controller: controller FIC-119 reads "FIC-119 Stripper steam flow controller" at C-101 (`controllers[FIC-119]`)
- Equipment: equipment C-101 reads "C-101 Product Stripper" (`units[C-101]`)

**Data to collect**

- Steam supply pressure and temperature [not on drawing]. Where: a walkdown: pressure gauge and thermometer at the supply; then site records: steam header list. How: Record supply conditions; saturation temperature follows from pressure.
- Temperature the user actually needs [not on drawing]. Where: historian / recorded data: TT-118: recorded signal XMEAS(18) in the TE data files; then DCS/PLC configuration: the temperature setpoint. How: Note setpoint and normal range.
- A lower-grade heat source on site (a lower steam header, exhaust or waste heat) with spare capacity [not on drawing]. Where: site records: site steam balance; then a walkdown: headers and hot streams near this user. How: List sources whose temperature exceeds the need with a practical approach.

**How it is decided:** Worth a change only if a lower-grade source can meet the needed temperature with margin, for the hours the user runs; if the steam is already the lowest grade available, close it.

**What the source says (S19, S6):** Closest source wordings: pinch potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management" (S19, no % stated); for letdown to the lower pressure, S6's turbogenerator condition. No source gives a number for matching steam grade to duty.

**Limits:** Where the model does not state the steam grade, the question is first 'what grade is it?'.

### H4: Is heat rejected to cooling water at a temperature another user could use?

**About:** R-101  

**Evidence on the drawing / model**

- instrument TT-121 reads "TT-121 Reactor cooling water outlet temperature" at R-101 (`instruments[TT-121]`)
- valve TV-121 reads "TV-121 Reactor cooling water flow valve" at R-101 (`final_elements[TV-121]`)
- Temperature measurement: instrument TT-109 reads "TT-109 Reactor temperature" at R-101 (`instruments[TT-109]`)
- Equipment: equipment R-101 reads "R-101 Reactor" (`units[R-101]`)

**Data to collect**

- Cooling water supply temperature [not on drawing]. Where: a walkdown: thermometer on the supply. How: Record at normal operation.
- Cooling water return temperature [not on drawing]. Where: historian / recorded data: TT-121: recorded signal XMEAS(21) in the TE data files; then a walkdown: thermometer on the return. How: Record at normal operation; the return temperature is the grade of the heat on offer.
- Temperature of the stream being cooled (in and out) [not on drawing]. Where: historian / recorded data: TT-109: recorded signal XMEAS(9) in the TE data files; then site records: heat and material balance. How: Record at normal operation.
- Cooler duty [not on drawing]. Where: the vendor datasheet: exchanger datasheet; then site records: heat and material balance. How: Duty = flow x heat capacity x temperature rise.
- A heat user that needs heat below the return temperature [not on drawing]. Where: site records: list of heating duties with temperatures; then a walkdown: users nearby. How: Match by temperature, hours and distance.

**How it is decided:** Worth a study only if the heat leaves hotter than a nearby user needs, for overlapping hours; cooling water returning only a few degrees above ambient closes it.

**What the source says (S19, S11):** Closest source wording (S19, pinch): potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management." No % stated. For air compressors S11 says recovery "anywhere from 50 to 90 percent" of the heat, which applies to compressors only.
IAC/ITAC recommendation code: 2.243x (by description).

**Limits:** Does not fire on equipment that cools the cooling water itself (a cooling water cooler, air-cooled exchanger or cooling tower): that equipment rejects the loop's heat, it does not receive process heat.

### H4: Is heat rejected to cooling water at a temperature another user could use?

**About:** E-101  

**Evidence on the drawing / model**

- instrument TT-122 reads "TT-122 Separator Cooling Water Outlet Temp" at E-101 (`instruments[TT-122]`)
- valve FV-117 reads "FV-117 Condenser cooling water flow valve" at E-101 (`final_elements[FV-117]`)
- Equipment: equipment E-101 reads "E-101 Product Condenser" (`units[E-101]`)

**Data to collect**

- Cooling water supply temperature [not on drawing]. Where: a walkdown: thermometer on the supply. How: Record at normal operation.
- Cooling water return temperature [not on drawing]. Where: historian / recorded data: TT-122: recorded signal XMEAS(22) in the TE data files; then a walkdown: thermometer on the return. How: Record at normal operation; the return temperature is the grade of the heat on offer.
- Temperature of the stream being cooled (in and out) [not on drawing]. Where: site records: heat and material balance. How: Record at normal operation.
- Cooler duty [not on drawing]. Where: the vendor datasheet: exchanger datasheet; then site records: heat and material balance. How: Duty = flow x heat capacity x temperature rise.
- A heat user that needs heat below the return temperature [not on drawing]. Where: site records: list of heating duties with temperatures; then a walkdown: users nearby. How: Match by temperature, hours and distance.

**How it is decided:** Worth a study only if the heat leaves hotter than a nearby user needs, for overlapping hours; cooling water returning only a few degrees above ambient closes it.

**What the source says (S19, S11):** Closest source wording (S19, pinch): potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management." No % stated. For air compressors S11 says recovery "anywhere from 50 to 90 percent" of the heat, which applies to compressors only.
IAC/ITAC recommendation code: 2.243x (by description).

**Limits:** Does not fire on equipment that cools the cooling water itself (a cooling water cooler, air-cooled exchanger or cooling tower): that equipment rejects the loop's heat, it does not receive process heat.

## Metering

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** R-101  

**Evidence on the drawing / model**

- valve TV-121 reads "TV-121 Reactor cooling water flow valve" at R-101 (`final_elements[TV-121]`)
- Utility temperature or pressure: instrument TT-121 reads "TT-121 Reactor cooling water outlet temperature" at R-101 (`instruments[TT-121]`)
- Equipment: equipment R-101 reads "R-101 Reactor" (`units[R-101]`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: only the valve position is recorded (TV-121: recorded signal XMV(10) in the TE data files); flow needs a meter or a calibrated valve curve; then a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** E-101  

**Evidence on the drawing / model**

- valve FV-117 reads "FV-117 Condenser cooling water flow valve" at E-101 (`final_elements[FV-117]`)
- Utility temperature or pressure: instrument TT-122 reads "TT-122 Separator Cooling Water Outlet Temp" at E-101 (`instruments[TT-122]`)
- Equipment: equipment E-101 reads "E-101 Product Condenser" (`units[E-101]`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: only the valve position is recorded (FV-117: recorded signal XMV(11) in the TE data files); flow needs a meter or a calibrated valve curve; then a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

## Controls and automation

### C2: Which measurements have no controller (read by people, or by nothing)?

**About:** FT-106, PT-107, TT-111, PT-113, FT-114, PT-116 and 2 more  

**Evidence on the drawing / model**

- instrument FT-106 reads "FT-106 Reactor feed rate" at R-101 (`instruments[FT-106]`)
- instrument PT-107 reads "PT-107 Reactor pressure" at R-101 (`instruments[PT-107]`)
- instrument TT-111 reads "TT-111 Separator temperature" at V-101 (`instruments[TT-111]`)
- instrument PT-113 reads "PT-113 Separator pressure" at V-101 (`instruments[PT-113]`)
- instrument FT-114 reads "FT-114 Separator underflow" at V-101 (`instruments[FT-114]`)
- instrument PT-116 reads "PT-116 Stripper pressure" at C-101 (`instruments[PT-116]`)
- instrument JT-120 reads "JT-120 Compressor work" at K-101 (`instruments[JT-120]`)
- instrument TT-122 reads "TT-122 Separator Cooling Water Outlet Temp" at E-101 (`instruments[TT-122]`)
- Checked, none found: no controller in the model or loop list reads these measurements (`applies_when.without`)

**Data to collect**

- Whether operators adjust anything by hand from these readings [not on drawing]. Where: site records: operator logs and round sheets; then ask the operators which of these they act on, and how often. How: Note manual adjustments per shift tied to each reading.
- The control system's own loop list [not on drawing]. Where: DCS/PLC configuration: export the loop and point list. How: Confirm the reading is indication-only and not read by logic the model lacks.

**How it is decided:** Worth automating a reading that operators adjust by hand often, on a service where steadier control saves energy or quality; indication-only readings nobody acts on close the question.

**What the source says (S19):** "energy and cost savings are around 5% or more for many industrial applications of process control systems" (for plants without updated controls). Process control: "Typically 2-18% savings." The source says these figures "cannot be added".

**Limits:** The model or loop list may be incomplete; an uncontrolled reading may be read by logic not in the model.

### C3: Do these control valves lack position feedback?

**About:** FV-102, FV-103, FV-101, FV-104, FV-105, FV-110 and 5 more  

**Evidence on the drawing / model**

- valve FV-102 reads "FV-102 D feed flow valve" at U-100 (`final_elements[FV-102]`)
- valve FV-103 reads "FV-103 E feed flow valve" at U-100 (`final_elements[FV-103]`)
- valve FV-101 reads "FV-101 A feed flow valve" at U-100 (`final_elements[FV-101]`)
- valve FV-104 reads "FV-104 A and C feed flow valve" at C-101 (`final_elements[FV-104]`)
- valve FV-105 reads "FV-105 Compressor recycle valve" at K-101 (`final_elements[FV-105]`)
- valve FV-110 reads "FV-110 Purge valve" at V-101 (`final_elements[FV-110]`)
- valve LV-112 reads "LV-112 Separator pot liquid flow valve" at V-101 (`final_elements[LV-112]`)
- valve LV-115 reads "LV-115 Stripper liquid product flow valve" at C-101 (`final_elements[LV-115]`)
- valve FV-119 reads "FV-119 Stripper steam valve" at C-101 (`final_elements[FV-119]`)
- valve TV-121 reads "TV-121 Reactor cooling water flow valve" at R-101 (`final_elements[TV-121]`)
- valve FV-117 reads "FV-117 Condenser cooling water flow valve" at E-101 (`final_elements[FV-117]`)
- Checked, none found: no position transmitter or indicator (ZT, ZI) drawn on these valves (`applies_when.without`)

**Data to collect**

- Positioner type and diagnostics available [not on drawing]. Where: DCS/PLC configuration: valve positioner configuration (smart positioner? HART/fieldbus diagnostics?); then maintenance records: valve records. How: List which valves report position.
- Valve stiction or backlash [not on drawing]. Where: historian / recorded data: FV-101: recorded signal XMV(3) in the TE data files; FV-102: recorded signal XMV(1) in the TE data files; FV-103: recorded signal XMV(2) in the TE data files; FV-104: recorded signal XMV(4) in the TE data files; FV-105: recorded signal XMV(5) in the TE data files; FV-110: recorded signal XMV(6) in the TE data files; FV-117: recorded signal XMV(11) in the TE data files; FV-119: recorded signal XMV(9) in the TE data files; LV-112: recorded signal XMV(7) in the TE data files; LV-115: recorded signal XMV(8) in the TE data files; TV-121: recorded signal XMV(10) in the TE data files; then a walkdown: a small step test on each loop in manual. How: Compare controller output with measured response.

**How it is decided:** Add feedback or diagnostics first on valves in energy- or safety-significant loops that show stiction or hunting.

**What the source says (S13):** "Control valve backlash and stiction... are major contributors to process variability." No % stated.

**Limits:** P&IDs often omit positioners; the model saying 'none drawn' does not mean none fitted.

## Safety questions to verify

### C9: Is a trip or interlock shown for this rotating or fired equipment?

**About:** K-101  

**Evidence on the drawing / model**

- equipment K-101 reads "K-101 Recycle Compressor" (`units[K-101]`)
- Checked, none found: no safety switch (xSLL, xSHH...), burner management or trip interlock drawn for this equipment (`applies_when.without`)

**Data to collect**

- Cause-and-effect matrix and HAZOP/LOPA records [not on drawing]. Where: site records: cause-and-effect matrix, HAZOP and LOPA reports; then DCS/PLC configuration: safety system configuration. How: Confirm what protects each machine and that it is tested.

**How it is decided:** This is a question to verify, not a finding: close it once the protection is found in the cause-and-effect matrix or safety system.

**What the source says (no source):** Safety benefit; no energy source. Present it as a question to verify, not a finding.

**Limits:** P&IDs often leave trips to the cause-and-effect matrix; 'none drawn' is common and not by itself a gap.

## Questions that found nothing to ask here

No item in this model matched these questions' triggers. That is not a clean bill of health: the model may simply not show what the question looks for. E1, E2, E3, E4, E5, E7, E8, E9, E10, E11, E12, E13, E14, E15, E16, E17, E19, E20, E21, E22, E23, E24, H1, H3, C4, C5, C6, C7, C10, C8, E25, E26.

## Sources cited above

- S6: Steam Tip #20, Replace Pressure-Reducing Valves with Backpressure Turbogenerators (DOE/GO-102012-3409). https://www.energy.gov/sites/prod/files/2014/05/f16/steam20_turbogenerators.pdf (license: Public domain)
- S11: Improving Compressed Air System Performance: A Sourcebook for Industry, 3rd ed. (DOE + Compressed Air Challenge). https://www.energy.gov/sites/default/files/2016/03/f30/Improving%20Compressed%20Air%20Sourcebook%20version%203.pdf (license: DOE publication co-produced with CAC; mostly federal, reuse of CAC content unclear)
- S13: Improving Pumping System Performance: A Sourcebook for Industry, 2nd ed. (DOE + Hydraulic Institute; DOE/GO-102006-2079). https://www.energy.gov/sites/prod/files/2014/05/f16/pump.pdf (license: Federal, co-developed with HI: unclear for HI content)
- S19: Worrell & Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for Petroleum Refineries: An ENERGY STAR Guide (LBNL-56183, Feb 2005). https://www.osti.gov/servlets/purl/862119 (license: DOE-lab (contractor) report: unclear, but freely citable. Its tables quote older secondary sources, so figures are cited as reported in LBNL-56183)
- S22: FEMP Metering Best Practices: A Guide to Achieving Utility Resource Efficiency, Release 3.0 (PNNL-23892, Mar 2015). https://www.wbdg.org/FFC/DOE/NLCRIT/mbpg_2015.pdf (license: Contractor-prepared federal guide: unclear. Its savings figures are buildings-focused)
- S24: DOE IAC/ITAC database: browse pages, download, schema document. https://itac.university/index/arc/2. (license: No license or terms stated: unclear)
