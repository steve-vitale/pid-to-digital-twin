"""Diff an extracted twin against the verified Tennessee Eastman model: what a reviewer would have to correct.

The extracted twin (scripts/build_twin.py output) came from the generated TE sheets (scripts/draw_pid_from_model.py).
The verified model is data/te_process_model.json (36/37 confirmed, 1 corrected against the simulator source).
Matching is by tag only, after upper-casing and dropping separators ("FI 101" = "FI-101"); nothing is matched by
position, so a misread tag shows up as one missing item plus one extra item, exactly as a reviewer would see it.

Compared, item by item:
  units          found as equipment / found but as a line item (wrong role) / missing; class vs the verified type
  instruments    found / missing; kind (measurement vs final element); measured variable from the ISA first letter;
  final elements the owning unit the converter chose vs the verified unit
  extras         extracted tagged items the verified model doesn't have (to delete or explain)
  topology       unit-to-unit process connections. Extracted: two units are connected when the extracted links join
                 them through non-equipment symbols only, with off-page pairs joining sheets. Verified: the model's
                 streams between units (battery-limit streams are not unit pairs).
  not on a drawing  fields the verified model holds that no P&ID prints (XMEAS/XMV index, units of measure,
                 descriptions, verification evidence). These come from the instrument index or I/O list.

Usage: python scripts/te_model_diff.py <plant_model.json> [--verified data/te_process_model.json] [--name NAME]
Writes out/te_pid/diff_<name>.{md,json}.
"""
import argparse
import json
import re
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPE_CLASS = {"compressor": "pump", "feed_header": "general"}  # every other TE unit type is drawn as a vessel (tank)
FIRST_LETTER_VARIABLE = {"flow": "F", "pressure": "P", "level": "L", "temperature": "T", "power": "J",
                         "composition": "A"}
SAME_VARIABLE = {"composition": "analysis"}  # the model says composition; ISA-5.1's A is "analysis": same thing


def norm(tag):
    return re.sub(r"[^A-Z0-9]", "", str(tag or "").upper())


