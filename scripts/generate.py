"""Process model -> SVG graphics + Ignition tag JSON + PI AF sheet + Operations review sheet.

Two kinds of model are accepted:
  - a hand-built process model (data/te_process_model.json): outputs go to out/ as before;
  - an extracted twin (meta.model_kind == "extracted_twin", written by scripts/build_twin.py): outputs go next to
    the model file (review_queue.csv, ignition/tags.json, pi/pi_builder_af.csv, svg/sheet_<n>.svg).

Stdlib only. Usage:  python scripts/generate.py [path/to/model.json]
"""
import csv
import json
import os
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = ROOT / "data" / "te_process_model.json"
OUT = ROOT / "out"

STROKE = "#1f2937"
ACCENT = "#2563eb"
BASE_STYLE = (
    f".eq{{fill:#fff;stroke:{STROKE};stroke-width:2}}"
    f".ln{{fill:none;stroke:{STROKE};stroke-width:2}}"
    f".pipe{{fill:none;stroke:#475569;stroke-width:2.5}}"
    f".inst{{fill:#fff;stroke:{ACCENT};stroke-width:1.5}}"
    f".t{{font:12px Arial,sans-serif;fill:{STROKE}}}"
    f".ti{{font:bold 10px Arial,sans-serif;fill:{ACCENT}}}"
    f".ts{{font:10px Arial,sans-serif;fill:#64748b}}"
)

# ---------------------------------------------------------------- validation

def validate(model):
    """Structural checks. Every failure is a review item, not a silent fix."""
    problems = []
    unit_ids = {u["id"] for u in model["units"]}
    stream_ids = {s["id"] for s in model["streams"]}
    tags = [i["tag"] for i in model["instruments"] + model["final_elements"]]
    for t in {t for t in tags if tags.count(t) > 1}:
        problems.append(f"duplicate tag {t}")
    for item in model["instruments"] + model["final_elements"]:
        if item["unit"] not in unit_ids:
            problems.append(f"{item['tag']}: unknown unit {item['unit']}")
        if item.get("stream") and item["stream"] not in stream_ids:
            problems.append(f"{item['tag']}: unknown stream {item['stream']}")
        letters = item["tag"].split("-")[0]
        expected = {"flow": "F", "pressure": "P", "level": "L", "temperature": "T",
                    "power": "J", "composition": "A"}.get(item.get("variable"))
        if expected and not letters.startswith(expected):
            problems.append(f"{item['tag']}: ISA first letter does not match variable '{item['variable']}'")
    for s in model["streams"]:
        for end in (s["from"], s["to"]):
            if end != "BL" and end not in unit_ids:
                problems.append(f"stream {s['id']}: unknown endpoint {end}")
    return problems

# ---------------------------------------------------------------- symbols (drawn around 0,0)

def sym_reactor():
    return ('<rect class="eq" x="-45" y="-75" width="90" height="150" rx="40"/>'
            '<line class="ln" x1="0" y1="-95" x2="0" y2="35"/>'
            '<path class="ln" d="M-22 35 L22 35 M-22 28 L-22 42 M22 28 L22 42"/>'
            '<rect class="eq" x="-12" y="-110" width="24" height="15"/>'), 75

def sym_condenser():
    return ('<circle class="eq" r="38"/>'
            '<path class="ln" d="M-38 0 L-22 0 L-12 -18 L0 18 L12 -18 L22 0 L38 0"/>'), 38

def sym_separator():
    return ('<rect class="eq" x="-85" y="-35" width="170" height="70" rx="35"/>'
            '<rect class="eq" x="30" y="35" width="30" height="25"/>'), 60

def sym_compressor():
    return ('<circle class="eq" r="34"/>'
            '<path class="ln" d="M-24 -24 L28 -12 M-24 24 L28 12"/>'), 34

def sym_stripper():
    trays = "".join(f'<line class="ln" stroke-dasharray="6 4" x1="-30" y1="{y}" x2="30" y2="{y}"/>'
                    for y in range(-80, 100, 30))
    return f'<rect class="eq" x="-32" y="-115" width="64" height="230" rx="30"/>{trays}', 115

def sym_feed_header():
    return ('<rect class="eq" x="-14" y="-70" width="28" height="140" rx="4"/>'
            '<text class="ts" x="0" y="4" text-anchor="middle" transform="rotate(-90)">MIX</text>'), 70

SYMBOLS = {"reactor": sym_reactor, "condenser": sym_condenser, "separator": sym_separator,
           "compressor": sym_compressor, "stripper": sym_stripper, "feed_header": sym_feed_header}


