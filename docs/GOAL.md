# Goal and scoring, round 2 (written before any round-2 experiment)

Committed 2026-10-08, before any of the round-2 methods below were built or run. The commit history is the
timestamp. Changing anything here later is allowed, but only in a new dated commit that says what changed and why.

## The goal, in one sentence

**From P&ID sheets, produce a digital twin starter kit (an asset hierarchy, tag-bound graphics, and import files for
Ignition and PI AF) that needs as little human correction as possible, and that tells the reviewer where to look.**

"Less hand-holding" is the measure. So the primary score counts the corrections a person would have to make.

## Primary score: review load

To turn the system's output into the answer key, a reviewer has to:

| Correction | Counted as |
|---|---|
| Delete a symbol that isn't there | 1 |
| Add a symbol the system missed | 1 |
| Relabel a symbol found in the right place with the wrong class | 1 |
| Delete a connection that isn't there | 1 |
| Add a connection the system missed | 1 |

**Review load = total corrections ÷ (symbols + connections in the answer key) × 100.** That's corrections per 100
things on the drawing. **Lower is better.** 0 means nothing to fix. Around 100 means about as much work as drawing
it from scratch.

- **Matching:** symbol matching uses rough location (IoU ≥ 0.1, as in round 1), because a reviewer fixes "is it
  there and what is it", not pixel boxes. Box precision for graphics is a secondary score.
- **Weighting (stated up front):** connections are about two-thirds of the items in each answer key, so review load
  is dominated by connectivity. That's intended: topology is what turns a symbol list into a twin.
- **Baseline (round-1 prompt v2), computed from existing runs before any round-2 work:**

  | Tool | Dev (0–5) | Holdout A (6–11) |
  |---|---|---|
  | Codex (gpt-6.1-sol) | 66.5 | 48.8 |
  | Claude (claude-opus-5-5) | 66.4 | 61.1 |
  | Gemini (gemini-3.1-pro) | 90.8 | 75.9 |

  Holdout B has no baseline yet. Each tool's baseline on it is run once, alongside the final methods.
  *(Pre-registered text, left as written. Holdout-B baselines are in Results below.)*
- **Classes:** the six asset classes (tank, pump, valve, instrumentation, inlet/outlet, general). Drawing plumbing
  (line bends, crossings, arrows, frames) is not scored.
- **Connections:** asset-to-asset links traced through line bends and crossings, same definition as round 1.

## Secondary scores (reported, not optimized)

- Detection F1, rough and strict, plus per-class F1 (round-1 definitions, unchanged).
- Connection precision and recall separately: is it inventing links, or missing them?
- **Confidence usefulness:** of the items the system marks "auto-accept", the share that are right. A system that's
  honest about what it doesn't know saves more review time than one that's slightly more accurate but uniformly
  confident.
