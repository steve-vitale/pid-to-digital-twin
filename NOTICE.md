# Notices

**Code** in this repository is MIT licensed (see `LICENSE`).

**Data derived from PID2Graph** (Zenodo record 14803338, CC BY-SA 4.0, including the OPEN100 design by the Energy
Impact Center) is shared under **CC BY-SA 4.0**, as that license requires. This covers:
- `data/sheet_registers/`;
- the extracted twin packages under `out/twin/` (plant models, review queues, SVGs, Ignition and PI AF files built
  from the drawings);
- the Perspective screens in `out/ignition/gateway/PIDTwin.zip`, which embed those SVGs and the greyed drawings;
- images made from the drawings: `docs/screenshots/before-after-sheet0.png`, `scan-levels.png`, the OPEN100 screen
  captures, and `docs/demo.gif`;
- `data/drawings/`: the 12 OPEN100 drawings, greyed and downscaled as screen backgrounds
  (`scripts/ignition/prepare_drawings.py`);
- `data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100 scan-L1` to `scan-L3`: degraded "old scan" copies
  of six drawings (`scripts/degrade_scans.py`), with their answer keys.

**PID2Graph files redistributed unchanged**, under CC BY-SA 4.0 with credit to the PID2Graph authors and the Energy
Impact Center: the 12 OPEN100 drawings and their answer keys in
`data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/`, so nobody has to download them to reproduce the
results. The holdout-B drawings are not included; `scripts/fetch_pid2graph.py` downloads them.

**Tennessee Eastman** simulation code and data are from the Braatz group (University of Illinois, NCSA-style
license). They are downloaded by `scripts/verify_te_source.py` and `scripts/fetch_te_data.py`, not redistributed.
The process is from Downs & Vogel (1993). The flowsheet in this repo is redrawn from the model, not copied from the
paper.
