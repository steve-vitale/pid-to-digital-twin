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
- `out/open100_structural/` (flow directions, plant structure, mimic views, 3D scene, isolation points, and the
  spot-check crops of the drawings), `data/open100_equipment_schedule.json` (equipment schedules transcribed from
  the drawings), `data/open100_direction_confidence.json`, and the images in `docs/screenshots/open100/`;
- `data/drawings/`: the 12 OPEN100 drawings, greyed and downscaled as screen backgrounds
  (`scripts/ignition/prepare_drawings.py`);
- `data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100 scan-L1` to `scan-L3`: degraded "old scan" copies
  of six drawings (`scripts/degrade_scans.py`), with their answer keys;
- `docs/screenshots/te-pid-style-side-by-side.png`, whose left half is a crop of OPEN100 sheet 6.
- `examples/statement-review/bound-sheet0/`: statements and drawing crops from OPEN100 sheet 0, with cropping,
  JPEG conversion and an explicitly fictional review exercise. Credit to the PID2Graph authors Jan Marius
  Stürmer, Marius Graumann and Tobias Koch, and to the Energy Impact Center for the OPEN100 design.

The **generated Tennessee Eastman P&ID sheets** in `data/te_pid/` (images, SVG, answer keys) are drawn by this
repo's code from this repo's own process model, so they are MIT licensed like the code. Their drafting style
imitates the OPEN100 sheets' conventions (symbol shapes, sizes, line weights, flags, title-block layout); no
OPEN100 artwork, logo or text is copied into them.

**PID2Graph files redistributed unchanged**, under CC BY-SA 4.0 with credit to the PID2Graph authors and the Energy
Impact Center: the 12 OPEN100 drawings and their answer keys in
`data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/`, so nobody has to download them to reproduce the
results. The holdout-B drawings are not included; `scripts/fetch_pid2graph.py` downloads them.

**Tennessee Eastman** simulation code and data are from the Braatz group (University of Illinois, NCSA-style
license). They are downloaded by `scripts/verify_te_source.py` and `scripts/fetch_te_data.py`, not redistributed as files. The one exception is the draft interactive tour pages in `drafts/interactive-tour/page/`, which embed values from the test runs `d00_te.dat` and `d06_te.dat`; they are redistributed under the permission notice in the Braatz group's `TE_process` archive readme, reproduced verbatim in `drafts/interactive-tour/TE_DATA_NOTICE.txt` and summarized on each page. `examples/historian-csv/*.csv` carry XMEAS 1-22 of the same two runs, under the same notice, reproduced in `examples/historian-csv/TE_DATA_NOTICE.txt`. `data/te_control_loops.json` restates the controller pairings, setpoints and tuning read from the archive's closed-loop code (`temain_mod.f`), under the same permission notice.
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
files and item lists are downloaded by `scripts/adapt_dexpi.py` and are not redistributed, except for the one
unchanged 6,144-byte training XML `examples/source-handoff/fixture/I01V01-VER.EX01.xml` from commit
`a23d61e2e089eb2ca464cd552f9ae580a2785963`. That original and its adapted
`embedded.model.json` (Native conversion plus the complete existing policy-filtered source packet) are
redistributed under CC BY 4.0 with credit to the DEXPI initiative and its contributing members; they are not
MIT-only. Exact original path, license and adaptation details are adjacent in `PROVENANCE.json` and the example
guide. The XML remains unchanged; no blanket permission for company source data is implied. Material derived from
them (scores, summaries and any committed review-kit images in `out/`) is shared under CC BY 4.0 with credit to the
DEXPI initiative and its contributing members. Changes: rasterised to PNG, converted to this repository's
answer-key format, and scored.

**AVEVA AF SDK sample**: the unit-of-measure list in `data/pi_builder_reference.json` (`uom_sample.units`: class,
name and abbreviation) is extracted from `AF Database - Green Power Company.xml` in
[AVEVA/AF-SDK-Getting-Started-Guide](https://github.com/AVEVA/AF-SDK-Getting-Started-Guide), licensed under the
Apache License 2.0. Only those three fields were extracted; nothing else from that file is included. AVEVA, PI System, PI Builder and
PI AF are AVEVA trademarks. This project is not affiliated with or endorsed by AVEVA.

**MetroPT-3 context packet**: selected transcriptions, computed released-file observations and the proposed
question/answer material in `examples/context-register/metropt3/` derive from *MetroPT-3 Dataset*, N. Davari,
B. Veloso, R. Ribeiro and J. Gama, UCI Machine Learning Repository,
[doi:10.24432/C5VW3R](https://doi.org/10.24432/C5VW3R), under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
Changes include source-scoped identities, explicit uncertainty, collection prompts and synthetic software
revision controls. The original PDF and CSV remain unchanged in the ignored cache and are not redistributed.
Packet helper code remains MIT licensed like the repository code.

**anatomy** (MIT License, Copyright (c) 2026 Ryan, [github.com/wheresryan22/anatomy](https://github.com/wheresryan22/anatomy),
commit `e6600ff`): the interactive process tour in `drafts/interactive-tour/` vendors four files of its drawing kit
unchanged, `kit/iso-kit.mjs`, `kit/lathe.mjs`, `kit/tube.mjs` and `kit/audit.mjs`, with the MIT licence text in
`drafts/interactive-tour/kit/LICENSE`. `drafts/interactive-tour/cdp.mjs` adapts its `scripts/drive.mjs` and
`scripts/chrome-port.mjs` (headless Chrome over the DevTools protocol), and `build.mjs` follows the patterns of its
`examples/raptor-engine/build.mjs` (pipes, valves, seated nozzle pads, the audit hook). Those adapted files remain
under the MIT licence of their origin.

**Atkinson Hyperlegible** (Regular), copyright 2020 Braille Institute of America, Inc., licensed under the
[SIL Open Font License 1.1](https://openfontlicense.org), is the label typeface of the 3D orientation tour. It is bundled
as `assets/fonts/AtkinsonHyperlegible-Regular.ttf`, with the licence text in `assets/fonts/OFL.txt`
(source: the google/fonts repository, `ofl/atkinsonhyperlegible/`), and the OPEN100 structural tour uses it too.
The font is bundled unmodified; the OFL allows bundling and
redistribution with software, but not selling the font by itself.


## MGPI source-adapted development case

The model, adapted narrative, draft drawings and derived source inventories in `examples/from-description/mgpi/` are repository-authored development artifacts. They cite the U.S. Chemical Safety and Hazard Investigation Board, *Key Lessons for Preventing Inadvertent Mixing During Chemical Unloading Operations*, report 2017-01-I-KS, December 2017, https://www.csb.gov/file.aspx?DocumentId=6047. The original PDF is fetched only into ignored local source storage and is not redistributed. No CSB report figure or third-party photograph is republished. Project aliases, proposed geometry and agent-derived interpretations are not CSB plant tags, answer keys, approved designs or current installed-state evidence. See the case guide for exposure and source-revision limits.
