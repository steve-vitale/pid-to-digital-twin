"""DEXPI public example P&IDs -> the repository's answer-key format (round 5, docs/GOAL.md).

Source: the DEXPI TrainingTestCases repository, CC BY 4.0, pinned to one commit in
data/dataset_adapters/dexpi_examples.json. Downloads, renders and converted keys stay in the gitignored
data/external/dexpi/ folder.

Two kinds of key:

1. Geometry-keyed sheets (DEXPI XML with the drawing's own shapes and topology). For each, this writes
     <id>.png       the published SVG rasterised with MuPDF, long side fixed in the config (no other processing)
     <id>.graphml   same schema as the PID2Graph keys, so scripts/score_pid2graph.py scores it unchanged
     <id>.tags.json the visible label text of each scored symbol (tag truth for scripts/score_tags.py)
2. Tag-list-keyed sheets (a PDF drawing plus the published equipment, instrument and valve lists). For each:
     <id>.png       the PDF page rasterised with MuPDF
     <id>.taglist.json  identifiers from the lists that name this drawing AND are printed on it

Conversion rules (written before any model saw a DEXPI image; changing them is a visible commit):
  Classes (dexpi_class): equipment whose class names a pump/compressor/blower/fan -> pump; other top-level
    equipment (tanks, vessels, columns, heat exchangers) -> tank; any *Valve -> valve;
    ProcessInstrumentationFunction (the bubble) -> instrumentation; PipeOffPageConnector -> inlet/outlet;
    reducers, flanges, blinds, orifices, fittings and other in-line PipingComponents -> general;
    PipeTee -> connector (pass-through, as in the PID2Graph keys). Not separate symbols: nozzles, chambers,
    impellers, column sections and other equipment internals, actuators (drawn on their valve), signal-generating functions,
    flow arrows, insulation and slope marks.
  Boxes: the union of the symbol's shape-catalogue geometry (scaled, rotated, mirrored and placed by its
    Position and Scale) and any geometry written directly on the item. Labels and text are excluded. A box
    narrower than min_box_side_frac of the image's long side (config) is widened to that size about its centre:
    flanges and blinds are drawn as one stroke, and a zero-area box can never be matched.
  Links: every drawn line, as in the PID2Graph keys. Inside a piping segment, consecutive items are joined
    (start item, in-line items in order, end item); nozzles stand for their equipment; tees are connectors.
    Measuring and signal lines join their two ends; an actuator end stands for the valve it operates.
  Tag truth: the text of the item's own label as drawn. Instrument bubbles: the first two lines joined (letters
    and number; a third line such as an area prefix is left out). Other labels: the first line (the identifier;
    later lines carry set pressure, sizes and similar). A valve without its own label takes the number label of
    the actuating system that operates it (first two lines joined, as for a bubble).
    Items without a label have no tag truth and are left out of tag scoring.
  Tag lists: an identifier counts for a sheet only if its list row names that drawing and the identifier is
    printed in the PDF's text layer for that page. Rows without an identifier ("No Itemtag!") are skipped.

Usage:
  python scripts/adapt_dexpi.py fetch     # download the pinned files, check every SHA-256
  python scripts/adapt_dexpi.py build     # render images and write keys
  python scripts/adapt_dexpi.py overlay   # draw key boxes on the renders for a visual check (out of git)
"""
import argparse
import hashlib
import json
import math
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "dataset_adapters" / "dexpi_examples.json"
BASE = ROOT / "data" / "external" / "dexpi"
SOURCE = BASE / "source"
SHEETS = BASE / "sheets"   # point PID_DATA_DIR here for run_extraction.py / trace_connections.py

GEOMETRY = {"Line", "PolyLine", "Shape", "Circle", "Ellipse", "TrimmedCurve"}
ITEM_TAGS = {"Equipment", "PipingComponent", "ProcessInstrumentationFunction", "PipeOffPageConnector"}
PUMP_WORDS = ("Pump", "Compressor", "Blower", "Fan")
# Equipment classes that are parts drawn inside another item, never a separate symbol. ColumnSection was added
# after the oracle overlay (before any model run) showed a top-level section drawn inside its column.
INTERNAL_WORDS = ("Section", "Chamber", "Impeller", "TubeBundle", "Displacer", "Packing", "Nozzle", "Agitator")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def local_path(rel):
    return SOURCE / rel


