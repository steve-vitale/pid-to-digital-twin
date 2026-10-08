# Extraction scorecard: `r4-scan-L3-symbols-clean-trace` (split: holdout-a)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 6 (0) | **47.9** | 0.86 (P 0.98 / R 0.77) | 0.81 (P 0.92 / R 0.72) | 0.74 (P 0.85 / R 0.67) | 0.63 (P 0.84 / R 0.50) | 64.2 | $0.00 |
| codex | gpt-6.1-sol | 6 (0) | **60.7** | 0.82 (P 0.97 / R 0.71) | 0.77 (P 0.90 / R 0.66) | 0.64 (P 0.75 / R 0.55) | 0.53 (P 0.70 / R 0.43) | 53.2 | $0.00 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.74 (19) | 0.35 (5) | 0.88 (118) | 0.99 (190) | 0.99 (48) | 0.05 (108) |
| codex | 0.78 (19) | 0.67 (5) | 0.70 (118) | 0.96 (190) | 0.96 (48) | 0.09 (108) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
