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

## Round-2 methods (planned)

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
