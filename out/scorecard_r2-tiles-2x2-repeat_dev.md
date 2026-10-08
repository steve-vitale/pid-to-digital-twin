# Extraction scorecard: `r2-tiles-2x2-repeat` (split: dev)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 6 (0) | **72.8** | 0.84 (P 0.91 / R 0.79) | 0.80 (P 0.86 / R 0.75) | 0.67 (P 0.72 / R 0.63) | 0.33 (P 0.64 / R 0.22) | 75.6 | $0.00 |
| codex | gpt-6.1-sol | 6 (0) | **46.9** | 0.96 (P 0.96 / R 0.95) | 0.90 (P 0.91 / R 0.90) | 0.82 (P 0.83 / R 0.82) | 0.62 (P 0.80 / R 0.51) | 63.0 | $0.00 |
| gemini | gemini-3.1-pro-preview | 6 (0) | **75.1** | 0.85 (P 0.93 / R 0.78) | 0.79 (P 0.86 / R 0.72) | 0.59 (P 0.65 / R 0.55) | 0.28 (P 0.61 / R 0.18) | 27.9 | $1.09 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.65 (16) | 0.48 (11) | 0.86 (139) | 0.95 (160) | 0.98 (48) | 0.39 (126) |
| codex | 0.65 (16) | 0.48 (11) | 0.97 (139) | 0.98 (160) | 1.00 (48) | 0.77 (126) |
| gemini | 0.65 (16) | 0.48 (11) | 0.85 (139) | 0.96 (160) | 0.98 (48) | 0.21 (126) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
