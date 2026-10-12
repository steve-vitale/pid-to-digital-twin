# Source-image connectivity, development v2

This **opt-in local development stage** adds repeated-dash recovery and guarded symbol barriers to the existing deterministic tracer. It consumes only the source image and previously detected symbol boxes. It makes no model or network calls and changes no prompt, model selection, scorer, original predictions, frozen results, ownership/parent-assignment rule, site-workflow default, gateway or PI artifact.

## Why the prior result missed links

The synthetic adaptation selected the raw whole-sheet recipe, not the complete M3 tiled-detection/traced-connectivity recipe. `site_extraction_workflow.py` explicitly declares `tiles: None` and `tracing: False`; journal section 32 records the distinction. Therefore these existing predictions cannot reproduce M3 just by running a tracer.

The unchanged OPEN100 tracer traces connected ink. Dotted/dashed strokes are separate components. On the now-exposed Synthetic sheets 2/3, simply replacing raw links with the legacy trace **reduces** true collapsed links from 58 to 48 and increases false links from 3 to 5. A broad horizontal/vertical morphological close can recover far more links, but also joins unrelated ink. Neither omission alone nor indiscriminate gap filling is an adequate solution.

## New behavior

- Preserve original source records in `source_record`; output a fresh method record. Detected symbols are byte-for-byte equal as JSON values. Frozen metadata is never relabeled as belonging to the new prediction.
- Mask detected symbol interiors and a 2.5%-of-median-symbol-short-side guard. This prevents stroke outlines left outside imperfect boxes from bypassing an inline component. The legacy through-line snap heuristic is disabled in this **new** wrapper only.
- Along each raster axis, recover trains containing at least four short runs. Maximum internal gap is 25% of median symbol short side; maximum dash is 50%; minimum train span is 60%. Horizontal and vertical evidence both come from the original masked raster, never recursively from synthesized strokes.
- Extend a qualified train endpoint by at most the same gap bound, stopping at symbol barriers. Two qualified trains can therefore meet across up to twice that bound. This supports dotted bends and endpoint phase gaps; it is a declared inference, not observed continuous ink.
- Reuse the unchanged legacy tracer, with joined-crossing/all-pairs collapsed-network graph convention. This matches the scoring target, **not verified physical pipe junctions or flow**.
- Prediction contains traced candidates only. Original model edges and a separate union reconciliation retain model-only, trace-only and shared evidence. That reconciliation is not the default prediction or approval.
- Every output link has unknown semantic line type/direction and an unverified review status. `gap_recovery_dependent` compares against the same guarded trace without recovery. Network IDs point to source-pixel network bounds, recovered-pixel count and recovery envelope. These are support regions, not exact shortest paths or proof that every stroke is a pipe.

No instrument ownership or parent assignment is changed. As the original journal noted, a better collapsed clique score can coexist with worse instrument-parent assignment.

## Run locally

Installed NumPy/OpenCV dependencies are required. No installation happens here.

```bash
python scripts/trace_connections_v2.py \
  --image /path/to/drawing.png \
  --record /path/to/preserved_prediction.json \
  --out /path/to/new_connectivity_dev_record.json
python scripts/test_trace_connections_v2.py
python scripts/evaluate_connectivity_dev_v2.py --out runs/new-connectivity-dev-evaluation
python scripts/run_tests.py --full
```

The inference CLI refuses an existing output. The evaluation harness likewise creates a new directory and writes predictions before opening labels for scoring. It only evaluates the four already-exposed Synthetic sheets, reads the same preserved detections for every method, verifies input hashes did not change, and creates exact recovered-pixel overlays: **red = synthesized recovery pixels; blue = supplied symbol boxes/IDs**. Overlays and annotation-derived outputs remain ignored local data subject to the source dataset licensing; see the synthetic adaptation guide.

## Development results, not a new holdout

All sheets 0–3 are exposed development data. Values below are TP / FP / FN against the unchanged collapsed-undirected-link scorer. Symbols are identical in every column.

