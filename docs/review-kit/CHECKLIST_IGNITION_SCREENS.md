# Checklist: operator screens (Ignition)

**Live:** Docker demo (`start-demo.bat`; `docker/README.md`), then the plant overview at
`http://localhost:8088/data/perspective/client/PIDTwin`, the unit screens from its top menu, and the drawing screens
`/open100/0` to `/11`. `fault-demo.bat` switches the replay to fault 6 (loss of A feed); `normal-demo.bat` switches
it back.
**Without the demo:** `docs/screenshots/native-overview-normal.png`, `native-overview-fault-early.png`,
`native-overview-fault-alarm.png`, `native-reactor-normal.png`, `native-reactor-fault-alarm.png`,
`native-stripper-normal.png`, `native-alarms-fault.png`, `native-sheet0-not-connected.png`,
`native-overview-390px.png`.
**Design notes:** `docs/OPERATOR_SCREENS.md` (what was chosen and why). **Data behind the numbers:**
`out/ignition/gateway/build_meta.json` (alarm setpoints and their sources).

Write findings in a plain notes file, one line per finding: screen, what you saw, track, severity
(`blocks use` / `confusing` / `cosmetic`).

## Track A: anyone

1. **Legibility.** Every label and value readable at normal viewing distance, at full screen and on the 390 px
   mobile view. Note anything you had to squint at, and anything clipped or overlapping.
2. **Units.** Every number has a unit next to it, or in its row heading.
3. **State is never ambiguous.** For each value, can you tell whether it is normal, outside its band, in alarm or
   not connected, without being told? "Not connected" must never look like a real value or like an alarm.
4. **Transcription.** Pick the reactor pressure (PI-107) and reactor temperature (TI-109). Does the alarm number
   on screen equal the setpoint in `build_meta.json`? This checks copying, not whether the limit is right.
5. **Fault story.** Switch to fault 6. Without reading the docs, can you say which unit went wrong first and
   what is in alarm? Write down what you would have guessed.
6. **Labelling honesty.** Do the screens say they are a first pass, replayed data and not reviewed, where
   someone would see it?
7. **Navigation.** Can you get from the overview to any unit and back, and to a drawing, without getting lost?

## Track B: operations reviewer

1. **Alarm limits.** For each alarmed tag, is the limit sensible for this kind of unit and service, and is the
   priority right? The TE limits come from the published process. A plant's would come from its alarm
   rationalization; say where your view differs. Changing which alarms exist is a change review (MOC) decision and is
   recorded, not applied.
2. **Which values represent each unit.** The 2 to 4 values on each overview tile were chosen by one model and
   have not been checked against another or reviewed by anyone. Would you watch these? What is missing?
3. **Normal bands.** The green bands are statistics from a recorded normal run. Would an operator read them as
   targets, limits or neither? Is that a problem?
4. **Display spans** on trends and bars: do they hide or exaggerate movement that matters?
5. **Fault 6 walk:** does the screen lead an operator to the reactor pressure problem in time? What would they do
   next, and does the screen support it?
6. Anything on the screens that an operator would act on wrongly.

Record each Track B answer against the tag or screen. Alarm priority and screen choices for the TE tags can go
straight into `out/ops_review_sheet.csv` (`OPS_alarm_priority_H_M_L_none`, `OPS_show_on_operator_screen_Y_N`);
see [FEEDBACK.md](FEEDBACK.md).
