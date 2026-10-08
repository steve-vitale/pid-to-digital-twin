"""Risk rating for every extracted item (round 3, docs/GOAL.md "Goal 1"): which symbols and links to look at first.

A model's own confidence is a weak signal (Codex and Gemini say 0.9-1.0 for almost everything), so the rating is built
from independent signals that exist at run time, WITHOUT the answer key. This file never reads an answer key; the
fitting and scoring that need the key live in scripts/score_triage.py.

Symbol signals (each 0..1, higher = more suspicious):
    xm_miss        share of the OTHER models (same pass, same sheet) with no same-class box overlapping it (IoU >= 0.1)
    xp_miss        the same model's other pass (whole sheet vs 2x2 tiles) has no same-class box overlapping it
    detached       the line tracer found no line network touching the box, or dropped the box because one unbroken
                   straight line runs right through it (a real symbol interrupts its line)
    dup_box        another symbol from the same run sits on the same spot (IoU >= 0.5): a double detection
    tag_placeholder  the tag is a placeholder (XXX, TBD, ?)
    tag_missing    no tag on a class that normally carries one (instrument, tank, pump, off-page connector)
    tag_malformed  an instrument tag that doesn't read as ISA-style letters + loop number
    tag_dup        the same tag text is on another symbol of the same sheet
    is_general     the catch-all "general" class (whatever is not a tank, pump, valve or instrument)
    low_conf       the model's own confidence, as a rank within the run: share of this sheet's symbols it was more
                   sure of (raw confidences aren't comparable across models; one weak signal among many)
Link signals:
    end_xm         for the worse of the two ends: share of the other models with no symbol of any class there
                   (a link to a symbol nobody else sees is doubtful; class doesn't matter for a link)
    end_xp         either end has no symbol of any class there in the same model's other pass
    not_model      the model's own link list doesn't contain it (traced runs only; 0 for the model's own links)
    not_traced     the line tracer doesn't join the two symbols (model-link runs only; 0 for traced links)
    net_size       how many symbols share the traced network (log2 scale / 5, capped at 1). The tracer links every
                   pair on a network, so on a big network each pair is less certain
    xm_miss        share of the other models whose output on this sheet doesn't join the same two places
    low_conf       the less confident end's low_conf

The rating is a logistic regression with one weight per signal, fit on the development drawings (0-5) only, with
every weight constrained to the sign the signal is meant to have (a "suspicious" signal can only raise risk). That
keeps it monotonic and readable: the risk is a probability-like number, and each reason in "why" is a signal whose
weight x value pushed the risk up. Weights live in scripts/confidence_model.json (written by score_triage.py --fit).

Tiers (thresholds on the risk, set on the development drawings only, scripts/confidence_model.json):
    green  risk below green_max: safe to batch-accept
    amber  in between: quick check
    red    risk at or above red_min: look closely

Library:   rate_run(label, tool, sheet, images_dir) -> {"symbols": {id: rating}, "links": {(a, b): rating}}
           annotate_model(model, run_dir, sheets, images_dir)   (adds "risk" to every twin item; see build_twin.py)
CLI:       python scripts/confidence.py --label r2-tiles-trace --tool codex --sheets 0,1,2,3,4,5
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import score_pid2graph as sc  # noqa: E402  (iou, valid classes only; never the answer key)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / os.environ.get("PID2GRAPH_SET", "PID2Graph OPEN100")
# Run folders are looked up in order; runs-main is an optional read-only link to another checkout's runs.
RUN_ROOTS = [ROOT / "runs", ROOT / "runs-main"]
CACHE = ROOT / "out" / "confidence_cache"
MODEL_FILE = Path(__file__).parent / "confidence_model.json"
DEV_SHEETS = {str(i) for i in range(6)}
TOOLS = ["claude", "codex", "gemini"]

# Run families: the same prompt run as a whole-sheet pass and as a 2x2-tiled pass. A traced run names its symbol
# source in its record ("source_label"), so M2/M3 find their pass through it. Generic, not drawing-specific.
FAMILIES = [
    {"whole": "v2-named-fields", "tiled": "r2-tiles-2x2"},   # OPEN100 (dev + holdout A)
    {"whole": "hb-v2", "tiled": "hb-tiles-2x2"},             # Dataset-P&ID (holdout B)
]

PLACEHOLDER = re.compile(r"(?<![A-Z0-9])(X{2,}|\?+|#{2,}|TBD|TBA|N/A)(?![A-Z0-9])", re.I)  # same as build_twin.py
ISA_TAG = re.compile(r"^([A-Z]{1,6})[\s-]*([0-9][0-9A-Z]*(?:-[0-9A-Z]+)?)?$")             # same as build_twin.py
TAGGED_CLASSES = {"instrumentation", "tank", "pump", "inlet/outlet"}

SYMBOL_FEATURES = ["xm_miss", "xp_miss", "detached", "dup_box", "tag_placeholder", "tag_missing", "tag_malformed",
                   "tag_dup", "is_general", "low_conf"]
LINK_FEATURES = ["end_xm", "end_xp", "not_model", "not_traced", "net_size", "xm_miss", "low_conf"]

WHY = {  # plain language for a reviewer, per signal
    "xm_miss": "the other models didn't find this symbol here",
    "xp_miss": "the same model's other pass (whole sheet vs tiles) didn't find it",
    "detached": "it isn't on any drawn line (or a straight line runs right through its box)",
    "dup_box": "another detection sits on the same spot (possible double count)",
    "tag_placeholder": "placeholder tag on the drawing",
    "tag_missing": "no tag was read",
    "tag_malformed": "tag doesn't read as an instrument tag (letters + loop number)",
    "tag_dup": "the same tag is on another symbol on this sheet",
    "is_general": "catch-all 'general' class: often mislabeled",
    "low_conf": "the model itself was unsure",
    "end_xm": "one end is a symbol the other models didn't see",
    "end_xp": "one end is a symbol the model's other pass didn't see",
    "not_model": "found by line tracing only; the model didn't draw this link",
    "not_traced": "the line tracer doesn't join these two symbols",
    "net_size": "on a large pipe network where every pair is linked; the pairing is less certain",
}
WHY_LINK = {**WHY, "xm_miss": "the other models don't link these two places",
            "low_conf": "the model was unsure of one end"}


# ---------------------------------------------------------------- loading

def find_record(label, tool, sheet):
    for root in RUN_ROOTS:
        p = root / label / tool / f"{sheet}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def read_box(s):
    box = s.get("box")
    b = s.get("bbox")
    if box is None and isinstance(b, dict):
        box = [b.get("x_min"), b.get("y_min"), b.get("x_max"), b.get("y_max")]
    if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)):
        return None
    x0, y0, x1, y1 = (float(v) for v in box)
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def symbols_of(rec):
    """Symbols the scorer would keep (valid box, scored class, id), with tag and confidence."""
    out = {}
    for s in ((rec or {}).get("prediction") or {}).get("symbols", []):
        box = read_box(s)
        if box is None or s.get("class") not in sc.SCORED or s.get("id") is None:
            continue
        conf = s.get("confidence")
        tag = re.sub(r"\s+", " ", str(s["tag"])).strip() if s.get("tag") not in (None, "") else None
        out.setdefault(str(s["id"]), {"id": str(s["id"]), "class": s["class"], "box": box, "tag": tag,
                                      "confidence": float(conf) if isinstance(conf, (int, float)) else None})
    return out


def links_of(rec):
    """Unordered, de-duplicated links as the run outputs them (self-links dropped, as the scorer can't credit them)."""
    seen = []
    for c in ((rec or {}).get("prediction") or {}).get("connections", []):
        a, b = str(c.get("from")), str(c.get("to"))
        if a == b:
            continue
        k = tuple(sorted((a, b)))
        if k not in seen:
            seen.append(k)
    return seen


def has_prediction(rec):
    return bool(rec and rec.get("prediction"))


# ---------------------------------------------------------------- the tracer, as a library

def trace_info(image, symbols, options):
    """Which line networks each symbol touches, and which symbols the tracer dropped. Cached on disk by input hash."""
    import trace_connections as tc
    key = hashlib.sha256(json.dumps([str(image), sorted((s["id"], s["box"]) for s in symbols), options],
                                    sort_keys=True).encode()).hexdigest()[:24]
    cpath = CACHE / f"{key}.json"
    if cpath.exists():
        return json.loads(cpath.read_text(encoding="utf-8"))
    dbg = {}
    tc.trace(image, [{"id": s["id"], "box": s["box"]} for s in symbols], debug=dbg, **(options or {}))
    attach = dbg.get("_attach", {})
    kept = sorted({s["id"] for s in dbg.get("_syms", [])})
    info = {"networks": {str(r): ids for r, ids in attach.items()}, "kept": kept}
    CACHE.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(info), encoding="utf-8")
    return info


