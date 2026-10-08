# Twin-level scores: `r2-tiles-trace` (sheets 6, 7, 8, 9, 10, 11)

Secondary scores from docs/GOAL.md. Written by `scripts/score_twin.py`; definitions in its docstring.

## Instrument parent assignment

| Tool | Key instruments | with a key parent | found as instrument | parent right | **end-to-end** | **if found** | lenient if found | control: position only, if found | by method; parent agrees with nearest-by-position? (right/n) |
|---|---|---|---|---|---|---|---|---|---|
| codex | 190 | 154 | 154 | 134 | 0.87 | 0.87 | 0.929 | 0.857 | geometry_nearest 27/29, linked 107/125; agrees 123/135, disagrees 11/19 |

## Off-page connector pairing (no automatic truth: check the list by hand)

| Tool | Connectors | Pairs | Status counts | Sheet drawing numbers (number, method) |
|---|---|---|---|---|
| codex | 95 | 7 | paired: 14; unpaired: no drawing number read from the text: 31; unpaired: target drawing is not in this sheet set: 35; unpaired: target sheet is in this set but no matching connector was found: 15 | 0=140-1 (inferred_offpage_refs); 1=150-1 (inferred_offpage_refs); 2=160-1 (inferred_offpage_refs); 3=170-1 (inferred_offpage_refs); 4=? (unknown); 5=100-1 (inferred_offpage_refs); 6=100-2 (inferred_offpage_refs); 7=210-1 (inferred_offpage_refs); 8=? (unknown); 9=? (ambiguous); 10=110-1 (inferred_offpage_refs); 11=120-1 (inferred_offpage_refs) |

### Pairs to check: codex

| Sheet | Connector text | Sheet | Connector text | Method | Description overlap | Other candidates |
|---|---|---|---|---|---|---|
| 0 | FWS TO STM BYPASS FWS PID 170-1 | 3 | FWS TO MAIN STM BYPASS MSS PID 140-1 | reciprocal_drawing_refs | 0.5 | 0 |
| 1 | CND PID 160-1 CONDENSATE SYSTEM | 2 | ACC PID 150-1 (C-12) CONDENSATE RETURN | reciprocal_drawing_refs | 0.5 | 2 |
| 11 | RES HEAT REMOVAL SYSTEM RCS PID 100-1 | 5 | RES. HEAT REMOVAL SYSTEM RHRS PID-120-01 | reciprocal_drawing_refs | 0.5 | 3 |
| 1 | PID 160-1 (F-1) CND RECEIVER TANK VENT | 2 | ACC PID 150-1 ACC VACUUM PMPS | reciprocal_drawing_refs | 0.0 | 2 |
| 11 | REACTOR COOLANT SYSTEM RCS PID 100-1 (H-1) | 5 | PID 120-1 (E-1) RHRS | reciprocal_drawing_refs | 0.0 | 3 |
| 11 | RES HEAT REMOVAL SYSTEM RCS PID 100-1 | 5 | PID 120-1 (C-1) RHRS | reciprocal_drawing_refs | 0.0 | 3 |
| 5 | REACTOR COOLANT SYSTEM RCS-PID-100-2 | 6 | PID 100-1 (D-1) RCS | reciprocal_drawing_refs | 0.0 | 0 |
