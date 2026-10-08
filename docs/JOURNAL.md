# Build journal

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
| Gemini (gemini-3.1-pro) | 0.44 → 0.57 → 0.74 | 0.24 |

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

  It passed on the first run.
- **The Windows launchers were tested locally,** with a stand-in `docker` command and the throwaway gateway answering
  the "is Ignition up?" check.

**What testing caught:**
- **The window title "P&ID" broke the start script for everyone.** In a batch file, `&` means "and then run".
- **A build setting was read before it was loaded,** so the first throwaway build still pointed at `localhost`.
- **I was about to document that restarting resets Ignition's 2-hour trial.** Earlier the same day, a restart had
  shown the opposite. The guide gives the real steps instead.

**Lesson:** "easy for anyone" is a claim like any other. It needs the same from-nothing test as the code: a check
that starts where a newcomer starts and looks at what they would see.

**At your plant:** for a pilot, give operations and reviewers the twin in a form they can start themselves on a test
machine, and keep it from a throwaway, credential-free build. The fastest way to collect operator feedback is to
remove the setup between them and the screen.

