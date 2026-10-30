# One item, three drawing appearances

`CND-TK-165` (`S2-TK002`) appears on sheets 2, 3 and 4 in the existing OPEN100 extraction.
This packet copies that one item exactly from the [full model](../../../out/twin/r2-tiles-trace/codex/plant_model.json).
[source.json](source.json) binds the model revision and identifies the selection. It is a development regression
on existing public-source data, not a new extraction, held-out accuracy result or plant verification.

The graph keeps the item's ordered `provenance` records, including each box, read tag, extraction run, model,
confidence and extra fields. Its `source` remains the primary locator. A statement's source can instead be a
specific document or a later correction; **item appearances do not establish that every sheet supports that
statement or agrees with the others**. One statement still receives one verdict.

The copied `risk.*` values are the project's extraction-review priorities, not plant safety risk. They remain
in the graph and are counted as skipped bookkeeping in the statement view. Its summary separately reports
image availability: zero primary or appearance images here. Appearance counts are per-statement evidence
entries, so the two item statements reference six entries backed by three original appearance records.

## Try the packet offline

From the repository root, Python 3.10+ and standard library only:

```sh
python -S examples/graph-export/multi-appearance/check_packet.py
python -S scripts/graph_export.py examples/graph-export/multi-appearance/model.json --out my_full.graph.json
python -S scripts/graph_export.py examples/graph-export/multi-appearance/model.json --profile core --out my_core.graph.json
python -S scripts/statements.py render my_full.graph.json --out my-review
```

Open `my-review/review.html`. Expand **Recorded item appearances** to inspect all three locations and original
records. The CSV source column lists all three locators; the JSON retains the complete records. No original
images were supplied for the committed [review](review/review.html), so each appearance explicitly says its
image is unavailable. A coordinate reference alone is not a source check.

With Pillow installed and the public OPEN100 images already cached, add any approved local images:

```sh
python scripts/statements.py render my_full.graph.json --image "2=data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/2.png" --image "3=data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/3.png" --image "4=data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/4.png" --out my-review-with-images
```

Each supplied appearance gets its own crop; missing images remain explicit. Samples copy every referenced crop.
Review fingerprints bind the full graph and every supplied original's bytes. A later appearance or source-file
change requires a new review. These hashes are content bindings, not authenticated approvals.

Both [full](full.graph.json) and [core](core.graph.json) graphs retain these item records. Core still drops its
documented extraction claims and selected links; it is a view, so retain the full export, model and originals.
Snapshot access returns the records without fetching sources; context refresh can detect their later changes.
Company ownership, document retention and engineering acceptance remain the company's responsibilities.