def all_files(cfg):
    out = [(s["xml"], s["xml_sha256"]) for s in cfg["geometry_keyed"]]
    out += [(s["image"], s["image_sha256"]) for s in cfg["geometry_keyed"]]
    out += [(v["path"], v["sha256"]) for v in cfg["tag_list_keyed"]["lists"].values()]
    out += [(s["pdf"], s["pdf_sha256"]) for s in cfg["tag_list_keyed"]["sheets"]]
    out.append(("LICENSE", cfg["license_file_sha256"]))
    return out


def fetch(cfg):
    for rel, expected in all_files(cfg):
        dest = local_path(rel)
        if dest.exists() and sha(dest) == expected:
            print(f"ok      {rel}")
            continue
        url = cfg["raw_url_template"].format(commit=cfg["source_commit"], path=urllib.parse.quote(rel))
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        got = hashlib.sha256(data).hexdigest()
        if got != expected:
            sys.exit(f"SHA-256 mismatch for {rel}: {got} (expected {expected}); refusing to use it")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(f"fetched {rel} ({len(data)} bytes)")


# ---------------------------------------------------------------- classes

def dexpi_class(tag, component_class, top_level_equipment=True):
    """Map a DEXPI item to a scored class, 'connector', or None (not a separate symbol)."""
    c = component_class or ""
    if tag == "ProcessInstrumentationFunction":
        return "instrumentation"
    if tag == "PipeOffPageConnector":
        return "inlet/outlet"
    if tag == "Equipment":
        if not top_level_equipment or any(w in c for w in INTERNAL_WORDS):
            return None
        return "pump" if any(w in c for w in PUMP_WORDS) else "tank"
    if tag == "PipingComponent":
        if c == "PipeTee":
            return "connector"
        if "Valve" in c:
            return "valve"
        return "general"
    return None


# ---------------------------------------------------------------- geometry

def fnum(e, k, default=0.0):
    v = e.get(k)
    return float(v) if v not in (None, "") else default


def position(e):
    """(x, y, angle_rad, mirrored) from a <Position> child, or None."""
    p = e.find("Position")
    if p is None:
        return None
    loc, ref, axis = p.find("Location"), p.find("Reference"), p.find("Axis")
    ang = math.atan2(fnum(ref, "Y"), fnum(ref, "X", 1.0)) if ref is not None else 0.0
    mirrored = axis is not None and fnum(axis, "Z", 1.0) < 0
    return fnum(loc, "X"), fnum(loc, "Y"), ang, mirrored


def primitive_points(g):
    """Points outlining one geometry primitive, in the coordinates it is written in."""
    if g.tag in ("PolyLine", "Line", "Shape"):
        return [(fnum(c, "X"), fnum(c, "Y")) for c in g.iter("Coordinate")]
    if g.tag in ("Circle", "Ellipse"):
        pos = position(g) or (0.0, 0.0, 0.0, False)
        rx = fnum(g, "Radius", fnum(g, "PrimaryAxis", 0.0))
        ry = fnum(g, "Radius", fnum(g, "SecondaryAxis", rx))
        return [(pos[0] + rx * math.cos(t), pos[1] + ry * math.sin(t))
                for t in (i * math.pi / 18 for i in range(36))]
    if g.tag == "TrimmedCurve":
        curve = g.find("Circle")
        if curve is None:
            curve = g.find("Ellipse")
        if curve is None:
            return []
        pos = position(curve) or (0.0, 0.0, 0.0, False)
        rx = fnum(curve, "Radius", fnum(curve, "PrimaryAxis", 0.0))
        ry = fnum(curve, "Radius", fnum(curve, "SecondaryAxis", rx))
        a0, a1 = fnum(g, "StartAngle"), fnum(g, "EndAngle")
        if a1 < a0:
            a1 += 360.0
        steps = max(2, int((a1 - a0) / 5) + 1)
        return [(pos[0] + rx * math.cos(math.radians(a0 + (a1 - a0) * i / (steps - 1))),
                 pos[1] + ry * math.sin(math.radians(a0 + (a1 - a0) * i / (steps - 1)))) for i in range(steps)]
    return []