def bubble(item, x, y):
    """ISA-5.1 shared-display instrument (circle in square) or control valve, tagged for binding."""
    letters, num = item["tag"].split("-")
    attrs = (f'id="{item["tag"]}" data-tag="{item["tag"]}" data-unit="{item["unit"]}" '
             f'data-uom="{escape(item["uom"])}"')
    title = f'<title>{escape(item["tag"])}: {escape(item["description"])}</title>'
    if "xmv" in item:  # final element: bowtie valve + actuator + tag label
        body = ('<path class="inst" d="M-14 -8 L14 8 L14 -8 L-14 8 Z"/>'
                '<line class="inst" x1="0" y1="0" x2="0" y2="-16"/>'
                '<path class="inst" d="M-9 -16 A9 9 0 0 1 9 -16 Z"/>'
                f'<text class="ti" y="22" text-anchor="middle">{letters}-{num}</text>')
    else:
        body = ('<rect class="inst" x="-19" y="-19" width="38" height="38"/>'
                '<circle class="inst" r="17"/><line class="inst" x1="-17" y1="0" x2="17" y2="0"/>'
                f'<text class="ti" y="-4" text-anchor="middle">{letters}</text>'
                f'<text class="ti" y="11" text-anchor="middle">{num}</text>')
    return f'<g {attrs} transform="translate({x},{y})">{title}{body}</g>'


def unit_group(unit, x, y, label=True):
    shape, half_h = SYMBOLS[unit["type"]]()
    text = (f'<text class="t" y="{-half_h - 12 if unit["type"] != "reactor" else -122}" text-anchor="middle">'
            f'{unit["id"]} {escape(unit["name"])}</text>') if label else ""
    return (f'<g id="{unit["id"]}" data-asset="{unit["id"]}" data-type="{unit["type"]}" '
            f'transform="translate({x},{y})">{shape}{text}</g>'), half_h


def items_for(model, unit_id):
    return [i for i in model["instruments"] + model["final_elements"] if i["unit"] == unit_id]


def instrument_grid(items, cx, top, per_row=5, dx=48, dy=56):
    out = []
    for n, item in enumerate(items):
        row, col = divmod(n, per_row)
        count = min(per_row, len(items) - row * per_row)
        out.append(bubble(item, cx + (col - (count - 1) / 2) * dx, top + row * dy))
    return "".join(out)


def svg_doc(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<title>{escape(title)}</title><defs><style>{BASE_STYLE}</style>'
            f'<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#475569"/></marker></defs>'
            f'{body}</svg>\n')

# ---------------------------------------------------------------- SVG outputs

# Hand-routed pipe paths for the overview (a real extraction would carry line geometry from the drawing).
ROUTES = {
    "S1": [(10, 290), (76, 290)], "S2": [(10, 330), (76, 330)], "S3": [(10, 370), (76, 370)],
    "S4": [(1240, 470), (1042, 470)],
    "S5": [(1010, 265), (1010, 40), (60, 40), (60, 310), (76, 310)],
    "S6": [(104, 360), (285, 360)],
    "S7": [(375, 330), (430, 330), (430, 230), (502, 230)],
    "S7b": [(578, 230), (640, 230), (640, 380), (655, 380)],
    "S8": [(740, 345), (740, 164)],
    "S8b": [(706, 130), (150, 130), (150, 345), (104, 345)],
    "S9": [(774, 130), (1240, 130)],
    "S10": [(825, 380), (978, 380)],
    "S11": [(1010, 495), (1010, 520), (1240, 520)],
}

# Instrument-grid placement where the default (centered under the unit) collides: (cx, top, per_row).
GRID_OVERRIDES = {"U-100": (110, 445, 3), "K-101": (430, 70, 6)}


def overview_svg(model):
    W, H = 1250, 760
    pipes, labels = [], []
    for s in model["streams"]:
        pts = ROUTES.get(s["id"])
        if not pts:
            continue
        d = " ".join(f"{x},{y}" for x, y in pts)
        pipes.append(f'<polyline class="pipe" data-stream="{s["id"]}" points="{d}" marker-end="url(#arr)">'
                     f'<title>{s["id"]} {escape(s["name"])}</title></polyline>')
        (x1, y1), (x2, y2) = pts[0], pts[1]
        labels.append(f'<text class="ts" x="{(x1 + x2) / 2 + 4}" y="{(y1 + y2) / 2 - 5}">{s["id"]}</text>')
    units = []
    for u in model["units"]:
        g, half_h = unit_group(u, u["layout"]["x"], u["layout"]["y"])
        cx = u["layout"]["x"]
        grid_top = u["layout"]["y"] + half_h + (70 if u["type"] == "separator" else 45)
        per_row = 5
        if u["id"] in GRID_OVERRIDES:
            cx, grid_top, per_row = GRID_OVERRIDES[u["id"]]
        units.append(g + instrument_grid(items_for(model, u["id"]), cx, grid_top, per_row))
    title = f'{model["meta"]["title"]}: overview (generated)'
    head = f'<text class="t" x="10" y="20">{escape(title)}</text>'
    foot = (f'<text class="ts" x="10" y="{H - 10}">Source: {escape(model["meta"]["source_document"][:110])}… '
            f'Tags assigned by project; see model meta.</text>')
    return svg_doc(W, H, head + "".join(pipes) + "".join(labels) + "".join(units) + foot, title)


