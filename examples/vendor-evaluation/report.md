# Vendor evaluation: GPT (Codex), round-5 method

Controls behaved on every sheet: perfect and empty answers met their declared checks, and both deliberately wrong answers stayed at or below symbol F1 0.1. These checks passed; they do not validate the answer keys or every possible extraction error.

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

Each run's value, then two 95% intervals: **runs** is an approximate Student-t interval for the mean score on these fixed sheets, assuming independent, comparable runs. It is not a prediction interval for the next run. Duplicate or correlated answers do not establish independent replicates. **Bootstrap** resamples only the observed sheets with replacement and picks one observed run per sampled sheet, then recomputes the pooled score. It does not resample a whole run together or demonstrate performance on unfamiliar drawings. Seed and draws are as in `scripts/replicate_stats.py`.

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

- **Start with the controls.** The perfect row checks agreement with these keys; the empty row is the no-prediction baseline. Wrong-class and shifted answers must satisfy the declared control thresholds. A failure is reported at the top. Passing these controls does not establish that the keys are correct or that other kinds of error will be caught.
- **Review load** counts differences from the answer key (delete false symbols, add missed ones, fix wrong classes, delete false links, add missed links), normalized per 100 key items. 0 means no counted differences; 100 equals the empty-answer count; above 100 means more counted differences than that baseline. This is not measured review time, effort or labor savings: different corrections can take different amounts of work, and real review may include tasks this score omits.
- **Symbol F1** says whether the tool found the symbols and called them the right class. *Rough* uses box intersection-over-union of at least 0.10; *strict* uses at least 0.50. A gap shows sensitivity to the overlap threshold. Neither threshold establishes CAD precision or drawing readiness.
- **Connection F1** compares undirected asset-network pairs through the key's pass-through nodes. It does not verify direct pipe adjacency, physical routing or flow direction. Class-agnostic symbol matches can receive connection credit even with wrong classes: read the symbol columns too.
- **Per sheet**: inspect sheets that score worse than the rest. Drawing style, scan quality, symbol mix and key quality are possible causes to investigate; the score alone does not identify the cause.
- **Several runs**: *min-max* describes the observed runs; *runs 95%* estimates their mean under its assumptions. Overlap alone does not establish a tie, equivalence or absence of a difference; this report does not perform a between-vendor comparison test. The *bootstrap* interval is conditional on the observed sheets and runs, not a guarantee for new drawings or another plant.
- **Missing or failed sheets count as empty answers.** A tool shouldn't look better by failing quietly.
- **What this does not measure:** tag text (use `scripts/score_tags.py` on keys with tag truth), line routes, sizes, flow direction, or anything outside the six classes. And it is only as good as your labelled sheets.
