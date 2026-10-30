# Test any P&ID digitization tool on your own sheets

**Why it matters:** Vendors quote accuracy on their own test drawings. Scoring them on yours, with a deliberately wrong answer scored beside them, shows whether the number means anything.

A vendor demo shows you their best drawing. This kit shows you what their tool does on yours, and it never shows
that number alone: every report puts the vendor's score next to the score of answers whose quality is already known.

| Known answer | What it must score | Why it's there |
|---|---|---|
| **Perfect**: your answer key, converted into a prediction | Review load 0, symbol F1 1.000; connection F1 1.000 when the key has scored links | Checks key-to-prediction conversion under the scored fields |
| **Every class wrong**: right places, wrong names | Symbol F1 near 0 | Checks this deliberately mislabelled answer against the rejection threshold |
| **Every box moved half a sheet**: right names, wrong places | Symbol F1 near 0 | Checks this deliberately displaced answer against the rejection threshold |
| **Empty**: nothing found | Review load 100, every F1 0 | The no-prediction count baseline; no time or effort measured |

The two wrong answers are the reason the kit exists. This project's first scorer gave a deliberately wrong answer
15-32% credit, and the second version still gave 3-20% ([journal entry 7](../../docs/JOURNAL.md#7-fix-the-scoring-rules-first-then-test-the-scorer-until-it-cant-be-fooled)).
A grader that generous flatters every tool, and the weak ones most. If either wrong answer earns more than symbol
F1 0.10 on your keys, the report opens with **CONTROLS FAILED** and the script exits 2.

## What you need

1. **A few of your own sheets, hand-labelled.** For each sheet, `<sheet>.png` and `<sheet>.graphml` side by side in
   one folder. The GraphML is the PID2Graph format: one node per symbol with a `label` and a pixel box
   (`xmin`, `ymin`, `xmax`, `ymax`), and edges along the process lines. Labels the scorer grades: `tank`, `pump`,
   `valve`, `instrumentation`, `inlet/outlet`, `general`. Line bends, tees and crossings go in as `connector`,
   `crossing` or `arrow` nodes so that two assets joined by a line are linked through them. Open any key in
   `data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/` to see a complete example.
2. **The tool's answer for each sheet**, one folder per run, `<sheet>.json` per sheet, in the prediction format of
   [`extraction/prompt.md`](../../extraction/prompt.md): symbols with a class and a box on a 0-1000 scale, and
   connections between symbol ids. A run record from `scripts/run_extraction.py` works as is. A vendor that exports
   something else needs a small converter; that converter is the vendor's job, and you should check it with the
   perfect control (convert your own key through it and expect 0).
3. **Ideally, several runs.** AI tools don't give the same answer twice. Ask for the same sheets processed three to
   five times and pass every folder: the report treats them as replicates.

```sh
python scripts/evaluate_vendor.py --keys my_keys --predictions vendor_run1 vendor_run2 vendor_run3 \
    --name "Vendor X" --out my_report/vendor_x
```

Standard library only (`python -S` works). It writes `my_report/vendor_x.md` and `.json`. Exit 0 means the controls
behaved; 2 means a control failed and the vendor numbers must not be used; 1 means bad input.

## Worked example: round 5 on OPEN100 holdout A

"The vendor" here is this repository's own declared method (2x2 tiles with GPT, then the code line tracer), run five
times on six public OPEN100 sheets (6-11), historically called holdout A. These sheets also informed method
selection, so this is validation evidence rather than an untouched final holdout. The output is committed here:
[`report.md`](report.md) and [`report.json`](report.json). The original scoring command was

```sh
python scripts/evaluate_vendor.py \
    --keys "data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100" --sheets 6,7,8,9,10,11 \
    --predictions runs/r5-hA-rep1-trace/codex runs/r5-hA-rep2-trace/codex runs/r5-hA-rep3-trace/codex \
                  runs/r5-hA-rep4-trace/codex runs/r5-hA-rep5-trace/codex \
    --name "GPT (Codex), round-5 method" --out examples/vendor-evaluation/report
```

The five run folders hold raw model output, so they are not in git ([runs/README.md](../../runs/README.md)); the
report records each prediction file's SHA-256 instead. For a short single-sheet demonstration, use the committed
sheet 0 extraction from [the own-drawing example](../own-drawing/README.md); sheet 0 was seen during
development, so treat its score as a demonstration of the kit, not as evidence about the method:

```sh
mkdir -p try/run1 && cp examples/own-drawing/extraction_sheet0.json try/run1/0.json
python -S scripts/evaluate_vendor.py --keys "data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100" \
    --sheets 0 --predictions try/run1 --name "sheet 0 example" --out try/report
```

That gives review load 7.4, symbol F1 0.970, connection F1 0.960, beside a perfect control at 0 and wrong answers at
100 and 121.9.

### What the holdout-A report says

| Answer | Review load per 100 | Symbol F1 (rough) | Symbol F1 (strict) | Connection F1 |
|---|---|---|---|---|
| Round-5 method, mean of 5 runs (min-max) | **20.1** (18.4-21.5) | 0.929 (0.919-0.940) | 0.890 (0.881-0.899) | 0.872 (0.866-0.879) |
| Perfect answer | 0.0 | 1.000 | 1.000 | 1.000 |
| Every class wrong | 99.9 | 0.002 | 0.000 | 0.000 |
| Every box moved half a sheet | 136.2 | 0.006 | 0.000 | 0.000 |
| Empty answer | 100.0 | 0.000 | 0.000 | 0.000 |

- The method leaves 20.1 counted differences per 100 key items on these sheets. No reviewer time was measured;
  this is not a labor-saving estimate. The controls reject the planted wrong answers: neither earned more than
  0.006 symbol F1 overall. Empty-answer normalization compares counts, not human effort.
- **Sheet 6 is the bad sheet the average hides.** Its review load is 38.7 (34.4-44.8 over the runs), about twice
  any other sheet's, and its connection F1 is 0.685 against 0.87-0.92 elsewhere. It is also the only sheet where
  the wrong answers earn any credit (symbol F1 0.011 with every class wrong, 0.033 with every box moved). For the
  moved boxes the cause is known: the sheet draws two identical pump details half a sheet apart, so a box moved half
  a sheet can land on the twin. That chance floor is documented in journal entry 7.
- The bootstrap 95% interval is 14.3 to 28.0 for review load under resampling of these six observed sheets and
  runs. It does not establish performance on unfamiliar drawings or another plant. Runs 95% estimates a mean
  on these fixed sheets, not the outcome of one future run. Overlapping intervals do not establish a tie or
  equivalence; this report does not perform a between-vendor comparison test.

### Report interpretation revision

The current Markdown is rendered from the unchanged saved JSON using the corrected `evaluate_vendor.markdown`
function. This is a wording revision, not a new model or scoring trial. The [original Markdown](history/report-before-interpretation.md)
is retained byte-for-byte, including its earlier interpretation errors. Numeric table rows, source hashes,
scoring thresholds and intervals are unchanged. The [task benchmark](../../benchmarks/README.md#report-implementation-revisions)
separately records the new implementation fingerprint and cohort identities after actual offline re-scoring.

For a new vendor, use the normal CLI above. The report describes six-class box matches and undirected keyed
asset-network pairs; strict IoU does not prove CAD readiness, and network matches do not verify direct pipe
adjacency, flow direction or process truth. The four controls probe declared failures, not every kind of error.

### Agreement with the published round-5 numbers

`out/replicates_r5_holdout-a.md` (made by `scripts/replicate_stats.py` from the same records) reports GPT at 20.1.

| Measure | This report | `out/replicates_r5_holdout-a.md` |
|---|---|---|
| Review load, the five runs | 20.7, 21.5, 18.4, 18.8, 21.0 | 20.7, 21.5, 18.4, 18.8, 21.0 |
| Review load, mean and runs 95% | 20.1, 18.3 to 21.8 | 20.1, 18.3 to 21.8 |
| Symbol F1 rough, mean and runs 95% | 0.929, 0.918 to 0.940 | 0.929, 0.918 to 0.940 |
| Connection F1, mean and runs 95% | 0.872, 0.864 to 0.879 | 0.872, 0.864 to 0.879 |
| Review load, bootstrap 95% | 14.3 to 28.0 | 14.2 to 28.0 |
| Connection F1, bootstrap 95% | 0.800 to 0.916 | 0.801 to 0.916 |

Every run value, mean and runs interval agrees exactly: the kit calls the same per-sheet counting
(`replicate_stats.drawing_counts`) and the same interval code. The only differences are in the last digit of two
bootstrap bounds. Both use the same seed and 10,000 draws, but the published file drew Claude's bootstrap first
from the same random stream, so GPT's draws started at a different point. Running `replicate_stats.py` with
`--tools codex` alone gives 14.3 to 28.0 and 0.800 to 0.916, the same as this report. Strict symbol F1 and the
controls are new here; the published file doesn't report them.

## Limits

- **Six classes.** Anything else a tool reports (nozzles, line numbers, notes, its own class names) is ignored and
  counted in the report as "ignored symbols", not as wrong. Decide whether that matters for your use.
- **Not scored:** tag text (keys with tag truth need `scripts/score_tags.py`), line routes, line sizes, flow
  direction, spec breaks. Connections are judged by which assets connect, on class-agnostic matches, so read
  connection F1 together with the symbol columns.
- **`general` is the annotators' catch-all.** Don't let a vendor tune toward it ([EVALUATION.md](../../docs/EVALUATION.md),
  rule 9).
- **Your keys set the ceiling.** The perfect control checks agreement with them, not that they are right. Have a
  second person check a sample of the labelling before you rank vendors on it.
- **Sheets the vendor has seen aren't a test.** Keep the labelled sheets away from the vendor until they have
  delivered, and give every vendor the same sheets.
- **The score is a filter, not the outcome.** The outcome is the time your reviewers spend correcting the result
  ([EVALUATION.md](../../docs/EVALUATION.md), section 1). Use the report to decide which tool is worth a timed review.
