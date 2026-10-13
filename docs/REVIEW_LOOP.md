# Closing the loop: operations review and real data points

The extraction gives a draft. Two things turn a draft into a twin a plant can run on:
1. the people who run the unit correct it;
2. each instrument gets the address where its live value comes from.

Both are files that operations and controls people already know: a review spreadsheet and an I/O list. Both flow
back into the twin through code, with a record of who decided what.

```
review sheet (spreadsheet) ──► apply_review.py ──► asset model ──► generate.py ──► Ignition / PI AF / screens
I/O list (spreadsheet)     ──► map_points.py   ──►      │                              │
                                                  change records                 build_gateway.py
                                                  (out/review, out/mapping)      verify_gateway.py
```

## 1. The operations review

**The sheet.** It's one row per item, riskiest first (red, amber, green):
- Tennessee Eastman: `out/ops_review_sheet.csv`;
- an extracted twin: `review_queue.csv`.

CSV exports prefix formula-like text (`=`, `+`, `-`, `@`, including after leading
whitespace), control-containing text and leading apostrophes with one apostrophe.
This is intentional spreadsheet text encoding, not a change to the engineering
model. Ordinary cells remain unchanged. The review importer recognizes unchanged
encoded notes against the existing model, so regenerating and reapplying a sheet
preserves the original notes and history. New or edited notes are taken as written;
when editing a protected cell, remove the serialization prefix if it is visible
and is not intended as literal text. Raw or encoded item identifiers must resolve
to exactly one record; ambiguous spellings are refused rather than guessed.

The reviewer fills in the `OPS_` columns:

| Column | What to write |
|---|---|
| `OPS_confirm_or_correct` | `confirm`, `correct` or `reject` (not real). Blank means not reviewed yet |
| `OPS_correct_value` | For `correct`: `field=value` pairs separated by `;`, e.g. `tag=FT-1401; uom=kg/h`. A bare value corrects the main field (the tag; for TE instruments, the description) |
| `OPS_show_on_operator_screen_Y_N` | `Y` or `N` |
| `OPS_alarm_priority_H_M_L_none` | `H`, `M`, `L` or `none` |
| `OPS_notes` | Free text, kept with the decision |

**Apply it:**
```
python scripts/apply_review.py data/te_process_model.json reviewed.csv --reviewer "Name, role" --dry-run
python scripts/apply_review.py data/te_process_model.json reviewed.csv --reviewer "Name, role"
python scripts/generate.py                                  # or: generate.py <twin>/plant_model.json
# Gateway import is a separate, approved isolated-lab step; see IGNITION_ACCEPTANCE.md.
```

**What happens:**
- **Every row is checked against the model before anything changes.** An unknown item, an unknown field, a
  `correct` with no value, or an unreadable decision is refused and listed. The run exits non-zero, so a bad sheet
  can't half-apply.
- **Decisions are written onto each item** as `ops_review`: status, reviewer, date, notes, screen and alarm choices.
  Each correction keeps the old value in the item's history. The model file is updated in place, so the git diff is
  exactly the review. A dated change record goes to `out/review/`.
- **Re-applying the same sheet changes nothing.** The regenerated sheet prints earlier decisions back into the
  `OPS_` columns, so a reviewer can stop and resume.
- **Downstream:**
  - rejected items leave the Ignition tags, the PI AF sheet and the SVGs (items under rejected equipment move to
    `_Unassigned`);
  - each Ignition instance's `ReviewStatus` tag carries the decision, and the verifier checks it matches (V2);
  - "don't show" items get no screen label.

An existing OPC `data_point` or reviewed PI `pi_point` blocks a scoped valve-callout
conversion before any fields or review history change. Changing or removing that
mapping needs a separate authorized mapping review; the correction never erases it.

**Identifier text only.** An optional `OPS_scope=identifier_text` column on a twin correction row limits
approval to the written identifier. It requires `tag=...`, unchanged function letters and an existing loop
that matches the old tag. The matching derived loop, exact tag-mirroring description and hierarchy display
cache update together. A non-mirrored description, semantic-field edit, invalid tag, screen/alarm decision or
mismatched loop is refused. The whole-record review status stays unchanged; corrected fields and scope are
recorded separately in `ops_review.field_decisions` and history. Extraction provenance, inferred function,
classification, parent, connections and I/O are untouched. Regeneration never turns this into `confirm`.

