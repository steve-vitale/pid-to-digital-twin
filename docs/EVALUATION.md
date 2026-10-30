# How we know the job is done well

A score is only useful if it moves when the work gets better and stays put when it doesn't. This document
describes the evaluation system for this project, the rules that stop us from "teaching to the test", and how a
plant can adapt both to its own situation without loosening its governance.

---

## 1. Start from the outcome, not the metric

**The outcome we actually want:** a reviewed asset model (equipment, instruments, tags, connections) that a plant can
load into Ignition or PI. It should cost operations and engineering *less time* than building it by hand, and carry
*no more errors* than the manual version.

No single number captures that. Every metric below is a **proxy**, and each one is listed with what it *can't* see:

| Measure | What it tells us | What it can't see |
|---|---|---|
| **Rough detection** (box overlap IoU ≥ 0.1) | Did it find the thing, roughly where it is? | Whether the box is precise enough for graphics; whether the tag text is right |
| **Strict detection** (IoU ≥ 0.5) | Is the box precise enough to draw from? | Whether the class matters to operations |
| **Classification** (class must also match) | Did it call a valve a valve? | Whether the answer key's classes match *your* needs |
| **Per-class scores** | Where it's strong and where it's weak | Rare classes (16 pumps in 12 drawings) swing a lot |
| **Connectivity** (asset-to-asset links) | Does it understand the process topology? | Line sizes, flow direction, spec breaks |
| **Tag text** (generated TE sheets and DEXPI sheets only) | Did it read the tag exactly? Scored on the generated TE sheets (§6, a round trip on our own drawings) and on five clean DEXPI sheets from one publisher (round 5, §4a) | Not scorable on the OPEN100 and Dataset-P&ID keys, which have no text; tag reading on real plant scans is still unmeasured |
| **Answer-key topology** (Tennessee Eastman only) | Do the key's units, stream endpoints, flow directions and tag ownership match the simulator source? 51 confirmed, 4 corrected, 1 unresolvable (`out/te_topology_check.md`) | Tap positions, sizes and pipe routes, which the simulator does not model; anything where the source itself is split |
| **Operations review corrections** | What a real reviewer still had to fix | Only as good as the reviewer's time and attention |
| **Time and cost per sheet** | Whether it saves anything at all | Quality, so always read alongside the measures above |

The final judge is the review step: what a person who runs the unit had to correct. The benchmark is a filter that
decides what is worth putting in front of that person. It is not the goal.

## 2. The anti-Goodhart rules

> *Goodhart's law: when a measure becomes a target, it stops being a good measure.* With AI tools the risk is
> sharper, because you can keep tweaking prompts until a number goes up for reasons unrelated to the real work.

These are the rules this project follows. Each one also applies at a plant.

1. **Fix the rules before you see results.** The scoring rules are written down and dated in
   `scripts/score_pid2graph.py`, and committed before any model ran. Changing them later is allowed, but it's
   visible in the history, with the reason.
2. **Test the grader before you grade.** Five controls run on every drawing: a perfect answer, an empty answer,
   every class wrong, every box moved, and half the symbols dropped (`scripts/test_scorer_controls.py`). The scorer's
   first version gave a deliberately wrong answer 15–32%, and the tightened second version still gave 3–20%. See
   journal entry 7. Rerun the controls after every scorer change.
3. **Never let one number be the headline.** Report precision *and* recall, strict *and* rough, per class, and
   connectivity separately. A tool can raise one by sacrificing another, for example by reporting fewer symbols to
   raise precision.
4. **Measure the noise before claiming a difference.** In round 1 every tool was run at least twice with the identical
   prompt and images; rounds 2 and 4 were single runs (most tuning attempts were: see
   [TRIED.md](TRIED.md)). In round 1, Claude and Codex moved about ±0.03 F1 between runs; first-try Gemini moved ±0.13. Round 5
   ran the declared method five times per tool on holdout A: review load moved with a standard deviation of 1.4
   (GPT) and 1.9 (Claude) points, more than the "about 1 point" round 2 assumed. A gap smaller than the run-to-run
   noise is a tie, not a ranking, and a gap bigger than the noise on six drawings can still be a tie across drawings
   (section 4a). Here "tie" means no clear ranking under that rule; it does not establish statistical equivalence.
5. **Count failures as zeros.** A crashed or unparseable run scores zero on that drawing; it is never skipped. A tool
   shouldn't look better by failing quietly.
6. **First try is the headline; improvements are labeled.** The first-try scorecard is kept and published as-is.
   Anything after it, such as prompt v2, is shown separately and named as a change.
7. **Separate what you tune on from what you report on.** This is the rule we've already bent, so here it is
   plainly:
   - Prompt v2 (named box fields) was written after seeing first-try results on all 12 drawings. So all 12 are now
     "seen", and the v2 scores are optimistic in principle.
   - Why we think the bias is small: the change fixes the output *format* (axis order). It carries no information
     about any drawing. It was applied identically to every tool, and it barely moved the two tools that didn't
     have the format problem.
   - Still, a principle you only follow when convenient isn't a principle. From here on, any prompt or model
     change is tuned on a declared development set and then checked once on a **sealed held-out set** of drawings
     no one has looked at. That's either fresh public drawings or the dataset's unseen synthetic sheets, reported
     separately.