def shape_points(shape):
    """Every primitive point in a shape-catalogue entry (local coordinates); skips nested labels."""
    pts = []
    for g in shape:
        if g.tag in GEOMETRY:
            pts += primitive_points(g)
        elif g.tag not in ("Label", "Text", "GenericAttributes", "Position", "Scale", "Presentation"):
            pts += shape_points(g)
    return pts


def place(points, item):
    """Local catalogue points -> drawing coordinates via the item's Scale and Position."""
    pos = position(item)
    if pos is None:
        return []
    x0, y0, ang, mirrored = pos
    s = item.find("Scale")
    sx, sy = (fnum(s, "X", 1.0), fnum(s, "Y", 1.0)) if s is not None else (1.0, 1.0)
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    for x, y in points:
        x, y = x * sx, y * sy
        if mirrored:
            y = -y
        out.append((x0 + x * ca - y * sa, y0 + x * sa + y * ca))
    return out


def item_box(item, catalogue):
    """Drawing-coordinate box (xmin, ymin, xmax, ymax) of an item, or None if it has no geometry."""
    pts = []
    shape = catalogue.get(item.get("ComponentName"))
    if shape is not None:
        pts += place(shape_points(shape), item)
    for g in item:
        if g.tag in GEOMETRY:
            pts += primitive_points(g)   # geometry written on the instance is already absolute
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------- labels / tags

def label_lines(label):
    return [t.get("String", "").strip() for t in label.iter("Text") if t.get("String", "").strip()]


def own_labels(item):
    return [c for c in item if c.tag == "Label"]


def tag_truth(item, actuating_number):
    labels = own_labels(item)
    if item.tag == "ProcessInstrumentationFunction":
        for lab in labels:
            if lab.get("ComponentClass") == "ProcessInstrumentationFunctionLabel":
                lines = label_lines(lab)
                return " ".join(lines[:2]) if lines else None
        return None
    for lab in labels:
        cls = lab.get("ComponentClass", "")
        if cls in ("EquipmentBarLabel", "NozzleStandardLabel", "InsulationLabel"):
            continue
        lines = label_lines(lab)
        if lines:
            return lines[0]
    return actuating_number.get(item.get("ID"))


# ---------------------------------------------------------------- one geometry-keyed sheet

