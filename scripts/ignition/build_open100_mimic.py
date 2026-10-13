"""Read-only OPEN100 process mimic: structure only, no process data.

The OPEN100 track has twelve real drawings and no historian, so these screens show what the drawings alone support:
recognizable equipment from the extracted symbol classes, the main flow paths with an arrow ONLY where a direction was
read from the drawing (scripts/flow_direction.py), the twelve sheets stitched into one plant by their off-page
connectors (scripts/open100_structure.py), and every instrument value as "not connected".

Same style rules as the TE mimic (build_mimic.py / build_hmi.py): grey and calm, colour reserved for abnormal states
(there are none without data), shapes are illustrative, no animation, unknown direction draws no arrow
(display_contract.stream_is_directed), and every value binding goes through the same tag binding and the same
"not connected" transform as the drawing screens. Built from the same components (build_hmi.label/view/tag_binding).

  OPEN100/Plant        Level 1: the plant as 12 areas in the inferred tour order, with the connections between them
  OPEN100/Area_<n>     Level 2: one sheet's equipment laid out as on the drawing, with unit-to-unit flow paths

These views are generated for review and rendered offline (scripts/render_open100_structural.py). They are NOT part
of the 23-view project that passed native acceptance, and they have not been imported into a gateway.

Model use: none at build time. Layout and icon choices are Claude's (the coding agent that wrote this file).
"""
import base64
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_hmi import (EDGE, GREY_BG, HEAD, INK, MUTED, PANEL, SHEET_VALUE_SCRIPT, W, label, script_transform,  # noqa: E402
                       tag_binding, view)
from display_contract import stream_is_directed  # noqa: E402

LINE, ARROW = "#717b85", "#4b5563"
MODE = "OPEN100 DRAWINGS  /  STRUCTURE ONLY  /  NO PROCESS DATA  /  READ ONLY"
CAVEAT = ("Built from 12 public drawings and nothing else. Shapes are illustrative; equipment and connections are "
          "extracted and UNVERIFIED. An arrow means a flow direction was read from the drawing (arrowhead, off-page "
          "flag or pump ports); a dashed grey line means connected, direction not shown on the drawing.")


def uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def icon_kind(e):
    """Shape from the extracted class, refined by the tag code where the tag says what it is."""
    t = e["purpose"]["text"].lower() if e["purpose"]["source"] in ("equipment_schedule", "tag_code",
                                                                    "drawing_label") else ""
    if e["class"] == "pump":
        return "pump"
    if any(w in t for w in ("exchanger", "heater", "cooler", "condenser")):
        return "exchanger"
    if "reactor" in t or "steam generator" in t or "pressurizer" in t:
        return "tall_vessel"
    if e["class"] == "tank":
        return "vessel"
    return "box"


def icon_svg(kind, x, y, s):
    """One equipment shape centred at (x, y), size s, in the shared stroke style."""
    st = 'fill="#eef0f1" stroke="#4b5563" stroke-width="2"'
    h = s / 2
    if kind == "pump":
        return ('<circle cx="%.1f" cy="%.1f" r="%.1f" %s/><path d="M%.1f %.1f L%.1f %.1f L%.1f %.1f Z" fill="#c4cbd0" '
                'stroke="#4b5563" stroke-width="1.5"/>' % (x, y, h * 0.8, st, x - h * 0.45, y - h * 0.45, x + h * 0.6,
                                                           y, x - h * 0.45, y + h * 0.45))
    if kind == "exchanger":
        return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" %s/><path d="M%.1f %.1f L%.1f %.1f L%.1f '
                '%.1f L%.1f %.1f" fill="none" stroke="#66717c" stroke-width="1.5"/>'
                % (x - h, y - h * 0.45, s, h * 0.9, h * 0.45, st, x - h * 0.7, y,
                   x - h * 0.25, y - h * 0.3, x + h * 0.2, y + h * 0.3, x + h * 0.7, y))
    if kind == "tall_vessel":
        return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" %s/>' % (x - h * 0.45, y - h, s * 0.45, s,
                                                                                     h * 0.4, st)
    if kind == "vessel":
        return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" %s/>' % (x - h * 0.6, y - h * 0.8, s * 0.6,
                                                                                     s * 0.8, h * 0.35, st)
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" %s stroke-dasharray="4 3"/>' % (
        x - h * 0.6, y - h * 0.6, s * 0.6, s * 0.6, st)


def marker_defs():
    return ('<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
            '<path d="M0 0 L9 4.5 L0 9 Z" fill="%s"/></marker></defs>' % ARROW)


