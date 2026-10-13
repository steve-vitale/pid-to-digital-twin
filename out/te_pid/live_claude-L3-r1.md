# Live values for the extracted twin (claude-L3-r1)

`scripts/te_live_check.py` against the TE replay server (normal run), reads 5 s apart.

- Extracted instrument symbols (bubbles, including valve tags): **37**
- Matched by tag to a replay point: **16**; value moved between reads: **16**
- Replay points with no matching tag on the drawings: AI-123, AI-123-B, AI-123-C, AI-123-D, AI-123-E, AI-123-F, AI-129, AI-129-B, AI-129-C, AI-129-D, AI-129-E, AI-129-F, AI-129-G, AI-129-H, AI-137, AI-137-E, AI-137-F, AI-137-G, AI-137-H, FI-104, FI-106, FI-114, FI-117, FI-119, FV-204, FV-206, FV-209, LI-115, LV-207, LV-208, TI-109, TI-111, TI-118, TI-121, TI-122, TV-210

| Extracted tag | Replay point | First read | Second read | Moved |
|---|---|---|---|---|
| FV 201 | FV-201 | 63.16 | 64.41 | yes |
| FI 101 | FI-101 | 0.2511 | 0.3001 | yes |
| FV 202 | FV-202 | 54.12 | 54.28 | yes |
| FI 102 | FI-102 | 3658 | 3653 | yes |
| FV 203 | FV-203 | 24.59 | 29.19 | yes |
| FI 103 | FI-103 | 4498 | 4454 | yes |
| SIC 212 | (no point) |  |  | no |
| PI 107 | PI-107 | 2707 | 2704 | yes |
| LI 108 | LI-108 | 73.99 | 75.5 | yes |
| TI 106 | (no point) |  |  | no |
| TI | (no point) |  |  | no |
| AI | (no point) |  |  | no |
| TV | (no point) |  |  | no |
| None | (no point) |  |  | no |
| TI 123 | (no point) |  |  | no |
| TV 211 | TV-211 | 20.09 | 18.23 | yes |
| FI 105 | FI-105 | 26.53 | 26.91 | yes |
| JI 120 | JI-120 | 341.3 | 341.4 | yes |
| HV 205 | HV-205 | 21.96 | 21.94 | yes |
| FI 110 | FI-110 | 0.3366 | 0.3452 | yes |
| AI 120 | (no point) |  |  | no |
| FX 206 | (no point) |  |  | no |
| None | (no point) |  |  | no |
| LI 112 | LI-112 | 48.22 | 50.4 | yes |
| PI 113 | PI-113 | 2636 | 2632 | yes |
| TI 114 | (no point) |  |  | no |
| LC 101 | (no point) |  |  | no |
| PI 116 | PI-116 | 3105 | 3101 | yes |
| TI 116 | (no point) |  |  | no |
| LI 116 | (no point) |  |  | no |
| PV 204 | (no point) |  |  | no |
| FT 204 | (no point) |  |  | no |
| PV 205 | (no point) |  |  | no |
| FI 115 | (no point) |  |  | no |
| PT | (no point) |  |  | no |
| AI | (no point) |  |  | no |
| None | (no point) |  |  | no |
