# Round trip on the generated Tennessee Eastman sheets

Sheets and keys: `data/te_pid/rev-c`; runs `tec-*`.

**A round trip, not real-plant accuracy.** The three sheets were generated from the verified TE model and the answer keys come from the same model, so these numbers measure how faithfully the frozen method (2×2 tiles, prompt v2, code line tracer; nothing re-tuned) reads clean drawings in the learned house style. They are an upper bound and are not comparable with the OPEN100 results.

Mean over replicates, with the min–max range in brackets. 95% t-intervals are in the JSON.

| Image | Tool | Runs | Review load /100 (lower is better) | Symbols found F1 | Class F1 | Connections F1 | Tags read exactly | Tags read, if found | Off-page refs read | Misreads that are another real tag |
|---|---|---|---|---|---|---|---|---|---|---|
| clean | codex | 5 | 1.26 (1.20–1.50) | 0.99 (0.99–1.00) | 0.99 (0.99–1.00) | 0.99 (0.99–0.99) | 100% (100%–100%) | 100% (100%–100%) | 100% (100%–100%) | 0.00 (0.00–0.00) |
| clean | claude | 5 | 1.38 (1.20–1.8) | 0.99 (0.99–1.00) | 0.99 (0.99–1.00) | 0.99 (0.99–0.99) | 100% (100%–100%) | 100% (100%–100%) | 100% (100%–100%) | 0.00 (0.00–0.00) |
| L1 | codex | 3 | 1.30 (1.20–1.50) | 0.99 (0.99–1.00) | 0.99 (0.99–1.00) | 0.99 (0.99–0.99) | 100% (100%–100%) | 100% (100%–100%) | 93% (89%–94%) | 0.00 (0.00–0.00) |
| L1 | claude | 3 | 4.1 (1.50–5.4) | 0.99 (0.99–1.00) | 0.99 (0.99–1.00) | 0.97 (0.96–0.99) | 100% (100%–100%) | 100% (100%–100%) | 100% (100%–100%) | 0.00 (0.00–0.00) |
| L2 | codex | 3 | 1.20 (1.20–1.20) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) | 0.99 (0.99–0.99) | 61% (56%–66%) | 61% (56%–66%) | 0% (0%–0%) | 0.67 (0.00–2.0) |
| L2 | claude | 3 | 10.0 (9.9–10.1) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) | 0.93 (0.93–0.93) | 89% (84%–92%) | 89% (84%–92%) | 91% (89%–94%) | 0.00 (0.00–0.00) |
| L3 | codex | 3 | 14.9 (13.4–17.9) | 0.98 (0.98–0.99) | 0.98 (0.96–0.99) | 0.88 (0.86–0.89) | 9% (8%–10%) | 9% (8%–10%) | 0% (0%–0%) | 0.00 (0.00–0.00) |
| L3 | claude | 3 | 15.7 (13.4–17.0) | 0.98 (0.98–0.99) | 0.98 (0.98–0.98) | 0.87 (0.86–0.90) | 50% (45%–52%) | 50% (45%–52%) | 0% (0%–0%) | 0.33 (0.00–1.00) |

## What produced these numbers

Every sheet's {model, prompt, adapter, date, seconds, cost} is in `roundtrip_scores_revC.json` (`runs[].records`). Claude dollars are the CLI's API-equivalent figure (the runs used a flat subscription); Codex reports no cost. No Gemini call was made.

| Tool | Models | Prompt | Sheet runs | Failed tiles | Wall s (sum) | Serial s (sum) | Claude API-equivalent $ |
|---|---|---|---|---|---|---|---|
| codex | gpt-6.1-sol | extraction/prompt_v2.md | 42 | 0 | 1414 | 4207 | not reported |
| claude | claude-opus-5-5 | extraction/prompt_v2.md | 42 | 0 | 2432 | 8072 | 19.66 |

## Every tag that was not read exactly

