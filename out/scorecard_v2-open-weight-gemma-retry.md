# Extraction scorecard: `v2-open-weight-gemma-retry`

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|
| gemini | gemma-4-31b-it | 5 (3) | 0.21 (P 0.92 / R 0.12) | 0.17 (P 0.72 / R 0.09) | 0.05 (P 0.23 / R 0.03) | 0.02 (P 0.19 / R 0.01) | 3342.1 | $0.27 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| gemini | 0.24 (20) | 0.00 (6) | 0.03 (112) | 0.21 (176) | 0.59 (43) | 0.00 (112) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
