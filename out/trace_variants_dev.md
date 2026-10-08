# Traced connections: every variant tried (development set only, OPEN100 0-5)

Method: `scripts/trace_connections.py`. Review load per 100 key items (lower is better), connection precision / recall,
micro-averaged over drawings 0-5. "Oracle" feeds the tracer the answer key's own symbol boxes, which isolates tracing
from detection. Tools use their round-1 prompt-v2 symbols (`runs/round1-v2-named-fields`). Holdouts were not touched.

## Final defaults

| Symbols | Connections from | Review load | Conn. P | Conn. R |
|---|---|---|---|---|
| Oracle (answer-key boxes) | tracer | **9.6** | 0.96 | 0.90 |
| Claude | model (round-1 baseline) | 66.4 | 0.70 | 0.27 |
| Claude | tracer (replace) | **29.8** | 0.92 | 0.74 |
| Claude | tracer + model (union) | 35.4 | 0.82 | 0.76 |
| Codex | model (round-1 baseline) | 66.5 | 0.65 | 0.35 |
| Codex | tracer (replace) | **34.4** | 0.85 | 0.76 |
| Codex | tracer + model (union) | 41.6 | 0.74 | 0.81 |
| Gemini | model (round-1 baseline) | 90.8 | 0.36 | 0.12 |
| Gemini | tracer (replace) | **87.6** | 0.46 | 0.22 |
| Gemini | tracer + model (union) | 97.1 | 0.37 | 0.26 |

Defaults: crossings joined, band 0.05 x median symbol side (2 px floor), through-line snap on, missed-symbol barrier
(blob >= 0.3 side, fill < 0.4, < 60% orthogonal strokes), all pairs per network.

## Variants, in the order tried (review load: oracle / claude / codex / gemini)

| Variant | Oracle | Claude | Codex | Gemini | Verdict |
|---|---|---|---|---|---|
| First cut: split 4-arm crossings, band 0.15, no through-line or barrier | 15.2 | - | - | - | starting point |
| Join crossings (key treats crossings as pass-through), band 0.15 | 12.2 | 34.3 | 43.9 | 131.4 | kept: joining |
| ... band 0.05 | 9.8 | 32.5 | 36.6 | 120.3 | kept |
| ... band 0.3 / 0.5 (oracle column: band 0.25 / 0.4 with crossings split) | 17.2 / 21.3 | 39.5 / 51.6 | 45.8 / 60.1 | 138.3 / 152.5 | rejected |
| line_frac 0.3 / 0.6 / 1.0 with crossings joined | 9.8 all | - | - | - | no effect |
| Through-line boxes dropped | 14.7 | 36.5 | 39.6 | 117.5 | rejected |
| Through-line boxes snapped to remaining ink | 9.8 | 32.2 | 36.1 | 117.1 | kept (small) |
| + barrier, size only, 0.3 side | 9.5 | 34.3 | 37.8 | 80.0 | blocks nozzles |
| + barrier, size only, 0.5 / 0.8 side | 9.7 / 8.4 | 30.7 / 30.8 | 34.6 / 34.7 | 103.2 / 111.2 | |
| + barrier 0.3 side, < 60% orthogonal strokes (**final**) | 9.6 | **29.8** | **34.4** | 87.6 | kept |
| + barrier 0.3 side, < 40% orthogonal | 8.3 | 30.9 | 34.5 | 100.5 | |
| + barrier 0.2 side, < 60% orthogonal | 9.9 | 30.3 | 34.4 | 87.6 | |
| + barrier only if compact (not one slanted stroke) | 9.7 | 31.1 | 36.1 | 88.4 | rejected |
| + barrier size cap 2 / 3 / 5 sides | 10.9 / 9.6 / 9.6 | 29.8 | 35.8 / 34.4 | 87.5 | no effect |
| Final, but split 4-arm crossings | 17.9 | 45.8 | 40.3 | 83.9 | rejected |
| Final, nearest-neighbour tree instead of all pairs | 45.5 | 60.5 | 62.3 | 81.5 | rejected (best for Gemini only) |
| Final, all pairs only up to 6 / 12 symbols per network, else tree | 39.5 / 36.3 | 55.6 / 52.3 | 58.5 / 55.3 | 81.2 / 81.6 | rejected |
| Final, band 0.1 / 0.2 | 10.1 / 11.3 | 30.0 / 32.0 | 36.6 / 38.6 | 89.7 / 93.4 | rejected |
| Final, frame filter off | 9.6 | 29.8 | - | - | never fires on dev |
| Union (tracer + model links), any band | - | 35.4-37.7 | 41.6-45.5 | 97-103 | rejected |

Run with `python scripts/trace_connections.py ...` then `python scripts/scorecard.py --label <label> --split dev`.
Variant numbers came from an in-memory sweep with the same `trace()` and `score_pid2graph.score()`; the final rows
match the scorecards `out/scorecard_r2-trace*_dev.md`.
