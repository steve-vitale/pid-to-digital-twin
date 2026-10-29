# 3D tour verification

| Group | Check | Status | Result |
|---|---|---|---|
| A | A0 scene tags = contract tags | PASS | 37 scene markers, 37 contract records |
| A | A0 scene units = contract units | PASS | 6 scene units |
| A | A ignition_gateway: 1:1 tags, units, owning unit, UOM | PASS | 37/37 scene tags found; 16 extra explained (analyzer component channels; the 3D marker shows the first component only); 0 unexplained extra; 0 mismatches; unit folders differ: none |
| A | A bands and alarm setpoints colouring the 3D markers = gateway tag parameters | PASS | 36 banded tags compared, 2 alarmed tags |
| A | A ignition_seed_udt: 1:1 tags, units, owning unit, UOM | PASS | 37/37 scene tags found; 0 extra explained (analyzer component channels; the 3D marker shows the first component only); 0 unexplained extra; 0 mismatches; unit folders differ: none |
| A | A pi_af: 1:1 tags, units, owning unit, UOM | PASS | 37/37 scene tags found; 0 extra explained (analyzer component channels; the 3D marker shows the first component only); 0 unexplained extra; 0 mismatches; unit folders differ: none |
| A | A perspective: every scene tag bound in the TE views under its owning unit | PASS | 37/37 tags bound |
| A | A stream membership: scene stream placement agrees with the contract | PASS | 19 tags placed on streams; the Ignition and PI exports carry no stream field, so membership is checked against the contract only |
| B | B pipe endpoints in 3D reproduce the contract stream topology | PASS | 13/13 streams derived from geometry match from/to |
| B | B no tag marker inside equipment; markers near what they measure | PASS | 0 markers inside equipment, 0 far from their stream/unit |
| B | B utility stubs are labelled inferred and valve symbols map to contract final elements | PASS | 5 inferred utility stubs, 10 valve symbols |
| B | B tour order is a valid walk of the directed stream graph | PASS | each stop is reached by a directed stream from the battery limit or an earlier stop (directions from the model, checked against the simulator source) |
| C | C every scene tag traces to a drawing (id + bbox) or is declared seed/synthetic | PASS | drawing-traced 0/37; declared seed 37/37 (37 of them checked against teprob.f (Braatz group TE code)); unexplained 0/37 |
| C | C drawing coverage | INFO | 0 of 37 tags trace to a P&ID drawing: this model is 'hand-built seed model (Phase 0). Serves as the answer-key dr...', built from a paper, not extracted from a drawing |
| D | D legibility: no overlap, crowding, covered markers, pills on the silhouette, all-caps, off-screen, occlusion, small text or low contrast | PASS | 12 stills, 116 labels + captions; overlaps 0, crowded 0, labels covering markers 0, pills on the focus silhouette 0, all-caps runs 0, off-screen 0, occluded 0, text < 18px 0, contrast < 4.5:1 0, expected-but-missing 0; min text height 18.7px, min contrast 8.11:1; 0 drawn labels entirely outside their still's frame were not counted (layout 'declutter') |
| D | D contrast cross-check with an independent pixel reader (Pillow) | PASS | 116 boxes re-measured from the PNGs; largest difference 0.00 (40_loto_mockup loto:9: Pillow 8.18 vs Blender 8.18) |
| D | D OCR readability | INFO | skipped: no tesseract executable on PATH (not installed by this verifier) |

## B tour order is a valid walk of the directed stream graph (pass)

- stop 1 U-100: entered via S1 (BL -> U-100)
- stop 2 R-101: entered via S6 (U-100 -> R-101)
- stop 3 E-101: entered via S7 (R-101 -> E-101)
- stop 4 V-101: entered via S7b (E-101 -> V-101)
- stop 5 K-101: entered via S8 (V-101 -> K-101)
- stop 6 C-101: entered via S4 (BL -> C-101)

## Tag map: scene -> Ignition -> PI AF

