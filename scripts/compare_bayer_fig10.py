"""Check the Bayer residue treater model against the report's own drawing (CSB Figure 10, p. 29).

python scripts/compare_bayer_fig10.py            # writes out/bayer_rt/fig10_compare.{json,md}
python scripts/compare_bayer_fig10.py --check    # exit 1 if the committed comparison is stale

Figure 10 is a simplified piping layout drawn by someone else: equipment, transmitters, valves and lines, no tags.
data/bayer_rt/fig10_inventory.json records what it shows, read from the figure alone. This script compares it with
data/bayer_rt/process_model.json at the level the figure is drawn:

- every figure unit is a model unit (the inventory names which);
- every figure line is a model stream with the same two ends (the inventory claims which stream; the ends check the
  claim), counting a line that joins or branches off another line;
- the items on each line, and mounted on each unit, are the same TYPES in the same numbers (control valve, manual
  valve, relief valve, pressure / level / temperature / flow transmitter);
- every model item the figure doesn't show is listed, and is a difference unless the model already says
  drawn_in_source_figure: false.

It also checks the DRAWING generated from the model (data/bayer_rt/pid/key.json, the answer key
scripts/draw_pid_from_model.py emits with the sheet): each figure line is traced through the drawn line network
from end to end, counting the valves and transmitters actually drawn on that path.

Differences are listed, never tuned away. Stdlib only.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "data" / "bayer_rt" / "fig10_inventory.json"
MODEL = ROOT / "data" / "bayer_rt" / "process_model.json"
OUT = ROOT / "out" / "bayer_rt"


def counts(c):
    """A Counter as a dict in a fixed order, so the written report doesn't change between runs."""
    return dict(sorted(c.items()))


def model_items(model):
    """(tag, type, unit, stream, shown_in_figure) for every drawable model item."""
    for it in model["instruments"]:
        yield it["tag"], f"{it['variable']}_transmitter", it.get("unit"), it.get("stream"), it.get("drawn_in_source_figure", True)
    for it in model["final_elements"]:
        yield it["tag"], "control_valve", it.get("unit"), it.get("stream"), it.get("drawn_in_source_figure", True)
    for it in model["manual_valves"]:
        yield it["tag"], "manual_valve", it.get("unit"), it.get("stream"), it.get("drawn_in_source_figure", True)
    for it in model["relief_devices"]:
        yield it["tag"], "relief_valve", it.get("unit"), it.get("stream"), it.get("drawn_in_source_figure", True)


def compare(fig, model):
    unit_map = {u["id"]: u["model"] for u in fig["units"]}
    terminals = {t["id"] for t in fig["terminals"]}
    line_stream = {l["id"]: l["model_stream"] for l in fig["lines"]}
    streams = {s["id"]: s for s in model["streams"]}
    model_units = {u["id"] for u in model["units"]}
    items = list(model_items(model))
    matched, rows, diffs = set(), [], []

    def end(e):
        if isinstance(e, list):
            return frozenset(end(x) for x in e)
        if e in unit_map:
            return unit_map[e]
        if e in terminals:
            return "BL"
        if e in line_stream:
            return f"stream:{line_stream[e]}"
        raise ValueError(f"figure end {e!r} is not a unit, terminal or line")

    def stream_from(s):
        if s.get("branches_from"):
            return f"stream:{s['branches_from']}"
        froms = [s["from"]] + list(s.get("joins_from", []))
        return frozenset(froms) if len(froms) > 1 else froms[0]

    for u in fig["units"]:
        ok = u["model"] in model_units
        rows.append({"what": f"unit {u['label'] or u['id']}", "figure": u["id"], "model": u["model"], "ok": ok})
        if not ok:
            diffs.append(f"Figure unit {u['id']} maps to {u['model']}, which is not a model unit.")

    for l in fig["lines"]:
        sid = l["model_stream"]
        s = streams.get(sid)
        want = Counter(i["type"] for i in l["items"])
        if s is None:
            rows.append({"what": f"line {l['id']}", "figure": f"{l['from']} -> {l['to']}", "model": f"{sid} (missing)", "ok": False})
            diffs.append(f"Figure line {l['id']} ({l['from']} -> {l['to']}, {counts(want) or 'no items'}): the model has no stream {sid}.")
            continue
        ends_ok = (end(l["from"]), end(l["to"])) == (stream_from(s), s["to"])
        on = [(t, ty) for t, ty, _, st, shown in items if st == sid and shown]
        got = Counter(ty for _, ty in on)
        ok = ends_ok and got == want
        rows.append({"what": f"line {l['id']}", "figure": f"{l['from']} -> {l['to']}: {counts(want)}",
                     "model": f"{sid} {s['from']} -> {s['to']}: {counts(got)}", "ok": ok})
        if not ends_ok:
            diffs.append(f"Line {l['id']}: the figure joins {l['from']} -> {l['to']}; model stream {sid} runs "
                         f"{s.get('branches_from') or s['from']} -> {s['to']}.")
        if got != want:
            diffs.append(f"Line {l['id']} / {sid}: the figure shows {counts(want) or 'nothing'}, the model has "
                         f"{counts(got) or 'nothing'} ({', '.join(t for t, _ in on) or 'no tags'}).")
        matched.update(t for t, _ in on)

    for uid in sorted({m["unit"] for m in fig["unit_mounted"]}):
        mu = unit_map[uid]
        want = Counter(m["type"] for m in fig["unit_mounted"] if m["unit"] == uid)
        on = [(t, ty) for t, ty, unit, st, shown in items if unit == mu and not st and shown]
        got = Counter(ty for _, ty in on)
        rows.append({"what": f"mounted on {uid}", "figure": counts(want), "model": f"{mu}: {counts(got)}", "ok": got == want})
        if got != want:
            only_fig, only_model = want - got, got - want
            if only_fig:
                diffs.append(f"Mounted on {uid}: the figure shows {counts(only_fig)} that the model doesn't have.")
            if only_model:
                diffs.append(f"Mounted on {mu}: the model has {counts(only_model)} that the figure doesn't show.")
        matched.update(t for t, _ in on)

    not_in_fig = []
    for t, ty, unit, st, shown in items:
        if t in matched:
            continue
        not_in_fig.append({"tag": t, "type": ty, "declared_not_shown": not shown})
        if shown:
            diffs.append(f"{t} ({ty}) is in the model as shown in Fig 10, but no figure line or unit carries it.")
    passed = sum(r["ok"] for r in rows)
    return {"rows": rows, "passed": passed, "total": len(rows), "differences": diffs,
            "model_items_not_in_figure": not_in_fig}


