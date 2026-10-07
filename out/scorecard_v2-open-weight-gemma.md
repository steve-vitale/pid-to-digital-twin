# Extraction scorecard: `v2-open-weight-gemma`

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|
| gemini | gemma-4-31b-it | 12 (5) | 0.32 (P 0.93 / R 0.19) | 0.25 (P 0.73 / R 0.15) | 0.12 (P 0.36 / R 0.07) | 0.02 (P 0.12 / R 0.01) | 888.4 | $0.89 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| gemini | 0.35 (35) | 0.55 (16) | 0.14 (257) | 0.29 (350) | 0.69 (96) | 0.00 (234) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
