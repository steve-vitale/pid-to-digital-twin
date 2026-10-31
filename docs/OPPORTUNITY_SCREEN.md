# The opportunity screen: questions worth asking of a drawing

**Why it matters:** Many energy and controls questions can be spotted on a P&ID before anyone collects data: a throttled pump, high-pressure steam let down for a low-temperature job, heat dumped to cooling water, a loop with no controller. A solo engineer rarely has time to look. This lists the questions with the evidence by tag and exactly what to collect, and where, to settle each one, without inventing a savings number.

`scripts/question_engine.py` runs a list of engineering questions over a plant model and writes, for every place a
question applies, what the drawing shows, what is still missing, exactly where to get it, and how the answer
settles the question. Run every question and you get a draft energy and controls screen. Run one question and you
get the answer to "what do I need to collect, and from where, to answer this?". Examples, with a hand check of every
finding: [`examples/opportunity-screen/`](../examples/opportunity-screen/README.md).

Decision rules describe which investigations to pursue or conclude. In this screening language, "close it" means
close the investigation, never operate or close equipment. Findings do not authorize operational changes.

```sh
python -S scripts/question_engine.py --list
python -S scripts/question_engine.py --model data/te_process_model.json --loops examples/loop-audit/te_loops.csv --out out/screen-te
python -S scripts/question_engine.py --model data/bayer_rt/process_model.json --question E1 --question H4
python -S scripts/question_engine.py --model my-bundle/plant_model.json --out out/screen-site
python -S scripts/question_engine.py --rollup out/screen-site-a --rollup out/screen-site-b --out out/rollup
```

Stdlib only, offline, no model calls. Without `--out` it prints the screen.

Before writing either report, the engine checks both destinations against the model, catalog, loop list and
every supplied schedule, including any local I/O-description file it reads. Roll-ups check their catalog and
input screens too. An overlapping input, aliased output pair or invalid target is refused before either report
changes. Both reports are rendered before writing; this is not a lock against concurrent filesystem changes.
Normal refresh into the same folder is allowed when inputs have different filenames. Choose another output
folder to keep an earlier report pair.

For company-specific questions, use a working copy of `data/questions.json` with `--catalog`:

```sh
python -S scripts/question_engine.py --model my-bundle/plant_model.json --catalog my-bundle/questions.json --out out/screen-site
```

The screen's `catalog` field and readable header name the selected file. Paths outside this repository are
displayed as a filename to avoid disclosing local directories. Keep the actual catalog with the packet and record
its revision and content hash in the [plain brief](../examples/first-pilot/pilot-brief.md); a displayed filename is
not a version or authority check. The catalog supplies the investigation rules and collection instructions, so it
is evidence needed to interpret the generated finding too.

For your own model, add `--schedule` only for your corresponding records after checking their sheet/asset
identities and scope. The committed OPEN100 schedules describe that public source, not arbitrary site equipment.
Its complete scheduled example is in the [worked-example commands](../examples/opportunity-screen/README.md).

## Refresh after reviewing the model

Apply your decisions with `apply_review.py`, then run the screen again with the same loop list, schedules and
question selection. Explicit `ops_review.status = rejected` records are excluded from triggers, evidence,
data-request locations, required model kinds and relationships. Rejected records and history stay in the model;
the screen lists the recorded rejections. Non-rejected children remain eligible without references to rejected
units, parents or streams. No replacement ownership or recursive rejection is inferred. A supplemental loop list
cannot silently reinstate a rejected controller; live duplicate tags remain eligible and require review.

Missing/unverified review stays eligible and does not mean approval. Malformed review metadata is refused before
output writes. The [offline worked refresh](../examples/opportunity-screen/review-refresh/README.md) follows three
fictional decisions through the actual CLIs, checks changed questions, repeats the review and explicitly reinstates
the items. It uses invented equipment and establishes software behavior only. For the first investigation, carry
the finding IDs, source revision, answers and remaining evidence requests into the
[question and pilot brief](../examples/first-pilot/README.md). As colleagues contribute, take the packet into the
company's shared context and decision system; that system owns ongoing review, responsibility and history.

