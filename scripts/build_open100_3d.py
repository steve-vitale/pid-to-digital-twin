"""3D orientation tour for the OPEN100 plant: structure only, no process data.

Builds a scene for the Blender renderer copied from the 3D tour prototype (scripts/blender_tour_template.py, with
scripts/label_layout.py embedded, both unchanged) from the OPEN100 plant structure (scripts/open100_structure.py):

  - the 12 sheets become 12 areas on a plot, in the inferred tour order (off-page flags say which way flow crosses);
  - each area's equipment sits where it sits on its drawing, scaled to metres, as a placeholder shape for its class;
  - pipes join equipment along the extracted paths (one per nearest connection, as on the 2D area mimic), and between
    areas along their off-page connections; chevrons ONLY where a direction was read from the drawing;
  - every instrument marker is "not connected": there is no process data on this track, and the stills say so.
Each stop gets a purpose card built from the drawing's own words where it has them (the printed equipment schedule,
the equipment's own label, the title block or other sheets' connector text), else the tag's type code, else a generic
class description marked "generic".

PROTOTYPE, NOT PLANT GEOMETRY. A P&ID gives topology and tags, not layout: positions are drawing positions, every
size, elevation and pipe route is a placeholder. Deterministic: the same inputs give the same scene.

  python scripts/build_open100_3d.py                                  # scene JSON + Blender script
  python scripts/build_open100_3d.py --blender PATH/blender.exe       # also render the stills
Output: out/open100_structural/3d/ (scene, script, renders) and, with --blender, docs/screenshots/open100/3d-*.jpg

Model use: none at run time. Claude (the coding agent) wrote this script and chose the placeholder shapes.
"""
import argparse
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ignition"))
import label_layout  # noqa: E402
from build_open100_mimic import directed_pair, display_links, icon_kind  # noqa: E402
from display_contract import stream_is_directed  # noqa: E402

TEMPLATE = ROOT / "scripts" / "blender_tour_template.py"
OUT = ROOT / "out" / "open100_structural" / "3d"
SHOTS = ROOT / "docs" / "screenshots" / "open100"
LENS_MM, SENSOR_MM = 28.0, 36.0
PAD_W, PAD_D, GAP = 34.0, 22.0, 10.0          # area footprint on the plot, metres (placeholder)
RACK_Z, AREA_RACK_Z = 4.2, 6.0
BADGE = "STRUCTURE ONLY · NO PROCESS DATA\nOPEN100 drawings, extracted, unverified"
SHAPES = {   # placeholder per icon kind: (template shape, dims (d, h, length), nozzle_z)
    "vessel": ("vertical_vessel", (2.2, 3.6, 0), 1.6),
    "tall_vessel": ("vertical_vessel", (2.8, 6.0, 0), 2.5),
    "exchanger": ("horizontal_exchanger", (0.9, 0.9, 3.6), 1.4),
    "pump": ("compressor", (0.9, 0.9, 1.4), 0.7),
    "box": ("box", (1.6, 1.6, 0), 0.8),
}
NOT_CONNECTED = "not connected"


def _r(v):
    return round(float(v), 3)