def flow_line(a, b, directed, width=2):
    """Straight line a->b. Directed: solid, arrowhead at the middle. Otherwise dashed grey, no arrowhead."""
    (x0, y0), (x1, y1) = a, b
    if directed:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return ('<path d="M%.1f %.1f L%.1f %.1f" stroke="%s" stroke-width="%s" fill="none" marker-end="url(#arrow)"/>'
                '<path d="M%.1f %.1f L%.1f %.1f" stroke="%s" stroke-width="%s" fill="none"/>'
                % (x0, y0, mx, my, ARROW, width, mx, my, x1, y1, ARROW, width))
    return '<path d="M%.1f %.1f L%.1f %.1f" stroke="%s" stroke-width="%s" fill="none" stroke-dasharray="6 5"/>' % (
        x0, y0, x1, y1, LINE, width)


def header(title, active, areas):
    kids = [label("HeaderBar", 0, 0, W, HEAD, "", {"backgroundColor": "#d4d4d4", "borderBottom": f"1px solid {EDGE}"}),
            label("Title", 16, 8, 520, 20, title, {"fontSize": 16, "fontWeight": "bold"}),
            label("Subtitle", 16, 30, 520, 18, "OPEN100 drawings · structure only · no process data · read-only",
                  {"fontSize": 11, "color": MUTED})]
    x = 560
    for text, page in [("Plant", "/open100/plant")] + [("S" + a["sheet"], "/open100/area/" + a["sheet"])
                                                        for a in areas] + [("Drawings", "/drawings")]:
        w = 8 * len(text) + 18
        on = page == active
        kids.append(label("Nav_" + text, x, 14, w, 28, text, {
            "textAlign": "center", "borderRadius": 3, "fontWeight": "bold" if on else "normal",
            "backgroundColor": "#ffffff" if on else "transparent", "borderStyle": "solid", "borderWidth": 1,
            "borderColor": EDGE if on else "transparent"}, page=page))
        x += w + 3
    return kids


def value_label(name, x, y, w, path, tooltip):
    """The same binding and transform as the drawing screens: a Good number shows; anything else says so."""
    c = label(name, x, y, w, 16, "not connected", {"fontSize": 10, "fontStyle": "italic", "color": MUTED,
                                                   "whiteSpace": "nowrap", "backgroundColor": "#ffffff",
                                                   "borderStyle": "solid", "borderWidth": 1, "borderColor": EDGE,
                                                   "paddingLeft": 2}, tooltip=tooltip)
    if path:
        c["propConfig"] = {"props.text": tag_binding(path + "/PV", [script_transform(SHEET_VALUE_SCRIPT %
                                                                                     "not connected")])}
    return c


def directed_pair(link):
    """Unit link -> (from, to) display record for the shared direction contract."""
    if link["direction"] == "a_to_b":
        return {"from": link["a"], "to": link["b"], "direction": "forward"}
    if link["direction"] == "b_to_a":
        return {"from": link["b"], "to": link["a"], "direction": "forward"}
    return {"from": link["a"], "to": link["b"], "direction": "unknown"}


