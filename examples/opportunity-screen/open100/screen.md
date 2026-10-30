# Opportunity screen: extracted drawing set, 12 sheets

Model: `out/twin/r2-tiles-trace/codex/plant_model.json`. Questions: `data/questions.json`. Schedule: `data/open100_equipment_schedule.json`. Schedule: `examples/opportunity-screen/open100_schedule_fields.json`.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Energy | 16 |
| Heat grade (high-grade heat for low-grade duty) | 4 |
| Metering | 7 |
| Controls and automation | 1 |
| Emissions | 0 |
| Safety questions to verify | 1 |

## Energy

### E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

**About:** CND-PU-162  

**Evidence on the drawing / model**

- equipment CND-PU-162 (asset S2-PU001) reads "CND-PU-162 CONDENSATE PUMP" on sheet 2 (`units[S2-PU001]`)
- Control valve on the discharge: valve FCV-1621 (asset S2-IN022) on sheet 2 at CND-HTR-161 (by the extraction's attribution) (`instruments[S2-IN022]`)
- Flow measurement: instrument FIT-16299 (asset S2-IN015) on sheet 2 at CND-PU-162 (by the extraction's attribution) (`instruments[S2-IN015]`)
- Flow measurement: instrument FO-1621 (asset S2-IN018) on sheet 2 at CND-PU-162 (by the extraction's attribution) (`instruments[S2-IN018]`)
- Flow measurement: instrument FT-XXX (asset S2-IN019) [placeholder tag on the drawing] on sheet 2 at CND-PU-162 (by the extraction's attribution) (`instruments[S2-IN019]`)
- Flow measurement: instrument FIT-163101 (asset S2-IN020) on sheet 2 at CND-PU-163 (by the extraction's attribution) (`instruments[S2-IN020]`)
- Flow measurement: instrument FIT-164102 (asset S2-IN021) on sheet 2 at CND-PU-164 (by the extraction's attribution) (`instruments[S2-IN021]`)
- Checked, none found: no speed control (SC, SIC, SY tag, VFD or VSD) on or next to the pump (`applies_when.without`)
- Caveat: the extracted links have no recorded flow direction, so 'near' means within the stated number of drawn links on the same sheet; which side of the equipment it is on is not established by the model

**Data to collect**

- Control valve position (% open) over normal operation [not on drawing]. Where: historian or DCS trend for FCV-1621 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the valve's controller output; then a walkdown: read the positioner stroke indicator at several rates. How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
- Flow over the same period (a flow-duration curve) [not on drawing]. Where: historian or DCS trend for FIT-16299, FIT-163101, FIT-164102, FO-1621, FT-XXX (no historian tag is mapped in this model for these); then site records: production rate records. How: Bin the flow into ranges and count the hours in each.
- Pump rated flow and head [blank on drawing]. Where: the blank CAPACITY field on the sheet 2 equipment schedule, entry CND-PU-162; then the blank DISCHARGE field on the sheet 2 equipment schedule, entry CND-PU-162; then the vendor datasheet: pump curve and rated duty point; then the pump nameplate on CND-PU-162. How: Copy the rated flow and head and get the pump curve.
- Motor rating and speed [blank on drawing]. Where: the blank HP field on the sheet 2 equipment schedule, entry CND-PU-162; then the blank RPM field on the sheet 2 equipment schedule, entry CND-PU-162; then the motor nameplate on CND-PU-162; then maintenance records: motor record card. How: Copy rated power, speed and efficiency from the motor nameplate.
- Static head versus friction head [not on drawing]. Where: a walkdown: elevations and pressures at the suction source and the delivery point; then site records: line list or isometrics for pipe lengths and sizes. How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.

**How it is decided:** Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

**What the source says (S15, S24):** "With rotodynamic pump installations, savings of between 30% and 50% have been achieved in many installations by installing VSDs." Also: "It is estimated that 75% of pump systems are oversized, many by more than 20%."
IAC/ITAC recommendation code: 2.4146 (IAC/ITAC browse page: 5,227 recommendations, 3.0 yr average payback, 31.4% implemented; average dollar figure omitted).

**Limits:** On a hand-built model the valve sits on a stream leaving the pump. On an extracted drawing the links have no direction, so the rule takes a control valve within four drawn links that do not pass through other equipment; it may still be on a branch or the suction side, so check the drawing. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

**About:** CND-PU-163  

**Evidence on the drawing / model**

- equipment CND-PU-163 (asset S2-PU002) reads "CND-PU-163 CONDENSATE PUMP" on sheet 2 (`units[S2-PU002]`)
- Control valve on the discharge: valve FCV-1621 (asset S2-IN022) on sheet 2 at CND-HTR-161 (by the extraction's attribution) (`instruments[S2-IN022]`)
- Flow measurement: instrument FIT-16299 (asset S2-IN015) on sheet 2 at CND-PU-162 (by the extraction's attribution) (`instruments[S2-IN015]`)
- Flow measurement: instrument FO-1621 (asset S2-IN018) on sheet 2 at CND-PU-162 (by the extraction's attribution) (`instruments[S2-IN018]`)
- Flow measurement: instrument FT-XXX (asset S2-IN019) [placeholder tag on the drawing] on sheet 2 at CND-PU-162 (by the extraction's attribution) (`instruments[S2-IN019]`)
- Flow measurement: instrument FIT-163101 (asset S2-IN020) on sheet 2 at CND-PU-163 (by the extraction's attribution) (`instruments[S2-IN020]`)
- Flow measurement: instrument FIT-164102 (asset S2-IN021) on sheet 2 at CND-PU-164 (by the extraction's attribution) (`instruments[S2-IN021]`)
- Checked, none found: no speed control (SC, SIC, SY tag, VFD or VSD) on or next to the pump (`applies_when.without`)
- Caveat: the extracted links have no recorded flow direction, so 'near' means within the stated number of drawn links on the same sheet; which side of the equipment it is on is not established by the model

**Data to collect**

- Control valve position (% open) over normal operation [not on drawing]. Where: historian or DCS trend for FCV-1621 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the valve's controller output; then a walkdown: read the positioner stroke indicator at several rates. How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
- Flow over the same period (a flow-duration curve) [not on drawing]. Where: historian or DCS trend for FIT-16299, FIT-163101, FIT-164102, FO-1621, FT-XXX (no historian tag is mapped in this model for these); then site records: production rate records. How: Bin the flow into ranges and count the hours in each.
- Pump rated flow and head [blank on drawing]. Where: the blank CAPACITY field on the sheet 2 equipment schedule, entry CND-PU-163; then the blank DISCHARGE field on the sheet 2 equipment schedule, entry CND-PU-163; then the vendor datasheet: pump curve and rated duty point; then the pump nameplate on CND-PU-163. How: Copy the rated flow and head and get the pump curve.
- Motor rating and speed [blank on drawing]. Where: the blank HP field on the sheet 2 equipment schedule, entry CND-PU-163; then the blank RPM field on the sheet 2 equipment schedule, entry CND-PU-163; then the motor nameplate on CND-PU-163; then maintenance records: motor record card. How: Copy rated power, speed and efficiency from the motor nameplate.
- Static head versus friction head [not on drawing]. Where: a walkdown: elevations and pressures at the suction source and the delivery point; then site records: line list or isometrics for pipe lengths and sizes. How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.

**How it is decided:** Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

**What the source says (S15, S24):** "With rotodynamic pump installations, savings of between 30% and 50% have been achieved in many installations by installing VSDs." Also: "It is estimated that 75% of pump systems are oversized, many by more than 20%."
IAC/ITAC recommendation code: 2.4146 (IAC/ITAC browse page: 5,227 recommendations, 3.0 yr average payback, 31.4% implemented; average dollar figure omitted).

**Limits:** On a hand-built model the valve sits on a stream leaving the pump. On an extracted drawing the links have no direction, so the rule takes a control valve within four drawn links that do not pass through other equipment; it may still be on a branch or the suction side, so check the drawing. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

**About:** CND-PU-164  

**Evidence on the drawing / model**

- equipment CND-PU-164 (asset S2-PU003) reads "CND-PU-164 CONDENSATE PUMP" on sheet 2 (`units[S2-PU003]`)
- Control valve on the discharge: valve FCV-1621 (asset S2-IN022) on sheet 2 at CND-HTR-161 (by the extraction's attribution) (`instruments[S2-IN022]`)
- Flow measurement: instrument FIT-16299 (asset S2-IN015) on sheet 2 at CND-PU-162 (by the extraction's attribution) (`instruments[S2-IN015]`)
- Flow measurement: instrument FO-1621 (asset S2-IN018) on sheet 2 at CND-PU-162 (by the extraction's attribution) (`instruments[S2-IN018]`)
- Flow measurement: instrument FT-XXX (asset S2-IN019) [placeholder tag on the drawing] on sheet 2 at CND-PU-162 (by the extraction's attribution) (`instruments[S2-IN019]`)
- Flow measurement: instrument FIT-163101 (asset S2-IN020) on sheet 2 at CND-PU-163 (by the extraction's attribution) (`instruments[S2-IN020]`)
- Flow measurement: instrument FIT-164102 (asset S2-IN021) on sheet 2 at CND-PU-164 (by the extraction's attribution) (`instruments[S2-IN021]`)
- Checked, none found: no speed control (SC, SIC, SY tag, VFD or VSD) on or next to the pump (`applies_when.without`)
- Caveat: the extracted links have no recorded flow direction, so 'near' means within the stated number of drawn links on the same sheet; which side of the equipment it is on is not established by the model

**Data to collect**

- Control valve position (% open) over normal operation [not on drawing]. Where: historian or DCS trend for FCV-1621 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the valve's controller output; then a walkdown: read the positioner stroke indicator at several rates. How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
- Flow over the same period (a flow-duration curve) [not on drawing]. Where: historian or DCS trend for FIT-16299, FIT-163101, FIT-164102, FO-1621, FT-XXX (no historian tag is mapped in this model for these); then site records: production rate records. How: Bin the flow into ranges and count the hours in each.
- Pump rated flow and head [blank on drawing]. Where: the blank CAPACITY field on the sheet 2 equipment schedule, entry CND-PU-164; then the blank DISCHARGE field on the sheet 2 equipment schedule, entry CND-PU-164; then the vendor datasheet: pump curve and rated duty point; then the pump nameplate on CND-PU-164. How: Copy the rated flow and head and get the pump curve.
- Motor rating and speed [blank on drawing]. Where: the blank HP field on the sheet 2 equipment schedule, entry CND-PU-164; then the blank RPM field on the sheet 2 equipment schedule, entry CND-PU-164; then the motor nameplate on CND-PU-164; then maintenance records: motor record card. How: Copy rated power, speed and efficiency from the motor nameplate.
- Static head versus friction head [not on drawing]. Where: a walkdown: elevations and pressures at the suction source and the delivery point; then site records: line list or isometrics for pipe lengths and sizes. How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.

**How it is decided:** Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

**What the source says (S15, S24):** "With rotodynamic pump installations, savings of between 30% and 50% have been achieved in many installations by installing VSDs." Also: "It is estimated that 75% of pump systems are oversized, many by more than 20%."
IAC/ITAC recommendation code: 2.4146 (IAC/ITAC browse page: 5,227 recommendations, 3.0 yr average payback, 31.4% implemented; average dollar figure omitted).

**Limits:** On a hand-built model the valve sits on a stream leaving the pump. On an extracted drawing the links have no direction, so the rule takes a control valve within four drawn links that do not pass through other equipment; it may still be on a branch or the suction side, so check the drawing. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

**About:** FWS-PU-170A  

**Evidence on the drawing / model**

- equipment FWS-PU-170A (asset S3-PU001) reads "FWS-PU-170A FEEDWATER PUMP" on sheet 3 (`units[S3-PU001]`)
- Control valve on the discharge: valve FCV-XXX (asset S3-IN006) [placeholder tag on the drawing] on sheet 3 at FWS-PU-170A (by the extraction's attribution) (`instruments[S3-IN006]`)
- Control valve on the discharge: valve PCV-1703 (asset S3-IN029) on sheet 3 at FWS-PU-170A (by the extraction's attribution) (`instruments[S3-IN029]`)
- Checked, none found: no speed control (SC, SIC, SY tag, VFD or VSD) on or next to the pump (`applies_when.without`)
- Caveat: the extracted links have no recorded flow direction, so 'near' means within the stated number of drawn links on the same sheet; which side of the equipment it is on is not established by the model

**Data to collect**

- Control valve position (% open) over normal operation [not on drawing]. Where: historian or DCS trend for FCV-XXX, PCV-1703 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the valve's controller output; then a walkdown: read the positioner stroke indicator at several rates. How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
- Flow over the same period (a flow-duration curve) [not on drawing]. Where: site records: production rate records. How: Bin the flow into ranges and count the hours in each.
- Pump rated flow and head [blank on drawing]. Where: the blank CAPACITY field on the sheet 3 equipment schedule, entry FWS-PU-170A; then the blank DISCHARGE field on the sheet 3 equipment schedule, entry FWS-PU-170A; then the vendor datasheet: pump curve and rated duty point; then the pump nameplate on FWS-PU-170A. How: Copy the rated flow and head and get the pump curve.
- Motor rating and speed [blank on drawing]. Where: the blank HP field on the sheet 3 equipment schedule, entry FWS-PU-170A; then the blank RPM field on the sheet 3 equipment schedule, entry FWS-PU-170A; then the motor nameplate on FWS-PU-170A; then maintenance records: motor record card. How: Copy rated power, speed and efficiency from the motor nameplate.
- Static head versus friction head [not on drawing]. Where: a walkdown: elevations and pressures at the suction source and the delivery point; then site records: line list or isometrics for pipe lengths and sizes. How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.

**How it is decided:** Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

**What the source says (S15, S24):** "With rotodynamic pump installations, savings of between 30% and 50% have been achieved in many installations by installing VSDs." Also: "It is estimated that 75% of pump systems are oversized, many by more than 20%."
IAC/ITAC recommendation code: 2.4146 (IAC/ITAC browse page: 5,227 recommendations, 3.0 yr average payback, 31.4% implemented; average dollar figure omitted).

**Limits:** On a hand-built model the valve sits on a stream leaving the pump. On an extracted drawing the links have no direction, so the rule takes a control valve within four drawn links that do not pass through other equipment; it may still be on a branch or the suction side, so check the drawing. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E1: Is this pump throttled by a control valve when it could run on a variable speed drive?

**About:** FWS-PU-170B  

**Evidence on the drawing / model**

- equipment FWS-PU-170B (asset S3-PU002) reads "FWS-PU-170B FEEDWATER PUMP" on sheet 3 (`units[S3-PU002]`)
- Control valve on the discharge: valve FCV-XXX (asset S3-IN006) [placeholder tag on the drawing] on sheet 3 at FWS-PU-170A (by the extraction's attribution) (`instruments[S3-IN006]`)
- Control valve on the discharge: valve PCV-1703 (asset S3-IN029) on sheet 3 at FWS-PU-170A (by the extraction's attribution) (`instruments[S3-IN029]`)
- Checked, none found: no speed control (SC, SIC, SY tag, VFD or VSD) on or next to the pump (`applies_when.without`)
- Caveat: the extracted links have no recorded flow direction, so 'near' means within the stated number of drawn links on the same sheet; which side of the equipment it is on is not established by the model

**Data to collect**

- Control valve position (% open) over normal operation [not on drawing]. Where: historian or DCS trend for FCV-XXX, PCV-1703 (no historian tag is mapped in this model for these); then DCS/PLC configuration: the valve's controller output; then a walkdown: read the positioner stroke indicator at several rates. How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
- Flow over the same period (a flow-duration curve) [not on drawing]. Where: site records: production rate records. How: Bin the flow into ranges and count the hours in each.
- Pump rated flow and head [blank on drawing]. Where: the blank CAPACITY field on the sheet 3 equipment schedule, entry FWS-PU-170B; then the blank DISCHARGE field on the sheet 3 equipment schedule, entry FWS-PU-170B; then the vendor datasheet: pump curve and rated duty point; then the pump nameplate on FWS-PU-170B. How: Copy the rated flow and head and get the pump curve.
- Motor rating and speed [blank on drawing]. Where: the blank HP field on the sheet 3 equipment schedule, entry FWS-PU-170B; then the blank RPM field on the sheet 3 equipment schedule, entry FWS-PU-170B; then the motor nameplate on FWS-PU-170B; then maintenance records: motor record card. How: Copy rated power, speed and efficiency from the motor nameplate.
- Static head versus friction head [not on drawing]. Where: a walkdown: elevations and pressures at the suction source and the delivery point; then site records: line list or isometrics for pipe lengths and sizes. How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.

**How it is decided:** Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

**What the source says (S15, S24):** "With rotodynamic pump installations, savings of between 30% and 50% have been achieved in many installations by installing VSDs." Also: "It is estimated that 75% of pump systems are oversized, many by more than 20%."
IAC/ITAC recommendation code: 2.4146 (IAC/ITAC browse page: 5,227 recommendations, 3.0 yr average payback, 31.4% implemented; average dollar figure omitted).

**Limits:** On a hand-built model the valve sits on a stream leaving the pump. On an extracted drawing the links have no direction, so the rule takes a control valve within four drawn links that do not pass through other equipment; it may still be on a branch or the suction side, so check the drawing. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** ACC-PU-151  

**Evidence on the drawing / model**

- equipment ACC-PU-151 (asset S1-PU013) reads "ACC-PU-151 AIR COOLED CONDENSER PUMP" on sheet 1 (`units[S1-PU013]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 1 equipment schedule, entry ACC-PU-151; then the motor nameplate on ACC-PU-151; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** ACC-PU-152  

**Evidence on the drawing / model**

- equipment ACC-PU-152 (asset S1-PU014) reads "ACC-PU-152 AIR COOLED CONDENSER PUMP" on sheet 1 (`units[S1-PU014]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 1 equipment schedule, entry ACC-PU-152; then the motor nameplate on ACC-PU-152; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** ACC-PU-153  

**Evidence on the drawing / model**

- equipment ACC-PU-153 (asset S1-PU015) reads "ACC-PU-153 AIR COOLED CONDENSER PUMP" on sheet 1 (`units[S1-PU015]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 1 equipment schedule, entry ACC-PU-153; then the motor nameplate on ACC-PU-153; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** CND-PU-162  

**Evidence on the drawing / model**

- equipment CND-PU-162 (asset S2-PU001) reads "CND-PU-162 CONDENSATE PUMP" on sheet 2 (`units[S2-PU001]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 2 equipment schedule, entry CND-PU-162; then the motor nameplate on CND-PU-162; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** CND-PU-163  

**Evidence on the drawing / model**

- equipment CND-PU-163 (asset S2-PU002) reads "CND-PU-163 CONDENSATE PUMP" on sheet 2 (`units[S2-PU002]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 2 equipment schedule, entry CND-PU-163; then the motor nameplate on CND-PU-163; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** CND-PU-164  

**Evidence on the drawing / model**

- equipment CND-PU-164 (asset S2-PU003) reads "CND-PU-164 CONDENSATE PUMP" on sheet 2 (`units[S2-PU003]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 2 equipment schedule, entry CND-PU-164; then the motor nameplate on CND-PU-164; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** FWS-PU-170A  

**Evidence on the drawing / model**

- equipment FWS-PU-170A (asset S3-PU001) reads "FWS-PU-170A FEEDWATER PUMP" on sheet 3 (`units[S3-PU001]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 3 equipment schedule, entry FWS-PU-170A; then the motor nameplate on FWS-PU-170A; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** FWS-PU-170B  

**Evidence on the drawing / model**

- equipment FWS-PU-170B (asset S3-PU002) reads "FWS-PU-170B FEEDWATER PUMP" on sheet 3 (`units[S3-PU002]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 3 equipment schedule, entry FWS-PU-170B; then the motor nameplate on FWS-PU-170B; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** ACW-PU-211A  

**Evidence on the drawing / model**

- equipment ACW-PU-211A (asset S7-PU001) reads "ACW-PU-211A AUX COOLING WATER PUMP" on sheet 7 (`units[S7-PU001]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 7 equipment schedule, entry ACW-PU-211A; then the motor nameplate on ACW-PU-211A; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** ACW-PU-211B  

**Evidence on the drawing / model**

- equipment ACW-PU-211B (asset S7-PU002) reads "ACW-PU-211B AUX COOLING WATER PUMP" on sheet 7 (`units[S7-PU002]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 7 equipment schedule, entry ACW-PU-211B; then the motor nameplate on ACW-PU-211B; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

### E4: Is this motor oversized for its load?

**About:** ACW-PU-211C  

**Evidence on the drawing / model**

- equipment ACW-PU-211C (asset S7-PU003) reads "ACW-PU-211C AUX COOLING WATER PUMP" on sheet 7 (`units[S7-PU003]`)

**Data to collect**

- Motor rated power [blank on drawing]. Where: the blank HP field on the sheet 7 equipment schedule, entry ACW-PU-211C; then the motor nameplate on ACW-PU-211C; then maintenance records: motor record card. How: Copy rated power, full-load amps and efficiency.
- Measured input power or current at normal load [not on drawing]. Where: a walkdown: a clamp-on power meter (or ammeter plus voltage) at the motor starter. How: Measure kW (or amps and volts) over a typical period.

**How it is decided:** Load factor = measured input power divided by (rated output divided by rated efficiency). A motor running well below about 40% of full load is worth a resize question; one oversized slightly is fine.

**What the source says (S16, S24):** "At loads below 40% of full load, motor efficiency begins to decline dramatically." "Slightly oversizing a motor (up to 25%) can actually increase efficiency." No % saving stated.
IAC/ITAC recommendation code: 2.41xx (category only) (IAC/ITAC browse page: motors: 18,002 recommendations, 2.5 yr average payback, 52.3% implemented; average dollar figure omitted).

**Limits:** Fires only where the drawing carries a motor rating field (filled or blank); a drawing without one gives no trigger. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

## Heat grade (high-grade heat for low-grade duty)

### H1: Is high-grade steam let down, bypassed or desuperheated for a duty a lower grade could serve?

**About:** ESS-HTR-180  

**Evidence on the drawing / model**

- equipment ESS-HTR-180 (asset S4-TK001) reads "ESS-HTR-180 DE SUPERHEATER" on sheet 4 (`units[S4-TK001]`)
- Station valve: valve TCV-16013 (asset S4-IN001) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`instruments[S4-IN001]`)
- Station valve: valve FCV-18012 (asset S4-IN014) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`instruments[S4-IN014]`)
- Station valve: valve PCV-14011 (asset S4-IN016) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`instruments[S4-IN016]`)
- Steam source or user: offpage "MSS PID 140-1 PEGGING STEAM" (S4-OP005) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`offpage_connectors[S4-OP005].text`)
- Spray or quench water: offpage "CND PID 160-1 (E-1) CONDENSATE SYSTEM" (S4-OP001) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`offpage_connectors[S4-OP001].text`)

**Data to collect**

- Steam flow through the station, with hours [not on drawing]. Where: only a valve (FCV-18012, PCV-14011, TCV-16013) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then site records: steam balance. How: Build a flow-duration curve: how many hours at each flow.
- Upstream and downstream pressure and temperature [not on drawing]. Where: a walkdown: gauges and thermometers either side of the station; then site records: header design conditions. How: Record at normal operation.
- Station rating [blank on drawing]. Where: the blank CAPACITY field on the sheet 4 equipment schedule, entry ESS-HTR-180; then the vendor datasheet: station or desuperheater datasheet. How: Copy rated flow.
- When the station is used [not on drawing]. Where: site records: operating procedures: startup, trip, normal duty. How: Mark the station startup-only, trip-only or normal duty.

**How it is decided:** If the station passes steam only at startup or trips, close it. If it passes steady flow in normal duty, ask whether a lower-grade source (an extraction or exhaust at the right pressure) could serve the user, or whether the pressure drop could do work: S6's condition for a backpressure turbogenerator is a constant flow of at least 3,000 lb/hr and a drop of at least 100 psi.

**What the source says (S6):** Closest source wording (for the pressure-reducing part, S6): consider a backpressure turbogenerator when a PRV has "constant steam flows of at least 3,000 pounds per hour (lb/hr), and when the steam pressure drop is at least 100 psi." No source found with a number for desuperheater or bypass stations themselves.

**Limits:** Turbine bypass and pegging stations exist for startup, trips and low load; the question is only about hours of normal-duty flow.

### H1: Is high-grade steam let down, bypassed or desuperheated for a duty a lower grade could serve?

**About:** "MAIN STEAM BY-PASS" (S0-OP005)  

**Evidence on the drawing / model**

- offpage "MAIN STEAM BY-PASS" (S0-OP005) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`offpage_connectors[S0-OP005].text`)
- Station valve: final element MSBV-1407 (asset S0-IN034) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`instruments[S0-IN034]`)
- Station valve: valve TCV-1408 (asset S0-IN035) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`instruments[S0-IN035]`)
- Spray or quench water: offpage "FWS TO STM BYPASS FWS PID 170-1" (S0-OP006) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`offpage_connectors[S0-OP006].text`)

**Data to collect**

- Steam flow through the station, with hours [not on drawing]. Where: only the valve position is recorded (TCV-1408: SYNTHETIC mapped data point TCV_1408_POS on OPEN100-Demo (open100_sheet0_demo.csv row 24: synthetic demo point (valve position)), not plant data); flow needs a meter or a calibrated valve curve; then site records: steam balance. How: Build a flow-duration curve: how many hours at each flow.
- Upstream and downstream pressure and temperature [not on drawing]. Where: a walkdown: gauges and thermometers either side of the station; then site records: header design conditions. How: Record at normal operation.
- Station rating [not on drawing]. Where: the vendor datasheet: station or desuperheater datasheet. How: Copy rated flow.
- When the station is used [not on drawing]. Where: site records: operating procedures: startup, trip, normal duty. How: Mark the station startup-only, trip-only or normal duty.

**How it is decided:** If the station passes steam only at startup or trips, close it. If it passes steady flow in normal duty, ask whether a lower-grade source (an extraction or exhaust at the right pressure) could serve the user, or whether the pressure drop could do work: S6's condition for a backpressure turbogenerator is a constant flow of at least 3,000 lb/hr and a drop of at least 100 psi.

**What the source says (S6):** Closest source wording (for the pressure-reducing part, S6): consider a backpressure turbogenerator when a PRV has "constant steam flows of at least 3,000 pounds per hour (lb/hr), and when the steam pressure drop is at least 100 psi." No source found with a number for desuperheater or bypass stations themselves.

**Limits:** Turbine bypass and pegging stations exist for startup, trips and low load; the question is only about hours of normal-duty flow.

### H1: Is high-grade steam let down, bypassed or desuperheated for a duty a lower grade could serve?

**About:** "MSS PID 140-1 (E-1) MAIN STEAM BYPASS" (S1-OP002)  

**Evidence on the drawing / model**

- offpage "MSS PID 140-1 (E-1) MAIN STEAM BYPASS" (S1-OP002) on sheet 1 at ACC-AC-150 (by the extraction's attribution) (`offpage_connectors[S1-OP002].text`)

**Data to collect**

- Steam flow through the station, with hours [not on drawing]. Where: site records: steam balance. How: Build a flow-duration curve: how many hours at each flow.
- Upstream and downstream pressure and temperature [not on drawing]. Where: a walkdown: gauges and thermometers either side of the station; then site records: header design conditions. How: Record at normal operation.
- Station rating [not on drawing]. Where: the vendor datasheet: station or desuperheater datasheet. How: Copy rated flow.
- When the station is used [not on drawing]. Where: site records: operating procedures: startup, trip, normal duty. How: Mark the station startup-only, trip-only or normal duty.

**How it is decided:** If the station passes steam only at startup or trips, close it. If it passes steady flow in normal duty, ask whether a lower-grade source (an extraction or exhaust at the right pressure) could serve the user, or whether the pressure drop could do work: S6's condition for a backpressure turbogenerator is a constant flow of at least 3,000 lb/hr and a drop of at least 100 psi.

**What the source says (S6):** Closest source wording (for the pressure-reducing part, S6): consider a backpressure turbogenerator when a PRV has "constant steam flows of at least 3,000 pounds per hour (lb/hr), and when the steam pressure drop is at least 100 psi." No source found with a number for desuperheater or bypass stations themselves.

**Limits:** Turbine bypass and pegging stations exist for startup, trips and low load; the question is only about hours of normal-duty flow.

### H2: Is high-grade (or unknown-grade) steam doing a low-temperature job?

**About:** "MSS PID 140-1 PEGGING STEAM" (S4-OP005)  

**Evidence on the drawing / model**

- offpage "MSS PID 140-1 PEGGING STEAM" (S4-OP005) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`offpage_connectors[S4-OP005].text`)

**Data to collect**

- Steam supply pressure and temperature [not on drawing]. Where: a walkdown: pressure gauge and thermometer at the supply; then site records: steam header list. How: Record supply conditions; saturation temperature follows from pressure.
- Temperature the user actually needs [not on drawing]. Where: DCS/PLC configuration: the temperature setpoint. How: Note setpoint and normal range.
- A lower-grade heat source on site (a lower steam header, exhaust or waste heat) with spare capacity [not on drawing]. Where: site records: site steam balance; then a walkdown: headers and hot streams near this user. How: List sources whose temperature exceeds the need with a practical approach.

**How it is decided:** Worth a change only if a lower-grade source can meet the needed temperature with margin, for the hours the user runs; if the steam is already the lowest grade available, close it.

**What the source says (S19, S6):** Closest source wordings: pinch potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management" (S19, no % stated); for letdown to the lower pressure, S6's turbogenerator condition. No source gives a number for matching steam grade to duty.

**Limits:** Where the model does not state the steam grade, the question is first 'what grade is it?'.

## Metering

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** "EXTRACTION STEAM ES PID 180-1" (S0-OP001)  

**Evidence on the drawing / model**

- offpage "EXTRACTION STEAM ES PID 180-1" (S0-OP001) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`offpage_connectors[S0-OP001].text`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** "WTS PID 200-4 MAKE-UP WATER" (S2-OP003)  

**Evidence on the drawing / model**

- offpage "WTS PID 200-4 MAKE-UP WATER" (S2-OP003) on sheet 2 at CND-TK-160 (by the extraction's attribution) (`offpage_connectors[S2-OP003].text`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** "WTS PID 200-4 MAKE-UP WATER" (S4-OP004)  

**Evidence on the drawing / model**

- offpage "WTS PID 200-4 MAKE-UP WATER" (S4-OP004) on sheet 4 (`offpage_connectors[S4-OP004].text`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** "MSS PID 140-1 PEGGING STEAM" (S4-OP005)  

**Evidence on the drawing / model**

- offpage "MSS PID 140-1 PEGGING STEAM" (S4-OP005) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`offpage_connectors[S4-OP005].text`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** "TBS PID 240-1 (E-1) LP EXTRACTION STEAM" (S4-OP006)  

**Evidence on the drawing / model**

- offpage "TBS PID 240-1 (E-1) LP EXTRACTION STEAM" (S4-OP006) on sheet 4 at CND-HTR-166 (by the extraction's attribution) (`offpage_connectors[S4-OP006].text`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** "TBS PID 240-1 (D-1) HP EXTRACTION STEAM" (S4-OP008)  

**Evidence on the drawing / model**

- offpage "TBS PID 240-1 (D-1) HP EXTRACTION STEAM" (S4-OP008) on sheet 4 (`offpage_connectors[S4-OP008].text`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

### C1: Is utility use (steam, cooling water, air, fuel, makeup water) metered at this user?

**About:** "WTS PID 160-1 MAKE-UP WATER" (S7-OP001)  

**Evidence on the drawing / model**

- offpage "WTS PID 160-1 MAKE-UP WATER" (S7-OP001) on sheet 7 (`offpage_connectors[S7-OP001].text`)
- Checked, none found: no flow measurement on the same stream, none on the same user for the same utility, and (on an extracted drawing) no flow element within three drawn links on the same sheet (`applies_when.without`)

**Data to collect**

- Utility flow to this user [not on drawing]. Where: a walkdown: clamp-on ultrasonic flow meter (water) or a vortex/orifice spool piece (steam, air) for a temporary reading; then utility bills or the site energy report: site-level meter readings to apportion. How: Measure flow over a representative period and compare with production.
- Who would use the reading [not on drawing]. Where: site records: energy or production reporting. How: Name the report the meter would feed.

**How it is decided:** Meter where the user is large enough that its use would change decisions; a meter nobody reads saves nothing.

**What the source says (S22, S19):** "You can't manage what do don't measure" [sic]. Buildings: "efficiency improvements of 10-20%." The guide warns "only success stories are published" and that savings come only if action is taken. LBNL Monitoring & Targeting (as reported in LBNL-56183): "Typical savings 4-17%, average 8%" (UK experience).

**Limits:** On an extracted drawing the check is 'no flow element within three drawn links on this sheet'; the meter may be on the sheet the line comes from.

## Controls and automation

### C3: Do these control valves lack position feedback?

**About:** TCV-1401, TCV-1402, TCV-1403, TCV-1406, TCV-1408, TCV-1409 and 21 more  

**Evidence on the drawing / model**

- valve TCV-1401 (asset S0-IN001) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`instruments[S0-IN001]`)
- valve TCV-1402 (asset S0-IN013) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`instruments[S0-IN013]`)
- valve TCV-1403 (asset S0-IN024) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`instruments[S0-IN024]`)
- valve TCV-1406 (asset S0-IN031) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`instruments[S0-IN031]`)
- valve TCV-1408 (asset S0-IN035) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`instruments[S0-IN035]`)
- valve TCV-1409 (asset S0-IN036) on sheet 0 at MSS-XSS-140 (by the extraction's attribution) (`instruments[S0-IN036]`)
- valve LCV-1501 (asset S1-IN001) on sheet 1 at ACC-AC-150 (by the extraction's attribution) (`instruments[S1-IN001]`)
- valve LCV-1501 (asset S1-IN007) on sheet 1 at TURBINE-EXHAUST-DUCT (by the extraction's attribution) (`instruments[S1-IN007]`)
- valve TCV-1622 (asset S2-IN011) on sheet 2 at CND-HTR-161 (by the extraction's attribution) (`instruments[S2-IN011]`)
- valve FCV-XXX (asset S2-IN012) [placeholder tag on the drawing] on sheet 2 at CND-HTR-166 (by the extraction's attribution) (`instruments[S2-IN012]`)
- valve LCV-1611 (asset S2-IN013) on sheet 2 (`instruments[S2-IN013]`)
- valve FCV-1621 (asset S2-IN022) on sheet 2 at CND-HTR-161 (by the extraction's attribution) (`instruments[S2-IN022]`)
- valve FCV-XXX (asset S3-IN006) [placeholder tag on the drawing] on sheet 3 at FWS-PU-170A (by the extraction's attribution) (`instruments[S3-IN006]`)
- valve FCV-1615 (asset S3-IN019) on sheet 3 at FWS-HTR-170 (by the extraction's attribution) (`instruments[S3-IN019]`)
- valve PCV-1703 (asset S3-IN029) on sheet 3 at FWS-PU-170A (by the extraction's attribution) (`instruments[S3-IN029]`)
- valve TCV-16013 (asset S4-IN001) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`instruments[S4-IN001]`)
- valve FCV-6508 (asset S4-IN006) on sheet 4 (`instruments[S4-IN006]`)
- valve FCV-6506 (asset S4-IN007) on sheet 4 at CND-HTR-166 (by the extraction's attribution) (`instruments[S4-IN007]`)
- valve TCV-2502 (asset S4-IN011) on sheet 4 at CND-HTR-166 (by the extraction's attribution) (`instruments[S4-IN011]`)
- valve LCV-6507 (asset S4-IN012) on sheet 4 (`instruments[S4-IN012]`)
- valve LCV-5509 (asset S4-IN013) on sheet 4 (`instruments[S4-IN013]`)
- valve FCV-18012 (asset S4-IN014) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`instruments[S4-IN014]`)
- valve PCV-14011 (asset S4-IN016) on sheet 4 at ESS-HTR-180 (by the extraction's attribution) (`instruments[S4-IN016]`)
- valve FCV-XXX (asset S7-IN001) [placeholder tag on the drawing] on sheet 7 (`instruments[S7-IN001]`)
- valve FCV-XXX (asset S7-IN009) [placeholder tag on the drawing] on sheet 7 at LUBE-OIL-COOLER (by the extraction's attribution) (`instruments[S7-IN009]`)
- valve TCV-XXX (asset S7-IN010) [placeholder tag on the drawing] on sheet 7 at LUBE-OIL-COOLER (by the extraction's attribution) (`instruments[S7-IN010]`)
- valve TCV-XXX (asset S7-IN024) [placeholder tag on the drawing] on sheet 7 at FWS-PU-170B (by the extraction's attribution) (`instruments[S7-IN024]`)
- Checked, none found: no position transmitter or indicator (ZT, ZI) drawn on these valves (`applies_when.without`)

**Data to collect**

- Positioner type and diagnostics available [not on drawing]. Where: DCS/PLC configuration: valve positioner configuration (smart positioner? HART/fieldbus diagnostics?); then maintenance records: valve records. How: List which valves report position.
- Valve stiction or backlash [not on drawing]. Where: historian / recorded data: TCV-1401: SYNTHETIC mapped data point TCV_1401_POS on OPEN100-Demo (open100_sheet0_demo.csv row 20: synthetic demo point (valve position)), not plant data; TCV-1402: SYNTHETIC mapped data point TCV_1402_POS on OPEN100-Demo (open100_sheet0_demo.csv row 21: synthetic demo point (valve position)), not plant data; TCV-1403: SYNTHETIC mapped data point TCV_1403_POS on OPEN100-Demo (open100_sheet0_demo.csv row 22: synthetic demo point (valve position)), not plant data; TCV-1406: SYNTHETIC mapped data point TCV_1406_POS on OPEN100-Demo (open100_sheet0_demo.csv row 23: synthetic demo point (valve position)), not plant data; TCV-1408: SYNTHETIC mapped data point TCV_1408_POS on OPEN100-Demo (open100_sheet0_demo.csv row 24: synthetic demo point (valve position)), not plant data; TCV-1409: SYNTHETIC mapped data point TCV_1409_POS on OPEN100-Demo (open100_sheet0_demo.csv row 25: synthetic demo point (valve position)), not plant data (no historian tag is mapped in this model for FCV-1615, FCV-1621, FCV-18012, FCV-6506, FCV-6508, FCV-XXX, LCV-1501, LCV-1611, LCV-5509, LCV-6507, PCV-14011, PCV-1703, TCV-16013, TCV-1622, TCV-2502, TCV-XXX); then a walkdown: a small step test on each loop in manual. How: Compare controller output with measured response.

**How it is decided:** Add feedback or diagnostics first on valves in energy- or safety-significant loops that show stiction or hunting.

**What the source says (S13):** "Control valve backlash and stiction... are major contributors to process variability." No % stated.

**Limits:** P&IDs often omit positioners; the model saying 'none drawn' does not mean none fitted.

## Safety questions to verify

### C9: Is a trip or interlock shown for this rotating or fired equipment?

**About:** ACC-PU-151, ACC-PU-152, ACC-PU-153, CND-PU-162, CND-PU-163, CND-PU-164 and 5 more  

**Evidence on the drawing / model**

- equipment ACC-PU-151 (asset S1-PU013) reads "ACC-PU-151 AIR COOLED CONDENSER PUMP" on sheet 1 (`units[S1-PU013]`)
- equipment ACC-PU-152 (asset S1-PU014) reads "ACC-PU-152 AIR COOLED CONDENSER PUMP" on sheet 1 (`units[S1-PU014]`)
- equipment ACC-PU-153 (asset S1-PU015) reads "ACC-PU-153 AIR COOLED CONDENSER PUMP" on sheet 1 (`units[S1-PU015]`)
- equipment CND-PU-162 (asset S2-PU001) reads "CND-PU-162 CONDENSATE PUMP" on sheet 2 (`units[S2-PU001]`)
- equipment CND-PU-163 (asset S2-PU002) reads "CND-PU-163 CONDENSATE PUMP" on sheet 2 (`units[S2-PU002]`)
- equipment CND-PU-164 (asset S2-PU003) reads "CND-PU-164 CONDENSATE PUMP" on sheet 2 (`units[S2-PU003]`)
- equipment FWS-PU-170A (asset S3-PU001) reads "FWS-PU-170A FEEDWATER PUMP" on sheet 3 (`units[S3-PU001]`)
- equipment FWS-PU-170B (asset S3-PU002) reads "FWS-PU-170B FEEDWATER PUMP" on sheet 3 (`units[S3-PU002]`)
- equipment ACW-PU-211A (asset S7-PU001) reads "ACW-PU-211A AUX COOLING WATER PUMP" on sheet 7 (`units[S7-PU001]`)
- equipment ACW-PU-211B (asset S7-PU002) reads "ACW-PU-211B AUX COOLING WATER PUMP" on sheet 7 (`units[S7-PU002]`)
- equipment ACW-PU-211C (asset S7-PU003) reads "ACW-PU-211C AUX COOLING WATER PUMP" on sheet 7 (`units[S7-PU003]`)
- Checked, none found: no safety switch (xSLL, xSHH...), burner management or trip interlock drawn for this equipment (`applies_when.without`)

**Data to collect**

- Cause-and-effect matrix and HAZOP/LOPA records [not on drawing]. Where: site records: cause-and-effect matrix, HAZOP and LOPA reports; then DCS/PLC configuration: safety system configuration. How: Confirm what protects each machine and that it is tested.

**How it is decided:** This is a question to verify, not a finding: close it once the protection is found in the cause-and-effect matrix or safety system.

**What the source says (no source):** Safety benefit; no energy source. Present it as a question to verify, not a finding.

**Limits:** P&IDs often leave trips to the cause-and-effect matrix; 'none drawn' is common and not by itself a gap.

## Not checked

- C2: the model holds no controllers; give a loop list with --loops (controller,measurement,output) to check this
- C6: the model holds no controllers; give a loop list with --loops to check this

## Questions that found nothing to ask here

No item in this model matched these questions' triggers. That is not a clean bill of health: the model may simply not show what the question looks for. E2, E3, E5, E6, E7, E8, E9, E10, E11, E12, E13, E14, E15, E16, E17, E18, E19, E20, E21, E22, E23, E24, H3, H4, C4, C5, C7, C10, C8, E25, E26, E27, E28, E29, E30, E31, E32, H5, H6, C11, C12.

## Left out of the screen

- nuclear reactor coolant, chemical and volume control and residual heat removal systems: safety-related design changes go through the licensing basis, not an energy or controls screen: COOLANT-HT-EXCH-RC-P100-X001, CVCS-AN-113A, CVCS-AN-113B, CVCS-FL-112A, CVCS-FL-112B, CVCS-HX-110, CVCS-HX-111, CVCS-ION-114A, CVCS-ION-114B, CVCS-PU-115, CVCS-PU-116, CVCS-PU-117, CVCS-VCT-118, RC-P100-X001, RCS-EX-105, RCS-PU-102A, RCS-PU-102B, RCS-SG-101, RCS-V-103, RCS-VE-104, RCS-XR-100, RCS-XR-100A, RCS-XR-100B, RCS-XR-100C, RCS-XR-100D, RCS-XR-100E, RCS-XR-100F, RHR-HX-121A, RHR-HX-121B, RHR-PU-120A, RHR-PU-120B, S6-TK003, S6-TK004

## Sources cited above

- S6: Steam Tip #20, Replace Pressure-Reducing Valves with Backpressure Turbogenerators (DOE/GO-102012-3409). https://www.energy.gov/sites/prod/files/2014/05/f16/steam20_turbogenerators.pdf (license: Public domain)
- S13: Improving Pumping System Performance: A Sourcebook for Industry, 2nd ed. (DOE + Hydraulic Institute; DOE/GO-102006-2079). https://www.energy.gov/sites/prod/files/2014/05/f16/pump.pdf (license: Federal, co-developed with HI: unclear for HI content)
- S15: Variable Speed Pumping: A Guide to Successful Applications, Executive Summary (DOE ITP with Europump/HI, DOE/GO-102004-1913, May 2004). https://www.energy.gov/sites/prod/files/2014/05/f16/variable_speed_pumping.pdf (license: Unclear (joint with Europump/HI))
- S16: Improving Motor and Drive System Performance: A Sourcebook for Industry (DOE/GO-102014-4356, Feb 2014; prepared by WSU Energy Program + NREL). https://www.energy.gov/sites/prod/files/2014/04/f15/amo_motors_sourcebook_web.pdf (license: Federal publication; contractor-prepared, so unclear but citable)
- S19: Worrell & Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for Petroleum Refineries: An ENERGY STAR Guide (LBNL-56183, Feb 2005). https://www.osti.gov/servlets/purl/862119 (license: DOE-lab (contractor) report: unclear, but freely citable. Its tables quote older secondary sources, so figures are cited as reported in LBNL-56183)
- S22: FEMP Metering Best Practices: A Guide to Achieving Utility Resource Efficiency, Release 3.0 (PNNL-23892, Mar 2015). https://www.wbdg.org/FFC/DOE/NLCRIT/mbpg_2015.pdf (license: Contractor-prepared federal guide: unclear. Its savings figures are buildings-focused)
- S24: DOE IAC/ITAC database: browse pages, download, schema document. https://itac.university/index/arc/2. (license: No license or terms stated: unclear)
