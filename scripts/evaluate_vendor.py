"""Score any P&ID digitization tool on your own hand-labelled sheets, always beside known-answer controls.

A plant labels a few of its own sheets (answer keys), asks a vendor or tool to digitize them, and runs this script.
The report it writes never shows the vendor's score alone. Every table puts it next to four controls scored on the
same keys by the same frozen scorer (scripts/score_pid2graph.py):

  perfect      the answer key itself, converted to a prediction        -> must score perfect (review load 0)
  wrong class  every symbol in the right place, every class wrong       -> must score near zero on classes
  shifted      every box moved half a sheet, sizes kept                 -> must score near zero on location
  empty        no symbols, no connections                               -> must score zero (review load 100)

These are the controls of scripts/test_scorer_controls.py (journal entry 7: a looser first scorer gave a deliberately
wrong answer 15-32%). If any control misbehaves on your keys, the report says so at the top and the script exits 2:
a scorer that can't tell a wrong answer from a right one can't grade the vendor either.

Inputs
  --keys DIR          <sheet>.graphml answer keys (PID2Graph GraphML), each with its <sheet>.png beside it (the PNG
                      gives the pixel size; key boxes are pixels, predictions are 0-1000).
  --predictions DIR   one folder of <sheet>.json per run. Each file is either the prediction contract
                      (extraction/prompt.md: {"symbols": [...], "connections": [...]}) or a run record from
                      scripts/run_extraction.py / trace_connections.py (its "prediction" field is scored). Give the
                      flag several folders to treat them as replicates of the same method: mean, min-max, a 95%
                      interval over runs and a bootstrap interval over sheets (the logic of replicate_stats.py).
  --sheets 6,7,...    optional subset of the keys folder (default: every key in it).
A missing, unreadable or failed prediction file scores as an empty answer on that sheet and is listed in the report;
it is never skipped (docs/EVALUATION.md rule 5).

Usage
  python scripts/evaluate_vendor.py --keys my_keys --predictions vendor_run1 [vendor_run2 ...] \\
      --name "Vendor X" --out my_report/vendor_x
  Writes my_report/vendor_x.md and .json and prints the markdown. Exit 0 = controls behaved; 2 = a control failed
  (do not use the vendor numbers); 1 = bad input (no keys, no PNG, etc.).
  Worked example on public sheets: examples/vendor-evaluation/README.md.

Limits (read before quoting a number)
  - Six classes only: tank, pump, valve, instrumentation, inlet/outlet, general (PID2Graph's asset classes). Anything
    else a tool reports (line numbers, nozzles, notes, a seventh class name) is ignored by the scorer and counted
    in the report as "ignored symbols", not as wrong.
  - The scorer ignores tag text, line routes and sizes, flow direction, spec breaks and box precision beyond the two
    IoU thresholds (0.5 strict, 0.1 rough). Connections are judged by which assets connect, not by how the line
    runs, and on class-agnostic rough matches: a tool that gets every class wrong but the boxes and links right
    still gets connection credit. Read the classification columns for that.
  - Tag text is not scored here. Keys that carry tag truth need scripts/score_tags.py (and the .tags.json /
    .taglist.json formats it defines).
  - "general" is a catch-all whose meaning is the annotators' habit; don't let a vendor tune toward it
    (docs/EVALUATION.md rule 9).
  - A handful of sheets is a small sample. The bootstrap interval says how far the score could move on other
    sheets like these; it is wide on purpose.
  - The answer is only as good as your labelling. The perfect control proves the scorer reads your keys; it can't
    prove your keys are right.
"""
import argparse
import hashlib
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replicate_stats as rs  # noqa: E402
import score_pid2graph as sc  # noqa: E402
from test_scorer_controls import perfect_prediction, shift  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# A deliberately wrong answer may earn at most this symbol F1 (rough, class must match), aggregated over the sheets
# and on any one sheet. The shifted control's honest chance floor is 8.8% rough *location* recall on OPEN100 sheet 6
# (journal entry 7); its class-matched F1 there is lower. Anything above this means the scorer is being fooled.
WRONG_MAX_F1 = 0.10
SHIFT_CHANCE = 0.05  # share of key symbols a half-sheet shift may hit by chance on a repeating layout
# Headline metrics: (key in the report, label, replicate_stats metric name or None for the extra strict metric).
HEADLINE = (("review_load_per_100", "Review load per 100 key items (lower is better)"),
            ("symbol_f1_rough_classified", "Symbol F1, rough, class must match"),
            ("symbol_f1_strict_classified", "Symbol F1, strict, class must match"),
            ("connection_f1", "Connection F1"))