def diff(twin, verified):
    by_id = {x["id"]: x for k in ("units", "instruments", "line_items", "offpage_connectors") for x in twin.get(k, [])}
    tag_of = lambda aid: (by_id.get(aid) or {}).get("tag")  # noqa: E731
    ext_units = {norm(u["tag"]): u for u in twin["units"] if u.get("tag")}
    ext_line = {norm(x["tag"]): x for x in twin["line_items"] if x.get("tag")}
    ext_inst = defaultdict(list)
    for x in twin["instruments"]:
        if x.get("tag"):
            ext_inst[norm(x["tag"])].append(x)
    rows, corrections = [], []

    # units
    for u in verified["units"]:
        want = TYPE_CLASS.get(u["type"], "tank")
        e, role = ext_units.get(norm(u["id"])), "equipment"
        if not e and norm(u["id"]) in ext_line:
            e, role = ext_line[norm(u["id"])], "line item"
        status = "missing" if not e else "ok" if role == "equipment" and e["class"] == want else "wrong role/class"
        rows.append({"kind": "unit", "tag": u["id"], "status": status,
                     "extracted": None if not e else {"id": e["id"], "class": e["class"], "role": role}})
        if not e:
            corrections.append(f"ADD unit {u['id']} ({u['name']}): not found on the drawings")
        elif status != "ok":
            corrections.append(f"RECLASS {u['id']}: extracted as {role} '{e['class']}', the model has a {u['type']} "
                               f"unit")

    # instruments and final elements
    verified_items = [(i, "instrument") for i in verified["instruments"]] + \
                     [(f, "final_element") for f in verified["final_elements"]]
    for it, kind in verified_items:
        cands = ext_inst.get(norm(it["tag"]), [])
        if not cands:
            rows.append({"kind": kind, "tag": it["tag"], "status": "missing"})
            corrections.append(f"ADD {it['tag']} ({it['description']}): tag not read on the drawings")
            continue
        e = cands[0]
        problems = []
        ext_kind = "final_element" if (e.get("instrument_kind") or "").startswith(("final", "operated")) else \
            "instrument"
        if ext_kind != kind:
            problems.append(f"kind {ext_kind} (model: {kind})")
        if kind == "instrument" and it.get("variable") in FIRST_LETTER_VARIABLE and \
                e.get("variable") != SAME_VARIABLE.get(it["variable"], it["variable"]):
            problems.append(f"variable {e.get('variable')} (model: {it['variable']})")
        unit_tag = tag_of(e.get("unit")) if e.get("unit") else None
        if norm(unit_tag) != norm(it["unit"]):
            problems.append(f"unit {unit_tag or 'none'} (model: {it['unit']})")
            corrections.append(f"SET unit of {it['tag']}: {unit_tag or 'none'} -> {it['unit']} "
                               f"(converter rule: {e.get('unit_method')})")
        if len(cands) > 1:
            problems.append(f"read on {len(cands)} symbols")
            corrections.append(f"MERGE {it['tag']}: the tag was read on {len(cands)} instrument symbols")
        rows.append({"kind": kind, "tag": it["tag"], "status": "ok" if not problems else "found, fields differ",
                     "problems": problems, "extracted": {"id": e["id"], "tag": e["tag"], "unit": unit_tag,
                                                         "kind": ext_kind, "variable": e.get("variable")}})

    # extras: tagged extracted items that are not in the verified model
    known = {norm(u["id"]) for u in verified["units"]} | {norm(i["tag"]) for i, _ in verified_items}
    extras = []
    for x in twin["units"] + twin["instruments"] + twin["line_items"]:
        if x.get("tag") and norm(x["tag"]) not in known:
            extras.append({"id": x["id"], "tag": x["tag"], "class": x["class"]})
            corrections.append(f"DELETE or explain {x['id']} '{x['tag']}' ({x['class']}): not a model item")
    untagged = [x["id"] for x in twin["units"] + twin["instruments"] if not x.get("tag")]
    for aid in untagged:
        corrections.append(f"DELETE or tag {aid}: extracted without a tag")

    # topology: unit pairs
    units_by_tag = {norm(u["tag"]): u["id"] for u in twin["units"] if u.get("tag")}
    for x in twin["line_items"]:  # a unit drawn as a line item still counts as that unit for topology
        if x.get("tag") and norm(x["tag"]) in {norm(u["id"]) for u in verified["units"]}:
            units_by_tag.setdefault(norm(x["tag"]), x["id"])
    unit_ids = set(units_by_tag.values())
    adj = defaultdict(set)
    for s in twin["streams"]:
        adj[s["from"]].add(s["to"])
        adj[s["to"]].add(s["from"])
    for p in twin.get("offpage_pairs", []):
        adj[p["a"]].add(p["b"])
        adj[p["b"]].add(p["a"])
    instrument_ids = {x["id"] for x in twin["instruments"]}
    ext_pairs = set()
    for start in unit_ids:
        seen, q = {start}, deque([start])
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt in seen or nxt in instrument_ids:
                    continue
                seen.add(nxt)
                if nxt in unit_ids:
                    ext_pairs.add(frozenset((tag_of(start), tag_of(nxt))))
                else:
                    q.append(nxt)
    ext_pairs = {frozenset(norm(t) for t in p) for p in ext_pairs if len(p) == 2}
    ver_pairs = {frozenset((norm(s["from"]), norm(s["to"]))) for s in verified["streams"]
                 if "BL" not in (s["from"], s["to"]) and s["from"] != s["to"]}
    name = {norm(u["id"]): u["id"] for u in verified["units"]}
    show = lambda p: " - ".join(sorted(name.get(t, t) for t in p))  # noqa: E731
    for p in sorted(ver_pairs - ext_pairs, key=show):
        corrections.append(f"ADD connection {show(p)}: a model stream joins these units")
    for p in sorted(ext_pairs - ver_pairs, key=show):
        corrections.append(f"DELETE connection {show(p)}: no model stream joins these units")
    topo = {"verified_pairs": sorted(show(p) for p in ver_pairs), "extracted_pairs": sorted(show(p) for p in ext_pairs),
            "matched": len(ver_pairs & ext_pairs), "missing": sorted(show(p) for p in ver_pairs - ext_pairs),
            "extra": sorted(show(p) for p in ext_pairs - ver_pairs)}

    not_on_drawing = {"xmeas/xmv index": sum(1 for i, _ in verified_items if "xmeas" in i or "xmv" in i),
                      "unit of measure": sum(1 for i, _ in verified_items if i.get("uom")),
                      "description": len(verified_items), "verification evidence": len(verified_items)}
    counts = defaultdict(int)
    for r in rows:
        counts[(r["kind"], r["status"])] += 1
    return {"rows": rows, "extras": extras, "untagged": untagged, "topology": topo, "not_on_drawing": not_on_drawing,
            "corrections": corrections, "counts": {f"{k[0]}: {k[1]}": v for k, v in sorted(counts.items())}}


