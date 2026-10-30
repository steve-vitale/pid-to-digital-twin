# From a DEXPI file: a draft twin bundle with no model reading the drawing

**Why it matters:** A supported CAD export can supply symbols and connections as data, avoiding a visual
model-reading step. Conversion rules, source errors and omissions still need checking.

This route uses three configured public example sheets. For your own CAD XML, start with the
[DEXPI reader](../from-dexpi-xml/README.md).

A DEXPI P&ID (the ISO 15926 / DEXPI XML exchange format) already holds the symbols, their labels and the lines
between them. This example turns one public DEXPI sheet into the same review bundle that
[`examples/own-drawing`](../own-drawing/README.md) builds from a model's extraction: asset model, review sheet,
Ignition tags, PI AF staging and SVG overlay. No model, OCR or line tracer runs at any step, so every tag in the
bundle comes from the drawn label text with no reading step: an equipment tag is its label as drawn, and an
instrument bubble's tag is assembled from the label's first two separate text pieces joined with a space (`PI` and
`4712.01` become `PI 4712.01`).

This is an oracle-route demonstration using converted answer keys, not a visual-extraction benchmark. Agreement
with those keys is by construction; it does not prove that a CAD export or its conversion is complete or correct.
It says nothing about how well a model reads drawings.

## Source

