# Triage score: `hb-trace` (split: holdout-b)

Errors caught in the riskiest k% of output items (symbols + links pooled). Random = k%.

| Tool | Items (errors) | Top 10%: risk / self / random | Top 20%: risk / self / random | Top 30%: risk / self / random | Green precision | Green share | Error rate green / amber / red |
|---|---|---|---|---|---|---|---|
| claude | 13814 (840) | 72% / 15% / 10% | 77% / 28% / 20% | 82% / 38% / 30% | 100% | 41% | 0% / 3% / 73% |
| codex | 15014 (435) | 43% / 17% / 10% | 61% / 33% / 20% | 68% / 44% / 30% | 100% | 39% | 0% / 3% / 12% |
| gemini | 8969 (3152) | 25% / 8% / 10% | 53% / 22% / 20% | 81% / 34% / 30% | 99% | 60% | 1% / 55% / 95% |

Tier sizes (share of items): claude 41% / 53% / 6%; codex 39% / 52% / 10%; gemini 60% / 10% / 31% (green / amber / red).
Symbols-only and links-only top-20% catch rates are in the JSON.