def unit_svg(model, unit):
    items = items_for(model, unit["id"])
    rows = (len(items) + 4) // 5
    g, half_h = unit_group(unit, 150, 140 if unit["type"] != "stripper" else 150)
    top = 140 + half_h + 50
    H = top + rows * 56 + 10
    return svg_doc(300, H, g + instrument_grid(items, 150, top), f'{unit["id"]} {unit["name"]}')

# ---------------------------------------------------------------- platform exports

def member_name(desc):
    return re.sub(r"[^A-Za-z0-9]", "", desc.title())[:40]


def ignition_tags(model):
    """Ignition 8.x tag JSON: one UDT type per equipment type + one instance per unit.
    Members are OPC tags whose path is built from instance parameters. The asset exists and is
    'ready to receive' a real equipment tag: set BasePath/OPCServer per instance on import."""
    types, instances = [], []
    for u in model["units"]:
        type_name = member_name(u["type"].replace("_", " "))
        members = []
        for it in items_for(model, u["id"]):
            idx = it.get("xmeas", it.get("xmv"))
            members.append({
                "name": member_name(it["description"]),
                "tagType": "AtomicTag",
                "valueSource": "opc",
                "dataType": "Float8",
                "engUnit": it["uom"],
                "documentation": f'{it["tag"]} | {"XMV" if "xmv" in it else "XMEAS"} {idx} | {it["description"]}',
                "opcServer": {"bindType": "parameter", "binding": "{OPCServer}"},
                "opcItemPath": {"bindType": "parameter", "binding": "{BasePath}." + it["tag"]},
            })
        types.append({"name": type_name, "tagType": "UdtType",
                      "parameters": {"BasePath": {"dataType": "String", "value": ""},
                                     "OPCServer": {"dataType": "String", "value": "Ignition OPC UA Server"}},
                      "tags": members})
        instances.append({"name": u["id"], "tagType": "UdtInstance", "typeId": type_name,
                          "documentation": u["name"],
                          "parameters": {"BasePath": {"dataType": "String", "value": f"ns=1;s=TE.{u['id']}"}}})
    return {"name": "", "tagType": "Provider", "tags": [
        {"name": "_types_", "tagType": "Folder", "tags": types},
        {"name": "TE_Plant", "tagType": "Folder", "tags": instances},
    ]}


PI_COLS = ["Selected(x)", "Parent", "Name", "ObjectType", "Description", "Template",
           "AttributeValueType", "AttributeDefaultUOM", "AttributeDataReference", "AttributeConfigString"]


def pi_af_rows(model):
    """PI Builder-style flat sheet: plant element, unit elements, attributes with PI Point references.
    PI Point names are placeholders (TE.<tag>.PV) until the real historian tags are mapped."""
    root = "TE Plant"
    rows = [["x", "", root, "Element", model["meta"]["title"], "", "", "", "", ""]]
    for u in model["units"]:
        rows.append(["x", root, u["id"], "Element", u["name"], member_name(u["type"].replace("_", " ")),
                     "", "", "", ""])
        for it in items_for(model, u["id"]):
            rows.append(["x", f"{root}\\{u['id']}", member_name(it["description"]), "Attribute",
                         f'{it["tag"]}: {it["description"]}', "", "Double", it["uom"], "PI Point",
                         f'\\\\%Server%\\TE.{it["tag"]}.PV'])
    return rows


REVIEW_COLS = ["item_id", "item_type", "what_it_is", "belongs_to", "units", "source",
               "extraction_confidence", "model_status",
               "OPS_confirm_or_correct", "OPS_correct_value", "OPS_show_on_operator_screen_Y_N",
               "OPS_alarm_priority_H_M_L_none", "OPS_notes"]


def review_rows(model):
    unit_names = {u["id"]: u["name"] for u in model["units"]}
    rows = []
    for u in model["units"]:
        rows.append([u["id"], "equipment", u["name"], "", "", u.get("source", ""), "seed",
                     u["verification"]["status"], "", "", "", "", ""])
    for it in model["instruments"] + model["final_elements"]:
        kind = "control valve / output" if "xmv" in it else "measurement"
        rows.append([it["tag"], kind, it["description"], unit_names[it["unit"]], it["uom"],
                     f'D&V 1993 {"XMV" if "xmv" in it else "XMEAS"} {it.get("xmeas", it.get("xmv"))}',
                     "seed", it.get("verification", {}).get("status", "unverified"), "", "", "", "", ""])
    return rows

# ---------------------------------------------------------------- extracted twin (scripts/build_twin.py output)
#
# Everything below reads a model whose meta.model_kind is "extracted_twin". Signal paths are placeholders:
# no real OPC item path or PI Point name is known from a drawing, so none is invented.

TWIN_PLACEHOLDER = "PLACEHOLDER"


def _label(item):
    return item.get("tag") or item["id"]


def _unique(name, used):
    base, n, i = name, name, 2
    while n.lower() in used:
        n, i = f"{base}_{i}", i + 1
    used.add(n.lower())
    return n


