# Adapt the existing pipeline to another labeled collection

**Status update, 2026-10-11:** reserved Synthetic sheets 2 and 3 have now been evaluated once under a separately committed frozen protocol. They are no longer unopened holdouts. See [the prospective results](PID2GRAPH_RESERVED23_RESULTS.md). The development narrative below preserves the earlier state and does not turn inspected sheets 0/1 into holdout evidence.

This example uses **PID2Graph Synthetic**, a separate collection from the OPEN100 drawings and the previously evaluated Dataset-P&ID/holdout-B. It is **third-party synthetic data, not evidence of accuracy at a real plant**. It is also distributed in the same PID2Graph archive and uses the same coarse graph ontology, so this is a limited transfer exercise, not an independent benchmark of every schema or drafting convention.

## Choose data before changing the method

The original candidates are recorded in `docs/PLAN.md` and JOURNAL §6: PID2Graph, Dataset-P&ID/Digitize-PID, and OPEN100. Dataset-P&ID was already used for holdout B, so another sample of it would not be a new collection. The selected Synthetic collection had not been used in the repository's evaluations.

Primary source: [PID2Graph, Zenodo record 14803338](https://zenodo.org/records/14803338). Dataset authors: Jan Marius Stürmer, Marius Graumann, Tobias Koch. Synthetic symbols: copyright 2023 Steven Baltakatei Sandoval. The source explicitly specifies [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) for the Synthetic symbols/collection. Keep attribution and the same license on adaptations of these data; code remains MIT. Source drawings, labels, converted PNGs, raw model responses, and generated twins stay in gitignored folders. Do not bundle them by accident.

Archive: 9,303,633,645 bytes (publisher checksum MD5 `90f782220de97e7e249d2595c49ddc1c`). We do **not** download or verify the whole archive checksum. ZIP CRC checks validate fetched entries; the sample manifest records individual SHA-256 hashes. Range responses are checked before accepting bytes.

An actual central-directory inventory found **250 complete JPEG/GraphML pairs**, contrary to the old journal's statement of 500 synthetic complete drawings. This example uses only development sheets 0 and 1. Their JPEGs plus keys total **1,575,041 bytes**; indexing the archive additionally costs about 10 MB. Reserved sheets 2 and 3 are not fetched, opened, or scored. Existing Dataset-P&ID holdout-B IDs and OPEN100 holdouts are unaffected.

Configuration: `data/dataset_adapters/pid2graph_synthetic.json`. Freeze the selection, label coverage, recipe, and limits before reading evaluation drawings. These two inspected sheets are development evidence, with no instrumentation examples; they cannot test instrument measurement placement or live-value mapping. Future holdout evaluation must be separately frozen; do not call these results held-out generalization.

## The copied approach

1. Inspect primary-source licensing and archive inventory. Record the exact collection, not merely the archive name.
2. Declare what the labels can judge. Here: symbol classes, boxes, undirected adjacency. Not tag text, engineering units, directed process flow, PLC/OPC mapping, verified equipment roles, or operating envelopes.
3. Normalize file format at the boundary. This collection uses JPEG, but the existing runner/scorer expects PNG. Decode to RGB PNG **without resizing**; keep original and converted hashes. This adds no visual information.
4. Run an **oracle-label adaptation** first. Convert ground-truth labels into the existing prediction format, collapse connector/crossing/arrow nodes using the unchanged scorer's rule, and invoke the existing `build_twin.build` and `generate.export_twin`. A perfect score here measures adapter consistency only. It is not extraction accuracy.
5. Run the already selected extraction recipe once. No second model comparison. Original first-try and repeat-v1 scorecards favor **Codex gpt-6.1-sol with `extraction/prompt.md`, whole sheet, no tiling** for rough classification and connectivity (0.87 and 0.56 respectively on the original set). Claude had slightly stronger first-try strict boxes; there was no universal winner for every metric. The selected recipe is frozen for this example.
6. Give extraction only the image and pinned prompt. The CLI wrapper uses a temporary image-only folder, read-only sandbox, ignored user configuration, and disabled shell/unified execution/web search. Both CLI attempts failed before inference. The successful native fallback used fresh isolated agent conversations with the selected model and instructions to read only the specified image and prompt; its native wrapper/tools differ from CLI, and disabled-tool isolation is **not** claimed for native agents. Parent orchestration verified model selection; reasoning settings were unverified/inherited. Ground truth was never supplied to extraction. Keep raw output, hashes, failures and transport distinctions; never overwrite the first attempt.
7. Use the **same frozen scorer** for extraction, then build the same `twin-1` outputs. Validate before export. Do not apply the OPEN100-trained confidence calibration to this new domain. The adapter uses the existing `linked` parent rule to keep this exercise deterministic; it is not an additional extraction recipe or a measured winning parenting method.
8. Inspect missing fields before drawing an attractive screen. Preserve unknowns and send unresolved items to review. A renderer working does not imply the process interpretation is correct.

## Reproduce

From the repository root, install the repository's dependencies in a virtual environment, then:

```bash
python scripts/test_pid2graph_synthetic_adapter.py
python scripts/adapt_pid2graph_synthetic.py fetch
python scripts/adapt_pid2graph_synthetic.py oracle
# Uses an already-authenticated ChatGPT subscription; no API keys are requested.
python scripts/adapt_pid2graph_synthetic.py extract
python scripts/adapt_pid2graph_synthetic.py evaluate  # scores your successful local CLI run
python scripts/test_scorer_controls.py
```

To reproduce the **recorded native fallback evaluation**, use its preserved run folder, rather than the failed CLI run:

```bash
python scripts/adapt_pid2graph_synthetic.py evaluate --run-dir runs/pid2graph-synthetic-adaptation/codex-native
```

The raw native predictions are local, gitignored receipts. A source-only checkout cannot reproduce those exact outputs without obtaining that run bundle or rerunning extraction; it can reproduce the frozen oracle adapter and run its own selected-model extraction. No native result is disguised as a successful CLI result.

For a new checkout, install the repository requirements in an isolated Python environment before commands that use the converter/model runner. Historical temporary dependency directories are not portable installation instructions.

Results:
- Sample manifest: `data/external/pid2graph/PID2Graph/Complete/PID2Graph Synthetic/sample_manifest.json`
- Failed CLI attempt: `runs/pid2graph-synthetic-adaptation/codex/`; failed runtime retry: `codex-runtime-retry/` under the same parent
- Successful native predictions and metadata: `runs/pid2graph-synthetic-adaptation/codex-native/`
- Oracle run: `runs/pid2graph-synthetic-adaptation/oracle/`
- Aggregate evidence: `out/pid2graph_synthetic_{oracle,evaluate}_adaptation.json`
- Existing-format twin/export output: `out/twin/pid2graph-synthetic-{oracle,evaluate}/`

The script never fetches the reserved sheets and accepts only configured development sheets. If source size, classes, coordinate bounds, model, prompt hash, or image hash differ, stop and explain the change instead of silently treating it as comparable.

## Gaps to carry into your own dataset

- **Input adapters:** image extension, dimensions, annotation coordinates and ontology must be explicit. The JPEG mismatch was discovered by actual archive inspection.
- **Taxonomy:** a generic `general` class does not identify arbitrary equipment types. Unknown classes fail closed rather than disappearing silently.
- **Tag truth:** these graph labels cannot score OCR or ISA parsing; empty tags stay empty. A synthetic identifier generated by the pipeline is not an observed tag.
- **Direction and line semantics:** actual keys contain 221 solid and 29 non-solid graph edges across the two sheets. The existing scorer and prediction schema discard this line-style distinction when collapsing to 65 asset links. These links cannot be presented as verified process-flow connections. The adapter retains source style counts and a warning in model metadata/report; exported streams keep unknown direction. Mapping solid/non-solid to process/signal semantics still needs source-domain validation.
- **Parenting:** adjacency and proximity heuristics may assign a plausible parent without proving process ownership. Report missing unit ownership and inspect guesses.
- **Operational configuration:** live-point identity, units, signal type, range, quality, alarms, and display roles still require plant-specific configuration. Existing exporters include placeholders and cannot establish a live import test.
- **Confidence:** the old calibration is domain-specific. Do not transfer auto-accept thresholds without new calibration.
- **Evaluation:** the oracle and model scores need separate labels. Tiny development samples locate failure modes; they do not establish general deployment reliability or eliminate human review.

## Observed results

Verified on the two downloaded development sheets:

| Stage | Observed result | Interpretation |
|---|---|---|
| Download | 1,575,041 source bytes; 12,201,709 range bytes including index/block overhead | Source JPEGs + GraphML keys, with entry CRC and SHA-256 |
| Dimensions | Both 7000 × 4500 pixels | RGB PNG normalization preserves dimensions |
| Oracle sheet 0 | 20 scored assets, 38 collapsed links; 0 corrections | Adapter consistency, not extraction accuracy |
| Oracle sheet 1 | 23 scored assets, 27 collapsed links; 0 corrections | Adapter consistency, not extraction accuracy |
| Oracle twin | 6 equipment, 37 line items, 0 instruments; 65 links | No instrument-placement coverage in these two samples |
| Oracle missing evidence | 43 missing tag labels, 65 unknown directions | No invented tag truth or directional flow |
| Oracle exports | Twin validation clean; SVG, Ignition, PI, review queue written | Not imported into a gateway or PI environment |
| Controls | 9 adapter tests + frozen scorer controls across 12 OPEN100 drawings pass | Unit/plumbing safeguards, not generalization evidence |

The image pixels were inspected: randomized text and sparse artificial routing make the synthetic provenance obvious. The first Codex CLI attempt and a labeled writable-runtime retry both failed before inference (`failed to initialize in-process app-server client: Read-only file system`). Actual model/provider were therefore unverified/null; neither attempt has an accuracy score. Receipts remain in `runs/pid2graph-synthetic-adaptation/codex/` and `codex-runtime-retry/`. No credentials were copied or access restrictions relaxed. A native-agent fallback uses the same selected model and exact prompt/image; any resulting score is labeled with its transport/reasoning difference rather than presented as a byte-for-byte repeat of the CLI recipe.


### Selected-model extraction: development results, frozen first output

Successful transport: two separate native `gpt-6.1-sol` workers, same exact original prompt and normalized image, no label context. Native wrapper instructions differ from CLI and reasoning is unverified/inherited. No timing comparison is made.

| Sheet | Located symbols | Source-class agreement | Connection TP / predicted / key | Class F1 | Connection F1 | Corrections / key items |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 20 / 20 | 9 / 20 | 19 / 19 / 38 | 0.450 | 0.667 | 30 / 58 (51.7 per 100) |
| 1 | 22 / 23 | 9 / 23 | 25 / 26 / 27 | 0.400 | 0.943 | 17 / 50 (34.0 per 100) |
| Micro aggregate | 42 / 43 | 18 / 43; 42 predictions | 44 / 45 / 65 | 0.424 | 0.800 | 47 / 108 (43.52 per 100) |

The 47 corrections comprise **24 source-class disagreements, 1 missed symbol, 21 missed links, 1 false link**. This is agreement with the published labels under the unchanged scorer, not a count of independently verified engineering errors. Strict class F1 equals rough class F1 on these sheets.

The extraction-built twin has 15 equipment, 3 instruments, 20 line items, 4 unpaired off-page items and 45 links; the oracle has 6 equipment, no instruments, 37 line items and no off-page items. The difference demonstrates why a valid export is not a verified process model. Forty extracted assets lack tags and all 45 links have unknown direction. These remain review drafts.

### Why not simply remap the labels?

Twenty of the 24 source-class disagreements are source `general` → model `tank` (8), `pump` (5), `inlet/outlet` (3), `instrumentation` (2), or `valve` (2). The other four are source `tank` → model `general` (2), `inlet/outlet` (1), or `instrumentation` (1). The original prompt explicitly includes heat exchangers/columns/other large equipment under `tank` and describes `general` as other inline items. The source uses a broad heterogeneous General class and Tank/Vessel terminology. The [authors discuss this ontology difficulty in §V/A3 and list the categories in Table I](https://arxiv.org/html/2411.13929v2).

Thus not every mismatch proves that the model misunderstood the physical component. Conversely, plausible interpretation does not entitle us to change the answer key. Keep `source_class` and `model_class` separate. `source_annotation_context.json` in each local twin export preserves the matched comparison and **every original edge's solid/non-solid style**, with semantic line type null. It is CC BY-SA dataset-derived context, not included in a source-only Git bundle. No global remapping or answer-key correction has been applied.

### Before operational export: explicit review gate

The narrow implemented improvement is an operational-readiness check before export, alongside the existing structural validator. Structural validity permits **draft review files only**. Reports and model metadata list unresolved ontology alignment, line semantics, plant mapping/ranges/quality/deployment verification, and existing `ops_review` decisions. The operational flag stays false for this bounded example. This is an adapter-level guard; it does not claim to harden every independent exporter in the repository.

```bash
python scripts/adapt_pid2graph_synthetic.py evaluate --run-dir runs/pid2graph-synthetic-adaptation/codex-native --require-reviewed
# Expected: refuses before writing twin outputs while operational blockers remain.
```

Use the existing `review_queue.csv` and [operations review loop](REVIEW_LOOP.md) to record real reviewer decisions, first with `apply_review.py --dry-run`. No decisions are prefilled or auto-approved. A class correction can change whether an item belongs in equipment, instruments or line items: the current review script changes fields in place, so class-role changes need an explicitly reviewed rebuild and revalidation, not merely a class string edit. Point mapping and the display contract require their own verified units, signal type, range, quality and role configuration; absent annotations cannot provide those.

The smallest **next** class/schema change is a versioned, domain-reviewed ontology map with an unresolved category and preserved source/model labels, plus edge line-style preservation through the prediction contract. A mapping must be justified from source definitions/examples rather than a lookup tuned to these two answer keys. Freeze its mapping, prompt/schema, scorer policy and acceptance criteria before a prospective trial on new data. Sheets 2/3 were subsequently evaluated and are now consumed; see the status update above. This development trial claims no held-out improvement.
