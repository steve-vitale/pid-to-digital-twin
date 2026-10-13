"""The OPEN100 plant structure that needs no process data: areas, equipment and what each is for, the main flow paths
between equipment, the 12 sheets stitched into one plant by their off-page connectors, a tour order, and the
isolation points a lockout/tagout review would start from.

Inputs (all committed): the extracted twin (out/twin/r2-tiles-trace/codex/plant_model.json), the inferred flow
directions (out/open100_structural/flow_direction.json, scripts/flow_direction.py) and the drawing register read
from the title blocks of the development sheets (data/sheet_registers/open100_dev.csv).
Output: out/open100_structural/plant_structure.json (and loto_isolation_points.csv).

Every name and purpose says where it came from:
  equipment_schedule  the equipment schedule printed along the bottom of the drawing ("SERVICE: LETDOWN FILTER"),
                   transcribed by scripts/transcribe_equipment_schedules.py into data/open100_equipment_schedule.json
  title_block      the drawing register, read by a person from the sheet's title block (development sheets only)
  connector_text   what OTHER sheets' off-page connectors call this drawing ("RES HEAT REMOVAL SYSTEM ... PID 120-1")
  drawing_label    the equipment's own text on the drawing when it is words, not a tag ("AIR COOLED CONDENSER")
  tag_code         the equipment-type code inside the tag (the "HX" in RHR-HX-121A), read with a common convention;
                   the site's own tag standard would confirm it
  generic          a class description only ("tank" in PID2Graph covers vessels, exchangers and tanks)
No process data is used anywhere. Nothing here is a live value.

  python scripts/open100_structure.py
"""
import csv
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TWIN = ROOT / "out" / "twin" / "r2-tiles-trace" / "codex" / "plant_model.json"
DIRS = ROOT / "out" / "open100_structural" / "flow_direction.json"
REGISTER = ROOT / "data" / "sheet_registers" / "open100_dev.csv"
SCHEDULE = ROOT / "data" / "open100_equipment_schedule.json"
OUT = ROOT / "out" / "open100_structural"

GENERIC = {
    "tank": "Vessel class. PID2Graph's 'tank' covers tanks, pressure vessels, heat exchangers and similar shells: "
            "it holds, heats, cools or separates process fluid.",
    "pump": "Pump class: moves liquid from its suction to its discharge. Motor-driven, so it has an electrical "
            "energy source as well as the process fluid. (On sheet 1 this class also caught the air-cooler fans.)",
    "general": "Unclassified equipment symbol: the extraction saw equipment but could not give it a class.",
}
# Equipment-type codes inside tags (SYS-CODE-NNN). A common reading of this drawing set's tags, not the site's tag
# standard, which would be the authority.
TAG_CODES = {
    "PU": "pump", "TK": "tank", "HTR": "heater", "HX": "heat exchanger", "XR": "reactor vessel",
    "SG": "steam generator", "VCT": "volume control tank", "FL": "filter", "ION": "ion exchanger",
    "AC": "air-cooled condenser", "V": "vessel", "VE": "vessel", "EX": "heat exchanger", "AN": "analyzer or sampler",
    "AXC": "auxiliary cooler", "SX": "skid or unit package", "XSS": "steam header or separator",
}
UTILITY_WORDS = ("STEAM", "COOLING WATER", "SERVICE WATER", "MAKE-UP", "MAKEUP", "AIR", "DRAIN", "WASTE", "VENT",
                 "SAMPLE", "CHEMICAL ADDITION", "GLAND", "BLOWDOWN")
VENT_DRAIN_WORDS = ("VENT", "DRAIN", "BLOWDOWN")
CONTROL_VALVE = re.compile(r"^(FCV|TCV|LCV|PCV|LVC|HCV)\b")
MOTOR_VALVE = re.compile(r"^(MOV|MSIV|MSV|MSBV)\b")
RELIEF = re.compile(r"^(PSV|PRV|RV|AORV|RD)\b")


DASHES = re.compile("[%s]" % "".join(map(chr, (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212, 0xFFFD))))


def norm(text):
    """Whitespace collapsed and every dash-like character read as '-'. The drawings' text uses en dashes in many
    drawing numbers ("PID 110" + en dash + "1"), which the twin's converter did not read as numbers."""
    return re.sub(r"\s+", " ", DASHES.sub("-", text or "")).strip()


def drawing_number(text):
    m = re.search(r"(\d{3})\s*-\s*0?(\d{1,2})\b", norm(text))
    return f"{m.group(1)}-{int(m.group(2))}" if m else None


