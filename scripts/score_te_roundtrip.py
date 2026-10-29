"""Score the round trip on the generated Tennessee Eastman sheets: symbols, TAG TEXT and connections, with replicates.

This is a ROUND TRIP. The sheets were drawn by scripts/draw_pid_from_model.py from data/te_process_model.json and the
answer keys were emitted from the same model. So the numbers measure how faithfully the frozen extraction method
reads our own clean house-style drawings. They are an upper bound, not real-plant accuracy, and they are not
comparable with the OPEN100 numbers (different drawings, sparser sheets, a key we wrote ourselves).

Symbols and connections use the frozen scorer unchanged (scripts/score_pid2graph.py: rough IoU >= 0.1, review load
per 100 key items). Tag text is new, because the OPEN100 keys carry no text:
  - every key symbol that prints a tag (instrument and valve bubbles, equipment) is matched to a predicted symbol by
    the frozen scorer's match() at rough IoU >= 0.1, any class;
  - the predicted `tag` is compared with the printed text after upper-casing and dropping everything that is not a
    letter or digit ("FI-101", "FI 101" and "fi101" are equal);
  - "read" = exact after that normalization / all tagged key symbols (a missed symbol counts as not read);
    "read if found" = the same over the tagged key symbols that were matched.
  - off-page references: for flags that name another drawing, whether the predicted text carries the same
    "PID nnn-n" reference.
Replicates are summarized as mean, min-max and a 95% t-interval (n = number of replicates; with 3 replicates the
t-interval is wide on purpose).

Usage: python scripts/score_te_roundtrip.py [--conditions clean,L1,L2,L3] [--tools codex,claude]
                                             [--keys data/te_pid] [--prefix te] [--out roundtrip_scores]
Reads runs/<prefix>-<cond>-trace-<rep>/<tool>/<sheet>.json; writes out/te_pid/<out>.{json,md}.
Revision A (journal entry 44): --keys data/te_pid/rev-a --prefix te (the default output name).
Revision C: --keys data/te_pid --prefix tec --out roundtrip_scores_revC. Each revision is scored against its own keys.
"""
import argparse
import json
import math
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import score_pid2graph as sc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEYS = ROOT / "data" / "te_pid"
SHEETS = ("101", "102", "103")
T95 = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571}  # two-sided 95% t, by number of replicates
DWG = re.compile(r"PID\s*(\d+)\s*-\s*(\d+)")


def norm(text):
    return re.sub(r"[^A-Z0-9]", "", str(text or "").upper())


def printed_tags(key):
    return {norm(v["text"]) for sh in key["sheets"].values() for v in sh["symbols"].values()
            if v["text"] and v["class"] != "inlet/outlet"}


def score_sheet(sheet, record, key):
    pred = record.get("prediction") or {"symbols": [], "connections": []}
    s = sc.score(KEYS / f"{sheet}.graphml", pred, KEYS / f"{sheet}.png")
    w, h = sc.png_size(KEYS / f"{sheet}.png")
    nodes, _ = sc.load_key(KEYS / f"{sheet}.graphml", w, h)
    keys = {k: v for k, v in nodes.items() if v["class"] in sc.SCORED}
    preds = sc.valid_symbols(pred)
    tags = {str(p.get("id")): p.get("tag") for p in pred.get("symbols", [])}
    matched = {kid: pid for pid, kid in sc.match(preds, keys, False, sc.THRESHOLDS["rough"]).items()}
    syms = key["sheets"][sheet]["symbols"]
    tag_rows, ref_rows = [], []
    for kid, meta in syms.items():
        if meta["class"] == "inlet/outlet":
            m = DWG.search(meta["text"] or "")
            if m:
                got = DWG.search(str(tags.get(matched.get(kid)) or ""))
                ref_rows.append({"key": kid, "printed": m.group(0), "found": kid in matched,
                                 "read": bool(got) and got.groups() == m.groups()})
            continue
        if not meta["text"]:
            continue
        got = tags.get(matched.get(kid)) if kid in matched else None
        read = kid in matched and norm(got) == norm(meta["text"])
        tag_rows.append({"key": kid, "printed": meta["text"], "model_ref": meta["model_ref"], "found": kid in matched,
                         "extracted": got, "read": read,
                         # the dangerous misread: another real tag, so an I/O list would bind it to the wrong point
                         "is_another_real_tag": not read and norm(got) in printed_tags(key)})
    return s, tag_rows, ref_rows


