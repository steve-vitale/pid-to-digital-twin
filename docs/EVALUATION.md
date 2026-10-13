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
| **Tag text** (Tennessee Eastman only) | Did it read the tag exactly? Scored on the generated TE sheets (§6), a round trip on our own drawings | Not scorable on the public dataset, whose key has no text; real-plant tag reading is still unmeasured |
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
4. **Measure the noise before claiming a difference.** Every tool was run at least twice with the identical prompt
   and images. Claude and Codex move about ±0.03 between runs; first-try Gemini moved ±0.13. A gap smaller than the
   run-to-run noise is a tie, not a ranking.
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
    are the outcome measure. If the
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

## 4. Results so far (12 real OPEN100 drawings)

Rough "found + right class" F1, plus connectivity F1 (precision and recall are in `out/scorecard_*.md`):

| Tool / model | First try | Repeat (same prompt) | Prompt v2 (named fields) | Connections (v2) |
|---|---|---|---|---|
| Codex · gpt-6.1-sol | 0.87 | 0.87 | 0.85 | 0.53 |
| Claude · claude-opus-5-5 | 0.85 | 0.85 | 0.85 | 0.42 |
| Gemini · gemini-3.1-pro-preview | 0.44 | 0.57 | 0.74 | 0.24 |
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
- **Any statement about tag-reading accuracy on real drawings.** The only tag-reading score is the Tennessee Eastman
  round trip (§6): sheets we generated, read back. It is an upper bound for clean house-style drawings.

## 5. Where the evaluation files live

| File | Role |
|---|---|
| `scripts/score_pid2graph.py` | Scoring rules (dated docstring) |
| `scripts/test_scorer_controls.py` | Positive and negative controls; must pass before any score is trusted |
| `scripts/run_extraction.py` | Runs a tool; records model, prompt hash, image hash, time, cost, token usage |
| `scripts/cost_report.py` | Time and cost totals from every run record → `out/costs.*` ([COSTS.md](COSTS.md)) |
| `scripts/run_tests.py` | Every test in one command (CI runs it) |
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

**Style check** (`out/te_pid/style_fidelity.md`): 32 of 36 measurements inside the OPEN100 per-sheet range. The four
outside are symbol counts on all three sheets and ink coverage on one, because the model has no drains, vents or
manual valves to draw.

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
  FV 202 and FV 203 in one run, and TI 122 as TI 121 in another. Each is a real tag, so an I/O list would bind it to
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
- so the six feed-line items (FI-101–103, FV-201–203) get the reactor as their owning unit instead of U-100;
- two extra unit links (C-101–K-101, U-100–V-101) come from lines that meet at the feed header and at the compressor
  bypass. On the drawing they share pipe; the model's stream list doesn't join them.

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
$3.86 for 13 runs on a superseded version of sheet 102 (redrawn after the purge correction, journal entry 40). Codex
reports no cost. No Gemini call; the Gemini ledger is unchanged at $16.57.