- **Twin-level scores, once the converter exists:**
  - share of instruments attached to the right parent asset (parent taken from the answer key's graph);
  - share of off-page connectors correctly paired across sheets.
- **Cost and time per sheet.**

## The anti-overfitting protocol

Overtraining to the scorecard would be cheating, so these rules bind every round-2 method:

1. **Fixed splits.**
   - **Development set: OPEN100 drawings 0–5.** Methods may be built, inspected and tuned on these.
   - **Holdout A: OPEN100 drawings 6–11.** Never inspected per drawing from now on. Each finished method is scored
     on it once.
   - **Holdout B: 20 synthetic drawings from a different collection (Dataset-P&ID inside PID2Graph).** Chosen by
     fixed seed 20261008: ids 23, 44, 62, 78, 109, 111, 122, 143, 149, 158, 209, 224, 290, 345, 363, 366, 382, 400,
     494, 496. Never opened. They use a different drafting style, so they catch methods that only work on OPEN100.
     Their keys have no tank, pump or off-page classes, so they score instruments, valves, general symbols and
     connections only.
   - **Honesty note:** round-1 first-try outputs were seen for all 12 OPEN100 drawings. No round-1 change used
     drawing-specific information. From this commit on, holdout A is sealed.
2. **No drawing-specific logic.** No rule may mention a drawing, a tag, or a pattern seen only in a particular
   sheet. Every threshold is set on the development set only.
3. **Frozen grader.** The scorer and this definition are frozen for round 2. Its controls must pass before and
   after (`scripts/test_scorer_controls.py`).
4. **Report everything tried,** including methods that didn't help, with their development and holdout scores.
5. **What counts as a win:** a method beats the round-1 baseline only if its holdout review load is lower by more
   than the run-to-run noise measured for that tool. A win on development that doesn't hold on the holdouts is
   reported as overfitting, not as a win.
6. **Holdout B is the generalization check.** A method that improves holdout A but makes holdout B worse is
   probably learning OPEN100's style, and is reported as such.

## Round-2 methods (planned; results below)

| Method | Idea | Why it might help the goal |
|---|---|---|
| Baseline | Round-1 prompt v2, whole image | Reference point |
| Tiling | Overlapping image tiles, merged | Small symbols and tags get lost when a 3,000-pixel sheet is downscaled |
| Traced connections | Find symbols with AI, trace lines with computer vision | Connections were every model's weakest point (recall 0.17–0.44); lines are geometry, which code does deterministically |
| Ensemble | Combine two models; agreements auto-accept, disagreements go to review | Fewer misses, and confidence that's honest about where to look |

## What "done" looks like for round 2

1. The table above is filled in with development, holdout A and holdout B scores for each method, failures
   included.
2. The best method, on holdout scores only, feeds the converter, which outputs the digital twin starter kit for a
   sheet set: asset hierarchy, Ignition tags and views, PI AF import, and a review queue sorted by confidence.
3. A plain statement of what the numbers do and don't support.

## Addendum (before any holdout run): the declared methods and decision rule

Written after development work finished, and before a single round-2 method touched holdout A or B. All four methods
run for all three tools. No per-tool choice is made in advance, and nothing changes after the holdout runs start.

| Id | Method | Dev review load: claude / codex / gemini |
|---|---|---|
| M0 | Baseline: whole sheet, prompt v2 | 66.4 / 66.5 / 90.8 |
| M1 | Tiling: 2×2 tiles, 15% overlap, merge rules in `scripts/tiling.py` | 73.5 / 46.3 / 76.1 |
| M2 | Traced connections on M0's symbols (`scripts/trace_connections.py`, defaults, replace mode) | 29.8 / 34.4 / 87.6 |
| M3 | Traced connections on M1's symbols | 36.1 / 20.5 / 59.2 |

**Decision rule, fixed now:**
- Each tool's best method is the one with the lowest holdout A review load.
- A method beats M0 only if its holdout A review load is lower by more than that tool's measured run-to-run noise
  (repeat runs differed by about 1 point in round 2).
- Holdout B is reported for every method. A method that wins on A but loses to M0 on B is reported as style
  overfitting.
- Each method is scored on each holdout once. Failures count as zero.

**Known limitation, stated before the results:** the connection score counts every pair of assets on a shared pipe
network (junctions connect, as in the answer keys). It can't see the order along a line. The tracer matches that
definition. For the twin, stream order matters, and the scorecard neither rewards nor punishes it.

**Not attempted in round 2:** the planned ensemble method. It's reported as not done, not dropped silently.

## Results (round 2, scored after the addendum above; each method once per holdout)

Review load: corrections per 100 key items, lower is better.

| Method | Codex: dev / A / B | Claude: dev / A / B | Gemini: dev / A / B |
|---|---|---|---|
| M0 baseline | 66.5 / 48.8 / 67.0 | 66.4 / 61.1 / 76.6 | 90.8 / 75.9 / 92.7 |
| M1 tiling | 46.3 / 31.7 / 64.8 | 73.5 / 54.9 / 71.5 | 76.1 / 68.0 / 80.2 |
| M2 traced on M0 | 34.4 / 28.7 / **16.2** | 29.8 / 36.0 / 28.2 | 87.6 / 55.4 / 83.9 |
| **M3 traced on M1** | 20.5 / **17.8** / 20.7 | 36.1 / **32.4** / **16.5** | 59.2 / **40.2** / **38.3** |

**Verdict under the decision rule:**
- **M3 is every tool's declared method** (lowest holdout A review load), well beyond the ~1-point run-to-run noise.
- **M3 also beats M0 on holdout B for every tool,** so by the pre-registered rule it is **not** style overfitting:
  the gain carries over to a different drafting style.
- **Best result:** Codex with M3 cuts review load on holdout A from 48.8 to 17.8, about 63% fewer corrections.
  Connections found go from 55% to 88% (recall), at 89% precision.

**What the decision rule doesn't hide:**
- **Codex, holdout B:** plain tracing (M2, 16.2) beat M3 (20.7). The rule picks on holdout A, so M3 stays declared,
  and this difference is reported, not acted on.
- **Claude, tiling:** tiling made Claude *worse* on development (66.4 → 73.5) but better on holdout A
  (61.1 → 54.9) and holdout B (76.6 → 71.5). Six development drawings weren't enough to judge it, which is why the
  decision is made on the holdout.
- **Failures:** one Gemini M0 run on holdout B (drawing 23) returned malformed JSON and scores zero. The tracer
  writes an empty record for it, so tracer rows show "0 failed" while still scoring that drawing as zero.

**Twin-level result (secondary score), and an honest step backwards:**
- Built from Codex M3, instruments are attached to the right parent **87.0%** of the time on holdout A, against a
  position-only control of 85.7%.
- **The round-1 twin did better on the same sheets: 90.9%** (140 vs 134 of 154).
- **Why:** the tracer links every pair of assets on a shared pipe network. That's the connection definition the
  primary score uses (the limitation stated before the results), and it makes "which asset is this instrument on?"
  more ambiguous. The primary score improved while this twin measure slipped. It's the reason the twin measures sit
  next to the primary score.
- **Round-3 direction:** choose an instrument's parent by distance *along* the traced line, not by shared network
  membership. Tune it on development, then score it once on the holdouts.

---

# Round 3 (written before any round-3 work): a confidence marker, and the twin regression

**Constraint: no new Gemini spend.** Round 3 reuses the existing extraction runs (whole-sheet, tiled and traced, for
Claude, Codex and Gemini on all 12 OPEN100 drawings plus holdout B). The splits are unchanged: tune on dev 0–5,
score once on holdout A (6–11) and holdout B.

## Goal 1: point reviewers at the most problematic items

Give every item the system outputs (each symbol and each link) a **risk rating** and a tier: **green** (safe to
batch-accept), **amber** (quick check) or **red** (look closely). The rating may only use signals available without
the answer key at run time. Examples:
- agreement between models;
- agreement between the whole-sheet and tiled passes;
- whether the symbol sits on a traced line;
- agreement between the two parent rules;
- whether the tag is well-formed or a placeholder;
- the model's own confidence.

**Measured on the holdouts (an item is "right" if the scorer matches it to the answer key with the correct class, or
for a link, if the key contains it):**
1. **Errors caught early:** the share of all wrong items that land in the riskiest 20% of items. A random order
   catches 20%. The rating must beat the model's own self-confidence ordering on both holdouts.
2. **Green precision and green share:** the share of green items that are right, and the share of all items that
   are green. That's work a reviewer can batch-accept.
3. **Calibration:** the error rate by tier. It should rise from green to amber to red.

Tier thresholds are set on dev only. **Stated limitation:** risk ratings can only rank items the system *output*.
They can't point at symbols the system missed entirely. Missed items still need a person scanning the sheet, which
the review queue says.

## Goal 2: fix the twin's parent assignment

Choose each instrument's parent by distance along the traced line network (the nearest non-instrument asset reached
by following the line), instead of by shared network membership.

