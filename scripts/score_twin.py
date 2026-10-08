"""Twin-level scores (docs/GOAL.md, secondary): instrument parent assignment and off-page pairing.

Parent-assignment accuracy
    Answer-key parent of an instrument = the nearest scored NON-instrument asset reachable from it through
    connector / crossing / arrow nodes only (fewest hops, then closest centre). Instruments with no such asset in
    the key (e.g. linked only to other instruments) have no key parent and are counted separately.
    Twin symbols are matched to key symbols with the frozen scorer's match() at rough IoU >= 0.1 (any class).
    A key instrument scores as correct when its matched twin item is an instrument whose parent symbol matches the
    key parent. Reported two ways:
      end-to-end   correct / key instruments that have a key parent (detection misses count as wrong)
      if matched   correct / those whose twin counterpart was found as an instrument
    "lenient" also accepts any non-instrument asset the key links the instrument to, not only the nearest one.

Off-page pairing
    The answer keys carry no text, so there is no automatic truth for which connectors pair. This reports counts
    and lists every pair for a person to check. No score is invented.

Usage: python scripts/score_twin.py --label round1-v2-named-fields [--sheets 0,1,2,3,4,5] [--tools claude,codex]
Reads out/twin/<label>/<tool>/plant_model.json; writes out/twin/<label>/twin_scores.{json,md}.
"""
import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import score_pid2graph as sc  # noqa: E402  (imported, never edited: the grader is frozen)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
DEV_SHEETS = {str(i) for i in range(6)}


def key_parents(nodes, adj):
    """{instrument key id: (nearest parent or None, set of all reachable non-instrument assets)}."""
    out = {}
    for kid, n in nodes.items():
        if n["class"] != "instrumentation":
            continue
        seen, frontier, level, found = {kid}, [kid], 0, []
        while frontier:
            level += 1
            nxt = []
            for cur in frontier:
                for m in adj[cur]:
                    if m in seen:
                        continue
                    seen.add(m)
                    cls = nodes[m]["class"]
                    if cls in sc.SCORED and cls != "instrumentation":
                        found.append((level, m))
                    elif cls in sc.PASS_THROUGH:
                        nxt.append(m)
            frontier = nxt
        if not found:
            out[kid] = (None, set())
            continue
        cx, cy = sc.centre(n["box"])
        best = min(found, key=lambda f: (f[0], math.hypot(sc.centre(nodes[f[1]]["box"])[0] - cx,
                                                          sc.centre(nodes[f[1]]["box"])[1] - cy)))
        out[kid] = (best[1], {m for _, m in found})
    return out


def gap(a, b):
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy)


def sheet_items(model, sheet):
    """Every twin item with an appearance on this sheet, keyed by the extraction's symbol id."""
    items = {}
    for kind in ("units", "instruments", "line_items", "offpage_connectors"):
        for it in model[kind]:
            for p in it["provenance"]:
                if p["sheet"] == sheet:
                    items[p["symbol"]] = (it, p)
    return items


def score_parents(model, sheets, images_dir):
    tot = Counter()
    by_method, by_agree = {}, {}
    for sheet in sheets:
        nodes, adj = sc.load_key(DATA / f"{sheet}.graphml", *sc.png_size(Path(images_dir) / f"{sheet}.png"))
        keys = {k: v for k, v in nodes.items() if v["class"] in sc.SCORED}
        items = sheet_items(model, sheet)
        preds = [{"id": sym, "class": p["class"], "box": p["box_0_1000"]} for sym, (it, p) in items.items()]
        located = sc.match(preds, keys, False, sc.THRESHOLDS["rough"])
        key_to_pred = {k: p for p, k in located.items()}
        for kid, (kp, linked) in key_parents(nodes, adj).items():
            tot["key_instruments"] += 1
            if kp is None:
                tot["key_instruments_without_key_parent"] += 1
                continue
            tot["with_key_parent"] += 1
            sym = key_to_pred.get(kid)
            if sym is None:
                tot["missed_by_twin"] += 1
                continue
            it, _ = items[sym]
            if it["class"] != "instrumentation":
                tot["found_but_not_as_instrument"] += 1
                continue
            tot["matched"] += 1
            # Control: parent = nearest non-instrument twin symbol by position alone, ignoring connections.
            # If the connection-based parent can't beat this, the extracted links add nothing to attachment.
            own_box = items[sym][1]["box_0_1000"]
            others = [s for s, (o, _) in items.items() if o["class"] != "instrumentation"]
            if others and located.get(min(others, key=lambda s: gap(items[s][1]["box_0_1000"], own_box))) == kp:
                tot["control_geometry_only_correct"] += 1
            method = it["parent_method"]
            m = by_method.setdefault(method, Counter())
            m["n"] += 1
            agree = "agrees_with_position" if it.get("parent_agrees_with_position") else "disagrees_with_position"
            a = by_agree.setdefault(agree, Counter())
            a["n"] += 1
            src = it.get("parent_source")
            if not src:
                tot["twin_no_parent"] += 1
                continue
            mp = located.get(src["symbol"])
            if mp is None:
                tot["twin_parent_not_in_key"] += 1
            elif mp == kp:
                tot["correct"] += 1
                tot["correct_lenient"] += 1
                m["correct"] += 1
                a["correct"] += 1
            elif mp in linked:
                tot["correct_lenient"] += 1
                tot["wrong_but_linked"] += 1
            else:
                tot["wrong_parent"] += 1
    r = lambda a, b: round(a / b, 3) if b else None  # noqa: E731
    return {**dict(tot),
            "accuracy_end_to_end": r(tot["correct"], tot["with_key_parent"]),
            "accuracy_if_matched": r(tot["correct"], tot["matched"]),
            "lenient_accuracy_if_matched": r(tot["correct_lenient"], tot["matched"]),
            "control_geometry_only_if_matched": r(tot["control_geometry_only_correct"], tot["matched"]),
            "by_parent_method": {k: {**dict(v), "accuracy": r(v["correct"], v["n"])} for k, v in by_method.items()},
            "by_position_agreement": {k: {**dict(v), "accuracy": r(v["correct"], v["n"])}
                                      for k, v in by_agree.items()}}


