"""Perspective project for the twin: the operator screens (scripts/ignition/build_hmi.py), the process schematic and
one screen per extracted drawing.

  TE/Overview, TE/Unit_<id>, TE/Alarms   operator screens, ISA-101 style (build_hmi.py)
  TE/Schematic         the Tennessee Eastman schematic with a live value on each instrument; a label turns red while its
                       tag's alarm is active.
  OPEN100/Index        the 12 drawings as thumbnails.
  OPEN100/Sheet_<n>    one per extracted drawing: the ORIGINAL drawing (greyed, data/drawings/) with every extracted
                       instrument's label bound to its tag. Unmapped placeholders get Perspective's bad-quality overlay:
                       the screen shows what is not connected yet. Falls back to the redrawn SVG if the image is missing.

The screens are written as a project export (zip) to out/ignition/gateway/PIDTwin.zip and imported by
build_gateway.py. Bindings are the contract the verifier checks (V3): every binding must name an existing tag, every
TE value must be on its unit screen, and every instrument on a drawing must have a label.

Model use: none at build time. The instruments placed on the drawings come from the multi-model extraction (see
build_hmi.py's header); this file only lays them out.
"""
import base64
import io
import json
import re
import zipfile
from pathlib import Path

import build_hmi
from build_hmi import HEAD, header, label, tag_binding, color_map, data_uri, view

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "PIDTwin"
RESOURCE = {"scope": "G", "version": 1, "restricted": False, "overridable": True, "files": ["view.json"],
            "attributes": {}}
SHEET_W = 1400  # drawing width on screen; the legend takes the rest of the 1600 px


def svg_size(svg):
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    return float(m.group(1)), float(m.group(2))


def image(svg, w, h, top=0):
    return {"type": "ia.display.image", "meta": {"name": "Drawing"},
            "position": {"x": 0, "y": top, "width": w, "height": h},
            "props": {"source": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(),
                      "fit": {"mode": "fill"}}}


def value_label(name, x, y, tag_path, uom="", alarm_path=None):
    """A label showing the tag's value. A Bad-quality binding gets Perspective's quality overlay automatically."""
    comp = label(name, x, y, 46, 14, "", {"fontSize": 9.5, "paddingLeft": 2, "borderStyle": "solid", "borderWidth": 1,
                                          "borderColor": "#94a3b8", "backgroundColor": "#ffffffdd"},
                 tooltip=f"{tag_path} ({uom})" if uom else None)
    comp["propConfig"] = {"props.text": tag_binding(tag_path, [
        {"type": "format", "formatType": "numeric", "formatValue": "#,##0.0"}])}
    if alarm_path:
        # A tag binding plus a map transform (an expression binding errored on every label in testing).
        comp["propConfig"]["props.style.backgroundColor"] = tag_binding(alarm_path, [
            color_map([{"input": True, "output": "#fecaca"}], "#ffffffdd")])
    return comp


def te_schematic(provider, alarmed, hidden=frozenset()):
    svg = (ROOT / "out" / "svg" / "overview.svg").read_text(encoding="utf-8")
    w, h = svg_size(svg)
    kids = header(provider, "Process schematic", "/schematic") + [image(svg, w, h, HEAD)]
    for m in re.finditer(r'<g id="([^"]+)" data-tag="([^"]+)" data-unit="([^"]+)" data-uom="([^"]*)" '
                         r'transform="translate\(([\d.]+),([\d.]+)\)"', svg):
        _, tag, unit, uom, x, y = m.groups()
        if tag in hidden:  # operations asked not to show it on the operator screen
            continue
        base = f"[{provider}]TE_Plant/{unit}/{tag}"
        below = 27 if int(re.sub(r"\D", "", tag)) >= 200 else 20  # valves (2xx) have their tag text underneath
        kids.append(value_label(tag, float(x) - 23, HEAD + float(y) + below, base + "/PV", uom,
                                base + "/AlarmActive" if tag in alarmed else None))
    return view(max(HEAD + h, 600), kids)


def asset_paths(provider_doc, provider):
    """AssetId -> instance path for the extracted twin, from the import file."""
    out = {}

    def walk(node, path):
        for t in node.get("tags", []):
            p = f"{path}/{t['name']}" if path else t["name"]
            if t["tagType"] == "UdtInstance" and t["typeId"].startswith("Instrument_"):
                out[t["parameters"]["AssetId"]["value"]] = f"[{provider}]{p}"
            elif t["tagType"] == "Folder":
                walk(t, p)
    walk(next(x for x in provider_doc["tags"] if x["name"] == "OPEN100"), "OPEN100")
    return out


