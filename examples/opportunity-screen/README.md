# Opportunity screen: worked examples and a roll-up

**Why it matters:** the first day of an energy or controls review is mostly asking the same questions of the
drawings and writing down what to go and measure. These screens do that part, cite where every claim comes from,
and say where each missing number lives. They are question lists, not audits: nothing here computes a saving.

How the engine works, the three evidence states and how to add a question: [`docs/OPPORTUNITY_SCREEN.md`](../../docs/OPPORTUNITY_SCREEN.md).

| Folder | Model | Findings | Read it |
|---|---|---|---|
| [`te/`](te/) | Tennessee Eastman, hand-built (`data/te_process_model.json`) plus its loop list | 10 | [`te/screen.md`](te/screen.md) |
| [`bayer/`](bayer/) | Bayer residue treater from the CSB report (`data/bayer_rt/process_model.json`) | 12 | [`bayer/screen.md`](bayer/screen.md) |
| [`open100/`](open100/) | 12 OPEN100 sheets extracted to a twin (`out/twin/r2-tiles-trace/codex/plant_model.json`) plus the equipment schedules | 29 | [`open100/screen.md`](open100/screen.md) |
| [`food/`](food/) | **ILLUSTRATIVE** synthetic food plant section: ammonia refrigeration, a dryer, an oven, a fryer and utilities ([`food_plant_model.json`](food_plant_model.json)) | 24 | [`food/screen.md`](food/screen.md) |
| [`millard/`](millard/) | Two source-authored records from a historical refrigeration bulletin; E30 only, deliberately incomplete model | 1 | [Screen and first-question brief](millard/README.md) |
| [`rollup-food-bayer/`](rollup-food-bayer/) | Roll-up of the `food` and `bayer` screens as two sites | 36 across 24 questions | [`rollup-food-bayer/rollup.md`](rollup-food-bayer/rollup.md) |

The separate [two-supply regression](field-coverage/README.md) shows why grouping questions by unit must not
combine different assets' partial answers. It is a fictional software control, not another public source family.
The [fan/heater collection example](collection-basis/README.md) keeps nameplate candidates separate from
curves, actual operation and the review still needed. It also uses invented assets, without a usefulness claim.

Regenerate (the test checks these outputs byte for byte):

```sh
python -S scripts/question_engine.py --model data/te_process_model.json --loops examples/loop-audit/te_loops.csv --out examples/opportunity-screen/te
python -S scripts/question_engine.py --model data/bayer_rt/process_model.json --out examples/opportunity-screen/bayer
python -S scripts/question_engine.py --model out/twin/r2-tiles-trace/codex/plant_model.json \
    --schedule data/open100_equipment_schedule.json \
    --schedule examples/opportunity-screen/open100_schedule_fields.json --out examples/opportunity-screen/open100
python -S scripts/question_engine.py --model examples/opportunity-screen/food_plant_model.json --out examples/opportunity-screen/food
python -S scripts/question_engine.py --model examples/opportunity-screen/millard/model.json --question E30 --out examples/opportunity-screen/millard/screen
python -S scripts/question_engine.py --rollup examples/opportunity-screen/food --rollup examples/opportunity-screen/bayer \
    --out examples/opportunity-screen/rollup-food-bayer
```

[`food_plant_model.json`](food_plant_model.json) is an input and is **ILLUSTRATIVE**: written by hand for this
example, not any plant, every tag invented, nothing measured. No source P&ID was used to
build that example, so each item instead cites the public source that describes that kind of item in food plants (S25 dairy
and S26 fruit and vegetable ENERGY STAR guides, S27 the DOE burner tip sheet, with pages). Some items are drawn on
purpose to show a question staying quiet (listed under "Anti-triggers" below).

The separate [Millard example](millard/README.md) starts from an actual public report and simplified diagram.
Its two-record subset exercises E30 and carries an unresolved question into a plain brief. It does not validate
the other refrigeration/oven questions, real food-plant P&ID reading, or the completeness of its own equipment model.

