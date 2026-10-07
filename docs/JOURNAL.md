# Build journal

How this project was built and why each choice was made, written as it happens. Results are in the README and
`out/`. This file is the reasoning behind them.

Each entry: **What** (one line) · **How** (the method, concretely) · **Why** (the reasoning, including what we rejected) ·
**Lesson** (what generalizes beyond this project).

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

---

## 4. Work within the hardware you have

**What:** the scoring dataset is one 8.7 GB zip. The build machine has about 11 GB free, and Ignition needs room
too.

**How (planned):** a zip file keeps its table of contents at the end. We read just that part over HTTP range
requests, then fetch only the entries we need (the OPEN100 subset and the real P&IDs).

**Why:** buying disk or cleaning up would also work, but pulling only what you need is the habit that scales.
Datasets in this field are large, and most projects need a small slice of them.

**Lesson:** constraints are design inputs, not blockers.

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
