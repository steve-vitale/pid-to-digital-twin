# Opportunity screen: ILLUSTRATIVE food plant section (synthetic): ammonia refrigeration, dryer, oven, fryer and utilities

Model: `plant_model.json`. Questions: `data/questions.json`.

## Rejected model items excluded

These recorded rejections are excluded from triggers, evidence and relationships. The source model and its history are retained. Non-rejected children remain eligible without a rejected owner, parent or stream; no replacement is inferred. Other items remain unverified unless separately reviewed. Recorded names and decisions do not authenticate a reviewer or establish plant truth.

- `units[HX-303]`: rejected; recorded by Illustrative software control, not a real review, on 2026-10-30. ILLUSTRATIVE software control: pretend this heat-recovery unit was a false positive.
- `instruments[JT-201]`: rejected; recorded by Illustrative software control, not a real review, on 2026-10-30. ILLUSTRATIVE software control: pretend this power meter was a false positive.
- `final_elements[SC-203]`: rejected; recorded by Illustrative software control, not a real review, on 2026-10-30. ILLUSTRATIVE software control: pretend this speed drive was a false positive.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Energy | 6 |
| Heat grade (high-grade heat for low-grade duty) | 3 |
| Metering | 1 |
| Controls and automation | 0 |
| Emissions | 0 |
| Safety questions to verify | 0 |

## Energy

### E29: Does this refrigeration compressor carry part load on its slide valve (or hot gas bypass) with no speed control?

**About:** K-201  

**Evidence on the drawing / model**

- equipment K-201 reads "K-201 Ammonia (R-717) screw compressor, low stage (booster)" (`units[K-201]`)
- Checked, none found: no variable speed drive or speed controller drawn on this compressor (`applies_when.without`)

**Data to collect**

- Slide valve (capacity) position over normal operation [not on drawing]. Where: DCS/PLC configuration: slide valve position or percent capacity per compressor from the refrigeration plant controls, a month or more. How: Hours spent below full load, by load band.
- Compressor power and run hours [not on drawing]. Where: a walkdown: power logger on the compressor motor across a normal week. How: Power at each load band, so part-load efficiency can be seen.
- How the compressors are sequenced [not on drawing]. Where: DCS/PLC configuration: which compressor trims, and the order and pressures at which they load and unload. How: Note whether more than one machine trims at the same time.

**How it is decided:** Worth a look when screws spend long hours part-loaded on the slide valve while another could be off, or when no machine on a suction level has speed control to trim. Close it if each runs near full load or a sequencer already keeps one machine trimming.

**What the source says (S25):** Among control strategies that "may compromise system energy efficiency" (S25, p. 59, citing Pearson 2003): "Slide valve unloading of oversized screw compressors." and "Hot gas bypass of compressors." Speed control (S25, p. 63): "ASDs used on compressors below a part-load ratio of about 95% will deliver performance equal to a fixed speed compressor but with lower electricity requirements. However, at near full (i.e., 100%) load, ASDs are approximately 3% less efficient than fixed speed drives".

**Limits:** A drive or sequencing change goes through the compressor vendor (minimum speed, oil management, vibration). Fires only where the equipment's own name, type or service names the refrigerant (ammonia, NH3, R-717, a refrigerant number) or says refrigeration; an air compressor, a process recycle compressor, a process condenser on cooling water or a power-plant air-cooled condenser does not.

### E29: Does this refrigeration compressor carry part load on its slide valve (or hot gas bypass) with no speed control?

**About:** K-202  

**Evidence on the drawing / model**

- equipment K-202 reads "K-202 Ammonia (R-717) screw compressor, high stage" (`units[K-202]`)
- Capacity control: instrument ZT-202 reads "ZT-202 Slide valve (capacity) position" at K-202 (`instruments[ZT-202]`)
- Checked, none found: no variable speed drive or speed controller drawn on this compressor (`applies_when.without`)

**Data to collect**

