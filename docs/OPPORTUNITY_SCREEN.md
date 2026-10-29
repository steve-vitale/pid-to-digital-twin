# The opportunity screen: questions worth asking of a drawing

**Why it matters:** Many energy and controls questions can be spotted on a P&ID before anyone collects data: a throttled pump, high-pressure steam let down for a low-temperature job, heat dumped to cooling water, a loop with no controller. A solo engineer rarely has time to look. This lists the questions with the evidence by tag and exactly what to collect, and where, to settle each one, without inventing a savings number.

`scripts/question_engine.py` runs a list of engineering questions over a plant model and writes, for every place a
question applies, what the drawing shows, what is still missing, exactly where to get it, and how the answer
settles the question. Run every question and you get a draft energy and controls screen. Run one question and you
get the answer to "what do I need to collect, and from where, to answer this?". Examples, with a hand check of every
finding: [`examples/opportunity-screen/`](../examples/opportunity-screen/README.md).

```sh
python -S scripts/question_engine.py --list
python -S scripts/question_engine.py --model data/te_process_model.json --loops examples/loop-audit/te_loops.csv --out out/screen-te
python -S scripts/question_engine.py --model data/bayer_rt/process_model.json --question E1 --question H4
python -S scripts/question_engine.py --model my-bundle/plant_model.json \
    --schedule data/open100_equipment_schedule.json \
    --schedule examples/opportunity-screen/open100_schedule_fields.json --out out/screen-site
```

Stdlib only, offline, no model calls. Without `--out` it prints the screen.

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
- The 40 questions cover pumps, fans, steam, boilers and fired heaters, compressed air, cooling water, heat grade,
  metering, controls and a few emissions and safety checks ([the questions](#the-questions)). There are no questions
  yet for refrigeration or ammonia systems, ovens or dryers.
- One site per run. There is no multi-site roll-up; to compare sites, run each one and combine the outputs yourself.
- The worked examples are a chemical process simulation (Tennessee Eastman), a chemical unit from a public
  investigation report (Bayer) and the sheets of a power-plant design (OPEN100). None is a plant's own data.

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
the parts on the drawing are quoted as evidence and the request lists what is still needed.

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
  "fields"}]}}`. `fields` maps each printed field to its value, with `null` for a printed blank. Later files add to
  earlier ones, so a tag-and-service list and a printed-fields transcription can be kept apart.
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
- `screen.md`: the same, grouped by family, readable on its own, with a "how to read this" note at the top and the
  cited sources with their licenses at the bottom.

## The questions

`data/questions.json` holds 40 questions as data: energy (E1-E24), heat grade (H1-H4), metering (C1), controls
(C2-C7, C10), emissions (E25, E26) and safety questions to verify (C8, C9). `--list` prints them. E1-E26 and C1-C10
come from a review of public DOE, LBNL, EPA and HSE documents; the wording was copied from text extracts of those
documents. H1-H4 are the "high-grade heat used for low-grade duty" family:

| ID | Question | Closest source |
|---|---|---|
| H1 | Is high-grade steam let down, bypassed or desuperheated for a duty a lower grade could serve? | S6 (PRV to backpressure turbogenerator): its condition of a constant 3,000 lb/hr and a 100 psi drop. No source gives a number for desuperheater or bypass stations |
| H2 | Is high-grade (or unknown-grade) steam doing a low-temperature job? | S19 (pinch) wording; S6 for the letdown. No source gives a number for matching steam grade to duty |
| H3 | Is electric resistance heat serving a low-temperature load another source could carry? | No source in the reviewed set |
| H4 | Is heat rejected to cooling water at a temperature another user could use? | S19 (pinch) wording, no % stated; S11 for air compressors only. Never fires on equipment that cools the cooling water itself (a cooling water cooler, air-cooled exchanger or cooling tower) |

Each question has: `applies_when` (the triggers), `evidence_fields`, `data_requests`, `decision_rule`,
`typical_benefit` (`wording`, `source`, `arc`) and `limits`.

## How to add a question

Add an entry to `questions` in `data/questions.json`; no code change is needed for anything the trigger language
covers. `fields_help` in the file documents every key. In short:

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
  discharge side, near, a controller that drives it, a controller or interlock that reads it, anywhere.
- **quantity** on a historian place (`flow`, `temperature`, `pressure`, `power`, `composition`, `position`) limits
  it to signals that measure that quantity; **match** is a regex the item must match (for example supply versus
  return).
- **fields** in a data request are looked up in the model's facts and the equipment schedule, which is how the
  three evidence states are decided.
- Copy the source's wording exactly. If no source has a number, say so in the wording (the tests insist that a
  question with no source key says it has none). Never write a figure for a specific plant.

Then run `python -S scripts/test_question_engine.py` and regenerate the examples (the command lines are in
[`examples/opportunity-screen/README.md`](../examples/opportunity-screen/README.md)).

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

Full titles and URLs are in `data/questions.json` under `sources`. S12 is unused. Where a source quotes dollar
figures (cost per kW, a partner's annual saving, IAC average savings) they are left out on purpose: they assume one
plant's prices and hours.

## Honest limits

- **There is no public method for screening a P&ID for energy opportunities.** The closest citable building blocks
  are the DOE sourcebooks' "indications of oversized pumps/fans" lists, the steam sourcebook's table of common
  improvement opportunities, and the IAC recommendation codes. The triggers here are this project's own, built from
  those, and are not a standard.
- **The typical benefits are the sources' general figures,** mostly from US industry or refineries, sometimes from
  buildings (S22). They say nothing about your plant.
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
