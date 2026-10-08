# Twin outputs: from extracted sheets to a digital twin starter kit

`scripts/build_twin.py` turns a set of extracted sheets into a package a plant could load. Extraction gives a flat
list of symbols and links per sheet. The converter adds the structure a twin needs: a site/system/equipment
hierarchy, cross-sheet links, platform import files and a review queue. Nothing is drawing-specific. Every decision
records the method it used, and every item starts as `unverified`.

## One command

```
python scripts/build_twin.py --label round1-v2-named-fields --sheets 0,1,2,3,4,5 --score
```

- `--label` takes a run label (every tool folder under `runs/<label>/`) or one tool folder
  (`runs/round1-v2-named-fields/claude/`).
- Output goes to `out/twin/<label>/<tool>/`. `--score` also writes `out/twin/<label>/twin_scores.{md,json}`.
- `--sheet-register <csv>` supplies the plant's drawing index (`sheet,drawing_number,system_code,system_name`).
  Without it, drawing numbers are inferred (see below). The example for the development sheets is
  `data/sheet_registers/open100_dev.csv`, read by a person from the title blocks.
- `--svg-background` links the sheet image under each SVG, for checking alignment. Off by default: the drawings
  are not redistributed.
- Sheets outside the development set (0–5) are refused unless `--holdout-ok` is passed. That flag is only for the
  single holdout run of a finished method (docs/GOAL.md).

`python scripts/generate.py out/twin/<label>/<tool>/plant_model.json` rebuilds the platform files from an edited
model. Run with no argument, it still produces the Tennessee Eastman outputs, unchanged.

A small example package for Claude on sheets 0–5 is committed under `out/twin/round1-v2-named-fields/claude/`.

## The files

