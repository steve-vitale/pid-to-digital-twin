# Extraction scorecard: `r2-tiles-2x2` (split: holdout-a)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 6 (0) | **54.9** | 0.93 (P 0.98 / R 0.88) | 0.90 (P 0.95 / R 0.85) | 0.84 (P 0.89 / R 0.80) | 0.50 (P 0.70 / R 0.38) | 72.0 | $0.00 |
| codex | gpt-6.1-sol | 6 (0) | **31.7** | 0.97 (P 0.95 / R 0.98) | 0.94 (P 0.93 / R 0.95) | 0.89 (P 0.88 / R 0.90) | 0.76 (P 0.81 / R 0.72) | 55.0 | $0.00 |
| gemini | gemini-3.1-pro-preview | 6 (0) | **68.0** | 0.89 (P 0.97 / R 0.81) | 0.84 (P 0.92 / R 0.77) | 0.71 (P 0.78 / R 0.65) | 0.34 (P 0.57 / R 0.24) | 24.8 | $1.01 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.77 (19) | 0.47 (5) | 0.99 (118) | 1.00 (190) | 0.98 (48) | 0.52 (108) |
| codex | 0.72 (19) | 0.50 (5) | 0.99 (118) | 1.00 (190) | 0.99 (48) | 0.83 (108) |
| gemini | 0.64 (19) | 0.43 (5) | 0.92 (118) | 0.98 (190) | 0.97 (48) | 0.33 (108) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
