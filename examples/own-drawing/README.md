# Your own drawing: from one P&ID to a draft asset model

This is the runbook for using this repository on a drawing it has never seen. Start with the worked example below:
it runs offline from a clean clone, on a public sheet, with a real model extraction that is committed here.

What you get is a **draft**: an asset model, a review sheet, Ignition tags and PI AF staging files, every item marked
unverified. What you don't get: verified structure, flow direction, live values, alarms or the Tennessee Eastman
screens. Those need your process knowledge, your I/O list and a person's review.

## 0. The worked example (offline, about a minute)

`manifest.json` here points at PID2Graph OPEN100 sheet 0 (a public drawing, CC BY-SA 4.0, already in the repository)
and at `extraction_sheet0.json`, the recorded GPT extraction of that sheet made with this repository's method
(2x2 tiles with `extraction/prompt_v2.md`, then the code line tracer). From the repository root:

```sh
python -S scripts/import_site_drawing.py --manifest examples/own-drawing/manifest.json --out my-bundle --check-only
python -S scripts/import_site_drawing.py --manifest examples/own-drawing/manifest.json --out my-bundle
```

`my-bundle/` must not exist yet. It holds:

| File | What it is |
|---|---|
| `review_queue.csv` | 445 rows for a person to confirm, correct or reject (the `OPS_` columns) |
| `plant_model.json` | The draft model: 2 equipment, 36 instruments, 53 line items, 9 off-page connectors, 345 links |
| `svg/sheet_0.svg` | The links drawn over the sheet: logical links, not pipe routes |
| `ignition/tags.json` | An Ignition tag import with UDT types; every value is a placeholder until mapped |
| `pi/` | PI AF staging sheets and the steps a PI site would still have to run |
| `READ_ME.txt` | What the bundle has not established |

The `tier` column in `review_queue.csv` is empty on purpose. The risk tiers in the main results come from a model
trained on OPEN100; it isn't applied to a drawing it wasn't trained on.

## 1. Your sheet as a PNG

Export one approved revision of one sheet to PNG. PDFs aren't read directly. Keep the drawing private: decide first
whether you're allowed to send it to a hosted model at all.

## 2. An extraction of it

Pick one route. Both write a file `import_site_drawing.py` accepts.

**A. The method behind this repository's results** (tiles, then the code line tracer). Put the PNG in a folder of
its own, named for the sheet (say `mysheets/0.png`), and point the scripts at it:

```sh
PID_SHEETS_DIR=mysheets python scripts/run_extraction.py --tool codex --drawings 0 --prompt extraction/prompt_v2.md --tiles 2x2 --overlap 0.15 --label mine-tiles
PID_SHEETS_DIR=mysheets python scripts/trace_connections.py --src-label mine-tiles --tool codex --drawings 0 --label mine-trace
```

The result is `runs/mine-trace/codex/0.json` (a run record). The first command sends the image to a hosted model
through its CLI (`--tool claude` and `--tool gemini` also exist); the second runs locally and needs `requirements.txt`.
The tracer's settings were tuned on six OPEN100 sheets, so expect it to do worse on faded scans and very different
drafting styles ([results](../../README.md#results-held-out-drawings-and-how-they-were-used)).

**B. The one-sheet workflow with a full audit trail** (`site_extraction_workflow.py` prepare, execute, collect).
It records hashes, the exact prompt and every attempt, but it uses a simpler recipe: the whole sheet at once, no
tiles, no tracing. It is not the method the headline numbers measure. See
[SITE_EXTRACTION_WORKFLOW.md](../../docs/SITE_EXTRACTION_WORKFLOW.md).

Or write the extraction yourself, by any means, in the contract at the top of `extraction/prompt_v2.md`
(symbols with class, tag and box; connections between symbol ids). Use `"extraction_format": "prediction"`.

## 3. The draft model

Copy `manifest.json`, change `drawing_id`, `revision`, `image`, `extraction`, `extraction_format` (`run-record` for
route A, `prediction` for your own file) and `producer`, then run the two commands from step 0 on it.

## 4. Review, then map to real signals

A qualified reviewer fills the `OPS_` columns in `review_queue.csv`. Then preview and apply the decisions with
`apply_review.py`, and regenerate the exports with `generate.py`. Mapping instruments to real signals needs your
I/O list (`map_points.py` for OPC addresses, `map_pi_points.py` for reviewed PI references). The commands, and what
each one refuses, are in [REPLICATE_AT_YOUR_PLANT.md §4](../../docs/REPLICATE_AT_YOUR_PLANT.md#4-review-and-map-on-copies).
Nothing here derives an I/O list from a drawing.

## 5. Into Ignition

Import `ignition/tags.json` into a tag provider in a **lab** gateway: Designer, Tag Browser, Import Tags. That
gives you the asset hierarchy with placeholder values. `scripts/ignition/build_gateway.py` is not for this: it
builds this repository's Tennessee Eastman demo (its model, replay connection, screens and historian) and bolts an
extracted twin onto it.

## What carries over to your plant, and what doesn't

- **Carries over:** the method (a model reads symbols and tags, code traces the lines, everything stays unverified
  until a person reviews it), the file formats, the review and mapping steps, and the habit of checking every
  number against its source (`scripts/check_claims.py` is an example).
- **Doesn't:** the accuracy numbers (measured on public drawings, not yours), the tracer settings and risk tiers
  (tuned on OPEN100), and everything that needs process data: values, normal bands, alarms, flow direction.
- **To measure accuracy on your own drawings** you need answer keys for a few sheets in the PID2Graph GraphML format,
  labelled by hand, and then `score_pid2graph.py`. That's real work, and it's the only way to know.
