# Checklist: extraction review queue (drawing sheet 0)

**File:** `out/twin/r2-tiles-trace/codex/review_queue.csv`. Work on a copy, e.g. `reviewed_sheet0.csv`, and keep the
original untouched.
**Drawing:** `data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/0.png` (2604 × 1744 px).
**Overlay:** `out/twin/r2-tiles-trace/codex/svg/sheet_0.svg` (what was extracted), or
`docs/screenshots/before-after-sheet0.png` (both side by side).

The queue has 2,886 rows over 12 drawings. One sitting covers **sheet 0 only**. Filter `sheet = 0` and leave out
`item_type = connection` for Track A: that leaves 100 items (4 red, 17 amber, 79 green). Do every red and amber
row, then the first 20 green rows by `rank`, so 41 rows in 45 minutes. Log how many you actually did.

**Finding a box.** `location_on_sheet_0_1000` is left, top, right, bottom, in thousandths of the drawing's width
and height. On the 2604 × 1744 image, multiply the first and third numbers by 2.604 and the second and fourth by
1.744 to get pixels. Example: `187.1 385.0 202.8 409.3` is about x 487–528, y 671–714.

## Track A: anyone

For each row, write what you saw in `OPS_notes`, starting with `A:`. Leave `OPS_confirm_or_correct` **blank**,
except for the one case in step 2.

1. **Is there a symbol in the box?** `A: box on symbol` / `A: box on empty paper` / `A: box on text only` /
   `A: box covers two symbols`.
2. **Does the tag text match the drawing, character for character?** Compare `what_it_is` with the text printed
   at the symbol.
   - It matches: `A: tag text matches`.
   - It is misread (a wrong digit, or `I` for `1`) **and the letters are the same**: write `correct` in
     `OPS_confirm_or_correct` and `tag=<text as printed>` in `OPS_correct_value`, add a column `OPS_scope` and
     write `identifier_text` in it. This changes the tag text only; the item stays unreviewed for everything
     else (`docs/REVIEW_LOOP.md`, "Identifier text only").
   - The function letters differ (e.g. `TI` versus `TIC`), or `tag_status` is `missing` and there is text on the
     drawing: describe it in `OPS_notes` only, e.g. `A: drawing reads FIC 1402`. That is a Track B decision.
3. **Obvious shape mismatch only.** `item_type` says instrument but the box holds a vessel outline, or similar:
   `A: looks like <shape>`. If you are unsure, do not write anything; this is not symbol classification.
4. **Can you read the drawing text at all at that spot?** If the scan is unreadable there:
   `A: unreadable on drawing`. That is a result, not a failure.

Do **not**: confirm or reject a row, set `OPS_show_on_operator_screen_Y_N` or `OPS_alarm_priority_H_M_L_none`,
or judge connections, parents or units.

## Track B: operations reviewer

Use the same copy. The session runner writes decisions as the reviewer states them.

1. **Red and amber rows on sheet 0, all types, including the connection rows** (start with `rank` order). For
   each: `confirm`, `correct` with `field=value` pairs, or `reject` (not a real item). `why_check_this` says
   what the risk model was unsure about.
2. **Connections:** does the drawn line join these two items, through any line breaks, off-page connectors and
   crossings, as the plant would read it? Is the flow direction right?
3. **Parents and units (`belongs_to`):** is the instrument on the right equipment or line? Items filed under
   `unassigned` need a home or a `reject`.
4. **Screen choice:** for confirmed instruments only, `OPS_show_on_operator_screen_Y_N`.
5. Anything the drawing does not show but the plant has (spares, demolished, local gauges): `OPS_notes`.

## Done when

- Every row you looked at has an `A:` note (Track A) or a decision (Track B); untouched rows stay blank.
- The timing log has the count of rows looked at and the minutes.
- The sheet goes through the dry run in [FEEDBACK.md](FEEDBACK.md) with no refused rows, or every refusal is
  understood.
