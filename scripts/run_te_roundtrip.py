"""Run the TE round trip on the current generated sheets: the declared method, every condition and replicate.

The method is frozen (docs/EVALUATION.md §6): 2x2 tiles with 0.15 overlap and extraction/prompt_v2.md, then
scripts/trace_connections.py with its defaults. Clean sheets: 5 replicates per model. Old-scan copies L1-L3 made by
scripts/degrade_scans.py (same levels and seeding as round 4): 3 replicates per model per level.

Labels: runs/<prefix>-<cond>-tiles-r<n>/ (raw tile replies) and runs/<prefix>-<cond>-trace-r<n>/ (what is scored).
The default prefix "tec" keeps revision C's runs apart from revision A's ("te"), which read different sheets.
Revision C's sheets are archived in data/te_pid/rev-c (journal entry 61); its runs were made with --sheets
data/te_pid/rev-c. A new revision needs its own --sheets and --prefix.
A finished run is skipped, so the script can be re-run after an interruption. Model calls go through the Codex and
Claude Code CLIs on their subscriptions; run_extraction.py records model, prompt hash, image hash and time per run.

Usage: python scripts/run_te_roundtrip.py --tool codex|claude --sheets data/te_pid/rev-c [--model M] [--prefix tec]
       [--conditions clean,L1,L2,L3]
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEETS = "101,102,103"
REPLICATES = {"clean": 5, "L1": 3, "L2": 3, "L3": 3}
MODELS = {"codex": "gpt-6.1-sol", "claude": "claude-opus-5-5"}


def sheet_dir(cond, sheets):
    return sheets if cond == "clean" else f"{sheets}/scan-{cond}"


def done(label, tool):
    d = ROOT / "runs" / label / tool
    return all((d / f"{s}.json").exists() for s in SHEETS.split(","))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tool", choices=list(MODELS), required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--prefix", default="tec")
    ap.add_argument("--sheets", required=True, help="the sheet directory the runs read, e.g. data/te_pid/rev-c")
    ap.add_argument("--conditions", default="clean,L1,L2,L3")
    a = ap.parse_args()
    model = a.model or MODELS[a.tool]
    if not all((ROOT / sheet_dir(c, a.sheets) / "101.png").exists() for c in ("L1", "L2", "L3")):
        subprocess.run([sys.executable, "scripts/degrade_scans.py", "--src", a.sheets, "--drawings", SHEETS,
                        "--dest", f"{a.sheets}/scan"], cwd=ROOT, check=True)
    for cond in a.conditions.split(","):
        env = dict(os.environ, PID_SHEETS_DIR=sheet_dir(cond, a.sheets))
        for rep in range(1, REPLICATES[cond] + 1):
            tiles, trace = f"{a.prefix}-{cond}-tiles-r{rep}", f"{a.prefix}-{cond}-trace-r{rep}"
            if not done(tiles, a.tool):
                print(f"== {a.tool} {cond} r{rep}: tiles", flush=True)
                subprocess.run([sys.executable, "scripts/run_extraction.py", "--tool", a.tool, "--model", model,
                                "--prompt", "extraction/prompt_v2.md", "--drawings", SHEETS, "--label", tiles,
                                "--tiles", "2x2", "--overlap", "0.15"], cwd=ROOT, env=env, check=False)
            if done(tiles, a.tool) and not done(trace, a.tool):
                print(f"== {a.tool} {cond} r{rep}: trace", flush=True)
                subprocess.run([sys.executable, "scripts/trace_connections.py", "--src-label", tiles, "--tool", a.tool,
                                "--drawings", SHEETS, "--label", trace], cwd=ROOT, env=env, check=False)
            print(f"   {cond} r{rep}: {'done' if done(trace, a.tool) else 'INCOMPLETE'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
