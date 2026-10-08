# Round-4 scan robustness runs for one tool (docs/GOAL.md, round 4). Each level is run once.
# Usage: powershell -File scripts/run_scan_robustness.ps1 -Tool claude|codex
param([Parameter(Mandatory = $true)][string]$Tool)
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
$holdoutA = "6,7,8,9,10,11"
foreach ($level in 1, 2, 3) {
    $env:PID2GRAPH_SET = "PID2Graph OPEN100 scan-L$level"
    "== $Tool L$level tiles"
    python scripts/run_extraction.py --tool $Tool --prompt extraction/prompt_v2.md --drawings $holdoutA --label "r4-scan-L$level-tiles" --tiles 2x2 --overlap 0.15
    "== $Tool L$level trace"
    python scripts/trace_connections.py --src-label "r4-scan-L$level-tiles" --tool $Tool --drawings $holdoutA --label "r4-scan-L$level-trace"
}
Remove-Item Env:PID2GRAPH_SET
"== $Tool done"
