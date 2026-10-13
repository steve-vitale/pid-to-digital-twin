# Which models did what

This page records the initial public benchmark and operator-screen snapshot (through 2026-10-08).
Subsequent source and documentation revisions also include OpenAI/Codex engineering under Steve Vitale’s
guidance. Current authorship is shared across those contributions; the historical comparisons below are
not claims that every later change received multi-model or native-runtime validation.

AI shows up in this project in two different jobs, and they're held to different standards:
1. **As the thing being tested:** reading P&IDs. Here several models were compared on the same drawings, scored
   against third-party answer keys, and the choice between them followed a rule written down in advance.
2. **As the builder:** writing the code, the screens and these documents. For the initial snapshot, Claude through Claude
   Code did the work; later revisions include OpenAI/Codex contributions. It was checked by tests, by the gateway verifier and by the author, not by a second model.

The extraction is where multi-model testing mattered most: it's the step whose output a plant would act on, and
models disagree there most. The rest of this page says, part by part, which kind of check each output got.

## Part by part

| Part | Models | How it was checked |
|---|---|---|
| **Reading the drawings** (symbols, tags, connections) | **Claude** (claude-opus-5-5, Claude Code CLI), **GPT** (gpt-6.1-sol, Codex CLI), **Gemini** (gemini-3.1-pro-preview, API); three runs each (two with the identical prompt, one with the revised prompt), plus **Gemma** (31B open weights) as an offline-capable baseline | Scored against PID2Graph answer keys; repeat runs to measure noise; sealed holdouts. [EVALUATION.md](EVALUATION.md), [GOAL.md](GOAL.md) |
| **Rounds 2–3 methods** (tiling, line tracing, parent choice) | Claude, GPT, Gemini, each scored on both holdouts | Pre-registered rule picked the method; losses reported |
| **Round 4** (old-scan robustness) | Claude and GPT. Gemini left out to keep metered spend down | Pre-registered; results in GOAL.md round 4 |
| **Which model's output became the published twin** | GPT's, with tiling + tracing (method M3) | Chosen by the rule written before the holdouts were scored, not by preference |
| **Review risk tiers** (green / amber / red) | Uses all three models' outputs as evidence: a symbol only one model saw is riskier | Calibrated on development drawings, tested on holdouts; where it failed is reported. [TWIN_OUTPUTS.md](TWIN_OUTPUTS.md) |
| **Line tracing, twin conversion, scoring** | None: deterministic code | Scorer has positive and negative controls (`test_scorer_controls.py`) |
| **Generated TE P&ID sheets** (drawing generator, layout, answer keys, style-fidelity check) | **None at run time:** deterministic code drawing from the verified model. The generator, the layout (where each item sits) and the checks were written by Claude (Claude Code) | Refuses a layout that drops, duplicates or invents a model item; the code line tracer, which sees only pixels, recovers every key link on all 3 sheets; 32 of 36 style measurements inside the OPEN100 range. Not reviewed by a drafter or by operations |
| **TE round trip** (extraction of the generated sheets, clean and degraded) | **Claude and GPT**, the declared method M3 unchanged (2×2 tiles, prompt v2, line tracer); clean sheets 5 runs each, each degraded level 3 runs each (84 sheet runs; 27 more on a superseded sheet 102 were set aside). **Gemini left out** by the project owner's direction | Scored against keys emitted from the same model: a round trip, not real-plant accuracy. [EVALUATION.md §6](EVALUATION.md#6-one-plant-end-to-end-tennessee-eastman) |
| **TE reviewer diff and live check** | None: deterministic code (`te_model_diff.py`, `te_live_check.py`), written by Claude | Unit tests with planted errors; the diff of a perfect reader shows what the converter itself gets wrong |
| **Tennessee Eastman seed model** | Transcribed by Claude from the published process | Checked line by line against the open simulator code by a script (`verify_te_source.py`): 36 confirmed, 1 corrected |
| **Tennessee Eastman topology check** (units, streams, flow directions, tag ownership; journal entry 39) | **Claude only** (Claude Code) wrote `verify_te_topology.py`, the correction rules and the unit purpose sentences | Deterministic: the script reads the simulator's balances and flow lines, so every result traces to a code line. Controls plant wrong models and edit the simulator text to show the conclusions follow the code. The rule for split evidence (code location plus a majority of documented names) is Claude's judgement. Not reviewed by a second model or a process expert |
| **Normal operating bands** on the operator screens | None: statistics on the published normal run | Fitted on half the normal run, tested on the other half and on a fault run. [OPERATOR_SCREENS.md](OPERATOR_SCREENS.md) |
| **Alarm setpoints** | None: published sources only | Verifier V8 proves the alarm fires in the gateway |
| **Operator screen choices** (which values represent each unit, display spans, layout) | **Claude only** | Not compared with another model and not reviewed by operations. Labelled as a first pass on every screen |
| **Initial-snapshot code** (extraction harness, tracer, converter, Ignition build, verifier, screens, Docker demo) | Claude, through Claude Code, built the initial public snapshot. OpenAI/Codex later contributed source and documentation engineering under Steve Vitale’s guidance | Tests in CI, the 9-check gateway verifier with 5 planted faults, the Docker demo checked from scratch on GitHub's machines, and the author reading results |
| **Native acceptance pass** (2026-10-12/13: transform parse fix, "not connected"/UNKNOWN text instead of `null`, indicator band visibility, Windows test portability, browser/live-check harness) | **Claude only** (Claude Code). The two display choices (wording and muted style of no-data labels; drawing an alarm limit only within 10 band half-widths) are Claude's judgement | A disposable Ignition 8.3.10 gateway (V1–V8, 277-target browser contract, quality transitions), regression tests shown failing on the old code, both suites on Windows and Linux. Not reviewed by a second model or by operations. Journal entry 38 |
| **Data-lineage spine** (2026-10-13: stage manifest, orchestrator, provenance rollup, seed-export provenance passthrough, mimic layout export, 3D scene data with inferred LOTO candidates, the mimic placement fix) | **Claude only** (Claude Code). Which outputs count as proof of concept and how a reviewer's role is read from the reviewer string are Claude's first pass, from the author's direction | `scripts/test_pipeline.py` (manifest consistency, committed lock fresh, a correction propagating to five outputs on a temp copy, deterministic rebuilds; the propagation check was shown failing with the old mimic placement), source-only suite on Windows. Not reviewed by a second model or by operations. Journal entry 41 |