def compare_drawing(fig, model, key):
    """Trace every figure line through the drawn sheet: the drawn path between its two ends, and what sits on it.

    Paths run only through line junctions (connectors) and valves, never through equipment, flags or bubbles, so a
    path exists only if the generator really drew the line. A transmitter counts when its tap hangs off the path.
    """
    nodes, adj = {}, {}
    for sh in key["sheets"].values():
        nodes.update(sh["symbols"])
        for a, b in sh["edges"]:
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    def cls(n):                             # key.json leaves out line junctions (connectors); edges keep them
        return nodes[n]["class"] if n in nodes else "connector"

    hidden = {it["tag"] for k in ("instruments", "final_elements", "manual_valves", "relief_devices")
              for it in model[k] if it.get("drawn_in_source_figure") is False}
    var = {it["tag"]: it["variable"] for it in model["instruments"]}
    by_ref = {n["model_ref"]: nid for nid, n in nodes.items() if n.get("model_ref")}
    unit_node = {u["id"]: by_ref[f"unit:{u['model']}"] for u in fig["units"]}
    terminals = {t["id"] for t in fig["terminals"]}
    term_flag = {}
    for l in fig["lines"]:                  # a terminal is the flag of a line ending there that has one
        flag = by_ref.get(f"stream:{l['model_stream']}")
        for e in (l["from"], l["to"]):
            if flag and isinstance(e, str) and e in terminals:
                term_flag.setdefault(e, flag)
    trails = {}

    def ends(e):
        if isinstance(e, list):
            return [x for y in e for x in ends(y)]
        if e in unit_node:
            return [{unit_node[e]}]
        if e in term_flag:
            return [{term_flag[e]}]
        if e in trails:                     # a line that branches off another starts anywhere on it
            return [trails[e]]
        raise ValueError(f"figure end {e!r} has no drawn symbol")

    def path(src, dst):
        prev, todo = {n: None for n in src}, list(src)
        while todo:
            nxt = []
            for n in todo:
                if n in dst:
                    out = []
                    while n is not None:
                        out.append(n)
                        n = prev[n]
                    return out
                for m in adj.get(n, ()):
                    if m not in prev and (m in dst or cls(m) in ("connector", "valve")):
                        prev[m] = n
                        nxt.append(m)
            todo = nxt
        return None

    def kind(nid):
        n = nodes[nid]
        if n["class"] == "valve":
            return {"final_element": "control_valve", "manual_valve": "manual_valve",
                    "relief_valve": "relief_valve"}.get(n["model_kind"])
        return f"{var[n['model_ref']]}_transmitter"

    rows, diffs = [], []
    for l in fig["lines"]:
        trail, found = set(), True
        for a in ends(l["from"]):
            for b in ends(l["to"]):
                p = path(a, b)
                found = found and p is not None
                trail.update(p or [])
        trails[l["id"]] = trail
        # A branch shares its junction with the line it leaves; what hangs off that junction belongs to that line.
        trail = trail - set().union(*(trails[e] for e in (l["from"], l["to"]) if isinstance(e, str) and e in trails
                                      and e != l["id"]))
        on = {n for n in trail if cls(n) == "valve" and nodes[n].get("model_ref")}
        on |= {m for n in trail if cls(n) == "connector" for m in adj.get(n, ())
               if m in nodes and nodes[m].get("model_kind") == "instrument"}
        on = {n for n in on if nodes[n]["model_ref"] not in hidden}
        got = Counter(kind(n) for n in on)
        want = Counter(i["type"] for i in l["items"])
        tags = ", ".join(sorted(nodes[n]["model_ref"] for n in on)) or "nothing"
        ok = found and got == want
        rows.append({"what": f"line {l['id']}", "figure": f"{l['from']} -> {l['to']}: {counts(want)}",
                     "drawing": f"{counts(got)} ({tags})" if found else "no drawn path", "ok": ok})
        if not found:
            diffs.append(f"Line {l['id']}: no drawn line joins {l['from']} and {l['to']}.")
        elif got != want:
            diffs.append(f"Line {l['id']}: the figure shows {counts(want) or 'nothing'}, the drawing has "
                         f"{counts(got) or 'nothing'} ({tags}).")
    return {"rows": rows, "passed": sum(r["ok"] for r in rows), "total": len(rows), "differences": diffs}


