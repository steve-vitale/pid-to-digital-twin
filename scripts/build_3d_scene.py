"""Prototype: build a 3D walkthrough scene for Blender from the same contract the 2D mimic uses.

Inputs (all existing, nothing new is invented as a source of truth):
  data/te_process_model.json   units, streams, instruments, final elements (the twin contract)
  data/te_display_layout.json  the 2D mimic's reviewed presentation: symbol kind per unit, which stream or unit each
                               displayed tag is associated with, and the direction adapter that authorizes seed arrows
  out/ignition/normal_bands.json, out/ignition/gateway/build_meta.json   normal bands and published alarm setpoints
  data/external/te-braatz/d06_te.dat (optional)   recorded fault-6 replay, to colour the tags per sample

Output: out/3d/te_scene.json (the derived scene, inspectable), out/3d/te_scene_blender.py (a self-contained script
for `blender --background --python`, built from scripts/blender_tour_template.py), and the orientation tour's
out/3d/orientation_tour.srt and orientation_script.json (scripts/orientation_tour.py). With --blender PATH, it also
runs Blender to render 1920x1080 stills into out/3d/renders/ together with label_boxes.json, the measured label
geometry and contrast that scripts/verify_3d_render.py checks. With --animation it renders the narrated orientation
video (low resolution); with --voice the narration is synthesized offline (Windows SAPI) and muxed by ffmpeg if one
is found; with --gltf it writes a GLB for web viewers. --label-layout legacy reproduces the 429d7a7 labels and
marker offsets, so the before/after legibility comparison is measured by the same code.

PROTOTYPE, NOT PLANT GEOMETRY. A P&ID (and the TE seed model) gives topology and tags, not layout. Plan positions
are the 2D mimic's seed coordinates scaled to metres; every size, elevation, nozzle and pipe route is a parametric
placeholder. Instrument positions follow the 2D layout's association (on a stream, or on a unit) where one exists;
otherwise the seed's stream/unit ownership only. Nothing here is a measured tap location. The scene is
deterministic: the same inputs always give the same scene and script.

Model use: none at run time. Claude (the coding agent) wrote this script and chose the placeholder shapes.

  python scripts/build_3d_scene.py                         # write scene JSON + Blender script only
  python scripts/build_3d_scene.py --blender <path to blender> [--gltf] [--animation --voice]
  python scripts/verify_3d_render.py                       # check the last render
"""
import argparse
import json
import math
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ignition"))
from display_contract import require_display_layout, stream_is_directed  # noqa: E402
import label_layout  # noqa: E402
import orientation_tour  # noqa: E402

TEMPLATE = ROOT / "scripts" / "blender_tour_template.py"
LABEL_FONT = ROOT / "assets" / "fonts" / "AtkinsonHyperlegible-Regular.ttf"  # SIL OFL 1.1; see NOTICE.md
LENS_MM, SENSOR_MM = 28.0, 36.0
STILL_RESOLUTION = (1920, 1080)   # legibility is judged at 1080p
VIDEO = {"width": 960, "height": 540, "fps": 10}
# Candidate stop views (direction from the unit toward the camera), in preference order: front-right, front-left,
# higher front-right, higher front-left, side-right, side-left, steep front. Chosen by Claude; the renderer picks by marker visibility.
VIEW_DIRECTIONS = ((0.3, -1.0, 0.55), (-0.3, -1.0, 0.55), (0.7, -1.0, 0.8), (-0.7, -1.0, 0.8), (1.0, -0.5, 0.6),
                   (-1.0, -0.5, 0.6), (0.0, -0.6, 1.0))
SCALE = 0.03            # metres per 2D seed-layout pixel (placeholder plan scale)
Y_ORIGIN = 500          # 2D y grows downward; flip it so "up the screen" is "further back" on the plot plan
RACK_Z, RACK_STEP = 7.0, 0.35
PLACEHOLDER = "placeholder: parametric shape and size, not plant geometry"

# Parametric placeholder per 2D symbol kind. dims are metres: (diameter or width, height, length). All invented.
PRIMITIVES = {
    "feed":      {"shape": "header",        "dims": (0.6, 0.6, 6.0), "nozzle_z": 1.5},
    "reactor":   {"shape": "vertical_vessel", "dims": (2.6, 5.0, 0), "nozzle_z": 3.0, "agitator": True},
    "condenser": {"shape": "horizontal_exchanger", "dims": (1.0, 1.0, 4.5), "nozzle_z": 3.5},
    "separator": {"shape": "vertical_vessel", "dims": (2.0, 3.5, 0), "nozzle_z": 2.0},
    "compressor": {"shape": "compressor",   "dims": (1.6, 1.4, 2.6), "nozzle_z": 1.2},
    "stripper":  {"shape": "column",        "dims": (1.4, 12.0, 0), "nozzle_z": 4.0},
}
LEGACY_COLUMN_HEIGHT = 10.0   # 429d7a7 stripper height, kept only for the before/after reproduction
RACK_LEVELS = {"upper": 6.2, "lower": 5.0}   # two pipe-rack elevations (placeholder)
FILLET_M = 0.35                              # bend radius on pipe routes (placeholder)
# Service per stream: Claude's reading of the TE flowsheet (Downs & Vogel 1993, Fig. 1) on the model's topology,
# which is checked against the simulator source (out/te_topology_check.md). Unknown streams fall back to "process". Used for colour coding and rack elevation only.
STREAM_SERVICE = {"S1": "gas_feed", "S2": "gas_feed", "S3": "gas_feed", "S4": "gas_feed", "S6": "gas_feed",
                  "S7": "reactor_effluent", "S7b": "reactor_effluent", "S10": "liquid_product",
                  "S11": "liquid_product", "S5": "recycle", "S8": "recycle", "S8b": "recycle", "S9": "purge"}
SERVICE_LEVEL = {"gas_feed": "upper", "recycle": "upper", "purge": "upper", "process": "upper",
                 "reactor_effluent": "lower", "liquid_product": "lower"}
SERVICE_BASIS = "Claude's reading of the published TE flowsheet on the source-checked topology (placeholder)"
# Utilities are not streams in the contract. A stub is drawn only where a final element's own description names
# the utility, and is labelled inferred.
UTILITY_RULES = (("cooling water", "cooling_water"), ("steam", "steam"))
EYE_Z = 5.0                                   # stop cameras at mezzanine eye height (m)
STOP_AZIMUTHS = (-70, -110, -45, -135, -20, -160)   # camera bearing from the unit, degrees (-90 = from -y)
OVERVIEW_DIRECTION = (0.75, -1.0, 0.85)       # elevated three-quarter view
GENERIC = {"shape": "box", "dims": (1.5, 1.5, 1.5), "nozzle_z": 1.0}
SHELL_HEIGHT = {"pressure": 0.85, "temperature": 0.5, "level": 0.3, "composition": 0.6, "flow": 0.4, "power": 0.9}
# Platform decks the Blender template draws on a column (blender_tour_template.py, same levels). A marker in a deck's
# plane is hidden by the deck from every elevated camera, so it is lifted just above it.
COLUMN_PLATFORM_Z = (3.0, 6.0, 9.0, 12.0)
STATES = ("normal", "outside_band", "alarm", "unknown", "not_connected")