def ign_name(text, used):
    """Ignition tag/folder name: letters, digits, _ and -; unique within its folder."""
    n = re.sub(r"[^A-Za-z0-9_-]+", "_", text or "").strip("_") or "item"
    return _unique(n if n[0].isalpha() or n[0] == "_" else "_" + n, used)


def af_name(text, used):
    """AF element/attribute name: drop the characters AF forbids in names."""
    n = re.sub(r"[\\*?;{}\[\]|^'\"]+", " ", text or "").strip() or "item"
    return _unique(re.sub(r"\s+", " ", n), used)


def _twin_doc(item, extra=""):
    p = item["provenance"][0]
    return (f'{item["id"]} | tag: {item.get("tag") or "none read"} ({item["tag_status"]}) | {extra}'
            f'sheet {p["sheet"]} symbol {p["symbol"]} | confidence {item.get("confidence")} | UNVERIFIED')


def twin_ignition(model):
    """Ignition 8 tag JSON (same shape as ignition_tags above). One UDT type per equipment class, per instrument
    type (ISA letters) and per line-item class; one instance per asset, foldered Site/System/Equipment.
    Instrument PVs are OPC tags marked readOnly (monitoring-only intent); BasePath and PointName are placeholders."""
    units = {u["id"]: u for u in model["units"]}
    types, used_types = {}, set()

    def udt(kind, cls):
        label = cls if kind == "Instrument" else cls.title()  # instrument types keep their ISA letters: PT, TCV
        name = f"{kind}_{re.sub(r'[^A-Za-z0-9]', '', label) or 'Unknown'}"
        if name not in types:
            members = [{"name": "ReviewStatus", "tagType": "AtomicTag", "valueSource": "memory",
                        "dataType": "String", "value": "unverified"}]
            params = {"AssetId": {"dataType": "String", "value": ""}, "SourceTag": {"dataType": "String", "value": ""}}
            if kind == "Instrument":
                params |= {"BasePath": {"dataType": "String", "value": TWIN_PLACEHOLDER},
                           "PointName": {"dataType": "String", "value": TWIN_PLACEHOLDER},
                           "OPCServer": {"dataType": "String", "value": "Ignition OPC UA Server"}}
                members.insert(0, {
                    "name": "PV", "tagType": "AtomicTag", "valueSource": "opc", "dataType": "Float8",
                    "readOnly": True,
                    "documentation": "Process value. OPC path is a placeholder until mapped to the real point.",
                    "opcServer": {"bindType": "parameter", "binding": "{OPCServer}"},
                    "opcItemPath": {"bindType": "parameter", "binding": "{BasePath}.{PointName}"}})
            types[name] = {"name": name, "tagType": "UdtType", "parameters": params, "tags": members}
            used_types.add(name.lower())
        return name

    def instance(item, type_name, used, extra=""):
        params = {"AssetId": {"dataType": "String", "value": item["id"]},
                  "SourceTag": {"dataType": "String", "value": item.get("tag") or ""}}
        if type_name.startswith("Instrument_"):
            params["PointName"] = {"dataType": "String",
                                   "value": f"{TWIN_PLACEHOLDER}_{ign_name(_label(item), set())}"}
        return {"name": ign_name(_label(item), used), "tagType": "UdtInstance", "typeId": type_name,
                "documentation": _twin_doc(item, extra), "parameters": params}

    sys_folders = {}
    for s in model["systems"]:
        sys_folders[s["id"]] = {"folder": {"name": "", "tagType": "Folder", "tags": [],
                                           "documentation": f'{s["name"]} | drawing {s.get("drawing_number")} '
                                                            f'({s.get("drawing_number_method")})'},
                                "used": set(), "equip": {}, "unassigned": None}
    used_sys = set()
    for s in model["systems"]:
        sys_folders[s["id"]]["folder"]["name"] = ign_name(s["name"], used_sys)

    def equip_folder(uid):
        u = units[uid]
        sf = sys_folders[u["system"]]
        if uid not in sf["equip"]:
            f = {"name": ign_name(_label(u), sf["used"]), "tagType": "Folder", "tags": []}
            used = set()
            f["tags"].append(instance(u, udt("Equipment", u["class"]), used,
                                      f'on sheets {",".join(u["sheets"])} | '))
            sf["equip"][uid] = (f, used)
            sf["folder"]["tags"].append(f)
        return sf["equip"][uid]

    def unassigned(system):
        sf = sys_folders[system]
        if sf["unassigned"] is None:
            f = {"name": ign_name("_Unassigned", sf["used"]), "tagType": "Folder", "tags": [],
                 "documentation": "Items with no connection path to equipment. Assign during review."}
            sf["unassigned"] = (f, set())
            sf["folder"]["tags"].append(f)
        return sf["unassigned"]

    for u in model["units"]:
        equip_folder(u["id"])
    for x in model["line_items"]:
        f, used = equip_folder(x["unit"]) if x["unit"] else unassigned(x["system"])
        f["tags"].append(instance(x, udt("LineItem", x["class"]), used))
    for x in model["instruments"]:
        f, used = equip_folder(x["unit"]) if x["unit"] else unassigned(x["system"])
        extra = f'attached to {x["parent"]} ({x["parent_method"]}) | '
        f["tags"].append(instance(x, udt("Instrument", x["isa_letters"] or "Unknown"), used, extra))
    site = {"name": ign_name(model["site"]["name"].split(" (")[0], set()), "tagType": "Folder",
            "documentation": model["meta"]["title"] + " | every value is a PLACEHOLDER until mapped",
            "tags": [sf["folder"] for sf in sys_folders.values()]}
    return {"name": "", "tagType": "Provider", "tags": [
        {"name": "_types_", "tagType": "Folder", "tags": sorted(types.values(), key=lambda t: t["name"])}, site]}


