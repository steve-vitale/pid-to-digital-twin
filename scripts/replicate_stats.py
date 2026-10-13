"""Replicate runs -> means with intervals (round 5, docs/GOAL.md). Offline; reads run records, makes no model calls.

For each tool and each replicate label, every drawing is scored with the unchanged scorer
(score_pid2graph.score) and, where the key carries tag truth, with score_tags.py. A missing or failed record
scores as an empty answer, never as skipped. Metrics are micro-averaged over drawings, as in scorecard.py.

Two intervals are reported for every metric, because they answer different questions:
  runs      : mean of the replicate values +/- t(0.975, n-1) * sd / sqrt(n). Drawings held fixed. Answers
              "how much does this number move if the same method is run again on these same drawings?"
  bootstrap : two-stage percentile bootstrap (B draws, fixed seed): resample drawings with replacement, then for
              each drawn drawing pick one replicate at random, and recompute the micro-average. Answers "how much
              could it move with other drawings like these AND another run?" With six drawings it is wide; that
              width is the honest size of the sample.
Model differences (first tool minus second) use the same two views: a Welch interval over replicate values, and a
bootstrap that resamples the same drawings for both tools and picks replicates independently. A difference is
called a difference only if its interval excludes zero; otherwise it is reported as a tie.

Usage:
  python scripts/replicate_stats.py --set holdout-a --labels r5-hA-rep1-trace,r5-hA-rep2-trace,... \\
      --tools claude,codex --out out/replicates_holdout-a
  python scripts/replicate_stats.py --set dexpi --labels r5-dx-rep1-trace,... --tools claude,codex --out out/replicates_dexpi
"""
import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_pid2graph as sc  # noqa: E402
import score_tags as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SETS = {
    "holdout-a": {"dir": ROOT / "data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100",
                  "geometry": ["6", "7", "8", "9", "10", "11"], "taglist": []},
    "dexpi": {"dir": ROOT / "data/external/dexpi/sheets",
              "geometry": ["dexpi-c01", "dexpi-c02", "dexpi-c03"], "taglist": ["dexpi-c08a", "dexpi-c08b"]},
}
SEED = 20261013
B = 10000
# Two-sided 95% Student t critical values by degrees of freedom (standard table values).
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
        20: 2.086, 25: 2.060, 30: 2.042}


def t975(df):
    if df < 1:
        return float("nan")
    if df in T975:
        return T975[df]
    lower = max(k for k in T975 if k <= df)
    return T975[lower] if df <= 30 else 1.96


COUNT_KEYS = ("corrections", "key_items", "cls_tp", "cls_pred", "cls_key", "conn_tp", "conn_pred", "conn_key",
              "tag_truth", "tag_found", "tag_strict", "tag_lenient", "list_n", "list_found")


def drawing_counts(data_dir, drawing, record, geometry):
    pred = (record or {}).get("prediction") or {"symbols": [], "connections": []}
    c = dict.fromkeys(COUNT_KEYS, 0)
    if geometry:
        s = sc.score(data_dir / f"{drawing}.graphml", pred, data_dir / f"{drawing}.png")
        rl, rc, cn = s["review_load"], s["rough"]["classified"], s["connections"]
        c.update(corrections=rl["corrections"], key_items=rl["key_items"], cls_tp=rc["tp"],
                 cls_pred=rc["predicted"], cls_key=rc["in_key"], conn_tp=cn["tp"], conn_pred=cn["predicted"],
                 conn_key=cn["in_key"])
        tags = data_dir / f"{drawing}.tags.json"
        if tags.exists():
            t = st.score_geometry(data_dir / f"{drawing}.graphml", tags, pred, data_dir / f"{drawing}.png")
            c.update(tag_truth=t["with_truth"], tag_found=t["strict"]["found"], tag_strict=t["strict"]["correct"],
                     tag_lenient=t["lenient"]["correct"])
    else:
        t = st.score_taglist(data_dir / f"{drawing}.taglist.json", pred)
        c.update(list_n=t["all"]["listed"], list_found=t["all"]["found"])
    return c


def f1(tp, pred, key):
    p = tp / pred if pred else 0.0
    r = tp / key if key else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def ratio(a, b):
    return a / b if b else float("nan")


