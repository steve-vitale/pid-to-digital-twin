"""Re-merge stored tile replies without calling any model again.

A tiled run record keeps every tile's raw parsed reply, so the merge (scripts/tiling.py) can be re-applied, or the
whole-sheet "overview" connections added, from what is already on disk. Model output is never changed, only the
deterministic post-processing. The new record says where it came from.

Usage:
  python scripts/remerge_tiles.py --from r2-tiles-2x2 --to r2-tiles-2x2-ov --overview round1-v2-named-fields [--tools claude,gemini] [--drawings 0,1,2,3,4,5]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiling  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--overview", default=None, help="label of whole-sheet runs (same tool and prompt)")
    ap.add_argument("--tools", default="claude,codex,gemini")
    ap.add_argument("--drawings", default="0,1,2,3,4,5")
    a = ap.parse_args()
    for tool in a.tools.split(","):
        for d in a.drawings.split(","):
            src = RUNS / a.src / tool / f"{d}.json"
            if not src.exists():
                continue
            r = json.loads(src.read_text(encoding="utf-8"))
            t = r["tiling"]
            preds = [x["prediction"] for x in r["tiles"]]
            boxes = [tuple(x["box_px"]) for x in r["tiles"]]
            w, h = t["sheet_px"]
            merged, stats = tiling.merge_tiles(preds, boxes, w, h) if any(preds) else (None, {})
            t = dict(t, merge_params=tiling.MERGE_PARAMS, merge_stats=stats, remerged_from=a.src)
            out = dict(r, label=a.dst, prediction=merged, tiling=t)
            if a.overview:
                ov_path = RUNS / a.overview / tool / f"{d}.json"
                ov = json.loads(ov_path.read_text(encoding="utf-8"))
                if ov.get("prompt_sha256") != r["prompt_sha256"] or ov.get("image_sha256") != r["image_sha256"]:
                    sys.exit(f"{ov_path}: different prompt or image from the tiled run")
                t["overview"] = {"source": str(ov_path.relative_to(ROOT)).replace("\\", "/"),
                                 **{k: ov.get(k) for k in ("prompt_sha256", "model", "seconds", "cost_usd", "error")}}
                if merged and ov.get("prediction"):
                    out["prediction"], t["overview"]["stats"] = tiling.add_overview_links(merged, ov["prediction"])
                # Price the second view: its time and cost are added (as if run one after the other).
                out["seconds"] = round((r.get("seconds") or 0) + (ov.get("seconds") or 0), 1)
                if ov.get("cost_usd") is not None:
                    out["cost_usd"] = round((r.get("cost_usd") or 0) + ov["cost_usd"], 4)
            dst = RUNS / a.dst / tool / f"{d}.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(json.dumps(out, indent=1), encoding="utf-8")
            print(f"{tool} {d}: {len((out['prediction'] or {}).get('symbols', []))} symbols, "
                  f"{len((out['prediction'] or {}).get('connections', []))} links "
                  f"{t.get('overview', {}).get('stats', '')}")


if __name__ == "__main__":
    main()