def twin_pi_rows(model):
    """PI Builder-style sheet, same columns as pi_af_rows: Site / System / Equipment elements, one attribute per
    instrument. Attributes reference PI Points whose names are placeholders (PLACEHOLDER.<tag>.PV)."""
    units = {u["id"]: u for u in model["units"]}
    root = af_name(model["site"]["name"].split(" (")[0], set())
    rows = [["x", "", root, "Element", model["meta"]["title"], "", "", "", "", ""]]
    sys_name, used_sys, el_path, el_used = {}, set(), {}, {}
    for s in model["systems"]:
        sys_name[s["id"]] = af_name(s["name"], used_sys)
        rows.append(["x", root, sys_name[s["id"]], "Element",
                     f'Sheet {s["sheet"]}, drawing {s.get("drawing_number") or "unknown"}', "", "", "", "", ""])
        el_used[s["id"]] = set()

    def element(uid):
        if uid not in el_path:
            u = units[uid]
            parent = f'{root}\\{sys_name[u["system"]]}'
            name = af_name(_label(u), el_used[u["system"]])
            rows.append(["x", parent, name, "Element", _twin_doc(u, f'{u["class"]} | '), "", "", "", "", ""])
            el_path[uid] = (f"{parent}\\{name}", set())
        return el_path[uid]

    def unassigned(system):
        key = ("unassigned", system)
        if key not in el_path:
            parent = f'{root}\\{sys_name[system]}'
            name = af_name("Unassigned", el_used[system])
            rows.append(["x", parent, name, "Element", "Instruments with no connection path to equipment",
                         "", "", "", "", ""])
            el_path[key] = (f"{parent}\\{name}", set())
        return el_path[key]

    for u in model["units"]:
        element(u["id"])
    for x in model["instruments"]:
        path, used = element(x["unit"]) if x["unit"] else unassigned(x["system"])
        name = af_name(_label(x), used)
        point = re.sub(r"[^A-Za-z0-9_.-]+", "_", _label(x))
        rows.append(["x", path, name, "Attribute",
                     _twin_doc(x, f'{x.get("variable") or "unknown variable"} | attached to {x["parent"]} | '),
                     "", "Double", x.get("uom", ""), "PI Point", f"\\\\%Server%\\{TWIN_PLACEHOLDER}.{point}.PV"])
    return rows


TWIN_SHAPES = {
    "tank": lambda x0, y0, x1, y1: (f'<rect class="eq" x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" '
                                    f'height="{y1 - y0:.1f}" rx="{min(x1 - x0, y1 - y0) / 4:.1f}"/>'),
    "pump": lambda x0, y0, x1, y1: (f'<circle class="eq" cx="{(x0 + x1) / 2:.1f}" cy="{(y0 + y1) / 2:.1f}" '
                                    f'r="{min(x1 - x0, y1 - y0) / 2:.1f}"/>'),
    "valve": lambda x0, y0, x1, y1: (f'<path class="vl" d="M{x0:.1f} {y0:.1f} L{x1:.1f} {y1:.1f} L{x1:.1f} {y0:.1f} '
                                     f'L{x0:.1f} {y1:.1f} Z"/>'),
    "instrumentation": lambda x0, y0, x1, y1: (f'<circle class="inst" cx="{(x0 + x1) / 2:.1f}" '
                                               f'cy="{(y0 + y1) / 2:.1f}" r="{min(x1 - x0, y1 - y0) / 2:.1f}"/>'),
    "inlet/outlet": lambda x0, y0, x1, y1: (f'<path class="op" d="M{x0:.1f} {y0:.1f} L{x1 - (y1 - y0) / 2:.1f} '
                                            f'{y0:.1f} L{x1:.1f} {(y0 + y1) / 2:.1f} L{x1 - (y1 - y0) / 2:.1f} '
                                            f'{y1:.1f} L{x0:.1f} {y1:.1f} Z"/>'),
    "general": lambda x0, y0, x1, y1: (f'<path class="gn" d="M{(x0 + x1) / 2:.1f} {y0:.1f} L{x1:.1f} '
                                       f'{(y0 + y1) / 2:.1f} L{(x0 + x1) / 2:.1f} {y1:.1f} L{x0:.1f} '
                                       f'{(y0 + y1) / 2:.1f} Z"/>'),
}
TWIN_STYLE = (BASE_STYLE + ".vl,.gn,.op{fill:#fff;stroke:#1f2937;stroke-width:1.5}"
              ".lk{stroke:#64748b;stroke-width:1.2;opacity:.8}.xs{stroke:#9333ea;stroke-width:1.5}"
              ".low>*:first-child{stroke:#dc2626;stroke-dasharray:4 2}.ph>*:first-child{stroke:#ea580c}"
              ".tl{font:9px Arial,sans-serif;fill:#1f2937}")


