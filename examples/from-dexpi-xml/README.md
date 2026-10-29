# From your own DEXPI XML: a process model that keeps sizes, specs and design limits

**Why it matters:** A plant's own CAD export becomes a model with its line sizes, piping specs, fluid codes and
design pressures and temperatures kept, each value pointing back at the XML element it came from.

[`examples/from-dexpi`](../from-dexpi/README.md) only converts the three public DEXPI sheets that
`scripts/adapt_dexpi.py` has prepared, and drops every attribute on the way. `scripts/dexpi_reader.py` reads a
DEXPI P&ID XML file directly (standard library only, no model, no drawing needed; written for DEXPI 1.x, tested on
the DEXPI 1.3 examples and on DEXPI 1.2 and 1.3 TrainingTestCases files, see [Other tools' exports](#other-tools-exports))
and writes the same kind of
process model that [`examples/from-description`](../from-description/README.md) starts from, so `generate.py` and
`graph_export.py` work on it unchanged.

## Commands

```sh
python -S scripts/dexpi_reader.py --xml my_pid.xml --out my-model --sheet-id unit-47
python -S scripts/generate.py my-model/unit-47.model.json --out my-exports      # Ignition tags, PI AF sheet, SVGs, review sheet
python -S scripts/graph_export.py my-model/unit-47.model.json --out unit-47.graph.json
```

The first writes `unit-47.model.json`, `unit-47.report.json` and `unit-47.report.md` and prints the report. Options:

- `--png drawing.png`: also write an intake prediction and manifest for `scripts/import_site_drawing.py` (the PNG
  must be a render of the whole drawing; this needs the drawing geometry in the XML). On C01 its symbols and
  connections are the same as in `examples/from-dexpi/c01/dexpi-c01.prediction.json` (25 symbols, 37 connections);
  the `producer` and `source` blocks differ, because they name this tool and the input file hashes.
- `--compare-key DIR`: compare against an answer key `scripts/adapt_dexpi.py build` wrote for the same sheet id.
- `--attribution TEXT`: carried in `meta.attribution`.

A file that is not well-formed XML, whose root is not `<PlantModel>`, or that reuses an element ID is refused with
a message and exit code 2; nothing is written. A pipe segment whose `Connection` names an ID the file does not
contain is read, not refused: that end becomes `BL`, the stream's `from_end`/`to_end` says "broken reference", and
the ID is listed under `broken_references` in the report and in the model's `meta` (the real end is unknown).

## This folder (public example C01)

| File | What it is |
|---|---|
| `dexpi-c01.model.json` | the model: 5 units, 12 streams, 3 instruments, 3 final elements, 3 controllers, 7 manual valves, 1 relief device, and its `line_layers`: 17 line networks, 5 junctions (the file's 5 PipeTees), 27 pipe segments |
| `dexpi-c01.report.json`, `.report.md` | what was read, kept, folded and dropped, with reasons; agreement with the adapt_dexpi key |
| `dexpi-c01.graph.json` | `graph_export.py` output: unit, instrument and valve records as sourced claims on their nodes, and each line's records as claims on its `connects` edge (`layer: stream`), plus the pipe layer (`junction` nodes, `piped_to` edges) and the network layer (`line_network` nodes, `on_network` edges); totals in the file's `counts`; `--check` finds 0 problems |

Reproduce (after `python scripts/adapt_dexpi.py fetch`; `--compare-key` also needs `build`):

```sh
python -S scripts/dexpi_reader.py --xml "data/external/dexpi/source/dexpi 1.3/example pids/C01 DEXPI Reference P&ID/C01V04-VER.EX01.xml" --out examples/from-dexpi-xml --sheet-id dexpi-c01 --compare-key data/external/dexpi/sheets --attribution "DEXPI example P&ID C01 (DEXPI reference P&ID, version 4) from the DEXPI TrainingTestCases repository (DEXPI initiative and its contributing members), licensed CC BY 4.0, pinned commit a23d61e2e089eb2ca464cd552f9ae580a2785963. Converted by scripts/dexpi_reader.py; this model is an adaptation under the same license."
python -S scripts/graph_export.py examples/from-dexpi-xml/dexpi-c01.model.json --out examples/from-dexpi-xml/dexpi-c01.graph.json
```

On all three public sheets:

| Sheet | Items | Attribute values in file | Kept on items | Meta only | Dropped (why) |
|---|---|---|---|---|---|
| C01 reference P&ID | 5 units, 12 streams, 3 instruments, 3 final elements, 3 controllers, 7 manual valves, 1 relief | 783 | 727 | 41 | 15 (10 empty, 5 person names) |
| C02 process column | 2 units, 4 streams, 3 instruments, 3 manual valves | 234 | 227 | 5 | 2 (empty) |
| C03 piping | 3 streams, 1 manual valve, 1 unplaced final element | 89 | 74 + 9 on the unplaced item | 3 | 3 (empty) |

`generate.py` passes structural validation and `graph_export.py --check` finds no problems on all three.
Against the `adapt_dexpi.py` keys: every key item is in the model (as its own item, or folded into the stream it sits
on); every drawn key tag is kept as a label record; every attribute value `dexpi_to_twin.py` reports as not carried
on C01 (249 distinct names per item; 432 values) is kept, and likewise 76 on C02 and 13 on C03. Unit-to-unit links
agree: all 7 compared C01 links and the 1 C02 link are in the key; the key's two extra C01 links (`BL - H1008`, `BL - T4750`) are branches of
one tee on the pump discharge, which the key links pairwise because it is undirected, while the model keeps the
drawn direction (both fed from P4712).

## What is kept

- **Every GenericAttribute** of an item, its parts and its connection points, as `{value, uom, source}` under the
  item, keyed by the DEXPI name (a part's attribute is prefixed with the part's XML ID). On C01: pump P4711's
  `DesignShaftPower` 60 Kilowatt, H1007's `Chamber-1:UpperLimitDesignPressure` 60 Bar, line 47121's
  `FluidCodeAssignmentClass` MNb, segment 6's `NominalDiameterRepresentationAssignmentClass` DN 50, the safety
  valve's `SetPressureHigh` 6 Bar, PV-4712.02's fail action FailClose.
- **Drawn labels** as `label:<class>` records, including spec codes like `73KH12-25` and the equipment data bars.
- **Where each item came from**: `dexpi_id`, `dexpi_class` and `source` on every item; `type_basis`, `tag_basis` and
  `unit_basis` wherever something was mapped or inferred.
- **Direction**: streams run in the drawn From/To direction of their pipe segments.
- **The pipe topology** as `line_layers` ([line layers](../../docs/GRAPH_EXPORT.md#three-layers-for-the-lines)): each
  segment chain is pipe; nozzles stand for their unit, valves are their model items, PipeTee elements are junctions,
  off-page connectors and open ends are the battery limit `BL`, and other fittings (reducers, flanges, blinds) are
  passed through. A stream folds a tee; the pipe layer keeps it, so "which valve is piped to which tee" survives.
  Measuring and signal lines are not pipes and are not in it. This is the truth the drawing's traced pipe layer is
  scored against ([EVALUATION.md §7](../../docs/EVALUATION.md#7-which-layer-each-evaluation-measures)).
- **Instruments as the file defines them**: a bubble that drives a valve actuator, or whose letters hold the control
  function C after the first letter, is a controller measuring its own sensor (`PICSA-4712.02` measures
  `PT-4712.02`, the sensor's own number in the file); a plain indicator stays an instrument with its sensor folded in.
  A controller that drives no valve but signals another controller sets its point (`output.setpoint_of`).

## What is lost or changed

- **Line attributes live on edges, not nodes.** `graph_export.py` exports each stream as a `connects` edge and
  carries the line's own records (line, segment, fitting and off-page connector attributes) as claims on that edge;
  a pipe's size or fluid code is found on the edge between its two ends, not on a pipe node.
- **Geometry and presentation are not read**: no positions (`generate.py` lays units out automatically), no flow
  arrows, slope or insulation marks, no shape catalogue, no drawing title block.
- **Equipment types** are the generator's symbol set: heat exchangers, blowers, fans and columns are approximate
  (columns use the trayed stripper symbol), and any class without a type is drawn as a generic vessel and listed.
- **Tees, reducers, flanges, blinds and off-page connectors** are folded into the stream they sit on, not nodes.
- **Units of instruments and valves are inferred** through the piping (first unit upstream, else downstream). A
  line that ends only at a closed end (blind, plug, vent valve) gets `BL` as that end and says so in `to_end` or
  `from_end`. Signal lines between bubbles are kept as `signal_from`/`signal_to` lists, not edges.
- **Items that need a unit and reach none** (C03's shutdown valve ESV 3712 sits on a line with no equipment) go to
  `unplaced`: kept in the model, not exported by `generate.py` or `graph_export.py`.
- **Tags**: valves with no unique identifier use their XML ID (drawn spec codes repeat); the drawn label is kept.
  A hand switch (HS 4750.01) that drives a valve is a controller, so it gets no Ignition tag.
- **Person names** in the drawing metadata are left out on purpose. **Values** stay as written (text) with DEXPI
  unit names (`Bar` is as written; the drawn labels say barg); nothing is converted.

## Other tools' exports

The DEXPI TrainingTestCases (`scripts/fetch_corpus.py`, `data/external/dexpi-ttc-all`) hold DEXPI 1.2 exports from
SPPID, Comos, AVEVA and AutoCAD with the DEXPI reference solutions, and 31 small DEXPI 1.3 single-feature cases.
On 2026-10-29 the reader learned the structures those files use (each with a synthetic test in
`scripts/test_dexpi_reader.py`, `ToolExportStructures`). First change:

- DEXPI 1.2 names the operated valve with a `ShutOffValveReference` (1.3: `OperatedValveReference`) and puts the
  valve's tag on it as `SubTagNameAssignmentClass`; any actuating system component that refers to a piping
  component now operates it, and the valve may say so itself (`is referenced by`).
- The 1.3 single-feature cases give the actuating system no number; the valve carries it
  (`PipingComponentNumberAssignmentClass`, e.g. `FV 04`). Before, such a valve was tagged by its XML ID.
- A bubble whose letters hold C (LICSA, FIC, YCS) is a controller even when the file shows no valve it drives.
- A hand switch written as category H with modifier S is tagged `HS-...` (the modifier is part of the letters).
- Equipment tagged only by the `TagName` XML attribute (DEXPI 1.2) keeps that tag.

The structures were found on a development split written down before the change: all DEXPI 1.2 reference
solutions, the 1.3 C01-C03, and the 1.3 single-feature cases at even positions in file-name order (E02 E04 E06 E08
E11 E13 I02 I04 I06 I08 I10 I12 I14 P01 P03). The vendor exports and the other 16 single-feature cases were run once,
at the end. Results with `corpus_matrix.py`'s own per-file check (row 7) and loop audit (row 4):

| Files | Split | Files pass: before -> first change | Control functions read as controllers | Loops with tags present |
|---|---|---|---|---|
| DEXPI 1.2 reference (11) | development | 9 -> 11 | 0/3 -> 3/3 | 2/2 (none auditable before) |
| DEXPI 1.3 C01-C03 (3) | development | 2 -> 2 | 2/2 -> 2/2 | 2/2 -> 2/2 |
| DEXPI 1.3 single-feature, even (15) | development | 11 -> 11 | 4/5 -> 5/5 | 0/1 -> 0/1 |
| DEXPI 1.3 single-feature, odd (16) | held out | 11 -> 12 | 2/4 -> 4/4 | 0/1 -> 0/1 |
| SPPID (55) | held out | 35 -> 51 | 0/18 -> 18/18 | 0/11 (none auditable before) |
| AutoCAD (54; 6 refused) | held out | 36 -> 40 | 0/16 -> 15/16 | none auditable |
| AVEVA (24) | held out | 22 -> 24 | no control functions | none auditable |
| Comos (41) | held out | 22 -> 22 | 0/7 -> 0/7 | none auditable |

That held-out run found three more dialects, and they were then read too (second change, same day; synthetic tests
in `MoreExportDialects`, real-file checks in `TrainingTestCaseFiles`). **These numbers are after fixing gaps found
on these files, so they are not held out**; the held-out result is the table above (`data/attempts.json` A157).

- **Comos** writes a bubble's letters only as its `TagName` (`FIC`) and the number on its loop (`04`); the tag is
  letters + loop number. It has no ActuatingSystem: the actuator is drawn inside the valve (`Equipment` or
  `Component` nested in the `PipingComponent`) and an information flow joins it to the bubble, in either
  direction. A flow from a bubble to a plant element (nozzle, pipe item, segment) places the bubble there. A
  bubble wired only to another bubble takes the unit of the bubble it signals (also when that is the only link).
- **AutoCAD** ties a bubble to its tank by a `Leader` information flow, or by a pipe segment that ends at the
  bubble; such a segment is not process pipe and places the bubble. Control valves are written as
  `ProcessInstrumentationFunction` elements of class `ControlValve` at a pipe end: read as operated valves.
- **Proteus 3.3.3** (SPPID `C01V01-HEX.EX01`): bubbles are `ProcessInstrument` (or `InstrumentComponent`) elements,
  off-line ones on instrument pipe runs (read as leaders, not pipe) and in-line ones (`IsInline` True, class
  `Controlvalvesandregulators`) as the operated valve itself; the actuator is an `InstrumentComponent` of class
  `Actuator` wired to the controller by a `SignalLine` and tied to its valve by their `InstrumentLoop`; associations
  name their target by GUID in `TagName`, not `ItemID`.

| Files | Held-out result (first change) | After fixing gaps found on these files (not held out) | Control functions | Loops with tags present now |
|---|---|---|---|---|
| SPPID (55) | 51/55 | 52/55 | 18/18 | 11/11 |
| AutoCAD (54) | 40/54 | 45/54 | 15/16 | none auditable |
| Comos (41) | 22/41 | 33/41 | 0/7 -> 7/7 | none auditable |
| AVEVA (24) | 24/24 | 24/24 | none | none auditable |
| DEXPI 1.2 reference, 1.3 C01-C03, 1.3 single-feature | 11/11, 2/3, 23/31 | unchanged | 3/3, 2/2, 9/9 | 2/2, 2/2, 2/2 |

The loop column uses `loop_audit.py` as changed the same day by another lane (it now reads `unplaced` and treats
`P_4712.02` as `P-4712.02`); with the earlier audit the SPPID loops failed on that punctuation and FIC 04 / LICSA 03 on
their unplaced valves. DEXPI 1.2 overall: 43 of 44 control functions read as controllers (0 of 44 before).

What still fails, and why:

- **No unit to place the item on**: 1.3 C03 and every 1.3 single-feature failure, 9 AutoCAD, 3 SPPID (the I11
  files), 4 Comos. The file has no equipment (Comos `I10`), or the item's line reaches none (Comos
  `C01V01-SAG.EX02`, `I07`, `I08`: the one pipe segment has no connection at either end). `generate.py` needs a unit on every instrument and
  final element, so these stay in `unplaced` (kept in the model, exported as unplaced nodes by `graph_export.py`);
  the matrix's row 7 counts only placed items.
- **Nothing in the XML ties the bubble to anything** (Comos `I01V01-SAG.EX01`, `I01V02-SAG.EX01..03`): the level
  indicator has no sensor, no flow, no leader and no loop association, so it has neither a place nor a number; it
  keeps its XML ID and stays unplaced.
- **XML problems, refused or contradictory**: 6 AutoCAD files reuse element IDs and are refused (the matrix confirms
  each reason in the XML). AutoCAD `I05V01_AUD.EX01` writes a control valve as a `ControlValve` instrument function
  with category `IEC` and tag `IEC-?`; it is read as the valve it is, so the matrix, which takes the C in `IEC` as
  a control function, counts it as a missed controller. The structure (control valves as instrument functions) is
  general in AutoCAD's exports and is read; the `IEC` category on a valve is the one-off.

The C01 model, report and graph in this folder are byte-identical before and after the change.

## Limits

Tested on the three public DEXPI 1.3 examples, the DEXPI 1.2 and 1.3 TrainingTestCases, including the 1.2 exports
from SPPID, Comos, AVEVA and AutoCAD (Proteus 3.3.3 for the SPPID ones), and synthetic files
(`scripts/test_dexpi_reader.py`). Those are public test files, not a plant's own export. The reader still does not pass
every one: of the vendor files, SPPID 52 of 55, AutoCAD 45 of 54 (6 more refused for reused element IDs) and Comos 33 of 41
pass the matrix's per-file check, mostly because items stay unplaced (see above), and the vendors disagree with each
other in the XML itself: 10 of 45 vendor exports give different counts from the reference export of the same case, and in 8
of those the XML already differs (`dexpi-1.2-cross-vendor` in [GENERALIZATION.md](../../docs/GENERALIZATION.md)). Other CAD tools write DEXPI differently
still: an element type with no rule is listed in the report, never silently kept or guessed. The model is a draft: nothing in it is verified by anyone, and it is
not a drawing of record.

## Source and license

DEXPI example P&IDs from the [DEXPI TrainingTestCases](https://gitlab.com/dexpi/TrainingTestCases) repository
(DEXPI initiative and its contributing members), licensed CC BY 4.0, pinned to one commit in
`data/dataset_adapters/dexpi_examples.json`. The XML itself is not committed here. The model, report and graph in
this folder are adaptations of example C01 under the same license.