[`open100_schedule_fields.json`](open100_schedule_fields.json) is an input, not an output: the printed fields of
every OPEN100 equipment schedule entry, read by eye from `data/drawings/open100_<sheet>.jpg` (one reader,
unverified). Rotating-style entries print CAPACITY, DISCHARGE, RPM and HP; vessel-style entries print OD, LENGTH and
MATERIAL; the two deaerator entries print design data as `XXX`. Every value is blank or a placeholder, because these
are template drawings. `data/open100_equipment_schedule.json` holds the tags and services; the second file
supplies each entry's complete fields object, replacing any earlier fields for that entry.

## How the findings were checked

Every finding below was checked against the model it cites (field by field) and, for OPEN100, against the drawing
image as well. **True** means the evidence quoted is what the model or drawing shows. A finding can be true and
still not worth much; those are marked **low value**. **Duplicate** means another finding covers the same physical
thing. No finding was judged false after the fixes listed under "Triggers tightened".

### Tennessee Eastman (10 findings, 10 true)

| Finding | Judgement |
|---|---|
| E6 K-101: compressor recycle valve FV-105 | True. FV-105 is "Compressor recycle valve" on K-101, the valve that spills flow back around the machine (`docs/JOURNAL.md`, topology check). The simulator models the spill-back only as a reduction of net flow, so there is no spill-back stream. Historian request names XMV(5) and XMEAS(20) |
| E18 model: reactor and condenser cooling water (TV-121, TT-121, FV-117, TT-122) while the stripper is steam heated (FV-119, FT-119) | True, and the textbook pinch question for TE. Caveat: TE's stripper "steam flow" is computed from the stripper heat duty in the simulator code |
| H2 C-101: stripper steam, grade not stated; TT-118 and FIC-119 shown | True. The model gives no steam pressure, so the first data request is "what grade is it?" |
| H4 R-101 and H4 E-101: heat rejected to cooling water, outlet temperatures TT-121 and TT-122 | True. TT-122's source name is "Separator Cooling Water Outlet Temp"; the model places it on the condenser E-101 |
| C1 R-101 and C1 E-101: cooling water to the reactor and condenser has no flow measurement | True: none of TE's measurements is a cooling water flow. The stripper steam (FT-119) is metered, so C-101 correctly does not fire |
| C2 model: FT-106, PT-107, TT-111, PT-113, FT-114, PT-116, JT-120, TT-122 read by no loop | True against the model and the 19-loop list |
| C3 model: no valve shows position feedback | True of the model; **low value** (the model has no positioners at all, so this is a blanket question) |
| C9 model: no trip drawn for K-101 | True of the model; **low value**: the simulator has process shutdown limits that the model does not list, so this is a "go and check" question |

Not found and why: no pumps are modeled, so the pump questions (E1-E4) are silent; K-101 is a process recycle
compressor, so the compressed-air questions (E19-E23, C7) are silent too.

### Bayer residue treater (12 findings, 12 true)

| Finding | Judgement |
|---|---|
| E18 model: the 80 C water cooler E-3 (U2, HV-112) and the steam heater E-2 (U1, FT-106, TV-104C, HV-108) | True, and the question asked for: one recirculation loop is heated with steam and cooled with 80 C water. The decision rule turns on timing: the heater runs at startup and the cooler at the 135 C hold, so a direct exchange only helps if the duties overlap. Any change on this reactive system needs a hazard review first |
| H4 E-3: cooler rejects heat to 80 C water; `cooling_water_C = 80` quoted as on-drawing evidence | True. Shows the "on drawing" state for the supply temperature (the model holds it); the return temperature, which is the grade of the heat on offer, is still requested |
| H2 E-2: steam heater, grade not stated; TIC-104 (setpoint 135 C) shown | True |
| C6 TV-104C: TIC-104 drives the steam valve directly; FT-106 steam flow exists but no flow controller | True. The split-range logic was also misprogrammed (p. 39, footnote 29), which the finding quotes from the model's `as_found` note on TIC-104 |
| C1 E-3: 80 C cooling water to E-3 unmetered | True. E-2's steam is metered (FT-106), so it correctly does not fire |
| E26 model: vent to the flare (S8) and reliefs to the vent header (S9, S11) carry no flow meter | True of the model |
| C2 model: PT-101, FT-103, TT-105, FT-106 read by no controller (IL-2 and IL-3 interlocks shown) | True |
| C3 model: five control valves, no position feedback | True of the model; **low value** (a report reconstruction, not a P&ID) |
| E1 P-1: LV-102 on the discharge branch, TV-104A/B on the heater and cooler legs, no drive | True of the model; **low value**: P-1 serves a 4,500-gallon vessel with batch transfers, and the split valves route flow rather than throttle it |
| E11 S1 (80 C feed) and E11 U1 (steam supply): no insulation recorded | True but **low value**: the model is built from an investigation report that never records insulation. Kept because the rule is right; the limit says "not recorded, not bare" |
| C9 model: no trip drawn for P-1 | True of the model; a question to verify only |

