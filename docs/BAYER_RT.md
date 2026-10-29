# A real unit from the public record: the Bayer CropScience residue treater

**Status, 2026-10-28:** built: a sourced process model checked against the report's own drawing (Figure 10), a
generated P&ID of the unit checked against the same figure, and a checked digitization of the published trend
(Figure 11). Not built yet: the replay on operator screens and the walk-through.
Why this unit: [REAL_UNIT_SELECTION.md](REAL_UNIT_SELECTION.md).

On August 28, 2008, the residue treater in Bayer CropScience's methomyl unit in Institute, West Virginia, ruptured
during a restart. Two employees died: one at the scene, the second 41 days later. The U.S. Chemical Safety Board
investigated and published its report in January 2011
([report](https://www.csb.gov/assets/1/20/Bayer_Report_Final.pdf),
[CSB page](https://www.csb.gov/bayer-cropscience-pesticide-waste-tank-explosion/)). Everything here comes from that
public report. It shows what the published data showed and when. It does not judge the people who were there.

## Why this unit belongs in this project

This project builds operator screens from a process model and checks the model against what the plant publishes.
The report ties the incident to exactly that, in its own findings:

- **The unit was restarted on a new control system that operators hadn't been trained on.** "Operations personnel
  were inadequately trained to operate the methomyl unit with the new distributed control system" (key findings,
  p. 3; §3.5, pp. 58-62).
- **The screens were hard to use, and the overview screens operators asked for weren't there.** Operating some
  equipment needed at least three of five display screens; operators asked for equipment overview screens, but "the
  screens were not available for the August 2008 startup" (p. 60). Units of measure on the displays had changed
  (p. 62).
- **The control logic wasn't checked before startup.** Engineers had not verified all process controls and
  instruments in the new system (p. 35); the recirculation-flow interlock was left bypassed by the programmers
  (p. 38); the split-range temperature control was mis-programmed (p. 39).
- **An indication was wrong.** The DCS showed steam flowing to the heater while the steam block valve was closed
  (p. 71, Fig 19).

So the work asks an engineering question the report makes concrete: from the published drawing and control
narrative, can we build the model, the drawing and an overview of the unit's state, and check each against the
record? It does not claim that better screens would have prevented the explosion; the CSB found many causes, and
neither we nor the data can show that.

**How the incident is presented:** the casualties are stated once, factually, with the page (p. 1). Nobody is
named. The replay ends at the failure time and says what happened there, without effects. The incident is never a
post's hook; the lesson stays where the CSB put it, at the system level.

## The process model: `data/bayer_rt/process_model.json`

Five units (the 4,500-gallon residue treater, its vent condenser, recirculation pump, steam heater and 80 °C water
cooler), fifteen streams, six instruments, five control valves, six manual valves, two relief valves, two controllers,
three interlocks, seven operating limits and six timed events. **Every item cites the report's page or figure.**

- **Tags are assigned.** The report names instrument types (Fig 10: pressure, level, flow and temperature
  transmitters; feed, discharge and temperature control valves) but no tag numbers for the residue treater. Every
  tag here is this project's and is marked `assigned_tag`.
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
  are compared with the digitized trace. 8 of 11 agree within the pixel error. The 3 that don't are disagreements
  between the figure and the text, written up in [`fig11_check.md`](../out/bayer_rt/fig11_check.md): the figure's
  steady pressure is 25 psig where the text says 22 (the pressure scale is confirmed by the two labelled pressures,
  44 and 51.2 psig, which both agree), and its temperature runs about 2 °C below the text near the end.
- **Error stated with every value:** ±63 s, ±0.71 °C, ±0.27 psig, ±0.71 % level, ±0.71 klb/h (two pixels).
- **Reuse:** the script fetches the report from csb.gov at run time and checks its hash. The figure is not stored in
  this repository; only the digitized values, each cited to it, are.

The first run passed 6 of 11. Two of the failures were mine: the flow classifier picked up the red trace's
anti-aliased edge, and one check used the wrong time window for the statement it tested. Those were fixed. The three
remaining failures are recorded rather than calibrated away.

## Next

1. The digitized trend as a replay source for the existing replay server, with the operating limits as display
   bands, and each interlock's state derived from the published values and the model, minute by minute.
2. An overview screen of the unit generated from the model, the kind the operators asked for (p. 60), driven by
   the replay.
3. A walk-through page that puts the published timeline (pp. 38-40) next to the replayed overview. Every derived
   state either matches a statement in the report or goes on a list of disagreements.

Run: `python scripts/compare_bayer_fig10.py`, `python scripts/digitize_bayer_fig11.py` (needs PyMuPDF),
`python scripts/test_bayer_rt.py`; the drawing is regenerated by `python scripts/pipeline.py rebuild --from bayer.pid`.
