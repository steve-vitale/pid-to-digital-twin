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
key items. **Lower is better.** 0 means no scored differences. At 100, differences equal the number of key items;
this is a count, not a measured equivalence to drawing from scratch. Network-pair differences can share one cause.

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

## Round 4 results (scored once per level, as pre-registered)

Holdout A, declared method M3 (2×2 tiles + code line tracing), each tool run once per level. Scorecards are
`out/scorecard_r4-scan-L<n>-trace_holdout-a.md`; the clean numbers are round 2's.

| Image quality | GPT review load | Claude review load | Symbols, rough F1 (GPT / Claude) | Connections F1 (GPT / Claude) |
|---|---|---|---|---|
| Clean (round 2) | 17.8 | 32.4 | 0.94 / 0.90 | 0.89 / 0.78 |
| L1 photocopy | 20.6 | 29.7 | 0.92 / 0.90 | 0.87 / 0.79 |
| L2 old scan | 51.5 | 57.0 | 0.87 / 0.86 | 0.51 / 0.45 |
| L3 bad scan | 72.6 | 70.6 | 0.77 / 0.81 | 0.22 / 0.19 |
| L3 symbols, tracer on the clean image | 60.7 | 47.9 | 0.77 / 0.81 | 0.53 / 0.63 |

No drawing or tile failed at any level. Run-to-run noise from round 2's repeats is about 1 point of review load.

**What it says:**
- **Photocopy quality made no consistent difference.** GPT got 2.8 points worse and Claude 2.7 better: small, in
  opposite directions.
- **Old and bad scans cost 3–4× the review load.** That is far beyond noise.
- **The models degrade gently; the code tracer breaks.**
  - Symbol reading fell from 0.94 to 0.77 (GPT) and from 0.90 to 0.81 (Claude) at the worst level.
  - Connections collapsed to about 0.2. At L3 that is worse than the models' own links without tracing (0.36), so
    the tracer is hurting there.
  - Given the same L3 symbols, the tracer run on the clean image recovers connections to 0.53–0.63.
  - The tracer was tuned on clean digital drawings, and faded, blurred ink defeats it.
- **For an archive of scans:** clean up the images before tracing, or use the tracer only on sheets above a quality
  threshold. Either is a new method, so it would need its own sealed test. Nothing was tuned here.


# Round 5 (written before any round-5 model run): tag text on new public drawings, and replicate runs

Committed 2026-10-13, before any model saw a DEXPI image and before any replicate run started. The commit history is
the timestamp. Changes after this point go in a new dated commit that says what changed and why.

**Questions:**
1. Does the declared method M3 carry over to drawings from a different publisher, and how well does it read tag
   text? The OPEN100 and Dataset-P&ID keys have no text, so tag reading has never been scored.
2. How much does M3 move between runs of the same model on holdout A, and is the GPT–Claude gap bigger than that?

No decision rides on this round. Nothing is tuned: no prompt, tiling, tracer or scorer change, and no DEXPI result
feeds a change in this round.

## Data

**Holdout A (OPEN100 6–11), again.** It was scored once per method in round 2. Re-running the already declared
method only measures its noise; no method is chosen on it. That still uses the set up further, which is why the
replicates are pre-registered here rather than added quietly.

**New: DEXPI example P&IDs.** Source: the DEXPI initiative's public TrainingTestCases repository
(gitlab.com/dexpi/TrainingTestCases), pinned to commit `a23d61e2`, licensed **CC BY 4.0** (its LICENSE file). Every
file is fetched by SHA-256 (`data/dataset_adapters/dexpi_examples.json`); downloads, renders and converted keys stay
out of git. These are example and training drawings published by the standards body to test software exchange:
digital, vector-drawn, clean and small. They are not scans and not drawings of a running plant.