**Measured:** instrument parent accuracy on holdout A, using the same score_twin.py definition and the Codex M3
symbols. It's a win only if it beats **both** the round-2 M3 twin (87.0%) and the round-1 twin (90.9%). Holdout B is
reported; its keys have no tanks or pumps, so parents there are valves and in-line items.

## Decision rules
- Each round-3 method is scored once per holdout.
- Everything tried is reported, including what doesn't help.
- The round-2 primary score (review load) is reported alongside, to show the twin fix doesn't trade away connection
  quality.

## Round 3 results

### Goal 2: the twin's parent assignment (scored once per holdout; Codex M3 symbols)

| Parent rule | Dev (0–5) | Holdout A | Holdout B |
|---|---|---|---|
| Round 1 twin (round-1 links) | 75.4% | 90.9% (140/154) | not scored |
| Round 2: shared network (`linked`) | 86.9% | 87.0% (134/154) | **70.8%** (286/404) |
| **Round 3: along the traced line** | **92.6%** | **92.2%** (142/154) | 67.6% (273/404) |
| Position-only control | 82.8% | 83.8% | 60.6% |

(Holdout B rows are "parent right, if the instrument was found".)

**Verdict, stated plainly:**
- **Holdout A:** the pre-registered win condition is met. 92.2% beats both 87.0% and 90.9%. It clearly fixes the
  round-2 regression. The margin over round 1 is 2 instruments, which is within noise.