def fillet(points, radius=0.35, steps=4):
    """Rounded corners on a polyline (same rule as the TE tour's pipe routes)."""
    if len(points) < 3:
        return [list(map(_r, p)) for p in points]
    out = [list(points[0])]
    for i in range(1, len(points) - 1):
        a, b, c = points[i - 1], points[i], points[i + 1]
        v1 = [b[k] - a[k] for k in range(3)]
        v2 = [c[k] - b[k] for k in range(3)]
        l1, l2 = math.sqrt(sum(x * x for x in v1)), math.sqrt(sum(x * x for x in v2))
        if l1 < 1e-6 or l2 < 1e-6:
            continue
        r = min(radius, l1 / 2, l2 / 2)
        p0 = [b[k] - v1[k] / l1 * r for k in range(3)]
        p1 = [b[k] + v2[k] / l2 * r for k in range(3)]
        for s in range(steps + 1):
            t = s / steps
            out.append([(1 - t) ** 2 * p0[k] + 2 * (1 - t) * t * b[k] + t * t * p1[k] for k in range(3)])
    out.append(list(points[-1]))
    return [[_r(x) for x in p] for p in out]


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def fit(points, direction, side=0.82, top=0.5, bottom=0.62, aspect=16 / 9):
    """Camera along `direction` from the points' centre, at the smallest distance at which every point projects
    inside the allowed frame (room left for the cards at the top and the caption bar at the bottom)."""
    lo = [min(q[i] for q in points) for i in range(3)]
    hi = [max(q[i] for q in points) for i in range(3)]
    t = [(lo[i] + hi[i]) / 2 for i in range(3)]
    d = _norm(direction)
    tan_h = SENSOR_MM / 2 / LENS_MM
    tan_v = tan_h / aspect

    def fits(dist):
        cam = [t[i] + dist * d[i] for i in range(3)]
        fwd = _norm([t[i] - cam[i] for i in range(3)])
        right = _norm(_cross(fwd, (0.0, 0.0, 1.0)))
        up = _cross(right, fwd)
        for q in points:
            v = [q[i] - cam[i] for i in range(3)]
            depth = _dot(v, fwd)
            if depth <= 0.5:
                return False
            x, y = _dot(v, right) / depth / tan_h, _dot(v, up) / depth / tan_v
            if not (-side <= x <= side and -bottom <= y <= top):
                return False
        return True
    lo_d, hi_d = 1.0, 3000.0
    for _ in range(60):
        mid = (lo_d + hi_d) / 2
        lo_d, hi_d = (lo_d, mid) if fits(mid) else (mid, hi_d)
    return [_r(t[i] + hi_d * d[i]) for i in range(3)], [_r(c) for c in t]


SOURCE_WORDS = {"equipment_schedule": "equipment schedule", "drawing_label": "drawing label",
                "tag_code": "tag type code", "generic": "generic"}


def short(text):
    return text.split(" (from")[0]


