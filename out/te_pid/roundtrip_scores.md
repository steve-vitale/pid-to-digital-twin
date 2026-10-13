# Round trip on the generated Tennessee Eastman sheets

**A round trip, not real-plant accuracy.** The three sheets were generated from the verified TE model and the answer keys come from the same model, so these numbers measure how faithfully the frozen method (2×2 tiles, prompt v2, code line tracer; nothing re-tuned) reads clean drawings in the learned house style. They are an upper bound and are not comparable with the OPEN100 results.

Mean over replicates, with the min–max range in brackets. 95% t-intervals are in the JSON.

| Image | Tool | Runs | Review load /100 (lower is better) | Symbols found F1 | Class F1 | Connections F1 | Tags read exactly | Tags read, if found | Off-page refs read | Misreads that are another real tag |
|---|---|---|---|---|---|---|---|---|---|---|
| clean | codex | 5 | 2.1 (2.1–2.1) | 0.99 (0.99–0.99) | 0.99 (0.99–0.99) | 0.99 (0.99–0.99) | 100% (100%–100%) | 100% (100%–100%) | 100% (100%–100%) | 0.00 (0.00–0.00) |
| clean | claude | 5 | 2.2 (2.1–2.6) | 0.99 (0.99–0.99) | 0.99 (0.99–0.99) | 0.99 (0.99–0.99) | 100% (100%–100%) | 100% (100%–100%) | 100% (100%–100%) | 0.00 (0.00–0.00) |
| L1 | codex | 3 | 2.1 (2.1–2.1) | 0.99 (0.99–0.99) | 0.99 (0.99–0.99) | 0.99 (0.99–0.99) | 100% (100%–100%) | 100% (100%–100%) | 93% (93%–93%) | 0.00 (0.00–0.00) |
| L1 | claude | 3 | 8.0 (2.6–11.5) | 0.97 (0.93–0.99) | 0.97 (0.93–0.99) | 0.96 (0.93–0.98) | 98% (93%–100%) | 100% (100%–100%) | 100% (100%–100%) | 0.00 (0.00–0.00) |
| L2 | codex | 3 | 2.1 (2.1–2.1) | 0.99 (0.99–0.99) | 0.99 (0.99–0.99) | 0.99 (0.99–0.99) | 56% (54%–58%) | 56% (54%–58%) | 0% (0%–0%) | 0.00 (0.00–0.00) |
| L2 | claude | 3 | 13.4 (11.5–14.7) | 0.99 (0.99–0.99) | 0.99 (0.99–0.99) | 0.91 (0.90–0.92) | 95% (95%–95%) | 95% (95%–95%) | 86% (79%–93%) | 0.00 (0.00–0.00) |
| L3 | codex | 3 | 16.9 (16.2–17.8) | 0.99 (0.99–0.99) | 0.98 (0.97–0.99) | 0.85 (0.85–0.86) | 14% (14%–14%) | 14% (14%–14%) | 0% (0%–0%) | 0.00 (0.00–0.00) |
| L3 | claude | 3 | 17.3 (15.7–18.3) | 0.98 (0.98–0.99) | 0.98 (0.98–0.99) | 0.85 (0.84–0.87) | 49% (44%–51%) | 49% (44%–51%) | 0% (0%–0%) | 1.33 (0.00–3.0) |

## What produced these numbers

Every sheet's {model, prompt, adapter, date, seconds, cost} is in `roundtrip_scores.json` (`runs[].records`). Claude dollars are the CLI's API-equivalent figure (the runs used a flat subscription); Codex reports no cost. No Gemini call was made.

| Tool | Models | Prompt | Sheet runs | Failed tiles | Wall s (sum) | Serial s (sum) | Claude API-equivalent $ |
|---|---|---|---|---|---|---|---|
| codex | gpt-6.1-sol | extraction/prompt_v2.md | 42 | 0 | 1746 | 5336 | not reported |
| claude | claude-opus-5-5[1m] | extraction/prompt_v2.md | 42 | 0 | 1877 | 6356 | 12.56 |