# ---------------------------------------------------------------- features

def any_overlap(box, others, cls=None, thr=0.1):
    return any(sc.iou(box, o["box"]) >= thr and (cls is None or o["class"] == cls) for o in others)


def other_pass_label(symbol_label):
    for f in FAMILIES:
        if symbol_label == f["whole"]:
            return f["tiled"]
        if symbol_label == f["tiled"]:
            return f["whole"]
    return None


def sheet_features(label, tool, sheet, images_dir=None):
    """Features for every symbol and link of runs/<label>/<tool>/<sheet>.json. Uses only run files and the image."""
    rec = find_record(label, tool, sheet)
    syms = symbols_of(rec)
    links = links_of(rec)
    traced_run = bool(rec and rec.get("source_label"))
    sym_label = rec.get("source_label") if traced_run else label
    src = find_record(sym_label, tool, sheet) if traced_run else rec
    model_links = set(links_of(src))

    # Other models, same pass (symbols) and same label (links).
    others_sym, others_link = [], []
    for t in TOOLS:
        if t == tool:
            continue
        r = find_record(sym_label, t, sheet)
        if has_prediction(r):
            others_sym.append(list(symbols_of(r).values()))
        rl = find_record(label, t, sheet)
        if has_prediction(rl):
            others_link.append((symbols_of(rl), set(links_of(rl))))
    xp_label = other_pass_label(sym_label)
    xp_rec = find_record(xp_label, tool, sheet) if xp_label else None
    xp_syms = list(symbols_of(xp_rec).values()) if has_prediction(xp_rec) else None

    # Line networks.
    image = Path(images_dir or DATA) / f"{sheet}.png"
    net_of, kept = {}, set(syms)
    if image.exists() and syms:
        opts = (rec.get("tracer") or {}).get("options") if traced_run else None
        info = trace_info(image, list(syms.values()), opts)
        kept = set(info["kept"])
        for r, ids in info["networks"].items():
            for i in ids:
                net_of.setdefault(i, {})[r] = len(ids)
    traced_pairs = {}
    for i, nets in net_of.items():
        for r, size in nets.items():
            traced_pairs.setdefault(r, (size, []))[1].append(i)
    pair_net = {}
    for r, (size, ids) in traced_pairs.items():
        ids = sorted(set(ids))
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                k = (ids[x], ids[y])
                pair_net[k] = min(pair_net.get(k, size), size)

    # Tags on this sheet (for duplicates).
    norm = lambda t: re.sub(r"[\s_-]+", "", t.upper())  # noqa: E731
    tag_count = Counter(norm(s["tag"]) for s in syms.values() if s["tag"] and not PLACEHOLDER.search(s["tag"]))

    # Self-confidence as a within-run rank: the share of this run's symbols on the sheet that the model was MORE
    # sure of. Raw numbers aren't comparable across models (Codex says 0.98 where Claude says 0.6); ranks are.
    confs_all = [s["confidence"] for s in syms.values() if s["confidence"] is not None]

    def conf_rank(c):
        return sum(1 for x in confs_all if x > c) / len(confs_all) if c is not None and confs_all else 0.5

    sym_feats, loc = {}, {}
    for sid, s in syms.items():
        tag = s["tag"]
        ph = bool(tag and PLACEHOLDER.search(tag))
        letters = ISA_TAG.match(PLACEHOLDER.sub("", tag or "").strip(" -").upper()) if tag else None
        f = {
            "xm_miss": (sum(1 for o in others_sym if not any_overlap(s["box"], o, s["class"])) / len(others_sym))
            if others_sym else 0.5,
            "xp_miss": (0.0 if any_overlap(s["box"], xp_syms, s["class"]) else 1.0) if xp_syms is not None else 0.5,
            "detached": 0.0 if (sid in kept and net_of.get(sid)) else (1.0 if image.exists() else 0.5),
            "dup_box": 1.0 if any(sc.iou(s["box"], o["box"]) >= 0.5 for oid, o in syms.items() if oid != sid) else 0.0,
            "tag_placeholder": 1.0 if ph else 0.0,
            "tag_missing": 1.0 if (not tag and s["class"] in TAGGED_CLASSES) else 0.0,
            "tag_malformed": 1.0 if (s["class"] == "instrumentation" and tag and not ph and not letters) else 0.0,
            "tag_dup": 1.0 if (tag and not ph and tag_count[norm(tag)] > 1) else 0.0,
            "is_general": 1.0 if s["class"] == "general" else 0.0,
            "low_conf": conf_rank(s["confidence"]),
        }
        sym_feats[sid] = f
        loc[sid] = (
            (sum(1 for o in others_sym if not any_overlap(s["box"], o)) / len(others_sym)) if others_sym else 0.5,
            (0.0 if any_overlap(s["box"], xp_syms) else 1.0) if xp_syms is not None else 0.5)

    link_feats = {}
    for a, b in links:
        sa, sb = syms.get(a), syms.get(b)
        size = pair_net.get((a, b))
        xm = 0.5
        if others_link and sa and sb:
            miss = 0
            for osyms, olinks in others_link:
                ca = {o["id"] for o in osyms.values() if sc.iou(sa["box"], o["box"]) >= 0.1}
                cb = {o["id"] for o in osyms.values() if sc.iou(sb["box"], o["box"]) >= 0.1}
                hit = any(tuple(sorted((x, y))) in olinks for x in ca for y in cb if x != y)
                miss += 0 if hit else 1
            xm = miss / len(others_link)
        link_feats[(a, b)] = {
            "_ends": (a, b), "_valid_ends": bool(sa and sb),
            "end_xm": max(loc[a][0], loc[b][0]) if sa and sb else 1.0,
            "end_xp": max(loc[a][1], loc[b][1]) if sa and sb else 1.0,
            "not_model": 0.0 if (a, b) in model_links else 1.0,
            "not_traced": 0.0 if size else 1.0,
            "net_size": min(1.0, math.log2(size) / 5) if size else 0.0,
            "xm_miss": xm,
            "low_conf": max(sym_feats[a]["low_conf"], sym_feats[b]["low_conf"]) if sa and sb else 1.0,
        }
    return {"symbols": syms, "symbol_features": sym_feats, "link_features": link_feats,
            "failed": not has_prediction(rec), "traced_run": traced_run}


