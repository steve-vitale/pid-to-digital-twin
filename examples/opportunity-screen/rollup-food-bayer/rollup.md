# Opportunity screen roll-up: food, bayer

**How to read this.** Each site's screen, combined. A question is listed once, with every site and asset it fired on and the data to collect at each site, so the same request can be planned across sites. The order is only how many sites a question fired at, then how many findings: it is not a ranking by value, and no savings are computed. The "what the source says" lines are the sources' general figures, quoted as written. Read each site's own screen for the evidence behind a finding.

| Site | Screen | Model | Findings |
|---|---|---|---|
| food | `examples/opportunity-screen/food/questions.json` | `examples/opportunity-screen/food_plant_model.json` | 24 |
| bayer | `examples/opportunity-screen/bayer/questions.json` | `data/bayer_rt/process_model.json` | 12 |

| Question | Family | Sites | Findings |
|---|---|---|---|
| C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user? | Metering | food, bayer | 4 |
| C2: Which measurements have no controller (read by people, or by nothing)? | Controls and automation | food, bayer | 2 |
| C3: Do these control valves lack position feedback? | Controls and automation | food, bayer | 2 |
| C9: Is a trip or interlock shown for this rotating or fired equipment? | Safety questions to verify | food, bayer | 2 |
| E11: Is this hot line insulated? | Energy | bayer | 2 |
| E29: Does this refrigeration compressor carry part load on its slide valve (or hot gas bypass) with no speed control? | Energy | food | 2 |
| E31: Does this oven, dryer or fryer send its hot exhaust to atmosphere with no heat recovery on it? | Energy | food | 2 |
| E32: Is the burner air-fuel ratio on this oven, dryer or fryer checked and set, with no flue O2 measurement drawn? | Energy | food | 2 |
| H6: Could this oven's, dryer's or fryer's exhaust heat serve a low-grade heating duty elsewhere (hot water, CIP, space heating)? | Heat grade (high-grade heat for low-grade duty) | food | 2 |
| C11: Is this dryer's or oven's exhaust (and make-up air) rate set by hand rather than by exhaust humidity? | Controls and automation | food | 2 |
| E1: Is this pump throttled by a control valve when it could run on a variable speed drive? | Energy | bayer | 1 |
| E18: Is heat rejected to cooling water in one place while steam heats a colder stream in another (a heat-integration question)? | Energy | bayer | 1 |
| E19: Is the compressed air header pressure higher than the end users need? | Energy | food | 1 |
| E22: Does the air compressor lack enough storage for intermittent large users? | Energy | food | 1 |
| E23: Is air compressor heat rejected when it could heat something? | Energy | food | 1 |
| H2: Is high-grade (or unknown-grade) steam doing a low-temperature job? | Heat grade (high-grade heat for low-grade duty) | bayer | 1 |
| H4: Is heat rejected to cooling water at a temperature another user could use? | Heat grade (high-grade heat for low-grade duty) | bayer | 1 |
| C6: Does a temperature controller write straight to a steam valve with no flow controller underneath (a cascade candidate)? | Controls and automation | bayer | 1 |
| E26: Are relief and vent flows to the flare or atmosphere unmetered? | Emissions | bayer | 1 |
| E27: Is the refrigeration condensing (head) pressure held higher than the weather allows, with no floating head pressure? | Energy | food | 1 |
| E28: Is each refrigeration suction level held colder than the warmest load on it needs? | Energy | food | 1 |
| E30: Are these evaporators defrosted on a fixed timer rather than when frost is actually there? | Energy | food | 1 |
| H5: Is refrigeration condenser heat rejected while a low-grade heating duty nearby is met with fuel or steam? | Heat grade (high-grade heat for low-grade duty) | food | 1 |
| C12: Is power to these refrigeration compressors measured, so the plant's kW against load can be tracked? | Metering | food | 1 |

## C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

Fired at 2 of 2 sites.

- **food**, O-302 (`C1@O-302`): O-302, TV-302, U2
- **food**, F-303 (`C1@F-303`): F-303, TV-303, U3
- **food**, WH-401 (`C1@WH-401`): TV-401, U4, WH-401
- **bayer**, E-3 (`C1@E-3`): E-3, HV-112, U2

**Data to collect**

- Utility flow to this user. How: Measure flow over a representative period and compare with production.
  - food [not on drawing]: For `C1@O-302`: only a valve (TV-302) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve. For `C1@F-303`: only a valve (TV-303) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve. For `C1@WH-401`: only a valve (TV-401) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve. Then, for all of them: a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion
  - bayer [not on drawing]: only a valve (HV-112) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion
- Who would use the reading. How: Name the report the meter would feed.
  - food [not on drawing]: site records: energy or production reporting
  - bayer [not on drawing]: site records: energy or production reporting

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

## C2: Which measurements have no controller (read by people, or by nothing)?

Fired at 2 of 2 sites.

- **food**, PT-201, JT-201, TT-202, TT-205, TT-206, PDT-206 and 4 more (`C2@model`): AT-302, FT-301, JT-201, PDT-206, PT-201, TT-202, TT-205, TT-206, TT-304, TT-305
- **bayer**, PT-101, FT-103, TT-105, FT-106 (`C2@model`): FT-103, FT-106, IL-2, IL-3, PT-101, TT-105

