# Twin outputs: from extracted sheets to a digital twin starter kit

`scripts/build_twin.py` turns a set of extracted sheets into a package a plant could load. Extraction gives a flat
list of symbols and links per sheet. The converter adds the structure a twin needs: a site/system/equipment
hierarchy, cross-sheet links, platform import files and a review queue. The converter includes OPEN100-shaped tag/off-page parsing and confidence assumptions; new sites need an adapter and validation. Every decision
records the method it used, and every item starts as `unverified`.

## One command

```
python scripts/build_twin.py --label round1-v2-named-fields --sheets 0,1,2,3,4,5 --score
```
The label names a folder of your own extraction runs under `runs/` (gitignored). Use the label from README tutorial
step 5.

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
model. Run with no argument, it produces the Tennessee Eastman outputs. Both paths validate and render the entire bundle before touching existing exports; malformed models fail nonzero without export changes. This structural gate does not approve inferred semantics or operational use. Writes are not a multi-file atomic transaction, so a filesystem failure can still leave partial output.

Two packages are committed:
- `out/twin/round1-v2-named-fields/claude/`: a small round-1 example (Claude, sheets 0–5);
- `out/twin/r2-tiles-trace/codex/`: the full 12-sheet twin from the declared method. This is the one loaded into
  Ignition.

## The files

| File | What it is | Load it into |
|---|---|---|
| `plant_model.json` | The asset model. Site → system (one per sheet) → equipment → line items → instruments, plus streams, off-page connectors and pairs, and per-item provenance (sheet, box, source run, model, confidence, status). It is a superset of `data/te_process_model.json`: `meta`, `units`, `streams`, `instruments` and `final_elements` keep their meaning, and `meta.model_kind = "extracted_twin"` tells the generator which path to take. | Your asset register, after review |
| `review_queue.csv` | One row per item (symbols and connections), riskiest first. Columns `tier` (red / amber / green), `risk_score` and `why` come from the risk rating (see "Risk tiers" below). Same plain-language and `OPS_` columns as `out/ops_review_sheet.csv`, plus `rank`, `why_check_this` (the converter's own flags), `sheet`, `symbol`, location, `tag_status` and `how_attached`. | A spreadsheet, for the reviewer |
| `ignition/tags.json` | Ignition 8 tag JSON, same shape as `out/ignition/te_tags.json`. UDT types per equipment class (`Equipment_Tank`, `Equipment_Pump`), per instrument type (`Instrument_PT`, `Instrument_TCV`, …) and per line-item class. Instances are foldered Site/System/Equipment, with an `Unassigned` folder per system. See "Ignition tag paths and UDTs" below. | Ignition Designer → Tag Browser → Import Tags (JSON) |
| `pi/pi_builder_af.csv` | PI Builder sheet (schema v2, same columns as `out/pi/pi_builder_af.csv`). Elements are Site / System / Equipment (plus `Unassigned`), with one PI Point attribute per instrument. Placeholder references are left unselected, so they are not published. **Not import-tested** | PI Builder (Excel add-in) → Publish, in the order in `pi/IMPORT_STEPS.txt` |
| `pi/custom_uoms.csv`, `pi/attribute_descriptions.csv`, `pi/IMPORT_STEPS.txt`, `pi/reconciliation.json` | Unit definitions the site must create or map; attribute descriptions (kept out of the sheet); the publish order; the reconciliation record. See [PI_MAPPING.md](PI_MAPPING.md) | Read before publishing |
| `svg/sheet_<n>.svg` | Each symbol drawn at its extracted box, each extracted connection as a straight line. Every symbol group carries `data-asset`, `data-tag`, `data-class`, `data-confidence`, `data-status` (and `data-parent` / `data-pair`). Low confidence shows red and dashed; placeholder tags show orange. | Ignition Perspective (Drawing / embedded SVG), bound by `data-asset` |

### Ignition tag paths and UDTs

A UDT (user-defined type) is Ignition's reusable tag template. `generate.py` (`twin_ignition`) writes:

- **Tag paths** of the form `Site/<system>/<equipment>/<item>`. The system folder is named from the sheet (for
  example `MSS_sheet_0`), the equipment folder is the equipment's tag (`MSS-XSS-140`), and each item is a UDT instance
  inside it. Items with no connection path to equipment go in that system's `Unassigned` folder. Names are cleaned
  to letters, digits, `_` and `-`, and made unique within their folder with a `_2`, `_3` suffix.
- **Instance names** are the item's tag. An item with no tag read keeps its converter id, such as `S0-VL001` (sheet
  0, valve 1), until a reviewer supplies the tag through the review sheet (`OPS_correct_value` = `tag=...`, applied
  with `apply_review.py`) and the files are regenerated. The id is a key for this repository, not a plant tag.
