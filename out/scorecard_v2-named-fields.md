# Extraction scorecard: `v2-named-fields`

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 12 (0) | 0.90 (P 0.99 / R 0.82) | 0.85 (P 0.94 / R 0.77) | 0.68 (P 0.75 / R 0.62) | 0.42 (P 0.67 / R 0.30) | 103.7 | $0.00 |
| codex | gpt-6.1-sol | 12 (0) | 0.90 (P 0.93 / R 0.88) | 0.85 (P 0.88 / R 0.83) | 0.71 (P 0.73 / R 0.69) | 0.53 (P 0.69 / R 0.44) | 112.8 | $0.00 |
| gemini | gemini-3.1-pro-preview | 12 (0) | 0.79 (P 0.91 / R 0.70) | 0.74 (P 0.85 / R 0.66) | 0.56 (P 0.64 / R 0.49) | 0.24 (P 0.43 / R 0.17) | 50.9 | $1.45 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.69 (35) | 0.44 (16) | 0.97 (257) | 0.99 (350) | 0.99 (96) | 0.27 (234) |
| codex | 0.70 (35) | 0.44 (16) | 0.98 (257) | 0.99 (350) | 0.99 (96) | 0.45 (234) |
| gemini | 0.74 (35) | 0.47 (16) | 0.64 (257) | 0.98 (350) | 0.99 (96) | 0.11 (234) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