# ---------------------------------------------------------------- the rating

def load_model(path=MODEL_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def logit_risk(part, f):
    z = part["intercept"] + sum(w * f[n] for n, w in zip(part["features"], part["coef"]))
    return 1 / (1 + math.exp(-z))


def reasons(part, f, limit=3, words=WHY):
    """The signals that pushed this item's risk up most (weight x value above 0.25), in plain language."""
    contrib = sorted(((w * f[n], n) for n, w in zip(part["features"], part["coef"]) if w * f[n] > 0.25), reverse=True)
    return [words[n] for _, n in contrib[:limit]]


def tier_of(risk, tiers):
    if risk is None:
        return "amber"
    return "green" if risk < tiers["green_max"] else "red" if risk >= tiers["red_min"] else "amber"


def rate_features(feats, model):
    """Apply the model to sheet_features() output."""
    out = {"symbols": {}, "links": {}}
    for sid, f in feats["symbol_features"].items():
        r = logit_risk(model["symbol"], f)
        out["symbols"][sid] = {"risk": round(r, 4), "tier": tier_of(r, model["tiers"]),
                               "why": reasons(model["symbol"], f), "features": f}
    for k, f in feats["link_features"].items():
        a, b = f["_ends"]
        if not f["_valid_ends"]:
            r, why = 1.0, ["an end of this link is not a valid symbol"]
        else:
            r = logit_risk(model["link"], f)
            why = reasons(model["link"], f, words=WHY_LINK)
        out["links"][k] = {"risk": round(r, 4), "tier": tier_of(r, model["tiers"]), "why": why,
                           "features": {n: f[n] for n in LINK_FEATURES}}
    return out


def rate_run(label, tool, sheet, images_dir=None, model=None):
    return rate_features(sheet_features(label, tool, sheet, images_dir), model or load_model())


def why_text(why, tier=None):
    if tier == "green":
        return "no strong warning signs" + (f" (minor: {'; '.join(why)})" if why else "")
    return "; ".join(why) if why else "no single strong signal; several small ones add up"


# ---------------------------------------------------------------- twin integration (called by build_twin.py)

def annotate_model(model, run_dir, sheets, images_dir=None):
    """Add "risk" = {risk_score, tier, why} to every twin item and stream, from the run the twin was built from.
    run_dir is runs/<label>/<tool>/. Items whose run can't be rated keep no "risk" (the queue shows them amber)."""
    run_dir = Path(run_dir)
    label, tool = run_dir.parent.name, run_dir.name
    global RUN_ROOTS
    roots = RUN_ROOTS
    if run_dir.parent.parent not in roots:
        RUN_ROOTS = [run_dir.parent.parent] + roots
    try:
        cp = load_model()
        rated = {}
        for s in sheets:
            try:
                rated[str(s)] = rate_run(label, tool, s, images_dir, cp)
            except Exception as e:  # a rating problem must never stop the twin from being built
                print(f"  confidence: sheet {s} not rated ({e})")
    finally:
        RUN_ROOTS = roots

    def pack(r):
        return {"risk_score": r["risk"], "tier": r["tier"], "why": why_text(r["why"], r["tier"])}

    tier_rank = {"red": 0, "amber": 1, "green": 2}
    for key in ("units", "instruments", "line_items", "offpage_connectors"):
        for x in model.get(key, []):
            got = [rated.get(str(p["sheet"]), {}).get("symbols", {}).get(str(p["symbol"])) for p in x["provenance"]]
            got = [g for g in got if g]
            if got:
                worst = max(got, key=lambda g: (-tier_rank[g["tier"]], g["risk"]))
                x["risk"] = pack(worst)
    for st in model.get("streams", []):
        if st.get("kind") != "extracted_link":
            continue
        k = tuple(sorted((str(st["from_symbol"]), str(st["to_symbol"]))))
        r = rated.get(str(st["sheet"]), {}).get("links", {}).get(k)
        if r:
            st["risk"] = pack(r)
    model.setdefault("meta", {})["risk_model"] = {"file": "scripts/confidence_model.json", "tiers": cp["tiers"],
                                                  "note": "risk from independent signals; see docs/TWIN_OUTPUTS.md"}
    return model


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True)
    ap.add_argument("--tool", default="codex")
    ap.add_argument("--sheets", default="0,1,2,3,4,5")
    ap.add_argument("--images", default=str(DATA))
    ap.add_argument("--out", default="", help="default out/confidence/<label>/<tool>.json")
    ap.add_argument("--holdout-ok", action="store_true", help="allow sheets outside the development set 0-5")
    a = ap.parse_args()
    sheets = [s.strip() for s in a.sheets.split(",") if s.strip()]
    if any(s not in DEV_SHEETS for s in sheets) and not a.holdout_ok:
        sys.exit("refusing sheets outside the development set 0-5 (docs/GOAL.md); pass --holdout-ok for the single "
                 "holdout run of the finished method")
    model = load_model()
    res = {}
    for s in sheets:
        r = rate_run(a.label, a.tool, s, a.images, model)
        res[s] = {"symbols": r["symbols"], "links": {f"{x}|{y}": v for (x, y), v in r["links"].items()}}
        n = Counter(v["tier"] for v in list(r["symbols"].values()) + list(r["links"].values()))
        print(f"{a.label}/{a.tool} sheet {s}: {len(r['symbols'])} symbols, {len(r['links'])} links; "
              f"green {n['green']} / amber {n['amber']} / red {n['red']}")
    out = Path(a.out) if a.out else ROOT / "out" / "confidence" / a.label / f"{a.tool}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
