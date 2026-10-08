# Extraction scorecard: `r4-scan-L2-trace` (split: holdout-a)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 6 (0) | **57.0** | 0.91 (P 0.99 / R 0.84) | 0.86 (P 0.94 / R 0.80) | 0.81 (P 0.88 / R 0.75) | 0.45 (P 0.76 / R 0.32) | 67.9 | $0.00 |
| codex | gpt-6.1-sol | 6 (0) | **51.5** | 0.92 (P 0.99 / R 0.87) | 0.87 (P 0.93 / R 0.82) | 0.74 (P 0.79 / R 0.70) | 0.51 (P 0.82 / R 0.38) | 59.2 | $0.00 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.72 (19) | 0.40 (5) | 0.99 (118) | 1.00 (190) | 0.98 (48) | 0.22 (108) |
| codex | 0.68 (19) | 0.62 (5) | 0.97 (118) | 1.00 (190) | 0.99 (48) | 0.36 (108) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