def _finite(*values):
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)


def _r(v):
    return round(float(v), 3)


def flow_order(model, directed):
    """Units in flow order: start where boundary feeds enter, follow authorized directions (stream order breaks
    ties). Without authorized directions the order is the model's own, and is labelled as such."""
    ids = [u["id"] for u in model["units"]]
    if not directed:
        return ids, "model_order (no authorized flow direction)"
    nxt = {u: [] for u in ids}
    starts = []
    for s in model["streams"]:
        if s["from"] in nxt and s["to"] in nxt:
            nxt[s["from"]].append(s["to"])
        elif s["from"] == "BL" and s["to"] in nxt and s["to"] not in starts:
            starts.append(s["to"])
    order, seen = [], set()

    def visit(u):
        if u in seen:
            return
        seen.add(u)
        order.append(u)
        for v in nxt[u]:
            visit(v)
    for u in starts + ids:
        visit(u)
    return order, "stream directions from the model, checked against the simulator source; unverified by operations"


def classify(value, band, alarms):
    """One replay value -> display state. Bands are display aids; only published setpoints are alarms."""
    if not _finite(value):
        return "unknown"
    if any(value > a["setpointA"] for a in alarms):
        return "alarm"
    if band and not band["lo"] <= value <= band["hi"]:
        return "outside_band"
    return "normal"


def replay_states(tags, rows, columns, bands, alarms, samples, fault_start=None):
    """Per requested sample: tag -> state (and the recorded value, for labels and narration). Tags without a replay
    column stay not_connected; never inferred."""
    out = []
    for sample in samples:
        row = rows[sample] if 0 <= sample < len(rows) else None
        states, values = {}, {}
        for tag in tags:
            col = columns.get(tag)
            if col is None:
                states[tag] = "not_connected"
            elif row is None or col >= len(row):
                states[tag] = "unknown"
            else:
                states[tag] = classify(row[col], bands.get(tag), alarms.get(tag, []))
                if _finite(row[col]):
                    values[tag] = _r(row[col]) if abs(row[col]) >= 1 else round(float(row[col]), 5)
        minutes = None if fault_start is None else (sample - fault_start) * 3
        out.append({"sample": sample, "minutes_after_fault": minutes, "states": states, "values": values})
    return out


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _norm(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return tuple(c / n for c in a)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def fit_camera(points, direction, aspect=16 / 9, side=0.8, top=0.74, bottom=0.40, lens=LENS_MM, sensor=SENSOR_MM):
    """Procedural framing: put the camera along `direction` from the points' centre, at the smallest distance at
    which every point projects inside the frame. The bottom limit leaves room for the caption band and the top
    limit leaves room for labels above their anchors."""
    d = _norm(direction)
    fwd = tuple(-c for c in d)
    right = _norm(_cross(fwd, (0.0, 0.0, 1.0)))
    up = _cross(right, fwd)
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    t = tuple((lo[i] + hi[i]) / 2 for i in range(3))
    tan_h = sensor / 2 / lens
    tan_v = tan_h / aspect
    dist = 1.0
    for p in points:
        v = _sub(p, t)
        x, y, toward = _dot(v, right), _dot(v, up), _dot(v, d)
        dist = max(dist, abs(x) / (side * tan_h) + toward,
                   (y / (top * tan_v) if y > 0 else -y / (bottom * tan_v)) + toward)
    return [_r(t[i] + dist * d[i]) for i in range(3)], [_r(c) for c in t]


def clear_of(ang, avoid, min_sep=math.radians(22)):
    """Nearest angle to `ang` that is at least min_sep from every angle in `avoid` (searching 3-degree steps)."""
    def ok(a):
        return all(abs((a - b + math.pi) % (2 * math.pi) - math.pi) >= min_sep for b in avoid)
    for step in range(0, 61):
        for sign in (1, -1):
            cand = ang + sign * math.radians(3 * step)
            if ok(cand):
                return cand
    return ang


def inside_equipment(p, e, margin=0.0):
    """True if point p falls inside the placeholder volume of equipment e (plus margin)."""
    x, y, _ = e["position"]
    hx, hy, top = e.get("extent") or equipment_extent(e)
    if p[2] > top + margin or p[2] < -margin:
        return False
    if e["shape"] in ("vertical_vessel", "column"):
        return math.hypot(p[0] - x, p[1] - y) < hx + margin
    return abs(p[0] - x) < hx + margin and abs(p[1] - y) < hy + margin


def equipment_extent(e):
    """Half sizes (x, y) and top z of the placeholder shape, matching the Blender builder."""
    d, h, length = e["dims"]
    shape = e["shape"]
    if shape in ("vertical_vessel", "column"):
        return d / 2, d / 2, 0.8 + h + d * 0.22 + (1.2 if e.get("agitator") else 0.0)
    if shape == "horizontal_exchanger":
        return length / 2 + 0.4, d / 2, e["nozzle_z"] + d / 2
    if shape == "header":
        return length / 2, d / 2, e["nozzle_z"] + d / 2
    if shape == "compressor":
        return (length + 1.2) / 2, (d + 0.4) / 2, 0.3 + d
    return d / 2, d / 2, h


def fit_dir(points, direction, side=0.86, top=0.6, bottom=0.62, lens=LENS_MM, sensor=SENSOR_MM, aspect=16 / 9):
    """Overview camera along `direction`, exact pinhole fit by binary search, then the target is re-centred so the
    content sits in the middle of the allowed band (no empty half-frame)."""
    lo = [min(q[i] for q in points) for i in range(3)]
    hi = [max(q[i] for q in points) for i in range(3)]
    t = [(lo[i] + hi[i]) / 2 for i in range(3)]
    d = _norm(direction)
    tan_h = sensor / 2 / lens
    tan_v = tan_h / aspect

    def proj(tgt, dist):
        cam = tuple(tgt[i] + dist * d[i] for i in range(3))
        fwd = _norm(_sub(tgt, cam))
        right = _norm(_cross(fwd, (0.0, 0.0, 1.0)))
        up = _cross(right, fwd)
        out = []
        for q in points:
            v = _sub(q, cam)
            depth = _dot(v, fwd)
            out.append((_dot(v, right) / depth / tan_h, _dot(v, up) / depth / tan_v, depth))
        return out, right, up

    def fits(tgt, dist):
        pts, _, _ = proj(tgt, dist)
        return all(p[2] > 0.5 and -side <= p[0] <= side and -bottom <= p[1] <= top for p in pts)

    dist = 50.0
    for _ in range(4):
        lo_d, hi_d = 1.0, 2000.0
        for _ in range(60):
            mid = (lo_d + hi_d) / 2
            lo_d, hi_d = (lo_d, mid) if fits(t, mid) else (mid, hi_d)
        dist = hi_d
        pts, right, up = proj(t, dist)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        dx = (max(xs) + min(xs)) / 2
        dy = (max(ys) + min(ys)) / 2 - (top - bottom) / 2
        depth = sum(p[2] for p in pts) / len(pts)
        t = [t[i] + right[i] * dx * depth * tan_h + up[i] * dy * depth * tan_v for i in range(3)]
    cam = [t[i] + dist * d[i] for i in range(3)]
    return [_r(c) for c in cam], [_r(c) for c in t]


def fit_eye(points, azimuth_deg, eye_z=EYE_Z, side=0.55, top=0.5, bottom=0.6, lens=LENS_MM, sensor=SENSOR_MM,
            aspect=16 / 9):
    """Stop camera at a fixed eye height on a bearing from the points' centre, at the smallest distance at which
    every point projects inside the margins (normalized frame half-extents). Margins leave room for the cards at
    the top and the caption bar at the bottom: breathing room, not a tight crop."""
    lo = [min(q[i] for q in points) for i in range(3)]
    hi = [max(q[i] for q in points) for i in range(3)]
    t = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)
    az = math.radians(azimuth_deg)
    tan_h = sensor / 2 / lens
    tan_v = tan_h / aspect

    def fits(dist):
        cam = (t[0] + dist * math.cos(az), t[1] + dist * math.sin(az), eye_z)
        fwd = _norm(_sub(t, cam))
        right = _norm(_cross(fwd, (0.0, 0.0, 1.0)))
        up = _cross(right, fwd)
        for q in points:
            v = _sub(q, cam)
            depth = _dot(v, fwd)
            if depth <= 0.5:
                return False
            x, y = _dot(v, right) / depth / tan_h, _dot(v, up) / depth / tan_v
            if not (-side <= x <= side and -bottom <= y <= top):
                return False
        return True
    lo_d, hi_d = 1.0, 400.0
    for _ in range(60):
        mid = (lo_d + hi_d) / 2
        lo_d, hi_d = (lo_d, mid) if fits(mid) else (mid, hi_d)
    cam = (t[0] + hi_d * math.cos(az), t[1] + hi_d * math.sin(az), eye_z)
    return [_r(c) for c in cam], [_r(c) for c in t]


