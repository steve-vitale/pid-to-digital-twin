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
| D | D legibility: no overlap, crowding, covered markers, pills on the silhouette, all-caps, off-screen, occlusion, small text or low contrast | PASS | 12 stills, 116 labels + captions; overlaps 0, crowded 0, labels covering markers 0, pills on the focus silhouette 0, all-caps runs 0, off-screen 0, occluded 0, text < 18px 0, contrast < 4.5:1 0, expected-but-missing 0; min text height 18.7px, min contrast 8.18:1; 0 drawn labels entirely outside their still's frame were not counted (layout 'declutter') |
| D | D contrast cross-check with an independent pixel reader (Pillow) | PASS | 116 boxes re-measured from the PNGs; largest difference 0.00 (01_u-100_normal tag:FI-101: Pillow 12.86 vs Blender 12.86) |
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
| AI-123 | R-101 | mol% | stream/S6 | TE_Plant/R-101/AI-123 | \\TE Plant\R-101|ReactorFeedAnalyzerComponentsAF |
| AI-129 | V-101 | mol% | stream/S9 | TE_Plant/V-101/AI-129 | \\TE Plant\V-101|PurgeGasAnalyzerComponentsAH |
| AI-137 | C-101 | mol% | stream/S11 | TE_Plant/C-101/AI-137 | \\TE Plant\C-101|ProductAnalyzerComponentsDH |
| FI-101 | U-100 | kscmh | stream/S1 | TE_Plant/U-100/FI-101 | \\TE Plant\U-100|AFeedFlow |
| FI-102 | U-100 | kg/h | stream/S2 | TE_Plant/U-100/FI-102 | \\TE Plant\U-100|DFeedFlow |
| FI-103 | U-100 | kg/h | stream/S3 | TE_Plant/U-100/FI-103 | \\TE Plant\U-100|EFeedFlow |
| FI-104 | C-101 | kscmh | stream/S4 | TE_Plant/C-101/FI-104 | \\TE Plant\C-101|AAndCFeedFlow |
| FI-105 | K-101 | kscmh | stream/S8b | TE_Plant/K-101/FI-105 | \\TE Plant\K-101|RecycleFlow |
| FI-106 | R-101 | kscmh | stream/S6 | TE_Plant/R-101/FI-106 | \\TE Plant\R-101|ReactorFeedRate |
| FI-110 | V-101 | kscmh | stream/S9 | TE_Plant/V-101/FI-110 | \\TE Plant\V-101|PurgeRate |
| FI-114 | V-101 | m3/h | stream/S10 | TE_Plant/V-101/FI-114 | \\TE Plant\V-101|SeparatorUnderflow |
| FI-117 | C-101 | m3/h | stream/S11 | TE_Plant/C-101/FI-117 | \\TE Plant\C-101|StripperUnderflowProduct |
| FI-119 | C-101 | kg/h | unit/C-101 | TE_Plant/C-101/FI-119 | \\TE Plant\C-101|StripperSteamFlow |
| FV-201 | U-100 | % | stream/S2 | TE_Plant/U-100/FV-201 | \\TE Plant\U-100|DFeedFlowValve |
| FV-202 | U-100 | % | stream/S3 | TE_Plant/U-100/FV-202 | \\TE Plant\U-100|EFeedFlowValve |
| FV-203 | U-100 | % | stream/S1 | TE_Plant/U-100/FV-203 | \\TE Plant\U-100|AFeedFlowValve |
| FV-204 | C-101 | % | stream/S4 | TE_Plant/C-101/FV-204 | \\TE Plant\C-101|AAndCFeedFlowValve |
| FV-206 | V-101 | % | stream/S9 | TE_Plant/V-101/FV-206 | \\TE Plant\V-101|PurgeValve |
| FV-209 | C-101 | % | unit/C-101 | TE_Plant/C-101/FV-209 | \\TE Plant\C-101|StripperSteamValve |
| HV-205 | K-101 | % | unit/K-101 | TE_Plant/K-101/HV-205 | \\TE Plant\K-101|CompressorRecycleValve |
| JI-120 | K-101 | kW | unit/K-101 | TE_Plant/K-101/JI-120 | \\TE Plant\K-101|CompressorWork |
| LI-108 | R-101 | % | unit/R-101 | TE_Plant/R-101/LI-108 | \\TE Plant\R-101|ReactorLevel |
| LI-112 | V-101 | % | unit/V-101 | TE_Plant/V-101/LI-112 | \\TE Plant\V-101|SeparatorLevel |
| LI-115 | C-101 | % | unit/C-101 | TE_Plant/C-101/LI-115 | \\TE Plant\C-101|StripperLevel |
| LV-207 | V-101 | % | stream/S10 | TE_Plant/V-101/LV-207 | \\TE Plant\V-101|SeparatorPotLiquidFlowValve |
| LV-208 | C-101 | % | stream/S11 | TE_Plant/C-101/LV-208 | \\TE Plant\C-101|StripperLiquidProductFlowValve |
| PI-107 | R-101 | kPa g | unit/R-101 | TE_Plant/R-101/PI-107 | \\TE Plant\R-101|ReactorPressure |
| PI-113 | V-101 | kPa g | unit/V-101 | TE_Plant/V-101/PI-113 | \\TE Plant\V-101|SeparatorPressure |
| PI-116 | C-101 | kPa g | unit/C-101 | TE_Plant/C-101/PI-116 | \\TE Plant\C-101|StripperPressure |
| SC-212 | R-101 | % | unit/R-101 | TE_Plant/R-101/SC-212 | \\TE Plant\R-101|AgitatorSpeed |
| TI-109 | R-101 | degC | unit/R-101 | TE_Plant/R-101/TI-109 | \\TE Plant\R-101|ReactorTemperature |
| TI-111 | V-101 | degC | unit/V-101 | TE_Plant/V-101/TI-111 | \\TE Plant\V-101|SeparatorTemperature |
| TI-118 | C-101 | degC | unit/C-101 | TE_Plant/C-101/TI-118 | \\TE Plant\C-101|StripperTemperature |
| TI-121 | R-101 | degC | unit/R-101 | TE_Plant/R-101/TI-121 | \\TE Plant\R-101|ReactorCoolingWaterOutletTemperature |
| TI-122 | E-101 | degC | unit/E-101 | TE_Plant/E-101/TI-122 | \\TE Plant\E-101|SeparatorCoolingWaterOutletTemp |
| TV-210 | R-101 | % | unit/R-101 | TE_Plant/R-101/TV-210 | \\TE Plant\R-101|ReactorCoolingWaterFlowValve |
| TV-211 | E-101 | % | unit/E-101 | TE_Plant/E-101/TV-211 | \\TE Plant\E-101|CondenserCoolingWaterFlowValve |
