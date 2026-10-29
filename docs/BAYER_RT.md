# A real unit from the public record: the Bayer CropScience residue treater

**Status, 2026-10-29:** built: a sourced process model checked against the report's own drawing (Figure 10), a
generated P&ID of the unit checked against the same figure, and a checked digitization of the published trend
(Figure 11), replayed through the model's interlocks and limits and checked against the report's account of the
evening, and shown on a generated overview screen of the unit (proof of concept) with the report's timeline as a
walk-through beside it. The steps planned for this unit are done; what comes next is a decision, not a build.
Why this unit: [REAL_UNIT_SELECTION.md](REAL_UNIT_SELECTION.md).

On August 28, 2008, the residue treater in Bayer CropScience's methomyl unit in Institute, West Virginia, ruptured
during a restart. Two employees died: one at the scene, the second 41 days later. The U.S. Chemical Safety Board
investigated and published its report in January 2011
([report](https://www.csb.gov/assets/1/20/Bayer_Report_Final.pdf),
[CSB page](https://www.csb.gov/bayer-cropscience-pesticide-waste-tank-explosion/)). Everything here comes from that
public report. It shows what the published data showed and when. It does not judge the people who were there.

## Why this unit belongs in this project

This project builds operator screens from a process model and checks the model against what the plant publishes.
Among the report's findings, several are about exactly that (it found many other causes too):

- **The unit was restarted on a new control system that operators hadn't been trained on.** "Operations personnel
  were inadequately trained to operate the methomyl unit with the new distributed control system" (key findings,
  p. 3; §3.5, pp. 58-62).
- **The screens were hard to use, and the overview screens operators asked for weren't there.** Operating some
  equipment needed at least three of five display screens; operators asked for equipment overview screens, but "the
  screens were not available for the August 2008 startup" (p. 60). Units of measure on the displays had changed
  (p. 62).
- **The control logic wasn't checked before startup.** Engineers had not verified all process controls and
  instruments in the new system (p. 35); the recirculation-flow interlock was left bypassed by the programmers
  (p. 38); the split-range temperature control was mis-programmed (p. 39), though the CSB concluded that fault was
  not causal (p. 39, footnote 29).
- **An indication was wrong.** The DCS showed steam flowing to the heater while the steam block valve was closed
  (p. 71, Fig 19).

So the work asks an engineering question the report makes concrete: from the published drawing and control
narrative, can we build the model, the drawing and an overview of the unit's state, and check each against the
record? It does not claim that better screens would have prevented the explosion; the CSB found many causes, and
neither we nor the data can show that.

**How the incident is presented:** the casualties are stated once, factually, with the page (p. 1). Nobody is
named. The replay ends at the failure time and says what happened there, without effects. The incident is not used
as a hook anywhere in this repository; the lesson stays where the CSB put it, at the system level.

## The process model: `data/bayer_rt/process_model.json`

Five units (the 4,500-gallon residue treater, its vent condenser, recirculation pump, steam heater and 80 °C water
cooler), fifteen streams, six instruments, five control valves, six manual valves, two relief valves, two controllers,
three interlocks, seven operating limits and six timed events. **Every item cites the report's page or figure.**

- **Tags are assigned.** The report names instrument types (Fig 10: pressure, level, flow and temperature
  transmitters; feed, discharge and temperature control valves) but no tag numbers for the residue treater. Every
  tag here is this project's and is marked `assigned_tag`. The field instruments are tagged as the transmitters the
  figure shows (PT-101, LT-102, FT-103, TT-104, TT-105, FT-106); until 2026-10-29 they were tagged as indicators
  (PI-101 and so on), which an ISA-5.1 reader would take for local gauges. Each keeps its old tag as `former_tag`
  (journal entry 60). The drawing is now revision B.
- **Only what the report describes.** The level controller (automatic at about 50 percent, p. 28; in practice kept in
  manual, p. 32) and the split-range temperature controller (p. 28-29) are controllers. The feed valve has three
  interlocks (minimum temperature and maximum pressure, both safety; recirculation flow, operating; p. 30), not a flow
  loop, because the report never shows a feed flow transmitter.
- **What the report found is recorded on the item it concerns.** The minimum-temperature interlock was bypassed on
  the night (p. 69), and the recirculation-flow interlock was left bypassed by the programmers (p. 38). A manual block valve on the heater's steam supply was found closed instead of open (p. 70,
  Fig 20). The split-range temperature control had been programmed so that changing from heating to cooling closed
  the recirculation valves to both heater and cooler (p. 39, footnote 29; the CSB concluded this was not causal).
- **One open question:** the control system measured both the bulk liquid and the recirculation loop (p. 28), and the
  report doesn't say which one Figure 11 plots. Both are in the model; which is which is marked unresolved.

## Checked against the report's own drawing: `scripts/compare_bayer_fig10.py`

Figure 10 (p. 29) is a simplified piping layout drawn by someone else. `data/bayer_rt/fig10_inventory.json` records
what it shows, read from the figure alone: five units, nine terminals, fifteen lines and what sits on each, four
items mounted on the vessel. The figure has no tags, so the check is at the level it is drawn: every figure line must
be a model stream with the same two ends and the same types and numbers of valves and transmitters on it.

**The first run agreed on 10 of 21 checks** (11 of 21 after fixing one bug in the checker, which counted the steam
flow meter that the model already marks as not drawn in the figure). The model, written from the text, had the
figure wrong in four ways:

- the flow transmitter was on the pump suction; the figure puts it on the recirculation return;
- the discharge to the fuel tank came off the vessel; the figure branches it off the recirculation return;
- the heater and cooler legs returned to the vessel separately; the figure joins them into one return line;
- the condenser relief line, the heater's steam outlet and the cooling water return weren't in the model, nor were
  the three hand valves on the utility lines.

Each was corrected from the figure, with the correction noted on the item. **Now 20 of 21 agree.** The one
difference left is a blind-flanged nozzle on the vessel whose purpose the report doesn't state; it is listed, not
modelled. The figure also draws one valve, on the heater's steam outlet, shaded grey without saying why; the model
records that and does not guess.

Planted faults prove the check can fail: the transmitter moved back to the suction, the discharge taken off the
vessel again (`scripts/test_bayer_rt.py`).

## The generated drawing: `data/bayer_rt/pid/RT1.png`

The same generator that drew the Tennessee Eastman sheets draws the residue treater from the model
(`data/bayer_rt/pid_layout.json` says only where things go). It now draws the model's hand valves and relief valves,
a split-range controller with all three of its outputs, and the three interlocks on the feed valve as ISA diamonds
with their signal lines. It refuses a layout that drops or duplicates any of them, or misses a signal the model
implies. The Tennessee Eastman sheets came out byte-identical after the change.

- **Against Figure 10: 15 of 15 lines agree.** Each figure line is traced through the drawn sheet's answer key, end
  to end, and what is drawn on the path is counted. This checks the drawing's connections, not just the model's.
  Planted faults (a cut line, a valve of the wrong type) fail it.
- **The line tracer reads back exactly the key's connections.** The first layout had three utility lines crossing
  the recirculation return, and the tracer read each crossing as a junction, as a model reading the sheet would.
  With every terminal at the sheet edge, the two parallel exchanger legs force a crossing, so the cooler's water
  connections now end in utility flags beside the exchanger, as P&IDs often draw them.
- **No control valve stations,** unlike the TE sheets: Figure 10 draws none and the report doesn't describe any.

Every tag on the sheet is assigned by this project, and the title block says it is not the plant's drawing.

## The published trend, digitized: `scripts/digitize_bayer_fig11.py`

Figure 11 (p. 39) is the residue treater's DCS trend for the evening: temperature, pressure, liquid level and
recirculation flow from 17:58 to after the failure at 22:33. It is a raster image, so its values are read off the
pixels.

- **Calibrated from the figure only.** Time comes from a least-squares fit through the nine labelled tick marks;
  values from the gridlines (left axis 0 to 160, right axis 0 to 60 psig). The figure's own dotted failure line then
  lands 0.1 minutes from 22:33 before any curve is read.
- **Read by colour.** Red temperature, black pressure, blue level, brown flow. Gridlines and two annotation boxes are
  removed, and small black blobs (text, the dotted line) are dropped, because the pressure trace and the gridlines
  are the same black.
- **Checked against the text, never tuned to it.** Eleven values the report states (the figure's labels and pp. 38-39)
  are compared with the digitized trace. 8 of 11 agree within each check's stated tolerance (never tighter than the
pixel error; the tolerances are in the table). The 3 that don't are disagreements
  between the figure and the text, written up in [`fig11_check.md`](../out/bayer_rt/fig11_check.md): the figure's
  steady pressure is 25 psig where the text says 22 (the pressure scale is confirmed by the two labelled pressures,
  44 and 51.2 psig, which both agree), and its temperature runs about 2 °C below the text near the end.
- **Error stated with every value:** ±63 s, ±0.71 °C, ±0.27 psig, ±0.71 % level, ±0.71 klb/h (two pixels).
- **Reuse:** the script fetches the report from csb.gov at run time and checks its hash. The figure is not stored in
  this repository; only the digitized values, each cited to it, are.

**A digitizer bug, found by the replay (2026-10-29).** The level series had 39 single-column spikes (to about 15,
24, 61, 91, 105 and 113 percent) between 18:38 and 21:58. They were the blue fringes of the figure's black text
labels: the level mask was the one series without a minimum component size. Components under 10 px are those
fringes and over 20 px start to drop the trace's broken steep segment, so the level mask now keeps components of at
least 15 px (`level_min_component_px` in the calibration). The 11 text checks are unchanged (8 pass), because none of
them falls in those minutes; a test now fails on any one-column spike in any series.

The first run passed 6 of 11. Two of the failures were mine: the flow classifier picked up the red trace's
anti-aliased edge, and one check used the wrong time window for the statement it tested. Those were fixed. The three
remaining failures are recorded rather than calibrated away.

## The evening replayed through the model: `scripts/bayer_replay.py`

Each figure column up to the failure (17:59 to 22:33, 519 columns) gets a value and bounds per tag: its range in the
figure, widened by the digitizing error. The model's three interlocks and four operating limits are then evaluated
column by column from `data/bayer_rt/replay_rules.json`, where every rule cites the pages that bound it.

- **The report publishes no interlock setpoints.** The rules use the bounds it supports instead: the minimum
  temperature setpoint lies between about 130 and 135 C (pp. 30, 69); the maximum pressure setpoint between the
  normal 25 psig and the 50 psig allowable pressure (pp. 28, 39); recirculation flow either plainly zero or plainly
  established (p. 30). A state is *met* or *clear* only when the whole bound is on one side; otherwise *cannot tell*.
  A test fails if a straddling bound is ever called.
- **What the replay derives** (`out/bayer_rt/replay_states.md`): the minimum-temperature condition was met from the
  start of the trend until 21:25. The report says that interlock was bypassed (p. 69) and the feed had been open
  since about 4 a.m. (p. 38); the replay states the condition and makes no claim about what would have followed. The
  temperature was clear of it from 22:12. Recirculation flow was established from about 18:25, after two short
  starts the report doesn't mention, and was zero again from 22:22. The pressure left its normal level at 22:15.
- **Five limited consistency checks against the report's account all agree.** Two use proxies: the alarm check
  tests that the pressure had left its normal level, not the alarm itself, and the relief check tests that the
  pressure stops rising, not the valve's position. Pump start at 18:14 (no-flow ends
  18:14:26), flow lost at 22:21 (no flow from 22:22:29), the pressure off its normal level before the 22:25 alarm
  (22:15), the relief valve near 22:27 (pressure peaks 22:27:46 and falls), and the 155 C safe operating limit
  never reached (highest 147.8 C). **This is a consistency check, not a blind test:** I wrote the rules after
  looking at the digitized values.

