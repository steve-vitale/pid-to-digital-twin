# Round-4 scoring (docs/GOAL.md, round 4): each level scored once, plus the isolating comparison at L3
# (the L3 symbols traced on the CLEAN image, to separate the models' loss from the tracer's).
Set-Location (Split-Path $PSScriptRoot -Parent)
foreach ($tool in "codex", "claude") {
    python scripts/trace_connections.py --src-label r4-scan-L3-tiles --tool $tool --drawings 6,7,8,9,10,11 --label r4-scan-L3-symbols-clean-trace | Out-Null
}
python scripts/scorecard.py --label r4-scan-L3-symbols-clean-trace --split holdout-a | Out-Null
foreach ($level in 1, 2, 3) {
    $env:PID2GRAPH_SET = "PID2Graph OPEN100 scan-L$level"
    python scripts/scorecard.py --label "r4-scan-L$level-tiles" --split holdout-a | Out-Null
    python scripts/scorecard.py --label "r4-scan-L$level-trace" --split holdout-a | Out-Null
}
Remove-Item Env:PID2GRAPH_SET
"scored"
