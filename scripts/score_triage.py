"""Score the round-3 risk rating (docs/GOAL.md, "Round 3", Goal 1), and fit it on the development drawings.

An output item is "right" when:
  - symbol: the frozen scorer's rough match (IoU >= 0.1, greedy one-to-one, class must agree) pairs it with a key
    symbol of the same class (score_pid2graph.match(..., need_class=True, 0.1));
  - link: both ends are located by the scorer's class-free rough match and the key's asset-link set contains the pair
    (exactly how score_pid2graph.score credits a connection). Duplicate links count once, self-links are dropped.
Everything else the run output is an error. Missed key items are NOT counted: a rating can only rank what was output.

Metrics (pre-registered in docs/GOAL.md), pooled over the split's drawings, per tool:
  1. errors caught in the riskiest 10 / 20 / 30% of items, for the risk rating, for the model's self-confidence
     ordering (link confidence = the lower endpoint confidence, as build_twin.py does) and for a random order
     (expected value = the percentage itself). Ties are broken at random, in expectation.
  2. green precision (share of green items that are right) and green share (share of all items that are green);
  3. error rate by tier (green / amber / red).

Usage:
    python scripts/score_triage.py --label r2-tiles-trace --split dev                 # all tools
    python scripts/score_triage.py --fit                                             # refit on dev, write model
    python scripts/score_triage.py --label r2-tiles-trace --split holdout-a --holdout-ok
    $env:PID2GRAPH_SET="Dataset PID"; python scripts/score_triage.py --label hb-tiles-trace --split holdout-b --holdout-ok
Sheets outside 0-5 are refused without --holdout-ok. Writes out/triage_<label>_<split>.{md,json}.
"""
import argparse
import json
import os
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import confidence as cf  # noqa: E402
import score_pid2graph as sc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = cf.DATA
SPLITS = {"dev": [str(i) for i in range(6)], "holdout-a": [str(i) for i in range(6, 12)],
          "holdout-b": ["23", "44", "62", "78", "109", "111", "122", "143", "149", "158", "209", "224", "290", "345",
                        "363", "366", "382", "400", "494", "496"]}
# Every round-2 method (M0-M3) and every tool pooled, dev drawings only. Pooling all four was chosen over M3 alone on
# the dev leave-one-drawing-out check (Codex M3 top-20% catch 51% vs 43%), and it is the only way the "tracer
# doesn't join these" signal gets a weight (M3 links are all traced). Dev M2 (r2-trace, drawings 0-5) is re-created
# deterministically with scripts/trace_connections.py --src-label v2-named-fields --label r2-trace if missing.
FIT_LABELS = ["v2-named-fields", "r2-tiles-2x2", "r2-trace", "r2-tiles-trace"]
L2 = 1.0                         # ridge penalty (total, not per item): keeps weights small on six drawings


# ---------------------------------------------------------------- truth (answer key; scoring and fitting only)

def truth(label, tool, sheet):
    rec = cf.find_record(label, tool, sheet)
    pred = (rec or {}).get("prediction") or {"symbols": [], "connections": []}
    w, h = sc.png_size(DATA / f"{sheet}.png")
    nodes, adj = sc.load_key(DATA / f"{sheet}.graphml", w, h)
    keys = {k: v for k, v in nodes.items() if v["class"] in sc.SCORED}
    preds = sc.valid_symbols(pred)
    right_cls = sc.match(preds, keys, True, sc.THRESHOLDS["rough"])
    located = sc.match(preds, keys, False, sc.THRESHOLDS["rough"])
    key_links = sc.asset_links(nodes, adj)
    sym_ok = {p["id"]: p["id"] in right_cls for p in preds}
    link_ok = {}
    for a, b in cf.links_of(rec):
        ka, kb = located.get(a), located.get(b)
        link_ok[(a, b)] = bool(ka and kb and ka != kb and frozenset((ka, kb)) in key_links)
    return sym_ok, link_ok


# ---------------------------------------------------------------- rows

def sheet_rows(label, tool, sheet, model, images_dir=None):
    feats = cf.sheet_features(label, tool, sheet, images_dir)
    sym_ok, link_ok = truth(label, tool, sheet)
    rated = cf.rate_features(feats, model) if model else None
    rows = []
    for sid, f in feats["symbol_features"].items():
        if sid not in sym_ok:
            continue
        c = feats["symbols"][sid]["confidence"]
        rows.append({"kind": "symbol", "sheet": sheet, "id": sid, "ok": sym_ok[sid], "f": f,
                     "conf": c if c is not None else 0.5, **(rated["symbols"][sid] if rated else {})})
    for k, f in feats["link_features"].items():
        a, b = k
        ca = feats["symbols"].get(a, {}).get("confidence")
        cb = feats["symbols"].get(b, {}).get("confidence")
        confs = [x for x in (ca, cb) if x is not None]
        conf = min(confs) if confs else (0.0 if not f["_valid_ends"] else 0.5)
        rows.append({"kind": "link", "sheet": sheet, "id": f"{a}|{b}", "ok": link_ok.get(k, False), "f": f,
                     "conf": conf, **(rated["links"][k] if rated else {})})
    return rows