- **Holdout B:** the new rule is *worse* than round 2's (67.6% vs 70.8%). By the round-2 convention, that's a
  style-overfitting warning. Following the line works on the real OPEN100 drafting style and loses on the synthetic
  different-style set.
- **So the twin regression is fixed for this drafting style, not in general.** Claiming more would overstate it.
- **Product decision that follows from the data:** don't trust one rule. Where `along_line` and `linked` agree on a
  parent, accept it. Where they differ, send it to review. The confidence marker (Goal 1) is where that belongs.

### Goal 1: the confidence marker (scored once per holdout, all methods and tools)

Share of all wrong items caught in the riskiest 20% of output items: **risk rating / model's own confidence** (a
random order catches 20%).

| Method | Holdout A: claude / codex / gemini | Holdout B: claude / codex / gemini |
|---|---|---|
| M0 baseline | 70/30 · 65/40 · 61/16 | 71/31 · 69/30 · 53/31 |
| M1 tiling | 62/24 · 57/44 · 74/24 | 62/37 · 45/32 · 72/34 |
| M2 tracing | 57/31 · 55/38 · 78/17 | 77/28 · 61/33 · 53/22 |
| **M3 tiling + tracing (declared)** | 64/31 · **40/43 ✗** · 67/28 | 68/42 · **58/30** · 76/31 |

**Green tier:**
- **Holdout A:** precision 94–96%, covering 44–79% of items.
- **Holdout B:** precision 97–100%, covering 27–77% of items.
- **Calibration:** error rates rise green → amber → red in every combination. For example, Codex M3 on holdout A is
  6% → 15% → 23%, and on holdout B 3% → 11% → 47%.

**Verdict, stated plainly:**
- **Passes in 23 of 24 holdout comparisons.** The rating beats the model's own confidence, usually by two to four
  times.
- **Fails in the one that matters most:** Codex with M3 on holdout A, the declared tool and method (40% vs 43%).
  There, the tiers are still calibrated, but the ordering adds nothing over Codex's own confidence.
- **Likely cause** (flagged by the builder before any holdout run): the strongest signal is "the other models didn't
  find this". Codex is often right where the others miss, so its correct solo finds get flagged.
- **The direction for a next round, not done here:** weight agreement by how reliable each peer is, so a weaker
  model's miss counts for less.

**What a reviewer gets now:** the twin built from Codex M3 on all 12 sheets has a review queue of 2,886 items:
377 red (13%), 676 amber (23%) and 1,833 green (64%), each with a plain-language reason. Green items are about
95% right on the same-style holdout; spot-checking a sample of them stays part of the process.

# Round 4 (written before any round-4 model run): does it survive old scans?

**Question:** real archives are scans: faded, blurred, low resolution, yellowed, with speckle and worn patches. How
much does the declared method's review load grow as image quality drops? And where does it break: the models'
reading, or the code line tracer, which was tuned on clean drawings?

**Images:** holdout A (OPEN100 drawings 6–11), degraded by `scripts/degrade_scans.py` at three cumulative levels:
- L1, photocopy;
- L2, old scan;
- L3, bad scan.

Every operation keeps geometry fixed, so the original answer keys apply unchanged. The levels were set by eye on
drawing 6, before any model saw a degraded image (`docs/screenshots/scan-levels.png`). Skew and rotation are not
tested.

**Method:** the declared method M3, unchanged:
- 2×2 tiles, 0.15 overlap, `extraction/prompt_v2.md`;
- then `scripts/trace_connections.py` with its default options, run on the degraded image.

**Tools:** GPT (Codex) and Claude, both on subscriptions. Gemini is left out to keep model spend flat, per the
project owner's direction after round 3.

**Measures:**
- **Primary:** review load per level, against the clean M3 numbers already recorded (holdout A: GPT 17.8, Claude
  32.4).
- **Secondary:** symbol F1, connection F1, and failed tiles or drawings. Plus one isolating comparison: at L3, the
  tracer run on the CLEAN image with the L3 symbols. That separates the models' loss from the tracer's.

**Rules:**
- No prompt, tiling or tracer change for this round. Each level is run once per tool.
- Failures count as zero.
- Every number is reported, including a level where one tool does better than at a cleaner level, which would be
  noise. Run-to-run noise from round 2's repeats is quoted beside the results.
- No decision rides on this round. It is a measurement for planning, so there is nothing to tune toward.