- Slide valve (capacity) position over normal operation [not on drawing]. Where: historian or DCS trend for ZT-202 (no historian tag is mapped in this model for these); then DCS/PLC configuration: slide valve position or percent capacity per compressor from the refrigeration plant controls, a month or more. How: Hours spent below full load, by load band.
- Compressor power and run hours [not on drawing]. Where: a walkdown: power logger on the compressor motor across a normal week. How: Power at each load band, so part-load efficiency can be seen.
- How the compressors are sequenced [not on drawing]. Where: DCS/PLC configuration: which compressor trims, and the order and pressures at which they load and unload. How: Note whether more than one machine trims at the same time.

**How it is decided:** Worth a look when screws spend long hours part-loaded on the slide valve while another could be off, or when no machine on a suction level has speed control to trim. Close it if each runs near full load or a sequencer already keeps one machine trimming.

**What the source says (S25):** Among control strategies that "may compromise system energy efficiency" (S25, p. 59, citing Pearson 2003): "Slide valve unloading of oversized screw compressors." and "Hot gas bypass of compressors." Speed control (S25, p. 63): "ASDs used on compressors below a part-load ratio of about 95% will deliver performance equal to a fixed speed compressor but with lower electricity requirements. However, at near full (i.e., 100%) load, ASDs are approximately 3% less efficient than fixed speed drives".

**Limits:** A drive or sequencing change goes through the compressor vendor (minimum speed, oil management, vibration). Fires only where the equipment's own name, type or service names the refrigerant (ammonia, NH3, R-717, a refrigerant number) or says refrigeration; an air compressor, a process recycle compressor, a process condenser on cooling water or a power-plant air-cooled condenser does not.

### E29: Does this refrigeration compressor carry part load on its slide valve (or hot gas bypass) with no speed control?

**About:** K-203  

**Evidence on the drawing / model**

- equipment K-203 reads "K-203 Ammonia (R-717) screw compressor, high stage (trim)" (`units[K-203]`)
- Checked, none found: no variable speed drive or speed controller drawn on this compressor (`applies_when.without`)

**Data to collect**

- Slide valve (capacity) position over normal operation [not on drawing]. Where: DCS/PLC configuration: slide valve position or percent capacity per compressor from the refrigeration plant controls, a month or more. How: Hours spent below full load, by load band.
- Compressor power and run hours [not on drawing]. Where: a walkdown: power logger on the compressor motor across a normal week. How: Power at each load band, so part-load efficiency can be seen.
- How the compressors are sequenced [not on drawing]. Where: DCS/PLC configuration: which compressor trims, and the order and pressures at which they load and unload. How: Note whether more than one machine trims at the same time.

**How it is decided:** Worth a look when screws spend long hours part-loaded on the slide valve while another could be off, or when no machine on a suction level has speed control to trim. Close it if each runs near full load or a sequencer already keeps one machine trimming.

**What the source says (S25):** Among control strategies that "may compromise system energy efficiency" (S25, p. 59, citing Pearson 2003): "Slide valve unloading of oversized screw compressors." and "Hot gas bypass of compressors." Speed control (S25, p. 63): "ASDs used on compressors below a part-load ratio of about 95% will deliver performance equal to a fixed speed compressor but with lower electricity requirements. However, at near full (i.e., 100%) load, ASDs are approximately 3% less efficient than fixed speed drives".

**Limits:** A drive or sequencing change goes through the compressor vendor (minimum speed, oil management, vibration). Fires only where the equipment's own name, type or service names the refrigerant (ammonia, NH3, R-717, a refrigerant number) or says refrigeration; an air compressor, a process recycle compressor, a process condenser on cooling water or a power-plant air-cooled condenser does not.

### E31: Does this oven, dryer or fryer send its hot exhaust to atmosphere with no heat recovery on it?

**About:** D-301  

**Evidence on the drawing / model**

