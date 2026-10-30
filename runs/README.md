# Run records (not committed)

`scripts/run_extraction.py` writes one JSON record per drawing per tool to `runs/<label>/<tool>/<drawing>.json`.
They hold the raw model output, so they stay out of git. Each record carries:
- the model and the prompt and image hashes;
- wall-clock seconds (and, for tiled runs, per-tile seconds and their serial sum);
- estimated or notional cost, and token usage where the tool reports it (recorded from 2026-10-08 on);
- errors, and the parsed prediction.

Trace labels (`*-trace`) add the code line tracer's own record (`tracer.seconds`) and copy the source run's model
time and cost.

What is committed instead:
- `predictions/<label>/<tool>/<drawing>.json`: the parsed prediction and the metadata the scorers read from each
  record, without the raw model text, including records recovered from preserved research working copies on
  2026-10-29 (`predictions/README.md`, `predictions/RECOVERY.json`).
  `python scripts/rescore.py --check` re-scores the committed scorecards and replicate tables from them alone.
  After a new run, `python scripts/rescore.py --export --label <label>` writes its predictions;
- `runs/gemini_spend.json`: the spend ledger the $25 Gemini cap enforces;
- `out/scorecard_<label>.*`: scores per run label;
- `out/costs.*`: time and cost totals from every record (`python scripts/cost_report.py`).

Predictions still not located: the development drawings of `r2-trace`, and the `-ov`, oracle and union variants of
round 2. The round-5 replicates and revision-A Tennessee Eastman runs were recovered; their tables now re-score.
`scripts/rescore.py` lists the five unrecovered diagnostic tables in `KNOWN_GAPS`.
