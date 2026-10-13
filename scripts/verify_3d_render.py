"""Procedural verification of the 3D tour against the twin contract, the Ignition/PI exports, the P&ID trace, and
the rendered pixels. Stdlib only; reads committed or generated files, never a gateway or the network.

Four groups of checks:
  A. Accuracy vs exports: every scene tag/unit maps 1:1 to the Ignition gateway tag import
     (out/ignition/gateway/twin_provider.json, folder TE_Plant/<unit>/<tag>), the seed Ignition UDT export
     (out/ignition/te_tags.json), the PI AF staging sheet (out/pi/pi_builder_af.csv, \\TE Plant\\<unit>|<attribute>)
     and the Perspective project (PIDTwin.zip view bindings); names, units of measure, owning unit, stream
     membership, and the bands/alarm setpoints that colour the markers agree.
  B. Geometry and flow: pipe endpoints derived from 3D geometry reproduce the contract's stream topology; no marker
     sits inside equipment; the camera tour is a valid walk of the directed stream graph.
  C. P&ID trace: each scene tag traces to an extracted instrument with a drawing id and bbox, or is explicitly a
     seed/synthetic record. Coverage is reported either way.
  D. Legibility from the render: label boxes measured in Blender (out/3d/renders/label_boxes.json: projected boxes,
     raycast occlusion, WCAG contrast from the rendered pixels) checked for overlap, off-screen, occlusion,
     minimum text height at 1080p and contrast. Optional cross-check of contrast with Pillow, and OCR only if a
     tesseract executable is already installed (it is not installed by this script).

  python scripts/verify_3d_render.py                     # uses out/3d/te_scene.json and out/3d/renders/label_boxes.json
  python scripts/verify_3d_render.py --boxes drafts/3d-tour/label_boxes.json --report drafts/3d-tour/verification

Model use: none. Claude wrote this verifier; it has not been reviewed by a second model or an operator.
"""
import argparse
import csv
import io
import json
import math
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import label_layout as LL  # noqa: E402

PI_ROOT = "TE Plant"
IGN_ROOT = "TE_Plant"


# ------------------------------------------------------------------ loading exports

def ignition_provider_index(provider):
    """twin_provider.json -> {tag: {path, unit, uom, lo, hi, alarms, doc}} for the TE_Plant folder only."""
    te = next((t for t in provider.get("tags", []) if t.get("name") == IGN_ROOT), None)
    out, units = {}, []
    if te is None:
        return out, units
    for folder in te.get("tags", []):
        if folder.get("tagType") != "Folder" or folder["name"].startswith("_"):
            continue
        units.append(folder["name"])
        for inst in folder.get("tags", []):
            if inst.get("tagType") != "UdtInstance":
                continue
            params = inst.get("parameters", {})
            pv = next((t for t in inst.get("tags", []) if t.get("name") == "PV"), {})
            out[inst["name"]] = {
                "path": f"{IGN_ROOT}/{folder['name']}/{inst['name']}", "unit": folder["name"],
                "uom": pv.get("engUnit"), "doc": inst.get("documentation", ""),
                "lo": (params.get("NormalLo") or {}).get("value"), "hi": (params.get("NormalHi") or {}).get("value"),
                "alarms": [a.get("setpointA") for a in pv.get("alarms", [])],
                "param_tag": (params.get("Tag") or {}).get("value")}
    return out, units


def strip_provenance(text):
    """The seed exports end each description with the item's provenance (scripts/provenance.py, data lineage):
    ' | source check: <status> | ops review: <status>'. The contract comparison is on the description itself."""
    head, sep, _ = text.partition(" | source check: ")
    return head if sep else text


def ignition_seed_index(te_tags):
    """te_tags.json (generate.py seed export): UDT member per tag, instance per unit."""
    types = {t["name"]: t for t in next(f for f in te_tags["tags"] if f["name"] == "_types_")["tags"]}
    out, units = {}, []
    for inst in next(f for f in te_tags["tags"] if f["name"] == IGN_ROOT)["tags"]:
        units.append(inst["name"])
        for member in types[inst["typeId"]]["tags"]:
            tag = member.get("documentation", "").split(" | ")[0]
            out[tag] = {"path": f"{IGN_ROOT}/{inst['name']}/{member['name']}", "unit": inst["name"],
                        "uom": member.get("engUnit"), "doc": strip_provenance(member.get("documentation", ""))}
    return out, units


