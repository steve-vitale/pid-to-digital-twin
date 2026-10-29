# Statement review pilot: the OPEN100 sheet 0 extraction and the Bayer model, as plain sentences

**Why it matters:** every output here can be said as plain statements, each with a source (a box on a drawing, a
page of a report, a field of a model). Checking a random, stratified sample of them against those sources turns
"does this look right?" into a measured error rate, and lets an operator check a unit in plain English instead of
JSON. Two verdicts are kept apart: **matches its source** (anyone can check) and **true in the plant** (only an
operator, a walkdown or live data, and only for statements that matched). Guide: [`docs/STATEMENT_REVIEW.md`](../../docs/STATEMENT_REVIEW.md).

## First sampled review (2026-10-29): what it measured

An independent agent with fresh context checked each sample against its source: the Bayer statements against the
cited report pages and figures, the sheet-0 statements against the drawing, following every traced line at full zoom.
Only **matches its source** was judged. **True in the plant** is empty: that needs someone who knows the unit. The
filled sheets and the `score` output are in `bayer/review-2026-10-29/` and `sheet0/review-2026-10-29/`.

| Sample | Doesn't match its source | 95% interval | Weighted to all statements | Unclear |
|---|---|---|---|---|
| Bayer model (written from the report) | 5 of 57 (8.8%) | 3.8% to 18.9% | 7.9% | 3 |
| Sheet 0 extraction, "joined" read as on the same line network | 2 of 60 (3.3%) | 0.9% to 11.4% | 1.9% | 0 |
| Sheet 0 extraction, "joined" read as next to each other | 24 of 60 (40%) | 28.6% to 52.6% | 40.6% | 0 |

