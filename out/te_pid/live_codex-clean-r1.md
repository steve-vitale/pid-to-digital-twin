# Live values for the extracted twin (codex-clean-r1)

`scripts/te_live_check.py` against the TE replay server (normal run), reads 5 s apart.

- Extracted instrument symbols (bubbles, including valve tags): **37**
- Matched by tag to a replay point: **36** (36 through the tag's earlier name, `former_tag`: the drawings were read before a retag); value moved between reads: **36**
- Replay points with no matching tag on the drawings: AT-123-B, AT-123-C, AT-123-D, AT-123-E, AT-123-F, AT-129-B, AT-129-C, AT-129-D, AT-129-E, AT-129-F, AT-129-G, AT-129-H, AT-137-E, AT-137-F, AT-137-G, AT-137-H

| Extracted tag | Replay point | First read | Second read | Moved |
|---|---|---|---|---|
| FV 203 | FV-101 (earlier name) | 24.45 | 29.46 | yes |
| FI 101 | FT-101 (earlier name) | 0.2456 | 0.2974 | yes |
| FV 201 | FV-102 (earlier name) | 63.33 | 63.25 | yes |
| FI 102 | FT-102 (earlier name) | 3698 | 3721 | yes |
| FV 202 | FV-103 (earlier name) | 53.91 | 53.34 | yes |
| FI 103 | FT-103 (earlier name) | 4537 | 4533 | yes |
| SC 212 | (no point) |  |  | no |
| PI 107 | PT-107 (earlier name) | 2705 | 2706 | yes |
| LI 108 | LT-108 (earlier name) | 75.28 | 74.81 | yes |
| TI 109 | TT-109 (earlier name) | 120.4 | 120.4 | yes |
| FI 106 | FT-106 (earlier name) | 42.35 | 42.63 | yes |
| AI 123 | AT-123 (earlier name) | 32.2 | 32.06 | yes |
| TV 210 | TV-121 (earlier name) | 41.73 | 41.65 | yes |
| TI 121 | TT-121 (earlier name) | 94.4 | 94.39 | yes |
| TI 122 | TT-122 (earlier name) | 77.16 | 77.42 | yes |
| TV 211 | FV-117 (earlier name) | 18.33 | 16.78 | yes |
| FI 105 | FT-105 (earlier name) | 26.74 | 26.99 | yes |
| JI 120 | JT-120 (earlier name) | 341.2 | 341.6 | yes |
| HV 205 | FV-105 (earlier name) | 22.27 | 22.39 | yes |
| FI 110 | FT-110 (earlier name) | 0.3252 | 0.3395 | yes |
| AI 129 | AT-129 (earlier name) | 33.39 | 33.35 | yes |
| FV 206 | FV-110 (earlier name) | 39.54 | 40.89 | yes |
| TI 111 | TT-111 (earlier name) | 80.13 | 80.15 | yes |
| LI 112 | LT-112 (earlier name) | 49.52 | 48.81 | yes |
| PI 113 | PT-113 (earlier name) | 2634 | 2635 | yes |
| FI 114 | FT-114 (earlier name) | 22.34 | 24.64 | yes |
| LV 207 | LV-112 (earlier name) | 36.68 | 34.6 | yes |
| FV 204 | FV-104 (earlier name) | 61.39 | 60.63 | yes |
| FI 104 | FT-104 (earlier name) | 9.375 | 9.313 | yes |
| PI 116 | PT-116 (earlier name) | 3104 | 3102 | yes |
| TI 118 | TT-118 (earlier name) | 65.79 | 65.66 | yes |
| LI 115 | LT-115 (earlier name) | 49.66 | 48.85 | yes |
| FV 209 | FV-119 (earlier name) | 47.46 | 47.28 | yes |
| FI 119 | FT-119 (earlier name) | 230.1 | 232.2 | yes |
| FI 117 | FT-117 (earlier name) | 22.85 | 23.52 | yes |
| AI 137 | AT-137 (earlier name) | 0.01787 | 0.03605 | yes |
| LV 208 | LV-115 (earlier name) | 45.75 | 43.88 | yes |
