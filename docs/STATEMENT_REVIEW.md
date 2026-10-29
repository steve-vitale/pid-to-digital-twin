# Statement review: check the model one plain sentence at a time

**Why.** Everything this repository produces can be said as plain statements, and every statement has a source of
truth: a box on a drawing sheet, a page of a report, a field of a model, an element of an XML file, a row of a CSV.
Reviewing a random, stratified sample of those statements against their sources, grouped by asset, turns "does this
output look right?" into a measured error rate with an honest interval. It also lets an operator check a unit in
plain language ("PSV-101 protects the residue treater RT-1 against overpressure") without reading JSON.

**Two verdicts, never mixed.**

1. **Matches its source.** Does the drawing box, the report page or the model field say this? Anyone can check it:
   a reviewer, an agent, or a script where the source is structured. This is what the error rate measures.
2. **True in the plant.** Is it actually so on the unit today? Only an operator, a walkdown or live data can say,
   and only for a statement that matched its source. A drawing can be faithfully read and still be out of date.

The review page keeps the second verdict locked until the first says `match`; `score` ignores (and lists) any plant
verdict on a statement that did not match; `apply` refuses one.

```sh
python scripts/statements.py render examples/graph-export/bayer_graph.json --document data/external/csb/Bayer_Report_Final.pdf --out my-review
python scripts/statements.py render examples/graph-export/sheet0_graph.json --image "0=data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/0.png" --out my-review
python scripts/statements.py sample my-review/statements.json --n 60 --seed 1029 --out my-review/sample_60.json
python scripts/statements.py sample my-review/statements.json --n 60 --seed 1030 --strata layer --floor 15 --out my-review/sample_layers.json
python scripts/statements.py score reviewed_sample_60.csv --sample my-review/sample_60.json
python scripts/statements.py apply examples/graph-export/bayer_graph.json reviewed_sample_60.csv --reviewer "R1" --date 2026-11-02 --out bayer_graph_reviewed.json
```

Worked pilot, not yet reviewed: [`examples/statement-review/`](../examples/statement-review/README.md).

## What `render` makes

The input is a twin-graph-1 file from [`graph_export.py`](GRAPH_EXPORT.md); anything else is refused with a message
saying how to make one. Each node, each attribute claim and each edge becomes one statement:

| Field | What it is |
|---|---|
| `id` | `st-` + the first 12 hex of SHA-1 over `subject|predicate|object`. Status, source and evidence are not part of it, so a reviewed graph gives the same ids. A stream's own id is part of its key, so two streams between the same ends stay two statements |
| `text` | The sentence, from a template per node kind, attribute and edge type ("FT 1401 measures flow", "Controller TIC-104 moves TV-104C", "TIC-104 is set to hold 135 C (its setpoint)"). An item without a tag is named by what it is and its id ("Untagged valve S0-VL001"); a tag that appears twice gets its id ("FT 1401 (S0-IN002)") |
| `layer` | Which relationship it states: `pipe` (a `piped_to` segment or a junction: what is piped directly to what), `network` (a line network and what is attached to it), `network_pair` (a drawing's pairwise link: both items on the same line network, **not** piped to each other), `stream` (a hand-built model's process stream), `offpage_pair`, or `item` (identity, attributes, every other relation). Error rates are reported per layer, never blended ([line layers](GRAPH_EXPORT.md#three-layers-for-the-lines)) |
| `type`, `rank` | `identity` / `attribute` / `relation`, and consequence rank 1 control or safety relation (controls, trips, protects, sets_point_of, applies_to, interlock action, interlock cause/effect/bypass, relief basis, limit values), 2 connection, 3 value with units, 4 identity, 5 descriptive text |
| `group`, `system` | The asset the statement is about, and the system it sits in (its containing system, else the equipment its `unit` names). The page groups by these |
| `source`, `source_pointer` | The graph's own source, and one line a reviewer can follow ("drawing sheet 0, box [287, 354, 303, 377] (0-1000 scale), read as "FT 1401"", "document: p. 28; p. 32"), or **"no source of its own"** |
| `evidence` | Drawing source: a JPEG crop of the box with margin, outlined, under `evidence/`. Document source: the cited printed pages and figures, the PDF page each is on, the figure page rendered as a small JPEG, and the line on the cited page that best matches the statement's words. Model-only source: says so; for a traced line on a drawing it also crops both ends (red, blue) so the reviewer can follow the line |
| `machine_check` | Hand-built models only: is the statement exactly what the model's own field holds (`units[RT-1].mawp_psig`)? See below |
| `targets` | Which claim(s), node or edge the statement stands for; `apply` writes the verdict there |

Each layer has its own wording: "A pipe runs directly from X to Y, with no junction or other item between" (or "A
line is drawn directly ..." when an end is an instrument); "X and Y are on the same drawn line network (S0-NET003):
lines, bends, junctions or crossings join them with no item between. This does not say a pipe runs directly from one
to the other"; "X is attached to drawn line network S0-NET003"; "Junction S0-JN-... is a junction: a point on the
drawing where 3 line arms meet".

It also writes `review_sheet.csv` (`statement_id, group, stratum, layer, text, source, source_match, plant_truth,
reviewer, note`, verdicts empty) and `review.html` (`--no-html` skips it for a very large graph). Fields that are
bookkeeping rather than statements about the plant (`extraction_confidence`, `*_method`, hashes, layout, ids, tag
status, nearest-neighbour working) are skipped and **counted** under `skipped` in statements.json, as are claims that
would only repeat the tag or another statement, so nothing disappears silently.

**The quoted line is a search aid, not evidence of a match.** It is found by word overlap (the claim's value must
appear, and at least two of the subject's distinctive name words) and labelled "read it, don't trust it". Identity
statements are never quoted: a name match would point at the wrong item. Quoting needs PyMuPDF or `pdftotext`; with
neither, only the page is given. Report pages are read as the report's printed page numbers (the number at the top
of each page), which is how the Bayer model cites them.

## Sampling and scoring

`sample` draws a stratified random sample: strata are statement type x rank; every stratum gets at least
`min(--floor, its size)` (default 2) so rare high-consequence strata are seen, the rest is split in proportion to
stratum size; within a stratum, `random.Random("<seed>:<stratum>")` samples statements sorted by id. The strata,
their population and sample counts, the weights and the seed are written into the sample file and printed. It writes
`sample.json`, `sample.csv` (the sheet to fill) and `sample.html` (copying only the crops it shows).

`--strata layer` makes each relationship layer its own stratum instead (with `--floor 15` and `--n 60`, 15 per
layer on sheet 0), so a sample measures each layer on its own; the floor is written into the sample file.

`score` reports, for MATCHES ITS SOURCE, **per relationship layer** (the sheet's `layer` column, else the sample
file's statements): mismatches over statements checked (`match` + `mismatch`), with a Wilson 95% interval, for the
layer and per stratum. When the sheet holds more than one layer there is no overall rate: a pipe adjacency, a network
membership and a pairwise link are different facts. An older sheet without the column is one layer, scored as
before; `unclear` and unreviewed rows are counted, not folded in. Given `--sample`, it
also gives the error rate weighted back to the whole population within each layer (small strata are over-sampled on
purpose). TRUE IN
THE PLANT is tallied separately, only over statements that matched.

`apply` writes each verdict onto its targets as a `checks` entry (`statement, source_match, plant_truth, by, on`) and
one `statement_review` event, and sets a status: `mismatch` -> `rejected`; `match` + plant `confirmed` -> `confirmed`;
`match` + plant `wrong` -> `rejected`; a source match alone leaves the status as it was (it says nothing about the
plant). **It never changes a value.** Rows it can't apply (unknown statement, bad verdict, plant verdict without a
match, no reviewer) are listed and the run exits 1; the output still validates with `graph_export.py --check`.

## The machine check, and what it does not prove

For a hand-built model (the Bayer and Tennessee Eastman models) whose graph names a model file in this repository,
each statement is compared with the model field it came from, and the page shows "machine: matches its model field".
That **only proves the export says what the model says.** It cannot tell you the model is right: whether RT-1 really
was 4,500 gallons is the human source check against the report, and whether it still is, is the plant check. A drawing
extraction (sheet 0) has no structured source in the repository to compare against, so every statement there is
"not checked" and the crop is the evidence.

## Limits

- The sentence is a rendering of the claim, not the claim. A template can mislead; when a reviewer finds the sentence
  wrong but the underlying claim right, mark `unclear` and say so in the note, so template errors and data errors are
  counted apart. Known weak spots are listed in the pilot README.
- Ranks are a fixed rule, not a hazard study: a connection on a relief line is still rank 2.
- Crops show the box the extractor reported. A wrong box (the right tag, the wrong place) shows up as a mismatch only
  if the reviewer looks around it; the crop includes a margin for that reason.
- Reviewer time is not recorded here; [`review_kit.py`](../scripts/review_kit.py) times a review.