**Alarms stay a change-review decision.** A reviewer may set the priority of an alarm that already has a published
setpoint, and that is applied. Asking to remove a published alarm, or to add one where no setpoint exists, changes
which alarms the plant has. Those requests are recorded as needing a change review (MOC) and are not applied.

## 2. Mapping instruments to data points

**The I/O list.** A CSV with `tag, server, base_path, point` (plus optional `asset_id, units, description`):
- `server`: the Ignition OPC connection name;
- `base_path`: the OPC UA namespace and prefix (`nsu=<uri>;s=<prefix>`);
- `point`: the node under it.

A real site exports this from its control-system or historian database. **Work on a private copy, back it up and preview with `--dry-run` before applying.** Default mapping is a partial update: unrelated mappings remain. The preview includes complete before/after mapping snapshots and every added, changed or removed mapping; `--json` selects machine-readable output. `--sheets` limits eligible targets and replacement scope, but does not resolve globally ambiguous tags. A resolved out-of-scope row rejects the update.

Use `--replace-all` only for an explicitly approved authoritative replacement in that scope (all sheets if omitted). Replacement refuses unmatched, ambiguous or blocked rows. Unknown/rejected explicit IDs never fall back to tags; duplicate target rows, invalid scopes or empty addresses reject the whole transaction without model/report writes. Partial mode reports ambiguous/unmatched/callout rows without assigning them, preserves existing mappings, and may still apply other valid rows. Have the qualified reviewer inspect the complete diff and approve application; inspect the report, not just the exit code. Nonempty address checks do not prove valid OPC syntax, connectivity or signal identity. Validate units, types, scaling and ranges separately: optional CSV units/description do not validate or populate those model properties. This is OPC mapping; the PI exporter still emits placeholder PI point references.

```
python scripts/map_points.py out/twin/r2-tiles-trace/codex/plant_model.json data/io_lists/open100_sheet0_demo.csv --sheets 0 --dry-run
# After inspecting the full diff and approving the partial update, repeat without --dry-run.
python scripts/generate.py out/twin/r2-tiles-trace/codex/plant_model.json
# Gateway import is a separate, approved isolated-lab step; see IGNITION_ACCEPTANCE.md.
```

**Gateway caution:** `build_gateway.py --fresh` deletes/recreates the lab provider and configures gateway resources; it is not a file-only regeneration command. Runtime import and verification require a separately approved isolated lab, not production. See [native acceptance page](IGNITION_ACCEPTANCE.md).

**Matching never guesses.** Tags match after separators and case are normalized, so `FT 1401`, `FT-1401` and
`ft_1401` are the same tag. `asset_id` pins a row when needed. An applied report is saved under `out/mapping/`; dry-run only prints it. In addition to errors and the complete mapping diff, it retains four worklists:

| List | What it usually means at a site |
|---|---|
| Mapped | The instrument now has a live data address |
| On the drawing, not in the I/O list | Spare, demolished, a local gauge with no signal, or a missing I/O row |
| In the I/O list, not on the drawing | **The drawing may be out of date.** The plant has a point the drawing doesn't show |
| Ambiguous | The same tag on two drawing items; a person decides, then pins it with `asset_id` |

**The demo.** OPEN100 has no plant behind it, so `data/io_lists/open100_sheet0_demo.csv` is a synthetic I/O list,
labeled as such. On sheet 0 it maps 24 instruments, with three different spellings of the tag style, and finds 2
points that aren't on the drawing. It also hits one real ambiguity: the drawing shows `FT 1401` on two symbols.
`scripts/ignition/demo_points_server.py` serves synthetic values for those points.

The historical runtime receipt showed 24 mapped tags Good and 335 placeholders Bad. The current reviewed model has 334 placeholder PVs plus the metadata-only MS 14010 valve callout; in the 2026-10-13 native run of the current project, the gateway read 24 mapped points Good and all 334 placeholders Bad, with 0 false-good ([native acceptance page](IGNITION_ACCEPTANCE.md)).

![OPEN100 sheet 0 in Ignition: mapped points live, the rest not connected](screenshots/ignition-open100-sheet0-mapped.png)

## Status

- **Review loop:** tested on copies of both models (`scripts/test_apply_review.py`, in CI).
- **Point mapping:** proven in a running gateway (receipt `out/ignition/gateway/receipts/20261008T175223Z.md`).
- **Not done yet:** the Tennessee Eastman operations review itself. A review only means something from someone who knows the process and is looking at the drawings; a sign-off without that would be a rubber stamp, so none has been recorded.
