# P&ID → Digital Twin Jumpstart

[![tests](https://github.com/steve-vitale/pid-to-digital-twin/actions/workflows/tests.yml/badge.svg)](https://github.com/steve-vitale/pid-to-digital-twin/actions/workflows/tests.yml)

Turning piping and instrumentation diagrams into a tagged asset model for Ignition and AVEVA PI with AI tools,
**and measuring whether the result can be trusted.**

The first step of most digital twin projects is someone redrawing P&IDs and typing tag lists by hand. This
project tests how much of that AI vision models can do, how to check their work honestly, and how a plant could use
the approach without compromising its safety and data governance.

**Start here:**

| You are… | Read this |
|---|---|
| **Evaluating the work** (2 minutes) | [Results](#results-so-far) and [Try it in Ignition](#try-it-in-ignition) below, then [what it cost](docs/COSTS.md). For the judgment calls, journal entries [7](docs/JOURNAL.md#7-fix-the-scoring-rules-first-then-test-the-scorer-until-it-cant-be-fooled), [13](docs/JOURNAL.md#13-round-3-results-a-review-queue-that-points-people-at-the-problems-and-a-fix-that-only-half-generalized) and [14](docs/JOURNAL.md#14-the-ignition-build-the-twin-in-a-real-gateway-judged-by-the-gateway) |
| **Exploring the historical Docker lab** | [Docker lab demo](docker/README.md): requires Docker setup, an isolated lab and license acceptance; restores the historical backup |
| **An Ignition user testing an isolated lab** | [Ignition lab workflow](docs/IGNITION_QUICKSTART.md), with setup/license requirements and current-versus-historical validation limits |
| **Planning something like this at a plant** | [Replicate at your plant: self-guided or assisted](docs/REPLICATE_AT_YOUR_PLANT.md) |
| **Checking or reproducing the numbers** | [Tutorial](#tutorial-reproduce-it), [How "done well" is defined](docs/EVALUATION.md), [Pre-registered goal and results](docs/GOAL.md) |

Have one local PNG and an existing extraction JSON? The [bounded site-intake recipe](docs/REPLICATE_AT_YOUR_PLANT.md#bounded-local-intake-one-png--an-existing-extraction) builds a source-preserving, unverified review bundle with the standard library. It does not run extraction or establish plant readiness.

For a new single-PNG job, the [frozen extraction handoff](docs/SITE_EXTRACTION_WORKFLOW.md) separates offline preparation/collection from explicitly authorized model execution. [Reviewed PI mapping](docs/PI_MAPPING.md), [offline Ignition acceptance preflight](docs/REPLICATE_AT_YOUR_PLANT.md#offline-exact-candidate-ignition-preflight), and a [future human review-effort protocol](docs/REVIEW_EFFORT_PROTOCOL.md) cover the next handoffs. These are local tools and draft evidence contracts; native imports and the human study remain unrun.

**Contents:** [Results](#results-so-far) · [Try it in Ignition](#try-it-in-ignition) ·
[What this demonstrates](#what-this-project-demonstrates) · [How it was built](#how-it-was-built) ·
[Tutorial](#tutorial-reproduce-it) · [Repository map](#repository-map) · [Read next](#read-next) · [Status](#status) ·
[Data and credits](#data-and-credits) · [Environment variables](#environment-variables)

![30-second demo: OPEN100 drawing extraction and synthetic point mapping, followed by the separate hand-built Tennessee Eastman model in recorded fault replay](docs/demo.gif)

*30 seconds, two separate demonstrations: OPEN100 drawing extraction with synthetic I/O mapping, then the hand-built Tennessee Eastman process model/HMI driven by recorded fault-replay data. The TE fault screen was not extracted from the OPEN100 drawing. Made from the repo's own historical screens (`scripts/make_demo_gif.py`); this GIF does not validate later local display revisions.*

**Keep the evidence tracks separate:**
- **OPEN100:** drawing extraction, scored outputs and a labeled synthetic point-mapping demo. These are not site-verified live plant connections.
- **Tennessee Eastman (TE):** a hand-built seed process model and generated HMI, driven by recorded simulation replay. Historical gateway checks apply to their recorded build; the later local spatial-display revision has offline checks only, with runtime limits in [its verification summary](out/process_mimic/VERIFICATION.txt).
- **PID2Graph Synthetic:** a bounded two-development-sheet adaptation through the existing scorer and exporters, with unresolved ontology and line-semantics review gates. This is neither a held-out generalization result nor operational plant validation. See [the adaptation guide](docs/ADAPT_LABELED_DATASET.md).

---

## Results so far

The goal ([docs/GOAL.md](docs/GOAL.md)) is a digital twin starter kit that needs as little human correction as
possible. The primary score, **review load**, counts the corrections a reviewer must make per 100 items on the
drawing (lower is better).

The rules, splits and decision rule were committed before any method was tested. Each method was scored once on two
sealed sets nobody tuned on:
- **A:** 6 real OPEN100 drawings;
- **B:** 20 drawings in a different drafting style.

| Model | Baseline (whole sheet), A / B | **Tiling + line tracing**, A / B |
|---|---|---|
| GPT (gpt-6.1-sol, via Codex) | 48.8 / 67.0 | **17.8 / 20.7** |
| Claude (claude-opus-5-5) | 61.1 / 76.6 | **32.4 / 16.5** |
| Gemini (gemini-3.1-pro) | 75.9 / 92.7 | **40.2 / 38.3** |

![Before and after: a crop of a public OPEN100 drawing, and the same crop with every extracted symbol boxed and coloured by review risk tier](docs/screenshots/before-after-sheet0.png)

**What that means:**
- **AI reads symbols and tags; code traces the lines.** Connections are two-thirds of the work and the models'
  weakest skill. A deterministic line tracer took the best result from about 49 corrections per 100 items to about
  18.
- **It held on a different drafting style,** so it isn't tuned to one drawing set.
- **Not everything improved.** Choosing the right parent equipment for each instrument got slightly worse (90.9% →
  87.0%), because the tracer links everything on a shared pipe network. Round 3 fixed it for this drafting style
  (next bullet but one).
- **Reviewers get a risk-ranked queue.** Every item has a green / amber / red tier and a plain-language reason. For
  example, the twin built from 12 sheets has 377 red, 676 amber and 1,833 green items out of 2,886. On drawings
  nobody tuned on, the riskiest 20% held 2–4× as many errors as the models' own confidence would point to (23 of 24
  comparisons), and green items were 94–100% right. The one failure was the best model with the best method on
  same-style drawings, where it was no better than the model's own confidence. That's reported in
  [GOAL.md](docs/GOAL.md).
- **Instrument-to-equipment assignment is fixed for this drafting style** (92.2%, up from 87.0%) by following the
  drawn line. On a different style it slipped (67.6% vs 70.8%), so the two rules' disagreements go to review.
- **An open-weight model you can run offline** (Gemma 4 31B, round 1) trailed far behind: about 0.53 detection F1
  where it finished, and it stalled on dense sheets.
- **It runs in a real Ignition gateway, judged by the gateway.** The Tennessee Eastman plant is live from open
  simulation data, with alarms. The 12-sheet extracted twin is honestly "not connected", and every drawing has a
  Perspective screen.
  - A verifier runs nine checks against the running gateway. Among them: the gateway holds exactly what was sent, no
    tag without a source ever reads Good, outside writes are refused, and the reactor pressure alarm fires on a
    replayed fault.
  - Before its passes counted, it had to catch five faults planted on purpose. It caught all five, and all nine
    checks pass. See [docs/IGNITION_BUILD.md](docs/IGNITION_BUILD.md).
- **Operations corrections flow back into the twin.** The reviewer fills in a spreadsheet: confirm, correct or
  reject, show on screen, alarm priority. A script checks every row, applies the decisions with a change record, and
  regenerates Ignition, PI AF and the screens. Removing or inventing an alarm is routed to a change review instead
  of being applied. See [docs/REVIEW_LOOP.md](docs/REVIEW_LOOP.md).
- **Placeholders become live points from an I/O list.** Matching never guesses. It also lists the points a plant
  has that the drawing doesn't show, the first sign of an out-of-date drawing. In the demo (a labeled synthetic I/O
  list), 24 mapped instruments read live in Ignition while the rest stay honestly "not connected".
- **Old scans: where it breaks** (round 4, pre-registered). Photocopy quality made no consistent difference. On
  old-scan quality, review load roughly tripled (GPT 17.8 → 51.5); on a bad scan it quadrupled (72.6). Most of the
  loss is the code line tracer, not the models: their symbol reading fell gently, and tracing the same symbols on
  the clean image recovers much of the connection score. An archive of scans needs image cleanup before tracing.
  Details in [GOAL.md](docs/GOAL.md), round 4.

![Ignition Perspective screen during the fault-6 replay: reactor pressure above its 2,895 kPa limit shows red; the agitator speed, which has no data source, shows a not-connected overlay](docs/screenshots/ignition-te-fault6-alarm.png)

## Try it in Ignition

The historical demo ran in Ignition 8.3. For a current-source isolated-lab trial, regenerate the project
with `python scripts/ignition/build_gateway.py --write-only` after satisfying data/dependency prerequisites.
The committed project ZIP is historical and is not matched to the current provider/build metadata; see the
[current-source handoff](docs/CURRENT_GATEWAY_HANDOFF.md). A candidate kit needs:
- a tag import ([`twin_provider.json`](out/ignition/gateway/twin_provider.json));
- a locally regenerated Perspective project (`PIDTwin.zip`; the [committed ZIP](out/ignition/gateway/PIDTwin.zip) is historical);
- the small replay server that feeds the live values ([`te_sim_server.py`](scripts/ignition/te_sim_server.py)).

The historical gateway assembled through the web UI plus one tag import passed all nine verifier checks;
current-source native runtime acceptance remains unrun. Steps:
**[docs/IGNITION_QUICKSTART.md](docs/IGNITION_QUICKSTART.md)**. To do the same thing by script with every check,
see [docs/IGNITION_BUILD.md](docs/IGNITION_BUILD.md).

The screens are generated from the twin in the ISA-101 style: grey when the plant is normal, amber when a value
leaves its learned normal band, red only for a real alarm. In the fault replay, the first value turns amber 294
plant-minutes before the pressure alarm. What they infer, and how far to trust it:
[docs/OPERATOR_SCREENS.md](docs/OPERATOR_SCREENS.md).

| Plant overview, normal | Fault 6: early warning, then the alarm | An extracted drawing, live |
|---|---|---|
| ![Plant overview in normal running: grey tiles with values, indicators and trends](docs/screenshots/hmi-overview-normal.png) | ![Plant overview at the pressure alarm: values outside their normal band amber, reactor pressure red](docs/screenshots/hmi-overview-fault-alarm.png) | ![The original OPEN100 sheet 0, greyed, with live values beside mapped instruments](docs/screenshots/hmi-drawing-sheet0.png) |

**Three ways to run it:**
- **Historical Docker lab:** [the Docker demo](docker/README.md) requires Docker setup, license acceptance and an isolated lab. Its launcher restores the historical backup; historical CI checks do not validate current provider/project exports.
- **Isolated Ignition lab:** [the lab workflow](docs/IGNITION_QUICKSTART.md), with explicit setup and current-artifact acceptance requirements.
- **Scripted, with every check:** [docs/IGNITION_BUILD.md](docs/IGNITION_BUILD.md).

There's no public live instance. It runs on your own computer, and Ignition's free trial is enough. With the
gateway's settings in place, one command fetches the data, builds and verifies the twin, and keeps it live:
`python scripts/demo.py --build --verify`.

**What it cost:** $16.57 of metered model spend (a $25 cap), plus two flat-rate subscriptions. Machine time is
cents per sheet; reviewer time is the real cost, and the docs show how to size it. See [docs/COSTS.md](docs/COSTS.md).

Full results, every method tried (including the losses), and caveats: [docs/GOAL.md](docs/GOAL.md) →
Results, and [docs/EVALUATION.md](docs/EVALUATION.md).

## What this project demonstrates

- **Domain to data.** P&ID conventions (ISA-5.1 tags, off-page connectors, equipment classes) turned into one
  structured model. That model generates SVG graphics, Ignition UDTs and tags, a PI AF hierarchy, and a
  plain-language review sheet for operations.
- **Evaluation you can defend.**
  - Scoring rules were written before any model ran.
  - The scorer was tested with deliberately wrong answers. Its first version gave them 15–32% credit and had to be
    rebuilt.
  - Every result is repeated to measure noise.
  - Failures count as zero.
  - Where I broke one of my own rules, the docs say so.
- **Judgment about tools.** Three cloud models compared fairly, plus an open-weight model as a stand-in for a fully
  offline deployment, with time and cost recorded per drawing.
- **Plant reality.** Every step carries an "At your plant" note covering:
  - messy drawing sets;
  - getting savings from an imperfect draft;
  - Management of Change;
  - read-only, monitoring-only use;
  - data-egress terms;
  - OT network zoning;
  - what an air-gapped model setup would cost.

## How it was built

Claude (through Claude Code) and OpenAI/Codex contributed code and documentation under Steve Vitale’s
guidance. The initial public baseline was built with Claude; later source and documentation work also used
OpenAI/Codex. The models under test (Claude, GPT, Gemini, and open-weight Gemma) were compared on drawing
extraction. [docs/MODELS.md](docs/MODELS.md) records the historical baseline’s model roles, not current authorship. No operations review of the Tennessee Eastman model has been done yet: the tooling for it is built and tested, but a review only counts if it comes from someone who knows the process and is looking at the drawings. The
[build journal](docs/JOURNAL.md) records each decision, what was rejected, and what went wrong, including the
agents' own mistakes and mine.

---

## Tutorial: reproduce it

Requires Python 3.10+. Steps 1–2 use the standard library only; the rest need `pip install -r requirements.txt`.
Model runs need the relevant CLI or API key and send drawings to the selected service. File generation and offline tests can run locally; dependency installation, uncached source/data fetches and gateway operations are separate networked steps. Use a disposable learning checkout: generation, source verification with `--write`, review and mapping can overwrite files. Start with [the replication guide](docs/REPLICATE_AT_YOUR_PLANT.md) for the bounded public-data path.

**1. Check the seed model against its source.** This verifies the Tennessee Eastman model against the open TE
simulation code (36 of 37 items confirmed, 1 corrected):
```
python scripts/verify_te_source.py --write
```

**2. Generate the platform outputs.** SVGs, the Ignition tag import, the PI AF sheet and the operations review sheet
go to `out/`:
```
python scripts/generate.py
```

**3. The scoring drawings are already here.** The 12 OPEN100 drawings with their answer keys, and their degraded
"old scan" copies from round 4, are committed under `data/external/pid2graph/` (CC BY-SA 4.0, see
[NOTICE.md](NOTICE.md)). Only the 20 holdout-B drawings (130 MB) are left out; fetch them, or re-fetch the rest from
the source, by reading only the needed parts of the 9.3 GB archive:
```
python scripts/fetch_pid2graph.py --get "Complete/Dataset PID/"
```

**4. Prove the scorer before trusting it.** Start with stdlib and committed-fixture checks; this explicitly narrower mode is not a full-suite pass:
```
python scripts/run_tests.py --source-only
```
The full cached-data suite (also the no-argument/CI default) requires installed pinned dependencies, hash-verified TE replay files and a locally regenerated current-source project ZIP. The committed ZIP is historical. In a disposable checkout, the write-only build below regenerates local exports without contacting a gateway; it overwrites local generated files. The suite fails preflight rather than silently skipping tests or downloading data:
```
python scripts/ignition/build_gateway.py --write-only
python scripts/run_tests.py --full --check-prerequisites
python scripts/run_tests.py --full
```
See [replication prerequisites and limits](docs/REPLICATE_AT_YOUR_PLANT.md#c-check-the-pipeline-then-optionally-rerun-public-extraction) before any separate networked setup. A prerequisite check alone is not a test pass.

**5. Run a model and score it.** Use `claude`, `codex`, or `gemini`; for Gemini, set `GEMINI_API_KEY`:
```
python scripts/run_extraction.py --tool gemini --drawings 0,1,2 --label my-run --prompt extraction/prompt_v2.md
python scripts/scorecard.py --label my-run
```

**6. Trace the connections with code and build the digital twin starter kit:**
```
python scripts/trace_connections.py --src-label my-run --tool gemini --drawings 0,1,2 --label my-run-traced
python scripts/build_twin.py --label runs/my-run-traced/gemini/ --sheets 0,1,2 --score
```
The twin package lands in `out/twin/`: asset hierarchy, review queue, Ignition tags, PI AF rows, and per-sheet SVGs.
See [docs/TWIN_OUTPUTS.md](docs/TWIN_OUTPUTS.md).

**7. Build it into Ignition and verify it** (needs an Ignition 8.3 gateway; the free trial works). The build
script takes a backup, then creates the replay connection, tag provider, tags and screens. The verifier plants five
faults, confirms each is caught, restores the gateway, then runs all nine checks:
```
python scripts/fetch_te_data.py                      # the open TE simulation runs the replay uses
python scripts/ignition/build_gateway.py --fresh
python scripts/ignition/te_sim_server.py --run normal   # live values for the screens (leave running)
python scripts/ignition/verify_gateway.py --controls   # stop the replay first: the verifier drives it itself
```
Setup (API key, HTTPS, OPC UA certificate) is in [docs/IGNITION_BUILD.md](docs/IGNITION_BUILD.md). To just
load the committed kit by hand, use [docs/IGNITION_QUICKSTART.md](docs/IGNITION_QUICKSTART.md).

**8. Close the loop: operations review and real data points.** Apply a filled-in review sheet, map instruments
from an I/O list, then regenerate and rebuild (details in [docs/REVIEW_LOOP.md](docs/REVIEW_LOOP.md)):
```
python scripts/apply_review.py data/te_process_model.json reviewed.csv --reviewer "Name, role"
python scripts/map_points.py out/twin/r2-tiles-trace/codex/plant_model.json data/io_lists/open100_sheet0_demo.csv --sheets 0
python scripts/generate.py && python scripts/generate.py out/twin/r2-tiles-trace/codex/plant_model.json
python scripts/demo.py --build --verify       # one command: data, build, nine checks, then live
```

**9. Read why each step is done this way** in [docs/JOURNAL.md](docs/JOURNAL.md). Each entry ends with how to apply
it at a real site.

## Repository map

| Path | What's there |
|---|---|
| [`docs/`](docs/) | Everything to read; see [Read next](#read-next). Screenshots are in [`docs/screenshots/`](docs/screenshots/) |
| [`data/te_process_model.json`](data/te_process_model.json) | The Tennessee Eastman seed model, checked against the simulator source |
| [`data/sheet_registers/`](data/sheet_registers/) | A drawing index read from the OPEN100 title blocks (an example of what a plant supplies) |
| [`data/io_lists/`](data/io_lists/README.md) | A synthetic I/O list for the point-mapping demo, shaped like a real export |
| [`data/external/pid2graph/`](data/external/pid2graph/) | The 12 OPEN100 drawings with answer keys, and their degraded-scan copies (CC BY-SA 4.0) |
| [`data/drawings/`](data/drawings/) | The drawings greyed for use as screen backgrounds |
| [`extraction/`](extraction/) | The prompts every model got (`prompt_v2.md` is current), hashed into every run record |
| [`scripts/`](scripts/) **, by stage** | |
| · source and data | `verify_te_source.py`, `fetch_te_data.py`, `fetch_pid2graph.py` |
| · extraction | `run_extraction.py` (Claude / Codex / Gemini adapters, cost meter, spend cap), `tiling.py`, `remerge_tiles.py`; `site_extraction_workflow.py` (frozen single-PNG handoff) |
| · line tracing (code, no AI) | `trace_connections.py` |
| · scoring | `score_pid2graph.py` (the frozen scorer), `scorecard.py`, `per_drawing.py`, `score_twin.py`, `score_triage.py` |
| · the twin | `build_twin.py` (sheets to hierarchy, review queue, platform files), `confidence.py` + `confidence_model.json` (risk tiers), `generate.py` (SVG, Ignition, PI AF, review sheet) |
| · operator screens | `normal_bands.py` (learned normal bands, checked on unseen normal data and a fault run) |
| · review loop | `apply_review.py` (operations decisions back into the model), `map_points.py` (OPC), `map_pi_points.py` (separately reviewed PI references), `review_effort.py` (future study records) |
| · scans (round 4) | `degrade_scans.py` (geometry-preserving old-scan images), `run_scan_robustness.ps1`, `score_scan_robustness.ps1` |
| · demo | `demo.py` (one command to a live twin), `make_before_after.py`, `make_demo_gif.py` |
| · Ignition | [`scripts/ignition/`](scripts/ignition/): `build_gateway.py`, `build_hmi.py` (operator screens), `build_views.py`, `prepare_drawings.py`, `import_tags.py`, `te_sim_server.py`, `demo_points_server.py`, `verify_gateway.py`, `acceptance_preflight.py` (offline exact-candidate checks), `ua_client.py`, `gw.py`, `make_local_ca.py` |
| · tests and costs | `run_tests.py` (explicit source-only/full cached-data modes; CI defaults to full), `test_*.py`, `cost_report.py`; `*.ps1` reproduce the holdout tables on Windows |
| [`out/`](out/) | Committed results: `scorecard_<label>.md`, [`costs.md`](out/costs.md), the TE outputs (`svg/`, `ignition/`, `pi/`, `ops_review_sheet.csv`) |
| [`out/twin/r2-tiles-trace/codex/`](out/twin/r2-tiles-trace/codex/) | The 12-sheet extracted twin: `plant_model.json`, `review_queue.csv` (risk-tiered), Ignition tags, PI AF sheet, per-sheet SVGs |
| [`out/ignition/gateway/`](out/ignition/gateway/) | The Ignition kit (tag import, Perspective project) and dated verification receipts in `receipts/` |
| [`out/mapping/`](out/mapping/), `out/review/` | Point-mapping reports, and the change records each applied review writes |
| [`docker/`](docker/README.md), `docker-compose.yml`, `*-demo.bat` | Historical Docker lab: Ignition restored from a prepared backup, plus the two data servers and launchers; requires setup/license acceptance |
| [`runs/`](runs/README.md) | Raw model run records (not committed) and the Gemini spend ledger (committed) |
| [`NOTICE.md`](NOTICE.md), [`LICENSE`](LICENSE), [`CITATION.cff`](CITATION.cff) | Licensing (MIT code; CC BY-SA for files derived from PID2Graph) and how to cite |

## Read next

| Document | For |
|---|---|
| [docs/GOAL.md](docs/GOAL.md) | The round-2 goal, review-load score, sealed splits, decision rule, and results |
| [docs/EVALUATION.md](docs/EVALUATION.md) | How "done well" is defined, the anti-Goodhart rules, round-1 results |
| [docs/FROM_DEMO_TO_A_REAL_SITE.md](docs/FROM_DEMO_TO_A_REAL_SITE.md) | What it takes to go from a clean annotated set to a 40-year drawing archive |
| [docs/TWIN_OUTPUTS.md](docs/TWIN_OUTPUTS.md) | The digital twin starter kit: each output file and how to load it into Ignition and PI AF |
| [docs/COSTS.md](docs/COSTS.md) | What it cost, per drawing and in total, and how to size it for 1,000 sheets |
| [docs/REVIEW_LOOP.md](docs/REVIEW_LOOP.md) | Operations review back into the twin, and mapping instruments to live data points |
| [docs/SITE_EXTRACTION_WORKFLOW.md](docs/SITE_EXTRACTION_WORKFLOW.md) | Frozen single-PNG prepare/execute/collect workflow, provenance and retry boundaries |
| [docs/PI_MAPPING.md](docs/PI_MAPPING.md) | Reviewed PI-only mapping, staging reconciliation and native-import limits |
| [docs/REVIEW_EFFORT_PROTOCOL.md](docs/REVIEW_EFFORT_PROTOCOL.md) | Future measured engineering labor and independent residual-error study; no human results yet |
| [docs/IGNITION_QUICKSTART.md](docs/IGNITION_QUICKSTART.md) | Historical isolated-lab workflow and current-artifact validation limits; setup and licenses required |
| [docs/IGNITION_BUILD.md](docs/IGNITION_BUILD.md) | The twin in a running Ignition gateway: the nine checks, planted faults, results, security |
| [docs/OPERATOR_SCREENS.md](docs/OPERATOR_SCREENS.md) | The generated operator screens: normal bands, early warning, what's data and what's judgement |
| [docs/MODELS.md](docs/MODELS.md) | Which work used several models, which used Claude alone, and how each was checked |
| [docs/JOURNAL.md](docs/JOURNAL.md) | Each step: what, how, why, lesson, and "at your plant" |
| [docs/AT_YOUR_PLANT.md](docs/AT_YOUR_PLANT.md) | Messy data, savings from imperfect drafts, safety and security, offline models and cost |
| [docs/PLAN.md](docs/PLAN.md) | Phases, decisions, risks, sources, and a dated status of what changed |

## Status

| Phase | State |
|---|---|
| Seed model, generator, platform outputs | Done |
| Answer keys (TE verified; OPEN100 fetched) | Done |
| Extraction comparison (3 cloud models × 3 runs, plus an open-weight model) | Done |
| Round 2: tiling, computer-vision line tracing, extraction-to-twin converter, scored on sealed holdouts | Done |
| Round 3: risk-tiered review queue; instrument parents chosen along the traced line | Done (one partial result, reported) |
| Ignition build: live TE values and alarms, extracted twin as placeholders, Perspective screens, 9-check verifier with 5 planted faults | Done; also verified when loaded by hand ([quickstart](docs/IGNITION_QUICKSTART.md)) |
| Review loop and point mapping: decisions and data addresses flow into Ignition, PI AF and the screens | Done; verified in a running gateway |
| Operator screens (ISA-101 style): overview, unit screens, trends, learned normal bands, drawings as backgrounds | First pass done and verified; key values and spans are Claude's choice, not yet reviewed by operations |
| Round 4: robustness on old-scan images, pre-registered | Done (measured; where it breaks is reported) |
| One-click Docker demo (`start-demo.bat`), checked from scratch in CI | Done |
| Demo animation and before/after image | Done ([docs/demo.gif](docs/demo.gif)); a narrated video isn't made |
| Twin converter: extracted sheets to hierarchy, Ignition tags, PI Builder sheet, SVG overlays, review queue (`scripts/build_twin.py`) | Done |
| PI AF: asset structure as a PI Builder sheet; not imported into a PI System, by decision (below) | Scoped |
| Operations review of the Tennessee Eastman model | Tooling done and tested; the review itself is not done. It needs someone who knows the process, working from the drawings |

**PI is scoped to the asset structure, by decision.** The twin produces a PI AF hierarchy as a PI Builder sheet
(elements, templates, attributes with point references), but it has not been imported into a PI System. Why:
- **No free PI environment exists.** The 45-day developer trial is a full Windows Server install behind an account.
- **The asset structure is PI's transferable value.** PI Vision dropped plain custom-SVG import, so the graphics
  story belongs to Ignition here.
- **A historical Ignition build was tested end to end:** import, replayed values, alarms and verification. Current regenerated artifacts have offline checks only; native runtime/browser acceptance is not run.

To validate at a site, publish the sheet to a development AF database with PI Builder, check the hierarchy in PI
System Explorer, then verify real PI point bindings. [The PI-only mapper](docs/PI_MAPPING.md) can stage explicit, reviewer-supplied archive/point/type/UOM references on a copied extracted model; unmapped attributes retain `%Server%`/placeholder references. `map_points.py` maps OPC addresses for Ignition and does not fill PI bindings. Staging CSV columns must be reconciled against the installed PI Builder version before a separately authorized native import.

## Data and credits

- **PID2Graph** (Zenodo 14803338, CC BY-SA 4.0) and the **OPEN100** design by the Energy Impact Center. The 12
  OPEN100 drawings and answer keys are included, with derived copies (degraded scans, greyed screen backgrounds),
  under the same licence. The holdout-B drawings are fetched by script.
- **Tennessee Eastman process**, Downs & Vogel (1993); open simulation code by the Braatz group (University of
  Illinois). Downloaded by script.
- Code in this repository: MIT. Files derived from PID2Graph are CC BY-SA 4.0; see [NOTICE.md](NOTICE.md).

## Environment variables

| Variable | Used by | What |
|---|---|---|
| `GEMINI_API_KEY` or `GEMINI_KEY_ENV_FILE` | `run_extraction.py --tool gemini` | The key, or a path to a private `.env` file holding it |
| `PID2GRAPH_SET` | extraction, scoring, twin scripts | `Dataset PID` selects the holdout-B set; the default is OPEN100 |
| `IGNITION_ENV_FILE` | `scripts/ignition/*` | A private file of the variables below, as `KEY=VALUE` lines |
| `IGNITION_URL`, `IGNITION_API_TOKEN`, `IGNITION_CA_FILE` | `scripts/ignition/gw.py` | Gateway HTTPS address, API key, and the CA that signed the gateway's certificate |
| `IGNITION_BACKUP_DIR`, `IGNITION_SECRETS_DIR` | `build_gateway.py`, `verify_gateway.py`, `ua_client.py` | Private folders for gateway backups, the OPC UA client certificate and the verifier's OPC UA login |
| `IGNITION_UA_URL` | `ua_client.py` | The gateway's OPC UA server (default `opc.tcp://localhost:62541`) |

Keep every one of these outside the repo.