# ---------------------------------------------------------------- metrics

def caught(scores, wrong, frac):
    """Expected share of all errors in the top `frac` of items by score (higher = riskier); ties split evenly."""
    n, total_err = len(scores), sum(wrong)
    if not n or not total_err:
        return None
    k = frac * n
    groups = {}
    for s, w in zip(scores, wrong):
        g = groups.setdefault(s, [0, 0])
        g[0] += 1
        g[1] += w
    taken, got = 0.0, 0.0
    for s in sorted(groups, reverse=True):
        cnt, err = groups[s]
        if taken >= k:
            break
        use = min(cnt, k - taken)
        got += err * use / cnt
        taken += use
    return got / total_err


def metrics(rows):
    wrong = [0 if r["ok"] else 1 for r in rows]
    risk = [r["risk"] for r in rows]
    selfc = [-r["conf"] for r in rows]
    out = {"items": len(rows), "symbols": sum(r["kind"] == "symbol" for r in rows),
           "links": sum(r["kind"] == "link" for r in rows), "errors": sum(wrong),
           "error_rate": round(sum(wrong) / len(rows), 3) if rows else None, "caught": {}}
    for frac in (0.1, 0.2, 0.3):
        out["caught"][f"top{int(frac * 100)}"] = {
            "risk": _r(caught(risk, wrong, frac)), "self_confidence": _r(caught(selfc, wrong, frac)),
            "random": frac}
    tiers = {}
    for t in ("green", "amber", "red"):
        sel = [r for r in rows if r["tier"] == t]
        tiers[t] = {"items": len(sel), "share": _r(len(sel) / len(rows)) if rows else None,
                    "error_rate": _r(sum(not r["ok"] for r in sel) / len(sel)) if sel else None}
    out["tiers"] = tiers
    g = tiers["green"]
    out["green_precision"] = _r(1 - g["error_rate"]) if g["error_rate"] is not None else None
    out["green_share"] = g["share"]
    for kind in ("symbol", "link"):
        sel = [r for r in rows if r["kind"] == kind]
        w = [0 if r["ok"] else 1 for r in sel]
        out[f"{kind}_caught_top20"] = {"risk": _r(caught([r["risk"] for r in sel], w, 0.2)),
                                       "self_confidence": _r(caught([-r["conf"] for r in sel], w, 0.2))}
    return out


def _r(x):
    return None if x is None else round(x, 3)


# ---------------------------------------------------------------- fitting (development drawings only)

