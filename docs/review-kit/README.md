# Review day kit

Nobody with operations knowledge has reviewed anything in this project yet. This kit gets the first review done in
one sitting at a desktop, and makes sure each check is done by someone qualified to make it.

There are two tracks, and they must not be mixed:

| Track | Who | What they can decide | What they must not decide |
|---|---|---|---|
| **A. Anyone** | Any careful reader (the project owner, a developer) | Does the text match the drawing? Is the box on the symbol? Can the label be read? Is the screen clear about what it shows? | Whether a line, alarm, isolation point or hazard is *right for the plant* |
| **B. Operations** | Someone who has run, engineered or supervised a process plant (operator, process engineer, controls engineer, process-safety engineer) | Topology, alarm limits and priorities, which values belong on the screen, LOTO isolation points, hazard relevance, unit purpose text | Nothing outside their own experience; "not my area" is a valid answer |

A Track A pass is **not** an operations review. Nothing in Track A may be recorded as `confirm`; see
[FEEDBACK.md](FEEDBACK.md).

## What you need

- This repository checked out, with Python 3 (stdlib is enough for everything except the optional live screens).
- A spreadsheet program (Excel, LibreOffice) and an image viewer.
- Optional: the Docker demo for live screens (`start-demo.bat`, see `docker/README.md`). Without it, use the
  screenshots in `docs/screenshots/`.
- A copy of [TIMING_LOG.csv](TIMING_LOG.csv) for the session.

## The sitting (Track A, about 2 h 20 min)

| Start | Block | Minutes | Checklist |
|---|---|---|---|
| 0:00 | Set up: open the files below, copy the timing log, note the repository commit (`git rev-parse HEAD`) | 10 | this page |
| 0:10 | Extraction review queue, drawing sheet 0 | 45 | [CHECKLIST_EXTRACTION_QUEUE.md](CHECKLIST_EXTRACTION_QUEUE.md) |
| 0:55 | Operator screens (Ignition) | 30 | [CHECKLIST_IGNITION_SCREENS.md](CHECKLIST_IGNITION_SCREENS.md) |
| 1:25 | PI AF export | 20 | [CHECKLIST_PI_AF.md](CHECKLIST_PI_AF.md) |
| 1:45 | 3D tour draft stills | 20 | [CHECKLIST_3D_STILLS.md](CHECKLIST_3D_STILLS.md) |
| 2:05 | Feed results back (dry run, then apply) | 15 | [FEEDBACK.md](FEEDBACK.md) |

Stop a block when its time is up, even if unfinished, and log it as unfinished with a reason. An honest partial
review is worth more than a rushed complete one.

## Track B (about 90 min, a separate sitting with the operations reviewer)

Hand them [OPS_REVIEWER_BRIEF.md](OPS_REVIEWER_BRIEF.md) beforehand. In the sitting, work through the **Track B**
section of each checklist, in this order: alarm limits and screen values (30), topology on sheet 0 and the TE
flowsheet (25), LOTO isolation points (15), hazard citations and purpose cards (15), wrap-up (5). Write down
what they say in their words. They do not have to touch the files: the person running the session records the
decisions, and the `--reviewer` string names the person who made them.

## Timing: what this does and does not measure

[TIMING_LOG.csv](TIMING_LOG.csv) records active minutes per block, using the field names and status values of the
[review-effort protocol](../REVIEW_EFFORT_PROTOCOL.md): `preparation_minutes`, `review_minutes`, and status
`complete`, `abstained`, `failed` or `missing`, with a `reason` for anything not complete. One review day is a
**pilot timing log, not a study.** The protocol's comparison needs a frozen protocol, two workflows, different
reviewers per arm and an independent auditor (sections 1 to 3 there), and none of that exists after one sitting.
Put a role ID (e.g. `A-1`, `B-1`) in `reviewer_role_id`, never a name. Use the log to plan a real study (how long
each artifact actually takes) and to report honestly what was looked at. Do not quote its minutes as a time saving.

If a study is later run, start from the protocol itself:

```sh
python -S scripts/review_effort.py template > review-protocol.json   # fill in and freeze before anyone starts
python -S scripts/review_effort.py validate review-protocol.json
python -S scripts/review_effort.py report review-protocol.json review-records.json > review-report.json
```

## Files under review

| Artifact | File |
|---|---|
| Extraction review queue (12 drawings, riskiest first) | `out/twin/r2-tiles-trace/codex/review_queue.csv` |
| Drawing images | `data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/<n>.png` |
| Extracted overlay per drawing | `out/twin/r2-tiles-trace/codex/svg/sheet_<n>.svg`; side by side: `docs/screenshots/before-after-sheet0.png` |
| Tennessee Eastman review sheet (seed model, alarms) | `out/ops_review_sheet.csv` |
| Operator screens | live demo, or `docs/screenshots/native-*.png` and `hmi-*.png`; design notes `docs/OPERATOR_SCREENS.md` |
| PI AF export | `out/pi/pi_builder_af.csv`; what is verified: `docs/PI_MAPPING.md` |
| 3D tour stills (draft) | `drafts/3d-tour/*.jpg`; review notes `drafts/3d-tour/REVIEW_NOTES.md` |
