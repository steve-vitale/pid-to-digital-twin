# Extraction scorecard: `r2-trace-union` (split: dev)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 6 (0) | **35.4** | 0.89 (P 0.99 / R 0.82) | 0.83 (P 0.92 / R 0.76) | 0.63 (P 0.69 / R 0.57) | 0.79 (P 0.82 / R 0.76) | 106.8 | $0.00 |
| codex | gpt-6.1-sol | 6 (0) | **41.6** | 0.89 (P 0.92 / R 0.86) | 0.83 (P 0.86 / R 0.81) | 0.67 (P 0.69 / R 0.65) | 0.77 (P 0.74 / R 0.81) | 117.9 | $0.00 |
| gemini | gemini-3.1-pro-preview | 6 (0) | **97.1** | 0.75 (P 0.86 / R 0.66) | 0.69 (P 0.80 / R 0.61) | 0.49 (P 0.57 / R 0.43) | 0.30 (P 0.37 / R 0.26) | 52.9 | $0.76 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.63 (16) | 0.48 (11) | 0.96 (139) | 0.98 (160) | 1.00 (48) | 0.31 (126) |
| codex | 0.65 (16) | 0.48 (11) | 0.97 (139) | 0.98 (160) | 1.00 (48) | 0.43 (126) |
| gemini | 0.67 (16) | 0.48 (11) | 0.57 (139) | 0.97 (160) | 1.00 (48) | 0.13 (126) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