| File | What it is | Load it into |
|---|---|---|
| `plant_model.json` | The asset model. Site → system (one per sheet) → equipment → line items → instruments, plus streams, off-page connectors and pairs, and per-item provenance (sheet, box, source run, model, confidence, status). It is a superset of `data/te_process_model.json`: `meta`, `units`, `streams`, `instruments` and `final_elements` keep their meaning, and `meta.model_kind = "extracted_twin"` tells the generator which path to take. | Your asset register, after review |
| `review_queue.csv` | One row per item (symbols and connections), riskiest first. Columns `tier` (red / amber / green), `risk_score` and `why` come from the risk rating (see "Risk tiers" below). Same plain-language and `OPS_` columns as `out/ops_review_sheet.csv`, plus `rank`, `why_check_this` (the converter's own flags), `sheet`, `symbol`, location, `tag_status` and `how_attached`. | A spreadsheet, for the reviewer |
| `ignition/tags.json` | Ignition 8 tag JSON, same shape as `out/ignition/te_tags.json`. UDT types per equipment class (`Equipment_Tank`, `Equipment_Pump`), per instrument type (`Instrument_PT`, `Instrument_TCV`, …) and per line-item class. Instances are foldered Site/System/Equipment, with an `_Unassigned` folder per system. | Ignition Designer → Tag Browser → Import Tags (JSON) |
| `pi/pi_builder_af.csv` | PI Builder-style flat sheet, same columns as `out/pi/pi_builder_af.csv`. Elements are Site / System / Equipment (plus `Unassigned`), with one PI Point attribute per instrument. | PI Builder (Excel add-in) → Publish |
| `svg/sheet_<n>.svg` | Each symbol drawn at its extracted box, each extracted connection as a straight line. Every symbol group carries `data-asset`, `data-tag`, `data-class`, `data-confidence`, `data-status` (and `data-parent` / `data-pair`). Low confidence shows red and dashed; placeholder tags show orange. | Ignition Perspective (Drawing / embedded SVG), bound by `data-asset` |

## How the hierarchy is decided (and where it guesses)

- **Equipment** is every `tank` and `pump` symbol. A `general` symbol is promoted to equipment only when its tag
  follows the SYSTEM-TYPE-NUMBER pattern (e.g. `ACC-SX-154`). Promoted items are flagged in the queue.
- **One asset per real tag.** Equipment carrying the same real tag on several sheets (the same tank drawn on three
  sheets) becomes one asset with several appearances. This is flagged for confirmation. Placeholder and untagged
  equipment are never merged. Instruments and valves with repeated tags are not merged either; they are flagged.
- **Line items** (valves, other in-line symbols) belong to the nearest equipment along extracted connections
  through other line items only (fewest hops, then closest). If there is no such path, the item goes under
  `Unassigned`. Equipment is never guessed by position.
- **Instrument parent**, in order:
  1. the linked non-instrument neighbour (closest one if several);
  2. else the first non-instrument reached through other instruments;
  3. else the nearest symbol by position (`geometry_nearest`, with the gap recorded).

  A second opinion by position alone is always computed. When it disagrees with the connection-based parent, the
  instrument goes to the review queue. On the development set, an instrument whose two opinions agree was right
  about 9 times in 10 for Claude and Codex. One whose opinions disagree was right about 3 in 10.
- **Off-page connectors.** The drawing reference is parsed from the text (`HPD PID 190-1`, `RCS-PID-100-2`,
  `PID-120-01`), along with any grid reference (`(E-1)`) and the description words. Two connectors on different
  sheets are paired when each points at the other's sheet. When there are several candidates, the pair whose
  descriptions overlap most wins. Pairs whose descriptions share no words go near the top of the queue.
  Unpaired connectors are listed with the reason: target not in this set, target in set but no reciprocal
  connector, or no drawing number readable.
- **Sheet identity** (needed for pairing) comes from the sheet register when given. Without it:
  - the system code is the most common prefix of the sheet's equipment tags;
  - the drawing number is the one that other sheets' connectors pair with that code, and that the sheet doesn't
    point to itself.

  Ties stay unknown. On sheets 0–5 the inference named 4 sheets, all correct against the title blocks, and left 2
  unknown. A sheet without a confirmed number is named "Sheet n (mostly XXX tags)" so nobody mistakes the guess
  for a fact.

## What is placeholder

- **Every signal path.** Ignition `BasePath` defaults to `PLACEHOLDER`, and `PointName` is `PLACEHOLDER_<tag>`.
  PI attributes point at `\\%Server%\PLACEHOLDER.<tag>.PV`. A drawing does not say which PLC address or historian
  point carries a value. Mapping these is a site task, ideally from the control system's I/O list.
- **Engineering units** are blank, and **data types** default to Float8 / Double. Switches and discrete signals
  need changing.
- **The measured variable** comes from the ISA-5.1 first letter (T = temperature). Plant shorthand for operated
  valves (`MOV`, `AOV`, `AORV`) gets no variable, because ISA would read MOV's M as "moisture".
- **Asset ids** (`S2-VL004`) are converter keys, not plant tags. Placeholder tags on the drawing (`FCV XXX`,
  `MSCV-XXX`) are kept as written, flagged, and never filled in.
- **Stream direction** is `unknown`. Extraction gives which items connect, not flow direction.
- **Read-only intent.** Instrument PV members are written with `"readOnly": true`, because the starter kit is for
  monitoring, never control (docs/AT_YOUR_PLANT.md). Check the property survives import on your Ignition version.
  Don't rely on it alone: enforce read-only at the OPC connection and in tag security as well.

## AF XML: not emitted

PI AF can import an XML export format, but I am not certain of its exact element names and required attributes. A
file that looks right but fails to import, or imports wrongly, is worse than none. So only the PI Builder sheet is
written. To get AF XML:

1. Build one element by hand in PI System Explorer.
2. Export it.
3. Template the converter's output from that real export.

## Risk tiers: where to spend review time

Every symbol and every connection gets a risk score (roughly, the chance it is wrong) and a tier. The queue is
sorted red first, then amber, then green, riskiest first inside each tier.

| Tier | Meaning | What to do |
|---|---|---|
| **Red** | More likely wrong than right (risk 50% or more). | Look closely at the sheet. Delete, relabel or fix. |
| **Amber** | Probably right, with at least one warning sign. | Quick check against the sheet. |
| **Green** | No strong warning sign. On the development sheets, about 1 in 20 green items was wrong (1 in 8 to 1 in 16 when each sheet was left out of the fitting). | Spot-check a sample, then accept as a batch. |

The `why` column says what raised the risk, in plain words. The rating doesn't trust the model's own confidence
much, because Codex and Gemini say 0.9–1.0 for almost everything. It uses checks that need no answer key:

- **Did the other models see it?** Claude, Codex and Gemini each read the same sheet. A symbol only one of them
  found, or a link only one of them drew, is suspect.
- **Did the same model see it twice?** Each model reads the sheet whole and again as four tiles. A symbol found in
  only one of those passes is suspect.
- **Is it on a line?** A valve or instrument with no drawn line touching it, or with a straight line running
  right through it (a real symbol interrupts its line), is suspect.
- **Is the tag sensible?** A missing tag where one is expected, or an instrument tag that doesn't read as letters
  plus a loop number. A duplicate box on the same spot points to a double count.
- **For links:** whether the model drew the link itself or only the line tracer found it, whether the tracer
  joins the two ends, and whether the ends are symbols the other passes saw.

How it was built (`scripts/confidence.py`, fit by `scripts/score_triage.py --fit`): one logistic regression for
symbols (10 signals) and one for links (7), fit on development sheets 0–5 only, with every weight forced to be zero
or positive, so a warning sign can only raise risk. Signals that didn't help got a weight of zero: placeholder tags
(placeholders are real symbols with an unassigned tag), duplicate tags, the `general` class, network size and,
notably, the model's own confidence. The green and red cut-offs were also set on the development sheets. Results:
`out/triage_<label>_<split>.md`.

**Limits a reviewer should know:**

- **It can only rank what the system output.** A symbol every model missed isn't in the queue at all. Someone still
  has to scan each sheet for missing items, especially small valves and instruments.
- **Models can agree and still be wrong.** The rating trusts agreement. When the models make the same mistake
  (they read the same drawing, and every traced run uses the same line tracer), the item can land in green or amber.
- **Without the other models' runs,** the agreement signals are neutral (0.5). The rating still works, but it
  ranks less sharply.
- **Instrument parents aren't rated here.** The risk is about "is this item real and labeled right", not "which
  equipment does it hang under". Parent flags stay in `why_check_this`.

## What must be reviewed before anything goes live

Work the queue top-down by tier (above). The converter's own flags are still in `why_check_this`. Without a risk
rating, the queue falls back to this order:

1. low extraction confidence;
2. off-page connectors that didn't pair, and pairs whose descriptions share nothing;
3. placeholder tags;
4. instruments with no drawn connection, or whose connection and position disagree;
5. other flags: merged equipment, duplicate tags, items under `Unassigned`, links to doubtful symbols;
6. everything else, including every connection.

Confidence thresholds are not comparable across models: Claude uses 0.3–0.95, while Codex and Gemini almost
always say 0.9–1.0. So a Codex queue has fewer tier-1 rows, but that does not mean Codex is more certain where it
matters.

Then:

- confirm the system names and drawing numbers;
- map the placeholders to the real I/O list;
- run the change through Management of Change before any import touches a production gateway or AF database.

## Twin-level scores (development set 0–5)

`scripts/score_twin.py`, secondary scores from docs/GOAL.md:

- **Parent accuracy.** Each answer-key instrument's parent is the nearest non-instrument asset reachable through
  connector, crossing or arrow nodes. That is compared with the twin's parent after matching symbols at IoU ≥ 0.1
  with the frozen scorer's `match()`. A position-only control is reported beside it.
- **Off-page pairing.** Counts plus the list of pairs, for checking by hand. The answer keys carry no text, so no
  automatic pairing score is claimed.

Results: `out/twin/round1-v2-named-fields/twin_scores.md`.