`data/bayer_rt/replay.csv` holds every column with values, bounds and states.

## The overview screen: `drafts/bayer-overview/index.html` (proof of concept)

The board operators asked for equipment overview screens, and they "were not available for the August 2008
startup" (p. 60). This page is an overview of the one unit, generated the way this project builds screens:
`scripts/build_bayer_overview.py` takes the mimic's geometry from the generated P&ID's layout, the items and tags from
the model, and the values and states from the replay. Nothing on it is typed in by hand.

- **High-performance HMI practice:** grey process, colour only for an abnormal state. The 135 C line is also the
  normal operating temperature, so being above it is shown without alarm colour (the rules file says why).
- **Every value with its bound,** and every interlock as its condition (met, clear, cannot tell) beside its
  as-operated state from the report: two of the three bypassed.
- **A timeline to scrub,** with the report's events and their pages, and trends of the evening so far.
- **It stops at 22:33** and says, in one sentence with its page, what happened: the vessel ruptured and two
  employees died. No effects.
- **On a phone** the values, interlocks and limits come first; the mimic is an overview, not where values are read.

`drafts/bayer-overview/verify.mjs` reads `replay.csv` itself and checks the page in headless Chrome: all 519 rows'
values, interlock and limit states equal the file; the failure note shows at the last row only; no horizontal scroll,
no text under 12 px, no console errors at 390 and 1440 px in light and dark; mimic text at least 11 px on desktop.
16 of 16 pass. The first build passed every check and was still unreadable (mimic text about 6 px, no values on a
phone); the readability checks were added after looking at the screens.

