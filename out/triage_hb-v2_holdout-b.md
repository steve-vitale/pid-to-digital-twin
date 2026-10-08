# Triage score: `hb-v2` (split: holdout-b)

Errors caught in the riskiest k% of output items (symbols + links pooled). Random = k%.

| Tool | Items (errors) | Top 10%: risk / self / random | Top 20%: risk / self / random | Top 30%: risk / self / random | Green precision | Green share | Error rate green / amber / red |
|---|---|---|---|---|---|---|---|
| claude | 4332 (232) | 59% / 21% / 10% | 71% / 31% / 20% | 82% / 46% / 30% | 98% | 38% | 2% / 3% / 32% |
| codex | 6139 (334) | 50% / 15% / 10% | 69% / 30% / 20% | 72% / 42% / 30% | 98% | 27% | 2% / 4% / 27% |
| gemini | 2742 (792) | 34% / 22% / 10% | 53% / 31% / 20% | 80% / 39% / 30% | 98% | 51% | 2% / 28% / 78% |

Tier sizes (share of items): claude 38% / 53% / 10%; codex 27% / 63% / 10%; gemini 51% / 21% / 28% (green / amber / red).
Symbols-only and links-only top-20% catch rates are in the JSON.