def edge_point(box, toward):
    """Where the segment from the box centre toward `toward` leaves the box."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    dx, dy = toward[0] - cx, toward[1] - cy
    t = min((w / 2) / abs(dx) if dx else 1e9, (h / 2) / abs(dy) if dy else 1e9)
    return cx + dx * t, cy + dy * t


def plant_view(structure, inst_paths):
    areas = {a["sheet"]: a for a in structure["areas"]}
    order = structure["tour_order"]
    eq = {e["id"]: e for e in structure["equipment"]}
    kids = header("OPEN100 plant overview (stitched from 12 drawings)", "/open100/plant", [areas[s] for s in order])
    kids += [label("Mode", 24, 66, 1550, 22, MODE, {"fontWeight": "bold", "fontSize": 15}),
             label("Caveat", 24, 92, 1550, 36, CAVEAT, {"fontSize": 12})]
    cols, pw, ph, gx, gy, top = 4, 340, 206, 64, 44, 142
    pos = {}
    for k, s in enumerate(order):
        r, c = divmod(k, cols)
        c = c if r % 2 == 0 else cols - 1 - c   # serpentine, so consecutive stops sit side by side
        pos[s] = (24 + c * (pw + gx), top + r * (ph + gy))
    pairs = {}
    for e in structure["area_links"]:
        key = tuple(sorted((e["a"], e["b"]), key=int))
        p = pairs.setdefault(key, {"fwd": 0, "rev": 0, "und": 0})
        if e["direction"] in ("a_to_b", "b_to_a"):
            frm = e["a"] if e["direction"] == "a_to_b" else e["b"]
            p["fwd" if frm == key[0] else "rev"] += 1
        else:
            p["und"] += 1
    flows = defaultdict(lambda: {"in": set(), "out": set(), "und": set()})
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">', marker_defs()]
    for (a, b), p in sorted(pairs.items()):
        ba, bb = pos[a] + (pw, ph), pos[b] + (pw, ph)
        ca, cb = (ba[0] + pw / 2, ba[1] + ph / 2), (bb[0] + pw / 2, bb[1] + ph / 2)
        n = (cb[1] - ca[1], ca[0] - cb[0])
        L = max(1.0, (n[0] ** 2 + n[1] ** 2) ** 0.5)
        n = (n[0] / L * 7, n[1] / L * 7)
        for d, sign in (("fwd", 1), ("rev", -1)):
            if not p[d]:
                continue
            frm, to = (a, b) if d == "fwd" else (b, a)
            flows[frm]["out"].add(to)
            flows[to]["in"].add(frm)
            off = (n[0] * sign, n[1] * sign) if p["fwd"] and p["rev"] else (0, 0)
            src = edge_point(pos[frm] + (pw, ph), cb if frm == a else ca)
            dst = edge_point(pos[to] + (pw, ph), ca if frm == a else cb)
            svg.append('<path d="M%.1f %.1f L%.1f %.1f" stroke="%s" stroke-width="3" fill="none" '
                       'marker-end="url(#arrow)"/>' % (src[0] + off[0], src[1] + off[1], dst[0] + off[0],
                                                       dst[1] + off[1], ARROW))
        if not p["fwd"] and not p["rev"]:
            flows[a]["und"].add(b)
            flows[b]["und"].add(a)
            svg.append(flow_line(edge_point(ba, cb), edge_point(bb, ca), False, 2))
    svg.append("</svg>")
    kids.append({"type": "ia.display.image", "meta": {"name": "AreaConnections"},
                 "position": {"x": 0, "y": 0, "width": 1600, "height": 900},
                 "props": {"source": uri("".join(svg)), "fit": {"mode": "fill"}, "style": {"pointerEvents": "none"}}})
    for k, s in enumerate(order):
        a = areas[s]
        x, y = pos[s]
        mine = [eq[i] for i in a["equipment"]]
        named = [e for e in mine if e["tag"]]
        kids.append(label("Panel_" + s, x, y, pw, ph, "", {"backgroundColor": PANEL, "borderStyle": "solid",
                                                           "borderWidth": 1, "borderColor": EDGE, "borderRadius": 4}))
        title = a["label"] if a["name"] else "unnamed sheet (%s tags)" % (a["system_code"] or "?")
        kids.append(label("AreaTitle_" + s, x + 8, y + 5, pw - 16, 20, "%d. Sheet %s · %s" % (k + 1, s, title),
                          {"fontSize": 13, "fontWeight": "bold", "whiteSpace": "nowrap"}, page="/open100/area/" + s,
                          tooltip="Name from %s" % a["name_source"].replace("_", " ")))
        icons = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d 84">' % (pw - 16)]
        shown = (named or mine)[:4]
        for j, e in enumerate(shown):
            cx = 40 + j * 82
            icons.append(icon_svg(icon_kind(e), cx, 30, 44))
            icons.append('<text x="%.1f" y="76" text-anchor="middle" font-family="Arial" font-size="10" '
                         'fill="%s">%s</text>' % (cx, INK, html.escape((e["tag"] or "untagged")[:13])))
        icons.append("</svg>")
        kids.append({"type": "ia.display.image", "meta": {"name": "Equipment_" + s},
                     "position": {"x": x + 8, "y": y + 27, "width": pw - 16, "height": 84},
                     "props": {"source": uri("".join(icons)), "fit": {"mode": "contain"}, "style": {"cursor": "pointer"}},
                     "events": {"dom": {"onClick": {"type": "nav", "scope": "C",
                                                    "config": {"page": "/open100/area/" + s}}}}})
        more = len(mine) - len(shown)
        kids.append(label("AreaCounts_" + s, x + 8, y + 112, pw - 16, 16,
                          "%d equipment%s · %d instruments" % (len(mine), (" (+%d not shown)" % more) if more else "",
                                                              a["instruments"]), {"fontSize": 11, "color": MUTED}))
        f = flows[s]
        fmt = lambda xs: ", ".join("S" + t for t in sorted(xs, key=int)) or "none"  # noqa: E731
        kids.append(label("AreaFlows_" + s, x + 8, y + 129, pw - 16, 30,
                          "In from: %s · Out to: %s%s" % (fmt(f["in"]), fmt(f["out"]),
                                                          (" · direction not shown: %s" % fmt(f["und"])) if f["und"]
                                                          else ""), {"fontSize": 11}))
        insts = [i for i in inst_paths if i["sheet"] == s][:2]
        for j, i in enumerate(insts):
            kids.append(label("InstTag_%s_%d" % (s, j), x + 8 + j * 165, y + 166, 70, 18, i["tag"],
                              {"fontSize": 11, "fontWeight": "bold", "whiteSpace": "nowrap"}))
            kids.append(value_label("Value_%s_%d" % (s, j), x + 78 + j * 165, y + 167, 82, i["path"],
                                    "%s: extracted from sheet %s; no data point mapped" % (i["tag"], s)))
    kids.append(label("Legend", 24, 852, 1550, 34,
                      "Arrow = flow between two areas read from off-page connector flags. Dashed = the drawings connect "
                      "the areas but don't show the direction. 1-12 = inferred tour order: %s." %
                      structure["tour_order_basis"].split(";")[0], {"fontSize": 12}))
    kids.append(label("Scope", 24, 888, 1550, 20, "Offline structural prototype, not imported into a gateway. Values "
                      "need an I/O list or historian mapping; without one every value reads 'not connected'.",
                      {"fontSize": 11, "color": MUTED}))
    return view(915, kids)


def spread(pos, keys, min_d=118, bounds=(40, 20, 1560, 700)):
    """Nudge overlapping icons apart (drawing positions crowd), deterministic, keeping the drawing's arrangement."""
    p = {k: list(pos[k]) for k in keys}
    for _ in range(60):
        moved = False
        ks = sorted(p)
        for i, a in enumerate(ks):
            for b in ks[i + 1:]:
                dx, dy = p[b][0] - p[a][0], p[b][1] - p[a][1]
                d = (dx * dx + dy * dy) ** 0.5
                if d < min_d:
                    if d < 1e-6:
                        dx, dy, d = 1.0, 0.0, 1.0
                    push = (min_d - d) / 2 + 0.5
                    p[a][0] -= dx / d * push; p[a][1] -= dy / d * push
                    p[b][0] += dx / d * push; p[b][1] += dy / d * push
                    moved = True
        for k in p:
            p[k][0] = min(max(p[k][0], bounds[0]), bounds[2])
            p[k][1] = min(max(p[k][1], bounds[1]), bounds[3])
        if not moved:
            break
    return {k: tuple(v) for k, v in p.items()}