def pi_index(csv_text, descriptions_text=None):
    """PI Builder-style sheet -> {tag: {path, unit, uom, description, reference}}, plus unit elements.

    Sheet schema v2 leaves attribute descriptions out of the sheet (their column header is unconfirmed) and writes
    them to attribute_descriptions.csv; v2 also writes AF unit abbreviations (e.g. the degree-sign form of degC).
    Both are mapped back here so the comparison with the contract stays like for like."""
    rows = list(csv.DictReader(io.StringIO(csv_text.lstrip(chr(0xFEFF)))))
    extra = {r["attribute_path"]: r["description"] for r in
             csv.DictReader(io.StringIO((descriptions_text or "").lstrip(chr(0xFEFF))))} if descriptions_text else {}
    try:
        from pi_mapping import VENDOR_UOM
    except ImportError:  # sheet schema v1 checkouts
        VENDOR_UOM = {}
    model_uom = {v: k for k, v in VENDOR_UOM.items()}
    out, units = {}, []
    for r in rows:
        if r["ObjectType"] == "Element" and r["Parent"] == PI_ROOT:
            units.append(r["Name"])
        if r["ObjectType"] != "Attribute":
            continue
        description = strip_provenance(r.get("Description") or extra.get(f'{r["Parent"]}|{r["Name"]}', ""))
        tag = description.split(":", 1)[0].strip()
        ref = r.get("AttributeConfigString", "")
        out[tag] = {"path": "\\\\%s|%s" % (r["Parent"], r["Name"]), "unit": r["Parent"].split("\\")[-1],
                    "uom": model_uom.get(r["AttributeDefaultUOM"], r["AttributeDefaultUOM"]),
                    "description": description, "reference": ref,
                    "reference_tag": (re.search(r"TE\.([A-Z0-9-]+)\.PV", ref) or [None, None])[1]}
    return out, units


def perspective_index(zip_path):
    """Tag paths bound in the TE Perspective views: {tag: set(view names)}."""
    found = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if "/views/TE/" not in name or not name.endswith("view.json"):
                continue
            view = name.rsplit("/view.json", 1)[0].rsplit("/", 1)[-1]
            text = z.read(name).decode("utf-8", "replace")
            for unit, tag in re.findall(r"TE_Plant/([A-Z]-\d+)/([A-Z]{2}-\d+)(?![-\w])", text):
                found.setdefault(tag, {}).setdefault(view, set()).add(unit)
    return found


# ------------------------------------------------------------------ check plumbing

class Report:
    def __init__(self):
        self.checks = []

    def add(self, group, cid, ok, summary, details=None, status=None):
        self.checks.append({"group": group, "id": cid, "status": status or ("pass" if ok else "fail"),
                            "summary": summary, "details": details or []})

    @property
    def failed(self):
        return [c for c in self.checks if c["status"] == "fail"]


# ------------------------------------------------------------------ A. accuracy vs exports