def fillet(points, radius=FILLET_M, steps=4):
    """Round each orthogonal corner with a short quadratic arc (modest bend radius; still a schematic route)."""
    if len(points) < 3:
        return [list(p) for p in points]
    out = [tuple(points[0])]
    for i in range(1, len(points) - 1):
        a, b, c = points[i - 1], points[i], points[i + 1]
        l1, l2 = math.dist(a, b), math.dist(b, c)
        r = min(radius, 0.45 * l1, 0.45 * l2)
        if r <= 1e-6:
            out.append(tuple(b))
            continue
        q1 = tuple(b[k] + (a[k] - b[k]) * r / l1 for k in range(3))
        q2 = tuple(b[k] + (c[k] - b[k]) * r / l2 for k in range(3))
        for j in range(steps + 1):
            u = j / steps
            out.append(tuple((1 - u) ** 2 * q1[k] + 2 * (1 - u) * u * b[k] + u ** 2 * q2[k] for k in range(3)))
    out.append(tuple(points[-1]))
    return [[_r(c) for c in p] for p in out]


def _route(a, b, lane, z=None):
    """Schematic pipe: up from nozzle a to a rack elevation, across in X then Y, down to nozzle b. Placeholder.
    z=None is the 429d7a7 rule (one lane per stream, stacked from 7 m)."""
    z = RACK_Z + RACK_STEP * lane if z is None else z
    pts = [a, (a[0], a[1], z), (b[0], a[1], z), (b[0], b[1], z), b]
    clean = [pts[0]]
    for p in pts[1:]:
        if any(abs(p[i] - clean[-1][i]) > 1e-6 for i in range(3)):
            clean.append(p)
    return [tuple(_r(c) for c in p) for p in clean]


def _point_along(points, t):
    seg = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    goal, run = t * sum(seg), 0.0
    for i, length in enumerate(seg):
        if run + length >= goal and length:
            f = (goal - run) / length
            return tuple(points[i][k] + f * (points[i + 1][k] - points[i][k]) for k in range(3))
        run += length
    return points[-1]


