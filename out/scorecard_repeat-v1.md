# Extraction scorecard: `repeat-v1`

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 12 (0) | 0.90 (P 0.99 / R 0.82) | 0.85 (P 0.94 / R 0.77) | 0.72 (P 0.80 / R 0.66) | 0.42 (P 0.68 / R 0.30) | 94.7 | $0.00 |
| codex | gpt-6.1-sol | 12 (0) | 0.92 (P 0.94 / R 0.90) | 0.87 (P 0.89 / R 0.85) | 0.71 (P 0.73 / R 0.69) | 0.56 (P 0.72 / R 0.46) | 93.7 | $0.00 |
| gemini | gemini-3.1-pro-preview | 12 (0) | 0.61 (P 0.71 / R 0.54) | 0.57 (P 0.66 / R 0.51) | 0.45 (P 0.51 / R 0.39) | 0.14 (P 0.25 / R 0.10) | 73.1 | $1.22 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.69 (35) | 0.44 (16) | 0.97 (257) | 0.99 (350) | 0.98 (96) | 0.26 (234) |
| codex | 0.72 (35) | 0.40 (16) | 0.98 (257) | 0.98 (350) | 0.99 (96) | 0.56 (234) |
| gemini | 0.63 (35) | 0.53 (16) | 0.44 (257) | 0.79 (350) | 0.76 (96) | 0.07 (234) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