## What it is, and what it is not

A solo plant engineer rarely has time for an energy audit, but usually has the drawings. Most of the first audit
day is spent asking the same questions of them: is this pump throttled when it could run on a drive? Is
high-pressure steam doing a low-temperature job? Is heat thrown into cooling water that another stream needs? Which
readings has nobody automated? Is this utility metered? The engine asks those questions for you and hands back a
collection list.

It is a screen, not an audit. A finding means the drawing shows a pattern worth a question. It never means the
plant wastes energy, and the engine never computes savings, dollars or energy for your plant. Each question carries
what a public source says about the typical benefit, quoted as written, with the source and its license. Those
are general figures for plants in general.

**What it covers, and what it doesn't yet.**
- The 50 questions cover pumps, fans, steam, boilers and fired heaters, compressed air, cooling water, heat grade,
  metering, controls, a few emissions and safety checks, and (since 2026-10-29) refrigeration plant (head pressure,
  suction pressure, compressor part load, defrost, condenser heat recovery, compressor power metering) and ovens,
  dryers and fryers (exhaust heat recovery, burner air-fuel ratio, exhaust humidity control) ([the
  questions](#the-questions)). Refrigerated spaces themselves (doors, infiltration, lighting) are not on a P&ID and
  are not asked about.
- One site per run; `--rollup` then combines several runs into one list ([the roll-up](#several-sites-the-roll-up)).
  The roll-up does not weigh sites against each other: there are no savings to weigh.
- The worked examples are a chemical process simulation (Tennessee Eastman), a chemical unit from a public
  investigation report (Bayer), the sheets of a power-plant design (OPEN100) and an ILLUSTRATIVE synthetic food plant
  section written to exercise the refrigeration and oven questions. None is a plant's own data, and no refrigeration
  or oven question has been checked against a real food plant's complete drawing. A separate
  [historical refrigeration subset](../examples/opportunity-screen/millard/README.md) exercises E30 on two
  source-authored records from the CSB Millard bulletin and carries its missing evidence into a first-question
  brief. It is a development example, not a test of full plant coverage, actual defrost initiation or safe controls.

## The three evidence states

Every data request is in one of three states, and the output says which:

| State | Meaning | What the request says |
|---|---|---|
| **on drawing** | The value is on the drawing or model | Nothing to collect; the value is quoted as evidence with the model field it came from |
| **blank on drawing** | The drawing prints a field for it and leaves it empty (or writes a placeholder such as `XXX`) | Fill that field: "the blank HP field on the sheet 2 equipment schedule, entry CND-PU-162" |
| **not on drawing** | The drawing has no place for it | Where it lives instead, most direct first: a historian tag if the model maps one (named), the DCS/PLC configuration, a nameplate, the vendor datasheet, maintenance records, utility bills, or a walkdown with a named instrument |

The OPEN100 drawings show why the middle state matters. They are template drawings: every equipment schedule prints
CAPACITY, DISCHARGE, RPM and HP (or OD, LENGTH and MATERIAL) and leaves them blank. A screen that treated those as
"not on the drawing" would send you to the nameplate for a number the drawing was designed to hold.

A request with several parts (rated flow and head, motor power and speed) stays open until every part is found:
the parts on the drawing are quoted as evidence and the request lists what is still needed **for each subject**.
By default, `field_scope: anchors` checks each triggering model record independently. Pressure on one steam
supply cannot combine with temperature on another, and a complete supply cannot hide an unknown sibling.
Related equipment or instruments remain context, without filling another subject's fields. The
[two-supply regression example](../examples/opportunity-screen/field-coverage/README.md) shows this distinction.

A catalog author can explicitly choose `field_scope: unit` when the request concerns the finding's owning
equipment record. H4 uses that scope for cooling-water supply temperature and cooler duty. Only the actual
equipment owner selected by unit grouping is checked; related role names do not select an owner. If no owner
is identified, every field remains requested with a scope note. This declares where to look, without proving
common physical conditions, timing, units or the correctness of the supplied value.

Open field requests retain `field_scope`, `field_coverage` (subject identity, each field's present/blank/absent
state and locator) and `still_needed`. `already_on_drawing` names fields supplied on at least one subject;
it can overlap the remaining list when another subject lacks that field. Read the subject coverage rather than
treating either list as a plant-wide answer. Null, empty/whitespace and recognized placeholder values are blank;
zero and false remain supplied values. Conflicting facts/schedules and duplicate case variants are not resolved.
This accounting covers the fields encoded in a request, not everything its prose may require. E5's fan curve
and H3's hours/power contract remain [open catalog gaps](STATUS.md#known-defects); field completion alone does
not establish that the full engineering collection task is satisfied.

Historian names come from the model: TE's recorded signal indices (`XMEAS(n)`, `XMV(n)`), the Bayer model's
digitized Fig 11 series, and an extracted twin's mapped data points (`data_point`). Where none is mapped the request
says so. A request only names signals that measure the quantity it asks for: a valve's position or controller
output is never offered as a flow ("only the valve position is recorded; flow needs a meter or a calibrated valve
curve"), and a cooling water outlet temperature is not offered as the supply temperature. A mapped point whose I/O
list row (in `data/io_lists/`) describes it as synthetic is labelled SYNTHETIC, not plant data. Placeholder tags
(`FCV XXX`) are marked as placeholders in the evidence.

## Inputs

- `--model`: a hand-built process model (`data/te_process_model.json`, `data/bayer_rt/process_model.json`, or one
  from `generate.py`) or an extracted twin (`plant_model.json` from `import_site_drawing.py` or `build_twin.py`).
- `--loops`: a loop list CSV in the `loop_audit.py` format (`controller,measurement,output[,description]`). An
  extracted drawing has no controllers, so without this the controller questions (C2, C6) are reported as
  "not checked".
- `--schedule` (repeatable): equipment schedule entries per sheet, `{"sheets": {"2": [{"tag", "service",
  "fields"}]}}`. `fields` maps each printed field to its value, with `null` for a printed blank. A later file's
  fields object replaces the earlier fields object for a matching entry; it does not merge individual field
  keys. Supply a complete replacement when combining a tag/service list with a fields transcription.
- `--question ID` (repeatable): run only these questions.

A missing, empty or malformed file, a model with no units or instruments, a loop list without the
`controller,measurement,output` columns, or a schedule without `sheets` is refused with a message saying which file
and why (exit code 2), never a traceback or an empty "found nothing" screen.

## Outputs

- `questions.json`: the graph-export questions shape. Each finding has `id` (question@group), `question_id`,
  `question`, `family`, `about`, `assets` (`id` and `tag`), `evidence` (role, text, the model field), `data_requests`
  (item, state, ordered `where`, `how`), `decision_rule`, `typical_benefit` (source wording, source keys and
  titles, IAC/ITAC code), `limits` and `status: "asked"`. It also lists the questions that found nothing
  (`did_not_fire`), the ones that could not be checked (`not_checked`) and the equipment left out of the screen
  (`left_out`). `python -S scripts/graph_export.py MODEL --questions questions.json` attaches it to the twin graph.
  When applicable, `review_exclusions` records explicit model rejections and `loop_rows_rejected` names supplemental
  controller rows excluded by those decisions. Empty fields are omitted, preserving older unreviewed examples.
- `screen.md`: the same, grouped by family, readable on its own, with a "how to read this" note at the top and the
  cited sources with their licenses at the bottom.

## Several sites: the roll-up

```sh
python -S scripts/question_engine.py --rollup examples/opportunity-screen/food --rollup examples/opportunity-screen/bayer \
    --out examples/opportunity-screen/rollup-food-bayer
```

Each `--rollup` is the `--out` folder of one site's screen (or `NAME=FOLDER` to name the site; otherwise the folder's
name is used). It writes `rollup.json` (`schema: opportunity-rollup-1`) and `rollup.md`: every question that fired
anywhere, listed once, with the sites and assets it fired on (`finding_id`, `about`, `assets`), the sites where it was
asked and found nothing (`quiet_at`), could not be checked (`not_checked_at`) or was not run (`not_run_at`), and its
data requests merged by item. Per site, the places every finding there shares are listed once (`where`) and the rest
per finding (`where_by_finding`), so a request such as "utility flow to this user" can be planned across all sites at
once. Field coverage and partial answers remain under each site's `coverage_by_finding`; subjects and values are
never pooled across findings or sites. Questions are ordered by how many sites they fired at, then by findings, then catalog order. That order says
where a question is common, not where the money is: the roll-up computes no savings and ranks nothing by value. A
folder with no `questions.json`, a file that is not a screen, a screen with question ids this catalog does not know,
or the same site named twice is refused (exit code 2). Example:
[`examples/opportunity-screen/rollup-food-bayer/rollup.md`](../examples/opportunity-screen/rollup-food-bayer/rollup.md).

Use `--catalog` for a custom roll-up too. Its JSON names that catalog, and its Markdown adds the custom filename.
Before combining findings, the engine refuses disagreement with the selected catalog in the embedded question,
family, decision rule, typical-benefit record or limits, and emitted collection items/instructions. Findings must
identify a catalog question; request lists must contain records with matching item/instruction strings. Conflicting
instructions for one selected-catalog request item are also refused before publication.
New field coverage must agree with the selected catalog's effective field scope. Malformed coverage is refused.
Legacy screens without scope/coverage remain readable, but cannot establish which subject policy produced them;
regenerate them under the reviewed catalog before using them as evidence of the current completeness behavior.

This checks visible finding conflicts, not complete catalog equivalence. The input JSON does not retain all trigger
rules, exclusions, source URLs/licenses or the meaning of quiet/unrun questions. A request omitted from a screen may
already have been satisfied on the drawing, so omission cannot prove that the catalog never requested it. Retain
the exact original catalogs and their revisions/hashes; after rule changes, reconcile them and regenerate the
screens under the reviewed catalog. Matching IDs or filenames alone do not establish the same investigation.

## The questions

`data/questions.json` holds 50 questions as data: energy (E1-E24, E27-E32), heat grade (H1-H6), metering (C1,
C12), controls (C2-C7, C10, C11), emissions (E25, E26) and safety questions to verify (C8, C9). `--list` prints them. E1-E26 and C1-C10
come from a review of public DOE, LBNL, EPA and HSE documents; the wording was copied from text extracts of those
documents. H1-H4 are the "high-grade heat used for low-grade duty" family:

| ID | Question | Closest source |
|---|---|---|
| H1 | Is high-grade steam let down, bypassed or desuperheated for a duty a lower grade could serve? | S6 (PRV to backpressure turbogenerator): its condition of a constant 3,000 lb/hr and a 100 psi drop. No source gives a number for desuperheater or bypass stations |
| H2 | Is high-grade (or unknown-grade) steam doing a low-temperature job? | S19 (pinch) wording; S6 for the letdown. No source gives a number for matching steam grade to duty |
| H3 | Is electric resistance heat serving a low-temperature load another source could carry? | No source in the reviewed set |
| H4 | Is heat rejected to cooling water at a temperature another user could use? | S19 (pinch) wording, no % stated; S11 for air compressors only. Never fires on equipment that cools the cooling water itself (a cooling water cooler, air-cooled exchanger or cooling tower) |

**Refrigeration, ovens, dryers and fryers** (added 2026-10-29 after an energy manager's walkthrough for a multi-site
food manufacturer). Every quote names its page and was checked word for word against a text extract of the PDF at
the source's URL; each source entry in `data/questions.json` records that file's SHA-256 under `checked`.

| ID | Question | Fires on | Source (page) |
|---|---|---|---|
| E27 | Is the refrigeration condensing (head) pressure held higher than the weather allows? | a condenser whose name or service names the refrigerant; quiet if a floating head or wet-bulb reset is named | S25 pp. 62, 65 (2% to 3% per degree C of condensing temperature, as reported there) |
| E28 | Is each suction level colder than its warmest load needs? | refrigeration compressors (one finding per model), shown with suction pressures and the freezers, cold stores and chillers | S25 p. 63 (about 8% for a two-stage system raised from -30 °F to -20 °F) |
| E29 | Does a refrigeration compressor carry part load on its slide valve with no speed control? | a refrigeration compressor with no drive (VFD, VSD, ASD, SC, SIC) on it | S25 pp. 59, 63 |
| E30 | Are evaporators defrosted on a fixed timer? | an evaporator or unit cooler with defrost drawn on it; quiet with a coil differential pressure or demand defrost | S25 pp. 59, 66 (no %) |
| E31 | Does an oven, dryer or fryer send hot exhaust to atmosphere with no heat recovery? | an oven, dryer, fryer, roaster or dehydrator; quiet if a heat recovery item is on it or at the other end of a stream from it | S26 pp. 104, 107; S25 p. 90 (up to 30% of spray dryer exhaust heat) |
| E32 | Is the burner air-fuel ratio checked, with no flue O2 drawn? | an oven, dryer or fryer with a burner or fuel supply; quiet with an O2 analyser | S27 p. 1 (no %; excess air is part of a drying process) |
| H5 | Is refrigeration condenser heat rejected while a low-grade duty is heated another way? | refrigeration plant plus a hot water, CIP, wash water, floor or space heating duty anywhere; quiet with a refrigeration desuperheater or heat recovery | S25 p. 64 (no %) |
| H6 | Could oven, dryer or fryer exhaust heat serve a low-grade duty elsewhere? | the E31 units, plus a low-grade duty anywhere | S28 p. 1; S26 p. 107 (no %) |
| C11 | Is a dryer's or oven's exhaust rate set by hand rather than by humidity? | a dryer or oven with no humidity, dew point or moisture measurement | S26 p. 104 (no %) |
| C12 | Is refrigeration compressor power measured? | refrigeration compressors with no power, current or energy measurement | S25 p. 58 (3% for monitoring, one winery review as reported there) |

Anti-triggers, each in the tests: an air compressor, a recycle gas compressor, a process condenser on cooling water,
a power-plant air-cooled condenser, a refrigerated or desiccant compressed air dryer and a nuclear steam dryer are not
refrigeration plant, ovens or dryers. Adding these also tightened older questions, without changing any finding in
the TE, Bayer or OPEN100 examples: E19, E22, E23 and C7 no longer read an air dryer, filter, separator, receiver or
aftercooler as an air compressor; E22's air storage check no longer counts an ammonia receiver or a cold store; E26
no longer reads an oven, dryer or fryer exhaust as a relief or process vent. And a flow request no longer adds "only
a valve is drawn on this line, with no flow measurement" when a flow meter is drawn on the same line (one line each
in the TE and Bayer E18 findings changed: FV-119 beside FT-119, HV-108 and TV-104C beside FT-106).

Each question has: `applies_when` (the triggers), `evidence_fields`, `data_requests`, `decision_rule`,
`typical_benefit` (`wording`, `source`, `arc`) and `limits`.

## How to add a question

Add an entry to `questions` in `data/questions.json` or your working copy; no code change is needed for anything
the trigger language covers. `fields_help` in the file documents every key. The example below illustrates that format:

```json
{"id": "E99", "family": "energy", "question": "Is this agitator running at full speed all the time?",
 "applies_when": {
   "anchor": {"kind": ["equipment"], "type_text": "agitator|mixer", "tagged": true},
   "group_by": "unit",
   "without": [{"select": {"text": "\\bVFD\\b|\\bS(C|IC)-\\d"}, "relation": "near", "max_hops": 2}],
   "absent_note": "no speed control drawn on the agitator"},
 "evidence_fields": ["agitator tag", "no speed control"],
 "data_requests": [
   {"item": "Motor rating", "fields": ["HP"], "where": [{"place": "nameplate", "what": "motor"}], "how": "Copy rated kW."},
   {"item": "Run hours", "where": [{"place": "historian", "for": "trigger"}, {"place": "records", "what": "operator logs"}], "how": "Hours per year."}],
 "decision_rule": "Worth a look when it runs long hours on a duty that varies.",
 "typical_benefit": {"wording": "No source found; report as qualitative only.", "source": [], "arc": null},
 "limits": null}
```

- An **anchor** is the item that triggers the question (equipment, an instrument, a valve, a stream, an off-page
  connector...). A list of anchors means any of them.
- **with** clauses must all find a related item; **without** clauses must find none; **also_show** quotes related
  items as evidence if present. Relations: same unit, same stream, same unit and same utility, another unit, the
  discharge side, near, linked (a stream drawn from or to the unit, an item on that stream, or the equipment at its
  other end: an exhaust going to a heat recovery exchanger), a controller that drives it, a controller or interlock
  that reads it, anywhere.
- **quantity** on a historian place (`flow`, `temperature`, `pressure`, `power`, `composition`, `position`) limits
  it to signals that measure that quantity; **match** is a regex the item must match (for example supply versus
  return).
- **fields** in a data request are looked up in the model's facts and the equipment schedule, which is how the
  three evidence states are decided.
- Copy the source's wording exactly. If no source has a number, say so in the wording (the tests insist that a
  question with no source key says it has none). Never write a figure for a specific plant.

For changes to the repository catalog, run `python -S scripts/test_question_engine.py` and regenerate the examples
(the command lines are in [`examples/opportunity-screen/README.md`](../examples/opportunity-screen/README.md)).
Those tests cover the committed catalog. For your working copy, run with `--catalog`, review the emitted findings
and collection instructions against the intended sources, and retain the reviewed file with the first packet.

## Left out on purpose

`screen_exclusions` in the catalog removes systems a plant engineer should not be screening for energy or controls
changes. Today that is the OPEN100 nuclear reactor coolant (RCS), chemical and volume control (CVCS) and residual
heat removal (RHR) systems: safety-related design changes there go through the licensing basis. The excluded
equipment is listed under "Left out" in every screen.

## Sources and licenses

| Key | Source | License |
|---|---|---|
| S1-S8 | DOE AMO steam tip sheets #1, #2, #3, #9, #17, #20, #26B and the *Steam System Sourcebook* | Public domain (US federal) |
| S9, S10 | DOE compressed air tip sheets #3, #9 | Public domain |
| S11 | DOE + Compressed Air Challenge, *Compressed Air Sourcebook*, 3rd ed. | Mostly federal; reuse of CAC content unclear |
| S13, S14, S15 | DOE + Hydraulic Institute pumping sourcebook, pumping tip #6, *Variable Speed Pumping* (with Europump) | S14 public domain; S13, S15 unclear for the co-authors' content |
| S16, S17 | DOE motor and fan sourcebooks | Federal; contractor- or AMCA-co-produced content unclear |
| S18 | DOE process heating tip #8 | Public domain |
| S19 | LBNL-56183, Worrell & Galitsky, refinery ENERGY STAR guide | DOE-lab report: unclear, freely citable; its tables quote older sources, cited "as reported in LBNL-56183" |
| S20 | EPA Natural Gas STAR, *Installing Vapor Recovery Units on Storage Tanks* (archived) | Public domain |
| S21 | DOE FEMP Best Management Practice #10, cooling towers | Public domain |
| S22 | FEMP *Metering Best Practices* 3.0 (PNNL-23892) | Contractor-prepared: unclear; buildings-focused figures |
| S23 | UK HSE, *Better Alarm Handling* (CHIS6) | Crown copyright, generally Open Government Licence; verify |
| S24 | DOE IAC/ITAC database (itac.university) | No license or terms stated: unclear |
| S25 | LBNL-6261E, Brush, Masanet & Worrell, dairy processing ENERGY STAR guide (2011) | DOE-lab report for US EPA: unclear, freely citable; figures from older sources quoted "as reported" |
| S26 | LBNL-59289-Revision, Masanet, Worrell, Graus & Galitsky, fruit and vegetable processing ENERGY STAR guide (2008) | As S25 |
| S27, S28 | DOE process heating tip sheets #2 (burner air-fuel ratios) and #10 (waste heat for external processes) | Public domain |

Full titles and URLs are in `data/questions.json` under `sources`. S12 is unused. Where a source quotes dollar
figures (cost per kW, a partner's annual saving, IAC average savings) they are left out on purpose: they assume one
plant's prices and hours.

## Keep the answers and test one useful decision

`questions.json` is the handoff from screening to investigation. Its stable finding IDs and exact asset/stream
references let the [context register](CONTEXT_REGISTER.md) retain answers, owners, dates and evidence revisions
without editing the starting model. The [Bayer bridge example](../examples/context-register/bayer/README.md) runs
the actual E18 screen and attaches a proposed partial answer from a public narrative. The original three collection
requests, decision rule and limits remain visible; historical source text does not establish actual duty overlap
or savings. Changed supporting evidence reopens the affected answers when the register is refreshed.

Choose one finding with the [first-pilot brief](../examples/first-pilot/README.md). Name the operational decision,
baseline, evidence owner, decision-maker and stop conditions before collecting the trial result. The engine
generates investigation prompts; the company chooses the priority and decides whether the result supports a next
step. It is most developed for energy and utility questions, not a complete transformation roadmap.

## Honest limits

- **There is no public method for screening a P&ID for energy opportunities.** The closest citable building blocks
  are the DOE sourcebooks' "indications of oversized pumps/fans" lists, the steam sourcebook's table of common
  improvement opportunities, and the IAC recommendation codes. The triggers here are this project's own, built from
  those, and are not a standard.
- **The typical benefits are the sources' general figures,** mostly from US industry or refineries, sometimes from
  buildings (S22) or dairy, fruit and vegetable or winery reviews (S25, S26). They say nothing about your plant.
- **The refrigeration questions fire on names.** A compressor or condenser counts as refrigeration plant only when
  its own name, type or service says ammonia, NH3, R-717, a refrigerant number or refrigeration. A drawing that labels
  an ammonia compressor only "K-201 SCREW COMPRESSOR" gets the generic compressor questions and none of these; give
  the service in the equipment schedule (`--schedule`) or the model. The refrigeration, oven, dryer and fryer
  questions have been run on a synthetic model only.
- **IAC/ITAC numbers are averages from the browse pages,** read through a summarizing fetch and not re-verified
  against the downloadable database. Averages are skewed badly by outliers (one code shows a 1,201-year average
  payback). Medians and quartiles per code would need the database download (about 15.7 MB); that was not done
  here, and average dollar figures are left out entirely.
- **A drawing only shows so much.** Valve opening, run hours, insulation and trips are usually not on a P&ID.
  "Not drawn" is not "not there": every finding is a question for someone who knows the plant.
- **Extracted drawings carry extraction errors.** Links have no direction, equipment classes can be wrong (the
  OPEN100 air-cooled condenser fans were read as pumps) and off-page attribution to equipment is a guess. The rules
  that walk links stop at other equipment and say when direction is unknown, but check every finding against the
  drawing. The examples' README lists each one checked and the ones judged doubtful.
