# Opportunity screen: Illustrative water utility

Model: `model.json`. Questions: `data/questions.json`.

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
| Heat grade (high-grade heat for low-grade duty) | 0 |
| Metering | 0 |
| Controls and automation | 1 |
| Emissions | 0 |
| Safety questions to verify | 1 |

## Energy

### E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

**About:** P-1\

**Evidence on the drawing / model**

- equipment P-1 reads "P-1 Water pump" (`units[P-1]`)
- Control valve on the discharge: valve FV-101 reads "FV-101 Discharge flow control valve" at P-1 (`final_elements[FV-101]`)
- Flow measurement: instrument FT-101 reads "FT-101 Discharge flow measurement" at P-1 (`instruments[FT-101]`)
- Checked, none found: no speed control (SC, SIC, SY tag, VFD or VSD) on or next to the pump (`applies_when.without`)

**Data to collect**

- Control valve position (% open) over normal operation [not on drawing]. Where: historian or DCS trend for FV-101 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the valve's controller output; then a walkdown: read the positioner stroke indicator at several rates. How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
- Flow over the same period (a flow-duration curve) [not on drawing]. Where: historian or DCS trend for FT-101 (no historian tag is mapped in this model for these); then site records: production rate records. How: Bin the flow into ranges and count the hours in each.
- Pump rated flow and head [not on drawing]. Where: the vendor datasheet: pump curve and rated duty point; then the pump nameplate on P-1. How: Copy the rated flow and head and get the pump curve.
- Motor rating and speed [not on drawing]. Where: the motor nameplate on P-1; then maintenance records: motor record card. How: Copy rated power, speed and efficiency from the motor nameplate.
- Static head versus friction head [not on drawing]. Where: a walkdown: elevations and pressures at the suction source and the delivery point; then site records: line list or isometrics for pipe lengths and sizes. How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.

**How it is decided:** Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

**What the source says (S15, S24):** "With rotodynamic pump installations, savings of between 30% and 50% have been achieved in many installations by installing VSDs." Also: "It is estimated that 75% of pump systems are oversized, many by more than 20%."
IAC/ITAC recommendation code: 2.4146 (IAC/ITAC browse page: 5,227 recommendations, 3.0 yr average payback, 31.4% implemented; average dollar figure omitted).

**Limits:** On a hand-built model the valve sits on a stream leaving the pump. On an extracted drawing the links have no direction, so the rule takes a control valve within four drawn links that do not pass through other equipment; it may still be on a branch or the suction side, so check the drawing. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

## Controls and automation

### C3: Do these control valves lack position feedback?

**About:** FV-101\

**Evidence on the drawing / model**

- valve FV-101 reads "FV-101 Discharge flow control valve" at P-1 (`final_elements[FV-101]`)
- Checked, none found: no position transmitter or indicator (ZT, ZI) drawn on these valves (`applies_when.without`)

**Data to collect**

- Positioner type and diagnostics available [not on drawing]. Where: DCS/PLC configuration: valve positioner configuration (smart positioner? HART/fieldbus diagnostics?); then maintenance records: valve records. How: List which valves report position.
- Valve stiction or backlash [not on drawing]. Where: historian or DCS trend for FV-101 (no historian tag is mapped in this model for these); then a walkdown: a small step test on each loop in manual. How: Compare controller output with measured response.

**How it is decided:** Add feedback or diagnostics first on valves in energy- or safety-significant loops that show stiction or hunting.

**What the source says (S13):** "Control valve backlash and stiction... are major contributors to process variability." No % stated.

**Limits:** P&IDs often omit positioners; the model saying 'none drawn' does not mean none fitted.

## Safety questions to verify

### C9: Is a trip or interlock shown for this rotating or fired equipment?

**About:** P-1\

**Evidence on the drawing / model**

- equipment P-1 reads "P-1 Water pump" (`units[P-1]`)
- Checked, none found: no safety switch (xSLL, xSHH...), burner management or trip interlock drawn for this equipment (`applies_when.without`)

**Data to collect**

- Cause-and-effect matrix and HAZOP/LOPA records [not on drawing]. Where: site records: cause-and-effect matrix, HAZOP and LOPA reports; then DCS/PLC configuration: safety system configuration. How: Confirm what protects each machine and that it is tested.

**How it is decided:** This is a question to verify, not a finding: close it once the protection is found in the cause-and-effect matrix or safety system.

**What the source says (no source):** Safety benefit; no energy source. Present it as a question to verify, not a finding.

**Limits:** P&IDs often leave trips to the cause-and-effect matrix; 'none drawn' is common and not by itself a gap.

## Questions that found nothing to ask here

No item in this model matched these questions' triggers. That is not a clean bill of health: the model may simply not show what the question looks for. E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12, E13, E14, E15, E16, E17, E18, E19, E20, E21, E22, E23, E24, H1, H2, H3, H4, C1, C2, C4, C5, C6, C7, C10, C8, E25, E26, E27, E28, E29, E30, E31, E32, H5, H6, C11, C12.

## Sources cited above

- S13: Improving Pumping System Performance: A Sourcebook for Industry, 2nd ed. (DOE + Hydraulic Institute; DOE/GO-102006-2079). https://www.energy.gov/sites/prod/files/2014/05/f16/pump.pdf (license: Federal, co-developed with HI: unclear for HI content)
- S15: Variable Speed Pumping: A Guide to Successful Applications, Executive Summary (DOE ITP with Europump/HI, DOE/GO-102004-1913, May 2004). https://www.energy.gov/sites/prod/files/2014/05/f16/variable_speed_pumping.pdf (license: Unclear (joint with Europump/HI))
- S24: DOE IAC/ITAC database: browse pages, download, schema document. https://itac.university/index/arc/2. (license: No license or terms stated: unclear)
