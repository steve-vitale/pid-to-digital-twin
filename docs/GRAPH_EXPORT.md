# The twin graph export (twin-graph-1)

`scripts/graph_export.py` writes any plant model this repository produces as one JSON graph that an asset register,
a graph database or a change-management system can load without knowing this repository. Examples:
[`examples/graph-export/`](../examples/graph-export/) (the Tennessee Eastman model, the Bayer model and the extracted
OPEN100 sheet 0).

**Current preservation gaps:** for extracted items with several provenance appearances, the exporter uses the
first appearance's locator; it does not retain the complete provenance list or report that loss. Keep the source
model and original records alongside the graph. See the [audited defects](STATUS.md#known-defects).

The CLI refuses an output that aliases the input model, question file or any consumed `--reviews/*.json`
record, including resolved directory links and existing hardlinks. Choose a separate output path. This local
preflight does not lock files against concurrent changes.

```sh
python scripts/graph_export.py data/te_process_model.json --out te_graph.json
python scripts/graph_export.py my-bundle/plant_model.json --reviews out/review --out my_graph.json
python scripts/graph_export.py --check te_graph.json
```

## Keep known roles when placement is unknown

An item can have a known role without a known owning unit. The exporter keeps an explicit `unplaced.kind` for
equipment, instruments, final elements, controllers, line items, off-page connectors, manual valves and relief
devices. It retains the placement reason, original role/class claims, citations and existing review status. It
does not assign a unit, a physical location or plant truth. An unsupported explicit role becomes a generic
`line_item`; the original role remains an attribute. Older models without an explicit role retain the existing
`OperatedValve`/`actuated` final-element fallback.

For a controller, an explicit `measurement_unplaced` reference becomes a `controls` edge from the represented
instrument to the controller; `output_unplaced` becomes a `controls` edge to each represented final element.
Both fields accept one tag or a list of tags. The original reference claims remain on the controller. The edge
inherits the controller record's source and status: it projects the reader's interpretation, including its
caveats, and does not independently verify physical signal direction. A nonempty malformed reference, a missing
or ambiguous target, or an incompatible target role refuses the export before writing the output file. Resolve
the source/model reference explicitly; the exporter does not guess an alias or reinterpret a manual valve.

The [unplaced DEXPI example](../examples/graph-export/unplaced-dexpi/README.md) follows actual public XML through
the reader and export. Its software checks show retained meaning, not better extraction accuracy or resolved
placement. The original generalization-matrix criteria and failed placement cells remain unchanged.

`examples/graph-export/sheet0_graph.json` is the extracted OPEN100 sheet 0, with its line layers (below):

```sh
python -S scripts/import_site_drawing.py --manifest examples/own-drawing/manifest.json --out my-bundle
python scripts/line_layers.py enrich my-bundle/plant_model.json --image "0=data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/0.png" --out my-bundle/plant_model.json
python scripts/graph_export.py my-bundle/plant_model.json --out sheet0_graph.json
```

## Three layers for the lines

A drawn line carries two facts, and a reader needs to know which one a link states. Not every drawn line is pipe
either: a bubble's leader, a valve's actuator stem and a nozzle stub on a vessel are drawn the same way.

| Layer | In the graph | Means | Where it comes from |
|---|---|---|---|
| Pipe | `junction` nodes (`junction_kind` pipe_tee or marked_crossing), `piped_to` edges | consecutive process items along a run, through bends and past instrument taps, with no pipe tee or other item between; a `touching: true` edge instead records two items drawn against each other with no line between | a drawing: `scripts/line_layers.py` from the tracer's geometry and item boxes; DEXPI XML: `scripts/dexpi_reader.py` from the piping segments (tees are elements) |
| Lines that are not pipe | `instrument_connection` edges (and `junction` nodes of kind instrument_tap or instrument_line_junction), `actuated_by` edges, `nozzle_of` edges | a bubble's leader or impulse line (to a tap on a pipe, an item, or another instrument line); a valve and the actuator stacked on it; a nozzle mark and the vessel it sits on. None of them is a pipe | a drawing: `scripts/line_layers.py` (rules below) |
| Network | `line_network` nodes, `on_network` edges (item or junction to its network) | the items and junctions on one drawn line network: lines that touch outside the item boxes, through bends, junctions or crossings, as the tracer joins them | the same |
| Pairwise | `connects` edges with `layer: network_pair` (and the `network` they share) | both ends are on the same line network. Every pair of a network's members, so derivable from the network layer. **Not** pipe adjacency | the tracer's links, unchanged (every connection score uses them: `score_pid2graph.py` reads the answer key's graph the same way, every pair of symbols reachable through its connector and crossing nodes) |

- **Which line is which** (`item_roles` and `classify` in `scripts/line_layers.py`), from what a line joins, using
  the item classes the extraction gives and the boxes:
  - a line with an instrument bubble (class `instrumentation`) at an end is an **instrument connection**; at a
    junction where instrument lines meet and only one other arm is left, that arm carries the instrument line on;
  - a small symbol classed `general` stacked on a valve (its box at most a quarter of a symbol side from the valve's,
    centred on it and no wider than it across the gap) is the valve's **actuator** when, read without that role,
    every line it has goes to its valve, to a bubble, or to a point where only those meet; the line between them is
    the stem (`actuated_by`, valve to actuator). Lines meeting at the valve or its actuator meet at the valve: a leader
    drawn to the valve that touches the stem there goes to the valve, not to the actuator. A line from an actuator to
    anything else is read as an instrument (signal) line;
  - a symbol whose text reads as a nozzle mark (N1, N2, N12A), within half a symbol side of a vessel (class `tank`, or
    one of the model's units), is that vessel's **nozzle**; the stub between them is part of the vessel (`nozzle_of`);
  - the rest is **pipe**.
  Limits: an actuator drawn inside its valve's box or classed other than `general` is not seen, and one with a signal
  line to something other than a bubble loses the role (its stem then reads as pipe); an untagged nozzle, or one whose
  label was read as something else, keeps its stub as a pipe segment; a process line drawn to an instrument symbol
  (an in-line flow element classed `instrumentation`) would be read as an instrument line.
- **Junction**: a point where three or more line arms meet: a tee, a short stroke joining three or more runs, or an
  item drawn beside a run that carries on past it on both sides. Ids are `<sheet>-JN-<x>-<y>` (position on the
  0-1000 sheet scale; DEXPI: `<sheet>-JN-<PipeTee id>`); each junction claims its `arms`, how it was found
  (`junction_method`) and its `junction_kind`, with a drawing box a reviewer can crop:
  - `pipe_tee`: three or more pipe arms (a tee or branch);
  - `instrument_tap`: an instrument line meets a pipe that carries on through it. **A tap does not split the pipe**:
    the pipe segment runs past it (the segment lists its `taps` in order), the tap names the segment it sits on
    (`on_segment`), and the instrument's `instrument_connection` ends at the tap;
  - `marked_crossing`: a crossing the drawing marks connected with a dot;
  - `instrument_line_junction`: instrument lines meeting away from any pipe.
- **Crossings**: two runs crossing with arms on all four sides. The tracer joins them into one network (its default:
  the answer key passes connectivity through crossings, and splitting them lost recall on the development set), so
  the network and pairwise layers keep that. In the pipe layer a crossing is **not** a junction: each run passes
  straight through, unless the drawing marks it connected with a dot. The dot test: a 4-arm crossing is marked
  connected only if the ink left over beyond the two runs also fills all four corners between the arms (a filled
  disc wider than the lines); stray pixels in some corners (anti-aliasing, a thin line's ragged edge) are not a
  dot. A slanted stroke that carries straight across a run (a label's leader, a dashed outline, hatching) crosses
  it too and does not join it in the pipe layer; the traced output lists those points as `slanted_crossings`. A
  run that stops a line-width past another (or a junction dot's stub) is not a fourth arm, so a tee is never read
  as a crossing.
- **An item's own drawing**: meeting points inside an item's box, or just outside it, are the item's own drawing (an
  outline stroke, an actuator stem, a nozzle stub): lines meeting there meet at the item. Except a tee drawn beside a
  box: two arms leading away to other items must leave within half a symbol side of each other, with an arm into the
  item. This keeps the tee where MS 14010 lands beside MSCV-XXX, while pipes landing further apart on a vessel's
  shell remain separate connections to the vessel (A194). Two nozzles closer than that tolerance can still be read
  as one tee.
- **Closed shapes on a line**: a retained junction must meet at least three **different neighbours**. A line that
  leaves a point and comes back, or two lines between the same two places, can make three arms without three
  neighbours (an arrowhead, an unkeyed symbol outline, a box on a stem). `contract()` passes through points with two
  neighbours and prunes those with one, repeatedly. This definition also changes the truth derived from the OPEN100
  key graph (A191); a score improvement can therefore include a truth change, not just better tracing.
- **Items drawn touching**: two process items (excluding bubbles and actuators) with a box gap at most 0.1 of a
  symbol side are treated as consecutive when no traced line joins them (a flange against a valve or vessel, a
  reducer against a valve). Their edge has `touching: true`; its statement says they are drawn against each other,
  with no line between. It has no line network unless both ends already share one; network and pairwise links are
  unchanged. A nozzle against its own vessel remains `nozzle_of`. Limit: on the OPEN100 development drawings only
  18 of 26 such process contacts are segments in the derived key (A195), so contact alone is a draft inference to
  check, not proof of a pipe connection.
- **Left out of the layers**: dead-end stubs, and line that joins fewer than two items (a closed loop, a symbol's own
  outline or internals drawn outside its box). A network with a single item carries no link and is only counted
  (`single_item_networks`).
- **The network layer is the tracer's** (the pairwise links, which the scores use, are derived from it), so it is
  not re-cut here. The tracer joins lines that touch anywhere outside the item boxes, and the boxes are approximate,
  so two lines that meet only at an item's edge (sheet 0: MSV 1404's leader and the H actuator's stem, both drawn to
  the valve) are one network there. Such a network names the item in `joined_only_at`, its statement says so, and
  each network counts the lines it holds by kind (`lines`): sheet 0's S0-NET018 and S0-NET019 hold an actuator stem
  and an instrument line each, and no pipe.
- **Hand-built models** (the TE and Bayer models): a stream is already pipe-level, a process stream recorded from one
  end to the other, so `connects` there has `layer: stream` and no line layers are added. Cross-sheet off-page pairs
  are `layer: offpage_pair`.

Sheet 0: 345 pairwise links (unchanged) on 48 line networks (17 more networks touch only one item); 38 junctions (28
pipe tees, 10 instrument taps); 92 pipe segments (2 inferred from touching items), 20 instrument connections, 2 actuator stems, 2 nozzle stubs. DEXPI
C01: 17 networks, 5 junctions (its 5 PipeTees), 27 pipe segments. How well the pipe layer matches a real topology
(DEXPI XML, the generated drawings, and a truth derived from the PID2Graph key graph on the OPEN100 development
and holdout sheets, and the DEXPI 1.2 vendor renders), and which evaluation measures which layer: [EVALUATION.md §7](EVALUATION.md#7-which-layer-each-evaluation-measures).

The latest pipe rules were chosen on DEXPI C01-C03, SPPID renders and OPEN100 sheets 0-5, with TE and Bayer as
guards (A177, A191-A195). Comos and AVEVA renders, OPEN100 6-11 and the agent-keyed sheets were held out for those
changes, after their baselines had been seen (A196). The pooled vendor result mixes development and held-out
renders. About two thirds of the SPPID development gain comes from a scorer fix: matching position-less tees
through already matched neighbouring tees raises F1 from 0.679 to 0.852 with tracing unchanged (A192), before the
final 0.939. OPEN100 scores also include the changed derived truth. These are not pure tracing gains.

## Scan clean-up before tracing

`scripts/scan_cleanup.py` is an optional step for faded, blurred or noisy drawing images. It detects speckled or
uneven paper, estimates its background, keeps stroke cores and reconnects faint straight runs while preserving
visible gaps. OpenCV and NumPy are required; there are no model calls.

```sh
python scripts/scan_cleanup.py my-sheet.png --clean auto --out my-sheet-cleaned.png
```

The command prints the detection and writes the image to use when tracing. With `auto`, a drawing detected as clean
is left unchanged. `--clean on` forces clean-up when a faded image has flat paper and no specks that auto can detect.
In code, `scan_cleanup.trace(image, symbols, clean="auto")` runs the tracer on a temporary cleaned image or the
original file. The [generalization matrix](GENERALIZATION.md) uses this wrapper in row 1; the underlying tracer's
default and the pipe-layer row are unchanged.

Chosen on synthetic damage to OPEN100 development sheets 0-5, the frozen method raises holdout sheets 6-11 from
0.877 to 0.894 at L1, 0.566 to 0.818 at L2, and 0.387 to 0.753 at L3; only L1 clears the 0.88 bar (A189/A190).
Both splits use the same damage generator. On the one keyed real archive scan, the agent-keyed OMRE quadrant, F1
falls from 0.561 to 0.522. It has not been shown to improve real archive scans; check its result on your drawing.

## Why you'd want this, if you've never needed a graph

Most plant data lives in lists: an instrument index, an equipment list, a tag database. A list is good at "what is
FT-101?" It is bad at questions about how things connect, and those are the questions that come up when something
goes wrong or something has to change:

- Feed valve FV-107 is sticking. What does it feed, which transmitters would show it, and which interlocks act on it?
- We're replacing pump P-1. Which instruments, valves and controllers are tied to it, on this sheet and others?
- Which items has nobody checked since they were read off the drawing?
- This valve was retagged last year. Which old documents still use the old tag?

A **graph** stores the items and the links between them (this transmitter measures that line, this controller moves
that valve, this relief valve protects that vessel), so those questions become a lookup instead of an afternoon with
the drawings. Graph databases, many asset-management tools and some change-management systems load exactly this
shape. You don't need one to use the rest of this repository; you need it when your questions start with "what's
connected to...".

**Why every value carries a source.** A value someone typed in and a value someone checked look identical in a list.
Here each attribute says where it came from (which sheet and box, which document and page, which reviewer) and
whether anyone has confirmed it. So "which items has nobody checked?" has an answer, and a correction doesn't erase
what the value used to be.

## Asking it questions

Two of the questions above, answered from the committed Bayer example with nothing but the Python standard library.
Run each from the repository root.

**What does a valve's failure affect?** What FV-107 acts on and which line it sits on (and where that line goes),
what moves it (here three interlocks, with the measurement that trips each), and which instruments watch the same
vessel or line, so you know which readings would show a stuck valve.

```python
import json
from collections import defaultdict

g = json.load(open("examples/graph-export/bayer_graph.json", encoding="utf-8"))
into, out = defaultdict(list), defaultdict(list)
for e in g["edges"]:
    out[e["from"]].append(e)
    into[e["to"]].append(e)
lines = {e["id"]: e for e in g["edges"] if e["type"] == "connects"}

valve = "FV-107"
for e in out[valve]:
    if e["type"] == "sits_on":
        line = lines[e["to"].removeprefix("stream:")]
        print(f'{valve} sits on line {line["id"]}: {line["from"]} -> {line["to"]}')
    else:
        print(f'{valve} {e["type"]} {e["to"]}')
for e in into[valve]:
    trips = [x["from"] for x in into[e["from"]] if x["type"] == "trips"]
    print(f'{e["from"]} {e["type"]} {valve}' + (f', tripped by {", ".join(trips)}' if trips else ""))
for e in out[valve]:
    near = sorted({x["from"] for x in into[e["to"]] if x["from"] != valve and x["type"] in ("measures", "sits_on")})
    print(f'also on {e["to"].removeprefix("stream:")}: {", ".join(near) or "nothing else"}')
```

Output:

```text
FV-107 acts_on RT-1
FV-107 sits on line S1: BL -> RT-1
IL-1 acts_on FV-107, tripped by TT-104
IL-2 acts_on FV-107, tripped by PT-101
IL-3 acts_on FV-107, tripped by FT-103
also on RT-1: LT-102, PT-101, TT-104, TT-105
also on S1: nothing else
```

**Which instruments has nobody checked?** Every instrument whose status is not confirmed, corrected or rejected,
with how many of its claims are still unchecked. In this example none has been checked yet.

```python
import json

g = json.load(open("examples/graph-export/bayer_graph.json", encoding="utf-8"))
checked = ("confirmed", "corrected", "rejected")
for n in g["nodes"]:
    if n["kind"] == "instrument" and n["status"] not in checked:
        left = sum(c["status"] not in checked for c in n["attributes"])
        print(f'{n["id"]:7} {n["status"]:10} {left} of {len(n["attributes"])} claims unchecked  {n["name"]}')
```

Output:

```text
PT-101  unverified 6 of 6 claims unchecked  Residue treater pressure
LT-102  unverified 6 of 6 claims unchecked  Residue treater liquid level
FT-103  unverified 7 of 7 claims unchecked  Recirculation flow
TT-104  unverified 7 of 7 claims unchecked  Residue treater temperature (as plotted in Fig 11)
TT-105  unverified 6 of 6 claims unchecked  Second temperature measurement (bulk liquid or recirculation loop; see TT-104)
FT-106  unverified 7 of 7 claims unchecked  Indicated steam flow to the heater
```

## Two profiles: the full record, and the part a change system needs

**Why:** a drawing extraction carries a lot about *how* it was read: method names, image hashes, pixel positions,
candidate lists, and the all-pairs network links. That's the evidence trail, and it belongs with the extraction. A
system that tracks changes to the plant, such as a CMMS, an MOC tool or an asset register, needs a smaller set. It
needs what each item is, the settings a change would alter, the relations that decide what a change affects, and
where each fact came from. Loading the full export for every sheet of a plant would bury that set. Sheet 0 alone is
over 6,000 claims.

```sh
python scripts/graph_export.py my-bundle/plant_model.json --profile core --out my_graph_core.json
```

| Profile | Keeps | Drops |
|---|---|---|
| `full` (default) | all supported claims and relations | declared exclusions listed in `not_exported` (for example, the Bayer incident timeline) |
| `core` | nodes, identity and configuration claims, `measures` / `controls` / `sets_point_of` / `protects` / `trips` / `piped_to` / `instrument_connection` / `actuated_by` / `nozzle_of` / `on_network` / `contains`, every claim's `source` | extraction internals (`*_method`, hashes, `source_evidence.*`, pixel geometry, candidate lists, `sheet`, which every claim's source already names) and the all-pairs `connects` links, which `on_network` rebuilds |

Nothing leaves silently: a `core` graph has a `profile` block counting every dropped claim name, the dropped edges
and the claims they carried. On sheet 0, 6,581 claims become 956 kept + 1,140 extraction internals + 4,485 carried on
the 345 dropped all-pairs links, and 736 edges become 391
([`sheet0_graph_core.json`](../examples/graph-export/sheet0_graph_core.json)). Hand-built models (TE, Bayer) carry no
extraction internals, so their `core` export equals the full one. `core` is a view for loading, not a replacement:
keep the full export as the record. Each kept claim still carries its source; the full export retains methods and
candidate alternatives a reviewer may also need.

## The format

| Section | Each entry has | Notes |
|---|---|---|
| `nodes` | `id`, `kind`, `tag`, `name`, `aliases`, `status`, `attributes` | `kind`: plant, system, equipment, instrument, final_element, controller, line_item, offpage_connector, boundary, manual_valve, relief_device, interlock, limit, junction, line_network (the last two: [line layers](#three-layers-for-the-lines)). `aliases` holds every earlier tag (`former_tag`), so older documents still join |
| `nodes[].attributes` | `name`, `value`, `status`, `source` | One claim per attribute. `status`: confirmed, corrected, unverified, rejected, extracted, unresolvable. `source.kind` is `drawing` (sheet, box, the text as read, run and model), `document` (what it was checked against, the evidence, the date), `review` (who changed it, when, and what it was) or `model` (the item cites no source of its own: the model's source document is given so the gap is visible). Nested content becomes claims at any depth: a record becomes dotted names (a controller's `setpoint.value` and `setpoint.uom`, which cite the page that gives the setpoint, since a record naming its own `source` lends it to everything under it; a drawn line's `source_evidence.source_drawing.page`), a list of plain values is one claim, and a list holding records is indexed (`ratings[0].psig`, `ratings[1].psig`). Not claims: the item's id, tag and former tags (they are the node), its own source, status and review (every claim carries them), its drawing layout, keys starting with `_`, and keys that became edges (a controller's `measurement` and output valve or cascade target, an interlock's `measurement` and `final_element`); any other key in a controller's `output` is a claim (`output.action`). A value is always a plain value or a list of them |
| `edges` | `id`, `type`, `from`, `to`, `status`, `direction`, `source` | `type`: contains, connects, measures, controls (measurement to controller, controller to each valve it moves, split range included), acts_on, sets_point_of (a cascade: the controller whose output is another controller's setpoint, from `output.setpoint_of`), sits_on, protects (relief device to the vessel), trips (measurement to interlock), applies_to (limit to its tag), piped_to (pipe segment between two items or junctions), instrument_connection (a bubble's leader or impulse line), actuated_by (valve to the actuator stacked on it), nozzle_of (nozzle to its vessel), on_network (item or junction to its line network). A `connects` edge carries `layer`: `network_pair` for a link read off a drawing, which means the two items are on the same drawn line network (lines, bends, junctions or crossings join them with no symbol in between: how `score_pid2graph.py` reads the public answer key's graph, every pair of symbols reachable through its connector and crossing nodes), not that a pipe runs directly from one to the other (on sheet 0, 22 of 27 sampled links passed through one or more tees, [statement review](../examples/statement-review/README.md)); with line layers it also names the `network` both ends are on. `stream` for a hand-built model's process stream (pipe-level); `offpage_pair` for two off-page connectors paired across drawings. A drawn `connects` or `piped_to` edge has `direction: unknown` unless the drawing showed it. A `connects` edge also carries `attributes`: the line's own claims (size, fluid, insulation, temperature), sourced like a node's |
| `questions` | (from the question engine, when attached) | Open engineering questions tied to assets, with the data needed to answer them |
| `events` | `type`, `item`, `by`, `on`, plus the decision | Review decisions and change-review requests from `apply_review.py` records |
| `nodes[].placement` | text | Only on an item no owning unit could be found for (for example a valve on a line between two off-page connectors): it is still a node, with the reason, never left out |
| `not_exported` | `section`, `items`, `why` | Every top-level section of the model that has no export rule, so nothing is dropped silently, plus an extracted twin's `dropped` (what the extraction itself dropped) and `offpage_pairs` when they are not empty. The Bayer model's incident timeline and named people are left out on purpose |

## What it does not do

It infers nothing. An item with no recorded status is exported as `unverified`; a drawn process connection with
no recorded direction keeps its direction unknown. A `controls` edge's from/to expresses the recorded
measurement/controller/output roles; it does not verify physical signal direction. Units, ranges and point
addresses are exported only when the model holds them. `--check`
validates the structure (known kinds, statuses and edge types, unique ids, every edge end a node, every claim
sourced and a plain value; a `piped_to` end is an item or a junction; `on_network` ends at a `line_network`; every
junction is on exactly one network and has a `piped_to` edge; a `connects` edge's `layer` is known and the `network`
it names holds both its ends); it does not judge whether a claim is true. An unreadable, empty or non-graph file is
refused with a one-line reason (exit 1), as is a `--reviews` folder that doesn't exist, or a model missing a
section or key the export is built from (it names which: `units[0] has no 'id'`). Exit 2 is a usage error.
