"""Process model -> SVG graphics + Ignition tag JSON + PI AF sheet + Operations review sheet.

Stdlib only. Usage:  python scripts/generate.py [path/to/model.json]
"""
import csv
import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "te_process_model.json"
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

# ---------------------------------------------------------------- main

def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
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
