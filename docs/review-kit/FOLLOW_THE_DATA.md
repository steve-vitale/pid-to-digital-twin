# Follow the data: a lineage walk for a review day

This is the order to check things in: start where the data starts, confirm or correct each stage, and watch each
correction travel forward. It pairs with the rest of the review day kit (`README.md`, `FEEDBACK.md` and the
`CHECKLIST_*.md` files in this folder, merged separately), which says *what* to look at in each artifact and who is
qualified to decide it. This page says *in what order*, and how to prove a correction reached everything built
from it.

The stages are described in [DATA_LINEAGE.md](../DATA_LINEAGE.md). Python 3 and the standard library are enough for
everything here except the stages that need the TE replay download or a gateway.

## Three rules for the day

1. **Correct the source, never an output.** A correction goes into the model with the stage's `edited_by` tool
   (`scripts/apply_review.py`, `scripts/map_points.py`). Then rebuild. If you find yourself editing a CSV in `out/`,
   stop: the next rebuild will overwrite it, and nothing upstream learns.
2. **Rebuild from where you corrected, then check status.**
   `python scripts/pipeline.py rebuild --from <stage>` re-runs that stage and everything downstream;
   `python scripts/pipeline.py status` must then show every rebuildable stage downstream as `FRESH`.
3. **A check keeps the label of whoever made it.** Anything recorded as `confirmed` by someone who is not a process
   expert stays labelled that way in the model, in every output and in `pipeline.py confidence`: it shows as
   `confirmed (non-operations reviewer)` and is never counted as an operations review. Put the role in the reviewer
   string every time: `"<ID>, non-operations reviewer: text and legibility only"` for Track A,
   `"<ID>, process engineer"` (their actual role) for Track B. A string with no role counts as `role not stated`,
   which is not an operations review either.

## Before you start (10 min)

```sh
git rev-parse HEAD                                  # write it in the log below
python scripts/pipeline.py status > status-before.txt
python scripts/pipeline.py confidence > confidence-before.txt
```

Expect `te.bands`, `ignition.gateway`, `te.replay` and `te.source_check` to show `NEVER BUILT HERE` unless the TE
replay files are downloaded (`python scripts/fetch_te_data.py`) and someone has run the manual steps. That is
expected, not a failure. Everything else should be `FRESH`. If it isn't, find out why before reviewing anything:
a stale output is not the thing you think you are reviewing.

## Walk 1: Tennessee Eastman

| Step | Look at | You can confirm (Track A) | Only an operations reviewer can decide (Track B) | If you correct something |
|---|---|---|---|---|
| **Stage 0: the model** | `data/te_process_model.json`, `out/te_source_check.md` | each tag's description and units match the source-check report; the open question on TI-122 is still open | that a unit, stream or tag owner is right for the process | review sheet row → `apply_review.py` (dry run first), then `rebuild --from te.source` |
| Optional: re-run the source check | `python scripts/verify_te_source.py` (report only; downloads `teprob.f` if not cached) | the report is unchanged, or explain every difference | n/a | then `python scripts/pipeline.py record --stage te.source_check` |
| **Stage 1: exports** | `out/ops_review_sheet.csv`, `out/ignition/te_tags.json`, `out/pi/pi_builder_af.csv` | every tag is present, under the unit the model says, and its documentation ends with the same source check and review status as the model | which values belong on a screen; alarm priorities | never here: go back to Stage 0 |
| **Stage 2: mimic layout (proof of concept)** | `out/mimic/te_overview_layout.json`, the overview screenshots | each reading is drawn beside the unit that owns it in the model, and reads that unit's tag path | which 2–4 readings represent a unit | a display choice goes into the findings file; an ownership fix goes back to Stage 0 |
| **Stage 2: 3D scene data and LOTO candidates (proof of concept)** | `out/scene/te_scene.json`, `drafts/3d-tour/` | the tags on each unit match the model; geometry says placeholder; LOTO says inferred | whether any listed valve is a real isolation point (it is not a procedure) | findings file; ownership fixes go back to Stage 0 |
| Stages 3–5 (need the download or a gateway) | `out/ignition/normal_bands.md`, the gateway screens | the bands report matches what the screens show | alarm limits and band usefulness | `rebuild --from te.bands`, then the gateway steps in `docs/IGNITION_BUILD.md` |