8. **Don't change the grader and the thing being graded in the same step.** Each run records the prompt hash,
   image hash, model, and date. Scorer changes are separate commits with controls rerun. The parsed prediction
   from each run, with those hashes, is committed under `predictions/`, so `python scripts/rescore.py --check` can
   re-score the committed tables with the current scorer and show that a scorer change moved nothing it shouldn't
   (five earlier diagnostic tables still lack predictions; the recovered round-5 records now re-score too;
   `predictions/README.md` gives the coverage).
9. **Watch for "teaching to the key".** The answer key has a catch-all class called `general`. Every model scores
   poorly on it (F1 0.11–0.45), because "general" means whatever the annotators decided.
   - We could raise that number by tuning prompts to guess the annotators' habits.
   - That would improve the score and do nothing for a digital twin.
   - So we report it, and we don't tune toward it. Decide which classes matter for *your* use (section 3) and weight
     those.
10. **Price the gain.** Every result carries time and cost per sheet. A quality gain that doubles review time, or
    costs ten times more, may not be a gain.
11. **Close the loop with people.** The operations review corrections (Phase 4, deferred by the project owner)
    are the outcome measure. A ready-to-run timing kit for one sheet is in `out/review_kit/sheet-8/`; no review
    has been timed yet. If the
    benchmark improves but reviewers still fix the same things, the benchmark is measuring the wrong thing.

## 3. Be flexible for your situation, without loosening governance

Different uses need different measures. Pick yours before you evaluate anything:

| If the goal is… | Weight these most | Accept weakness in |
|---|---|---|
| Instrument index / tag list | Instrument recall, tag text accuracy | Box precision, line connectivity |
| HMI / twin graphics | Strict detection, classification | Rare classes, if a person places them |
| Asset hierarchy (PI AF / Ignition UDTs) | Equipment and instrument recall, correct parent assignment | Line details |
| Process topology / analytics | Connectivity | Nothing much. This is today's weakest area, so keep a person on it |

What stays fixed whichever row you pick: rules written before results, controls on the scorer, variance
measured, failures counted, a held-out check, and a human review that has the final say. Those are governance, and
they shouldn't bend to the use case.

## 4. Round-1 results (12 real OPEN100 drawings)

