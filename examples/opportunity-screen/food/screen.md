# Opportunity screen: ILLUSTRATIVE food plant section (synthetic): ammonia refrigeration, dryer, oven, fryer and utilities

Model: `examples/opportunity-screen/food_plant_model.json`. Questions: `data/questions.json`.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Energy | 12 |
| Heat grade (high-grade heat for low-grade duty) | 3 |
| Metering | 4 |
| Controls and automation | 4 |
| Emissions | 0 |
| Safety questions to verify | 1 |

## Energy

### E19: Is the compressed air header pressure higher than the end users need?

**About:** AC-501  

**Evidence on the drawing / model**

- equipment AC-501 reads "AC-501 Instrument air compressor" (`units[AC-501]`)
- Pressure control or regulator: controller PIC-202 reads "PIC-202 High-stage suction pressure control, loads and unloads K-202 and K-203" at K-202 (`controllers[PIC-202]`)
- Pressure control or regulator: controller PIC-203 reads "PIC-203 Head pressure control at a fixed setpoint, on the condenser fans" at C-201 (`controllers[PIC-203]`)
- Pressure control or regulator: controller PIC-501 reads "PIC-501 Instrument air header pressure control" at AC-501 (`controllers[PIC-501]`)

**Data to collect**

- Header pressure profile and the minimum end-use pressure [not on drawing]. Where: a walkdown: pressure at the farthest and most demanding users. How: Find the highest pressure any user truly needs.

**How it is decided:** Lower the setpoint toward the highest true end-use need plus distribution losses.

**What the source says (S11, S24):** "for every 2 psi decrease in discharge pressure, energy consumption will decrease by approximately 1 percent at full output flow." With 30-50% unregulated usage, "about 1 to 1.6 percent for every 2 psi."
IAC/ITAC recommendation code: 2.4231 (IAC/ITAC browse page: 6,522 recommendations, 0.5 yr average payback, 51.6% implemented; average dollar figure omitted).

**Limits:** IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E22: Does the air compressor lack enough storage for intermittent large users?

**About:** AC-501  

**Evidence on the drawing / model**

- equipment AC-501 reads "AC-501 Instrument air compressor" (`units[AC-501]`)
- Checked, none found: no receiver or air storage anywhere in the model (`applies_when.without`)

**Data to collect**

- Demand profile [not on drawing]. Where: a walkdown: data-log compressor load and header pressure for a week. How: Find short high-demand events.

**How it is decided:** Add storage when short peaks force an extra compressor on.

**What the source says (S10, S24):** Storage "may allow such a compressor to be turned off." No % stated.
IAC/ITAC recommendation code: 2.422x (category only) (IAC/ITAC browse page: 8,589 recommendations, 1.2 yr average payback, 46.5% implemented; average dollar figure omitted).

**Limits:** IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E23: Is air compressor heat rejected when it could heat something?

**About:** AC-501  

**Evidence on the drawing / model**

- equipment AC-501 reads "AC-501 Instrument air compressor" (`units[AC-501]`)

**Data to collect**

- Load hours and a nearby heat sink [not on drawing]. Where: site records: compressor run hours; then a walkdown: space or water heating needs nearby. How: List heat users within reach.

**How it is decided:** Worth a look when the compressor runs long hours and a low-temperature heat user is nearby.

**What the source says (S11):** "As much as 80 to 93 percent of the electrical energy" becomes heat; recovery "anywhere from 50 to 90 percent of this".
IAC/ITAC recommendation code: 2.243x (by description).

### E27: Is the refrigeration condensing (head) pressure held higher than the weather allows, with no floating head pressure?

**About:** C-201  

**Evidence on the drawing / model**

- equipment C-201 reads "C-201 Ammonia evaporative condenser" (`units[C-201]`)
- Head pressure or condensing temperature: instrument PT-203 reads "PT-203 Condenser head (discharge) pressure" at C-201 (`instruments[PT-203]`)
- Head pressure control: controller PIC-203 reads "PIC-203 Head pressure control at a fixed setpoint, on the condenser fans" at C-201 (`controllers[PIC-203]`)
- Refrigeration compressor: equipment K-201 reads "K-201 Ammonia (R-717) screw compressor, low stage (booster)" (`units[K-201]`)
- Refrigeration compressor: equipment K-202 reads "K-202 Ammonia (R-717) screw compressor, high stage" (`units[K-202]`)
- Refrigeration compressor: equipment K-203 reads "K-203 Ammonia (R-717) screw compressor, high stage (trim)" (`units[K-203]`)
- Compressor power: instrument JT-201 reads "JT-201 Low-stage compressor motor power" at K-201 (`instruments[JT-201]`)
- Checked, none found: no floating head pressure or wet-bulb reset is named on any controller or item (`applies_when.without`)

**Data to collect**