def convert_xml(xml_path):
    """Parse a DEXPI XML file into scored nodes, connector nodes and edges (drawing coordinates)."""
    root = ET.parse(xml_path).getroot()
    cat_el = root.find("ShapeCatalogue")
    catalogue = {e.get("ComponentName"): e for e in (cat_el if cat_el is not None else [])}
    drawing = root.find("Drawing")
    ext = drawing.find("Extent")
    extent = (fnum(ext.find("Min"), "X"), fnum(ext.find("Min"), "Y"),
              fnum(ext.find("Max"), "X"), fnum(ext.find("Max"), "Y"))
    parent = {c: p for p in root.iter() for c in p}
    in_catalogue = set(cat_el.iter()) if cat_el is not None else set()

    # Actuating systems: valve id -> number label text; actuator id -> valve id.
    actuating_number, actuator_valve = {}, {}
    for asys in root.iter("ActuatingSystem"):
        if asys in in_catalogue:
            continue
        number = next((" ".join(label_lines(l)[:2]) for l in own_labels(asys)
                       if l.get("ComponentClass") == "ActuatingSystemNumberLabel" and label_lines(l)), None)
        valves = [a.get("ItemID") for ref in asys.iter("ActuatingSystemComponent")
                  if ref.get("ComponentClass") == "OperatedValveReference"
                  for a in ref.iter("Association") if a.get("Type") == "refers to"]
        actuators = [c.get("ID") for c in asys.iter("ActuatingSystemComponent")
                     if c.get("ComponentClass") != "OperatedValveReference"]
        for v in valves:
            if number:
                actuating_number[v] = number
            for act in actuators:
                actuator_valve[act] = v

    nodes, alias = {}, {}
    for item in root.iter():
        if item in in_catalogue or item.tag not in ITEM_TAGS or not item.get("ID"):
            continue
        top = item.tag != "Equipment" or parent.get(item) is root
        cls = dexpi_class(item.tag, item.get("ComponentClass"), top)
        if cls is None:
            continue
        box = item_box(item, catalogue)
        if box is None and cls != "connector":
            raise ValueError(f"{xml_path.name}: {item.get('ID')} ({item.get('ComponentClass')}) has no geometry")
        nodes[item.get("ID")] = {"class": cls, "box": box, "dexpi_class": item.get("ComponentClass"),
                                 "tag": tag_truth(item, actuating_number) if cls != "connector" else None}
        if item.tag == "Equipment":
            for noz in item.iter("Nozzle"):
                alias[noz.get("ID")] = item.get("ID")
    for act, valve in actuator_valve.items():
        alias[act] = valve

    def resolve(i):
        i = alias.get(i, i)
        return i if i in nodes else None

    edges = set()
    unresolved = []

    def join(a, b):
        if a and b and a != b:
            edges.add(tuple(sorted((a, b))))

    for seg in root.iter("PipingNetworkSegment"):
        if seg in in_catalogue:
            continue
        conn = seg.find("Connection")
        chain = []
        if conn is not None and conn.get("FromID"):
            chain.append(conn.get("FromID"))
        chain += [c.get("ID") for c in seg if c.tag in ("PipingComponent", "PipeOffPageConnector")]
        if conn is not None and conn.get("ToID"):
            chain.append(conn.get("ToID"))
        resolved = []
        for i in chain:
            r = resolve(i)
            if r is None:
                unresolved.append(i)
                continue
            if not resolved or resolved[-1] != r:
                resolved.append(r)
        for a, b in zip(resolved, resolved[1:]):
            join(a, b)
    for flow in root.iter("InformationFlow"):
        if flow in in_catalogue:
            continue
        for conn in flow.iter("Connection"):
            a, b = resolve(conn.get("FromID")), resolve(conn.get("ToID"))
            if a is None or b is None:
                unresolved.append(f"{conn.get('FromID')}->{conn.get('ToID')}")
            join(a, b)
    return {"extent": extent, "nodes": nodes, "edges": sorted(edges), "unresolved": unresolved}


def to_pixels(box, extent, scale):
    xmin, ymin, xmax, ymax = box
    return ((xmin - extent[0]) * scale, (extent[3] - ymax) * scale,
            (xmax - extent[0]) * scale, (extent[3] - ymin) * scale)


def min_size(px, min_side):
    """Widen a box to at least min_side in each direction, keeping its centre. Flanges and blinds are drawn as a
    single stroke, so their geometry box has zero width, and a zero-area box can never be matched (IoU = 0)."""
    x0, y0, x1, y1 = px
    if x1 - x0 < min_side:
        c = (x0 + x1) / 2
        x0, x1 = c - min_side / 2, c + min_side / 2
    if y1 - y0 < min_side:
        c = (y0 + y1) / 2
        y0, y1 = c - min_side / 2, c + min_side / 2
    return x0, y0, x1, y1