CONTROL_ORDER = ("perfect", "wrong_class", "shifted", "empty")
CONTROL_LABELS = {"perfect": "Control: perfect answer (the key itself)",
                  "wrong_class": "Control: every class wrong",
                  "shifted": "Control: every box moved half a sheet",
                  "empty": "Control: empty answer"}


def sha256(path):
    """Of the file with a UTF-8 BOM dropped and line endings as LF, so a Windows and a Linux checkout agree."""
    data = Path(path).read_bytes()
    data = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def sheet_sort(name):
    return (0, int(name), "") if name.isdigit() else (1, 0, name)


def display(folder):
    """Folder name for the report: its last two parts, never a local absolute path."""
    p = Path(folder).resolve()
    return f"{p.parent.name}/{p.name}" if p.parent.name else p.name


def load_prediction(path):
    """-> (prediction dict, status, note). status: ok | missing | failed."""
    if not path.exists():
        return None, "missing", "no file"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return None, "failed", f"unreadable JSON: {str(e)[:120]}"
    if not isinstance(data, dict):
        return None, "failed", "not a JSON object"
    if "prediction" in data:  # run record
        pred = data.get("prediction")
        if not isinstance(pred, dict):
            why = data.get("error") or data.get("parse_error") or "record has no prediction"
            return None, "failed", str(why)[:160]
        data, note = pred, str(data.get("model") or "")
    elif "symbols" in data:  # prediction contract
        note = ""
    else:
        return None, "failed", "neither a prediction (no 'symbols') nor a run record (no 'prediction')"
    if not isinstance(data.get("symbols"), list) or not isinstance(data.get("connections", []), list):
        return None, "failed", "'symbols' and 'connections' must be lists"
    return data, "ok", note


def controls_for(graphml, png):
    perfect = perfect_prediction(graphml, png)
    rot = {c: sc.SCORED[(i + 1) % len(sc.SCORED)] for i, c in enumerate(sc.SCORED)}
    return {"perfect": perfect,
            "wrong_class": {"symbols": [dict(s, **{"class": rot[s["class"]]}) for s in perfect["symbols"]],
                            "connections": []},
            "shifted": {"symbols": [dict(s, box=shift(s["box"])) for s in perfect["symbols"]], "connections": []},
            "empty": {"symbols": [], "connections": []}}


def score_sheet(keys_dir, sheet, pred):
    """Scores one sheet. 'counts' are replicate_stats.drawing_counts (so aggregates match that script exactly);
    'detail' is the scorer's own per-sheet result for the strict metric and the per-sheet table."""
    pred = pred or {"symbols": [], "connections": []}
    counts = rs.drawing_counts(keys_dir, sheet, {"prediction": pred}, True)
    detail = sc.score(keys_dir / f"{sheet}.graphml", pred, keys_dir / f"{sheet}.png")
    sc_cls = detail["strict"]["classified"]
    counts = dict(counts, strict_tp=sc_cls["tp"], strict_pred=sc_cls["predicted"], strict_key=sc_cls["in_key"],
                  ignored_symbols=detail["malformed_symbols"])
    return counts, detail


def metrics(t):
    out = {name: rs.METRICS[name](t) for name in ("review_load_per_100", "symbol_f1_rough_classified",
                                                  "connection_f1")}
    out["symbol_f1_strict_classified"] = rs.f1(t["strict_tp"], t["strict_pred"], t["strict_key"])
    return out


def total(rows):
    rows = list(rows)
    keys = rs.COUNT_KEYS + ("strict_tp", "strict_pred", "strict_key", "ignored_symbols")
    return {k: sum(r[k] for r in rows) for k in keys}


BOOT_ORDER = ("review_load_per_100", "symbol_f1_rough_classified", "connection_f1", "symbol_f1_strict_classified")