- Head (discharge) pressure and condensing temperature, hourly over a year [not on drawing]. Where: historian or DCS trend for PT-203 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the head pressure setpoint and its low limit in the refrigeration plant controls. How: Convert pressure to saturated condensing temperature with the refrigerant's tables; see whether it falls in cool weather or sits at the setpoint.
- Ambient wet-bulb temperature (dry-bulb for an air-cooled condenser) at the same times [not on drawing]. Where: site records: the site weather station, or the nearest public weather station's hourly record. How: Line it up hour by hour with the condensing temperature.
- The lowest head pressure the plant can run at [not on drawing]. Where: DCS/PLC configuration: the minimum needed for hot gas defrost, liquid injection oil cooling and liquid feed to the farthest evaporator; then the vendor datasheet: compressor and expansion valve minimum pressure difference. How: This is the floor a floating setpoint may not go below.
- Compressor and condenser fan and pump power [not on drawing]. Where: historian or DCS trend for JT-201 (no historian tag is mapped in this model for these); then a walkdown: power logger on the compressor motors and on the condenser fan and spray pump motors. How: Floating the head pressure moves load from the compressors to the condenser fans; count both.

**How it is decided:** Worth a look when the head pressure sits at a fixed setpoint through cool weather, above both what the condenser could reach and the plant's own minimum. If it already follows the wet-bulb down to that minimum, close it.

**What the source says (S25):** Floating head pressure (S25, p. 62) "allows compressor head pressures to move up or down with variations in ambient wet-bulb temperature, saving energy compared to fixed head pressure operation." Condensing pressure (S25, p. 65): "Lowering the condensing temperature can reduce compressor energy use by around 2% to 3% for every degree Celsius (1.8 degrees Fahrenheit) of temperature reduction (SenterNovem 2003)." Condenser fans (S25, p. 65): "On systems where floating head operation is stable, ASDs can lower condenser fan energy consumption by up to 40% compared to operating a fixed-speed condenser fan in on/off fashion (IRC 2004b)."

**Limits:** S25 (p. 62) warns that condenser fan energy rises as head pressure falls and that head pressure must not go below what defrost or liquid injection oil cooling need. Fires only where the equipment's own name, type or service names the refrigerant (ammonia, NH3, R-717, a refrigerant number) or says refrigeration; an air compressor, a process recycle compressor, a process condenser on cooling water or a power-plant air-cooled condenser does not.

### E28: Is each refrigeration suction level held colder than the warmest load on it needs?

**About:** K-201, K-202, K-203  

**Evidence on the drawing / model**

- equipment K-201 reads "K-201 Ammonia (R-717) screw compressor, low stage (booster)" (`units[K-201]`)
- equipment K-202 reads "K-202 Ammonia (R-717) screw compressor, high stage" (`units[K-202]`)
- equipment K-203 reads "K-203 Ammonia (R-717) screw compressor, high stage (trim)" (`units[K-203]`)
- Suction pressure: instrument PT-201 reads "PT-201 Low-stage suction pressure" at K-201 (`instruments[PT-201]`)
- Suction pressure: instrument PT-202 reads "PT-202 High-stage suction pressure" at K-202 (`instruments[PT-202]`)
- Refrigeration load: equipment EV-201 reads "EV-201 Spiral freezer evaporator (ammonia, hot gas defrost)" (`units[EV-201]`)
- Refrigeration load: equipment EV-202 reads "EV-202 Frozen store unit cooler (ammonia, hot gas defrost)" (`units[EV-202]`)
- Refrigeration load: equipment CS-201 reads "CS-201 Frozen product cold store" (`units[CS-201]`)
- Refrigerated space temperature: instrument TT-205 reads "TT-205 Spiral freezer air temperature" at EV-201 (`instruments[TT-205]`)
- Refrigerated space temperature: instrument TT-206 reads "TT-206 Frozen store air temperature" at EV-202 (`instruments[TT-206]`)
- Compressor power: instrument JT-201 reads "JT-201 Low-stage compressor motor power" at K-201 (`instruments[JT-201]`)

**Data to collect**

- Suction pressure at each suction level, hourly [not on drawing]. Where: historian or DCS trend for PT-201, PT-202 (no historian tag is mapped in this model for these); then DCS/PLC configuration: suction pressure setpoints per compressor or suction level. How: Convert to saturated evaporating temperature; note whether it changes at night, weekends or in winter.
- The temperature each load actually needs [not on drawing]. Where: site records: room and product temperature specifications for each freezer, cold store and chiller, and which suction level serves it; then historian or DCS trend for TT-205, TT-206 (no historian tag is mapped in this model for these). How: The warmest load on a suction level, less its coil approach, sets the coldest suction that level needs.
- Compressor power and run hours per suction level [not on drawing]. Where: historian or DCS trend for JT-201 (no historian tag is mapped in this model for these); then site records: compressor run hours from the refrigeration plant controls. How: A month or more at normal production.

**How it is decided:** Worth a look when a suction level runs colder than its warmest load needs after the coil approach, or stays fixed when loads ease at night and weekends. Close it when the loads on that level need the present temperature.

