# Round-3 parent-fix holdout scoring (docs/GOAL.md round 3). Codex M3 symbols, scored once per holdout.
Set-Location (Split-Path $PSScriptRoot -Parent)
$A = "6,7,8,9,10,11"
foreach ($rule in "along_line", "linked") {
    python scripts/build_twin.py --label runs/r2-tiles-trace --tools codex --sheets $A --holdout-ok --parent-rule $rule --out "out/twin/r3-hA-$rule/codex" | Select-Object -Last 1
    "== holdout A, rule $rule"
    python scripts/score_twin.py --label "out/twin/r3-hA-$rule" --sheets $A --holdout-ok | Select-String "^\| codex"
}
$env:PID2GRAPH_SET = "Dataset PID"
$B = "23,44,62,78,109,111,122,143,149,158,209,224,290,345,363,366,382,400,494,496"
$I = "data/external/pid2graph/PID2Graph/Complete/Dataset PID"
foreach ($rule in "along_line", "linked") {
    python scripts/build_twin.py --label runs/hb-tiles-trace --tools codex --sheets $B --holdout-ok --images $I --parent-rule $rule --out "out/twin/r3-hB-$rule/codex" | Select-Object -Last 1
    "== holdout B, rule $rule"
    python scripts/score_twin.py --label "out/twin/r3-hB-$rule" --sheets $B --holdout-ok --images $I | Select-String "^\| codex"
}
