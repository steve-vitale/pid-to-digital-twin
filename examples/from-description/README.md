# From a written description: process model, then P&ID and exports

**Why it matters:** Many older units have no usable drawing but do have procedures and design notes. A model with a source on every item lets you build asset lists and screens for them anyway, and shows where the text and the plant disagree.

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

Add a `source` to every item. An item with no source is not refused: it is still exported, `generate.py` prints a
warning naming it, and the review sheet shows `NO SOURCE GIVEN` in its source column. Anything the description
doesn't say stays out, or is marked as an assumption.

Ignition member and PI attribute names come from `description` (letters and digits, cut at 40 characters). Two items
on one unit whose names would come out the same get their tag appended (`..._TI_101`, `..._TI_102`); if they still
collide, structural validation refuses the model and names both tags. A missing required field is refused with the
item and field named (`unit RT-1: missing name`).

## 2. Check it against something it wasn't written from

This is the step that earns trust. The Bayer model, written from the report's text, got the report's own piping
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

The drawing needs one more file the description can't supply: a drafting layout saying where each item goes on
the sheet (`data/bayer_rt/pid_layout.json`). The generator draws only what the model holds and refuses a layout that
drops, duplicates or invents an item. Its relative paths resolve against the repository root, not the folder you run
it from; a missing file or a layout made for another model is refused with a message.

```sh
python scripts/draw_pid_from_model.py --model data/bayer_rt/process_model.json --layout data/bayer_rt/pid_layout.json --check
python scripts/draw_pid_from_model.py --model data/bayer_rt/process_model.json --layout data/bayer_rt/pid_layout.json --out my-pid --register my-pid/sheet_register.csv
```

`my-pid/` gets the sheet as PNG and SVG, and an answer key emitted from the same model, so the drawing can be read
back and scored. Run on the committed inputs it reproduces `data/bayer_rt/pid/RT1.png` byte for byte.

**The gap:** the layout is written by hand (or by an agent) today. Positions are display configuration, never
process content, so getting them wrong can't change what the model says, but someone has to place them. The
platform files in step 3 don't need it.

## What this route can't give you

A model written from text is only as good as the text. Every item stays unverified until someone who knows the
unit checks it, and the generated drawing is not a drawing of record.