def build_scene(model, layout, bands=None, alarms=None, replay=None, samples=(), fault_start=None, legacy_markers=False):
    """Pure function: contract -> scene description. Raises ValueError on a layout that drifted from the model.
    legacy_markers=True reproduces the 429d7a7 marker offsets (for the before/after legibility comparison only)."""
    require_display_layout(model, layout)
    bands, alarms = bands or {}, alarms or {}
    for u in model["units"]:
        if not _finite(u.get("layout", {}).get("x"), u.get("layout", {}).get("y")):
            raise ValueError("unit %s has no finite 2D layout position to place in 3D" % u["id"])
    adapter = layout.get("direction_adapter") == "te_seed_from_to_unverified"
    directed = {s["id"]: stream_is_directed(s) or (adapter and "direction" not in s) for s in model["streams"]}

    equipment = {}
    for u in model["units"]:
        kind = layout["units"].get(u["id"], {}).get("kind")
        prim = PRIMITIVES.get(kind, GENERIC)
        x, y = u["layout"]["x"] * SCALE, (Y_ORIGIN - u["layout"]["y"]) * SCALE
        d, h, length = prim["dims"]
        if legacy_markers and prim["shape"] == "column":
            h = LEGACY_COLUMN_HEIGHT
        height = h if prim["shape"] in ("vertical_vessel", "column") else max(h, prim["nozzle_z"])
        equipment[u["id"]] = {
            "id": u["id"], "name": u["name"], "kind": kind or "unknown", "shape": prim["shape"],
            "position": [_r(x), _r(y), 0.0], "dims": [d, h, length], "height": _r(height),
            "nozzle_z": prim["nozzle_z"], "agitator": bool(prim.get("agitator")),
            "geometry_status": PLACEHOLDER if kind in PRIMITIVES else "placeholder: unknown kind, generic box",
            "verification": u.get("verification", {}).get("status", "unverified"),
        }
    cx = sum(e["position"][0] for e in equipment.values()) / len(equipment)
    cy = sum(e["position"][1] for e in equipment.values()) / len(equipment)

    incident = {uid: [s["id"] for s in model["streams"] if uid in (s["from"], s["to"])] for uid in equipment}

    def nozzle(uid, toward, sid):
        """Placeholder nozzle facing the other end; streams on one unit are spread sideways so they stay apart."""
        e = equipment[uid]
        x, y, _ = e["position"]
        dx, dy = toward[0] - x, toward[1] - y
        n = math.hypot(dx, dy) or 1.0
        r = e["dims"][0] / 2 + 0.2
        k, count = incident[uid].index(sid), len(incident[uid])
        if e["shape"] == "header":  # a header takes its connections along its (x) axis
            step = e["dims"][2] / count
            return (x + (k - (count - 1) / 2) * step, y, e["nozzle_z"] + e["dims"][0] / 2)
        if e["shape"] in ("vertical_vessel", "column") and not legacy_markers:
            # Spread by angle around the shell so every nozzle stays 0.2 m off it. (429d7a7 spread sideways by
            # 0.8 m, which left the stripper's S4/S11 ends floating off the thin column; the verifier caught it.)
            ang = math.atan2(dy, dx) + math.radians(28) * (k - (count - 1) / 2)
            return (x + r * math.cos(ang), y + r * math.sin(ang), e["nozzle_z"])
        side = (k - (count - 1) / 2) * 0.8
        return (x + r * dx / n - side * dy / n, y + r * dy / n + side * dx / n, e["nozzle_z"])

    boundaries, pipes, bl_count = [], [], {}
    for lane, s in enumerate(model["streams"]):
        ends = [s["from"], s["to"]]
        unit = next(e for e in ends if e in equipment)
        if "BL" in ends:
            ux, uy, _ = equipment[unit]["position"]
            dx, dy = ux - cx, uy - cy
            n = math.hypot(dx, dy) or 1.0
            k = bl_count.get(unit, 0)
            bl_count[unit] = k + 1
            side = (-dy / n, dx / n)
            off = (k - 1) * 1.6
            bx, by = ux + 5.5 * dx / n + off * side[0], uy + 5.5 * dy / n + off * side[1]
            boundaries.append({"id": "BL-" + s["id"], "stream": s["id"], "name": s["name"],
                               "position": [_r(bx), _r(by), 0.0]})
        pos = {e: tuple(equipment[e]["position"][:2]) for e in ends if e in equipment}
        if "BL" in ends:
            pos["BL"] = tuple(boundaries[-1]["position"][:2])
        a = pos["BL"] + (1.0,) if s["from"] == "BL" else nozzle(s["from"], pos[s["to"]], s["id"])
        b = pos["BL"] + (1.0,) if s["to"] == "BL" else nozzle(s["to"], pos[s["from"]], s["id"])
        service = STREAM_SERVICE.get(s["id"], "process")
        corners = _route(a, b, lane) if legacy_markers else _route(a, b, lane, RACK_LEVELS[SERVICE_LEVEL[service]])
        pipes.append({"id": s["id"], "name": s["name"], "from": s["from"], "to": s["to"],
                      "corners": [list(c) for c in corners],
                      "points": [list(c) for c in corners] if legacy_markers else fillet(corners),
                      "service": service, "service_basis": SERVICE_BASIS, "directed": directed[s["id"]],
                      "direction_basis": ("model direction, source-checked" if "direction" in s else "seed from/to, unverified")
                      if directed[s["id"]] else "unknown: no arrow",
                      "route_status": "placeholder: schematic rack route, not a piping route"})
    pipe_by_id = {p["id"]: p for p in pipes}
    # A paired-column corridor under the recycle return's actual long rack run. Invented structure, not plant data.
    recycle = pipe_by_id.get("S8b")
    rack = None
    if recycle and not legacy_markers:
        a, b = recycle["corners"][1:3]
        lo, hi = sorted((a[0], b[0]))
        rack = {"status": "placeholder: inferred overhead corridor, not a plant layout",
                "stations": [_r(lo + (hi - lo) * t) for t in (.15, .38, .61, .84)],
                "x": [lo, hi], "y": [_r(a[1] - .8), _r(a[1] + .8)], "z": _r(a[2] - .1)}

    cards = {}
    for uid, spec in layout["units"].items():
        for tag, card in spec.get("cards", {}).items():
            cards.setdefault(tag, card.get("association", {}))
    unavailable = set()
    for spec in layout["units"].values():
        for item in spec.get("unavailable", []) or []:
            unavailable.add(item.get("tag") if isinstance(item, dict) else item)
    # A tag is disputed while a discrepancy the layout records about it is still open; "Resolved ..." and
    # "Corrected ..." notes (the topology check, out/te_topology_check.md) settle it.
    open_notes = [d for d in layout.get("provenance", {}).get("discrepancies", [])
                  if not d.lower().startswith(("resolved", "corrected"))]
    disputed = {i["tag"] for i in model["instruments"] + model["final_elements"]
                if any(re.search(r"(?<![A-Z0-9-])%s(?![0-9])" % re.escape(i["tag"]), d) for d in open_notes)}

    markers, on_stream, on_unit, planned = [], {}, {}, []
    for item in model["instruments"] + model["final_elements"]:
        assoc = cards.get(item["tag"])
        if assoc and assoc.get("kind") == "stream" and assoc.get("id") in pipe_by_id:
            basis, attach = "display layout card: stream %s (%s)" % (assoc["id"], assoc.get("status")), ("stream", assoc["id"])
        elif assoc and assoc.get("kind") == "unit" and assoc.get("id") in equipment:
            basis, attach = "display layout card: unit %s (%s)" % (assoc["id"], assoc.get("status")), ("unit", assoc["id"])
        elif item.get("stream") in pipe_by_id:
            basis, attach = "seed model stream ownership only (no display card)", ("stream", item["stream"])
        else:
            basis, attach = "seed model unit ownership only (position on unit is arbitrary)", ("unit", item["unit"])
        planned.append((item, basis, attach))
    def nozzle_angles(uid):
        x, y, _ = equipment[uid]["position"]
        ends = [p["points"][0] for p in pipes if p["from"] == uid] + [p["points"][-1] for p in pipes if p["to"] == uid]
        return [math.atan2(pt[1] - y, pt[0] - x) for pt in ends if math.hypot(pt[0] - x, pt[1] - y) > 0.3]

    per_unit = {}
    for item, _, attach in planned:
        if attach[0] == "unit" and item["tag"] not in unavailable:
            per_unit[attach[1]] = per_unit.get(attach[1], 0) + 1
    for item, basis, attach in planned:
        if attach[0] == "stream":
            # Stack the tag on the riser at its owning unit's end of the pipe, so each tour stop shows its own
            # instruments; a tag owned by neither end sits mid-route. Still not a tap location.
            pipe = pipe_by_id[attach[1]]
            end = 0 if item.get("unit") == pipe["from"] else -1 if item.get("unit") == pipe["to"] else None
            key = (attach[1], end)
            k = on_stream.get(key, 0)
            on_stream[key] = k + 1
            if end is None:
                p = _point_along(pipe["points"], min(0.4 + 0.1 * k, 0.8))
                pos = (p[0] + 0.35, p[1] - 0.35, p[2] + 0.5)
            elif legacy_markers:
                p = pipe["points"][end]
                pos = (p[0] + 0.35, p[1] - 0.35, p[2] + 0.9 + 0.65 * k)
            else:
                # Beside the riser, on the side away from the unit's axis. (429d7a7 used a fixed (+0.35, -0.35)
                # offset, which put FT-106 and AT-123 inside the reactor shell; the render verifier caught it.)
                p = pipe["points"][end]
                e = equipment[item["unit"]]
                ox, oy = p[0] - e["position"][0], p[1] - e["position"][1]
                n = math.hypot(ox, oy)
                ox, oy = (ox / n, oy / n) if n > 0.3 else (0.0, -1.0)
                pos = (p[0] + 0.45 * ox, p[1] + 0.45 * oy - 0.2, p[2] + 0.9 + 0.65 * k)
                step = 0
                while inside_equipment(pos, e, margin=0.25) and step < 40:
                    pos, step = (pos[0] + 0.1 * ox, pos[1] + 0.1 * oy, pos[2]), step + 1
        elif item["tag"] in unavailable:
            # The display layout marks it unavailable (no replay source): show it above the unit, imply no position.
            e = equipment[attach[1]]
            basis = "display layout 'unavailable' entry; shown above unit %s, no position implied" % attach[1]
            pos = (e["position"][0], e["position"][1] - e["dims"][0] / 2 - 0.3, e["height"] + 1.2)
        else:
            e = equipment[attach[1]]
            k = on_unit.get(attach[1], 0)
            on_unit[attach[1]] = k + 1
            # Spread over the half of the shell facing the tour camera (-y), so every tag is visible at its stop,
            # and keep clear of the unit's own nozzles/risers (a riser in front of a marker hides it).
            ang = math.radians(-90 + (k - (per_unit[attach[1]] - 1) / 2) * min(40, 150 / per_unit[attach[1]]))
            ang = ang if legacy_markers else clear_of(ang, nozzle_angles(attach[1]))
            r = e["dims"][0] / 2 + 0.45
            z = e["height"] * SHELL_HEIGHT.get(item.get("variable"), 0.7)
            if not legacy_markers and e["shape"] == "column":
                z = next((zp + 0.5 for zp in COLUMN_PLATFORM_Z if abs(z - zp) < 0.5), z)
            pos = (e["position"][0] + r * math.cos(ang), e["position"][1] + r * math.sin(ang), max(z, 0.4))
        connected = item["tag"] not in unavailable and not (item.get("xmv", 0) > 11)
        markers.append({
            "tag": item["tag"], "kind": "final_element" if "xmv" in item else "instrument",
            "label": layout.get("labels", {}).get(item["tag"], item.get("description", "")),
            "description": item.get("description", ""), "model_stream": item.get("stream"),
            "unit": item.get("unit"), "attach": list(attach), "position": [_r(c) for c in pos],
            "placement_basis": basis, "connected": connected, "disputed": item["tag"] in disputed,
            "uom": item.get("uom", ""), "verification": item.get("verification", {}).get("status", "unverified"),
        })

    for e in equipment.values():
        hx, hy, top = equipment_extent(e)
        e["extent"] = [_r(hx), _r(hy), _r(top)]
        e["key_tags"] = key_tags(e["id"], markers, alarms, bands)
        e["nozzles"] = [{"stream": p["id"], "at": p["points"][0] if p["from"] == e["id"] else p["points"][-1]}
                        for p in pipes if e["id"] in (p["from"], p["to"])]

    utilities, valves = [], []
    if not legacy_markers:
        utilities = utility_stubs(model, equipment)
        for m in markers:
            if m["kind"] != "final_element" or not m["connected"]:
                continue
            if m["attach"][0] == "stream":
                pipe = pipe_by_id[m["attach"][1]]
                if m["unit"] in (pipe["from"], pipe["to"]):
                    end = pipe["corners"][0] if m["unit"] == pipe["from"] else pipe["corners"][-1]
                    valves.append({"tag": m["tag"], "on": "stream:" + pipe["id"], "unit": m["unit"],
                                   "service": pipe["service"], "axis": "z",
                                   "position": [end[0], end[1], m["position"][2]],
                                   "basis": "symbol on the line the contract attaches the tag to; position placeholder"})
            else:
                stub = next((u for u in utilities if u["tag"] == m["tag"] and u["role"] in ("supply", "steam")), None)
                if stub:
                    a, b = stub["corners"][0], stub["corners"][1]
                    vpos = [_r((a[k] + b[k]) / 2) for k in range(3)]
                    valves.append({"tag": m["tag"], "on": "utility:" + stub["id"], "unit": m["unit"],
                                   "service": stub["service"], "axis": "x" if abs(b[0] - a[0]) > abs(b[1] - a[1]) else "y",
                                   "position": vpos,
                                   "basis": "inferred: utility line inferred from the tag's description"})
                    # The tag's marker sits at its valve symbol (still a placeholder position, now a consistent one).
                    m["position"] = [vpos[0], _r(vpos[1] - 0.3), _r(vpos[2] + 0.35)]
                    m["placement_basis"] += "; marker moved to its valve symbol on the inferred utility line"

    def unit_points(uid):
        e = equipment[uid]
        x, y, _ = e["position"]
        hx, hy, top = e["extent"]
        pts = [(x + sx * hx, y + sy * hy, z) for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, top + 1.2)]
        pts += [tuple(m["position"]) for m in markers if m["unit"] == uid]
        pts += [tuple(b["position"][:2]) + (1.4,) for b in boundaries
                if any(p["id"] == b["stream"] and uid in (p["from"], p["to"]) for p in pipes)]
        return pts

    def focus_points(uid):
        """What a stop must frame: the unit's shape and label room, its key tags, its utility stubs."""
        e = equipment[uid]
        x, y, _ = e["position"]
        hx, hy, top = e["extent"]
        pts = [(x + sx * hx, y + sy * hy, z) for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, top + 0.8)]
        pts += [tuple(m["position"]) for m in markers if m["tag"] in e["key_tags"]]
        pts += [tuple(q) for u in utilities if u["unit"] == uid for q in (u["corners"][0], u["corners"][-1])]
        return pts

    order, order_basis = flow_order(model, any(directed.values()))
    tour = []
    for uid in order:
        e = equipment[uid]
        x, y, _ = e["position"]
        h = e["height"]
        dist = 6.5 + h * 0.9
        if legacy_markers:
            candidates = [dict(zip(("camera", "target"), fit_camera(unit_points(uid), d))) for d in VIEW_DIRECTIONS]
        else:
            candidates = [dict(zip(("camera", "target"), fit_eye(focus_points(uid), az))) for az in STOP_AZIMUTHS]
        tour.append({"unit": uid, "name": e["name"], "target": candidates[0]["target"],
                     "camera": candidates[0]["camera"], "camera_candidates": candidates,
                     "framing": "eye height %.1f m; unit, key tags and utility stubs inside the frame with margins; "
                                "the renderer picks the first candidate view that hides the fewest key markers" % EYE_Z,
                     "legacy_target": [x, y, _r(max(h * 0.5, e["nozzle_z"] + 1.0))],
                     "legacy_camera": [_r(x + dist * 0.3), _r(y - dist), _r(2.5 + h * 0.55)]})
    every = [p for uid in equipment for p in unit_points(uid)] + [tuple(b["position"][:2]) + (1.4,) for b in boundaries]
    ov_cam, ov_target = fit_camera(every, (-0.12, -1.0, 0.75)) if legacy_markers else fit_dir(
        every, OVERVIEW_DIRECTION, side=0.80, top=0.55, bottom=0.62)
    xs = [e["position"][0] for e in equipment.values()] + [b["position"][0] for b in boundaries]
    ys = [e["position"][1] for e in equipment.values()] + [b["position"][1] for b in boundaries]
    gcx, gcy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    gw, gd = max(xs) - min(xs) + 12, max(ys) - min(ys) + 12
    overview = {"camera": ov_cam, "target": ov_target,
                "legacy_camera": [_r(gcx - 4), _r(gcy - max(gw, gd) * 0.75), _r(max(gw, gd) * 0.55)],
                "legacy_target": [_r(gcx), _r(gcy + 1.0), 1.5]}
    tags = [m["tag"] for m in markers]
    columns = replay["columns"] if replay else {}
    rows = replay["rows"] if replay else []
    states = replay_states(tags, rows, columns, bands, alarms, samples, fault_start) if samples else []
    for m in markers:
        if not m["connected"]:
            for st in states:
                st["states"][m["tag"]] = "not_connected"
    return {
        "schema": "pid-3d-scene/0 (prototype)", "model_id": model["meta"]["model_id"], "title": model["meta"]["title"],
        "disclaimer": ("PROTOTYPE. Plan positions are the 2D seed layout scaled to metres; every size, elevation, "
                       "nozzle and pipe route is a placeholder, not plant geometry. Stream connections and "
                       "directions are checked against the simulator source (out/te_topology_check.md), not reviewed by operations. Colours come from recorded replay, not a live plant."),
        "plan_scale_m_per_px": SCALE, "equipment": list(equipment.values()), "boundaries": boundaries,
        "pipes": pipes, "utilities": utilities, "valves": valves, "markers": markers, "tour": tour, "tour_order_basis": order_basis, "overview": overview, "rack": rack,
        "replay_states": states, "state_vocabulary": list(STATES),
        "camera_lens_mm": LENS_MM, "camera_sensor_mm": SENSOR_MM, "still_resolution": list(STILL_RESOLUTION),
        "video": dict(VIDEO), "labels": label_specs(equipment, boundaries, markers, layout.get("labels", {})),
    }


