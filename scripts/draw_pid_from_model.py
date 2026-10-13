"""Process model -> P&ID sheets in the OPEN100 house style (PNG + SVG), plus answer keys emitted from the same model.

Why this exists: a plant without usable drawings can still start. It has process knowledge (an instrument index, a
historian tag list, a simulator), so it can GENERATE drawings in its own house style from that knowledge, then put
them through the same extraction, review and export path as scanned sheets. Here the house style is the one the
project learned from the 12 OPEN100 sheets and their PID2Graph answer keys: ISA-5.1 bubbles with the letters over
the loop number, bow-tie control valves with a dome actuator and their own tag bubble, pentagon off-page flags with
a drawing reference and grid zone, heavy process lines with filled flow arrows, placeholder line numbers, a zoned
border, an equipment legend and a title block. Sizes come from the OPEN100 keys (scripts/style_fidelity.py checks
them).

What is drawn comes ONLY from the model (data/te_process_model.json): units, streams, every instrument and final
element, which unit owns each item and which stream it sits on. WHERE it is drawn comes from a drafting layout
(data/te_pid_layout.json). The generator refuses to draw if the layout drops a model item, draws one twice, or
names a tag the model doesn't have. Lines the model has no stream for (cooling water, steam, the compressor recycle
bypass) are drafting additions and are marked so in the key.

A generated drawing is NOT a drawing of record. It shows what the model says, not what is in the field, until
engineering walks it down and accepts it under management of change.

No AI is used anywhere here. Deterministic: the same model + layout give the same key; PNG bytes can differ between
Pillow versions (font rasterizing), so the manifest records the Pillow version.

Outputs (data/te_pid/):
  <sheet>.png        the rendered sheet (3200 x 2130 px): what the extraction pipeline reads
  <sheet>.svg        the same primitives as vector graphics
  <sheet>.graphml    answer key in the PID2Graph schema, so the frozen scorer reads it unchanged; extra node
                     attributes `text` (what is printed in/at the symbol) and `model_ref` (the model item it draws)
  key.json           every symbol with its printed text, model reference and drafting flag; every link
  manifest.json      sha256 of the model, layout, generator and each output
  ../sheet_registers/te_generated.csv   the drawing register (sheet, drawing number, system), as a plant supplies

Usage: python scripts/draw_pid_from_model.py [--model data/te_process_model.json] [--layout data/te_pid_layout.json]
                                             [--out data/te_pid] [--check]   (--check: validate only, write nothing)
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- house style (px on a 3200 px wide sheet)
# Measured on the OPEN100 sheets / keys (scripts/style_fidelity.py): instrument bubbles ~0.0154 of sheet width,
# off-page flags ~0.0715 x 0.0157, valves ~0.008, process lines 4-6 px and thin lines 1-2 px at ~3200 px.
PROCESS_W = 5
THIN_W = 2
EQUIP_W = 3
BUBBLE_R = 25
FLAG_W, FLAG_H, FLAG_TIP = 230, 50, 26
VALVE_HALF, VALVE_H = 13, 9
ACT_STEM, ACT_R = 16, 10
TAP_OFFSET = 80
TEXT = 15          # bubble and flag text
SMALL = 13
EQ_TEXT = 26       # equipment tag
ARROW_L, ARROW_W = 18, 12
FRAME = (70, 70, 3130, 2060)
COLS, ROWS = 12, 8


# ---------------------------------------------------------------- canvas: one call draws PNG and SVG

class Canvas:
    def __init__(self, w, h):
        from PIL import Image, ImageDraw, ImageFont
        self.w, self.h = w, h
        self.img = Image.new("L", (w, h), 255)
        self.d = ImageDraw.Draw(self.img)
        self._font = lambda size: ImageFont.load_default(size=size)
        self.svg = []

    def line(self, pts, width, dash=None):
        pts = [tuple(map(float, p)) for p in pts]
        if dash:
            for a, b in zip(pts, pts[1:]):
                L = math.dist(a, b)
                n = int(L // sum(dash))
                for k in range(n + 1):
                    s, e = k * sum(dash), min(L, k * sum(dash) + dash[0])
                    if s >= L:
                        break
                    p = (a[0] + (b[0] - a[0]) * s / L, a[1] + (b[1] - a[1]) * s / L)
                    q = (a[0] + (b[0] - a[0]) * e / L, a[1] + (b[1] - a[1]) * e / L)
                    self.d.line([p, q], fill=0, width=width)
        else:
            self.d.line(pts, fill=0, width=width, joint="curve" if len(pts) > 2 else None)
        attr = f' stroke-dasharray="{dash[0]} {dash[1]}"' if dash else ""
        self.svg.append(f'<polyline points="{" ".join(f"{x:g},{y:g}" for x, y in pts)}" fill="none" '
                        f'stroke="#000" stroke-width="{width}"{attr}/>')

    def polygon(self, pts, width, fill=None):
        pts = [tuple(map(float, p)) for p in pts]
        self.d.polygon(pts, fill={"black": 0, "white": 255}.get(fill), outline=0, width=width)
        f = {"black": "#000", "white": "#fff"}.get(fill, "none")
        self.svg.append(f'<polygon points="{" ".join(f"{x:g},{y:g}" for x, y in pts)}" fill="{f}" stroke="#000" '
                        f'stroke-width="{width}"/>')

    def rect(self, box, width, fill=None):
        x0, y0, x1, y1 = box
        if fill == "white" and width == 0:
            self.d.rectangle(box, fill=255)
            self.svg.append(f'<rect x="{x0:g}" y="{y0:g}" width="{x1 - x0:g}" height="{y1 - y0:g}" fill="#fff"/>')
            return
        self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], width, fill)

    def circle(self, cx, cy, r, width, fill="white"):
        self.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255 if fill == "white" else None, outline=0, width=width)
        f = "#fff" if fill == "white" else "none"
        self.svg.append(f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{f}" stroke="#000" stroke-width="{width}"/>')

    def arc(self, box, start, end, width):
        """Elliptic arc, PIL convention (degrees clockwise from 3 o'clock)."""
        self.d.arc(box, start, end, fill=0, width=width)
        x0, y0, x1, y1 = box
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        p = lambda a: (cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))  # noqa: E731
        (sx, sy), (ex, ey) = p(start), p(end)
        large = 1 if (end - start) % 360 > 180 else 0
        self.svg.append(f'<path d="M{sx:.1f} {sy:.1f} A{rx:g} {ry:g} 0 {large} 1 {ex:.1f} {ey:.1f}" fill="none" '
                        f'stroke="#000" stroke-width="{width}"/>')

    def text(self, x, y, s, size, underline=False, background=False, anchor="mm"):
        font = self._font(size)
        x0, y0, x1, y1 = self.d.textbbox((x, y), s, font=font, anchor=anchor)
        if background:
            self.rect((x0 - 4, y0 - 3, x1 + 4, y1 + 3), 0, "white")
        self.d.text((x, y), s, fill=0, font=font, anchor=anchor)
        ta = {"m": "middle", "l": "start", "r": "end"}[anchor[0]]
        self.svg.append(f'<text x="{x:g}" y="{y:g}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
                        f'text-anchor="{ta}" dominant-baseline="central">{escape(s)}</text>')
        if underline:
            self.line([(x0, y1 + 3), (x1, y1 + 3)], 1)
        return (x0, y0, x1, y1)

    def write(self, png, svg):
        self.img.save(png, optimize=True)
        svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                       f'viewBox="0 0 {self.w} {self.h}"><rect width="100%" height="100%" fill="#fff"/>'
                       + "".join(self.svg) + "</svg>\n", encoding="utf-8")


