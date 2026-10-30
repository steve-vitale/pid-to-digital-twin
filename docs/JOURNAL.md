# Build journal

Entries describe their historical snapshots. Local receipts, review conversations, intermediate render packages
and sealed trial evidence are not included here. A historical verification statement is not a current result.
AI coding agents (Claude Code, and later Codex) wrote most of the code and first drafts; I set the direction and
checked the results.

How this project was built and why each choice was made, written as it happens. Results are in the README and
`out/`. This file is the reasoning behind them.

Each entry: **What** (one line) · **How** (the method, concretely) · **Why** (the reasoning, including what we rejected) ·
**Lesson** (what generalizes beyond this project) · **At your plant** (how to apply it to a real site; full guide in [AT_YOUR_PLANT.md](AT_YOUR_PLANT.md)).

---

## 1. Start with a sketch that runs end to end

**What:** a hand-built model of the Tennessee Eastman plant, plus one script that turns it into every output format.

**How:** one JSON file describes the plant: units, streams, instruments, valves, and where each item came from. A
Python script (stdlib only) reads that file and produces:
- SVG graphics with tag IDs embedded in each element
- an Ignition tag/UDT import file
- a PI Builder-style asset sheet
- a plain-language review sheet for operations

**Why:**
- **One model, many outputs.** If the SVG, the Ignition tags and the PI hierarchy were each built separately, they'd
  drift apart. With one source, a correction made once shows up everywhere.
- **Build the output end first.** Before asking any AI to read a drawing, we need to know exactly what shape its
  answer must take. The hand-built model defines that target. It also becomes the answer key when we score
  extraction later.
- **Tags inside the graphics.** Every element carries a `data-tag`, so connecting live data is a mapping step,
  not a redraw.
- **Stdlib only.** Anyone can run it with no install friction.

**Lesson:** the first render had instruments clipped at the canvas edge and drawn over pipes. Every structural check
passed (unique tags, valid references, ISA letters matching the measured variable), but no check could see layout.
Someone had to look. *Checks prove what they check, and nothing more.*

**At your plant:** define the target format first: your tag convention, your asset hierarchy levels, and which attributes Ignition or PI needs. Then capture a few sheets by hand into exactly that format. That becomes both your spec and your answer key. Always have a person look at rendered output; structural checks miss layout and meaning. See [AT_YOUR_PLANT.md](AT_YOUR_PLANT.md) §2.

---

## 2. Plan the whole arc before building more

**What:** decided who this is for, what counts as proof, and what's out of scope, before writing more code.

**How:** wrote down the constraining questions (audience, which drawings, which platforms, who reviews, which AI
tools, what budget) and answered each one. Then researched every assumption the plan rested on, before building
anything that depends on it.

**Why:** the expensive mistakes in a project like this are wrong *assumptions*, not wrong code. Three assumptions
failed under research:

| Assumption | What research showed | What we changed |
|---|---|---|
| We'd score AI extraction against our own answer key | A public dataset (PID2Graph) has independently annotated real P&IDs, including the open OPEN100 reactor design | Score against third-party ground truth. A number we define ourselves is weaker evidence |
| SVGs can be pasted into PI Vision | PI Vision stopped supporting plain custom SVG import (2023+) | Graphics go to Ignition Perspective (it keeps SVG element ids, so styles can bind to tags); PI gets the asset hierarchy |
| We could demo on both platforms for free | There's no free PI environment for individuals (only a 45-day developer trial); Ignition has a free, resettable trial | Ignition carries the "it actually loaded" proof; the PI output is clearly labeled as not import-tested |

**Lesson:** check vendor reality before promising a workflow. Half a day of research removed a deliverable that
would have been impossible.

**At your plant:** before promising anyone a workflow, confirm three things:
- what your platform versions actually import (Ignition, PI AF, PI Vision);
- whether your drawings are intelligent P&IDs you could export instead of reading as images;
- what your security policy allows to leave the network.

Any one of these can change the plan. See §1 and §5.

---

## 3. Write the fairness rules before running any comparison

**What:** Claude, GPT and Gemini will read the same drawings. The rules for comparing them are fixed in advance.

**How:**
- same images, same prompt, same output schema, same scorer
- record which model and access path produced every run
- report first-try scores, not the best of several attempts
- repeat runs to show variance
- report real and synthetic drawings separately

**Why:** comparisons drift toward whatever the author hoped to find. Fixing the rules before seeing results is the
cheapest guard against that. The tools are also reached through different paths (subscriptions, an API), so we
record the path and say so wherever it could explain a gap.

**Lesson:** decide how you'll judge before you see the answer.

**At your plant:** when you evaluate vendors or models, give each one the same sheets, including your worst scans. Score them against the same hand-built key and agree on the scoring rules before the demo. Vendor demos on hand-picked drawings tell you little.

---

## 4. Work within the hardware you have

**What:** the scoring dataset is one 9.3 GB zip. The build machine has about 11 GB free, and Ignition needs room
too.

**How (planned):** a zip file keeps its table of contents at the end. We read just that part over HTTP range
requests, then fetch only the entries we need (the OPEN100 subset and the real P&IDs).

**Why:** buying disk or cleaning up would also work, but pulling only what you need is the habit that scales.
Datasets in this field are large, and most projects need a small slice of them.

**Lesson:** constraints are design inputs, not blockers.

**At your plant:** the equivalent constraints are bandwidth, data-egress policy, and whether a cloud model may see your drawings at all. Design for the narrowest one first: send only the sheets in scope, redact title blocks if policy requires, or use an on-premises model. See §5.

---

## 5. Check the answer key against a source, with a checker you've tested

**What:** the 37 instruments and valves in the seed model were checked against the open Tennessee Eastman source
code. 36 matched and 1 was wrong.

**How:**
- The original 1993 paper is paywalled. The simulation code the research community uses (`teprob.f`, Braatz group,
  open license) lists every measurement and valve, with units, in its header comments.
- `scripts/verify_te_source.py` downloads that file and parses the list.
- It compares each model item's name and units, then writes a verification record into the model: status, source,
  date, the exact source line, and the old value whenever something was corrected.
- Run it again any time; correction history is kept.

**Why a script and not a careful read:**
- A script can be rerun, and anyone can audit it.
- It also hands the operations review a list in which every row already says where it came from.

**The checker needed checking too:**
1. **First run:** it flagged "Separator temperature" as wrong because the source abbreviates it to "Sep Temp".
   That was a false alarm.
2. **First fix (wrong):** a stop-word list that was too aggressive, which threw away the very words being compared.
3. **Second fix:** abbreviation handling, plus a small stop-word list.
4. **Negative control:** we then planted three deliberate errors (a wrong unit, the wrong equipment, an unrelated
   name). It caught all three. A checker that only ever says "confirmed" proves nothing.

**What it found:** measurement 22 (TI-122) was in the model as the *condenser* cooling-water outlet temperature.
The source calls it the *separator* cooling-water outlet temperature. Many write-ups say "condenser" because the
cooling-water valve (XMV 11) is labeled "condenser cooling water flow". The model now uses the source's name.
Which equipment the tag belongs to is left as an explicit open question for operations review.

**Bonus:** the source also gives each composition analyzer's sampling period and dead time (6 minutes for
reactor-feed and purge-gas analysis, 15 minutes for product analysis). These map directly to tag scan settings,
so they're now in the model.

**Lesson:** verify the verifier. Test a checker with known-bad input before you trust its "all clear". And when
the source itself is ambiguous, record the question; don't quietly resolve it.

**At your plant:** your sources disagree too. That includes the drawing vs the DCS tag list vs the historian vs the maintenance asset register. A small script that cross-checks extracted tags against those lists does the same job as `verify_te_source.py`, and the mismatches it finds are often real documentation gaps, not AI errors. Test the script with planted errors before trusting it. See §1 and §4.

---

## 6. Take 0.2% of a 9.3 GB dataset

**What:** we pulled the 12 real P&IDs from the PID2Graph dataset (the OPEN100 reactor design drawings, plus their
answer keys) out of a 9.3 GB zip. We downloaded 19.5 MB.

**How:**
- The server supports HTTP range requests: "send me bytes X to Y".
- A zip file stores its table of contents at the end. `scripts/fetch_pid2graph.py` wraps the remote file in a small
  seekable reader, so Python's standard `zipfile` module can read that table of contents over the network (10 MB
  for all 74,655 entries).
- It then fetches only the entries we ask for. Nothing else is downloaded.

**What the listing showed (worth knowing before writing a scorer):**
- **Contents:** the archive has the 12 OPEN100 drawings, 500 synthetic drawings from an earlier dataset (Dataset-P&ID),
  500 PID2Graph synthetic drawings, and tiled "patched" copies of all three for model training.
- **Not in the public archive:** the paper's 60 annotated real industrial P&IDs. That leaves OPEN100 as the only real,
  inspectable test set.
- **Answer-key format:** each drawing comes with a `.graphml` graph. Nodes are symbols with a class and a bounding box.
  The 8 classes are connector, crossing, arrow, instrumentation, valve, inlet/outlet, general and background. Edges
  are the lines between symbols.
- **No text in the key:** the drawings carry real tags (MOV 1113, TCV 1115, TE 111216A), but the answer key doesn't
  record any text. Tag reading can't be scored against this key. The TE plant (entry 5) is where tag accuracy gets
  measured.

**Why it matters:**
- The extraction prompt's output schema has to map onto these 8 classes, or the score is meaningless.
- That's decided now, before any model runs, so no one can tune the mapping after seeing results (entry 3).

**Lesson:** read the answer key's format before building the thing it grades.

**At your plant:** you'll rarely have a third-party answer key. Hand-annotate 3–5 sheets yourself, including a bad scan, and decide up front what counts as a match. Do you need the exact tag text, the right symbol class, the right equipment, the right connection? Decide before the first model run. See §2.

---

## 7. Fix the scoring rules first, then test the scorer until it can't be fooled

**What:** a scorer that grades any model's extraction against the PID2Graph answer keys, written and tested before
a single model ran.

**How:**
- **Profile the key.** It has 10 classes, not 8. Four are drawing plumbing (2,408 line-bend points, 734 line
  crossings, 451 flow arrows, 48 drawing frames). Six matter for a twin: instruments (350), valves (257), other
  inline symbols (234), off-page connectors (96), tanks and vessels (35), pumps (16).
- **Detection.** Score only the six asset classes, matching predicted boxes to key boxes by overlap. Two thresholds:
  - strict IoU ≥ 0.5, the object-detection standard;
  - rough IoU ≥ 0.1, "in about the right place", because vision models give loose coordinates.
- **Connectivity.** Score at the asset level: which tanks, pumps, valves and instruments connect, tracing through
  the line-bend and crossing points. That's what a twin needs.
- **Controls.** Five tests on every drawing: a perfect answer (built from the key itself), an empty answer, every
  class deliberately wrong, every box moved half a sheet, and half the symbols dropped.

**What the controls caught:**
1. **First rule:** "the predicted box centre lands near the key box". With every class wrong, it still gave
   **15–32% credit**, because a mislabeled valve landed in the neighbouring instrument's zone and small symbols sat
   inside a tank's large box.
2. **Tightened version:** still 3–20%. The rule itself was wrong, not the setting. Switched to IoU.
3. **My own control was weak:** the "moved" test also shrank every box to 1×1, which can never overlap anything
   under IoU, so it passed for the wrong reason. Fixed to keep box sizes.
4. **One honest chance floor:** drawing 6 contains two identical reactor-coolant-pump details half a sheet apart.
   Shifting every box half a sheet lands one detail on the other: strict score 0, rough score 8.8%. So the rough
   score carries a small chance floor on repetitive sheets. It's documented, not hidden.

**Why this matters more than the model comparison itself:** a loose scorer flatters every model at once, and it
flatters weak ones most. Without the controls, a model that labeled everything wrong would have scored 15–32%.

**Lesson:** test the grader before you grade. Positive controls prove it can say yes; negative controls prove it
can say no. Both are needed.

**At your plant:** before trusting any accuracy number from a vendor or an internal pilot, ask how a match is
decided, and ask what a deliberately wrong answer scores under the same rules. If nobody has tried, try it. Also
decide which symbol classes matter for your use. Scoring line-bend points next to pumps inflates or deflates
results for reasons that don't matter to operations.

---

## 8. Define "done well" first, then guard the definition from the people chasing it (us)

**What:**
- Three runs of three frontier models (Claude, GPT via Codex, Gemini) on 12 real drawings: first try, an identical
  repeat, and a prompt revision.
- An open-weight model (Gemma 4 31B) as a stand-in for what a plant could run fully offline.
- The evaluation rules that make those numbers worth anything. They're written up in full in
  [EVALUATION.md](EVALUATION.md).

**How we define "done well":** not "a high score".
- The outcome is a reviewed asset model that costs operations less time than building it by hand, with no more
  errors.
- Every metric is a proxy for that, so each one is listed with what it *can't* see. Rough detection can't judge
  graphics precision; strict detection can't tell whether a class matters to operations; nothing on the public
  dataset can judge tag text.
- The last word belongs to the operations review: what a person who runs the unit still had to fix.

**How (the anti-Goodhart rules, each one used in this project):**
1. **Rules written before results.** The scorer's rules are dated and were committed before any model ran.
2. **The grader was tested before it graded.** A deliberately wrong answer scored 15–32% under the first scorer; it
   scores about 0 now (entry 7).
3. **No single headline.** Precision and recall, strict and rough, per class, and connectivity separately.
4. **Noise measured before claims.**
   - The identical repeat run showed Claude and Codex move about ±0.03 between runs, so their 0.85 vs 0.87 is a tie.
   - First-try Gemini moved ±0.13, which is how we found its problem.
5. **Failures count as zero.** No tool looks better by crashing quietly.
6. **First try stays the headline.** Every later change is labeled as a change.
7. **Tune on one set, report on another, and admit it when we didn't.**
   - Prompt v2 was written after seeing first-try results on all 12 drawings. That breaks the held-out rule in
     spirit.
   - Why we think the bias is small: the change was format-only, applied to every tool, and barely moved the two
     tools without the format problem.
   - Still, from now on any change is tuned on a declared development set and checked once on a sealed set nobody
     has looked at.
8. **Don't teach to the answer key.** Every model scores poorly on the key's catch-all class `general`
   (F1 0.11–0.45), because "general" means whatever the annotators decided. We could tune prompts to guess their
   habits and the score would rise. A digital twin would gain nothing. We report it and leave it alone.
9. **Price the gain.** Time and cost per sheet sit next to every score.

**What the numbers say (12 real drawings; details in EVALUATION.md §4):**

| Tool | Found + right class: first → repeat → v2 | Connections (v2) |
|---|---|---|
| Codex (gpt-6.1-sol) | 0.87 → 0.87 → 0.85 | 0.53 |
| Claude (claude-opus-5-5) | 0.85 → 0.85 → 0.85 | 0.42 |
| Gemini (gemini-3.1-pro-preview) | 0.44 → 0.57 → 0.74 | 0.24 |

- **Gemini's gap was mostly format, not vision.** On 5 of 12 drawings it wrote box coordinates in a different axis
  order (y before x). Those drawings scored about 0 as delivered and 0.60–0.92 with the axes swapped back.
  - Prompt v2 replaced the bare `[x, y, x, y]` list with named fields (`x_min`, `y_min`…). The collapses
    disappeared, and its score went from 0.44 to 0.74.
  - The first-try number is still the headline. In production, a silently wrong format would have put every box in
    the wrong place.
- **Everyone is near-perfect on instruments and off-page connectors (0.98–0.99), and everyone misses more than half
  of the connections** (recall 0.17–0.44). Topology is where people stay in the loop.
- **Twelve drawings from one public design** is enough to see patterns, not enough to rank tools for a different
  drafting style.

**Why the rules matter more than the ranking:** for each of these numbers, it was easy to find a way to make it
look better without making the result more useful: a looser grader, a best-of-three run, quiet failures, tuning to
the key's quirks. The rules exist because the person chasing the metric (here, an AI agent and me) is the one most
likely to fool themselves.

**Lesson:** write down what "done well" means in operational terms, pick proxies with their blind spots named, and
decide how you'll catch yourself gaming them, all before the first result arrives.

**At your plant:** the same rules apply whether you evaluate a vendor, a cloud model, or an open-weight model you
run offline:
- **Weight the measures by your goal.** A tag list cares about instrument recall and tag text; graphics care about
  box precision; analytics care about connectivity (see EVALUATION.md §3).
- **What doesn't flex:** rules before results, controls on the grader, measured noise, failures counted, a held-out
  check, and a person with the final say. Those are governance, and they shouldn't bend to the use case or to a
  deadline.
- **Re-run the same suite for every change:** model, prompt or fine-tune. Keep the scorecards as the change record.
  That's how AI tooling fits inside MOC instead of around it.
- **Sensitive drawings and open-weight models:** an open-weight model can run with no network at all.
  [AT_YOUR_PLANT.md §6](AT_YOUR_PLANT.md) covers what that takes and roughly what it costs.

---

## 9. Ask the offline question with data, not opinions

**What:** Gemma 4 31B, an open-weight model a plant could run with no network connection, went through the same
evaluation as the cloud models.

**How:**
- Same prompt v2, same 12 drawings, same scorer.
- Run through Google's hosted copy of the open weights. That's the cheapest way to see the model's behaviour before
  anyone buys a GPU.

**What happened, reported the way the rules require:**
- **First try:** 5 of 12 calls hit the 30-minute timeout and scored zero, for 0.25 "found + right class". That
  number stays the headline.
- **Retry with a 90-minute timeout, labeled as a retry:** 2 of the 5 finished in about 4 minutes each. The other
  three (drawings 0, 9, 10) timed out again, the same three both times.
- **Where it completed:** high precision (when it names a symbol, it's usually right) and low recall (it misses
  most). About 0.53 "found" F1 across the 9 completed drawings, against about 0.90 for the frontier models.

**Why it matters:**
- **For plants that can't send drawings out,** this is the honest trade-off today: a ~30B open model gives up a
  lot of accuracy out of the box on this task, and it stalls on some dense sheets.
- **That doesn't make it the wrong choice.** It means the decision needs numbers. Annotating your own sheets and
  tuning the model (AT_YOUR_PLANT.md §6) is how the gap usually narrows, and this same suite is how you'd prove it
  narrowed.

**Lesson:** "can we run it offline?" is a measurable question. Measure it with the same rules as everything else,
including the failures, before anyone signs a hardware purchase order.

**At your plant:**
- **Before sizing hardware,** run your 3–5 annotated sheets through candidate open-weight models on rented or
  hosted compute. It costs dollars, not a GPU purchase.
- **Record timeouts and stalls as failures,** not as missing data. A model that hangs on your densest sheets will
  hang in production too.
- **Decide what you'll accept before you look.** Write down the accuracy threshold and the share of sheets that
  must complete before results come in. Otherwise the procurement decision turns into goalpost-moving (§2 of
  EVALUATION.md).

---

## 10. Checkpoint: what works, what doesn't yet, and how round 2 will be judged

**Where things stand:**
- **Works:** extraction by four models, scored honestly; a generator that turns a plant model into SVG graphics,
  Ignition tags and UDTs, a PI AF sheet, and an operator review sheet.
- **Not built yet:** the step that turns *extraction output* into a plant model (equipment hierarchy, instruments
  attached to their equipment, streams from connections, sheets stitched together). Without it the demo stops at
  "here is what the AI found" instead of "here is your digital twin". Round 2 builds it.
- **Biggest weakness measured so far:** connections. Every model misses most of them (recall 0.12–0.55). Process
  topology is what makes a twin more than a parts list.

**The goal, written down before round 2 started ([GOAL.md](GOAL.md)):** produce a digital twin starter kit that
needs as little human correction as possible, and that says where to look.

**The primary score, review load,** is literally that: the corrections a reviewer must make (delete, add, relabel,
fix a link) per 100 items on the drawing. Round-1 baseline: about 49–61 on the held-out drawings for the two best
models.

**How we avoid overtraining to our own scorecard:**
- **Three fixed splits:**
  - drawings we may inspect and tune on;
  - sealed drawings from the same design;
  - sealed drawings from a *different* drafting style, chosen by a fixed random seed and never opened.
- **No drawing-specific rules,** a frozen grader, and every method reported including the ones that don't help.
- **Wins must clear the measured run-to-run noise.** A gain that holds on the same-style holdout but not on the
  different-style one is reported as overfitting, not success.

**Lesson:** decide what "better" means, and how you'll catch yourself gaming it, before you start making things
better.

**At your plant:** the equivalent of the sealed sets is a few areas of the site nobody tunes on. If the tool gets
better on the pilot unit but not on a unit drafted by a different contractor in a different decade, it learned the
pilot, not the job.

---

## 11. Round 2: let code do the geometry, then judge it on drawings nobody tuned on

**What:**
- Three methods built in parallel: tiling, a computer-vision line tracer, and a converter that turns extracted sheets
  into a twin starter kit.
- All judged on review load, the corrections a reviewer must make per 100 drawing items.
- Scored on two sealed sets: same-style drawings and a different drafting style.

**How:**
- **Rules first.** The goal, the score, the splits and the decision rule were committed before any method existed.
  The final method list and the decision rule were committed again before any holdout run (`docs/GOAL.md`).
- **Tiling:** each sheet is cut into four overlapping tiles, so models see small symbols at full size. The tiles are
  stitched back with seam-aware de-duplication. The grid was chosen by running the stitching on the answer key
  itself (a perfect model still loses ~10% of links at 2×2 seams), not by sweeping grids against the score.
- **Line tracing:** an AI model finds the symbols. Code erases them from the image, joins the remaining ink into
  line networks, blocks undetected valves from passing a connection through, and links assets that share a network.
  No AI, about 0.3–30 seconds per sheet (mean 13; `out/costs.md`).
- **The converter** builds the hierarchy, Ignition tags, PI AF rows, per-sheet SVGs at the extracted positions, and a
  review queue with the least certain items first.

**Results (holdout A, the same style; holdout B, a different style; lower is better):**
- **Tiling + tracing (M3) won for every model on holdout A, and held on holdout B.**
- **Codex:** 48.8 → **17.8** on holdout A, and 67.0 → 20.7 on holdout B.
- **Claude:** 61.1 → 32.4 on A, and 76.6 → 16.5 on B.
- **Gemini:** 75.9 → 40.2 on A, and 92.7 → 38.3 on B.
- Full table, including every loss: `GOAL.md` → Results.

**Why it worked:** connections are two-thirds of the work and the models' weakest skill, but lines are geometry.
Giving the geometry to deterministic code and keeping AI for "what is this symbol and what does its tag say" plays
to each side's strength.

**What didn't go to plan, kept on the record:**
- **Tiling made Claude worse on the six development drawings and better on both holdouts.** Small development sets
  mislead; that's why the decision is made on the holdout.
- **On the different-style set,** plain tracing beat tiling + tracing for Codex. The pre-registered rule still picks
  M3, and the difference is reported.
- **The twin's parent assignment got slightly worse** on holdout A (90.9% → 87.0%), even as the connection score
  improved a lot. The tracer links every asset on a shared pipe network, which is what the score counts but not what
  "which equipment is this instrument on" needs. **A better score did not automatically mean a better twin.**
- **Two small engineering catches:**
  - Windows line endings silently changed a prompt file's bytes between branches. The wording was identical, but it
    broke "same prompt for every run". Caught by the hash in each run record, and fixed by pinning the files to LF.
  - The review-queue CSV needed a byte-order mark, or Excel garbles tags like "ESS–HTR–180".

**Lesson:** decide the rules before you look, measure on what you didn't tune on, and keep a second measure that
the first can't fool. The connection score improved by a lot. The twin measure caught where that improvement didn't
translate.

**At your plant:**
- **Split the work by what it is.** Reading symbols and text: AI. Following lines, checking tag syntax,
  cross-referencing the DCS: code. Deciding: people.
- **Judge any tool on areas of the site nobody tuned on,** and keep an outcome measure, such as "did the
  instrument land under the right equipment in the asset framework", next to whatever accuracy number a vendor
  quotes.

---

## 12. Round 3 setup: point people at the problems, fix what the better score broke, spend nothing new

**What:** two goals for round 3, set before any work:
1. **A confidence marker:** every symbol and link gets a risk rating and a green / amber / red tier, so reviewers
   spend their time where the problems are.
2. **A fix for the twin regression from round 2:** instrument parents chosen by following the drawn line, not by
   "shares a pipe network with".

**How (the process steps, in order):**
1. **Pre-register before building.** The success tests went into `GOAL.md` and were committed first:
   - **Errors caught early:** the share of all mistakes that land in the riskiest 20% of items. A random order
     catches 20%, and the model's own confidence ordering is the bar to beat.
   - **Green tier:** its precision, and how much work it removes.
   - **Calibration:** error rates must rise from green to amber to red.
   - **The parent fix wins only if it beats both earlier twins** on the sealed drawings (87.0% and 90.9%).
2. **No new spend.** The constraint was set by the project owner: "we have plenty of data." Every signal comes from
   runs that already exist: three models × whole-sheet and tiled passes × the traced lines. No new model calls of
   any kind in round 3.
3. **Independent signals instead of self-reported confidence.** Two of the three models report 0.9–1.0 confidence
   for nearly everything, which ranks nothing. Independent evidence is more honest. Do two different models agree on
   this symbol? Does the same model agree with itself across two passes? Is the symbol actually sitting on a drawn
   line? Is the tag well-formed or a placeholder?
4. **Parallel builders in isolated copies of the repo.** One builder per goal, each tuning on the six development
   drawings only. Results get verified, then each method is scored once on the sealed sets.
5. **Housekeeping done safely.** The round-2 workspaces linked to the shared dataset folder. Removing a workspace
   carelessly can follow such a link and delete the real data, so the links were removed first, the data was
   confirmed intact, and only then were the workspaces deleted.

**Why:**
- **Review time is the real cost.** Ranking items so people check the riskiest first turns "review everything" into
  "review what matters". That's the difference between a tool that saves a plant time and one that just moves the
  work.
- **The parent fix closes the loop on round 2.** A better primary score must not be allowed to quietly make the
  twin worse.

**Stated limitation (written before results):** a risk rating can only rank what the system *found*. It can't point
at a symbol the system missed entirely, so a person still scans each sheet for gaps, and the review queue says so.

**Lesson:** decide how you'll know the marker helps (errors caught per hour of review) before you build it, or
you'll end up admiring a colour scheme.

**At your plant:**
- **Set the review budget first.** For example: "a reviewer checks the riskiest 20% closely and batch-accepts the
  green items".
- **Then measure how many real errors that budget catches,** on units nobody tuned on.
- **Sample the green items from time to time** (spot-check a few percent), so the green tier keeps earning its
  trust.

---

## 13. Round 3 results: a review queue that points people at the problems, and a fix that only half-generalized

**What:** two round-3 results, scored once each on drawings nobody tuned on, with no new model spend.

**1. The confidence marker. Mostly a success, with one important failure.**
- **What it is:** every symbol and connection gets a risk score and a green / amber / red tier with a plain-language
  reason ("the other models didn't find this symbol here; no tag was read").
- **How the risk is judged:** by independent checks, not by asking the model how sure it is:
  - Do the other models agree?
  - Does the same model agree with itself across whole-sheet and tiled passes?
  - Is the symbol on a drawn line?
  - Is the tag well-formed?
  
  A small formula, fit only on the six development drawings, weighs the checks. Each check can only raise risk.
- **Result:**
  - Across 24 holdout comparisons (4 methods × 3 models × 2 holdouts), the riskiest 20% of items held two to four
    times as many errors as ranking by the model's own confidence, in 23 of them.
  - Green items were 94–100% right and made up roughly half to three-quarters of everything.
  - Error rates climb from green to amber to red everywhere.
- **The failure:** the best model with the best method (Codex, tiling + tracing) on the same-style holdout. There
  the rating caught 40% of errors in the riskiest 20%, against 43% for Codex's own confidence. The tiers were still
  calibrated, but the ordering added nothing.
- **Why:** the strongest signal is "the other models didn't find it", and the best model is often right where the
  others miss. Agreement is evidence, not proof, and it punishes the model that's right alone.

**2. The twin's parent fix. Fixed for this drafting style, not in general.**
- **What changed:** each instrument's parent is now chosen by following the drawn line.
- **Same-style holdout:** 92.2% right, against 87.0% (round 2) and 90.9% (round 1).
- **Different-style holdout:** 67.6%, against 70.8% for the round-2 rule.
- **What the review queue does with it:** where the two rules agree, accept; where they disagree, flag for review.

**Why it matters:** review time is the cost. The twin's queue now reads: 377 red items to look at closely, 676
amber to check quickly, and 1,833 green to batch-accept with spot checks, out of 2,886 items across 12 sheets. Not
"review all 2,886".

**Lessons:**
- Honest uncertainty comes from cross-checks, not from a model's own score. Self-confidence ended up with zero
  weight.
- Pre-registering "must beat the model's own confidence on both holdouts" is what exposed the one failure that
  mattered. An average across all combinations would have hidden it.
- A fix that wins where you tuned it and slips on a new drawing style is a partial fix. Say so.

**At your plant:**
- **Before anyone batch-accepts the "green" pile,** measure its error rate on units nobody tuned on, and keep
  spot-checking it after go-live.
- **Ask what the tool's confidence is based on.** If the answer is "the model says it's sure", that's not enough.
- **Expect agreement-based checks to under-trust your best source.** A drawing reading that no other source
  confirms might be the one that's right. Route it to a person rather than rejecting it.

## 14. The Ignition build: the twin in a real gateway, judged by the gateway

**What:** the twin now runs inside an Ignition 8.3 gateway:
- the Tennessee Eastman plant, live from the open simulation data, with alarms;
- the extracted 12-sheet twin, honestly "not connected";
- one Perspective screen per drawing.

A verifier checks the running gateway against nine checks drawn from how Ignition itself judges data. Before its
results counted, it had to catch five faults planted on purpose. It caught all five, and all nine checks pass.
Details and receipts: [IGNITION_BUILD.md](IGNITION_BUILD.md).

**How:**
- **Everything is scripted against the gateway's REST API:** backup first, then an OPC connection to a small replay
  server, a separate `Twin` tag provider, one tag import, and the screens.
- **The verifier never reads our own files alone.** It exports the configuration back from the gateway, and it reads
  live values the way any outside system would: through the gateway's encrypted OPC UA server.
- **Quality as truth:**
  - The 36 tags fed by the replay must read Good.
  - The one instrument with no data in the replay (agitator speed) and the 359 placeholders must not.
  - A "Good" on a tag with no source is the worst failure a twin can have: it looks fine and is invented.
- **Alarms proven, not assumed:** the verifier switches the replay to fault 6 (loss of A feed) and watches the
  reactor pressure alarm go active, using setpoints from published sources only.

**Why:** the extraction work produced files. A digital twin is the running system. "The import said success" and
"the gateway holds what we meant" turned out to be different statements, several times.

**What went wrong, and what each mistake taught:**
- **Twice, "accepted" was not "working".**
  - The gateway saved a connection with a missing settings block (HTTP 200), which then failed at runtime.
  - An alarm expression read fine but was evaluated only once at startup: it would never have turned true in a
    fault.

  Neither shows up until you check the running state.
- **I blamed the gateway, wrongly.** I briefly recorded "changing a tag's type breaks it" as an Ignition bug. A clean
  reproduction in a throwaway provider showed the real cause was my expression. The claim came out.
- **The verifier changed what it verifies.** Its "can this client write at all?" test wrote to a review field, and
  Ignition stores that write as configuration, so the next fidelity check failed. Fixed by writing a probe tag
  outside the twin.
- **A refused write proves nothing on its own.** The read-only check uses a write-capable account on purpose, and
  first proves that account *can* write somewhere. Otherwise "write refused" might only mean "this user has no
  rights".

**Lessons:**
- Verify the running system, not the deployment receipt.
- Every check needs a case it must fail on. The planted faults are what make the nine passes mean something.
- When the evidence contradicts your story, rewrite the story, including the parts you already wrote down.

