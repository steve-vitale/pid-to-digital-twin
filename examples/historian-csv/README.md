# Your own historian export: replay it over OPC UA and learn normal bands from it

The Tennessee Eastman (TE) screens get their values from `scripts/ignition/te_sim_server.py` and their normal bands
from `scripts/normal_bands.py`. Both read the TE `.dat` files only. The two tools here do the same jobs for **any**
historian-style CSV, so a plant can try them on its own export:

- `scripts/csv_replay_server.py` replays the CSV over OPC UA, one row per step (read-only nodes, same conventions as the
  TE server). It is not a simulator: the values are the recorded ones and do not respond to anything.
- `scripts/csv_normal_bands.py` learns per-tag normal bands from a CSV of normal running, with the method of
  `normal_bands.py` (mean ± K population standard deviations on the first half; K = the smallest of 3, 4, 5, 6 whose
  worst per-tag false-flag rate on the held-out second half is under 0.5%), then scores a second CSV.

Both are stdlib plus `asyncua` (for the server only). Nothing here uses a model.

## The CSV shape

```
minutes,FT-101,FT-102,...        <- header: time/index column name, then tag names (unique, non-empty, not numbers)
0,0.24889,3702.3,...             <- first column: an ISO 8601 timestamp or a number (sample index / elapsed time)
12,0.24563,3698.0,,Bad,...       <- a blank or non-numeric cell is a BAD sample for that tag, never a number
```

Comma-separated, with `.` as the decimal point. A malformed header (missing, duplicate or empty tag names), a row with the wrong number of cells, or a first-column
value that is neither a number nor a timestamp is refused with a message naming the line.

## Files

| File | What it is |
|---|---|
| `te_normal_d00.csv` | TE test run `d00_te.dat` (normal operation), all 960 rows, XMEAS 1-22 (the 22 continuous measurements) |
| `te_fault6_d06.csv` | TE test run `d06_te.dat` (fault 6, A feed loss, switched on at row 160), same rows and columns |
| `with_gaps.csv` | Rows 0-19 of `te_normal_d00.csv` with four cells deliberately emptied (see below) |
| `results/csv_normal_bands.md`, `.json` | Bands fitted on `te_normal_d00.csv`, fault-6 CSV scored |
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

# Replay over OPC UA (Ctrl+C to stop). Node ids: ns=2;s=CSV/<column>, plus CSV/_sample and CSV/_time
python scripts/csv_replay_server.py --csv examples/historian-csv/te_fault6_d06.csv --port 4871 --rate 1 --loop

# Tests (synthetic CSVs; TE agreement when the TE cache is present; a live OPC UA smoke when asyncua is installed)
python scripts/test_csv_tools.py
```

`--fault-start` takes a 0-based data-row number (an integer, `160`), or a first-column value: a timestamp
(`"2026-10-01 09:40:00"`) or a number with a decimal point (`480.0`) picks the first row at or after it. With timestamps, delays are in seconds. `--k 5` fixes K instead of choosing it;
`--fit-fraction` changes the fit share (default 0.5). For an Ignition OPC UA connection to the replay, point it at
`opc.tcp://<host>:<port>/csv-replay` with no security, as for the TE server.

## Results on the TE export

From `results/csv_normal_bands.md`: K = 6 (worst-tag held-out false-flag rate 0.0%; K = 5 would be 3.1%, TT-118).
On the fault-6 export: first flag at the fault itself (row 160, FT-101, 0 minutes), detection by the 3-consecutive
rule at 0 minutes, 0 of the 160 pre-fault samples flagged, 100% of post-fault samples flagged. 13 of 22 tags leave
their band; the first are FT-101 (0 min), JT-120 (21), PT-116 (66), PT-107 (90), PT-113 (93).

### (a) Agreement with `normal_bands.py` and `fault_detection_eval.py` for fault 6

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
the held-out false-flag table before trusting the bands, and fit on a period you know was normal. A value outside its
band says "unusual compared with this export", not why.