def fit_logistic(X, y, l2=L2, iters=4000):
    """Logistic regression with every weight >= 0 (each feature is a 'suspicious' signal), ridge penalty,
    projected gradient descent. Intercept unconstrained and unpenalized."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    n, d = X.shape
    w, b = np.zeros(d), float(np.log((y.mean() + 1e-6) / (1 - y.mean() + 1e-6)))
    lr = 2.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w + b)))
        gw = X.T @ (p - y) / n + l2 * w / n
        gb = float(np.mean(p - y))
        w = np.maximum(0.0, w - lr * gw)
        b -= lr * gb
    return w, b


def fit(sheets, labels, tools, images_dir=None, quiet=False):
    rows = []
    for label in labels:
        for tool in tools:
            for s in sheets:
                rows += sheet_rows(label, tool, s, None, images_dir)
    srows = [r for r in rows if r["kind"] == "symbol"]
    ws, bs = fit_logistic([[r["f"][n] for n in cf.SYMBOL_FEATURES] for r in srows], [not r["ok"] for r in srows])
    sym_part = {"features": cf.SYMBOL_FEATURES, "coef": [round(float(v), 4) for v in ws], "intercept": round(bs, 4)}
    # Links whose end is not a valid symbol are rated 1.0 outright (cf.rate_features), so they aren't fit.
    lrows = [r for r in rows if r["kind"] == "link" and r["f"]["_valid_ends"]]
    wl, bl = fit_logistic([[r["f"][n] for n in cf.LINK_FEATURES] for r in lrows], [not r["ok"] for r in lrows])
    link_part = {"features": cf.LINK_FEATURES, "coef": [round(float(v), 4) for v in wl], "intercept": round(bl, 4)}
    if not quiet:
        print(f"fit on {len(srows)} symbols, {len(lrows)} links ({labels}, {tools}, sheets {sheets})")
    return {"symbol": sym_part, "link": link_part}


def choose_tiers(model, sheets, labels, tools, images_dir=None):
    """Tier rule (fixed before looking at any holdout): green = items whose dev error rate stays at or below 5%
    when taken from the lowest risk up; red = items with a predicted risk of at least 50% (more likely wrong than
    right). Both thresholds come from the development drawings only."""
    rows = []
    tmp = {**model, "tiers": {"green_max": 0.0, "red_min": 1.1}}
    for label in labels:
        for tool in tools:
            for s in sheets:
                rows += sheet_rows(label, tool, s, tmp, images_dir)
    rows.sort(key=lambda r: r["risk"])
    err, best = 0, 0.0
    for i, r in enumerate(rows, 1):
        err += not r["ok"]
        nxt = rows[i]["risk"] if i < len(rows) else 1.0
        if err / i <= 0.05 and nxt > r["risk"]:
            best = (r["risk"] + nxt) / 2
    return {"green_max": round(best, 4), "red_min": 0.5, "rule": choose_tiers.__doc__.split("Tier rule ")[1].strip()}


# ---------------------------------------------------------------- main

def write_report(label, split, results, extra=None):
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    pct = lambda x: "-" if x is None else f"{100 * x:.0f}%"  # noqa: E731
    lines = [f"# Triage score: `{label}` (split: {split})", "",
             "Errors caught in the riskiest k% of output items (symbols + links pooled). Random = k%.", "",
             "| Tool | Items (errors) | Top 10%: risk / self / random | Top 20%: risk / self / random | "
             "Top 30%: risk / self / random | Green precision | Green share | Error rate green / amber / red |",
             "|---|---|---|---|---|---|---|---|"]
    for tool, m in results.items():
        c = m["caught"]
        lines.append(f"| {tool} | {m['items']} ({m['errors']}) | "
                     + " | ".join(f"{pct(c[k]['risk'])} / {pct(c[k]['self_confidence'])} / {pct(c[k]['random'])}"
                                  for k in ("top10", "top20", "top30"))
                     + f" | {pct(m['green_precision'])} | {pct(m['green_share'])} | "
                     + " / ".join(pct(m["tiers"][t]["error_rate"]) for t in ("green", "amber", "red")) + " |")
    lines += ["", "Tier sizes (share of items): " + "; ".join(
        f"{tool} " + " / ".join(pct(m["tiers"][t]["share"]) for t in ("green", "amber", "red"))
        for tool, m in results.items()) + " (green / amber / red).",
              "Symbols-only and links-only top-20% catch rates are in the JSON."]
    (out / f"triage_{label}_{split}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / f"triage_{label}_{split}.json").write_text(json.dumps({"label": label, "split": split, "tools": results,
                                                                  **(extra or {})}, indent=1), encoding="utf-8")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="r2-tiles-trace")
    ap.add_argument("--split", choices=list(SPLITS), default="dev")
    ap.add_argument("--sheets", default="", help="override the split's sheet list")
    ap.add_argument("--tools", default=",".join(cf.TOOLS))
    ap.add_argument("--images", default=str(DATA))
    ap.add_argument("--holdout-ok", action="store_true", help="allow sheets outside the development set 0-5")
    ap.add_argument("--fit", action="store_true", help="refit the rating on dev and write scripts/confidence_model.json")
    ap.add_argument("--cv", action="store_true", help="with --fit: leave-one-drawing-out check on dev")
    ap.add_argument("--fit-labels", default=",".join(FIT_LABELS), help="with --fit: run labels pooled for fitting")
    ap.add_argument("--model", default=str(cf.MODEL_FILE), help="model file to write (--fit) or read")
    a = ap.parse_args()
    tools = [t for t in a.tools.split(",") if t]
    if a.fit:
        dev = SPLITS["dev"]
        labels = [x for x in a.fit_labels.split(",") if x]
        model = fit(dev, labels, cf.TOOLS, a.images)
        model["tiers"] = choose_tiers(model, dev, labels, cf.TOOLS, a.images)
        model["fit"] = {"labels": labels, "tools": cf.TOOLS, "sheets": dev, "l2": L2,
                        "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "by": "scripts/score_triage.py --fit"}
        Path(a.model).write_text(json.dumps(model, indent=1), encoding="utf-8")
        print(json.dumps({k: model[k] for k in ("symbol", "link", "tiers")}, indent=1))
        if a.cv:  # refit without each drawing in turn, score that drawing on --label
            cv = {t: [] for t in cf.TOOLS}
            for s in dev:
                m = fit([x for x in dev if x != s], labels, cf.TOOLS, a.images, quiet=True)
                m["tiers"] = choose_tiers(m, [x for x in dev if x != s], labels, cf.TOOLS, a.images)
                for t in cf.TOOLS:
                    cv[t] += sheet_rows(a.label, t, s, m, a.images)
            write_report(a.label, "dev-leave-one-drawing-out", {t: metrics(r) for t, r in cv.items()})
        return
    sheets = [s for s in a.sheets.split(",") if s] or SPLITS[a.split]
    outside = [s for s in sheets if s not in SPLITS["dev"]]
    if outside and not a.holdout_ok:
        sys.exit(f"refusing sheets {outside}: outside the development set 0-5 (docs/GOAL.md). Holdouts are scored "
                 "once per finished method; pass --holdout-ok only for that run.")
    model = cf.load_model(a.model)
    results = {}
    for tool in tools:
        rows = []
        for s in sheets:
            rows += sheet_rows(a.label, tool, s, model, a.images)
        results[tool] = metrics(rows)
    write_report(a.label, a.split, results, {"sheets": sheets, "model_fit": model.get("fit")})


if __name__ == "__main__":
    main()