METRICS = {
    "review_load_per_100": lambda t: 100 * ratio(t["corrections"], t["key_items"]),
    "symbol_f1_rough_classified": lambda t: f1(t["cls_tp"], t["cls_pred"], t["cls_key"]),
    "connection_f1": lambda t: f1(t["conn_tp"], t["conn_pred"], t["conn_key"]),
    "tag_accuracy_on_found_strict": lambda t: ratio(t["tag_strict"], t["tag_found"]),
    "tag_end_to_end_recall_strict": lambda t: ratio(t["tag_strict"], t["tag_truth"]),
    "tag_end_to_end_recall_lenient": lambda t: ratio(t["tag_lenient"], t["tag_truth"]),
    "list_identifier_recall": lambda t: ratio(t["list_found"], t["list_n"]),
}


def total(rows):
    out = dict.fromkeys(COUNT_KEYS, 0)
    for r in rows:
        for k in COUNT_KEYS:
            out[k] += r[k]
    return out


def applicable(name, t):
    need = {"review_load_per_100": "key_items", "symbol_f1_rough_classified": "cls_key",
            "connection_f1": "conn_key", "tag_accuracy_on_found_strict": "tag_truth",
            "tag_end_to_end_recall_strict": "tag_truth", "tag_end_to_end_recall_lenient": "tag_truth",
            "list_identifier_recall": "list_n"}[name]
    return t[need] > 0


def run_interval(values):
    n = len(values)
    m = statistics.fmean(values)
    if n < 2:
        return {"n": n, "mean": m, "sd": None, "lo": None, "hi": None}
    sd = statistics.stdev(values)
    h = t975(n - 1) * sd / math.sqrt(n)
    return {"n": n, "mean": m, "sd": sd, "lo": m - h, "hi": m + h}


