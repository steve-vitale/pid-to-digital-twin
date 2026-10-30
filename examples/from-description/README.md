# From a written description: sourced model, questions and optional outputs

**Current status: an assisted workflow, not a raw-text generator command.** An engineer or approved assistant
authors the source-cited model and drafting layout; the supplied commands validate and render those inputs.
There is no packaged description interpreter or automatic detailed drafting layout. Those are missing workflow
steps, not functions demonstrated by the corpus matrix. The [connection map](../../README.md#what-connects-today-the-hub-and-spokes)
shows this route alongside the other tools.

**Why it matters:** A unit may have procedures and design notes but no usable drawing. A model with a source on every item supports draft asset lists, logical SVGs and platform staging. It makes the interpretation checkable; agreement with the actual plant still needs independent evidence and engineering review.

When there's no usable drawing but there is a description (an operating procedure, a design basis, an
investigation report, a PFD with notes), write a process model with a source on every item and check it against
something it wasn't written from. Use that model for a first engineering question or generate the draft outputs
the work needs. This repository built two such models: the Tennessee Eastman process from its published paper
and simulator code, and the Bayer CropScience residue treater from the CSB's investigation report. The commands
below use the Bayer model.

Begin with one useful question and an intended recipient. If the question only needs a clarification of the
source text, use the [plain question brief](../first-pilot/pilot-brief.md) without creating a model. Build a model
when the investigation needs asset identities or relationships. A first evidence packet does not require a new
drawing or platform import.

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

## Use the model for one engineering question

The existing question engine reads this process-model format directly, offline and with the standard library:

```sh
python -S scripts/question_engine.py --model data/bayer_rt/process_model.json --out out/from-description-question
```

Open `out/from-description-question/screen.md`. For your model, replace the `--model` path and choose a separate
output folder. Check a relevant finding against its cited model fields and original source before using its
collection requests. The model is still a draft; a screen does not establish an opportunity, current plant
conditions, savings or permission to change equipment. No findings means no catalog pattern fired on the supplied
model, not that the unit has no useful questions.

Choose one question with the intended engineering recipient. Copy its exact finding ID, asset references and
missing-evidence requests into a private copy of the [plain brief](../first-pilot/pilot-brief.md). Keep the source
revision and exact locations, what they support, competing evidence and the next owner together. The existing
[Bayer E18 example](../context-register/bayer/README.md) shows a generated question with a qualified partial answer;
its local register is optional. No drawing layout, extra model call or platform connection is needed for this step.

Follow the [first-question guide](../first-pilot/README.md) for source review and company handoff. Leave unknown
ownership and acceptance visible. As the work becomes shared, the company needs a maintained home for the evidence,
decisions and history. Continue below when the investigation actually needs generated platform files or a drawing.

## 3. Platform files straight from the model

```sh
python scripts/generate.py data/bayer_rt/process_model.json --out my-exports
```

`my-exports/` gets `ignition/tags.json` (UDT types and one instance per unit, every value a placeholder until
mapped), `pi/` (PI Builder staging sheets), `svg/` (an overview and one view per unit) and `ops_review_sheet.csv`.
Units with no screen position are placed automatically in flow order from the main feed, and the overview says so:
links between them are logical, not pipe routes. On the Bayer model it writes 5 units, 15 streams, 6 instruments
and 5 valves, and passes structural validation (which is not engineering approval).

## 4. A P&ID from the model, when needed

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

## What has actually been evaluated

There is no end-to-end accuracy score for turning an unfamiliar process description into a correct P&ID.
The two worked examples use authored models and layouts. Keep the evidence for each step separate:

| Step | Available evidence | What remains unmeasured |
|---|---|---|
| Description → sourced process model | The Bayer model was checked against the report's Figure 10. Its initial text interpretation had four substantive errors; after corrections, 20 of 21 model checks agree. The remaining difference is reported. | Accuracy on new descriptions; missing facts or invented assumptions that a source comparison has not caught. |
| Model + authored layout → P&ID | The Bayer drawing's generated routing key agrees with all 15 reference lines. Generator regression controls reject missing, duplicate or invented model references and missing or invalid signals. | Automatic drafting layout, general drawing readability, and acceptance by a site engineer or operator. The 15-line check reads generated routing data, not the rendered image. |
| Rendered drawing → recoverable geometry | Separate regression tests trace the committed TE and Bayer images with known symbol boxes and compare the recovered links with their keys. | Finding the symbols from pixels, reading every label, or proving that the source model describes the plant correctly. |
| Model → platform exports | Matrix **row 5** runs `generate.py --out` on the listed inputs. It checks export behavior; the external flowsheets extend unit/stream coverage. | This row does not execute the P&ID drawing generator or score prose interpretation or drafting quality. |
| Existing drawing → loops and pipe layer | Matrix **rows 4 and 8** check their stated loop and tracing criteria, including generated TE and Bayer examples. | The generated examples use this project's models and keys. Those passes are consistency checks, not independent accuracy on unfamiliar descriptions. |

See the [Bayer comparison](../../docs/BAYER_RT.md),
[generator regression controls](../../scripts/test_te_pid_roundtrip.py), and the
[matrix's exact criteria](../../docs/GENERALIZATION.md). A description-to-P&ID evaluation needs separately frozen
source facts, allowed assumptions, model and layout submissions, and checks of the actual rendered drawing.
The [evaluation plan](../../docs/EVALUATION.md#8-description-to-pid-evaluation-gap) explains that missing measurement.

## What this route can't give you

A model written from text is only as good as the text. Every item stays unverified until someone who knows the
unit checks it, and the generated drawing is not a drawing of record.
