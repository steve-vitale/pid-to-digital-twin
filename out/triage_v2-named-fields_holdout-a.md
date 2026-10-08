# Triage score: `v2-named-fields` (split: holdout-a)

Errors caught in the riskiest k% of output items (symbols + links pooled). Random = k%.

| Tool | Items (errors) | Top 10%: risk / self / random | Top 20%: risk / self / random | Top 30%: risk / self / random | Green precision | Green share | Error rate green / amber / red |
|---|---|---|---|---|---|---|---|
| claude | 835 (172) | 43% / 12% / 10% | 70% / 30% / 20% | 77% / 40% / 30% | 95% | 59% | 5% / 26% / 88% |
| codex | 1087 (221) | 43% / 31% / 10% | 65% / 40% / 20% | 73% / 53% / 30% | 95% | 46% | 5% / 17% / 84% |
| gemini | 762 (233) | 31% / 6% / 10% | 61% / 16% / 20% | 80% / 25% / 30% | 93% | 64% | 7% / 44% / 91% |

Tier sizes (share of items): claude 59% / 30% / 11%; codex 46% / 41% / 13%; gemini 64% / 14% / 22% (green / amber / red).
Symbols-only and links-only top-20% catch rates are in the JSON.
