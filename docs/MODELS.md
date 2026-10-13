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
| **Tennessee Eastman seed model** | Transcribed by Claude from the published process | Checked line by line against the open simulator code by a script (`verify_te_source.py`): 36 confirmed, 1 corrected |
| **Normal operating bands** on the operator screens | None: statistics on the published normal run | Fitted on half the normal run, tested on the other half and on a fault run. [OPERATOR_SCREENS.md](OPERATOR_SCREENS.md) |
| **Alarm setpoints** | None: published sources only | Verifier V8 proves the alarm fires in the gateway |
| **Operator screen choices** (which values represent each unit, display spans, layout) | **Claude only** | Not compared with another model and not reviewed by operations. Labelled as a first pass on every screen |
| **Initial-snapshot code** (extraction harness, tracer, converter, Ignition build, verifier, screens, Docker demo) | Claude, through Claude Code, built the initial public snapshot. OpenAI/Codex later contributed source and documentation engineering under Steve Vitale’s guidance | Tests in CI, the 9-check gateway verifier with 5 planted faults, the Docker demo checked from scratch on GitHub's machines, and the author reading results |
| **Native acceptance pass** (2026-10-12/13: transform parse fix, "not connected"/UNKNOWN text instead of `null`, indicator band visibility, Windows test portability, browser/live-check harness) | **Claude only** (Claude Code). The two display choices (wording and muted style of no-data labels; drawing an alarm limit only within 10 band half-widths) are Claude's judgement | A disposable Ignition 8.3.10 gateway (V1–V8, 277-target browser contract, quality transitions), regression tests shown failing on the old code, both suites on Windows and Linux. Not reviewed by a second model or by operations. Journal entry 38 |
| **OPEN100 structural deliverables** (2026-10-13: flow direction from drawing evidence, sheet stitching, mimic, 3D tour stills, LOTO isolation view) | Code and every design choice (arrowhead rule and its settings, flag rule, pump convention, what counts as a branch, mimic layout and icons, 3D placeholder shapes, isolation-point categories, using the lower 95% bound as confidence): **Claude only** (Claude Code). Equipment schedules transcribed from the drawings by **Claude** (claude CLI). Blind direction spot check read independently by **Claude** (claude CLI, fresh session) and **GPT** (gpt-6.1-sol, Codex CLI); neither disagreed with the code on any of 65 crops | Arrowhead detection scored against the keys' arrow positions, settings chosen on sheets 0-5 and reported on 6-11; the keys carry no direction, so direction is checked only by the blind spot check; arrowheads and flags agree on 70 of 70 shared links; all 95 flag readings looked at by Claude (the builder); `test_open100_structural.py`. The schedule transcription was not checked by a second model. No gateway import, no operations review. Journal entry 39 |
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
