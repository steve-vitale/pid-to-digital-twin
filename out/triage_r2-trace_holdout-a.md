# Triage score: `r2-trace` (split: holdout-a)

Errors caught in the riskiest k% of output items (symbols + links pooled). Random = k%.

| Tool | Items (errors) | Top 10%: risk / self / random | Top 20%: risk / self / random | Top 30%: risk / self / random | Green precision | Green share | Error rate green / amber / red |
|---|---|---|---|---|---|---|---|
| claude | 1041 (112) | 41% / 14% / 10% | 57% / 31% / 20% | 66% / 44% / 30% | 95% | 72% | 5% / 21% / 73% |
| codex | 1165 (129) | 36% / 26% / 10% | 55% / 38% / 20% | 66% / 50% / 30% | 96% | 64% | 4% / 15% / 67% |
| gemini | 923 (180) | 49% / 10% / 10% | 78% / 17% / 20% | 81% / 20% / 30% | 95% | 79% | 5% / 45% / 96% |

Tier sizes (share of items): claude 72% / 26% / 2%; codex 64% / 30% / 5%; gemini 79% / 9% / 12% (green / amber / red).
Symbols-only and links-only top-20% catch rates are in the JSON.