def check_exports(rep, scene, model, provider=None, seed_tags=None, pi_csv=None, perspective=None, bands=None,
                  alarms=None, pi_descriptions=None):
    items = {i["tag"]: i for i in model["instruments"] + model["final_elements"]}
    markers = {m["tag"]: m for m in scene["markers"]}
    units = [u["id"] for u in model["units"]]
    rep.add("A", "A0 scene tags = contract tags", set(markers) == set(items) and len(markers) == len(scene["markers"]),
            f"{len(markers)} scene markers, {len(items)} contract records",
            sorted(set(markers) ^ set(items)))
    rep.add("A", "A0 scene units = contract units", sorted(e["id"] for e in scene["equipment"]) == sorted(units),
            f"{len(scene['equipment'])} scene units", [])
    table = {t: {"tag": t, "scene_unit": m["unit"], "scene_uom": m["uom"], "attach": "/".join(m["attach"])}
             for t, m in markers.items()}

    def compare(label, index, idx_units, fields, desc_ok=None):
        missing = sorted(t for t in markers if t not in index)
        extra = sorted(t for t in index if t not in markers)
        explained = [t for t in extra if re.match(r"^(AI-\d+)-[A-Z]$", t) and t.rsplit("-", 1)[0] in markers]
        unexplained = [t for t in extra if t not in explained]
        bad = []
        for t, m in markers.items():
            x = index.get(t)
            if not x:
                continue
            table[t][label] = x["path"]
            if x["unit"] != m["unit"] or m["unit"] != items[t]["unit"]:
                bad.append(f"{t}: owning unit scene={m['unit']} {label}={x['unit']} contract={items[t]['unit']}")
            if "uom" in fields and (x.get("uom") or "") != (m["uom"] or ""):
                bad.append(f"{t}: unit of measure scene={m['uom']!r} {label}={x.get('uom')!r}")
            if desc_ok and not desc_ok(t, x):
                bad.append(f"{t}: name/description disagrees with the contract ({label})")
        unit_diff = sorted(set(idx_units) ^ set(units))
        ok = not missing and not unexplained and not bad and not unit_diff
        rep.add("A", f"A {label}: 1:1 tags, units, owning unit" + (", UOM" if "uom" in fields else ""), ok,
                f"{len(markers) - len(missing)}/{len(markers)} scene tags found; {len(explained)} extra explained "
                f"(analyzer component channels; the 3D marker shows the first component only); "
                f"{len(unexplained)} unexplained extra; {len(bad)} mismatches; unit folders differ: {unit_diff or 'none'}",
                [f"missing: {t}" for t in missing] + [f"extra: {t}" for t in unexplained] + bad)

    if provider is not None:
        prov, prov_units = ignition_provider_index(provider)
        compare("ignition_gateway", prov, prov_units, ("uom",),
                lambda t, x: x["param_tag"] == t and (x["doc"].startswith(items[t]["description"] + " |") or (
                    # Analyzers: the gateway documents one tag per component ("<stem> | component A | ...").
                    t.startswith("AI-") and x["doc"].startswith(re.sub(r"\s*\(.*?\)", "", items[t]["description"]) + " | component "))))
        if bands is not None:
            diffs = []
            for t in markers:
                b, x = bands.get(t), prov.get(t)
                if b and x and (abs(b["lo"] - x["lo"]) > 1e-3 * max(1, abs(b["lo"])) or abs(b["hi"] - x["hi"]) > 1e-3 * max(1, abs(b["hi"]))):
                    diffs.append(f"{t}: scene band {b['lo']}-{b['hi']} vs gateway {x['lo']}-{x['hi']}")
                if (b is None) != (x is None or x["lo"] is None):
                    diffs.append(f"{t}: band present in one source only")
            al = []
            for t, sp in (alarms or {}).items():
                if sorted(a["setpointA"] for a in sp) != sorted(prov.get(t, {}).get("alarms", [])):
                    al.append(f"{t}: scene setpoints {[a['setpointA'] for a in sp]} vs gateway {prov.get(t, {}).get('alarms')}")
            extra_alarm = sorted(t for t, x in prov.items() if x["alarms"] and t not in (alarms or {}) and t in markers)
            rep.add("A", "A bands and alarm setpoints colouring the 3D markers = gateway tag parameters",
                    not diffs and not al and not extra_alarm,
                    f"{sum(1 for t in markers if bands.get(t))} banded tags compared, {len(alarms or {})} alarmed tags",
                    diffs + al + [f"{t}: alarm in gateway only" for t in extra_alarm])
    if seed_tags is not None:
        seed, seed_units = ignition_seed_index(seed_tags)
        compare("ignition_seed_udt", seed, seed_units, ("uom",),
                lambda t, x: x["doc"].endswith(" | " + items[t]["description"]))
    if pi_csv is not None:
        pi, pi_units = pi_index(pi_csv, pi_descriptions)
        compare("pi_af", pi, pi_units, ("uom",),
                lambda t, x: x["description"] == f"{t}: {items[t]['description']}" and x["reference_tag"] == t)
    if perspective is not None:
        missing, wrong = [], []
        for t, m in markers.items():
            views = perspective.get(t, {})
            if not views:
                missing.append(t)
                continue
            table[t]["perspective_views"] = sorted(views)
            units_seen = {u for us in views.values() for u in us}
            if units_seen != {m["unit"]}:
                wrong.append(f"{t}: bound under {sorted(units_seen)}, scene unit {m['unit']}")
            if f"Unit_{m['unit']}" not in views:
                wrong.append(f"{t}: not on its own unit view Unit_{m['unit']}")
        rep.add("A", "A perspective: every scene tag bound in the TE views under its owning unit", not missing and not wrong,
                f"{len(markers) - len(missing)}/{len(markers)} tags bound", [f"unbound: {t}" for t in missing] + wrong)
    # Stream membership: the scene's attachment vs the contract (Ignition/PI carry no stream field).
    diffs = []
    for t, m in markers.items():
        cs = items[t].get("stream")
        if m["attach"][0] == "stream" and cs and m["attach"][1] != cs:
            diffs.append(f"{t}: scene on stream {m['attach'][1]}, contract stream {cs}")
        if m["attach"][0] == "stream" and not cs and "display layout card" not in m["placement_basis"]:
            diffs.append(f"{t}: placed on stream {m['attach'][1]} without contract or card basis")
    n_stream = sum(1 for m in markers.values() if m["attach"][0] == "stream")
    rep.add("A", "A stream membership: scene stream placement agrees with the contract", not diffs,
            f"{n_stream} tags placed on streams; the Ignition and PI exports carry no stream field, so membership "
            "is checked against the contract only", diffs)
    return table


# ------------------------------------------------------------------ B. geometry and flow

def _seg_dist(p, a, b):
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    n = sum(c * c for c in ab)
    t = 0.0 if n == 0 else max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / n))
    return math.dist(p, [a[i] + t * ab[i] for i in range(3)])


def _owner_of(point, scene):
    """Which unit or battery-limit post a pipe end touches, from geometry alone."""
    best = None
    for e in scene["equipment"]:
        x, y, _ = e["position"]
        hx, hy, top = e["extent"]
        if point[2] > top + 1.0 or point[2] < -0.1:
            continue
        if e["shape"] in ("vertical_vessel", "column"):
            gap = math.hypot(point[0] - x, point[1] - y) - hx
        elif e["shape"] == "header":
            gap = max(abs(point[0] - x) - hx, abs(point[1] - y) - hy, 0.0) + max(0.0, point[2] - top)
        else:
            gap = max(abs(point[0] - x) - hx, abs(point[1] - y) - hy)
        if gap <= 0.6 and (best is None or gap < best[0]):
            best = (gap, e["id"])
    for b in scene["boundaries"]:
        d = math.hypot(point[0] - b["position"][0], point[1] - b["position"][1])
        if d <= 0.3 and (best is None or d < best[0]):
            best = (d, "BL:" + b["stream"])
    return best[1] if best else None


