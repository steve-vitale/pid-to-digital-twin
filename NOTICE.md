# Notices

**Code** in this repository is MIT licensed (see `LICENSE`).

**Data derived from PID2Graph** (Zenodo record 14803338, CC BY-SA 4.0, including the OPEN100 design by the Energy
Impact Center) is shared under **CC BY-SA 4.0**, as that license requires. This covers:
- `data/sheet_registers/`;
- the timed-review kit in `out/review_kit/` (one sheet's drawing, overlay and review queue);
- the extracted twin packages under `out/twin/` (plant models, review queues, SVGs, Ignition and PI AF files built
  from the drawings);
- the Perspective screens in `out/ignition/gateway/PIDTwin.zip`, which embed those SVGs and the greyed drawings;
- images made from the drawings: `docs/screenshots/before-after-sheet0.png`, `docs/social-preview.png`, `scan-levels.png`, the OPEN100 screen
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

**PID2Graph Synthetic** adaptation and evaluation material (including summaries in `out/`) derives from
[PID2Graph, Zenodo record 14803338](https://zenodo.org/records/14803338), by Jan Marius Stürmer, Marius Graumann
and Tobias Koch. Synthetic symbols: copyright 2023 Steven Baltakatei Sandoval. This dataset-derived material is
shared under [Creative Commons Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/).
Changes include adaptation, normalization and evaluation summaries; the source Synthetic images and labels are
not included in this publication. This attribution does not change the MIT license for repository code or any
other source license stated above.

**DEXPI example P&IDs** (round 5) are from the DEXPI initiative's public
[TrainingTestCases repository](https://gitlab.com/dexpi/TrainingTestCases), commit `a23d61e2`, licensed
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). The drawings, XML
files and item lists are downloaded by `scripts/adapt_dexpi.py` and are not redistributed. Material derived from
them (scores, summaries and any committed review-kit images in `out/`) is shared under CC BY 4.0 with credit to the
DEXPI initiative and its contributing members. Changes: rasterised to PNG, converted to this repository's
answer-key format, and scored.
