# Extraction scorecard: `hb-tiles-trace` (split: all)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 20 (0) | **16.5** | 0.99 (P 0.99 / R 0.99) | 0.93 (P 0.94 / R 0.93) | 0.91 (P 0.91 / R 0.90) | 0.90 (P 0.98 / R 0.83) | 97.6 | $0.00 |
| codex | gpt-6.1-sol | 20 (0) | **20.7** | 0.98 (P 0.97 / R 0.99) | 0.92 (P 0.92 / R 0.93) | 0.91 (P 0.90 / R 0.92) | 0.88 (P 0.95 / R 0.82) | 86.3 | $0.00 |
| gemini | gemini-3.1-pro-preview | 20 (0) | **38.3** | 0.92 (P 0.96 / R 0.88) | 0.86 (P 0.90 / R 0.83) | 0.71 (P 0.74 / R 0.68) | 0.76 (P 0.90 / R 0.67) | 41.2 | $4.99 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.00 (0) | 0.00 (0) | 0.97 (1202) | 0.93 (464) | 0.00 (0) | 0.88 (693) |
| codex | 0.00 (0) | 0.00 (0) | 0.96 (1202) | 0.93 (464) | 0.00 (0) | 0.85 (693) |
| gemini | 0.00 (0) | 0.00 (0) | 0.93 (1202) | 0.93 (464) | 0.00 (0) | 0.68 (693) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
