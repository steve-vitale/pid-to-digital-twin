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
python scripts/ignition/build_gateway.py --fresh            # then verify_gateway.py
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

**Alarms stay a change-review decision.** A reviewer may set the priority of an alarm that already has a published
setpoint, and that is applied. Asking to remove a published alarm, or to add one where no setpoint exists, changes
which alarms the plant has. Those requests are recorded as needing a change review (MOC) and are not applied.

## 2. Mapping instruments to data points

**The I/O list.** A CSV with `tag, server, base_path, point` (plus optional `asset_id, units, description`):
- `server`: the Ignition OPC connection name;
- `base_path`: the OPC UA namespace and prefix (`nsu=<uri>;s=<prefix>`);
- `point`: the node under it.

A real site exports this from its control-system or historian database.

```
python scripts/map_points.py out/twin/r2-tiles-trace/codex/plant_model.json data/io_lists/open100_sheet0_demo.csv --sheets 0
python scripts/generate.py out/twin/r2-tiles-trace/codex/plant_model.json
python scripts/ignition/build_gateway.py --fresh            # creates an OPC connection per data source
```

**Matching never guesses.** Tags match after separators and case are normalized, so `FT 1401`, `FT-1401` and
`ft_1401` are the same tag. `asset_id` pins a row when needed. The report (`out/mapping/`) has four lists, each a
worklist:

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

In Ignition, the 24 mapped tags read Good while the other 335 placeholders stay Bad. The verifier checks both (V4).

![OPEN100 sheet 0 in Ignition: mapped points live, the rest not connected](screenshots/ignition-open100-sheet0-mapped.png)

## Status

- **Review loop:** tested on copies of both models (`scripts/test_apply_review.py`, in CI).
- **Point mapping:** proven in a running gateway (receipt `out/ignition/gateway/receipts/20261008T175223Z.md`).
- **Not done yet:** the Tennessee Eastman operations review itself. A review only means something from someone who knows the process and is looking at the drawings; a sign-off without that would be a rubber stamp, so none has been recorded.