**See a correction propagate.** After applying a review to the TE model:

```sh
python scripts/pipeline.py status        # te.source: changed since accepted; te.exports, te.mimic, te.scene: STALE
python scripts/pipeline.py rebuild --from te.source
python scripts/pipeline.py status        # te.source, te.exports, te.mimic, te.scene: FRESH
git diff --stat                          # the model, the regenerated outputs and the lock; nothing else
```

Then open the corrected item in each output (the Ignition tags, the PI sheet, the review sheet, the mimic layout,
the scene data) and check it moved. `scripts/test_pipeline.py` does exactly this on a temp copy with FI-110, if you
want to see the expected result first.

## Walk 2: OPEN100

| Step | Look at | You can confirm (Track A) | Only an operations reviewer can decide (Track B) | If you correct something |
|---|---|---|---|---|
| **Stage 0: drawings and answer keys** | `data/external/pid2graph/.../PID2Graph OPEN100/<n>.png`, `docs/GOAL.md` results | the drawing you review is the one the scores were computed on (sheet number) | n/a | nothing: third-party data is not corrected here |
| **Stage 1: extraction scores (recorded)** | `out/scorecard_r2-tiles-trace_holdout-a.md` | the numbers you quote are the ones in the file | n/a | nothing: re-running needs model calls |
| **Stage 2: asset model and review queue** | `out/twin/r2-tiles-trace/codex/review_queue.csv` (riskiest first), the sheet image and `svg/sheet_<n>.svg` | the tag text matches the drawing; the box is on the symbol | that a line, parent or equipment class is right; any `confirm` or `reject` | Track A: tag text only, with `OPS_scope = identifier_text`; then `apply_review.py` and `rebuild --from open100.model` |
| **Stage 3: exports** | `ignition/tags.json`, `pi/pi_builder_af.csv` next to the model | the corrected tag appears in both; the item still says `UNVERIFIED` after a Track A text fix | n/a | never here: go back to Stage 2 |
| Stage 4: gateway sheet screens | the sheet screens, `docs/screenshots/native-sheet0-not-connected.png` | unmapped instruments read "not connected" | which instruments matter on a screen | findings file |

```sh
python scripts/apply_review.py out/twin/r2-tiles-trace/codex/plant_model.json reviewed_sheet0.csv --reviewer "<ID>, non-operations reviewer: text and legibility only" --dry-run
python scripts/apply_review.py out/twin/r2-tiles-trace/codex/plant_model.json reviewed_sheet0.csv --reviewer "<ID>, non-operations reviewer: text and legibility only"
python scripts/pipeline.py rebuild --from open100.model
python scripts/pipeline.py status        # open100.model and open100.exports: FRESH
```

## Log what you confirmed at each stage

Keep one row per stage you looked at, with the review (not in the repository if it names people; use role IDs):

```
stage id | what I looked at | confirmed / corrected / not checked | track A or B | change record (out/review/...) | time (min)
```

"Not checked" is a valid entry and better than a guess. A stage you did not look at stays at the confidence it had.

## Close the day

1. `python scripts/pipeline.py status`: everything you could rebuild is `FRESH`.
2. `python scripts/pipeline.py confidence > confidence-after.txt` and compare with the morning's. Every change in the
   counts should match a row in your log.
3. Commit together: the reviewed CSV, the model change, the regenerated outputs and `pipeline/pipeline.lock.json`.
   The change record goes to `out/review/`, which is gitignored by default; keep it with the review, or add it on
   purpose with `git add -f` once it holds no names.
4. Add a journal entry saying what was reviewed, by which track, what changed, and what was **not** reviewed.
