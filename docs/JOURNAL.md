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

**What:** the scoring dataset is one 8.7 GB zip. The build machine has about 11 GB free, and Ignition needs room
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
