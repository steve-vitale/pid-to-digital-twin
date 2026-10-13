# Live values for the extracted twin (codex-clean-r1)

`scripts/te_live_check.py` against the TE replay server (normal run), reads 5 s apart.

- Extracted instrument symbols (bubbles, including valve tags): **37**
- Matched by tag to a replay point: **36**; value moved between reads: **36**
- Replay points with no matching tag on the drawings: AI-123-B, AI-123-C, AI-123-D, AI-123-E, AI-123-F, AI-129-B, AI-129-C, AI-129-D, AI-129-E, AI-129-F, AI-129-G, AI-129-H, AI-137-E, AI-137-F, AI-137-G, AI-137-H

| Extracted tag | Replay point | First read | Second read | Moved |
|---|---|---|---|---|
| FV 203 | FV-203 | 24.45 | 29.46 | yes |
| FI 101 | FI-101 | 0.2456 | 0.2974 | yes |
| FV 201 | FV-201 | 63.33 | 63.25 | yes |
| FI 102 | FI-102 | 3698 | 3721 | yes |
| FV 202 | FV-202 | 53.91 | 53.34 | yes |
| FI 103 | FI-103 | 4537 | 4533 | yes |
| SC 212 | (no point) |  |  | no |
| PI 107 | PI-107 | 2705 | 2706 | yes |
| LI 108 | LI-108 | 75.28 | 74.81 | yes |
| TI 109 | TI-109 | 120.4 | 120.4 | yes |
| FI 106 | FI-106 | 42.35 | 42.63 | yes |
| AI 123 | AI-123 | 32.2 | 32.06 | yes |
| TV 210 | TV-210 | 41.73 | 41.65 | yes |
| TI 121 | TI-121 | 94.4 | 94.39 | yes |
| TI 122 | TI-122 | 77.16 | 77.42 | yes |
| TV 211 | TV-211 | 18.33 | 16.78 | yes |
| FI 105 | FI-105 | 26.74 | 26.99 | yes |
| JI 120 | JI-120 | 341.2 | 341.6 | yes |
| HV 205 | HV-205 | 22.27 | 22.39 | yes |
| FI 110 | FI-110 | 0.3252 | 0.3395 | yes |
| AI 129 | AI-129 | 33.39 | 33.35 | yes |
| FV 206 | FV-206 | 39.54 | 40.89 | yes |
| TI 111 | TI-111 | 80.13 | 80.15 | yes |
| LI 112 | LI-112 | 49.52 | 48.81 | yes |
| PI 113 | PI-113 | 2634 | 2635 | yes |
| FI 114 | FI-114 | 22.34 | 24.64 | yes |
| LV 207 | LV-207 | 36.68 | 34.6 | yes |
| FV 204 | FV-204 | 61.39 | 60.63 | yes |
| FI 104 | FI-104 | 9.375 | 9.313 | yes |
| PI 116 | PI-116 | 3104 | 3102 | yes |
| TI 118 | TI-118 | 65.79 | 65.66 | yes |
| LI 115 | LI-115 | 49.66 | 48.85 | yes |
| FV 209 | FV-209 | 47.46 | 47.28 | yes |
| FI 119 | FI-119 | 230.1 | 232.2 | yes |
| FI 117 | FI-117 | 22.85 | 23.52 | yes |
| AI 137 | AI-137 | 0.01787 | 0.03605 | yes |
| LV 208 | LV-208 | 45.75 | 43.88 | yes |