def inside_any(point, scene, margin=0.05):
    hits = []
    for e in scene["equipment"]:
        x, y, _ = e["position"]
        hx, hy, top = e["extent"]
        if not -margin <= point[2] <= top + margin:
            continue
        inside = (math.hypot(point[0] - x, point[1] - y) < hx + margin if e["shape"] in ("vertical_vessel", "column")
                  else abs(point[0] - x) < hx + margin and abs(point[1] - y) < hy + margin)
        if inside:
            hits.append(e["id"])
    return hits


def check_geometry(rep, scene, model):
    streams = {s["id"]: s for s in model["streams"]}
    derived, bad = {}, []
    for p in scene["pipes"]:
        a, b = _owner_of(p["points"][0], scene), _owner_of(p["points"][-1], scene)
        norm = lambda o: "BL" if o and o.startswith("BL:") else o  # noqa: E731
        derived[p["id"]] = (norm(a), norm(b))
        s = streams.get(p["id"])
        if s is None or (norm(a), norm(b)) != (s["from"], s["to"]):
            bad.append(f"{p['id']}: geometry joins {a} -> {b}, contract {s and s['from']} -> {s and s['to']}")
        for o in (a, b):
            if o and o.startswith("BL:") and o[3:] != p["id"]:
                bad.append(f"{p['id']}: ends at the battery-limit post of {o[3:]}")
        corners = p.get("corners") or p["points"]
        for i in range(len(corners) - 1):
            moved = sum(1 for k in range(3) if abs(corners[i][k] - corners[i + 1][k]) > 1e-6)
            if moved != 1:
                bad.append(f"{p['id']}: segment {i} is not axis-aligned (schematic route rule)")
        if math.dist(corners[0], p["points"][0]) > 1e-6 or math.dist(corners[-1], p["points"][-1]) > 1e-6:
            bad.append(f"{p['id']}: rounded bends moved a pipe end")
    missing = sorted(set(streams) - set(derived))
    rep.add("B", "B pipe endpoints in 3D reproduce the contract stream topology", not bad and not missing,
            f"{len(derived) - sum(1 for x in bad if 'geometry joins' in x)}/{len(streams)} streams derived from "
            "geometry match from/to", bad + [f"no pipe for stream {s}" for s in missing])
    inside = []
    far = []
    pipes = {p["id"]: p for p in scene["pipes"]}
    eq = {e["id"]: e for e in scene["equipment"]}
    for m in scene["markers"]:
        hits = inside_any(m["position"], scene)
        if hits:
            inside.append(f"{m['tag']} is inside {', '.join(hits)} at {m['position']}")
        if m["attach"][0] == "stream":
            pts = pipes[m["attach"][1]]["points"]
            d = min(_seg_dist(m["position"], pts[i], pts[i + 1]) for i in range(len(pts) - 1))
            if d > 1.5:
                far.append(f"{m['tag']}: {d:.2f} m from its stream {m['attach'][1]}")
        else:
            e = eq[m["attach"][1]]
            d = math.hypot(m["position"][0] - e["position"][0], m["position"][1] - e["position"][1]) - max(e["extent"][:2])
            if d > 2.0:
                far.append(f"{m['tag']}: {d:.2f} m outside the footprint of {e['id']}")
    rep.add("B", "B no tag marker inside equipment; markers near what they measure", not inside and not far,
            f"{len(inside)} markers inside equipment, {len(far)} far from their stream/unit", inside + far)
    # Inferred utilities and valve symbols must say so and point at a real final element of that unit.
    fes = {f["tag"]: f for f in model["final_elements"]}
    probs = []
    for u in scene.get("utilities", []):
        fe = fes.get(u["tag"])
        if not fe or fe.get("unit") != u["unit"] or not u.get("basis", "").startswith("inferred"):
            probs.append(f"{u['id']}: utility stub without an inferred basis on a final element of {u['unit']}")
        if any(s["id"] == u["id"] for s in model["streams"]):
            probs.append(f"{u['id']}: utility stub collides with a contract stream id")
    for v in scene.get("valves", []):
        fe = fes.get(v["tag"])
        if not fe or fe.get("unit") != v["unit"]:
            probs.append(f"{v['tag']}: valve symbol not backed by a contract final element on {v['unit']}")
        if v["on"].startswith("stream:") and fe and fe.get("stream") and v["on"][7:] != fe["stream"]:
            probs.append(f"{v['tag']}: valve symbol on {v['on']}, contract stream {fe['stream']}")
    rep.add("B", "B utility stubs are labelled inferred and valve symbols map to contract final elements", not probs,
            f"{len(scene.get('utilities', []))} inferred utility stubs, {len(scene.get('valves', []))} valve symbols",
            probs)
    # Tour walk.
    order = [t["unit"] for t in scene["tour"]]
    units = [u["id"] for u in model["units"]]
    if not scene["tour_order_basis"].startswith("seed") and "direction" not in scene["tour_order_basis"]:
        rep.add("B", "B tour order is a valid walk of the directed stream graph", sorted(order) == sorted(units),
                "no authorized directions: tour is in model order and labelled so (walk check not applicable)", [],
                status="info" if sorted(order) == sorted(units) else "fail")
        return derived
    directed = {p["id"]: p["directed"] for p in scene["pipes"]}
    why, problems = [], []
    if sorted(order) != sorted(units) or len(order) != len(set(order)):
        problems.append(f"tour visits {order}, contract units {units}")
    seen = set()
    for k, u in enumerate(order):
        feeds = [s for s in model["streams"] if s["to"] == u and directed.get(s["id"]) and
                 (s["from"] == "BL" or s["from"] in seen)]
        if k == 0 and not any(s["from"] == "BL" for s in feeds):
            problems.append(f"stop 1 {u} is not fed from the battery limit")
        elif not feeds:
            problems.append(f"stop {k + 1} {u} has no directed inflow from an earlier stop or the battery limit")
        else:
            why.append(f"stop {k + 1} {u}: entered via {feeds[0]['id']} ({feeds[0]['from']} -> {u})")
        seen.add(u)
    rep.add("B", "B tour order is a valid walk of the directed stream graph", not problems,
            "each stop is reached by a directed stream from the battery limit or an earlier stop (directions from the "
            "model, checked against the simulator source)", problems or why)
    return derived