def bootstrap(per_rep, metric, rng):
    """replicate_stats.bootstrap, extended to the strict metric: resample sheets with replacement, pick one run at
    random for each drawn sheet, recompute the micro-average. Returns the sorted values."""
    sheets = sorted(per_rep[0])
    vals = []
    for _ in range(rs.B):
        pick = [rng.choice(sheets) for _ in sheets]
        v = metrics(total(rng.choice(per_rep)[s] for s in pick))[metric]
        if v == v:  # drop NaN (a draw with no key items)
            vals.append(v)
    return sorted(vals)


def sheet_metrics(detail):
    return {"review_load_per_100": detail["review_load"]["per_100"],
            "symbol_f1_rough_classified": detail["rough"]["classified"]["f1"],
            "symbol_f1_strict_classified": detail["strict"]["classified"]["f1"],
            "symbol_recall_rough_located": detail["rough"]["located"]["recall"],
            "connection_f1": detail["connections"]["f1"],
            "corrections": detail["review_load"]["corrections"], "key_items": detail["review_load"]["key_items"]}


def check_controls(per_sheet, agg):
    """Known answers must score as known. Returns a list of failure strings (empty = scorer trustworthy here)."""
    fails = []
    for sheet, c in per_sheet.items():
        p, w, s, e = (c[k] for k in CONTROL_ORDER)
        if not (p["review_load_per_100"] == 0 and p["symbol_f1_strict_classified"] == 1
                and (p["connection_f1"] == 1 or p["key_items"] == 0 or c["_key_links"] == 0)):
            fails.append(f"sheet {sheet}: the perfect answer did not score perfect ({p})")
        if (e["review_load_per_100"] != 100 and e["key_items"]) or e["symbol_recall_rough_located"] != 0:
            fails.append(f"sheet {sheet}: the empty answer did not score zero ({e})")
        for name, r in (("wrong_class", w), ("shifted", s)):
            if r["symbol_f1_rough_classified"] > WRONG_MAX_F1:
                fails.append(f"sheet {sheet}: the {name} answer earned symbol F1 {r['symbol_f1_rough_classified']:.3f}"
                             f" (> {WRONG_MAX_F1})")
            if r["review_load_per_100"] < 90:
                fails.append(f"sheet {sheet}: the {name} answer needed only {r['review_load_per_100']} corrections"
                             " per 100 key items (an empty answer needs 100)")
        # A box moved half a sheet can land on an identical symbol by chance where a layout repeats (synthetic
        # sheets do): allow that up to SHIFT_CHANCE of the key's symbols. A scorer that ignored location would match
        # nearly all of them.
        allowed = max(1, int(SHIFT_CHANCE * s.get("_strict_located_key", 0)))
        if s["_strict_located_tp"] > allowed:
            fails.append(f"sheet {sheet}: {s['_strict_located_tp']} boxes moved half a sheet still matched at strict "
                         f"IoU (chance allowance {allowed})")
    for name in ("wrong_class", "shifted"):
        if agg[name]["symbol_f1_rough_classified"] > WRONG_MAX_F1:
            fails.append(f"all sheets: the {name} answer earned symbol F1 {agg[name]['symbol_f1_rough_classified']:.3f}")
    return fails


