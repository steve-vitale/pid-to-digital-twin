# A review bound to the original drawing

This small **illustrative software exercise** uses the current committed sheet-0 graph and the original public
PID2Graph sheet. It demonstrates the render, sample and apply route with evidence fingerprints. It is not an
engineering review, a new accuracy measurement or an approval of any plant fact. Earlier reviewed samples and
their scores remain unchanged in the parent example.

Drawing source: [PID2Graph, Zenodo record 14803338](https://zenodo.org/records/14803338), OPEN100 sheet 0.
Credit to Jan Marius Stürmer, Marius Graumann and Tobias Koch, and the Energy Impact Center for the OPEN100 design.
The drawing crops in `evidence/` are adaptations (cropping and JPEG conversion) of that public sheet and retain
its [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license. They are not covered by the repository's
MIT software license. Source attribution and dataset distinctions are also recorded in `data/corpus.json`.

`sample.json`, `sample.csv` and `sample.html` are a new 12-statement sample, seed 1032, stratified by relationship
layer with a floor of two. Its drawing crops are in `evidence/`. Open `sample.html` to inspect the packet. The
blank sheet is the starting point for a person's review; the browser download retains its fingerprint.

`illustrative_review.csv` deliberately fills only the first row with `unclear`, a fictional training reviewer
and an explanatory note. Plant truth stays blank. `apply_summary.json` records that single software application
and its input/output bindings. The result does not certify that the sampled statements match the drawing.

The `*-before-appearances.*` files retain the previous packet, worksheet and receipt byte-for-byte. Their graph
revision is [74f2a11](https://github.com/steve-vitale/pid-to-digital-twin/tree/74f2a11376b84f01669843681b576497ff1257c1/examples/graph-export).
The old worksheet correctly refuses against the expanded evidence. The current worksheet is a **new fictional
software exercise**, dated 2026-10-30; no real verdict was transferred to a new fingerprint. Historical measured
reviews and scores in the parent example remain unchanged.

## Reproduce in a new working folder

From the repository root, with Pillow installed for drawing crops:

```sh
python scripts/statements.py render examples/graph-export/sheet0_graph.json --image "0=data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/0.png" --out examples/statement-review/bound-sheet0/run/full
python scripts/statements.py sample examples/statement-review/bound-sheet0/run/full/statements.json --n 12 --seed 1032 --strata layer --floor 2 --out examples/statement-review/bound-sheet0/run/sample.json
python scripts/statements.py apply examples/graph-export/sheet0_graph.json examples/statement-review/bound-sheet0/illustrative_review.csv --image "0=data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/0.png" --date 2026-10-30 --out examples/statement-review/bound-sheet0/run/reviewed_graph.json
python scripts/graph_export.py --check examples/statement-review/bound-sheet0/run/reviewed_graph.json
python -S scripts/test_bound_statement_example.py
```

The tests need only the standard library and committed inputs. They apply this exact CSV through the CLI, check
the retained note and provenance, confirm that engineering values and plant-truth states do not change, and
refuse the old sheet after changing a disposable source copy or graph snapshot. Original inputs are preserved.
The generated full packet is deliberately outside the committed record; the small sample and crops are retained.

After a real source or graph change, render and review a new packet. Do not add a fresh hash to an old verdict.
This route binds the whole graph, including statuses and events, so the reviewed output also needs a new packet
before another review is applied. Hashes establish snapshot consistency; they do not authenticate a reviewer,
prove source authority or monitor changes between runs. See the [full rules](../../../docs/STATEMENT_REVIEW.md).