def summarize(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    n, mean = len(values), st.mean(values)
    out = {"n": n, "mean": round(mean, 3), "min": round(min(values), 3), "max": round(max(values), 3)}
    if n >= 2:
        half = T95.get(n, 1.96) * st.stdev(values) / math.sqrt(n)
        out["ci95"] = [round(mean - half, 3), round(mean + half, 3)]
    return out


def run_records(label, tool):
    """What produced each sheet's answer: {model, prompt, adapter, date, time, cost}, from the (uncommitted) run
    records. The trace record names its source extraction; both are read so the published file is self-contained."""
    out = []
    for sheet in SHEETS:
        p = ROOT / "runs" / label / tool / f"{sheet}.json"
        if not p.exists():
            continue
        tr = json.loads(p.read_text(encoding="utf-8"))
        src = ROOT / "runs" / (tr.get("source_label") or "") / tool / f"{sheet}.json"
        ex = json.loads(src.read_text(encoding="utf-8")) if tr.get("source_label") and src.exists() else tr
        tiling = ex.get("tiling") or {}
        out.append({"sheet": sheet, "model": ex.get("model"), "adapter": {"claude": "Claude Code CLI",
                    "codex": "Codex CLI"}.get(tool, tool), "prompt_file": ex.get("prompt_file"),
                    "prompt_sha256": ex.get("prompt_sha256"), "image_sha256": ex.get("image_sha256"),
                    "tiles": tiling.get("grid"), "overlap": tiling.get("overlap"),
                    "preface_sha256": tiling.get("preface_sha256"), "ran_at": ex.get("ran_at"),
                    "wall_s": ex.get("seconds"), "serial_s": tiling.get("tile_seconds_sum"),
                    "tiles_failed": tiling.get("tiles_failed"), "cost_usd_notional": ex.get("cost_usd_notional"),
                    "error": ex.get("error"), "tracer": {k: (tr.get("tracer") or {}).get(k)
                                                          for k in ("script", "mode", "seconds", "ran_at")}})
    return out


def run_scores(label, tool, key):
    tot = {"located": [0, 0, 0], "classified": [0, 0, 0], "conn": [0, 0, 0], "corr": 0, "items": 0}
    tag_rows, ref_rows, missing = [], [], []
    for sheet in SHEETS:
        p = ROOT / "runs" / label / tool / f"{sheet}.json"
        record = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        if not p.exists():
            missing.append(sheet)  # a missing or failed sheet counts as zero output, never as skipped
        s, tr, rr = score_sheet(sheet, record, key)
        for k in ("located", "classified"):
            r = s["rough"][k]
            tot[k] = [a + b for a, b in zip(tot[k], (r["tp"], r["predicted"], r["in_key"]))]
        c = s["connections"]
        tot["conn"] = [a + b for a, b in zip(tot["conn"], (c["tp"], c["predicted"], c["in_key"]))]
        tot["corr"] += s["review_load"]["corrections"]
        tot["items"] += s["review_load"]["key_items"]
        tag_rows += [dict(r, sheet=sheet) for r in tr]
        ref_rows += [dict(r, sheet=sheet) for r in rr]
    f1 = lambda t: sc.prf(*t)["f1"]  # noqa: E731
    found = [r for r in tag_rows if r["found"]]
    return {"label": label, "tool": tool, "missing_sheets": missing, "records": run_records(label, tool),
            "review_load": round(100 * tot["corr"] / tot["items"], 1), "corrections": tot["corr"],
            "key_items": tot["items"],
            "symbols_found_f1": f1(tot["located"]), "symbols_class_f1": f1(tot["classified"]),
            "connections": sc.prf(*tot["conn"]),
            "tags_read": round(sum(r["read"] for r in tag_rows) / len(tag_rows), 3),
            "tags_read_if_found": round(sum(r["read"] for r in found) / len(found), 3) if found else None,
            "tags_total": len(tag_rows),
            "offpage_refs_read": round(sum(r["read"] for r in ref_rows) / len(ref_rows), 3) if ref_rows else None,
            "misreads_that_are_another_real_tag": sum(r["is_another_real_tag"] for r in tag_rows),
            "tag_misses": [r for r in tag_rows if not r["read"]]}


def write_key_run(key):
    """runs/te-key/key/<sheet>.json: the answer key written as if it were an extraction (a perfect reader).

    Fed to scripts/build_twin.py and scripts/te_model_diff.py, it separates what a reviewer corrects because the
    READER erred from what they correct even with a perfect reading (converter rules and model conventions)."""
    for sheet in SHEETS:
        w, h = sc.png_size(KEYS / f"{sheet}.png")
        nodes, adj = sc.load_key(KEYS / f"{sheet}.graphml", w, h)
        syms = key["sheets"][sheet]["symbols"]
        symbols = [{"id": k, "class": v["class"], "tag": syms[k]["text"],
                    "bbox": dict(zip(("x_min", "y_min", "x_max", "y_max"), v["box"])), "confidence": 1.0}
                   for k, v in nodes.items() if v["class"] in sc.SCORED]
        links = [{"from": a, "to": b} for a, b in sorted(tuple(sorted(link)) for link in sc.asset_links(nodes, adj))]
        rec = {"tool": "key", "drawing": sheet, "label": "te-key", "model": "answer-key (perfect reader)",
               "prompt_file": None, "prediction": {"symbols": symbols, "connections": links}}
        out = ROOT / "runs" / "te-key" / "key" / f"{sheet}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print("wrote runs/te-key/key/ (the key as a perfect extraction)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", default="clean,L1,L2,L3")
    ap.add_argument("--tools", default="codex,claude")
    ap.add_argument("--write-key-run", action="store_true", help="write runs/te-key/key/ and stop")
    ap.add_argument("--keys", default="data/te_pid", help="the sheets and answer keys the runs read")
    ap.add_argument("--prefix", default="te", help="run label prefix: runs/<prefix>-<cond>-trace-r<n>")
    ap.add_argument("--out", default="roundtrip_scores", help="output name in out/te_pid/")
    a = ap.parse_args()
    global KEYS
    KEYS = ROOT / a.keys
    key = json.loads((KEYS / "key.json").read_text(encoding="utf-8"))
    if a.write_key_run:
        write_key_run(key)
        return
    runs, table = [], []
    for cond in a.conditions.split(","):
        for tool in a.tools.split(","):
            labels = sorted(p.name for p in (ROOT / "runs").glob(f"{a.prefix}-{cond}-trace-r*") if (p / tool).is_dir())
            rs = [run_scores(lb, tool, key) for lb in labels]
            runs += rs
            if not rs:
                continue
            row = {"condition": cond, "tool": tool, "replicates": len(rs)}
            for k in ("review_load", "symbols_found_f1", "symbols_class_f1", "tags_read", "tags_read_if_found",
                      "offpage_refs_read", "misreads_that_are_another_real_tag"):
                row[k] = summarize([r[k] for r in rs])
            row["connections_f1"] = summarize([r["connections"]["f1"] for r in rs])
            row["connections_precision"] = summarize([r["connections"]["precision"] for r in rs])
            row["connections_recall"] = summarize([r["connections"]["recall"] for r in rs])
            table.append(row)
    out = ROOT / "out" / "te_pid"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.out}.json").write_text(json.dumps({"summary": table, "runs": runs}, indent=1),
                                               encoding="utf-8")

    def cell(s, pct=False):
        if not s:
            return "n/a"
        f = (lambda v: f"{100 * v:.0f}%") if pct else (lambda v: f"{v:.2f}" if v <= 1.5 else f"{v:.1f}")
        rng = f" ({f(s['min'])}–{f(s['max'])})" if s["n"] > 1 else ""
        return f"{f(s['mean'])}{rng}"
    md = ["# Round trip on the generated Tennessee Eastman sheets", "", f"Sheets and keys: `{a.keys}`; runs `{a.prefix}-*`.", "",
          "**A round trip, not real-plant accuracy.** The three sheets were generated from the verified TE model and "
          "the answer keys come from the same model, so these numbers measure how faithfully the frozen method "
          "(2×2 tiles, prompt v2, code line tracer; nothing re-tuned) reads clean drawings in the learned house style. "
          "They are an upper bound and are not comparable with the OPEN100 results.", "",
          "Mean over replicates, with the min–max range in brackets. 95% t-intervals are in the JSON.", "",
          "| Image | Tool | Runs | Review load /100 (lower is better) | Symbols found F1 | Class F1 | Connections F1 | "
          "Tags read exactly | Tags read, if found | Off-page refs read | Misreads that are another real tag |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in table:
        md.append(f"| {r['condition']} | {r['tool']} | {r['replicates']} | {cell(r['review_load'])} | "
                  f"{cell(r['symbols_found_f1'])} | {cell(r['symbols_class_f1'])} | {cell(r['connections_f1'])} | "
                  f"{cell(r['tags_read'], True)} | {cell(r['tags_read_if_found'], True)} | "
                  f"{cell(r['offpage_refs_read'], True)} | {cell(r['misreads_that_are_another_real_tag'])} |")
    md += ["", "## What produced these numbers", "",
           "Every sheet's {model, prompt, adapter, date, seconds, cost} is in " f"`{a.out}.json` (`runs[].records`). "
           "Claude dollars are the CLI's API-equivalent figure (the runs used a flat subscription); Codex reports no "
           "cost. No Gemini call was made.", "",
           "| Tool | Models | Prompt | Sheet runs | Failed tiles | Wall s (sum) | Serial s (sum) | Claude API-equivalent $ |",
           "|---|---|---|---|---|---|---|---|"]
    for tool in a.tools.split(","):
        recs = [x for r in runs if r["tool"] == tool for x in r["records"]]
        if not recs:
            continue
        usd = sum(x["cost_usd_notional"] or 0 for x in recs)
        md.append(f"| {tool} | {', '.join(sorted({str(x['model']) for x in recs}))} | "
                  f"{', '.join(sorted({str(x['prompt_file']) for x in recs}))} | {len(recs)} | "
                  f"{sum(x['tiles_failed'] or 0 for x in recs)} | {sum(x['wall_s'] or 0 for x in recs):.0f} | "
                  f"{sum(x['serial_s'] or 0 for x in recs):.0f} | {f'{usd:.2f}' if usd else 'not reported'} |")
    md += ["", "## Every tag that was not read exactly", "",
           "| Run | Tool | Sheet | Printed | Extracted |", "|---|---|---|---|---|"]
    for r in runs:
        for m in r["tag_misses"]:
            got = "(symbol not found)" if not m["found"] else repr(m["extracted"]).replace("|", "/")
            md.append(f"| {r['label']} | {r['tool']} | {m['sheet']} | {m['printed']} | {got}"
                      f"{' **(another real tag)**' if m['is_another_real_tag'] else ''} |")
    md.append("")
    (out / f"{a.out}.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:8 + len(table)]))


if __name__ == "__main__":
    main()