def evaluate(keys_dir, pred_dirs, sheets=None, name="vendor"):
    keys_dir = Path(keys_dir)
    available = sorted((g.stem for g in keys_dir.glob("*.graphml")), key=sheet_sort)
    if sheets:
        absent = [s for s in sheets if s not in available]
        if absent:
            raise ValueError(f"no answer key for sheet(s) {absent} in the keys folder")
    sheets = sorted(sheets or available, key=sheet_sort)
    if not sheets:
        raise ValueError("no <sheet>.graphml answer keys in the keys folder")
    for s in sheets:
        if not (keys_dir / f"{s}.png").exists():
            raise ValueError(f"sheet {s}: {s}.png must sit beside {s}.graphml (it gives the pixel size)")

    # Controls: same keys, same scorer.
    ctrl_counts = {c: {} for c in CONTROL_ORDER}
    ctrl_sheet = {}
    for s in sheets:
        g, png = keys_dir / f"{s}.graphml", keys_dir / f"{s}.png"
        ctrl_sheet[s] = {}
        for cname, pred in controls_for(g, png).items():
            counts, detail = score_sheet(keys_dir, s, pred)
            ctrl_counts[cname][s] = counts
            m = sheet_metrics(detail)
            if cname == "shifted":
                m["_strict_located_tp"] = detail["strict"]["located"]["tp"]
                m["_strict_located_key"] = detail["strict"]["located"]["in_key"]
            ctrl_sheet[s][cname] = m
        ctrl_sheet[s]["_key_links"] = ctrl_counts["perfect"][s]["conn_key"]
    ctrl_agg = {c: metrics(total(ctrl_counts[c].values())) for c in CONTROL_ORDER}
    flat = {s: {c: ctrl_sheet[s][c] for c in CONTROL_ORDER} | {"_key_links": ctrl_sheet[s]["_key_links"]}
            for s in sheets}
    control_failures = check_controls(flat, ctrl_agg)

    # Vendor runs.
    runs, problems = [], []
    for d in pred_dirs:
        d = Path(d)
        label = display(d)
        if not d.is_dir():
            raise ValueError(f"prediction folder not found: {label}")
        rep_counts, rep_sheets, files, ignored, models = {}, {}, {}, 0, set()
        for s in sheets:
            path = d / f"{s}.json"
            pred, status, note = load_prediction(path)
            if status == "ok":
                try:
                    score_sheet(keys_dir, s, pred)
                except (AttributeError, KeyError, TypeError, ValueError) as e:  # malformed entries inside the lists
                    pred, status, note = None, "failed", f"the scorer could not read it: {type(e).__name__}: {e}"[:160]
            if status == "ok" and note:
                models.add(note)
            if status != "ok":
                problems.append({"run": label, "sheet": s, "status": status, "note": note})
            counts, detail = score_sheet(keys_dir, s, pred)
            rep_counts[s] = counts
            rep_sheets[s] = dict(sheet_metrics(detail), status=status)
            ignored += counts["ignored_symbols"]
            files[s] = sha256(path) if path.exists() else None
        extra = sorted((p.stem for p in d.glob("*.json") if p.stem not in sheets), key=sheet_sort)
        runs.append({"label": label, "models_in_records": sorted(models),
                     "aggregate": metrics(total(rep_counts.values())), "per_sheet": rep_sheets,
                     "ignored_symbols": ignored, "files_sha256": files, "extra_files_not_scored": extra,
                     "_counts": rep_counts})

    # Replicates: mean, min-max, runs interval, bootstrap over sheets (replicate_stats logic).
    summary = {}
    for metric, _ in HEADLINE:
        vals = [r["aggregate"][metric] for r in runs]
        ri = rs.run_interval(vals)
        summary[metric] = {"values": vals, "mean": ri["mean"], "min": min(vals), "max": max(vals),
                           "runs_95": [ri["lo"], ri["hi"]] if ri["lo"] is not None else None}
    # Same order as replicate_stats.py (its three metrics first, then strict), one seeded stream.
    rng = random.Random(rs.SEED)
    for metric in BOOT_ORDER:
        boot = bootstrap([r["_counts"] for r in runs], metric, rng)
        summary[metric]["bootstrap_95"] = [rs.percentile(boot, 0.025), rs.percentile(boot, 0.975)]

    per_sheet = {s: {"vendor_mean": {m: statistics.fmean(r["per_sheet"][s][m] for r in runs) for m, _ in HEADLINE},
                     "vendor_runs": [r["per_sheet"][s] for r in runs],
                     "controls": {c: {k: v for k, v in ctrl_sheet[s][c].items() if not k.startswith("_")}
                                  for c in CONTROL_ORDER}} for s in sheets}
    for r in runs:
        del r["_counts"]
    return {"name": name, "sheets": sheets, "scorer": "scripts/score_pid2graph.py",
            "scorer_sha256": sha256(Path(sc.__file__)),
            "keys_sha256": {s: sha256(keys_dir / f"{s}.graphml") for s in sheets},
            "controls_ok": not control_failures, "control_failures": control_failures,
            "wrong_answer_max_f1": WRONG_MAX_F1, "controls": ctrl_agg, "runs": runs, "replicates": summary,
            "per_sheet": per_sheet, "missing_or_failed": problems}


def fmt(v, metric):
    if v is None:
        return "n/a"
    return f"{v:.1f}" if metric.startswith("review_load") else f"{v:.3f}"


