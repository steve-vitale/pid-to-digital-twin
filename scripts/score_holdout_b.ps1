# Round-2 holdout B scoring (docs/GOAL.md addendum): apply the tracer to the M0 and M1 outputs, then score
# M0-M3 once on the 20 sealed Dataset-P&ID drawings.
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PID2GRAPH_SET = "Dataset PID"
$B = "23,44,62,78,109,111,122,143,149,158,209,224,290,345,363,366,382,400,494,496"
foreach ($t in "claude", "codex", "gemini") {
    python scripts/trace_connections.py --src-label hb-v2 --tool $t --drawings $B --label hb-trace --mode replace | Select-Object -Last 1
    python scripts/trace_connections.py --src-label hb-tiles-2x2 --tool $t --drawings $B --label hb-tiles-trace --mode replace | Select-Object -Last 1
}
foreach ($l in "hb-v2", "hb-tiles-2x2", "hb-trace", "hb-tiles-trace") {
    "=== $l (holdout B)"
    python scripts/scorecard.py --label $l | Select-String "^\| (claude|codex|gemini) \|" | ForEach-Object { ($_.Line -split "\|")[1, 3, 4, 5, 8] -join " | " }
}