def report(d, name, twin_path):
    ok = sum(1 for r in d["rows"] if r["status"] == "ok")
    md = [f"# Reviewer diff: extracted twin vs the verified TE model ({name})", "",
          f"Extracted twin: `{twin_path}`. Verified model: `data/te_process_model.json`. Generated by "
          "`scripts/te_model_diff.py`; matching is by tag only.", "",
          f"**{ok} of {len(d['rows'])} verified units and tagged items came through exactly** (tag read, right kind, "
          f"variable and owning unit). Unit-to-unit connections: {d['topology']['matched']} of "
          f"{len(d['topology']['verified_pairs'])} recovered, {len(d['topology']['extra'])} extra.", "",
          f"**{len(d['corrections'])} reviewer corrections** to reach the verified model's structure:", ""]
    md += [f"1. {c}" for c in d["corrections"]] or ["(none)"]
    md += ["", "## Item by item", "", "| Kind | Tag | Status | Notes |", "|---|---|---|---|"]
    for r in d["rows"]:
        notes = "; ".join(r.get("problems", [])) or ("" if r["status"] != "missing" else "not read")
        if r["kind"] == "unit" and r.get("extracted"):
            notes = f"extracted as {r['extracted']['role']} ({r['extracted']['class']})"
        md.append(f"| {r['kind']} | {r['tag']} | {r['status']} | {notes} |")
    md += ["", "## Connections between units", "",
           f"- Verified (model streams between units): {', '.join(d['topology']['verified_pairs'])}",
           f"- Extracted: {', '.join(d['topology']['extracted_pairs']) or 'none'}", "",
           "## What no drawing carries", "",
           "These verified fields are not printed on a P&ID, so no extraction can supply them. A plant takes them "
           "from its instrument index or I/O list (here: the simulator variable list):", ""]
    md += [f"- {k}: {v} items" for k, v in d["not_on_drawing"].items()]
    md.append("")
    return "\n".join(md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("twin")
    ap.add_argument("--verified", default="data/te_process_model.json")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    twin_path = Path(a.twin) if Path(a.twin).is_absolute() else ROOT / a.twin
    twin = json.loads(twin_path.read_text(encoding="utf-8"))
    verified = json.loads((ROOT / a.verified).read_text(encoding="utf-8"))
    d = diff(twin, verified)
    name = a.name or twin_path.parent.name
    out = ROOT / "out" / "te_pid"
    out.mkdir(parents=True, exist_ok=True)
    rel = twin_path.relative_to(ROOT).as_posix() if twin_path.is_relative_to(ROOT) else twin_path.name
    (out / f"diff_{name}.json").write_text(json.dumps(d, indent=1), encoding="utf-8")
    text = report(d, name, rel)
    (out / f"diff_{name}.md").write_text(text, encoding="utf-8")
    print(text[:3000])


if __name__ == "__main__":
    main()
