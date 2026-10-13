# Live values for the extracted twin (claude-L3-r1)

`scripts/te_live_check.py` against the TE replay server (normal run), reads 5 s apart.

- Extracted instrument symbols (bubbles, including valve tags): **37**
- Matched by tag to a replay point: **16**; value moved between reads: **16**
- Replay points with no matching tag on the drawings: AI-123, AI-123-B, AI-123-C, AI-123-D, AI-123-E, AI-123-F, AI-129, AI-129-B, AI-129-C, AI-129-D, AI-129-E, AI-129-F, AI-129-G, AI-129-H, AI-137, AI-137-E, AI-137-F, AI-137-G, AI-137-H, FI-104, FI-106, FI-114, FI-117, FI-119, FV-204, FV-206, FV-209, LI-115, LV-207, LV-208, TI-109, TI-111, TI-118, TI-121, TI-122, TV-210

| Extracted tag | Replay point | First read | Second read | Moved |
|---|---|---|---|---|
| FV 201 | FV-201 | 63.33 | 63.25 | yes |
| FI 101 | FI-101 | 0.2456 | 0.2974 | yes |
| FV 202 | FV-202 | 53.91 | 53.34 | yes |
| FI 102 | FI-102 | 3698 | 3721 | yes |
| FV 203 | FV-203 | 24.45 | 29.46 | yes |
| FI 103 | FI-103 | 4537 | 4533 | yes |
| SIC 212 | (no point) |  |  | no |
| PI 107 | PI-107 | 2705 | 2706 | yes |
| LI 108 | LI-108 | 75.28 | 74.81 | yes |
| TI 106 | (no point) |  |  | no |
| TI | (no point) |  |  | no |
| AI | (no point) |  |  | no |
| TV | (no point) |  |  | no |
| None | (no point) |  |  | no |
| TI 123 | (no point) |  |  | no |
| TV 211 | TV-211 | 18.33 | 16.78 | yes |
| FI 105 | FI-105 | 26.74 | 26.99 | yes |
| JI 120 | JI-120 | 341.2 | 341.6 | yes |
| HV 205 | HV-205 | 22.27 | 22.39 | yes |
| FI 110 | FI-110 | 0.3252 | 0.3395 | yes |
| AI 120 | (no point) |  |  | no |
| FX 206 | (no point) |  |  | no |
| None | (no point) |  |  | no |
| LI 112 | LI-112 | 49.52 | 48.81 | yes |
| PI 113 | PI-113 | 2634 | 2635 | yes |
| TI 114 | (no point) |  |  | no |
| LC 101 | (no point) |  |  | no |
| PI 116 | PI-116 | 3104 | 3102 | yes |
| TI 116 | (no point) |  |  | no |
| LI 116 | (no point) |  |  | no |
| PV 204 | (no point) |  |  | no |
| FT 204 | (no point) |  |  | no |
| PV 205 | (no point) |  |  | no |
| FI 115 | (no point) |  |  | no |
| PT | (no point) |  |  | no |
| AI | (no point) |  |  | no |
| None | (no point) |  |  | no |