def open100_sheets(twin_dir, provider_doc, provider, hidden=frozenset(), mapped=frozenset()):
    paths = asset_paths(provider_doc, provider)
    model = json.loads((twin_dir / "plant_model.json").read_text(encoding="utf-8"))
    tags = {i["id"]: i.get("tag") or i["id"] for i in model["instruments"]}
    titles = {s["sheet"]: (s.get("system_code") or "") + (f" {s['drawing_number']}" if s.get("drawing_number")
                                                          else "") for s in model["systems"]}
    views, index = {}, []
    for f in sorted((twin_dir / "svg").glob("sheet_*.svg"), key=lambda p: int(p.stem.split("_")[1])):
        n = f.stem.split("_")[1]
        svg = f.read_text(encoding="utf-8")
        w, h = svg_size(svg)
        scale = SHEET_W / w
        insts, seen = [], set()
        for m in re.finditer(r'<g id="[^"]+" data-asset="([^"]+)"[^>]*data-class="instrumentation"[^>]*>.*?'
                             r'<circle class="inst" cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', svg):
            asset, cx, cy, r = m.group(1), *map(float, m.groups()[1:])
            if asset in paths and asset not in hidden and asset not in seen:
                seen.add(asset)
                insts.append((asset, tags.get(asset, asset), cx * scale, cy * scale, r * scale, paths[asset],
                              asset in mapped))
        jpg = ROOT / "data" / "drawings" / f"open100_{n}.jpg"
        uri = data_uri(jpg, "image/jpeg") if jpg.exists() else \
            "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
        live = sum(1 for i in insts if i[6])
        views[f"OPEN100/Sheet_{n}"] = build_hmi.sheet_screen(provider, n, titles.get(n, "").strip(), uri,
                                                             (SHEET_W, round(h * scale)), insts,
                                                             (live, len(insts) - live))
        thumb = ROOT / "data" / "drawings" / f"thumb_{n}.jpg"  # never the full image: see prepare_drawings.py
        index.append((n, titles.get(n, "").strip(), data_uri(thumb, "image/jpeg") if thumb.exists() else uri))
    views["OPEN100/Index"] = build_hmi.drawings_index(provider, index)
    return views


def project_zip(provider_doc, twin_dir, provider, alarmed, hidden=frozenset(), meta=None):
    """hidden: tags and asset ids operations asked not to show on screens (scripts/apply_review.py).
    meta: build_gateway's build_meta (ranges with normal bands, alarm setpoints, point mappings)."""
    meta = meta or {}
    ranges = json.loads(json.dumps(meta.get("te_ranges", {})))
    views, pages = build_hmi.te_views(provider, ranges, meta.get("alarms", {}), hidden)
    views["TE/Schematic"] = te_schematic(provider, alarmed, hidden)
    pages["/schematic"] = ("Process schematic", "TE/Schematic")
    views.update(open100_sheets(twin_dir, provider_doc, provider, hidden,
                                set(meta.get("twin_review", {}).get("mapped", {}))))
    pages["/drawings"] = ("Extracted drawings", "OPEN100/Index")
    for p in views:
        if p.startswith("OPEN100/Sheet_"):
            pages["/open100/" + p.split("_")[-1]] = (p, p)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        def put(name, data):
            # Fixed entry timestamps: the same inputs must give byte-identical output, or every rebuild looks like a
            # config change and V9 (config matches a commit) fails. V9 caught this.
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
        put("project.json", json.dumps({
            "title": "P&ID digital twin", "enabled": True, "inheritable": False, "parent": "",
            "description": "Operator screens and drawing screens generated from the twin. Read-only monitoring."},
            indent=2))
        for p, v in views.items():
            base = f"com.inductiveautomation.perspective/views/{p}/"
            put(base + "view.json", json.dumps(v, indent=1))
            put(base + "resource.json", json.dumps(RESOURCE, indent=2))
        pc = "com.inductiveautomation.perspective/page-config/"
        put(pc + "config.json", json.dumps({"pages": {k: {"title": t, "viewPath": v} for k, (t, v) in
                                                      pages.items()}}, indent=1))
        put(pc + "resource.json", json.dumps(dict(RESOURCE, files=["config.json"]), indent=2))
    return buf.getvalue(), views