def build(structure):
    areas = {a["sheet"]: a for a in structure["areas"]}
    order = structure["tour_order"]
    eq_all = {e["id"]: e for e in structure["equipment"]}
    cols = 4
    origin = {}
    for k, s in enumerate(order):
        r, c = divmod(k, cols)
        c = c if r % 2 == 0 else cols - 1 - c
        origin[s] = (c * (PAD_W + GAP), -r * (PAD_D + GAP))
    equipment, labels, markers = [], [], []
    pos2 = {}
    for s in order:
        ox, oy = origin[s]
        mine = [eq_all[i] for i in areas[s]["equipment"]]
        pts = {}
        for e in mine:
            b = e["box_0_1000"]
            pts[e["id"]] = [ox + 2 + (b[0] + b[2]) / 2000 * (PAD_W - 4), oy - 2 - (b[1] + b[3]) / 2000 * (PAD_D - 4)]
        for _ in range(80):   # keep shapes apart (drawing positions crowd), deterministic
            moved = False
            ids = sorted(pts)
            for i, a in enumerate(ids):
                for b2 in ids[i + 1:]:
                    dx, dy = pts[b2][0] - pts[a][0], pts[b2][1] - pts[a][1]
                    d = math.hypot(dx, dy)
                    if d < 4.0:
                        if d < 1e-6:
                            dx, dy, d = 1.0, 0.0, 1.0
                        push = (4.0 - d) / 2 + 0.05
                        pts[a][0] -= dx / d * push; pts[a][1] -= dy / d * push
                        pts[b2][0] += dx / d * push; pts[b2][1] += dy / d * push
                        moved = True
            if not moved:
                break
        for e in mine:
            kind = icon_kind(e)
            shape, dims, nz = SHAPES[kind]
            x, y = pts[e["id"]]
            d, h, length = dims
            top = (0.8 + h + d * 0.22) if shape == "vertical_vessel" else nz + d / 2 + 0.3
            p = {"text": short(e["purpose"]["text"]), "source": SOURCE_WORDS[e["purpose"]["source"]]}
            equipment.append({"id": e["id"], "name": e["tag"] or "untagged " + e["class"], "kind": e["class"],
                              "icon": kind, "shape": shape, "position": [_r(x), _r(y), 0.0], "dims": list(dims),
                              "height": _r(top), "nozzle_z": nz, "agitator": False, "nozzles": [], "area": s,
                              "extent": [_r(max(d, length) / 2 + 0.3), _r(d / 2 + 0.3), _r(top)],
                              "purpose": p, "geometry_status": "placeholder: parametric shape and size, not plant "
                                                               "geometry; position = drawing position"})
            pos2[e["id"]] = (x, y)
            labels.append({"id": "unit:" + e["id"], "kind": "tag", "body": "%s\n%s" % (
                e["tag"] or "untagged " + e["class"], p["text"][:46]), "anchor": [_r(x), _r(y), _r(top + 0.5)],
                "unit": e["id"]})
        title = areas[s]["label"] if areas[s]["name"] else "Sheet %s, unnamed (%s tags)" % (
            s, areas[s]["system_code"] or "?")
        labels.append({"id": "area:" + s, "kind": "unit", "body": "%d. %s" % (order.index(s) + 1, title),
                       "anchor": [_r(ox + PAD_W / 2), _r(oy - PAD_D / 2), 9.0]})
    by_id = {e["id"]: e for e in equipment}
    pipes = []
    for s in order:
        links = [l for l in structure["unit_links"] if l["sheet"] == s and l["a"] in by_id and l["b"] in by_id]
        for k, l in enumerate(display_links(links, {i: (p[0] * 40, -p[1] * 40) for i, p in pos2.items()})):
            d = directed_pair(l)
            directed = stream_is_directed(d)
            a, b = by_id[d["from"]], by_id[d["to"]]
            za, zb = min(a["nozzle_z"], 1.2), min(b["nozzle_z"], 1.2)
            z = RACK_Z + 0.35 * (k % 3)
            (ax, ay), (bx, by) = pos2[a["id"]], pos2[b["id"]]
            corners = [(ax, ay, za + 0.4), (ax, ay, z), (bx, ay, z), (bx, by, z), (bx, by, zb + 0.4)]
            pipes.append({"id": "P-%s-%s" % (a["id"], b["id"]), "from": a["id"], "to": b["id"], "service": "process",
                          "points": fillet(corners), "directed": directed,
                          "direction_basis": ("read from the drawing (%s, confidence %s)" % (l["hops_directed"],
                                                                                             l["confidence"]))
                          if directed else "not shown on the drawing: no chevrons",
                          "route_status": "placeholder route, not a piping route", "area": s})
    # between areas: one pipe per pair and direction, pad centre to pad centre on a higher rack
    pairs = defaultdict(set)
    for e in structure["area_links"]:
        if e["direction"] in ("a_to_b", "b_to_a"):
            frm, to = (e["a"], e["b"]) if e["direction"] == "a_to_b" else (e["b"], e["a"])
            pairs[(frm, to)].add("directed")
        else:
            pairs[tuple(sorted((e["a"], e["b"]), key=int))].add("undirected")
    for k, ((frm, to), kinds) in enumerate(sorted(pairs.items())):
        if "directed" not in kinds and ((to, frm) in pairs and "directed" in pairs[(to, frm)]):
            continue
        (fx, fy), (tx, ty) = origin[frm], origin[to]
        off = 1.2 if (to, frm) in pairs else 0.0
        a = (fx + PAD_W / 2 + off, fy - PAD_D / 2 + off)
        b = (tx + PAD_W / 2 + off, ty - PAD_D / 2 + off)
        z = AREA_RACK_Z + 0.4 * (k % 3)
        corners = [(a[0], a[1], 0.6), (a[0], a[1], z), (b[0], a[1], z), (b[0], b[1], z), (b[0], b[1], 0.6)]
        pipes.append({"id": "A-%s-%s" % (frm, to), "from": "area:" + frm, "to": "area:" + to, "service": "process",
                      "points": fillet(corners, radius=0.8), "directed": "directed" in kinds,
                      "direction_basis": "off-page connector flags" if "directed" in kinds else
                      "connected, direction not shown", "route_status": "schematic link between areas, not a route"})
    # instruments: a few markers per stop, all not connected
    insts = structure.get("instrument_markers", [])
    for i in insts:
        e = by_id.get(i["unit"])
        if not e:
            continue
        n = sum(1 for m in markers if m["unit"] == e["id"])
        if n >= 1 or sum(1 for m in markers if by_id[m["unit"]]["area"] == e["area"]) >= 4:
            continue
        x, y, _ = e["position"]
        ang = math.radians(-60 - 60 * n)
        r = e["extent"][0] + 0.5
        p = [_r(x + r * math.cos(ang)), _r(y + r * math.sin(ang)), _r(min(e["height"], 3.0) * 0.6 + 0.4)]
        markers.append({"tag": i["tag"], "unit": e["id"], "position": p, "connected": False,
                        "placement_basis": "beside its equipment; no tap location implied"})
        labels.append({"id": "tag:" + i["tag"] + "@" + e["id"], "kind": "tag", "body": "%s  %s" % (i["tag"],
                                                                                                   NOT_CONNECTED),
                       "anchor": p, "marker": i["tag"], "unit": e["id"]})
    seen, uniq = set(), []
    for m in markers:   # the template keys markers by tag
        if m["tag"] in seen:
            continue
        seen.add(m["tag"])
        uniq.append(m)
    markers = uniq
    labels = [l for l in labels if not l["id"].startswith("tag:") or l["marker"] in seen]
    scene = {"schema": "pid-3d-scene/0 (prototype)", "model_id": structure["meta"]["model_id"],
             "title": "OPEN100: 12 drawings stitched into one plant", "label_layout": "declutter",
             "disclaimer": "PROTOTYPE. Structure only, no process data. Positions are drawing positions; sizes, "
                           "elevations and routes are placeholders.",
             "equipment": equipment, "boundaries": [], "pipes": pipes, "utilities": [], "valves": [],
             "markers": markers, "labels": labels, "replay_states": [], "level_bands": [],
             "camera_lens_mm": LENS_MM, "camera_sensor_mm": SENSOR_MM, "still_resolution": [1920, 1080],
             "video": {"width": 960, "height": 540, "fps": 10}, "timeline": [], "tour_order": order,
             "tour_order_basis": structure["tour_order_basis"]}
    scene["shots"] = shots(scene, structure, origin, by_id)
    return scene