# ------------------------------------------------------------------ C. P&ID trace

def drawing_trace(item):
    for p in item.get("provenance") or []:
        box = p.get("box_0_1000") or p.get("bbox")
        if p.get("sheet") not in (None, "") and isinstance(box, list) and len(box) == 4 and \
                all(isinstance(v, (int, float)) and math.isfinite(v) for v in box):
            return {"drawing": str(p["sheet"]), "bbox": box, "source_run": p.get("source_run")}
    return None


def check_pid_trace(rep, scene, model):
    items = {i["tag"]: i for i in model["instruments"] + model["final_elements"]}
    method = model["meta"].get("extraction_method", "")
    seed_model = "seed" in method.lower() or "synthetic" in method.lower()
    rows, traced, seed, unexplained = [], [], [], []
    for m in scene["markers"]:
        it = items.get(m["tag"], {})
        tr = drawing_trace(it)
        if tr:
            traced.append(m["tag"])
            rows.append({"tag": m["tag"], "trace": "drawing", **tr})
        elif seed_model or it.get("seed") or it.get("synthetic"):
            seed.append(m["tag"])
            rows.append({"tag": m["tag"], "trace": "seed (no drawing)",
                         "source": model["meta"].get("source_document", ""),
                         "checked_against": (it.get("verification") or {}).get("checked_against"),
                         "check_status": (it.get("verification") or {}).get("status")})
        else:
            unexplained.append(m["tag"])
            rows.append({"tag": m["tag"], "trace": "UNEXPLAINED: no drawing id/bbox and not declared seed"})
    n = len(scene["markers"])
    checked = sum(1 for r in rows if r.get("checked_against"))
    rep.add("C", "C every scene tag traces to a drawing (id + bbox) or is declared seed/synthetic", not unexplained,
            f"drawing-traced {len(traced)}/{n}; declared seed {len(seed)}/{n} ({checked} of them checked against "
            f"{', '.join(sorted({r['checked_against'] for r in rows if r.get('checked_against')})) or 'nothing'}); "
            f"unexplained {len(unexplained)}/{n}", [f"unexplained: {t}" for t in unexplained])
    if seed and not traced:
        rep.add("C", "C drawing coverage", True, f"0 of {n} tags trace to a P&ID drawing: this model is "
                f"'{method[:60]}...', built from a paper, not extracted from a drawing", [], status="info")
    return rows


# ------------------------------------------------------------------ D. legibility

