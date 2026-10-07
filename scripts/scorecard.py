"""Score every run under runs/<label>/<tool>/*.json and write out/scorecard_<label>.md (+ .json).

Totals are micro-averaged (summed true positives over summed counts across drawings), so big drawings weigh more.
Failed or unparseable runs count as zero output, never as skipped, so a tool can't look better by failing quietly.

Usage: python scripts/scorecard.py [--label first-try]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import score_pid2graph as sc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"


def add(acc, part):
    for k in ("tp", "predicted", "in_key"):
        acc[k] = acc.get(k, 0) + part[k]


def finish(acc):
    return sc.prf(acc.get("tp", 0), acc.get("predicted", 0), acc.get("in_key", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="first-try")
    label = ap.parse_args().label
    base = ROOT / "runs" / label
    summary = {}
    for tool_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        agg = {"strict": {"located": {}, "classified": {}}, "rough": {"located": {}, "classified": {}},
               "connections": {}, "by_class": {c: {} for c in sc.SCORED}}
        meta = {"drawings": 0, "failed": 0, "seconds": 0.0, "cost_usd": 0.0, "models": set()}
        for run in sorted(tool_dir.glob("*.json")):
            r = json.loads(run.read_text(encoding="utf-8"))
            d = r["drawing"]
            pred = r.get("prediction") or {"symbols": [], "connections": []}
            s = sc.score(DATA / f"{d}.graphml", pred, DATA / f"{d}.png")
            for t in ("strict", "rough"):
                for k in ("located", "classified"):
                    add(agg[t][k], s[t][k])
            for c in sc.SCORED:
                add(agg["by_class"][c], s["rough"]["by_class"][c])
            add(agg["connections"], s["connections"])
            meta["drawings"] += 1
            meta["failed"] += 0 if r.get("prediction") else 1
            meta["seconds"] += r.get("seconds") or 0
            meta["cost_usd"] += r.get("cost_usd") or 0
            meta["models"].add(str(r.get("model")))
        summary[tool_dir.name] = {
            "drawings": meta["drawings"], "failed_runs": meta["failed"], "models": sorted(meta["models"]),
            "avg_seconds": round(meta["seconds"] / max(meta["drawings"], 1), 1), "cost_usd": round(meta["cost_usd"], 2),
            "strict_located": finish(agg["strict"]["located"]), "strict_classified": finish(agg["strict"]["classified"]),
            "rough_located": finish(agg["rough"]["located"]), "rough_classified": finish(agg["rough"]["classified"]),
            "connections": finish(agg["connections"]),
            "rough_by_class": {c: finish(agg["by_class"][c]) for c in sc.SCORED},
        }

    f = lambda m: f'{m["f1"]:.2f} (P {m["precision"]:.2f} / R {m["recall"]:.2f})'  # noqa: E731
    lines = [f"# Extraction scorecard: `{label}`", "",
             "Scored against PID2Graph OPEN100 answer keys with `scripts/score_pid2graph.py` (rules fixed before any "
             "run; controls in `scripts/test_scorer_controls.py`). F1 with precision/recall.", "",
             "| Tool | Model | Drawings (failed) | Rough: found | Rough: found + right class | Strict (IoU≥0.5): found + right class | Connections | Avg s/drawing | Cost |",
             "|---|---|---|---|---|---|---|---|---|"]
    for tool, s in summary.items():
        lines.append(f'| {tool} | {", ".join(s["models"])} | {s["drawings"]} ({s["failed_runs"]}) | {f(s["rough_located"])} | '
                     f'{f(s["rough_classified"])} | {f(s["strict_classified"])} | {f(s["connections"])} | '
                     f'{s["avg_seconds"]} | ${s["cost_usd"]:.2f} |')
    lines += ["", "## Rough match by class (F1)", "", "| Tool | " + " | ".join(sc.SCORED) + " |",
              "|---|" + "---|" * len(sc.SCORED)]
    for tool, s in summary.items():
        lines.append(f"| {tool} | " + " | ".join(f'{s["rough_by_class"][c]["f1"]:.2f} ({s["rough_by_class"][c]["in_key"]})'
                                                  for c in sc.SCORED) + " |")
    lines += ["", "Numbers in parentheses in the class table are how many of that class the answer keys contain.",
              "Subscription tools show $0.00; their cost is a flat subscription, not per call."]
    out = ROOT / "out"
    (out / f"scorecard_{label}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / f"scorecard_{label}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
