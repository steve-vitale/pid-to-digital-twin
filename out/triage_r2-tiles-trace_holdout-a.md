# Triage score: `r2-tiles-trace` (split: holdout-a)

Errors caught in the riskiest k% of output items (symbols + links pooled). Random = k%.

| Tool | Items (errors) | Top 10%: risk / self / random | Top 20%: risk / self / random | Top 30%: risk / self / random | Green precision | Green share | Error rate green / amber / red |
|---|---|---|---|---|---|---|---|
| claude | 1148 (142) | 47% / 20% / 10% | 64% / 31% / 20% | 69% / 44% / 30% | 95% | 77% | 5% / 26% / 77% |
| codex | 1312 (129) | 29% / 30% / 10% | 40% / 43% / 20% | 57% / 60% / 30% | 94% | 69% | 6% / 15% / 23% |
| gemini | 1022 (132) | 60% / 18% / 10% | 67% / 28% / 20% | 71% / 38% / 30% | 95% | 76% | 5% / 13% / 96% |

Tier sizes (share of items): claude 77% / 18% / 5%; codex 69% / 16% / 15%; gemini 76% / 17% / 7% (green / amber / red).
Symbols-only and links-only top-20% catch rates are in the JSON.