**Data to collect**

- Whether operators adjust anything by hand from these readings. How: Note manual adjustments per shift tied to each reading.
  - food [not on drawing]: site records: operator logs and round sheets; then ask the operators which of these they act on, and how often
  - bayer [not on drawing]: site records: operator logs and round sheets; then ask the operators which of these they act on, and how often
- The control system's own loop list. How: Confirm the reading is indication-only and not read by logic the model lacks.
  - food [not on drawing]: DCS/PLC configuration: export the loop and point list
  - bayer [not on drawing]: DCS/PLC configuration: export the loop and point list

**How it is decided:** Worth automating a reading that operators adjust by hand often, on a service where steadier control saves energy or quality; indication-only readings nobody acts on close the question.

**What the source says (S19):** "energy and cost savings are around 5% or more for many industrial applications of process control systems" (for plants without updated controls). Process control: "Typically 2-18% savings." The source says these figures "cannot be added".

## C3: Do these control valves lack position feedback?

Fired at 2 of 2 sites.

- **food**, TV-301, TV-302, TV-303, TV-401, PV-501 (`C3@model`): PV-501, TV-301, TV-302, TV-303, TV-401
- **bayer**, FV-107, LV-102, TV-104A, TV-104B, TV-104C (`C3@model`): FV-107, LV-102, TV-104A, TV-104B, TV-104C

**Data to collect**

- Positioner type and diagnostics available. How: List which valves report position.
  - food [not on drawing]: DCS/PLC configuration: valve positioner configuration (smart positioner? HART/fieldbus diagnostics?); then maintenance records: valve records
  - bayer [not on drawing]: DCS/PLC configuration: valve positioner configuration (smart positioner? HART/fieldbus diagnostics?); then maintenance records: valve records
- Valve stiction or backlash. How: Compare controller output with measured response.
  - food [not on drawing]: historian or DCS trend for PV-501, TV-301, TV-302, TV-303, TV-401 (no historian tag is mapped in this model for these); then a walkdown: a small step test on each loop in manual
  - bayer [not on drawing]: historian or DCS trend for FV-107, LV-102, TV-104A, TV-104B, TV-104C (no historian tag is mapped in this model for these); then a walkdown: a small step test on each loop in manual

**How it is decided:** Add feedback or diagnostics first on valves in energy- or safety-significant loops that show stiction or hunting.

**What the source says (S13):** "Control valve backlash and stiction... are major contributors to process variability." No % stated.

## C9: Is a trip or interlock shown for this rotating or fired equipment?

Fired at 2 of 2 sites.

- **food**, K-201, K-202, K-203, AC-501 (`C9@model`): AC-501, K-201, K-202, K-203
- **bayer**, P-1 (`C9@model`): P-1

**Data to collect**

- Cause-and-effect matrix and HAZOP/LOPA records. How: Confirm what protects each machine and that it is tested.
  - food [not on drawing]: site records: cause-and-effect matrix, HAZOP and LOPA reports; then DCS/PLC configuration: safety system configuration
  - bayer [not on drawing]: site records: cause-and-effect matrix, HAZOP and LOPA reports; then DCS/PLC configuration: safety system configuration

**How it is decided:** This is a question to verify, not a finding: close it once the protection is found in the cause-and-effect matrix or safety system.

**What the source says (no source):** Safety benefit; no energy source. Present it as a question to verify, not a finding.

## E11: Is this hot line insulated?

Fired at 1 of 2 sites. Asked and quiet at: food.

- **bayer**, S1 (`E11@stream:S1`): S1
- **bayer**, U1 (`E11@stream:U1`): U1

**Data to collect**

- Insulation condition and length of bare pipe. How: Note bare or damaged lengths and their pipe size.
  - bayer [not on drawing]: a walkdown: infrared camera or surface thermometer along the line; then site records: line list insulation code
- Line temperature. How: Surfaces over 120 F (49 C) qualify.
  - bayer [not on drawing]: a walkdown: surface thermometer

**How it is decided:** Insulate bare lengths over 120 F (49 C) unless they are deliberately bare (for example a line that must cool); closes if the line is already insulated.

**What the source says (S1, S19, S24):** "Insulation can typically reduce energy losses by 90%." "Any surface over 120°F should be insulated." LBNL (as reported in LBNL-56183): insulation 3-13%, 1.1 yr.

## E29: Does this refrigeration compressor carry part load on its slide valve (or hot gas bypass) with no speed control?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, K-201 (`E29@K-201`): JT-201, K-201
- **food**, K-202 (`E29@K-202`): K-202, ZT-202

**Data to collect**

- Slide valve (capacity) position over normal operation. How: Hours spent below full load, by load band.
  - food [not on drawing]: For `E29@K-202`: historian or DCS trend for ZT-202 (no historian tag is mapped in this model for these). Then, for all of them: DCS/PLC configuration: slide valve position or percent capacity per compressor from the refrigeration plant controls, a month or more
