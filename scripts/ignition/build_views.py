"""Perspective screens for the twin: the generated drawing as the background, with a live value label on each
instrument, bound to its tag in the Twin provider.

  TE/Overview          the Tennessee Eastman overview. Live values; a label turns red while its tag's alarm is active.
  OPEN100/Sheet_<n>    one per extracted drawing. Every instrument label is bound to its placeholder tag, so
                       Perspective draws its bad-quality overlay: the screen shows what is not connected yet.

The screens are written as a project export (zip) to out/ignition/gateway/PIDTwin.zip and imported by
build_gateway.py. Bindings are the contract the verifier checks (V3): every binding must name an existing tag and
every instrument on a drawing must have one.
"""
import base64
import io
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "PIDTwin"
RESOURCE = {"scope": "G", "version": 1, "restricted": False, "overridable": True, "files": ["view.json"],
            "attributes": {}}


def svg_size(svg):
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    return float(m.group(1)), float(m.group(2))


def image(svg, w, h):
    return {"type": "ia.display.image", "meta": {"name": "Drawing"},
            "position": {"x": 0, "y": 0, "width": w, "height": h},
            "props": {"source": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(),
                      "fit": {"mode": "fill"}}}


def value_label(name, x, y, tag_path, uom="", alarm_path=None):
    """A label showing the tag's value. A Bad-quality binding gets Perspective's quality overlay automatically."""
    comp = {"type": "ia.display.label", "meta": {"name": name},
            "position": {"x": round(x, 1), "y": round(y, 1), "width": 46, "height": 14},
            "props": {"text": "", "style": {"fontSize": 9.5, "fontFamily": "Arial", "paddingLeft": 2,
                                            "borderStyle": "solid", "borderWidth": 1, "borderColor": "#94a3b8",
                                            "backgroundColor": "#ffffffdd"}},
            "propConfig": {"props.text": {"binding": {
                "type": "tag", "config": {"mode": "direct", "tagPath": tag_path, "fallbackDelay": 2.5},
                "transforms": [{"type": "format", "formatType": "numeric", "formatValue": "#,##0.0"}]}}}}
    if uom:
        comp["meta"]["tooltip"] = {"enabled": True, "text": f"{tag_path} ({uom})"}
    if alarm_path:
        # A tag binding plus a map transform (an expression binding errored on every label in testing).
        comp["propConfig"]["props.style.backgroundColor"] = {"binding": {
            "type": "tag", "config": {"mode": "direct", "tagPath": alarm_path, "fallbackDelay": 2.5},
            "transforms": [{"type": "map", "inputType": "scalar", "outputType": "color",
                            "mappings": [{"input": True, "output": "#fecaca"}], "fallback": "#ffffffdd"}]}}
    return comp


def view(w, h, children):
    return {"custom": {}, "params": {}, "props": {"defaultSize": {"width": int(w), "height": int(h)}},
            "root": {"type": "ia.container.coord", "meta": {"name": "root"}, "props": {"mode": "fixed"},
                     "children": children}}


def te_overview(provider, alarmed):
    svg = (ROOT / "out" / "svg" / "overview.svg").read_text(encoding="utf-8")
    w, h = svg_size(svg)
    kids = [image(svg, w, h)]
    for m in re.finditer(r'<g id="([^"]+)" data-tag="([^"]+)" data-unit="([^"]+)" data-uom="([^"]*)" '
                         r'transform="translate\(([\d.]+),([\d.]+)\)"', svg):
        _, tag, unit, uom, x, y = m.groups()
        base = f"[{provider}]TE_Plant/{unit}/{tag}"
        below = 27 if int(re.sub(r"\D", "", tag)) >= 200 else 20  # valves (2xx) have their tag text underneath
        kids.append(value_label(tag, float(x) - 23, float(y) + below, base + "/PV", uom,
                                base + "/AlarmActive" if tag in alarmed else None))
    return view(w, h, kids)


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


def open100_sheets(twin_dir, provider_doc, provider):
    paths = asset_paths(provider_doc, provider)
    views = {}
    for f in sorted((twin_dir / "svg").glob("sheet_*.svg"), key=lambda p: int(p.stem.split("_")[1])):
        svg = f.read_text(encoding="utf-8")
        w, h = svg_size(svg)
        kids = [image(svg, w, h)]
        for m in re.finditer(r'<g id="[^"]+" data-asset="([^"]+)"[^>]*data-class="instrumentation"[^>]*>.*?'
                             r'<circle class="inst" cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', svg):
            asset, cx, cy, r = m.group(1), *map(float, m.groups()[1:])
            if asset in paths and not any(k["meta"]["name"] == asset for k in kids):
                kids.append(value_label(asset, cx + r + 2, cy - 7, paths[asset] + "/PV"))
        views[f"OPEN100/Sheet_{f.stem.split('_')[1]}"] = view(w, h, kids)
    return views


def project_zip(provider_doc, twin_dir, provider, alarmed):
    views = {"TE/Overview": te_overview(provider, alarmed)}
    views.update(open100_sheets(twin_dir, provider_doc, provider))
    pages = {"/": {"title": "TE plant", "viewPath": "TE/Overview"}}
    for p in views:
        if p.startswith("OPEN100/"):
            pages["/open100/" + p.split("_")[-1]] = {"title": p, "viewPath": p}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", json.dumps({
            "title": "P&ID digital twin", "enabled": True, "inheritable": False, "parent": "",
            "description": "Screens generated from the twin's drawings. Read-only monitoring."}, indent=2))
        for p, v in views.items():
            base = f"com.inductiveautomation.perspective/views/{p}/"
            z.writestr(base + "view.json", json.dumps(v, indent=1))
            z.writestr(base + "resource.json", json.dumps(RESOURCE, indent=2))
        pc = "com.inductiveautomation.perspective/page-config/"
        z.writestr(pc + "config.json", json.dumps({"pages": pages}, indent=1))
        z.writestr(pc + "resource.json", json.dumps(dict(RESOURCE, files=["config.json"]), indent=2))
    return buf.getvalue(), views
