# Triage score: `hb-tiles-2x2` (split: holdout-b)

Errors caught in the riskiest k% of output items (symbols + links pooled). Random = k%.

| Tool | Items (errors) | Top 10%: risk / self / random | Top 20%: risk / self / random | Top 30%: risk / self / random | Green precision | Green share | Error rate green / amber / red |
|---|---|---|---|---|---|---|---|
| claude | 5117 (184) | 44% / 25% / 10% | 62% / 37% / 20% | 69% / 54% / 30% | 98% | 57% | 2% / 5% / 12% |
| codex | 6733 (435) | 36% / 21% / 10% | 45% / 32% / 20% | 60% / 44% / 30% | 97% | 44% | 3% / 7% / 21% |
| gemini | 4136 (442) | 40% / 22% / 10% | 72% / 34% / 20% | 81% / 43% / 30% | 98% | 56% | 2% / 9% / 43% |

Tier sizes (share of items): claude 57% / 38% / 5%; codex 44% / 47% / 9%; gemini 56% / 28% / 16% (green / amber / red).
Symbols-only and links-only top-20% catch rates are in the JSON.