- equipment D-301 reads "D-301 Gas-fired product dryer (continuous belt)" (`units[D-301]`)
- Exhaust: stream S1 (asset stream:S1) reads "Dryer exhaust air to atmosphere" (`streams[S1]`)
- Exhaust: instrument TT-304 reads "TT-304 Dryer exhaust air temperature" at D-301 (`instruments[TT-304]`)
- Fuel or heat supply: stream U1 (asset stream:U1) reads "Natural gas to the dryer burner" at D-301 (`streams[U1]`)
- Fuel or heat supply: instrument FT-301 reads "FT-301 Dryer burner natural gas flow" at D-301 (`instruments[FT-301]`)
- Fuel or heat supply: valve TV-301 reads "TV-301 Dryer burner natural gas control valve" at D-301 (`final_elements[TV-301]`)
- Checked, none found: no heat recovery exchanger, recuperator, run-around coil or exhaust recirculation on this unit or on a stream drawn from it (`applies_when.without`)

**Data to collect**

- Exhaust temperature and flow [not on drawing]. Where: historian or DCS trend for TT-304 (no historian tag is mapped in this model for these); then a walkdown: thermometer and a pitot or anemometer traverse in the exhaust duct, at normal production. How: Record both at normal production; heat on offer = mass flow x specific heat x (exhaust temperature minus the temperature it could be cooled to).
- Exhaust moisture and contaminants [not on drawing]. Where: a walkdown: humidity or dew point probe in the exhaust; note fat, flour, sugar or product dust; then maintenance records: duct and stack cleaning history. How: Moist exhaust carries latent heat but condenses; fat and dust foul exchangers unless filtered or washed.
- Fuel or heat input and operating hours [not on drawing]. Where: historian or DCS trend for FT-301 (no historian tag is mapped in this model for these); then utility bills or the site energy report: gas sub-meter readings for this line; then site records: production schedule: hours per week the line runs. How: A month of input at a known production rate.
- Where the heat could go in the unit itself [not on drawing]. Where: site records: inlet (drying or combustion) air temperature and flow; then a walkdown: room next to the unit for ductwork or a run-around coil. How: Preheating the unit's own inlet air comes first; H6 asks about users elsewhere.

**How it is decided:** Worth a study when the exhaust leaves hot, the line runs long hours, and the exhaust is clean enough or can be filtered or washed. Close it for short or intermittent runs, or when there is no room for the ductwork.

**What the source says (S26, S25):** Dryers (S26, p. 104): "A simple form of heat recovery in retrofit applications is to utilize the exhaust air of a dryer to preheat the inlet air stream, thereby saving energy." Spray dryers (S25, p. 90): "It is estimated that up to 30% of the heat from the dryer exhaust can be recovered." Fryers (S26, p. 107): "Conditioning of the exhaust gas is required, however, to remove fats and to reduce fouling of the heat exchange system." No source in this set gives a figure for ovens.

**Limits:** S26 (p. 104) notes that recirculating saturated exhaust can raise the inlet humidity and cut drying capacity. A heat recovery item on the unit, or at the other end of a stream drawn from it, quiets the question; recovery drawn elsewhere does not. Ovens and dryers that drive off solvents, or carry combustible dust, need a safety review before any exhaust change.

### E31: Does this oven, dryer or fryer send its hot exhaust to atmosphere with no heat recovery on it?

**About:** O-302  

**Evidence on the drawing / model**

- equipment O-302 reads "O-302 Gas-fired tunnel oven" (`units[O-302]`)
- Exhaust: stream S2 (asset stream:S2) reads "Oven exhaust (flue gas and vapour) to stack" (`streams[S2]`)
- Exhaust: instrument TT-305 reads "TT-305 Oven exhaust temperature" at O-302 (`instruments[TT-305]`)
- Exhaust: instrument AT-302 reads "AT-302 Oven flue O2 analyser" at O-302 (`instruments[AT-302]`)
- Fuel or heat supply: stream U2 (asset stream:U2) reads "Natural gas to the oven burners" at O-302 (`streams[U2]`)
- Fuel or heat supply: valve TV-302 reads "TV-302 Oven burner natural gas control valve" at O-302 (`final_elements[TV-302]`)
- Checked, none found: no heat recovery exchanger, recuperator, run-around coil or exhaust recirculation on this unit or on a stream drawn from it (`applies_when.without`)