- **UDT types** are generated per group, not written as reusable templates: one per equipment class
  (`Equipment_Tank`), one per instrument tag-letter group (`Instrument_PT`, `Instrument_FIT`, `Instrument_LIT`) and one
  per line-item class. The 12-sheet twin has 37 types, because every letter group a drawing uses gets its own,
  including plant-coded ones such as `Instrument_MSIV`. All instrument types have the same members (`PV`,
  `ReviewStatus`) and parameters. To collapse them into your own templates by hand: pick or create one type (say an
  analog-input UDT), change the `typeId` of the instances that should use it in `tags.json` (or in the Tag Browser
  after import), then delete the unused types. Regenerating writes the generated types again, so do this on a copy
  you keep.

The PI sheet is an empty shell until an I/O list maps each point; placeholder references stay unselected so they are
never published. The PI mapping step is `map_pi_points.py`, from reviewer-supplied PI references
([PI_MAPPING.md](PI_MAPPING.md)).

## How the hierarchy is decided (and where it guesses)

- **Equipment** is every `tank` and `pump` symbol. A `general` symbol is promoted to equipment only when its tag
  follows the SYSTEM-TYPE-NUMBER pattern (e.g. `ACC-SX-154`). Promoted items are flagged in the queue.
- **One asset per real tag.** Equipment carrying the same real tag on several sheets (the same tank drawn on three
  sheets) becomes one asset with several appearances. This is flagged for confirmation. Placeholder and untagged
  equipment are never merged. Instruments and valves with repeated tags are not merged either; they are flagged.
- **Line items** (valves, other in-line symbols) belong to the nearest equipment along extracted connections
  through other line items only (fewest hops, then closest). If there is no such path, the item goes under
  `Unassigned`. Equipment is never guessed by position.
- **Instrument parent** is chosen by `--parent-rule` (default `along_line`, round 3). Each instrument records the
  method it actually got (`parent_method`) and, under `along_line`, why (`along_line_status`).
  - `along_line`: the sheet is re-traced with the run's own symbols and tracer options
    (`trace_connections.line_geometry`), and the parent is the first non-instrument asset reached by following the
    drawn lines from the instrument (shortest path in pixels; `along_line_px`). In order:
    1. directly along the lines (`along_line`). Assets within a quarter of a symbol side of the nearest are a tie,
       broken by position (`tie_broken_by_position`; every candidate is listed in `along_line_candidates`);
    2. else through other instruments, for a signal chain (`along_line_via_instrument_chain`, with `along_line_via`);
    3. else the `linked` rule below, with `along_line_status` = `not_on_traced_line` (no traced line touches the
       instrument, e.g. a dashed or very short leader) or `no_asset_reached_along_line`.
  - `linked` (rounds 1-2): the linked non-instrument neighbour (closest centre if several); else the first
    non-instrument reached through other instruments; else the nearest symbol by position (`geometry_nearest`, with
    the gap recorded).
  - `nearest`: the nearest non-instrument symbol by position only.

  A second opinion by position alone is always computed (`parent_agrees_with_position`). Under the `linked` rule on
  the development set, an instrument whose two opinions agreed was right about 9 times in 10 for Claude and Codex,
  and one whose opinions disagreed about 3 in 10. Under `along_line` disagreement is no longer a warning sign:
  disagreeing parents were right 12/13 (Codex), 15/17 (Claude) and 8/14 (Gemini) on the development set, because
  following the line is exactly what fixes the cases where the nearest symbol by position is wrong.
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
  valves (`MOV`, `AOV`, `AORV`) gets no variable, because ISA would read MOV's M as "moisture". Neither does a
  plant-coded tag: a letter group that starts with a system code seen on its own sheet (the sheet's system code or
  an equipment tag prefix; a code ending in S also matches without it, so MSS gives MS), such as `MSBV`, `MSIV` or
  `MSV` on a main steam (MSS) sheet. Its `variable_method` says which code matched; only its last letter is read
  (`instrument_kind` "valve (plant-coded tag)" for a ...V, none otherwise). Limits: a sheet with no
  SYSTEM-TYPE-NUMBER equipment tag (and no sheet register) has no codes to match, so plant tags on it are still
  read as ISA letters; a system code whose stem is also an ISA letter pair would hide real variables. On the OPEN100
  extraction this changes 5 of 359 instruments, all on sheet 0 (`build_twin.plant_coded`).
