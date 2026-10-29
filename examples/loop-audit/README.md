# Your own loop list: which loops does the drawing actually show?

**Why it matters:** Drawings drift from what the control system actually runs. A quick check shows which loops a drawing misses before someone relies on it to troubleshoot or plan a change.

`scripts/loop_audit.py` takes a control-loop list (the kind a plant can export from its DCS or PLC configuration) and
a drawing's answer key, and reports each loop as **drawn**, **partly drawn** (with what is missing) or **not drawn**.
It is the drawing half of `scripts/te_control_loops.py`, made to work on any loop list instead of the Tennessee
Eastman code. Stdlib only, no AI, offline.

It grades the drawing against the list. It never judges the control strategy: a wrong list gives a confident wrong
report.

## The loop list

A CSV with a header row. Required columns `controller`, `measurement`, `output`; optional `description`. Any other
column is ignored and named in the report. Lines starting with `#` are skipped.

| Column | Meaning | Example |
|---|---|---|
| `controller` | the controller's tag | `FIC-101` |
| `measurement` | the instrument it reads | `FT-101` |
| `output` | what it moves: a valve or other final element, or for a cascade, the inner loop's controller | `FV-101`, or `FIC-101` for the analyzer cascade `AIC-123A` |
| `description` | free text, copied into the report | `A feed flow` |

Tags match on printed text, ignoring case, spaces and hyphens (`FIC 101` on the sheet matches `FIC-101` in the list).
Nothing else is normalised: strip DCS suffixes such as `.PV` or `/PID1` before exporting. A row with an empty
required field, more fields than the header, a controller listed twice, or a controller that names itself as its
own output stops the audit with that row's line number.

A controller may name itself as its own measurement: that is a **combined instrument**, one bubble that measures and
controls (DEXPI draws `PICSA 4712.02` this way, a sensor, controller, switch and alarm in one symbol). The measurement
is then taken to be inside the controller symbol, so the measurement and signal-in checks pass on the controller
symbol alone and no drawn signal line stands behind them. The report says so: those two table cells read
`combined`, not `yes`, the per-check totals count the combined loops separately, and a note under the table names
them. For such a loop only the controller, the output and the signal line controller -> output are really checked.

[`te_loops.csv`](te_loops.csv) is the worked example: the 19 running Tennessee Eastman loops from
`data/te_control_loops.json`, which `scripts/te_control_loops.py` reads out of the simulator's closed-loop code.
It was exported once and committed; `scripts/test_loop_audit.py` checks it still matches that table row for row.

## Reproduce the Tennessee Eastman audit

From the repository root:

```sh
python scripts/loop_audit.py --loops examples/loop-audit/te_loops.csv --drawing data/te_pid/rev-a/key.json --out out/loop_audit_rev_a
# 0 of 19 loops drawn, 0 partly drawn, 19 not drawn

python scripts/loop_audit.py --loops examples/loop-audit/te_loops.csv --drawing data/te_pid/key.json --out out/loop_audit_rev_d
# 19 of 19 loops drawn, 0 partly drawn, 0 not drawn
```

Each run writes `<out>.md` (a table, one row per loop) and `<out>.json` (the same, with every check); the committed
copies are in [`results/`](results/). Both agree with the original, Tennessee Eastman-only audit: revision A drew no
controller and no signal line, so 0 of 19 (journal entry 50); revision D draws all 19, which is what
[`out/te_loop_audit.md`](../../out/te_loop_audit.md) holds today.

Revision C is a useful in-between case:

```sh
python scripts/loop_audit.py --loops examples/loop-audit/te_loops.csv --drawing data/te_pid/rev-c/key.json --out out/loop_audit_rev_c
# 0 of 19 loops drawn, 19 partly drawn, 0 not drawn
```

Its controllers, valves and signal lines are there, but each measurement is printed as an indicator (`FI 101`) where
the list names the transmitter (`FT-101`). The report says so loop by loop ("missing: measurement symbol; signal line
measurement -> controller") and lists what each controller's signal lines actually reach (`FI 101`), without
assuming the two tags are the same instrument. `te_control_loops.py` also scores revision C 0 of 19; its per-check
counts differ (controller 0/19 there, 19/19 here) because it only counts a controller joined to the listed
measurement, while this tool looks the controller up by its own tag.

## What "drawn" means

On an answer key (this repository's `key.json` format, written by `scripts/draw_pid_from_model.py`), a loop is drawn
when the controller, measurement and output symbols are all printed, a signal line joins measurement and controller,
and a signal line joins controller and output. A loop that crosses sheets counts when the controller is joined to an
outbound signal flag naming the output and an inbound flag naming the controller is joined to the output. Only the
key's `signal_edges` count: a process line joining an indicator to a valve is not a signal. A loop is not drawn when
no symbol carries the controller tag.

## From an extracted drawing

`--drawing` also takes a `plant_model.json` from `scripts/import_site_drawing.py` (see
[the own-drawing runbook](../own-drawing/README.md)) or `scripts/build_twin.py`. An extracted model keeps tags but not
signal lines (the extraction has one kind of connection, and it becomes process streams), so only "controller,
measurement and output tags present" is checked. The best result is **tags present**, never drawn, and the report
says the signal lines were not checked. Read the sheet, or build an answer key, to settle those.

## What it does not check

- whether the control strategy is right (pairings, cascades, tag choices): the list is taken as the truth
- loop numbering: `te_control_loops.py` also requires measurement, controller and valve to share a loop number; here
  the tags come from your own list, so a mismatch would be your tagging convention, not a drawing fault
- controller letters, signal direction, line type (electric, pneumatic, software), fail positions, ranges, alarms,
  interlocks, and controllers on the drawing that are not on the list
- the drawing image itself: it reads the key or the extracted model only

## Tests

```sh
python -m unittest scripts/test_loop_audit.py
```

Reproduces 0/19 and 19/19, the revision C case, a removed signal line (partly drawn), a removed cross-sheet flag
(partly drawn), a removed controller (not drawn, and its cascade's outer loop becomes partly drawn), a tags-only
extracted model, a combined instrument (its measurement and signal-in cells read `combined`, never `yes`), and
refused rows with their line numbers.
