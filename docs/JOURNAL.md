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
