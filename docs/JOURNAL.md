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