VARIABLE_PRIORITY = ("pressure", "temperature", "level", "flow", "composition", "power")


def key_tags(uid, markers, alarms, bands, limit=4):
    """The 3-4 tags a stop names: tags with a published alarm first, then the unit's first connected final element,
    then instruments by measured variable. Only connected tags with a normal band qualify (numbers come from data)."""
    mine = [m for m in markers if m["unit"] == uid and m["connected"] and m["tag"] in bands]
    alarmed = sorted((m for m in mine if alarms.get(m["tag"])), key=lambda m: m["tag"])
    finals = sorted((m for m in mine if m["kind"] == "final_element" and m not in alarmed), key=lambda m: m["tag"])
    var = {m["tag"]: next((i for i, v in enumerate(VARIABLE_PRIORITY) if v in m["description"].lower() or
                           v == (m.get("variable") or "")), len(VARIABLE_PRIORITY)) for m in mine}
    insts = sorted((m for m in mine if m["kind"] == "instrument" and m not in alarmed),
                   key=lambda m: (m["tag"].startswith("AT-"), var[m["tag"]], m["tag"]))
    picked = alarmed[:2] + finals[:1]
    picked += [m for m in insts if m not in picked][:max(0, limit - len(picked))]
    return [m["tag"] for m in picked[:limit]]