## Every tag that was not read exactly

| Run | Tool | Sheet | Printed | Extracted |
|---|---|---|---|---|
| te-L1-trace-r3 | claude | 102 | FI 110 | (symbol not found) |
| te-L1-trace-r3 | claude | 102 | AI 129 | (symbol not found) |
| te-L1-trace-r3 | claude | 102 | FV 206 | (symbol not found) |
| te-L2-trace-r1 | codex | 101 | FV 203 | 'FV\n200' |
| te-L2-trace-r1 | codex | 101 | FI 106 | 'PI 106' |
| te-L2-trace-r1 | codex | 101 | AI 123 | 'AI' |
| te-L2-trace-r1 | codex | 101 | PI 107 | 'PR 107' |
| te-L2-trace-r1 | codex | 101 | LI 108 | 'LE 108' |
| te-L2-trace-r1 | codex | 101 | TI 109 | 'TR 109' |
| te-L2-trace-r1 | codex | 101 | SC 212 | 'SC 721' |
| te-L2-trace-r1 | codex | 102 | FI 105 | 'PI 109' |
| te-L2-trace-r1 | codex | 102 | FI 110 | 'PI 110' |
| te-L2-trace-r1 | codex | 102 | AI 129 | 'AI 119' |
| te-L2-trace-r1 | codex | 102 | HV 205 | 'FV 205' |
| te-L2-trace-r1 | codex | 102 | FI 114 | 'PI 114' |
| te-L2-trace-r1 | codex | 102 | JI 120 | 'AI 120' |
| te-L2-trace-r1 | codex | 103 | FV 204 | 'PV 204' |
| te-L2-trace-r1 | codex | 103 | FI 104 | 'PI 104' |
| te-L2-trace-r1 | codex | 103 | FI 117 | 'TI\n133' |
| te-L2-trace-r1 | codex | 103 | FV 209 | 'PV 209' |
| te-L2-trace-r1 | codex | 103 | FI 119 | 'TI 110' |
| te-L2-trace-r2 | codex | 101 | FV 203 | 'PV\n200' |
| te-L2-trace-r2 | codex | 101 | FV 201 | 'PV\n201' |
| te-L2-trace-r2 | codex | 101 | FV 202 | 'PV\n202' |
| te-L2-trace-r2 | codex | 101 | FI 106 | 'PI 100' |
| te-L2-trace-r2 | codex | 101 | AI 123 | 'AI 101' |
| te-L2-trace-r2 | codex | 101 | PI 107 | 'PR\n107' |
| te-L2-trace-r2 | codex | 101 | LI 108 | 'LE\n108' |
| te-L2-trace-r2 | codex | 101 | TI 109 | 'TE' |
| te-L2-trace-r2 | codex | 101 | SC 212 | 'SC\n721' |
| te-L2-trace-r2 | codex | 102 | FI 105 | 'PI 109' |
| te-L2-trace-r2 | codex | 102 | AI 129 | 'AI 119' |
| te-L2-trace-r2 | codex | 102 | FV 206 | 'PV 206' |
| te-L2-trace-r2 | codex | 102 | HV 205 | 'PV 205' |
| te-L2-trace-r2 | codex | 102 | FI 114 | 'PI 114' |
| te-L2-trace-r2 | codex | 102 | JI 120 | 'AI 120' |
| te-L2-trace-r2 | codex | 103 | FV 204 | 'PV 204' |
| te-L2-trace-r2 | codex | 103 | FI 104 | 'PI\n104' |
| te-L2-trace-r2 | codex | 103 | FI 117 | 'TI\n137' |
| te-L2-trace-r2 | codex | 103 | FI 119 | 'PI\n110' |
| te-L2-trace-r3 | codex | 101 | FV 203 | 'PV\n200' |
| te-L2-trace-r3 | codex | 101 | FV 201 | 'PV\n201' |
| te-L2-trace-r3 | codex | 101 | FV 202 | 'PV\n202' |
| te-L2-trace-r3 | codex | 101 | FI 106 | 'FI 100' |
| te-L2-trace-r3 | codex | 101 | AI 123 | 'AI 102' |
| te-L2-trace-r3 | codex | 101 | TI 121 | 'TI 101' |
| te-L2-trace-r3 | codex | 101 | LI 108 | 'LE 108' |
| te-L2-trace-r3 | codex | 101 | TI 109 | 'TI 100' |
| te-L2-trace-r3 | codex | 101 | SC 212 | 'SC 727' |
| te-L2-trace-r3 | codex | 102 | FI 105 | 'PI 100' |
| te-L2-trace-r3 | codex | 102 | AI 129 | 'AI 109' |
| te-L2-trace-r3 | codex | 102 | FV 206 | 'PV 206' |
| te-L2-trace-r3 | codex | 102 | HV 205 | 'PV 205' |
| te-L2-trace-r3 | codex | 102 | FI 114 | 'PI 114' |
| te-L2-trace-r3 | codex | 102 | JI 120 | 'SI 120' |
| te-L2-trace-r3 | codex | 103 | FV 204 | 'PV 204' |
| te-L2-trace-r3 | codex | 103 | FI 104 | 'PI 104' |
| te-L2-trace-r3 | codex | 103 | FI 117 | 'TI\n137' |
| te-L2-trace-r3 | codex | 103 | FV 209 | 'PV 209' |
| te-L2-trace-r3 | codex | 103 | FI 119 | 'TI 119' |
| te-L2-trace-r1 | claude | 101 | TI 109 | 'TI 108' |
| te-L2-trace-r1 | claude | 103 | FV 209 | 'FV 208' |
| te-L2-trace-r2 | claude | 101 | TI 109 | 'TI 108' |
| te-L2-trace-r2 | claude | 102 | AI 129 | 'AI 120' |
| te-L2-trace-r3 | claude | 101 | TI 109 | 'TI 108' |
| te-L2-trace-r3 | claude | 102 | AI 129 | 'AI 120' |
| te-L3-trace-r1 | codex | 101 | FV 203 | None |
| te-L3-trace-r1 | codex | 101 | FI 101 | None |
| te-L3-trace-r1 | codex | 101 | FV 201 | None |
| te-L3-trace-r1 | codex | 101 | FI 102 | None |
| te-L3-trace-r1 | codex | 101 | FV 202 | None |
| te-L3-trace-r1 | codex | 101 | FI 103 | None |
| te-L3-trace-r1 | codex | 101 | FI 106 | None |
| te-L3-trace-r1 | codex | 101 | AI 123 | None |
| te-L3-trace-r1 | codex | 101 | TV 210 | None |
| te-L3-trace-r1 | codex | 101 | TI 121 | None |
| te-L3-trace-r1 | codex | 101 | PI 107 | None |
| te-L3-trace-r1 | codex | 101 | LI 108 | None |
| te-L3-trace-r1 | codex | 101 | TI 109 | None |
| te-L3-trace-r1 | codex | 101 | SC 212 | None |
| te-L3-trace-r1 | codex | 102 | FI 105 | None |
| te-L3-trace-r1 | codex | 102 | FI 110 | None |
| te-L3-trace-r1 | codex | 102 | AI 129 | None |
| te-L3-trace-r1 | codex | 102 | FV 206 | None |
| te-L3-trace-r1 | codex | 102 | HV 205 | None |
| te-L3-trace-r1 | codex | 102 | FI 114 | None |
| te-L3-trace-r1 | codex | 102 | LV 207 | None |
| te-L3-trace-r1 | codex | 102 | TV 211 | None |
| te-L3-trace-r1 | codex | 102 | TI 122 | None |
| te-L3-trace-r1 | codex | 102 | TI 111 | None |
| te-L3-trace-r1 | codex | 102 | LI 112 | None |
| te-L3-trace-r1 | codex | 102 | PI 113 | None |
| te-L3-trace-r1 | codex | 102 | JI 120 | None |
| te-L3-trace-r1 | codex | 103 | FV 204 | None |
| te-L3-trace-r1 | codex | 103 | FI 104 | None |
| te-L3-trace-r1 | codex | 103 | FI 117 | None |
| te-L3-trace-r1 | codex | 103 | AI 137 | None |
| te-L3-trace-r1 | codex | 103 | LV 208 | None |
| te-L3-trace-r1 | codex | 103 | FV 209 | None |
| te-L3-trace-r1 | codex | 103 | FI 119 | None |
| te-L3-trace-r1 | codex | 103 | PI 116 | None |
| te-L3-trace-r1 | codex | 103 | TI 118 | None |
| te-L3-trace-r1 | codex | 103 | LI 115 | None |
| te-L3-trace-r2 | codex | 101 | FV 203 | None |
| te-L3-trace-r2 | codex | 101 | FI 101 | None |
| te-L3-trace-r2 | codex | 101 | FV 201 | None |
| te-L3-trace-r2 | codex | 101 | FI 102 | None |
| te-L3-trace-r2 | codex | 101 | FV 202 | None |
| te-L3-trace-r2 | codex | 101 | FI 103 | None |
| te-L3-trace-r2 | codex | 101 | FI 106 | None |
| te-L3-trace-r2 | codex | 101 | AI 123 | None |
| te-L3-trace-r2 | codex | 101 | TV 210 | None |
| te-L3-trace-r2 | codex | 101 | TI 121 | None |
| te-L3-trace-r2 | codex | 101 | PI 107 | None |
| te-L3-trace-r2 | codex | 101 | LI 108 | None |
| te-L3-trace-r2 | codex | 101 | TI 109 | None |
| te-L3-trace-r2 | codex | 101 | SC 212 | None |
| te-L3-trace-r2 | codex | 102 | FI 105 | None |
| te-L3-trace-r2 | codex | 102 | FI 110 | None |
| te-L3-trace-r2 | codex | 102 | AI 129 | None |
| te-L3-trace-r2 | codex | 102 | FV 206 | None |
| te-L3-trace-r2 | codex | 102 | HV 205 | None |
| te-L3-trace-r2 | codex | 102 | FI 114 | None |
| te-L3-trace-r2 | codex | 102 | LV 207 | None |
| te-L3-trace-r2 | codex | 102 | TV 211 | None |
| te-L3-trace-r2 | codex | 102 | TI 122 | None |
| te-L3-trace-r2 | codex | 102 | TI 111 | None |
| te-L3-trace-r2 | codex | 102 | LI 112 | None |
| te-L3-trace-r2 | codex | 102 | PI 113 | None |
| te-L3-trace-r2 | codex | 102 | JI 120 | None |
| te-L3-trace-r2 | codex | 103 | FV 204 | None |
| te-L3-trace-r2 | codex | 103 | FI 104 | None |
| te-L3-trace-r2 | codex | 103 | FI 117 | None |
| te-L3-trace-r2 | codex | 103 | AI 137 | None |
| te-L3-trace-r2 | codex | 103 | LV 208 | None |
| te-L3-trace-r2 | codex | 103 | FV 209 | None |
| te-L3-trace-r2 | codex | 103 | FI 119 | None |
| te-L3-trace-r2 | codex | 103 | PI 116 | None |
| te-L3-trace-r2 | codex | 103 | TI 118 | None |
| te-L3-trace-r2 | codex | 103 | LI 115 | None |
| te-L3-trace-r3 | codex | 101 | FV 203 | None |
| te-L3-trace-r3 | codex | 101 | FI 101 | None |
| te-L3-trace-r3 | codex | 101 | FV 201 | None |
| te-L3-trace-r3 | codex | 101 | FI 102 | None |
| te-L3-trace-r3 | codex | 101 | FV 202 | None |
| te-L3-trace-r3 | codex | 101 | FI 103 | None |
| te-L3-trace-r3 | codex | 101 | FI 106 | None |
| te-L3-trace-r3 | codex | 101 | AI 123 | None |
| te-L3-trace-r3 | codex | 101 | TV 210 | None |
| te-L3-trace-r3 | codex | 101 | TI 121 | None |
| te-L3-trace-r3 | codex | 101 | PI 107 | None |
| te-L3-trace-r3 | codex | 101 | LI 108 | None |
| te-L3-trace-r3 | codex | 101 | TI 109 | None |
| te-L3-trace-r3 | codex | 101 | SC 212 | None |
| te-L3-trace-r3 | codex | 102 | FI 105 | None |
| te-L3-trace-r3 | codex | 102 | FI 110 | None |
| te-L3-trace-r3 | codex | 102 | AI 129 | None |
| te-L3-trace-r3 | codex | 102 | FV 206 | None |
| te-L3-trace-r3 | codex | 102 | HV 205 | None |
| te-L3-trace-r3 | codex | 102 | FI 114 | None |
| te-L3-trace-r3 | codex | 102 | LV 207 | None |
| te-L3-trace-r3 | codex | 102 | TV 211 | None |
| te-L3-trace-r3 | codex | 102 | TI 122 | None |
| te-L3-trace-r3 | codex | 102 | TI 111 | None |
| te-L3-trace-r3 | codex | 102 | LI 112 | None |
| te-L3-trace-r3 | codex | 102 | PI 113 | None |
| te-L3-trace-r3 | codex | 102 | JI 120 | None |
| te-L3-trace-r3 | codex | 103 | FV 204 | None |
| te-L3-trace-r3 | codex | 103 | FI 104 | None |
| te-L3-trace-r3 | codex | 103 | FI 117 | None |
| te-L3-trace-r3 | codex | 103 | AI 137 | None |
| te-L3-trace-r3 | codex | 103 | LV 208 | None |
| te-L3-trace-r3 | codex | 103 | FV 209 | None |
| te-L3-trace-r3 | codex | 103 | FI 119 | None |
| te-L3-trace-r3 | codex | 103 | PI 116 | None |
| te-L3-trace-r3 | codex | 103 | TI 118 | None |
| te-L3-trace-r3 | codex | 103 | LI 115 | None |
| te-L3-trace-r1 | claude | 101 | FV 203 | 'FV 201' **(another real tag)** |
| te-L3-trace-r1 | claude | 101 | FV 201 | 'FV 202' **(another real tag)** |
| te-L3-trace-r1 | claude | 101 | FV 202 | 'FV 203' **(another real tag)** |
| te-L3-trace-r1 | claude | 101 | FI 106 | 'TI' |
| te-L3-trace-r1 | claude | 101 | AI 123 | 'AI' |
| te-L3-trace-r1 | claude | 101 | TV 210 | 'TV' |
| te-L3-trace-r1 | claude | 101 | TI 121 | None |
| te-L3-trace-r1 | claude | 101 | TI 109 | 'TI 106' |
| te-L3-trace-r1 | claude | 101 | SC 212 | 'SIC 212' |
| te-L3-trace-r1 | claude | 102 | AI 129 | 'AI 120' |
| te-L3-trace-r1 | claude | 102 | FV 206 | 'FX 206' |
| te-L3-trace-r1 | claude | 102 | FI 114 | 'TI 114' |
| te-L3-trace-r1 | claude | 102 | LV 207 | 'LC 101' |
| te-L3-trace-r1 | claude | 102 | TI 122 | 'TI 123' |
| te-L3-trace-r1 | claude | 102 | TI 111 | None |
| te-L3-trace-r1 | claude | 103 | FV 204 | 'PV 204' |
| te-L3-trace-r1 | claude | 103 | FI 104 | 'FT 204' |
| te-L3-trace-r1 | claude | 103 | FI 117 | 'PT' |
| te-L3-trace-r1 | claude | 103 | AI 137 | 'AI' |
| te-L3-trace-r1 | claude | 103 | LV 208 | None |
| te-L3-trace-r1 | claude | 103 | FV 209 | 'PV 205' |
| te-L3-trace-r1 | claude | 103 | FI 119 | 'FI 115' |
| te-L3-trace-r1 | claude | 103 | TI 118 | 'TI 116' |
| te-L3-trace-r1 | claude | 103 | LI 115 | 'LI 116' |
| te-L3-trace-r2 | claude | 101 | FV 202 | 'FC-202' |
| te-L3-trace-r2 | claude | 101 | FI 106 | 'TI 100' |
| te-L3-trace-r2 | claude | 101 | AI 123 | 'AI 100' |
| te-L3-trace-r2 | claude | 101 | TV 210 | 'TC 210' |
| te-L3-trace-r2 | claude | 101 | TI 121 | None |
| te-L3-trace-r2 | claude | 101 | SC 212 | 'SIC 212' |
| te-L3-trace-r2 | claude | 102 | AI 129 | 'AI 120' |
| te-L3-trace-r2 | claude | 102 | FI 114 | 'TI 114' |
| te-L3-trace-r2 | claude | 102 | LV 207 | 'LC 103' |
| te-L3-trace-r2 | claude | 102 | TI 122 | 'TI 123' |
| te-L3-trace-r2 | claude | 102 | TI 111 | None |
| te-L3-trace-r2 | claude | 103 | FV 204 | 'PV 204' |
| te-L3-trace-r2 | claude | 103 | FI 104 | 'FT' |
| te-L3-trace-r2 | claude | 103 | FI 117 | 'PI 131' |
| te-L3-trace-r2 | claude | 103 | AI 137 | 'AI 131' |
| te-L3-trace-r2 | claude | 103 | LV 208 | None |
| te-L3-trace-r2 | claude | 103 | FV 209 | 'PV 205' |
| te-L3-trace-r2 | claude | 103 | FI 119 | 'FI 118' |
| te-L3-trace-r2 | claude | 103 | PI 116 | 'PI 110' |
| te-L3-trace-r2 | claude | 103 | TI 118 | 'TI 110' |
| te-L3-trace-r2 | claude | 103 | LI 115 | 'LI 110' |
| te-L3-trace-r3 | claude | 101 | FI 106 | 'TI' |
| te-L3-trace-r3 | claude | 101 | AI 123 | 'AI' |
| te-L3-trace-r3 | claude | 101 | TV 210 | 'TV' |
| te-L3-trace-r3 | claude | 101 | TI 121 | None |
| te-L3-trace-r3 | claude | 101 | TI 109 | 'TI 106' |
| te-L3-trace-r3 | claude | 101 | SC 212 | 'SIC 212' |
| te-L3-trace-r3 | claude | 102 | AI 129 | 'AI 120' |
| te-L3-trace-r3 | claude | 102 | FV 206 | 'FX 205' |
| te-L3-trace-r3 | claude | 102 | FI 114 | 'TI 114' |
| te-L3-trace-r3 | claude | 102 | LV 207 | 'LC 101' |
| te-L3-trace-r3 | claude | 102 | TI 122 | 'TI 121' **(another real tag)** |
| te-L3-trace-r3 | claude | 102 | TI 111 | None |
| te-L3-trace-r3 | claude | 103 | FV 204 | 'PV 204' |
| te-L3-trace-r3 | claude | 103 | FI 104 | 'FT' |
| te-L3-trace-r3 | claude | 103 | FI 117 | 'PI 133' |
| te-L3-trace-r3 | claude | 103 | AI 137 | 'AI 131' |
| te-L3-trace-r3 | claude | 103 | LV 208 | None |
| te-L3-trace-r3 | claude | 103 | FV 209 | 'PV 200' |
| te-L3-trace-r3 | claude | 103 | FI 119 | 'FI 116' |
| te-L3-trace-r3 | claude | 103 | TI 118 | 'TI 116' |
| te-L3-trace-r3 | claude | 103 | LI 115 | 'LI 116' |
