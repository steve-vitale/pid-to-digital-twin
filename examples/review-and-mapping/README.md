# Review decisions back into the model, and instruments mapped to signals

**Why it matters:** A model is only useful once someone who knows the unit has checked it and its instruments point at real signals. This records who decided what and when, so every change can be traced.

A worked example on the sheet-0 bundle from [own-drawing](../own-drawing/README.md). **The review here is an
illustration, not a real review:** the reviewer is labelled "R1 (illustrative example, not a real review)", and the
one corrected tag (`MSCV-1401`) is invented to show the mechanism; a real one comes from the plant's valve list.
The I/O list is the repository's synthetic demo list.

## What's here

For a hand-built process model, the [seed refresh example](seed-refresh/README.md) carries fictional review
decisions through the next SVG, Ignition and PI bundle, including unknown ownership, unchanged address claims,
obsolete generated files and explicit reinstatement. The sheet-0 example below remains an extracted-twin example.

| File | Made by | What it shows |
|---|---|---|
| `reviewed_sheet0.csv` | a reviewer, filling the `OPS_` columns of `review_queue.csv` | 4 decisions: 2 confirmed, 1 rejected (a second read of the same bubble), 1 corrected (a placeholder tag) |
| `records/2026-10-29-bundle.md` and `.json` | `apply_review.py` | The dated change record: who decided what, and what changed |
| `mapping_dry_run.md` | `map_points.py --dry-run` | 25 instruments matched to I/O points, 10 on the drawing but not in the list, 2 the other way round; nothing written |
| `graph_after_review.json` | `graph_export.py --reviews records` | The model as a graph after the review: the rejected item shows `rejected`, the corrected valve keeps its old tag as an alias, and the 4 decisions are events |
| `REPORT_after_review.html` | `generate.py` on the reviewed model, then `deliverable_report.py` | The client report after the review: "partly reviewed", the 4 decisions listed with what the sheet now says, and left out of the items to check first. Run before regenerating, the report refuses: the review sheet no longer matches the model |
| `reviewed_pi_sheet0.csv`, `pi_mapping_dry_run.txt` | a reviewer, then `map_pi_points.py --dry-run` | Two PI points attested by a reviewer (illustrative names, not a real archive), and the mapping plan; nothing written |
| [`out/review_kit/sheet-8/`](../../out/review_kit/sheet-8/README.md) | `review_kit.py make` | A one-sheet timed-review kit: the queue, the drawing, the overlay and a timer that logs itself. Ready to run, not run |

## Reproduce it

From the repository root, on a fresh copy of the example bundle (the review edits the model in place). The bundle
folder must be called `bundle`, as here: its name is written into the change record (`records/2026-10-29-bundle.*`)
and the reports. `bundle/` and `my-review/` must not exist yet; delete both afterwards.

```sh
python -S scripts/import_site_drawing.py --manifest examples/own-drawing/manifest.json --out bundle
python scripts/apply_review.py bundle/plant_model.json examples/review-and-mapping/reviewed_sheet0.csv --reviewer "R1 (illustrative example, not a real review)" --date 2026-10-29 --record-dir my-review/records
python scripts/map_points.py bundle/plant_model.json data/io_lists/open100_sheet0_demo.csv --sheets 0 --dry-run > my-review/mapping_dry_run.md
python scripts/graph_export.py bundle/plant_model.json --reviews my-review/records --out my-review/graph_after_review.json
python scripts/generate.py bundle/plant_model.json
python scripts/deliverable_report.py bundle --out my-review/REPORT_after_review.html
python -S scripts/map_pi_points.py bundle/plant_model.json examples/review-and-mapping/reviewed_pi_sheet0.csv --dry-run > my-review/pi_mapping_dry_run.txt
```

Every file in `my-review/` is then byte-identical to the one committed here
(`scripts/test_deliverable_report.py` checks this).

Add `--dry-run` to `apply_review.py` to see the changes without writing them. If some rows are refused (an unknown
item, a bad decision, a correction with no value), the valid rows are still applied and the run exits 1 listing the
refusals: fix the sheet and apply it again, which leaves the rows already applied unchanged. Mapping without `--dry-run` writes the
addresses into the model; regenerate the exports afterwards with `generate.py`.

For PI, a reviewer supplies the archive, point, type and unit for each instrument (the last command above).

## What it doesn't show

A real reviewer's time, a real I/O list, or anything about whether the mapped points carry the right signals: the
mapper checks that addresses are present and unambiguous, not that they're correct. It doesn't flag two instruments
mapped to the same OPC point either, which is usually a wiring mistake: check the plan for repeated points.