**At your plant:**
- **Run the same checks on your own twin or SCADA build.**
  - Export the configuration back and diff it against what was approved (that's Management of Change evidence).
  - Make sure no tag without a live source can read Good.
  - Prove each critical alarm on a replayed event before go-live.
- **Keep the twin's tags in their own provider,** read-only at three layers (device, connection, tag). Give the build
  account its own security level, not an administrator role.
- **Approve OPC UA client certificates by fingerprint.** Don't accept them all.
- **Take a gateway backup before every import, and keep the config in version control.** Then "what changed and
  when" has an answer.
- **Treat engineering ranges and alarm setpoints as engineering data with a source.** Where none exists (spans
  here), label the value as assumed and send it to operations to confirm.

## 15. Counting the cost, and a loose-ends sweep

**What:**
- Every recorded cost and time figure is now in one place, [COSTS.md](COSTS.md), generated from the run records
  rather than typed in.
- A sweep fixed the gaps a newcomer or reviewer would hit: a missing data download, stale plan rows, two
  contradictions, undocumented settings, no test command, no CI.

**How:**
- `scripts/cost_report.py` reads every run record and writes `out/costs.md`. Its total ties to the Gemini spend
  ledger to the cent: $16.57 of the $25 cap.
- Two independent read-only reviews ran in parallel, one on costs and one on loose ends. Their findings were checked
  against the files before anything was changed.

**What the cost picture says:**
- **Machine cost is small.** Model calls cost cents per sheet, roughly $200–$600 per thousand sheets at API prices.
  Compute is about a day of unattended runtime per thousand sheets.
- **People are the cost.** The declared method still needs about 16–40 corrections per 100 items, and the minutes per
  correction were never measured here. COSTS.md shows how to size it, with the assumption labeled.
- **Two vendors' costs aren't known.** Claude and GPT ran on flat subscriptions. Claude's tool reports an
  API-equivalent figure ($36.37); GPT's reports nothing, so no figure is claimed for it.

**What was wrong:**
- **Token counts were never saved,** so past runs can't be re-priced at new rates. Every run records them from now on.
- **Two numbers in the docs didn't match the data:**
  - the line tracer's "2–18 seconds per sheet" (actually 0.3–30);
  - an unsourced "for weeks" in the README's first paragraph.

  Both are fixed.
- **The tutorial's Ignition step needed simulation files no script downloaded.** It worked only on the machine that
  built it. There is now a fetch script with pinned checksums.

**Lesson:** "every number traces to a file" has to include the cost numbers. A cost claim nobody can recompute is a
guess with a dollar sign.

**At your plant:**
- **Before a pilot, write down what you'll measure:** minutes per sheet by hand (the baseline) and minutes per
  correction for reviewers. Those two numbers decide the business case. Machine cost almost never does.
- **Ask any vendor for per-sheet cost and per-sheet time from their own logs,** split into machine and reviewer time.
  If they can't produce it, they haven't measured it.

## 16. Can someone else run it? Rebuilding the gateway by hand

**What:** a test of whether the Ignition result can be shared, not just shown:
1. I backed up the gateway, then deleted the twin's tag provider, its OPC connection and its project.
2. I rebuilt the twin through the web UI only (create a provider, create a connection, import a project), plus one
   tag import, using only files committed in the repo.
3. The verifier ran its full set against that gateway. All nine checks passed, including the fault-replay alarm.

The steps are now [IGNITION_QUICKSTART.md](IGNITION_QUICKSTART.md).

**Why:** "it works on my gateway with my scripts" isn't the same as "you can load it". The scripted build might
have been doing something the files alone don't carry.

**What it showed:**
- **The UI wizard fills in every connection setting the REST API made me copy by hand** (journal 14, lesson 1).
  Someone using the UI never meets that trap.
- **The 8.3 web UI imports projects but not tags.** Tags go in through the Designer or the REST API. The quickstart
  says which path was tested (REST) and which is standard but untested here (Designer).
- **Names are part of the interface.** The provider must be `Twin` and the connection `TE-Sim`, because the screens
  and alarm expressions refer to them. The quickstart says so up front.

**Lesson:** a deliverable is only shareable if someone else's path through it has been walked once, start to finish,
from the published files.

**At your plant:** when an integrator hands over a twin or SCADA project, rebuild it from the handover package on a
clean test gateway before go-live, and run your acceptance checks there. Anything that only works on their machine
shows up then, not during commissioning.

## 17. Closing the loop: operations corrections and real data points flow back into the twin

**What:** the two missing halves of "a twin operations can use":
- the review comes back;
- the instruments get real data addresses.

`scripts/apply_review.py` reads a filled-in review sheet. `scripts/map_points.py` reads a plant I/O list. Both
update the asset model, both write a change record, and regenerating carries the result into Ignition, PI AF and the
screens. Details: [REVIEW_LOOP.md](REVIEW_LOOP.md).

**How:**
- **The review sheet is the interface operations already use:** a spreadsheet with confirm / correct / reject, show
  on screen, and alarm priority.
- **Every row is checked before anything changes.** Unknown items, unknown fields and corrections with no value are
  refused and listed, so a bad sheet can't half-apply.
- **The sheet round-trips.** It comes back pre-filled with earlier decisions, and re-applying it changes nothing.
- **Mapping matches tags after normalizing spelling, and never guesses.** It reports four worklists: mapped; on the
  drawing but not in the I/O list; in the I/O list but not on the drawing (is the drawing out of date?); and
  ambiguous.
- **The demo uses a synthetic I/O list, labeled as such.** It maps 24 instruments on sheet 0 and finds 2 points not
  on the drawing. It also hits one real ambiguity: the drawing shows `FT 1401` on two symbols.
- **In Ignition, 24 tags read live and 335 stay honestly Bad.** The verifier checks both, and that each tag's
  `ReviewStatus` matches the model's decision.

**Why:** the alarm rule is the design decision worth noting. A reviewer may set the priority of an alarm that has a
published setpoint. Removing an alarm, or adding one without a setpoint, changes what alarms the plant has. Those
requests are recorded for a change review and not applied. A spreadsheet should never be able to silently delete a
safety alarm.

**What went wrong:**
- **My first "keep corrections" rule broke the round trip.** Re-applying a regenerated sheet was refused for asking
  for a correction value it didn't need. The test caught it.
- **The first format check measured the wrong thing:** it counted every line after an insertion as changed. Also
  caught by the test, which was then fixed to compare a real diff.

**Lesson:** the review loop is a data pipeline with a person in it. It needs the same guards as any import: refuse
bad rows, apply the same input once, and leave a record.

**At your plant:**
- **Treat the review sheet and the I/O list as controlled inputs,** with a named reviewer and a dated record.
- **Read "in the I/O list but not on the drawing" as a drawing-update worklist.** In a 40-year archive it will not
  be empty.
- **Keep alarm creation and removal on the change-review path,** whatever tool proposes them.

## 18. Old scans: where the method breaks, and which part breaks

**What:** round 4. A pre-registered test of the declared method on holdout-A drawings degraded to three scan
qualities: photocopy, old scan, bad scan. The degradation keeps geometry fixed, so the original answer keys still
apply. The levels were set by eye before any model saw them. GPT and Claude only; Gemini was left out to keep spend
flat.

**Result:**
- **Photocopy quality: no consistent change.**
- **Old scan: review load about 3×** (GPT 17.8 → 51.5).
- **Bad scan: about 4×** (72.6).
- **The models' symbol reading degraded gently; the code line tracer collapsed.** At the worst level, connections
  fell to about 0.2, below the models' own untraced links.
- **The models aren't the main cause.** Feeding the same degraded-image symbols to the tracer on the clean image
  brings connections back to 0.53–0.63.

**Why it matters:** this is the "40-year archive" question with a number on it. The part of the pipeline that looked
strongest on clean drawings, deterministic code, is the most brittle on old paper. A lesson about tuning, not about
AI.

**What I didn't do:** tune anything. An image clean-up step, or a rule to skip tracing on poor sheets, is a new
method and would need its own sealed test.

**Lesson:** test the conditions you'll actually deploy into before claiming a number. Decompose the failure so the
fix goes to the right part.

**At your plant:**
- **Sort the archive by scan quality first.** Clean CAD exports and good scans can use the full pipeline.
- **For poor scans, budget 3–4× the review time,** or add an image clean-up step and prove it on your own sheets.
- **Rescanning the worst sheets may be cheaper than reviewing them.**

## 19. Making it shareable: one command, a 30-second demo, and two bugs only the verifier saw

**What:**
- `scripts/demo.py` goes from a clone to a live, verified twin in one command (given a gateway's settings).
- A 30-second animation for the README (`docs/demo.gif`), made from the repo's own screens: the drawing and the
  extraction, then the mapped sheet in Ignition, then the Tennessee Eastman plant through a fault until the alarm
  turns red.
- A before/after image of a real drawing with every extracted symbol coloured by review risk.

**Two bugs the verifier found that nothing else would have:**
- **Rebuilds weren't reproducible.** The project zip stored the time each file was written, so every rebuild looked
  like a configuration change. V9 (the gateway config matches a commit) failed on a build where nothing had changed.
  Now the timestamps are fixed and builds are byte-identical.
- **A fresh build once lost data silently.** One build in about eight imported "1,093 of 1,093" into a provider still
  starting up, and the tag overrides (ranges, units, alarms) never landed. V1 found 113 differences. The build now
  reads its import back with V1's own comparison, re-imports once if needed, and fails loudly otherwise.

**Lesson:** a check that runs every time beats a fix you can't reproduce. The rare failure is the one that reaches
production.

**At your plant:** make the acceptance checks part of every deployment, not just the first one, and keep their
receipts. Intermittent "it imported fine" failures only show up when something checks every time.

## 20. A one-click demo, built and tested without being able to run Docker

**What:** an optional way to run the twin with no setup. Install Docker Desktop, double-click `start-demo.bat`, and
the plant screen opens in the browser. Three containers:
- the official Ignition image, restoring a prepared demo backup on first start;
- two small containers running the data servers, so nobody needs Python.

`fault-demo.bat` trips the alarm, and `stop-demo.bat` stops it. The guide is
[docker/README.md](../docker/README.md), written for someone who has never used a terminal.

**How, under a constraint:** Docker Desktop installed fine on the build machine, but its Linux layer needed a
restart. The machine was unattended and 600 miles from its owner, so a restart was not an option. Instead:
- **The demo backup came from a second, throwaway Ignition** run natively on the same machine, built with
  `build_gateway.py --demo-backup`. Its temporary API key and permission level were deleted before the backup was
  downloaded through the web UI. `prepare_demo_backup.py` then set a neutral gateway name, because the download
  carried the machine's hostname. It refuses if any API key, extra user or personal string remains.
- **The whole demo is tested on GitHub's own machines,** which have Docker. A workflow starts it from nothing, opens
  the screens in a real browser, and checks three things:
  - 36 live values on the plant screen;
  - 24 live and 12 "not connected" on sheet 0;
  - the reactor pressure alarm turning red in the fault replay.

  **The record, and the bug it found.** Each change now starts three independent fresh copies, and the results are
  posted publicly.
  - The first 9 starts had 2 failures, both at the alarm step.
  - Once the check reported what the screen showed, the cause was clear. Switching to the fault recreated the replay
    container, so Ignition had to rebuild its OPC UA session: usually in about 25 seconds, once not within 2
    minutes.
  - **The fix is how a real plant behaves:** the data source changes mode without dropping the connection. The
    replay now switches live from a control file.
  - Every start since has passed, with the alarm at 26 seconds each time.
- **The Windows launchers were tested locally,** with a stand-in `docker` command and the throwaway gateway answering
  the "is Ignition up?" check.

**What testing caught:**
- **A demo that worked 7 times in 9.** "Usually works" isn't one click for a newcomer, and running it three times
  per change is what made the 2 failures visible.
- **The window title "P&ID" broke the start script for everyone.** In a batch file, `&` means "and then run".
- **A build setting was read before it was loaded,** so the first throwaway build still pointed at `localhost`.
- **I was about to document that restarting resets Ignition's 2-hour trial.** Earlier the same day, a restart had
  shown the opposite. The guide gives the real steps instead.

**Lesson:** "easy for anyone" is a claim like any other. It needs the same from-nothing test as the code: a check
that starts where a newcomer starts and looks at what they would see.

**At your plant:** for a pilot, give operations and reviewers the twin in a form they can start themselves on a test
machine, and keep it from a throwaway, credential-free build. The fastest way to collect operator feedback is to
remove the setup between them and the screen.

## 21. Screens an operator could use, and which model made which call

**What:** the first screens were correct and nearly useless: the drawing, with a number on every instrument, all
with the same weight. The new ones are a first pass at an operator display, generated from the twin in the ISA-101
style ([OPERATOR_SCREENS.md](OPERATOR_SCREENS.md)):
- a plant overview with one tile per unit, each with its key values, an analog indicator and a trend;
- a screen per unit, the alarm list, and the schematic;
- the 12 extracted drawings, now shown as the **original** drawings, greyed, with live values on top.

Grey means normal, amber means a value has left its normal band, and red is only for a real alarm.

**How, and the one inference that carries it:** an alarm says when it's too late; a band says "this isn't normal".
TE has no published operating envelopes, so `normal_bands.py` learns them from the normal run, the way the scorer
was built: rules first, then a test the rules never saw.
- **Fit:** mean ± K standard deviations on the first half of the normal run.
- **K chosen on the second half,** which the fit never saw. K = 6 is the smallest width with under 0.5% false flags
  on every tag. At K = 3, some value would be amber in 27% of normal samples, which operators learn to ignore.
- **Then the fault run, which chose nothing.** The A feed leaves its band in the same sample the fault starts; the
  pressure alarm comes **294 plant-minutes later**. Nothing was flagged in the 8 hours before the fault.
- **The gateway does the logic, not the screen:** each tag got `OutOfNormal` and `State` members, so anything reading
  the tags agrees with the colours. V8 now checks it: nothing flagged in normal running, the A feed flagged before
  the alarm, the pressure red at the alarm.

**Which model did what** ([MODELS.md](MODELS.md)), written down now, though it should have been from the start. Several models were compared only where it mattered most: reading the drawings. Everything else was
built by one model, Claude, through Claude Code. The judgement calls on these screens (which values represent each
unit, the display spans, the layout) are Claude's alone. They're labelled that way on every screen and are the first
thing an operator should change.

**What went wrong:**
- **The gateway ran out of memory, and it looked like a caching bug.** Images inside the views (5.2 MB) exhausted the
  trial gateway's 1 GB heap while it built each browser's copy of the project. Open screens kept their old views, and
  I first blamed the browser. The gateway log said `OutOfMemoryError`. Screen-resolution drawings and small thumbnails
  brought it to 2.4 MB.
- **Trends showed upsets that never happened.** Gaps in history (a stopped replay) drew as drops to zero. They now
  use raw points and skip bad quality.
- **A PowerShell edit corrupted the source,** turning "·" into "Â·" on screen: Windows PowerShell 5 read UTF-8 as the
  old Windows code page and wrote it back with a byte-order mark. Files are now edited with tools that keep UTF-8.

**Three overclaims, corrected:**
- **"Played the operations reviewer"** (corrected earlier the same day, commit 475c122). Nobody with TE process
  knowledge has reviewed the model, so the README now says the review is not done.
- **"The 3,000 kPa shutdown alarm never activates."** The data never goes above 3,000.0, so it seemed safe. On the new
  screens it went active at exactly 3,000.0: Ignition's above-setpoint alarm fired at equality. The claim had been
  inferred, never watched; the verifier stops looking seconds after the first alarm.
- **Authorship at that historical snapshot:** Claude wrote the initial code, while Codex supplied extraction
  results. Later revisions include OpenAI/Codex code and documentation work under Steve Vitale’s guidance.

**Lesson:** a claim about what a system does is a prediction until something has watched it happen. The screens
watched things the checks never looked at: a limit at equality, a gateway out of memory, a trend inventing upsets.
Walking the screens through a fault, as an operator would, belongs in the test plan next to the automated checks.

**At your plant:** generate the first screens, then spend the saved time with operators. Have them pick the key
values, and learn normal bands from your own historian, per operating mode. Count false flags on held-out data before
anyone sees the colour; a band that's amber every shift is worse than none.

## 22. Put the process on the overview, then make the unit pages earn the click

**Date:** 2026-10-10. **Status:** implemented and checked locally; native Ignition and browser validation remain
unrun. No deployment or successful remote push is claimed.

**What:** the three-unit mimic has become the six-unit **Overview**, with one consistent navigation bar and
more detailed unit graphics. A follow-on request for the maximum available instrumentation expanded the work:
all 52 recorded channels now have display/mapping entries, alongside the explicitly unconnected agitator.
The overview stays selective; the unit pages carry the full readings, trends, state and source context.

**The local sequence, checked against the available commit history:**
1. **October 8, `20aa7cd`:** the baseline carried the operator screens, normal bands and trend historian in the
   Docker demo backup. That is the starting point for the later local mimic work.
2. **October 10, `3b97ecb`:** the first read-only mimic covered the reactor, condenser and separator. Its alignment
   revision put readings into equipment-grouped rows, with each numeric value and engineering unit in one binding.
   Local tests and approximate SVG renders supported that checkpoint; neither established Ignition or browser
   runtime behavior.
3. **October 10, this revision:** the process picture moved into the normal application path, then the detail
   inventory expanded to every available replay channel. The current implementation and verification notes are in
   [PROCESS_MIMIC.md](PROCESS_MIMIC.md) and [INSTRUMENT_COVERAGE.md](INSTRUMENT_COVERAGE.md).

This checkout has shallow history. The first two items are inspectable commit checkpoints; the third records the
current local work rather than inventing additional published milestones.

**How:**
- **Show the whole process first.** The compact 1600 × 930 Overview contains feed U-100, reactor R-101,
  condenser E-101, separator V-101, compressor K-101 and stripper C-101, with all 13 seed-model stream directions.
  Its 21 headline readings are deliberate display choices pending operator review. The branches, recycle and
  external boundaries remain visible without putting every instrument on the first screen.
- **Give each destination one name.** Every shared header uses Overview, Feed, Reactor, Condenser, Separator,
  Compressor, Stripper, Alarms and Drawings in the same order. There is no extra Mimic tab; `/mimic` remains a
  compatibility alias to Overview. Equipment and neighboring-unit links support drilldown, while the full schematic
  remains a reference drawing. The tab order does not imply that this branched process is one serial train.
- **Make detail mean more process context.** Unit pages combine equipment-specific graphics, measured level where
  available, recorded-output gauges, and all tag rows with the existing state and history configuration. Boundary
  cards and connection stubs identify each modeled stream's source and destination and its currently mapped scalar
  readings. A boundary with no mapped instrument says so. Utility instruments are identified separately because
  the source model supplies no utility endpoints; the drawing does not invent piping to fill that gap.
- **Count channels before claiming complete coverage.** The seed has 37 model records, including three analyzer
  groups. The replay has 41 XMEAS channels and 11 XMV channels: 52 unique recorded columns. Sixteen analyzer
  components were previously undisplayed. They now have source-indexed sibling paths, completing the 19 analyzer
  components without changing the original scalar paths. The resulting 53 detail rows represent 52 mapped channels
  and SC-212 explicitly unconnected. New suffixes such as AI-123-B are project-assigned identifiers, not newly
  discovered physical instrument tags.
- **Keep timing with the measurement.** Feed and purge analyzers show their 6-minute sample periods and 6-minute
  dead times; product analyzers show 15 minutes for each. A replay row every 3 minutes does not make those readings
  instantaneous. Source index, component and review metadata travel with the added channels.
- **Preserve the existing meaning.** All 36 legacy normal bands are unchanged, including K = 6. Added components
  use that existing calibration rather than retuning it to flatter the expanded display. Existing alarm limits,
  read-only behavior and parent analyzer review exclusions remain in force. Normal bands are display aids, not
  site-approved operating limits.
- **Keep uncertainty visible.** Bad-quality, missing, nonnumeric and nonfinite readings remain unknown. Vessel
  fills become hatched and output gauges hide their fill. Zero remains zero, and an off-scale percentage keeps
  its number even when the graphic is clamped. Value and State quality are checked independently. History retains
  raw points and ignores bad quality, avoiding the false drops to zero found in entry 21.

**What needed correction along the way:**
- **A plausible feed label was assigned to the wrong unit in an early selection.** FI-104 sounds like it belongs
  with the other feeds, but the seed assigns it to stripper C-101 on S4. The final selection follows that ownership
  and keeps U-100's three actual feed readings together.
- **The expanded overview became too large.** The layout was reduced to a compact overview with 21 essential
  readings; the additional cooling, utility, analyzer and final-element detail belongs on the unit pages. Complete
  instrumentation coverage does not require every value to compete for attention on the first screen.
- **The first aggregate test run could not complete.** This environment lacked `asyncua` and `cv2`. Temporary PyPI
  installs of asyncua 2.1.0 and opencv-python-headless 5.0.0.93 supplied those dependencies, then the full runner
  passed. The repository's pinned requirements were not changed, and this was not an exact-lockfile reproduction.

**What the drawing still cannot prove:** it is a **replay-only, read-only** display. Static stream lines follow the
seed model; topology and equipment geometry remain **unverified pending operations review**. Recorded XMV outputs
are not measured valve-position feedback. XMV12 is absent from the replay, so SC-212 remains not connected and the
agitator stays static. Level percentages are measurements on a display scale, not calculated liquid volumes.

TI-122 remains a useful test of that discipline. The published source calls it **separator cooling-water outlet
temperature**; the seed retains its E-101 ownership while operations review is open (entry 5). The disagreement is
kept visible. A condenser graphic cannot turn it into a verified condenser process temperature.

**Evidence and limits:** this revision has its own local results, separate from the earlier prototype's receipts:
- **15 focused process-display tests passed** in the historical local run.
- **All seven aggregate test scripts passed, with no skips**, in that local run. These include source-channel coverage and compatibility checks.
- The gateway builder completed in **write-only** mode, and the proposed project export was checked for
  deterministic generation. The normal and fault replay fixtures passed their recorded SHA-256 checks.
- Normal, fault and bad-quality static renders were generated for the Overview and reactor detail. They are
  approximate offline SVG/PNG renders, not browser or gateway screenshots.

**Still unrun:** Ignition import, native Perspective/Jython execution, live OPC bindings, native historian
behavior, browser interaction/layout and operator acceptance. The earlier Chromium launch was blocked by the
environment's socket restrictions. Local configuration checks do not replace any of these stages, and previous
gateway receipts cover previous builds only. The preceding GitHub push attempt returned HTTP 403; no push retry,
deployment or public release was performed for this revision.

**Why:** the useful progression is from a complete data model, to readable measurements, to a process picture
that helps someone decide where to look next. The instrumentation request exposed an important distinction:
covering every model record had still left recorded analyzer components unused. A channel inventory caught that
without forcing all 52 values onto the overview or inventing measurements that do not exist.

**Lesson:** check completeness against the source channels, then choose visual detail for the decision each page
supports. Better-looking equipment can make a viewer assume more has been verified; improve the evidence labels
alongside the graphics. Local generation, automated checks, runtime observation and operations acceptance remain
separate milestones.

**At your plant:** agree on the overview-to-unit navigation with operators, then reconcile every available source
channel against the display inventory, including individual analyzer components and their timing. Keep unmapped
signals and uncertain ownership visible. Walk the whole path on an authorized development gateway with normal,
fault and bad-quality data, and have a process reviewer confirm the connections independently of the screen's
appearance.

**Preserving the handoff:** a historical shallow-checkout restore initially failed when it traversed
history before the baseline; retaining the known boundary allowed an exact restore. The lesson is to test
a restore, not just archive integrity. Those private handoff files are not included here.

## 23. Put measurements where operators look, then separate the plant-specific layout

**What:** operator feedback was that each unit page still spread readings away from the process. A complete table
was not enough to show what was measured and roughly where. All six unit pages now begin with a compact annotated
process diagram. Plain-language names and value plus engineering unit are primary; project tags are smaller.
Dashed leaders associate vessel pressure, temperature and level with approximate regions, stream measurements with
their mapped streams, and composition groups with their sample stream. The full inventory and history remain below.

The reactor was rendered and reviewed before applying the same visual grammar to the other units. Feed A/D/E stay
in order; reactor feed flow and A–F composition stay on S6; separator liquid readings remain on bottom S10; stripper
S10 enters above S4, with S5 overhead and S11 product below. All 52 available source channels remain accessible;
SC-212 has no replay source and stays explicitly unknown. Recorded valve outputs never become measured feedback.

**Evidence and limits:** this correction inspected pixels from the repository's generated overview and from
[Singhal & Seborg (2006), Figure 1, p.603](https://sites.me.ucsb.edu/~ceweb/faculty/seborg/pdfs/Singhal_JPC.pdf).
The latter is a published control-strategy schematic, not the original 1993 P&ID or proof of physical instrument taps.
It supports coarse regions and branch order. Exact tap and along-stream valve/instrument order remain approximate.
No source utilities, pumps or bypasses were added to the seed topology. Utilities without modeled endpoints appear
as nearby context, without invented pipes. TI-122 retains the source name “Separator Cooling Water Outlet Temp”
and disputed E-101 ownership. The published purge branch appears on the separator side of the compressor; the seed
still assigns S9 to K-101. That disagreement is visible rather than silently resolved by moving a measurement.

**What changed in the method:** this project should support different plant types, not accumulate TE-specific
screen logic. New labels, rectangles, routes, region anchors, uncertainty and source attribution live in additive
`data/te_display_layout.json`; the process facts remain in the original model. Shared unit rendering accepts a
layout parameter. The small display contract checks referenced units, streams and measurements, finite geometry,
association evidence and conflicts. Unknown direction draws no arrow; TE explicitly opts into its existing seed
from/to adapter, still unverified. Unknown equipment types receive a neutral symbol; unmapped values remain UNKNOWN.
A synthetic water-utility fixture exercises the same renderer with different IDs, topology and units. This checks
a presentation seam only: it does not establish broad industrial coverage or make the TE replay/export adapters generic.

**Lesson:** completeness, spatial readability and generalization are separate tests. Keep association evidence
separate from drawing coordinates, preserve unresolved data, and validate a second process through the same renderer
before calling a configuration seam reusable. Plant labels and layout are configuration; process topology, real data
mapping and operations acceptance remain site-specific work.

**Verification:** detailed local render receipts are not included in this publication. All six units have normal, fault and
bad-quality SVG/PNG renders. These are approximate offline renders, not browser screenshots or Perspective runtime
validation. No gateway import, live OPC operation, public action, spending or GitHub retry is part of this correction.

Local verification for this correction: **19 focused process-display tests passed**, **26 display-contract checks
passed**, and **all eight aggregate test scripts passed with no skips** using the previously documented temporary
dependencies. Repeated project generation produced the same ZIP hash. Independent pixel review covered all six
normal diagrams and representative bad-quality views; the final pass moved the stripper S10 caption clear of a
leader and gave unmapped-stream notes clearance from arrows and measurement cards. An overlap regression test protects the stripper overhead note. Native Ignition/Jython, live bindings, browser layout
and operations acceptance remain unrun. Private handoff artifacts are omitted from this publication; no remote push was claimed at that stage.

---

## 24. Try a separately labeled collection before claiming a general method

**What:** the next test should show someone adapting this code to their own drawings, and find what the first
workflow missed. We used an already labeled public collection, **PID2Graph Synthetic**, with the same existing
scorer and `twin-1` converter/exporters. It is a separate synthetic collection from OPEN100 and the Dataset-P&ID
holdout already used in round 2, but shares the PID2Graph distribution and ontology. It is not real-plant evidence.
No second model comparison was run: the selected first-round Codex `gpt-6.1-sol` model and original whole-sheet
prompt were retained.

**What the data actually contained:** archive inspection found 250 complete JPEG/GraphML pairs, correcting the
500-complete-drawings statement in entry 6. Development sheets 0 and 1 took 1,575,041 source bytes, or 12,201,709
range bytes including the archive index and block overhead. Reserved 2 and 3 were not downloaded or opened.
The JPEG format exposed an existing PNG-only assumption; the adapter now normalizes without resizing and records
source and converted hashes. The license is CC BY-SA 4.0, with attribution to the dataset authors and Steven
Baltakatei Sandoval's symbols. Source drawings and answer keys remain gitignored, with a bounded fetch manifest.

**First isolate the plumbing:** ground-truth labels were converted into the existing prediction format. This
oracle-label path passed all 43 scored assets and 65 collapsed links into a valid twin and draft SVG, Ignition,
PI and review files. Zero adapter-consistency corrections is expected; it is not an extraction accuracy claim.
Neither sampled key contains instrumentation labels. Tag text and flow direction are absent from the keys, so
all 43 oracle tags and all 65 directions remain unknown.

**Then run the selected model:** the subscribed Codex CLI could not initialize because its runtime filesystem was
read-only. A documented writable-runtime retry failed before inference as well. Those failure receipts were kept.
Two fresh native workers used the same selected model, exact prompt and images, with no ground-truth context.
This changed transport and wrapper instructions; reasoning settings are unverified/inherited. It is not a claim
of bit-for-bit reproduction of the old CLI execution.

| Development sheet | Located symbols | Source-class F1 | Connection TP / predicted / key | Review corrections / key items |
|---|---:|---:|---:|---:|
| 0 | 20 / 20 | 0.450 | 19 / 19 / 38 | 30 / 58 |
| 1 | 22 / 23 | 0.400 | 25 / 26 / 27 | 17 / 50 |
| Combined | 42 / 43 | 0.424 micro | 44 / 45 / 65 | 47 / 108 (43.52 per 100) |

**The useful failure:** 24 of those corrections are source-class disagreements, not independently proven physical
misinterpretations. Twenty are source `general` versus more specific model classes. The original prompt's equipment
definitions and the source's broad General category are not interchangeable. We kept both classes and the original
score, rather than learning a post-hoc remap from the answer key. The other corrections are one missed symbol,
21 missed links and one false link.

A second concrete gap is line semantics: the source has 221 solid and 29 non-solid edges, while the current
prediction/scoring contract collapses those into untyped adjacency. Every original edge style is now preserved
in a local sidecar; it is not silently interpreted as process versus signal flow. The generated model's structure
can be valid while its equipment roles, ownership, tags and directions remain unreviewed.

**What changed:** a small dataset config, bounded fetch/normalization adapter, source/hash checks, nine controls,
reproducible reports and `docs/ADAPT_LABELED_DATASET.md`. Structural validation runs before export. A separate
operational-readiness gate uses the existing review workflow and refuses `--require-reviewed` while ontology,
line semantics, operations decisions and site-specific live-data requirements remain unresolved. Default exports
are explicitly review drafts. No confidence calibration from OPEN100 is applied to this new domain.

**Lesson:** generalization begins with agreeing what a label means. Preserve the source vocabulary, model
interpretation and uncertain semantics independently. Freeze a domain-reviewed mapping and test it prospectively
on untouched data; do not rewrite the score after seeing the answer. These two development sheets identify gaps,
not broad performance. Nine adapter tests and the frozen scorer's controls pass; the review-required gate fails
closed without changing existing outputs. No gateway/PI import, deployment, public upload or API spending occurred.

---

### Documentation maintenance — 2026-10-10

The README animation caption now separates OPEN100 extraction with synthetic point mapping from the hand-built
TE process model/HMI with recorded fault replay. A third track identifies the two-development-sheet PID2Graph
Synthetic adaptation and its unresolved review gates. No new performance result or user decision is attributed.
The process-display verification summary now identifies the spatial and adaptation stages and distinguishes the
historical eight-script pass from the current rerun: 19 focused tests, 26 display-contract checks, nine separate
adapter tests and all eight aggregate scripts passed without skips using the unchanged repository dependency pins.
The initial rerun lacked cv2/asyncua because the earlier temporary dependency directory was absent; that failure
was preserved before restoring dependencies into a new temporary directory. Detailed command/output receipts are local and are not included in this publication. Runtime validation,
operations acceptance, and the prior GitHub HTTP 403 blocker remain unchanged. This is local documentation
maintenance only: no code behavior change, new extraction, generated image package, public action or push retry.

---

## 25. Flag a real review ambiguity without turning it into a confirmation

**Review outcome — 2026-10-10:** retain both FT 1401 symbols, flag the ambiguity for drawing-owner
clarification and block automatic signal assignment. This does not settle physical identity or count.

**Evidence:** the publisher's native 2604 × 1744 raster for PID 140-1-A contains two adjacent circles labeled
FT / 1401. The retained extraction has S0-IN002/s7 and S0-IN003/s8; the demo I/O CSV contains only one synthetic
FT-1401 row. Detailed local crop evidence is not included here. Raw extraction `runs/r2-tiles-trace/codex/0.json` is absent;
no extraction replay or vector-original verification is claimed.

**Applied effect:** a dry-run-checked, two-row OPS_notes-only review records the scoped outcome. Both symbols remain, both verification and review statuses remain `unverified`, and neither
has a data_point. No correction, merge, rejection, screen/alarm decision or MOC request was applied. The existing
review format has no clarification status enum, so no new engineering status was invented. An explicit leading
`NEEDS CLARIFICATION:` note is now echoed in the queue's `why_check_this` column when regenerated; original risk
scores, tiers and order remain intact. Only the queue was regenerated, with original newline style retained.

**Aftereffect and unknowns:** the current mapper dry run still reports FT-1401 row 26 as ambiguous between both
IDs; existing mapping output is byte-identical. Physical-device count/identity, tag correctness, parent/line
connectivity, line/signal semantics and real I/O address remain unresolved. Drawing-owner identity/contact,
clarification answer and resolution date are unknown. No external clarification was sent. Subsequent assignment
requires evidence and a separately authorized judgment identifying the target; this note is not such authority.

**Verification:** exact before/after records and full-file hashes, dry-run/application logs and a bounded CSV
are saved with the decision. Regression controls cover notes-only isolation, unverified/no-address retention,
visible queue flagging and idempotent round-trip. No gateway work, live mapping, public action, spending or push
retry occurred; the prior HTTP 403 blocker is unchanged. Local restoration was checked separately; those handoff artifacts are omitted here.
All eight aggregate test scripts passed with no skips using unchanged dependencies in
an isolated temporary environment; detailed local logs are not included. This does not establish runtime or operator acceptance.

---

## 26. Correct MS 14010 as text without approving the device interpretation

**Review outcome — 2026-10-10:** a field-scoped review corrected the MS 4010 identifier to MS 14010.
It did not approve function, classification or signal mapping.

**Applied effect:** S0-IN019/s39 now reads MS 14010. The existing review tool gained an optional
`identifier_text` scope with regression controls. Its matching derived loop changes from 4010 to 14010;
the exact mirrored description and hierarchy display cache change with it. The scoped decision is recorded
per field and in history, while whole-record review and verification remain `unverified`. Source extraction
provenance keeps MS 4010. No function, class, parent, connection, I/O or confidence interpretation is approved
or recomputed. The FT 1401 pair, its clarification flags and unmapped state are unchanged.

**Verification and limits:** normal CSV review dry run and application, exact before/after paths and hashes,
focused regression tests and all eight aggregate scripts passed without skips. Local read-only SVG, queue,
PI AF and Ignition JSON exports were regenerated, retaining unverified status and placeholder addresses.
No gateway import, production deployment, mapping application, spending, external contact or public push
occurred. The existing HTTP 403 limitation is unchanged. A historical local restore check established recoverability, not publication or runtime/operator acceptance.

---

## 27. Review the MS 14010 callout as a valve without inventing a signal

**Review outcome — 2026-10-10:** a field-scoped review associated the existing MS 14010 callout
with an existing valve, without approving a measured variable or signal.

**Applied effect:** the existing S0-IN019/s39 callout is associated by a field-scoped review with the
existing S0-VL013/s38 valve. Both source symbols remain distinct; no valve is created or merged.
The unsupported `moisture` variable becomes `unknown`, its method records the missing source legend,
and its current role becomes `valve callout`. The reusable `valve_association` scope accepts only
`parent=<existing parent valve>;variable=unknown` and refuses reassignment, mapped records, semantic
expansion, or screen/alarm decisions. `reviewed_valve_association` is the reviewed callout reference;
`parent`, `parent_method` and connectivity remain the original inferences. Raw extraction class,
provenance, geometry, confidence, risk, and the existing valve record are unchanged. No MS expansion,
valve subtype, actuator/control function, or signal type is inferred.

**Boundaries:** MS 14010, loop 14010, earlier identifier review and FT 1401 clarification are preserved.
Whole-record verification and operations review remain unverified. The source instrumentation collection
and class are retained as drawing-symbol provenance, not a claim that the callout is a measured process
variable. Local Ignition output uses a metadata-only Callout_Valve type without PV/OPC parameters;
PI output uses a String metadata attribute with no PI Point reference. The queue calls it a valve callout.
Point mapping refuses callouts even when an I/O row pins an asset ID; assigning a signal needs separate
review. No current mapping output is changed, and no gateway import or deployment is performed.

**Verification:** scoped isolation, idempotence/queue round-trip, refusal controls, metadata-only exports
and tag/asset-ID mapping guards pass focused regression. The first aggregate attempt retained two missing
import failures (cv2/asyncua); unchanged dependency pins were then restored into a temporary directory.
The final aggregate receipt records all eight scripts passing without skips. This establishes local model
and export checks, not runtime/operator acceptance. Local restoration was checked separately. No external contact, spending,
public push, or retry of the existing HTTP 403 failure occurred.

---

## 28. Regenerate current gateway artifacts and prepare isolated runtime acceptance

**2026-10-10:** regenerated `PIDTwin.zip` and `twin_provider.json` locally from the reviewed
MS 14010 valve-callout model at `3205ce8ea203d5e6e36fa8174cd58d85d40bf07e`, using only the
supported `--write-only` path after auditing its return before gateway/account/access operations.
The export contains all 23 views and 1,082 tag/history/expression bindings, all resolving offline;
53 TE instances retain 52 recorded channels plus unavailable SC-212. The 910 OPEN100 instances
include a metadata-only MS 14010 callout, 24 existing synthetic mappings, and 334 placeholder PVs.
Both FT 1401 records remain unmapped and flagged for clarification in the source.

**Local verifier corrections:** V2 previously reconciled only the 37 unexpanded seed items and
misclassified 16 added analyzer channels as orphans. It now derives expectations from the channel
expansion and independently rejects invented callout PVs or OPC assignments. V3 derives unit
coverage from source rather than held instances, excludes only source-reviewed valve callouts
from PV completeness, and requires the explicit NOT CONNECTED plus spatial UNKNOWN indicators
for source-unavailable SC-212. Ordinary unmapped instruments still require their quality-bearing
bindings. An outdated display-code comment was corrected without changing generated output.

**Checks:** ten new offline regressions include deterministic write-only generation under blocked
Gateway/network entry points, resource/route/tag checks, field-review lineage and negative semantic/
quality controls. All nine aggregate scripts pass without skips using the unchanged pinned temporary
dependencies in an isolated temporary environment. JSON/ZIP shape checks are not an Ignition-native schema
validation. Synthetic quality objects and generated views are not runtime evidence.

**Handoff and blocker:** [current-source handoff](IGNITION_ACCEPTANCE.md) describes the browser
acceptance checklist. Detailed local receipts are not included in this publication.
Compose still restores the untouched historical `docker/twin-demo.gwbk`; that backup and old
screenshots/receipts do not validate these artifacts. Java 21/Chromium are available, but no container
engine or running gateway exists here; desktop is offline and no saved coding environment is
available. No gateway start/import, license acceptance, credential/account change, external contact,
spending, public push or retry of the existing HTTP 403 failure occurred. Runtime and operator
acceptance remain unestablished. Local restoration was checked separately.


---

## 29. Give readers a bounded replication path, with or without the author

**2026-10-11:** added `docs/REPLICATE_AT_YOUR_PLANT.md` as the plant-reader entrypoint, linked from
the README. The path starts with public-data file generation in a disposable checkout, distinguishes
the manual TE seed from OPEN100 extraction and the two-sheet Synthetic development exercise, then
lists required site inputs, adapter work, review/mapping precautions, target-system requirements,
acceptance evidence and stop conditions. Optional assistance is a possible bounded scope, not an
offer of availability, pricing or production approval.

**Inspection findings carried into the docs:** OPC mapping replaces prior mappings across non-rejected
instruments; `--sheets` only scopes missing-I/O reporting. Dry-run output is a report, not a full diff.
PI export retains placeholder point references, independent of OPC mappings. Both replay servers
bind all interfaces with anonymous lab endpoints. Generic file exports are drafts without a blanket
operational gate; full-suite current-artifact checks need cached TE replay data. New-site input,
ontology, signal semantics, type/range verification and local inference are not turnkey adapters.
Directly misleading onboarding statements were corrected in README, IGNITION_QUICKSTART, REVIEW_LOOP
and TWIN_OUTPUTS; historical evidence and earlier journal entries remain intact.

**Validation:** checked the 16 relative links in the new guide, all 10 fenced Python command script
paths and five source/example inputs. Seven argparse invocations were accepted using isolated AST
extraction of the scripts' parser definitions, without importing or executing their entry points.
The first validation harness missed the review parser's `datetime` dependency; adding that standard
library binding fixed the harness, and the rerun passed. `git diff --check` passed. This is command
and file inspection, not execution of the documented workflow or a fresh test-suite pass. This documentation/parser check itself ran no generator,
model call, dependency installation, gateway/PI import, replay server, security change or public action.
Existing generated outputs in the working checkout were not changed. The separately authorized
isolated reproduction below has a distinct scope.

**Independent file-only replication check:** a separate reviewer executed the guide's seed generation,
copied OPEN100 model generation, blank-review dry run and synthetic point-mapping dry run against
a fresh archive of `4566e87` in a temporary directory. Python 3.12.14 ran with `-I -S`, a stripped
environment and an audit hook denying socket/urllib requests. All four commands returned zero.
Seed generation wrote seven SVGs and its exports; copied-model generation wrote twelve sheet SVGs
and its exports. The blank review applied/refused zero decisions. The mapping preview reported
24 mapped, 12 sheet-0 model records without a proposed mapping, two points absent from the drawing and
one ambiguity. Working source models and the copied model after dry runs were hash-verified unchanged.
Detailed local logs are not included. This validates those
four file-only paths on that Python version, not extraction, full-suite tests, model services,
native import, runtime behavior or engineering acceptance.

**Evidence boundary:** inspected baseline `4566e87` is the offline-verified local gateway handoff.
Current native Ignition runtime/browser acceptance and PI import remain not run; operations acceptance
is also outstanding. Historical Docker backup/receipts do not validate the current artifacts. The
previous public push was blocked by HTTP 403, and no retry occurred. The guide is local documentation
until separately published; it does not establish production readiness or new extraction performance.

---

## 30. Harden the replication path before wider use

**2026-10-11:** local follow-on hardening from documentation baseline `c774b63` addresses the
three concrete replication hazards recorded in §29. Its earlier observations remain historical;
the contracts below supersede the replace-all mapper, post-write validation and implicit test prerequisites.
No engineering review decisions, signal identities, source model or committed gateway artifacts changed.

**Mapping:** partial updates now preserve omitted mappings. Destructive replacement requires
`--replace-all` and is restricted by `--sheets` when supplied; unresolved, ambiguous or blocked rows
refuse replacement. Unknown/rejected explicit asset IDs do not fall back to tags. Duplicate target
rows, missing address values and invalid/out-of-scope targets reject the complete transaction.
A sheet filter does not disambiguate globally duplicated tags. Dry-run writes nothing and includes
complete before/after mapping snapshots and added/changed/removed entries; `--json` exposes the same
report for machine inspection. Partial mode preserves prior mappings for unresolved rows and may still apply resolved rows while
reporting unmatched or ambiguous rows, so exit zero is not full row reconciliation. Address checks
establish nonempty fields, not valid OPC syntax, connectivity or signal identity. Units, types, scaling and real-world
signal correctness remain outside the mapper's validation.

**Export gate:** seed and extracted models are structurally checked and every export rendered in
memory before output directories, files or stale SVG cleanup are touched. Invalid structure or
unrenderable required fields raises an actionable error; the CLI returns nonzero without changing
existing exports. Unknown semantics are preserved. This is not an atomic multi-file filesystem
transaction: a later disk/permission error can still leave a partially written bundle, and structural
success does not establish native-schema compatibility or operational approval.

**Tests and CI:** `--source-only` explicitly runs nine stdlib/committed-fixture scripts and names its
four exclusions; it never claims a full-suite pass. Default/`--full` runs all thirteen registered
scripts and requires dependencies plus checksum-verified cached TE data. Missing prerequisites exit
2 before any test script; test failures exit 1. `--check-prerequisites` does not run tests. The runner
never installs, downloads or silently skips. The existing CI job now stages the two public TE fixtures
through the checksum-verifying fetcher before `--full`; triggers, actions and permissions are unchanged.
That workflow edit was inspected locally, not executed on hosted CI.

**Independent integration evidence (Python 3.12.14):**

- `python -S scripts/run_tests.py --source-only`: 9/9 scripts passed. Separately, a source-only temporary
  checkout without ignored TE data passed the same nine scripts; full preflight there correctly
  reported the missing cache instead of passing. Source-only is deliberately narrower evidence.
- `python scripts/run_tests.py --full --check-prerequisites`: initially exited 2 for missing `cv2` and
  `asyncua`; cached `d00_te.dat` and `d06_te.dat` hashes passed. No full-suite scripts ran in that attempt.
- A new disposable virtual environment was then created under the integration receipt directory.
  `python -m pip install --index-url https://pypi.org/simple -r requirements.txt` installed the repository's
  unchanged pins (`numpy==2.4.6`, `pillow==12.2.0`, `opencv-python-headless==5.0.0.93`, `asyncua==2.1.0`,
  `cryptography==49.0.0`) and resolver dependencies. Exact installed versions and the initial blocker
  were retained. This was explicit test-only setup, not a test runner side effect or global installation.
- Using that environment in a temporary copy of the final working source and existing verified TE
  cache, `python scripts/run_tests.py --full --check-prerequisites` exited 0, followed by
  `python scripts/run_tests.py --full`: **13/13 scripts passed, zero failures or skips**. All six changed
  implementation/regression scripts were byte-compared to the shared checkout afterward. The full
  run occurred on the copy so any normal-band regeneration did not touch shared outputs.
- A separate comparison generated seed and reviewed OPEN100 exports with both baseline `c774b63`
  and the candidate in temporary destinations: **all 25 files were byte-identical**. Existing review
  controls, new invalid-model no-write cases and current-artifact controls passed. FT 1401 remains two
  unverified, unmapped records with clarification notes; MS 14010 remains an unverified metadata-only
  valve callout, without PV/OPC parameters or PI Point references.
- `python -S scripts/map_points.py out/twin/r2-tiles-trace/codex/plant_model.json
  data/io_lists/open100_sheet0_demo.csv --sheets 0 --dry-run --json` produced a valid partial plan:
  24 mapped rows, two unmatched rows, one FT 1401 ambiguity and **zero mapping changes**. Neither FT
  record nor the valve callout gained a mapping. SHA-256 checks confirm the reviewed source model,
  current gateway ZIP/provider and existing untracked process-mimic patch were unchanged.
- `git diff --check` and checks of all 100 relative links in the four affected user-facing guides passed.
  Replication, review-loop, twin-output and README instructions now describe
  the new contracts, explicit setup and remaining gates. Test logs, package versions, baseline export
  hashes and protected-file hashes are retained in the separate integration receipt for the handoff.

**Limits:** no model calls, extraction rerun, gateway start/import, PI import, live process connection,
security change, public push or production action occurred. The only networked setup in this pass was
installation from official PyPI into the disposable test environment. Native runtime/browser, PI and
operations acceptance remain not run. The prior public HTTP 403 blocker was not retried. These results
establish local offline hardening and repeatability, not publication, new extraction performance or
plant readiness.

---

## 31. Add a bounded local drawing-intake path

**2026-10-11:** local follow-on from `55f5734` adds `scripts/import_site_drawing.py` for
one locally supplied PNG plus an **existing extraction JSON**, described by a
`site-drawing-intake-1` manifest. It does not read a PDF, obtain extraction, call a model,
trace lines, apply the trained confidence model, score a drawing or connect process data.
The detailed manifest and command recipe is in [Replicate at your plant](REPLICATE_AT_YOUR_PLANT.md#bounded-local-intake-one-png--an-existing-extraction).

**Contract:** input filenames need not match or be numeric. The manifest records drawing ID,
revision, original page and supplied producer claims; optional register fields remain supplied
claims. The importer accepts only the existing six symbol classes and supported normalized boxes,
rejects malformed/duplicate-key/non-finite JSON, duplicate or unsafe IDs, bad geometry/confidence,
unknown endpoints, duplicate undirected links and self-links. It refuses unsupported text that
could become a spreadsheet formula or invalid XML. Source fields it does not interpret remain
in the preserved original JSON; they are not silently promoted into engineering semantics.
PNG checks cover bounded dimensions/container structure/CRCs, **not compressed pixel decoding**,
readability or revision authority. This is a narrow input boundary, not a hostile-file security certification.

**Publication and evidence:** `--check-only` writes nothing and tests inputs only, not conversion or
rendering. A normal run requires a new output directory with an existing parent, stages beside it,
validates/renders before publishing, and refuses existing destinations. Concurrent writers to the
same destination are unsupported. The bundle retains original manifest/PNG/extraction bytes,
SHA-256 hashes and implementation hashes, a normalized run record, and bundle-relative model/source
references. It contains an unverified model, review CSV, SVG and draft Ignition/PI exports. Original
manifests may expose private paths; keep sources private and review the entire bundle before sharing.
All items remain unverified and unmapped. Supplied confidence and the inherited 0.75 highlighting
rule are explicitly uncalibrated; blocked operational-readiness metadata is descriptive, not an
interlock in other tools. Site ontology, tag/role/parent heuristics, signal identity, native import
and operational acceptance still require separate qualified review.

**Determinism fix discovered during review:** importing the converter no longer imports OpenCV/numpy
unless the along-line rule is requested. Three linked/owner distance ties now use stable symbol keys.
Independent review also found a forked instrument chain whose parent changed with Python's hash seed;
linked-parent adjacency traversal now has stable ordering. This preserves its first-found-branch
heuristic and existing method labels. Repeatable selection does not resolve engineering ambiguity
or establish a better parent assignment.

**Final independent evidence (Python 3.12.14):**

- `python -S scripts/test_site_drawing_intake.py`: **18/18 tests passed**, including original-source
  hashes, malformed input/no-publish controls, escaping/rejection, image structure, check-only,
  repeated-bundle byte equality, and distance-tie/forked-chain fixtures across multiple hash seeds.
- In an isolated copy using the existing disposable test environment and cached TE data:
  `python -S scripts/run_tests.py --source-only`: **10/10 scripts passed**;
  full prerequisite check passed, then `python scripts/run_tests.py --full`: **14/14 passed**,
  zero skips/failures. Source-only remains deliberately narrower. Tested implementation files were
  byte-compared with the shared checkout after the run.
- Additional independent checks rejected nested duplicate keys, malformed/multiple JSON documents,
  duplicate manifest keys and symlink/dangling-symlink destinations without publishing output.
  Accepted quotes/angle brackets/Unicode rendered parseable SVG, with no formula-prefixed CSV cells.
  A simulated final rename failure removed staging and published no destination.
- Converter comparison against `55f5734`: all nine full models were identical under hash seed 1
  for retained OPEN100 provenance reconstruction and both available Synthetic development sources
  (oracle/native), each under linked, nearest and along-line rules. Six linked/nearest comparisons
  were also identical under seed 2. Historical raw OPEN100 extraction runs were absent, so its
  reconstruction used retained symbols/links from the committed model rather than claiming a raw-run
  replay. No baseline parent changes were observed in these cases; the synthetic tie fixtures do
  intentionally replace previously hash-dependent choices with stable, still-unverified choices.
- SHA-256 checks confirm the reviewed OPEN100 model, current gateway ZIP/provider and pre-existing
  untracked process-mimic patch are unchanged. `git diff --check` and relative guide links passed.
  Receipts are retained separately from the repository for the private replication handoff.

**Limits:** no dependency installation, download, model/extraction run, gateway start/import,
security change, public push or production action occurred. Native Ignition runtime/browser,
PI import and operations acceptance remain **not run**. This is local intake/review plumbing and
regression evidence, not plant-readiness evidence or a new extraction/generalization result.

---

## 32. Connect the remaining local replication handoffs

**2026-10-11:** local follow-on from `1e0618b3` adds four bounded pieces, developed in
parallel and reviewed together. These close local workflow gaps; they do not establish
plant readiness or replace native target-system and human acceptance.

- **Single-PNG extraction handoff:** `site_extraction_workflow.py` prepares an arbitrary
  local PNG and drawing/revision/page identity, freezes the existing
  `synthetic-adaptation-whole-sheet-v1` recipe, and collects a matching preserved record
  into the local intake. The pinned original prompt, `gpt-6.1-sol`, whole-sheet input
  and linked-parent conversion are deliberately distinct from the M3 tiled/traced
  benchmark method. Prepare/check/collect make no model or network call. The separate
  `execute` path reuses the existing strict Codex adapter, requires independently
  authorized transmission, preserves failed/incomplete attempts, and never retries
  automatically. Native replay retains its transport/reasoning deviation; fixtures
  remain synthetic. No new extraction was executed. The job and importer now record
  the PI helper hash alongside their generator/converter provenance.
- **PI-only mapping:** `map_pi_points.py` accepts exact instrument IDs and supplied
  archive/point/type/UOM/reviewer evidence. It never derives PI identities from OPC
  mappings. Dry-run exposes complete before/after snapshots and changes; partial
  updates preserve other PI mappings, while explicit replacement removes omitted
  mappings. Invalid or blocked rows reject the plan without changing the model.
  Generation preserves legacy CSVs, adds a mapping reconciliation file, and adds an
  explicitly `UNVALIDATED` candidate CSV correcting only the known type-column header.
  The remaining native PI Builder column/row contract, type/UOM compatibility,
  actual import and read-back remain unverified. Reviewer fields are attestations,
  not authenticated approval.
- **Ignition acceptance preflight:** an offline read-only tool verifies the exact 51
  manifest-listed build inputs, three artifacts and bound browser contract. Candidate
  identity includes the manifest hash, so changed source provenance rejects old
  observations even when export bytes are unchanged. Required input paths cannot be
  omitted or substituted. Historical check/handoff drift is reported separately.
  Future sample validation distinguishes 52 recorded TE and 24 mapped OPEN100 Good
  paths from SC-212 Bad and 334 non-Good placeholders; unknown values and absent source
  timestamps remain unknown. The callout has no PV path. Local sample validation
  cannot authenticate capture provenance or promote any native stage to accepted.
- **Future review-effort protocol:** `review_effort.py` supplies a blank registration,
  strict local record validation and descriptive assignment/pair summaries. It keeps
  preparation/review/total labor, independent residual-critical-error audit evidence,
  failures, abstentions and missing observations distinct. It rejects altered protocol
  hashes and mixed synthetic/human labels. The protocol addresses eligible information,
  reviewer independence, counterbalancing and same-task learning contamination. It is
  an administration kit: no human trial, time-saving, quality-equivalence, ROI or
  operator-usability result is claimed.

The [replication guide](REPLICATE_AT_YOUR_PLANT.md), [extraction handoff](SITE_EXTRACTION_WORKFLOW.md),
[PI mapping guide](PI_MAPPING.md) and [review-effort protocol](REVIEW_EFFORT_PROTOCOL.md)
describe the commands, boundaries and remaining gates.

**Independent integration evidence (Python 3.12.14):**

- In a fresh source-only copy containing tracked and proposed files but no ignored TE
  or Synthetic raw cache, `python -S scripts/run_tests.py --source-only` passed
  **14/14 scripts**. A separate copy using the existing disposable environment and
  SHA-256-verified TE cache passed prerequisite checks and the full cached-data suite:
  **18/18 scripts**, zero failures or skips. No dependency installation or download
  occurred. All 68 Python source/test files were byte-compared to the final tested copy.
- Focused standard-library controls passed: **15 workflow**, **14 PI mapping**,
  **25 acceptance preflight**, **14 review-effort**, and **18 intake** tests. These
  include explicit fake-process execution failures/retries, malformed input/no-write,
  source/prompt drift, duplicate JSON keys, stale/missing candidate evidence,
  unavailable-quality handling and synthetic-versus-human labeling. Fake subprocess
  output in test logs is not evidence of a real model call.
- All **25 existing seed/reviewed OPEN100 export files** were byte-identical to the
  `1e0618b3` generator outputs. Only the two new extracted-model PI staging/reconciliation
  files were added in temporary destinations. The actual reviewed MS 14010 callout
  rejects PI assignment and retains a metadata-only `Callout_Valve` UDT with no PV,
  OPC parameters or PI reference. Both FT 1401 records remain separate, unverified,
  unmapped clarification items.
- Existing public Synthetic development sheet 0 and its retained native response
  replayed through prepare/collect without a model call. The resulting one-sheet
  bundle retained source/implementation hashes and native recipe deviation, with
  6 equipment, 1 instrument, 9 line items, 4 off-page connectors and 19 extracted
  links; all remain unverified/unmapped. This checks local plumbing only, not new
  extraction accuracy or generalization.
- Exact current artifact preflight passed **51 required inputs and 3 artifacts**.
  The older runner hash in the historical handoff correctly reports **DRIFT**;
  historical receipts were not rewritten. Upstream generation is outside that
  manifest's direct input scope. The unchanged artifacts need no regeneration for
  this code-only handoff. `--require-native` exits **3**, keeping every native stage
  **NOT RUN**. With TE cache absent, preflight exits **2** rather than downloading
  data or treating missing evidence as acceptance.
- Protected reviewed-model/current provider/project/pre-existing patch hashes are
  unchanged. Relative guide links and `git diff --check` passed. Final logs and hash
  receipts are retained with the separate private replication handoff.

**Limits:** no new model/extraction execution, dependency installation, download,
gateway start/import, PI import/read-back, process connection, security change,
participant contact, human trial, public push or production action occurred.
Native Ignition/browser acceptance, licensed PI acceptance and actual human-effort
or operator-usability outcomes remain **NOT RUN**. The previous public HTTP 403
blocker was not retried. Local tests and authenticated-looking supplied strings
cannot waive engineering, data-sharing, change-control or operational approvals.

## 33. Preserve engineering text at the export and review boundaries

The release-candidate checks exposed three bounded defects in supplied-model
exports and the operations review loop. This pass fixes those defects without
changing the engineering interpretation or using a live service:

- **SVG serialization:** use XML attribute quoting for model-derived string
  attributes, including the complete provenance-based group identifier. Seed tag
  and asset labels are escaped as text too. Quotes, ampersands and angle brackets
  remain the supplied engineering text after XML parsing; they cannot become new
  attributes or elements through string interpolation.
- **Review CSV text:** spreadsheet-active strings and control-containing cells are
  prefixed with an apostrophe at serialization. Leading apostrophes are encoded
  too, preserving distinct source spellings. This covers both review sheets and
  all their cells, including notes, identifiers and descriptive fields. The model
  is not rewritten. Unchanged encoded notes are recognized against the model on
  reapplication, preserving review history and literal text. Identifier spellings
  must identify exactly one record; ambiguous raw/encoded spellings are refused.
  Edited notes are taken as written, as explained in [the review guide](REVIEW_LOOP.md).
- **Mapped callouts:** a scoped valve-association correction refuses any existing
  OPC `data_point` or PI `pi_point` before model or history mutation. It neither
  silently discards the mapping nor creates a metadata-only callout that invalidates
  the retained PI mapping. Separate authorized mapping review is still required.

**Local regression evidence (Python 3.12.14):**

- Nine new standard-library boundary tests passed. XML parser assertions check
  preserved values and attribute sets; no supplied script was executed in a browser.
  CSV tests cover each column in both review formats, notes/history round trips,
  literal apostrophes and ambiguous identifiers. Mapping tests preserve the full
  model on refusal and verify that an existing PI mapping remains exportable.
- Existing review-loop controls passed **48/48**, generation validation **8/8**,
  and PI mapping **14/14**. The new boundary script is registered in both aggregate
  modes. An isolated tracked-source copy passed **15/15 source-only scripts**.
- The initial full-suite prerequisite check reported missing `cv2` and `asyncua`
  and ran no test scripts. A separately authorized temporary virtual environment
  then installed the exact repository requirements and resolver dependencies from
  official PyPI. With existing TE cache files verified against their recorded
  SHA-256 values, the isolated full cached-data suite passed **19/19 scripts**.
  No global packages or cached source data were changed or downloaded.
- Regenerating the existing seed and reviewed OPEN100 models into temporary
  directories produced **27/27 byte-identical export files** compared with the
  `b13d8e5` generator. The intentional CSV encoding changes affect supplied text
  requiring protection; these baseline files required none. Committed models,
  generated outputs and the pre-existing process-mimic patch were untouched.

**Limits:** these are offline serialization and regression checks, not a broader
security audit or native acceptance. No model API call, gateway operation, PI
import/read-back, process connection, credential change, publication or production
operation occurred. Native Ignition/browser, PI and human-effort acceptance remain
**NOT RUN**.

## 34. Prospective frozen Synthetic 2/3 transfer check

On 2026-10-11, a separately named trial consumed the two previously unopened
PID2Graph Synthetic sheets 2 and 3. Original freeze `75d6306` preceded image
acquisition. Effective freeze `00540b1` amended only the reasoning declaration
before inference: omit the override and record unverified/inherited reasoning.
Original protocol, config and acquisition evidence were preserved. The explicitly
selected gpt-6.1-sol, exact original prompt, whole-sheet method and scorer stayed
unchanged. There was no new model comparison, tuning, answer repair or retry.

Both first native outputs were sealed before parent-authorized unblinding at
17:48:50 UTC. The unchanged scorer ran once at 17:50:36 UTC. Result: **73 corrections
/ 158 key items = 46.20 per 100**, comprising 2 missed symbols, 17 source-class
relabels, 3 false links, 51 missed links and no false symbols. The model located
47/49 symbols; rough source-class F1 was 0.625. Connection precision/recall/F1 were
0.951/0.532/0.682 (58 correct / 61 predicted / 109 key links). Both attempts
succeeded; no malformed symbols were counted.

These are published-label disagreements, not independently verified engineering
errors. Fourteen relabels involve the source's heterogeneous `general` class.
The key contains no instrument or off-page positive examples. Original edge
styles remain in local annotation context, but the frozen adjacency score drops
solid/non-solid distinctions. Neither semantics nor operational interpretation
was corrected from these held-out results. Both sheets are now consumed;
prospective validation of a changed method needs new data.

Observed durations of 103/111 seconds are approximate parent-observed worker
intervals, not inference-only latency. Selection/timestamps are parent-recorded
evidence, not independently authenticated provider telemetry. Subscribed native
execution used no separately invoked paid API; actual token/compute cost was
unmetered and remains unknown, not free or $0. Backend revision, actual reasoning
level and worker tool traces
were not independently verified. Isolation was procedural. Public-model training
contamination cannot be excluded. These two synthetic sheets do not establish
real-plant accuracy, actual human-effort savings or operational readiness.

Local regression checks passed **15/15 source-only scripts**, **19/19 full
cached-data scripts**, and **18/18 separately invoked synthetic harness tests**.
No new dependency installation or TE download was needed. Development artifacts,
protected method bytes and the unrelated process-mimic patch were untouched.
No gateway/PI operation, operational export, public push, paid API request or
production action occurred. The previous publication blocker was not retried.

See [results and public-evidence limits](PID2GRAPH_RESERVED23_RESULTS.md) and
[summary metrics](../out/pid2graph_reserved23_summary.json). The sealed local evidence and trial-specific
protocol/configuration/harness are not included; this public checkout cannot reproduce the exact trial.

---

## 35. Test the packaged demo after the source checks pass

**What:** on 2026-10-12, fixed a missing Docker dependency exposed by clean-image
browser testing, then verified the repaired demo in three independent starts.

**How:** the published source passed all 20 offline test scripts, but its
[first Docker run](https://github.com/steve-vitale/pid-to-digital-twin/actions/runs/38194280260)
failed all three browser checks. The replay server called the new `te_channels`
helper, which was present in the checkout but absent from the image's `COPY` list.
The container logs reported `ModuleNotFoundError`.

Added a regression that reconstructs the Dockerfile's copied files in a temporary
directory, imports the real server modules in an isolated Python process, and
exercises the real 52-channel replay mapping. It failed before the fix and passed
after adding the missing `COPY`; SC-212 remains unavailable. No dependency stubs
or source-checkout fallback hide a missing packaged module.

At repair commit `36038390cfacb7e19cc1f714ef2b8adeb651a56c`, the
[offline CI run](https://github.com/steve-vitale/pid-to-digital-twin/actions/runs/38195512089)
passed **20/20 scripts**, and the
[Docker/browser run](https://github.com/steve-vitale/pid-to-digital-twin/actions/runs/38195512100)
passed **all three independent starts**. Each browser check reported 29 overview
numbers with zero bad-quality overlays; the fault-6 alarm check passed after
26 seconds.

**Why:** source-level tests could import a neighboring file that the shipped image
never contained. The repair keeps packaging and functional dependency checks
together without changing process semantics or weakening the browser check.

**Lesson:** exercise the files actually shipped, and retain a failing regression
before applying the fix. Passing offline tests and passing a clean-start demo
answer different questions.

**At your plant:** repeat acceptance against the exact deployment artifact and
record its identity. This Docker result covers the **historical packaged demo**
restored from `docker/twin-demo.gwbk`. Native Ignition/browser acceptance of the
**newly generated 23-view project** remains outstanding, as does licensed PI
import and read-back. The [current-source handoff](IGNITION_ACCEPTANCE.md)
keeps those gates separate; a working demo does not establish plant readiness.

## 36. Bring the reviewed work onto one branch and make the next step explicit

**2026-10-12:** the reviewed public branch (`e565c74`) and a later Docker-guide edit made on another checkout were
brought together on one working branch, without rewriting any published commit. No private conversation or
gateway backup was added.

**What a Windows run of the tests showed at that point:** a disposable copy of the reviewed source, using the
SHA-256-verified TE cache and the pinned package versions, regenerated 23 views and 23 routes. Source-only checks
passed 12/15 and the full suite 16/20. The failures were a filename that Windows doesn't allow, two tests that need
symlink rights Windows hadn't granted, and the packaging test's isolated Python process correctly refusing a
user-site package. None of the checks was weakened to make them pass; entry 38 fixes the portability problems.
This result didn't replace the Linux CI run (20/20) or the historical Docker starts (3/3).

**Direction kept:** the engineering judgement is the point of the project: instrument positions and connection
boundaries, realistic process placement, uncertainty linked to its source, and an overview whose unit screens add
useful detail. It stays an open-source method that readers can evaluate and adapt themselves. No further model
comparison is planned for the second dataset. A 3D walkthrough was considered and deferred until native acceptance
of the 2D screens was finished. Recorded TE replay and synthetic OPEN100 values establish neither responsive
physics nor plant readiness.

## 37. Take a cold-reader documentation review seriously

**2026-10-13:** a cold-reader review, done from GitHub alone with no access to the working machine, read the
replication docs at `e565c74` and asked whether a competent engineer could follow them from a fresh checkout. Two findings mattered most. The
quickstart warned about versions, but its import steps could still pair the committed historical project ZIP
with the current tag provider. And the full-suite instructions skipped the step that regenerates the project ZIP.
Neither was a claim that a check passed without evidence; both were places where a careful reader could still go
wrong.

Both are fixed in release v1.2.0: the quickstart now makes you pick one set of files before importing, and the
README's full-suite block lists every step in order. The other findings (a real-candidate recipe beside the offline
preflight, an own-dataset handoff contract, and a domain warning beside the batch advice in the twin outputs guide)
are still open.

**Lesson:** a warning at the top of a page doesn't help if the numbered steps below it contradict it. Readers follow
the steps.

## 38. Import the current project into a real gateway, and watch what the offline checks could not

**2026-10-12/13:** the 23-view project finally ran in Ignition. Steve authorized Docker and an isolated test
target, so the whole current source went into a **disposable Ignition 8.3.10 container** (trial, fresh volume,
port bound to localhost only, removed afterwards), fed by the replay image built from `docker/sim.Dockerfile`.
No real plant, controls or site gateway was involved. The first import found that every live reading on the
new screens was broken. Nothing offline had caught it.

**What the gateway showed first.** The import itself was clean: 1,118 tags with zero read-back differences, and
the 23 views exported back identical. V1 to V7 passed, and the gateway's own OPC UA server read 52 TE values and 24
mapped OPEN100 points Good. Yet the overview showed `null` in every reading, each under Perspective's red error
marker, and the vessels said ERROR ([screenshot](screenshots/native-before-fix-overview-transform-parse-error.png)).
Opening the marker gave the cause: *Error_Configuration: Parse Error in script transform*. Perspective stores a
script transform as the body of `def transform(self, value, quality, timestamp):` and compiles it as written. The
generators stored the body unindented. All **580 of 580** script transforms failed to parse.

The offline preview and tests had run the same code, but they indented it themselves before executing it. So
they tested a version of the code that Ignition never sees. The historical October 8 screens did not have this
problem because they used Ignition's built-in format transforms, not scripts. The scripts arrived with the
October 10 process mimic, which had never been imported.

**The fixes, each with a test that fails on the old code:**
- One choke point (`build_hmi.tag_binding`) now stores every script transform as an indented body. The offline
  harness compiles stored code exactly as Perspective does, so an unindented body now fails offline too. An
  artifact test parses all exported transforms under the Perspective signature. Run against the old export,
  580 of 580 fail.
- The drawing sheets and the schematic used a numeric format transform, which turns a value with no data into
  the literal text `null`. Unmapped placeholders now read **not connected**, in muted italics, and mapped points
  without Good data read **UNKNOWN**. The tag binding stays, so a placeholder that ever read Good would show its
  number and fail V4 instead of being hidden. The test covers all 334 placeholders.
- TI-109's band was invisible. Its real normal band, 120.28–120.52 °C, sat on an indicator stretched to its 175 °C
  shutdown limit, so the band took 0.4% of the width
  ([before](screenshots/native-before-fix-reactor-rows-TI-109-band.png), [after](screenshots/native-reactor-rows-bands-normal.png)).
  The indicator now draws an alarm limit only when it lies within 10 band half-widths. PI-107's limits still
  appear; TI-109's limit stays in the text column and in the State colour. This reverses an earlier Claude-only
  display choice, and operations should confirm it.

**Steve's October 8 question, answered.** He had asked why many tags registered as null and whether the normal
bands were right, since most looked like missing data. To see what he saw, the historical backup was restored into
a second disposable container. On those screens the agitator SC-212 read `null`
([screenshot](screenshots/historical-oct8-reactor-sc212-null.png)), and every unmapped drawing instrument read
`null`: **359** placeholders then, 12 on sheet 0 alone ([screenshot](screenshots/historical-oct8-sheet0-placeholders-null.png)).
None of these was a broken tag. Each one has no data source: SC-212's channel (XMV 12) is not in the published
replay, and the drawing instruments have no I/O mapping. Ignition reads them Bad, as it should, and the format
transform printed that as `null`. Today the count is **334**: 24 instruments have since been mapped to synthetic
demo points, and MS 14010 became a metadata-only callout with no PV. The census from the final run:

| Group | Count | Gateway quality | Shown on screen |
|---|---|---|---|
| TE recorded channels | 52 | Good | numbers |
| OPEN100 mapped (synthetic demo points) | 24 | Good | numbers |
| SC-212, no replay channel | 1 | Bad | NOT CONNECTED and UNKNOWN / no replay source |
| OPEN100 placeholders, no I/O mapping | 334 | Bad | not connected |
| False-good placeholders | 0 | | |

The bands are right where data exists. All 52 recorded channels have a band learned from the normal run, and
SC-212, with no data, has none. In normal replay the gateway flagged 0 of 52 values. Early in the fault, 16
values were outside their band before any alarm. At the alarm, 25 were outside their band, PI-107 among them,
and PI-107 was red. On the screen, though, only TI-109's band really looked missing, for the reason above. I
can't be sure that is what Steve saw on October 8. A freshly started demo also shows short trend history for its
first minutes.

**The final run.** Everything above was repeated from scratch on commit `485f000` (published as `34b4ef5`; see [commit identity](IGNITION_ACCEPTANCE.md#result)): a pristine archive, the same
write-only build (provider `f735cebe…` unchanged, project ZIP `1a6ce79c…`), and a fresh container. The receipt is
[`native-current-20261013.json`](../out/ignition/gateway/receipts/native-current-20261013.json). The tools are in
`scripts/ignition/acceptance/`.

| Check | Result | Evidence |
|---|---|---|
| Import fidelity (V1), both directions | PASS: 1,253 tag nodes and 23 views, 0 differences; exported views identical JSON | receipt `verifier.V1`, `exports` |
| Reconciliation (V2) | PASS: 53/53 TE, 910/910 OPEN100; MS 14010 metadata-only | receipt `V2` |
| Binding resolution (V3) | PASS: 1,082 bindings on 23 views | receipt `V3` |
| Quality honesty (V4) | PASS: 76 fed Good, SC-212 and 334 placeholders Bad, 0 false-good | receipt `V4`, `census.normal` |
| Liveness (V5), plausibility (V6) | PASS: 76 of 76 changed; 52 inside range | receipt `V5`, `V6` |
| Read-only (V7) | PASS: probe write accepted, two twin writes refused (BadUserAccessDenied) | receipt `V7` |
| Alarm pipeline (V8), recorded fault 6 | PASS: A feed flagged first; PI-107 active 0.5 s after crossing 2,895 kPa | receipt `V8` |
| Perspective transforms run | PASS after fix: 0 parse errors in the gateway log, 0 `null` on 23 routes | `native-overview-normal.png` |
| Direct load and reload of all 23 routes | PASS 23/23 | receipt `browser` |
| Every navigation target clicked | PASS 277/277; Back after each 277/277; Back/Forward chain 6/6; repeated clicks; 0 console errors | receipt `browser` |
| `/mimic` is the same overview | PASS: identical view; no second tab | contract, test |
| Desktop layout 1600 × 930 | PASS: unit pages scroll to their inventory and history rows | `native-reactor-rows-bands-normal.png`, `native-stripper-normal.png` |
| 390 px layout | **PARTIAL:** every route reachable by two-way scrolling and touch, but it is a fixed 1600 px control-room layout, not a phone layout | `native-overview-390px.png` |
| Quality transition: replay stopped | PASS: 52 TE values went Uncertain; screens read UNKNOWN with hatched vessels and "Outside band: unknown" | `native-overview-replay-disconnected.png` |
| Recovery | PASS: 52 Good again within about 14 s of restart | `native-overview-replay-recovered.png` |
| Fault replay on screen | PASS: amber values before the alarm, PI-107 red at the alarm, alarm table populated | `native-overview-fault-early.png`, `native-overview-fault-alarm.png`, `native-reactor-fault-alarm.png`, `native-alarms-fault.png` |
| MS 14010 callout | PASS: no value label, PV or OPC address; both FT 1401 records keep separate placeholders | receipt `exports`, `native-sheet0-not-connected.png` |

*(Note added with entry 47: the `native-*.png` screenshots named in this table were replaced by the entry 47 run of the corrected build. The originals from this run are in the repository history at commit `f5c270e`.)*

**What went wrong on the way, besides the product bugs.** My first scroll test said the unit pages could not
scroll, and I nearly "fixed" that. Git Bash had rewritten the route argument into a Windows path, so the browser
had opened a missing page. Re-run correctly, the pages already scroll; no change was made. The browser harness also
counted Perspective's own hidden page chrome ("by null") as a broken value at 390 px; it now reads only the view.
And a path-conversion bug in my scratch orchestration wrote one run's verifier credential to the wrong folder, so
the post-import stages were run again on the same fresh gateway. The import itself was not repeated.

**Also observed, not changed:**
- The header counts *tags* in alarm, so it read "Alarms: 1" while the table listed two active alarms on PI-107.
- With the replay stopped, "Alarms: 0" stays Good, because no alarm is active on uncertain data. The values
  around it all read UNKNOWN. Whether stale data should raise an alarm is an operations decision, not a screen edit.
- The gateway logged "Received event for missing view TE/Alarms" after navigating away from the alarm table. No
  visible effect was seen.
- Setup differs from a site in three ways: the API key was provisioned into the disposable gateway's config files,
  HTTP was used on localhost, and the verifier ran inside the container's network namespace so the OPC UA server
  could stay bound to localhost.

**Windows test portability, same pass.** On a plain Windows shell the suite failed 4 of 15 source-only scripts
and 5 of 20 full scripts. The fifth, not seen in the earlier desktop run, was a test reading a child process's
output as UTF-8 while Windows wrote its ANSI code page. The fixes: portable SVG filenames (identifiers keep their
XML escaping; distinct names, collision checks); symlink controls that skip only that sub-case, only on Windows
error 1314, with a printed SKIP that the runner counts; `-E -P` instead of `-I` for the packaging probe, plus an
assertion that the checkout is not on the path; and the UTF-8 request. After: Windows 15/15 and 20/20 with two
symlink sub-cases explicitly skipped (the runner withholds "suite passed"); a Linux Python 3.12 container 15/15
and 20/20 with no skips.

**Lesson:** an offline check that adjusts its input before testing it is checking a different system. The
gateway was the first thing that ran the generated code unmodified. It also showed that "honest" quality can
still read as broken: Bad was the right quality for those 334 instruments, and `null` was the wrong way to show it.

**At your plant:** import the exact candidate into a disposable development gateway before anyone reviews the
screens. Click every link, stop the data source, and watch what an operator would see. Keep "no data source" and
"broken" visibly different. None of this establishes operator usability, responsive physics, PI integration or
plant readiness. The screens were checked against recorded replay and synthetic points only.

---

## 39. Prototype: a 3D tour generated from the same contract as the screens (proof of concept)

**2026-10-12, built on a separate local branch and merged as a proof of concept on 2026-10-13 (entry 49); not
reviewed by operations.** Steve asked whether a Blender 3D tour of the process would help operations training. Native
acceptance still came first; this entry scopes the idea and records a small build that ran.

**What:** a generator that turns the TE seed model and the 2D display layout into a 3D scene, rendered headless in
Blender, with a camera that walks the units in flow order and tag markers coloured from the recorded fault-6
replay. Plan: [3D_TOUR_PLAN.md](3D_TOUR_PLAN.md).

**How:** `scripts/build_3d_scene.py` reads `data/te_process_model.json`, `data/te_display_layout.json`, the committed
normal bands and the published alarm setpoints. It validates the layout with the same contract check the 2D
renderer uses, derives a scene (`out/3d/te_scene.json`) and writes a self-contained Blender script. Blender 5.2.2 LTS,
the official portable ZIP with its checksum verified, rendered ten stills in about 20 seconds and a 361-frame
low-resolution walkthrough in about two minutes on a GTX 1060. The same scene exports to a GLB with each marker's tag
id in its node extras. `scripts/test_build_3d_scene.py` (40 checks at the time) runs the generated script against a
stub `bpy` and fails when a deliberate break marks every tag connected.

**What is data and what is Claude's:**
- From data: which units, streams and tags exist; tag ownership; the 26 stream/unit associations already reviewed
  for the 2D cards; the seed flow directions (then unverified; checked against the simulator source in entry
  42) and the flow order derived from them; every colour (replay samples 150, 200 and 258 against the existing
  bands and the 2895 kPa published limit); SC-212 not connected; TI-122's disputed owner.
- Claude only: every shape, size, height, nozzle, pipe route and marker height; the plan scale (2D seed pixels ×
  0.03 m); the camera stops and the choice of fault samples. These are placeholders, labelled as such in the scene
  data, on the ground plane and in a caption on every frame. Nothing was compared with another model or reviewed by
  an operator.

**Why:** the tempting version is a nice-looking model built by hand in Blender. It would drift from the screens on the
first correction, and it would look more certain than the drawing allows. Generating it from the screens' own
contract keeps one source of truth, and the drift checks fail before anything is drawn. A P&ID gives topology, not
geometry, so the honest scene is schematic: plausible shapes in the 2D arrangement, every dimension declared a
placeholder. The OPEN100 twin was not used then: its 1,881 links had unknown direction and its units are drawing
symbols (entry 48 later read direction from the drawings and gave OPEN100 its own structure-only tour).

**Recommendation recorded in the plan:** rendered video for training material now, because a fixed, captioned video
is hardest to mistake for an engineering model and needs no runtime or gateway change; an interactive viewer (from the
same GLB) once a site has verified geometry and instrument locations.

**Lesson:** a 3D view adds no process information; it adds credibility, which is the risk. Label the placeholders in
the artifact itself, not only in the documentation, and generate the scene from the same contract as everything else.

**At your plant:** the software is the cheap part. The cost is real geometry (a 3D design model, scan, plot plan or
walkdown), instrument locations from isometrics or the field, an operator-written tour script, and keeping it current
under management of change. Walk it down with an operator before anyone trains on it.

---

## 40. Check the 3D render procedurally, then make it an orientation tour (proof of concept)

**2026-10-12, same local branch; not reviewed by operations or a process-safety engineer.** Steve asked for three
things:
1. a way to verify the render procedurally against the Ignition/PI asset framework and the P&ID;
2. a version for orienting new operators, or existing operators on a new process;
3. emphasis on the highest-risk elements, tied to what public accident data shows.

**What:**
- `scripts/verify_3d_render.py`: four groups of checks.
  - Accuracy against the Ignition gateway import, the seed UDT export, the PI AF sheet and the Perspective
    bindings.
  - Topology derived from the 3D pipe ends, markers inside equipment, and the tour as a valid walk.
  - Trace of each tag to a P&ID drawing.
  - Legibility from Blender's own measurement of each still: projected label boxes, raycast occlusion and WCAG
    contrast from the rendered pixels.
- A narrated orientation tour: captions, an SRT and an offline synthetic voice.
- Emphasis, from data, on the unit carrying published shutdown limits (R-101) and on the unit where fault 6 shows first
  (U-100).
- One cited public incident per stop, from a prototype keyword match over a compiled corpus of public agency records
  (CSB, OSHA, EPA RMP; [HAZARD_CITATIONS_DESIGN.md](HAZARD_CITATIONS_DESIGN.md)).

**What the checks found in the first prototype** (reproduced with `--label-layout legacy` and measured by the same
code):
- 25 label overlaps, 166 labels under 20 px at 1080p (the smallest 4.6 px), 241 under 4.5:1 contrast, and 105
  labels or markers hidden by geometry.
- Two tag markers (FI-106, AI-123) were **inside** the reactor shell. A fixed offset from the riser pushed them in.
- Two pipes (S4, S11) ended 0.8 m off the stripper, because nozzles on a thin column were spread sideways.

The legibility numbers were visible by eye. The buried markers and floating pipe ends were not; they were found by
the occlusion raycast and by deriving each pipe's endpoints from geometry.

After the fixes, all 16 checks passed on all 10 stills. Every scene tag maps 1:1 to its Ignition path and PI AF
attribute; the 16 extra analyzer component channels in Ignition are explained.

**The E-101 / K-101 case, honestly:** Steve saw those two labels "overlapping". The strict overlap test did not flag
them: they sat 13 px apart on one baseline and read as one string. Looking at the crop, I added two checks:
- a crowding rule for plate-less labels closer than one line height;
- occlusion sampled over a grid of points on each label instead of its centre.

With those, the case is caught (crowded, 11 px text, contrast 2.9 and 3.2:1, a pipe hiding a third of K-101). The
rules were written after seeing the defect, so this shows they catch it now. It does not show they would have found
it first.

**P&ID trace, honestly:** 0 of 37 TE tags trace to a drawing, because the TE model was built from a paper. All 37
are declared seed and checked against `teprob.f`. The check also reads the extracted twin's drawing id and bbox, so
an extracted plant would report real coverage.

**How the fixes work:**
- **Labels per still.** A still shows only the labels it needs.
- **Fixed screen size.** Labels are scaled to a fixed on-screen size and sit on dark plates.
- **Greedy declutter.** Placement avoids other labels, every marker and the caption band. The rectangle code is
  shared with the verifier.
- **View choice.** Cameras are fitted to each unit's shape, markers and battery limits. The renderer takes the
  first of seven candidate views that hides the fewest markers, by raycast.
- Pillow re-read the same pixels and agreed with Blender's contrast to 0.00. OCR was not run; tesseract is not
  installed and was not added.

**What is data and what is Claude's:**
- **From data:** every number in the narration and captions (streams in and out, normal bands, published limits,
  first band exits and counts in the recorded fault-6 replay, values at the alarm sample), the emphasis, and the
  incident URLs exactly as recorded.
- **Claude only:**
  - the one-sentence role of each unit and the connecting prose;
  - the choice of 3-5 citations per equipment kind from the heuristic's shortlist, and their one-line summaries;
  - the label sizes, thresholds and candidate views.

  Every caption says the script is Claude's and not operator-reviewed. The video's audio track is titled as a
  synthetic voice.

**Voice:** Windows' built-in System.Speech (SAPI), offline, one WAV per segment, timed into the video. ffmpeg, which
was already installed, muxes it with soft subtitles. The narration runs about 640 seconds, longer than my word-count
estimate of 466 seconds; the timeline uses the measured WAV lengths.

**Why:**
- A 3D render adds credibility faster than it adds information, so it needs checks that do not depend on someone
  looking.
- An orientation tour is only safe if its numbers cannot drift from the screens. So the narration is generated from
  the same files as the screens and the Ignition and PI exports, and the verifier proves the 1:1 mapping.
- The hazard emphasis keeps the data-backed parts (limits, first warning) apart from the heuristic part (public
  incidents). The heuristic produced false positives: NTSB's Asiana 214 matched "tower".

**A wording slip, caught before the final render:** my first summaries or captions for seven incidents said more than
their records do: most stated CSB recommendations as findings ("dead legs in feed piping caused..."). The emphasis
label also said "HIGHEST CONSEQUENCE", which the data does not show; it now says "PUBLISHED SHUTDOWN LIMITS". All were
rewritten and the tour was re-rendered.

**Lesson:** a verifier written after seeing a defect needs to say so. Separately, the two most important defects
here (buried markers, pipes ending in air) were invisible in the stills and were caught only by checks that reason
about geometry.

**At your plant:** a tour script for real operators must be written or reviewed by an operator. The hazard emphasis
should come from the site's PHA/HAZOP. Public incidents can illustrate it; they cannot rank it. Run the verifier
whenever the twin, the Ignition tags or the PI AF model change, because the tour is only as right as the 1:1 mapping.

---

## 41. Review: clean up the 3D stills before rendering any more video (proof of concept)

**2026-10-12, same local branch; review stills only, not reviewed by operations.** Steve looked at the reactor still
from entry 40 and said "it kinda looks like we need quite a bit of cleanup and review". The full video render that
was running was stopped and its partial output deleted. The review became ten rules:
- focus per stop and 3-4 key tags;
- one pill label system;
- pipes coloured by service on two racks;
- recognizable equipment and an eye-height camera;
- a corner badge instead of per-frame disclaimers, and a two-line caption;
- natural, short narration;
- operating alarm vs shutdown limit kept apart;
- a reactor-apt citation.

A second round from Steve asked for:
- the process flow made visible;
- a "why each piece exists" card at each stop;
- essential-function animations later;
- a lockout/tagout version designed now.

**What was built:** the redesign in [3D_TOUR_PLAN.md](3D_TOUR_PLAN.md#review-redesign-2026-10-12). Only five stills
were rendered: overview, reactor stop, fault 6 at the high alarm, a flow legend, and a LOTO mockup. The verifier
gained three checks: no pill on the focus unit's silhouette, no all-caps runs, and the review's 18 px minimum. It
also now checks that inferred utilities and valve symbols map to contract final elements. All 17 checks passed on
the five stills; the first prototype's layout, measured the same way, failed 3.

**What I got wrong first, and fixed before reporting:**
- Overlay cards rendered pale grey. Swapping a plate's mesh dropped its material.
- The flow legend's plate came out too short. Blender does not re-evaluate hidden text, so the bounding box was stale.
- The ground grid showed as one big cross. The texture used object coordinates on a scaled plane.

None of these was caught by a check; they were seen by looking at the stills. The legibility checks then caught three
pills at 16.2 px (text with no descenders measures shorter). The pills were enlarged; the threshold was not loosened.

**Limits, honestly:**
- PI-107's 2,895 kPa g is the operating high alarm the Ignition screens use. 3,000 kPa g and TI-109's 175 °C are
  the simulator's published shutdown points, shown only on fault stills.
- TI-109 has no operating alarm, so at the normal reactor stop its pill shows no limit. That is my reading of "the
  shutdown limit only on the fault stop".

**Purpose cards:** at the time, paraphrased by Claude from the published TE description (Downs & Vogel 1993), with
the paper not in this repo. The text check in entry 43 found errors in them (the purge placed at the compressor,
the stripper overhead missing from the feed header); since the merge every card takes its purpose sentence from
`data/te_unit_purposes.json`, which cites the simulator lines it restates (entry 42).

**Reactor citation aptness:** the corpus has no gas-phase reactor incident. Kuraray (a reactor taken above its
pressure limit; the CSB asked for the limit to be made clear to operators) now leads. Bayer CropScience is kept,
phrased generally.

**Naming:** the incident corpus was compiled in a separate, private project. Nothing in this repository names it,
reads it at build time or depends on it; only public agency records were used, and the curated result is committed.

**LOTO:** a design section and a mockup still. Every isolation point is inferred from the seed model and marked `*`;
the numbers are list order, not an isolation sequence. The still says it is not a procedure, and points to OSHA 29
CFR 1910.147, the site's verified P&IDs and an authorized person.

**Lesson:** checks of legibility and accuracy do not catch "looks like scaffolding". A person looking at one still
found more than the 17 checks did. Keep both, and render a handful of stills for review before rendering minutes of
video.

**At your plant:** design reviews of training visuals belong with operators early, on stills, before anyone spends
render time or narration on them. A LOTO view built from a P&ID alone is a sketch; the isolation list comes from the
energy-control program.

---

## 42. Verify the TE topology against the simulator source

**What:** every unit, stream, flow direction and tag-to-unit assignment in the Tennessee Eastman model was checked
against the simulator code. Until now only tag names and units had been checked (entry 5); the topology was a
hand-built seed that every screen inherited. Result, over 56 elements (6 units, 13 streams, 37 tags): **51
confirmed, 4 corrected, 1 unresolvable.**

**How:**
- `scripts/verify_te_topology.py` reads `teprob.f`, the same open Downs & Vogel code entry 5 used, and pins its
  checksum. It does not use a hand-typed table of the answer. It reads the code itself:
  - the component balances (`YP(I+9)=FCM(I,8)-FCM(I,9)-FCM(I,10)-FCM(I,11)` is the separator: stream 8 in,
    9, 10 and 11 out) give each internal stream's source and destination;
  - the state mapping (`UCLS(I)=YY(I+9)`) and variable suffixes give which holdup is which unit;
  - each pressure-driven flow line (`DLP=PTS-760.0`, then `IF(DLP.LT.0.0)DLP=0.0`) gives a direction that cannot
    reverse, and valve-set flows are never negative;
  - the `XMEAS(n)=`, `XCMP(n)=XST(i,k)` and `VPOS(k)` lines give what each measurement and valve acts on;
  - the header comments give each internal stream's published number.
- The second source is the revised TE code by Bathelt, Ricker and Jelali (2015), `temexd_mod.c` from
  [N. L. Ricker's TE archive](https://depts.washington.edu/control/LARRY/TE/download.html) (paper:
  [IFAC-PapersOnLine 48(8), 309-314](https://doi.org/10.1016/j.ifacol.2015.08.199)). Its header documents the states,
  measurements and stream names in words. It cross-checks every holdup and stream number teprob.f gives (all agree).
  It also supplies the one fact teprob.f doesn't state: the numbers of the two streams with no instrument (5,
  stripper overhead; 7, reactor effluent). Without it, those streams are reported unresolvable.
- The model's own `type` field maps units to source roles; no unit ID is hard-coded. Corrections are written into
  the model with the old value kept under `previous`, the same way `verify_te_source.py` does it. The full table
  is [`out/te_topology_check.md`](../out/te_topology_check.md).

**What it found:**
- **Corrected: the purge.** The seed drew the purge (S9) leaving the compressor. In the code the purge flow is
  driven by separator pressure (`DLP=PTS-760.0`), carries separator vapour composition, and is subtracted from
  the separator balance, independently of the compressor. S9 now starts at V-101, and its three tags (FI-110,
  FV-206, AI-129 with its seven component channels) moved from K-101 to V-101. Entry 23 had already noticed the
  published schematic disagreed and left it flagged. The code settles it.
- **Resolved: TI-122 stays on the condenser.** The source header calls XMEAS 22 the *separator* cooling-water
  outlet temperature. But it is the outlet of the circuit whose flow is XMV 11 ("Condenser Cooling Water Flow") and
  whose inlet is disturbed by IDV 5 ("Condenser Cooling Water Inlet Temperature"). Its heat term
  `QUS=UAS*(TWS-TST(8))` exchanges heat with the reactor effluent, which is where the condenser sits. The revised
  code names it "Condenser cooling water outlet temperature". The "separator" label comes from where the code books
  the duty: in the separator's energy balance, because the simulator has no condenser vessel. The open question
  from entry 5 is closed and kept in the model as `resolved_question`.
- **Unresolvable: PI-116.** Both sources call XMEAS 16 "stripper pressure", but the code computes it from `PTV`,
  the feed-header pressure. The simulator has no separate stripper vapour space. The code and the names point at
  different units, so the script keeps it on C-101 and flags it. The screens say so.
- **Confirmed with caveats.** The condenser and compressor have no holdup in the simulator; their positions come
  from the heat term and the compressor curve. The split of streams 7 and 8 at those machines (S7/S7b, S8/S8b) is
  the published flowsheet's drawing: the code has one flow for each. Which segment FI-105 is on is therefore a
  model choice. The compressor recycle valve HV-205 spills flow back around the machine, and the code computes
  that only as a reduction of net flow, so no spill-back stream exists to assign it to. FI-119 "steam flow" is
  computed from the stripper heat duty.
- **Plain-language purposes.** `data/te_unit_purposes.json` did not exist on any branch. It now holds one
  sentence per unit. Each one restates cited simulator lines and carries line numbers against the pinned checksum.
  A test confirms every cited line still says what is quoted, so the purposes can't drift from the source unnoticed.
  The 3D tour draft's narration predates this and should take its purpose text from here.

**Downstream:** stream directions now live in the model (`direction: forward`), so the display's "seed direction"
adapter was removed. The screens now say "TOPOLOGY VERIFIED AGAINST SIMULATOR SOURCE" where they used to say
UNVERIFIED. They keep the caveats that are still true: tap positions and along-line order are not in the source.
The separator page gained the purge route, its two cards and the purge analyzer. The compressor page lost them.
SVGs, Ignition tags, the PI sheet, the review sheet and the 23-view project were regenerated. Ten TE tag paths
moved, so the native gateway acceptance from entry 38 covers the build before this change, not this one.

**Tests:** `scripts/test_te_topology.py` (20 checks, in the full suite). Two kinds of control matter most:
- **Wrong models must be rejected.** Reverse a stream, move a stream's endpoint, put the purge back on the
  compressor, move a reactor tag or valve to another unit, give an instrument the wrong stream. Each one is
  corrected or flagged.
- **The check must read the code.** Edit the simulator text and the conclusions must follow. Point the condenser
  heat term at another stream and E-101 and TI-122 lose their confirmation. Reverse the purge pressure difference
  and S9 becomes unresolvable. Move the purge into the header balance and S9 becomes unresolvable while the
  pressure driver still says separator. Change both and it is corrected to the header.

**Why a script that reads the code, not a careful read of the code:** a reviewer can rerun it and audit every
row. Each row names the code line that decided it. When the source is split, the script says so instead of
picking a side quietly.

**Lesson:** "verified" needs a scope. Entry 5 verified names and units, and the topology underneath stayed a
guess while every screen drew it. When two parts of one source disagree (a header label and the equation behind
it), the deciding rule has to be explicit and applied the same way everywhere. Here it is: the code's location
plus a majority of documented names; where they split, the element stays flagged. The same rule that confirms
TI-122 leaves PI-116 unresolved. It was written while looking at both cases, so it is not pre-registered.

**At your plant:** the equivalent of `teprob.f` is whatever system already computes the process: a simulator
model, the DCS configuration, or the historian's tag-to-unit hierarchy. Check the drawing-derived topology
against it mechanically, and keep the disagreements as a list for the process engineer. What still needs a person
here: PI-116's owner; whether the S7/S7b and S8/S8b splits and FI-105's segment match how a real plant would draw
them; and every tap position, size and pipe route, none of which any simulator records.

---

## 43. Check the PI files against what AVEVA publishes, and get ready for a first human review

**2026-10-13:** three gaps a reviewer would point at first. The PI AF files have never been in a PI system. The
3D tour's text has never been checked against a source. And no one with operations knowledge has looked at
anything. None of the three is closed. Each is now smaller, and what remains open is written down.

**PI without a licence.** The free route is gone. The PI Developers Club, which included a personal development
PI System and a 45-day free trial, was retired on January 1, 2026. What remains is partner agreements, paid Flex
test credits, or a university's academic licence ([PI_MAPPING.md](PI_MAPPING.md) lists the terms and sources;
nothing was signed up for). So the check stays offline, against what AVEVA itself publishes: three course
workbooks and an Apache-2.0 AF export in AVEVA's own SDK samples. The sheet headers are mostly in screenshots, so
they were read by OCR and checked by eye. The results, now in `data/pi_builder_reference.json` with a page for
each entry:
- `AttributeType` is the documented column. `AttributeValueType`, which the legacy staging CSV still writes, appears
  nowhere. The candidate CSV's one correction was right.
- `%`, `kW` and `m3/h` match the vendor export's abbreviations exactly. `degC` does not: the vendor writes `°C`.
  `kg/h`, `kPa g`, `kscmh` and `mol%` are not in the sample, which covers only 33 UOM classes. Most likely
  `kscmh` (a TE unit) and the gauge pressure need custom UOMs at a site.
- The TE sheet names six element templates it never defines. The extracted twin's attributes have no units at all,
  while the vendor workbook says "Always assign a unit of measurement!"
- The AF XML schema types `Type`, `DefaultUOM` and `ConfigString` as plain strings. Adding an AF XML export and
  validating it against the schema would not have caught any of the above.

`scripts/check_pi_export.py` reports those findings with their evidence and fails only on internal
inconsistencies. Its test plants each error class to show the check catches it.

**The 3D tour's text.** The purpose cards were checked against Ricker's revised simulator code and against open
papers that restate Downs and Vogel. That check found the same purge error as the TE topology work, which used
the original Fortran: the compressor card said the purge leaves at the compressor, and both codes draw it from the
separator. The cards now take their sentences from the verified TE file. The public-incident citations were read
against the CSB and OSHA pages. Seven needed a correction or a missing detail, and the six EPA RMP links did not
resolve to their records. The biggest: Tesoro Anacortes ruptured during a
maintenance stream switch, not "during a restart". The Williams Geismar link returned 404. And the Bayer summary said more than its
cited page does. The fixes wait as a patch for the clean merge ([drafts/3d-tour/REVIEW_NOTES.md](../drafts/3d-tour/REVIEW_NOTES.md)).
An OCR read-back of the five stills found one real legibility problem. In the tour's typeface, 1, I and l look
alike. Every tag ID the whole-frame read missed was one of those confusions: `Pl-107`, `Tl-109`, `E-10I`.

**The first human review.** [docs/review-kit/](review-kit/README.md) is a one-sitting kit with two tracks that
must not mix. Anyone can check that text matches the drawing, that boxes sit on symbols, and that labels can be
read. Only an operations person can say whether a line, an alarm limit, an isolation point or a hazard is right.
Track A findings go in as notes or identifier-text-only corrections, never as `confirm`, so the record cannot
later pass for an operations review. The timing log uses the review-effort protocol's fields, but one sitting is
a pilot, not the study.

**Follow-up, same day: fix the exporter, not just the report.** The PI files are now PI Builder sheet schema v2:
- `AttributeType` replaces `AttributeValueType`.
- `°C` replaces `degC`.
- The four units with no vendor evidence are written to `custom_uoms.csv` with a definition, never assumed. Gauge
  pressure and standard volume flow each get their own class with no conversion, because converting either needs a
  local reference: the atmosphere, or the standard conditions.
- The six TE element templates are defined at the top of the sheet.
- Attribute descriptions move to their own file. A full OCR pass over the workbooks found no attribute description
  header, so writing one would have been a guess.
- Placeholder rows are left unselected, so PI Builder won't publish them.

`IMPORT_STEPS.txt` gives the publish order. The offline check now passes the TE sheet with a single instruction
(create or map four units) and flags any selected placeholder as an error. It's still not import-tested; every
generated file says so.

**Lesson:** "we can't test it without a licence" was half true. The import can't be tested, but the vendor's own
published material settled the header question and found a unit spelling no test of ours could have flagged.

**At your plant:** run `check_pi_export.py`, then pull your own UOM classes out of PI Builder before mapping
anything. The vendor sample is a subset; your UOM database is the authority.

---

## 44. One plant, end to end: draw the TE model in the house style and read it back

**What:** 2026-10-13. The extraction (OPEN100) and the live twin (Tennessee Eastman) were on two different plants,
so "drawing → extraction → twin → live values" had never been shown on one plant. The plan called for extracting a
TE drawing in phase 3; it was never done. Now the verified TE model is drawn as three P&ID sheets in the house style
learned from OPEN100, read back by the frozen method, diffed against the model, exported, and matched to the replay
server's live points.

**How:**
- `scripts/draw_pid_from_model.py` renders the sheets (PNG and SVG) and emits answer keys in the PID2Graph schema
  from the same model, with each symbol's printed text and the model item it draws. What is drawn comes only from
  `data/te_process_model.json`; where it goes comes from a drafting layout (`data/te_pid_layout.json`). The generator
  refuses a layout that drops a model item, draws one twice, or names a tag the model doesn't have. Cooling water,
  steam and the compressor bypass are lines the model has no stream for, so the key marks them as drafting additions.
- The style is measured, not asserted: `scripts/style_fidelity.py` runs the same measurements on the 12 OPEN100
  sheets and the 3 generated ones. 32 of 36 generated values sit inside the OPEN100 range; the four outside are
  symbol counts and one ink figure, because the model holds no drains, vents or manual valves.
- The key is checked against the pixels: the code line tracer, given only the key's symbol boxes and the image,
  recovers exactly the key's links on all three sheets. The first version failed this on two sheets: an equipment
  box drawn to the centre of its outline let the wall's outer edge join three lines, and a bubble placed inside the
  reactor's box hid its leader. Both were drawing bugs, fixed in the generator, not in the tracer.
- Extraction: method M3 unchanged (2×2 tiles, prompt v2, tracer defaults), GPT and Claude, 5 runs each on the clean
  sheets and 3 each on the round-4 degraded copies (`degrade_scans.py --src`, same levels and seeds). No Gemini.
  84 sheet runs, no failed tile.
- Scoring: the frozen scorer for symbols and connections, plus the project's first tag-text score
  (`scripts/score_te_roundtrip.py`): matched by position, compared after dropping case and separators.
- `scripts/te_model_diff.py` lists what a reviewer would correct against the verified model; `scripts/te_live_check.py`
  matches the extracted tags to the replay server's points and reads them twice.
- Midway, the topology check (entry 42) moved the purge stream and its three tags from the compressor to the
  separator. Sheet 102 was regenerated with the purge leaving the separator, the 27 runs made on the old sheet 102
  were set aside by image checksum, and sheet 102 was re-run under every label. Sheets
  101 and 103 came out byte-identical, so their runs stood.

**What it found** (details in [EVALUATION.md §6](EVALUATION.md#6-one-plant-end-to-end-tennessee-eastman)):
- On clean sheets both models read every one of the 43 printed tags in every run. Review load 2.1 (GPT, all 5 runs)
  and 2.2 (Claude, 2.1–2.6), almost all of it the agitator motor reported as an extra symbol.
- Text fails before shapes. At the old-scan level GPT still found every symbol and line but read only 56% of tags
  exactly (FI as PI, LI as LE, FV as PV). At the bad-scan level GPT read 14% and Claude 49%.
- In one bad-scan run Claude rotated the three feed valve tags (FV 203 read as FV 201, FV 201 as FV 202, FV 202 as
  FV 203). Each is a real tag, so a tag-only diff passes it and the live check binds all three to moving points. Only
  the position-aware score catches it.
- For the declared chain (GPT, clean, run 1), the reviewer diff has 10 corrections. Feeding the key in as a perfect
  extraction leaves 9 of them, so they come from the converter and the model's conventions, not from the reading. The
  feed header drawn as an in-line mixer becomes a line item, so its six feed-line items get the reactor as owner. Two
  extra unit links come from lines that share pipe at the header and the bypass.
- 36 of the extracted twin's 37 tags resolve to replay points and all 36 moved; SC-212 has no recorded data.

**Why:**
- **Generate, don't look for a picture.** A drawing generated from the verified model in a learned house style is
  closer to what a plant would actually do than any diagram we could find: most sites have an instrument list long
  before they have trustworthy drawings, and generated sheets can be redrawn in each site's own style.
- **Call it a round trip.** The drawing and the key come from the same model, so the scores can't say how well this
  reads a real plant's sheets. They measure reading fidelity on clean house-style drawings: an upper bound. The
  tracer check and the generator's refusals keep the key honest about what is drawn, not about the plant.
- **Replicates, not a single run.** Five clean and three degraded runs per model show the spread. GPT's clean runs
  scored identically; Claude's degraded runs varied by several points.
- **The perfect-reader diff** separates the converter's errors from the models'. Without it, the feed-header ownership
  errors would have looked like reading errors.
- **Rejected:** fixing `build_twin.py` so a tagged in-line mixer becomes a unit. That would tune the converter to the
  one drawing we generated, and it would change the OPEN100 twin. The diff reports it instead. Also rejected:
  importing the extracted twin's tags into a gateway here, because the disposable gateway was in use by another
  workstream at the time.

**Lesson:** on clean drawings the reading is nearly solved and the remaining work is in the converter's rules and the
model's conventions. On poor images the dangerous error is a misread that is still a valid tag, and only checking
against position (a walkdown, a loop check) catches it. A live value that moves proves the binding exists, not that
it is right.

**At your plant:** if you have no usable drawings, generate them from your instrument index in your own house
style, label them "not a drawing of record", and walk them down under your management of change before anyone
relies on them. Use the generated sheets and their keys to measure your extraction method on your own style before
you trust it on your scans. And never accept an I/O binding because the value moves: loop-check it.

---

## 45. Start from the data: assess both datasets first, then make every correction travel

**What:** a written Stage 0 for each dataset (where the data came from, what is checked, what is inferred, how sure
we are per element class), a machine-readable list of every stage after it, and an orchestrator that shows which
outputs are stale after a correction and rebuilds them.

**How:**
- [DATA_LINEAGE.md](DATA_LINEAGE.md) lays out Tennessee Eastman and OPEN100 as staged pipelines: input, treatment,
  output, confidence carried forward, and who or what checked it. The numbers come from files already in the repo:
  37 TE tags checked against the simulator source (36 confirmed, 1 corrected), units and streams not yet checked on
  this branch, OPEN100 review load 17.8 per 100 on sealed drawings, and 2,886 twin items, all unverified.
- [`pipeline/stages.json`](../pipeline/stages.json) lists the 13 stages with their real scripts, inputs, outputs,
  prerequisites and the provenance fields each output carries. `scripts/pipeline.py` hashes each stage's inputs,
  code and config into a lock file when it builds the stage; `status` marks a stage stale when any of them changed;
  `rebuild --from <stage>` re-runs it and everything downstream; `confidence` rolls the per-element fields
  (source check, review status, risk tier, tag status) up per dataset.
- `scripts/provenance.py` reads one item's provenance from fields the models already carry. The seed exports now
  end each Ignition tag's documentation and each PI attribute's description with
  `source check: … | ops review: …`, the way the extracted twin's exports already did. Two new generators are
  labelled proof of concept in their own files: the overview mimic as layout data, and 3D scene data with
  inferred LOTO candidates.
- `scripts/test_pipeline.py` copies the repo to a temp folder, moves FI-110 from K-101 to V-101 with
  `apply_review.py` (one part of the purge correction the topology check makes), rebuilds from the model, and checks the move in
  the Ignition tags, the PI sheet, the review sheet, the mimic layout and the scene data. It also checks that no
  script changed and that a second rebuild writes identical bytes.

**What the test found:** the overview mimic picked its readings from a hard-coded list per unit. With FI-110 moved
in the model, the reading's tag path followed the model (`TE_Plant/V-101/FI-110`) but the reading was still drawn
beside the compressor. The topology branch had to edit that list by hand to move the purge. The fix is small: the
list still chooses *which* readings the overview shows, and the model decides *where* each one is drawn. With the
old placement put back, the propagation check fails on exactly that reading.

**Why:**
- **Changes at the start have to be cheap.** The review day will correct things in the models. If each correction
  also needs hand edits in four generators, corrections stop happening, or they happen in one output and not the
  others. A stale flag after the correction and one rebuild command make the cheap path the right one.
- **Confidence has to be visible before results are.** It is easy to read a polished screen as a validated one.
  Every output inherits its inputs' confidence, and the replay, the mimic, the 3D data and the LOTO candidates say
  "proof of concept" in their own files. They are there to iterate on.
- **Who checked matters as much as what was checked.** The rollup counts a review as an operations review only
  when the reviewer string names an operations role. A confirmation by anyone else, including me, keeps its label
  in every output. This trusts the string; nothing authenticates it.
- **Rejected:** a general workflow engine (more machinery than 13 stages need), timestamps instead of hashes (a
  checkout changes them; Windows and Linux line endings are normalised before hashing instead), and rewriting the
  generators to emit provenance (a one-line passthrough where a format has a free-text field was enough).

**What it does not do:**
- Two stages need the TE replay download (the normal bands and the gateway kit). They show `NEVER BUILT HERE` in
  this checkout: their committed outputs predate the lock, and I have not rebuilt them through the orchestrator.
- Extraction, scoring and the twin build are "recorded" stages. They need model calls or run records that are not
  committed, so the lock accepts their committed outputs as the record. It does not re-run them.
- "Fresh" means rebuilt from current inputs, not correct.

**Who did what:** Claude (Claude Code) wrote the manifest, the orchestrator, the tests, the docs and this entry
from my direction. No second model reviewed it, and I have not walked the lineage myself yet; that walk is the
review day ([review-kit/FOLLOW_THE_DATA.md](review-kit/FOLLOW_THE_DATA.md)). The source-only suite passed 16/16 on
Windows with two symlink sub-cases skipped by the platform. The full suite was not run in this checkout because the
TE replay files are not downloaded here.

**Lesson:** a pipeline that regenerates outputs from one model can still hide hand-kept copies of that model. Here
it was a per-unit list in a screen generator. The way to find them is to change one fact upstream and check every
output for it, rather than read the generators.

**At your plant:** write each source's Stage 0 before building anything: who owns it, what checks it, what is
inferred, and how sure you are per element class. Then make sure every correction goes into the source, not an
output, and that one command shows what a correction left stale. When a reviewer signs off, record their role with
the decision, so a document-control check never reads as an operations approval.

---

## 46. More drawings with tag text, five runs per model, and a kit for the first timed review

**2026-10-13.** Reviewers of the results could point at four gaps. Holdout A is six drawings. Tag reading had never
been scored, because the OPEN100 keys carry no text. Claude against GPT was called a tie or a win from single runs.
And review time, the number the cost case rests on, was never measured. This entry closes the first three as far
as public data allows, and prepares the fourth.

**Finding drawings with tag truth.** The PID2Graph paper's 60 industrial P&IDs aren't public. Dataset-P&ID has text
labels, but they are random strings, its licence forbids sharing adaptations, and its drawings are already holdout
B. The DEXPI standards initiative publishes example and training P&IDs with their DEXPI XML (CC BY 4.0, on GitLab
now; the old GitHub repositories point there). The XML carries every item's class, its drawn shape and position, its label
text and the piping topology, which is all an answer key needs. One example also ships a CAD tool's equipment,
instrument and valve lists for its two drawings. The selection rule took every complete DEXPI 1.3 example sheet
plus that one: three XML-keyed sheets (49 symbols, 60 links, 33 tags) and two list-keyed sheets (145 identifiers).

**The adapter, and what the oracle check caught.** `scripts/adapt_dexpi.py` places each shape-catalogue symbol by
its position, rotation, mirroring and scale, rasterises the published SVG or PDF, and writes keys in the PID2Graph
format so the frozen scorer reads them unchanged. Drawing the key boxes over each render and scoring the key against
itself found three problems before any model ran: a column section drawn inside its column counted as a second
tank; flanges and blinds, drawn as a single stroke, had zero-area boxes that can never match; and one instrument
label's third line (an area prefix) had joined its tag. All three were fixed and recorded in the pre-registration,
which was committed before the first model call (`bd7d7ff`).

**Replicates.** Five fresh runs of the declared method per model on holdout A and on the DEXPI sheets, Claude and
GPT only. Gemini wasn't run, on Steve's direction; its earlier numbers stay, labelled as earlier runs. 220 records,
no failures, and every record reports the same model IDs as round 2.

- **Holdout A:** GPT 20.1, Claude 29.8 review load. GPT is better by more than run noise on these six drawings (9.8
  points, interval 7.3–12.2), but resampling the drawings gives −4.5 to +26.5 for the gap, so across drawings like
  these it is a tie. The pre-registered rule made that call before the numbers existed, which is the only reason I
  trust it: the runs-only interval is the more flattering one, and I would have been tempted to lead with it.
- **Noise was underestimated.** Round 2 assumed "about 1 point" between runs, from one repeat on the development
  set. Five runs give a standard deviation of 1.4–1.9 points. Round 2's single runs were a lucky draw for GPT (17.8,
  below its five-run interval) and an unlucky one for Claude (32.4, above). The round-2 verdict, a ~30-point gain
  from tiling plus tracing, is far outside that and stands.

**DEXPI: worse, and partly for a reason the key decides.** Review load was 95.4 (GPT) and 61.8 (Claude), against
about 20–30 on holdout A. Much of it is what counts as a symbol. Equipment nozzles are drawn as little stubs with
labels (N1, N2), but DEXPI treats them as parts of the equipment, and the key followed DEXPI. GPT reported them as
symbols in three of five runs on the reference sheet and not in the other two; the tracer then attached lines to
each one. Its review load on that sheet swung between about 33 and 145. A single run would have shown either
number, and either would have been wrong as a summary. The small sheets also amplify: on a 21-item sheet each
correction is about 5 points.

**Tag text, finally measured.** On the reference sheet both models read all 20 tags exactly, including two-line
instrument bubbles. Across the three XML sheets: GPT 29 of 33, Claude 28 of 33, identical in every run. The misses
share a cause: vertical valve labels, a two-line equipment label, and a control-valve number drawn on a separate
actuator bubble. On the list-keyed sheets GPT found all 145 identifiers in every run and Claude 99.4% on average. A
cross-sheet control showed why that is an upper bound: valve numbers repeat between the two sheets, so a short
identifier can match by coincidence.

**A bug in my own report, caught by reading it.** The first replicate summary called the tag difference "different"
under the runs interval. Every run had the same score, so the interval had zero width and excluded zero trivially.
The script now says "no run-to-run variation" in that case, with a test, and the commit says when and why.

**The review kit.** Review minutes stay unmeasured: no reviewer timed anything, and inventing a number would undo
everything above. `out/review_kit/sheet-8/` packages the smallest holdout-A sheet's review queue (88 rows) with the
drawing, the overlay, a timer that records only pseudonymous start/pause/stop timestamps, a summary that refuses an
unfinished log or a reordered sheet, and a draft study protocol whose design decisions are deliberately blank. One
sitting gives one reviewer's minutes on one sheet: a first observation, not a saving.

**What this doesn't fix.** Five DEXPI sheets from one publisher are clean, vector-drawn and small; they test a third
drafting style and tag reading, not real archives. The sample of drawings, not of runs, is still the limit on every
model comparison. Nothing was tuned on these results: a key that counts nozzles, or a tracer that ignores stubs on
equipment, would be a new method needing new drawings.

**Lesson:** report the interval that answers the question you are asking. "Would it change if I ran it again?" and
"would it hold on other drawings?" have different answers here, and only the second one matters to a plant.

**At your plant:** run the selected method several times on your pilot sheets before believing a single score; a
bimodal result (like the nozzles) is a sign that a definition, not the model, needs a decision. Write down which
drawn things are symbols for you before scoring anything. And time the first review: it costs one sitting and
replaces the most important assumption in the cost case.

---

## 47. Count what the bands detect, and make lost data an alarm

**2026-10-13.** Three gaps a reviewer would point at first. The fault demo showed one easy fault and called the
bands an early warning. When the replay stopped, every value read UNKNOWN while the header still said "Alarms: 0".
And the header counted tags in alarm, not alarms. A fourth: at 390 px the screens were a 1600 px control room you
scroll around in.

**How often do the bands detect a fault?** I fetched the rest of the Braatz set (44 files; every one is
byte-identical to the Braatz group's own archive at MIT, which I checked before recording the checksums) and wrote
the rule down before scoring any fault file: the plant is flagged when any of the 52 channels is outside its band,
and a fault counts as detected at the first post-onset sample that starts 3 flagged samples in a row (9 minutes).
Nothing was tuned on fault data; the bands are the shipped ones (K = 6). False alarms were measured on normal
running the bands never fitted on: the separate normal training run and the fault-free first 8 hours of all 21
fault runs, 193 plant hours in all.

| | Shipped bands | PCA T² baseline |
|---|---|---|
| Faults detected | **17 of 21** | 19 of 21, of which 3 are probably chance (below) |
| Median delay, detected faults | 48 min | 84 min |
| False alarms, held-out normal data | **0 in 193 h** (95% upper bound about 0.37 a day) | 5 in 216 h, 1.04% of samples flagged |

The bands miss faults 3, 9 and 15, which I had named as expected misses before scoring (the literature widely
reports them as near-invisible in these variables), and 19, which PCA misses too. Slow faults are late: fault 21 is
flagged after 26.5 hours. PCA T² is my own reimplementation (numpy, parallel analysis, F threshold), not a
literature number; I couldn't verify a published table's exact values from a primary source, so none is quoted.
Its "detections" of faults 3, 4 and 15 come after 18 to 34 hours with 2–8% of samples flagged, which is close to
its own false-alarm rate, so I count them as chance. On fault 4 the bands are clearly better (6 minutes, through
TI-109). Details: [EVALUATION.md section 4b](EVALUATION.md#4b-fault-detection-with-the-normal-bands-tennessee-eastman-all-21-faults).
The first tags to leave their band are reported per fault by tag. They don't depend on which unit a tag belongs
to, so the topology correction in entry 42 doesn't change them.

**Lost data is now an alarm, of its own kind.** Two expression tags count the fed values that are not Good, one
per data connection (52 replay values, 24 demo points). Each carries a "Data source lost" alarm. ISA-18.2 treats
this as a diagnostic, not a process alarm: it says the operator has lost sight of the process. So the header now
has three boxes: "Process alarms: N", a data-source box that turns dark slate and reads DATA SOURCE LOST, and
"Outside band". Process alarms now count each configured alarm once, so PI-107's two alarms count as two, which is
what the alarm table lists. Two choices here are mine alone and need operations: the diagnostic priority (Medium)
and the dark slate colour. Neither the setpoints nor any process alarm changed.

**"Not connected" and UNKNOWN now look the same everywhere.** Before, the same no-source agitator read NOT
CONNECTED in its table row and UNKNOWN in its label beside the reactor drawing, and a mapped drawing value with no data looked like a
normal white label. Now there are two states with one look each: *not connected* (no data source configured;
muted italic on white, dashed border) and *UNKNOWN* (a source is configured but nothing Good is arriving; muted on
grey). The rationale is ISA-101's intent, stated rather than quoted: one documented style in which an indication
means the same thing on every screen, quality never mistaken for a value, and alarm colours kept for alarms.
Exception, recorded in a test: two schematic labels with alarms keep their alarm colour binding, because a label has
one background.

**A narrow overview.** `/m` is a 390 px view: process alarm count, data source and band count first, then the active
alarm list, then the six units stacked in process order with the same key values as the overview, coloured the
same way. The control-room views are unchanged in layout and still 1600 px; the tiles link to them.

**Merged first.** Midway, the topology check (entry 42) moved the purge and its tags from the compressor to the
separator. I merged that branch before the gateway run and regenerated the provider, project and drawings instead of
merging generated files. The auto-merged provider would have been wrong: its new data-source expression still
pointed at the purge tags' old compressor paths.

**What the gateway found.** The first import held both data-source alarms active with a count of 0. Ignition's
AboveValue mode is inclusive (the 3,000 kPa shutdown alarm firing at exactly 3,000.0 had already shown that, and I
didn't apply it), so a setpoint of 0 meant "0 or more". The setpoint is now 0.5, with a test. Walking the screens
with the replay stopped showed every band indicator drawing its pointer at the scale minimum, which reads as a real
low value; it is now hidden without Good data. And the Alarms page still said "the only alarms are the published
ones", which stopped being true. All three were fixed before the final run of commit `4a00c35`.

| Check | Result |
|---|---|
| V1–V8 | PASS: 1,256 tag nodes and 24 views, 0 differences; 1,448 bindings; 76 Good, 335 Bad as designed; writes refused; PI-107 alarm 0.5 s after crossing |
| Routes and navigation | PASS: 24/24 load and reload; 284/284 clicks, Back after each, 0 console errors |
| Replay stopped / restarted | PASS: diagnostic fires, header DATA SOURCE LOST, 52 UNKNOWN; clears within about 25 s of restart |
| Demo points stopped / restarted | PASS: second diagnostic fires and clears |
| Header vs alarm table | 40/40 samples through the fault, 29/30 through a loss and recovery. The miss, and one capture, fell within about 2 s of an alarm changing state: the header polls every second, the table refreshes every two |
| Process alarm active when data is lost | Observed: PI-107's alarm stays active on its last value while PI-107 reads UNKNOWN. Ignition's default; whether stale data should hold, clear or suppress a process alarm is an operations decision |
| `/m` at 390 × 844 | PASS: no horizontal scroll, alarms first, honest UNKNOWN and DATA SOURCE LOST |

The `native-*.png` screenshots now show this build; entry 38's originals are in the history at `f5c270e`.
Receipt: [`native-current-20261013-alarms.json`](../out/ignition/gateway/receipts/native-current-20261013-alarms.json).
Afterwards I removed the containers, the volume, the network, both images and the build cache, and checked that
Docker held nothing. The rollback is in the receipt.

**What went wrong on the way.** Git Bash rewrote a route argument into a Windows path again, the same trap as entry
38: my alarm-count sampler asked the gateway for a project called `PIDTwinC:` for six minutes before I read the
gateway log. My scratch orchestration also had two path bugs that cost one stage-1 rerun. None reached the
committed tools; the sampler is now a `count` mode of the browser harness, added after the run.

**Not established:** real phones (headless Chromium only), operator usability, operations approval of the diagnostic
priority and of process-alarm behaviour on stale data, and anything beyond one simulated operating mode for the
fault evaluation.

**Lesson:** a detection claim needs a denominator and a false-alarm rate measured on data the method never saw,
and both numbers belong in the same sentence. The single fault was true and misleading. On the alarm side, a
quiet header is a claim too: "Alarms: 0" over a screen of UNKNOWN said nothing was wrong, when the truth was that
nothing could be known.

**At your plant:** score the band, or any detector, on every recorded upset you have, with the rule fixed first,
and measure false alarms over weeks of normal running before trusting the colour. Treat loss of a data source as a
diagnostic alarm with an owner and a response, separate from process alarms, and decide with operations what a
process alarm should do while its value is stale.

---

## 48. Give the drawings-only track the deliverables it can support

**What:** the OPEN100 track (12 real drawings, no process data) gets flow direction read from the drawings, the 12
sheets stitched into one plant, a process mimic, a 3D orientation tour and a LOTO isolation view. All of it is
structure. Where the drawings can't supply something, the README matrix says so and says what is missing.

**How:**
- **Direction first, because everything else draws arrows.** The twin's 1,881 connections all said "unknown", and
  the answer keys can't help: every graphml is undirected, and its `arrow` nodes have a position and no
  orientation. `scripts/flow_direction.py` re-traces each sheet with the same tracer and symbols, and checks that the
  links come out identical to the twin's (1,874 of 1,874). It then reads three kinds of evidence. Arrowheads: ink
  sticking out on both sides of a straight run, tapering to a tip. Off-page flags: which end of the pentagon is
  pointed, compared with where the line attaches. Pumps: discharge at the top of the casing. A fourth rule carries
  direction through in-line valves with exactly two connections.
- **The first version over-claimed, and the conflicts showed it.** At first an arrow oriented every symbol behind it
  against every symbol ahead of it. On a header with two outlets, that says outlet A flows to outlet B and back
  again: 380 conflicts, still 237 after instrument links were taken out. The fix split the evidence. "First-hand" means the arrow sits on the pipe between the two
  symbols, with no branch in between. "Across a branch" is the weaker reading. Two more rounds were needed before
  "no branch" meant what it says: instrument taps and arrowheads' own wings had made every pipe look branched, and
  so had three join points stacked on one corner.
- **Checking a direction with no key.** The detector's settings were chosen on sheets 0-5. On the held-out sheets
  6-11 it found 77% of the keys' arrow nodes, with 83% of its detections on one. For direction itself, 65 directed
  links (stratified, fixed seed) were cut out as crops with the two symbols outlined A and B, A picked at random.
  GPT (Codex CLI) and Claude (a fresh claude CLI session) read them blind. Neither disagreed with the code once. Each
  left some unclear, mostly across-a-branch links. Each link carries the lower end of the 95% interval as its
  confidence, not the 100%.
- **Two things the extraction never read.** The equipment schedules printed along the bottom of each sheet
  ("SERVICE: LETDOWN FILTER") say what each piece of equipment is for. Claude transcribed them, and 49 of the 74
  purpose cards come from them. Drawing numbers written with en dashes ("PID 110–1") had defeated the twin's
  connector pairing. Read as numbers, they let 31 more connectors find their sheet: 38 sheet-to-sheet connections
  instead of 7.
- **The screens reuse what exists.** The mimic is built from the TE screens' components and their "not connected"
  transform. The 3D tour uses the 3D branch's renderer, copied byte for byte in its own commit. The LOTO view numbers
  each isolation point on the real drawing.

**Why:**
- A twin without process data is still most of a starter kit. Steve put it plainly: the mimic and the tour don't
  need the data, so show what the two sets we have can do.
- Rejected: drawing every link with an arrow by guessing from layout (left to right, top to bottom). It would have
  looked complete and taught people to trust arrows nobody drew. Two-thirds of the process links stay undirected,
  and the screens show them dashed.
- Rejected: tank nozzle position as direction evidence (bottom inlets are common), and direction on instrument
  links (they carry signals, not flow).

**Lesson:** when there is no key, two independent readings agreeing is the next best evidence. Here it took three
forms: arrowheads and flags agreed on all 70 links where both spoke, two models read blind crops, and the
re-traced links had to match the twin before any direction was trusted. Conflicts are information too. 380 of
them said the rule was wrong, not that the drawings were.

**At your plant:** if you have the drawings and no historian access yet, build the model, the asset framework, the
mimic, the tour and the isolation view now, and add values when the data arrives. Read the equipment schedules on
your sheets. Keep arrows only where the drawing shows them. Treat the isolation list as a reviewer's checklist for
your energy-control procedure (OSHA 1910.147), never as the procedure: a valve the extraction missed is missing from
the list too.

---

## 49. Bring eight lines of work onto one branch, and make every output a stage

**2026-10-13.** Seven branches had been built side by side from the same starting commit, each finished and tested on
its own: the data-lineage spine (entry 45), the topology check (42), the generated TE P&ID (44),
the fault evaluation with the data-loss alarms (47), round 5 (46), the PI and review-kit work (43)
and the OPEN100 structural deliverables (48). The 3D tour (39-41) lived on an unpublished local
branch whose history could not be published. This entry is the merge.

**How:**
- **Real merges, in dependency order:** lineage first (everything else is a stage in it), then the topology check,
  the generated P&ID and the fault work (both already contained the topology check), round 5, the PI and review-kit
  work, and the OPEN100 structural branch last. No branch was rebased.
- **Generated files were never hand-merged.** Where a conflict was in an output (the TE tag export, the PI sheets,
  the reconciliation file), one side was taken and the file rebuilt with `pipeline.py rebuild`. Hand merges were
  only in source and documents.
- **Every branch's outputs became stages** in `pipeline/stages.json`: 39 stages over three datasets (DEXPI joined
  TE and OPEN100). Recorded stages (model calls, downloads) are accepted as the record, not re-run. The
  orchestrator learned two things on the way: a stage can need a Python package (`requires_modules`) or a local
  program named in an environment variable (`requires_env`, used as `$BLENDER_EXE` in the command), so no machine
  path is written into the manifest. 37 of 39 are fresh; the two that need a running Ignition gateway are listed as
  such.
- **The 3D tour came in without its history:** only its current source files were copied from the local branch's
  last commit, the review patch was applied to that copy, two files were replaced by scrubbed versions, and the
  public-hygiene check ran with the private terms supplied from the environment, never written down. Details:
  [drafts/3d-tour/REVIEW_NOTES.md](../drafts/3d-tour/REVIEW_NOTES.md), section 6.

**What the merge itself found** (none of it was a text conflict):
- **A demonstration became a fact.** The lineage test proved propagation by moving FI-110 from K-101 to V-101 on a
  temp copy. The topology check had made that move real, so the test's "before" control failed. The fixture now
  moves FI-105 instead, and says it is a fixture.
- **The same feature twice, under two names.** The P&ID branch and round 5 both added a setting that points the
  extraction scripts at another folder of sheets: `PID_SHEETS_DIR` and `PID_DATA_DIR`. Every script now reads one
  setting and accepts both names.
- **A hash that depended on the operating system.** The generated P&ID's manifest hashed raw bytes, so a Windows
  checkout (CRLF) and a Linux one disagreed about the same files. Text is now hashed with line endings normalised,
  as the orchestrator already did.
- **Two formats meeting.** The PI sheet v2 moved attribute descriptions out of the sheet, and the lineage branch had
  added each item's confidence to those descriptions. The merged exporter keeps both, the propagation test reads the
  v2 layout, and the 3D render verifier compares descriptions with the confidence suffix removed.
- **The accepted gateway build is still the accepted build.** Rebuilt from the merged source on Windows, the project
  ZIP is byte-identical to the one natively accepted (`8982ccd2…`), so the acceptance in entry 47 applies to it.
- **The first CI run after the push found one more.** On Linux the same build writes the same ZIP members, but the
  compressed bytes differ (another zlib build, and the archive records the OS that wrote it), so the orchestrator
  called the gateway stage stale. ZIPs are now hashed by their members. Rendered stills are the other
  non-reproducible output: Blender's renders can differ by a few grey levels between runs, so a rebuild may rewrite
  the JPEGs while the measured label boxes stay identical.
- **The tour's new font measured smaller.** Atkinson Hyperlegible at the old sizes drew labels of 14.9-16.6 px, under
  the 18 px minimum; sizes were scaled by 1.25 and the minimum kept. Rendering all twelve stills (not only the five
  that are committed) found one more defect: a stripper tag sat in the plane of a platform deck, hidden from every
  camera. Both tours share the renderer, so the OPEN100 stills were re-rendered too.

**Numbers, reconciled:** the holdout-A review load is now quoted from the round-5 replicates (GPT 20.1, Claude 29.8,
with run and drawing intervals). The round-2 figures (17.8 and 32.4 with the method, 48.8 for GPT alone) stay where
they are, labelled as the earlier single runs, because the decisions of round 2 were taken on them.

**Why:**
- Branches built in parallel each pass their own tests. What breaks at the merge is an assumption one branch made
  about another: that a correction had not happened yet, that a file format had not changed, that nobody else had
  added the same setting.
- Rebuilding instead of hand-merging outputs is what makes those visible. A hand-merged CSV would have hidden the
  description that moved columns.

**Lesson:** after a merge, rebuild from the source and read the test failures as findings about the merge, not as
noise. Most of what broke here was in tests, hashes and checks rather than product logic, and each would have
silently weakened a check if it had been "fixed" by loosening it.

**At your plant:** when pilot workstreams converge (drawing extraction, historian mapping, screens, a PI structure),
merge them through the same lineage: correct the source, rebuild everything downstream, never edit an output to make
two of them agree, and tie acceptance evidence to file hashes so you can tell whether it still applies after the
merge.

---

## 50. Find the control loops before drawing them: the generated P&ID draws none

**What:** 2026-10-28. The generated TE sheets (entry 44) draw every transmitter and every valve, but no controller and
no signal line. FI-102 sits beside FV-201 and nothing says one drives the other. A practitioner reads that as a
process flow diagram with bubbles on it, not a P&ID, and would be right. Before fixing the drawing, this entry finds
out what the loops actually are and measures how much of them the sheets show. The answer is none of them.

**How:**
- **Source:** `temain_mod.f`, the closed-loop code in the Braatz group's TE archive, the same archive the replay data
  comes from. The GitHub mirror's copy is byte-identical to the archive member (SHA-256 `31b83c17…`, checked
  2026-10-28), so `scripts/fetch_te_data.py` now fetches and verifies it with the other files.
- **Reading it:** `scripts/te_control_loops.py` takes each controller subroutine's error line
  (`ERRn = (SETPT(j) - XMEAS(m))`) for the measurement, and its update line for what it moves: a valve
  (`XMV(k) = XMV(k) + DXMV`) or another loop's setpoint (`SETPT(j) = SETPT(j) + DXMV`), which makes it a cascade.
  The `CALL` lines in the simulation loop give which controllers run and how often. The result is
  `data/te_control_loops.json`, named with the model's tags.
- **Comments ignored on purpose:** the file's comments were copied from one subroutine to the next. "Stripper Level
  Controller" sits on the purge loop and on the reactor cooling loop. Only the code is read.
- **Checked against the data:** that copy of the code is set up for a fault-12 run, so the code alone doesn't prove
  the published files used these loops. Every controlled variable in `d00_te.dat` sits on its coded setpoint: all 19
  within 0.34 standard deviations, 17 within 0.07. The two furthest off are steam flow and stripper temperature,
  inner loops whose setpoints a cascade moves. A negative control rotates the pairings by one place, and 18 of 19
  loops then miss by more than 3 standard deviations.
- **Drawing audit:** for each running loop, an answer key passes if it draws the measurement, a controller with
  matching letters (FIC for a flow), signal lines from measurement to controller and from controller to valve (or
  to the inner controller), and one loop number across all three. Process lines don't count as signals. The test
  file checks the grader before the score: it passes a correctly drawn loop and a cascade, and fails each mistake
  separately.

**What it found** ([`out/te_loop_audit.md`](../out/te_loop_audit.md)):
- **19 loops run:** 11 move a valve and 8 move another loop's setpoint. Three composition loops on the reactor feed
  analyzer trim the A, D and E feed flows. Purge composition trims purge flow. Reactor level trims the A and C feed.
  Reactor temperature trims the cooling water outlet temperature. Product composition trims stripper temperature,
  which trims steam flow. One more controller (separator pressure to purge) is defined but never called.
- **Production rate is set by condenser cooling water.** The stripper product flow loop moves the condenser
  cooling-water valve, not the product valve. The model tagged that valve TV-211, which says temperature control.
- **An override sits on the purge:** separator pressure at or above 2,950 kPa forces the purge fully open, at or
  below 2,300 kPa fully shut, and the controller gets it back when pressure returns to 2,633.7 kPa.
- **Score on the generated sheets: 0 of 19 loops.** Every measurement is drawn (19/19). No controller, no signal and
  no shared loop number (0/19 each).
- **The tags are wrong before anything is drawn.** All 11 valves carry a different loop number from the measurement
  that drives them (FV-201 is moved by FI-102's loop). Two carry the wrong letter: HV-205 (a hand valve on a flow
  loop) and TV-211 (a temperature valve on a flow loop).

**Why:**
- **Measure, then fix.** Drawing controllers without the table would have meant guessing pairings from tag numbers,
  which is how the wrong pairings got there in the first place.
- **The data check is the independent witness.** The code and the drawing share an author's interpretation; the
  recorded run doesn't.
- **Rejected:** fixing the tag numbers in this entry. They run through the Ignition project, the PI sheet, both tours
  and the replay mapping (about 1,300 references), so renumbering is a separate, regenerated change.

**Lesson:** a drawing that shows every instrument can still miss the reason they're there. Count what the sheet says
about control, not what it says about equipment.

**At your plant:** the control narrative is in the DCS configuration, not the drawing. Export the controller list
(PV, OP or cascade target, mode) and audit your P&IDs against it the same way: every loop needs a controller, signal
lines and one loop number. Drawings where indicators sit next to valves with different numbers are the ones to walk
down first.

---

## 51. Draw the control loops, and give each valve its loop's number

**What:** 2026-10-28. Revision B of the generated TE sheets draws all 19 control loops that entry 50 read out of the
closed-loop code, and every control valve now carries the number of the loop that moves it. The loop audit goes from
0 of 19 to 19 of 19. Revision A stays in the repository, because the recorded extraction runs read it.

**How:**
- **Controllers belong to the model.** `scripts/te_control_loops.py --write-model` adds a `controllers` list to
  `data/te_process_model.json`: tag, loop, what it reads, what it moves (a valve, or another controller's setpoint),
  mode, scan period, and the source lines and recorded-data deviation as evidence. Tags follow ISA-5.1: FIC-101 reads
  FI-101. The analyzer that feeds three loops gets component suffixes (AIC-123A, AIC-123D, AIC-123E).
- **One mapping renames the valves.** `scripts/retag_te_valves.py` applies `data/te_retag_2026-10-28.json` to the
  source files that name tags (126 replacements in 16 files: the model, layouts, tour cards, hazard citations, HMI
  unit lists, tests, current-state docs). It refuses a mapping that isn't one-to-one or that would chain. Each renamed
  valve keeps `former_tag`. HV-205 became FV-105 and TV-211 became FV-117: both sit on flow loops. Outputs were rebuilt
  by `scripts/pipeline.py`, never edited.
- **The generator draws what the model says.** Controllers are drawn as DCS functions (a circle in a square, with
  the operator-visible line), joined by dashed signal lines; the two loops that cross sheets (reactor level to the
  A and C feed, stripper product flow to condenser cooling water) end in signal continuation flags naming the other
  sheet, the grid zone and the far end. The layout only gives positions and corner points. The generator refuses a
  controller placed twice or not at all, a model signal not drawn, a signal the model doesn't have, a diagonal
  segment, and a signal line through any symbol or vessel. The first full layout drew clean; the refusal tests break
  it on purpose.
- **Signals stay out of the scored graph.** The frozen scorer counts every edge in a key's graph file regardless of
  its label, and the line tracer follows solid lines only. Putting signal lines there failed the tracer check (18
  untraced links on sheet 101 alone) and would have changed what the round-trip connection score means. Signal lines live in `key.json` as
  `signal_edges` and are scored by the loop audit; the graph file keeps process lines, as the OPEN100 keys do.
  Controllers are in it as symbols, because they are on the drawing.
- **Revision A is kept as evidence.** The recorded extraction, round-trip and twin stages read the 2026-10-13
  sheets. Those sheets are archived in `data/te_pid/rev-a/`, byte-identical to the hashes the lock recorded when the
  runs were made, and a source stage (`te.pid_rev_a`) owns them. The reviewer diff joins old extractions through
  `former_tag`, so all five diffs keep their correction counts (9, 10, 11, 47, 54) and note each valve as "read as
  FV-201, its revision-A tag".
- **Everything downstream rebuilt:** Ignition project, PI sheet, SVGs, mimic, scene, bands, fault detection, both
  tours (the Blender stills re-rendered; the render verifier passes 15 and reports 2 informational, as before) and the
  style check. 40 of 42 pipeline stages are fresh; the two that aren't need a running gateway.

**What it found:**
- **Style fidelity dropped from 32 to 30 of 36.** The instrument share per sheet (0.55 to 0.61) is now above every
  OPEN100 sheet (at most 0.54): the drawing gained 19 controllers but still has none of the block valves, bypasses,
  drains and vents that surround a control valve on a real P&ID. Ink coverage moved into range.
- **The model already knew the answer.** Every pairing was in the code; only the numbering hid it. Once tags follow
  loops, a reader can check a loop by eye: FI-117, FIC-117, FV-117.

**Why:**
- **Rename at the source, rebuild the rest.** Hand-editing about 1,300 references across exports would have left
  some behind; the pipeline found the ones the rename tool didn't own (a sorted list and a spoken "T V 210" in the 3D
  tests).
- **Keep the old evidence honest.** Re-pointing recorded runs at new sheets would have called stale evidence fresh.
  Archiving the exact bytes they read keeps their numbers true and says what they describe.
- **Rejected:** renaming the transmitters to FT (purists draw FT under an FIC). The I letters are the replay points'
  names everywhere; the loop audit and a reader both get the loop from the shared number. Also rejected: drawing the
  purge override from PI-113 as a signal. The code implements it as a latched trip with a hand-back inside the purge
  controller; drawing it properly needs a selector symbol and a cause-and-effect note, not a dashed line.

**Native acceptance, the same evening:** the rebuilt project went into the local disposable gateway with
`build_gateway.py --fresh` (1,121 tags, 0 failures, 0 read-back differences). The verifier caught 5/5 planted faults
and passed V1–V9 on `c15b362`; the browser contract passed 24/24 routes and 284/284 clicks with no console errors;
stopping the replay raised the data-source-lost diagnostic and restarting it cleared it, with the header's count
matching the alarm table in all 24 samples ([receipt](../out/ignition/gateway/receipts/native-revB-20261028.json)).
One snag: Git Bash rewrote the browser contract's route arguments (`/unit/U-100`) into Windows paths;
`MSYS_NO_PATHCONV=1` fixed it.

**Not done here:** the revision-B sheets haven't been read back by the models (a paid, recorded run), the 3D OCR
read-back still describes the old stills, and no control engineer has reviewed the loops. The audit grades the drawing against the code; it doesn't judge the control
strategy.

**Lesson:** a loop table is cheap to read and expensive to guess. Once the drawing came from the table, the drawing,
the tags and every export agreed by construction.

**At your plant:** number control valves by the loop that moves them and draw the controller even when it lives in the
DCS. When you renumber, do it from one mapping table at the source, keep the old tag on each item, and leave dated
evidence pointing at the drawing revision it was made from.

---

## 52. Put each control valve in a station: block valves and a bypass

**What:** 2026-10-28, later the same day. Revision C of the generated TE sheets draws a control valve station around
every inline control valve: a manual block valve on each side and a bypass with a hand-operated globe valve. That is
how a real P&ID draws a control valve, so it can be isolated and pulled while the line runs on the bypass. Style
fidelity goes from 30 to 35 of 36 OPEN100 measurements.

**How:**
- **A layout switch, not model content.** The model holds no manual valves, so the stations are drafting additions:
  `control_valve_stations` in the layout turns them on, and each block and bypass valve is in the key with
  `drafting_addition` set and no model reference. A route opts out with `"station": false` and must give a
  `station_reason`. The compressor's spill-back valve (FV-105) does: it sits inside its own recycle loop.
- **Refuse rather than squeeze.** A station needs a straight run 80 px either side of its valve with nothing else in
  it, and its bypass must clear every symbol. The generator refuses otherwise. The first try failed on paper before
  any code ran: at a 60 px offset, the feed-line bypasses ran through the flow controllers between the feed lines. The
  bypass offset became 45 px and the three feed lines moved apart (330, 590, 850).
- **The pixels still agree with the key.** The bypass joins the line at two tees, so the key's process links change.
  The code line tracer, given only the symbol boxes and the image, recovered every key link on all three sheets,
  bypasses included. New tests check one station per inline control valve, the crowded-station refusal and the
  opt-out reason.
- Revision C, because revision B was already on the public main branch. The loop audit still reads 19 of 19, and
  every downstream stage was rebuilt (42 of 42 fresh).

**What it found:** the remaining style miss is sheet 103's symbol count (37 against an OPEN100 minimum of 40). Real
sheets also carry drains, vents, reducers and line breaks that a process model doesn't hold.

**Why:**
- **A reviewer's first question.** A practitioner looking at a control valve with no block valves sees a drawing
  nobody checked. This is the cheapest fix that answers it honestly, because it's a convention, not process data.
- **Rejected:** adding drains and vents the same way. Where they go depends on line routing and low and high points
  that the model doesn't hold, so placing them would be decoration rather than a convention.

**Lesson:** separate what the process says from what the drafting convention says, and label which is which in the
key. Then a convention can be added everywhere at once without anyone mistaking it for plant data.

**At your plant:** when you generate drawings, apply your drafting standard's conventions (valve stations, spec
breaks, vents and drains at the high and low points your routing defines) as declared rules, not hand edits, and walk
the result down before anyone treats it as a drawing of record.

---

## 53. Carry the October 15 tour review onto the renumbered build

**What:** 2026-10-28. A review of the draft 3D and browser tours on October 15 found confusing callouts on the
separator and compressor, no proper overhead corridor for the recycle, an S-bend, and no cutaway into the feed header
or compressor. Those corrections were made in a separate working copy on the old main branch and never merged. They
are now applied on top of revision C's tags.

**How:**
- Only the source changes were carried over (the tour builders, the browser tour's code, styles and verifier, the
  Blender template and the 3D scene builder, their tests and READMEs, plus a new geometry test). They were taken as a
  patch against the old base and applied with a three-way merge. Every output (pages, stills, audits, label boxes)
  was then rebuilt by the pipeline, not copied, so it carries the new valve tags.
- One conflict, in the 3D tour README: both the October 15 review and the renumbering had rewritten the same
  paragraph. The merged text keeps both. The tour stage now publishes the eight review stills, not five.
- The 3D scene builder is shared with the OPEN100 structure-only scene, so that scene was re-rendered too.

**Result:** the browser tour's verifier passes 38 checks with 5 informational and none failing; the 3D render verifier
fails none; the new geometry test passes; all 42 pipeline stages are fresh. The impeller, rack dimensions and LOTO
locations remain illustrative placeholders, and the stills still need the owner's approval before any video.

**Lesson:** corrections made outside the main line are a liability until they're merged. Carry the source, not the
outputs, and let the pipeline rebuild.

---

## 54. Read revision C back with the same method

**What:** 2026-10-28. The project owner approved paying for the model read-back of the revised drawings. Revision C
(controllers, signal lines, valve stations) was read with exactly the protocol of entry 44: 2×2 tiles, prompt v2, the
line tracer, 5 clean runs and 3 per degraded level per model.

**How:** `scripts/run_te_roundtrip.py` runs every condition and replicate, labelled `tec-*` so revision C's runs never
mix with revision A's `te-*`, and skips anything already done so it can resume. The scorer gained `--keys`,
`--prefix` and `--out`, so each revision is scored against its own sheets. That also exposed a gap from revision B:
the recorded revision-A scoring command had no way to name its keys, and the default folder now holds revision C. Its
recorded command now names `data/te_pid/rev-a`. The revision-A scores themselves were not re-run (their run records
aren't on this machine); they are unchanged.

**What it found (GPT, gpt-6.1-sol through the Codex CLI, and Claude, claude-opus-5-5 through the Claude Code CLI;
42 sheet runs each, no failed tile):**

| Image | GPT, revision A | GPT, revision C | Claude, revision A | Claude, revision C |
|---|---|---|---|---|
| Clean | 2.1 per 100, 100% of tags | 1.26, 100% | 2.2, 100% | 1.38, 100% |
| L1 photocopy | 2.1, 100% | 1.30, 100% | 8.0, 98% | 4.1, 100% |
| L2 old scan | 2.1, 56% | 1.20, 61% | 13.4, 95% | 10.0, 89% |
| L3 bad scan | 16.9, 14% | 14.9, 9% | 17.3, 49% | 15.7, 50% |

- **More symbols didn't make the drawing harder to read.** Revision C has 19 controllers, 30 manual valves and more
  tags, and the clean review load fell. Part of that is denominator: more key items, about as many corrections.
- **Tag text is still what fails on bad scans,** and slightly worse at L3. The controller symbols' smaller text
  (letters above a line, number below) goes first: at L2, 51% of controller tags were misread against 34% of the
  others; at L3, all of them against 87%. A drafting choice (text size inside the DCS symbol) costs readability on
  poor copies.
- **Claude reads tags far better on poor copies** (89% against 61% at L2, 50% against 9% at L3), and its
  controller tags hold up better too (missed at L2: 21% against 7% for other tags; GPT 51% against 34%). One habit
  shows: 13 of its misses read an FI bubble as FT, a transmitter tag, the letters it expects rather than the ones
  printed.
- **Claude's higher review load at L1 and L2 is not worse reading. It comes from the line tracer.** Its connections
  fall to 0.93 at L2 while every symbol is found, with about 30 extra links per run, all whole networks merged into
  one: everything on the reactor wall linked to everything else. Claude's equipment boxes stay tight on degraded
  scans (median vessel box 20,708 px² against GPT's 21,859), sitting just inside the drawn wall, so the tracer
  follows the wall as if it were a pipe. Growing only the equipment boxes by 4 px removes every extra link (sheet
  101: 0.93 to 0.99; sheet 103: 0.86 to 1.00) and changes nothing for GPT. The revision-A Claude scores at L1 and L2
  (8.0 and 13.4) look like the same cause; those run records aren't on this machine, so that is unverified.
- **The scores above stay as measured.** The method is frozen; the tracer fix (pad equipment boxes by the outline
  width before tracing) is a method change, to be measured on every result it would touch, not slipped into this
  one.

**Lesson:** when two models differ on a score that neither model produces (here, connections come from code), look
for the interaction before ranking the models. The difference was in my tracer's assumption about box size.

**At your plant:** when a drawing standard changes (new symbols, new tags), re-measure your extraction method on the
new drawings with the same protocol, and keep the old results tied to the old drawings rather than overwriting them.

---

## 55. Start the real unit: a sourced model and a checked trend

**What:** 2026-10-28. The owner chose the Bayer CropScience residue treater (docs/REAL_UNIT_SELECTION.md). Two pieces
are built: a process model that cites the CSB report for every item, and a digitization of the report's DCS trend
(Figure 11) checked against the report's own text. Details: [BAYER_RT.md](BAYER_RT.md).

**How:**
- **The model** follows Figure 10 and pp. 27-32 and 38-40: units, streams, instruments, valves, the two controllers
  the report describes, three interlocks, limits and the timeline. The report gives no tag numbers, so every tag is
  assigned and marked so. Findings sit on the items they concern: the bypassed minimum-temperature interlock (p. 69),
  the steam block valve found closed (p. 70), the mis-programmed split range (p. 39).
- **The trend** is read from the figure's pixels. Calibration uses only the figure's tick marks and gridlines; the
  figure's dotted failure line then lands 0.1 minutes from 22:33 before any curve is read. Eleven values stated in
  the text and labels are checks, never calibration inputs.
- **Research claims were checked against the PDF before use.** A research pass said "8 injured". The report says six
  volunteer firefighters and two contractors were treated for possible toxic exposure, so the model and the selection
  memo now say that.

**What it found:** 6 of 11 checks passed on the first run. Two failures were my own bugs (the flow classifier caught
the red trace's anti-aliased edge; one check used the wrong time window) and were fixed. The other three are real
disagreements between the figure and the text: the figure's steady pressure is about 25 psig where the text says 22,
and its temperature runs about 2 °C below the text's values near the end. The pressure scale is confirmed by the two
labelled pressures, which both agree, so the replay will use the figure and state the difference.

**Why:**
- **A trend digitized without checks is a drawing of a drawing.** The report's own numbers are the only independent
  reference available, so they test the digitizer instead of tuning it.
- **Rejected:** shifting the pressure calibration by 3 psig to match the text. Two labelled pressures on the same axis
  agree with the figure as calibrated; moving the axis would break them to hide a disagreement in the source.

**Lesson:** when two parts of one source disagree, record both and say which the twin uses. Picking the convenient
one silently is how a replay gains false precision.

**At your plant:** historian exports carry tag names and units, but screenshots of trends in incident reports,
shift logs and old studies don't. When you digitize them, calibrate on the axes, test against every number written
down elsewhere, and keep the error with every value.

## 56. Draw the real unit and check it against the report's own drawing

**What:** 2026-10-28. The residue treater model was checked against the CSB report's Figure 10, a piping layout drawn
by someone else, then drawn by the same generator as the Tennessee Eastman sheets and checked against that figure
again. Details: [BAYER_RT.md](BAYER_RT.md).

**How:**
- **The figure, written down first.** `data/bayer_rt/fig10_inventory.json` records every unit, terminal, line and
  item Figure 10 shows, read from the figure alone. The figure has no tags, so `scripts/compare_bayer_fig10.py`
  checks at the level it is drawn: each line's two ends, and the types and numbers of items on it.
- **The generator grew to fit a real unit:** the model's hand valves and relief valves, a split-range controller
  with three outputs, and interlocks as ISA diamonds with their signal lines, all refused if dropped or duplicated.
  The TE sheets came out byte-identical.
- **The drawing checked twice:** every figure line traced end to end through the drawn sheet's answer key, and the
  pixel line tracer run on the sheet to confirm it reads back exactly the key's connections.

**What it found:**
- **The model, written from the text, got the figure wrong in four places** (first run 10 of 21; 11 of 21 after one
  bug in my checker): the flow transmitter on the wrong line, the discharge off the vessel instead of off the
  return, the two exchanger outlets returning separately, and the utility outlets and the condenser relief line
  missing. All corrected from the figure, each noted on the item: 20 of 21. The one left is a nozzle whose purpose
  the report doesn't state.
- **The drawing agrees with the figure on 15 of 15 lines.**
- **The first layout had three line crossings, and the tracer read each as a junction.** The two parallel exchanger
  legs make the loop non-planar with every terminal at the sheet edge, so the cooler's water connections now end
  in flags beside the exchanger. The tracer then read back exactly the key.
- **The report gives the project a real tie to the incident**, in its own findings: a new control system,
  operators not trained on it, overview screens they asked for that weren't ready for the startup (p. 60), control
  logic not checked before the restart (pp. 35, 38, 39), and a steam flow indication that was wrong (p. 71). That is
  the motivation the series uses, cited by page. The casualties are stated once and nobody is named.

**Why:**
- **Text describes, drawings connect.** The report's prose says what each item does; only the figure says where it
  sits. Every topology error came from writing the model from prose.
- **Rejected:** adding control valve stations to match the TE sheets. Figure 10 draws none and the report doesn't
  describe any; adding them would be drafting the record doesn't support.
- **Rejected:** keeping the crossings and teaching the tracer to skip them. That would change the tracer the TE
  scores were measured with, and a model reading the sheet would still misread them.

**Lesson:** check a model built from a narrative against any drawing of the same thing before using it, even a
simplified one. Half of the first checks failed, all on connections.

**At your plant:** the same split exists between operating procedures and the P&ID. Procedures say what a valve is
for; the P&ID says what line it's on. Check one against the other, item by item, before trusting either.

## 57. Replay the evening through the interlocks

**What:** 2026-10-29. The digitized Figure 11 trend replayed through the residue treater model's three interlocks and
four operating limits, column by column up to the failure, and checked against what the report says happened.
Details: [BAYER_RT.md](BAYER_RT.md).

**How:**
- **Rules as cited data.** `data/bayer_rt/replay_rules.json` states each interlock and limit with the pages behind
  it. The report publishes no interlock setpoints, so each rule carries the bounds the report supports, and a state
  between them is "cannot tell".
- **Bounds, not points.** Every value carries its column range widened by the digitizing error; a condition is met
  or clear only when the whole bound is on one side.
- **The report's account as the check:** five statements about the evening (pump start, flow loss, the
  high-pressure alarm, the relief valve, the safe operating limit), each turned into a test of the derived states.

**What it found:**
- **A digitizer bug first.** The level series had 39 one-column spikes: the blue fringes of the figure's black text
  labels, picked up because the level mask had no minimum component size. Fixed (components of at least 15 px, the
  middle of the clean 10-20 px range), with a test against any one-column spike. The 11 text checks never sampled
  those minutes, which is why they passed with the bug.
- **5 of 5 statements agree,** within two minutes where the statement gives a time.
- **The minimum-temperature condition was met for the first three and a half hours shown,** until about 21:25. The
  report says that interlock was bypassed (p. 69) and the feed had been open since about 4 a.m. (p. 38). (Corrected
  2026-10-29: an earlier wording here said what the interlock "would have" done, an outcome claim this project
  doesn't make; entry 60.)
- **The figure shows two short flow starts after the pump started,** each falling back to zero, before flow was
  established at about 18:25. The report doesn't mention them; the replay records them as the figure shows them.

**Why:**
- **Rejected: picking a setpoint.** 135 C or 50 psig would make every state crisp and some of them wrong in ways
  nobody could see. "Cannot tell" between two cited bounds is the honest output.
- **Not a blind test.** I wrote the rules after looking at the digitized values, so 5 of 5 shows the replay is
  consistent with the report, not that it predicts it.

**Lesson:** a downstream consumer is a test of its input. The replay read every column; the text checks read eleven.
The bug sat in the minutes nobody sampled.

**At your plant:** when you rebuild an event from a trend, publish the bounds and say when a state can't be told.
A timeline that is crisp everywhere has usually guessed somewhere.

## 58. An overview screen for the unit

**What:** 2026-10-29. A generated overview screen of the residue treater, replaying the evening: the kind of screen
the operators asked for and didn't have at the startup (report p. 60). Proof of concept, at
`drafts/bayer-overview/index.html`. Details: [BAYER_RT.md](BAYER_RT.md).

**How:** `scripts/build_bayer_overview.py` writes one self-contained page from the P&ID layout (geometry), the model
(items and tags) and the replay (values, bounds, states). `drafts/bayer-overview/verify.mjs` checks it in headless
Chrome against `replay.csv`, read independently of the page.

**What it found:**
- **Every check passed on the first build, and the page was unusable.** Mimic text came out about 6 px on a desktop,
  and a phone had no readable values anywhere. The checks covered data and layout, not legibility of the drawing.
  Looking at the screens found it; the fix was a "Values now" card that comes first on a phone, larger mimic text,
  and a check that mimic text is at least 11 px on desktop.
- **The "critical decomposition temperature" is also the normal operating temperature** (p. 30). Shown as a crossed
  limit in amber, it would flag normal operation as abnormal, the alarm habit high-performance HMI guidance warns
  against. It is now marked informational in the rules and shown without colour.
- **All 519 rows on the page match the replay file,** and the failure note appears at the last row only.

**Why:**
- **Rejected: a live Ignition screen first.** The project's gateway path exists for TE, but this replay is 519
  points from a figure, not a running process; a static page shows the same states with less to go wrong, and the
  gateway version can follow if the series wants it.
- **Rejected: colouring every interlock that would act.** "Met" is amber because the feed valve should then be
  closed and isn't; "cannot tell" is a dashed outline, so an unknown never looks like an alarm or an all-clear.

**Lesson:** a page that passes every check can still fail the person reading it. Look at it at the sizes people
use, then make what you saw into a check.

**At your plant:** before you trust an overview screen, ask what it shows when a value is uncertain, and whether
anything coloured as abnormal is actually normal operation.

## 59. Walk the report's timeline beside the screen

**What:** 2026-10-29. The six events the report times on the evening (pp. 38-40), each paired with the replayed
overview screen at that moment and with the checks that test it. On the overview page, below the screen; details in
[BAYER_RT.md](BAYER_RT.md).

**How:** `scripts/bayer_walkthrough.py` derives nothing new. A small data file names which checks test which event;
the script places every existing check (11 figure against text, 5 report statements) under exactly one event and
fails if one is missing or doubled. The digitizer now also writes its checks as JSON, so nothing parses markdown.

**What it found:**
- **13 of 16 checks agree; no report statement disagrees with the replay.** The 3 that don't are the
  figure-against-text disagreements from entry 56, now shown at the moment they apply.
- **The report times 3 of the replay's 20 state changes.** The other 17 are listed, not hidden: the two short flow
  starts, the minimum-temperature condition leaving "met" at 21:26, and the pressure condition's brief "cannot tell"
  around the pump start.
- **My own plan's wording was wrong.** It said every derived state would match the report or be a disagreement. Most
  derived changes are neither: the report just doesn't time them. They get their own list.

**Why:**
- **Rejected: a second page.** The timeline already sat under the screen; making it the walk-through kept one page,
  one data source and one verifier.
- **Rejected: nearest event by eye.** Each event shows the replayed column nearest its time, worked out again by the
  verifier from the CSV; the 18:14 event lands on 18:13:54, before the pump start registers, and the page shows the screen time beside the event.

**Lesson:** put every check you already have in the order a reader meets the story, and count what's left over. The
leftover list is where the next question is.

**At your plant:** when an incident timeline is rebuilt from trends, ask for two lists: where the trend and the
written account disagree, and what the trend shows that the account never mentions.

## 60. Let two hostile reviewers read it before anyone else does

**What:** 2026-10-29. Before the project is linked from a public post series, two independent reviewers, a Claude
panel and a Codex (GPT) reviewer, each read the repository and the draft posts cold, playing the commenters a post
like this gets: a controls engineer, a process-safety specialist, an HMI practitioner, an evaluation skeptic, a
hiring manager and the general snark. Every finding was checked against the files before anything changed.

**What it found, and what changed:**
- **An outcome claim I said I'd never make.** BAYER_RT.md and entry 57 said the bypassed minimum-temperature
  interlock "would have held the feed closed" for three and a half hours. That is a counterfactual about the night,
  and the same document says the project makes none. Both now state the condition and the report's facts only; the
  overview's badge says "condition true" instead of "would hold feed closed".
- **A finding listed as a cause that the report says wasn't one.** The split-range programming fault was cited among
  the reasons this unit belongs here; the CSB concluded it was not causal (p. 39, footnote 29). Now said where it's
  cited, and the opening sentence no longer says the report "ties the incident" to control-system findings.
- **Indicators where the figure shows transmitters.** The Bayer field instruments were tagged PI, LI, FI and TI, which
  an ISA-5.1 reader takes for local gauges, while Figure 10 calls them transmitters and two of them feed controllers.
  Retagged PT, LT, FT, TT with `former_tag` kept; the drawing is revision B; every Bayer output rebuilt, all checks
  unchanged (Figure 10 20 of 21 and 15 of 15; walk-through 13 of 16). The TE sheets have the same convention issue
  (an indicator bubble feeding a controller); that retag touches the gateway and the recorded runs, so it is a
  separate decision.
- **README overclaims.** "Sealed drawings nobody tuned on": holdout A chose each tool's method, and round-1 outputs had
  been seen for all twelve sheets, so its numbers are selection numbers. "Every result is repeated": rounds 2 and 4
  were single runs. "19 of 19 loops": the audit reads the key the generator writes, so it's a regression check, not
  evidence a model can read loops off a sheet. "Review load" was described as a reviewer's corrections; it counts
  differences from the answer key, and no review has been timed. Each is now said plainly.
- **Stale facts.** The README's loop row still said revision C hadn't been read back; the revision C scores now have
  their own table beside revision A's; the Bayer work is counted as its own evidence track; "8 of 11 within the pixel
  error" is "within each check's tolerance"; the "5 of 5" report checks are described as five limited consistency
  checks, two of them proxies.
- **Valve stations as a universal rule.** They are a drafting assumption the TE model doesn't contain, and the style
  score measures resemblance to OPEN100, not engineering quality. Now said.

**Why:**
- **Rejected: answering the critiques in posts instead of fixing the repo.** A commenter reads the linked file, not the
  reply.
- **Rejected: one reviewer.** The two overlapped on the biggest points (the counterfactual, the circular 19 of 19) and
  each found things the other didn't: the Claude panel the transmitter tags and stale screenshots, the Codex reviewer
  the non-causal footnote and the holdout-selection history.
- **Stale screenshots.** The README's two overview screenshots predated the valve renumbering and showed two
  retired tags (HV-205, TV-211). They are replaced by revision B captures from the local test gateway: the normal
  overview from the 2026-10-28 acceptance run, and the fault-6 overview captured 2026-10-29 from the same build, with
  reactor pressure past its alarm. The old images stay for the documents that describe the 2026-10-13 run.

**Lesson:** the same document can state a rule and break it a hundred lines later. A reader looking for the break finds
it in minutes; the author, reading for flow, doesn't.

**At your plant:** before a model, a drawing or a screen goes to the people who'll use it, give it to someone whose job
is to find what's wrong with it, and fix what they find in the artifact, not in the cover note.


---

## 61. Tag the TE transmitters as transmitters, and let a stranger's agent check the README

**What:** 2026-10-29. Every TE measurement is now a field transmitter (FT, PT, LT, TT, AT, JT) read by its
controller: FT-101 feeds FIC-101. The generated sheets are revision D. Entry 51 rejected this rename; entry 60's
reviewers made the case for it (an indicator bubble feeding a controller is the first comment a controls engineer
leaves), and the Bayer drawing had already been retagged the same way. Separately, `scripts/check_claims.py` compares
each headline number in the README with the committed file it comes from, and `AGENTS.md` tells a reader's coding
agent to run it.

**How:**
- **The same tool, one more mapping.** `scripts/retag_te_valves.py` now takes `--mapping`;
  `data/te_retag_2026-10-29.json` renames the 25 measurement tags (639 replacements in 49 source files). Instruments
  now keep `former_tag` too, and an item renamed twice keeps the tag it had just before this rename (the valves keep
  their revision-A numbers). Outputs were rebuilt by the pipeline, not edited.
- **Revision C is archived.** Its sheets moved to `data/te_pid/rev-c/` (a new source stage, `te.pid_rev_c`),
  byte-identical to what the revision C read-back stages hashed when they ran; those stages now point there, and
  `run_te_roundtrip.py` takes `--sheets` so a future run names the revision it reads.
- **Old evidence still joins.** The reviewer diffs keep their correction counts (9, 10, 11, 47, 54) through
  `former_tag`. The live check now does the same: 36 of 36 and 16 of 16 extracted tags reach a moving replay point,
  as before.

**What it found:**
- **The live check had been stale since entry 51 without saying so.** Its committed output still showed the old valve
  numbers as replay points, because the stage didn't list the process model as an input: the replay server reads the
  model, but the pipeline couldn't see that. It does now, and the check joins renamed tags explicitly.
- **A text rename can't see code that tests a prefix.** Four places picked tags by their letters (level bands by
  `LI-`, analyzers by `AI-`): after the rename they would have matched nothing and said nothing. The 3D render
  verifier caught one (16 analyzer channels suddenly "unexplained"); a search for `startswith` found the rest. All
  follow the new letters.
- **The published tour pages were a hand copy.** `drafts/interactive-tour/page/` kept the old tags because the stage
  wrote to `out/` and nothing copied it over. The copy is now a step of the stage, and the pages are its outputs.
- **The README's headline F1 was one run's best metric.** "Symbols F1 0.97, connections 0.89" came from the single
  round-2 run (symbols located, class ignored) and sat beside a five-run review load. The five-run means are 0.93
  and 0.87; the README and the deliverables table now say those. The claim checker found it on its first run.
- **7 streams disagree on their tier.** The review queue puts them in amber; the plant model's per-item rollup says
  "n/a", so the pipeline's summary line reads 669 amber against the README's 676. The README matches the queue a
  reviewer works from. Not fixed here.

**Why:**
- **A checker, not another document.** The reviewers' strongest findings were drift: numbers and screenshots that
  stopped matching their sources. `check_claims.py` makes that a test (it runs in CI), and it's what a skeptical
  reader's agent can run in under a minute without trusting the prose. Claims no result file holds are listed as
  "prose only" instead of passing quietly (one: Figure 10's first run, 10 of 21).
- **AGENTS.md asks for nothing on the author's behalf.** It lists the checks and the limits to report, and asks the
  agent to tell its user what fails. A file that steered an agent's verdict would deserve to be ignored.
- **Rejected:** keeping indicator letters for the replay points' names (entry 51's reason). The HMI shows whatever
  the tag is called; there was no reason for the field device's tag to be wrong to keep a display name.

**Native acceptance, the same day:** the revision D project went into the local disposable gateway with
`build_gateway.py --fresh` (1,121 tags, 0 failures, 0 read-back differences). The verifier caught 5/5 planted faults
and passed V1–V9 on `1b9e815`; the browser contract passed 24/24 routes and 284/284 clicks with no console errors; the
header's alarm count matched the alarm table running, stopped and restarted (4/4, 8/8, 12/12). This time fault 6 was
also watched on screen: PT-107 red at 3,000 kPa g, two alarms in both the header and the table. The README's
overview screenshots are from this run ([receipt](../out/ignition/gateway/receipts/native-revD-20261029.json)).
Not read back by the models yet: revision D is a tag-letter change on the sheets revision C's runs already read.

**Lesson:** a pipeline is only as honest as its list of inputs. Two outputs went stale here without anything turning
red, and both times the missing piece was a dependency the code had and the manifest didn't.

**At your plant:** when you retag, search the code for logic that keys on tag letters (alarm grouping, display
filters, historian queries), not just for the tags themselves. A rename tool finds names; it can't find a rule.

---

## 62. Give a stranger's agent the repository and see what it can do

**What:** 2026-10-29. A fresh agent with no context got a clean clone of public main and the brief of another
engineer's coding agent: "can I use this on our own P&IDs to get a starting asset model into Ignition?" It worked
offline, read the agent-facing files, ran what it could and reported where it got stuck. Its findings, checked
against the files, drove this change: a runbook for one drawing, `examples/own-drawing/`, that runs end to end from
a clean clone.

**What it found (each confirmed before changing anything):**
- **No extraction to start from.** The intake tool wanted "an existing extraction", and a clean clone has none
  (model run records aren't committed). The agent had to hand-write one. The example now ships the recorded GPT
  extraction of public sheet 0, made with the method behind the results, and a manifest pointing at the sheet
  already in the repository: two commands give a 445-row review bundle with Ignition tags and PI staging files.
- **A tool listed for your drawings that isn't one.** The README put `build_gateway.py` under "tools for your own
  drawings"; it builds this repository's Tennessee Eastman demo. The Ignition step is now importing the bundle's
  `ignition/tags.json` in Designer, and `build_gateway.py` is listed with the research record.
- **Stale numbers in the file written for agents.** AGENTS.md still quoted the single-run F1 (0.97, 0.89) that
  entry 61 corrected in the README; the claim checker only reads the README. AGENTS.md now names the claims without
  numbers, so there is nothing there to drift. It also said Python 3.11+; the README and CI say 3.10+.
- **Passing tests that print FAIL.** The claim checker's deliberate-failure control printed its table into the
  log. It is now captured and asserted instead.

**What the agent missed, and the runbook says:** the line tracer is not tied to the OPEN100 folder; `PID_SHEETS_DIR`
points it at any folder of PNGs, and with no answer key present it reproduced the recorded 345 links on sheet 0
exactly. It did get one thing right that the README had blurred: the one-sheet workflow
(`site_extraction_workflow.py`) uses a simpler recipe than the results (whole sheet, no tiles, no tracer). The
runbook names both routes and says which one the numbers measure.

**Its verdict, kept as it said it:** the method, the file formats, the review and mapping loop and the checking
habits generalize; the accuracy numbers, the tracer settings and the risk tiers (tuned on OPEN100) and everything
that needs process data don't. About half a day to a day to a reviewed draft of one drawing, most of it review;
days to weeks to a usable Ignition model with real bindings, most of it the plant's own engineering.

**Lesson:** the author can't read their own repository cold. An agent that can is cheap, and it found in five
minutes what a stranger would have found by giving up.

---

## 63. Prove every way in, and time one

**What:** 2026-10-29. The README said the project starts "wherever you are", and only the drawing-image route had
a runnable path. Each other way in the code implied was built out or proven, with a runnable example under
`examples/`, a test, and a row in the README's "Start wherever you are" table. A fresh agent then timed the
drawing route on a sheet it was handed as its own, and a client-facing report was added as the example deliverable.

**What each one showed:**
- **Timing (one model call, approved):** PNG to review bundle in 88 seconds of commands (extraction 36 s, tracing
  4 s, intake under 1 s) on OPEN100 sheet 8, everything first time. Scored afterwards against the sheet's key it
  matched the published mean for that sheet (review load 11.0 against 10.99). The earlier estimate of half a day to
  a day was mine and was wrong: it priced in a stranger learning the repository, not the work. Review time is still
  unmeasured.
- **DEXPI file to twin, no model at all** (`dexpi_to_twin.py`, `examples/from-dexpi`): lossless against the key on
  three public DEXPI sheets (zero corrections, F1 1.0). What it loses is listed: six-class collapse, tees, direction,
  attributes, hierarchy. A drawn label isn't a governed tag: one sheet labels five manual valves with pipe-spec codes,
  and the bundle flags them as duplicates.
- **Written description to exports** (`examples/from-description`): `generate.py` only accepted Tennessee Eastman's
  symbols and hand-placed positions, and treated a valve as a valve only if it had a simulator index. It now takes
  any model in the same schema: more symbol types, valves from `final_elements`, units placed automatically in flow
  order (labelled as such), `--out`. The TE outputs are byte-identical. The first automatic layout put every unit
  off the right edge (a recycle loop inflated the column count) and the second stacked them in one column (utility
  feeds counted as starting points); both were caught by looking at the render, not by a test. The drawing itself
  still needs a hand-written drafting layout, and the guide says so.
- **Loop list to loop audit** (`loop_audit.py`): any `controller,measurement,output` CSV against a drawing key gives
  0 of 19 on revision A and 19 of 19 on revision D, as the original audit does. On revision C it is more precise:
  the controllers were drawn but read indicators, not the listed transmitters, so it says "partly drawn" instead of
  "not drawn".
- **Historian CSV** (`csv_normal_bands.py`, `csv_replay_server.py`): the bands from a CSV export of the TE runs
  match the committed bands within rounding and give the same fault-6 result; a blank or "Bad" cell is served as
  Bad quality, never zero.
- **Vendor evaluation** (`evaluate_vendor.py`): any tool's output scored with a perfect, a deliberately wrong and an
  empty answer beside it, refusing to report if the wrong answer scores above F1 0.10. On the round-5 runs it
  reproduces the published 20.1 exactly.

**Bugs the timing run found:** the scorer's command line scored a run record as zero instead of reading its
`prediction` (it now unwraps it, or refuses a file with no symbols); the runbook didn't say where the manifest goes,
that `--drawings` is the file name, that both commands need the requirements, or that the example's output folder
can't be reused. All fixed.

**Labels:** `data/script_index.json` gives every script a kind (tool, check, support, research record) and each
tool a guide; `docs/SCRIPTS.md` is generated from it and the scripts' own docstrings, and a test fails if a script
is missing, gone, or a tool has no guide: 20 tools, 6 checks, 8 support modules, 76 research scripts.

**The deliverable:** `deliverable_report.py` turns a bundle into the page a client reads first: the drawing with
every extracted item boxed, the 46 of 445 rows to check first and why, the hierarchy, next steps and limits
(`examples/own-drawing/deliverable/REPORT.html`).

**One near miss:** re-running the recorded round-trip scoring to show the scorer change didn't move it emptied the
revision A tables, because those run records aren't in this checkout. Restored from git; the stages whose runs
aren't local were recorded on the strength of the diff (the scoring function is unchanged; only the command line
moved), and that is what this sentence says.

**Lesson:** "it supports X" means nothing until X runs from a clean clone. Every one of the six ways in needed new
code or a fix before it ran on someone else's input, and the one I estimated, I estimated wrong.

## 64. Review everything, measure what the graph says, and widen the corpus until it fails honestly

**What:** 2026-10-29. Every feature now has an entry in `data/features.json` (what it is for, who it serves, its
guide, example outputs and tests), and every review is recorded in `data/reviews.json` with the hashes of the files
it checked, so "proven" means a passing independent review that still matches today's outputs
([FEATURES.md](FEATURES.md)). Four review rounds by fresh Claude agents, with Codex (another model family) on the
opportunity screen and the estimator, recorded 89 findings in rounds 2 to 4 (46 should-fix, the rest nits); every should-fix was fixed or is listed open. Proven features went from 2 to 8 of 16 in
this batch; the rest are in a final confirmation round.

**The statement review measured something the earlier checks couldn't.** Every graph claim rendered as a plain
sentence, and a seeded, stratified sample checked against its source by an independent agent
([statement review](../examples/statement-review/README.md)):
- The Bayer model, written from the CSB report: 5 of 57 sentences don't match their cited source (8.8%, 95%
  interval 3.8–18.9%). Five real model errors that the structural and figure checks had passed.
- The sheet-0 extraction: 3.3% read as written, 40% read as a person would. The extracted "links" mean "on the
  same drawn line network", which is the public answer key's definition, not "a pipe runs between them". Only 5
  of 27 sampled links were next to each other.

**So the graph now has layers** ([GRAPH_EXPORT.md](GRAPH_EXPORT.md#three-layers-for-the-lines)): pipe segments and
their tees (`piped_to`, junctions by kind), line networks (`on_network`), and the network pairs the key scores.
Instrument connections, actuator stems and nozzle stubs are their own edge types, because the first layered review
found them read as pipe (3 of 15 pipe sentences wrong). After the fix a fresh sample had 0 of 15 wrong in every line
layer. That review also caught plant tags read as ISA letters: MSBV, the main steam bypass valve, became "a
moisture valve". Now a tag whose letters start with a system code on its own sheet isn't read as ISA. Each
evaluation now names the layer it measures ([EVALUATION.md §7](EVALUATION.md#7-which-layer-each-evaluation-measures)).
One correction came from outside: the PID2Graph key *is* a graph with connector nodes, so pipe truth can be derived
from it. That gave the first real-world pipe-layer score: OPEN100 development sheets 0.914, holdout 0.898 (only
partly blind, because one error class was first noticed on holdout images).

**The export no longer drops anything silently.** A review found nested records, verification caveats, a second
check's evidence and the model's own notes missing; the TE export went from 336 to 495 claims, and a test now fails if
any sentence in a hand-built model doesn't reach the graph outside the declared exclusions. Two missed cases surfaced
on the way: all 8 TE cascade loops had no `sets_point_of` edge. A `--profile core` export keeps what a change system
needs (identity, settings, impact relations, sources) and counts everything it leaves out.

**The corpus grew until things failed.** Twelve openly licensed families were staged (527 MB, pinned by hash) and 29
cells added to the [matrix](GENERALIZATION.md), each criterion fixed before its run:
- The DEXPI reader read no controller in any DEXPI 1.2 export. After fixes developed on reference files and checked
  once on held-out vendor exports, it reads 43 of 44 across SPPID, Comos, AVEVA and AutoCAD (the held-out score
  before the remaining gaps were fixed is kept in the ledger).
- Historian bands flagged normal running on every real source. A drift-aware default passes PRONTO day 3 and the
  HAI testbed but fails three untouched cyclic sources (1 of 21 runs). Neither method handles cyclic processes yet,
  and the README says so.
- Exported vendor renders and agent-keyed scans fail the pipe layer. Agent-made keys are labelled as weaker than a
  human key and never counted as an independent source.

**Estimates are first drafts and say so:** a banner and grade before the numbers, the assumptions the figure rests
on, and the data to collect (and where) to replace each one, generated from what the run actually used.

**Six people from LinkedIn, role-played:** a solo plant engineer, an Ignition integrator, an energy manager, a
process-safety engineer, a hiring manager and an ML researcher. They found the first screen too dense, the headline
stronger than the evidence ("a tagged asset model for Ignition" when the tags are placeholders), the LOTO warning
three clicks from the artifact, no Windows or scanned-PDF path, and a headline split that is really a same-plant
validation set. The README now opens with what goes in, what comes out and how long, and safety warnings sit on the
isolation CSV and image themselves.

**Recorded, not re-run:** the OPEN100 direction spot check (model calls) was marked current after the twin's
`variable` fields changed for four instruments, because neither of its scripts reads those fields.

**Lesson:** a claim checked only against the thing that produced it isn't checked. The statement review, the corpus
and the role-played readers each found what every internal test had passed.

## 65. Finish the tool handoff and check the public story

**What:** 2026-10-29. Continued the same evening's handoff: scan cleanup, the pipe layer, cyclic historian data,
review metadata, food-plant questions, estimates and reproducible predictions. The aim was a coherent set of
prototype tools a visitor can try and check, with the research record kept distinct from general-purpose tools.
The README links each entry point to a runnable example; [DELIVERABLES.md](DELIVERABLES.md) carries the full output
inventory, [SCRIPTS.md](SCRIPTS.md) identifies the 27 tools, and [FEATURES.md](FEATURES.md) records which exact
examples have passed an independent agent review. That status is software evidence, not a person's sign-off.

**Scan cleanup helps some scans and hurts another.** The optional `scan_cleanup.py` wrapper is now wired into
matrix row 1 and documented in the own-drawing runbook. On the OPEN100 synthetic scans, with answer-key symbols
supplied, network F1 is 0.894 / 0.818 / 0.753 for L1 / L2 / L3; the original tracer gave 0.877 / 0.566 / 0.387.
The real OMRE quadrant goes the other way, 0.561 to 0.522 against an agent-made key. Cleanup stays opt-in; the
original tracer default is unchanged. These are deterministic oracle-symbol checks, not new model-extraction
runs, and do not replace round 4's pre-registered results.

**Pipe scores improved, partly because the scorer was wrong.** DEXPI 1.3 pipe F1 is now 0.916, OPEN100 development
0.931 and validation 0.912. The vendor-render pool is 0.776 and still fails the 0.88 criterion. Its SPPID subset
became development data: the scorer-only junction correction accounts for 0.679 to 0.852, about two thirds of its
total gain to 0.939. Reserved Comos renders still score 0.264; the one AVEVA render has just one pipe segment.
The pooled result mixes splits and is not a held-out accuracy claim. OPEN100 is only partly blind, and the derived
truth changed too. [EVALUATION.md §7](EVALUATION.md#7-which-layer-each-evaluation-measures) gives the current numbers
and limitations. The PID2Graph paper's metric was checked directly: edge mAP on individual graph edges differs
from this project's F1 on network pairs or derived pipe segments.

**Cyclic history is a limited result.** CSV `auto` selects daily-cycle bands only with sufficient periodic evidence;
drift remains the fallback. The 2018 BattLeDIM development windows pass 8 of 14 cases. The reserved 2019 year,
from the same water network, passes only 6 of 19: 13 leaks detected, seven windows with excessive pre-leak flags,
and detections delayed roughly 14 to 120 hours. This is not a new-plant test or an early-warning claim. The guide
now says history can highlight unusual changes. Independent probes also found accepted NaN/infinite timestamps
and finite inputs whose derived values overflowed: these now fail explicitly before writing an invalid report.

**Review information reaches the exports.** The tag-based safety floor marks 25 instruments and moved 22 from
green to amber; it does not catch untagged valves, manual block valves or every NC/MOV/AOV convention. Ignition
types are keyed by kind (12 instead of 37 on the extracted twin), with per-instance engineering units when the
model supplies them. Ignition documentation and PI descriptions carry review status, risk and applicable safety
notes. Unit labels do not perform conversion or validate a source signal's units. Pipeline confidence now names
the seven unrated cross-sheet links that the review queue puts in amber. All 2,886 extracted items remain
unverified until reviewed; risk ranking does not upgrade their verification status.

**The estimator's checks now constrain the calculation.** Redundant electricity forms must constrain the annual
energy actually used, including complete ranges and zero-hour cases. Ambiguous partial load increases are refused
with explicit alternatives. Incremental steam enthalpy can be smaller than gross steam-production heat; the E7
assumption names the actual turbine inlet/outlet boundary. Site notes and measurement provenance survive both
JSON and Markdown. A fresh reviewer reproduced all 12 example files, passed 37 tests, and checked 400 scalar
endpoints and 10,000 mixed saving/load scenarios against the reported intervals. These are first-draft estimates,
not measured plant savings. Ten food-process questions and a multi-site rollup bring the question registry to 50;
the food model and its 24 findings are explicitly illustrative, not evidence from a food plant.

**Fresh reviews found faults the existing suite missed.** The graph validator accepted duplicate edge IDs,
invalid review states and dangling stream endpoints; it now refuses them. All eight TE cascade statements were
being checked against the wrong model field, and nested source paths caused false mismatches: the source checker
now reports 576 matches, seven not checked and no differences on the TE graph, with negative controls. Safety
sentences now identify tag-derived, unverified screening. The sheet-0 population is 1,087 statements (163
attributes, 188 identities, 736 relations); older seeded samples and their measured error rates are retained as
historical samples rather than silently redrawn. A DEXPI report wrongly said unplaced items were excluded from
platform exports; the report now describes the automatic fallback placement that the code actually uses.

**The headline can now be re-scored.** Preserved research working copies contained the round-5 and TE parsed run
records that were missing from the earlier export. Recovered 391 parsed predictions, with raw-byte and exported
hashes in [predictions/RECOVERY.json](../predictions/RECOVERY.json); an independent reviewer verified every source
hash and slim export. Raw model text stays outside git. There are now 1,123 prediction files across 101 labels.
`rescore.py --check` reproduces 30 of 35 result tables, including the round-5 headline replicates and both TE
round trips. Twenty-three match current formats and seven match explicitly supported historical formats; no
metric differences are discarded. Five earlier diagnostic tables still report GAP. A recovery receipt proves
which local records were exported, not provider attestation or a fresh commercial-model run.

**Four LinkedIn readers, role-played by fresh agents:** a solo plant engineer, a controls integrator, a manager and
a skeptic. Their checks removed unmeasured time-saving claims, clarified that the review CSV cannot add an omitted
symbol, corrected an old PI file list and explained that valid CSV review rows can persist even if another row
fails. A rebuilt extraction needs review reconciliation by source symbol IDs; decisions are not automatically
merged. Generic drawing bundles do not generate the research demo's mimic, 3D or LOTO outputs. The delivered
one-page report was regenerated and inspected in a browser with its draft banner and review steps visible.

**Verification and remaining boundaries.** The full matrix is 63 pass / 23 fail / 8 n/a (94 cells), compared with
61 / 24 / 8 before this batch; BattLeDIM 2019 adds one failing cell. Every cell records the current tool hashes,
and all 52 pipeline stages are fresh after rebuilding the affected exports and renders. The claim checker now
also checks the six new README matrix claims against the result JSON. It checks agreement with committed evidence;
the separate rescore check regenerates results from predictions. No commercial extraction, human timed review,
operations review, PI import or own-drawing native gateway import was run in this continuation. Historical native
gateway receipts remain historical. Median-of-three drift smoothing and making scan cleanup the tracer's default
remain unadopted choices; no LinkedIn post was published.

The 55 registered test scripts passed after the final matrix freshness test was rerun (its first invocation
preceded the last cell refresh); two Windows symlink subcases require Linux CI. The claim check reports 41 numeric
matches, one prose-only claim and zero failures. All 16 feature entries have current passing independent reviews
of their registered example outputs, with limitations attached. That does not mean every possible input or
organizational workflow has been validated.

## 66. Keep the questions, answers and next owner together

**What:** 2026-10-29. Extend the tools from producing a draft model to retaining the engineering investigation
around it. The [context register](CONTEXT_REGISTER.md) accepts a model, questions and original local documents,
then keeps answers, explicit assignments, source-match reviews and plant-truth judgments separately. It emits a
readable report, dated history and versioned JSON with enriched graph and questions. No model call or account is
needed. Initial owners and reviewers remain unassigned; the tool does not invent responsibility from a file date.

**The question engine now has a demonstrated return path.** The
[Bayer E18 example](../examples/context-register/bayer/README.md) runs the actual engine and retains a partial
interpretation of the original CSB report's temperature-control narrative. Its six asset/stream references,
three collection prompts, decision rule and limits survive in the register. A description of intended operating
sequence does not establish simultaneous duties, an energy opportunity or savings. Answers do not automatically
complete collection prompts. The example remains proposed, unassigned and unknown for plant truth.

**Expand linked evidence, rather than count the same plant twice.** The
[PRONTO packet](../examples/context-register/pronto/README.md) connects four existing original documents: the
technical report, alarm workbook, operation log and day-3 event journal. It has 22 proposed statements over 21
questions and 11 asset identities. Every original byte hash is checked; the derived transcription key never
substitutes for a missing original. An independent agent checked all 22 facts against the actual cells, records,
PDF text and a separately rendered schematic. Three disabled-limit controls stay disabled; uncertain numerical
units and the FIC301/FIR305/FT302 labels stay unresolved. No alias is guessed. This adds linked-document workflow
coverage within an existing source family, not an independent plant or a human-reviewed answer key.

**A source revision reopens its dependent answers.** Each answer records exact question and asset content,
incident relationships, source revision, raw-byte hash and locator. A refresh compares that snapshot with the
current inputs; an old CSV cannot approve new evidence. Synthetic copies of the PRONTO report reopened exactly
six answers, leaving sixteen unrelated answers current; an alarm-workbook revision reopened seven, leaving
fifteen current. Both retained the decision history. An offline invented packet also exercises accepted source
interpretation, conflicting values, missing data and unanswered questions. Its fictional people and approvals
are explicitly labelled. Plant truth is unknown throughout these examples.

**Independent probes changed the implementation.** Early versions could overwrite a register saved under an
alternate output filename or clobber a source through a hard link. They also accepted correctly rehashed but
malformed historical identities, and silently trimmed an asset ID whose references did not match. Those cases
now refuse before output writes. Exact IDs, attributed dates, record structure and evidence bindings are checked
separately from hashes. History hashes are consistency checks, not signatures or tamper-proof records. Exact
source reversion matches the old snapshot again; there is no watcher, expiry or record of intervening changes.

**A young engineer needs a decision and an organization around the tools.** A fresh reader found that collection
requests, walkdown guidance, mapping previews and technical review already exist. The missing step was a compact
[first-pilot brief](../examples/first-pilot/README.md): choose one operational decision, involve its sponsor and
operator, record a baseline and trial observation under comparable conditions, then decide continue, change
scope, stop or insufficient evidence. The site supplies authority and thresholds. The brief is a manual working
record, with no approval or measured benefit in its blank fields. Retain unsuccessful attempts and a receiving
owner as well as the successful result.

**Maintenance and handoff are explicit.** Refresh deliberately against released source revisions, retain the
register and backups, and hand over stable identities, unresolved states, original evidence and full history.
The neutral interchange is `context-register-1` plus `twin-graph-1`; a receiving system needs a reviewed adapter.
There is no live sync or verified downstream integration. The earlier statement-review CSV remains a separate
workflow with a documented limitation: its semantic statement IDs do not bind a changed source revision, and
those approvals are not migrated into this register.

**Validation boundary:** deterministic software examples and independent agent review. Engineering adoption,
review time, source authority at a real site, operational acceptance and measured business value remain untested.
The next useful evidence is one engineer using the packet for one real decision, including a recorded result
that it did not help. Additional synthetic examples cannot establish that outcome.

All 57 registered test scripts passed locally; two Windows symlink subcases remain for Linux CI. The new controls
include 32 register tests and three example tests. The claim check still reports 41 numeric matches, one prose-only
claim and no failures; the existing 52 pipeline stages remain fresh. All 17 feature entries now have a current
passing independent agent review of their exact registered example outputs. The new receipt also records the
primary-source checks and remaining limits; it is not human adoption or an operational acceptance record.

## 67. Explain the engineering foundation and each piece's job

**What:** 2026-10-29. Reframe the README around engineering context an organization can inspect, maintain and
own. A drawing is one view into the assets, relationships, evidence, open questions and decisions. Future
manufacturing applications are the intended use of that foundation; the present evidence remains the prototype's
public-source software checks and recorded lab demonstrations.

The entry page now explains nine contributions: intake; the asset/relationship model; source review, loop checks
and signal mapping; the question engine; historian analysis and impact estimates; retained context; a bounded
pilot; portable handoff and staging; and reproducibility/change checks. Each contribution links to a runnable
route or its guide. The diagram shows the engineering investigation and its source refresh, with controls records
and recorded data joining the review route. The prose makes clear that a written description needs an authored
model and that historian CSV analysis can be used on its own.

**The organizational transition has a boundary.** The local tools can supply a complete, inspectable packet.
Ongoing shared use adds source authority, identity reconciliation, access, accountable review and decisions across
projects. The README names those responsibilities and the neutral handoff requirements without claiming a hosted
service, authenticated approval, automatic monitoring or an available downstream adapter. No product-specific
commercial material is included in the public repository.

**Reader review changed the copy.** A fresh young-engineer/controls/manager reading removed an unsupported claim
about what most digital-twin projects do first. It also caught wording that could make every input route sound
like a model builder; the final text separates controls and historian analyses from model creation. The old
diagram could imply that an arbitrary drawing bundle produces working screens and inherits the demo's gateway
acceptance. Its replacement and the platform section now keep that lab evidence with its actual demonstration.
The young-engineer and independent technical readers checked the final framing against the guides; 26 links in
the revised material resolve, including the renamed platform-section anchor.

This is documentation work. The claim check still reports 41 numeric matches, one prose-only claim and no
failures. No model, method, benchmark, runtime receipt or tool implementation changed. The legacy statement-review
revision-binding limitation remains documented; this edit does not fix it or upgrade historical approvals. No
LinkedIn post, real-site pilot, measured adoption or downstream import was performed.

## 68. Make source changes and generated outputs fit one reviewed context

**What:** 2026-10-29. Define the organizational lifecycle, close the legacy statement-review evidence-binding gap,
and add a manufacturing source family to the context examples. The intended authority is one central reviewed
context. Specialized tools consume versioned snapshots and return draft outputs, questions and proposed changes
through engineering review. The [lifecycle guide](CONTEXT_LIFECYCLE.md) specifies that contract and distinguishes
the implemented local tools from an organizational service that remains to be built and accepted.

**Documents need different maintenance rules.** Original records keep their bytes, revisions, owners and controlled
references. Generated views keep their source snapshot, recipe, dependencies and release state. Authored documents
need explicitly managed sections, proposed differences and reconciliation of manual or concurrent edits. Incoming
evidence should be visible while review is pending. Local CSV acceptance is provenance, not authenticated authority
in a receiving organization. No document watcher, managed-section merger or live organizational integration was added.

Actual input shapes matter. `generate.py` and `question_engine.py` consume process-model or extracted-twin JSON;
the graph is not their general input. Graph export has no general inverse, and the context sidecar does not update
the original generator model. The guide therefore requires declared projections, loss reports and readback checks.
It sets an acceptance target for one source-backed change through a hub, one generator, reviewed release and the
next revision, including rejection, concurrent edits, interruption and rollback. That organizational-context round
trip has not been performed. An asset-count match would not establish that claims and history survived it.

**Close an actual unsafe reuse path.** The independent pre-change reproduction kept a statement's semantic ID and
text unchanged while moving its source from one document revision/page to another. The old CSV applied successfully.
New packets and browser downloads now bind the complete canonical graph, actual machine-check model, supplied
original image/report bytes and exact statement/source/target/layer details. Apply rereads those files and refuses
any reviewed row with a stale, missing or edited binding before writing output. Sampling preserves bindings;
sampling a legacy packet does not manufacture them. Historical samples and scores remain unchanged and scoreable,
but their unbound verdicts cannot be applied to today's graph. Notes now travel verbatim with checks and events.

Independent adversarial review found two additional clobber cases: sampling onto its own full packet, and a source
image named as a generated crop. Both now refuse without changing input or destination bytes. Render stages its
dynamic crops before collision preflight, including hardlink/symlink aliases. A first collision implementation was
quadratic in file count and made the actual full drawing run impractical on Windows. It now scans paths and file
identities once; a 600-target regression control preserves that bound. Ordinary filesystem failures can still
interrupt publication, so prior records and backups remain necessary.

The [bound sheet-0 packet](../examples/statement-review/bound-sheet0/README.md) retains a new 12-statement sample
over five relationship layers, the original drawing crops, and one explicitly fictional `unclear` verdict. Three
standard-library integration controls exercise actual CLI application, note/value preservation, and refusal after
copied source or graph changes. This is evidence of software behavior, not another accuracy review. Whole-graph
binding is intentionally conservative: unrelated assets, statuses and events reopen the packet. The context
register's separate selective dependencies are unchanged. Hashes are not signatures; exact restoration can match
an old snapshot, and neither tool monitors intervening changes or authenticates a reviewer.

**A different source family exposes a real revision problem.** The new
[NIST SMS Test Bed packet](../examples/context-register/nist-smstestbed/README.md) fetches two published device
configurations, an archived raw operating log and the upstream reuse notice. All four are pinned by immutable
revision, raw hash and byte count, with no originals redistributed. The same machine UUID links the configurations,
but a reused data-item ID changes meaning from tool number to accumulated program time. Observations stay scoped
to each revision. The raw log does not prove which configuration was deployed, so that question stays open.
`UNAVAILABLE`, numeric zero and a single blank program-name space remain distinct. No job or live machine condition
is inferred.

Discovery inspected these facts before packet acceptance criteria were written: this is a development example,
not held-out generalization. Ten proposed answers over eight questions produce five partial and three needs-data
states; all questions need an owner and plant truth remains unknown. Copied older-config, later-config, raw-log and
unrelated-notice changes stale exactly 3/3/4/0 answers while preserving history. Independent review checked ten
primary XML/raw fact groups, original hashes, lifecycle/refusal controls and missing-original failures. The derived
key is never substituted for unavailable original bytes.

The three multi-document context packets are listed separately in `data/corpus.json`. The eight-workflow matrix
still has its existing 94 cells; the new packet is not counted as another extraction benchmark. Its packet-local
registry reuses the pinned-file fetcher without changing existing matrix recipe hashes. Prototype source checks,
independent agent review and a clear integration contract do not establish human adoption, review-time savings or
an organization's continuing document-management outcome.

A young-engineer/engineering-manager reader pass also caught a missing connection to the already implemented
`apply_review.py` model-correction route. The lifecycle table and pilot guide now explain that limited local
return path, its in-place/partial-row behavior and the separate organizational approval needed on transfer.
The README's older class-wide "public drawings only" wording now distinguishes drawing validation from the
other public-record workflows. These edits make existing capabilities discoverable; they add no hub adapter.

All 58 registered test scripts passed locally; two Windows symlink subcases were skipped and remain for Linux CI.
All 17 feature entries have current independent review receipts for their exact registered outputs. The narrow
matrix receipt checks only the added context registry and preserves prior result/review scope; no 94-cell rerun
is claimed. The claim check still has 41 numeric matches, one prose-only claim and no failures, and all 52 pipeline
stages remain fresh. These are offline software checks, with no new operational acceptance or measured adoption.

## 69. Preserve known engineering meaning and retained review history

**What:** 2026-10-29. Two maintenance failures found while following the document-to-maintained-context route:
known unplaced instruments and valves lost their semantic roles at graph export, and a context refresh could
silently replace retained history. The prospective checks are in [GOAL.md](GOAL.md#maintenance-acceptance-retain-unplaced-asset-semantics-and-context-history).
These are development repairs to inspected examples, not new blind extraction results.

The DEXPI reader already retained these items and their source claims. The exporter ignored an explicit
`unplaced.kind`, usually calling the node a generic line item. The original role and controller reference survived
as attributes, but asset queries and plain statements used the wrong role and the known control path was not
traversable. The [actual-source example](../examples/graph-export/unplaced-dexpi/README.md) follows a public
PID Toolbox flow loop and a Comos unplaced instrument through reader model, graph and statements. Placement stays
unresolved. A controller's interpreted output relationship is not a fresh verification of physical signal direction.

An in-memory diagnostic over all 220 already-inspected cached XMLs produced 214 reader models and the same six
known duplicate-ID refusals. Before the repair, 87 of 88 unplaced items lost their declared role: 52 instruments
and 35 final elements, in 55 files across four exporters. Forty-four recorded unplaced control endpoints across
33 files had no corresponding control edge. After the repair, all declared roles and those 44 relationships are
represented, with no new export failure. The exporter adds no unit, physical location or plant-truth verdict.
Original reference claims, source and uncertainty remain. Missing, ambiguous, incompatible or malformed nonempty
references refuse before output writes. Unknown explicit roles retain a generic fallback and their original claim.

No parser, matrix criterion or historical score changed. The existing matrix tool-hash check remains current:
graph export is not an exercised dependency of its current cells. Its 94 cells therefore retain their recorded
63 pass, 23 fail and eight n/a results; no new matrix run or placement pass is claimed. In particular, a retained
unplaced item is still unplaced.

**History needs an explicit continuation.** A real CLI reproduction using the pinned NIST originals first saved ten
proposals, then silently erased them when refreshed without `--register`. A second reproduction replaced an
eleven-decision history with an older ten-decision register. The new guard validates the destination and requires
an explicit register once either decision or ownership history exists. Every retained history must remain an
unchanged ordered prefix of the computed result. Older, divergent or invalid destinations refuse before any write;
a deliberate fork needs a fresh directory. Initial apply into an empty prepared register still works.

The [NIST history check](../examples/context-register/nist-smstestbed/check_history.py) exercises the actual CLI
and originals in disposable folders: omitted-register and older-register refusals preserve all working files,
current-register refresh is byte-idempotent, and an explicitly separate older-history fork works. A synthetic note
revision creates the eleventh proposal; it does not invent a human review. The original documents and historical
packet report remain unchanged. Ownership-only and divergent-history controls belong to the core regression suite.
The guide explains recovery and the difference between continuing and forking.

These guards concern a single local invocation. They add no automatic merge, authenticated authority, concurrent
writer lock, atomic multi-file publication or live integration. Independent review passed 50 graph and 26 history
adversarial controls, the original-source checks and all 31 graph, 43 context and three existing example tests.
The exact nine graph and 17 context outputs have current hash-bound receipts, with the earlier outputs unchanged
and their prior review scope preserved. All 17 feature entries have current software evidence. The full local
suite passed 58 registered scripts with two Windows symlink subcases skipped; Linux CI must check those.

A cold reader clarified drawn connection direction versus logical control roles, and added the exact second-revision
apply command using the retained current register. The neutral lifecycle guide now also explains how existing
systems can retain execution/release authority while reviewed context supports investigation. Outcome learning
requires attributed execution and observations to return. No incumbent connector is supplied. Software preservation
and clearer responsibilities do not establish engineer adoption, review time saved or a successful operational decision.

## 70. Count omitted checks before calling the suite complete

**What:** 2026-10-30. The `8b90d3a` CI run completed all 58 registered scripts successfully, but its final
zero-platform-skip summary was not an exhaustive omission count. At least 12 unittest skips were visible in its
per-script last lines, and the DEXPI oracle printed that its check was skipped before returning normally. Other
successful scripts' stderr was discarded by the wrapper, so the old log cannot establish the total. The local
cached-data run and Linux CI had different coverage. Historical receipts retain their original, limited scope.

The runner now reads unittest's skipped-case totals from both output streams, including failure summaries. Explicit
platform notices identify operating-system restrictions; generic skipped-check notices have their own category.
Platform notices explain unittest cases rather than adding another case count. Additional notices can describe
groups, so they are not another unit-test denominator either. A successful script exit can coexist with omitted
cases. Any reported omission withholds the complete full-suite message; test failure and prerequisite exit meanings
are unchanged. No missing source or dependency is installed or fetched by the runner.

The known oracle early return is now a real unittest skip. This repair does not prove that an arbitrary test
program cannot silently omit work or fabricate a report. Tests with optional original-source caches can still
skip; preflight covers the declared required files and dependencies. Source-only still selects a narrower suite.
The reviewer, replication and entry guides explain those boundaries and how to inspect affected cases with `-v`.

The [offline four-child example](../examples/test-coverage/README.md) executes actual illustrative programs through
the runner: all checks execute; four class/method/subtest skips reported on stdout; a simulated platform restriction
plus an extra check notice; and a failure with a skipped method on stderr. Declared fixture counts are checked
against the real reports and the committed expected JSON. Only test selection and prerequisite discovery are
replaced; process execution is real. These are software controls, not another corpus benchmark or a plant review.

Independent actual-child controls reproduce four incorrect complete-pass cases in the earlier implementation,
including the missing-cache oracle path. The repaired reporting passed 18 independent controls covering class,
setup, method and subtest skips; both streams and multiple summaries; failures/errors/expected failures; genuine
platform-helper behavior under a planted privilege error; generic notices and prose negatives; and source-only,
preflight and exit semantics. The real three-sheet cached oracle also executes without skips, with its six input
cache files unchanged. The core runner controls now include the public process example.

**Make optional source preparation runnable.** Following the skip messages found that the DEXPI guide claimed
PyMuPDF was in `requirements.txt`, although the core file did not list it. A separate `requirements-render.txt`
now pins the locally tested renderer. Rebuilding all five configured public sheets into a disposable directory
with PyMuPDF 1.27.2.3 reproduced all 13 adapted files byte for byte. No source original or existing cache was
overwritten. The guide also replaces its error-free/perfect-conversion wording with the actual oracle-route
scope, points own-CAD users to the reader, and distinguishes ignored originals from committed derived examples.
This changes no adapter rule, drawing, model prediction, answer key, benchmark score or matrix criterion.

All 58 registered scripts passed in the local cached-data run. Its new summary reports two skipped unittest cases,
two platform notices explaining those same cases, and zero additional skipped-check notices; it correctly withholds
the complete-suite message. No optional-cache skip was reported locally. CI and other environments need their own
reports. All 17 feature entries have current independent output receipts; this increment binds the two repo-checks
outputs, 18 supporting files and the reviewed README section. The 94-cell matrix and its tool hashes remain unchanged,
all 52 pipeline stages are fresh, and the claim check still has 41 numeric matches, one prose-only entry and no failures.

## 71. Carry explicit model rejections into the next question screen

**What:** 2026-10-30. Following the review-to-question workflow found that the question engine ignored
`ops_review`. Applying three fictional rejections to the existing synthetic food model left the rejected power
meter, speed drive and heat-recovery unit suppressing questions. The independent baseline reproduction kept all
24 findings unchanged; removing only those three records as a diagnostic control produced 27. K-201 also remained
absent from the existing model-wide C12 question. These are software controls on invented equipment, not a new
plant, human review, corpus family or accuracy measurement.

The engine now builds a separate active projection. Explicitly rejected records cannot trigger or suppress a
question, supply evidence or collection locations, satisfy required model kinds, or carry a relationship path.
Source bytes, rejected records and review history are retained. Non-rejected children remain eligible without a
rejected owning unit, parent or stream; no replacement is inferred. Ordinary unresolved references retain their
previous behavior. Missing/unverified review remains eligible and is not approval. Malformed review metadata
refuses before output writes. JSON and Markdown report the recorded exclusions; empty extra fields are omitted
so the earlier unreviewed screens and roll-up reproduce unchanged.

The [offline refresh example](../examples/opportunity-screen/review-refresh/README.md) uses the actual review and
screen CLIs on a temporary model copy. Rejecting JT-201 adds K-201 to C12's triggers; rejecting SC-203 opens E29 at
K-203; rejecting HX-303 opens E31 and H6 at F-303. It checks the three new finding IDs and C12 membership separately,
repeated-review byte stability, explicit reconfirmation restoring the questions, retained history and unchanged
source bytes. Its committed screen selects only those four question types. The original full food screen and all
other historical outputs retain their original population and evidence scope.

Independent review caught a bypass in the first repair: a supplemental loop row could recreate a rejected drive
as a controller and silence a live measurement question. The guard now checks rejected IDs and tags across model
sections, after accounting for live duplicate identities. A supplemental row does not override rejection. This is
not identity reconciliation: a live duplicate remains eligible and needs an engineer's review. The registered
question-engine script currently passes 51 tests, including the actual CLI packet and the new bypass regression.

A fresh cold reader found an additional documentation trap: when a finding disappears, its old source-manifest
binding is refused as an unknown question. The maintenance guides now say to preserve the previous packet and
manifest, withdraw absent IDs from the current locator bindings, then refresh with the existing register and no
old answer resubmission. Independent actual CLI checks on a temporary Bayer packet verify the refusal preserves
all bytes, the corrected refresh retains the original decision and ownership history exactly, and the removed
question is marked absent with its earlier answer stale. The pinned raw source remains unchanged.

The existing 94-cell matrix does not exercise the question engine, so this change makes no matrix generalization
claim and changes no cell, tool hash or criterion. All 52 pipeline stages remain fresh. Engineer adoption,
review effort and operational value remain unmeasured; the actual first-pilot observation is still open.

Final independent review passed 37 adversarial controls and all 51 registered question-engine cases, independently
reproduced the ten older outputs and the three new packet files, and bound those exact outputs plus the supporting
code and instructions. The local full runner passed all 58 scripts with two Windows symlink unittest cases skipped,
two platform notices explaining those same cases and no additional skipped-check notices. It correctly withholds
a complete-suite claim. CI and optional-source environments require their own coverage report.

**Separate export gap retained as N064.** The independent scope check applied fictional rejections of U-100 and
FT-101 to a copy of the TE model. The legacy seed Ignition exporter still emits that unit instance and instrument
tag, and the PI exporter still selects its element and attribute rows. Their descriptions carry the rejected
review annotation; exclusion is missing. The review-loop guide now limits its export-filtering claim to extracted
twins and states the legacy limitation. No gateway, import or source-model change occurred. The question repair
does not fix those exporters; they are the next concrete maintenance issue, with historical outputs preserved.

## 72. Make a reviewed seed bundle consistent across its outputs

**What:** 2026-10-30. N064 was more than a missing tag filter. An independent actual-CLI reproduction on a
temporary Tennessee Eastman model confirmed that rejected equipment and signals survived in Ignition, PI and
SVG outputs. Removing a unit from the source also left its old SVG in the output folder. These are software
maintenance defects on a simulation fixture, not plant discrepancies. Acceptance was written in `GOAL.md` before
the repair.

The seed generator now excludes explicitly rejected units, instruments, final elements and drawn streams.
Streams incident to rejected equipment also leave the overview, without inventing replacement connections.
Independently eligible children remain under an explicit `_Unassigned` display container: their original OPC
server/item and PI point claims stay unchanged, while exported/display paths change. Names are allocated from
the complete source before filtering, so rejecting a naming competitor cannot rename a surviving signal.
The complete model and its review history remain untouched. Reviewed seed streams now remain in the review CSV;
unreviewed streams retain the historical sheet's scope.

`seed_review_projection.json` explains each exclusion and old/new child path. `seed_export_manifest.json` records
the generated artifacts and their CRLF/LF-normalized content hashes. Later refresh checks those files, renders
the next bundle and retires unchanged obsolete managed files. It refuses manual edits, untracked artifact files,
invalid inventory ownership, known file/parent conflicts and source-model output collisions before writing.
Unrelated non-artifact notes remain untouched. Legacy folders need matching contents or migration to a fresh
dedicated output directory. The inventory is not signed provenance, organizational approval, a concurrent-writer
lock or an atomic filesystem transaction.

Independent adversarial review found four gaps in the first implementation: a hard-linked output could rewrite
an unrelated backup; a parent-path file conflict failed after earlier writes; Windows junctions allowed writes
through an alias; and a model stored at the inventory path could be overwritten. A final Windows control found
that a case-only inventory alias could retire a still-needed unit SVG. Preflight now refuses these cases before
any known fixture byte changes, including conflicting inventory spellings and existing native file aliases.
A distinct Windows short-name alias was unavailable on the host and is not claimed as exercised.

The final independent review passes 44 actual-CLI controls, the public three-file demonstration, all 30 generator
validation cases, 15 any-model cases and 15 PI-export cases. Separate identity controls check duplicate unit types,
colliding member descriptions and orphan names across two owners; surviving address, unit and read-only claims
are compared against the baseline. These are independent coding-agent software checks, not a person's engineering
review or a native platform import.

The [offline worked refresh](../examples/review-and-mapping/seed-refresh/README.md) uses four fictional review
decisions, checks all 13 earlier unreviewed artifact contents unchanged, repeats without changes, refuses a
manual SVG edit, then explicitly reconfirms the records. Original paths return, the obsolete unassigned SVG
is retired and intervening decisions remain in history. A separate cold reader executed the instructions.
The guide explains source-address claims versus deployment overrides, dedicated output ownership and migration.

This repair covers seed SVG/platform generation. Extracted twins retain their existing route, and the separate
gateway demo, P&ID drafting, mimic and 3D tools are outside this change. It supplies no live organizational
adapter, incumbent approval receipt, human adoption measurement or operational outcome.

The final corpus refresh executes 54 cells covering all 47 that depend on the changed generator; the other
40 cells retain their earlier records. Pass/fail criteria and the 63 pass / 23 fail / 8 not-applicable results
remain unchanged. Seed-generated file counts rise by two for the added sidecars, including the per-model DWSIM
counts; these are output-accounting changes, not accuracy gains. The three affected pipeline stages were rebuilt
through their actual declared commands, with no change to existing output contents; all 52 stages are fresh.

The first full-suite run passed 57 of 58 scripts. Its single failure was the older parent review-and-mapping
example's test counting the new independent seed example as parent-generated output. That comparison now excludes
only the named sub-example, whose actual CLI packet is already exercised by the registered generator tests.
The parent's seven cases pass, retaining exact comparison of its own generated files and rejection of unexpected
parent artifacts. No generator, matrix method or expected historical output was changed to resolve this failure.

## 73. Make maintenance records useful without inventing repair effectiveness

**What:** 2026-10-30. The context workflow now includes the original MetroPT-3 description and measured CSV,
already an input to the historian matrix. The question is practical: does a reported failure have enough linked
evidence for a maintenance-effectiveness review, and what record should the engineer request next? This is
development on an existing family, not a new global source family, held-out test or anomaly-method improvement.
Discovery facts were seen before the packet acceptance was written.

The original three-page PDF reports 15,169,480 instances at 1 Hz. The actual released CSV has 1,516,948 data rows,
timestamps extending into September 1 and nonuniform gaps. No downsampling history, timezone or healthy-state
labels are inferred. The PDF enumerates motor current before oil temperature; their named CSV columns appear
in the opposite order. Joining by enumeration would swap meanings. The failure table prints two different rows
as `#1`; its May 29-30 interval carries a literal `30Apr` maintenance note. These source observations remain
separate, without correcting dates or treating an interval end as verified repair completion.

The [maintenance packet](../examples/context-register/metropt3/README.md) has six source-specific questions and
twelve proposed answers. The questions use the existing context format rather than new automatic catalog rules.
Five need data and one is partial; all six need an owner. No human assignment, reviewer, acceptance, plant truth
or maintenance-success verdict is invented. The source-scoped APU identity is not a known serial number/current
train. Concrete collection prompts request the original execution record, affected asset, actual action/times,
resulting configuration and disposition, followed by comparable observations and an attributed effectiveness
review. A maintenance note or copied completed status cannot supply those facts by itself.

Independent primary review inspected all three rendered PDF pages and streamed the complete CSV. All twelve
final values and locators match. It caught four proposed-answer sentences that compared documents while binding
only one source. Each answer now states only its own source's facts; comparison stays in the question and its
collection rule. That scope matters: otherwise changing one document could leave a cross-document assertion
marked current through its unchanged other source. Separate claim slots also prevent a documentation acquisition
claim and released-file observation becoming an invented simultaneous dispute.

The packet retains raw hashes and exact page/table-row/CSV-line locators. The explicit existing fetch command
downloads the archive; offline preparation verifies and extracts only the two pinned original members, refusing
to replace a changed/incomplete cache. Originals stay ignored and unchanged. The default verifier checks their
hashes and computes the full CSV profile without reading the derived key or proposals. Optional PDF text checks
are explicit; table layout was separately inspected. Original-source checks never substitute a committed key.

Actual prepare/apply CLIs verify twelve bindings, byte-identical repetition, retained history and original bytes.
Labelled synthetic PDF/CSV revisions reopen exactly eight/four answers; changing only the effectiveness collection
request reopens its two answers. Stale-answer resubmission and missing originals refuse without output changes.
The registered example script passes six cases locally, including an optional actual-original workflow and
always-offline committed-packet/path controls. Environments without the ZIP report an explicit source-case skip.

Software review reproduced a hard-link defect in the first `check_packet.py --write`: expected-output publication
could overwrite an original after the preservation check and still report success. Both expected destinations
and their ancestors/known input aliases are now checked before either write, and originals are checked again
after publication. These local guards are not a concurrent-writer lock or atomic filesystem transaction.
Final independent software review passes 33 actual-source/CLI controls, including eight expected-publication
cases, and all six registered example tests with no local skips. A private harness's reason-text assertion was
corrected from `hash` to the actual `sha256` refusal text and that already-safe case was rerun; no product change
was made to accommodate it.
A separate cold reader executed the offline commands in fresh paths, reproduced the expected report/register
and could reconstruct the May question and next evidence request. This is AI software/reader evidence, not an
engineer's observed adoption, timed review, executed intervention or operational outcome.

The 94-cell matrix, its methods, scores and tool hashes remain unchanged; its MetroPT result is still a failing
development result. No matrix cell was rerun for this packet-only increment. All 52 configured pipeline stages
remain fresh without a rebuild. The corpus registry adds this linked-context packet separately from its 42
matrix inputs. The central-context/receiving-system adapter and real engineer pilot remain unverified.

The full local runner reports 58 successful script exits, zero failures, two Windows privilege-related unittest
skips and two platform notices explaining those same cases. The MetroPT original-source case executes locally.
This is not a complete-suite pass; CI and source-absent environments need their own omission report.

The first Linux CI run at `700b920` passed 57 scripts and failed the expected-publication regression. Linux
raises `NotADirectoryError` for a child beneath an ordinary file; Windows first reports that child missing and
then reaches the explicit parent-directory check. The unsafe path already refused, but its exception did not
match the intended consistent diagnostic. Preflight now normalizes that Linux error to the same directory
refusal. The real filesystem control is unchanged; a separately labelled Linux-errno control also exercises this
path on Windows. No source/output content, matrix criterion or assertion was relaxed to obtain a pass.

## 74. Keep the toolkit a starting point

The next useful result is an engineer's first evidence and decision packet around one problem. As people and
projects begin relying on it, the company needs a shared home for the information, relationships, decisions,
ownership and history. The toolkit should make that need concrete through useful work, rather than grow into a
local organizational-governance application.

The README now describes that journey explicitly. The pilot guide adds what happens after the first packet;
the context and lifecycle introductions place ongoing organizational responsibility in the company's shared
system. Operational execution can remain in its existing systems, and specialist tools can later consume
released context and return findings for review. No ready receiving-system adapter or measured adoption is claimed.
This increment changes documentation only: existing scripts, schemas, source packets, outputs and matrix results
remain unchanged. Further feature work should earn its place by helping an engineer start or demonstrate the
handoff, rather than recreating the company system inside this repository.

## 75. Make the first useful investigation easy to reach

A fresh local clone produced the public sheet-0 draft bundle, readable report and question screen using four
standard-library commands, without installing packages or calling a model. An independent reader ran the same
path. The screen contains three investigation prompts; its asset references still need checking against the
drawing. This is a demonstration on an existing development sheet, not a new extraction or transfer score, a
timed human review or measured adoption.

The own-drawing runbook now makes that existing path visible: skip dependency installation for the offline
example, create the draft, read the report, screen the model, then choose one relevant question with an engineering
counterpart. Copy its finding ID, asset references and collection requests into the existing private pilot brief.
The next step remains a shared company home for the context and decisions, not additional local governance code.

Two independent readers exposed consequential gaps in the old starter advice. The plant guide called all twelve
OPEN100 sheets sealed holdouts although six were development and six validation, with validation also used for
method selection. It routed authored models through optional drawing generation and paid re-extraction, implied
generic native screens/3D/replay from those models, and asserted review-time savings that nobody measured. It now
separates supported starting routes and static staging from research demos, begins with one question or sheet,
and makes larger annotation studies optional. Hosted Gemma results no longer support local hardware/throughput
advice in this guide. The OSHA reference is qualified to covered processes and linked to the official rule.

The description route now states that drawing checks need Pillow and that layouts can depict explicitly marked
drafting additions. It also narrows the missing-source warning promise to what the exporter actually checks:
signals without simulator references, rather than every item or stream. Engineering must inspect the source
coverage itself. Structured CAD avoids rereading pixels; no universal site accuracy or cost advantage is claimed.

The actual first question screen surfaced an ambiguous H1 sentence, "close it", which could read as an equipment
instruction. The catalog now explicitly closes the screening investigation and says not to operate the station.
Only that decision-rule wording changes in three existing OPEN100 findings; all other JSON fields, triggers,
thresholds and the 29-finding population remain unchanged. The other worked screens and roll-up reproduce; all
51 question-engine controls pass. The comparison helper initially replaced the same generic phrase in other
questions as well; limiting its expected replacement to the exact H1 sentence corrected that helper assertion,
without changing product behavior. The screen guide also explains that closing a screening question never means
operating equipment and stops offering public OPEN100 schedules as inputs to an arbitrary site's model.

Nine source/reader findings are resolved with code inspection and bounded actual CLI evidence. These are AI
reader and software checks, not engineering approval. The change adds no application feature, schema, public
source family or extraction result. Existing matrix results and their tool hashes remain unchanged, with no
matrix-cell rerun; all 52 configured pipeline stages remain fresh. Local verification targets the exercised
starter commands, exact catalog/output diff and existing question tests. CI must report its own actual coverage.

## 76. Keep a vendor controls export intact before inventing a loop

The existing corpus candidate described the Covestro C08 PCS export as two signal loops suitable for the generic
loop audit. Reading the pinned original shows seven connection records around two system functions, with several
links per function. The report does not by itself establish signal direction or cause-and-effect logic. Mapping
it to one controller/measurement/output row per function would discard connections or require an interpretation.
The candidate is now a worked development intake case, not a new row-4 score or source family.

The example retains every field in all seven connection rows, including both sides' identities, drawing references,
blank OPC addresses and source report-date serials. A standard-library checker compares the transcription to the
original workbook and verifies the instrument workbook and licence against existing byte/SHA-256 pins. Optional
fetch uses the existing downloader for just those three files. An actual fresh-cache fetch retrieved 329,011 bytes
and passed; matching cached files also pass at a zero download budget. Workbooks are read as ZIP/XML data only.

The first draft wrongly described a C-versus-S disagreement for U0020. The actual source checker refused that
assertion, and a separate controls reader independently found C in both reports. The draft was corrected before
acceptance. The remaining question is supported and bounded: what reviewed records explain U0001's connections,
including two references to a legend sheet, and establish its intended behavior? A legend reference is a request
for context, not proof of a drawing error. The public records do not supply a current governing revision, logic,
setpoints, test evidence or an assigned site owner.

An engineer can carry that question and the source packet into the existing pilot brief without inventing an asset
model or question-engine finding. The guide explains that generated screens need a supported model; manually
authored investigations also belong in the toolkit. When colleagues begin contributing, the next home is the
company's shared context and decision system, with execution remaining in existing operational systems. No local
governance application or receiving-system adapter was added.

Root verification exercises eight actual CLI controls: original/cached success, changed field, omitted row, absent
source, exhausted fetch budget, nonfinite budget and changed original. All pass their expected outcomes; the existing
17 loop-audit tests pass. A separate source reader compares every connection field and reproduces the older revision-A
and revision-D Markdown and JSON reports byte-for-byte. The catalog now says supplied loop list and key/model rather
than claiming knowledge of what a DCS currently runs. Matrix cells, tool hashes and recorded extraction results are
unchanged; its page is re-rendered only for the corrected candidate description. These are software and AI source-reader
checks, not engineering approval, measured adoption or operational benefit.

## 77. Let a first source question precede a measured pilot

Two reader perspectives found the same first-use mismatch. The drawing guide and Covestro intake invited one
useful question, including a manually authored document clarification with no asset model. Their linked brief
still assumed an operational trial: sponsor/operator, baseline, observation and comparable conditions looked
necessary for any packet. Missing fields could stay unknown, but the desk-based source question had no clear
way to record its result and next recipient without appearing to be an incomplete trial.

The same plain brief now starts with a source investigation: question, complete generated finding ID or labelled
manual reference, exact source identities/locators, evidence, missing records, qualified disposition, reviewer/date
and next recipient. Model/context references apply only where used. Unknown ownership or recipient acceptance
keeps the handoff marked needs owner. A source answer does not establish current installed state, governing
authority, operating permission or measured benefit. With no trial, the brief explicitly records trial not run
and benefit not measured instead of inventing a baseline.

If the team chooses a measured pilot, the extension retains the actual comparison, pretrial threshold, resource
and stop conditions, applicable authority and participants, baseline and observation, comparable conditions,
dated decision, fallback and receiving owner. A source disposition cannot satisfy that completion check. The real
site-pilot need N062 remains open. The context register is optional and still requires its supported model/graph
and question identities; a plain document question needs neither a fabricated model nor a new storage service.
The README, drawing bridge and lifecycle introduction use the same source-question-to-company-handoff path.

One independent AI reader filled three private copies: the Covestro manual source question with no model or
trial; the existing generated Bayer E18@model with all six asset references, its proposed partial answer and
three outstanding collection requests; and an explicitly illustrative planned pilot without observations.
The source drafts retain unknown owners and acceptance, and the illustrative trial remains insufficient evidence.
A second AI reader checked the authority/identity boundaries and fifteen relevant links/anchors. Neither
performed new runtime, plant or primary-source runs. Root checks retain sixteen existing pilot-field/completion
phrases and verify that runtime scripts, schemas and example outputs are unchanged.

These are documentation walkthroughs and manual checks, not tests of an automated completion validator or a
human adoption study. No new feature, corpus result, schema, integration or operational outcome is claimed.
Existing benchmark results and matrix cells remain unchanged. The proof of actual engineer use still needs a
real participant and observations; this repair only removes an unnecessary prerequisite for starting.

## 78. Keep the original I/O record behind an address assignment

The address mapper labelled parsed records as CSV rows. A blank line before a quoted multiline record made
those references wrong: records occupying physical lines 3–4 and 6 appeared as rows 2 and 3. The model also
retained no fingerprint of the supplied file. An engineer could inspect an assigned address without being able
to identify the exact original record from that assignment alone. The docstring's promise of live points and
the worklist's inference about what exists in the plant also exceeded what local address assignment proves.

The CLI now reads one raw CSV snapshot, fingerprints those exact bytes and records each parsed record's physical
line span. Assigned OPC mappings carry that fingerprint and span; the plan shows the filename, byte count and
digest. Blank lines, quoted newlines, UTF-8 BOMs and line-ending differences remain part of the source identity.
CSV columns cannot override the computed locator or fingerprint. Direct dictionary callers without source
metadata get explicitly logical row references, without an invented file hash or physical locator.

Matching, partial updates, explicit replacement and refusal policies stay the same. Repeating an identical
application is byte-stable. A prose-only source revision changes provenance without changing the address;
omitted mappings retain their previous evidence in partial mode. Legacy mappings do not acquire reconstructed
evidence. The exact synthetic fixture is pinned to LF in Git so its raw fingerprint reproduces across clones.
PI keeps its separate contract. Generated OPC addresses are unchanged, while the graph retains the new metadata.

The worked example explains what to retain with the investigation: the original I/O file and the reviewed plan.
Reports at the same name are still overwritten on apply, so they are current snapshots rather than a company
decision-history service. Fingerprints establish source identity, not authority, valid signal syntax, connection,
units, scaling or current plant truth. Unmatched records require reconciling both sources. The toolkit prepares
a checkable packet for the company's shared context system; it does not take over that system's responsibility.

The mapper's 26 tests pass. An independent AI controls reader runs 47 actual CLI commands and 166 adversarial
checks, including apply/repeat, source revisions, partial preservation, scoped replacement, atomic refusals,
newline/BOM variants, metadata spoofing and downstream generation/graph retention. Its three-step mapping
example reproduces the new report byte-for-byte with unchanged counts: 25 assignments, 10 model items absent
from this input, two unmatched source records and zero ambiguous rows. A separate AI reader checks the source
handoff and independently exercises dry-run revisions and locators; its apply/overwrite assessment is source-read
only. Root runs all seven worked-example commands; only the mapping report changes among registered outputs.
These are software and AI reader checks on existing public/synthetic inputs, not new corpus accuracy, receiving-
system acceptance, signal verification, human adoption or measured operational value. Matrix results remain
unchanged. Full-suite and CI logs retain their actual omissions separately.

## 79. Show what an incomplete first packet looks like

The starter already permitted a manual source question, a partial answer and an unassigned next owner. The
Covestro intake contained the question and supporting facts; the plain brief contained the fields. A recipient
reader found those instructions coherent, but a newcomer still had to assemble the handoff document. The new
filled brief shows that first result in one place without inventing a completed investigation or an owner.

It keeps the existing U0001 question, complete source identity, original fingerprints and exact workbook cells,
a qualified partial explanation, outstanding records and the next action. The cited records support identities,
function labels and connection references; they do not settle the intended behavior or establish a drawing error.
Reviewer, receiving owner, acceptance, current installed state and authority remain unknown. The trial is not run
and benefit is not measured. No model, generated finding or context-register entry is fabricated for this question.

The packet retains the complete seven-row transcription, unchanged originals, licence and toolkit revision used
for checking. Two commands let a colleague fetch just the three pinned originals into a separate cache and repeat
the existing source check offline. Root executes both from an isolated copy of the five required public files,
with no access to the original workspace's cache: three files, 329,011 bytes, both commands pass. A missing-original
control refuses with exit 2 and no output. This is a minimal receiving-copy software check, not a clean-clone or
human handoff experiment. The checker does not validate the new prose; original-cell review is separate.

The first-pilot guide and source-intake guide link directly to the filled example. A separate AI recipient reader
finds no consequential instruction or identity ambiguity and confirms the unresolved states remain visible. Its
review checks the CSV and document links, not the original workbooks. Source/controls review compares the factual
claims and raw fingerprints against the original records. Neither is engineering approval, observed adoption or
measured benefit. The next company home supplies ongoing access, ownership and decision history; no application,
schema, connector or new company workflow is added. Existing scripts, data, registered outputs, matrix results
and not-tried items are unchanged. No feature-output verdict or generalization result is renewed by this example.

## 80. Refuse a historian timeline that runs backward

The CSV reader checked time syntax and type, but not chronological order. Actual CLI probes accepted descending
and reordered exports and wrote negative detection delays: minus 3 in root's small fixtures and minus 80 in an
independent reader's example. A first-at-or-after timestamp lookup also selected the wrong row in file order.
Duplicate instants were accepted. The replay loader shared the same behavior. Separately, skipping blank CSV
records before counting rows made a physical-line-6 error appear as line 3.

The shared reader now requires strictly increasing parsed time/index values, with no duplicate instants. It
does not sort, deduplicate, aggregate or resample. Timestamp comparison uses the parsed instants, so different
UTC-offset strings for the same instant are duplicates; uneven increasing intervals and original value/text
associations remain supported. Record parsing retains physical spans through blank lines and quoted multiline
records. Data errors locate the offending record; an ordering error also cites the previous one. Existing generic
header-format guidance remains separate. Invalid normal or scored CSVs refuse before report creation or replacement,
and replay refuses before constructing its server.

Keep the raw export, prepare a separate chronological copy and record how duplicate records were reconciled with
their source meaning. Passing the check establishes neither clock accuracy nor uniform sampling. Detector windows
still count rows, and replay still advances at its explicit rate. Every existing detector function and constant
outside the reader is unchanged by AST comparison; replay implementation is unchanged below its module docstring.
This is input correctness, not a new anomaly method or a company context-management feature.

The 36 existing and added CSV tests pass, including sixteen band-CLI refusal cases, four replay-CLI refusals and
constructor tripwires. A separate controls reader executes 52 CLIs and 261 checks across order, offset, source-span,
bad-quality, valid-input and no-write cases; another reader checks the engineer's repair instructions. Old/current
valid reports agree byte-for-byte, including the committed TE default JSON and Markdown. Root's first Markdown
comparison omitted the guide's units option and differed only in that label; the corrected documented command
reproduces both outputs. The failed probe is retained separately rather than presented as a product failure.

The affected ten historian matrix cells are rerun against their existing inputs and criteria. All per-run metrics
and verdicts are unchanged; the other 84 cell records remain exact. This is compatibility evidence on previously
inspected sources, not another held-out experiment. Existing detector limitations and failed cells remain visible.

The full local run uses D: for temporary files to avoid C: disk pressure and completes 56 of 58 scripts, with two
unittest skips and two corresponding platform notices. Both failures expose the unchanged DEXPI image-path code's
inability to make relative links from C: sources to D: outputs. With only the temporary-file volume changed back
to C:, the two failed scripts pass all eight and 28 tests respectively. The original full-run failures remain
recorded; this chronology fix does not repair that separate cross-volume limitation. CI has its own exact-commit
result and omissions rather than inheriting a passing label from these focused retries.

A stale ledger marker is corrected too: N057's rolling/drift idea was already tried and implemented in A163/A171, with later cyclic
development in A183/A184. Marking that idea done does not claim the remaining false-alarm and detection gaps are
solved. No other not-tried item, source family, original record, scoring criterion or operational authority changes.


## 81. Make company handoff clear in the feature catalog

The README introduction describes a first engineering packet followed by a shared company home, but the
context-register feature still promised context the team could "maintain and own" and described a persistent
register without that next step. The example's recurring-refresh instruction could reinforce the impression
that local files were the intended long-term organizational system.

The feature now describes preparing a first evidence and decision packet for company handoff. Its result still
names the actual local report, dated records, open questions and portable JSON; the receiving company system
supplies shared access and ongoing governance. The example limits local refresh to packet preparation and
describes later tool use against released company snapshots, with its existing explicit-adapter and no-live-sync
limits retained. The question engine's investigative role and the document-only first-question path remain.

Only five descriptive feature fields change; tools, tests, example outputs, other features and corpus records
remain exact. Catalog generation and a separate AI engineer reader check the wording. This is documentation
clarity, not a feature-output review renewal, implemented connector, human adoption result or new operational
capability. A first useful investigation should make the need for retained company context concrete.


## 82. Keep the drawing with its DEXPI intake

The previous full run exposed a practical handoff failure: the public DEXPI converter could not form a relative
image path between Windows drives. An actual C01 CLI left a prediction and no manifest. The direct XML reader
avoided that exception by recording an absolute image path, but its intake still depended on the original
engineer's file location. Both observations are from local public-source staging, not a site import.

Both routes now retain an exact `<sheet-id>.source.png` beside the prediction and manifest, which reference local
filenames. An engineer can transfer those three files together before running the existing intake. The PNG hash
must match the prediction. An identical retained file is reused; a conflicting file, retained-image symlink or
generated-output/source overlap refuses before replacing generated reports. Use a fresh folder for a changed
drawing. The original XML and attribution remain part of the wider source packet; they are not automatically
copied by this image fix. This is single-writer local staging, not atomic publication of multiple files.

The direct reader prepares its PNG prediction before writing model/report files, so an image refusal no longer
leaves those reports replaced first. Model reading, conversion rules and score criteria are outside this change.
The committed C01 manifest remains an explicitly labelled historical cache-path record; current commands create
the retained-image intake. No original cache record or committed example result is rewritten to improve a score.

Focused controls pass 15 intake tests with one explicit OS symlink-permission skip and all 34 XML-reader tests.
The first matrix unit check correctly reports the 27 dependent cells as stale; its previous cross-drive exception
is absent. All 27 cells are then actually rerun under the existing criteria. Engineering metrics, details and
verdicts are unchanged; the other 67 complete records remain exact. Execution metadata includes 21 per-sheet
runtimes, and two citations move to identical text at new line numbers. Root's first private comparison omitted
the nested runtimes and stopped before publication; the corrected check isolates those exact fields. A separate
matrix reviewer verifies all 94 records and 732 current file hashes, retaining the original 63 pass, 23 fail and
eight n/a verdicts. These sources were already inspected; this supplies no new held-out or generalization result.

An independent controls reader runs 72 actual CLIs and 226 checks across 12 same/cross-drive cases on C01-C03 and
both routes. Relocated intake succeeds while each supplied original image path is unavailable. Source bytes,
prediction objects and XML model/report bytes remain unchanged. The direct reader's prediction text now uses LF
newlines; this formatting difference is kept separate from semantic equality. Two actual symlink controls are
explicitly skipped because Windows denies link creation. Another AI reader checks the transfer instructions.
Neither review supplies human approval, source-engineering correctness or measured adoption.

The full local run with temporary files on a different drive now passes all 58 scripts, including both previously
failing DEXPI/matrix scripts. It reports three unittest skips and two platform notices; notices do not add to the
skip count. The original failed run remains in the earlier chronology record. CI reports its own exact-commit
coverage and omissions. Only the matrix output review is renewed; existing feature/source review scopes remain.
The transfer mechanism prepares a first engineering packet for company handoff and adds no organizational
governance service or ready receiving-system connector.


## 83. Use risk tiers to order review, not accept items

The export guide still called red items more likely wrong than right and told a reviewer to spot-check green
items and accept the batch. The CLI help repeated that green was safe to batch-accept. Those instructions were
stronger than the evidence: the [saved Codex M3 holdout-A result](../out/triage_r2-tiles-trace_holdout-a.json)
records a red-tier observed error fraction of 0.230 across 191 output items. That historical result is not a
new-site calibration. Its truth test covers rough symbol class/location and keyed link endpoints; missing items,
tag text, parents, installed state and operating duty are outside that denominator.

The guide, review loop and actual CLI help now describe priority. A tier accepts nothing; sampling alone does not
accept the unreviewed remainder. Unfamiliar drawings need an agreed review plan against originals. Green does not
establish safety duty: the floor only recognizes its implemented tag/model-field rules on instruments and in-line
items. Independent source review also caught the old zero-weight duplicate-tag statement (its fitted weight is
small but nonzero) and the claim that the score tested correct labels. Both are corrected. The original round-3
goal and fitted threshold-rule text remain historical, with a dated current-use note rather than rewritten rules.
Source review also corrects the displayed holdout-A green-precision lower bound from 94% to 93%: the saved Gemini
M0 result is 93.4%. A dated correction cites that table; no stored result is changed or re-scored. The old round's
"calibration" label is qualified as its tier-order check, not demonstrated probability calibration.

Only the confidence module docstring changes. Removing that module docstring yields the exact old executable AST,
including all function docstrings and constants. Coefficients, thresholds, six recorded model outputs and every
saved triage file remain unchanged. Actual old/current help commands check the exposed wording. The two existing
recorded pipeline stages accept their historical files unchanged using the existing ACCEPT branch, with generation
subprocesses prohibited. The lock changes exactly their two confidence-source hashes; every output hash and other
entry remains exact. Stage notes and the lineage guide explicitly state that no extraction, build or scoring run
was repeated. This is source-binding maintenance, not reproduced extraction or new calibration.

The N054 audit finds a separate unresolved packaging gap. The documented default Ignition preflight exits 2:
its required manifest and browser contract are ignored and not committed. Native acceptance stays NOT RUN, also
when `--require-native` first encounters those missing inputs. The guides now state that limitation, the fixed
TE/OPEN100 scope and conditional held-package arguments. Synthetic tests do not supply actual candidate evidence.
The outdated release-version claim is replaced by instructions to use matching checkout files and record the commit;
the 2026-10-13 native receipts remain specific to their historical candidate.

The own-input contract is exercised separately on a task-owned receiving copy of the existing public OPEN100
sheet and saved extraction: `--check-only` writes no output, the build retains original image/extraction bytes,
and existing-output and duplicate-ID controls refuse. No plant data or model call is involved. Root's first
preflight wrapper wrongly expected a default success and stopped on the actual missing-manifest refusal; that
failed wrapper/output is retained, and the missing evidence stays a gap. No manifest was manufactured to make it pass.

All 45 existing pipeline checks and the existing risk/safety-floor controls pass. The 26 synthetic preflight tests
pass with one explicit Windows symlink skip. A separate AI engineer reader checks what a newcomer would follow;
independent source and provenance readers check the bounded evidence. No feature-output review, corpus score,
held-out result, operator approval or adoption claim is renewed. N054 remains not-done for the complete public
candidate-package recipe; N062 and N063 remain unproven. A first source question or evidence packet needs no gateway.


## 84. Start a refrigeration question with two sourced records

A fresh AI newcomer/recipient reading found no consequential first-use obstacle in the existing source-only brief
and drawing-to-question route. It did not justify another workflow feature. The refrigeration corpus still had a
concrete gap: the worked refrigeration questions used only the illustrative food model.

The new [Millard example](../examples/opportunity-screen/millard/README.md) starts from the official CSB January
2015 safety bulletin, No. 2010-13-A-AL. The PDF's exact bytes are pinned; its original asset URL returned HTTP403,
while the official file.aspx link supplied the 656,148-byte original. A fixed-case standard-library helper checks
the fingerprint offline and fetches missing bytes only with explicit --fetch. Changed local originals refuse,
including with --fetch, rather than being replaced. The original remains outside Git.

The model retains one authored aggregate and a hot-gas main valve from the simplified diagram/narrative. Their
identifiers are local labels, not plant tags. It deliberately does not reconstruct complete piping, devices or
logic. The existing E30 produces one finding over both records with three unanswered collection requests. Its
absence statement refers to this incomplete model, not actual plant absence or confirmed timer initiation.
Only E30 is selected; the other questions and safety functions have not been evaluated here.

The plain first-question brief separates that generated energy prompt from a manually authored question about
applicable controls records. Source review matters: the historical 20-versus-15-minute comparison concerns a
pump-out step, not defrost frequency, energy performance or a safe duration. The partial source explanation does
not complete E30's requests. The recipient, current authority, governing revision and accepted handoff remain
unknown; no operational instruction or configuration change is proposed. The company system owns continuing
stewardship when an actual recipient takes the packet. No context-register expansion or connector is added.

The original was read before choosing the subset, and a private feasibility run preceded the committed screen.
The acceptance note records that sequence. This is development evidence on an additional historical CSB case,
not a new independent source agency, held-out drawing test, full refrigeration model or accuracy improvement.
Independent source reading inspected the full original pages and simplified diagram. Five offline CLIs reproduce
the screen, remove the valve as a labelled anti-trigger, and check original/changed/missing source behavior. Root
runs six actual CLIs including the explicit download and preservation/refusal controls. All 51 existing question-
engine tests pass with the new fixture included. Software and engineer-reader receipts keep their narrower scope;
existing outputs retain their inherited reviews. Full-suite/CI coverage and skips are recorded separately.

The question engine/catalog, all earlier screens, matrix criteria and results are unchanged. Corpus registration
uses a separate question-packet entry outside the eight-workflow matrix. The catalog also binds that manifest
as matrix evidence, so its new metadata requires a narrow independent binding renewal: existing input objects and
all matrix results stay exact, and no cells are rerun. This does not renew the original execution/source audits.
No measured engineer adoption, energy saving, site approval or receiving-company round trip is claimed;
N062/N063 remain unproven.


## 85. Keep the operating context with a normal baseline

N056 proposed fitting longer normal-running windows. The source audit comes first: the inspected PRONTO day2-4
merged originals contain nine separate Normal blocks totaling 11,899 records; the longest is 2,770 one-second
records. A source label is not an operating-mode definition. Measured air/water values differ between and within
blocks, and the operation log separately records nominal settings, health labels and flow descriptions. All 14
original members inspected by the independent source reader match their pins and remain unchanged. No contiguous
qualified multi-day normal baseline is established by that cache subset.

One preliminary identity guess was refused before publication. The log's Test3 Normal row is not the second
merged day2 Normal block: exact raw alignment puts that block later, beside later logged actions. The brief
preserves the supplied labels and asks for reviewed time/identity joins instead of manufacturing a source conflict.

The independent methods review fixed four paired comparisons before new band runs and rejected pooling disjoint
Normal blocks. Preserving timestamp text would not preserve filter dynamics: the row-based drift method treats
those records as adjacent across gaps. No gap policy or detector change was added. For each accepted pair, a
short recent labeled-normal segment fits/selects K before both choices score identical later rows. The earlier
baseline and recent candidate use the same frozen drift method, fit fraction, K search and diagnostic criterion.
All cases are development data already inspected; the recent candidate is shorter in every case. Context, length
and noise history change together, so this is sensitivity evidence, not a causal mode study or prospective rule.

The [comparison](../examples/historian-csv/baseline-context/expected/results.md) retains mixed outcomes: early
baselines meet the diagnostic in three of four cases, recent candidates in two. Day2 pre-fault flags change from
155/181 to 0/181, but day3 leakage changes from 0/150 to 17/150 and day4's second slugging case from 0/1,385 to
895/1,385. Those two recent candidates also miss K's calibration target. Day3 diverted-flow detection moves from
1,922 to 7,290 seconds, near the end of its 7,320-record fault interval; a criterion pass does not establish prompt
detection or causal attribution. Every complete band result, source fingerprint, range, warning and bad-sample
count is retained. Companion log cells and source metadata were added after the first run; all complete scored
case objects stayed exact.

The paired scoring start resets both filters, and three cases reach the fault before 600 good scoring samples.
There is no carried history or extra discarded burn-in. The shorter scoring population is different from the
original matrix: day4's early baseline is clean on the common prefix while its separate original full-score
control remains 492/2,770 flagged. All four full-score controls match the existing matrix metrics. The paired
counts cannot replace those older populations. No method, default, threshold, source label, matrix cell or
headline accuracy changes.

A fresh AI engineering/LinkedIn-reader perspective supports the narrow usefulness of a baseline-applicability
case even when recent data is worse. The resulting plain brief asks which operating/configuration and mapping
records establish comparability and who reviews that choice. Ownership, governing authority and acceptance stay
unknown. It creates no automated baseline selector, local governance service or company connector. Independent
source, methods, software and wording checks retain their separate scopes; repetition and CI coverage are
reported separately from any human outcome. N056 remains open for qualified longer multi-day data; N062/N063
remain unproven.


## 86. Take a written description to one question before drafting

The previous goal turn published the fixed baseline-context investigation; that is completed progress, not a
reason to add another toolkit feature. The next reader pass looks for a consequential obstacle in the existing
on-ramp. The written-description guide has one: it takes an engineer from a sourced model into platform files
and a manually authored drawing layout, then ends without showing the first-question and company-handoff route.
The root guide already explains that route, so this is an entry-guide omission rather than a missing capability
or proof that a real engineer was blocked.

The revised guide puts the existing offline question engine before optional outputs. An actual full screen on
its exact committed Bayer model produces 12 findings; its complete `E18@model` object matches the existing
single-question example. The engineer can take one finding's exact ID, asset references and missing-evidence
requests into the plain brief, retain source revisions and qualified answers, and identify a company recipient.
A source-text clarification can begin without any model. No new drawing, drafting layout, platform import or
model call is needed for this first investigation.

The existing partial-answer example remains an optional worked illustration, not a required local register.
Unknown ownership and acceptance stay visible. Shared maintenance, decisions and history belong in the company's
home as the work grows. This change adds no governance application, adapter, document synchronization or company
round trip. It neither re-audits the historical report/model nor changes the catalog, tools, committed screens,
matrix or accuracy claims. AI reader/CLI checks establish a runnable route, not human adoption or benefit;
N062/N063 remain unproven.