def utility_stubs(model, equipment):
    """Cooling-water / steam stubs for units whose final elements name the utility. Inferred, not in the contract."""
    out = []
    for fe in model["final_elements"]:
        service = next((svc for word, svc in UTILITY_RULES if word in fe.get("description", "").lower()), None)
        e = equipment.get(fe.get("unit"))
        if not service or e is None:
            continue
        x, y, _ = e["position"]
        hx, hy, top = e["extent"]
        roles = (("supply", 1.3), ("return", 2.1)) if service == "cooling_water" else (("steam", 1.2),)
        ang = math.radians(-150)
        for k, (role, z) in enumerate(roles):
            if e["shape"] == "horizontal_exchanger":
                start = (x - hx, y + (k - 0.5) * 0.5, e["nozzle_z"] + (k - 0.5) * 0.3)
                out_pt = (start[0] - 2.4, start[1], start[2])
            else:
                off = (k - 0.5) * 0.5 if len(roles) > 1 else 0.0
                dx, dy, px, py = math.cos(ang), math.sin(ang), -math.sin(ang), math.cos(ang)
                start = (x + hx * dx + off * px, y + hx * dy + off * py, z)
                out_pt = (x + (hx + 2.4) * dx + off * px, y + (hx + 2.4) * dy + off * py, z)
            corners = [start, out_pt, (out_pt[0], out_pt[1], 0.5)]
            svc = service + ("_" + role if service == "cooling_water" else "")
            out.append({"id": "%s-%s" % (fe["tag"], role), "tag": fe["tag"], "unit": e["id"], "role": role,
                        "service": svc, "corners": [[_r(c) for c in q] for q in corners],
                        "points": fillet(corners), "post": [_r(out_pt[0]), _r(out_pt[1]), 0.0],
                        "basis": "inferred: %s is described as '%s'; the contract has no %s stream" % (
                            fe["tag"], fe["description"], service.replace("_", " "))})
    return out


def label_specs(equipment, boundaries, markers, short_labels):
    """Every label the renderer may show, with its 3D anchor. Which ones a shot shows is decided per shot."""
    specs = []
    for e in equipment.values():
        x, y, _ = e["position"]
        top = e["extent"][2]
        legacy_top = e["height"] + (3.4 if e["shape"] in ("vertical_vessel", "column") else 3.0)
        anchor = [x, y, _r(top + 0.4)]
        if e["shape"] == "compressor":
            anchor = [_r(x - .7), y, _r(.25 + e["dims"][0] * .75)]
        elif e["kind"] == "separator":
            anchor = [x, y, _r(1 + e["dims"][1] * .8)]
        specs.append({"id": "unit:" + e["id"], "kind": "unit", "body": "%s  %s" % (e["id"], e["name"]),
                      "anchor": anchor, "legacy_location": [x, y, _r(legacy_top)], "unit": e["id"]})
    for b in boundaries:
        bx, by, _ = b["position"]
        specs.append({"id": "bl:" + b["stream"], "kind": "boundary", "body": "BL %s %s" % (b["stream"], b["name"]),
                      "anchor": [bx, by, 1.05], "legacy_location": [bx, by, 1.6]})
    for m in markers:
        x, y, z = m["position"]
        legacy = m["tag"] + ("" if m["connected"] else " (no data)\nNOT CONNECTED") + ("  (?)" if m["disputed"] else "")
        specs.append({"id": "tag:" + m["tag"], "kind": "tag", "body": orientation_tour.tag_body(m, short_labels),
                      "legacy_body": legacy, "anchor": [x, y, z], "legacy_location": [x, y, _r(z + 0.22)],
                      "marker": m["tag"], "unit": m["unit"]})
    return specs


def add_emphasis(scene, emphasis):
    """Emphasis labels and rings for the units the tour flags (from data; see orientation_tour.emphasis)."""
    eq = {e["id"]: e for e in scene["equipment"]}
    rings = []
    for unit, items in sorted(emphasis.items()):
        e = eq[unit]
        x, y, _ = e["position"]
        hx, hy, top = e["extent"]
        for k, item in enumerate(items):
            radius = hy + 0.7 + 0.35 * k
            rings.append({"unit": unit, "style": item["style"], "center": [x, y, 0.12 + 0.05 * k],
                          "radius": _r(radius), "stretch_x": _r(max(1.0, (hx + 0.7) / (hy + 0.7)))})
            scene["labels"].append({"id": "emph:%s:%s" % (unit, item["style"]), "kind": "emphasis",
                                    "style": item["style"], "body": item["label"],
                                    "anchor": [_r(x - hx - 0.2), _r(y - hy - 0.2), _r(min(top, 4.0) * (0.35 + 0.25 * k))],
                                    "legacy_location": [x, y, 0.0], "unit": unit, "reason": item["reason"]})
    scene["emphasis_rings"] = rings
    return scene