def check_legibility(rep, boxes, scene=None, pixel_check=None, ocr=None):
    W, H = boxes["resolution"]
    scale = 1080.0 / H
    shots = {s["name"]: s for s in (scene or {}).get("shots", [])}
    totals = {"stills": 0, "labels": 0, "overlaps": 0, "offscreen": 0, "occluded": 0, "small": 0, "low_contrast": 0,
              "not_in_view": 0, "no_contrast": 0, "crowded": 0, "covers_marker": 0, "caps": 0, "on_silhouette": 0}
    out_of_frame = 0   # drawn in the 3D scene but entirely outside this still's frame: not part of this still
    per_still, worst = [], {"min_height_px_1080": None, "min_contrast": None}
    for st in boxes["stills"]:
        totals["stills"] += 1
        issues = []
        shown = []
        for e in st["labels"]:
            if not e.get("shown"):
                continue
            b = e.get("plate_box") or e["text_box"]
            if not e.get("in_front", True) or LL.outside_area(b, W, H) >= LL.box_area(b) - 1e-6:
                out_of_frame += 1
                continue
            shown.append(e)
        for e in st["labels"]:
            if not e.get("shown"):
                totals["not_in_view"] += 1
                issues.append(f"{e['id']}: expected in this still but not shown ({e.get('reason')})")
        expected = set(shots.get(st["name"], {}).get("visible", []) if shots else st.get("visible", []))
        measured = {e["id"] for e in st["labels"]}
        for lid in sorted(expected - measured):
            totals["not_in_view"] += 1
            issues.append(f"{lid}: in the shot list but not measured")
        for e in shown:
            totals["labels"] += e["kind"] != "caption"
            box = e.get("plate_box") if e["kind"] != "caption" and e.get("plate_box") else e["text_box"]
            if e["kind"] == "overlay_caption":
                box = e["text_box"]   # the caption bar plate spans the full width by design
            if LL.outside_area(box, W, H) > 1.0 or not e.get("in_front", True):
                totals["offscreen"] += 1
                issues.append(f"{e['id']}: off-screen or behind the camera ({[round(v) for v in box]})")
            h = (e["text_box"][3] - e["text_box"][1]) / max(1, e["lines"]) * scale
            worst["min_height_px_1080"] = h if worst["min_height_px_1080"] is None else min(worst["min_height_px_1080"], h)
            if h < LL.MIN_LINE_PX_1080:
                totals["small"] += 1
                issues.append(f"{e['id']}: text height {h:.1f}px at 1080p < {LL.MIN_LINE_PX_1080:.0f}")
            c = e.get("contrast")
            if c is None:
                totals["no_contrast"] += 1
                issues.append(f"{e['id']}: no contrast measurement")
            else:
                worst["min_contrast"] = c["ratio"] if worst["min_contrast"] is None else min(worst["min_contrast"], c["ratio"])
                if c["ratio"] < LL.MIN_CONTRAST:
                    totals["low_contrast"] += 1
                    issues.append(f"{e['id']}: contrast {c['ratio']:.2f}:1 < {LL.MIN_CONTRAST}:1")
            for key in ("marker_occluded_by", "label_occluded_by"):
                if e.get(key):
                    totals["occluded"] += 1
                    what = "marker" if key.startswith("marker") else "label (%d%% of samples)" % round(
                        100 * e.get("label_occluded_fraction", 1.0))
                    issues.append(f"{e['id']}: {what} hidden by {e[key]}")
        for i, a in enumerate(shown):
            for b in shown[i + 1:]:
                ba = a.get("plate_box") or a["text_box"]
                bb = b.get("plate_box") or b["text_box"]
                ov = LL.overlap_area(ba, bb, LL.OVERLAP_TOLERANCE_PX)
                if ov > 0:
                    totals["overlaps"] += 1
                    issues.append(f"overlap: {a['id']} x {b['id']} ({ov:.0f} px^2)")
                elif not a.get("plate_box") and not b.get("plate_box") and "caption" not in (a["id"], b["id"])                         and not a["kind"].startswith("overlay") and not b["kind"].startswith("overlay"):
                    # Crowding: two plate-less labels on overlapping baselines, closer than one line height, read
                    # as one string (429d7a7 overview: "E-101 Product Condenser K-101 Recycle Compressor").
                    ta, tb = a["text_box"], b["text_box"]
                    vy = min(ta[3], tb[3]) - max(ta[1], tb[1])
                    hmin = min(ta[3] - ta[1], tb[3] - tb[1])
                    gap = max(ta[0], tb[0]) - min(ta[2], tb[2])
                    line = max((ta[3] - ta[1]) / a["lines"], (tb[3] - tb[1]) / b["lines"])
                    if hmin > 0 and vy >= 0.5 * hmin and 0 <= gap < line:
                        totals["crowded"] += 1
                        issues.append(f"crowded: {a['id']} and {b['id']} are {gap:.0f}px apart on one baseline "
                                      f"(< one line height, {line:.0f}px), so they read as one string")
        # No ALL-CAPS runs inside the picture (three or more consecutive all-caps words of letters).
        for e in shown:
            for line in e.get("text", "").split(chr(10)):
                words = [w for w in re.findall(r"[A-Za-z][A-Za-z'/-]*", line)]
                run = best = 0
                for w in words:
                    run = run + 1 if (w.isupper() and len(w) > 1 and not re.match(r"^[A-Z]{1,3}$", w)) else 0
                    best = max(best, run)
                if best >= 3:
                    totals["caps"] += 1
                    issues.append(f"{e['id']}: all-caps run in {line!r}")
        # At a focus stop, tag and unit pills sit outside the unit's silhouette (projected part rectangles).
        for e in shown:
            if e["kind"] not in ("tag", "unit", "boundary") or not st.get("focus_rects"):
                continue
            box = e.get("plate_box") or e["text_box"]
            hit = max((LL.overlap_area(box, r, 3.0) for r in st["focus_rects"]), default=0.0)
            if hit > 0:
                totals["on_silhouette"] += 1
                issues.append(f"{e['id']}: pill overlaps the {st.get('focus')} silhouette ({hit:.0f} px^2)")
        # No label may cover a drawn marker; the caption band may not cover this still's own markers.
        own = {e.get("marker") for e in shown}
        for e in shown:
            box = e.get("plate_box") or e["text_box"]
            for tag, (mx, my) in (st.get("markers_px") or {}).items():
                if tag == e.get("marker") or (e["kind"].startswith(("caption", "overlay")) and tag not in own):
                    continue
                if box[0] + 2 < mx < box[2] - 2 and box[1] + 2 < my < box[3] - 2:
                    totals["covers_marker"] += 1
                    issues.append(f"{e['id']} covers the {tag} marker")
        per_still.append({"still": st["name"], "labels": len(shown), "issues": issues})
    problems = sum(v for k, v in totals.items() if k not in ("stills", "labels"))
    rep.add("D", "D legibility: no overlap, crowding, covered markers, pills on the silhouette, all-caps, off-screen, "
                 "occlusion, small text or low contrast",
            problems == 0,
            f"{totals['stills']} stills, {totals['labels']} labels + captions; overlaps {totals['overlaps']}, "
            f"crowded {totals['crowded']}, labels covering markers {totals['covers_marker']}, "
            f"pills on the focus silhouette {totals['on_silhouette']}, all-caps runs {totals['caps']}, "
            f"off-screen {totals['offscreen']}, occluded {totals['occluded']}, text < {LL.MIN_LINE_PX_1080:.0f}px "
            f"{totals['small']}, contrast < {LL.MIN_CONTRAST}:1 {totals['low_contrast']}, expected-but-missing "
            f"{totals['not_in_view']}; min text height {worst['min_height_px_1080'] and round(worst['min_height_px_1080'], 1)}px, "
            f"min contrast {worst['min_contrast'] and round(worst['min_contrast'], 2)}:1; {out_of_frame} drawn labels "
            f"entirely outside their still's frame were not counted (layout '{boxes.get('label_layout')}')",
            [f"{s['still']}: {i}" for s in per_still for i in s["issues"]])
    if pixel_check is not None:
        rep.add("D", "D contrast cross-check with an independent pixel reader (Pillow)", pixel_check["ok"],
                pixel_check["summary"], pixel_check.get("details", []), status=pixel_check.get("status"))
    rep.add("D", "D OCR readability", True if ocr is None else ocr["ok"],
            "skipped: no tesseract executable on PATH (not installed by this verifier)" if ocr is None else ocr["summary"],
            [] if ocr is None else ocr.get("details", []), status="info" if ocr is None else None)
    return {"totals": totals, "per_still": per_still, "worst": worst}