| Sheet | Raw extraction | Legacy trace | Development v2 trace |
|---|---:|---:|---:|
| 0 | 19 / 0 / 19 | 24 / 0 / 14 | 27 / 0 / 11 |
| 1 | 25 / 1 / 2 | 15 / 0 / 12 | 19 / 0 / 8 |
| 2 | 31 / 0 / 43 | 29 / 0 / 45 | 48 / 0 / 26 |
| 3 | 27 / 3 / 8 | 19 / 5 / 16 | 23 / 7 / 12 |
| All 0–3 | 102 / 4 / 72 | 87 / 5 / 87 | 117 / 7 / 57 |
| Exposed 2–3 only | 58 / 3 / 51 | 48 / 5 / 61 | 71 / 7 / 38 |

Aggregate missed-plus-false corrections on 2/3 fall from 54 to 45, but sheets1 and3 regress against raw extraction. This is **not a universal replacement**, full-M3 transfer result, or production-readiness claim. Confidence calibration, process/signal semantics, directional flow, tags, instrument ownership and live mapping are not established.

The machine-readable local report lists every correctly/incorrectly added/removed pair against raw and legacy baselines, plus separately labeled union diagnostics. A removed correct link is a regression; an incorrect removal is a beneficial deletion. Union results must not be presented as traced-only performance.

Separate **candidate union diagnostic** (TP / FP / FN): sheet0 29/0/9; sheet1 25/1/2; sheet2 52/0/22; sheet3 28/7/7. Aggregate0–3 =134/8/40; exposed2–3 =80/7/29. The union preserves model-only hypotheses and all trace-only false joins. It is a review reconciliation, not a verified improvement or default traced prediction.

## Verification

Final local full cached-data suite:20/20 scripts. Source-only suite:15/15 scripts. Frozen-trial harness:18/18 tests. New focused fixture suite:8 tests with multi-scale subcases; the known threshold miss is explicitly asserted as a limit. Independent additional geometry controls:34/36 recover as expected,2 documented threshold misses,0 false links. Frozen files/source evidence and the unrelated process-mimic patch remain byte-identical by SHA-256. These are offline checks, not live gateway/PI acceptance.

## Experiments retained honestly

1. Unchanged tracer baseline: 0–3 true/false = 24/0, 15/0, 29/0, 19/5.
2. Broad-close diagnostic: 15% symbol-side axis closing, unchanged tracer: 38/6, 25/5, 73/0, 29/10. Disabling through-line snap did not change these counts. Rejected as default because it lacks repeated-dash evidence and increases false joins.
3. Initial selective interior-only recovery at15% gap/30% dash, without guard, was tested with a diagnostic raw union: 29/0,25/1,50/0,28/7. These **union** values were not adopted as the traced headline.
4. Added guard, fixed25% gap/50% dash, traced-only: 24/0,19/0,45/0,21/7. Guarded attachment boxes corrected masking-band mismatch: 26/0,19/0,48/0,22/7.
5. Qualified endpoint extension (final geometry): 27/0,19/0,48/0,23/7. Fractions are shared across every sheet; no per-sheet switches, class remapping or source-label input.

These sequential exposed-data diagnostics are development, not unbiased model comparisons or prospective generalization evidence.

## Controls and remaining limits

Authored fixtures cover bends, tees, joined crossings, detected inline barriers (including a through-running stroke), solid/dashed parallel lines, isolated gaps, large breaks, insufficient ticks and source-record immutability at half/normal/double scale. A specific small-symbol/dash threshold case is recorded as an expected **miss**: raster endcaps can make a21px dash exceed a20px bound. This test documents a sensitivity limit, not successful recovery.

Repeated text strokes can resemble dashes. Small or missed symbols can remain hidden barriers, close parallel ink can be mistaken for contact, and one mistaken junction expands to many false clique links. Box error, short trains, diagonal/dashed non-axis lines, scan degradation and threshold-adjacent scale changes remain unresolved. A network bounds overlay is not a verified path. Qualified engineering review and new prospectively frozen data are needed before wider promotion.
