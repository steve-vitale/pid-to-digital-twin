# Triage score: `hb-tiles-trace` (split: holdout-b)

Errors caught in the riskiest k% of output items (symbols + links pooled). Random = k%.

| Tool | Items (errors) | Top 10%: risk / self / random | Top 20%: risk / self / random | Top 30%: risk / self / random | Green precision | Green share | Error rate green / amber / red |
|---|---|---|---|---|---|---|---|
| claude | 14823 (341) | 44% / 22% / 10% | 68% / 42% / 20% | 74% / 62% / 30% | 99% | 74% | 1% / 5% / 32% |
| codex | 15070 (830) | 39% / 23% / 10% | 58% / 30% / 20% | 66% / 39% / 30% | 97% | 77% | 3% / 11% / 47% |
| gemini | 13116 (1355) | 71% / 18% / 10% | 76% / 31% / 20% | 80% / 41% / 30% | 98% | 50% | 2% / 6% / 84% |

Tier sizes (share of items): claude 74% / 24% / 1%; codex 77% / 21% / 2%; gemini 50% / 42% / 8% (green / amber / red).
Symbols-only and links-only top-20% catch rates are in the JSON.
