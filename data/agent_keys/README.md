# Agent-made answer keys

Everything in this folder was made by a coding agent (Claude), not by a person. Each key is a **first pass**: no person
has reviewed it, and it is weaker evidence than a hand key. Use these keys to run the tools on inputs that had no key
at all, and say "scored against an agent-made key" whenever a number comes from one. Do not mix their results with
results on human keys (OPEN100, DEXPI) or on this repository's generated keys (Tennessee Eastman, Bayer).

Made 2026-10-29. The inputs are the corpus entries in `data/corpus.json` that had kind `needs_key` or
`needs_confirmation`. The source images live under `data/external/` and are not committed, so fetch them with the
`fetch` command of each corpus entry.

## What is here

| Folder | Corpus input | Files | Scope |
|---|---|---|---|
| `commons-pid-sheets/` | `commons-pid-sheets` | `<sheet>.graphml`, `key.json`, `key_meta.json` | 5 of the 6 Commons files. `Oil_field_flow_metering.svg` is skipped because it is not a P&ID (see `key_meta.json`). |
| `omre-1958-pid/` | `omre-1958-pid` | `omre_q4.graphml`, `key.json`, `key_meta.json` | **Bottom-right quadrant only**: crop x 2000-4000, y 1633-3266 of the 4000 x 3266 scan. Coordinates are in the crop's pixels. |
| `pronto-fig1/` | `pronto-fig1` | `fig1.graphml`, `key.json`, `key_meta.json`, `controllers_documented.json` | Figure 1 of the technical report, extracted from the PDF unchanged (see `key_meta.json` for page, xref and hash). There is no loop list (see below). |
| `hai-dcs-loops/` | `hai-dcs-loops` | `loops.csv`, `loops_leg2.csv`, `resolution.json` | Loops the HAI technical PDF supports. Unresolved pairings are listed with reasons. |

## Formats

- **`<sheet>.graphml`** follows the PID2Graph key format that `scripts/score_pid2graph.py` (`load_key`) reads.
  - Node `label` is one of `tank`, `pump`, `valve`, `instrumentation`, `inlet/outlet` or `general`, or `crossing` for a
    pipe junction (tee).
  - Node boxes `xmin`/`ymin`/`xmax`/`ymax` are in pixels of the image named in `key_meta.json`. The scorer divides them
    by the PNG's size, so the PNG must be that image at that size.
  - Optional node `text` holds the printed tag.
  - Edge `edge_label` is `solid` (pipe, instrument connection or leader line) or `non-solid` (signal line).
  - Junctions are 8 px `crossing` nodes. That lets `scripts/line_layers.py`'s `pid2graph_truth` derive the pipe-level
    truth (segments and junctions). For every key here, its `networks_match_key_pairs` check is true.
  - Node ids contain no `/`, so row 3's intake accepts them.
- **`key.json`** is this repository's key format (`data/te_pid/key.json`) and is what `scripts/loop_audit.py` reads.
  - Per sheet: `symbols` (class, pixel box, printed `text`) and `edges` (pipes and instrument connections).
  - `signal_edges` are the signal lines, joined through junctions so that each one is a symbol-to-symbol pair.
  - A dashed signal line drawn beside a pipe between the same two symbols is one graph edge in the graphml, and is
    also listed in `signal_edges`.
- **`key_meta.json`** gives, per sheet:
  - who made the key, and the image and its sha256;
  - the licence and attribution;
  - counts by class and by edge kind;
  - what was hard, and the `uncertain` list;
  - the consistency check.

## How the keys were made

- Enlarged crops (Pillow), drawn with a pixel grid, were read by eye.
- Instrument bubbles were placed with Hough circle centres (OpenCV) and then checked by eye.
- Every key was drawn back over its image and checked before it was finalised.
- `Sch_ma_P_ID1.jpg` is a second scan of the same drawing as `Sch_ma_P_ID.jpg`. Its key is the first key moved by an
  affine map fitted on the 19 bubbles the two scans share (residual at most 3.9 px). It is not independent data.
- Two keys were made by separate agent runs of the same model, with the same written brief: `P_ID` and the OMRE
  quadrant. The orchestrating agent reviewed them by overlay.

What counts as a symbol, junction or edge is in the brief that every keying run followed:

- Valves box the body plus its actuator.
- Inline flow elements, reducers, filters, motors and heat exchangers are `general`.
- Tag-bubble leader lines and impulse lines are edges of kind `i`.
- A line crossing with no join mark is not a junction.
- Line labels, flow arrows, nozzle letters, legends and title blocks are not keyed.

Scoring a reader's output against these conventions measures agreement with them. Where a convention is arguable, it
is listed in `key_meta.json` (`hard`, `uncertain`).

## Consistency check: the same agent, not independent

After each key was finished, the agent re-keyed from fresh crops, without opening the key:

- every symbol whose centre falls in a seeded random 20% of a 5 x 4 grid of cells (seed 20261029);
- the links between those symbols.

It then compared the result with the key: symbols at IoU >= 0.5 with the same class, and links as asset-to-asset
pairs. The agent still had its own key in context, so this measures self-consistency at best. It is **not** an
inter-keyer agreement figure, and it says nothing about whether the key's conventions are right. On some sheets the
cells fall mostly on empty paper, so the sample is small. The sample sizes are in `key_meta.json`.

## Licences

- A key annotates its image, so a key of a CC BY-SA image is a derivative and carries the same licence and attribution.
  This applies to `Sch_ma_P_ID`, `Sch_ma_P_ID1`, `Pump_with_tank_pid_en` and `P_ID` (CC BY-SA 3.0; the authors are in
  `key_meta.json`).
- `RI_Sample_ISO` is public domain.
- The OMRE scan is a US Government work and public domain.
- PRONTO is CC BY 4.0 (A. Stief et al., doi:10.5281/zenodo.1341583).
- HAI is CC BY-SA 4.0 (H.-K. Shin, W. Lee, J.-H. Yun, B.-G. Min). The loop lists are derivatives under CC BY-SA 4.0.

None of this is legal advice.