def card_text(s, structure, by_id):
    a = next(x for x in structure["areas"] if x["sheet"] == s)
    lines = ["What is here (from the drawing)"]
    for e in [by_id[i] for i in a["equipment"] if i in by_id][:6]:
        lines.append("%s: %s [%s]" % (e["name"], e["purpose"]["text"][:40], e["purpose"]["source"]))
    more = len(a["equipment"]) - 6
    if more > 0:
        lines.append("+%d more equipment" % more)
    lines.append("Area name: %s" % a["name_source"].replace("_", " "))
    return "\n".join(lines)


def flows_text(s, structure):
    ins = sorted({e["a"] if e["direction"] == "a_to_b" else e["b"] for e in structure["area_links"]
                  if s in (e["a"], e["b"]) and e["direction"] in ("a_to_b", "b_to_a")
                  and (e["b"] if e["direction"] == "a_to_b" else e["a"]) == s}, key=int)
    outs = sorted({e["b"] if e["direction"] == "a_to_b" else e["a"] for e in structure["area_links"]
                   if s in (e["a"], e["b"]) and e["direction"] in ("a_to_b", "b_to_a")
                   and (e["a"] if e["direction"] == "a_to_b" else e["b"]) == s}, key=int)
    f = lambda xs: ", ".join("sheet " + x for x in xs) or "none"  # noqa: E731
    return "Flow read from off-page flags: in from %s; out to %s." % (f(ins), f(outs))