- Compressor power and run hours. How: Power at each load band, so part-load efficiency can be seen.
  - food [not on drawing]: For `E29@K-201`: historian or DCS trend for JT-201 (no historian tag is mapped in this model for these). Then, for all of them: a walkdown: power logger on the compressor motor across a normal week
- How the compressors are sequenced. How: Note whether more than one machine trims at the same time.
  - food [not on drawing]: DCS/PLC configuration: which compressor trims, and the order and pressures at which they load and unload

**How it is decided:** Worth a look when screws spend long hours part-loaded on the slide valve while another could be off, or when no machine on a suction level has speed control to trim. Close it if each runs near full load or a sequencer already keeps one machine trimming.

**What the source says (S25):** Among control strategies that "may compromise system energy efficiency" (S25, p. 59, citing Pearson 2003): "Slide valve unloading of oversized screw compressors." and "Hot gas bypass of compressors." Speed control (S25, p. 63): "ASDs used on compressors below a part-load ratio of about 95% will deliver performance equal to a fixed speed compressor but with lower electricity requirements. However, at near full (i.e., 100%) load, ASDs are approximately 3% less efficient than fixed speed drives".

## E31: Does this oven, dryer or fryer send its hot exhaust to atmosphere with no heat recovery on it?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, D-301 (`E31@D-301`): D-301, FT-301, S1, TT-304, TV-301, U1
- **food**, O-302 (`E31@O-302`): AT-302, O-302, S2, TT-305, TV-302, U2

**Data to collect**

- Exhaust temperature and flow. How: Record both at normal production; heat on offer = mass flow x specific heat x (exhaust temperature minus the temperature it could be cooled to).
  - food [not on drawing]: For `E31@D-301`: historian or DCS trend for TT-304 (no historian tag is mapped in this model for these). For `E31@O-302`: historian or DCS trend for TT-305 (no historian tag is mapped in this model for these). Then, for all of them: a walkdown: thermometer and a pitot or anemometer traverse in the exhaust duct, at normal production
- Exhaust moisture and contaminants. How: Moist exhaust carries latent heat but condenses; fat and dust foul exchangers unless filtered or washed.
  - food [not on drawing]: a walkdown: humidity or dew point probe in the exhaust; note fat, flour, sugar or product dust; then maintenance records: duct and stack cleaning history
- Fuel or heat input and operating hours. How: A month of input at a known production rate.
  - food [not on drawing]: For `E31@D-301`: historian or DCS trend for FT-301 (no historian tag is mapped in this model for these). For `E31@O-302`: only a valve (TV-302) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve. Then, for all of them: utility bills or the site energy report: gas sub-meter readings for this line; then site records: production schedule: hours per week the line runs
- Where the heat could go in the unit itself. How: Preheating the unit's own inlet air comes first; H6 asks about users elsewhere.
  - food [not on drawing]: site records: inlet (drying or combustion) air temperature and flow; then a walkdown: room next to the unit for ductwork or a run-around coil

**How it is decided:** Worth a study when the exhaust leaves hot, the line runs long hours, and the exhaust is clean enough or can be filtered or washed. Close it for short or intermittent runs, or when there is no room for the ductwork.

**What the source says (S26, S25):** Dryers (S26, p. 104): "A simple form of heat recovery in retrofit applications is to utilize the exhaust air of a dryer to preheat the inlet air stream, thereby saving energy." Spray dryers (S25, p. 90): "It is estimated that up to 30% of the heat from the dryer exhaust can be recovered." Fryers (S26, p. 107): "Conditioning of the exhaust gas is required, however, to remove fats and to reduce fouling of the heat exchange system." No source in this set gives a figure for ovens.

## E32: Is the burner air-fuel ratio on this oven, dryer or fryer checked and set, with no flue O2 measurement drawn?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, D-301 (`E32@D-301`): D-301, FT-301, TV-301, U1
- **food**, F-303 (`E32@F-303`): F-303, TV-303, U3

**Data to collect**

- Flue O2 and CO at high and low fire. How: Compare with the burner maker's recommended O2 for this equipment.
  - food [not on drawing]: a walkdown: portable combustion analyser in the flue or exhaust at high and low fire; then site records: the last burner tuning report
- Air-fuel ratio settings and how they are held. How: Note whether the ratio is fixed linkage, electronic ratio or trimmed.
  - food [not on drawing]: DCS/PLC configuration: burner management and ratio control settings; then the vendor datasheet: burner datasheet: recommended excess air across the turndown range
- Fuel use. How: A month of fuel use at a known production rate.
  - food [not on drawing]: For `E32@D-301`: historian or DCS trend for FT-301 (no historian tag is mapped in this model for these). For `E32@F-303`: only a valve (TV-303) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve. Then, for all of them: utility bills or the site energy report: gas sub-meter readings for this unit
- Excess air the process needs. How: This is a floor: the burner may not be tuned below it.
  - food [not on drawing]: site records: the oven or dryer maker's minimum exhaust and excess air for moisture and solvent removal, and any flammable-vapour (LEL) limit

**How it is decided:** Worth a tune-up when measured flue O2 is above what the burner maker recommends and the process does not need the extra air. On ovens and dryers that drive off water or solvent the dilution and drying air are part of the process: never cut below the maker's or the safety minimum.