- **Asset ids** (`S2-VL004`) are converter keys, not plant tags. Placeholder tags on the drawing (`FCV XXX`,
  `MSCV-XXX`) are kept as written, flagged, and never filled in.
- **Stream direction** is `unknown`. Extraction gives which items connect, not flow direction.
- **Read-only intent.** Instrument PV members are written with `"readOnly": true`, because the starter kit is for
  monitoring, never control (docs/AT_YOUR_PLANT.md). Checked on Ignition 8.3.10: the property survives import, and
  outside writes are refused (V1 and V7 in [IGNITION_BUILD.md](IGNITION_BUILD.md)). Don't rely on it alone: enforce
  read-only at the OPC connection and in tag security as well. The `ReviewStatus` members are memory tags and
  stay writable by design: they are review workflow, not process data.
- **Review decisions and data points.** `scripts/apply_review.py` writes operations decisions onto the model, and
  `scripts/map_points.py` writes real data addresses from an I/O list. Regenerating then carries both into these
  files: rejected items leave them, `ReviewStatus` carries the decision, and mapped instruments get their real OPC
  server and path. See [REVIEW_LOOP.md](REVIEW_LOOP.md).
- **Scripted import.** Instead of the Designer, `scripts/ignition/build_gateway.py` imports this file into a running
  gateway over its REST API, adds Perspective screens built from `svg/`, and `verify_gateway.py` checks the result.

## PI AF: asset structure only, by decision

**PI is scoped to the asset structure, by decision.** The twin produces a PI AF hierarchy as a PI Builder sheet
(elements, templates, attributes with point references), but it has not been imported into a PI System. Why:
- **No free PI environment exists.** The 45-day developer trial is a full Windows Server install behind an account.
- **The asset structure is PI's transferable value.** PI Vision dropped plain custom-SVG import, so the graphics
  story belongs to Ignition here.
- **A historical Ignition build was tested end to end:** import, replayed values, alarms and verification. The current regenerated project then passed V1–V8 and a 23-route browser contract in a disposable Ignition gateway, and the corrected 24-view build passed again with 24 routes ([native acceptance page](IGNITION_ACCEPTANCE.md)). PI import has not been run.

To validate at a site, publish the sheet to a development AF database with PI Builder, check the hierarchy in PI
System Explorer, then separately configure and verify real PI point bindings. The current exporter retains
`%Server%`/placeholder point references; `map_points.py` maps OPC addresses for Ignition and does not fill PI bindings.

### AF XML: not emitted

PI AF can import an XML export format, but I am not certain of its exact element names and required attributes. A
file that looks right but fails to import, or imports wrongly, is worse than none. So only the PI Builder sheet is
written. To get AF XML:

1. Build one element by hand in PI System Explorer.
2. Export it.
3. Template the converter's output from that real export.

## Loading and checking the platform files

Two tools sit after `generate.py`: one checks a PI Builder sheet offline, the other pushes a tag file into an
Ignition gateway. Neither approves anything; the review below still comes first.

### Check a PI Builder sheet offline: `scripts/check_pi_export.py`

```
python scripts/check_pi_export.py out/pi/pi_builder_af.csv
python scripts/check_pi_export.py out/twin/r2-tiles-trace/codex/pi/pi_builder_af.csv --json   # full report
```

It compares the sheet with the vendor conventions recorded in `data/pi_builder_reference.json` (each with its
source and page). It is not a PI Builder import and cannot say a file will import.

