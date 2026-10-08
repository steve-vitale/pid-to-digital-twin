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
- `runs/gemini_spend.json`: the spend ledger the $25 Gemini cap enforces;
- `out/scorecard_<label>.*`: scores per run label;
- `out/costs.*`: time and cost totals from every record (`python scripts/cost_report.py`).
