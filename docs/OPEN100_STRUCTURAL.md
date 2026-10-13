# OPEN100 without process data: what the drawings alone support

The OPEN100 track is 12 real P&IDs, extracted and scored, with **no process data**: no historian, no I/O list, no
setpoints. Until this page, its only screens were the greyed drawings with "not connected" beside each instrument,
while the Tennessee Eastman track (process knowledge, no drawing) got the mimic, the 3D tour, the purpose cards and
the LOTO mockup. Most of those don't need process data. They need structure, and the drawings carry structure.

This page covers the structural deliverables built from the drawings alone, how far each one goes, and how it was
checked. The [deliverables matrix](../README.md#what-you-can-do-with-only-drawings-only-process-knowledge-or-both)
puts both tracks side by side.

| Deliverable | Output | Still |
|---|---|---|
| Flow direction on connections | [`out/open100_structural/flow_direction.json`](../out/open100_structural/flow_direction.json) | [evidence on sheet 5](screenshots/open100/flow-evidence-sheet5.png) |
| Plant structure: areas, purposes, stitching, tour order, isolation points | [`out/open100_structural/plant_structure.json`](../out/open100_structural/plant_structure.json) | |
| Process mimic, plant overview and 12 area views | [`out/open100_structural/mimic/views.json`](../out/open100_structural/mimic/views.json) | [overview](screenshots/open100/mimic-plant-overview.png), [area, sheet 7](screenshots/open100/mimic-area-sheet7.png) |
| 3D orientation tour | [`out/open100_structural/3d/open100_scene.json`](../out/open100_structural/3d/open100_scene.json) | [overview](screenshots/open100/3d-00_overview.jpg), [stop 1](screenshots/open100/3d-01_stop_sheet3.jpg), [stop 5](screenshots/open100/3d-05_stop_sheet7.jpg) |
| LOTO isolation view on the real drawing | [`out/open100_structural/loto_isolation_points.csv`](../out/open100_structural/loto_isolation_points.csv) | [sheet 7](screenshots/open100/loto-isolation-sheet7.png) |

Nothing on this page is a live or historical value, and no screen here has been imported into a gateway.

## 1. Flow direction

**The answer keys can't score direction.** Every PID2Graph OPEN100 graphml says `edgedefault="undirected"`. Its 451
`arrow` nodes have a position and no orientation, and some of them are text leaders rather than flow arrows. So the
keys can score whether an arrowhead was *found*, not which way it points. Direction is checked by a blind spot check
instead (below), and the result is labelled as that, not as accuracy against a key.

**What the drawing shows, and how the code reads it** (`scripts/flow_direction.py`, no AI):

| Evidence | Rule | Links it decides |
|---|---|---|
| Arrowhead on the pipe | Ink sticking out on both sides of a straight run, tapering to a tip, is an arrowhead pointing at its narrow end. It splits the line network: symbols behind it flow to symbols ahead of it | 45 first-hand; 237 weaker (below) |
| Off-page connector flag | The pentagon points the way flow goes: tip toward the attached line means flow enters the sheet, tip away means it leaves | 52 first-hand; 79 weaker |
| Pump ports | Centrifugal convention: discharge at the top of the casing, suction at the side. Fires only when a pump has one line network at its top and another at a side | 7 (rule fired on 3 of the 20 pumps on a traced line) |
| Valve continuity | What flows into an in-line valve with exactly two process connections flows out of the other side. Seeded only from first-hand evidence, never from another propagated direction | 11 |

"First-hand" means the arrowhead or flag sits on the pipe between the two symbols, with no branch in between.
"Weaker" (`*_via_junction`) means the arrow is on one symbol's own pipe, but the other symbol is beyond a branch,
so the flow passing the arrow may not be the flow between them. Instrument taps and dangling stubs don't count as
branches. Where two pieces of evidence in the deciding tier disagree, the link is a **conflict** and shows no arrow.

**Not used, and why:** tank nozzle position (bottom inlets and top returns are both common, and nozzle labels such
as N1 carry no in/out meaning without the data sheet); instrument links (they are measurement or signal
connections, so process flow direction doesn't apply); check valves (the extraction has a single "valve" class).

**Results**, on the twin's 1,881 connections:

| | Links |
|---|---|
| Directed | **361** (84 first-hand, 266 weaker, 11 by valve continuity) |
| Conflict (evidence disagrees: shown without arrow) | 101 |
| Undirected (no evidence: shown without arrow) | 1,419, of which 748 are instrument links |
| Process links (not instrument) directed | **361 of 1,133 (32%)** |

**Arrowhead detection against the keys' arrow nodes** (position only; settings chosen on sheets 0-5):

| Sheets | Detections | On a key arrow (precision) | Key arrows found (recall) |
|---|---|---|---|
| 0-5 (tuning) | 124 | 98 (79%) | 100 of 214 (47%) |
| 6-11 (held out) | 211 | 176 (83%) | 182 of 237 (77%) |

Of the 335 arrowheads found, 184 orient links. The rest sit on the drawing frame (31), at a line end with nothing
beyond (59), next to branches on both sides (35), with no symbol on one side (23), or in a loop (3).

**Off-page flags.** All 95 flags got a reading. I looked at every one: each matched the drawn convention (tip and
attached line). Where an arrowhead sits on a flag's line, they agree.

**Independent sources agree.** Arrowheads and flags are found by different code from different ink. On the 70 links
where both give a direction, they agree on all 70.

**How right is it: the blind spot check** (`scripts/direction_spot_check.py`). A stratified random sample of 65
directed links (fixed seed), drawn as crops of the original drawing with the two symbols outlined A and B. Which one
is A was a coin flip. Readers saw only the crop and the question, never the inferred direction, and could answer
UNCLEAR.

| Source | Sampled | GPT: agree / unclear / disagree | Claude: agree / unclear / disagree | Confidence carried (lower 95%) |
|---|---|---|---|---|
| Arrowhead, first-hand | 15 | 15 / 0 / 0 | 15 / 0 / 0 | 0.89 |
| Off-page flag, first-hand | 10 | 10 / 0 / 0 | 10 / 0 / 0 | 0.84 |
| Pump ports | 7 | 5 / 2 / 0 | 5 / 2 / 0 | 0.72 |
| Arrowhead, across a branch | 15 | 10 / 5 / 0 | 5 / 10 / 0 | 0.80 |
| Off-page flag, across a branch | 10 | 7 / 3 / 0 | 10 / 0 / 0 | 0.82 |
| Valve continuity | 8 | 7 / 1 / 0 | 5 / 3 / 0 | 0.76 |

No reading by either model disagreed with the code. The two readers agreed with each other on all 46 crops where both decided; on 19 crops at least one said UNCLEAR, mostly across-a-branch links, where the crop can't show which branch the flow takes.

The confidence on each link is the **lower end of the 95% interval** for its source, not the raw agreement: with
10-30 readings, a perfect score is not certainty. The readers are AI models looking at the same drawing, not plant
engineers. This shows that a careful reader of the drawing agrees with the code. It does not show that the drawing
matches the plant.

## 2. Plant structure

`scripts/open100_structure.py` turns the twin and the directions into one plant:
- **Areas.** One per sheet. Names come from the title block (sheets 0-5, read by a person into
  `data/sheet_registers/open100_dev.csv`) or from what other sheets' off-page connectors call the drawing (4 more).
  Sheets 8 and 9 have no readable drawing number, so they stay unnamed.
- **Stitching.** 45 connectors find their target sheet: 14 through the twin's pairing, 31 more through the drawing
  number in their text. Many drawing numbers use en dashes ("PID 110–1"), which the twin's converter did not read as
  numbers. The result is 38 sheet-to-sheet connections, 36 of them with a direction from the flags.
- **Tour order.** The order follows those 36 directed connections: feedwater, main steam, air-cooled condenser,
  condensate, then the cooling-water, reactor-coolant and chemical-control sheets. The plant loops (condensate to
  feedwater to steam and back), so the starting point is a choice; the order is labelled as inferred.
- **What each piece of equipment is for.** First from the **equipment schedule printed along the bottom of each
  drawing** ("CVCS-PU-115 SERVICE: POSITIVE DISPLACEMENT CHARGING PUMP"). The extraction never read this text, so
  `scripts/transcribe_equipment_schedules.py` had Claude transcribe it (`data/open100_equipment_schedule.json`,
  unverified, one list per sheet). Then from the equipment's own words, then the tag's type code, then a generic class
  description. Of the 74 pieces of equipment: 49 from the schedule, 6 drawing labels, 4 tag codes, 15 generic. Every
  purpose carries its source.
- **Equipment-to-equipment paths.** 238 paths through valves and line items, 164 with a direction, 46 without, 28 in
  conflict.

## 3. Process mimic

`scripts/ignition/build_open100_mimic.py` builds a plant overview and 12 area views from the same Perspective
components as the TE screens (`build_hmi.label`, `view`, `tag_binding`), in the same style: grey and calm, shapes
labelled illustrative, no animation. An arrow appears only where `display_contract.stream_is_directed` allows it.
Every value is bound to the same OPEN100 tags as the drawing screens, through the same transform, and reads **not
connected**. The overview shows the 12 areas in tour order, with arrows between areas where flags show the direction,
and each area's inflows and outflows. An area view lays its equipment out where it sits on the drawing and draws the
nearest connections that join everything up. The full set of paths stays in the JSON, and the screen says how many it
left out.

The stills are **offline renders** (`scripts/render_open100_structural.py`: the TE preview's renderer, screenshotted
by a headless browser). These views are not part of the 23-view project that passed native acceptance, and they have
not been imported into a gateway.

## 4. 3D orientation tour

`scripts/build_open100_3d.py` writes a scene for the Blender renderer copied unchanged from the 3D tour prototype
(`scripts/blender_tour_template.py`, `scripts/label_layout.py`). The 12 areas sit on a plot in tour order. Equipment
is placed by its drawing position, as a placeholder shape for its class and tag type. Pipes have chevrons only where
the path's direction was read from the drawing. Each stop carries a purpose card, every source named. Instrument
markers are dark and labelled "not connected", and every still is badged STRUCTURE ONLY · NO PROCESS DATA. Three
stills: the overview, stop 1 (feedwater) and stop 5 (aux cooling water). No video.

Geometry is a placeholder throughout: a P&ID gives topology and tags, not layout, sizes, elevations or routes.

## 5. LOTO isolation view

Here the drawing is real. The isolation points come from the extracted symbols, each with its sheet and box:

| Kind | Count | Note on the drawing view |
|---|---|---|
| Manual valve in a line | 139 | candidate block valve |
| Motor-operated valve | 35 | isolation point, and its motor is an energy source of its own |
| Motor-driven equipment (pumps) | 30 | electrical isolation at its breaker, not on the drawing |
| Line from another system | 87 | energy can come in from there; isolate there or at the first block valve |
| Line to a vent or drain system | 8 | |
| Valve with one connection | 21 | likely a vent, drain or test point |
| Control valve | 45 | listed so it is **not** mistaken for an isolation device |
| Relief device | 19 | never used for isolation |

The [sheet 7 view](screenshots/open100/loto-isolation-sheet7.png) numbers each point on the original drawing. It is
framed as on the TE mockup: **a design mockup, not a procedure.** A real lockout/tagout procedure comes from the
site's energy-control program (OSHA 1910.147), its verified P&IDs and an authorized person. Missed symbols mean
missed isolation points: a valve the extraction didn't see isn't on this list.

## Reproduce

    python scripts/flow_direction.py --overlay 5        # ~1 min; re-traces all 12 sheets, checks links match the twin
    python scripts/open100_structure.py
    python scripts/render_open100_structural.py --png   # needs Edge or Chrome for the PNGs (BROWSER_EXE)
    python scripts/build_open100_3d.py --blender PATH/blender.exe
    python scripts/test_open100_structural.py

The spot check (`direction_spot_check.py make | ask-claude | ask-gpt | score`) and the schedule transcription make
model calls (claude CLI, Codex CLI). Their outputs are committed, so the steps above don't repeat them.

## Limits

- Direction is known on a third of the process links. The rest are honestly undirected, and most are undirected
  because the drawing shows no arrow there.
- The "weaker" readings (266 links) are the least checked: the readers left half of the sampled ones unclear.
- The tracer joins crossing lines, so a few networks merge two pipes. Loops are caught; crossings without loops are
  not.
- Equipment purposes from the schedule are a model transcription, and the tag-code meanings are a common reading,
  not the site's tag standard.
- No screen here was imported into a gateway, reviewed by operations or checked against the plant.
