# Twin-level scores: `round1-v2-named-fields` (sheets 0, 1, 2, 3, 4, 5)

Secondary scores from docs/GOAL.md. Written by `scripts/score_twin.py`; definitions in its docstring.

## Instrument parent assignment

| Tool | Key instruments | with a key parent | found as instrument | parent right | **end-to-end** | **if found** | lenient if found | control: position only, if found | by method; parent agrees with nearest-by-position? (right/n) |
|---|---|---|---|---|---|---|---|---|---|
| claude | 160 | 122 | 122 | 97 | 0.795 | 0.795 | 0.902 | 0.828 | linked 97/122; agrees 88/96, disagrees 9/26 |
| codex | 160 | 122 | 122 | 92 | 0.754 | 0.754 | 0.852 | 0.828 | linked 92/122; agrees 86/94, disagrees 6/28 |
| gemini | 160 | 122 | 115 | 63 | 0.516 | 0.548 | 0.6 | 0.539 | geometry_nearest 2/11, linked 61/103, via_instrument_chain 0/1; agrees 58/85, disagrees 5/30 |

## Off-page connector pairing (no automatic truth: check the list by hand)

| Tool | Connectors | Pairs | Status counts | Sheet drawing numbers (number, method) |
|---|---|---|---|---|
| claude | 48 | 4 | paired: 8; unpaired: target drawing is not in this sheet set: 36; unpaired: target sheet is in this set but no matching connector was found: 4 | 0=140-1 (inferred_offpage_refs); 1=150-1 (inferred_offpage_refs); 2=160-1 (inferred_offpage_refs); 3=170-1 (inferred_offpage_refs); 4=? (unknown); 5=? (unknown) |
| codex | 48 | 4 | paired: 8; unpaired: target drawing is not in this sheet set: 36; unpaired: target sheet is in this set but no matching connector was found: 4 | 0=140-1 (inferred_offpage_refs); 1=150-1 (inferred_offpage_refs); 2=160-1 (inferred_offpage_refs); 3=170-1 (inferred_offpage_refs); 4=? (unknown); 5=? (unknown) |
| gemini | 48 | 4 | paired: 8; unpaired: no drawing number read from the text: 5; unpaired: target drawing is not in this sheet set: 31; unpaired: target sheet is in this set but no matching connector was found: 4 | 0=140-1 (inferred_offpage_refs); 1=150-1 (inferred_offpage_refs); 2=160-1 (inferred_offpage_refs); 3=170-1 (inferred_offpage_refs); 4=? (unknown); 5=? (unknown) |

### Pairs to check: claude

| Sheet | Connector text | Sheet | Connector text | Method | Description overlap | Other candidates |
|---|---|---|---|---|---|---|
| 0 | MAIN STEAM BY-PASS ACC PID 150-1 | 1 | MSS PID 140-1 (E-1) MAIN STEAM BYPASS | reciprocal_drawing_refs | 1.0 | 0 |
| 0 | FWS TO STM BYPASS FWS PID 170-1 | 3 | FWS TO MAIN STM BYPASS MSS PID 140-1 | reciprocal_drawing_refs | 0.5 | 0 |
| 1 | CND PID 160-1 CONDENSATE SYSTEM | 2 | ACC PID 150-1 (C-12) CONDENSATE RETURN | reciprocal_drawing_refs | 0.5 | 2 |
| 1 | PID 160-1 (F-1) CND RECEIVER TANK VENT | 2 | ACC PID 150-1 ACC VACUUM PMPS | reciprocal_drawing_refs | 0.0 | 2 |

### Pairs to check: codex

| Sheet | Connector text | Sheet | Connector text | Method | Description overlap | Other candidates |
|---|---|---|---|---|---|---|
| 0 | MAIN STEAM BY-PASS ACC PID 150-1 | 1 | MSS PID 140-1 (F-1) MAIN STEAM BYPASS | reciprocal_drawing_refs | 1.0 | 0 |
| 0 | FWS TO STM BYPASS FWS PID 170-1 | 3 | FWS TO MAIN STM BYPASS MSS PID 140-1 | reciprocal_drawing_refs | 0.5 | 0 |
| 1 | CND PID 160-1 CONDENSATE SYSTEM | 2 | ACC PID 150-1 (C-12) CONDENSATE RETURN | reciprocal_drawing_refs | 0.5 | 2 |
| 1 | PID 160-1 (F-1) CND RECEIVER TANK VENT | 2 | ACC PID 150-1 ACC VACUUM PMPS | reciprocal_drawing_refs | 0.0 | 2 |

### Pairs to check: gemini

| Sheet | Connector text | Sheet | Connector text | Method | Description overlap | Other candidates |
|---|---|---|---|---|---|---|
| 0 | MAIN STEAM BY-PASS ACC PID 150-1 | 1 | MSS PID 140-1 (E-1) MAIN STEAM BYPASS | reciprocal_drawing_refs | 1.0 | 0 |
| 0 | FWS TO STM BYPASS FWS PID 170-1 | 3 | FWS TO MAIN STM BYPASS MSS PID 140-1 | reciprocal_drawing_refs | 0.5 | 0 |
| 1 | CND PID 160-1 CONDENSATE SYSTEM | 2 | ACC PID 150-1 (C-12) CONDENSATE RETURN | reciprocal_drawing_refs | 0.5 | 2 |
| 1 | PID 160-1 (F-1) CND RECEIVER TANK VENT | 2 | ACC PID 150-1 ACC VACUUM PMPS | reciprocal_drawing_refs | 0.0 | 2 |