def render(res):
    out = ["# The residue treater model against the report's Figure 10",
           "",
           "Generated by `scripts/compare_bayer_fig10.py` from `data/bayer_rt/fig10_inventory.json` (what Figure 10, "
           "p. 29, shows) and `data/bayer_rt/process_model.json`. The figure has no tags, so the check is at the "
           "level it is drawn: equipment, the two ends of every line, and the types and numbers of items on each.",
           "",
           f"**{res['passed']} of {res['total']} checks agree.**",
           "",
           "| Check | Figure 10 | Model | Agrees |",
           "|---|---|---|---|"]
    for r in res["rows"]:
        out.append(f"| {r['what']} | {r['figure']} | {r['model']} | {'yes' if r['ok'] else 'NO'} |")
    out += ["", "## Differences", ""]
    out += [f"- {d}" for d in res["differences"]] or ["None."]
    out += ["", "## Model items the figure doesn't show", ""]
    out += [f"- {n['tag']} ({n['type']})" + (": the model already says it isn't in the figure" if n["declared_not_shown"] else "")
            for n in res["model_items_not_in_figure"]] or ["None."]
    if res.get("drawing"):
        d = res["drawing"]
        out += ["", "## The generated drawing against Figure 10", "",
                "Each figure line traced through the drawn sheet's answer key (`data/bayer_rt/pid/key.json`): is there "
                "a drawn path between its two ends, and are the same types of item drawn on it? This checks the "
                "generator's connections, not just the model's stream fields.", "",
                f"**{d['passed']} of {d['total']} lines agree.**", "",
                "| Line | Figure 10 | Drawing | Agrees |", "|---|---|---|---|"]
        out += [f"| {r['what']} | {r['figure']} | {r['drawing']} | {'yes' if r['ok'] else 'NO'} |" for r in d["rows"]]
        out += ["", "### Differences", ""] + ([f"- {x}" for x in d["differences"]] or ["None."])
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed comparison is stale")
    ap.add_argument("--key", default="data/bayer_rt/pid/key.json", help="the generated drawing's answer key")
    a = ap.parse_args()
    fig, model = json.loads(FIG.read_text(encoding="utf-8")), json.loads(MODEL.read_text(encoding="utf-8"))
    res = compare(fig, model)
    key = ROOT / a.key
    if key.exists():
        res["drawing"] = compare_drawing(fig, model, json.loads(key.read_text(encoding="utf-8")))
    js, md = json.dumps(res, indent=1, default=str) + "\n", render(res)
    if a.check:
        stale = [p.name for p, txt in ((OUT / "fig10_compare.json", js), (OUT / "fig10_compare.md", md))
                 if not p.exists() or p.read_text(encoding="utf-8") != txt]
        if stale:
            sys.exit(f"stale: {stale}; run python scripts/compare_bayer_fig10.py")
        print("fig10 comparison is current")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fig10_compare.json").write_text(js, encoding="utf-8", newline="\n")
    (OUT / "fig10_compare.md").write_text(md, encoding="utf-8", newline="\n")
    print(f"model: {res['passed']} of {res['total']} agree; {len(res['differences'])} differences")
    for d in res["differences"]:
        print(" -", d)
    if res.get("drawing"):
        print(f"drawing: {res['drawing']['passed']} of {res['drawing']['total']} lines agree")
        for d in res["drawing"]["differences"]:
            print(" -", d)


if __name__ == "__main__":
    main()
