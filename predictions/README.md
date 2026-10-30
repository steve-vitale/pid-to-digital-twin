# Predictions (committed, re-scorable)

`predictions/<label>/<tool>/<drawing>.json` is the parsed answer each model run gave for one drawing: the part of a
run record the scorers read, and nothing else. The full run records under `runs/` stay out of git because they hold
the raw model text ([runs/README.md](../runs/README.md)); these files let anyone re-score the committed tables
without them.

```sh
python scripts/rescore.py --check               # regenerate every scorecard and replicate table, diff against out/
python scripts/rescore.py --check --label r2-tiles-trace
python scripts/rescore.py --list                # which tables have their predictions committed
```

`--check` exits 1 if any regenerated table differs from the committed one. It never writes to `runs/` or `out/`.
Standard library only, offline, a few minutes for everything.

## What a file holds

- `prediction`: every symbol with only `id`, `class`, `box` or `bbox`, `tag` and `confidence`, and every connection
  unchanged (`from`, `to`). `null` when the run failed; a failed run scores as an empty answer, never as skipped.
- The metadata the scorers and tables print: `tool`, `drawing`, `label`, `model`, `prompt_file`, `prompt_sha256`,
  `image_sha256`, `ran_at`, `seconds`, `cost_usd`, `cost_usd_notional`, `error`, `parse_error`; for a traced run
  `source_label` and `tracer` (script, mode, seconds, date); for a tiled run `tiling` (grid, overlap, preface hash,
  summed tile seconds, failed tiles).
- Dropped: the raw model text (whole-sheet and per tile), token usage, per-tile records, merge and tracer statistics,
  and each symbol's tile-merge provenance (`tiles_seen`, `merged_from`). No scorer reads them.

The prompt files themselves are in `extraction/`; `prompt_sha256` and `image_sha256` tie each prediction to the exact
prompt and image it answered.

## Labels committed (101 labels, 1,123 files, 15.0 MB)

The initial 52 labels were exported from the active checkout with `python scripts/rescore.py --export`.
Another 49 labels (391 files) were recovered from preserved research working copies on the same date.
[RECOVERY.json](RECOVERY.json) records each original raw-record hash and each parsed-export hash, plus the
checkout snapshot identity; the snapshot does not contain the ignored raw records. The receipt documents the
recovery and file identity, not an authenticated attestation from the model provider.

| Labels | Drawings | Tools | Size |
|---|---|---|---|
| `first-try`, `repeat-v1`, `v2-named-fields` (round 1) | OPEN100 0-11 | claude, codex, gemini | 1.1 MB |
| `smoke`, `smoke-gemma`, `v2-open-weight-gemma`, `v2-open-weight-gemma-retry` | OPEN100 | as run | 0.1 MB |
| `r2-tiles-2x2`, `r2-tiles-trace` (round 2) | OPEN100 0-11 | claude, codex, gemini | 1.1 MB |
| `r2-tiles-2x2-repeat` | OPEN100 0-5 | claude, codex, gemini | 0.2 MB |
| `r2-trace` | OPEN100 6-11 only | claude, codex, gemini | 0.2 MB |
| `hb-v2`, `hb-tiles-2x2`, `hb-trace`, `hb-tiles-trace` (holdout B) | PID2Graph Dataset PID, 20 sheets | claude, codex, gemini | 6.1 MB |
| `r4-scan-L1/L2/L3-tiles`, `-trace`, `r4-scan-L3-symbols-clean-trace` (round 4) | OPEN100 6-11, degraded copies | claude, codex | 1.0 MB |
| `r5-hA-rep*`, `r5-dx-rep*` (20 recovered labels) | OPEN100 6-11 and DEXPI C01-C03/C08a/C08b | claude, codex | 2.6 MB |
| `te-*` (29 recovered labels, revision A round trip and perfect-reader key) | generated TE sheets 101-103 | claude, codex, key | 1.0 MB |
| `tec-*` (Tennessee Eastman revision C round trip, 29 labels) | generated TE sheets 101-103 | claude, codex | 1.5 MB |
| `zz-runbook-trace-test` | OPEN100 0 | codex | 0.03 MB |

## What re-scores, and what doesn't

Checked on 2026-10-29 with `python scripts/rescore.py --check`:

- **Byte for byte (23 tables):** every round-2 scorecard on holdout A and the development set except `r2-trace_dev`
  (including `scorecard_r2-tiles-trace_holdout-a`, the README's round-2 numbers), the four holdout-B scorecards,
  all seven round-4 scan scorecards, `v2-named-fields_dev`/`_holdout-a`, and the Tennessee Eastman revision-C round
  trip `out/te_pid/roundtrip_scores_revC` (a replicate table, five clean and three per scan level). The three
  recovered round-5 tables also match, including the headline holdout-A replicates; the DEXPI tiles-only
  diagnostic compares its JSON because its Markdown has a hand-written header.
- **Byte for byte in their original format (7 tables):** `first-try`, `repeat-v1`, `smoke`, `v2-named-fields`,
  `v2-open-weight-gemma`, `v2-open-weight-gemma-retry`. They were written before the scorer printed a review-load
  column; every committed byte regenerates, and the current scorer also prints that column (`MATCH-OLD`).
  Revision-A `out/te_pid/roundtrip_scores` also matches: only the exact source-location line added by the
  current generator is omitted from its Markdown comparison, and its full JSON compares unchanged.
- **Not re-scorable (5 tables):** `scorecard_r2-trace_dev` (only drawings 6-11 remain),
  `scorecard_r2-tiles-2x2-ov_dev`, `scorecard_r2-tiles-2x2-repeat-ov_dev`,
  `scorecard_r2-trace-oracle_dev`, and `scorecard_r2-trace-union_dev`.

  Their original predictions have not been located. `scripts/rescore.py` lists each in `KNOWN_GAPS`; a table
  missing its predictions without an entry there fails the check. A `GAP` is not a reproduced result.

Holdout B's answer keys are not committed (`scripts/fetch_pid2graph.py` downloads them). Without them its four
scorecards report `SKIP`, not a pass.

## Provenance and licence

The predictions are model readings of public or generated drawings, so they are data derived from those drawings:

- **OPEN100 sheets 0-11 and their degraded scan copies** (`first-try`, `repeat-v1`, `v2-*`, `smoke*`, `r2-*`, `r5-hA-*`,
  `r4-*`, `zz-*`): derived from [PID2Graph, Zenodo record 14803338](https://zenodo.org/records/14803338) (OPEN100
  design by the Energy Impact Center), shared under **CC BY-SA 4.0** as that licence requires. Changes: read by a
  model, parsed into symbols and connections, and for traced labels re-linked by `scripts/trace_connections.py`.
- **Holdout B** (`hb-*`): derived from PID2Graph's "Dataset PID" in the same Zenodo record, **CC BY-SA 4.0**, same
  changes. The drawings themselves are not redistributed here.
- **Tennessee Eastman sheets** (`te-*`, `tec-*`): drawn by this repository's code from its own process model, so the
  readings are MIT licensed like the drawings (NOTICE.md).

Credit to the PID2Graph authors (Jan Marius Stürmer, Marius Graumann and Tobias Koch) and to the Energy Impact
Center. The models that produced the readings are named in each file (`model`); see [NOTICE.md](../NOTICE.md) for
the repository's other licences.

- **DEXPI round-5 readings** (`r5-dx-*`): derived from the DEXPI TrainingTestCases example drawings,
  CC BY 4.0, with attribution in [NOTICE.md](../NOTICE.md). Parsed and re-linked model readings are adaptations;
  the source drawings themselves are not redistributed here.
