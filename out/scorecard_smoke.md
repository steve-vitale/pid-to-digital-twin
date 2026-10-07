# Extraction scorecard: `smoke`

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 1 (0) | 1.00 (P 1.00 / R 1.00) | 0.97 (P 0.97 / R 0.97) | 0.72 (P 0.72 / R 0.72) | 0.87 (P 0.88 / R 0.86) | 76.3 | $0.00 |
| codex | gpt-6.1-sol | 1 (0) | 0.93 (P 0.87 / R 1.00) | 0.86 (P 0.80 / R 0.93) | 0.67 (P 0.63 / R 0.72) | 0.53 (P 0.50 / R 0.57) | 60.3 | $0.00 |
| gemini | gemini-3.1-pro-preview | 1 (0) | 0.86 (P 1.00 / R 0.75) | 0.74 (P 0.87 / R 0.65) | 0.37 (P 0.43 / R 0.33) | 0.24 (P 0.39 / R 0.18) | 26.2 | $0.05 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.00 (0) | 0.00 (0) | 1.00 (11) | 1.00 (14) | 1.00 (11) | 0.86 (4) |
| codex | 0.00 (0) | 0.00 (0) | 1.00 (11) | 0.92 (14) | 1.00 (11) | 0.40 (4) |
| gemini | 0.00 (0) | 0.00 (0) | 0.80 (11) | 0.67 (14) | 1.00 (11) | 0.00 (4) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
