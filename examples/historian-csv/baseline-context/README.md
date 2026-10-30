# Choose the normal export before judging a flag

A label of `Normal` does not establish comparable operating conditions. This worked investigation uses the
existing PRONTO records and unchanged band tool to show why an engineer needs the operating context beside the
CSV. Read the [comparison](expected/results.md) without downloading data, then the [first-question brief](first-question.md).

The fixed comparison has mixed outcomes. A recent candidate removes pre-fault flags in day 2, but creates them
in day 3's leakage run and day 4's second slugging run. For day 3's diverted-flow run, detection shifts from
1,922 to 7,290 seconds after the label. Two recent candidates also miss the tool's K-selection target. Every
outcome remains visible. No detector, default, threshold or matrix result changes.
The 7,290-second flag arrives near the end of that 7,320-record one-second fault interval; meeting this diagnostic
criterion does not establish prompt detection or attribution to the fault.

## What was compared

[plan.json](plan.json) fixes four previously inspected development cases before the new band runs. In each,
the first half of the existing pre-fault interval becomes a **recent labeled-normal candidate**. Its first half
fits bands and its second half chooses K. Both this candidate and the earlier baseline then score the exact
same remaining pre-fault rows and complete fault tail. All fit/K records precede those scoring rows.

The recent candidates are shorter in every case. This is sensitivity to context and length together, not a
controlled test of operating mode, a longer-baseline experiment or a prospective selection rule. Source labels
were known when the cases were chosen. No outcome-driven cuts, tag selection or threshold tuning are performed.

Both scoring filters initialize at the common scoring start. Three cases reach the fault before 600 good
scoring samples, the slow filter's nominal window. The shortened prefix changes initialization and population
relative to the older matrix runs. In particular, day 4's earlier baseline has zero flags on this common prefix,
while the separate original full-score control still has 492/2,770. These paired counts cannot replace the matrix.
No additional burn-in is removed. The full JSON keeps every band result, warning, bad-sample count and fingerprint.

## Why the source context matters

The inspected merged files contain nine separate `Normal` blocks, totaling 11,899 records, across three test
days. The longest has 2,770 one-second records, not a contiguous multi-day baseline. Some blocks themselves
contain changing flow values. The [source profile](expected/results.json) retains every block's exact rows,
reconstructed times and AirIn/WaterIn medians. Medians are measurements summarized from source columns, not setpoints.

The original `Operation log.xlsx`, sheet `Operation Log 0907`, calls both `A18` and `A98` Normal, while
`H18:H19` and `H98:H99` list different nominal air/water flows. The accompanying `G20` and `G100` flow descriptions
say `slugging condition`. Health labels, nominal settings and flow descriptions answer different questions.
Those log rows are not automatically joined to the two merged day-2 Normal blocks: timestamps and identities
must support a join. Source labels are preserved; no apparent contradiction is repaired by guesswork.

The authors' alignment readme says they combined air/water inputs and assigned health labels using the operation
log. `AirIn` therefore must not silently become one named transmitter. The runner pins the six measurement/raw
CSVs and three companion originals, preserves literal log cells, and checks the existing unique raw alignment.
It does not infer source meaning, configuration authority or a qualified baseline from those checks.

Disjoint blocks are not pooled: the row-based drift filter would treat samples across time gaps as adjacent.
The untried longer-baseline idea N056 stays open for appropriately qualified data. This cache subset does not
establish that such a record is unavailable elsewhere.

## Reproduce the fixed record

From the repository root, fetch the pinned public subsets if missing:

```sh
python -S scripts/fetch_corpus.py pronto
python -S scripts/fetch_corpus.py pronto-more
```

Then use Python 3.10+, standard library only, offline:

```sh
python -S examples/historian-csv/baseline-context/run.py --check
python -S examples/historian-csv/baseline-context/run.py --out out/pronto-baseline-context
```

Each command executes twelve actual band CLIs: eight paired scores and four separate original full-score
controls. Temporary CSVs retain original numeric text and reconstructed timestamps; no samples are pooled,
interpolated or imputed. `--check` compares both committed records. `--out` requires a fresh destination.
Use `--source-root PATH` for a copy of the `data/external` cache. Missing or changed originals refuse before
report publication. No implicit fetch, source repair or operational connection is involved.

The runner is a fixed research record. For another site's exports use [csv_normal_bands.py](../../../scripts/csv_normal_bands.py)
after reviewing the baseline's scope, operating conditions, timing, configuration and known disturbances.
The existing CSV format and method limits are in the [historian guide](../README.md). This record alone cannot
qualify a site's baseline or identify a fault's cause.

## Hand the question to the company owner

Keep the original records, selected windows, tool revision, all outcomes and the unresolved brief together.
Ask the responsible engineering/data owner which operating and configuration records establish comparability.
No owner, accepted handoff or measured benefit exists in this public example. Move ongoing ownership, decisions
and revision history into the company's shared context system when an actual recipient accepts the packet.
This adds no local governance service, automated baseline selector or connector.

Source: A. Stief, R. Tan, Y. Cao, J. R. Ottewill, N. F. Thornhill and J. Baranowski,
*A heterogeneous benchmark dataset for data analytics: Multiphase flow facility case study*, Journal of Process
Control 79 (2019), 41-55, [doi:10.1016/j.jprocont.2019.04.009](https://doi.org/10.1016/j.jprocont.2019.04.009).
[PRONTO data, Zenodo 1341583](https://zenodo.org/records/1341583), CC BY 4.0. This derived case adds window choices,
statistics and a records question; originals remain unchanged and outside Git.