def legacy_shots(scene):
    """The 429d7a7 behaviour, kept to reproduce the 'before' legibility measurement: every label always visible,
    fixed world sizes, the old cameras and captions."""
    ids = [s["id"] for s in scene["labels"] if s["kind"] != "emphasis"]
    legend = "grey: in normal band   amber: outside band   red: published alarm   black: not connected"

    def cap(head, idx):
        if scene["replay_states"]:
            st = scene["replay_states"][idx]
            when = "" if st["minutes_after_fault"] is None else " (%+d min from fault-6 start)" % st["minutes_after_fault"]
            state = "Recorded TE replay, sample %d%s.\n%s" % (st["sample"], when, legend)
        else:
            state = "No replay loaded: neutral colours only"
        return "\n".join((head, state, "PROTOTYPE: placeholder geometry, source-checked topology. Not live data."))

    ov = scene["overview"]
    shots = [{"name": "00_overview_normal", "camera": ov["legacy_camera"], "target": ov["legacy_target"],
              "state_index": 0, "visible": ids, "caption": cap("Overview: %s" % scene["title"], 0)}]
    n = len(scene["tour"])
    for i, s in enumerate(scene["tour"], 1):
        shots.append({"name": "%02d_%s_normal" % (i, s["unit"].lower()), "camera": s["legacy_camera"],
                      "target": s["legacy_target"], "state_index": 0, "visible": ids,
                      "caption": cap("Stop %d of %d (seed flow order): %s %s" % (i, n, s["unit"], s["name"]), 0)})
    if len(scene["replay_states"]) >= 3:
        shots.append({"name": "20_overview_fault_early", "camera": ov["legacy_camera"], "target": ov["legacy_target"],
                      "state_index": 1, "visible": ids, "caption": cap("Fault 6 (loss of A feed): early warning", 1)})
        shots.append({"name": "21_overview_fault_alarm", "camera": ov["legacy_camera"], "target": ov["legacy_target"],
                      "state_index": 2, "visible": ids, "caption": cap("Fault 6: reactor pressure alarm", 2)})
        r = next((s for s in scene["tour"] if s["unit"] == "R-101"), None)
        if r:
            shots.append({"name": "22_reactor_fault_alarm", "camera": r["legacy_camera"], "target": r["legacy_target"],
                          "state_index": 2, "visible": ids,
                          "caption": cap("Fault 6 at the reactor: PT-107 above its 2895 kPa published limit", 2)})
    return shots


def tour_scene(scene, model, layout, bands=None, alarms=None, replay=None, hazards=None, fault_start=160,
               label_mode="declutter", emphasis_on=True, durations=None, purposes=None, only=None):
    """Add what the renderer needs on top of the pure scene: shots (stills), the narrated timeline, emphasis.
    durations: seconds of narration per segment (measured from WAVs); None -> estimated from word count.
    only: still names to render (default: every non-optional still)."""
    scene = deepcopy(scene)
    bands, alarms, hazards = bands or {}, alarms or {}, hazards or {"kinds": {}}
    idx = {"normal": 0, "early": 1, "alarm": 2} if len(scene["replay_states"]) >= 3 else {"normal": 0, "early": 0, "alarm": 0}
    tour = orientation_tour.build_tour(scene, model, layout, bands, alarms, replay, hazards, fault_start, idx, emphasis_on,
                                       purposes)
    scene["label_layout"] = label_mode
    if label_mode == "legacy":
        scene["emphasis_rings"] = []
        scene["shots"] = legacy_shots(scene)
        scene["timeline"] = []
        scene["tour_script"] = None
        return scene
    scene["emphasis_rings"] = []   # emphasis is now a limit annotation on the tag pills, not a ring and a box
    scene["labels"] += tour["extra_labels"]
    scene["loto_mockup"] = {"status": "DESIGN MOCKUP: isolation points inferred from the TE seed model; not a lockout/"
                            "tagout procedure (a real one comes from the site's energy-control program, OSHA 1910.147, "
                            "verified P&IDs and an authorized person)", "points": tour["loto"]}
    scene["level_bands"] = level_bands(scene, bands)
    scene["purposes_source"] = (purposes or {}).get("source", "none loaded")
    shots = tour["shots"]
    scene["shots"] = [s for s in shots if s["name"] in only] if only else [s for s in shots if not s.get("optional")]
    scene["all_shot_names"] = [s["name"] for s in shots]
    segments = tour["segments"]
    estimated = durations is None
    durations = durations or [orientation_tour.estimate_seconds(s["narration"]) for s in segments]
    scene["timeline"] = orientation_tour.timeline(segments, durations)
    scene["tour_script"] = {"authorship": tour["authorship"], "voice_note": tour["voice_note"],
                            "durations": "estimated from word count (150 wpm)" if estimated else "measured from narration WAVs",
                            "stops": tour["stops"], "emphasis": tour["emphasis"], "fault_profile": tour["fault_profile"],
                            "hazard_source": hazards.get("status", "none loaded")}
    return scene


def level_bands(scene, bands):
    """A translucent band on a vessel shell at the normal-band mean of its level tag (a fraction of the placeholder
    shell height). Shown only where a stop highlights 'level'."""
    out = []
    for m in scene["markers"]:
        e = next((x for x in scene["equipment"] if x["id"] == m["unit"]), None)
        if not m["tag"].startswith("LT-") or m["tag"] not in bands or e is None or \
                e["shape"] not in ("vertical_vessel", "column"):
            continue
        frac = max(0.0, min(1.0, bands[m["tag"]]["mean"] / 100.0)) if bands[m["tag"]].get("mean") is not None else 0.5
        out.append({"unit": e["id"], "tag": m["tag"], "z": _r(0.8 + frac * e["dims"][1]), "radius": _r(e["dims"][0] / 2),
                    "basis": "normal-band mean of %s (%.1f %%) as a fraction of the placeholder shell height" % (
                        m["tag"], bands[m["tag"]].get("mean", 50.0))})
    return out


def blender_script(scene):
    payload = json.dumps(scene, indent=1, sort_keys=True)
    if '"""' in payload:
        raise ValueError("scene text cannot contain a triple quote")
    template = TEMPLATE.read_text(encoding="utf-8")
    return (template.replace("__SCENE_JSON__", payload)
            .replace("# __LABEL_LAYOUT__", label_layout.embeddable_source())
            .replace("__FONT_PATH__", LABEL_FONT.as_posix()))


def load_inputs(model_path, layout_path, bands_path, meta_path, replay_path):
    read = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    model, layout = read(model_path), read(layout_path)
    bands = read(bands_path)["bands"] if Path(bands_path).is_file() else {}
    alarms = read(meta_path).get("alarms", {}) if Path(meta_path).is_file() else {}
    replay = None
    if replay_path and Path(replay_path).is_file():
        from te_channels import channel_columns
        rows = [list(map(float, l.split())) for l in Path(replay_path).read_text().splitlines() if l.strip()]
        replay = {"rows": rows, "columns": channel_columns(model)}
    return model, layout, bands, alarms, replay