def offpage(model):
    s = model["summary"]
    return {"connectors": s["offpage_connectors"], "pairs": s["offpage_pairs"], "status": s["offpage_status"],
            "sheet_drawing_numbers": s["sheet_drawing_numbers"],
            "pair_list": [{k: p[k] for k in ("sheet_a", "text_a", "sheet_b", "text_b", "method",
                                              "description_similarity", "alternatives")}
                          for p in model["offpage_pairs"]]}


def main_for(dirs, sheets, images_dir, out_dir=None, holdout_ok=False):
    outside = [s for s in sheets if s not in DEV_SHEETS]
    if outside and not holdout_ok:
        sys.exit(f"refusing to score sheets {outside}: outside the development set (docs/GOAL.md)")
    results = {}
    for d in dirs:
        model = json.loads((Path(d) / "plant_model.json").read_text(encoding="utf-8"))
        results[Path(d).name] = {"parents": score_parents(model, sheets, images_dir), "offpage": offpage(model)}
    out_dir = Path(out_dir) if out_dir else Path(dirs[0]).parent
    (out_dir / "twin_scores.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    lines = [f"# Twin-level scores: `{out_dir.name}` (sheets {', '.join(sheets)})", "",
             "Secondary scores from docs/GOAL.md. Written by `scripts/score_twin.py`; definitions in its docstring.",
             "", "## Instrument parent assignment", "",
             "| Tool | Key instruments | with a key parent | found as instrument | parent right | "
             "**end-to-end** | **if found** | lenient if found | control: position only, if found | "
             "by method; parent agrees with nearest-by-position? (right/n) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for tool, r in results.items():
        p = r["parents"]
        meth = ", ".join(f'{k} {v.get("correct", 0)}/{v["n"]}' for k, v in sorted(p["by_parent_method"].items()))
        meth += "; " + ", ".join(f'{k.replace("_with_position", "")} {v.get("correct", 0)}/{v["n"]}'
                                 for k, v in sorted(p["by_position_agreement"].items()))
        lines.append(f'| {tool} | {p.get("key_instruments", 0)} | {p.get("with_key_parent", 0)} | '
                     f'{p.get("matched", 0)} | {p.get("correct", 0)} | {p["accuracy_end_to_end"]} | '
                     f'{p["accuracy_if_matched"]} | {p["lenient_accuracy_if_matched"]} | '
                     f'{p["control_geometry_only_if_matched"]} | {meth} |')
    lines += ["", "## Off-page connector pairing (no automatic truth: check the list by hand)", "",
              "| Tool | Connectors | Pairs | Status counts | Sheet drawing numbers (number, method) |",
              "|---|---|---|---|---|"]
    for tool, r in results.items():
        o = r["offpage"]
        st = "; ".join(f"{k}: {v}" for k, v in sorted(o["status"].items()))
        dn = "; ".join(f"{k}={v[0] or '?'} ({v[1]})" for k, v in o["sheet_drawing_numbers"].items())
        lines.append(f'| {tool} | {o["connectors"]} | {o["pairs"]} | {st} | {dn} |')
    for tool, r in results.items():
        lines += ["", f"### Pairs to check: {tool}", "", "| Sheet | Connector text | Sheet | Connector text | "
                  "Method | Description overlap | Other candidates |", "|---|---|---|---|---|---|---|"]
        for p in r["offpage"]["pair_list"]:
            lines.append(f'| {p["sheet_a"]} | {p["text_a"]} | {p["sheet_b"]} | {p["text_b"]} | {p["method"]} | '
                         f'{p["description_similarity"]} | {p["alternatives"]} |')
    (out_dir / "twin_scores.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:4 + 2 + 2 + len(results)]))
    print(f"wrote {out_dir / 'twin_scores.md'}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="twin label under out/twin/ (or a path to it)")
    ap.add_argument("--sheets", default="0,1,2,3,4,5")
    ap.add_argument("--tools", default="")
    ap.add_argument("--images", default=str(DATA))
    ap.add_argument("--holdout-ok", action="store_true", help="allow sheets outside 0-5 (the one holdout run)")
    args = ap.parse_args()
    base = Path(args.label)
    base = base if base.is_dir() else ROOT / "out" / "twin" / args.label
    tools = {t for t in args.tools.split(",") if t}
    dirs = [d for d in sorted(base.iterdir()) if (d / "plant_model.json").exists() and (not tools or d.name in tools)]
    main_for(dirs, [s.strip() for s in args.sheets.split(",") if s.strip()], args.images, base, args.holdout_ok)


if __name__ == "__main__":
    main()