| Sheet | What it is | Key | Scored items |
|---|---|---|---|
| dexpi-c01 | The DEXPI reference P&ID (pumps, exchangers, tank, valves, 4 instrument loops) | DEXPI XML: shapes, topology, labels | 25 symbols, 37 links, 20 tags |
| dexpi-c02 | A process column with instruments | DEXPI XML | 13 symbols, 13 links, 10 tags |
| dexpi-c03 | A short pipe run with an emergency shut-off valve | DEXPI XML | 11 symbols, 10 links, 3 tags |
| dexpi-c08a | A training plant drawing exported from a CAD tool, black and white | published equipment, instrument and valve lists | 129 identifiers |
| dexpi-c08b | Its connected second sheet | same lists | 16 identifiers |

Totals: 49 symbols, 60 links and 33 tags with geometry, plus 145 listed identifiers without geometry.

**How the sheets were chosen (a rule, not taste):** every DEXPI 1.3 example in the repository that is a complete
sheet with both XML and a rendering (C01–C03), plus the only example that ships drawings with item lists (C08). Left
out: the one-object test cases (E, I and P series: a single tank, a single pipe), the DEXPI 1.2 copies of C01–C04
(the same reference plant at an earlier revision, so not independent), and the colour PDFs of C08 (the same drawings
as the black-and-white ones, which are closer to archive drawings).

**Other public sets considered:** Dataset-P&ID (CC BY-NC-ND 4.0) has text labels, but they are synthetic random
strings, the licence forbids sharing adaptations, and its drawings are already holdout B. PID2Graph Synthetic has no
text. Symbol-only sets (box labels, no lines or text) cannot score the review load. The PID2Graph paper's 60
industrial sheets are not public. None of these was used.

## Conversion (scripts/adapt_dexpi.py, rules in its docstring)

- **Images:** the published SVG (C01–C03) or PDF (C08) rasterised with MuPDF, long side 3,200 px, the size of the
  larger OPEN100 sheets. No other processing.
- **Classes:** pumps/compressors → pump; other top-level equipment → tank; valves → valve; instrument bubbles →
  instrumentation; off-page connectors → inlet/outlet; reducers, flanges, blinds, orifices, fittings → general; tees
  → pass-through connectors, as in the PID2Graph keys. Equipment internals, actuators, nozzles and flow marks are
  not separate symbols. The mapping follows the class names and the prompt's own definitions.
- **Boxes:** the symbol's own drawn shape, placed by its position, rotation, mirroring and scale.
- **Links:** every drawn line, as in the PID2Graph keys: pipe segments item to item, measuring lines and signal
  lines end to end, nozzles standing for their equipment.
- **Tag truth:** the item's own label as drawn: equipment tag, valve label, the two lines of an instrument bubble,
  or a control valve's actuator number. Items without a label carry no tag truth.
- **Tag lists (C08):** an identifier counts for a sheet only if its list row names that drawing and it is printed
  in the PDF's text layer (one listed valve is not printed and is left out).

**Checked before freezing, on the keys only:** the key boxes were drawn over each render and inspected, and the key
converted to an answer scores zero corrections with the unchanged scorer (`scripts/test_dexpi_adapter.py`). That
check led to three adapter changes, all before any model run: column sections drawn inside the column are not
separate symbols; boxes drawn as a single stroke (flanges, blinds) are widened to 0.5% of the long side, because a
zero-area box can never match; an instrument label's third line (an area prefix on C03) is not part of the tag.

**Known key limitations, stated now:** a few drawn things are not DEXPI items, so a model that reports them is
counted as a false symbol. Examples: the second "ESV 3712" bubble on the C03 actuator, C03's shut-down trigger
symbol, C02's sample-point boxes. Only 3 of C03's 11 symbols have tag text. The C08 lists cannot judge precision:
they do not cover everything printed on a sheet (line numbers, nozzles, notes), so extra predicted tags are not
counted against the model.

## Method and runs

- **Method:** the declared M3, unchanged: `extraction/prompt_v2.md` (SHA-256 `d98a6475…`), 2×2 tiles with 0.15
  overlap and `extraction/tile_preface.md`, then `scripts/trace_connections.py` with its defaults. The only harness
  change is a path setting (`PID_DATA_DIR`) so the runner, tracer and scorecard can read the DEXPI folder.
