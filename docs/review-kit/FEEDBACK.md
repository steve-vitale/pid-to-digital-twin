# How review results feed back

Review sheets go back into the model through `scripts/apply_review.py`. Everything else (screens, PI AF, 3D stills)
goes into a findings file and becomes issues or fixes. Full rules: [REVIEW_LOOP.md](../REVIEW_LOOP.md).

## 1. Review sheets (extraction queue, TE sheet)

Always dry-run first. The script refuses the whole sheet if any row is invalid, and lists why.

```sh
# Extracted twin, sheet 0 (copy of review_queue.csv with the OPS_ columns filled in)
python scripts/apply_review.py out/twin/r2-tiles-trace/codex/plant_model.json reviewed_sheet0.csv --reviewer "<name or ID>, <role>" --dry-run
python scripts/apply_review.py out/twin/r2-tiles-trace/codex/plant_model.json reviewed_sheet0.csv --reviewer "<name or ID>, <role>"
python scripts/generate.py out/twin/r2-tiles-trace/codex/plant_model.json

# Tennessee Eastman (copy of out/ops_review_sheet.csv)
python scripts/apply_review.py data/te_process_model.json reviewed_te.csv --reviewer "<name or ID>, <role>" --dry-run
python scripts/apply_review.py data/te_process_model.json reviewed_te.csv --reviewer "<name or ID>, <role>"
python scripts/generate.py
```

The change record goes to `out/review/<date>-<model>.md` and `.json`. The model file is changed in place, so
`git diff` shows exactly what the review did. Commit the reviewed CSV, the model change and the change record
together.

**Keep the two tracks apart in the record:**

| Track | `--reviewer` role | What the sheet may contain |
|---|---|---|
| A (anyone) | say so, e.g. `"<ID>, non-operations reviewer: text and legibility only"` | `A:` notes in `OPS_notes`; tag-text corrections with `OPS_scope = identifier_text` only. **Never** `confirm`, `reject`, screen or alarm choices |
| B (operations) | their actual role, e.g. `"<ID>, process engineer"` | any decision: `confirm`, `correct`, `reject`, `OPS_show_on_operator_screen_Y_N`, `OPS_alarm_priority_H_M_L_none` |

Apply Track A and Track B as **separate runs** with separate `--reviewer` strings, so the history shows who
decided what. A Track A identifier-text correction leaves the item's review status unchanged; only Track B can
make an item `confirmed`.

**Read the TE sheet's `model_status` correctly:** `confirmed` there means checked against the simulator source
code (`scripts/verify_te_source.py`), not reviewed by operations. The operations decision is the `OPS_` columns.

**Alarm changes:** setting the priority of an existing alarm is applied. Adding or removing an alarm is recorded
as needing a change review (MOC) and is not applied.

## 2. Everything that is not a review sheet

Write one line per finding in a findings file (e.g. `review-findings-<date>.md`, kept with the review):

```
<artifact> | <where: screen / tag / still / file:line> | <what was seen> | track A or B | blocks use / confusing / cosmetic
```

Then:
- **screens:** fixes go into the screen generator (`scripts/ignition/`), and the next native gateway pass checks
  them (`docs/IGNITION_ACCEPTANCE.md`);
- **PI AF:** UOM and template answers go into `docs/PI_MAPPING.md` and, once confirmed by a PI administrator,
  into the exporter. Re-run `python scripts/check_pi_export.py` afterwards;
- **3D stills:** findings go into `drafts/3d-tour/REVIEW_NOTES.md` (the tour is merged as a proof of concept; the notes stay the review record);
- **anything about the TE process itself** (topology, purposes) is checked against the simulator source before it
  changes the seed model, and the journal records it.

## 3. Close the session

- Fill in [TIMING_LOG.csv](TIMING_LOG.csv): minutes, items looked at, findings, and status with a reason for
  anything not complete. Use role IDs, not names.
- Add a journal entry: what was reviewed, by which track, what changed, and what was **not** reviewed. Never
  describe a Track A pass as an operations review.