Every "connection" score in §4 to §6 is the **network layer**: two items count as connected when they are on the
same drawn line network: `score_pid2graph.py` collapses the answer key's graph (symbols joined through `connector` and
`crossing` nodes) into every pair on one network. None of them says which item is piped directly to which. [§7](#7-which-layer-each-evaluation-measures) lists each evaluation with the layer it measures.

Rough "found + right class" F1, plus connectivity F1 (precision and recall are in `out/scorecard_*.md`):

| Tool / model | First try | Repeat (same prompt) | Prompt v2 (named fields) | Connections (v2) |
|---|---|---|---|---|
| Codex · gpt-6.1-sol | 0.87 | 0.87 | 0.85 | 0.53 |
| Claude · claude-opus-5-5 | 0.85 | 0.85 | 0.85 | 0.42 |
| Gemini · gemini-3.1-pro-preview (earlier runs; not run after round 3) | 0.44 | 0.57 | 0.74 | 0.24 |
| Gemma 4 31B (open weights, via hosted API) | — | — | 0.25 first try (5 of 12 timed out → scored 0) | 0.02 |

What this supports:
- **Codex and Claude** are tied on finding and naming symbols, within noise.
- **Codex** leads on connectivity across all three runs.
- **Gemini's** first-try gap was mostly an output-format problem: on 5 of 12 drawings it wrote box coordinates in a
  different axis order. Naming the fields fixed it.
- **Every model** finds instruments and off-page connectors almost perfectly, and misses more than half the
  connections.

**Gemma 4 31B (open weights, the offline stand-in):**
- **First try counts the failures:** 5 of 12 calls hit our 30-minute client timeout on Google's shared hosted
  endpoint, so they score 0. That's honest for a plant relying on a slow shared service. It says little about a
  dedicated local GPU, which has no shared queue.
- **Labeled diagnostic on the 7 that completed:** "found" F1 averages about 0.54. Precision is high (0.93: when it
  reports a symbol, it's right) and recall is low (it misses most symbols).
- **Retry with a 90-minute timeout (labeled as a retry):** drawings 5 and 6 completed in about 4 minutes each (F1
  0.38 and 0.55). Drawings 0, 9 and 10 timed out **again**, the same three both times, two of them among the densest
  sheets. That is consistent with the model or the hosted service stalling on certain images, not just a slow
  queue. We can't tell which from outside, and on a self-hosted model you could.
- **Across both attempts:** 9 of 12 drawings completed, averaging about 0.53 "found" F1, against about 0.90 for the
  frontier models.
- **Bottom line so far:** on this task a ~30B open model is well behind the frontier cloud models. For a plant that
  can't send drawings out, that's the trade-off to weigh: fine-tuning on your own sheets (AT_YOUR_PLANT.md §6) is
  how that gap usually narrows, and it should be measured with this same suite before and after.

What it doesn't support:
- **Ranking claims beyond these drawings.** Twelve drawings come from one public design; a different drafting
  style may reorder the tools.
- **Any statement about tag-reading accuracy on these drawings.** Their keys have no text. Tag reading was measured
  elsewhere: on five clean DEXPI sheets (round 5, section 4a) and on the generated Tennessee Eastman sheets (§6, a
  round trip on our own drawings and an upper bound for clean house-style drawings).

## 4a. Later rounds at a glance

Each round was pre-registered in [GOAL.md](GOAL.md) before its model runs. The headline numbers, so none of them has
to be dug out:

**Round 2, the declared method (M3: 2×2 tiles + code line tracing), review load per 100 items, lower is better.**
Holdout A = 6 real OPEN100 sheets; holdout B = 20 synthetic sheets in another style. Each scored once.

| Tool | Model alone, A / B | M3, A / B |
|---|---|---|
| GPT (Codex) | 48.8 / 67.0 | 17.8 / 20.7 |
| Claude | 61.1 / 76.6 | 32.4 / 16.5 |
| Gemini (earlier runs) | 75.9 / 92.7 | 40.2 / 38.3 |

**Round 3.** Instrument-to-parent assignment along the traced line: 92.2% on holdout A (beats both earlier twins),
67.6% on holdout B (worse than round 2's 70.8%, a style-overfitting warning). Risk tiers: the riskiest 20% held more
of the errors than the model's own confidence in 23 of 24 holdout comparisons; the one failure is GPT with M3 on
holdout A.

**Round 4, old scans** (holdout A, M3, each level run once per tool; Gemini not run):

| Image quality | GPT review load | Claude review load | Symbol F1, rough (GPT / Claude) | Connection F1 (GPT / Claude) |
|---|---|---|---|---|
| Clean (round 2) | 17.8 | 32.4 | 0.94 / 0.90 | 0.89 / 0.78 |
| L1 photocopy | 20.6 | 29.7 | 0.92 / 0.90 | 0.87 / 0.79 |
| L2 old scan | 51.5 | 57.0 | 0.87 / 0.86 | 0.51 / 0.45 |
| L3 bad scan | 72.6 | 70.6 | 0.77 / 0.81 | 0.22 / 0.19 |
| L3 symbols, tracer on the clean image | 60.7 | 47.9 | 0.77 / 0.81 | 0.53 / 0.63 |

- Photocopy quality made no consistent difference; old and bad scans cost 3–4× the review load.
- The models' symbol reading degrades gently. The code line tracer is what breaks: given the same L3 symbols on the
  clean image, connections recover from about 0.2 to 0.53–0.63.
- The levels are synthetic degradations of digital drawings (`scripts/degrade_scans.py`: faded ink, blur, lower
  resolution, JPEG artifacts, yellowed background, speckle, patches where lines fade out). Skew, rotation,
  handwriting, stamps and torn edges are not tested, and real archive scans were not used.

**Round 5, replicates and tag text** (five fresh runs per tool, Claude and GPT only; Gemini not run, its earlier
results kept as earlier runs). Mean, then 95% intervals: runs (same drawings, run again) / bootstrap (other
drawings like these, and run again).

| Set and measure | GPT | Claude | GPT minus Claude |
|---|---|---|---|
| Holdout A, review load | 20.1 (18.3–21.8 / 14.2–28.0) | 29.8 (27.5–32.1 / 12.8–47.3) | −9.8: beyond run noise on these 6 sheets; a **tie** across drawings (bootstrap −26.5 to +4.5) |
| Holdout A, connection F1 | 0.872 (0.864–0.879 / 0.801–0.916) | 0.795 (0.779–0.811 / 0.638–0.920) | same pattern: no clear ranking across drawings |
| DEXPI (3 XML sheets), review load | 95.4 (53.2–137.6 / 42.1–138.6) | 61.8 (60.5–63.1 / 26.3–127.9) | tie |
| DEXPI tags, end-to-end, strict | 29 of 33 (0.88) | 28 of 33 (0.85) | tie; identical in all 5 runs |
| DEXPI tag lists (2 sheets, 145 identifiers) | 100% | 99.4% | tie |

- **The method does worse on the DEXPI drawings** than on holdout A, outside both tools' holdout-A intervals.
  Much of it is key scope: nozzles, sample points and actuator bubbles are drawn but are not DEXPI items, so a
  model that reports them is charged with false symbols, and the tracer then links them. GPT reported the nozzles
  in 3 of 5 runs and not in the other 2, which swung its C01 review load between about 33 and 145.
- **Tags on clean vector drawings are read almost perfectly** (all 20 on the reference sheet, by both tools). The
  misses are vertical labels, multi-line labels and a valve number drawn on a separate actuator bubble. This says
  nothing yet about scans or real archives.
- Full tables, per-sheet numbers and diagnostics: [GOAL.md, round 5 results](GOAL.md#round-5-results-scored-after-the-pre-registration-above).

## 4b. Fault detection with the normal bands (Tennessee Eastman, all 21 faults)

The operator screens flag a value that leaves its normal band (mean ± 6 sd, learned from the normal run;
[OPERATOR_SCREENS.md](OPERATOR_SCREENS.md)). The fault demo shows one easy fault, so this asks how the same bands do
on every published fault. Script: `scripts/fault_detection_eval.py`; data: the full Braatz set
(`python scripts/fetch_te_data.py --all`, 44 files, byte-identical to the Braatz group's own archive); results:
[`out/fault_detection/fault_detection.md`](../out/fault_detection/fault_detection.md).

**Rule, fixed before any fault file was scored:** the plant is flagged when any of the 52 channels is outside its
band; a fault counts as detected at the first post-onset sample that starts 3 consecutive flagged samples (9
minutes). Each test run switches its fault on at sample 160 of 960 (3 minutes per sample). Nothing was tuned on fault
data. False alarms are measured on normal running the bands never fitted on: the separate normal training run
(d00.dat, 500 samples) and the fault-free first 8 hours of each of the 21 fault runs (3,360 samples, 21 separate
simulation runs).

| Method | Detected | Median delay | Mean detection rate | False alarms on normal data |
|---|---|---|---|---|
| Shipped bands (what the screens use) | **17/21** | 48 min | 57.7% | **0 flagged samples of 3,860; 0 alarm events in 193 h** |
| Same K, refit on d00.dat (held-out d00_te) | 17/21 | 48 min | 57.6% | 0 of 4,320; 0 events in 216 h |
| PCA T² baseline (12 components) | 19/21 | 84 min | 54.5% | 1.04% of samples; 5 events in 216 h |

Detection rate is the share of post-onset samples flagged, the per-sample measure most TE papers report.

**What the bands miss, said plainly:**
- **Faults 3, 9 and 15** (D feed temperature step and random variation, condenser cooling-water valve sticking):
  missed, 0% of post-onset samples flagged. These were named as expected misses before scoring: the TE literature
  widely reports them as hard or impossible to see with data-driven monitoring of these variables.
- **Fault 19** (unknown in the original paper): missed. One sample flagged, 25.6 hours after onset. PCA T² misses it
  too.
- **Slow and random faults are late.** Fault 21 (stream 4 valve stuck) is flagged after 26.5 hours, faults 10, 18 and
  20 after 4 to 4.5 hours. K = 6 buys the zero false alarms with lateness.
- Per fault, the first tags to leave their band are in the results file. They are what an operator would see turn
  amber first, and they are mostly the obvious ones (FT-101 for the A feed loss, TT-109 and TV-210 for the reactor
  cooling-water faults).

**The PCA T² baseline is reimplemented, not cited.** Standardised on d00.dat, components kept by parallel analysis
(12), 99% threshold from the F distribution, the same 3-sample rule. It "detects" 19, but its detections of faults
3, 4 and 15 come at 18 to 34 hours with 2–8% of samples flagged, close to its own 1% normal flag rate: about 0.9
chance alarm events are expected in a 40-hour window, so those three are probably chance. Counting them out, PCA T²
detects 16, the bands 17. On fault 4 the difference is real: the bands catch it in 6 minutes through TT-109, PCA T²
does not. PCA T² is faster on fault 10 and catches more of faults 10 and 16 per sample. Published PCA results on
this data set vary with the number of components, the threshold and the detection rule, so no literature numbers
are quoted here; I could not verify a table's exact values from a primary source in this pass.

**What it doesn't show:**
- One operating mode, simulated data, one set of 21 runs. A plant has modes, sensor faults, maintenance and noise
  the simulator doesn't have.
- The detection rule is the band flag, which on the screens is amber, a display aid. No alarm was added.
- Zero false alarms in 193 hours is a measurement, not a guarantee: the 95% upper bound is about 0.37 alarm events
  per day. A site would measure its own rate over weeks before trusting the colour.
- Delays are from fault onset to the first 9-minute run of flags. An operator's time to notice is extra.

---

## 5. Where the evaluation files live

| File | Role |
|---|---|
| `scripts/score_pid2graph.py` | Scoring rules (dated docstring) |
| `scripts/test_scorer_controls.py` | Positive and negative controls; must pass before any score is trusted |
| `scripts/run_extraction.py` | Runs a tool; records model, prompt hash, image hash, time, cost, token usage |
| `scripts/cost_report.py` | Time and cost totals from every run record → `out/costs.*` ([COSTS.md](COSTS.md)) |
| `scripts/run_tests.py` | Every test in one command (CI runs it) |
| `scripts/fault_detection_eval.py`, `scripts/test_fault_detection_eval.py` | Section 4b: band and PCA T² fault detection on all 21 TE faults; the test regenerates the committed results |
| `scripts/degrade_scans.py`, `run_scan_robustness.ps1`, `score_scan_robustness.ps1` | Round 4: old-scan images (geometry kept, keys unchanged), the runs, and the scoring |
| `scripts/verify_te_topology.py`, `scripts/test_te_topology.py` | Checks the TE answer key's topology against the simulator code; controls plant wrong models and edit the simulator text to prove the check reads the code |
| `scripts/draw_pid_from_model.py`, `scripts/style_fidelity.py`, `scripts/score_te_roundtrip.py`, `scripts/te_model_diff.py`, `scripts/te_live_check.py`, `scripts/test_te_pid_roundtrip.py` | §6: the generated TE sheets and keys, the style check, the round-trip scorer (tag text, replicates), the reviewer diff, the replay live check, and their tests (layout refusals, key regeneration, tracer-key agreement, planted misreads) |
| `scripts/test_apply_review.py` | Controls for the review loop: bad sheets refused, alarm requests routed to change review, round trip stable |
| `scripts/run_holdouts.ps1`, `score_holdout_b.ps1`, `score_parent_holdouts.ps1`, `score_triage_holdouts.ps1` | Windows PowerShell helpers that reproduce the GOAL.md holdout tables, each label scored once |
| `scripts/scorecard.py`, `scripts/per_drawing.py` | Aggregate and per-drawing views |
| `extraction/prompt.md`, `extraction/prompt_v2.md` | Prompt versions; never edited in place once used |
| `scripts/tiling.py`, `extraction/tile_preface.md` | Round-2 tiled extraction: tile grid, merge rules (stated in the docstring), optional whole-sheet links; run with `run_extraction.py --tiles 2x2` |
| `scripts/test_tiling.py` | Controls for the tile merge: geometry, synthetic perfect-extractor round trip, and the dev-key oracle (`--oracle-dev`) that shows how many links seams lose by construction |
| `scripts/test_along_line.py` | Controls for the along-line parent rule on a synthetic sheet: following the line beats position, signal chains, the off-line fallback, and the tracer's links unchanged when the geometry is requested |
| `scripts/remerge_tiles.py` | Re-applies the merge (or adds whole-sheet links) to stored tile replies without new model calls |
| `out/scorecard_<label>.md` | Published results per run label |
| `out/te_pid/` | §6 results: `style_fidelity.md`, `roundtrip_scores.md` (+ `.json` with every run's model, prompt hash, date, time and cost), `diff_*.md`, `live_*.md`, extracted TE twins |
| `scripts/adapt_dexpi.py`, `data/dataset_adapters/dexpi_examples.json` | Round 5: DEXPI sheets fetched by SHA-256, rendered, and converted to answer keys (conversion rules in the docstring) |
| `scripts/score_tags.py` | Round 5: tag-text scoring rules (dated docstring), against DEXPI labels or published tag lists |
| `scripts/replicate_stats.py`, `scripts/run_round5.ps1` | Round 5: the replicate runs, and means with run and bootstrap intervals → `out/replicates_r5_*.md` |
| `scripts/test_dexpi_adapter.py`, `test_score_tags.py`, `test_replicate_stats.py` | Controls: the converted key scores itself perfectly; tag scoring and interval arithmetic on synthetic cases |
| `scripts/review_kit.py`, `out/review_kit/sheet-8/` | The ready-to-run timed-review kit (no measurement yet) |

## 6. One plant, end to end (Tennessee Eastman)

**Why:** the extraction (OPEN100) and the live twin (TE) were on two different plants, so "drawing → extraction →
twin → live values" was never shown on one plant. TE has a verified model but no public drawing we may use, so the
drawing is generated from the model in the house style learned from OPEN100 (`scripts/draw_pid_from_model.py`,
3 sheets). The same path is open to a plant with process knowledge and no usable drawings.

**What is and isn't being measured.** The keys come from the same model as the drawings, so this is a **round
trip**: how faithfully the frozen method reads clean drawings in a known style. It is an upper bound, not real-plant
accuracy, and not comparable with §4 or the OPEN100 holdouts: the sheets are sparser (20–28 scored symbols against
40–134), cleaner, and the key is ours. Two checks keep the key honest. The generator refuses a layout that drops,
duplicates or invents a model item. And the code line tracer, which sees only pixels, recovers every key link on all
three sheets from the key's symbol boxes, so the key's links describe what is drawn.

**Style check** (`out/te_pid/style_fidelity.md`): 32 of 36 measurements inside the OPEN100 per-sheet range on revision A (30 of 36 on revision B, which added 19 controllers but no manual valves; 35 of 36 on revision C, which adds a control valve station around each inline control valve but one). The four
outside are symbol counts on all three sheets and ink coverage on one, because the model has no drains, vents or
manual valves to draw.

**Revision C (2026-10-28).** The same method and protocol on the sheets that now draw controllers, signal lines and
control valve stations, scored against their own keys
([roundtrip_scores_revC.md](../out/te_pid/roundtrip_scores_revC.md)). GPT: review load 1.26, 1.30, 1.20 and 14.9 per
100 for clean, L1, L2 and L3; tags read 100%, 100%, 61% and 9%. Claude: 1.38, 4.1, 10.0 and 15.7; tags read 100%,
100%, 89% and 50%. Claude's L1 and L2 loads come from a tracer interaction, not reading: its equipment boxes sit just
inside the drawn vessel wall, the tracer follows the wall, and whole networks merge; growing only those boxes 4 px
removes every extra link (journal entry 54). The table below is revision A.

**Method, unchanged:** M3 (2×2 tiles, 0.15 overlap, `extraction/prompt_v2.md`, then `trace_connections.py` with
defaults), GPT (gpt-6.1-sol, Codex CLI) and Claude (claude-opus-5-5, Claude Code CLI). Gemini was left out by the
project owner's direction. Clean sheets: 5 runs per model. Round-4 degraded copies L1–L3 (`degrade_scans.py --src`,
same levels and seeding): 3 runs per model per level. 84 sheet runs, no failed tile. Scores: the frozen scorer for
symbols and connections, plus tag text, matched by position (rough IoU ≥ 0.1) and compared after dropping case and
separators (`scripts/score_te_roundtrip.py`).

| Image | Review load /100: GPT · Claude | Symbols found F1 | Connections F1 | Tags read exactly (of 43) | Off-page refs read |
|---|---|---|---|---|---|
| Clean | 2.1 (2.1–2.1) · 2.2 (2.1–2.6) | 0.99 · 0.99 | 0.99 · 0.99 | 100% · 100% | 100% · 100% |
| L1 photocopy | 2.1 · 8.0 (2.6–11.5) | 0.99 · 0.97 | 0.99 · 0.96 | 100% · 98% | 93% · 100% |
| L2 old scan | 2.1 · 13.4 (11.5–14.7) | 0.99 · 0.99 | 0.99 · 0.91 | 56% (54–58%) · 95% | 0% · 86% |
| L3 bad scan | 16.9 (16.2–17.8) · 17.3 (15.7–18.3) | 0.99 · 0.98 | 0.85 · 0.85 | 14% · 49% (44–51%) | 0% · 0% |

Means over runs, min–max in brackets where runs differed; 95% t-intervals are in `roundtrip_scores.json`.

**What it says:**
- **Clean house-style sheets read almost perfectly** by both models: every tag and every symbol was found. The
  residual 2 per 100 is mostly the agitator motor, which both models report as an extra symbol; the tracer then
  routes the agitator speed bubble through it.
- **Text fails before shapes.** At L2, GPT's symbols and connections were as good as on clean sheets while it read
  only 56% of the tags exactly: FI became PI, LI became LE, FV became PV, and off-page references were dropped. Claude
  held tags better (95%) but lost connections (0.91); whether its boxes or the tracer caused that was not isolated.
  In round 4 on OPEN100, connections collapsed at L2; GPT's held here until L3, on sparser and cleaner geometry.
- **The dangerous misread is a real tag.** Claude at L3 read the three feed valves FV 203, FV 201 and FV 202 as FV 201,
  FV 202 and FV 203 in one run, and TT 122 as TT 121 in another. Each is a real tag, so an I/O list would bind it to
  the wrong live point. A tag-only diff and the live check both pass these (all three valves "matched" and "moved",
  `out/te_pid/live_claude-L3-r1.md`); only comparing by position catches them. On a real plant that is what a
  walkdown or a loop check is for.
- **No winner is called.** The runs show the two models fail differently, not that one is better: GPT was steadier on
  shapes, Claude on text. Three runs per degraded level is enough to see that, not to rank.

**The reviewer diff** (`scripts/te_model_diff.py`, tag-only matching against the verified model). For the declared
chain (GPT, clean, run 1; chosen before scoring because GPT + M3 is the published method): 35 of 43 units and tagged
items came through exactly, all 7 unit-to-unit process connections were recovered, and 10 corrections remain. Nine of
them appear even when the key itself is fed in as a perfect extraction (`diff_key.md`), so they come from the
converter and the model's conventions, not from the reading:
- the feed header U-100 is drawn as an in-line mixer, and `build_twin.py` treats in-line symbols as line items, not
  units;
- so the six feed-line items (FT-101–103, FV-201–203) get the reactor as their owning unit instead of U-100;
- two extra unit links (C-101–K-101, U-100–V-101) come from lines that meet at the feed header and at the compressor
  bypass. On the drawing the two ends are on the same line network, through a tee; neither pair is piped directly to
  each other, and the model's stream list doesn't join them. The diff compares network pairs with streams, two
  different layers ([§7](#7-which-layer-each-evaluation-measures)).

The tenth is the motor symbol. On degraded sheets the corrections grow to 47 (GPT, L2) and 54 (Claude, L3), almost
all misread or unread tags (`diff_codex-L2-r1.md`, `diff_claude-L3-r1.md`).

**Exporters and live values.** Each extracted twin went through the same exporters as the OPEN100 twin (Ignition tags
and UDTs, PI AF sheet, SVG, review queue). `scripts/te_live_check.py` starts the TE replay server and matches the
twin's tags to its points: for the declared chain, 36 of 37 resolve and all 36 values moved between reads. SC-212 has
no recorded data, and the 16 per-component analyzer channels have no bubble of their own on the drawings. Not done:
importing the extracted twin's tag file into a gateway. The natively accepted gateway project is built from the
verified model, which is what the extracted twin becomes after the listed corrections plus the fields no P&ID prints
(simulator index, units of measure, descriptions), which come from the instrument list.

**Cost:** subscriptions only. Claude's CLI reported $12.56 API-equivalent for the 42 published Claude sheet runs, plus
$3.86 for 13 runs on a superseded version of sheet 102 (redrawn after the purge correction, journal entry 44). Codex
reports no cost. No Gemini call; the Gemini ledger is unchanged at $16.57.

## 7. Which layer each evaluation measures

A line on a P&ID carries two different facts, and this repository used one relationship for both until 2026-10-29.
`scripts/line_layers.py` now keeps them apart (definitions in its docstring and
[GRAPH_EXPORT.md](GRAPH_EXPORT.md#three-layers-for-the-lines)):

- **Network layer**: which items are on the same drawn line network (lines, bends, junctions or crossings join them
  with no item between). Its pairwise form, every pair of members, is how `score_pid2graph.py` reads a PID2Graph
  answer key (it walks the key's graph through its `connector`, `crossing` and `arrow` nodes and links every pair of
  symbols it reaches) and what the tracer emits as `connects`. The key itself is a graph, not a list of pairs. It
  answers "which items share this drawn line network?"; instrument and signal lines can be members too.
- **Pipe layer**: which item or junction is piped directly to which (consecutive along a run, through bends and past
  instrument taps, never through another item or a pipe tee). It supports checking drawn neighbours and what is
  between X and Y; it is a draft graph, not an isolation plan. 22 of 27 sampled sheet-0 network links were not pipe neighbours
  ([statement review](../examples/statement-review/README.md)). Drawn lines that are not pipe (instrument
  connections, actuator stems, nozzle stubs) are kept as their own edge types, and instrument taps as their own
  junction kind ([GRAPH_EXPORT.md](GRAPH_EXPORT.md#three-layers-for-the-lines)).

A high network score says nothing about pipe adjacency, and the other way round.

| Evaluation | Where | Truth | Layer | Current numbers | What it does not say |
|---|---|---|---|---|---|
| Round 1, model links (12 OPEN100 sheets) | §4, `out/scorecard_*.md` | PID2Graph keys, collapsed to all pairs | network | connection F1, prompt v2: Codex 0.53, Claude 0.42, Gemini 0.24, Gemma 0.02 | anything about adjacency; a model that gave only true pipe neighbours would be scored as missing most pairs |
| Oracle tracer, development set | `out/scorecard_r2-trace-oracle_dev.md` | same | network | F1 0.93 (P 0.96 / R 0.90) | which of those pairs are piped to each other |
| Round 2 review load (holdouts A and B) | §4a, [GOAL.md](GOAL.md) | same | network for the connection part | GPT 17.8 / 20.7, Claude 32.4 / 16.5 (model + tracer) | the review load of checking pipe adjacency, which is unmeasured |
| Round 4, old scans | §4a | same | network | connection F1 clean 0.89 / 0.78 down to 0.22 / 0.19 at L3 (GPT / Claude) | adjacency on scans |
| Round 5 replicates | §4a, `out/replicates_r5_*.md` | same; DEXPI keys from `adapt_dexpi.py` (all pairs, tees as pass-through connectors) | network | holdout A connection F1 0.872 (GPT) / 0.795 (Claude); DEXPI review load 95.4 / 61.8 | adjacency |
| Vendor kit controls and example | `examples/vendor-evaluation/` | the user's own PID2Graph-format keys | network | example: connection F1 0.960 | adjacency: a vendor delivering a pipe-level graph is scored against all pairs |
| Generalization matrix row 1, current opt-in scan cleanup | [GENERALIZATION.md](GENERALIZATION.md) | each set's key, with the key's symbols supplied | network | open100-dev 0.928, holdout 0.889, scans L1 0.894 / L2 0.818 / L3 0.753, synthetic 0.921, DEXPI 0.822, TE revisions A, C and D 1.000, TE C scan L3 0.988, Bayer 1.000 | adjacency (row 8), model symbol-reading accuracy, or a re-run of round 4; these are oracle-symbol tracer checks |
| Generalization matrix rows 3 and 7 | GENERALIZATION.md | key link counts; `dexpi_to_twin` against its own key | network | bundle links equal key links on every set; 0 corrections on C01-C03 | adjacency |
| TE round trip, revisions A and C | §6, `out/te_pid/roundtrip_scores*.json` | the drawer's key: one group per drawn line network | network | connection F1 clean 0.99 / 0.99, L3 0.85 / 0.85; revision C review load 1.26 to 14.9 (GPT) | adjacency (matrix row 8 measures it on revision D) |
| TE reviewer diff | §6, `scripts/te_model_diff.py` | the verified model's streams | network pairs compared with streams | 7 of 7 unit-to-unit streams found; 2 extra unit links | the 2 extras are network co-membership through a tee, not a reading error and not a missing stream |
| DEXPI reader against its key | `examples/from-dexpi-xml/` | adapt_dexpi key (all pairs) vs the model's streams | streams compared with network pairs | 7 of 7 compared C01 links in the key; the key's 2 extra links are two branches of one tee | the same layer mismatch, explained in that README |
| Instrument parent assignment (round 3) | §4a, `scripts/score_twin.py` | nearest non-instrument asset reachable through the key's graph | neither: nearest along the network | 92.2% holdout A, 67.6% holdout B | whether the parent is piped directly to the instrument |
| Flow direction blind spot check | [OPEN100_STRUCTURAL.md](OPEN100_STRUCTURAL.md) | two readers on crops | network pairs | 65 sampled, none disagreed; 19 unclear, mostly across a branch | a direction on a pair beyond a branch says flow can reach, not that a pipe joins the two |
| Statement review, sheet 0 (2026-10-29) | [statement review](../examples/statement-review/README.md) | the drawing, read by an independent agent | network wording read two ways | 2 of 60 wrong read as network (3.3%), 24 of 60 read as adjacency (40%) | measured the old wording |
| Layered statement review, sheet 0 (2026-10-29) | `sheet0/review-2026-10-29-layers/` | the drawing, read by an independent agent | each layer apart | network 0 of 15, pairwise 0 of 15, items 0 of 13 (2 unclear); **pipe 3 of 15 wrong (20%, Wilson 7-45%)**: an actuator stem and an instrument leader said to be pipes | measured the version before the pipe/instrument/actuator split (attempt A146); its fix is unreviewed: `sheet0/sample_layers_r2.*` (75 statements, 15 per layer, seed 1031) is ready |
| **Pipe layer, matrix row 8** | GENERALIZATION.md, `python scripts/line_layers.py score` | DEXPI 1.3 XML piping segments (tees are elements); the current drawer's routes, valves, taps and tees, split into pipe and instrument lines by the symbols' classes | **pipe** | DEXPI 1.3 F1 0.916 (P 1.000 / R 0.844; C01 0.962, C02 0.714, C03 0.941; 5 of 5 tees found, 5 junctions predicted); TE revision D 1.000; Bayer 1.000 (both self-generated) | DEXPI is scored on process piping only. Passes the 0.88 bar; development result, including scorer corrections, not a fresh held-out benchmark |
| Pipe layer, OPEN100 development sheets 0-5 (derived truth) | `python scripts/line_layers.py score --set open100` | **derived** from the PID2Graph key graph (`pid2graph_truth`); pipe vs instrument classes and junction rules supplied by this project | **pipe** | F1 0.931 (P 0.936 / R 0.926; sheets 0.995 / 0.896 / 0.960 / 0.980 / 0.981 / 0.758); 150 of 160 junctions found, 155 predicted. Passes the 0.88 bar | development sheets; the truth does not label pipe vs instrument lines or resolve all crossing ambiguities. A191 changed the derived truth as well as tracing. The truth's line networks still equal the key's all-pairs links on all six sheets |
| Pipe layer, OPEN100 holdout sheets 6-11 (derived truth) | same, matrix row 8 `open100-holdout`, A196 | derived the same way | **pipe** | F1 0.912 (P 0.901 / R 0.922; 356 of 386 true segments; sheets 0.839 / 0.903 / 0.862 / 0.988 / 0.937 / 0.901); 132 of 137 junctions found, 144 predicted. Passes the 0.88 bar | A177 reserved these sheets for the frozen A191-A195 rules, after a previous baseline. Only partly blind overall: A170's crossing error class came from sheet 6. A191 changed the truth from 388 to 386 segments, so 0.898 to 0.912 is not pure tracing gain |
| Pipe layer, DEXPI 1.2 vendor renders (mixed development and held out) | matrix rows 1 and 8 `dexpi-1.2-vendor-renders`, A173-A174, A191-A196 | each vendor export's XML, mapped onto its render; 22 of 81 renders map cleanly | **network and pipe** | pooled pipe F1 0.776 (P 0.720 / R 0.842), network F1 unchanged at 0.738. Pipe by exporter: SPPID 0.939 (14 development renders), Comos 0.264 (7 held-out renders), AVEVA 1.000 (one held-out render, one pipe segment); no AutoCAD render mapped. Pooled pipe fails 0.88 | the pool is not held out: A177 made SPPID development data and reserved Comos/AVEVA, seen previously as a baseline. A192's scorer-only junction fix moves SPPID 0.679 to 0.852, about two thirds of its total gain to 0.939. Ten mapped renders are small feature cases; 59 renders remain unscored |
| Agent-made keys: OMRE 1958 scan (bottom-right quadrant), Wikimedia Commons sheets, PRONTO Figure 1 | matrix rows 1 and 8, A172, A189 | first-pass keys a coding agent made (`data/agent_keys/`), not reviewed by a person | **network and pipe** | network F1 0.522 / 0.697 / 0.918; pipe F1 0.446 / 0.782 / 0.878 | weaker evidence than a hand key, not an independent source family. Opt-in scan cleanup lowers OMRE network F1 from 0.561 to 0.522; it stays opt-in. Only PRONTO passes the network bar; none passes the pipe bar |
| Pipe layer vs the review's notes, sheet 0 (diagnostic) | this section | the 27 network links the 2026-10-29 reviewer traced, with "direct" or "through N junctions" in the note | pipe | the pipe layer agrees on direct vs not for 24 of 27; of the other 3, 2 are drawn lines the reviewer said are not process lines (a tag leader, an actuator box) and 1 is a pair the reviewer saw one tee between | an error rate: one reviewer's notes, not a scored review |

**Adjacency in the PID2Graph keys (corrected 2026-10-29).** Earlier versions of this page said the OPEN100 and
PID2Graph keys define links as all pairs and hold no adjacency. That was wrong: the key is a graph of symbol nodes
joined through `connector` nodes (sheet 0: 225, every one with exactly 2 edges, a point along a line) and `crossing`
nodes (sheet 0: 71; the 38 with 3 edges sit within 3 px of the 38 tees and taps `line_layers.py` finds on that
sheet). It is this repository's scorer (`score_pid2graph.py`) that collapses those nodes into all-pairs network
co-membership, and every network-layer score above keeps that reading unchanged. Walked symbol to symbol, the key
gives direct adjacency; `line_layers.py` derives a pipe truth from it for the six development sheets (row above).
What the key does not say: which lines are pipe and which are instrument lines (split here by the symbols' classes),
and whether a 4-edge crossing is two lines passing or a 4-way joint. The [PID2Graph paper, §3.5.2 and supplement Algorithm S1](https://arxiv.org/html/2411.13929v1#S3.SS5.SSS2)
was checked against its text on 2026-10-29. It matches graph nodes by bounding boxes, then scores the presence and
class of individual edges using edge mAP, with crossings and bends represented as nodes. This repository's
network F1 collapses connector paths to symbol pairs, and its pipe F1 uses a separately derived pipe truth.
Neither reproduces the paper's metric, so their scores are not directly comparable.

**Not yet measured:** the pipe layer against truth with a model's own symbols (row 8 and the OPEN100 rows use the
key's symbols), on scans, and in a reviewed sample of the current version. The holdout and reserved Comos/AVEVA subsets above are the pipe-layer checks on drawings the latest rules were
not tuned on; both had been scored as baselines, and OPEN100 is only partly blind overall.
