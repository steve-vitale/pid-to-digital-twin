# Extraction scorecard: `first-try`

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 12 (0) | 0.90 (P 0.99 / R 0.82) | 0.85 (P 0.94 / R 0.78) | 0.69 (P 0.77 / R 0.63) | 0.43 (P 0.68 / R 0.31) | 100.0 | $0.00 |
| codex | gpt-6.1-sol | 12 (0) | 0.92 (P 0.94 / R 0.90) | 0.87 (P 0.90 / R 0.85) | 0.68 (P 0.70 / R 0.66) | 0.56 (P 0.71 / R 0.46) | 95.1 | $0.00 |
| gemini | gemini-3.1-pro-preview | 12 (0) | 0.47 (P 0.54 / R 0.42) | 0.44 (P 0.51 / R 0.40) | 0.33 (P 0.37 / R 0.29) | 0.15 (P 0.28 / R 0.10) | 48.9 | $1.25 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.71 (35) | 0.53 (16) | 0.97 (257) | 0.99 (350) | 0.99 (96) | 0.25 (234) |
| codex | 0.68 (35) | 0.33 (16) | 0.97 (257) | 0.99 (350) | 0.99 (96) | 0.57 (234) |
| gemini | 0.44 (35) | 0.44 (16) | 0.37 (257) | 0.59 (350) | 0.59 (96) | 0.06 (234) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