DEXPI example P&IDs from the [DEXPI TrainingTestCases](https://gitlab.com/dexpi/TrainingTestCases) repository
(DEXPI initiative and its contributing members), licensed CC BY 4.0, pinned to one commit in
`data/dataset_adapters/dexpi_examples.json`. Downloaded originals stay in the ignored cache. The committed outputs
in this example are derived records. Sources are checked against SHA-256 and converted into the gitignored
`data/external/dexpi/` by `scripts/adapt_dexpi.py`; converted keys and bundles are adaptations under the same license.

## Once: fetch and build the keys (network, PyMuPDF)

```sh
python -m pip install -r requirements-render.txt  # optional renderer; separate network-capable setup
python scripts/adapt_dexpi.py fetch    # downloads the pinned files, refuses any hash mismatch
python scripts/adapt_dexpi.py build    # renders each sheet to PNG and writes <id>.graphml + <id>.tags.json
```

`build` needs PyMuPDF from the separate [requirements-render.txt](../../requirements-render.txt), not the core
requirements file. The optional pin is [PyMuPDF 1.27.2.3](https://pypi.org/project/pymupdf/1.27.2.3/): on
2026-10-30 it rebuilt all 13 files of the five-sheet adapted cache byte for byte in a disposable directory.
The offline bundle commands below do not import that renderer. The three sheets with geometry are `dexpi-c01`, `dexpi-c02` and
`dexpi-c03`; the C08 sheets are keyed by tag lists only (no boxes, no links) and are refused.

## The two commands (offline, stdlib only)

```sh
python -S scripts/dexpi_to_twin.py --sheet dexpi-c01
python -S scripts/import_site_drawing.py --manifest data/external/dexpi/twin/dexpi-c01.intake-manifest.json --out my-bundle
```

The first writes `dexpi-c01.prediction.json` (the intake contract from `extraction/prompt_v2.md`),
`dexpi-c01.intake-manifest.json` and a byte-identical `dexpi-c01.source.png` into `data/external/dexpi/twin/`,
and prints every lossy step. The manifest names
the producer as `{"method": "converted from DEXPI XML, no model", "tool": "dexpi_to_twin.py", "model": null}`.
The second is the unchanged intake; `my-bundle/` must not exist yet. `--intake my-bundle` on the first command does
both in one go.

Keep these three files together when handing the intake to another engineer. The manifest uses local filenames,
so the folder can move to another drive or computer before running the second command. Existing identical source
copies are reused; a different image at that filename is refused before the prediction or manifest is replaced.
Use a new output folder for a changed drawing. The image hash must still match the prediction; no image conversion
or automatic revision choice occurs. Keep the original CAD XML and its attribution with the wider source packet.

The committed `c01/` files record an earlier conversion. Its manifest refers to the pinned local image cache;
run the commands above to produce the current intake folder with its retained image.

For `dexpi-c01` (DEXPI reference P&ID, example C01) on this commit:

| Stage | Count |
|---|---|
| Key | 30 nodes: 25 symbols in the six classes + 5 pipe tees; 33 edges; 20 symbols with a drawn label |
| Prediction | 25 symbols (11 valve, 4 instrumentation, 3 tank, 3 general, 2 pump, 2 inlet/outlet), 20 tags, 37 connections |
| Connections | 21 drawn directly between symbols, 16 added by linking each tee's neighbours pairwise; none lost |
| Bundle | 5 equipment, 4 instruments, 14 line items, 2 off-page connectors, 37 links |

Scored against its own key with `scripts/score_pid2graph.py`, the prediction needs zero corrections (classified F1
1.0) on all three sheets. That only shows the conversion is lossless with respect to the key.

## What is lost on the way

The converter prints these and writes them into the prediction's `conversion` block:

- **Classes.** Only the six scored classes survive. Every pump, compressor, blower and fan becomes `pump`; every
  other top-level equipment (vessels, columns, heat exchangers) becomes `tank`; reducers, flanges and fittings
  become `general`. The DEXPI class rides along as `dexpi_class`, which the intake keeps in its source copy and
  does not use.
- **Things that are not symbols.** Nozzles fold into their equipment, actuators into the valve they operate. Pipe
  tees become pairwise links between their neighbours. Equipment internals, flow arrows, sensor elements, loop
  groupings, the plant hierarchy (enterprise, site, plant, section) and off-page target references are dropped.
- **Direction.** DEXPI pipe segments run from one item to another; the intake's connections are undirected, so
  the direction is discarded (19 directed segments on C01).
- **Attributes.** Line numbers, nominal diameters, fluid and piping-class codes, design limits and fail actions are
  not carried (249 attribute values on C01's kept items); the intake has no field for them.
- **Tags are drawn labels, not a tag register.** On C01 the manual ball valves are labelled with piping-spec codes
  (`73KH12-25` on three valves, `73KH12-50` on two), so the bundle flags all five as duplicate tags; two in the
  same Ignition folder get a `_2` suffix, and Ignition names turn spaces and dots into underscores
  (`PI 4712.01` -> `PI_4712_01`). Symbols drawn
  without a label stay untagged even where the XML holds an identifier in an attribute; the converter lists those.
- **Off-page connectors stay unpaired**: the intake reads no drawing number from their text.

Everything in the bundle is still a draft marked unverified, exactly as in the own-drawing runbook: no signal
mapping, live values or operational approval come from a DEXPI file.

## From the bundle to one useful question

The existing question engine can screen the bundle's model without another extraction, renderer or platform
connection:

```sh
python -S scripts/question_engine.py --model my-bundle/plant_model.json --out my-questions
```

Open `my-questions/screen.md` beside the conversion's loss report and original source. This route's reduced
classes, undirected links and omitted controls/attributes limit which questions can fire and what their evidence
means. A quiet screen does not establish that the source or plant lacks an issue. The
[direct XML route](../from-dexpi-xml/README.md#from-the-model-to-one-question) retains more source structure, but
its screening input still needs review; neither route establishes current plant configuration.

Choose one question with the intended engineering recipient. Put its exact finding ID, asset references and
missing-evidence requests into a private copy of the [plain brief](../first-pilot/pilot-brief.md), together with
the XML/drawing revision and source locations, conversion limits and qualified answer or unresolved disposition.
Use the [first-question guide](../first-pilot/README.md) for source review and company handoff. Unknown ownership
or acceptance stays visible. The company needs a maintained home for ongoing evidence, decisions and history;
the toolkit supplies this starting packet. No native import or local context register is required for this step.
