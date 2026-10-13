# Brief for an operations reviewer

Thank you for looking at this. It should take about 90 minutes.

## What this is

An open-source experiment: AI models read process and instrumentation diagrams (P&IDs) and turn them into a
digital-twin starter kit: an asset list, operator screens for Ignition, a PI AF hierarchy, and a draft 3D
orientation tour. Two sources are used:
- **Tennessee Eastman (TE):** a published benchmark chemical process (Downs and Vogel, 1993) with an open
  simulator, standing in for a plant;
- **public engineering drawings** from the PID2Graph dataset.

**No real plant is involved. Nothing connects to any control system.** The live values are replays of a recorded
simulation.

## Why you

Nobody with operations experience has looked at any of it. Models and code checks have, and we know where they stop:
they can say a tag was copied correctly, not whether an alarm limit makes sense or an isolation point is the
right one. That is the part we are asking you for.

## What we ask

Four areas, in this order. Answer only what is in your experience; "not my area" and "I don't know" are useful
answers.

1. **Alarm limits and screen values (30 min).** Reactor pressure has a high alarm at 2,895 kPa g and the simulator
   shuts down at 3,000 kPa g; reactor temperature shuts down at 175 °C. Are the alarms and priorities sensible?
   Are the 2 to 4 values shown for each unit the ones you would watch? Watch the "loss of A feed" fault replay.
   Does the screen lead you to the problem in time?
2. **Topology (25 min).** On one drawing (sheet 0), are the connections the model found the ones the drawing
   shows? On the TE flowsheet, is the flow (feeds, reactor, condenser, separator, compressor, stripper, recycle,
   purge) right?
3. **Lockout/tagout view (15 min).** A design mockup marks 11 points to isolate. Are these the right *kinds* of
   energy source for these units, and what is missing? This is a question about a training view. It is not a
   procedure.
4. **Hazard examples and unit descriptions (15 min).** Each tour stop cites a public incident (CSB, OSHA or EPA)
   and a one-sentence description of what the unit does. Are they relevant and right? Could any of them mislead
   a new operator?

## What happens to your answers

The session runner writes your decisions into the review sheets under your name and role (or a pseudonym, if
you prefer) and applies them with a script. Every change is recorded with who decided it and when. Corrections
show up in the generated screens and files. Anything that would change which alarms exist is recorded as needing a change review
(MOC), not applied. Your name only appears in the project if you agree to it.

## What we are not asking

- To approve anything for use at a plant. Nothing here is fit for operation, and your review does not make it so.
- To review code, the AI models, or the 3D geometry (sizes and pipe routes are placeholders by design).
- To share anything about your own site.