def shots(scene, structure, origin, by_id):
    order = scene["tour_order"]
    n = len(order)
    legend = {"id": "overlay:legend", "kind": "legend", "corner": "bottom_right", "title": "What the marks mean",
              "rows": [{"text": "Chevrons: direction read from the drawing", "swatch": "service:process"},
                       {"text": "No chevrons: direction not shown", "swatch": "service:process"},
                       {"text": "Dark marker: instrument, not connected", "swatch": "state:not_connected"}]}
    badge = {"id": "overlay:badge", "kind": "badge", "corner": "top_right", "text": BADGE}

    def caption(title, sentence):
        return {"id": "overlay:caption", "kind": "caption", "text": title + "\n" + sentence}
    every = [tuple(e["position"][:2]) + (z,) for e in scene["equipment"] for z in (0.0, e["height"])]
    every += [(origin[s][0] + dx, origin[s][1] - dy, 0.0) for s in order for dx in (0, PAD_W) for dy in (0, PAD_D)]
    cam, tgt = fit(every, (0.35, -1.0, 1.3), side=0.86, top=0.42, bottom=0.62)
    out = [{"name": "00_overview", "camera": cam, "target": tgt, "state_index": 0, "focus": None,
            "visible": ["area:" + s for s in order], "bodies": {}, "markers": [], "utilities": [], "chevrons": True,
            "highlight": [], "level_bands": [],
            "overlays": [badge, legend, caption("Overview: %s" % scene["title"],
                                                "Areas in the inferred tour order 1-%d. Lines between areas carry flow "
                                                "chevrons only where off-page flags show the direction. No live values."
                                                % n)]}]
    for i, s in enumerate(order, 1):
        mine = [e for e in scene["equipment"] if e["area"] == s]
        if not mine:
            continue
        pts = [(e["position"][0] + sx * e["extent"][0], e["position"][1] + sy * e["extent"][1], z)
               for e in mine for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, e["height"] + 1.0)]
        pts += [tuple(m["position"]) for m in scene["markers"] if by_id[m["unit"]]["area"] == s]
        cam, tgt = fit(pts, (0.3, -1.0, 1.05), side=0.6, top=0.3, bottom=0.55)
        vis = ["area:" + s] + ["unit:" + e["id"] for e in mine] + [l["id"] for l in scene["labels"]
                                                                    if l["id"].startswith("tag:") and
                                                                    by_id[l["unit"]]["area"] == s]
        a = next(x for x in structure["areas"] if x["sheet"] == s)
        out.append({"name": "%02d_stop_sheet%s" % (i, s), "camera": cam, "target": tgt, "state_index": 0,
                    "focus": None, "visible": vis, "bodies": {},
                    "markers": [m["tag"] for m in scene["markers"] if by_id[m["unit"]]["area"] == s],
                    "utilities": [], "chevrons": True, "highlight": [], "level_bands": [], "optional": True,
                    "overlays": [badge, legend,
                                 {"id": "overlay:purpose", "kind": "card", "corner": "top_left",
                                  "text": card_text(s, structure, by_id)},
                                 caption("Stop %d of %d: sheet %s, %s" % (i, n, s, a["label"]),
                                         flows_text(s, structure) + " Structure only, no process data.")]})
    return out


def blender_script(scene):
    payload = json.dumps(scene, indent=1, sort_keys=True)
    if '"""' in payload:
        raise ValueError("scene text cannot contain a triple quote")
    return TEMPLATE.read_text(encoding="utf-8").replace("__SCENE_JSON__", payload).replace(
        "# __LABEL_LAYOUT__", label_layout.embeddable_source())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", help="Blender executable; renders the stills")
    ap.add_argument("--stops", default="1,5", help="tour stop numbers to render besides the overview")
    a = ap.parse_args()
    structure = json.loads((ROOT / "out/open100_structural/plant_structure.json").read_text(encoding="utf-8"))
    scene = build(structure)
    keep = {"00_overview"} | {s["name"] for s in scene["shots"] if s["name"][:2].isdigit()
                              and int(s["name"][:2]) in {int(x) for x in a.stops.split(",")}}
    scene["all_shot_names"] = [s["name"] for s in scene["shots"]]
    scene["shots"] = [s for s in scene["shots"] if s["name"] in keep]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "open100_scene.json").write_text(json.dumps(scene, indent=1), encoding="utf-8")
    (OUT / "open100_scene_blender.py").write_text(blender_script(scene), encoding="utf-8")
    print("scene: %d equipment, %d pipes (%d directed), %d markers, shots %s" % (
        len(scene["equipment"]), len(scene["pipes"]), sum(p["directed"] for p in scene["pipes"]),
        len(scene["markers"]), [s["name"] for s in scene["shots"]]))
    if a.blender:
        renders = OUT / "renders"
        subprocess.run([a.blender, "--background", "--factory-startup", "--python",
                        str(OUT / "open100_scene_blender.py"), "--", "--out", str(renders)], check=True)
        from PIL import Image
        SHOTS.mkdir(parents=True, exist_ok=True)
        for s in scene["shots"]:
            Image.open(renders / (s["name"] + ".png")).convert("RGB").save(SHOTS / ("3d-%s.jpg" % s["name"]),
                                                                           quality=88)
            print("still", SHOTS / ("3d-%s.jpg" % s["name"]))


if __name__ == "__main__":
    main()