def twin_svgs(model, images_dir=None, out_dir=None):
    """One SVG per sheet from the EXTRACTED geometry: each symbol at its extracted box, each extracted connection
    as a straight line between symbol centres (a logical link, not the drawn pipe route). Every group carries
    data-asset / data-tag / data-class / data-confidence / data-status for binding in Ignition Perspective."""
    low = model["meta"].get("low_confidence_threshold", 0.75)
    items = model["units"] + model["instruments"] + model["line_items"] + model["offpage_connectors"]
    svgs = {}
    for s in model["systems"]:
        sheet = s["sheet"]
        w_px, h_px = s.get("image_size_px") or (1000, 1000)
        W = 1400
        H = round(W * h_px / w_px)
        sx, sy = W / 1000, H / 1000
        boxes, groups = {}, []
        for it in items:
            for p in it["provenance"]:
                if p["sheet"] != sheet:
                    continue
                b = p["box_0_1000"]
                x0, y0, x1, y1 = b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy
                boxes[p["symbol"]] = ((x0 + x1) / 2, (y0 + y1) / 2)
                conf = p["confidence"]
                cls = " ".join(c for c, on in (("low", conf is not None and conf < low),
                                               ("ph", it["tag_status"] == "placeholder")) if on)
                tag = it.get("tag") or ""
                extra = f' data-pair="{it["pair"]}"' if it.get("pair") else ""
                if it.get("parent"):
                    extra += f' data-parent="{it["parent"]}"'
                label = (f'<text class="tl" x="{x0:.1f}" y="{y1 + 9:.1f}">{escape(tag[:24])}</text>'
                         if tag else "")
                groups.append(
                    f'<g id="{it["id"]}-s{sheet}-{escape(p["symbol"])}" data-asset="{it["id"]}" '
                    f'data-tag={quoteattr(tag)} data-class="{escape(it["class"])}" data-confidence="{conf}" '
                    f'data-status="{it["verification"]["status"]}" data-symbol={quoteattr(p["symbol"])}{extra}'
                    f'{" class=" + quoteattr(cls) if cls else ""}><title>{escape(it["id"])} {escape(tag)} '
                    f'({escape(it["class"])}, confidence {conf}, unverified)</title>'
                    f'{TWIN_SHAPES[it["class"]](x0, y0, x1, y1)}{label}</g>')
        lines = []
        for st in model["streams"]:
            if st.get("sheet") != sheet:
                continue
            a, b = boxes.get(st["from_symbol"]), boxes.get(st["to_symbol"])
            if a and b:
                lines.append(f'<line class="lk" data-stream="{st["id"]}" data-from="{st["from"]}" '
                             f'data-to="{st["to"]}" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" '
                             f'y2="{b[1]:.1f}"/>')
        bg = ""
        if images_dir is not None:
            img = Path(images_dir) / s["image"]
            href = os.path.relpath(img, out_dir / "svg") if out_dir else str(img)
            bg = (f'<image href={quoteattr(href.replace(os.sep, "/"))} x="0" y="0" width="{W}" height="{H}" '
                  f'opacity="0.35" preserveAspectRatio="none"/>')
        title = f'{s["name"]}: extracted overlay (sheet {sheet}, unverified)'
        foot = (f'<text class="ts" x="8" y="{H - 8}">Symbols at extracted positions; lines are extracted connections '
                f'drawn straight (not pipe routes). Red dashed = confidence below {low}. Orange = placeholder tag. '
                f'Source: {escape(str(s.get("source_run")))}</text>')
        body = (f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fff"/>{bg}'
                f'<text class="t" x="8" y="16">{escape(title)}</text>' + "".join(lines) + "".join(groups) + foot)
        svgs[sheet] = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
                       f'<title>{escape(title)}</title><defs><style>{TWIN_STYLE}</style></defs>{body}</svg>\n')
    return svgs


TWIN_REVIEW_COLS = (["rank", "why_check_this"] + REVIEW_COLS
                    + ["sheet", "symbol", "location_on_sheet_0_1000", "tag_status", "how_attached"])

ITEM_TYPE = {"tank": "equipment (vessel/tank)", "pump": "equipment (pump/compressor)", "valve": "valve",
             "general": "in-line item", "instrumentation": "instrument", "inlet/outlet": "off-page connector"}


