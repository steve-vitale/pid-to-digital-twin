# Extraction scorecard: `r2-trace-oracle` (split: dev)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| oracle | answer-key-symbols | 6 (0) | **9.6** | 1.00 (P 1.00 / R 1.00) | 1.00 (P 1.00 / R 1.00) | 1.00 (P 1.00 / R 1.00) | 0.93 (P 0.96 / R 0.90) | 0.0 | $0.00 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| oracle | 1.00 (16) | 1.00 (11) | 1.00 (139) | 1.00 (160) | 1.00 (48) | 1.00 (126) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