| **Fault-detection evaluation** (all 21 TE faults, held-out false alarms, PCA T² baseline; 2026-10-13) | None as an input: statistics on the published data. **Claude** (Claude Code) chose the detection rule (3 consecutive flagged samples), the expected-hard faults named before scoring, the PCA settings and wrote the code | The rule and the expected misses were written before any fault file was scored; the bands were not retuned; a test regenerates the committed results exactly; synthetic controls test the rule, the F quantile and the PCA. Not reviewed by a second model or a process expert. Journal entry 40 |
| **Alarm and narrow-screen pass** (data-source diagnostic alarms, active-alarm count, one look for "not connected" and UNKNOWN, hidden pointers without Good data, the 390 px `/m` overview; 2026-10-13) | **Claude only** (Claude Code). Judgement calls: the diagnostic priority (Medium), its dark slate colour, the two no-data styles and the `/m` layout. The ISA-18.2 / ISA-101 rationale is stated as intent, not quoted from the standards | A disposable Ignition 8.3.10 gateway on the exact commit (V1–V8, 284-target browser contract, both data sources stopped and restarted, header sampled against the alarm table), offline contract tests. Not reviewed by a second model or by operations. Journal entry 40 |
| **Documents and journal** | Initially drafted by Claude; subsequent revisions include OpenAI/Codex, under Steve Vitale’s guidance | Every number traces to a file in the repo; the author reviewed them. Corrections are left visible (journal) |

## Where a second model would add the most next

In order of value for the effort:
1. **The operator screen choices.** Ask GPT and Gemini, independently, which 2–4 values represent each unit, and
   compare. Agreement is weak evidence; disagreement is a question for an operator. Cheap: one prompt per unit.
2. **The verifier.** It is the thing that says everything else works; its initial implementation used one coding model. A second model
   reviewing it for checks that can pass while broken would find the most important class of bug.
3. **Claims in the documents.** A second model reading the docs against the repo files, looking for numbers or
   statements the files don't support. Three such overclaims were found by hand and corrected (journal 21): an
   operations review described as done, a shutdown alarm described as never firing, and authorship described inaccurately for that historical snapshot.

None of these replaces an operations review. Models agreeing with each other is not the same as being right about a
plant.
