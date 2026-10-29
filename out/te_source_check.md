# TE model vs. open source code (2026-10-29)

Source: `teprob.f (Braatz group TE code)`, https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/master/teprob.f

| Tag | Model says | Source says | Result |
|---|---|---|---|
| FT-101 | A feed flow (kscmh) | XMEAS 1: "A Feed" kscmh | **confirmed** |
| FT-102 | D feed flow (kg/h) | XMEAS 2: "D Feed" kg/hr | **confirmed** |
| FT-103 | E feed flow (kg/h) | XMEAS 3: "E Feed" kg/hr | **confirmed** |
| FT-104 | A and C feed flow (kscmh) | XMEAS 4: "A and C Feed" kscmh | **confirmed** |
| FT-105 | Recycle flow (kscmh) | XMEAS 5: "Recycle Flow" kscmh | **confirmed** |
| FT-106 | Reactor feed rate (kscmh) | XMEAS 6: "Reactor Feed Rate" kscmh | **confirmed** |
| PT-107 | Reactor pressure (kPa g) | XMEAS 7: "Reactor Pressure" kPa gauge | **confirmed** |
| LT-108 | Reactor level (%) | XMEAS 8: "Reactor Level" % | **confirmed** |
| TT-109 | Reactor temperature (degC) | XMEAS 9: "Reactor Temperature" Deg C | **confirmed** |
| FT-110 | Purge rate (kscmh) | XMEAS 10: "Purge Rate (stream 9)" kscmh | **confirmed** |
| TT-111 | Separator temperature (degC) | XMEAS 11: "Product Sep Temp" Deg C | **confirmed** |
| LT-112 | Separator level (%) | XMEAS 12: "Product Sep Level" % | **confirmed** |
| PT-113 | Separator pressure (kPa g) | XMEAS 13: "Prod Sep Pressure" kPa gauge | **confirmed** |
| FT-114 | Separator underflow (m3/h) | XMEAS 14: "Prod Sep Underflow (stream 10)" m3/hr | **confirmed** |
| LT-115 | Stripper level (%) | XMEAS 15: "Stripper Level" % | **confirmed** |
| PT-116 | Stripper pressure (kPa g) | XMEAS 16: "Stripper Pressure" kPa gauge | **confirmed** |
| FT-117 | Stripper underflow (product) (m3/h) | XMEAS 17: "Stripper Underflow (stream 11)" m3/hr | **confirmed** |
| TT-118 | Stripper temperature (degC) | XMEAS 18: "Stripper Temperature" Deg C | **confirmed** |
| FT-119 | Stripper steam flow (kg/h) | XMEAS 19: "Stripper Steam Flow" kg/hr | **confirmed** |
| JT-120 | Compressor work (kW) | XMEAS 20: "Compressor Work" kW | **confirmed** |
| TT-121 | Reactor cooling water outlet temperature (degC) | XMEAS 21: "Reactor Cooling Water Outlet Temp" Deg C | **confirmed** |
| TT-122 | Separator Cooling Water Outlet Temp (degC) | XMEAS 22: "Separator Cooling Water Outlet Temp" Deg C | **corrected** |
| AT-123 | Reactor feed analyzer (components A-F) (mol%) | Reactor Feed Analysis (stream 6): components A-F | **confirmed** |
| AT-129 | Purge gas analyzer (components A-H) (mol%) | Purge Gas Analysis (stream 9): components A-H | **confirmed** |
| AT-137 | Product analyzer (components D-H) (mol%) | Product Analysis (stream 11): components D-H | **confirmed** |
| FV-102 | D feed flow valve (%) | XMV 1: "D Feed Flow (stream 2)" | **confirmed** |
| FV-103 | E feed flow valve (%) | XMV 2: "E Feed Flow (stream 3)" | **confirmed** |
| FV-101 | A feed flow valve (%) | XMV 3: "A Feed Flow (stream 1)" | **confirmed** |
| FV-104 | A and C feed flow valve (%) | XMV 4: "A and C Feed Flow (stream 4)" | **confirmed** |
| FV-105 | Compressor recycle valve (%) | XMV 5: "Compressor Recycle Valve" | **confirmed** |
| FV-110 | Purge valve (%) | XMV 6: "Purge Valve (stream 9)" | **confirmed** |
| LV-112 | Separator pot liquid flow valve (%) | XMV 7: "Separator Pot Liquid Flow (stream 10)" | **confirmed** |
| LV-115 | Stripper liquid product flow valve (%) | XMV 8: "Stripper Liquid Product Flow (stream 11)" | **confirmed** |
| FV-119 | Stripper steam valve (%) | XMV 9: "Stripper Steam Valve" | **confirmed** |
| TV-121 | Reactor cooling water flow valve (%) | XMV 10: "Reactor Cooling Water Flow" | **confirmed** |
| FV-117 | Condenser cooling water flow valve (%) | XMV 11: "Condenser Cooling Water Flow" | **confirmed** |
| SC-212 | Agitator speed (%) | XMV 12: "Agitator Speed" | **confirmed** |

**Totals:** 36 confirmed · 1 corrected · 0 unverified (of 37)
