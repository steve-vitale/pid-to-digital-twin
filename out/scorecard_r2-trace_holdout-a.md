# Extraction scorecard: `r2-trace` (split: holdout-a)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 6 (0) | **36.0** | 0.90 (P 0.99 / R 0.82) | 0.86 (P 0.95 / R 0.79) | 0.73 (P 0.81 / R 0.67) | 0.75 (P 0.85 / R 0.67) | 100.6 | $0.00 |
| codex | gpt-6.1-sol | 6 (0) | **28.7** | 0.92 (P 0.94 / R 0.89) | 0.88 (P 0.90 / R 0.85) | 0.75 (P 0.77 / R 0.73) | 0.82 (P 0.88 / R 0.76) | 107.7 | $0.00 |
| gemini | gemini-3.1-pro-preview | 6 (0) | **55.4** | 0.83 (P 0.95 / R 0.73) | 0.79 (P 0.91 / R 0.70) | 0.63 (P 0.72 / R 0.56) | 0.59 (P 0.73 / R 0.49) | 49.0 | $0.69 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.74 (19) | 0.40 (5) | 0.98 (118) | 0.99 (190) | 0.99 (48) | 0.23 (108) |
| codex | 0.74 (19) | 0.40 (5) | 0.99 (118) | 1.00 (190) | 0.99 (48) | 0.46 (108) |
| gemini | 0.79 (19) | 0.46 (5) | 0.73 (118) | 0.99 (190) | 0.99 (48) | 0.09 (108) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
