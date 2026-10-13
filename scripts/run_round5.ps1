# Round-5 replicate runs (docs/GOAL.md round 5): the declared method M3, five fresh runs per tool per set.
# Usage: powershell -File scripts/run_round5.ps1 -Tool claude|codex -Set holdout-a|dexpi [-Reps 1,2,3,4,5]
# Already-finished drawings are skipped by run_extraction.py, so an interrupted run can be resumed; a failed
# drawing is kept as a failure (scored as zero), never re-run to replace it.
param([Parameter(Mandatory = $true)][string]$Tool, [Parameter(Mandatory = $true)][string]$Set,
      [int[]]$Reps = @(1, 2, 3, 4, 5))
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($Set -eq "holdout-a") {
    $drawings = "6,7,8,9,10,11"; $prefix = "r5-hA"
    Remove-Item Env:PID_DATA_DIR -ErrorAction SilentlyContinue
} elseif ($Set -eq "dexpi") {
    $drawings = "dexpi-c01,dexpi-c02,dexpi-c03,dexpi-c08a,dexpi-c08b"; $prefix = "r5-dx"
    $env:PID_DATA_DIR = "data/external/dexpi/sheets"   # built by: python scripts/adapt_dexpi.py fetch; ... build
} else { throw "unknown set $Set" }
foreach ($k in $Reps) {
    "== $Tool $Set replicate $k"
    python scripts/run_extraction.py --tool $Tool --prompt extraction/prompt_v2.md --drawings $drawings `
        --label "$prefix-rep$k-tiles" --tiles 2x2 --overlap 0.15
    python scripts/trace_connections.py --src-label "$prefix-rep$k-tiles" --tool $Tool --drawings $drawings `
        --label "$prefix-rep$k-trace" --mode replace | Select-Object -Last 1
}