- **Errors** (exit 1) are internal inconsistencies only: duplicate rows (same Parent, Name and ObjectType), an
  attribute whose Parent is not an element in the file, an element row carrying attribute fields, a PI Point
  reference with no config string, a selected row whose point is a placeholder, an `ElementTemplate` with a Parent,
  and a missing required column or an `ObjectType` the documented sheets don't show.
- **Warnings** (exit 0) need a person: attribute types and units with no vendor evidence, units defined in the
  `custom_uoms.csv` beside the sheet (the site creates or maps them), attributes with no unit, placeholder rows held
  back, templates used before they are defined or not defined at all. A unit the check does not recognise
  (`furlongs`) is a warning that says "not recognised", not an error: the vendor unit list is a sample of AF's
  default UOM database, so absence from it is not proof.
- Exit 2: the file can't be read.

On the committed Tennessee Eastman sheet (output as printed, 2026-10-29):

```
OFFLINE CONVENTION CHECK ONLY; not a PI Builder import, not proof the file will import; NOT import-tested on a licensed PI system
50 rows; object types {'ElementTemplate': 6, 'Element': 7, 'Attribute': 37}
WARN    units ['kPa g', 'kg/h', 'kscmh', 'mol%'] are defined in custom_uoms.csv: create them, or map them to the site's own units, before publishing
no errors, 1 warning to review
```

On the 12-sheet twin's sheet it reports 454 rows, no errors, and two warnings: 359 attributes have no unit, and
358 placeholder point references are left unselected, so PI Builder will not publish them. More on the evidence and
on what a plant with PI would run next: [PI_MAPPING.md](PI_MAPPING.md).

### Push a tag file into Ignition: `scripts/ignition/import_tags.py`

```
python scripts/ignition/import_tags.py out/ignition/gateway/twin_provider.json --provider Twin
```

It sends one tag JSON file to the Ignition 8.3 REST API (`/data/api/v1/tags/import`, JSON, into the provider
named by `--provider`). Pass `--provider Twin`: the committed Perspective screens bind to a provider of that name
(it is also the default). `--collision` sets what happens to tags that already exist: `Overwrite` (default),
`Abort`, `Rename`, `Ignore` or `MergeOverwrite`. It prints the gateway's status and reply, and exits 0 only when the
call succeeds with no failed tags.

The connection settings come from the environment (or a private file named by `IGNITION_ENV_FILE`), never from the
repository: `IGNITION_URL` (default `https://localhost:8043`), `IGNITION_API_TOKEN` (an API key from Platform >
Security > API Keys) and optionally `IGNITION_CA_FILE`. Without a CA file it skips certificate checks only for a
gateway on `localhost`/`127.0.0.1` and refuses any other host (`scripts/ignition/gw.py`). A missing file or one that
is not JSON is refused (exit 2) before any gateway is contacted.

The tested path imports `twin_provider.json`, which `scripts/ignition/build_gateway.py --write-only` writes (the TE
model plus this twin): see [IGNITION_QUICKSTART.md](IGNITION_QUICKSTART.md). A package's own `ignition/tags.json`
has the same provider-level shape and goes through the same call, but importing it on its own this way has not been
run here. Point it only at a disposable or development gateway, never a production one, until the review below is
done; it was not run for this page.

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
- **Instrument parents get a second opinion, not a score.** The risk score is about "is this item real and
  labeled right". For "which equipment does it hang under", the twin is also built with the other parent rule
  (`along_line` vs `linked`). When the two pick different equipment, the instrument is at least amber and `why`
  names both candidates (`parent_second_opinion` in `plant_model.json`). On the development sheets this happened
  to about 1 instrument in 20, and the along-the-line choice was right in 16 of 18 such cases. So it means "decide
  which", not "the parent is wrong". Other parent flags stay in `why_check_this`.

## What must be reviewed before anything goes live

Work the queue top-down by tier (above). The converter's own flags are still in `why_check_this`. Without a risk
rating, the queue falls back to this order:

1. low extraction confidence;
2. off-page connectors that didn't pair, and pairs whose descriptions share nothing;
3. placeholder tags;
4. instruments with no drawn connection, or (under the `linked` rule only) whose connection and position disagree;
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

Results: `out/twin/round1-v2-named-fields/twin_scores.md` and `out/twin/r2-tiles-trace/twin_scores.md`.