**Data to collect**

- Exhaust temperature and flow [not on drawing]. Where: historian or DCS trend for TT-305 (no historian tag is mapped in this model for these); then a walkdown: thermometer and a pitot or anemometer traverse in the exhaust duct, at normal production. How: Record both at normal production; heat on offer = mass flow x specific heat x (exhaust temperature minus the temperature it could be cooled to).
- Exhaust moisture and contaminants [not on drawing]. Where: a walkdown: humidity or dew point probe in the exhaust; note fat, flour, sugar or product dust; then maintenance records: duct and stack cleaning history. How: Moist exhaust carries latent heat but condenses; fat and dust foul exchangers unless filtered or washed.
- Fuel or heat input and operating hours [not on drawing]. Where: only a valve (TV-302) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then utility bills or the site energy report: gas sub-meter readings for this line; then site records: production schedule: hours per week the line runs. How: A month of input at a known production rate.
- Where the heat could go in the unit itself [not on drawing]. Where: site records: inlet (drying or combustion) air temperature and flow; then a walkdown: room next to the unit for ductwork or a run-around coil. How: Preheating the unit's own inlet air comes first; H6 asks about users elsewhere.

**How it is decided:** Worth a study when the exhaust leaves hot, the line runs long hours, and the exhaust is clean enough or can be filtered or washed. Close it for short or intermittent runs, or when there is no room for the ductwork.

**What the source says (S26, S25):** Dryers (S26, p. 104): "A simple form of heat recovery in retrofit applications is to utilize the exhaust air of a dryer to preheat the inlet air stream, thereby saving energy." Spray dryers (S25, p. 90): "It is estimated that up to 30% of the heat from the dryer exhaust can be recovered." Fryers (S26, p. 107): "Conditioning of the exhaust gas is required, however, to remove fats and to reduce fouling of the heat exchange system." No source in this set gives a figure for ovens.

**Limits:** S26 (p. 104) notes that recirculating saturated exhaust can raise the inlet humidity and cut drying capacity. A heat recovery item on the unit, or at the other end of a stream drawn from it, quiets the question; recovery drawn elsewhere does not. Ovens and dryers that drive off solvents, or carry combustible dust, need a safety review before any exhaust change.

### E31: Does this oven, dryer or fryer send its hot exhaust to atmosphere with no heat recovery on it?

**About:** F-303  

**Evidence on the drawing / model**

- equipment F-303 reads "F-303 Gas-fired continuous fryer" (`units[F-303]`)
- Exhaust: stream S3 (asset stream:S3) reads "Fryer exhaust vapour" (`streams[S3]`)
- Fuel or heat supply: stream U3 (asset stream:U3) reads "Natural gas to the fryer burner" at F-303 (`streams[U3]`)
- Fuel or heat supply: valve TV-303 reads "TV-303 Fryer burner natural gas control valve" at F-303 (`final_elements[TV-303]`)
- Checked, none found: no heat recovery exchanger, recuperator, run-around coil or exhaust recirculation on this unit or on a stream drawn from it (`applies_when.without`)

**Data to collect**

- Exhaust temperature and flow [not on drawing]. Where: a walkdown: thermometer and a pitot or anemometer traverse in the exhaust duct, at normal production. How: Record both at normal production; heat on offer = mass flow x specific heat x (exhaust temperature minus the temperature it could be cooled to).
- Exhaust moisture and contaminants [not on drawing]. Where: a walkdown: humidity or dew point probe in the exhaust; note fat, flour, sugar or product dust; then maintenance records: duct and stack cleaning history. How: Moist exhaust carries latent heat but condenses; fat and dust foul exchangers unless filtered or washed.
- Fuel or heat input and operating hours [not on drawing]. Where: only a valve (TV-303) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then utility bills or the site energy report: gas sub-meter readings for this line; then site records: production schedule: hours per week the line runs. How: A month of input at a known production rate.
- Where the heat could go in the unit itself [not on drawing]. Where: site records: inlet (drying or combustion) air temperature and flow; then a walkdown: room next to the unit for ductwork or a run-around coil. How: Preheating the unit's own inlet air comes first; H6 asks about users elsewhere.