def display_links(links, pos):
    """One line per nearest connection: a spanning forest over the extracted equipment-to-equipment paths (shortest
    on screen first, directed paths preferred at equal length). The full set stays in plant_structure.json; the
    screen says how many paths it simplified away."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def length(l):
        (x0, y0), (x1, y1) = pos[l["a"]], pos[l["b"]]
        return ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5 * (0.85 if l["direction"] in ("a_to_b", "b_to_a") else 1.0)
    keep = []
    for l in sorted(links, key=lambda l: (length(l), l["a"], l["b"])):
        ra, rb = find(l["a"]), find(l["b"])
        if ra != rb:
            parent[ra] = rb
            keep.append(l)
    return keep


def area_view(structure, sheet, inst_paths, dirs):
    areas = {a["sheet"]: a for a in structure["areas"]}
    a = areas[sheet]
    eq = {e["id"]: e for e in structure["equipment"] if e["sheet"] == sheet}
    kids = header("Area · sheet %s · %s" % (sheet, a["label"]), "/open100/area/" + sheet,
                  [areas[s] for s in structure["tour_order"]])
    kids += [label("Mode", 24, 66, 1550, 22, MODE, {"fontWeight": "bold", "fontSize": 15}),
             label("Caveat", 24, 92, 1550, 36, CAVEAT, {"fontSize": 12}),
             label("Purpose", 24, 132, 1550, 20, a["purpose"]["text"] + "  [source: %s]" %
                   a["purpose"]["source"].replace("_", " "), {"fontSize": 12, "color": MUTED})]
    X0, Y0, CW, CH = 60, 30, 1480, 560

    def at(box):
        return X0 + (box[0] + box[2]) / 2000 * CW, Y0 + (box[1] + box[3]) / 2000 * CH
    raw = {i: at(e["box_0_1000"]) for i, e in eq.items()}
    conns = {c["connector"]: c for c in structure["external_connectors"] + structure["connectors_stitched"]
             if c["sheet"] == sheet}
    for cid, c in conns.items():
        raw[cid] = at(c["box_0_1000"])
    pos = spread(raw, list(raw))
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 800">', marker_defs()]
    links = [l for l in structure["unit_links"] if l["sheet"] == sheet and l["a"] in pos and l["b"] in pos]
    counts = {"directed": 0, "undirected": 0, "conflict": 0}
    for l in links:
        counts["directed" if l["direction"] in ("a_to_b", "b_to_a") else l["direction"]] += 1
    shown = display_links(links, pos)
    for l in shown:
        d = directed_pair(l)
        directed = stream_is_directed(d)
        svg.append(flow_line(pos[d["from"]], pos[d["to"]], directed, 2.5 if directed else 1.5))
    for i, e in eq.items():
        x, y = pos[i]
        svg.append(icon_svg(icon_kind(e), x, y, 54))
        svg.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="Arial" font-size="12" font-weight="bold" '
                   'fill="%s">%s</text>' % (x, y + 42, INK, html.escape(e["tag"] or "untagged " + e["class"])))
    for cid, c in conns.items():
        x, y = pos[cid]
        pts = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (x - 30, y - 9, x + 18, y - 9, x + 30, y, x + 18,
                                                                       y + 9, x - 30, y + 9)
        svg.append('<polygon points="%s" fill="#ffffff" stroke="#4b5563" stroke-width="1.5"/>' % pts)
        tag = {"in": "IN", "out": "OUT"}.get(c.get("direction"), "?")
        svg.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="Arial" font-size="9" fill="%s">%s</text>'
                   % (x - 4, y + 3, INK, tag))
        ref = c.get("refers_to_drawing")
        if ref:
            svg.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="Arial" font-size="9" fill="%s">'
                       'PID %s</text>' % (x, y + 21, MUTED, html.escape(ref)))
    svg.append("</svg>")
    kids.append({"type": "ia.display.image", "meta": {"name": "AreaMimic_" + sheet},
                 "position": {"x": 0, "y": 160, "width": 1600, "height": 800},
                 "props": {"source": uri("".join(svg)), "fit": {"mode": "fill"}, "style": {"pointerEvents": "none"}}})
    # instrument values next to their equipment: same binding as the drawing screens, all "not connected"
    placed = []
    for i in inst_paths:
        if i["sheet"] != sheet or i["unit"] not in pos:
            continue
        k = sum(1 for p in placed if p == i["unit"])
        if k >= 2:
            continue
        placed.append(i["unit"])
        x, y = pos[i["unit"]]
        yy = 160 + y + 50 + k * 18
        kids.append(label("InstTag_" + i["id"], x - 95, yy, 70, 16, i["tag"], {"fontSize": 10, "fontWeight": "bold",
                                                                              "whiteSpace": "nowrap",
                                                                              "textAlign": "right"}))
        kids.append(value_label("Value_" + i["id"], x - 22, yy, 92, i["path"],
                                "%s on %s: extracted; no data point mapped" % (i["tag"], i["unit"])))
    kids.append(label("AreaLegend", 24, 975, 1550, 34,
                      "%d equipment-to-equipment paths extracted on this sheet: %d with a direction read from the drawing, "
                      "%d without, %d where the evidence disagrees. Drawn: the %d nearest connections that join "
                      "everything up (arrow = direction read; dashed = not). Flags: IN / OUT = flow crosses the sheet "
                      "edge, read from the flag's point; ? = not read." % (len(links), counts["directed"],
                                                                          counts["undirected"], counts["conflict"],
                                                                          len(shown)),
                      {"fontSize": 12}))
    kids.append(label("Scope", 24, 1012, 1550, 20, "Layout follows the drawing's own positions (not plant geometry). "
                      "Offline structural prototype, not imported into a gateway.", {"fontSize": 11, "color": MUTED}))
    return view(1040, kids)


def instrument_paths(model, provider_doc, provider):
    """Instrument asset id -> tag path in the existing OPEN100 provider (the same tags the drawing screens bind)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_views import asset_paths
    paths = asset_paths(provider_doc, provider)
    out = []
    for i in model["instruments"]:
        if not i.get("tag"):
            continue
        out.append({"id": i["id"], "tag": i["tag"], "unit": i.get("unit"), "sheet": i["provenance"][0]["sheet"],
                    "path": paths.get(i["id"])})
    return out


def views(structure, model, provider_doc, provider, dirs):
    inst = instrument_paths(model, provider_doc, provider)
    out = {"OPEN100/Plant": plant_view(structure, inst)}
    for a in structure["areas"]:
        out["OPEN100/Area_" + a["sheet"]] = area_view(structure, a["sheet"], inst, dirs)
    return out
