# A real unit from the public record: the Bayer CropScience residue treater

**Status, 2026-10-28:** started. Built: a sourced process model and a checked digitization of the published trend.
Not built yet: the generated drawing and its comparison with the report's figure, and the replay on operator screens.
Why this unit: [REAL_UNIT_SELECTION.md](REAL_UNIT_SELECTION.md).

On August 28, 2008, the residue treater in Bayer CropScience's methomyl unit in Institute, West Virginia, ruptured
during a restart. Two employees died: one at the scene, the second 41 days later. The U.S. Chemical Safety Board
investigated and published its report in January 2011
([report](https://www.csb.gov/assets/1/20/Bayer_Report_Final.pdf),
[CSB page](https://www.csb.gov/bayer-cropscience-pesticide-waste-tank-explosion/)). Everything here comes from that
public report. It shows what the published data showed and when. It does not judge the people who were there.

## The process model: `data/bayer_rt/process_model.json`

Five units (the 4,500-gallon residue treater, its vent condenser, recirculation pump, steam heater and 80 °C water
cooler), eleven streams, six instruments, five control valves, three manual valves, two relief valves, two controllers,
three interlocks, seven operating limits and six timed events. **Every item cites the report's page or figure.**

- **Tags are assigned.** The report names instrument types (Fig 10: pressure, level, flow and temperature
  transmitters; feed, discharge and temperature control valves) but no tag numbers for the residue treater. Every
  tag here is this project's and is marked `assigned_tag`.
- **Only what the report describes.** The level controller (automatic at about 50 percent, p. 28; in practice kept in
  manual, p. 32) and the split-range temperature controller (p. 28-29) are controllers. The feed valve has three
  interlocks (minimum temperature and maximum pressure, both safety; recirculation flow, operating; p. 30), not a flow
  loop, because the report never shows a feed flow transmitter.
- **What the report found is recorded on the item it concerns.** The minimum-temperature interlock was bypassed on
  the night (p. 69). A manual block valve on the heater's steam supply was found closed instead of open (p. 70,
  Fig 20). The split-range temperature control had been programmed so that changing from heating to cooling closed
  the recirculation valves to both heater and cooler (p. 39, footnote 29; the CSB concluded this was not causal).
- **One open question:** the control system measured both the bulk liquid and the recirculation loop (p. 28), and the
  report doesn't say which one Figure 11 plots. Both are in the model; which is which is marked unresolved.

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

1. A drafting layout and the generated drawing, then a structured comparison with Fig 10: every instrument type,
   valve and connection the figure shows.
2. The digitized trend as a replay source for the existing replay server, with the operating limits as display
   bands and the interlock states derived from the published values.
3. A walk-through page that puts the published timeline (p. 38-40) next to the replayed screens.

Run: `python scripts/digitize_bayer_fig11.py` (needs PyMuPDF), `python scripts/test_bayer_rt.py`.