def write_graphml(path, model, scale, min_side=0.0):
    """Same layout as the PID2Graph keys: label + xmin/xmax/ymin/ymax in pixels; undirected edges."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
             '  <key id="d0" for="node" attr.name="label" attr.type="string" />',
             '  <key id="d1" for="node" attr.name="xmin" attr.type="double" />',
             '  <key id="d2" for="node" attr.name="xmax" attr.type="double" />',
             '  <key id="d3" for="node" attr.name="ymin" attr.type="double" />',
             '  <key id="d4" for="node" attr.name="ymax" attr.type="double" />',
             '  <graph edgedefault="undirected">']
    for nid, n in model["nodes"].items():
        box = n["box"]
        if box is None:   # a tee with no drawn shape: a zero-size pass-through node at no particular place
            px = (0.0, 0.0, 0.0, 0.0)
        else:
            px = min_size(to_pixels(box, model["extent"], scale), min_side)
        lines.append(f'    <node id="{nid}"><data key="d0">{n["class"]}</data>'
                     f'<data key="d1">{px[0]:.2f}</data><data key="d2">{px[2]:.2f}</data>'
                     f'<data key="d3">{px[1]:.2f}</data><data key="d4">{px[3]:.2f}</data></node>')
    for i, (a, b) in enumerate(model["edges"]):
        lines.append(f'    <edge id="e{i}" source="{a}" target="{b}" />')
    lines += ["  </graph>", "</graphml>", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def render(source, dest, long_side):
    import fitz  # PyMuPDF
    doc = fitz.open(str(source))
    page = doc[0]
    zoom = long_side / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    pix.save(str(dest))
    return pix.width, pix.height, page


# ---------------------------------------------------------------- tag lists (xlsx without third-party code)

def xlsx_rows(path, sheet_name="Sheet1"):
    """Rows (lists of cell strings) of one worksheet, read with the standard library."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = None
        for s in wb.find("m:sheets", ns):
            if s.get("name") == sheet_name:
                rid = s.get(f"{{{ns['r']}}}id")
                target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        if target is None:
            raise ValueError(f"{path.name}: no sheet {sheet_name}")
        target = target.lstrip("/")
        sheet = ET.fromstring(z.read(target if target.startswith("xl/") else "xl/" + target))
    rows = []
    for row in sheet.iter(f"{{{ns['m']}}}row"):
        cells = {}
        for c in row.findall("m:c", ns):
            ref = re.match(r"([A-Z]+)", c.get("r")).group(1)
            col = 0
            for ch in ref:
                col = col * 26 + ord(ch) - 64
            v = c.find("m:v", ns)
            if c.get("t") == "s" and v is not None:
                val = shared[int(v.text)]
            elif c.get("t") == "inlineStr":
                val = "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
            else:
                val = v.text if v is not None else ""
            cells[col - 1] = (val or "").strip()
        if cells:
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return rows


def norm_id(text):
    return re.sub(r"[\s\-._/,:]", "", (text or "").upper())


def list_items(path, kind):
    """(identifier, drawing name, class) rows from one published list."""
    rows = xlsx_rows(path)
    header = rows[0]

    def col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        raise ValueError(f"{path.name}: none of {names} in header {header}")

    tech = col("Technical Item")
    drawing = col("P&ID Name", "PID Name", "Drawing Name")
    type_col = header.index("Equipment Type") if "Equipment Type" in header else None
    out = []
    for r in rows[1:]:
        ident = r[tech] if tech < len(r) else ""
        dname = r[drawing] if drawing < len(r) else ""
        if not ident or "itemtag" in ident.lower().replace(" ", ""):
            continue
        if kind == "equipment":
            etype = r[type_col] if type_col is not None and type_col < len(r) else ""
            cls = "pump" if "pump" in etype.lower() else "tank"
        else:
            cls = {"instrument": "instrumentation", "valve": "valve"}[kind]
        out.append((ident, dname, cls))
    return out


def build_taglist(cfg, sheet, page):
    words = {norm_id(w[4]) for w in page.get_text("words")}
    items, excluded = {}, []
    for kind, spec in cfg["tag_list_keyed"]["lists"].items():
        for ident, dname, cls in list_items(local_path(spec["path"]), kind):
            if dname != sheet["drawing_name"]:
                continue
            key = norm_id(ident)
            if key in items:
                continue
            if key in words:
                items[key] = {"identifier": ident, "class": cls, "list": kind}
            else:
                excluded.append({"identifier": ident, "list": kind, "reason": "not printed in the PDF text layer"})
    return {"sheet": sheet["id"], "drawing_name": sheet["drawing_name"], "items": list(items.values()),
            "excluded_not_printed": excluded}


# ---------------------------------------------------------------- commands