def markdown(r):
    n = len(r["runs"])
    L = [f"# Vendor evaluation: {r['name']}", ""]
    if not r["controls_ok"]:
        L += ["> **CONTROLS FAILED. Do not use the vendor numbers below.** The scorer did not score known answers as "
              "known on these keys, so it cannot tell a good extraction from a bad one here:", ""]
        L += [f"> - {f}" for f in r["control_failures"]] + [""]
    else:
        L += [f"Controls behaved on every sheet: the perfect answer scored perfect, the empty answer zero, and both "
              f"deliberately wrong answers stayed at or below symbol F1 {r['wrong_answer_max_f1']}. The scorer can "
              "tell right from wrong on these keys.", ""]
    L += [f"Sheets: {', '.join(r['sheets'])}. Runs treated as replicates: {n} "
          f"({', '.join(x['label'] for x in r['runs'])}). Scorer: `{r['scorer']}` (sha256 {r['scorer_sha256'][:12]}).",
          ""]
    models = sorted({m for x in r["runs"] for m in x["models_in_records"]})
    if models:
        L += [f"Models named in the run records: {', '.join(models)}.", ""]
    if r["missing_or_failed"]:
        L += ["**Missing or failed predictions (each scored as an empty answer on that sheet, not skipped):**", ""]
        L += [f"- {p['run']} sheet {p['sheet']}: {p['status']} ({p['note']})" for p in r["missing_or_failed"]]
        L += [""]
    L += ["## Vendor beside the controls", "",
          "All rows: same answer keys, same scorer, micro-averaged over the sheets. "
          + ("Vendor row: mean of the runs, then min-max." if n > 1 else "Vendor row: one run."), "",
          "| Answer | " + " | ".join(lbl for _, lbl in HEADLINE) + " |", "|---|" + "---|" * len(HEADLINE)]
    rep = r["replicates"]
    cells = []
    for m, _ in HEADLINE:
        e = rep[m]
        cells.append(f"**{fmt(e['mean'], m)}**" + (f" ({fmt(e['min'], m)}-{fmt(e['max'], m)})" if n > 1 else ""))
    L.append(f"| **{r['name']}** | " + " | ".join(cells) + " |")
    for c in CONTROL_ORDER:
        L.append(f"| {CONTROL_LABELS[c]} | " + " | ".join(fmt(r["controls"][c][m], m) for m, _ in HEADLINE) + " |")
    L += [""]
    if n > 1:
        L += ["## Replicates", "",
              "Each run's value, then two 95% intervals: **runs** (these sheets, the method run again) and "
              "**bootstrap** (other sheets like these, and another run; seed and draws as in "
              "`scripts/replicate_stats.py`).", "",
              "| Metric | Runs | Mean | Min-max | Runs 95% | Bootstrap 95% (sheets) |", "|---|---|---|---|---|---|"]
        for m, lbl in HEADLINE:
            e = rep[m]
            ri = e["runs_95"]
            bo = e.get("bootstrap_95")
            L.append(f"| {lbl} | {', '.join(fmt(v, m) for v in e['values'])} | {fmt(e['mean'], m)} | "
                     f"{fmt(e['min'], m)}-{fmt(e['max'], m)} | "
                     f"{(fmt(ri[0], m) + ' to ' + fmt(ri[1], m)) if ri else 'n/a'} | "
                     f"{(fmt(bo[0], m) + ' to ' + fmt(bo[1], m)) if bo else 'n/a'} |")
        L += [""]
    L += ["## Per sheet", "",
          "Review load per 100 key items on each sheet, so one bad sheet can't hide in the average. Vendor columns are "
          "the runs in order; controls on the right.", "",
          "| Sheet | Key items | " + " | ".join(f"Run {i + 1}" for i in range(n)) + (" | Mean" if n > 1 else "")
          + " | Perfect | Wrong class | Shifted | Empty |",
          "|---|---|" + "---|" * (n + (1 if n > 1 else 0) + 4)]
    for s, d in r["per_sheet"].items():
        runs = d["vendor_runs"]
        flags = ["" if x["status"] == "ok" else f" ({x['status']})" for x in runs]
        row = [f"{x['review_load_per_100']:.1f}{f}" for x, f in zip(runs, flags)]
        if n > 1:
            row.append(f"{d['vendor_mean']['review_load_per_100']:.1f}")
        row += [f"{d['controls'][c]['review_load_per_100']:.1f}" for c in CONTROL_ORDER]
        L.append(f"| {s} | {runs[0]['key_items']} | " + " | ".join(row) + " |")
    L += ["", "Symbol F1 (rough, class must match) and connection F1 per sheet, vendor mean over the runs:", "",
          "| Sheet | Symbol F1 | Connection F1 | Wrong-class control symbol F1 | Shifted control symbol F1 |",
          "|---|---|---|---|---|"]
    for s, d in r["per_sheet"].items():
        vm, ct = d["vendor_mean"], d["controls"]
        L.append(f"| {s} | {vm['symbol_f1_rough_classified']:.3f} | {vm['connection_f1']:.3f} | "
                 f"{ct['wrong_class']['symbol_f1_rough_classified']:.3f} | "
                 f"{ct['shifted']['symbol_f1_rough_classified']:.3f} |")
    ign = [f"{x['label']}: {x['ignored_symbols']}" for x in r["runs"] if x["ignored_symbols"]]
    extra = [f"{x['label']}: {', '.join(x['extra_files_not_scored'])}" for x in r["runs"] if x["extra_files_not_scored"]]
    if ign:
        L += ["", "Symbols the scorer ignored (malformed box, missing id, or a class outside the six): " + "; ".join(ign)
              + ". Ignored is not wrong: check whether they matter for your use."]
    if extra:
        L += ["", "Prediction files with no answer key (not scored): " + "; ".join(extra) + "."]
    L += ["", "## How to read this", "",
          "- **Start with the controls, not the vendor.** The perfect row is the best any tool can score on these "
          "keys; the empty row is what doing nothing scores. A deliberately wrong answer must land near the empty row. "
          "If it doesn't, the scorer is being fooled and the vendor number means nothing (the report would say so at "
          "the top).",
          "- **Review load** is the headline: the corrections a person needs to turn the tool's answer into the answer "
          "key (delete false symbols, add missed ones, fix wrong classes, delete false links, add missed links), per "
          "100 items in the key. 0 is perfect, 100 is the same work as starting from nothing. Above 100 is worse than "
          "nothing: the reviewer also deletes the tool's mistakes.",
          "- **Symbol F1** says whether the tool found the symbols and called them the right class. *Rough* means "
          "\"in about the right place\" (box overlap of at least 10%), *strict* means precise enough to draw from "
          "(at least 50%). A big gap between the two means the boxes are loose.",
          "- **Connection F1** says whether it knows which assets connect. It ignores classes: compare it with the "
          "symbol columns.",
          "- **Per sheet**: look for one sheet much worse than the rest. That sheet is usually a drawing style, scan "
          "quality or symbol mix the tool hasn't seen, and your other sheets may have more of it.",
          "- **Several runs**: AI tools don't give the same answer twice. *Min-max* and *runs 95%* show how much the "
          "same tool moves on the same sheets. Two vendors whose ranges overlap are tied on this evidence. The "
          "*bootstrap* interval is how far the score could move on other sheets like these: with a few sheets it is "
          "wide, and that width is the honest size of your sample.",
          "- **Missing or failed sheets count as empty answers.** A tool shouldn't look better by failing quietly.",
          "- **What this does not measure:** tag text (use `scripts/score_tags.py` on keys with tag truth), line "
          "routes, sizes, flow direction, or anything outside the six classes. And it is only as good as your "
          "labelled sheets.", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keys", required=True, help="folder of <sheet>.graphml answer keys with <sheet>.png beside them")
    ap.add_argument("--predictions", required=True, nargs="+", help="one or more folders of <sheet>.json (replicates)")
    ap.add_argument("--sheets", default="", help="comma-separated subset of sheets (default: every key)")
    ap.add_argument("--name", default="vendor", help="name shown for the tool or vendor")
    ap.add_argument("--out", required=True, help="output path without extension (.md and .json are written)")
    a = ap.parse_args(argv)
    try:
        r = evaluate(a.keys, a.predictions, [s for s in a.sheets.split(",") if s], a.name)
    except ValueError as e:
        print(f"evaluate_vendor: {e}", file=sys.stderr)
        return 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    md = markdown(r)
    out.with_suffix(".json").write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    for p in r["missing_or_failed"]:
        print(f"WARNING: {p['run']} sheet {p['sheet']} {p['status']}: scored as an empty answer", file=sys.stderr)
    if not r["controls_ok"]:
        print("CONTROLS FAILED: do not use the vendor numbers.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