**What the source says (S25):** Two-stage systems (S25, p. 63): "a simple way to save energy is to raise the suction pressure and temperature of the low-stage compressor when ambient temperatures decrease. It has been estimated that energy savings of about 8% can be realized in two-stage systems when suction temperatures are raised from -30 °F to -20 °F (ISU 2005)." No figure is given there for single-stage systems.

**Limits:** Product temperature and food-safety limits set the floor: a suction change changes how product is held and needs the quality owner's sign-off. Fires only where the equipment's own name, type or service names the refrigerant (ammonia, NH3, R-717, a refrigerant number) or says refrigeration; an air compressor, a process recycle compressor, a process condenser on cooling water or a power-plant air-cooled condenser does not.

### E29: Does this refrigeration compressor carry part load on its slide valve (or hot gas bypass) with no speed control?

**About:** K-201  

**Evidence on the drawing / model**

- equipment K-201 reads "K-201 Ammonia (R-717) screw compressor, low stage (booster)" (`units[K-201]`)
- Compressor power: instrument JT-201 reads "JT-201 Low-stage compressor motor power" at K-201 (`instruments[JT-201]`)
- Checked, none found: no variable speed drive or speed controller drawn on this compressor (`applies_when.without`)

**Data to collect**

- Slide valve (capacity) position over normal operation [not on drawing]. Where: DCS/PLC configuration: slide valve position or percent capacity per compressor from the refrigeration plant controls, a month or more. How: Hours spent below full load, by load band.
- Compressor power and run hours [not on drawing]. Where: historian or DCS trend for JT-201 (no historian tag is mapped in this model for these); then a walkdown: power logger on the compressor motor across a normal week. How: Power at each load band, so part-load efficiency can be seen.
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

### E30: Are these evaporators defrosted on a fixed timer rather than when frost is actually there?

**About:** EV-201  

**Evidence on the drawing / model**

- equipment EV-201 reads "EV-201 Spiral freezer evaporator (ammonia, hot gas defrost)" (`units[EV-201]`)
- Defrost: final element HGV-201 reads "HGV-201 Hot gas defrost valve, spiral freezer evaporator (defrost started by a timer)" at EV-201 (`final_elements[HGV-201]`)
- Room or coil temperature: instrument TT-205 reads "TT-205 Spiral freezer air temperature" at EV-201 (`instruments[TT-205]`)
- Checked, none found: no demand defrost initiation (coil differential pressure, frost sensor) drawn on this evaporator (`applies_when.without`)

**Data to collect**

- Defrost schedule per evaporator [not on drawing]. Where: DCS/PLC configuration: defrost initiation (timer or demand), defrosts per day, duration and termination (time or coil temperature) per evaporator. How: List defrosts per day by season.
- Frost on the coil when a scheduled defrost starts [not on drawing]. Where: a walkdown: look at the coil just before a few scheduled defrosts, in a dry week and a humid week. How: Note clear, light or heavy frost.
- Hot gas use and room temperature rise per defrost [not on drawing]. Where: historian or DCS trend for HGV-201 (no historian tag is mapped in this model for these); then historian or DCS trend for TT-205 (no historian tag is mapped in this model for these). How: The heat put in to defrost comes back as refrigeration load afterwards.

**How it is decided:** Worth a look when coils are clear at scheduled defrosts, or the count per day is the same in dry weeks as in humid ones. Close it if defrost is already started on demand.

**What the source says (S25):** Demand defrost (S25, p. 66): "Evaporators should be defrosted only when necessary, as opposed to on timed schedules where defrosting occurs regardless of need." "Too frequent defrosts." is listed among control strategies that "may compromise system energy efficiency" (S25, p. 59, citing Pearson 2003). No % stated.

**Limits:** A coil differential pressure instrument on the evaporator is taken as demand defrost; check that it is used for that. A P&ID rarely shows the defrost timer itself, so the schedule always comes from the controls.

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

### E32: Is the burner air-fuel ratio on this oven, dryer or fryer checked and set, with no flue O2 measurement drawn?

**About:** D-301  

**Evidence on the drawing / model**

- equipment D-301 reads "D-301 Gas-fired product dryer (continuous belt)" (`units[D-301]`)
- Burner or fuel supply: stream U1 (asset stream:U1) reads "Natural gas to the dryer burner" at D-301 (`streams[U1]`)
- Burner or fuel supply: instrument FT-301 reads "FT-301 Dryer burner natural gas flow" at D-301 (`instruments[FT-301]`)
- Burner or fuel supply: valve TV-301 reads "TV-301 Dryer burner natural gas control valve" at D-301 (`final_elements[TV-301]`)
- Checked, none found: no flue O2 analyser or excess air measurement drawn on this unit (`applies_when.without`)

**Data to collect**

