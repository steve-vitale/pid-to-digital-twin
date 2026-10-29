# Vendor evaluation: GPT (Codex), round-5 method

Controls behaved on every sheet: the perfect answer scored perfect, the empty answer zero, and both deliberately wrong answers stayed at or below symbol F1 0.1. The scorer can tell right from wrong on these keys.

Sheets: 6, 7, 8, 9, 10, 11. Runs treated as replicates: 5 (r5-hA-rep1-trace/codex, r5-hA-rep2-trace/codex, r5-hA-rep3-trace/codex, r5-hA-rep4-trace/codex, r5-hA-rep5-trace/codex). Scorer: `scripts/score_pid2graph.py` (sha256 a21da996c797).

Models named in the run records: gpt-6.1-sol.

## Vendor beside the controls

All rows: same answer keys, same scorer, micro-averaged over the sheets. Vendor row: mean of the runs, then min-max.

| Answer | Review load per 100 key items (lower is better) | Symbol F1, rough, class must match | Symbol F1, strict, class must match | Connection F1 |
|---|---|---|---|---|
| **GPT (Codex), round-5 method** | **20.1** (18.4-21.5) | **0.929** (0.919-0.940) | **0.890** (0.881-0.899) | **0.872** (0.866-0.879) |
| Control: perfect answer (the key itself) | 0.0 | 1.000 | 1.000 | 1.000 |
| Control: every class wrong | 99.9 | 0.002 | 0.000 | 0.000 |
| Control: every box moved half a sheet | 136.2 | 0.006 | 0.000 | 0.000 |
| Control: empty answer | 100.0 | 0.000 | 0.000 | 0.000 |

## Replicates

Each run's value, then two 95% intervals: **runs** (these sheets, the method run again) and **bootstrap** (other sheets like these, and another run; seed and draws as in `scripts/replicate_stats.py`).

| Metric | Runs | Mean | Min-max | Runs 95% | Bootstrap 95% (sheets) |
|---|---|---|---|---|---|
| Review load per 100 key items (lower is better) | 20.7, 21.5, 18.4, 18.8, 21.0 | 20.1 | 18.4-21.5 | 18.3 to 21.8 | 14.3 to 28.0 |
| Symbol F1, rough, class must match | 0.925, 0.919, 0.940, 0.937, 0.924 | 0.929 | 0.919-0.940 | 0.918 to 0.940 | 0.908 to 0.949 |
| Symbol F1, strict, class must match | 0.894, 0.887, 0.899, 0.889, 0.881 | 0.890 | 0.881-0.899 | 0.882 to 0.899 | 0.855 to 0.933 |
| Connection F1 | 0.866, 0.867, 0.879, 0.878, 0.869 | 0.872 | 0.866-0.879 | 0.864 to 0.879 | 0.800 to 0.916 |

## Per sheet

Review load per 100 key items on each sheet, so one bad sheet can't hide in the average. Vendor columns are the runs in order; controls on the right.

| Sheet | Key items | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Mean | Perfect | Wrong class | Shifted | Empty |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 192 | 37.5 | 35.9 | 34.4 | 44.8 | 41.1 | 38.7 | 0.0 | 99.5 | 141.7 | 100.0 |
| 7 | 212 | 16.0 | 15.6 | 16.5 | 13.2 | 16.5 | 15.6 | 0.0 | 100.0 | 132.5 | 100.0 |
| 8 | 91 | 11.0 | 11.0 | 12.1 | 11.0 | 9.9 | 11.0 | 0.0 | 100.0 | 144.0 | 100.0 |
| 9 | 226 | 12.8 | 19.0 | 14.2 | 16.8 | 19.5 | 16.5 | 0.0 | 100.0 | 123.9 | 100.0 |
| 10 | 341 | 26.1 | 21.1 | 17.3 | 14.1 | 22.0 | 20.1 | 0.0 | 100.0 | 138.4 | 100.0 |
| 11 | 238 | 14.7 | 21.8 | 15.1 | 14.3 | 13.0 | 15.8 | 0.0 | 100.0 | 140.3 | 100.0 |

Symbol F1 (rough, class must match) and connection F1 per sheet, vendor mean over the runs:

| Sheet | Symbol F1 | Connection F1 | Wrong-class control symbol F1 | Shifted control symbol F1 |
|---|---|---|---|---|
| 6 | 0.924 | 0.685 | 0.011 | 0.033 |
| 7 | 0.918 | 0.920 | 0.000 | 0.000 |
| 8 | 0.973 | 0.909 | 0.000 | 0.000 |
| 9 | 0.920 | 0.918 | 0.000 | 0.000 |
| 10 | 0.917 | 0.868 | 0.000 | 0.000 |
| 11 | 0.947 | 0.890 | 0.000 | 0.000 |

## How to read this

- **Start with the controls, not the vendor.** The perfect row is the best any tool can score on these keys; the empty row is what doing nothing scores. A deliberately wrong answer must land near the empty row. If it doesn't, the scorer is being fooled and the vendor number means nothing (the report would say so at the top).
- **Review load** is the headline: the corrections a person needs to turn the tool's answer into the answer key (delete false symbols, add missed ones, fix wrong classes, delete false links, add missed links), per 100 items in the key. 0 is perfect, 100 is the same work as starting from nothing. Above 100 is worse than nothing: the reviewer also deletes the tool's mistakes.
- **Symbol F1** says whether the tool found the symbols and called them the right class. *Rough* means "in about the right place" (box overlap of at least 10%), *strict* means precise enough to draw from (at least 50%). A big gap between the two means the boxes are loose.
- **Connection F1** says whether it knows which assets connect. It ignores classes: compare it with the symbol columns.
- **Per sheet**: look for one sheet much worse than the rest. That sheet is usually a drawing style, scan quality or symbol mix the tool hasn't seen, and your other sheets may have more of it.
- **Several runs**: AI tools don't give the same answer twice. *Min-max* and *runs 95%* show how much the same tool moves on the same sheets. Two vendors whose ranges overlap are tied on this evidence. The *bootstrap* interval is how far the score could move on other sheets like these: with a few sheets it is wide, and that width is the honest size of your sample.
- **Missing or failed sheets count as empty answers.** A tool shouldn't look better by failing quietly.
- **What this does not measure:** tag text (use `scripts/score_tags.py` on keys with tag truth), line routes, sizes, flow direction, or anything outside the six classes. And it is only as good as your labelled sheets.