def pillow_crosscheck(boxes, image_dir):
    """Recompute each text box's contrast from the PNG with Pillow (same heuristic, independent pixel reader)."""
    try:
        from PIL import Image
    except Exception:
        return {"ok": True, "status": "info", "summary": "skipped: Pillow not importable in this interpreter"}
    diffs, n = [], 0
    for st in boxes["stills"]:
        path = Path(image_dir) / st["image"]
        if not path.is_file():
            return {"ok": True, "status": "info", "summary": f"skipped: {path.name} not found next to the boxes file"}
        img = Image.open(path).convert("RGB")
        for e in st["labels"]:
            if not e.get("shown") or not e.get("contrast"):
                continue
            x0, y0 = (int(math.floor(v)) for v in e["text_box"][:2])
            x1, y1 = (int(math.ceil(v)) for v in e["text_box"][2:])
            crop = img.crop((max(0, x0), max(0, y0), min(img.width, x1), min(img.height, y1)))
            if crop.width < 2 or crop.height < 2:
                continue
            lum = [LL.relative_luminance((r / 255, g / 255, b / 255)) for r, g, b in (crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata())]
            ratio = LL.text_contrast(lum)["ratio"]
            n += 1
            diffs.append((abs(ratio - e["contrast"]["ratio"]), st["name"], e["id"], ratio, e["contrast"]["ratio"]))
    worst = max(diffs) if diffs else (0, "", "", 0, 0)
    ok = worst[0] <= 0.25 + 0.05 * worst[4] if diffs else True
    return {"ok": ok, "summary": f"{n} boxes re-measured from the PNGs; largest difference {worst[0]:.2f} "
            f"({worst[1]} {worst[2]}: Pillow {worst[3]:.2f} vs Blender {worst[4]:.2f})", "details": []}


def tesseract_ocr(boxes, image_dir):
    exe = shutil.which("tesseract")
    if not exe:
        return None
    misses, n = [], 0
    for st in boxes["stills"]:
        res = subprocess.run([exe, str(Path(image_dir) / st["image"]), "stdout", "--psm", "11"], capture_output=True,
                             text=True)
        for e in st["labels"]:
            if not e.get("shown") or e["kind"] == "caption":
                continue
            n += 1
            if e["text"].split()[0] not in res.stdout:   # the tag (first word) must be read back somewhere
                misses.append(f"{st['name']} {e['id']}")
    return {"ok": not misses, "summary": f"{n - len(misses)}/{n} label tags read back by OCR", "details": misses}


