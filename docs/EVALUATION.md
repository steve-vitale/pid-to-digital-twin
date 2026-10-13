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
| **Tag text** (DEXPI sheets, round 5) | Did it read the tag exactly? | Only 5 clean sheets from one publisher carry tag truth; the OPEN100 and Dataset-P&ID keys have no text |
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
4. **Measure the noise before claiming a difference.** Every tool was run at least twice with the identical prompt
   and images. In round 1, Claude and Codex moved about ±0.03 F1 between runs; first-try Gemini moved ±0.13. Round 5
   ran the declared method five times per tool on holdout A: review load moved with a standard deviation of 1.4
   (GPT) and 1.9 (Claude) points, more than the "about 1 point" round 2 assumed. A gap smaller than the run-to-run
   noise is a tie, not a ranking, and a gap bigger than the noise on six drawings can still be a tie across drawings
   (section 4a).
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
   image hash, model, and date. Scorer changes are separate commits with controls rerun.
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
- **Any statement about tag-reading accuracy on these drawings.** Their keys have no text. Round 5 measured tag
  reading on five clean DEXPI sheets instead (section 4a).

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
| Holdout A, connection F1 | 0.872 (0.864–0.879 / 0.801–0.916) | 0.795 (0.779–0.811 / 0.638–0.920) | same pattern: tie across drawings |
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

## 5. Where the evaluation files live

| File | Role |
|---|---|
| `scripts/score_pid2graph.py` | Scoring rules (dated docstring) |
| `scripts/test_scorer_controls.py` | Positive and negative controls; must pass before any score is trusted |
| `scripts/run_extraction.py` | Runs a tool; records model, prompt hash, image hash, time, cost, token usage |
| `scripts/cost_report.py` | Time and cost totals from every run record → `out/costs.*` ([COSTS.md](COSTS.md)) |
| `scripts/run_tests.py` | Every test in one command (CI runs it) |
| `scripts/degrade_scans.py`, `run_scan_robustness.ps1`, `score_scan_robustness.ps1` | Round 4: old-scan images (geometry kept, keys unchanged), the runs, and the scoring |
| `scripts/test_apply_review.py` | Controls for the review loop: bad sheets refused, alarm requests routed to change review, round trip stable |
| `scripts/run_holdouts.ps1`, `score_holdout_b.ps1`, `score_parent_holdouts.ps1`, `score_triage_holdouts.ps1` | Windows PowerShell helpers that reproduce the GOAL.md holdout tables, each label scored once |
| `scripts/scorecard.py`, `scripts/per_drawing.py` | Aggregate and per-drawing views |
| `extraction/prompt.md`, `extraction/prompt_v2.md` | Prompt versions; never edited in place once used |
| `scripts/tiling.py`, `extraction/tile_preface.md` | Round-2 tiled extraction: tile grid, merge rules (stated in the docstring), optional whole-sheet links; run with `run_extraction.py --tiles 2x2` |
| `scripts/test_tiling.py` | Controls for the tile merge: geometry, synthetic perfect-extractor round trip, and the dev-key oracle (`--oracle-dev`) that shows how many links seams lose by construction |
| `scripts/test_along_line.py` | Controls for the along-line parent rule on a synthetic sheet: following the line beats position, signal chains, the off-line fallback, and the tracer's links unchanged when the geometry is requested |
| `scripts/remerge_tiles.py` | Re-applies the merge (or adds whole-sheet links) to stored tile replies without new model calls |
| `out/scorecard_<label>.md` | Published results per run label |
| `scripts/adapt_dexpi.py`, `data/dataset_adapters/dexpi_examples.json` | Round 5: DEXPI sheets fetched by SHA-256, rendered, and converted to answer keys (conversion rules in the docstring) |
| `scripts/score_tags.py` | Round 5: tag-text scoring rules (dated docstring), against DEXPI labels or published tag lists |
| `scripts/replicate_stats.py`, `scripts/run_round5.ps1` | Round 5: the replicate runs, and means with run and bootstrap intervals → `out/replicates_r5_*.md` |
| `scripts/test_dexpi_adapter.py`, `test_score_tags.py`, `test_replicate_stats.py` | Controls: the converted key scores itself perfectly; tag scoring and interval arithmetic on synthetic cases |
| `scripts/review_kit.py`, `out/review_kit/sheet-8/` | The ready-to-run timed-review kit (no measurement yet) |
