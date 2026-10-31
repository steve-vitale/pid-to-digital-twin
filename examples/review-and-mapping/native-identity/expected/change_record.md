# Review applied: native-identity/model.json

Reviewer: Fictional example reviewer · Date: 2026-10-30

Applied: 3 · Unchanged: 0 · Refused: 0 · Need a change review: 0

## Applied

| Item | Decision | Changes | Screen | Alarm priority | Notes |
|---|---|---|---|---|---|
| PT-900 | corrected | tag: 'PT-900' → 'PT-902' |  |  | Fictional identity correction; no source or signal-address change |
| PV-900 | corrected | tag: 'PV-900' → 'PV-902' |  |  | Fictional identity correction; preserve recorded control relationships |
| TT-900 | confirmed |  |  |  | Fictional confirmation; unreadable alarm metadata stays unresolved |

### Native identity: PT-900 → PT-902

not updated: reconcile authored drawing/display layouts and external loop/mapping records; regenerate dependent outputs and refresh context

- `controllers[0].measurement`: `PT-900` → `PT-902`
- `controllers[1].measurement`: `PT-900` → `PT-902`
- `interlocks[0].measurement`: `PT-900` → `PT-902`
- `limits[0].tag`: `PT-900` → `PT-902`
- `line_layers.networks[0].members[0]`: `PT-900` → `PT-902`
- `line_layers.instrument_lines[0].from`: `PT-900` → `PT-902`

### Native identity: PV-900 → PV-902

not updated: reconcile authored drawing/display layouts and external loop/mapping records; regenerate dependent outputs and refresh context

- `controllers[0].output.final_element`: `PV-900` → `PV-902`
- `controllers[1].output.split_range[0]`: `PV-900` → `PV-902`
- `interlocks[0].final_element`: `PV-900` → `PV-902`
- `limits[1].tag`: `PV-900` → `PV-902`
- `line_layers.networks[0].members[1]`: `PV-900` → `PV-902`
- `line_layers.segments[0].to`: `PV-900` → `PV-902`
- `line_layers.actuator_stems[0].from`: `PV-900` → `PV-902`