- **Tools:** Claude through the Claude Code CLI and GPT through the Codex CLI, each on its default model, which on
  2026-10-13 is the same as round 2 (`claude-opus-5-5[1m]`, `gpt-6.1-sol`). Gemini is not run (project owner's
  direction); its earlier results stay in the documents, labelled as earlier runs. A record that reports a
  different model is reported, not dropped.
- **Replicates:** five fresh runs per tool on holdout A (labels `r5-hA-rep1…5`) and five on the DEXPI sheets
  (`r5-dx-rep1…5`). Every replicate is a new call; nothing is reused or selected. The round-2 run is shown beside
  them as earlier context, not pooled into the intervals.
- **Failures count as zero**, as before.

## Measures and statistics

- **Frozen scorer:** review load, rough "found + right class" F1, connection F1 (`scripts/score_pid2graph.py`,
  unchanged).
- **Tags (`scripts/score_tags.py`, new; rules in its docstring):** on the DEXPI XML sheets, a key symbol's tag is
  correct, wrong, empty, or missed (symbol not found). Headline: strict match (case and spaces ignored). Lenient
  match (letters and digits only) beside it. Reported as accuracy on found symbols and as end-to-end recall. On C08,
  the share of listed identifiers that appear in any predicted tag.
- **Intervals (`scripts/replicate_stats.py`):** for each number, the mean of the five runs with two 95% intervals:
  1. **runs** (t-interval over the five values, drawings fixed): how much it moves when run again;
  2. **bootstrap** (resample drawings, then one run per drawing; 10,000 draws, seed 20261013): how much it could move
     with other drawings like these as well.
- **Model comparison rule:** Claude and GPT are called different on a measure only if the 95% interval of the
  difference excludes zero. The bootstrap interval is the headline, because six drawings are the real limit; the
  runs interval is shown beside it.
- **Carry-over check:** if the DEXPI review load falls outside holdout A's bootstrap interval for that tool, the
  method is reported as behaving differently on this source. It is a measurement, not a pass/fail gate.

## Round 5 results (scored after the pre-registration above)

All 220 run records came back (2 tools × 11 sheets × 5 replicates, tiled and traced). No tile or drawing failed, and
every record reports the pre-registered model (`claude-opus-5-5[1m]`, `gpt-6.1-sol`). Full tables:
`out/replicates_r5_holdout-a.md` and `out/replicates_r5_dexpi.md`.

### Replicates on holdout A (M3, five fresh runs per tool)

| Measure | GPT: 5 runs | GPT mean (runs 95% / bootstrap 95%) | Claude: 5 runs | Claude mean (runs 95% / bootstrap 95%) |
|---|---|---|---|---|
| Review load | 20.7, 21.5, 18.4, 18.8, 21.0 | **20.1** (18.3–21.8 / 14.2–28.0) | 30.9, 30.8, 28.5, 27.2, 31.6 | **29.8** (27.5–32.1 / 12.8–47.3) |
| Symbol F1, rough + class | | 0.929 (0.918–0.940 / 0.908–0.949) | | 0.898 (0.892–0.904 / 0.840–0.952) |
| Connection F1 | | 0.872 (0.864–0.879 / 0.801–0.916) | | 0.795 (0.779–0.811 / 0.638–0.920) |

Round 2's single runs (GPT 17.8, Claude 32.4) sit just outside the five-run intervals, on opposite sides: GPT's
round-2 run was a good draw, Claude's a bad one.

**GPT minus Claude, review load:** −9.8. Runs interval −12.2 to −7.3: on these six sheets, GPT is better by more than
run-to-run noise. Bootstrap interval −26.5 to +4.5: across drawings like these, the gap is **not** established. By
the pre-registered rule (bootstrap is the headline) this is a **tie**. The same holds for symbol F1 and connection
F1: different on these sheets, no clear ranking across drawings. "Tie" here means the rule does not establish a
winner; it does not establish equivalence. One sheet carries much of it: sheet 10 (Claude 58.7, GPT
20.1 mean review load).