# ---------------------------------------------------------------- geometry helpers

def seg_dir(a, b):
    return "h" if abs(a[1] - b[1]) < 1e-6 else "v" if abs(a[0] - b[0]) < 1e-6 else None


def locate(pts, p, tol=2.0):
    """Arclength position of point p on polyline pts, and the segment's orientation; None if p is off the line."""
    t = 0.0
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        ax, ay, bx, by = *a, *b
        if L and min(ax, bx) - tol <= p[0] <= max(ax, bx) + tol and min(ay, by) - tol <= p[1] <= max(ay, by) + tol:
            cross = abs((bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)) / L
            if cross <= tol:
                return t + math.dist(a, p), seg_dir(a, b), (a, b)
        t += L
    return None


def point_at(pts, t):
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if t <= L:
            return (a[0] + (b[0] - a[0]) * t / L, a[1] + (b[1] - a[1]) * t / L), seg_dir(a, b), (a, b)
        t -= L
    return tuple(pts[-1]), seg_dir(pts[-2], pts[-1]), (pts[-2], pts[-1])


def length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def zone(x, y):
    fx0, fy0, fx1, fy1 = FRAME
    col = COLS - min(COLS - 1, max(0, int((x - fx0) / ((fx1 - fx0) / COLS))))
    row = "HGFEDCBA"[min(ROWS - 1, max(0, int((y - fy0) / ((fy1 - fy0) / ROWS))))]
    return f"{row}-{col}"


def split_tag(tag):
    letters, _, num = tag.partition("-")
    return letters, num


# ---------------------------------------------------------------- the drawing

