"""Score the tag text a model read, against keys that carry tag truth (round 5, docs/GOAL.md).

Rules (fixed 2026-10-13, before any model run on a tag-bearing key; changing them is a visible commit):

Normalisation. Both sides are Unicode-NFKC-normalised and upper-cased.
  strict  : all whitespace removed, everything else kept ("PIC-101" != "PIC101").
  lenient : only letters and digits kept ("PIC-101" == "PIC 101" == "PIC101").
  strict is the headline; lenient is reported beside it because drawings and lists disagree on separators.

Geometry-keyed sheets (<id>.graphml + <id>.tags.json from scripts/adapt_dexpi.py):
  Symbols are paired with the unchanged scorer's own rough, class-agnostic match (score_pid2graph.match,
  IoU >= 0.1, greedy, one-to-one). Only key symbols whose label carries text count. Each is one of:
    correct  - paired, and the predicted tag equals the truth after normalisation;
    wrong    - paired, predicted tag present but different;
    no_tag   - paired, predicted tag empty/null;
    missed   - no predicted symbol paired with it.
  Reported: accuracy on found symbols = correct / (correct + wrong + no_tag), and end-to-end tag recall =
  correct / all key symbols with tag text (a missed symbol counts as a missed tag).

Tag-list-keyed sheets (<id>.taglist.json: identifiers from published equipment/instrument/valve lists that
are printed on the sheet; no boxes):
  A listed identifier is found if, after lenient normalisation, it occurs inside any predicted tag on that sheet
  (a bubble read as "PIC P0020" contains "P0020"). Reported: identifier recall overall and by list, and the share
  of found identifiers whose predicted symbol also has the list's class. Precision is NOT scored: the lists do not
  cover everything printed on a sheet (line numbers, nozzles, notes), so an extra predicted tag is not evidence
  of an error.

Failed or unparseable runs count as no output (every truth tag missed), never as skipped.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_pid2graph as sc  # noqa: E402


def _nfkc(text):
    return unicodedata.normalize("NFKC", text or "").upper()


def norm_strict(text):
    return re.sub(r"\s+", "", _nfkc(text))


def norm_lenient(text):
    return re.sub(r"[^A-Z0-9]", "", _nfkc(text))


def predicted_tags(prediction):
    out = {}
    for s in (prediction or {}).get("symbols") or []:
        if s.get("id") is not None:
            t = s.get("tag")
            out[str(s["id"])] = t if isinstance(t, str) and t.strip() else None
    return out


def score_geometry(graphml, tags_json, prediction, png):
    prediction = prediction or {"symbols": [], "connections": []}
    width, height = sc.png_size(png)
    nodes, _ = sc.load_key(graphml, width, height)
    keys = {k: v for k, v in nodes.items() if v["class"] in sc.SCORED}
    truth = {k: t for k, t in json.loads(Path(tags_json).read_text(encoding="utf-8"))["tags"].items()
             if t and k in keys}
    preds = sc.valid_symbols(prediction)
    tags = predicted_tags(prediction)
    paired = {kid: pid for pid, kid in sc.match(preds, keys, False, sc.THRESHOLDS["rough"]).items()}
    items = []
    for kid, true_tag in sorted(truth.items()):
        pid = paired.get(kid)
        got = tags.get(pid) if pid else None
        row = {"key": kid, "class": keys[kid]["class"], "truth": true_tag, "predicted": got}
        for name, f in (("strict", norm_strict), ("lenient", norm_lenient)):
            if pid is None:
                row[name] = "missed"
            elif got is None:
                row[name] = "no_tag"
            else:
                row[name] = "correct" if f(got) == f(true_tag) else "wrong"
        items.append(row)
    return {"items": items, **summarise_geometry(items)}


def summarise_geometry(items):
    out = {"with_truth": len(items)}
    for name in ("strict", "lenient"):
        c = {k: sum(1 for i in items if i[name] == k) for k in ("correct", "wrong", "no_tag", "missed")}
        found = c["correct"] + c["wrong"] + c["no_tag"]
        out[name] = {**c, "found": found,
                     "accuracy_on_found": round(c["correct"] / found, 3) if found else None,
                     "end_to_end_recall": round(c["correct"] / len(items), 3) if items else None}
    return out


def score_taglist(taglist_json, prediction):
    prediction = prediction or {"symbols": []}
    key = json.loads(Path(taglist_json).read_text(encoding="utf-8"))
    syms = [(norm_lenient(s.get("tag")), s.get("class")) for s in prediction.get("symbols") or []
            if isinstance(s.get("tag"), str) and s.get("tag").strip()]
    items = []
    for it in key["items"]:
        ident = norm_lenient(it["identifier"])
        hits = [cls for tag, cls in syms if ident and ident in tag]
        items.append({"identifier": it["identifier"], "list": it["list"], "class": it["class"],
                      "found": bool(hits), "class_agrees": it["class"] in hits})
    return {"items": items, "predicted_tags": len(syms), **summarise_taglist(items)}


def summarise_taglist(items):
    def part(rows):
        found = sum(1 for r in rows if r["found"])
        return {"listed": len(rows), "found": found, "recall": round(found / len(rows), 3) if rows else None,
                "found_with_list_class": sum(1 for r in rows if r["class_agrees"])}
    return {"all": part(items), "by_list": {k: part([r for r in items if r["list"] == k])
                                            for k in sorted({r["list"] for r in items})}}


if __name__ == "__main__":
    # python scripts/score_tags.py <key .graphml|.taglist.json> <prediction.json> [--tags <.tags.json>] [--png <image>]
    key, pred_path = Path(sys.argv[1]), Path(sys.argv[2])
    pred = json.loads(pred_path.read_text(encoding="utf-8"))
    pred = pred.get("prediction", pred) if "symbols" not in pred else pred
    if key.name.endswith(".taglist.json"):
        result = score_taglist(key, pred)
    else:
        tags = sys.argv[sys.argv.index("--tags") + 1] if "--tags" in sys.argv else str(key.with_suffix(".tags.json"))
        png = sys.argv[sys.argv.index("--png") + 1] if "--png" in sys.argv else str(key.with_suffix(".png"))
        result = score_geometry(key, tags, pred, png)
    print(json.dumps({k: v for k, v in result.items() if k != "items"}, indent=1))