def build(cfg):
    SHEETS.mkdir(parents=True, exist_ok=True)
    long_side = cfg["render"]["long_side_px"]
    manifest = {"source_commit": cfg["source_commit"], "license": cfg["license"], "sheets": {}}
    for s in cfg["geometry_keyed"]:
        for rel, expected in ((s["xml"], s["xml_sha256"]), (s["image"], s["image_sha256"])):
            if sha(local_path(rel)) != expected:
                sys.exit(f"{rel}: hash differs from the config; run fetch")
        png = SHEETS / f"{s['id']}.png"
        w, h, page = render(local_path(s["image"]), png, long_side)
        model = convert_xml(local_path(s["xml"]))
        ext = model["extent"]
        scale = w / (ext[2] - ext[0])
        if abs(h - (ext[3] - ext[1]) * scale) > 2:
            sys.exit(f"{s['id']}: render {w}x{h} does not match the drawing extent {ext}")
        write_graphml(SHEETS / f"{s['id']}.graphml", model, scale, cfg["render"]["min_box_side_frac"] * max(w, h))
        tags = {nid: n["tag"] for nid, n in model["nodes"].items() if n["class"] != "connector"}
        (SHEETS / f"{s['id']}.tags.json").write_text(json.dumps(
            {"sheet": s["id"], "rule": "visible label text; see scripts/adapt_dexpi.py docstring",
             "tags": tags, "dexpi_class": {nid: n["dexpi_class"] for nid, n in model["nodes"].items()}},
            indent=1), encoding="utf-8")
        scored = [n for n in model["nodes"].values() if n["class"] != "connector"]
        manifest["sheets"][s["id"]] = {
            "kind": "geometry", "png_px": [w, h], "png_sha256": sha(png),
            "symbols": len(scored), "connectors": len(model["nodes"]) - len(scored), "edges": len(model["edges"]),
            "with_tag_truth": sum(1 for n in scored if n["tag"]), "unresolved_references": model["unresolved"]}
        print(f"{s['id']}: {w}x{h}px, {len(scored)} symbols, {len(model['edges'])} edges, "
              f"{manifest['sheets'][s['id']]['with_tag_truth']} with tag text, unresolved {model['unresolved']}")
    for s in cfg["tag_list_keyed"]["sheets"]:
        if sha(local_path(s["pdf"])) != s["pdf_sha256"]:
            sys.exit(f"{s['pdf']}: hash differs from the config; run fetch")
        png = SHEETS / f"{s['id']}.png"
        w, h, page = render(local_path(s["pdf"]), png, long_side)
        key = build_taglist(cfg, s, page)
        (SHEETS / f"{s['id']}.taglist.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
        manifest["sheets"][s["id"]] = {"kind": "tag_list", "png_px": [w, h], "png_sha256": sha(png),
                                       "identifiers": len(key["items"]),
                                       "excluded_not_printed": len(key["excluded_not_printed"])}
        print(f"{s['id']}: {w}x{h}px, {len(key['items'])} listed identifiers printed on the sheet, "
              f"{len(key['excluded_not_printed'])} listed but not printed")
    (BASE / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def overlay(cfg):
    from PIL import Image, ImageDraw
    sys.path.insert(0, str(ROOT / "scripts"))
    import score_pid2graph as sc
    colours = {"tank": "red", "pump": "magenta", "valve": "blue", "instrumentation": "green",
               "inlet/outlet": "orange", "general": "purple"}
    out = BASE / "overlay"
    out.mkdir(exist_ok=True)
    for s in cfg["geometry_keyed"]:
        png = SHEETS / f"{s['id']}.png"
        im = Image.open(png).convert("RGB")
        w, h = im.size
        nodes, adj = sc.load_key(SHEETS / f"{s['id']}.graphml", w, h)
        d = ImageDraw.Draw(im)
        for nid, n in nodes.items():
            if n["class"] not in colours:
                continue
            b = [n["box"][0] * w / 1000, n["box"][1] * h / 1000, n["box"][2] * w / 1000, n["box"][3] * h / 1000]
            d.rectangle(b, outline=colours[n["class"]], width=3)
            d.text((b[0], b[3] + 2), nid, fill=colours[n["class"]])
        im.save(out / f"{s['id']}_keyboxes.png")
        print(out / f"{s['id']}_keyboxes.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["fetch", "build", "overlay"])
    a = ap.parse_args()
    cfg = config()
    {"fetch": fetch, "build": build, "overlay": overlay}[a.command](cfg)


if __name__ == "__main__":
    main()