| Tag | Unit | UOM | On | Ignition path | PI AF path |
|---|---|---|---|---|---|
| AT-123 | R-101 | mol% | stream/S6 | TE_Plant/R-101/AT-123 | \\TE Plant\R-101|ReactorFeedAnalyzerComponentsAF |
| AT-129 | V-101 | mol% | stream/S9 | TE_Plant/V-101/AT-129 | \\TE Plant\V-101|PurgeGasAnalyzerComponentsAH |
| AT-137 | C-101 | mol% | stream/S11 | TE_Plant/C-101/AT-137 | \\TE Plant\C-101|ProductAnalyzerComponentsDH |
| FT-101 | U-100 | kscmh | stream/S1 | TE_Plant/U-100/FT-101 | \\TE Plant\U-100|AFeedFlow |
| FT-102 | U-100 | kg/h | stream/S2 | TE_Plant/U-100/FT-102 | \\TE Plant\U-100|DFeedFlow |
| FT-103 | U-100 | kg/h | stream/S3 | TE_Plant/U-100/FT-103 | \\TE Plant\U-100|EFeedFlow |
| FT-104 | C-101 | kscmh | stream/S4 | TE_Plant/C-101/FT-104 | \\TE Plant\C-101|AAndCFeedFlow |
| FT-105 | K-101 | kscmh | stream/S8b | TE_Plant/K-101/FT-105 | \\TE Plant\K-101|RecycleFlow |
| FT-106 | R-101 | kscmh | stream/S6 | TE_Plant/R-101/FT-106 | \\TE Plant\R-101|ReactorFeedRate |
| FT-110 | V-101 | kscmh | stream/S9 | TE_Plant/V-101/FT-110 | \\TE Plant\V-101|PurgeRate |
| FT-114 | V-101 | m3/h | stream/S10 | TE_Plant/V-101/FT-114 | \\TE Plant\V-101|SeparatorUnderflow |
| FT-117 | C-101 | m3/h | stream/S11 | TE_Plant/C-101/FT-117 | \\TE Plant\C-101|StripperUnderflowProduct |
| FT-119 | C-101 | kg/h | unit/C-101 | TE_Plant/C-101/FT-119 | \\TE Plant\C-101|StripperSteamFlow |
| FV-101 | U-100 | % | stream/S1 | TE_Plant/U-100/FV-101 | \\TE Plant\U-100|AFeedFlowValve |
| FV-102 | U-100 | % | stream/S2 | TE_Plant/U-100/FV-102 | \\TE Plant\U-100|DFeedFlowValve |
| FV-103 | U-100 | % | stream/S3 | TE_Plant/U-100/FV-103 | \\TE Plant\U-100|EFeedFlowValve |
| FV-104 | C-101 | % | stream/S4 | TE_Plant/C-101/FV-104 | \\TE Plant\C-101|AAndCFeedFlowValve |
| FV-105 | K-101 | % | unit/K-101 | TE_Plant/K-101/FV-105 | \\TE Plant\K-101|CompressorRecycleValve |
| FV-110 | V-101 | % | stream/S9 | TE_Plant/V-101/FV-110 | \\TE Plant\V-101|PurgeValve |
| FV-117 | E-101 | % | unit/E-101 | TE_Plant/E-101/FV-117 | \\TE Plant\E-101|CondenserCoolingWaterFlowValve |
| FV-119 | C-101 | % | unit/C-101 | TE_Plant/C-101/FV-119 | \\TE Plant\C-101|StripperSteamValve |
| JT-120 | K-101 | kW | unit/K-101 | TE_Plant/K-101/JT-120 | \\TE Plant\K-101|CompressorWork |
| LT-108 | R-101 | % | unit/R-101 | TE_Plant/R-101/LT-108 | \\TE Plant\R-101|ReactorLevel |
| LT-112 | V-101 | % | unit/V-101 | TE_Plant/V-101/LT-112 | \\TE Plant\V-101|SeparatorLevel |
| LT-115 | C-101 | % | unit/C-101 | TE_Plant/C-101/LT-115 | \\TE Plant\C-101|StripperLevel |
| LV-112 | V-101 | % | stream/S10 | TE_Plant/V-101/LV-112 | \\TE Plant\V-101|SeparatorPotLiquidFlowValve |
| LV-115 | C-101 | % | stream/S11 | TE_Plant/C-101/LV-115 | \\TE Plant\C-101|StripperLiquidProductFlowValve |
| PT-107 | R-101 | kPa g | unit/R-101 | TE_Plant/R-101/PT-107 | \\TE Plant\R-101|ReactorPressure |
| PT-113 | V-101 | kPa g | unit/V-101 | TE_Plant/V-101/PT-113 | \\TE Plant\V-101|SeparatorPressure |
| PT-116 | C-101 | kPa g | unit/C-101 | TE_Plant/C-101/PT-116 | \\TE Plant\C-101|StripperPressure |
| SC-212 | R-101 | % | unit/R-101 | TE_Plant/R-101/SC-212 | \\TE Plant\R-101|AgitatorSpeed |
| TT-109 | R-101 | degC | unit/R-101 | TE_Plant/R-101/TT-109 | \\TE Plant\R-101|ReactorTemperature |
| TT-111 | V-101 | degC | unit/V-101 | TE_Plant/V-101/TT-111 | \\TE Plant\V-101|SeparatorTemperature |
| TT-118 | C-101 | degC | unit/C-101 | TE_Plant/C-101/TT-118 | \\TE Plant\C-101|StripperTemperature |
| TT-121 | R-101 | degC | unit/R-101 | TE_Plant/R-101/TT-121 | \\TE Plant\R-101|ReactorCoolingWaterOutletTemperature |
| TT-122 | E-101 | degC | unit/E-101 | TE_Plant/E-101/TT-122 | \\TE Plant\E-101|SeparatorCoolingWaterOutletTemp |
| TV-121 | R-101 | % | unit/R-101 | TE_Plant/R-101/TV-121 | \\TE Plant\R-101|ReactorCoolingWaterFlowValve |
