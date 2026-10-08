# Extraction scorecard: `hb-trace` (split: all)

Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.

| Tool | Model | Drawings (failed) | **Review load** (per 100, lower=better) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |
|---|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5[1m] | 20 (0) | **28.2** | 0.95 (P 0.99 / R 0.92) | 0.89 (P 0.93 / R 0.86) | 0.78 (P 0.81 / R 0.75) | 0.83 (P 0.94 / R 0.74) | 134.8 | $0.00 |
| codex | gpt-6.1-sol | 20 (0) | **16.2** | 0.99 (P 0.99 / R 1.00) | 0.92 (P 0.92 / R 0.93) | 0.85 (P 0.85 / R 0.85) | 0.91 (P 0.98 / R 0.84) | 152.7 | $0.00 |
| gemini | gemini-3.1-pro-preview | 20 (0) | **83.9** | 0.67 (P 0.90 / R 0.54) | 0.63 (P 0.84 / R 0.50) | 0.30 (P 0.40 / R 0.24) | 0.42 (P 0.61 / R 0.32) | 75.3 | $3.11 |

## Rough match by class (F1)

| Tool | tank | pump | valve | instrumentation | inlet/outlet | general |
|---|---|---|---|---|---|---|
| claude | 0.00 (0) | 0.00 (0) | 0.96 (1202) | 0.97 (464) | 0.00 (0) | 0.72 (693) |
| codex | 0.00 (0) | 0.00 (0) | 0.95 (1202) | 0.93 (464) | 0.00 (0) | 0.87 (693) |
| gemini | 0.00 (0) | 0.00 (0) | 0.71 (1202) | 0.86 (464) | 0.00 (0) | 0.15 (693) |

Numbers in parentheses in the class table are how many of that class the answer keys contain.
Subscription tools show $0.00; their cost is a flat subscription, not per call.
