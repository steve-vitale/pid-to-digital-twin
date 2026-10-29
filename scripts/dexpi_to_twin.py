"""One DEXPI-derived answer key -> an intake prediction + manifest for import_site_drawing.py, with no model at all.

Usage (after `python scripts/adapt_dexpi.py fetch` and `build`, which download and convert the public DEXPI sheets):
  python scripts/dexpi_to_twin.py --sheet dexpi-c01                       # writes prediction + intake manifest
  python scripts/dexpi_to_twin.py --sheet dexpi-c01 --intake my-bundle    # ...and runs the intake into my-bundle/
  python -S scripts/import_site_drawing.py --manifest data/external/dexpi/twin/dexpi-c01.intake-manifest.json --out my-bundle

Input: the files scripts/adapt_dexpi.py writes for one geometry-keyed sheet in data/external/dexpi/sheets/
(<id>.graphml, <id>.tags.json, <id>.png). If the pinned DEXPI XML is cached too, it is read (stdlib only) to report
what the key never carried. Output, by default in the gitignored data/external/dexpi/twin/:
  <id>.prediction.json       symbols {id, class, tag, box, confidence} + connections {from, to}: the intake contract
                             (extraction/prompt_v2.md), plus a "conversion" block saying what was dropped and why
  <id>.intake-manifest.json  site-drawing-intake-1 manifest, producer {method: "converted from DEXPI XML, no model",
                             tool: "dexpi_to_twin.py", model: null}

What it does:
  symbols      every key node in the six classes, unchanged: DEXPI ID as symbol id, class as adapt_dexpi assigned it,
               box as the key's pixel box rescaled to 0-1000 (clamped to the page if a widened box crosses the edge)
  tags         the drawn label text from <id>.tags.json, exactly; null where the drawing has no label
  connections  the key's undirected adjacency with pass-through PipeTee nodes collapsed (the same rule the scorer
               uses, score_pid2graph.asset_links): a tee with three neighbours becomes three pairwise links
  confidence   null: nothing was estimated, and a number would look like a model's

What it does NOT do (each lossy step is printed and written into the prediction's "conversion" block):
  - It is not a DEXPI importer. Classes are only the six scored ones: every pump/compressor/blower/fan -> pump,
    every other top-level equipment (vessels, columns, heat exchangers) -> tank, in-line fittings -> general.
    The exact DEXPI class survives only as an extra field the intake preserves in its source copy.
  - Nozzles, actuators, equipment internals, flow arrows, signal-generating functions and loop groupings are not
    symbols; pipe segments and signal lines survive only as undirected links. Flow direction (DEXPI From/To) is
    discarded because the intake's connections are undirected.
  - Attributes (line numbers, nominal diameters, fluid codes, design limits, fail actions) are not carried: the
    intake contract has no field for them.
  - Tags are drawn label text, not a governed tag register. Where the XML holds an identifier in an attribute but
    draws no label, the symbol stays untagged (the identifier is listed, not used). On manual valves the drawn
    label is often a piping-spec code, not an instrument tag.
  - It reads one geometry-keyed sheet. The tag-list-keyed sheets (C08) have no geometry or links and are refused.
  - It makes no claim about extraction accuracy: this is the zero-model ceiling, not a test of reading drawings.
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import adapt_dexpi as A
import score_pid2graph as sc

PRODUCER = {"method": "converted from DEXPI XML, no model", "tool": "dexpi_to_twin.py", "model": None}
DEFAULT_OUT = A.BASE / "twin"

# Why an XML element with an ID is not a symbol in the key. Anything else unmapped says "no mapping".
NOT_A_SYMBOL = {
    "Nozzle": "nozzle: folded into its equipment as a link endpoint",
    "PipingNetworkSystem": "pipe system: survives only as undirected links",
    "PipingNetworkSegment": "pipe segment: survives only as undirected links (direction dropped)",
    "InformationFlow": "signal or measuring line: survives only as an undirected link",
    "ActuatingSystem": "actuating system: its number label tags the valve; otherwise dropped",
    "ActuatingSystemComponent": "actuator or valve reference: folded into the valve it operates",
    "InstrumentationLoopFunction": "instrument loop grouping: dropped",
    "ProcessSignalGeneratingFunction": "signal-generating function (sensor element): dropped",
    "SignalConveyingFunction": "signal line: survives only as an undirected link",
    "PipeFlowArrow": "flow arrow: dropped",
    "Equipment": "equipment internal (section, chamber, impeller...): not a separate symbol",
    "PipingComponent": "piping component with no class mapping",
    "Node": "connection point of an item: not a symbol",
    "PlantStructureItem": "plant hierarchy level (enterprise, site, plant, section): dropped",
    "ActuatingFunction": "actuating function: dropped",
    "PipeOffPageConnectorReference": "off-page target reference: dropped (the intake reads no drawing link)",
    "Symbol": "annotation symbol: dropped",
    "PipeSlopeSymbol": "slope mark: dropped",
    "InsulationSymbol": "insulation mark: dropped",
    "MetaData": "file metadata: not drawing content",
}
TAG_ATTRS = ("TagNameAssignmentClass", "SubTagNameAssignmentClass", "PipingComponentNumberAssignmentClass",
             "ProcessInstrumentationFunctionNumberAssignmentClass")


def sheet_spec(sheet_id):
    cfg = A.config()
    spec = next((s for s in cfg["geometry_keyed"] if s["id"] == sheet_id), None)
    if spec is None:
        tag_list = [s["id"] for s in cfg["tag_list_keyed"]["sheets"]]
        why = " (a tag-list-keyed sheet: no geometry or links in its key)" if sheet_id in tag_list else ""
        raise SystemExit(f"{sheet_id}: not a geometry-keyed DEXPI sheet{why}. Choose one of "
                         + ", ".join(s["id"] for s in cfg["geometry_keyed"]))
    return cfg, spec


def key_paths(sheet_id, sheets_dir=None):
    d = Path(sheets_dir) if sheets_dir else A.SHEETS
    return {k: d / f"{sheet_id}.{k}" for k in ("graphml", "png")} | {"tags": d / f"{sheet_id}.tags.json"}


def xml_inventory(xml_path, key_ids, drawn_tags=None):
    """What the DEXPI XML holds that the key does not carry as a symbol. Stdlib only; reporting, not conversion.
    drawn_tags: {kept symbol id: drawn tag or None}; identifiers are listed only for kept symbols drawn untagged."""
    drawn_tags = drawn_tags or {}
    root = ET.parse(xml_path).getroot()
    cat = root.find("ShapeCatalogue")
    in_cat = set(cat.iter()) if cat is not None else set()
    not_symbols, attributes, untagged_ids, directed = Counter(), Counter(), {}, 0
    for el in root.iter():
        if el in in_cat or not el.get("ID"):
            continue
        if el.get("ID") in key_ids:
            ga = {g.get("Name"): g.get("Value") for g in el.iter("GenericAttribute") if g.get("Value")}
            for name in ga:
                attributes[name] += 1
            ident = next(((n, ga[n]) for n in TAG_ATTRS if ga.get(n)), None)
            if ident and el.get("ID") in drawn_tags and not drawn_tags[el.get("ID")]:
                untagged_ids[el.get("ID")] = f"{ident[1]} ({ident[0]})"
            continue
        if el.tag in ("Drawing", "ShapeCatalogue", "PlantInformation", "Label", "Text"):
            continue
        reason = NOT_A_SYMBOL.get(el.tag, f"{el.tag}: no mapping to the six classes")
        if el.tag == "PipingComponent" and el.get("ComponentClass") == "PipeTee":
            reason = "PipeTee: pass-through, links collapsed through it"
        not_symbols[reason] += 1
        if el.tag == "PipingNetworkSegment":
            c = el.find("Connection")
            directed += int(c is not None and bool(c.get("FromID")) and bool(c.get("ToID")))
    return {"not_symbols": dict(not_symbols.most_common()),
            "attributes_not_carried_on_kept_items": dict(attributes.most_common()),
            "identifiers_on_untagged_symbols": untagged_ids, "directed_segments_made_undirected": directed}


def convert(sheet_id, sheets_dir=None, xml_path=None):
    """Return (prediction, report). Raises SystemExit if the built key is missing."""
    p = key_paths(sheet_id, sheets_dir)
    missing = [str(v) for v in p.values() if not v.is_file()]
    if missing:
        raise SystemExit("DEXPI key not built: missing " + ", ".join(missing)
                         + "\nRun: python scripts/adapt_dexpi.py fetch && python scripts/adapt_dexpi.py build")
    w, h = sc.png_size(p["png"])
    nodes, adj = sc.load_key(p["graphml"], w, h)
    tagfile = json.loads(p["tags"].read_text(encoding="utf-8"))
    tags, dexpi_class = tagfile["tags"], tagfile.get("dexpi_class", {})

    symbols, clamped, dropped_nodes = [], [], Counter()
    for nid, n in nodes.items():
        if n["class"] not in sc.SCORED:
            dropped_nodes[f"{n['class']} ({dexpi_class.get(nid, '?')}): pass-through, links collapsed through it"] += 1
            continue
        box = [round(min(1000.0, max(0.0, v)), 3) for v in n["box"]]
        if box != [round(v, 3) for v in n["box"]]:
            clamped.append(nid)
        symbols.append({"id": nid, "class": n["class"], "tag": tags.get(nid), "box": box, "confidence": None,
                        "dexpi_class": dexpi_class.get(nid)})
    kept = {s["id"] for s in symbols}

    key_edges = {frozenset((a, b)) for a in adj for b in adj[a]}
    direct = {e for e in key_edges if e <= kept}
    links = {frozenset(l) for l in sc.asset_links(nodes, adj)}
    collapsed = links - direct
    lost = direct - links   # must be empty: every direct asset edge is also an asset link
    connections = [{"from": a, "to": b} for a, b in sorted(tuple(sorted(l)) for l in links)]

    report = {
        "key_in": {"nodes": len(nodes), "symbols_in_six_classes": len(kept),
                   "pass_through_nodes": len(nodes) - len(kept), "edges": len(key_edges),
                   "edges_between_symbols": len(direct), "edges_touching_pass_through": len(key_edges) - len(direct),
                   "symbols_with_tag": sum(1 for s in symbols if s["tag"])},
        "out": {"symbols": len(symbols), "tags": sum(1 for s in symbols if s["tag"]), "connections": len(connections),
                "connections_kept_as_drawn": len(direct & links), "connections_added_by_collapsing_tees": len(collapsed)},
        "dropped": {"key_nodes": dict(dropped_nodes), "edges_between_symbols_lost": sorted(sorted(e) for e in lost),
                    "boxes_clamped_to_page": clamped},
        "lossy_steps": [
            "Classes collapsed to the six scored classes; the exact DEXPI class is kept only as dexpi_class, which "
            "the intake preserves in its source copy but does not use.",
            "Tees are not symbols: each tee's neighbours are linked pairwise, so a junction becomes a clique of links.",
            "Connections are undirected; DEXPI segment direction is discarded.",
            "Tags are drawn label text only; untagged symbols stay untagged even when the XML has an identifier.",
            "Line, size, fluid, design and fail-action attributes are not carried; the intake has no field for them.",
            "confidence is null: nothing was estimated.",
        ],
    }
    by_class = Counter(s["class"] for s in symbols)
    report["out"]["by_class"] = dict(sorted(by_class.items()))
    if xml_path and Path(xml_path).is_file():
        report["xml"] = xml_inventory(xml_path, set(nodes), {s["id"]: s["tag"] for s in symbols})
    else:
        report["xml"] = "DEXPI XML not cached; drop inventory against the source not computed"
    prediction = {"symbols": symbols, "connections": connections,
                  "producer": PRODUCER, "source": {"sheet": sheet_id, "key_graphml_sha256": A.sha(p["graphml"]),
                                                   "key_tags_sha256": A.sha(p["tags"]), "image_sha256": A.sha(p["png"])},
                  "conversion": report}
    return prediction, report


def write_outputs(sheet_id, prediction, out_dir, cfg, spec, png_path):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / f"{sheet_id}.prediction.json"
    pred_path.write_text(json.dumps(prediction, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    manifest = {"schema_version": "site-drawing-intake-1", "drawing_id": sheet_id, "revision": "public",
                "page": 1, "image": Path(os.path.relpath(png_path, out_dir)).as_posix(),
                "extraction": pred_path.name, "extraction_format": "prediction", "producer": PRODUCER,
                "drawing_number": Path(spec["xml"]).stem,
                "system_name": f"Public example: {spec['title']} ({cfg['license']}, DEXPI TrainingTestCases)"}
    man_path = out_dir / f"{sheet_id}.intake-manifest.json"
    man_path.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return pred_path, man_path


def print_report(sheet_id, r):
    k, o, d = r["key_in"], r["out"], r["dropped"]
    print(f"{sheet_id}: key {k['nodes']} nodes ({k['symbols_in_six_classes']} in the six classes, "
          f"{k['pass_through_nodes']} pass-through), {k['edges']} edges, {k['symbols_with_tag']} drawn tags")
    print(f"  out: {o['symbols']} symbols {o['by_class']}, {o['tags']} tags, {o['connections']} connections "
          f"({o['connections_kept_as_drawn']} as drawn, {o['connections_added_by_collapsing_tees']} from collapsing tees)")
    for reason, n in d["key_nodes"].items():
        print(f"  dropped from key: {n} x {reason}")
    if d["edges_between_symbols_lost"]:
        print(f"  LOST edges between symbols: {d['edges_between_symbols_lost']}")
    if d["boxes_clamped_to_page"]:
        print(f"  boxes clamped to the page: {d['boxes_clamped_to_page']}")
    x = r["xml"]
    if isinstance(x, dict):
        for reason, n in x["not_symbols"].items():
            print(f"  in XML, not a symbol: {n} x {reason}")
        print(f"  directed pipe segments made undirected: {x['directed_segments_made_undirected']}")
        attrs = x["attributes_not_carried_on_kept_items"]
        print(f"  attribute values not carried (kept items and their nozzles): {sum(attrs.values())} across {len(attrs)} names")
        for sid, ident in x["identifiers_on_untagged_symbols"].items():
            print(f"  untagged symbol {sid} has an identifier only in XML attributes: {ident} (not used)")
    else:
        print(f"  {x}")
    for step in r["lossy_steps"]:
        print(f"  lossy: {step}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True, help="geometry-keyed sheet id, e.g. dexpi-c01")
    ap.add_argument("--sheets-dir", help="folder with the built key (default data/external/dexpi/sheets)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT), help="where to write prediction + manifest")
    ap.add_argument("--intake", metavar="BUNDLE", help="also run import_site_drawing.py into this new folder")
    a = ap.parse_args(argv)
    cfg, spec = sheet_spec(a.sheet)
    prediction, report = convert(a.sheet, a.sheets_dir, A.local_path(spec["xml"]))
    png = key_paths(a.sheet, a.sheets_dir)["png"]
    pred_path, man_path = write_outputs(a.sheet, prediction, a.out_dir, cfg, spec, png)
    print_report(a.sheet, report)
    print(f"wrote {pred_path}\nwrote {man_path}")
    if a.intake:
        import import_site_drawing
        result = import_site_drawing.import_drawing(man_path, a.intake)
        print(json.dumps({"output": result["output"], "summary": result["summary"],
                          "operational_export_allowed": result["operational_export_allowed"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
