# Interactive tour: verification report (proof of concept)

Proof of concept, not reviewed by an operator. Passing these checks means the drawing agrees with the repository's model, exports and replay files and is legible by these measures; it does not mean an operator finds it useful, and the geometry is placeholder.

Result: 37 pass, 5 informational, 0 fail, of 42 checks. Written by `node drafts/interactive-tour/verify.mjs`.

| Group | Check | Status | Result |
|---|---|---|---|
| A | streams_vs_model | pass | 13 drawn process lines; 13 of 13 model streams matched one to one; 0 model streams not drawn; 0 drawn lines with no model stream |
| A | stream_ends_on_nozzles | pass | 13 of 13 lines start on a nozzle of their model 'from' unit and end on a nozzle of their 'to' unit (mount found by the kit audit's own search; battery-limit ends land on a battery-limit post) |
| A | streams_vs_pid_graph | pass | 13 of 13 drawn streams match exactly one connection in the generated P&ID graph (data/te_pid/key.json); the sheets are drawn from the same model, so this is a round-trip agreement, not independent plant evidence |
| A | utilities_inferred | pass | 5 inferred utility lines, each from a final element whose own description names cooling water or steam; the P&ID sheets draw 6 utility connections as drafting additions (R-101: CW PID 901-1 / COOLING WATER SUPPLY; R-101: CW PID 901-1 / COOLING WATER RETURN; E-101: CW PID 901-1 / COOLING WATER SUPPLY; E-101: CW PID 901-1 / COOLING WATER RETURN; C-101: LS PID 902-1 / LOW PRESSURE STEAM; C-101: LS PID 902-1 / CONDENSATE RETURN). Not drawn here: the stripper's condensate return (no final element names it). |
| A | tags_in_ignition_and_pi | pass | 37 tags drawn as markers; 37 found in the Ignition gateway tag import, 37 in the PI AF staging sheet; the paths on each purpose card equal the exports' |
| A | model_items_not_shown | info | reverse direction: 37 of 37 model tags shown; Ignition has 53 tag instances (16 not shown), PI AF 37 attributes (0 not shown) |
| A | valve_symbols | pass | 10 of 10 final elements that sit on a drawn line have a valve symbol on it |
| A | alarm_limits_from_gateway | pass | alarm setpoints on the page equal out/ignition/gateway/build_meta.json for all 37 tags (PI-107, TI-109 carry published setpoints) |
| A | replay_values_from_file | pass | 69120 replay values on the page compared with the raw Braatz files; 0 differ beyond six significant figures |
| A | not_connected_tags | info | tags with no replay source, shown as not connected and never animated: SC-212 |
| B | kit_clearance | pass | clearance: 0 |
| B | kit_terminals | pass | terminals: 0 |
| B | kit_loose_ends | pass | loose ends: 0 |
| B | kit_folds | pass | folds: 0 |
| B | kit_crowding | pass | crowding: 0 |
| B | kit_self_overlap | pass | self overlap: 0 |
| B | kit_wobble | pass | wobble: 0 |
| B | kit_stand_in_shapes | pass | stand in shapes: 0 |
| B | kit_unsupported_solids | pass | unsupported solids: 0 |
| B | kit_hanging_tubes | pass | hanging tubes: 0 |
| B | kit_sunk_pairs | pass | sunk pairs: 0 |
| B | kit_depth_order | pass | depth order: 0 |
| B | kit_items_without_shape | pass | items without shape: 0 |
| B | kit_allowed_pairs | info | explicitly excused depth pairs (a valve body against chunks of its own pipe, which meet it face to end cap): 0 |
| B | kit_audit | pass | anatomy kit audit over 589 drawn items, 28 tube runs, 314 solids: 0 problems |
| D | fault6_alarm_shown | pass | the raw d06_te.dat first crosses a published PI-107 setpoint at sample 258 (+294 min after the fault starts; 2897.3 > 2895 kPa g); "Jump to the first alarm" lands on sample 258, the alarm list shows PI-107, the marker ring is "alarm", the pill reads "PI-107 2,897 kPa g · high alarm 2,895" |
| D | no_alarm_one_sample_before | pass | one sample earlier (257) the page shows 0 alarms |
| D | pulses_move_forward | pass | 18 of 18 lines' pulses advance from the line's start (its model 'from' end) toward its end in 0.8 s |
| D | arrows_point_downstream | pass | 62 of 62 chevrons point along their line's path direction |
| D | loto_one_point | pass | isolating the A feed block valve: the model says S1 stop(s); the page greys S1 and the pulses stand still on S1; the rest keep moving |
| D | loto_downstream_stops | pass | isolating every feed block valve and the K-101 motor stops all 13 process lines (computed: 0 flowing; pulses moving on the page: 0); the readout lists the 6 sources still not isolated (outlets, agitator, utilities) |
| D | loto_compressor_still_drives_recycle | pass | with only the four feeds isolated the K-101 motor still drives the recycle loop: S5, S6, S7, S7b, S8, S8b, S9, S10, S11 keep flowing (the readout does not call the unit isolated) |
| D | keyboard | pass | arrow keys on the focused figure: U-100, then R-101; Escape returns to the overview (yes) |
| D | controls_named | pass | 0 visible buttons or inputs without an accessible name |
| C | label_overlaps | pass | 36 page states (2 themes × 390 and 1440 px × 9 views): 0 with overlapping labels |
| C | labels_off_geometry | pass | no label covers more than 10% of its box with drawn, undimmed pipes or machines (largest share 9.1%); 0 states over the limit |
| C | min_font_size | pass | smallest visible text 12 px (minimum 12 px) in every state |
| C | contrast_wcag_aa | pass | lowest text contrast 6.41:1 over 4366 visible text runs (WCAG AA for normal text: 4.5:1) |
| C | labels_inside_figure | pass | labels outside the figure: 0 states |
| C | no_horizontal_scroll | pass | pages wider than the viewport: 0 states |
| C | labels_without_room | info | labels the layout had no room for (hidden rather than overlapped; the same information stays on the purpose card): 0 of 36 states |
| E | hygiene | info | 17 files scanned for local paths (TOUR_DENY_TERMS not set: deny-term part skipped): 0 hits |

Groups: A topology and tags against the raw model, P&ID key, Ignition and PI AF exports and replay files; B the anatomy kit geometry audit; C legibility in headless Chrome; D behaviour; E publication hygiene.

## Details

**model_items_not_shown**

- model tags not shown: none
- Ignition instances not shown: AI-123-B, AI-123-C, AI-123-D, AI-123-E, AI-123-F, AI-129-B, AI-129-C, AI-129-D, AI-129-E, AI-129-F, AI-129-G, AI-129-H, AI-137-E, AI-137-F, AI-137-G, AI-137-H
- PI AF attributes not shown: none

## Review stills

- [overview-390-dark.jpg](../shots/overview-390-dark.jpg)
- [reactor-390-dark.jpg](../shots/reactor-390-dark.jpg)
- [fault6-alarm-390-dark.jpg](../shots/fault6-alarm-390-dark.jpg)
- [loto-mockup-390-dark.jpg](../shots/loto-mockup-390-dark.jpg)
- [overview-1440-dark.jpg](../shots/overview-1440-dark.jpg)
- [reactor-1440-dark.jpg](../shots/reactor-1440-dark.jpg)
- [fault6-alarm-1440-dark.jpg](../shots/fault6-alarm-1440-dark.jpg)
- [loto-mockup-1440-dark.jpg](../shots/loto-mockup-1440-dark.jpg)
- [overview-390-light.jpg](../shots/overview-390-light.jpg)
- [reactor-390-light.jpg](../shots/reactor-390-light.jpg)
- [fault6-alarm-390-light.jpg](../shots/fault6-alarm-390-light.jpg)
- [loto-mockup-390-light.jpg](../shots/loto-mockup-390-light.jpg)
- [overview-1440-light.jpg](../shots/overview-1440-light.jpg)
- [reactor-1440-light.jpg](../shots/reactor-1440-light.jpg)
- [fault6-alarm-1440-light.jpg](../shots/fault6-alarm-1440-light.jpg)
- [loto-mockup-1440-light.jpg](../shots/loto-mockup-1440-light.jpg)
- [loto-all-feeds-and-motor-1440-dark.jpg](../shots/loto-all-feeds-and-motor-1440-dark.jpg)