**How it is decided:** Worth a study when the exhaust leaves hot, the line runs long hours, and the exhaust is clean enough or can be filtered or washed. Close it for short or intermittent runs, or when there is no room for the ductwork.

**What the source says (S26, S25):** Dryers (S26, p. 104): "A simple form of heat recovery in retrofit applications is to utilize the exhaust air of a dryer to preheat the inlet air stream, thereby saving energy." Spray dryers (S25, p. 90): "It is estimated that up to 30% of the heat from the dryer exhaust can be recovered." Fryers (S26, p. 107): "Conditioning of the exhaust gas is required, however, to remove fats and to reduce fouling of the heat exchange system." No source in this set gives a figure for ovens.

**Limits:** S26 (p. 104) notes that recirculating saturated exhaust can raise the inlet humidity and cut drying capacity. A heat recovery item on the unit, or at the other end of a stream drawn from it, quiets the question; recovery drawn elsewhere does not. Ovens and dryers that drive off solvents, or carry combustible dust, need a safety review before any exhaust change.

## Heat grade (high-grade heat for low-grade duty)

### H6: Could this oven's, dryer's or fryer's exhaust heat serve a low-grade heating duty elsewhere (hot water, CIP, space heating)?

**About:** D-301  

**Evidence on the drawing / model**

- equipment D-301 reads "D-301 Gas-fired product dryer (continuous belt)" (`units[D-301]`)
- Low-grade heating duty: equipment WH-401 reads "WH-401 Gas-fired water heater, CIP and wash hot water" (`units[WH-401]`)
- Low-grade heating duty: stream W2 (asset stream:W2) reads "CIP and wash hot water supply" (`streams[W2]`)
- Exhaust: stream S1 (asset stream:S1) reads "Dryer exhaust air to atmosphere" (`streams[S1]`)
- Exhaust: instrument TT-304 reads "TT-304 Dryer exhaust air temperature" at D-301 (`instruments[TT-304]`)
- Checked, none found: no heat recovery on this unit or on a stream drawn from it (`applies_when.without`)

**Data to collect**

- Exhaust temperature, flow and hours [not on drawing]. Where: historian or DCS trend for TT-304 (no historian tag is mapped in this model for these); then a walkdown: thermometer and a pitot or anemometer traverse in the exhaust duct; then site records: production schedule. How: At normal production.
- The low-grade duty: temperature needed, load and hours [not on drawing]. Where: site records: hot water, CIP, wash water and space heating loads by hour. How: Match by temperature, hours and distance.
- Distance and exhaust cleanliness [not on drawing]. Where: a walkdown: duct or pipe run from the stack to the user; fat, dust or product carry-over in the exhaust. How: The closer and cleaner, the better.

**How it is decided:** Worth a study when the exhaust is well above the temperature the duty needs, the two run at the same times, and they are close enough to connect. Otherwise close it.

**What the source says (S28, S26):** S28 (p. 1): "many companies install heat exchangers on the exhaust stacks of furnaces and ovens to produce hot water or to generate hot air for space heating." The same sheet: "The temperature difference between the primary and secondary process should be high enough (at least 200°F), and there should be a sufficient amount of usable waste heat." Fryers (S26, p. 107): "Heat can be recovered indirectly from a fryer's fat-laden exhaust gases via a heat exchange system and used for pre-heating air and water for use in other facility processes." No % stated.

**Limits:** Overlaps E31, which asks about the unit's own inlet air first. The with-clause finds any low-grade duty in the model, not one next to the unit.

### H6: Could this oven's, dryer's or fryer's exhaust heat serve a low-grade heating duty elsewhere (hot water, CIP, space heating)?

**About:** O-302  

**Evidence on the drawing / model**

