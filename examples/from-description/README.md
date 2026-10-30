# From a written description: process model, then P&ID and exports

**Why it matters:** A unit may have procedures and design notes but no usable drawing. A model with a source on every item supports draft asset lists, logical SVGs and platform staging. It makes the interpretation checkable; agreement with the actual plant still needs independent evidence and engineering review.

When there's no usable drawing but there is a description (an operating procedure, a design basis, an
investigation report, a PFD with notes), the route is: write a process model from it with a source on every item,
check that model against something it wasn't written from, then generate the P&ID and the platform files from the
model. This repository did it twice: the Tennessee Eastman process from its published paper and simulator code, and
the Bayer CropScience residue treater from the CSB's investigation report. The commands below use the Bayer model.

## 1. Write the model, citing every item

`data/bayer_rt/process_model.json` is the worked example: an agent wrote it from the report's text, with a page or
figure on every item. The fields the generators need:

| Section | Required fields | Notes |
|---|---|---|
| `meta` | `model_id`, `title`, `source_document` | `model_id` names the PI AF root and point prefix |
| `units` | `id`, `name`, `type` | `type`: `pressure_vessel`, `vessel`, `tank`, `pump`, `heat_exchanger`, `reactor`, `condenser`, `separator`, `compressor`, `stripper`, `feed_header` |
| `streams` | `id`, `name`, `from`, `to` | `BL` for the battery limit |
| `instruments` | `tag`, `unit`, `variable`, `uom`, `description` | ISA first letter must match `variable`; field devices are transmitters (FT, PT, LT, TT) |
| `final_elements` | `tag`, `unit`, `description` | valves; `uom` optional and left blank if absent |

Add a `source` to every item. Missing source text alone does not refuse export. The warning and `NO SOURCE GIVEN`
marker cover instruments and final elements without simulator-channel references; equipment rows can instead
have a blank source, and the sheet is not a complete stream-source audit. Check the model's sources explicitly.
Anything the description doesn't say stays out, or is marked as an assumption.

Ignition member and PI attribute names come from `description` (letters and digits, cut at 40 characters). Two items
on one unit whose names would come out the same get their tag appended (`..._TI_101`, `..._TI_102`); if they still
collide, structural validation refuses the model and names both tags. A missing required field is refused with the
item and field named (`unit RT-1: missing name`).

## 2. Check it against something it wasn't written from

This step tests the interpretation. The Bayer model, written from the report's text, got the report's own piping
figure wrong in four places (10 of 21 checks at first; 20 of 21 after correcting from the figure):
`scripts/compare_bayer_fig10.py`, [BAYER_RT.md](../../docs/BAYER_RT.md). For your unit the second source might be an
old drawing, a walkdown, the DCS configuration ([loop list check](../loop-audit/README.md)) or the I/O list.

## 3. Platform files straight from the model

```sh
python scripts/generate.py data/bayer_rt/process_model.json --out my-exports
```

`my-exports/` gets `ignition/tags.json` (UDT types and one instance per unit, every value a placeholder until
mapped), `pi/` (PI Builder staging sheets), `svg/` (an overview and one view per unit) and `ops_review_sheet.csv`.
Units with no screen position are placed automatically in flow order from the main feed, and the overview says so:
links between them are logical, not pipe routes. On the Bayer model it writes 5 units, 15 streams, 6 instruments
and 5 valves, and passes structural validation (which is not engineering approval).

## 4. A P&ID from the model

The drawing needs a manually authored drafting layout (`data/bayer_rt/pid_layout.json`). It places modeled items;
validation refuses missing, duplicated or unknown model references. A layout can also declare drafting additions,
including utility symbols and manual block/bypass valves at control-valve stations. Those are marked as drafting
additions in the emitted answer key, not established physical equipment or extra process-model facts. Inspect them
separately; the Bayer example disables valve stations with stated reasons. Relative paths in the layout resolve
against the repository root, not the folder you run it from.

Step 3's platform export uses the standard library. This drawing step requires Pillow, including when using
`--check`; install the drawing dependencies with `python -m pip install -r requirements.txt` in your environment.

```sh
python scripts/draw_pid_from_model.py --model data/bayer_rt/process_model.json --layout data/bayer_rt/pid_layout.json --check
python scripts/draw_pid_from_model.py --model data/bayer_rt/process_model.json --layout data/bayer_rt/pid_layout.json --out my-pid --register my-pid/sheet_register.csv
```

`my-pid/` gets the sheet as PNG and SVG, and an answer key emitted from the same model, so the drawing can be read
back and scored. Run on the committed inputs it reproduces `data/bayer_rt/pid/RT1.png` byte for byte.

**The gap:** the layout is written by hand (or by an agent) today. Positions and explicitly declared drafting
additions affect the depicted drawing and its key; they do not update the source model or prove installed
configuration. Someone must check both the placements and additions. The platform files in step 3 don't need a layout.

## What this route can't give you

A model written from text is only as good as the text. Every item stays unverified until someone who knows the
unit checks it, and the generated drawing is not a drawing of record.