- Flue O2 and CO at high and low fire [not on drawing]. Where: a walkdown: portable combustion analyser in the flue or exhaust at high and low fire; then site records: the last burner tuning report. How: Compare with the burner maker's recommended O2 for this equipment.
- Air-fuel ratio settings and how they are held [not on drawing]. Where: DCS/PLC configuration: burner management and ratio control settings; then the vendor datasheet: burner datasheet: recommended excess air across the turndown range. How: Note whether the ratio is fixed linkage, electronic ratio or trimmed.
- Fuel use [not on drawing]. Where: historian or DCS trend for FT-301 (no historian tag is mapped in this model for these); then utility bills or the site energy report: gas sub-meter readings for this unit. How: A month of fuel use at a known production rate.
- Excess air the process needs [not on drawing]. Where: site records: the oven or dryer maker's minimum exhaust and excess air for moisture and solvent removal, and any flammable-vapour (LEL) limit. How: This is a floor: the burner may not be tuned below it.

**How it is decided:** Worth a tune-up when measured flue O2 is above what the burner maker recommends and the process does not need the extra air. On ovens and dryers that drive off water or solvent the dilution and drying air are part of the process: never cut below the maker's or the safety minimum.

**What the source says (S27):** S27 (p. 1): "Periodic checking and resetting of air-fuel ratios for burners is one of the simplest ways to get maximum efficiency out of fuel-fired process heating equipment such as furnaces, ovens, heaters, and boilers." And: "Processes that evaporate moisture or solvents need large amounts of excess air to dilute flammable solvents to noncombustible levels, to ensure adequate drying rates, and to carry vapors out of the oven. Lowering excess air to minimal levels can slow down the process and create an explosion hazard." No typical % stated (the sheet's worked example is one furnace).

**Limits:** Burner adjustment is a combustion-safety change, done by a qualified burner technician under the site's burner management procedures. Indirect (steam or thermal oil) heated units have no burner on them and do not fire this question.

### E32: Is the burner air-fuel ratio on this oven, dryer or fryer checked and set, with no flue O2 measurement drawn?

**About:** F-303  

**Evidence on the drawing / model**

- equipment F-303 reads "F-303 Gas-fired continuous fryer" (`units[F-303]`)
- Burner or fuel supply: stream U3 (asset stream:U3) reads "Natural gas to the fryer burner" at F-303 (`streams[U3]`)
- Burner or fuel supply: valve TV-303 reads "TV-303 Fryer burner natural gas control valve" at F-303 (`final_elements[TV-303]`)
- Checked, none found: no flue O2 analyser or excess air measurement drawn on this unit (`applies_when.without`)

**Data to collect**

- Flue O2 and CO at high and low fire [not on drawing]. Where: a walkdown: portable combustion analyser in the flue or exhaust at high and low fire; then site records: the last burner tuning report. How: Compare with the burner maker's recommended O2 for this equipment.
- Air-fuel ratio settings and how they are held [not on drawing]. Where: DCS/PLC configuration: burner management and ratio control settings; then the vendor datasheet: burner datasheet: recommended excess air across the turndown range. How: Note whether the ratio is fixed linkage, electronic ratio or trimmed.
- Fuel use [not on drawing]. Where: only a valve (TV-303) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then utility bills or the site energy report: gas sub-meter readings for this unit. How: A month of fuel use at a known production rate.
- Excess air the process needs [not on drawing]. Where: site records: the oven or dryer maker's minimum exhaust and excess air for moisture and solvent removal, and any flammable-vapour (LEL) limit. How: This is a floor: the burner may not be tuned below it.

**How it is decided:** Worth a tune-up when measured flue O2 is above what the burner maker recommends and the process does not need the extra air. On ovens and dryers that drive off water or solvent the dilution and drying air are part of the process: never cut below the maker's or the safety minimum.

**What the source says (S27):** S27 (p. 1): "Periodic checking and resetting of air-fuel ratios for burners is one of the simplest ways to get maximum efficiency out of fuel-fired process heating equipment such as furnaces, ovens, heaters, and boilers." And: "Processes that evaporate moisture or solvents need large amounts of excess air to dilute flammable solvents to noncombustible levels, to ensure adequate drying rates, and to carry vapors out of the oven. Lowering excess air to minimal levels can slow down the process and create an explosion hazard." No typical % stated (the sheet's worked example is one furnace).

**Limits:** Burner adjustment is a combustion-safety change, done by a qualified burner technician under the site's burner management procedures. Indirect (steam or thermal oil) heated units have no burner on them and do not fire this question.

## Heat grade (high-grade heat for low-grade duty)

### H5: Is refrigeration condenser heat rejected while a low-grade heating duty nearby is met with fuel or steam?

**About:** K-201, K-202, K-203, C-201  

**Evidence on the drawing / model**

- equipment K-201 reads "K-201 Ammonia (R-717) screw compressor, low stage (booster)" (`units[K-201]`)
- equipment K-202 reads "K-202 Ammonia (R-717) screw compressor, high stage" (`units[K-202]`)
- equipment K-203 reads "K-203 Ammonia (R-717) screw compressor, high stage (trim)" (`units[K-203]`)
- equipment C-201 reads "C-201 Ammonia evaporative condenser" (`units[C-201]`)
- Low-grade heating duty: equipment WH-401 reads "WH-401 Gas-fired water heater, CIP and wash hot water" (`units[WH-401]`)
- Low-grade heating duty: stream W2 (asset stream:W2) reads "CIP and wash hot water supply" (`streams[W2]`)
- Discharge or condensing measurement: instrument TT-202 reads "TT-202 Compressor discharge temperature" at K-202 (`instruments[TT-202]`)
- Discharge or condensing measurement: instrument PT-203 reads "PT-203 Condenser head (discharge) pressure" at C-201 (`instruments[PT-203]`)
- Compressor power: instrument JT-201 reads "JT-201 Low-stage compressor motor power" at K-201 (`instruments[JT-201]`)
- Checked, none found: no desuperheater or refrigeration heat recovery exchanger anywhere in the model (`applies_when.without`)

**Data to collect**

- Discharge and condensing temperatures [not on drawing]. Where: historian or DCS trend for PT-203, TT-202 (no historian tag is mapped in this model for these); then DCS/PLC configuration: discharge temperature and head pressure readings in the refrigeration plant controls. How: Discharge superheat is the hotter, smaller part; condensing heat is larger but only at the condensing temperature.
- Compressor power and run hours [not on drawing]. Where: historian or DCS trend for JT-201 (no historian tag is mapped in this model for these); then site records: compressor run hours from the refrigeration plant controls. How: Heat rejected is about the compressor power plus the refrigeration load at the same time.
- The low-grade duty: temperature needed, load and hours [not on drawing]. Where: site records: temperatures and loads of the hot water, CIP, wash water, floor heating and space heating users, by hour. How: Match by temperature, hours and distance.
- Effect on head pressure [not on drawing]. Where: the vendor datasheet: whether a heat recovery exchanger would need a higher condensing pressure than now. How: Recovery that raises the head pressure in cool weather costs compressor power (see E27); count it.

**How it is decided:** Worth a study when the refrigeration plant runs at the same times as a duty that needs heat below the discharge or condensing temperature, and recovery does not force the head pressure up. Close it if the duties do not overlap or recovery would need a higher condensing pressure all year.

**What the source says (S25):** S25 (p. 64), refrigeration compressors: "Where economically feasible, rejected heat can be recovered from compressors and used in other facility applications, such as space heating or water heating." No % stated there for refrigeration (the air compressor heat recovery figures quoted under E23 do not apply).

**Limits:** The with-clause finds any low-grade duty in the model, not one next to the plant: distance is for the walkdown. Fires only where the equipment's own name, type or service names the refrigerant (ammonia, NH3, R-717, a refrigerant number) or says refrigeration; an air compressor, a process recycle compressor, a process condenser on cooling water or a power-plant air-cooled condenser does not.

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

## Metering

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** O-302  

**Evidence on the drawing / model**

- stream U2 (asset stream:U2) reads "Natural gas to the oven burners" at O-302 (`streams[U2]`)
- valve TV-302 reads "TV-302 Oven burner natural gas control valve" at O-302 (`final_elements[TV-302]`)
- Equipment: equipment O-302 reads "O-302 Gas-fired tunnel oven" (`units[O-302]`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: only a valve (TV-302) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** F-303  

**Evidence on the drawing / model**

- stream U3 (asset stream:U3) reads "Natural gas to the fryer burner" at F-303 (`streams[U3]`)
- valve TV-303 reads "TV-303 Fryer burner natural gas control valve" at F-303 (`final_elements[TV-303]`)
- Equipment: equipment F-303 reads "F-303 Gas-fired continuous fryer" (`units[F-303]`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: only a valve (TV-303) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** WH-401  

**Evidence on the drawing / model**

- stream U4 (asset stream:U4) reads "Natural gas to the water heater" at WH-401 (`streams[U4]`)
- valve TV-401 reads "TV-401 Water heater burner natural gas control valve" at WH-401 (`final_elements[TV-401]`)
- Equipment: equipment WH-401 reads "WH-401 Gas-fired water heater, CIP and wash hot water" (`units[WH-401]`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: only a valve (TV-401) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C12: Is power to these refrigeration compressors measured, so the plant's kW against load can be tracked?

**About:** K-202, K-203  

**Evidence on the drawing / model**

- equipment K-202 reads "K-202 Ammonia (R-717) screw compressor, high stage" (`units[K-202]`)
- equipment K-203 reads "K-203 Ammonia (R-717) screw compressor, high stage (trim)" (`units[K-203]`)
- Suction or discharge pressure: instrument PT-202 reads "PT-202 High-stage suction pressure" at K-202 (`instruments[PT-202]`)
- Checked, none found: no power, current or energy measurement drawn on these compressors (`applies_when.without`)

**Data to collect**

- Compressor power [not on drawing]. Where: a walkdown: the drive's or motor protection relay's kW reading, or a temporary power logger, per compressor; then utility bills or the site energy report: site interval meter data to apportion. How: A representative period at known production.
- Suction and discharge pressures logged at the same times [not on drawing]. Where: historian or DCS trend for PT-202 (no historian tag is mapped in this model for these); then DCS/PLC configuration: suction and discharge pressure per compressor in the refrigeration plant controls. How: Logged together with power, these show how the plant runs.
- What to normalise against [not on drawing]. Where: site records: production throughput or freezer and cold store loads by day. How: kW per unit of product or per unit of refrigeration.

**How it is decided:** Meter, or log from the drives, where the refrigeration plant is large enough that kW against load would change decisions; a reading nobody reviews saves nothing.

**What the source says (S25):** S25 (p. 58): "A basic monitoring system should include ongoing measurement and logging of compressor suction and discharge pressures; a drop in suction pressure typically indicates a refrigerant leak, while a rise in discharge pressure can indicate a blocked condenser (EEBPP 2000a)." "In a review of energy efficiency opportunities for refrigeration systems in wineries, the energy savings associated with the installation of monitoring systems were estimated at 3% (Galitsky et al. 2005b)."

**Limits:** The 3% is one review of winery refrigeration, as reported in S25. Fires only where the equipment's own name, type or service names the refrigerant (ammonia, NH3, R-717, a refrigerant number) or says refrigeration; an air compressor, a process recycle compressor, a process condenser on cooling water or a power-plant air-cooled condenser does not.

## Controls and automation

### C2: Which measurements have no controller (read by people, or by nothing)?

**About:** PT-201, JT-201, TT-202, TT-205, TT-206, PDT-206 and 4 more  

**Evidence on the drawing / model**

- instrument PT-201 reads "PT-201 Low-stage suction pressure" at K-201 (`instruments[PT-201]`)
- instrument JT-201 reads "JT-201 Low-stage compressor motor power" at K-201 (`instruments[JT-201]`)
- instrument TT-202 reads "TT-202 Compressor discharge temperature" at K-202 (`instruments[TT-202]`)
- instrument TT-205 reads "TT-205 Spiral freezer air temperature" at EV-201 (`instruments[TT-205]`)
- instrument TT-206 reads "TT-206 Frozen store air temperature" at EV-202 (`instruments[TT-206]`)
- instrument PDT-206 reads "PDT-206 Unit cooler coil air-side differential pressure (demand defrost initiation)" at EV-202 (`instruments[PDT-206]`)
- instrument TT-304 reads "TT-304 Dryer exhaust air temperature" at D-301 (`instruments[TT-304]`)
- instrument FT-301 reads "FT-301 Dryer burner natural gas flow" at D-301 (`instruments[FT-301]`)
- instrument TT-305 reads "TT-305 Oven exhaust temperature" at O-302 (`instruments[TT-305]`)
- instrument AT-302 reads "AT-302 Oven flue O2 analyser" at O-302 (`instruments[AT-302]`)
- Checked, none found: no controller in the model or loop list reads these measurements (`applies_when.without`)

**Data to collect**

- Whether operators adjust anything by hand from these readings [not on drawing]. Where: site records: operator logs and round sheets; then ask the operators which of these they act on, and how often. How: Note manual adjustments per shift tied to each reading.
- The control system's own loop list [not on drawing]. Where: DCS/PLC configuration: export the loop and point list. How: Confirm the reading is indication-only and not read by logic the model lacks.

**How it is decided:** Worth automating a reading that operators adjust by hand often, on a service where steadier control saves energy or quality; indication-only readings nobody acts on close the question.

**What the source says (S19):** "energy and cost savings are around 5% or more for many industrial applications of process control systems" (for plants without updated controls). Process control: "Typically 2-18% savings." The source says these figures "cannot be added".

**Limits:** The model or loop list may be incomplete; an uncontrolled reading may be read by logic not in the model.

### C3: Do these control valves lack position feedback?

**About:** TV-301, TV-302, TV-303, TV-401, PV-501  

**Evidence on the drawing / model**

- valve TV-301 reads "TV-301 Dryer burner natural gas control valve" at D-301 (`final_elements[TV-301]`)
- valve TV-302 reads "TV-302 Oven burner natural gas control valve" at O-302 (`final_elements[TV-302]`)
- valve TV-303 reads "TV-303 Fryer burner natural gas control valve" at F-303 (`final_elements[TV-303]`)
- valve TV-401 reads "TV-401 Water heater burner natural gas control valve" at WH-401 (`final_elements[TV-401]`)
- valve PV-501 reads "PV-501 Air compressor load/unload control" at AC-501 (`final_elements[PV-501]`)
- Checked, none found: no position transmitter or indicator (ZT, ZI) drawn on these valves (`applies_when.without`)

**Data to collect**

- Positioner type and diagnostics available [not on drawing]. Where: DCS/PLC configuration: valve positioner configuration (smart positioner? HART/fieldbus diagnostics?); then maintenance records: valve records. How: List which valves report position.
- Valve stiction or backlash [not on drawing]. Where: historian or DCS trend for PV-501, TV-301, TV-302, TV-303, TV-401 (no historian tag is mapped in this model for these); then a walkdown: a small step test on each loop in manual. How: Compare controller output with measured response.

**How it is decided:** Add feedback or diagnostics first on valves in energy- or safety-significant loops that show stiction or hunting.

**What the source says (S13):** "Control valve backlash and stiction... are major contributors to process variability." No % stated.

**Limits:** P&IDs often omit positioners; the model saying 'none drawn' does not mean none fitted.

### C11: Is this dryer's or oven's exhaust (and make-up air) rate set by hand rather than by exhaust humidity?

**About:** D-301  

**Evidence on the drawing / model**

- equipment D-301 reads "D-301 Gas-fired product dryer (continuous belt)" (`units[D-301]`)
- Exhaust measurement: instrument TT-304 reads "TT-304 Dryer exhaust air temperature" at D-301 (`instruments[TT-304]`)
- Exhaust damper or fan: hand valve HV-304 reads "HV-304 Dryer exhaust damper (manual, fixed position)" at D-301 (`manual_valves[HV-304]`)
- Checked, none found: no humidity, dew point or moisture measurement drawn on this unit (`applies_when.without`)

**Data to collect**

- Exhaust humidity and temperature over a production run [not on drawing]. Where: historian or DCS trend for TT-304 (no historian tag is mapped in this model for these); then a walkdown: humidity or dew point logger in the exhaust duct for a full run. How: Compare the exhaust humidity with what the product and the process allow.
- Exhaust damper or fan setting and how it is set [not on drawing]. Where: historian or DCS trend for HV-304 (no historian tag is mapped in this model for these); then DCS/PLC configuration: exhaust damper position or fan speed, and whether anything adjusts it; then a walkdown: damper position marks. How: Note whether it moves with production rate or product.
- Product moisture at the exit and its specification [not on drawing]. Where: site records: quality records: product moisture out of the dryer or oven against specification. How: Over-drying shows as moisture well below specification.

**How it is decided:** Worth a look when the exhaust leaves well below the humidity the product and the safety limits allow, so heated air is thrown away unsaturated. Close it if the exhaust is already near the allowed humidity or the rate is set by a solvent (LEL) or dust limit.

**What the source says (S26):** S26 (p. 104): "Process controls, such as feedback controllers, feed forward controllers, and model-based predictive controllers, can help to minimize dryer energy consumption by more precisely controlling energy inputs to meet the needs of the product being processed." The sensors it lists include "absorption capacitive sensors (for air humidity)". No % stated.

**Limits:** Exhaust rates on ovens that bake off solvents, or dryers with combustible dust, are set by safety limits: any change goes through the safety review. Fryers are left out: their exhaust is set by the vapour they boil off.

### C11: Is this dryer's or oven's exhaust (and make-up air) rate set by hand rather than by exhaust humidity?

**About:** O-302  

**Evidence on the drawing / model**

- equipment O-302 reads "O-302 Gas-fired tunnel oven" (`units[O-302]`)
- Exhaust measurement: instrument TT-305 reads "TT-305 Oven exhaust temperature" at O-302 (`instruments[TT-305]`)
- Exhaust measurement: instrument AT-302 reads "AT-302 Oven flue O2 analyser" at O-302 (`instruments[AT-302]`)
- Checked, none found: no humidity, dew point or moisture measurement drawn on this unit (`applies_when.without`)

**Data to collect**

- Exhaust humidity and temperature over a production run [not on drawing]. Where: historian or DCS trend for TT-305 (no historian tag is mapped in this model for these); then a walkdown: humidity or dew point logger in the exhaust duct for a full run. How: Compare the exhaust humidity with what the product and the process allow.
- Exhaust damper or fan setting and how it is set [not on drawing]. Where: DCS/PLC configuration: exhaust damper position or fan speed, and whether anything adjusts it; then a walkdown: damper position marks. How: Note whether it moves with production rate or product.
- Product moisture at the exit and its specification [not on drawing]. Where: site records: quality records: product moisture out of the dryer or oven against specification. How: Over-drying shows as moisture well below specification.

**How it is decided:** Worth a look when the exhaust leaves well below the humidity the product and the safety limits allow, so heated air is thrown away unsaturated. Close it if the exhaust is already near the allowed humidity or the rate is set by a solvent (LEL) or dust limit.

**What the source says (S26):** S26 (p. 104): "Process controls, such as feedback controllers, feed forward controllers, and model-based predictive controllers, can help to minimize dryer energy consumption by more precisely controlling energy inputs to meet the needs of the product being processed." The sensors it lists include "absorption capacitive sensors (for air humidity)". No % stated.

**Limits:** Exhaust rates on ovens that bake off solvents, or dryers with combustible dust, are set by safety limits: any change goes through the safety review. Fryers are left out: their exhaust is set by the vapour they boil off.

## Safety questions to verify

### C9: Is a trip or interlock shown for this rotating or fired equipment?

**About:** K-201, K-202, K-203, AC-501  

**Evidence on the drawing / model**

- equipment K-201 reads "K-201 Ammonia (R-717) screw compressor, low stage (booster)" (`units[K-201]`)
- equipment K-202 reads "K-202 Ammonia (R-717) screw compressor, high stage" (`units[K-202]`)
- equipment K-203 reads "K-203 Ammonia (R-717) screw compressor, high stage (trim)" (`units[K-203]`)
- equipment AC-501 reads "AC-501 Instrument air compressor" (`units[AC-501]`)
- Checked, none found: no safety switch (xSLL, xSHH...), burner management or trip interlock drawn for this equipment (`applies_when.without`)

**Data to collect**

- Cause-and-effect matrix and HAZOP/LOPA records [not on drawing]. Where: site records: cause-and-effect matrix, HAZOP and LOPA reports; then DCS/PLC configuration: safety system configuration. How: Confirm what protects each machine and that it is tested.

**How it is decided:** This is a question to verify, not a finding: close it once the protection is found in the cause-and-effect matrix or safety system.

**What the source says (no source):** Safety benefit; no energy source. Present it as a question to verify, not a finding.

**Limits:** P&IDs often leave trips to the cause-and-effect matrix; 'none drawn' is common and not by itself a gap.

## Questions that found nothing to ask here

No item in this model matched these questions' triggers. That is not a clean bill of health: the model may simply not show what the question looks for. E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12, E13, E14, E15, E16, E17, E18, E20, E21, E24, H1, H2, H3, H4, C4, C5, C6, C7, C10, C8, E25, E26.

## Sources cited above

- S10: Compressed Air Tip #9, Compressed Air Storage Strategies (DOE/GO-102004-1965). https://www.energy.gov/sites/prod/files/2014/05/f16/compressed_air9.pdf (license: Public domain)
- S11: Improving Compressed Air System Performance: A Sourcebook for Industry, 3rd ed. (DOE + Compressed Air Challenge). https://www.energy.gov/sites/default/files/2016/03/f30/Improving%20Compressed%20Air%20Sourcebook%20version%203.pdf (license: DOE publication co-produced with CAC; mostly federal, reuse of CAC content unclear)
- S13: Improving Pumping System Performance: A Sourcebook for Industry, 2nd ed. (DOE + Hydraulic Institute; DOE/GO-102006-2079). https://www.energy.gov/sites/prod/files/2014/05/f16/pump.pdf (license: Federal, co-developed with HI: unclear for HI content)
- S19: Worrell & Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for Petroleum Refineries: An ENERGY STAR Guide (LBNL-56183, Feb 2005). https://www.osti.gov/servlets/purl/862119 (license: DOE-lab (contractor) report: unclear, but freely citable. Its tables quote older secondary sources, so figures are cited as reported in LBNL-56183)
- S22: FEMP Metering Best Practices: A Guide to Achieving Utility Resource Efficiency, Release 3.0 (PNNL-23892, Mar 2015). https://www.wbdg.org/FFC/DOE/NLCRIT/mbpg_2015.pdf (license: Contractor-prepared federal guide: unclear. Its savings figures are buildings-focused)
- S24: DOE IAC/ITAC database: browse pages, download, schema document. https://itac.university/index/arc/2. (license: No license or terms stated: unclear)
- S25: Brush, Masanet and Worrell, Energy Efficiency Improvement and Cost Saving Opportunities for the Dairy Processing Industry: An ENERGY STAR Guide for Energy and Plant Managers (LBNL-6261E, Oct 2011). https://www.osti.gov/servlets/purl/1171534 (license: DOE-lab report sponsored by US EPA: unclear, freely citable; its figures from older sources are quoted as reported there)
- S26: Masanet, Worrell, Graus and Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for the Fruit and Vegetable Processing Industry: An ENERGY STAR Guide for Energy and Plant Managers (LBNL-59289-Revision, Mar 2008). https://eta-publications.lbl.gov/sites/default/files/lbnl-59289-rev.pdf (license: DOE-lab report sponsored by US EPA: unclear, freely citable; its figures from older sources are quoted as reported there)
- S27: DOE Industrial Technologies Program, Process Heating Tip Sheet #2, Check Burner Air to Fuel Ratios (Nov 2007). https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/42110.pdf (license: Public domain (US federal))
- S28: DOE Industrial Technologies Program, Process Heating Tip Sheet #10, Using Waste Heat for External Processes (DOE/GO-102006-2225, Jan 2006). https://www1.eere.energy.gov/manufacturing/tech_assistance/pdfs/38853.pdf (license: Public domain (US federal))