**Run-to-run noise is larger than round 2 assumed.** Round 2's decision rule used "about 1 point" of review load,
from one repeat on the development set. Five runs on holdout A give a standard deviation of 1.4 (GPT) and 1.9
(Claude) points, and a spread of 3–4 points between the best and worst run. The round-2 verdict (M3 beats M0 by
31 points for GPT and 29 for Claude) is far outside either figure, so it stands.

### DEXPI sheets (M3, five runs per tool): symbols and connections

| Measure | GPT mean (runs 95% / bootstrap 95%) | Claude mean (runs 95% / bootstrap 95%) |
|---|---|---|
| Review load | **95.4** (53.2–137.6 / 42.1–138.6) | **61.8** (60.5–63.1 / 26.3–127.9) |
| Symbol F1, rough + class | 0.728 (0.658–0.797 / 0.585–0.826) | 0.754 (0.736–0.773 / 0.529–0.917) |
| Connection F1 | 0.454 (0.238–0.670 / 0.218–0.778) | 0.605 (0.591–0.618 / 0.071–0.821) |

Per sheet (mean review load, GPT / Claude): C01 100.0 / 25.8, C02 77.7 / 93.1, C03 103.8 / 129.5.

- **Carry-over check:** both tools' DEXPI review load is outside their holdout-A bootstrap interval (GPT 14.2–28.0,
  Claude 12.8–47.3). By the pre-registered wording, **the method behaves differently on this source: it does
  worse.** GPT minus Claude: a tie under both intervals.
- **GPT was bimodal.** On C01 it reported the equipment nozzles (labelled N1, N2…) as separate "general" symbols in 3
  of 5 runs, and not in the other 2. Those runs scored 143.5–146.8 on C01; the other two scored 32–34. The tracer
  then attached lines to every nozzle, which multiplied false links (50 per run). One run would have shown either
  number with no hint of the other.
- **Why the review load is high on C02 and C03.** These are small sheets (26 and 21 key items), so each correction weighs about 4–5 points. Most false symbols are drawn things the DEXPI model does not list as items: nozzles (45 of
  GPT's 102 false symbols across all runs, 17 of Claude's 51), sample-point boxes, the shut-down trigger and the
  second actuator bubble on C03, all of which were named as limitations before the run. Whether a nozzle is a
  symbol is a key-scope choice. The key was frozen before the runs, so these count as errors, and the count is
  reported here rather than corrected.

### Tag text (first measurement in this project)

**DEXPI XML sheets (33 symbols with label text):** identical in all five runs for each tool.

| | GPT | Claude |
|---|---|---|
| Correct, strict | 29 of 33 (0.879) | 28 of 33 (0.848) |
| Accuracy on symbols it found | 29 of 33 (0.879) | 28 of 31 (0.903) |
| Lenient (letters and digits only) | same as strict | same as strict |
| Bootstrap 95% (end-to-end) | 0.67–1.00 | 0.60–1.00 |

Every tag on the reference sheet C01 was read exactly by both tools (20 of 20): equipment, valve labels, control-
valve numbers and two-line instrument bubbles. The misses are all of one kind: text that isn't next to its symbol in
the usual way. Vertical valve labels on C02 were left empty (Claude) or replaced by nearby text, "25 / AS9" (GPT); the
blind-flange size labels on C02 were missed with their symbols (Claude); the column's two-line label "K 2750 / KX
2750" was read whole where the key's first-line rule wants "K 2750" (GPT); the C03 control valve's number sits on a
separate actuator bubble, and neither tool attached it to the valve.

**C08 tag lists (145 identifiers printed on two sheets):** GPT found every listed identifier in all five runs; Claude
found 99.4% on average (it missed 0–3 identifiers per run, mostly different ones). Precision cannot be scored
from the lists. A cross-sheet control finds 5 of sheet 2's 16 identifiers in a sheet-1 answer, because valve numbers
AB001–AB006 exist on both sheets; short identifiers can match by coincidence, so these recall figures are an upper
bound on true item-level reading.

