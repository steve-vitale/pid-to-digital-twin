# Round-3 confidence-marker holdout scoring (docs/GOAL.md round 3). Each label scored once per holdout.
Set-Location (Split-Path $PSScriptRoot -Parent)
foreach ($l in "v2-named-fields", "r2-tiles-2x2", "r2-trace", "r2-tiles-trace") {
    "=== holdout A: $l"
    python scripts/score_triage.py --label $l --split holdout-a --holdout-ok | Select-String "^\| (claude|codex|gemini) \|"
}
$env:PID2GRAPH_SET = "Dataset PID"
foreach ($l in "hb-v2", "hb-tiles-2x2", "hb-trace", "hb-tiles-trace") {
    "=== holdout B: $l"
    python scripts/score_triage.py --label $l --split holdout-b --holdout-ok | Select-String "^\| (claude|codex|gemini) \|"
}
