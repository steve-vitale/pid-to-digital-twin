# Your own drawing: from one P&ID to a draft asset model

**Why it matters:** Retyping drawings into an asset list is the first and slowest step of any historian, HMI or digital twin project. Starting from a draft turns that typing into checking.

This is the runbook for using this repository on a drawing it has never seen. Start with the worked example below:
it runs offline from a clean clone, on a public sheet, with a real model extraction that is committed here.

What you get is a **draft**: an asset model, a review sheet, Ignition tags and PI AF staging files, every item marked
unverified. What you don't get: verified structure, flow direction, live values, alarms or the Tennessee Eastman
screens. Those need your process knowledge, your I/O list and a person's review.

## On Windows, from zero

1. Install Python 3.10 or newer from python.org. In the installer, tick "Add python.exe to PATH".
2. Get the repository. With git: `git clone https://github.com/steve-vitale/pid-to-digital-twin`. Without git:
   on the repository page choose Code, then Download ZIP, and unzip it.
3. Open PowerShell in the repository folder and run:

   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

4. Use `.venv\Scripts\python` wherever the commands below say `python`. PowerShell sets environment variables on a
   line of their own: instead of `PID_SHEETS_DIR=mysheets python ...`, run `$env:PID_SHEETS_DIR = "mysheets"` once,
   then the command without the prefix.

The worked example (step 0) needs only Python. The extraction (step 2, route A) also needs a model's command-line
tool (`codex`, `claude` or `gemini`) installed and signed in, with a subscription or API key; the worked example
skips that by using a recorded extraction.

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

To turn the bundle into the one-page report a client reads first (the drawing with every extracted item boxed,
what to check first and why, the hierarchy, next steps and limits):

```sh
python scripts/deliverable_report.py my-bundle
```

[`deliverable/REPORT.html`](deliverable/REPORT.html) is that report for this example.

The `tier` column in `review_queue.csv` is empty on purpose. The risk tiers in the main results come from a model
trained on OPEN100; it isn't applied to a drawing it wasn't trained on.

## 1. Your sheet as a PNG

Export one approved revision of one sheet to PNG. PDFs aren't read directly. Keep the drawing private: decide first
whether you're allowed to send it to a hosted model at all.

**From a PDF, or a scanned PDF:** convert each page to PNG first. PyMuPDF does it (`pip install pymupdf`; it isn't
in `requirements.txt`). Create the output folder, then:

```sh
python -c "import pymupdf,sys; d=pymupdf.open(sys.argv[1]); [p.get_pixmap(dpi=200).save(f'{sys.argv[2]}/{i}.png') for i,p in enumerate(d)]" drawing.pdf mysheets
```

That writes `mysheets/0.png`, `1.png` and so on, one per page, which is the naming step 2 expects. The same line
works in PowerShell. The drawings behind the results are about 2,600 px wide and the tracer was tuned on them; how
much a very different image size changes the result has not been tested.

**Scanned archives:** expect much more to check. On synthetic old-scan copies of the held-out sheets the review load
roughly tripled (GPT 17.8 to 51.5 differences per 100 answer-key items), mostly because the line tracer loses faded
lines ([round 4](../../README.md#results-held-out-drawings-and-how-they-were-used)). Try one clean sheet first.

## 2. An extraction of it

Pick one route. Both write a file `import_site_drawing.py` accepts.

**A. The method behind this repository's results** (tiles, then the code line tracer). Install
`requirements.txt` first (both commands need it: tiling uses Pillow, tracing uses OpenCV). Put the PNG in a folder of
its own and point the scripts at it. `--drawings` is the PNG's file name without `.png`, so `mysheets/0.png` is
`--drawings 0`; rename yours or change both commands.

```sh
PID_SHEETS_DIR=mysheets python scripts/run_extraction.py --tool codex --drawings 0 --prompt extraction/prompt_v2.md --tiles 2x2 --overlap 0.15 --label mine-tiles
PID_SHEETS_DIR=mysheets python scripts/trace_connections.py --src-label mine-tiles --tool codex --drawings 0 --label mine-trace
```

The result is `runs/mine-trace/codex/0.json` (a run record). The first command sends the image to a hosted model
through its CLI (`--tool claude` and `--tool gemini` also exist; `codex` and `claude` run on a subscription, so the
record shows token counts per tile but no cost); the second runs locally in about two seconds.

**Measured:** an agent following this route on OPEN100 sheet 8, a drawing it was handed as its own, went from PNG
to review bundle in 88 seconds of commands (extraction 36 s, tracing 4 s, intake under 1 s) plus about half a
minute of reading. Scored afterwards against that sheet's answer key, it matched the published mean for that sheet
(review load 11.0 per 100 against 10.99; journal entry 63). Reviewing the bundle is the part nobody has timed.
The tracer's settings were tuned on six OPEN100 sheets, so expect it to do worse on faded scans and very different
drafting styles ([results](../../README.md#results-held-out-drawings-and-how-they-were-used)).

**B. The one-sheet workflow with a full audit trail** (`site_extraction_workflow.py` prepare, execute, collect).
It records hashes, the exact prompt and every attempt, but it uses a simpler recipe: the whole sheet at once, no
tiles, no tracing. It is not the method the headline numbers measure. See
[SITE_EXTRACTION_WORKFLOW.md](../../docs/SITE_EXTRACTION_WORKFLOW.md).

Or write the extraction yourself, by any means, in the contract at the top of `extraction/prompt_v2.md`
(symbols with class, tag and box; connections between symbol ids). Use `"extraction_format": "prediction"`.

## 3. The draft model

Copy `manifest.json` next to your PNG (say `mysheets/manifest.json`). Paths in it are relative to the manifest
itself, so for route A: `"image": "0.png"`, `"extraction": "../runs/mine-trace/codex/0.json"`,
`"extraction_format": "run-record"` (`"prediction"` for a file you wrote yourself). Set `drawing_id` and `revision`
to your drawing's, and `producer` to how the extraction was made (`model` is the run record's `model` field). Then
run the two commands from step 0 with `--manifest mysheets/manifest.json` and a new `--out` folder (it must not
exist yet, so don't reuse `my-bundle` from the example). The bundle always calls the sheet `0` (`svg/sheet_0.svg`,
`source/0.png`); your drawing number lives in the manifest and in `intake_manifest.json`.

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
  labelled by hand. Then `python scripts/score_pid2graph.py <sheet>.graphml runs/mine-trace/codex/0.json --png
  <sheet>.png` scores one run; [examples/vendor-evaluation](../vendor-evaluation/README.md) scores several runs (or a
  vendor's output) with the controls beside them. That's real work, and it's the only way to know.
