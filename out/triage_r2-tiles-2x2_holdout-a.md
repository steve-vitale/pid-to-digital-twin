# Triage score: `r2-tiles-2x2` (split: holdout-a)

Errors caught in the riskiest k% of output items (symbols + links pooled). Random = k%.

| Tool | Items (errors) | Top 10%: risk / self / random | Top 20%: risk / self / random | Top 30%: risk / self / random | Green precision | Green share | Error rate green / amber / red |
|---|---|---|---|---|---|---|---|
| claude | 883 (156) | 45% / 14% / 10% | 62% / 24% / 20% | 71% / 37% / 30% | 95% | 60% | 5% / 22% / 72% |
| codex | 1222 (174) | 48% / 31% / 10% | 57% / 44% / 20% | 65% / 54% / 30% | 95% | 44% | 5% / 11% / 38% |
| gemini | 750 (177) | 38% / 14% / 10% | 74% / 24% / 20% | 83% / 34% / 30% | 95% | 66% | 5% / 23% / 90% |

Tier sizes (share of items): claude 60% / 28% / 12%; codex 44% / 34% / 22%; gemini 66% / 15% / 19% (green / amber / red).
Symbols-only and links-only top-20% catch rates are in the JSON.