# ------------------------------------------------------------------ report

def to_markdown(rep, table, trace_rows, legibility):
    out = ["# 3D tour verification", "", "| Group | Check | Status | Result |", "|---|---|---|---|"]
    for c in rep.checks:
        out.append(f"| {c['group']} | {c['id']} | {c['status'].upper()} | {c['summary']} |")
    for c in rep.checks:
        if c["details"]:
            out += ["", f"## {c['id']} ({c['status']})", ""] + [f"- {d}" for d in c["details"][:60]]
            if len(c["details"]) > 60:
                out.append(f"- ... {len(c['details']) - 60} more")
    if table:
        out += ["", "## Tag map: scene -> Ignition -> PI AF", "", "| Tag | Unit | UOM | On | Ignition path | PI AF path |",
                "|---|---|---|---|---|---|"]
        for t in sorted(table):
            r = table[t]
            out.append(f"| {t} | {r['scene_unit']} | {r['scene_uom']} | {r['attach']} | {r.get('ignition_gateway', '-')} | "
                       f"{r.get('pi_af', '-')} |")
    return "\n".join(out) + "\n"


def run(scene, model, provider=None, seed_tags=None, pi_csv=None, perspective=None, bands=None, alarms=None,
        boxes=None, image_dir=None, crosscheck=True, pi_descriptions=None):
    rep = Report()
    table = check_exports(rep, scene, model, provider, seed_tags, pi_csv, perspective, bands, alarms,
                          pi_descriptions=pi_descriptions)
    check_geometry(rep, scene, model)
    trace_rows = check_pid_trace(rep, scene, model)
    leg = None
    if boxes is not None:
        px = pillow_crosscheck(boxes, image_dir) if (crosscheck and image_dir) else None
        ocr = tesseract_ocr(boxes, image_dir) if image_dir else None
        leg = check_legibility(rep, boxes, scene, px, ocr)
    else:
        rep.add("D", "D legibility", True, "not run: no label_boxes.json (render with Blender first)", [], status="info")
    return {"checks": rep.checks, "failed": len(rep.failed), "tag_map": table, "pid_trace": trace_rows,
            "legibility": leg}, rep, table, trace_rows, leg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scene", default=str(ROOT / "out/3d/te_scene.json"))
    ap.add_argument("--model", default=str(ROOT / "data/te_process_model.json"))
    ap.add_argument("--provider", default=str(ROOT / "out/ignition/gateway/twin_provider.json"))
    ap.add_argument("--seed-tags", default=str(ROOT / "out/ignition/te_tags.json"))
    ap.add_argument("--pi", default=str(ROOT / "out/pi/pi_builder_af.csv"))
    ap.add_argument("--perspective", default=str(ROOT / "out/ignition/gateway/PIDTwin.zip"))
    ap.add_argument("--bands", default=str(ROOT / "out/ignition/normal_bands.json"))
    ap.add_argument("--meta", default=str(ROOT / "out/ignition/gateway/build_meta.json"))
    ap.add_argument("--boxes", default=str(ROOT / "out/3d/renders/label_boxes.json"))
    ap.add_argument("--images", help="folder with the rendered PNGs (default: next to --boxes)")
    ap.add_argument("--report", default=str(ROOT / "out/3d/verification"), help="writes <report>.json and <report>.md")
    args = ap.parse_args(argv)
    read = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    exists = lambda p: Path(p).is_file()  # noqa: E731
    scene, model = read(args.scene), read(args.model)
    boxes = read(args.boxes) if exists(args.boxes) else None
    result, rep, table, trace, leg = run(
        scene, model,
        provider=read(args.provider) if exists(args.provider) else None,
        seed_tags=read(args.seed_tags) if exists(args.seed_tags) else None,
        pi_csv=Path(args.pi).read_text(encoding="utf-8-sig") if exists(args.pi) else None,
        pi_descriptions=(Path(args.pi).with_name("attribute_descriptions.csv").read_text(encoding="utf-8-sig")
                         if exists(Path(args.pi).with_name("attribute_descriptions.csv")) else None),
        perspective=perspective_index(args.perspective) if exists(args.perspective) else None,
        bands=read(args.bands)["bands"] if exists(args.bands) else None,
        alarms=read(args.meta).get("alarms") if exists(args.meta) else None,
        boxes=boxes, image_dir=args.images or (str(Path(args.boxes).parent) if boxes else None))
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report + ".json").write_text(json.dumps(result, indent=1, sort_keys=True, default=sorted) + "\n", encoding="utf-8")
    Path(args.report + ".md").write_text(to_markdown(rep, table, trace, leg), encoding="utf-8")
    for c in rep.checks:
        print(f"{c['status'].upper():4}  {c['id']}: {c['summary']}")
    print(f"{len(rep.checks) - len(rep.failed)}/{len(rep.checks)} checks not failed; report {args.report}.md")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
