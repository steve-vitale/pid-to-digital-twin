# Extraction scorecard: `r2-tiles-trace` (split: dev)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 6 (0) | **36.1** | 0.86 (P 0.91 / R 0.81) | 0.81 (P 0.86 / R 0.76) | 0.68 (P 0.73 / R 0.64) | 0.79 (P 0.88 / R 0.72) | 91.2 | $0.00 |
| codex | gpt-6.1-sol | 6 (0) | **20.5** | 0.95 (P 0.94 / R 0.96) | 0.90 (P 0.89 / R 0.91) | 0.83 (P 0.82 / R 0.83) | 0.88 (P 0.91 / R 0.85) | 64.7 | $0.00 |
| gemini | gemini-3.1-pro-preview | 6 (0) | **59.2** | 0.86 (P 0.92 / R 0.81) | 0.80 (P 0.85 / R 0.75) | 0.57 (P 0.61 / R 0.53) | 0.61 (P 0.67 / R 0.56) | 27.1 | $1.13 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.63 (16) | 0.48 (11) | 0.90 (139) | 0.94 (160) | 0.98 (48) | 0.40 (126) |
| codex | 0.63 (16) | 0.30 (11) | 0.96 (139) | 0.97 (160) | 1.00 (48) | 0.81 (126) |
| gemini | 0.63 (16) | 0.38 (11) | 0.88 (139) | 0.97 (160) | 0.97 (48) | 0.34 (126) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