def connector_name(text):
    """What a connector calls the system it leads to, minus drawing numbers, grid refs and bare system codes."""
    t = norm(text).upper()
    t = re.sub(r"\(\s*[A-Z]\s*-\s*\d+\s*\)", " ", t)
    t = re.sub(r"[A-Z]*-?PID\s*-?\s*\d{3}\s*-\s*\d+", " ", t)
    t = re.sub(r"\bPID\b|\b\d{3}-\d+\b", " ", t)
    words = [w for w in t.split() if not (w.isalpha() and w.isupper() and len(w) <= 5 and w not in
                                          ("WATER", "STEAM", "TANK", "AUX", "MAIN", "HIGH", "VENT", "AIR", "HEAT", "RES",
                                           "RES.", "FW", "TO", "LP", "HP", "&"))]
    t = " ".join(words).strip(" -.")
    return t if len(t.split()) >= 2 else None


def load_schedule():
    if not SCHEDULE.exists():
        return {}
    doc = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    return {(sheet, norm(r["tag"]).replace(" ", "").upper()): r["service"]
            for sheet, rows in doc.get("sheets", {}).items() for r in rows}


def equipment_purpose(u, schedule=None):
    tag = norm(u.get("tag"))
    for p in u.get("provenance", []):
        service = (schedule or {}).get((p["sheet"], tag.replace(" ", "").upper()))
        if service:
            return {"text": service.capitalize(), "source": "equipment_schedule"}
    words = re.findall(r"[A-Z]{3,}", tag.upper())
    if tag and len(words) >= 2 and not re.search(r"\d", tag.split()[0] if tag else ""):
        return {"text": tag.title(), "source": "drawing_label"}
    m = re.match(r"^[A-Z]{2,5}[- ]([A-Z]{1,4})[- ]?\d", tag.upper()) if tag else None
    if m and m.group(1) in TAG_CODES:
        return {"text": TAG_CODES[m.group(1)].capitalize() + " (from the tag code '%s')" % m.group(1),
                "source": "tag_code"}
    return {"text": GENERIC[u["class"]], "source": "generic"}