def welch(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    if len(a) < 2 or len(b) < 2:
        return {"diff": ma - mb, "lo": None, "hi": None}
    va = statistics.variance(a) / len(a) if len(a) > 1 else 0.0
    vb = statistics.variance(b) / len(b) if len(b) > 1 else 0.0
    se = math.sqrt(va + vb)
    if se == 0:
        return {"diff": ma - mb, "lo": ma - mb, "hi": ma - mb}
    df = (va + vb) ** 2 / ((va ** 2 / (len(a) - 1) if len(a) > 1 else 0) + (vb ** 2 / (len(b) - 1) if len(b) > 1 else 0))
    h = t975(max(1, int(df))) * se
    return {"diff": ma - mb, "lo": ma - mb - h, "hi": ma - mb + h, "df": round(df, 1)}


def percentile(sorted_vals, q):
    if not sorted_vals:
        return None
    i = q * (len(sorted_vals) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def bootstrap(per_rep, metric, rng, other=None):
    """per_rep: list over replicates of {drawing: counts}. Returns sorted bootstrap values (or differences)."""
    drawings = sorted(per_rep[0])
    vals = []
    for _ in range(B):
        pick = [rng.choice(drawings) for _ in drawings]
        a = total(rng.choice(per_rep)[d] for d in pick)
        v = METRICS[metric](a)
        if other is not None:
            b = total(rng.choice(other)[d] for d in pick)
            v = v - METRICS[metric](b)
        if not math.isnan(v):
            vals.append(v)
    return sorted(vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=SETS, required=True)
    ap.add_argument("--labels", required=True, help="comma-separated replicate labels under runs/")
    ap.add_argument("--tools", default="claude,codex")
    ap.add_argument("--out", required=True, help="output path without extension (.json and .md are written)")
    a = ap.parse_args()
    spec = SETS[a.set]
    labels = [x for x in a.labels.split(",") if x]
    tools = [x for x in a.tools.split(",") if x]
    data = {}
    meta = {}
    for tool in tools:
        reps, models, missing, failed = [], set(), [], []
        for label in labels:
            rep = {}
            for d in spec["geometry"] + spec["taglist"]:
                path = ROOT / "runs" / label / tool / f"{d}.json"
                rec = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
                if rec is None:
                    missing.append(f"{label}/{d}")
                else:
                    models.add(str(rec.get("model")))
                    if not rec.get("prediction"):
                        failed.append(f"{label}/{d}")
                rep[d] = drawing_counts(spec["dir"], d, rec, d in spec["geometry"])
            reps.append(rep)
        data[tool] = reps
        meta[tool] = {"models": sorted(models), "missing_records": missing, "failed_records": failed}
    rng = random.Random(SEED)
    result = {"set": a.set, "labels": labels, "tools": tools, "seed": SEED, "bootstrap_draws": B,
              "drawings": spec["geometry"] + spec["taglist"], "meta": meta, "metrics": {}, "differences": {}}
    for metric in METRICS:
        per_tool = {}
        for tool in tools:
            reps = data[tool]
            subset = spec["geometry"] if metric != "list_identifier_recall" else spec["taglist"]
            if not subset:
                continue
            reps_sub = [{d: r[d] for d in subset} for r in reps]
            if not applicable(metric, total(reps_sub[0].values())):
                continue
            values = [METRICS[metric](total(r.values())) for r in reps_sub]
            boot = bootstrap(reps_sub, metric, rng)
            per_tool[tool] = {"replicates": [round(v, 4) for v in values], "runs": run_interval(values),
                              "bootstrap": {"lo": percentile(boot, 0.025), "hi": percentile(boot, 0.975)},
                              "per_drawing_mean": {d: statistics.fmean(METRICS[metric](r[d]) for r in reps_sub)
                                                   if applicable(metric, reps_sub[0][d]) else None for d in subset}}
        if per_tool:
            result["metrics"][metric] = per_tool
        if len(tools) == 2 and len(per_tool) == 2:
            t1, t2 = tools
            subset = spec["geometry"] if metric != "list_identifier_recall" else spec["taglist"]
            r1 = [{d: r[d] for d in subset} for r in data[t1]]
            r2 = [{d: r[d] for d in subset} for r in data[t2]]
            w = welch(per_tool[t1]["replicates"], per_tool[t2]["replicates"])
            boot = bootstrap(r1, metric, rng, other=r2)
            bl, bh = percentile(boot, 0.025), percentile(boot, 0.975)
            result["differences"][metric] = {
                "pair": f"{t1} minus {t2}", "runs_welch": w,
                "bootstrap": {"lo": bl, "hi": bh},
                # Identical values in every run give a zero-width interval; that is "no run-to-run variation",
                # not evidence of a difference beyond noise (fixed 2026-10-13 after the first round-5 report
                # printed "different" for constant tag scores).
                "verdict_runs": "n/a (one run)" if w["lo"] is None else
                                ("no run-to-run variation" if w["lo"] == w["hi"] else
                                 ("tie" if w["lo"] <= 0 <= w["hi"] else "different")),
                "verdict_bootstrap": "tie" if bl is None or bl <= 0 <= bh else "different"}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    out.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
    print(markdown(result))


def fmt(v, metric):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:.1f}" if metric == "review_load_per_100" else f"{v:.3f}"


def markdown(r):
    lines = [f"# Replicates: {r['set']}", "",
             f"Labels: {', '.join(r['labels'])}. Drawings: {', '.join(r['drawings'])}. Generated by "
             f"`scripts/replicate_stats.py` (seed {r['seed']}, {r['bootstrap_draws']} bootstrap draws).", "",
             "Mean of the replicate values, then two 95% intervals: **runs** (same drawings, another run) and "
             "**bootstrap** (other drawings like these and another run).", "",
             "| Metric | Tool | Replicates | Mean | Runs 95% | Bootstrap 95% |", "|---|---|---|---|---|---|"]
    for metric, per_tool in r["metrics"].items():
        for tool, v in per_tool.items():
            ri, bo = v["runs"], v["bootstrap"]
            lines.append(f"| {metric} | {tool} | {', '.join(fmt(x, metric) for x in v['replicates'])} | "
                         f"{fmt(ri['mean'], metric)} | {fmt(ri['lo'], metric)} to {fmt(ri['hi'], metric)} | "
                         f"{fmt(bo['lo'], metric)} to {fmt(bo['hi'], metric)} |")
    if r["differences"]:
        lines += ["", "| Metric | Difference | Runs 95% (Welch) | Verdict | Bootstrap 95% | Verdict |",
                  "|---|---|---|---|---|---|"]
        for metric, d in r["differences"].items():
            w, b = d["runs_welch"], d["bootstrap"]
            lines.append(f"| {metric} | {d['pair']}: {fmt(w['diff'], metric)} | {fmt(w['lo'], metric)} to "
                         f"{fmt(w['hi'], metric)} | {d['verdict_runs']} | {fmt(b['lo'], metric)} to "
                         f"{fmt(b['hi'], metric)} | {d['verdict_bootstrap']} |")
    lines += ["", "Models seen in the records: " + "; ".join(f"{t}: {', '.join(m['models'])}"
                                                           for t, m in r["meta"].items())]
    for t, m in r["meta"].items():
        if m["missing_records"] or m["failed_records"]:
            lines.append(f"- {t}: missing {m['missing_records']}, failed {m['failed_records']} (scored as empty)")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
