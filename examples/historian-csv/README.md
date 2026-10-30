# Your own historian export: replay it over OPC UA and learn normal bands from it

**Why it matters:** Normal bands highlight unusual changes in recorded values, and replaying recorded data lets you test new screens without touching the live system.

The Tennessee Eastman (TE) screens get their values from `scripts/ignition/te_sim_server.py` and their normal bands
from `scripts/normal_bands.py`. Both read the TE `.dat` files only. The two tools here do the same jobs for **any**
historian-style CSV, so a plant can try them on its own export:

- `scripts/csv_replay_server.py` replays the CSV over OPC UA, one row per step (read-only nodes, same conventions as the
  TE server). It is not a simulator: the values are the recorded ones and do not respond to anything.
- `scripts/csv_normal_bands.py` learns per-tag normal bands from a CSV of normal running, then scores a second CSV.
  Three methods, and a default that picks between the first two:
  - `--method auto` (the default): `cyclic` when the data has a daily cycle, otherwise `drift`. "Has a daily cycle"
    means: the first column is a timestamp, the fit rows (the first half of the normal CSV) span at least 2 days,
    and a time-of-day profile fitted on them explains at least 0.1 of the variation of the held-out rows (the median
    over tags, each tag's level allowed to move between the halves). The report says which was chosen and why
    (`method_choice` in the JSON, a line in the .md).
  - `--method drift` (for real plant data): each tag is compared with its own recent past. The gap
    between its 10-sample average and its 600-sample baseline is flagged when it is wider than K times that gap's
    normal spread, and never when it is under 1% of the tag's normal reading. Where the tag runs below its normal
    reading the band shrinks in proportion (noise as a percent of reading, as a flowmeter's), to no less than half.
    Slow drift moves the baseline and is not flagged; a step or a fast change is. K is the smallest of 10, 12, 15, 20
    that flags under 0.5% of the held-out normal rows (any tag). The windows count rows, not seconds.
  - `--method cyclic` (for a daily cycle: water demand, shifts, day/night load): each value minus its tag's
    time-of-day profile (the fit rows' mean in each of 48 half-hour slots), then a median of 3 samples so a
    single-sample spike is ignored, then the drift method's gap on what is left. The band is the drift method's
    (K x the gap's normal spread, never under 1% of the reading) but does not shrink with the reading. The daily swing
    no longer sets the band's width, so a step it would hide (a leak's extra flow) shows. Without timestamps the
    profile is flat (one slot per tag) and the report warns.
  - `--method level`: the method of `normal_bands.py` (mean ± K population standard deviations on the first half;
    K = the smallest of 3, 4, 5, 6 whose worst per-tag false-flag rate on the held-out second half is under 0.5%).
    It reproduces the TE scripts exactly (section (a) below), and on real data it flags normal running long before
    any fault, because real plants drift and a short normal window cannot see it.

Both are stdlib plus `asyncua` (for the server only). Nothing here uses a model.

## Which method to use

| Your data | Use | Why |
|---|---|---|
| A real plant historian export: tags drift with ambient, feed, wear | `--method auto` (default), which picks drift unless it finds a daily cycle; `--method drift` forces it | On the development sources (PRONTO, SKAB, HAI 21.03) the level bands flagged normal running before almost every fault; auto picks drift and passes more runs on every one (PRONTO 4/6 against 2/6, SKAB 16/34 against 1/34, HAI 2/2 against 0/2) |
| A stationary simulation, or a plant held at one steady operating point with no drift | `--method level` | It flags a level that stays wrong forever and reacts on the first sample; on the TE runs it detects 16 of 21 faults to the drift method's 14, at 0 min on fault 6 against 18 |
| Timestamped data with a daily cycle (water demand, shifts, day/night load), at least 4 days of normal running | `--method cyclic` (the default `auto` picks it when the cycle is there) | BattLeDIM's simulated water network: 2018 (development) 8 of 14 leaks against 0 with drift and 1 with the level bands; 2019 (held-out year, scored once) 6 of 19 against 0 and 0. It is the same network across years; 2019 detections arrive 14 hours to 5 days late, and tank level T1 drives most flags ([attempts A183-A184](../../docs/TRIED.md)) |
| A cycle not tied to the clock (compressor load/unload, batch steps) or data already averaged per cycle | no method here handles it well | MetroPT-3's compressor: drift 1 of 4 failures, cyclic 0 of 4 (its pressure pulses before two failures flag either way). UCI's hydraulic rig (one row per load cycle): drift 0 of 3; `--method cyclic` (flat profile: only its 3-sample median differs) 2 of 3. A mode found in the data was tried and rejected: a fault can move the tag that defines the mode (`docs/TRIED.md` A183) |

Whichever you use, read the pre-fault and held-out flag counts in the report before trusting a detection.
The median of 3 belongs to `cyclic` only; `drift` keeps its existing timing. UCI, MetroPT-3 and BattLeDIM 2018
were held out for the earlier drift method, then became development inputs for auto/cyclic. BattLeDIM 2019
tests carry-over to another year of that same simulated network, not to a different plant.

## The CSV shape

```
minutes,FT-101,FT-102,...        <- header: time/index column name, then tag names (unique, non-empty, not numbers)
0,0.24889,3702.3,...             <- first column: an ISO 8601 timestamp or a number (sample index / elapsed time)
12,0.24563,3698.0,,Bad,...       <- a blank or non-numeric cell is a BAD sample for that tag, never a number
```

Comma-separated, with `.` as the decimal point. A malformed header (missing, duplicate or empty tag names), a row with the wrong number of cells, or a first-column
value that is neither a number nor a timestamp is refused with a message naming the line.

**Time order matters.** In both normal and scored exports, parsed times must strictly increase: oldest first,
with no duplicate instants. This also applies to replay and is checked before the server is initialized.
An out-of-order record can otherwise select the wrong fault-start row or produce a negative detection delay.
The error identifies the current and previous physical CSV records, including skipped blank lines and quoted
multiline records. Two timestamp strings with different offsets can represent the same instant and are duplicates.

Prepare a separate chronological copy and reconcile duplicate records using the export's source meaning; keep
the original and record that preparation with the evidence packet. The tools do not sort, drop duplicates,
aggregate or resample for you. Uneven but strictly increasing intervals remain supported. Passing this check
does not verify clock accuracy or a uniform sample interval: drift/cyclic windows still count rows, and replay
still uses `--rate` rather than the spacing between recorded times.

## Files

| File | What it is |
|---|---|
| `te_normal_d00.csv` | TE test run `d00_te.dat` (normal operation), all 960 rows, XMEAS 1-22 (the 22 continuous measurements) |
| `te_fault6_d06.csv` | TE test run `d06_te.dat` (fault 6, A feed loss, switched on at row 160), same rows and columns |
| `with_gaps.csv` | Rows 0-19 of `te_normal_d00.csv` with four cells deliberately emptied (see below) |
| `results/csv_normal_bands.md`, `.json` | Bands fitted on `te_normal_d00.csv` with default auto (chooses drift here), fault-6 CSV scored |
| `results/replay_smoke.txt` | Transcript of the replay server serving `with_gaps.csv` to an OPC UA client |
| `TE_DATA_NOTICE.txt` | The Braatz group's permission notice for the TE values in these CSVs |

**Exactly what was exported** (a one-off, not a committed script): for each of `d00_te.dat` and `d06_te.dat` (Braatz
TE data, cached by `python scripts/fetch_te_data.py`), every one of the 960 rows, columns 1-22 (XMEAS 1-22), each
value written with Python's `repr(float(text))` (the same number as the file). The header names come from
`scripts/ignition/te_channels.py` `channel_columns()` (model tag for column index 0-21, e.g. XMEAS 7 -> `PT-107`). The
first column, `minutes`, is not in the `.dat` files: it is the row number x 3, the TE sampling interval, so delays
come out in plant minutes. No subsampling: each file is about 150 KB, so all rows fit under the size budget.
XMV 1-11 and the analyzer channels (XMEAS 23-41) are left out to keep the example to one kind of signal; that is the
only difference from what the TE screens use.

`with_gaps.csv`: rows 0-19 of `te_normal_d00.csv`, with `PT-107` blank and `TT-109` = `Bad` on row 4 (`minutes` 12),
and `FT-101` blank on rows 10 and 11. These gaps are made up to show bad-quality handling; the TE data has none.

## Commands (from the repository root)

```sh
# Bands: fit on the normal export, score the fault export (labelled fault start = data row 160)
python scripts/csv_normal_bands.py --normal examples/historian-csv/te_normal_d00.csv \
    --score examples/historian-csv/te_fault6_d06.csv --fault-start 160 --units minutes \
    --out examples/historian-csv/results
# The TE scripts' fixed-level bands instead (section (a)); not committed, so write it elsewhere
python scripts/csv_normal_bands.py --normal examples/historian-csv/te_normal_d00.csv \
    --score examples/historian-csv/te_fault6_d06.csv --fault-start 160 --units minutes \
    --method level --out out/csv_normal_bands_level

# Replay over OPC UA (Ctrl+C to stop). Node ids: ns=2;s=CSV/<column>, plus CSV/_sample and CSV/_time
python scripts/csv_replay_server.py --csv examples/historian-csv/te_fault6_d06.csv --port 4871 --rate 1 --loop

# Tests (synthetic CSVs; TE agreement when the TE cache is present; a live OPC UA smoke when asyncua is installed)
python scripts/test_csv_tools.py
```

To reproduce the public daily-cycle check, fetch the pinned BattLeDIM 2019 source and run its matrix cell:

```sh
python scripts/fetch_corpus.py battledim-2019
python scripts/corpus_matrix.py --rows 6 --inputs battledim-2019
```

The [source and hash pins](../../docs/CORPUS_FETCH.md) credit S. G. Vrachimis et al., BattLeDIM, Zenodo record
[4017659](https://zenodo.org/records/4017659), CC BY 4.0. Downloaded data stay under `data/external/` and converted
CSVs live only in a temporary folder. Fit = January 1 up to the first leak starting in 2019 (January 15, 23:00);
the four leaks carried over from 2018 are part of this baseline. Each of the 19 runs spans two days before leak
start and up to seven days after it (or repair, if earlier). A run passes when three consecutive flags start at
or after the labelled leak start and at most 0.5% of its pre-fault rows are flagged. Other leaks can already be
running in those pre-fault windows, so a flag is not evidence that the method located the newly starting leak.

`--fault-start` takes a 0-based data-row number (an integer, `160`), or a first-column value: a timestamp
(`"2026-10-01 09:40:00"`) or a number with a decimal point (`480.0`) picks the first row at or after it. With timestamps, delays are in seconds. `--k 5` fixes K instead of choosing it;
`--fit-fraction` changes the fit share (default 0.5). If the fit rows, or the held-out rows K is chosen on, number fewer than 30 (or a tag has fewer than 30 good fit values), the .md and .json carry a small-sample warning: below that a band's sd is a rough estimate, and with fewer than 200 held-out rows one false flag already exceeds the 0.5% K target. The TE example (480 + 480 rows) has none. For an Ignition OPC UA connection to the replay, point it at
`opc.tcp://<host>:<port>/csv-replay` with no security, as for the TE server.

## Results on the TE export

From `results/csv_normal_bands.md` (default `auto`, which picks the drift method here: the `minutes` column is not a
timestamp, so there is no time of day to profile): K = 10 (0 of the 480 held-out rows flagged at any K);
three bands are set by the 1% floor (TT-109, TT-121, TT-122, whose 10-sample averages barely move in normal running).
On the fault-6 export: detection by the 3-consecutive rule at 18 minutes (row 166, FT-101), 0 of the 160 pre-fault
samples flagged, 99.2% of post-fault samples flagged. 13 of 22 tags leave their band; the first are FT-101 (18 min),
JT-120 (54), PT-116 (102), FT-104 (105), PT-107 (123).

**Why 18 minutes and not 0, as with the level method:** A feed loss drops FT-101 from 0.25 to almost nothing in one
sample, but the drift method compares a 10-sample average, which moves a tenth of the way per sample; at the TE's
3-minute sampling it takes 6 samples to clear FT-101's band. At 1-second sampling the same 6 samples are 6 seconds.
The trade was made for real data, where the level method flags normal running before every fault
(`docs/GENERALIZATION.md` row 6). Across all 21 TE fault runs the drift method flags no pre-fault sample in any run,
detects 14 of 21 on these 22 columns (the level method 16), later than the shipped TE bands on 13 of those 14,
and misses faults 4, 11 and 14, which the shipped bands see first in TT-109 and TT-121: those move 0.2-2.4 degC, mostly slowly, so the gap between the
10- and 600-sample averages stays at 0.25 degC or less, inside their bands (1.2 and 0.95 degC, set by the 1% floor;
without the floor TT-109's band would be 0.03 degC, which fault 11's 0.07 degC gap crosses). Use `--method level` on a stationary
simulation like the TE.

### (a) Agreement with `normal_bands.py` and `fault_detection_eval.py` for fault 6 (`--method level`)

With `--method level` the tool is `normal_bands.py`'s method, and on this export it gives K = 6 (worst-tag held-out
false-flag rate 0.0%; K = 5 would be 3.1%, TT-118); first flag at the fault itself (row 160, FT-101, 0 minutes),
detection by the 3-consecutive rule at 0 minutes, 0 of the 160 pre-fault samples flagged, 100% of post-fault samples
flagged. `test_csv_tools.py` re-runs it and checks K, every band and every tag's first flag against the TE scripts.

| | TE scripts (committed outputs) | CSV route (this example) | Same? |
|---|---|---|---|
| K | 6 (`out/ignition/normal_bands.json`) | 6 | yes |
| Worst-tag held-out false-flag rate, K = 3/4/5/6 | 15.8% FT-119 / 6.7% TT-118 / 3.1% TT-118 / 0.0% | the same | yes |
| Band mean, sd, lo, hi for the 22 tags | rounded to 4-5 decimals in the JSON | unrounded | equal within that rounding (largest relative difference 4e-4) |
| Fault 6 first flags (tags in both) | FT-101 160, JT-120 167, PT-116 182 | FT-101 160, JT-120 167, PT-116 182 | yes |
| First flag of every one of the 22 tags | d06_te.dat scored with the committed bands | the same rows | yes (asserted in `test_csv_tools.py`) |
| Detection delay, shipped bands | 0 min (`out/fault_detection/fault_detection.json`) | 0 min | yes |
| Flags before the fault | 0 (pre-onset flag rate 0.0) | 0/160 | yes |
| Post-fault samples flagged | 100.0% | 100.0% | yes |

The differences, and why:

- **Mean-tag and any-tag false-flag rates differ** (e.g. K = 3: mean tag 1.81% here vs 1.33%; any tag 23.8% vs 32.1%)
  because they are averaged over 22 channels here and 52 there. The per-tag rates are identical.
- **FV-101, FV-105, AT-129, AT-123, AT-129-C** appear in the TE scripts' first-flag list and not here: they are valve
  outputs (XMV) and analyzer channels, which this export leaves out.
- **K is chosen over different tag sets**: `normal_bands.py` chooses it over its original 36 scalar tags, this tool
  over every column in the CSV (22 here). Both give 6 on this data; on another tag set they could differ.
- **Not reproduced**: `fault_detection_eval.py` also measures false alarms on `d00.dat` and on the first 160 samples of
  all 21 fault runs, and compares against PCA T². This example is one normal/fault pair only.

No subsampling was done, so none of the agreement depends on it.

### (b) The replay server serves the CSV

`results/replay_smoke.txt`: the server was started on private port 4871 (`--host 127.0.0.1 --rate 2 --start 4`), an
asyncua client read six nodes twice, two seconds apart, and the server was then stopped (process tree killed; no
process left listening on 4871 afterwards). Read 1 is row 4: `PT-107` and `TT-109` read **BadNoData with a null
value**, the other tags Good. Read 2 is row 5: `_sample` moved 4 -> 5, `FT-101` 0.24563 -> 0.24759, and `PT-107`,
`TT-109` are Good again (2704.0, 120.4). A client write to `CSV/FT-101` was refused (BadUserAccessDenied).
`scripts/test_csv_tools.py` repeats this in-process on a free port in about two seconds.

## What this does not show

The TE export is clean, evenly sampled, single-mode simulator data. A real export brings gaps, compression
(repeated values), mode changes and shutdowns in the "normal" period; any of these widen or distort the bands. Look at
the held-out false-flag table before trusting the bands, and fit on a period you know was normal. A flag says
"unusual compared with this export", not why.

On public real-plant data auto still chooses drift for the sources below and does not pass everywhere
([generalization matrix](../../docs/GENERALIZATION.md), row 6; development and held-out runs reported separately
in [the attempts ledger](../../docs/TRIED.md)): no
pre-fault flag on PRONTO test day 3 and HAI 21.03, but normal running is still flagged before the PRONTO day 2
air leak and day 4's second slugging test, and 18 of 34 SKAB runs fail (11 faults missed). On three sources scored
once after the earlier drift method was frozen it passed 1 of 21 runs: UCI hydraulic 0/3 (one or more pre-fault flags in each run, where
none is allowed), MetroPT-3 1/4 (a pulsing dryer-discharge pressure flags normal running), BattLeDIM 0/14 (no leak
detected: the daily demand swing sets the bands, and a leak moves pressure less). Those three sources are now
development data for auto/cyclic: UCI and MetroPT-3 stay at 0/3 and 1/4; auto chooses cyclic for BattLeDIM 2018,
which improves to 8/14. On the held-out 2019 year of that same network it passes 6/19, detects 13/19 and flags too
many pre-fault rows in 7/19. Detections arrive **14 hours to 5 days late**, with tank level **T1 first in 11 of
13 detections**. This is a flag after the labelled start, not proof of leak isolation or early warning; the same
tag also drives most pre-fault flags. The method was not tuned further on 2019.

By design drift misses a fault that develops as slowly as normal drift, and it stops flagging a level that stays
wrong once the 600-sample baseline has
caught up with it.