def load_register():
    if not REGISTER.exists():
        return {}
    rows = [l for l in REGISTER.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    return {r["sheet"]: r for r in csv.DictReader(rows)}


def build(model, dirs):
    reg = load_register()
    schedule = load_schedule()
    recs = {r["id"]: r for r in dirs["streams"]}
    sheets = [s["sheet"] for s in model["systems"]]
    dn_of = {}
    for s in model["systems"]:
        r = reg.get(s["sheet"])
        if r:
            dn_of[s["sheet"]] = (r["drawing_number"], "title_block")
        elif s.get("drawing_number"):
            dn_of[s["sheet"]] = (s["drawing_number"], "inferred from connector references (twin)")
        else:
            dn_of[s["sheet"]] = (None, s.get("drawing_number_method") or "unknown")
    sheet_of_dn = {dn: sh for sh, (dn, _) in dn_of.items() if dn}
    conns = model["offpage_connectors"]
    sheet_of = {}
    for key in ("units", "instruments", "line_items", "offpage_connectors"):
        for x in model[key]:
            sheet_of[x["id"]] = x["provenance"][0]["sheet"]
    # area names: title block first, else what other sheets' connectors call the drawing
    called = defaultdict(Counter)
    for c in conns:
        dn = drawing_number(c["text"])
        name = connector_name(c["text"])
        if dn and name and sheet_of[c["id"]] != sheet_of_dn.get(dn):
            called[dn][name] += 1
    flags = {}
    for sh, p in dirs["sheets"].items():
        for sid, f in p["flags"].items():
            flags[(sh, sid)] = f
    areas = []
    for s in model["systems"]:
        sh = s["sheet"]
        dn, dn_src = dn_of[sh]
        r = reg.get(sh)
        if r:
            name, src = r["system_name"], "title_block"
        elif dn and called.get(dn):
            # prefer a name that says SYSTEM: "RCS PID 100-2 AUX COOLING WATER" names the service on the line,
            # "REACTOR COOLANT SYSTEM RCS-PID-100-2" names the drawing
            best = sorted(called[dn].items(), key=lambda kv: ("SYSTEM" not in kv[0], -kv[1], kv[0]))[0][0]
            name, src = best.title(), "connector_text"
        else:
            name, src = None, "none"
        areas.append({"sheet": sh, "drawing_number": dn, "drawing_number_source": dn_src,
                      "system_code": r["system_code"] if r else s.get("system_code"),
                      "name": name, "name_source": src,
                      "label": "%s%s" % (name or ("Sheet %s (%s tags)" % (sh, s.get("system_code") or "?")),
                                         " · PID %s" % dn if dn else "")})
    # equipment
    equipment = []
    for u in model["units"]:
        b = u["provenance"][0]["box_0_1000"]
        equipment.append({"id": u["id"], "tag": norm(u.get("tag")) or None, "class": u["class"],
                          "sheet": u["provenance"][0]["sheet"], "sheets": u.get("sheets"), "box_0_1000": b,
                          "purpose": equipment_purpose(u, schedule), "risk_tier": u.get("risk", {}).get("tier"),
                          "provenance": {"source_check": (u.get("verification") or {}).get("status", "unverified"),
                                         "ops_review": "unverified", "risk_tier": u.get("risk", {}).get("tier"),
                                         "tag_status": u.get("tag_status")}})
    units = {e["id"] for e in equipment}
    classes = {x["id"]: x["class"] for k in ("units", "instruments", "line_items", "offpage_connectors")
               for x in model[k]}
    # unit-level paths: through valves and unclassified line items only, shortest first, on one sheet
    adj = defaultdict(list)
    for s in model["streams"]:
        if s["kind"] != "extracted_link" or recs[s["id"]]["instrument_link"]:
            continue
        adj[s["from"]].append((s["to"], s["id"]))
        adj[s["to"]].append((s["from"], s["id"]))
    ends = units | {c["id"] for c in conns}
    unit_links = {}
    for a in sorted(ends):
        prev = {a: None}
        q = deque([(a, 0)])
        while q:
            n, d = q.popleft()
            if d >= 6:
                continue
            for m, sid in adj[n]:
                if m in prev:
                    continue
                prev[m] = (n, sid)
                if m in ends:
                    continue  # stop at the next piece of equipment or connector
                q.append((m, d + 1))
        for b in prev:
            if b == a or b not in ends or (b, a) in unit_links or (classes[a] == classes[b] == "inlet/outlet"):
                continue
            path, n = [], b
            while prev[n]:
                n0, sid = prev[n]
                path.append((n0, n, sid))
                n = n0
            path.reverse()
            signs, confs = [], []
            for x, y, sid in path:
                r = recs[sid]
                if r["direction"] in ("forward", "reverse"):
                    signs.append(1 if r["flow_from"] == x else -1)
                    confs.append(r["confidence"])
            if len(set(signs)) > 1:
                direction, conf = "conflict", None
            elif signs:
                direction, conf = ("a_to_b" if signs[0] > 0 else "b_to_a"), min(confs)
            else:
                direction, conf = "undirected", None
            unit_links[(a, b)] = {"a": a, "b": b, "sheet": sheet_of[a], "via": [p[1] for p in path[:-1]],
                                  "streams": [p[2] for p in path], "direction": direction, "confidence": conf,
                                  "hops_directed": "%d/%d" % (len(signs), len(path))}
    # areas stitched by off-page connectors: paired connectors, and connectors naming a drawing in this set
    pair_of = {}
    for p in model["offpage_pairs"]:
        pair_of[p["a"]], pair_of[p["b"]] = p["b"], p["a"]
    area_links, external = [], []
    for c in conns:
        sh = sheet_of[c["id"]]
        dn = drawing_number(c["text"])
        f = flags.get((sh, c["provenance"][0]["symbol"]), {})
        role = f.get("role")
        target = sheet_of.get(pair_of[c["id"]]) if c["id"] in pair_of else sheet_of_dn.get(dn)
        rec = {"connector": c["id"], "sheet": sh, "text": norm(c["text"]), "refers_to_drawing": dn,
               "flag_tip": f.get("tip"), "role": role, "box_0_1000": c["provenance"][0]["box_0_1000"],
               "stitched_by": "paired connector" if c["id"] in pair_of else "drawing number in the text" if target
               else None}
        if target and target != sh:
            rec.update(target_sheet=target,
                       direction="out" if role == "sink" else "in" if role == "source" else "undirected")
            area_links.append(rec)
        else:
            rec.update(direction="out" if role == "sink" else "in" if role == "source" else "undirected",
                       utility=any(w in rec["text"].upper() for w in UTILITY_WORDS))
            external.append(rec)
    # sheet-to-sheet edges (one per connector; both ends of a pair count once)
    seen, edges = set(), []
    for r in area_links:
        key = frozenset((r["connector"], pair_of.get(r["connector"], r["connector"])))
        if key in seen:
            continue
        seen.add(key)
        a, b = r["sheet"], r["target_sheet"]
        d = "a_to_b" if r["direction"] == "out" else "b_to_a" if r["direction"] == "in" else "undirected"
        other = pair_of.get(r["connector"])
        if other:  # a pair: both flags must agree, as in flow_direction.py's cross-sheet rule
            o = next((x for x in area_links if x["connector"] == other), None)
            od = o and ("b_to_a" if o["direction"] == "out" else "a_to_b" if o["direction"] == "in" else "undirected")
            if od and od != "undirected" and d != "undirected" and od != d:
                d = "conflict"
            elif d == "undirected" and od:
                d = od
        edges.append({"a": a, "b": b, "direction": d, "connectors": sorted(key), "text": r["text"]})
    order, order_note = tour_order(sheets, edges, areas)
    loto = isolation_points(model, dirs, equipment, external, area_links, recs)
    for a in areas:
        sh = a["sheet"]
        a["equipment"] = [e["id"] for e in equipment if e["sheet"] == sh]
        a["instruments"] = sum(1 for i in model["instruments"] if i["provenance"][0]["sheet"] == sh)
        a["purpose"] = area_purpose(a, equipment)
    return {"meta": {"model_id": model["meta"]["model_id"], "script": "scripts/open100_structure.py",
                     "process_data": "none: structure only, no live or historical values",
                     "sources": {"title_block": "drawing register read by a person (development sheets 0-5)",
                                 "connector_text": "other sheets' off-page connector text naming this drawing",
                                 "drawing_label": "the equipment's own words on the drawing",
                                 "equipment_schedule": "the drawing's printed equipment schedule, transcribed "
                                                       "(data/open100_equipment_schedule.json; unverified)",
                                 "tag_code": "equipment-type code in the tag, common convention (unverified)",
                                 "generic": "class description only"}},
            "areas": areas, "equipment": equipment, "unit_links": list(unit_links.values()),
            "area_links": edges, "connectors_stitched": area_links, "external_connectors": external,
            "tour_order": order, "tour_order_basis": order_note, "isolation_points": loto,
            "instrument_markers": [{"id": i["id"], "tag": norm(i["tag"]), "unit": i["unit"],
                                    "sheet": i["provenance"][0]["sheet"]} for i in model["instruments"]
                                   if i.get("tag") and i.get("unit") in units and "XXX" not in i["tag"].upper()]}


def area_purpose(area, equipment):
    mine = [e for e in equipment if e["sheet"] == area["sheet"]]
    kinds = Counter(e["purpose"]["text"].split(" (from")[0].lower() for e in mine
                    if e["purpose"]["source"] in ("equipment_schedule", "tag_code", "drawing_label"))
    text = ", ".join("%d %s" % (n, k + ("s" if n > 1 and not k.endswith("s") else "")) for k, n in kinds.most_common(4))
    return {"text": ("%s. Equipment read from the drawing: %s." % (area["name"], text)) if area["name"] and text else
            ("Equipment read from the drawing: %s." % text) if text else
            "No named equipment was extracted on this sheet.",
            "source": area["name_source"] if area["name"] else "tag_code" if text else "generic"}


def tour_order(sheets, edges, areas):
    """Areas in flow order where the drawings say which way flow crosses between them; sheet order breaks ties and
    fills in where they don't."""
    out = defaultdict(list)
    indeg = Counter()
    for e in edges:
        if e["direction"] == "a_to_b":
            out[e["a"]].append(e["b"]); indeg[e["b"]] += 1
        elif e["direction"] == "b_to_a":
            out[e["b"]].append(e["a"]); indeg[e["a"]] += 1
    directed = sum(len(v) for v in out.values())
    if not directed:
        return sorted(sheets, key=int), "sheet order (no directed connection between sheets)"
    score = {s: len(out[s]) - indeg[s] for s in sheets}
    order, seen = [], set()

    def visit(s):
        if s in seen:
            return
        seen.add(s)
        order.append(s)
        for t in sorted(set(out[s]), key=lambda t: (-score[t], int(t))):
            visit(t)
    for s in sorted(sheets, key=lambda s: (indeg[s] > 0, -score[s], int(s))):
        visit(s)
    return order, ("follows %d directed sheet-to-sheet connections read from off-page flags; where none says, sheet "
                   "order. Plants loop (condensate to feedwater to steam and back), so any start point is a choice."
                   % directed)


def isolation_points(model, dirs, equipment, external, area_links, recs):
    """Candidate isolation points per sheet, from the extracted symbols only. A mockup for a LOTO review to start
    from, never a procedure."""
    pts = []
    inst_by_parent = defaultdict(list)
    for i in model["instruments"]:
        if i.get("parent"):
            inst_by_parent[i["parent"]].append(norm(i.get("tag")))
    degree = Counter()
    for s in model["streams"]:
        if s["kind"] == "extracted_link" and not recs[s["id"]]["instrument_link"]:
            degree[s["from"]] += 1
            degree[s["to"]] += 1
    for v in model["line_items"]:
        if v["class"] != "valve":
            continue
        p = v["provenance"][0]
        ops = inst_by_parent.get(v["id"], [])
        if any(MOTOR_VALVE.match(t or "") for t in ops):
            kind, note = "motor_operated_valve", ("Motor-operated valve: an isolation point for the line, and its "
                                                  "motor is an electrical energy source of its own.")
        elif any(CONTROL_VALVE.match(t or "") for t in ops):
            kind, note = "control_valve", ("Control valve: not an energy-isolating device by itself. Listed so it is "
                                           "not mistaken for one.")
        elif any(RELIEF.match(t or "") for t in ops):
            kind, note = "relief_device", ("Relief device: must never be used for isolation, and must not be isolated "
                                           "from the equipment it protects while that equipment can be pressured.")
        elif degree[v["id"]] <= 1:
            kind, note = "vent_drain_or_test", ("Valve with one process connection: likely a vent, drain or test "
                                                "connection, used to release or check for trapped pressure.")
        else:
            kind, note = "manual_block_valve", "Manual valve in a line: a candidate block (isolation) valve."
        pts.append({"sheet": p["sheet"], "id": v["id"], "tag": norm(v.get("tag")) or None, "kind": kind,
                    "operators": ops, "box_0_1000": p["box_0_1000"], "note": note})
    for e in equipment:
        if e["class"] == "pump":
            pts.append({"sheet": e["sheet"], "id": e["id"], "tag": e["tag"], "kind": "motor_driven_equipment",
                        "box_0_1000": e["box_0_1000"],
                        "note": "Motor-driven: electrical isolation at its breaker or disconnect (not on this drawing), "
                                "plus the suction and discharge block valves."})
    for c in external + area_links:   # every off-page line is a way for energy to come in from another system
        t = c["text"].upper()
        vd = any(w in t for w in VENT_DRAIN_WORDS)
        pts.append({"sheet": c["sheet"], "id": c["connector"], "tag": None,
                    "kind": "vent_drain_connection" if vd else "boundary_connection",
                    "box_0_1000": c["box_0_1000"], "text": c["text"], "flow": c.get("direction"),
                    "note": ("Line leaves to a vent or drain system (%s): isolate or verify it on that drawing."
                             if vd else "Line crosses to another system (%s): energy can come in from there; "
                             "isolate at the first block valve on this side or on that drawing.") % c["text"]})
    return pts


def main():
    model = json.loads(TWIN.read_text(encoding="utf-8"))
    dirs = json.loads(DIRS.read_text(encoding="utf-8"))
    doc = build(model, dirs)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "plant_structure.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    with (OUT / "loto_isolation_points.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sheet", "id", "tag", "kind", "x0", "y0", "x1", "y1", "note"])
        for p in sorted(doc["isolation_points"], key=lambda p: (int(p["sheet"]), p["kind"], p["id"])):
            w.writerow([p["sheet"], p["id"], p["tag"] or "", p["kind"], *[round(v, 1) for v in p["box_0_1000"]],
                        p["note"]])
    ul = Counter(u["direction"] for u in doc["unit_links"])
    al = Counter(e["direction"] for e in doc["area_links"])
    print("areas", len(doc["areas"]), "equipment", len(doc["equipment"]), "unit links", dict(ul),
          "area links", dict(al), "external", len(doc["external_connectors"]))
    print("tour", doc["tour_order"], "|", doc["tour_order_basis"])
    print("isolation points", dict(Counter(p["kind"] for p in doc["isolation_points"])))
    print("purpose sources", dict(Counter(e["purpose"]["source"] for e in doc["equipment"])))
    for a in doc["areas"]:
        print(a["sheet"], a["label"], "|", a["name_source"])


if __name__ == "__main__":
    main()
