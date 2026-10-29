# Live values for the extracted twin (claude-L3-r1)

`scripts/te_live_check.py` against the TE replay server (normal run), reads 5 s apart.

- Extracted instrument symbols (bubbles, including valve tags): **37**
- Matched by tag to a replay point: **16** (16 through the tag's earlier name, `former_tag`: the drawings were read before a retag); value moved between reads: **16**
- Replay points with no matching tag on the drawings: AT-123, AT-123-B, AT-123-C, AT-123-D, AT-123-E, AT-123-F, AT-129, AT-129-B, AT-129-C, AT-129-D, AT-129-E, AT-129-F, AT-129-G, AT-129-H, AT-137, AT-137-E, AT-137-F, AT-137-G, AT-137-H, FT-104, FT-106, FT-114, FT-117, FT-119, FV-104, FV-110, FV-119, LT-115, LV-112, LV-115, TT-109, TT-111, TT-118, TT-121, TT-122, TV-121

| Extracted tag | Replay point | First read | Second read | Moved |
|---|---|---|---|---|
| FV 201 | FV-102 (earlier name) | 63.33 | 63.25 | yes |
| FI 101 | FT-101 (earlier name) | 0.2456 | 0.2974 | yes |
| FV 202 | FV-103 (earlier name) | 53.91 | 53.34 | yes |
| FI 102 | FT-102 (earlier name) | 3698 | 3721 | yes |
| FV 203 | FV-101 (earlier name) | 24.45 | 29.46 | yes |
| FI 103 | FT-103 (earlier name) | 4537 | 4533 | yes |
| SIC 212 | (no point) |  |  | no |
| PI 107 | PT-107 (earlier name) | 2705 | 2706 | yes |
| LI 108 | LT-108 (earlier name) | 75.28 | 74.81 | yes |
| TI 106 | (no point) |  |  | no |
| TI | (no point) |  |  | no |
| AI | (no point) |  |  | no |
| TV | (no point) |  |  | no |
| None | (no point) |  |  | no |
| TI 123 | (no point) |  |  | no |
| TV 211 | FV-117 (earlier name) | 18.33 | 16.78 | yes |
| FI 105 | FT-105 (earlier name) | 26.74 | 26.99 | yes |
| JI 120 | JT-120 (earlier name) | 341.2 | 341.6 | yes |
| HV 205 | FV-105 (earlier name) | 22.27 | 22.39 | yes |
| FI 110 | FT-110 (earlier name) | 0.3252 | 0.3395 | yes |
| AI 120 | (no point) |  |  | no |
| FX 206 | (no point) |  |  | no |
| None | (no point) |  |  | no |
| LI 112 | LT-112 (earlier name) | 49.52 | 48.81 | yes |
| PI 113 | PT-113 (earlier name) | 2634 | 2635 | yes |
| TI 114 | (no point) |  |  | no |
| LC 101 | (no point) |  |  | no |
| PI 116 | PT-116 (earlier name) | 3104 | 3102 | yes |
| TI 116 | (no point) |  |  | no |
| LI 116 | (no point) |  |  | no |
| PV 204 | (no point) |  |  | no |
| FT 204 | (no point) |  |  | no |
| PV 205 | (no point) |  |  | no |
| FI 115 | (no point) |  |  | no |
| PT | (no point) |  |  | no |
| AI | (no point) |  |  | no |
| None | (no point) |  |  | no |