def twin_review_rows(model):
    """One row per item, least certain first. Tiers, in order: low confidence; off-page connector not paired;
    placeholder tag; instrument with no drawn connection; other flags; then everything else. Inside a tier the
    lowest confidence comes first."""
    low = model["meta"].get("low_confidence_threshold", 0.75)
    names = {x["id"]: _label(x) for x in model["units"] + model["instruments"] + model["line_items"]
             + model["offpage_connectors"]}
    failed = {s["sheet"] for s in model["systems"] if s.get("extraction_failed")}
    rows = []

    def add(item, kind, what, belongs, reasons, conf, sheet, symbol, box, attach=""):
        tier = min((t for t, _ in reasons), default=6)
        why = "; ".join(r for _, r in sorted(reasons)) or "routine check"
        rows.append(((tier, conf if conf is not None else -1, item), [
            why, item, kind, what, belongs, "", f"{model['meta']['model_id']} sheet {sheet} symbol {symbol}",
            "" if conf is None else conf, "unverified", "", "", "", "", "", sheet, symbol,
            "" if box is None else " ".join(f"{v:g}" for v in box), "", attach]))

    def common(x):
        r = []
        c = x.get("confidence")
        if c is not None and c < low:
            r.append((1, f"low extraction confidence ({c})"))
        if x["tag_status"] == "placeholder":
            r.append((3, f'tag on the drawing is a placeholder ("{x["tag"]}"); the real tag must be supplied'))
        if x.get("duplicate_tag"):
            r.append((5, "the same tag appears on another item; confirm both are real"))
        if any(p.get("box_axes_were_swapped") for p in x["provenance"]):
            r.append((5, "extracted box had its corners reversed; position may be wrong"))
        if {p["sheet"] for p in x["provenance"]} & failed:
            r.append((1, "the extraction of this sheet failed"))
        return r

    for u in model["units"]:
        r = common(u)
        if len(u["sheets"]) > 1:
            r.append((5, f'same tag on sheets {", ".join(u["sheets"])}: merged into one asset; confirm it is one item'))
        if u["class"] == "general":
            r.append((5, "promoted from an in-line symbol because its tag looks like an equipment tag"))
        if u["tag_status"] == "missing":
            r.append((5, "equipment has no tag; supply one"))
        p = u["provenance"][0]
        add(u["id"], ITEM_TYPE.get(u["class"], u["class"]), _label(u), u["system"], r, u["confidence"],
            p["sheet"], p["symbol"], p["box_0_1000"])
    for x in model["instruments"]:
        r = common(x)
        if x["parent_method"] == "geometry_nearest":
            r.append((4, f'no connection was drawn to this instrument; attached to the nearest symbol '
                         f'({names.get(x["parent"], x["parent"])}) by position only'))
        elif x["parent_method"] == "no_candidate":
            r.append((4, "no connection and nothing nearby: instrument has no parent"))
        elif x["parent_method"] == "via_instrument_chain":
            r.append((5, "attached through another instrument; confirm what it measures"))
        elif x.get("parent_agrees_with_position") is False:
            r.append((4, f'drawn connection says it belongs to {names.get(x["parent"], x["parent"])}, but the '
                         f'nearest symbol is {names.get(x.get("position_nearest"), x.get("position_nearest"))}'))
        elif x.get("linked_candidates", 1) > 1:
            r.append((5, f'linked to {x["linked_candidates"]} items; the closest was taken as parent'))
        if not x["unit"]:
            r.append((5, "no path to any equipment; filed under Unassigned"))
        if x["tag_status"] == "missing":
            r.append((5, "no tag read"))
        p = x["provenance"][0]
        what = f'{_label(x)}: {x["variable"]} instrument' if x.get("variable") else _label(x)
        belongs = f'{names.get(x["unit"], "unassigned")} (attached to {names.get(x["parent"], "nothing")})'
        add(x["id"], "instrument", what, belongs, r, x["confidence"], p["sheet"], p["symbol"], p["box_0_1000"],
            x["parent_method"])
    for x in model["line_items"]:
        r = common(x)
        if not x["unit"]:
            r.append((5, "no path to any equipment; filed under Unassigned"))
        p = x["provenance"][0]
        add(x["id"], ITEM_TYPE.get(x["class"], x["class"]), _label(x), names.get(x["unit"], "unassigned"), r,
            x["confidence"], p["sheet"], p["symbol"], p["box_0_1000"], x["unit_method"])
    for x in model["offpage_connectors"]:
        r = common(x)
        if not x["pair"]:
            in_set = "in this set" in x["pair_status"]
            r.append((2 if in_set else 2.5, f'off-page connector not matched to another sheet ({x["pair_status"].split(": ", 1)[-1]})'
                      + ("" if in_set else "; fine if that drawing is not loaded")))
        elif x.get("pair_description_similarity") == 0:
            r.append((2, f'paired with {names.get(x["pair"], x["pair"])} by drawing numbers only; the two '
                         'descriptions share no words'))
        else:
            r.append((5, f'paired with {names.get(x["pair"], x["pair"])} on another sheet; confirm the pairing'))
        p = x["provenance"][0]
        add(x["id"], "off-page connector", x["text"] or "(no text read)", x["system"], r, x["confidence"],
            p["sheet"], p["symbol"], p["box_0_1000"], x["pair_method"] or "")
    for st in model["streams"]:
        r = []
        c = st.get("confidence")
        if c is not None and c < low:
            # Below the symbol itself: once the doubtful symbol is settled, its links are quick to confirm.
            r.append((5, f"connection to a low-confidence symbol ({c}); check after that symbol"))
        if st["kind"] == "cross_sheet":
            r.append((5, "cross-sheet link from off-page pairing; confirm"))
        what = f'connection: {names.get(st["from"], st["from"])} - {names.get(st["to"], st["to"])}'
        add(st["id"], "connection", what, "", r or [(6, "check the line exists and joins these two items")],
            c, st.get("sheet") or "", f'{st.get("from_symbol", "")}-{st.get("to_symbol", "")}'.strip("-"), None)
    rows.sort(key=lambda r: r[0])
    status = {x["id"]: x["tag_status"] for x in model["units"] + model["instruments"] + model["line_items"]
              + model["offpage_connectors"]}
    out = []
    for n, (_, row) in enumerate(rows, 1):
        row[17] = status.get(row[1], "")
        out.append([n] + row)
    return out


