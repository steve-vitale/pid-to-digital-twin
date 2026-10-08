# Round-2 holdout model runs for one tool (docs/GOAL.md addendum). Each method is scored on each holdout once.
# Usage: powershell -File scripts/run_holdouts.ps1 -Tool claude|codex|gemini
param([Parameter(Mandatory = $true)][string]$Tool)
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
$holdoutA = "6,7,8,9,10,11"
$holdoutB = "23,44,62,78,109,111,122,143,149,158,209,224,290,345,363,366,382,400,494,496"
$common = @("--tool", $Tool, "--prompt", "extraction/prompt_v2.md", "--gemini-cap", "25")

"== $Tool M1 tiling, holdout A"
python scripts/run_extraction.py @common --drawings $holdoutA --label r2-tiles-2x2 --tiles 2x2 --overlap 0.15

$env:PID2GRAPH_SET = "Dataset PID"
"== $Tool M0 baseline, holdout B"
python scripts/run_extraction.py @common --drawings $holdoutB --label hb-v2
"== $Tool M1 tiling, holdout B"
python scripts/run_extraction.py @common --drawings $holdoutB --label hb-tiles-2x2 --tiles 2x2 --overlap 0.15
Remove-Item Env:PID2GRAPH_SET
"== $Tool done"