- equipment O-302 reads "O-302 Gas-fired tunnel oven" (`units[O-302]`)
- Low-grade heating duty: equipment WH-401 reads "WH-401 Gas-fired water heater, CIP and wash hot water" (`units[WH-401]`)
- Low-grade heating duty: stream W2 (asset stream:W2) reads "CIP and wash hot water supply" (`streams[W2]`)
- Exhaust: stream S2 (asset stream:S2) reads "Oven exhaust (flue gas and vapour) to stack" (`streams[S2]`)
- Exhaust: instrument TT-305 reads "TT-305 Oven exhaust temperature" at O-302 (`instruments[TT-305]`)
- Exhaust: instrument AT-302 reads "AT-302 Oven flue O2 analyser" at O-302 (`instruments[AT-302]`)
- Checked, none found: no heat recovery on this unit or on a stream drawn from it (`applies_when.without`)

**Data to collect**

- Exhaust temperature, flow and hours [not on drawing]. Where: historian or DCS trend for TT-305 (no historian tag is mapped in this model for these); then a walkdown: thermometer and a pitot or anemometer traverse in the exhaust duct; then site records: production schedule. How: At normal production.
- The low-grade duty: temperature needed, load and hours [not on drawing]. Where: site records: hot water, CIP, wash water and space heating loads by hour. How: Match by temperature, hours and distance.
- Distance and exhaust cleanliness [not on drawing]. Where: a walkdown: duct or pipe run from the stack to the user; fat, dust or product carry-over in the exhaust. How: The closer and cleaner, the better.

**How it is decided:** Worth a study when the exhaust is well above the temperature the duty needs, the two run at the same times, and they are close enough to connect. Otherwise close it.

**What the source says (S28, S26):** S28 (p. 1): "many companies install heat exchangers on the exhaust stacks of furnaces and ovens to produce hot water or to generate hot air for space heating." The same sheet: "The temperature difference between the primary and secondary process should be high enough (at least 200°F), and there should be a sufficient amount of usable waste heat." Fryers (S26, p. 107): "Heat can be recovered indirectly from a fryer's fat-laden exhaust gases via a heat exchange system and used for pre-heating air and water for use in other facility processes." No % stated.

**Limits:** Overlaps E31, which asks about the unit's own inlet air first. The with-clause finds any low-grade duty in the model, not one next to the unit.

### H6: Could this oven's, dryer's or fryer's exhaust heat serve a low-grade heating duty elsewhere (hot water, CIP, space heating)?

**About:** F-303  

**Evidence on the drawing / model**

- equipment F-303 reads "F-303 Gas-fired continuous fryer" (`units[F-303]`)
- Low-grade heating duty: equipment WH-401 reads "WH-401 Gas-fired water heater, CIP and wash hot water" (`units[WH-401]`)
- Low-grade heating duty: stream W2 (asset stream:W2) reads "CIP and wash hot water supply" (`streams[W2]`)
- Exhaust: stream S3 (asset stream:S3) reads "Fryer exhaust vapour" (`streams[S3]`)
- Checked, none found: no heat recovery on this unit or on a stream drawn from it (`applies_when.without`)

**Data to collect**

- Exhaust temperature, flow and hours [not on drawing]. Where: a walkdown: thermometer and a pitot or anemometer traverse in the exhaust duct; then site records: production schedule. How: At normal production.
- The low-grade duty: temperature needed, load and hours [not on drawing]. Where: site records: hot water, CIP, wash water and space heating loads by hour. How: Match by temperature, hours and distance.
- Distance and exhaust cleanliness [not on drawing]. Where: a walkdown: duct or pipe run from the stack to the user; fat, dust or product carry-over in the exhaust. How: The closer and cleaner, the better.

**How it is decided:** Worth a study when the exhaust is well above the temperature the duty needs, the two run at the same times, and they are close enough to connect. Otherwise close it.