### OPEN100 twin (29 findings, 29 true; 3 duplicates)

| Finding | Judgement |
|---|---|
| H1 ESS-HTR-180: desuperheater with PCV-14011, FCV-18012, TCV-16013, fed by "MSS PID 140-1 PEGGING STEAM", condensate quench | True, checked on sheet 4: main steam is pressure-reduced and desuperheated to peg the deaerator. Station rating request points at the blank CAPACITY field on the sheet 4 schedule |
| H1 "MAIN STEAM BY-PASS" (sheet 0): MSBV-1407, TCV-1408 and the "FWS TO STM BYPASS" spray | True, checked on sheet 0: a turbine bypass with desuperheating spray. The decision rule closes it if the bypass runs only at startup and trips |
| H1 "MSS PID 140-1 (E-1) MAIN STEAM BYPASS" (sheet 1) | True; **duplicate**: the same bypass line arriving at the air-cooled condenser |
| H2 "MSS PID 140-1 PEGGING STEAM" (sheet 4) | True: main steam is used to heat the deaerator. **Overlaps** H1 on ESS-HTR-180 (same station, asked as a heat-grade question rather than a letdown question) |
| E1 CND-PU-162/163/164: FCV-1621 on the common discharge, no drive | True, checked on sheet 2 |
| E1 FWS-PU-170A/B: PCV-1703 on the discharge header and FCV-XXX on the line back to the deaerator, no drive | True, checked on sheet 3 (the FCV-XXX line looks like a recirculation back to the deaerator) |
| E4 ACC-PU-151..153, CND-PU-162..164, FWS-PU-170A/B, ACW-PU-211A..C (11): blank HP field | True, every schedule checked by eye. The ACC "pumps" are drawn venting to the silencer ACC-SX-154 (vacuum pumps); they still have motors, so the question stands |
| C1 makeup water (sheet 2 to CND-TK-160, sheet 4 via LCV-5509, sheet 7 via FCV-XXX), LP and HP extraction steam (sheet 4), pegging steam (sheet 4) | True: no flow element within three drawn links of each, checked on the images |
| C1 "EXTRACTION STEAM ES PID 180-1" (sheet 0) | True; **duplicate**: the pegging steam line seen from the main steam sheet |
| C3 model: 27 control-valve records, none with ZT/ZI drawn | True of the drawings; **low value** (P&IDs often omit positioners). The 27 records are 20 distinct numbered tags, one duplicate extraction (LCV-1501 twice) and 6 placeholder tags (FCV-XXX four times, TCV-XXX twice), which the evidence marks as placeholders |
| C9 model: 11 tagged pumps, no trip drawn | True of the drawings; question only |

C2 and C6 are reported as "not checked": an extracted drawing has no controllers, and no loop list was given.

**Left out:** the nuclear reactor coolant, chemical and volume control and residual heat removal systems
(sheets 5, 6, 8, 9, 10 and 11), 33 pieces of equipment in all, are excluded from every question:
safety-related design changes go through the licensing basis, not an energy screen.