**What the tag numbers support:** on clean, vector-rendered drawings at 3,200 px, both models read printed tags
almost perfectly. They do not show tag reading on scans, on handwriting, or on dense real archives, and 33 + 145
items on five sheets from one publisher is a small sample. The bootstrap intervals (0.6–1.0) are that size.

### Diagnostics (not pre-registered, labelled as such)

- **Tracer on DEXPI:** the model's own links without tracing (M1) give a review load of 79.3 (GPT) and 65.0
  (Claude). Tracing helped Claude a little (to 61.8) and hurt GPT (to 95.4), mostly through the nozzle runs above.
  `out/replicates_r5_dexpi_tiles_only_diagnostic.md`.
- **M1 on holdout A, five runs:** GPT 36.7 (round 2's single run: 31.7), Claude 53.0 (54.9).

**Nothing was changed because of these results.** A key that counts nozzles, a tracer that ignores small stubs on
equipment, or a prompt line about nozzles would each be a new method and would need new, unseen drawings.

## Standing engineering-context goal (2026-10-29)

Help an engineer start from a usable set of drawings, equipment information, operating documents, controls
records and historian data, then build context their organization can review, maintain and own. More inputs or
features count as progress only when they resolve a concrete engineering task and carry their source, uncertainty,
review state and update path. No saved answer should silently become a plant fact.

The next increment follows two fresh AI reader exercises: a solo plant engineer, and a controls integrator with
a skeptical manager's concerns. Both found the missing return step after a question is generated: preserve an
answer, its accountable owner, competing evidence and the reason it must be revisited. A read-only control also
showed that the legacy statement-review command accepts a verdict after the cited source changes if the statement's
subject, predicate and value stay the same. That command's limitation is now visible in its guide.

**First increment and acceptance criteria, set before measuring its results:**

1. A local, offline context-answer sidecar reads an existing model/questions and a document manifest, accepts an
   engineer-filled CSV, and writes a readable context report and enriched graph without editing the base model.
2. Answers have stable asset/question references, an explicit owner (or needs owner), reviewer/date, source identity,
   revision, exact locator and raw-byte hash. Source interpretation and plant truth remain separate.
3. Partial, unanswered, rejected, disputed and stale answers remain visible. Different sourced observations are
   not automatically a conflict; an explicit comparable claim with differing values is.
4. Identical reruns preserve decisions and history without duplicate events. Changing evidence or a dependent
   question/asset invalidates only affected decisions. Unrelated or status-only changes preserve other decisions.
5. An old CSV cannot approve revised evidence. Missing, unknown or ambiguous references refuse the operation before
   output writes. Old decision history survives; no automatic source rebinding or organizational authority is inferred.
6. An illustrative offline fixture tests these mechanics. A linked PRONTO packet exercises real public report,
   alarm-setting, operation-log and event-record sources with exact locators and independently checked facts.
   Disabled alarm settings must never become enabled alarms, and documented source disagreements remain unresolved.
7. Source-revision and conflict controls are planted changes to disposable copies, labelled as such. They are not
   historical revisions or real operator decisions. PRONTO expands multi-document coverage within an existing
   facility; it adds no independent source family.

After this increment, use another fresh reader pass and the observed failures to choose the next workflow or
corpus extension. Actual ownership assignments, governing-document decisions, walkdowns, live-signal validation
and review time require people at a site; this goal does not treat software fixtures as those results.

### Next maintenance check: bind statement reviews to their evidence

Prospective acceptance criteria, 2026-10-29, before the implementation is evaluated. The documented legacy
statement-review CSV can match a semantic statement ID after its cited evidence changes. Close that path while
retaining the historical samples and their scores as records of what was reviewed at the time.

1. Newly rendered statements, CSV sheets and browser downloads carry a per-statement fingerprint. It binds the
   canonical full graph snapshot, canonical machine-check model content when available, actual raw bytes of every
   supplied drawing/report file, and the statement's wording, source pointer, targets and relationship layer.
2. Sampling preserves that binding, including when sampling by relationship layer. Sampling an old unbound file
   must not create a new evidence-bound approval for it. Historical scoring remains available without importing
   old verdicts into current evidence.
3. Applying verdicts reads current evidence bytes through the same explicit input options. A changed or missing
   input, missing binding, edited statement text/source/layer or stale fingerprint refuses before output writes.
   One invalid binding must not let other rows silently persist. There is no legacy bypass or automatic rebinding.
4. All supplied files are checked before rendering output. Ambiguous sheet identities fail. Applying must not
   overwrite its graph, sheet, model or source documents through direct paths, symlinks or hard links.
5. Successful output retains the fingerprint and evidence basis with each dated review. The graph's engineering
   values remain unchanged and source interpretation remains separate from plant truth. Generated provenance must
   not introduce local absolute paths or infer authenticated organizational authority.
6. Whole-packet invalidation is explicit: any graph snapshot change, including an unrelated asset or review state,
   requires a new render. Canonical JSON formatting changes alone do not. Source images/reports bind raw bytes.
   The separate context register retains its existing selective-dependency workflow.
7. Clearly identify graph/model-only coverage when no original drawing/report was supplied. Neither fingerprints
   nor retained history prove that a source is authoritative, its passage supports a claim or a reviewer is
   authenticated. No watcher, downstream synchronization or automatic approval is implied.
8. Demonstrate the new round trip on a current public graph and supplied original drawing, with copied-input
   revision controls and fresh independent review. Preserve earlier reviewed samples rather than redrawing them
   and changing the historical population. This is software evidence, not a timed human or operational review.

The resulting [current sheet-0 packet](../examples/statement-review/bound-sheet0/README.md), independent review
receipt in `data/reviews.json` and [journal 68](JOURNAL.md#68-make-source-changes-and-generated-outputs-fit-one-reviewed-context)
record this maintenance increment. The [organizational lifecycle](CONTEXT_LIFECYCLE.md) sets the next integration
acceptance target; local binding controls do not establish that a live hub or ongoing document synchronization exists.

### Maintenance acceptance: retain unplaced asset semantics and context history

2026-10-29. Development repairs to inspected failures, not a new blind benchmark. Existing DEXPI dialect repairs
already read the control functions that the original reader missed. Do not retune the remaining IEC-category
truth-definition issue or change the matrix's pre-registered pass criteria.

1. A known `unplaced` item's recorded `kind` survives graph export when the graph contract supports that kind.
   An instrument remains an instrument and a final element remains a final element. Unknown/legacy kinds retain
   an explicit fallback; no owning unit, plant verification or physical connection is invented.
2. A controller's explicit `measurement_unplaced` or `output_unplaced` reference becomes the corresponding typed
   control relationship when the target is a represented, appropriate asset. Keep the original reference claim,
   source and placement uncertainty. Missing or incompatible targets must not become guessed edges or disappear.
3. Check the changed projection against original XML and the reader model on concrete public exports, including
   Comos I04V01 FIC-04 / FV-04. Broader cached-file checks retain refusals and report scope/counts; these files
   have already been inspected and are development evidence. Existing graph examples must still reproduce.
4. Refreshing into a folder containing nonempty context decision/ownership history without `--register` refuses
   before writes. Initial prepare-to-first-apply with an empty history remains supported.
5. A destination register's retained histories may not be discarded by supplying an older or divergent register.
   Preserve every prior record unchanged and in order, or refuse before writes and use a separate output folder.
   There is no automatic branch merge, reset bypass or inferred authority.
6. Validate known destination/input conflicts before writing any output. Refusal preserves the existing register,
   readable reports and base/source inputs. Explicit current-register refresh and idempotent repetition still work;
   actual source changes still reopen only their dependent answers while retaining history.
7. Demonstrate history preservation/refusal through the actual CLI on the public NIST packet and with focused
   illustrative controls for ownership and divergent branches. No source original is edited; historical examples,
   review verdicts and scoring criteria remain records of their original runs.
8. Independently review the frozen code and exact new examples, rerun affected matrix cells with their original
   criteria/tool hashes, and run the appropriate registered tests. These are local software/source checks, not
   adoption, authenticated approval, concurrent-service guarantees or an incumbent integration.

### Maintenance acceptance: report the checks that actually ran

2026-10-29. The exact-commit CI log for `8b90d3a` reported 58 successful scripts and zero platform skips, but also
showed at least 12 visible cache-dependent unittest skips and an optional oracle that returned normally without running its
check. The final complete-suite message hid those omissions. The local cache-backed run exercised those source
checks but skipped two Windows symlink controls. Those environments have different coverage.

1. Count unittest's reported skipped cases from either output stream, including failure summaries. Identify
   explicit platform notices separately from other skipped-check notices, without double-counting a platform
   case already included in unittest's total. Do not classify a missing source cache or dependency as a platform
   restriction merely because its message begins with `SKIP`.
2. Replace the oracle's normal return on absent data with a real unittest skip. A test script's successful exit
   may coexist with skipped cases; the runner must not claim a complete full-suite pass in that situation.
   Preserve failure/preflight exit meanings and source-only exclusions. Do not silently install or fetch inputs.
3. Exercise actual child processes with genuine unittest class/method/subtest skips and custom notices, as well
   as failures and fully executed positive controls. Verify counts across stdout/stderr and avoid false matches
   on ordinary prose mentioning a skipped action. Keep existing platform/refusal controls meaningful.
4. Reproduce the omission using the earlier implementation and the same child results, then show the corrected
   report. Check the actual optional-oracle path on a disposable missing cache and the real local cached path.
   Explain optional source coverage and setup in the reviewer/replication guides; historical receipts retain
   their original scope and must not be relabeled as having run missing checks.
5. Review the frozen reporting change independently and run the registered suite locally and in CI. Report each
   environment's actual omissions. No new extraction score, plant acceptance, customer benefit or exhaustive
   proof that arbitrary test programs cannot hide work is implied.

### Maintenance acceptance: carry model rejections into subsequent questions

2026-10-30, before repair. The engine currently ignores `ops_review`. On the existing synthetic food model,
applying explicitly fictional rejections of the power meter JT-201, speed drive SC-203 and heat-recovery unit
HX-303 leaves E29 at K-203 and E31/H6 at F-303 quiet, and still omits K-201 from the existing model-wide C12
metering question. A rejected item must not
continue to supply evidence that suppresses the next question. This is a software control on invented equipment,
not a new corpus, correction to a real plant, human review or energy finding.

1. Explicit `ops_review.status = rejected` records cannot trigger or suppress a question, provide evidence or
   data-request locations, satisfy a required model kind, or carry a relationship/traversal path. Apply this to
   both accepted model formats. Missing/unverified review remains eligible and is not implied to be approved.
2. Keep source model bytes, rejected records and their review history intact. List excluded records and their
   recorded decisions in generated screens. Retain non-rejected children independently; remove their reliance
   on explicitly rejected owning units, parents or streams without inventing a replacement or recursively
   rejecting them. Do not alter ordinary unresolved references or historical unreviewed example outputs.
3. A supplemental loop list must not silently recreate a controller explicitly rejected in the model. Preserve
   tag ambiguity where a live duplicate remains. Refuse malformed review metadata before writing a screen.
4. Demonstrate the actual apply-review-to-question CLI path and named changes on the existing illustrative
   food model, including idempotent review and a later explicit reconfirmation. Include positive controls and
   extracted-model relationship controls. Old examples retain their original populations and result files.
5. Independently reproduce the baseline failure, review the frozen change and exact new packet, run affected
   generalization cells with unchanged criteria and report actual local/CI test omissions. This establishes
   maintenance behavior only; no authenticated review, source authority, plant truth or adoption is inferred.