| Run | Tool | Sheet | Printed | Extracted |
|---|---|---|---|---|
| tec-L2-trace-r1 | codex | 101 | AI 123 | 'AI 103' |
| tec-L2-trace-r1 | codex | 101 | LI 108 | 'LT 100' |
| tec-L2-trace-r1 | codex | 101 | TI 109 | 'TT 100' |
| tec-L2-trace-r1 | codex | 101 | SC 212 | 'SC 121' |
| tec-L2-trace-r1 | codex | 101 | AIC 123A | None |
| tec-L2-trace-r1 | codex | 101 | AIC 123D | None |
| tec-L2-trace-r1 | codex | 101 | AIC 123E | None |
| tec-L2-trace-r1 | codex | 101 | LIC 108 | 'LIC 100' |
| tec-L2-trace-r1 | codex | 101 | TIC 109 | 'TIC 100' |
| tec-L2-trace-r1 | codex | 101 | TIC 121 | None |
| tec-L2-trace-r1 | codex | 102 | FI 105 | 'PI 105' |
| tec-L2-trace-r1 | codex | 102 | AI 129 | 'AI 109' |
| tec-L2-trace-r1 | codex | 102 | FV 105 | 'PV 105' |
| tec-L2-trace-r1 | codex | 102 | FI 114 | 'PI 114' |
| tec-L2-trace-r1 | codex | 102 | FV 117 | 'FY 117' |
| tec-L2-trace-r1 | codex | 102 | JI 120 | 'I 120' |
| tec-L2-trace-r1 | codex | 102 | FIC 105 | 'PIC 105' |
| tec-L2-trace-r1 | codex | 102 | AIC 129 | 'AIC 109' |
| tec-L2-trace-r1 | codex | 103 | FI 117 | 'AT 132' |
| tec-L2-trace-r1 | codex | 103 | LV 115 | 'LV 116' |
| tec-L2-trace-r1 | codex | 103 | FIC 117 | 'PIC 113' |
| tec-L2-trace-r2 | codex | 101 | FI 106 | 'PI 106' |
| tec-L2-trace-r2 | codex | 101 | AI 123 | 'AI 102' |
| tec-L2-trace-r2 | codex | 101 | LI 108 | 'LT 100' |
| tec-L2-trace-r2 | codex | 101 | TI 109 | 'TT 100' |
| tec-L2-trace-r2 | codex | 101 | SC 212 | 'SC 121' |
| tec-L2-trace-r2 | codex | 101 | AIC 123A | None |
| tec-L2-trace-r2 | codex | 101 | AIC 123D | None |
| tec-L2-trace-r2 | codex | 101 | AIC 123E | None |
| tec-L2-trace-r2 | codex | 101 | LIC 108 | 'LIC 100' |
| tec-L2-trace-r2 | codex | 101 | TIC 109 | 'TIC 100' |
| tec-L2-trace-r2 | codex | 102 | FI 105 | 'PI\n105' |
| tec-L2-trace-r2 | codex | 102 | AI 129 | 'AI\n109' |
| tec-L2-trace-r2 | codex | 102 | FV 105 | 'PV\n105' |
| tec-L2-trace-r2 | codex | 102 | FI 114 | 'PI 114' |
| tec-L2-trace-r2 | codex | 102 | FV 117 | 'FY 117' |
| tec-L2-trace-r2 | codex | 102 | JI 120 | 'SI\n120' |
| tec-L2-trace-r2 | codex | 102 | FIC 105 | 'PIC\n105' |
| tec-L2-trace-r2 | codex | 102 | AIC 129 | 'AIC\n109' |
| tec-L2-trace-r2 | codex | 103 | FV 104 | 'PV 104' |
| tec-L2-trace-r2 | codex | 103 | FI 104 | 'PI 104' |
| tec-L2-trace-r2 | codex | 103 | FI 117 | 'PI 113' **(another real tag)** |
| tec-L2-trace-r2 | codex | 103 | LV 115 | 'LV 118' |
| tec-L2-trace-r2 | codex | 103 | FV 119 | 'PV 110' |
| tec-L2-trace-r2 | codex | 103 | FI 119 | 'TI 110' |
| tec-L2-trace-r2 | codex | 103 | FIC 104 | 'FC\n104' |
| tec-L2-trace-r2 | codex | 103 | FIC 119 | 'FIC 110' **(another real tag)** |
| tec-L2-trace-r2 | codex | 103 | FIC 117 | 'PIC 113' |
| tec-L2-trace-r3 | codex | 101 | AI 123 | 'AI 113' |
| tec-L2-trace-r3 | codex | 101 | LI 108 | 'LE 108' |
| tec-L2-trace-r3 | codex | 101 | TI 109 | 'TI 100' |
| tec-L2-trace-r3 | codex | 101 | SC 212 | 'SC 721' |
| tec-L2-trace-r3 | codex | 101 | AIC 123A | None |
| tec-L2-trace-r3 | codex | 101 | AIC 123D | None |
| tec-L2-trace-r3 | codex | 101 | AIC 123E | None |
| tec-L2-trace-r3 | codex | 101 | LIC 108 | 'LIC 100' |
| tec-L2-trace-r3 | codex | 101 | TIC 109 | 'TIC 100' |
| tec-L2-trace-r3 | codex | 102 | FI 105 | 'PI 105' |
| tec-L2-trace-r3 | codex | 102 | AI 129 | 'AI 109' |
| tec-L2-trace-r3 | codex | 102 | FV 105 | 'PV 105' |
| tec-L2-trace-r3 | codex | 102 | FI 114 | 'PI 114' |
| tec-L2-trace-r3 | codex | 102 | FV 117 | 'TY 117' |
| tec-L2-trace-r3 | codex | 102 | JI 120 | 'SI 120' |
| tec-L2-trace-r3 | codex | 102 | FIC 105 | 'PIC 105' |
| tec-L2-trace-r3 | codex | 102 | AIC 129 | 'AIC 109' |
| tec-L2-trace-r3 | codex | 103 | FI 104 | 'PI\n104' |
| tec-L2-trace-r3 | codex | 103 | FI 117 | 'PT\n113' |
| tec-L2-trace-r3 | codex | 103 | LV 115 | 'LV\n116' |
| tec-L2-trace-r3 | codex | 103 | FV 119 | 'PV\n110' |
| tec-L2-trace-r3 | codex | 103 | FI 119 | 'PI\n110' |
| tec-L2-trace-r3 | codex | 103 | FIC 119 | 'PIC\n110' |
| tec-L2-trace-r3 | codex | 103 | TIC 118 | 'TIC\n119' |
| tec-L2-trace-r3 | codex | 103 | FIC 117 | 'AIC\n112' |
| tec-L2-trace-r1 | claude | 101 | TI 109 | 'TI 108' |
| tec-L2-trace-r1 | claude | 101 | TIC 109 | 'TIC 108' |
| tec-L2-trace-r1 | claude | 102 | AI 129 | 'AI 120' |
| tec-L2-trace-r1 | claude | 102 | AIC 129 | 'AIC 120' |
| tec-L2-trace-r1 | claude | 103 | TIC 118 | 'TIC 116' |
| tec-L2-trace-r2 | claude | 101 | TI 109 | 'TI 108' |
| tec-L2-trace-r2 | claude | 101 | AIC 123D | 'AIC 123B' |
| tec-L2-trace-r2 | claude | 101 | AIC 123E | 'AIC 123C' |
| tec-L2-trace-r2 | claude | 101 | TIC 109 | 'TIC 108' |
| tec-L2-trace-r2 | claude | 102 | AI 129 | 'AI 120' |
| tec-L2-trace-r2 | claude | 102 | AIC 129 | 'AIC 120' |
| tec-L2-trace-r2 | claude | 103 | FV 119 | 'FV 118' |
| tec-L2-trace-r2 | claude | 103 | FI 119 | 'FI 118' |
| tec-L2-trace-r2 | claude | 103 | FIC 119 | 'FIC 118' |
| tec-L2-trace-r2 | claude | 103 | TIC 118 | 'TIC 116' |
| tec-L2-trace-r3 | claude | 101 | TI 109 | 'TI 108' |
| tec-L2-trace-r3 | claude | 101 | TIC 109 | 'TIC 108' |
| tec-L2-trace-r3 | claude | 102 | AI 129 | 'AI 120' |
| tec-L2-trace-r3 | claude | 102 | AIC 129 | 'AIC 120' |
| tec-L2-trace-r3 | claude | 103 | TI 118 | 'TI 116' |
| tec-L2-trace-r3 | claude | 103 | TIC 118 | 'TIC 116' |
| tec-L3-trace-r1 | codex | 101 | FV 101 | None |
| tec-L3-trace-r1 | codex | 101 | FI 101 | None |
| tec-L3-trace-r1 | codex | 101 | FV 102 | None |
| tec-L3-trace-r1 | codex | 101 | FI 102 | None |
| tec-L3-trace-r1 | codex | 101 | FV 103 | None |
| tec-L3-trace-r1 | codex | 101 | FI 103 | None |
| tec-L3-trace-r1 | codex | 101 | FI 106 | None |
| tec-L3-trace-r1 | codex | 101 | AI 123 | None |
| tec-L3-trace-r1 | codex | 101 | TV 121 | None |
| tec-L3-trace-r1 | codex | 101 | TI 121 | None |
| tec-L3-trace-r1 | codex | 101 | PI 107 | None |
| tec-L3-trace-r1 | codex | 101 | LI 108 | None |
| tec-L3-trace-r1 | codex | 101 | TI 109 | None |
| tec-L3-trace-r1 | codex | 101 | SC 212 | None |
| tec-L3-trace-r1 | codex | 101 | FIC 101 | None |
| tec-L3-trace-r1 | codex | 101 | FIC 102 | None |
| tec-L3-trace-r1 | codex | 101 | FIC 103 | None |
| tec-L3-trace-r1 | codex | 101 | AIC 123A | None |
| tec-L3-trace-r1 | codex | 101 | AIC 123D | None |
| tec-L3-trace-r1 | codex | 101 | AIC 123E | None |
| tec-L3-trace-r1 | codex | 101 | LIC 108 | None |
| tec-L3-trace-r1 | codex | 101 | TIC 109 | None |
| tec-L3-trace-r1 | codex | 101 | TIC 121 | None |
| tec-L3-trace-r1 | codex | 102 | FI 105 | None |
| tec-L3-trace-r1 | codex | 102 | FI 110 | None |
| tec-L3-trace-r1 | codex | 102 | AI 129 | None |
| tec-L3-trace-r1 | codex | 102 | FV 110 | None |
| tec-L3-trace-r1 | codex | 102 | FV 105 | None |
| tec-L3-trace-r1 | codex | 102 | FI 114 | None |
| tec-L3-trace-r1 | codex | 102 | LV 112 | None |
| tec-L3-trace-r1 | codex | 102 | FV 117 | None |
| tec-L3-trace-r1 | codex | 102 | TI 122 | None |
| tec-L3-trace-r1 | codex | 102 | TI 111 | None |
| tec-L3-trace-r1 | codex | 102 | LI 112 | None |
| tec-L3-trace-r1 | codex | 102 | PI 113 | None |
| tec-L3-trace-r1 | codex | 102 | JI 120 | None |
| tec-L3-trace-r1 | codex | 102 | FIC 105 | None |
| tec-L3-trace-r1 | codex | 102 | FIC 110 | None |
| tec-L3-trace-r1 | codex | 102 | AIC 129 | None |
| tec-L3-trace-r1 | codex | 102 | LIC 112 | None |
| tec-L3-trace-r1 | codex | 103 | FV 104 | None |
| tec-L3-trace-r1 | codex | 103 | FI 104 | None |
| tec-L3-trace-r1 | codex | 103 | FI 117 | None |
| tec-L3-trace-r1 | codex | 103 | AI 137 | None |
| tec-L3-trace-r1 | codex | 103 | LV 115 | None |
| tec-L3-trace-r1 | codex | 103 | FV 119 | None |
| tec-L3-trace-r1 | codex | 103 | FI 119 | None |
| tec-L3-trace-r1 | codex | 103 | PI 116 | None |
| tec-L3-trace-r1 | codex | 103 | TI 118 | None |
| tec-L3-trace-r1 | codex | 103 | LI 115 | None |
| tec-L3-trace-r1 | codex | 103 | FIC 104 | None |
| tec-L3-trace-r1 | codex | 103 | FIC 119 | None |
| tec-L3-trace-r1 | codex | 103 | TIC 118 | None |
| tec-L3-trace-r1 | codex | 103 | LIC 115 | None |
| tec-L3-trace-r1 | codex | 103 | AIC 137 | None |
| tec-L3-trace-r1 | codex | 103 | FIC 117 | None |
| tec-L3-trace-r2 | codex | 101 | FV 101 | None |
| tec-L3-trace-r2 | codex | 101 | FI 101 | None |
| tec-L3-trace-r2 | codex | 101 | FV 102 | None |
| tec-L3-trace-r2 | codex | 101 | FI 102 | None |
| tec-L3-trace-r2 | codex | 101 | FV 103 | None |
| tec-L3-trace-r2 | codex | 101 | FI 103 | None |
| tec-L3-trace-r2 | codex | 101 | FI 106 | None |
| tec-L3-trace-r2 | codex | 101 | AI 123 | None |
| tec-L3-trace-r2 | codex | 101 | TV 121 | None |
| tec-L3-trace-r2 | codex | 101 | TI 121 | None |
| tec-L3-trace-r2 | codex | 101 | PI 107 | None |
| tec-L3-trace-r2 | codex | 101 | LI 108 | None |
| tec-L3-trace-r2 | codex | 101 | TI 109 | None |
| tec-L3-trace-r2 | codex | 101 | SC 212 | None |
| tec-L3-trace-r2 | codex | 101 | FIC 101 | None |
| tec-L3-trace-r2 | codex | 101 | FIC 102 | None |
| tec-L3-trace-r2 | codex | 101 | FIC 103 | None |
| tec-L3-trace-r2 | codex | 101 | AIC 123A | None |
| tec-L3-trace-r2 | codex | 101 | AIC 123D | None |
| tec-L3-trace-r2 | codex | 101 | AIC 123E | None |
| tec-L3-trace-r2 | codex | 101 | LIC 108 | None |
| tec-L3-trace-r2 | codex | 101 | TIC 109 | None |
| tec-L3-trace-r2 | codex | 101 | TIC 121 | None |
| tec-L3-trace-r2 | codex | 102 | K-101 | None |
| tec-L3-trace-r2 | codex | 102 | FI 105 | None |
| tec-L3-trace-r2 | codex | 102 | FI 110 | None |
| tec-L3-trace-r2 | codex | 102 | AI 129 | None |
| tec-L3-trace-r2 | codex | 102 | FV 110 | None |
| tec-L3-trace-r2 | codex | 102 | FV 105 | None |
| tec-L3-trace-r2 | codex | 102 | FI 114 | None |
| tec-L3-trace-r2 | codex | 102 | LV 112 | None |
| tec-L3-trace-r2 | codex | 102 | FV 117 | None |
| tec-L3-trace-r2 | codex | 102 | TI 122 | None |
| tec-L3-trace-r2 | codex | 102 | TI 111 | None |
| tec-L3-trace-r2 | codex | 102 | LI 112 | None |
| tec-L3-trace-r2 | codex | 102 | PI 113 | None |
| tec-L3-trace-r2 | codex | 102 | JI 120 | None |
| tec-L3-trace-r2 | codex | 102 | FIC 105 | None |
| tec-L3-trace-r2 | codex | 102 | FIC 110 | None |
| tec-L3-trace-r2 | codex | 102 | AIC 129 | None |
| tec-L3-trace-r2 | codex | 102 | LIC 112 | None |
| tec-L3-trace-r2 | codex | 103 | FV 104 | None |
| tec-L3-trace-r2 | codex | 103 | FI 104 | None |
| tec-L3-trace-r2 | codex | 103 | FI 117 | None |
| tec-L3-trace-r2 | codex | 103 | AI 137 | None |
| tec-L3-trace-r2 | codex | 103 | LV 115 | None |
| tec-L3-trace-r2 | codex | 103 | FV 119 | None |
| tec-L3-trace-r2 | codex | 103 | FI 119 | None |
| tec-L3-trace-r2 | codex | 103 | PI 116 | None |
| tec-L3-trace-r2 | codex | 103 | TI 118 | None |
| tec-L3-trace-r2 | codex | 103 | LI 115 | None |
| tec-L3-trace-r2 | codex | 103 | FIC 104 | None |
| tec-L3-trace-r2 | codex | 103 | FIC 119 | None |
| tec-L3-trace-r2 | codex | 103 | TIC 118 | None |
| tec-L3-trace-r2 | codex | 103 | LIC 115 | None |
| tec-L3-trace-r2 | codex | 103 | AIC 137 | None |
| tec-L3-trace-r2 | codex | 103 | FIC 117 | None |
| tec-L3-trace-r3 | codex | 101 | FV 101 | None |
| tec-L3-trace-r3 | codex | 101 | FI 101 | None |
| tec-L3-trace-r3 | codex | 101 | FV 102 | None |
| tec-L3-trace-r3 | codex | 101 | FI 102 | None |
| tec-L3-trace-r3 | codex | 101 | FV 103 | None |
| tec-L3-trace-r3 | codex | 101 | FI 103 | None |
| tec-L3-trace-r3 | codex | 101 | FI 106 | None |
| tec-L3-trace-r3 | codex | 101 | AI 123 | None |
| tec-L3-trace-r3 | codex | 101 | TV 121 | None |
| tec-L3-trace-r3 | codex | 101 | TI 121 | None |
| tec-L3-trace-r3 | codex | 101 | PI 107 | None |
| tec-L3-trace-r3 | codex | 101 | LI 108 | None |
| tec-L3-trace-r3 | codex | 101 | TI 109 | None |
| tec-L3-trace-r3 | codex | 101 | SC 212 | None |
| tec-L3-trace-r3 | codex | 101 | FIC 101 | None |
| tec-L3-trace-r3 | codex | 101 | FIC 102 | None |
| tec-L3-trace-r3 | codex | 101 | FIC 103 | None |
| tec-L3-trace-r3 | codex | 101 | AIC 123A | None |
| tec-L3-trace-r3 | codex | 101 | AIC 123D | None |
| tec-L3-trace-r3 | codex | 101 | AIC 123E | None |
| tec-L3-trace-r3 | codex | 101 | LIC 108 | None |
| tec-L3-trace-r3 | codex | 101 | TIC 109 | None |
| tec-L3-trace-r3 | codex | 101 | TIC 121 | None |
| tec-L3-trace-r3 | codex | 102 | FI 105 | None |
| tec-L3-trace-r3 | codex | 102 | FI 110 | None |
| tec-L3-trace-r3 | codex | 102 | AI 129 | None |
| tec-L3-trace-r3 | codex | 102 | FV 110 | None |
| tec-L3-trace-r3 | codex | 102 | FV 105 | None |
| tec-L3-trace-r3 | codex | 102 | FI 114 | None |
| tec-L3-trace-r3 | codex | 102 | LV 112 | None |
| tec-L3-trace-r3 | codex | 102 | FV 117 | None |
| tec-L3-trace-r3 | codex | 102 | TI 122 | None |
| tec-L3-trace-r3 | codex | 102 | TI 111 | None |
| tec-L3-trace-r3 | codex | 102 | LI 112 | None |
| tec-L3-trace-r3 | codex | 102 | PI 113 | None |
| tec-L3-trace-r3 | codex | 102 | JI 120 | None |
| tec-L3-trace-r3 | codex | 102 | FIC 105 | None |
| tec-L3-trace-r3 | codex | 102 | FIC 110 | None |
| tec-L3-trace-r3 | codex | 102 | AIC 129 | None |
| tec-L3-trace-r3 | codex | 102 | LIC 112 | None |
| tec-L3-trace-r3 | codex | 103 | FV 104 | None |
| tec-L3-trace-r3 | codex | 103 | FI 104 | None |
| tec-L3-trace-r3 | codex | 103 | FI 117 | None |
| tec-L3-trace-r3 | codex | 103 | AI 137 | None |
| tec-L3-trace-r3 | codex | 103 | LV 115 | None |
| tec-L3-trace-r3 | codex | 103 | FV 119 | None |
| tec-L3-trace-r3 | codex | 103 | FI 119 | None |
| tec-L3-trace-r3 | codex | 103 | PI 116 | None |
| tec-L3-trace-r3 | codex | 103 | TI 118 | None |
| tec-L3-trace-r3 | codex | 103 | LI 115 | None |
| tec-L3-trace-r3 | codex | 103 | FIC 104 | None |
| tec-L3-trace-r3 | codex | 103 | FIC 119 | None |
| tec-L3-trace-r3 | codex | 103 | TIC 118 | None |
| tec-L3-trace-r3 | codex | 103 | LIC 115 | None |
| tec-L3-trace-r3 | codex | 103 | AIC 137 | None |
| tec-L3-trace-r3 | codex | 103 | FIC 117 | None |
| tec-L3-trace-r1 | claude | 101 | FI 106 | 'TI 100' |
| tec-L3-trace-r1 | claude | 101 | AI 123 | 'AI 120' |
| tec-L3-trace-r1 | claude | 101 | TI 121 | 'TT 111' |
| tec-L3-trace-r1 | claude | 101 | AIC 123A | 'AIC' |
| tec-L3-trace-r1 | claude | 101 | AIC 123D | 'AIC' |
| tec-L3-trace-r1 | claude | 101 | AIC 123E | 'AIC' |
| tec-L3-trace-r1 | claude | 101 | TIC 121 | 'TIC 111' |
| tec-L3-trace-r1 | claude | 102 | FI 110 | 'FT 110' |
| tec-L3-trace-r1 | claude | 102 | AI 129 | 'AT 120' |
| tec-L3-trace-r1 | claude | 102 | FI 114 | 'TI 114' |
| tec-L3-trace-r1 | claude | 102 | TI 122 | 'TI 123' |
| tec-L3-trace-r1 | claude | 102 | TI 111 | None |
| tec-L3-trace-r1 | claude | 102 | LI 112 | 'LT 112' |
| tec-L3-trace-r1 | claude | 102 | FIC 105 | 'FC 105' |
| tec-L3-trace-r1 | claude | 102 | AIC 129 | 'AIC 120' |
| tec-L3-trace-r1 | claude | 102 | LIC 112 | 'LC 112' |
| tec-L3-trace-r1 | claude | 103 | FV 104 | 'PV 104' |
| tec-L3-trace-r1 | claude | 103 | FI 104 | 'FT 104' |
| tec-L3-trace-r1 | claude | 103 | FI 117 | 'FT 113' |
| tec-L3-trace-r1 | claude | 103 | AI 137 | None |
| tec-L3-trace-r1 | claude | 103 | LV 115 | None |
| tec-L3-trace-r1 | claude | 103 | FV 119 | 'PV 116' |
| tec-L3-trace-r1 | claude | 103 | FI 119 | 'FI 116' |
| tec-L3-trace-r1 | claude | 103 | TI 118 | 'TI 116' |
| tec-L3-trace-r1 | claude | 103 | LI 115 | 'LI 116' |
| tec-L3-trace-r1 | claude | 103 | FIC 119 | 'FC 116' |
| tec-L3-trace-r1 | claude | 103 | TIC 118 | 'TIC 116' |
| tec-L3-trace-r1 | claude | 103 | LIC 115 | 'LIC 116' |
| tec-L3-trace-r1 | claude | 103 | AIC 137 | None |
| tec-L3-trace-r1 | claude | 103 | FIC 117 | 'FC 117' |
| tec-L3-trace-r2 | claude | 101 | FI 106 | 'TI 100' |
| tec-L3-trace-r2 | claude | 101 | AI 123 | 'AI 100' |
| tec-L3-trace-r2 | claude | 101 | TV 121 | 'TV 101' |
| tec-L3-trace-r2 | claude | 101 | TI 121 | 'TT 121' |
| tec-L3-trace-r2 | claude | 101 | AIC 123A | None |
| tec-L3-trace-r2 | claude | 101 | AIC 123D | None |
| tec-L3-trace-r2 | claude | 101 | AIC 123E | None |
| tec-L3-trace-r2 | claude | 102 | FI 110 | 'FT 110' |
| tec-L3-trace-r2 | claude | 102 | AI 129 | 'AT 120' |
| tec-L3-trace-r2 | claude | 102 | FI 114 | 'TI 114' |
| tec-L3-trace-r2 | claude | 102 | TI 122 | 'TI-123' |
| tec-L3-trace-r2 | claude | 102 | TI 111 | None |
| tec-L3-trace-r2 | claude | 102 | LI 112 | 'LT 112' |
| tec-L3-trace-r2 | claude | 102 | AIC 129 | 'AIC 120' |
| tec-L3-trace-r2 | claude | 102 | LIC 112 | 'LC 112' |
| tec-L3-trace-r2 | claude | 103 | FV 104 | 'PV 104' |
| tec-L3-trace-r2 | claude | 103 | FI 104 | None |
| tec-L3-trace-r2 | claude | 103 | FI 117 | 'FT 117' |
| tec-L3-trace-r2 | claude | 103 | AI 137 | None |
| tec-L3-trace-r2 | claude | 103 | LV 115 | 'FV 117' **(another real tag)** |
| tec-L3-trace-r2 | claude | 103 | FV 119 | 'PV 116' |
| tec-L3-trace-r2 | claude | 103 | FI 119 | 'FI 116' |
| tec-L3-trace-r2 | claude | 103 | TI 118 | 'TI 116' |
| tec-L3-trace-r2 | claude | 103 | LI 115 | 'LI 116' |
| tec-L3-trace-r2 | claude | 103 | FIC 104 | None |
| tec-L3-trace-r2 | claude | 103 | FIC 119 | 'FC 116' |
| tec-L3-trace-r2 | claude | 103 | TIC 118 | 'TIC 116' |
| tec-L3-trace-r2 | claude | 103 | LIC 115 | 'LIC 116' |
| tec-L3-trace-r2 | claude | 103 | AIC 137 | None |
| tec-L3-trace-r2 | claude | 103 | FIC 117 | 'FC 117' |
| tec-L3-trace-r3 | claude | 101 | FI 101 | 'FT 101' |
| tec-L3-trace-r3 | claude | 101 | FI 102 | 'FT 102' |
| tec-L3-trace-r3 | claude | 101 | FI 103 | 'FT 103' |
| tec-L3-trace-r3 | claude | 101 | FI 106 | 'TI 100' |
| tec-L3-trace-r3 | claude | 101 | AI 123 | 'AI 100' |
| tec-L3-trace-r3 | claude | 101 | TV 121 | 'TV 101' |
| tec-L3-trace-r3 | claude | 101 | TI 121 | 'TT 121' |
| tec-L3-trace-r3 | claude | 101 | TI 109 | 'TI 108' |
| tec-L3-trace-r3 | claude | 101 | AIC 123A | None |
| tec-L3-trace-r3 | claude | 101 | AIC 123D | None |
| tec-L3-trace-r3 | claude | 101 | AIC 123E | None |
| tec-L3-trace-r3 | claude | 101 | TIC 109 | 'TIC 108' |
| tec-L3-trace-r3 | claude | 102 | FI 105 | 'FT 105' |
| tec-L3-trace-r3 | claude | 102 | FI 110 | 'FT 110' |
| tec-L3-trace-r3 | claude | 102 | AI 129 | 'AT 120' |
| tec-L3-trace-r3 | claude | 102 | FI 114 | 'TI 114' |
| tec-L3-trace-r3 | claude | 102 | TI 122 | 'TI 123' |
| tec-L3-trace-r3 | claude | 102 | TI 111 | None |
| tec-L3-trace-r3 | claude | 102 | LI 112 | 'LT 112' |
| tec-L3-trace-r3 | claude | 102 | FIC 105 | 'FC 105' |
| tec-L3-trace-r3 | claude | 102 | AIC 129 | 'AIC 120' |
| tec-L3-trace-r3 | claude | 103 | FI 104 | 'FT 104' |
| tec-L3-trace-r3 | claude | 103 | FI 117 | 'FT 117' |
| tec-L3-trace-r3 | claude | 103 | AI 137 | None |
| tec-L3-trace-r3 | claude | 103 | LV 115 | None |
| tec-L3-trace-r3 | claude | 103 | FV 119 | 'PV 116' |
| tec-L3-trace-r3 | claude | 103 | FI 119 | 'FT 116' |
| tec-L3-trace-r3 | claude | 103 | TI 118 | 'TI 116' |
| tec-L3-trace-r3 | claude | 103 | LI 115 | 'LI 116' |
| tec-L3-trace-r3 | claude | 103 | FIC 119 | 'FC 116' |
| tec-L3-trace-r3 | claude | 103 | TIC 118 | 'TIC 116' |
| tec-L3-trace-r3 | claude | 103 | LIC 115 | 'LIC 116' |
| tec-L3-trace-r3 | claude | 103 | AIC 137 | None |
| tec-L3-trace-r3 | claude | 103 | FIC 117 | 'FC 117' |