class Sheet:
    def __init__(self, spec, model, layout, register):
        self.spec, self.model, self.layout, self.register = spec, model, layout, register
        self.w, self.h = layout["sheet_px"]
        self.c = Canvas(self.w, self.h)
        self.nodes = {}           # id -> {class, box, text, model_ref, drafting}
        self.counts = {}
        self.edges = set()
        self.unit_geo = {}

    # -- key bookkeeping
    def node(self, cls, box, text=None, model_ref=None, drafting=False, kind=None):
        self.counts[cls] = self.counts.get(cls, 0) + 1
        nid = f"{cls.replace('/', '_')}{self.counts[cls]}"
        self.nodes[nid] = {"class": cls, "box": [round(v, 1) for v in box], "text": text, "model_ref": model_ref,
                           "model_kind": kind, "drafting_addition": drafting}
        return nid

    def link_group(self, members, at):
        """One line network: a connector node joined to every member symbol (the PID2Graph key convention)."""
        members = [m for m in dict.fromkeys(members) if m]
        if len(members) < 2:
            return
        cid = self.node("connector", (at[0] - 4, at[1] - 4, at[0] + 4, at[1] + 4))
        for m in members:
            self.edges.add((cid, m))

    # -- symbols
    def bubble(self, cx, cy, tag, kind):
        letters, num = split_tag(tag)
        self.c.circle(cx, cy, BUBBLE_R, THIN_W)
        self.c.text(cx, cy - 9, letters, TEXT)
        self.c.text(cx, cy + 9, num, TEXT)
        return self.node("instrumentation", (cx - BUBBLE_R, cy - BUBBLE_R, cx + BUBBLE_R, cy + BUBBLE_R),
                         f"{letters} {num}", tag, kind=kind)

    def valve(self, p, orient, tag, side, drafting):
        x, y = p
        s = -1 if side in ("down", "right") else 1
        if orient == "h":
            self.c.polygon([(x - VALVE_HALF, y - VALVE_H), (x, y), (x - VALVE_HALF, y + VALVE_H)], THIN_W, "white")
            self.c.polygon([(x + VALVE_HALF, y - VALVE_H), (x, y), (x + VALVE_HALF, y + VALVE_H)], THIN_W, "white")
            top = y - s * ACT_STEM
            self.c.line([(x, y), (x, top)], THIN_W)
            box = (x - ACT_R, top - ACT_R, x + ACT_R, top + ACT_R)
            self.c.arc(box, 180, 360, THIN_W) if s == 1 else self.c.arc(box, 0, 180, THIN_W)
            self.c.line([(x - ACT_R, top), (x + ACT_R, top)], THIN_W)
            vbox = (x - VALVE_HALF, min(y - VALVE_H, top - s * ACT_R), x + VALVE_HALF, max(y + VALVE_H, top - s * ACT_R))
            far = top - s * ACT_R
            bc = (x, y - s * TAP_OFFSET)
            lead = [(x, far), (x, bc[1] + s * BUBBLE_R)]
        else:
            self.c.polygon([(x - VALVE_H, y - VALVE_HALF), (x, y), (x + VALVE_H, y - VALVE_HALF)], THIN_W, "white")
            self.c.polygon([(x - VALVE_H, y + VALVE_HALF), (x, y), (x + VALVE_H, y + VALVE_HALF)], THIN_W, "white")
            left = x - s * ACT_STEM
            self.c.line([(x, y), (left, y)], THIN_W)
            box = (left - ACT_R, y - ACT_R, left + ACT_R, y + ACT_R)
            self.c.arc(box, 90, 270, THIN_W) if s == 1 else self.c.arc(box, 270, 450, THIN_W)
            self.c.line([(left, y - ACT_R), (left, y + ACT_R)], THIN_W)
            far = left - s * ACT_R
            vbox = (min(x - VALVE_H, far), y - VALVE_HALF, max(x + VALVE_H, far), y + VALVE_HALF)
            bc = (x - s * TAP_OFFSET, y)
            lead = [(far, y), (bc[0] + s * BUBBLE_R, y)]
        vid = self.node("valve", vbox, None, tag, drafting, kind="final_element")
        self.c.line(lead, THIN_W)
        bid = self.bubble(*bc, tag, "final_element")
        self.link_group([vid, bid], lead[0])
        return vid

    def tap(self, p, orient, tag, side):
        x, y = p
        s = -1 if side in ("down", "right") else 1
        bc = (x, y - s * TAP_OFFSET) if orient == "h" else (x - s * TAP_OFFSET, y)
        edge = (x, bc[1] + s * BUBBLE_R) if orient == "h" else (bc[0] + s * BUBBLE_R, y)
        self.c.line([p, edge], THIN_W)
        return self.bubble(*bc, tag, "instrument")

    def flag(self, fid, f):
        x, y = f["at"]
        y0, y1 = y - FLAG_H / 2, y + FLAG_H / 2
        if f["dir"] == "right":
            pts = [(x, y0), (x + FLAG_W - FLAG_TIP, y0), (x + FLAG_W, y), (x + FLAG_W - FLAG_TIP, y1), (x, y1)]
            tx = x + (FLAG_W - FLAG_TIP) / 2
        else:
            pts = [(x + FLAG_TIP, y0), (x + FLAG_W, y0), (x + FLAG_W, y1), (x + FLAG_TIP, y1), (x, y)]
            tx = x + FLAG_TIP + (FLAG_W - FLAG_TIP) / 2
        self.c.polygon(pts, THIN_W, "white")
        lines = self.flag_text(f)
        self.c.text(tx, y - 11, lines[0], SMALL)
        self.c.text(tx, y + 11, lines[1], SMALL)
        stream = f.get("stream")
        return self.node("inlet/outlet", (x, y0, x + FLAG_W, y1), " / ".join(lines),
                         f"stream:{stream}" if stream else None, drafting=not stream,
                         kind="stream_end" if stream else "utility")

    def flag_text(self, f):
        if f.get("utility"):
            return f["utility"]
        s = next(s for s in self.model["streams"] if s["id"] == f["stream"])
        here = self.spec["id"]
        partner = [(sh, fl) for sh in self.layout["sheets"] if sh["id"] != here
                   for fl in sh["flags"].values() if fl.get("stream") == f["stream"]]
        if partner:
            sh, fl = partner[0]
            # The zone points at where the line continues on the other sheet (OPEN100 convention).
            zx = fl["at"][0] + (FLAG_W if fl["dir"] == "right" and fl["at"][0] < self.w / 2 else 0)
            return [f"{sh['system']} PID {sh['drawing']} ({zone(zx, fl['at'][1])})", s["name"].upper()]
        return ["BATTERY LIMIT", s["name"].upper()]

    def unit(self, uid, u):
        name = next(x for x in self.model["units"] if x["id"] == uid)["name"]
        c = self.c
        if u["shape"] in ("vertical_vessel", "column"):
            cx, top, bot, w, hd = u["cx"], u["top"], u["bottom"], u["w"], u["head"]
            x0, x1 = cx - w / 2, cx + w / 2
            c.line([(x0, top + hd), (x0, bot - hd)], EQUIP_W)
            c.line([(x1, top + hd), (x1, bot - hd)], EQUIP_W)
            c.arc((x0, top, x1, top + 2 * hd), 180, 360, EQUIP_W)
            c.arc((x0, bot - 2 * hd, x1, bot), 0, 180, EQUIP_W)
            box_top = top
            mid = (top + bot) / 2
            if u["shape"] == "column":
                for ty in range(int(top + hd + 45), int(bot - hd - 40), 70):
                    if abs(ty - mid) > 40:
                        c.line([(x0 + 6, ty), (x1 - 6, ty)], THIN_W, dash=(14, 8))
            if u.get("agitator"):
                motor_y = top - 45 - 22
                c.line([(cx, top - 45), (cx, bot - hd - 70)], THIN_W)
                c.rect((cx - 45, bot - hd - 78, cx + 45, bot - hd - 64), THIN_W, "white")  # impeller blade
                c.circle(cx, motor_y, 22, THIN_W)
                c.text(cx, motor_y, "M", TEXT)
                box_top = motor_y - 22
                u = dict(u, motor=(cx, motor_y, 22))
            c.text(cx, mid, uid, EQ_TEXT, underline=True, background=True)
            box = (x0, box_top, x1, bot)
            cls = "tank"
        elif u["shape"] == "horizontal_exchanger":
            x0, x1, cy, h = u["x0"], u["x1"], u["cy"], u["h"]
            r = 40
            c.line([(x0 + r, cy - h / 2), (x1 - r, cy - h / 2)], EQUIP_W)
            c.line([(x0 + r, cy + h / 2), (x1 - r, cy + h / 2)], EQUIP_W)
            c.line([(x0 + r, cy - h / 2), (x0 + r, cy + h / 2)], EQUIP_W)
            c.line([(x1 - r, cy - h / 2), (x1 - r, cy + h / 2)], EQUIP_W)
            c.arc((x0, cy - h / 2, x0 + 2 * r, cy + h / 2), 90, 270, EQUIP_W)
            c.arc((x1 - 2 * r, cy - h / 2, x1, cy + h / 2), 270, 450, EQUIP_W)
            c.text((x0 + x1) / 2, cy, uid, EQ_TEXT, underline=True)
            box = (x0, cy - h / 2, x1, cy + h / 2)
            cls = "tank"
        elif u["shape"] == "compressor":
            (x, y), r = u["at"], u["r"]
            c.circle(x, y, r, EQUIP_W)
            k = r * 0.7
            c.line([(x - k, y - k), (x + k, y - r * 0.38)], THIN_W)
            c.line([(x - k, y + k), (x + k, y + r * 0.38)], THIN_W)
            c.text(x, y + 205, uid, EQ_TEXT, underline=True)
            box = (x - r, y - r, x + r, y + r)
            cls = "pump"
        elif u["shape"] == "mixer":
            (x, y) = u["at"]
            c.rect((x - 35, y - 15, x + 35, y + 15), THIN_W, "white")
            c.line([(x - 35, y + 15), (x - 21, y - 15), (x - 7, y + 15), (x + 7, y - 15), (x + 21, y + 15),
                    (x + 35, y - 15)], THIN_W)
            c.text(x, y + 45, uid, EQ_TEXT, underline=True)
            box = (x - 35, y - 15, x + 35, y + 15)
            cls = "general"
        else:
            raise ValueError(f"{uid}: unknown shape {u['shape']}")
        self.unit_geo[uid] = dict(u, box=box)  # outline geometry, for leaders
        pad = EQUIP_W / 2 + 0.5  # the key box holds the whole outline stroke, as the OPEN100 keys do
        box = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
        return self.node(cls, box, uid, f"unit:{uid}", kind="unit"), name

    def mount_leader(self, uid, bc):
        """Leader from a unit-mounted bubble to the unit outline (horizontal into the wall, or vertical)."""
        g = self.unit_geo[uid]
        x0, y0, x1, y1 = g["box"]
        bx, by = bc
        if "motor" in g and abs(by - g["motor"][1]) < 1:
            mx, my, mr = g["motor"]
            hit = mx + mr if bx > mx else mx - mr
            return [(bx - BUBBLE_R if bx > mx else bx + BUBBLE_R, by), (hit, by)]
        if g["shape"] == "compressor":
            (x, y), r = g["at"], g["r"]
            return [(bx, by - BUBBLE_R), (bx, y + math.sqrt(max(0, r * r - (bx - x) ** 2)))]
        if y0 <= by <= y1:
            wall = x1 if bx > x1 else x0
            return [(bx - BUBBLE_R if bx > x1 else bx + BUBBLE_R, by), (wall, by)]
        edge = y1 if by > y1 else y0
        return [(bx, by - BUBBLE_R if by > y1 else by + BUBBLE_R), (bx, edge)]

    def arrow(self, a, b, t_along, avoid):
        L = math.dist(a, b)
        for frac in (0.5, 0.3, 0.7, 0.2, 0.8):
            p = (a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac)
            if all(math.dist(p, q) > 70 for q in avoid):
                break
        else:
            return
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        tip = (p[0] + ux * ARROW_L / 2, p[1] + uy * ARROW_L / 2)
        base = (p[0] - ux * ARROW_L / 2, p[1] - uy * ARROW_L / 2)
        n = (-uy * ARROW_W / 2, ux * ARROW_W / 2)
        self.c.polygon([tip, (base[0] + n[0], base[1] + n[1]), (base[0] - n[0], base[1] - n[1])], 1, "black")
        self.node("arrow", (min(tip[0], base[0]) - 6, min(tip[1], base[1]) - 6,
                            max(tip[0], base[0]) + 6, max(tip[1], base[1]) + 6))

    # -- the sheet
    def draw(self, items_by_tag, drawn):
        spec, c = self.spec, self.c
        self.border()
        unit_nodes, flag_nodes, routes = {}, {}, {}
        # Lines first, so symbols sit on top of them.
        for r in spec["routes"]:
            c.line(r["pts"], PROCESS_W)
        for uid, u in spec["units"].items():
            unit_nodes[uid], _ = self.unit(uid, u)
            drawn.setdefault(f"unit:{uid}", []).append(spec["id"])
        for fid, f in spec["flags"].items():
            flag_nodes[fid] = self.flag(fid, f)
        # Items on each route: stream items come from the model; utility/bypass items are named by the layout.
        sheet_units = set(spec["units"])
        for r in spec["routes"]:
            if r.get("stream"):
                tags = [t for t, it in items_by_tag.items() if it.get("stream") == r["stream"] and it["unit"] in sheet_units]
                drawn.setdefault(f"stream:{r['stream']}", []).append(spec["id"])
            else:
                tags = list(r.get("items", []))
            unknown = [t for t in list(r.get("items", [])) + list(r.get("place", {})) if t not in items_by_tag]
            if unknown:
                raise ValueError(f"sheet {spec['id']} route {r['id']}: tags not in the model: {unknown}")
            routes[r["id"]] = self.place_items(r, tags, items_by_tag)
        avoid = [p for rr in routes.values() for (_, p, _, _) in rr["placed"]]
        # Inline items, taps, arrows, line labels.
        for r in spec["routes"]:
            rr = routes[r["id"]]
            side = r.get("bubble_side", "up")
            for tag, p, orient, t in rr["placed"]:
                it = items_by_tag[tag]
                s = side if orient == "h" else ("right" if side == "down" else "left")
                if "xmv" in it:
                    rr["valves"].append((t, self.valve(p, orient, tag, s, not r.get("stream"))))
                else:
                    rr["taps"].append((t, self.tap(p, orient, tag, s)))
                drawn.setdefault(tag, []).append(spec["id"])
            for a, b in zip(r["pts"], r["pts"][1:]):
                if math.dist(a, b) >= 300:
                    self.arrow(a, b, 0, avoid)
            self.line_label(r, rr)
        # Unit-mounted bubbles.
        for uid, u in spec["units"].items():
            for tag, bc in u.get("mount", {}).items():
                if tag not in items_by_tag:
                    raise ValueError(f"sheet {spec['id']} unit {uid}: mount tag {tag} is not in the model")
                it = items_by_tag[tag]
                lead = self.mount_leader(uid, bc)
                c.line(lead, THIN_W)
                kind = "final_element" if "xmv" in it else "instrument"
                bid = self.bubble(*bc, tag, kind)
                self.link_group([bid, unit_nodes[uid]], lead[1])
                drawn.setdefault(tag, []).append(spec["id"])
        self.connect(routes, unit_nodes, flag_nodes)
        self.legend()
        self.title_block()

    def place_items(self, r, tags, items_by_tag):
        pts = [tuple(p) for p in r["pts"]]
        L = length(pts)
        placed = []
        explicit = r.get("place", {})
        for tag in tags:
            if tag in explicit:
                loc = locate(pts, tuple(explicit[tag]))
                if loc is None:
                    raise ValueError(f"route {r['id']}: {tag} placed at {explicit[tag]}, which is not on the line")
                placed.append((tag, tuple(explicit[tag]), loc[1], loc[0]))
        auto = [t for t in tags if t not in explicit]
        if auto:
            # Owner end: measurements sit next to the unit that owns them, the valve beyond them (house rule).
            owner = {items_by_tag[t]["unit"] for t in auto}
            from_owner = r["from"].get("unit") in owner
            order = sorted(auto, key=lambda t: "xmv" in items_by_tag[t])
            for k, tag in enumerate(order):
                d = 130 + 110 * k
                t = d if from_owner else L - d
                (p, orient, seg) = point_at(pts, t)
                placed.append((tag, (round(p[0]), round(p[1])), orient, t))
        return {"pts": pts, "placed": sorted(placed, key=lambda x: x[3]), "valves": [], "taps": []}

    def line_label(self, r, rr):
        if not r.get("stream"):
            return
        segs = [(a, b) for a, b in zip(r["pts"], r["pts"][1:]) if seg_dir(a, b) == "h" and math.dist(a, b) >= 350]
        if not segs:
            return
        a, b = max(segs, key=lambda s: math.dist(*s))
        dy = -26 if r.get("bubble_side") == "down" else 22
        for frac in (0.5, 0.3, 0.7, 0.2, 0.8):
            x = a[0] + (b[0] - a[0]) * frac
            if all(abs(x - p[0]) > 150 for (_, p, _, _) in rr["placed"]):
                self.c.text(x, a[1] + dy, f"SIZE-TE-{r['stream'].upper()}-SPEC-X", SMALL)
                return

    def connect(self, routes, unit_nodes, flag_nodes):
        """Union the line pieces into networks: valves split a line; nets and tees join lines."""
        parent = {}

        def find(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            parent[find(a)] = find(b)

        members, where = {}, {}

        def end_member(end):
            if "unit" in end:
                return unit_nodes[end["unit"]]
            if "flag" in end:
                return flag_nodes[end["flag"]]
            return None

        def piece_of(rid, t):
            cuts = [tv for tv, _ in sorted(routes[rid]["valves"])]
            return (rid, sum(1 for cv in cuts if cv < t))

        for r in self.spec["routes"]:
            rid, rr = r["id"], routes[r["id"]]
            valves = sorted(rr["valves"])
            n = len(valves)
            for k in range(n + 1):
                pid = (rid, k)
                find(pid)
                mem = members.setdefault(pid, [])
                if k == 0:
                    mem.append(end_member(r["from"]))
                else:
                    mem.append(valves[k - 1][1])
                if k == n:
                    mem.append(end_member(r["to"]))
                else:
                    mem.append(valves[k][1])
                lo = 0 if k == 0 else valves[k - 1][0]
                hi = length(rr["pts"]) if k == n else valves[k][0]
                where[pid] = point_at(rr["pts"], (lo + hi) / 2)[0]
            for t, bid in rr["taps"]:
                members[piece_of(rid, t)].append(bid)
            for key, end, t_end in (("from", r["from"], 0.0), ("to", r["to"], length(rr["pts"]))):
                piece = (rid, 0) if key == "from" else (rid, n)
                if "net" in end:
                    union(piece, ("net", end["net"]))
                if "tee" in end:
                    loc = locate(routes[end["tee"]]["pts"], tuple(end["at"]))
                    if loc is None:
                        raise ValueError(f"route {rid}: tee point {end['at']} is not on route {end['tee']}")
                    union(piece, piece_of(end["tee"], loc[0]))
        groups = {}
        for pid, mem in members.items():
            groups.setdefault(find(pid), ([], where[pid]))[0].extend(mem)
        for mem, at in groups.values():
            self.link_group(mem, at)

    def border(self):
        c = self.c
        fx0, fy0, fx1, fy1 = FRAME
        c.rect((30, 30, self.w - 30, self.h - 30), THIN_W)
        c.rect(FRAME, PROCESS_W)
        cw, rh = (fx1 - fx0) / COLS, (fy1 - fy0) / ROWS
        for k in range(COLS):
            x = fx0 + k * cw
            if k:
                c.line([(x, 30), (x, fy0)], THIN_W)
                c.line([(x, fy1), (x, self.h - 30)], THIN_W)
            c.text(x + cw / 2, 50, str(COLS - k), 22)
            c.text(x + cw / 2, self.h - 50, str(COLS - k), 22)
        for k in range(ROWS):
            y = fy0 + k * rh
            if k:
                c.line([(30, y), (fx0, y)], THIN_W)
                c.line([(fx1, y), (self.w - 30, y)], THIN_W)
            c.text(50, y + rh / 2, "HGFEDCBA"[k], 22)
            c.text(self.w - 50, y + rh / 2, "HGFEDCBA"[k], 22)

    def legend(self):
        x = 300
        for uid in self.spec["units"]:
            u = next(v for v in self.model["units"] if v["id"] == uid)
            self.c.text(x, 1880, uid, EQ_TEXT, underline=True, anchor="lm")
            self.c.text(x, 1918, f"SERVICE:  {u['name'].upper()}", SMALL, anchor="lm")
            self.c.text(x, 1938, "SIZE:   DESIGN:   MATERIAL:", SMALL, anchor="lm")
            x += 420

    def title_block(self):
        c, tb = self.c, self.layout["title_block"]
        x0, x1 = 2740, 3110
        c.rect((x0, 1330, x1, 1520), THIN_W)
        for k, line in enumerate(tb["notes"]):
            c.text(x0 + 14, 1365 + 36 * k, line, SMALL, anchor="lm")
        n = len(self.layout["sheets"])
        idx = [s["id"] for s in self.layout["sheets"]].index(self.spec["id"]) + 1
        boxes = [((x0, 1540, x1, 1630), "PROJECT:", [tb["project"]]),
                 ((x0, 1640, x1, 1760), "TITLE:", [self.spec["title"], f"PID {self.spec['drawing']}"]),
                 ((x0, 1770, 2925, 1850), "DRAWN BY:", [tb["drawn_by"]]),
                 ((2935, 1770, x1, 1850), "DATE:", [tb["date"]]),
                 ((x0, 1860, 2860, 1940), "REVISION:", [tb["revision"]]),
                 ((2870, 1860, 2990, 1940), "SCALE:", [tb["scale"]]),
                 ((3000, 1860, x1, 1940), "SHEET:", [f"{idx} OF {n}"])]
        for (bx0, by0, bx1, by1), label, lines in boxes:
            c.rect((bx0, by0, bx1, by1), THIN_W)
            c.text(bx0 + 8, by0 + 14, label, 11, anchor="lm")
            for k, line in enumerate(lines):
                c.text((bx0 + bx1) / 2, by0 + 44 + 26 * k - 13 * (len(lines) - 1), line, SMALL)

    def graphml(self):
        keys = [("d9", "edge", "edge_label", "string"), ("d12", "node", "model_ref", "string"),
                ("d11", "node", "text", "string"),
                ("d4", "node", "ymax", "double"), ("d3", "node", "ymin", "double"), ("d2", "node", "xmax", "double"),
                ("d1", "node", "xmin", "double"), ("d0", "node", "label", "string")]
        out = ["<?xml version='1.0' encoding='utf-8'?>",
               '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">']
        out += [f'  <key id="{i}" for="{f}" attr.name="{n}" attr.type="{t}" />' for i, f, n, t in keys]
        out.append('  <graph edgedefault="undirected">')
        for nid, n in self.nodes.items():
            b = n["box"]
            out.append(f'    <node id="{nid}">')
            out.append(f'      <data key="d0">{escape(n["class"])}</data>')
            for k, v in zip(("d1", "d2", "d3", "d4"), (b[0], b[2], b[1], b[3])):
                out.append(f'      <data key="{k}">{v}</data>')
            if n["text"]:
                out.append(f'      <data key="d11">{escape(n["text"])}</data>')
            if n["model_ref"]:
                out.append(f'      <data key="d12">{escape(n["model_ref"])}</data>')
            out.append("    </node>")
        for a, b in sorted(self.edges):
            out.append(f'    <edge source="{a}" target="{b}"><data key="d9">solid</data></edge>')
        out += ["  </graph>", "</graphml>", ""]
        return "\n".join(out)


def sha_file(p):
    """sha256 of a file; text files are hashed with CRLF normalised to LF, so a Windows and a Linux checkout agree."""
    data = Path(p).read_bytes()
    if Path(p).suffix.lower() != ".png":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def generate(model_path, layout_path, out_dir, write=True, register=None):
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    layout = json.loads(Path(layout_path).read_text(encoding="utf-8"))
    items_by_tag = {i["tag"]: i for i in model["instruments"] + model["final_elements"]}
    drawn, sheets = {}, []
    for spec in layout["sheets"]:
        sh = Sheet(spec, model, layout, None)
        sh.draw(items_by_tag, drawn)
        sheets.append(sh)
    # Completeness: every model unit, item and stream drawn; items exactly once.
    problems = []
    for tag in items_by_tag:
        n = len(drawn.get(tag, []))
        if n != 1:
            problems.append(f"{tag}: drawn {n} times (must be exactly once)")
    for u in model["units"]:
        if len(drawn.get(f"unit:{u['id']}", [])) != 1:
            problems.append(f"unit {u['id']}: drawn {len(drawn.get('unit:' + u['id'], []))} times")
    for s in model["streams"]:
        if not drawn.get(f"stream:{s['id']}"):
            problems.append(f"stream {s['id']}: not drawn")
    if problems:
        raise ValueError("layout does not draw the model exactly:\n  " + "\n  ".join(problems))
    if not write:
        return sheets
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    key = {"about": "Answer key emitted by scripts/draw_pid_from_model.py from the same model that drew the sheets. "
                    "Scoring against it is a ROUND TRIP: it measures how faithfully a reader recovers our own "
                    "clean house-style drawing, not real-plant accuracy.",
           "model": (Path(model_path).resolve().relative_to(ROOT).as_posix()
                     if Path(model_path).resolve().is_relative_to(ROOT) else Path(model_path).name), "sheets": {}}
    import PIL
    manifest = {"generator": "scripts/draw_pid_from_model.py", "pillow": PIL.__version__,
                "model_sha256": sha_file(model_path), "layout_sha256": sha_file(layout_path),
                "generator_sha256": sha_file(__file__), "files": {}}
    for sh in sheets:
        sid = sh.spec["id"]
        png, svg, gml = out_dir / f"{sid}.png", out_dir / f"{sid}.svg", out_dir / f"{sid}.graphml"
        sh.c.write(png, svg)
        gml.write_text(sh.graphml(), encoding="utf-8")
        key["sheets"][sid] = {"drawing": sh.spec["drawing"], "system": sh.spec["system"], "title": sh.spec["title"],
                              "size_px": [sh.w, sh.h],
                              "symbols": {k: v for k, v in sh.nodes.items() if v["class"] not in ("connector", "arrow")},
                              "edges": sorted(sh.edges)}
        for p in (png, svg, gml):
            manifest["files"][p.name] = sha_file(p)
    (out_dir / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    manifest["files"]["key.json"] = sha_file(out_dir / "key.json")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    reg = Path(register) if register else out_dir / "sheet_register.csv"
    reg.write_text("# Drawing register for the generated Tennessee Eastman sheets (scripts/draw_pid_from_model.py).\n"
                   "# Read from each sheet's title block, as a plant would supply from its drawing index.\n"
                   "sheet,drawing_number,system_code,system_name\n"
                   + "".join(f"{s['id']},{s['drawing']},{s['system']},\"{s['title'].title()}\"\n"
                             for s in layout["sheets"]),
                   encoding="utf-8")
    return sheets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="data/te_process_model.json")
    ap.add_argument("--layout", default="data/te_pid_layout.json")
    ap.add_argument("--out", default="data/te_pid")
    ap.add_argument("--check", action="store_true", help="validate the layout against the model; write nothing")
    a = ap.parse_args()
    try:
        sheets = generate(ROOT / a.model, ROOT / a.layout, ROOT / a.out, write=not a.check,
                          register=ROOT / "data" / "sheet_registers" / "te_generated.csv")
    except ValueError as e:
        sys.exit(f"refused: {e}")
    for sh in sheets:
        n = {}
        for v in sh.nodes.values():
            n[v["class"]] = n.get(v["class"], 0) + 1
        print(f"sheet {sh.spec['id']} ({sh.spec['title']}): {n}")


if __name__ == "__main__":
    main()