**What the source says (S27):** S27 (p. 1): "Periodic checking and resetting of air-fuel ratios for burners is one of the simplest ways to get maximum efficiency out of fuel-fired process heating equipment such as furnaces, ovens, heaters, and boilers." And: "Processes that evaporate moisture or solvents need large amounts of excess air to dilute flammable solvents to noncombustible levels, to ensure adequate drying rates, and to carry vapors out of the oven. Lowering excess air to minimal levels can slow down the process and create an explosion hazard." No typical % stated (the sheet's worked example is one furnace).

## H6: Could this oven's, dryer's or fryer's exhaust heat serve a low-grade heating duty elsewhere (hot water, CIP, space heating)?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, D-301 (`H6@D-301`): D-301, S1, TT-304, W2, WH-401
- **food**, O-302 (`H6@O-302`): AT-302, O-302, S2, TT-305, W2, WH-401

**Data to collect**

- Exhaust temperature, flow and hours. How: At normal production.
  - food [not on drawing]: For `H6@D-301`: historian or DCS trend for TT-304 (no historian tag is mapped in this model for these). For `H6@O-302`: historian or DCS trend for TT-305 (no historian tag is mapped in this model for these). Then, for all of them: a walkdown: thermometer and a pitot or anemometer traverse in the exhaust duct; then site records: production schedule
- The low-grade duty: temperature needed, load and hours. How: Match by temperature, hours and distance.
  - food [not on drawing]: site records: hot water, CIP, wash water and space heating loads by hour
- Distance and exhaust cleanliness. How: The closer and cleaner, the better.
  - food [not on drawing]: a walkdown: duct or pipe run from the stack to the user; fat, dust or product carry-over in the exhaust

**How it is decided:** Worth a study when the exhaust is well above the temperature the duty needs, the two run at the same times, and they are close enough to connect. Otherwise close it.

**What the source says (S28, S26):** S28 (p. 1): "many companies install heat exchangers on the exhaust stacks of furnaces and ovens to produce hot water or to generate hot air for space heating." The same sheet: "The temperature difference between the primary and secondary process should be high enough (at least 200°F), and there should be a sufficient amount of usable waste heat." Fryers (S26, p. 107): "Heat can be recovered indirectly from a fryer's fat-laden exhaust gases via a heat exchange system and used for pre-heating air and water for use in other facility processes." No % stated.

## C11: Is this dryer's or oven's exhaust (and make-up air) rate set by hand rather than by exhaust humidity?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, D-301 (`C11@D-301`): D-301, HV-304, TT-304
- **food**, O-302 (`C11@O-302`): AT-302, O-302, TT-305

**Data to collect**

- Exhaust humidity and temperature over a production run. How: Compare the exhaust humidity with what the product and the process allow.
  - food [not on drawing]: For `C11@D-301`: historian or DCS trend for TT-304 (no historian tag is mapped in this model for these). For `C11@O-302`: historian or DCS trend for TT-305 (no historian tag is mapped in this model for these). Then, for all of them: a walkdown: humidity or dew point logger in the exhaust duct for a full run
- Exhaust damper or fan setting and how it is set. How: Note whether it moves with production rate or product.
  - food [not on drawing]: For `C11@D-301`: historian or DCS trend for HV-304 (no historian tag is mapped in this model for these). Then, for all of them: DCS/PLC configuration: exhaust damper position or fan speed, and whether anything adjusts it; then a walkdown: damper position marks
- Product moisture at the exit and its specification. How: Over-drying shows as moisture well below specification.
  - food [not on drawing]: site records: quality records: product moisture out of the dryer or oven against specification

**How it is decided:** Worth a look when the exhaust leaves well below the humidity the product and the safety limits allow, so heated air is thrown away unsaturated. Close it if the exhaust is already near the allowed humidity or the rate is set by a solvent (LEL) or dust limit.

**What the source says (S26):** S26 (p. 104): "Process controls, such as feedback controllers, feed forward controllers, and model-based predictive controllers, can help to minimize dryer energy consumption by more precisely controlling energy inputs to meet the needs of the product being processed." The sensors it lists include "absorption capacitive sensors (for air humidity)". No % stated.

## E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

Fired at 1 of 2 sites. Asked and quiet at: food.

- **bayer**, P-1 (`E1@P-1`): FT-103, LV-102, P-1, TV-104A, TV-104B

**Data to collect**

- Control valve position (% open) over normal operation. How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
  - bayer [not on drawing]: historian or DCS trend for LV-102 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the valve's controller output; then a walkdown: read the positioner stroke indicator at several rates
- Flow over the same period (a flow-duration curve). How: Bin the flow into ranges and count the hours in each.
  - bayer [not on drawing]: historian / recorded data: FT-103: digitized series 'recirc_flow_klbh' (from the source report's Fig 11); then site records: production rate records
- Pump rated flow and head. How: Copy the rated flow and head and get the pump curve.
  - bayer [not on drawing]: the vendor datasheet: pump curve and rated duty point; then the pump nameplate on P-1
- Motor rating and speed. How: Copy rated power, speed and efficiency from the motor nameplate.
  - bayer [not on drawing]: the motor nameplate on P-1; then maintenance records: motor record card
- Static head versus friction head. How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.
  - bayer [not on drawing]: a walkdown: elevations and pressures at the suction source and the delivery point; then site records: line list or isometrics for pipe lengths and sizes

**How it is decided:** Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

**What the source says (S15, S24):** "With rotodynamic pump installations, savings of between 30% and 50% have been achieved in many installations by installing VSDs." Also: "It is estimated that 75% of pump systems are oversized, many by more than 20%."

## E18: Is heat rejected to cooling water in one place while steam heats a colder stream in another (a heat-integration question)?

Fired at 1 of 2 sites. Asked and quiet at: food.

- **bayer**, U2, HV-112 (`E18@model`): FT-106, HV-108, HV-112, TV-104C, U1, U2

**Data to collect**

- Temperatures and duties of the cooled and the heated streams. How: For each stream: supply and target temperature and duty.
  - bayer [not on drawing]: only a valve (HV-112) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then historian or DCS trend for FT-106 (no historian tag is mapped in this model for these); then site records: heat and material balance
- Whether the duties overlap in time. How: Mark each duty continuous, batch or startup-only.
  - bayer [not on drawing]: site records: operating sequence: are both duties needed at the same time?
- Layout distance and fouling. How: Note pipe run and fouling service.
  - bayer [not on drawing]: a walkdown: distance between the two exchangers; then maintenance records: cleaning history

**How it is decided:** Worth a pinch or exchanger study only when the hot stream's temperature range sits above the cold stream's with a practical approach, both run at the same time for long hours, and they are close enough to connect. Otherwise close it.

**What the source says (S19, S24):** Pinch potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management." No % stated in that section.

## E19: Is the compressed air header pressure higher than the end users need?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, AC-501 (`E19@AC-501`): AC-501, PIC-202, PIC-203, PIC-501

**Data to collect**

- Header pressure profile and the minimum end-use pressure. How: Find the highest pressure any user truly needs.
  - food [not on drawing]: a walkdown: pressure at the farthest and most demanding users

**How it is decided:** Lower the setpoint toward the highest true end-use need plus distribution losses.

**What the source says (S11, S24):** "for every 2 psi decrease in discharge pressure, energy consumption will decrease by approximately 1 percent at full output flow." With 30-50% unregulated usage, "about 1 to 1.6 percent for every 2 psi."

## E22: Does the air compressor lack enough storage for intermittent large users?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, AC-501 (`E22@AC-501`): AC-501

**Data to collect**

- Demand profile. How: Find short high-demand events.
  - food [not on drawing]: a walkdown: data-log compressor load and header pressure for a week

**How it is decided:** Add storage when short peaks force an extra compressor on.

**What the source says (S10, S24):** Storage "may allow such a compressor to be turned off." No % stated.

## E23: Is air compressor heat rejected when it could heat something?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, AC-501 (`E23@AC-501`): AC-501

**Data to collect**

- Load hours and a nearby heat sink. How: List heat users within reach.
  - food [not on drawing]: site records: compressor run hours; then a walkdown: space or water heating needs nearby

**How it is decided:** Worth a look when the compressor runs long hours and a low-temperature heat user is nearby.

**What the source says (S11):** "As much as 80 to 93 percent of the electrical energy" becomes heat; recovery "anywhere from 50 to 90 percent of this".

## H2: Is high-grade (or unknown-grade) steam doing a low-temperature job?

Fired at 1 of 2 sites. Asked and quiet at: food.

- **bayer**, E-2 (`H2@E-2`): E-2, TIC-104, TV-104C, U1

**Data to collect**

- Steam supply pressure and temperature. How: Record supply conditions; saturation temperature follows from pressure.
  - bayer [not on drawing]: a walkdown: pressure gauge and thermometer at the supply; then site records: steam header list
    - For `H2@E-2`: U1 (stream:U1): supplied none; still needed steam_pressure (absent), steam_temperature_C (absent). TV-104C (TV-104C): supplied none; still needed steam_pressure (absent), steam_temperature_C (absent). Remaining across subjects (including additional evidence): steam_pressure, steam_temperature_C.
- Temperature the user actually needs. How: Note setpoint and normal range.
  - bayer [not on drawing]: DCS/PLC configuration: the temperature setpoint
- A lower-grade heat source on site (a lower steam header, exhaust or waste heat) with spare capacity. How: List sources whose temperature exceeds the need with a practical approach.
  - bayer [not on drawing]: site records: site steam balance; then a walkdown: headers and hot streams near this user

**How it is decided:** Worth a change only if a lower-grade source can meet the needed temperature with margin, for the hours the user runs; if the steam is already the lowest grade available, close it.

**What the source says (S19, S6):** Closest source wordings: pinch potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management" (S19, no % stated); for letdown to the lower pressure, S6's turbogenerator condition. No source gives a number for matching steam grade to duty.

## H4: Is heat rejected to cooling water at a temperature another user could use?

Fired at 1 of 2 sites. Asked and quiet at: food.

- **bayer**, E-3 (`H4@E-3`): E-3, HV-112, U2

**Data to collect**

- Cooling water return temperature. How: Record at normal operation; the return temperature is the grade of the heat on offer.
  - bayer [not on drawing]: a walkdown: thermometer on the return
- Temperature of the stream being cooled (in and out). How: Record at normal operation.
  - bayer [not on drawing]: site records: heat and material balance
- Cooler duty. How: Duty = flow x heat capacity x temperature rise.
  - bayer [not on drawing]: the vendor datasheet: exchanger datasheet; then site records: heat and material balance
- A heat user that needs heat below the return temperature. How: Match by temperature, hours and distance.
  - bayer [not on drawing]: site records: list of heating duties with temperatures; then a walkdown: users nearby

**How it is decided:** Worth a study only if the heat leaves hotter than a nearby user needs, for overlapping hours; cooling water returning only a few degrees above ambient closes it.

**What the source says (S19, S11):** Closest source wording (S19, pinch): potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management." No % stated. For air compressors S11 says recovery "anywhere from 50 to 90 percent" of the heat, which applies to compressors only.

## C6: Does a temperature controller write straight to a steam valve with no flow controller underneath (a cascade candidate)?

Fired at 1 of 2 sites. Asked and quiet at: food.

- **bayer**, TV-104C (`C6@TV-104C`): FT-106, TIC-104, TV-104C

**Data to collect**

- Loop behaviour. How: Look for oscillation or slow recovery after steam pressure changes.
  - bayer [not on drawing]: DCS/PLC configuration: controller tuning and output history
- Steam header pressure swings. How: Note how often supply pressure moves.
  - bayer [not on drawing]: site records: steam header pressure trend

**How it is decided:** A flow slave helps when steam supply pressure swings disturb the temperature; a steady header and a well-behaved loop close it.

**What the source says (no source):** No public numeric source found. Report as qualitative only.

## E26: Are relief and vent flows to the flare or atmosphere unmetered?

Fired at 1 of 2 sites. Asked and quiet at: food.

- **bayer**, S8, S9, S11 (`E26@model`): PSV-101, PSV-102, S11, S8, S9

**Data to collect**

- Flare or vent flow and composition. How: Separate continuous (background) flow from relief events.
  - bayer [not on drawing]: a walkdown: ultrasonic flare-gas meter or a temporary vent flow measurement; then site records: relief valve lift records

**How it is decided:** Worth metering when background flow is continuous; relief-only lines that seldom lift close the question.

**What the source says (S19):** Background flaring "can be as much as 50% of all flared gases (Miles, 2001)." In refineries it "will generally be less than 50%." No recovery % stated.

## E27: Is the refrigeration condensing (head) pressure held higher than the weather allows, with no floating head pressure?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, C-201 (`E27@C-201`): C-201, JT-201, K-201, K-202, K-203, PIC-203, PT-203

**Data to collect**

- Head (discharge) pressure and condensing temperature, hourly over a year. How: Convert pressure to saturated condensing temperature with the refrigerant's tables; see whether it falls in cool weather or sits at the setpoint.
  - food [not on drawing]: historian or DCS trend for PT-203 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the head pressure setpoint and its low limit in the refrigeration plant controls
- Ambient wet-bulb temperature (dry-bulb for an air-cooled condenser) at the same times. How: Line it up hour by hour with the condensing temperature.
  - food [not on drawing]: site records: the site weather station, or the nearest public weather station's hourly record
- The lowest head pressure the plant can run at. How: This is the floor a floating setpoint may not go below.
  - food [not on drawing]: DCS/PLC configuration: the minimum needed for hot gas defrost, liquid injection oil cooling and liquid feed to the farthest evaporator; then the vendor datasheet: compressor and expansion valve minimum pressure difference
- Compressor and condenser fan and pump power. How: Floating the head pressure moves load from the compressors to the condenser fans; count both.
  - food [not on drawing]: historian or DCS trend for JT-201 (no historian tag is mapped in this model for these); then a walkdown: power logger on the compressor motors and on the condenser fan and spray pump motors

**How it is decided:** Worth a look when the head pressure sits at a fixed setpoint through cool weather, above both what the condenser could reach and the plant's own minimum. If it already follows the wet-bulb down to that minimum, close it.

**What the source says (S25):** Floating head pressure (S25, p. 62) "allows compressor head pressures to move up or down with variations in ambient wet-bulb temperature, saving energy compared to fixed head pressure operation." Condensing pressure (S25, p. 65): "Lowering the condensing temperature can reduce compressor energy use by around 2% to 3% for every degree Celsius (1.8 degrees Fahrenheit) of temperature reduction (SenterNovem 2003)." Condenser fans (S25, p. 65): "On systems where floating head operation is stable, ASDs can lower condenser fan energy consumption by up to 40% compared to operating a fixed-speed condenser fan in on/off fashion (IRC 2004b)."

## E28: Is each refrigeration suction level held colder than the warmest load on it needs?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, K-201, K-202, K-203 (`E28@model`): CS-201, EV-201, EV-202, JT-201, K-201, K-202, K-203, PT-201, PT-202, TT-205, TT-206

**Data to collect**

- Suction pressure at each suction level, hourly. How: Convert to saturated evaporating temperature; note whether it changes at night, weekends or in winter.
  - food [not on drawing]: historian or DCS trend for PT-201, PT-202 (no historian tag is mapped in this model for these); then DCS/PLC configuration: suction pressure setpoints per compressor or suction level
- The temperature each load actually needs. How: The warmest load on a suction level, less its coil approach, sets the coldest suction that level needs.
  - food [not on drawing]: site records: room and product temperature specifications for each freezer, cold store and chiller, and which suction level serves it; then historian or DCS trend for TT-205, TT-206 (no historian tag is mapped in this model for these)
- Compressor power and run hours per suction level. How: A month or more at normal production.
  - food [not on drawing]: historian or DCS trend for JT-201 (no historian tag is mapped in this model for these); then site records: compressor run hours from the refrigeration plant controls

**How it is decided:** Worth a look when a suction level runs colder than its warmest load needs after the coil approach, or stays fixed when loads ease at night and weekends. Close it when the loads on that level need the present temperature.

**What the source says (S25):** Two-stage systems (S25, p. 63): "a simple way to save energy is to raise the suction pressure and temperature of the low-stage compressor when ambient temperatures decrease. It has been estimated that energy savings of about 8% can be realized in two-stage systems when suction temperatures are raised from -30 °F to -20 °F (ISU 2005)." No figure is given there for single-stage systems.

## E30: Are these evaporators defrosted on a fixed timer rather than when frost is actually there?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, EV-201 (`E30@EV-201`): EV-201, HGV-201, TT-205

**Data to collect**

- Defrost schedule per evaporator. How: List defrosts per day by season.
  - food [not on drawing]: DCS/PLC configuration: defrost initiation (timer or demand), defrosts per day, duration and termination (time or coil temperature) per evaporator
- Frost on the coil when a scheduled defrost starts. How: Note clear, light or heavy frost.
  - food [not on drawing]: a walkdown: look at the coil just before a few scheduled defrosts, in a dry week and a humid week
- Hot gas use and room temperature rise per defrost. How: The heat put in to defrost comes back as refrigeration load afterwards.
  - food [not on drawing]: historian or DCS trend for HGV-201 (no historian tag is mapped in this model for these); then historian or DCS trend for TT-205 (no historian tag is mapped in this model for these)

**How it is decided:** Worth a look when coils are clear at scheduled defrosts, or the count per day is the same in dry weeks as in humid ones. Close it if defrost is already started on demand.

**What the source says (S25):** Demand defrost (S25, p. 66): "Evaporators should be defrosted only when necessary, as opposed to on timed schedules where defrosting occurs regardless of need." "Too frequent defrosts." is listed among control strategies that "may compromise system energy efficiency" (S25, p. 59, citing Pearson 2003). No % stated.

## H5: Is refrigeration condenser heat rejected while a low-grade heating duty nearby is met with fuel or steam?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, K-201, K-202, K-203, C-201 (`H5@model`): C-201, JT-201, K-201, K-202, K-203, PT-203, TT-202, W2, WH-401

**Data to collect**

- Discharge and condensing temperatures. How: Discharge superheat is the hotter, smaller part; condensing heat is larger but only at the condensing temperature.
  - food [not on drawing]: historian or DCS trend for PT-203, TT-202 (no historian tag is mapped in this model for these); then DCS/PLC configuration: discharge temperature and head pressure readings in the refrigeration plant controls
- Compressor power and run hours. How: Heat rejected is about the compressor power plus the refrigeration load at the same time.
  - food [not on drawing]: historian or DCS trend for JT-201 (no historian tag is mapped in this model for these); then site records: compressor run hours from the refrigeration plant controls
- The low-grade duty: temperature needed, load and hours. How: Match by temperature, hours and distance.
  - food [not on drawing]: site records: temperatures and loads of the hot water, CIP, wash water, floor heating and space heating users, by hour
- Effect on head pressure. How: Recovery that raises the head pressure in cool weather costs compressor power (see E27); count it.
  - food [not on drawing]: the vendor datasheet: whether a heat recovery exchanger would need a higher condensing pressure than now

**How it is decided:** Worth a study when the refrigeration plant runs at the same times as a duty that needs heat below the discharge or condensing temperature, and recovery does not force the head pressure up. Close it if the duties do not overlap or recovery would need a higher condensing pressure all year.

**What the source says (S25):** S25 (p. 64), refrigeration compressors: "Where economically feasible, rejected heat can be recovered from compressors and used in other facility applications, such as space heating or water heating." No % stated there for refrigeration (the air compressor heat recovery figures quoted under E23 do not apply).

## C12: Is power to these refrigeration compressors measured, so the plant's kW against load can be tracked?

Fired at 1 of 2 sites. Asked and quiet at: bayer.

- **food**, K-202, K-203 (`C12@model`): K-202, K-203, PT-202

**Data to collect**

- Compressor power. How: A representative period at known production.
  - food [not on drawing]: a walkdown: the drive's or motor protection relay's kW reading, or a temporary power logger, per compressor; then utility bills or the site energy report: site interval meter data to apportion
- Suction and discharge pressures logged at the same times. How: Logged together with power, these show how the plant runs.
  - food [not on drawing]: historian or DCS trend for PT-202 (no historian tag is mapped in this model for these); then DCS/PLC configuration: suction and discharge pressure per compressor in the refrigeration plant controls
- What to normalise against. How: kW per unit of product or per unit of refrigeration.
  - food [not on drawing]: site records: production throughput or freezer and cold store loads by day

**How it is decided:** Meter, or log from the drives, where the refrigeration plant is large enough that kW against load would change decisions; a reading nobody reviews saves nothing.

**What the source says (S25):** S25 (p. 58): "A basic monitoring system should include ongoing measurement and logging of compressor suction and discharge pressures; a drop in suction pressure typically indicates a refrigerant leak, while a rise in discharge pressure can indicate a blocked condenser (EEBPP 2000a)." "In a review of energy efficiency opportunities for refrigeration systems in wineries, the energy savings associated with the installation of monitoring systems were estimated at 3% (Galitsky et al. 2005b)."

## Asked at every site, fired at none

Not a clean bill of health: the models may not show what these questions look for. E2, E3, E4, E5, E6, E7, E8, E9, E10, E12, E13, E14, E15, E16, E17, E20, E21, E24, H1, H3, C4, C5, C7, C10, C8, E25.

## Sources cited above

- S1: DOE AMO Steam Tip Sheet #2, Insulate Steam Distribution and Condensate Return Lines (DOE/GO-102012-3404, Jan 2012). https://www.energy.gov/sites/default/files/2014/05/f16/steam2_insulate.pdf (license: Public domain (US federal))
- S6: Steam Tip #20, Replace Pressure-Reducing Valves with Backpressure Turbogenerators (DOE/GO-102012-3409). https://www.energy.gov/sites/prod/files/2014/05/f16/steam20_turbogenerators.pdf (license: Public domain)
- S10: Compressed Air Tip #9, Compressed Air Storage Strategies (DOE/GO-102004-1965). https://www.energy.gov/sites/prod/files/2014/05/f16/compressed_air9.pdf (license: Public domain)
- S11: Improving Compressed Air System Performance: A Sourcebook for Industry, 3rd ed. (DOE + Compressed Air Challenge). https://www.energy.gov/sites/default/files/2016/03/f30/Improving%20Compressed%20Air%20Sourcebook%20version%203.pdf (license: DOE publication co-produced with CAC; mostly federal, reuse of CAC content unclear)
- S13: Improving Pumping System Performance: A Sourcebook for Industry, 2nd ed. (DOE + Hydraulic Institute; DOE/GO-102006-2079). https://www.energy.gov/sites/prod/files/2014/05/f16/pump.pdf (license: Federal, co-developed with HI: unclear for HI content)
- S15: Variable Speed Pumping: A Guide to Successful Applications, Executive Summary (DOE ITP with Europump/HI, DOE/GO-102004-1913, May 2004). https://www.energy.gov/sites/prod/files/2014/05/f16/variable_speed_pumping.pdf (license: Unclear (joint with Europump/HI))
- S19: Worrell & Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for Petroleum Refineries: An ENERGY STAR Guide (LBNL-56183, Feb 2005). https://www.osti.gov/servlets/purl/862119 (license: DOE-lab (contractor) report: unclear, but freely citable. Its tables quote older secondary sources, so figures are cited as reported in LBNL-56183)
- S22: FEMP Metering Best Practices: A Guide to Achieving Utility Resource Efficiency, Release 3.0 (PNNL-23892, Mar 2015). https://www.wbdg.org/FFC/DOE/NLCRIT/mbpg_2015.pdf (license: Contractor-prepared federal guide: unclear. Its savings figures are buildings-focused)
- S24: DOE IAC/ITAC database: browse pages, download, schema document. https://itac.university/index/arc/2. (license: No license or terms stated: unclear)
- S25: Brush, Masanet and Worrell, Energy Efficiency Improvement and Cost Saving Opportunities for the Dairy Processing Industry: An ENERGY STAR Guide for Energy and Plant Managers (LBNL-6261E, Oct 2011). https://www.osti.gov/servlets/purl/1171534 (license: DOE-lab report sponsored by US EPA: unclear, freely citable; its figures from older sources are quoted as reported there)
- S26: Masanet, Worrell, Graus and Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for the Fruit and Vegetable Processing Industry: An ENERGY STAR Guide for Energy and Plant Managers (LBNL-59289-Revision, Mar 2008). https://eta-publications.lbl.gov/sites/default/files/lbnl-59289-rev.pdf (license: DOE-lab report sponsored by US EPA: unclear, freely citable; its figures from older sources are quoted as reported there)
- S27: DOE Industrial Technologies Program, Process Heating Tip Sheet #2, Check Burner Air to Fuel Ratios (Nov 2007). https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/42110.pdf (license: Public domain (US federal))
- S28: DOE Industrial Technologies Program, Process Heating Tip Sheet #10, Using Waste Heat for External Processes (DOE/GO-102006-2225, Jan 2006). https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/38853.pdf (license: Public domain (US federal))