**What the source says (S28, S26):** S28 (p. 1): "many companies install heat exchangers on the exhaust stacks of furnaces and ovens to produce hot water or to generate hot air for space heating." The same sheet: "The temperature difference between the primary and secondary process should be high enough (at least 200°F), and there should be a sufficient amount of usable waste heat." Fryers (S26, p. 107): "Heat can be recovered indirectly from a fryer's fat-laden exhaust gases via a heat exchange system and used for pre-heating air and water for use in other facility processes." No % stated.

**Limits:** Overlaps E31, which asks about the unit's own inlet air first. The with-clause finds any low-grade duty in the model, not one next to the unit.

## Metering

### C12: Is power to these refrigeration compressors measured, so the plant's kW against load can be tracked?

**About:** K-201, K-202, K-203  

**Evidence on the drawing / model**

- equipment K-201 reads "K-201 Ammonia (R-717) screw compressor, low stage (booster)" (`units[K-201]`)
- equipment K-202 reads "K-202 Ammonia (R-717) screw compressor, high stage" (`units[K-202]`)
- equipment K-203 reads "K-203 Ammonia (R-717) screw compressor, high stage (trim)" (`units[K-203]`)
- Suction or discharge pressure: instrument PT-201 reads "PT-201 Low-stage suction pressure" at K-201 (`instruments[PT-201]`)
- Suction or discharge pressure: instrument PT-202 reads "PT-202 High-stage suction pressure" at K-202 (`instruments[PT-202]`)
- Checked, none found: no power, current or energy measurement drawn on these compressors (`applies_when.without`)

**Data to collect**

- Compressor power [not on drawing]. Where: a walkdown: the drive's or motor protection relay's kW reading, or a temporary power logger, per compressor; then utility bills or the site energy report: site interval meter data to apportion. How: A representative period at known production.
- Suction and discharge pressures logged at the same times [not on drawing]. Where: historian or DCS trend for PT-201, PT-202 (no historian tag is mapped in this model for these); then DCS/PLC configuration: suction and discharge pressure per compressor in the refrigeration plant controls. How: Logged together with power, these show how the plant runs.
- What to normalise against [not on drawing]. Where: site records: production throughput or freezer and cold store loads by day. How: kW per unit of product or per unit of refrigeration.

**How it is decided:** Meter, or log from the drives, where the refrigeration plant is large enough that kW against load would change decisions; a reading nobody reviews saves nothing.

**What the source says (S25):** S25 (p. 58): "A basic monitoring system should include ongoing measurement and logging of compressor suction and discharge pressures; a drop in suction pressure typically indicates a refrigerant leak, while a rise in discharge pressure can indicate a blocked condenser (EEBPP 2000a)." "In a review of energy efficiency opportunities for refrigeration systems in wineries, the energy savings associated with the installation of monitoring systems were estimated at 3% (Galitsky et al. 2005b)."

**Limits:** The 3% is one review of winery refrigeration, as reported in S25. Fires only where the equipment's own name, type or service names the refrigerant (ammonia, NH3, R-717, a refrigerant number) or says refrigeration; an air compressor, a process recycle compressor, a process condenser on cooling water or a power-plant air-cooled condenser does not.

## Sources cited above

- S25: Brush, Masanet and Worrell, Energy Efficiency Improvement and Cost Saving Opportunities for the Dairy Processing Industry: An ENERGY STAR Guide for Energy and Plant Managers (LBNL-6261E, Oct 2011). https://www.osti.gov/servlets/purl/1171534 (license: DOE-lab report sponsored by US EPA: unclear, freely citable; its figures from older sources are quoted as reported there)
- S26: Masanet, Worrell, Graus and Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for the Fruit and Vegetable Processing Industry: An ENERGY STAR Guide for Energy and Plant Managers (LBNL-59289-Revision, Mar 2008). https://eta-publications.lbl.gov/sites/default/files/lbnl-59289-rev.pdf (license: DOE-lab report sponsored by US EPA: unclear, freely citable; its figures from older sources are quoted as reported there)
- S28: DOE Industrial Technologies Program, Process Heating Tip Sheet #10, Using Waste Heat for External Processes (DOE/GO-102006-2225, Jan 2006). https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/38853.pdf (license: Public domain (US federal))