def validate_twin(model):
    problems = []
    ids = [x["id"] for k in ("units", "instruments", "line_items", "offpage_connectors") for x in model[k]]
    for i in {i for i in ids if ids.count(i) > 1}:
        problems.append(f"duplicate asset id {i}")
    known = set(ids)
    for s in model["streams"]:
        for end in (s["from"], s["to"]):
            if end not in known:
                problems.append(f"stream {s['id']}: unknown endpoint {end}")
    for x in model["instruments"] + model["line_items"]:
        for k in ("unit", "parent"):
            if x.get(k) and x[k] not in known:
                problems.append(f"{x['id']}: unknown {k} {x[k]}")
    return problems


def export_twin(model, out_dir, images_dir=None):
    """Write every platform output for an extracted twin next to its plant_model.json. Returns written names."""
    out_dir = Path(out_dir)
    for d in ("svg", "ignition", "pi"):
        (out_dir / d).mkdir(parents=True, exist_ok=True)
    for old in (out_dir / "svg").glob("sheet_*.svg"):
        old.unlink()
    for sheet, svg in twin_svgs(model, images_dir, out_dir).items():
        (out_dir / "svg" / f"sheet_{sheet}.svg").write_text(svg, encoding="utf-8")
    (out_dir / "ignition" / "tags.json").write_text(json.dumps(twin_ignition(model), indent=1), encoding="utf-8")
    write_csv(out_dir / "pi" / "pi_builder_af.csv", PI_COLS, twin_pi_rows(model))
    write_csv(out_dir / "review_queue.csv", TWIN_REVIEW_COLS, twin_review_rows(model))
    problems = validate_twin(model)
    for p in problems:
        print("  twin validation:", p)
    return ["review_queue.csv", "ignition/tags.json", "pi/pi_builder_af.csv",
            f"svg/sheet_*.svg ({len(model['systems'])})"] + (["VALIDATION ISSUES"] if problems else [])

# ---------------------------------------------------------------- main

def write_csv(path, header, rows):
    # utf-8-sig: Excel, where plant reviewers open these, needs the BOM to read tags like "ESS–HTR–180".
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    model_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MODEL
    model = json.loads(model_path.read_text(encoding="utf-8"))
    if model.get("meta", {}).get("model_kind") == "extracted_twin":
        written = export_twin(model, model_path.parent)
        print(f"twin: wrote {', '.join(written)} next to {model_path}")
        return 0
    problems = validate(model)
    for d in ("svg", "ignition", "pi"):
        (OUT / d).mkdir(parents=True, exist_ok=True)

    (OUT / "svg" / "overview.svg").write_text(overview_svg(model), encoding="utf-8")
    for u in model["units"]:
        (OUT / "svg" / f'{u["id"]}.svg').write_text(unit_svg(model, u), encoding="utf-8")
    (OUT / "ignition" / "te_tags.json").write_text(json.dumps(ignition_tags(model), indent=2), encoding="utf-8")
    write_csv(OUT / "pi" / "pi_builder_af.csv", PI_COLS, pi_af_rows(model))
    write_csv(OUT / "ops_review_sheet.csv", REVIEW_COLS, review_rows(model))

    n_inst, n_fe = len(model["instruments"]), len(model["final_elements"])
    print(f"model: {len(model['units'])} units, {len(model['streams'])} streams, "
          f"{n_inst} instruments, {n_fe} final elements")
    print(f"wrote: out/svg ({len(model['units']) + 1} files), out/ignition/te_tags.json, "
          f"out/pi/pi_builder_af.csv, out/ops_review_sheet.csv")
    print("validation:", "OK" if not problems else f"{len(problems)} issue(s)")
    for p in problems:
        print("  -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