### Missed (seen on the drawings, not found)

- FWS-PU-170A/B's line back to the deaerator is not flagged as a minimum-flow recirculation (E3): the drawing has no
  MIN FLOW text or restriction orifice, and the rule does not guess.
- The steam traps on the sheet 0 high-pressure drains (E8, C10): the extraction does not classify trap symbols.
- The FWS-PU-170A/B lube oil coolers on the auxiliary cooling water (H4): their text does not name the water.
  (H4 on the auxiliary cooling water cooler ACW-AXC-210 itself was a false finding in the first version: that
  air-cooled exchanger rejects the cooling water loop's heat to air, it does not receive process heat. H4 now
  never fires on a cooler of the cooling water system.)
- The turbine bypass is not asked as E7 (PRV to backpressure turbine): E7 needs header text on both sides; H1
  covers it.
- The deaerator storage tank's level-control spill to the plant drain (sheet 4, LCV-6507) is not asked as E9:
  the rule looks for condensate or trap outlets to drain.
- The ACC condensate drain through LCV-1501 to the condensate system is not asked about.

### Illustrative food plant section (24 findings)

Checked against the model it was written from. **Expected** means the finding is the question the item was drawn to
raise; **legit** means an older question fired on the new equipment and is a fair question there.

| Finding | Judgement |
|---|---|
| E27 C-201: ammonia evaporative condenser, PT-203 head pressure, PIC-203 "head pressure control at a fixed setpoint" | Expected. The head pressure request names PT-203 and the setpoint and low limit in the plant controls; the floor (hot gas defrost, liquid injection) is its own request |
| E28 model: K-201, K-202, K-203 with suction pressures PT-201, PT-202, the spiral freezer, unit cooler and cold store, TT-205 and TT-206 | Expected. One finding per model: suction levels are a plant-wide setting |
| E29 K-201 and K-202: screws with no drive (ZT-202 slide valve position shown on K-202) | Expected |
| E30 EV-201: hot gas defrost valve HGV-201, defrost started by a timer | Expected |
| E31 D-301 (exhaust S1, TT-304) and O-302 (exhaust S2, TT-305) | Expected. The fuel request names FT-301 on the dryer and, on the oven, says only a valve is drawn |
| E32 D-301 and F-303: gas-fired, no flue O2 | Expected; the decision rule and source keep the excess air a drying process needs |
| H5 model: compressors and condenser, with the CIP and wash hot water heater WH-401 as the low-grade duty | Expected |
| H6 D-301 and O-302, with WH-401 | Expected; overlaps E31 by design (E31 asks about the unit's own inlet air first) |
| C11 D-301 and O-302: no humidity measurement | Expected. The dryer's manual exhaust damper HV-304 is shown |
| C12 model: K-202, K-203 with no power measurement | Expected |
| E19, E22, E23 AC-501 (instrument air compressor) | Legit. E19 also lists the refrigeration pressure controllers PIC-202 and PIC-203 as "pressure control" because its clause looks anywhere: **low value** in that part |
| C1 O-302, F-303, WH-401: gas with no meter | Legit; the dryer's gas is metered (FT-301), so it is quiet |
| C2, C3 model | Legit; **low value** as in the other examples |
| C9 model: K-201, K-202, K-203, AC-501 with no trip drawn | Legit, a question to verify (no high discharge pressure cutout was drawn) |

**Anti-triggers, each drawn on purpose and pinned in the test:** K-203 has a drive (SC-203), so E29 is quiet there;
EV-202 starts defrost from a coil differential pressure (PDT-206), so E30 is quiet there; K-201's power is measured
(JT-201), so C12 leaves it out; the oven has a flue O2 analyser (AT-302), so E32 is quiet there; the fryer's exhaust
goes to a vapour condenser heat recovery exchanger (HX-303, the S26 p. 107 arrangement), so E31 and H6 are quiet
there; and the instrument air compressor AC-501 and its refrigerated air dryer AD-502 get no refrigeration, oven or
dryer question.

**On the other three examples:** none of the ten new questions fired on TE, Bayer or OPEN100 (TE's recycle
compressor K-101 and condenser E-101, Bayer's vent condenser E-1 and OPEN100's air-cooled condenser name no
refrigerant). Their regenerated outputs differ only in the list of questions run and quiet, and in one line of the
TE and Bayer E18 data requests, where a valve beside a drawn flow meter is no longer called "no flow measurement".

### Roll-up: food and Bayer as two sites

24 questions fired across the two; 4 fired at both (C1, C2, C3, C9). The roll-up lists every finding of both screens
exactly once (the test checks it), names the sites where each question was asked and quiet, and merges data requests
by item: C1's "utility flow to this user" shows the shared places (temporary meter, site meter readings) once for the
food site and each unmetered valve under its own finding. Its order (most sites first) is not a ranking by value.

## Triggers tightened while checking

For the next iteration after a model review, see the [review-refresh example](review-refresh/README.md). It applies
fictional decisions to the existing synthetic food model, then checks that rejected items stop triggering or
suppressing questions. Repeated review is idempotent; explicit reconfirmation restores the questions while retaining
history. This adds software evidence, not another plant or a new accuracy score.

Each of these fired wrongly on a first run and was fixed; the test keeps them quiet:

- **Food example, 2026-10-29:** E19 and E23 fired on the refrigerated compressed air dryer AD-502 (its name says
  "compressed air"), E22 was silenced by the ammonia receiver (its storage check looked for any RECEIVER), E26 read
  the dryer and fryer exhausts "to atmosphere" as relief or process vents, H5 was silenced by the fryer's vapour
  condenser heat recovery (its regex took any "condenser ... heat recovery"), E28 showed every temperature in the
  plant as a refrigerated space, and the dryer's fuel request said "only a valve is drawn on this line, with no flow
  measurement" beside the drawn gas meter FT-301. Each is fixed and pinned.

- **H4 on ACW-AXC-210** (found by an independent review): the auxiliary cooling water cooler was read as a user
  rejecting heat into cooling water, which reverses the heat flow. H4 now skips cooling water coolers, air-cooled
  exchangers and cooling towers.

- **E1 on the ACC vacuum pumps.** The pumps reached LCV-1501 only by passing through the air-cooled condenser.
  Walks along drawn links now stop at other equipment.
- **C1 on the Bayer discharge valve LV-102.** "alternate fuel tank" matched the word FUEL. Fuel now means fuel gas,
  fuel oil or natural gas.
- **E2/E3 on Bayer P-1.** Its streams are named "Recirculation", which is the process loop, not a pump bypass. The
  rules look for minimum-flow, spill-back, restriction-orifice and bypass wording instead.
- **H1 station valves on the main steam bypass** first included two drain-pot valves (TCV-1406, TCV-1409) three
  links away. Off-page anchors now show valves within two links.
- **C1 and H2 "about" text** first named whatever equipment the extraction attached an off-page connector to
  (for example the superheater MSS-XSS-140). Off-page findings now name the connector itself, and any unit
  attribution is marked as the extraction's.

Fixed after two independent reviews, each with its own regression test: a data request now stays open for any
part not on the drawing (Bayer E-3: supply temperature on the model, return temperature still requested); a flow
request never offers a valve position or output as the flow reading (TE's XMV(10) and the sheet 0 TCV_1408_POS now
say "only the valve position is recorded; flow needs a meter or a calibrated valve curve"); a cooling water outlet
temperature is not offered as the supply temperature; mapped demo points are labelled SYNTHETIC from the I/O list's
own description; a controller's `as_found` note is quoted; and empty, malformed or missing inputs are refused with
a message and exit code 2.

Also named in the test as must-not-fire: H1 on the steam superheater MSS-XSS-140 (a superheater is not a
desuperheater), E13 on "HPD BLOWDOWN TANK VENT" (not boiler blowdown), H3 on the pressurizer electric heater
RCS-EX-105 (no stated low temperature, and excluded), and the compressed-air questions on TE's recycle compressor.
