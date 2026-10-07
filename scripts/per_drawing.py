"""Per-drawing rough-located F1 for one tool across one or more run labels (spot inconsistent drawings).

Usage: python scripts/per_drawing.py gemini first-try repeat-v1 v2-named-fields
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import score_pid2graph as sc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"

tool, labels = sys.argv[1], sys.argv[2:]
print("drawing " + "".join(f"{l:>18}" for l in labels))
for d in range(12):
    row = []
    for label in labels:
        f = ROOT / "runs" / label / tool / f"{d}.json"
        if not f.exists():
            row.append("-")
            continue
        pred = json.loads(f.read_text(encoding="utf-8")).get("prediction") or {"symbols": []}
        s = sc.score(DATA / f"{d}.graphml", pred, DATA / f"{d}.png")
        row.append(f'{s["rough"]["located"]["f1"]:.2f}')
    print(f"{d:>7} " + "".join(f"{v:>18}" for v in row))