**Why sheet 0 has two rows.** The extraction links every pair of items that lines, bends and junctions join with no
symbol in between, which is how this repository's scorer reads the public answer key (the key itself is a graph
of symbols joined through connector and crossing nodes; the scorer links every pair it reaches). The sentences say "X and Y are joined by a
line", and most readers will take that to mean a pipe runs from one to the other. Only 5 of the 27 "joined" statements
in the sample were next to each other. The other 22 were on the same branched network, through up to six tees.
Read as written, 3.3% of statements were wrong. Read the way a person would, 40% were. Since then the link is no
longer one relationship standing in for two facts: the graph has a pipe layer (what is piped directly to what,
through which junctions), a network layer, and the pairwise links typed as network co-membership, each with its own
wording ([the layered sample](#the-layered-sample-and-its-review-2026-10-29), [line layers](../../docs/GRAPH_EXPORT.md#three-layers-for-the-lines)).
This review measured the earlier wording and stays as that measurement.

**What the reviewers found wrong**
- Bayer, in the model itself:
  - FT-106's unit is klb/h. Its cited figure is in pounds per hour; the klb/h axis is another figure's.
  - The 135 C setpoint cites p. 29. The sentence is on p. 30, and it describes the contents' temperature, not a
    controller setting.
  - TT-105's cited page doesn't support it.
  - "TT-104 was also tagged TI-104" appears nowhere in the report.
  - Stream S6 is drawn leaving the pump. In Figure 10 it branches off the common return, after the heater and cooler.
- Sheet 0:
  - TE 14089A attaches to a thermowell tap, not to the valve below it.
  - The sheet's description is import metadata, not text on the drawing.
- Wording that misleads even when the data is right:
  - Tags this project assigned (PT-101, TV-104A) and the model's own labels ("Solvent fill valve") appear as if the
    report used them.
  - The extracted class "tank" is used for a steam superheater.
  - The trap letter "T" is reported as a duplicate tag.
  - Valves with tag bubbles are called instruments in one sentence and valves in another.

**What happens next:** fix the five model errors and the sentence wording, then re-review a fresh sample. This review
stays as the measurement of the version it saw. It is not overwritten.

## What's here

| File | What it is |
|---|---|
| `sheet0/statements.json` | All 1,073 statements from [`sheet0_graph.json`](../graph-export/sheet0_graph.json) (the extracted OPEN100 sheet 0), with sources, evidence pointers, ranks, groups and layer |
| `sheet0/review_sheet.csv` | The full sheet, verdicts empty |
| `sheet0/sample_60.json`, `.csv`, `.html` | The seeded stratified sample of 60 the 2026-10-29 review measured, drawn from the 704 statements of the version before the line layers (their ids are unchanged; their wording has changed since), its sheet, and its review page with the drawing crops it shows (`sheet0/evidence/`) |
| `sheet0/sample_layers.json`, `.csv`, `.html` | The sample of 60, 15 per relationship layer (seed 1030), that the 2026-10-29 layered review measured (`review-2026-10-29-layers/`); kept as drawn from that day's statements |
| `sheet0/sample_layers_r2.json`, `.csv`, `.html` | The sample the r2 review measured: 75 statements, 15 for each of the five layers (seed 1031), drawn from the 1,078 statements of that day's version; kept as drawn |
| `bayer/statements.json` | All 215 statements from [`bayer_graph.json`](../graph-export/bayer_graph.json) (the CSB residue-treater model), with the cited report pages, the matching report line where one was found, and the machine check |
| `bayer/review.html`, `bayer/review_sheet.csv` | The full review page and sheet |
| `bayer/sample_60.json`, `.csv`, `.html` | The seeded stratified sample of 60 the 2026-10-29 review measured, drawn from the 208 statements of the version before the model's own notes were exported; kept as drawn |
| `bayer/evidence/` | The report's Figure 10, 11 and 19/20 pages, rendered small (a figure is a drawing; it can't be quoted) |

The full sheet-0 review page is not committed: it would carry 700 crops. Regenerate it (below); the sheet image is in
the repository.

## The statements

| | Sheet 0 (drawing extraction) | Bayer (hand-built from a report) |
|---|---|---|
| Statements | 1,073: 188 identity, 151 attribute, 734 relation | 215: 44 identity, 111 attribute, 60 relation |
| By layer | 354 item, 345 pairwise (same line network), 222 network (48 networks and what is attached), 118 pipe (28 pipe tees, 90 pipe segments), 34 lines that are not pipe (10 instrument taps, 20 instrument connections, 2 actuator stems, 2 nozzle stubs) | 200 item (7 of them the model's own notes, exported since round 4), 15 stream (the model's process streams, already pipe-level) |
| By rank | 795 connection, 277 identity, 1 descriptive; **no control or safety relation and no value with units was extracted** | 33 control/safety, 46 connection, 12 value with units, 79 identity, 45 descriptive |
| Evidence | 609 with a crop of their own drawing box (items, junctions, networks); 459 traced links and drawn lines with no source of their own, shown as a crop of both ends; 5 with no source and no crop (the plant, the drawing-area system, its description and code, and its place in the plant) | 206 cite report pages (57 with a matching report line quoted, 149 page/figure only); 9 with no source of their own (the plant, the battery limit and the model's 7 notes about itself) |
| Machine check | none possible: no structured source in the repository | 206 match their model field (this proves only that the export is faithful to the model); 2 not checked |

Strata are statement type x rank (`identity|4`, `attribute|1`, `relation|2`, ...). Each stratum gets at least two
statements, the rest in proportion to size; seed 1029. Sheet 0 (the 704 statements of the version reviewed): attribute|2 6 of 61, attribute|4 8 of 94,
attribute|5 1 of 1, identity|4 9 of 102, relation|2 36 of 446. Bayer (the 208 statements of the version reviewed): attribute|1 6 of 19, attribute|3 4 of 12,
attribute|4 10 of 35, attribute|5 11 of 38, identity|4 12 of 44, relation|1 4 of 14, relation|2 13 of 46. Small
strata are over-sampled on purpose; `score --sample` weights them back.

## The layered sample, and its review (2026-10-29)

An independent agent checked this sample on the drawing, judging each statement by its own wording. The result is in
`sheet0/review-2026-10-29-layers/`.

| Layer | Doesn't match the drawing | 95% interval | Unclear |
|---|---|---|---|
| Network (a line network and what is on it) | 0 of 15 | 0% to 20.4% | 0 |
| Network pair (two items on the same network) | 0 of 15 | 0% to 20.4% | 0 |
| Item (identity and attributes) | 0 of 13 | 0% to 22.8% | 2 |
| Pipe (what is piped directly to what) | 3 of 15 (20%) | 7.0% to 45.2% | 0 |

Once the wording said what the link means, the network statements held up. All three pipe errors had one cause: a
valve's actuator stem (to its M or H box) and an instrument's leader line were treated as pipe. The reviewer also
found:
- "junctions" that are instrument taps rather than pipe tees;
- a tee next to a check valve that was missed;
- two leader-and-stem pairs that meet only inside a valve body but were merged into one network, against the
  layer's own rule;
- "tank" used for a steam superheater.

What changed since (`scripts/line_layers.py`, `scripts/statements.py`; rules in
[GRAPH_EXPORT.md](../../docs/GRAPH_EXPORT.md#three-layers-for-the-lines)):
- each drawn line is classed by what it joins: a line to an instrument bubble is an **instrument connection**, the
  stem from a valve to the small symbol stacked on it is an **actuator stem** (`actuated_by`), the stub from a nozzle
  mark to its vessel is part of the vessel (`nozzle_of`); only the rest is pipe (`piped_to`), with its own layer
  `non_pipe` for the others. On sheet 0: 90 pipe segments (was 123), 20 instrument connections, 2 actuator stems
  (H on S0-VL022, M on S0-VL023), 2 nozzle stubs (N1, N2);
- junctions have a kind and are worded by it: 28 pipe tees and 10 instrument taps (the PT taps at y 276 and the TE
  thermowells). A tap does not split the pipe: the segment runs past it and the tap names the segment it is on;
- the tee where the drop from MS 14010 meets the main line beside MSCV-XXX is found (S0-JN-537-274): a meeting point
  just outside an item's box is the item's own drawing unless its arms lead away to two or more other items;
- MSV 1404's and MSV 1405's leaders now go to their valves, not to the H and M boxes. Their networks (S0-NET018,
  S0-NET019) stay one network each, because the network layer is the tracer's and the pairwise links (and every
  score) come from it; the statements now say that their lines meet only at the valve's edge and hold no pipe;
- "tank" is said as the extraction's class ("classed as a tank by the extraction"), and "belongs to ... (assigned by
  tracing the lines)" as "the extraction attributes it to ... by tracing the lines".

**Re-review of the fix (r2, 2026-10-29).** A fresh independent agent checked a new sample (`sheet0/sample_layers_r2.*`,
75 statements, seed 1031) on the drawing. The result is in `sheet0/review-2026-10-29-layers-r2/`.

| Layer | Doesn't match the drawing | 95% interval | Unclear |
|---|---|---|---|
| Pipe | 0 of 15 (was 3 of 15) | 0% to 20.4% | 0 |
| Non-pipe (instrument lines and taps, actuator stems, nozzle stubs) | 0 of 15 | 0% to 20.4% | 0 |
| Network | 0 of 15 | 0% to 20.4% | 0 |
| Network pair | 0 of 15 | 0% to 20.4% | 0 |
| Item | 1 of 14 (7.1%) | 1.3% to 31.5% | 1 |

Every sampled line kind was right. The one error was not in the lines. "MSBV 1407 is a valve in a moisture loop" came
from reading the plant's own tag prefix (MS, main steam) as the ISA-5.1 first letter M (moisture), and MSIV, MSV and
MSCV on the sheet have the same problem. The reviewer also found two wordings that say more than the data:
- An instrument kind is described as the extraction's class, though it comes from the tag letters.
- "By tracing the lines" is used where the item was attached by nearest position.

One line was miscounted too: a flow element's outline touching its transmitter bubble was counted as an instrument
line. Both reviews stay as the measurements of the versions they saw.

What changed since r2:
- a letter group that starts with a system code seen on its own sheet is the plant's tag, not ISA letters
  (`build_twin.plant_coded`; MS... on the MSS sheet): MSIV 1402, MSV 1404, MSV 1405 and MSBV 1407 have no measured
  variable now and their kind is "valve (plant-coded tag)"; MS 4010 has neither (5 of 36 instruments on this sheet; on
  the OPEN100 extraction, 5 of 359, all on sheet 0). MSCV-XXX is a valve symbol, not an instrument, so it never had a
  variable. Their five "moisture" statements are gone (1,078 statements, now 1,073);
- an instrument kind is said as the tag letters' reading, with the extraction's class beside it: "PSV 1405's tag
  letters read as a valve (PSV: pressure safety valve); the extraction classed the symbol as an instrument bubble".
  Nothing is called a "final element" any more (a PSV is self-acting);
- "by tracing the lines" now follows each item's own method: 16 of the 36 instruments were attached by nearest
  position (`parent_method` geometry_nearest), and say so ("by nearest position on the drawing (to untagged valve
  S0-VL001), then by tracing the lines from it"; "The extraction attaches TCV 1401 to untagged valve S0-VL001, the
  nearest item by position on the drawing");
- the outline-touching line is not fixed: dropping every line between an instrument bubble and an item whose boxes
  touch removed 21 instrument connections on the OPEN100 development sheets, and 20 of them are connections in the
  answer key's own graph (instrument connections F1 0.835 to 0.742). The key counts that contact as a connection,
  so no rule tells this one apart yet; it stays a known limit (`data/attempts.json`).

`sheet0/sample_layers.*` was drawn with one stratum per relationship layer and 15 statements each (seed 1030), so
each layer gets its own error rate. `sheet0/sample_layers_r2.*` does the same over today's five layers (75
statements, seed 1031): `pipe` (is X piped directly to Y, with no tee or other item between? is there a pipe tee where
the junction is placed?), `non_pipe` (is that line an instrument line, an actuator stem or a nozzle stub, and is that
point an instrument tap on a pipe?), `network` (is X on that drawn line network?), `network_pair` (are X and Y on the
same drawn line network?) and `item` (identity and attributes, as before). Each pipe and pairwise statement shows a
crop with both ends outlined; each junction and network statement a crop of where it is. Score it with
`python scripts/statements.py score reviewed_sample_layers_r2.csv --sample examples/statement-review/sheet0/sample_layers_r2.json`:
it prints one rate per layer and no blended one. What the pipe layer gets right where a source has the real topology
(DEXPI, the generated sheets, and a truth derived from the PID2Graph key graph on the OPEN100 development and holdout sheets, and the DEXPI 1.2 vendor renders) is in [EVALUATION.md §7](../../docs/EVALUATION.md#7-which-layer-each-evaluation-measures).

## How an operator uses the sheet

1. Open `sample_60.html` (or the full `review.html`). Statements are grouped by asset, each with its evidence beside
   it: the crop of the drawing box, or the cited report page and the line that best matches.
2. **Column 1, matches its source:** look only at the evidence. `match` if the box or page says this, `mismatch` if
   it says something else or nothing, `unclear` if you can't tell (and why, in the note: a misleading sentence, an
   unreadable crop, a page that doesn't cover it). Ignore what you know about the plant here.
3. **Column 2, true in the plant:** only after a `match`, and only if you know the unit or can walk down to it:
   `confirmed`, `wrong` (it matches the drawing, but the plant is different: the drawing needs a change), or
   `unknown`. The page keeps this locked until column 1 says `match`.
4. Put your name in Reviewer and press "Download the review sheet". Or fill `sample_60.csv` in a spreadsheet.
5. Score it, and if wanted write it back to the graph (statuses and dated events; values never change):

```sh
python scripts/statements.py score reviewed_sample_60.csv --sample examples/statement-review/bayer/sample_60.json
python scripts/statements.py apply examples/graph-export/bayer_graph.json reviewed_sample_60.csv --date 2026-11-02 --out bayer_graph_reviewed.json
```

## Reproduce it

```sh
python scripts/statements.py render examples/graph-export/sheet0_graph.json --image "0=data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/0.png" --out my-sheet0
python scripts/statements.py sample my-sheet0/statements.json --n 75 --seed 1031 --strata layer --floor 15 --out my-sheet0/sample_layers_r2.json
python scripts/statements.py render examples/graph-export/bayer_graph.json --document data/external/csb/Bayer_Report_Final.pdf --out examples/statement-review/bayer
python scripts/statements.py sample examples/statement-review/bayer/statements.json --n 60 --seed 1029 --out my-bayer-sample/sample_60.json
```

`bayer/sample_60.*` is not drawn again either: it was drawn with seed 1029 from the 208 Bayer statements before the model's 7 notes about itself became statements (215 now), so the command above draws a different sample into a scratch folder. All 60 of its statements are still in today's file, unchanged, and the review's scores stand.

`sheet0/statements.json` and `review_sheet.csv` are copied from `my-sheet0/`. `sheet0/sample_60.*` is not drawn again:
it was drawn with seed 1029 from the 704 statements of the version before the line layers (the statements whose layer
is `item` or `network_pair` today; drawing them again gave the same sample until the r2 fixes withdrew one of its
statements, MSBV 1407's kind), and it stays as the sample the 2026-10-29 review measured. `sheet0/sample_layers.*` (seed 1030) is not drawn again either:
the 2026-10-29 layered review measured it, from that day's statements. `sample_layers_r2` (its drawing crops are in
`sheet0/evidence/`) is not drawn again since the r2 fixes: one of its statements (MSBV 1407's moisture loop) was
withdrawn, so the command above now draws a different sample. `test_statements.py` checks that each kept sample
misses only the statements a later fix withdrew.

The report PDF is not in the repository (it is cached by the Bayer scripts from csb.gov). Without it, the Bayer
render still gives every cited page, but no quoted line and no figure image. Quoting used PyMuPDF; `pdftotext` also
works. Statement ids, the samples and the machine check do not depend on either.

## What the author's own read of 20 statements found (not the review)

Before handing this on, the author read 20 rendered statements against their sources (the Bayer report's pages and
Figure 10; the sheet-0 crops). This is a template check, not the independent review, and it is not scored.

- **A wrong page citation in the model:** "TIC-104 is set to hold 135 C (its setpoint)" cites p. 29, but the
  sentence ("maintained at approximately 135 °C") is on printed p. 30. No line is quoted for it for that reason.
- **The model's field name, not the report's words:** RT-1's `mawp_psig` is rendered as "MAWP (maximum allowable
  working pressure, as the model names it)"; the report says maximum allowable *operating* pressure. The sentence
  says so rather than hiding it.
- **A simplification a reviewer may call unclear:** "Stream S6 runs from the recirculation pump P-1 to the battery
  limit": in Figure 10 the discharge branch leaves the return line after the exchangers, not the pump outlet.
- **Extraction classifications rendered faithfully but wrong-sounding:** "PSV 1407 is a final element (valve)" (a
  relief valve is self-acting, not a control final element); an "MSV" bubble's first letter is read as moisture;
  single letters on in-line boxes ("T") are read as tags, so "The tag T appears more than once".
- **Templates fixed during this read:** "FT-103 measures flow at the recirculation pump P-1" implied a location (the
  transmitter is on the return line S10); measurement links now read "measures flow for ...". A rule that called any
  "..SV" tag a safety valve turned "MSV 1404" into "a moisture safety valve", a claim nobody made; only PSV/TSV get
  that wording now, and MSV reads "a valve in a moisture loop" (still the extraction's reading of the letter M).
- Checked and consistent with the source: RT-1 4,500 gal; relief basis 1.0 percent; E-3 80 °C water; LIM-1 30 %;
  LIM-6 155 °C; IL-1 password-protected bypass; IL-3 "operating" and left bypassed; S3, S9, HV-109 on S2, PSV-101 on
  the vessel, FT-103 on S10, U2 and S5 against Figure 10; on sheet 0, the tank/N1 nozzle line, the MSV 1404, PSV 1407
  and TE 14090A crops show what the statement names.