This is not the plant's screen or its DCS, and it claims nothing about what any screen would have changed.

## The walk-through: `scripts/bayer_walkthrough.py`, on the overview page

The report times six events on the evening (pp. 38-40). For each, the walk-through takes the replayed column nearest
it (what the overview screen shows then) and the checks that test it. `data/bayer_rt/walkthrough_steps.json` names
those checks: the eleven figure-against-text checks and the five report-statement checks, each placed under exactly
one event (a test fails otherwise). Nothing is derived again; the walk-through only puts what is already checked in
the report's order. On the page, each event has a Show button and the strip under the controls steps from one event
to the next.

- **6 events, 16 checks: 13 agree, 3 disagree.** The three are the figure-against-text disagreements already written
  up above (steady pressure 25 against 22 psig; 141 C reached later than the text says; the last drawn temperature
  1.6 C under the figure's own label). No report statement disagrees with the replay.
- **20 changes of a derived interlock or limit state; the report times 3 of them** (pump start, flow lost, pressure
  off its normal level). The other 17 are listed on the page and in `out/bayer_rt/walkthrough.md`, among them the
  two short flow starts at 18:16 and 18:22 and the minimum-temperature condition leaving "met" at 21:26.
- **Changed from the plan:** the plan said every derived state would either match a report statement or go on a
  list of disagreements. A state change the report doesn't time isn't a disagreement, so it has its own list.
  Disagreements are only the checks that fail.

The verifier (`drafts/bayer-overview/verify.mjs`, now 17 checks) works out each event's nearest row from
`replay.csv` itself, and reads each agree mark from the checks' own outputs, not from the walk-through file.

## Next

Nothing more is planned to build for this unit. Open decisions for the project owner: whether the unit goes in the
series, and where.

Run: `python scripts/compare_bayer_fig10.py`, `python scripts/digitize_bayer_fig11.py` (needs PyMuPDF),
`python scripts/bayer_replay.py`, `python scripts/bayer_walkthrough.py`,
`python scripts/test_bayer_rt.py`; the drawing is regenerated by `python scripts/pipeline.py rebuild --from bayer.pid`.
