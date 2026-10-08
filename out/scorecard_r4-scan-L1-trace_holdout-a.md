# Extraction scorecard: `r4-scan-L1-trace` (split: holdout-a)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 6 (0) | **29.7** | 0.93 (P 0.99 / R 0.88) | 0.90 (P 0.96 / R 0.85) | 0.85 (P 0.91 / R 0.80) | 0.79 (P 0.90 / R 0.70) | 68.1 | $0.00 |
| codex | gpt-6.1-sol | 6 (0) | **20.6** | 0.96 (P 0.94 / R 0.98) | 0.92 (P 0.91 / R 0.94) | 0.83 (P 0.82 / R 0.85) | 0.87 (P 0.89 / R 0.85) | 60.8 | $0.00 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.74 (19) | 0.50 (5) | 1.00 (118) | 1.00 (190) | 0.99 (48) | 0.51 (108) |
| codex | 0.70 (19) | 0.38 (5) | 0.99 (118) | 0.99 (190) | 0.99 (48) | 0.79 (108) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