def publish(renders, dest, stills):
    """Copy the measured label boxes and save the chosen stills as JPEG (quality 90) for review."""
    from PIL import Image
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "label_boxes.json").write_bytes((renders / "label_boxes.json").read_bytes())
    for name in stills:
        Image.open(renders / (name + ".png")).convert("RGB").save(dest / (name + ".jpg"), quality=90, optimize=True)
    print("published label_boxes.json%s to %s" % ("".join(", %s.jpg" % n for n in stills), dest))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=str(ROOT / "data/te_process_model.json"))
    ap.add_argument("--layout", default=str(ROOT / "data/te_display_layout.json"))
    ap.add_argument("--bands", default=str(ROOT / "out/ignition/normal_bands.json"))
    ap.add_argument("--meta", default=str(ROOT / "out/ignition/gateway/build_meta.json"))
    ap.add_argument("--hazards", default=str(ROOT / "data/hazard_citations_prototype.json"),
                    help="curated public-incident citations (prototype heuristic); absent -> no 'Why this matters'")
    ap.add_argument("--replay", default=str(ROOT / "data/external/te-braatz/d06_te.dat"),
                    help="recorded fault-6 replay; absent -> no state colours (python scripts/fetch_te_data.py)")
    ap.add_argument("--samples", default="150,200,258", help="replay samples: normal, early warning, alarm")
    ap.add_argument("--fault-start", type=int, default=160)
    ap.add_argument("--out", default=str(ROOT / "out/3d"))
    ap.add_argument("--renders", default=str(ROOT / "out/3d/renders"), help="where Blender writes stills/video/GLB")
    ap.add_argument("--blender", help="path to blender executable; renders stills when given")
    ap.add_argument("--animation", action="store_true", help="also render the narrated orientation video (low-res)")
    ap.add_argument("--gltf", action="store_true", help="also export te_scene.glb (tag ids in node extras)")
    ap.add_argument("--voice", action="store_true", help="synthesize narration with Windows SAPI (offline) and mux "
                    "it into the video with ffmpeg if an ffmpeg executable is found")
    ap.add_argument("--label-layout", choices=("declutter", "legacy"), default="declutter",
                    help="legacy reproduces the 429d7a7 labels (all visible, fixed sizes) for before/after checks")
    ap.add_argument("--no-emphasis", action="store_true", help="no shutdown-limit / first-warning emphasis")
    ap.add_argument("--cards", default=str(ROOT / "data/te_tour_cards.json"),
                    help="the tour's cards per equipment kind: function line, highlights, inferred items")
    ap.add_argument("--purposes", default=str(ROOT / "data/te_unit_purposes.json"),
                    help="one purpose sentence per unit with its teprob.f citations (the only source of purpose text)")
    ap.add_argument("--only", help="comma-separated still names to render (default: every non-optional still)")
    ap.add_argument("--publish", help="after rendering, copy label_boxes.json here and save --publish-stills as JPEG "
                    "(the committed review stills, drafts/3d-tour/)")
    ap.add_argument("--publish-stills", default="", help="comma-separated still names to save as <name>.jpg in --publish")
    args = ap.parse_args(argv)
    model, layout, bands, alarms, replay = load_inputs(args.model, args.layout, args.bands, args.meta, args.replay)
    hazards = json.loads(Path(args.hazards).read_text(encoding="utf-8")) if Path(args.hazards).is_file() else None
    purposes = (orientation_tour.load_purposes(args.cards, args.purposes)
                if Path(args.cards).is_file() and Path(args.purposes).is_file() else None)
    only = [x.strip() for x in args.only.split(",") if x.strip()] if args.only else None
    before = deepcopy(model)
    samples = [int(s) for s in args.samples.split(",") if s.strip()] if replay else []
    scene = build_scene(model, layout, bands, alarms, replay, samples, args.fault_start,
                        legacy_markers=args.label_layout == "legacy")
    full = tour_scene(scene, model, layout, bands, alarms, replay, hazards, args.fault_start, args.label_layout,
                      not args.no_emphasis, purposes=purposes, only=only)
    assert model == before, "scene generation must not modify the model"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    renders = Path(args.renders).resolve()
    wavs = None
    if args.voice and args.label_layout != "legacy":
        try:
            wavs, durations, voice = orientation_tour.synthesize(full["timeline"], out / "narration")
            full = tour_scene(scene, model, layout, bands, alarms, replay, hazards, args.fault_start,
                              args.label_layout, not args.no_emphasis, durations, purposes=purposes, only=only)
            full["tour_script"]["voice"] = "synthetic: Windows SAPI voice '%s'" % voice
            print("narration: %d WAVs from SAPI voice %s, %.1f s of speech" % (len(wavs), voice, sum(durations)))
        except (RuntimeError, OSError) as exc:
            print("no synthetic voice (%s); timings estimated from word count" % exc)
    (out / "te_scene.json").write_text(json.dumps(full, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if full["timeline"]:
        (out / "orientation_tour.srt").write_text(orientation_tour.srt(full["timeline"]), encoding="utf-8")
        orientation_tour.write_json(out / "orientation_script.json", {
            "authorship": full["tour_script"]["authorship"], "durations": full["tour_script"]["durations"],
            "voice": full["tour_script"].get("voice", "none"),
            "segments": [{k: s[k] for k in ("id", "start", "hold", "end", "speech", "caption", "narration")}
                         for s in full["timeline"]]})
    script = out / "te_scene_blender.py"
    script.write_text(blender_script(full), encoding="utf-8")
    print("wrote %s and %s (%d equipment, %d pipes, %d tags, %d tour stops, %d replay states, %d stills, %d segments)" % (
        out / "te_scene.json", script, len(full["equipment"]), len(full["pipes"]), len(full["markers"]),
        len(full["tour"]), len(full["replay_states"]), len(full["shots"]), len(full["timeline"])))
    if not replay:
        print("no replay file: stills will show neutral tag colours only")
    if not args.blender:
        return 0
    cmd = [args.blender, "--background", "--factory-startup", "--python", str(script), "--", "--out", str(renders)]
    cmd += ["--animation"] if args.animation else []
    cmd += ["--gltf"] if args.gltf else []
    code = subprocess.run(cmd).returncode
    if not code and args.publish:
        publish(renders, Path(args.publish), [x.strip() for x in args.publish_stills.split(",") if x.strip()])
    if code or not args.animation or not full["timeline"]:
        return code
    silent = renders / "orientation_tour_silent.mp4"
    if wavs and silent.is_file():
        track = orientation_tour.concat_wavs(wavs, full["timeline"], out / "narration" / "narration_track.wav")
        done = orientation_tour.mux(silent, track, out / "orientation_tour.srt", renders / "orientation_tour.mp4")
        print(("muxed %s" % (renders / "orientation_tour.mp4")) if done else
              "no ffmpeg executable: video left silent; narration WAVs and SRT are next to the scene")
    return 0


if __name__ == "__main__":
    sys.exit(main())
