"""Export a plant model as an open, versioned graph (twin-graph-1): assets, typed edges, every attribute as a sourced
claim, open questions and review events, for loading into any asset register, graph database or change system.

    python scripts/graph_export.py data/te_process_model.json --out te_graph.json
    python scripts/graph_export.py my-bundle/plant_model.json --reviews out/review --out my_graph.json
    python scripts/graph_export.py --check te_graph.json            # validate a file against twin-graph-1

Works on both model kinds this repository writes: a hand-built process model (data/te_process_model.json,
data/bayer_rt/process_model.json) and an extracted twin (plant_model.json from import_site_drawing.py or
build_twin.py), with the pipe and network line layers when the model holds them (scripts/line_layers.py for a
drawing, scripts/dexpi_reader.py for DEXPI XML). The format is described in docs/GRAPH_EXPORT.md. Nothing is inferred here: each claim carries the
source and status the model already holds, and an item with no status is exported as "unverified". Stdlib only.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from output_paths import protect_outputs

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "twin-graph-1"
STATUSES = ("confirmed", "corrected", "unverified", "rejected", "extracted", "unresolvable")
EDGE_TYPES = ("contains", "connects", "measures", "controls", "acts_on", "sets_point_of", "sits_on", "protects",
              "trips", "applies_to", "piped_to", "on_network", "instrument_connection", "actuated_by", "nozzle_of")
NODE_KINDS = ("plant", "system", "equipment", "instrument", "final_element", "controller", "line_item",
              "offpage_connector", "boundary", "manual_valve", "relief_device", "interlock", "limit", "junction",
              "line_network")
UNPLACED_KINDS = ("equipment", "instrument", "final_element", "controller", "line_item", "offpage_connector",
                  "manual_valve", "relief_device")
# What a `connects` edge means, by where it came from (the edge's `layer`). Extracted drawings: the tracer's pairwise
# link, network co-membership (both ends on one drawn line network, the answer key's definition), NOT pipe adjacency.
# Hand-built models: a process stream recorded from one end to the other (pipe-level). Cross-sheet pairs: two
# off-page connectors matched across drawings. The pipe layer itself is `piped_to` (scripts/line_layers.py); drawn
# lines that are not pipe are `instrument_connection` (a bubble's leader or impulse line), `actuated_by` (a valve's
# actuator stem) and `nozzle_of` (a nozzle stub on its vessel).
LINE_EDGES = ("piped_to", "instrument_connection", "actuated_by", "nozzle_of")
LINE_SECTIONS = {"segments": "piped_to", "instrument_lines": "instrument_connection",
                 "actuator_stems": "actuated_by", "nozzle_stubs": "nozzle_of"}
JUNCTION_NAMES = {"pipe_tee": "pipe tee", "instrument_tap": "instrument tap", "marked_crossing": "marked crossing",
                  "instrument_line_junction": "instrument line junction"}
CONNECTS_LAYERS = {"network_pair": "both ends are on the same drawn line network (pairwise co-membership)",
                   "stream": "a process stream recorded in the model from one end to the other (pipe-level)",
                   "offpage_pair": "two off-page connectors paired across drawings"}
LINE_LAYER_ENDS = ("plant", "system", "line_network", "controller", "interlock", "limit")  # never a line edge's end
# Never attribute claims: identity (id, tag and former_tag make the node and its aliases), the item's own source and
# status (every claim carries them), the review (it reshapes the claims), confidence (exported as its own claim),
# hierarchy and drawing layout. Keys a section turns into edges are passed per section (CONSUMED), so the same key on
# an item whose section has no edge rule for it is still exported.
SKIP = {"id", "tag", "former_tag", "provenance", "verification", "topology_verification", "source", "sources",
        "children", "layout", "confidence", "ops_review"}
CONSUMED = {"controllers": ("measurement", "output.final_element", "output.split_range", "output.setpoint_of"),
            "interlocks": ("measurement", "final_element"), "streams": ("from", "to"),
            "line_networks": ("members", "junctions"), "junctions": ("network",),
            "segments": ("from", "to", "network")}
NOT_EXPORTED = ("events_2008_08_28", "people")  # a model's incident timeline and named people stay out, on purpose
HAND_BUILT_SECTIONS = {"meta", "units", "streams", "instruments", "final_elements", "controllers", "manual_valves",
                       "relief_devices", "interlocks", "limits", "unplaced", "line_layers"}
EXTRACTED_SECTIONS = {"meta", "site", "systems", "units", "streams", "instruments", "final_elements", "line_items",
                      "offpage_connectors", "hierarchy", "summary", "offpage_pairs", "dropped", "line_layers"}


def status_of(item):
    for key in ("verification", "topology_verification"):
        st = (item.get(key) or {}).get("status")
        if st:
            return st
    return item.get("status") or "unverified"


def source_of(item, model_source):
    prov = item.get("provenance") or []
    if prov:
        p = prov[0]
        return {"kind": "drawing", "sheet": p.get("sheet"), "box_0_1000": p.get("box_0_1000"),
                "read_as": p.get("tag_as_extracted"), "run": p.get("source_run"), "model": p.get("model")}
    for key in ("verification", "topology_verification"):
        v = item.get(key) or {}
        if v.get("evidence"):
            return {"kind": "document", "document": v.get("checked_against"), "evidence": v.get("evidence"),
                    "checked_on": v.get("checked_on")}
    src = item.get("source") or item.get("sources")
    if src:
        return {"kind": "document", "document": src}
    return {"kind": "model", "document": model_source, "note": "the item cites no source of its own"}


def plain(v):
    """A claim value: a scalar, or a list of scalars."""
    scalar = lambda x: x is None or isinstance(x, (str, int, float, bool))  # noqa: E731
    return scalar(v) or (isinstance(v, list) and all(scalar(x) for x in v))


def claims(item, model_source, consumed=()):
    """One claim per attribute, at any depth. A nested record becomes dotted claims (setpoint.value, setpoint.uom,
    design.p.uom), and a record that names its own `source` lends it to everything under it. A list of plain values
    is one claim (`aliases`); a list holding records or lists is indexed (`ratings[0].psig`, `curve[1]`). A `facts`
    record's entries are claims under their own names. Every value under an item becomes a claim except: the
    top-level keys in SKIP, top-level keys starting with "_", and the `consumed` paths (CONSUMED) the caller turns
    into edges. An empty record holds no value and yields no claim. The result always passes plain()."""
    out = []
    st, src = status_of(item), source_of(item, model_source)

    def walk(name, v, source):
        if name in consumed:
            return
        if isinstance(v, dict):
            inner = {"kind": "document", "document": v["source"]} if v.get("source") else source
            for fk, fv in sorted(v.items()):
                if fk != "source":
                    walk(f"{name}.{fk}", fv, inner)
        elif not plain(v):  # a list holding records or lists
            for i, x in enumerate(v):
                walk(f"{name}[{i}]", x, source)
        else:
            out.append({"name": name, "value": v, "status": st, "source": source})

    for k, v in sorted(item.items()):
        if k in SKIP or k.startswith("_"):
            continue
        if k == "facts" and isinstance(v, dict):
            for fk, fv in sorted(v.items()):
                walk(fk, fv, src)
        else:
            walk(k, v, src)
    if "confidence" in item:
        out.append({"name": "extraction_confidence", "value": item["confidence"], "status": "extracted",
                    "source": src})
    # A check's caveats and notes are content, not bookkeeping: keep them. Status and evidence already shape every
    # claim (status_of, source_of); the rest of the check record becomes claims under its own name.
    for key in ("verification", "topology_verification"):
        v = item.get(key)
        if isinstance(v, dict):
            used = src.get("evidence") is not None and src.get("evidence") == v.get("evidence")
            for fk, fv in sorted(v.items()):
                if fk == "status" or (used and fk in ("evidence", "checked_against", "checked_on")):
                    continue  # already the claims' status or source
                walk(f"{key}.{fk}", fv, src)
    # When a check's evidence is the claims' source, the item's own citation would otherwise be lost.
    own = item.get("source") or item.get("sources")
    if own and src.get("kind") == "document" and src.get("document") != own:
        walk("cited_source", own, src)
    return out


def node(id_, kind, item, model_source, name=None, consumed=()):
    """A person's review (ops_review, written by apply_review.py) outranks the extraction's status: the node takes
    the reviewer's status, and every attribute the reviewer changed becomes a corrected claim sourced to the review."""
    aliases = [a for a in ([item.get("former_tag")] if item.get("former_tag") else [])]
    attrs = claims(item, model_source, consumed)
    review = item.get("ops_review") or None
    out = {"id": id_, "kind": kind, "tag": item.get("tag") or (id_ if kind in ("equipment", "system") else None),
           "name": name or item.get("name") or item.get("description"), "aliases": aliases,
           "status": status_of(item), "attributes": attrs}
    if review and review.get("status"):
        out["status"] = review["status"]
        out["review"] = {k: review.get(k) for k in ("status", "by", "on", "notes")}
        changed = {}
        for h in review.get("history", []):
            for field, (old, new) in (h.get("changes") or {}).items():
                changed[field] = {"kind": "review", "by": h.get("by"), "on": h.get("on"), "was": old}
                if field == "tag" and old and old not in aliases:
                    aliases.append(old)
        for c in attrs:
            if c["name"] in changed:
                c["status"], c["source"] = "corrected", changed[c["name"]]
    return out


def from_hand_built(m):
    src = m["meta"].get("source_document")
    # The model's own notes (its source, how it was made, its tag convention) are claims on the plant node.
    meta_claims = claims({k: v for k, v in m["meta"].items() if k not in ("model_id", "title")}, src)
    nodes = [{"id": "PLANT", "kind": "plant", "tag": m["meta"].get("model_id"), "name": m["meta"].get("title"),
              "aliases": [], "status": "unverified", "attributes": meta_claims},
             {"id": "BL", "kind": "boundary", "tag": None, "name": "battery limit", "aliases": [],
              "status": "confirmed", "attributes": []}]
    edges = []
    for u in m["units"]:
        nodes.append(node(u["id"], "equipment", u, src))
        edges.append(("contains", "PLANT", u["id"], u))
    for s in m["streams"]:
        edges.append(("connects", s["from"], s["to"], s))
    for kind, group in (("instrument", "instruments"), ("final_element", "final_elements")):
        for it in m.get(group, []):
            nodes.append(node(it["tag"], kind, it, src))
            edges.append(("measures" if kind == "instrument" else "acts_on", it["tag"], it["unit"], it))
            if it.get("stream"):
                edges.append(("sits_on", it["tag"], f'stream:{it["stream"]}', it))
    for c in m.get("controllers", []):
        nodes.append(node(c["tag"], "controller", c, src, consumed=CONSUMED["controllers"]))
        if c.get("measurement"):
            edges.append(("controls", c["measurement"], c["tag"], c))
        out = c.get("output") or {}
        for fe in ([out["final_element"]] if out.get("final_element") else []) + list(out.get("split_range") or []):
            edges.append(("controls", c["tag"], fe, c))
        if out.get("setpoint_of"):  # a cascade: this controller's output is another controller's setpoint
            edges.append(("sets_point_of", c["tag"], out["setpoint_of"], c))
    for v in m.get("manual_valves", []):
        nodes.append(node(v["tag"], "manual_valve", v, src))
        if v.get("stream"):
            edges.append(("sits_on", v["tag"], f'stream:{v["stream"]}', v))
        if v.get("unit"):
            edges.append(("acts_on", v["tag"], v["unit"], v))
    for r in m.get("relief_devices", []):
        nodes.append(node(r["tag"], "relief_device", r, src))
        if r.get("unit"):
            edges.append(("protects", r["tag"], r["unit"], r))
        if r.get("stream"):
            edges.append(("sits_on", r["tag"], f'stream:{r["stream"]}', r))
    for il in m.get("interlocks", []):
        nodes.append(node(il["id"], "interlock", il, src, name=il.get("cause"), consumed=CONSUMED["interlocks"]))
        if il.get("measurement"):
            edges.append(("trips", il["measurement"], il["id"], il))
        if il.get("final_element"):
            edges.append(("acts_on", il["id"], il["final_element"], il))
    for it in m.get("unplaced", []):
        # An item no unit could be found for (e.g. a valve on a line between two off-page connectors) is still part
        # of the plant: it becomes a node with no containing unit, and says why, instead of being left out.
        kind = it.get("kind")
        if kind not in UNPLACED_KINDS:
            # Older reader models have no explicit role. Keep their existing valve rule, but do not reinterpret
            # an explicitly unknown role. The original kind/class remain sourced attribute claims either way.
            kind = ("final_element" if not it.get("kind") and
                    ("Operated" in str(it.get("dexpi_class", "")) or it.get("actuated")) else "line_item")
        nd = node(it["tag"], kind, it, src)
        nd["placement"] = it.get("unit_basis") or "no owning unit recorded in the model"
        nodes.append(nd)
        if it.get("stream"):
            edges.append(("sits_on", it["tag"], f'stream:{it["stream"]}', it))
    for n, lim in enumerate(m.get("limits", []), 1):
        lid = lim.get("id") or f"LIM-{n}"
        nodes.append(node(lid, "limit", lim, src, name=lim.get("what")))
        if lim.get("tag"):
            edges.append(("applies_to", lid, lim["tag"], lim))
    return nodes, edges, src


def append_unplaced_controls(m, nodes, edges):
    # A missing owning unit does not erase an already-recorded measurement/output relationship. Append these
    # after existing edges so unrelated edge IDs stay stable. Keep the *_unplaced claims too: they explain the
    # reader's unresolved placement and interpretation, not an independently verified physical signal direction.
    by_id = {}
    for nd in nodes:
        by_id.setdefault(nd["id"], []).append(nd)
    linked = {(typ, a, b) for typ, a, b, _ in edges}
    for c in m.get("controllers", []):
        for field, role in (("measurement_unplaced", "instrument"), ("output_unplaced", "final_element")):
            refs = c.get(field)
            if refs is None or refs == "" or refs == []:
                continue
            refs = [refs] if isinstance(refs, str) else refs
            if not isinstance(refs, list) or not all(isinstance(t, str) and t for t in refs):
                raise ValueError(f"controller {c['tag']}: {field} must name a tag or a list of tags")
            for target in refs:
                candidates = by_id.get(target, [])
                if len(candidates) != 1 or candidates[0]["kind"] != role:
                    raise ValueError(f"controller {c['tag']}: {field} target {target!r} must identify one {role} "
                                     "node; original reference is retained in the model; resolve it before export")
                a, b = (target, c["tag"]) if field == "measurement_unplaced" else (c["tag"], target)
                if ("controls", a, b) not in linked:
                    edges.append(("controls", a, b, c))
                    linked.add(("controls", a, b))


def from_extracted(m):
    src = m["meta"].get("source_document")
    nodes = [{"id": "PLANT", "kind": "plant", "tag": None, "name": m["meta"].get("title"), "aliases": [],
              "status": "unverified", "attributes": []}]
    edges = []
    for s in m.get("systems", []):
        nodes.append(node(s["id"], "system", s, src))
        edges.append(("contains", "PLANT", s["id"], s))
    groups = (("equipment", "units"), ("instrument", "instruments"), ("final_element", "final_elements"),
              ("line_item", "line_items"), ("offpage_connector", "offpage_connectors"))
    parent_of = {}

    def walk(n, parent=None):
        if parent and n.get("id") and n.get("kind") not in ("site",):
            parent_of[n["id"]] = parent
        for k in n.get("children", []) + n.get("unassigned", []) + n.get("offpage_connectors", []):
            walk(k, n.get("id"))
    walk(m.get("hierarchy", {}))
    for kind, group in groups:
        for it in m.get(group, []):
            nodes.append(node(it["id"], kind, it, src))
            if parent_of.get(it["id"]):
                edges.append(("contains", parent_of[it["id"]], it["id"], it))
    for s in m.get("streams", []):
        edges.append(("connects", s["from"], s["to"], s))
    return nodes, edges, src


def from_line_layers(m, src):
    """The pipe and network layers (scripts/line_layers.py for a drawing, scripts/dexpi_reader.py for DEXPI XML):
    a node per junction (named by its kind: pipe tee, instrument tap...) and per line network, a piped_to edge per
    pipe segment, an instrument_connection / actuated_by / nozzle_of edge per drawn line that is not pipe, an
    on_network edge from each member item and junction to its network. Appended after every other node and edge, so
    existing edge ids don't move."""
    ll = m.get("line_layers") or {}
    nodes, edges = [], []
    for j in ll.get("junctions", []):
        nodes.append(node(j["id"], "junction", j, src, name=JUNCTION_NAMES.get(j.get("junction_kind"), "junction"),
                          consumed=CONSUMED["junctions"]))
    for n in ll.get("networks", []):
        nodes.append(node(n["id"], "line_network", n, src, name="line network", consumed=CONSUMED["line_networks"]))
    for n in ll.get("networks", []):
        for x in n.get("members", []) + n.get("junctions", []):
            edges.append(("on_network", x, n["id"], n))
    for sec, typ in LINE_SECTIONS.items():
        for sgm in ll.get(sec, []):
            edges.append((typ, sgm["from"], sgm["to"], sgm))
    return nodes, edges


def network_of_pairs(m):
    """{stream id: line network id} for the extracted links whose two ends share a network on their sheet."""
    ll = m.get("line_layers") or {}
    member = {}
    for n in ll.get("networks", []):
        for x in n.get("members", []):
            member.setdefault((str(n.get("sheet")), x), set()).add(n["id"])
    out = {}
    for s in m.get("streams", []):
        if s.get("kind") == "extracted_link":
            sh = str(s.get("sheet"))
            common = member.get((sh, s["from"]), set()) & member.get((sh, s["to"]), set())
            if len(common) == 1:
                out[s["id"]] = common.pop()
    return out


HAND_BUILT_NEEDS = {"units": ("id",), "streams": ("from", "to"), "instruments": ("tag", "unit"),
                    "final_elements": ("tag", "unit"), "controllers": ("tag",), "manual_valves": ("tag",),
                    "relief_devices": ("tag",), "interlocks": ("id",), "unplaced": ("tag",), "limits": ()}
EXTRACTED_NEEDS = {"systems": ("id",), "units": ("id",), "instruments": ("id",), "final_elements": ("id",),
                   "line_items": ("id",), "offpage_connectors": ("id",), "streams": ("from", "to")}
# Sections the extracted twin holds that are read (meta, hierarchy) or derived (summary, site), not lost. These two
# hold content of their own; when not empty they are listed in not_exported rather than passed over.
EXTRACTED_UNEXPORTED = {"dropped": "what the extraction itself dropped; no export rule for it yet",
                        "offpage_pairs": "pairings of off-page connectors across sheets; no export rule for them yet"}


def check_model(m, extracted):
    """Refuse, saying what is missing, a model the export can't read: a missing section or an item without the key
    its node or edge is built from."""
    needs = EXTRACTED_NEEDS if extracted else HAND_BUILT_NEEDS
    for sec in () if extracted else ("units", "streams"):
        if not isinstance(m.get(sec), list):
            raise ValueError(f"the model has no '{sec}' section (a list); a process model needs 'units' and "
                             f"'streams', even if empty")
    for sec, keys in needs.items():
        items = m.get(sec, [])
        if not isinstance(items, list):
            raise ValueError(f"'{sec}' is not a list")
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                raise ValueError(f"{sec}[{i}] is not a record")
            label = f"{sec}[{i}]" + (f" ({it.get('id') or it.get('tag')})" if it.get("id") or it.get("tag") else "")
            for k in keys:
                if not it.get(k):
                    raise ValueError(f"{label} has no '{k}'")


def build(model_path, reviews=None, questions=None):
    m = json.loads(Path(model_path).read_text(encoding="utf-8"))
    if not isinstance(m, dict) or not isinstance(m.get("meta"), dict):
        raise ValueError("not a plant model: no 'meta' section")
    extracted = m.get("meta", {}).get("model_kind") == "extracted_twin"
    check_model(m, extracted)
    if reviews and not Path(reviews).is_dir():
        raise ValueError(f"--reviews {reviews}: not a folder (give the folder apply_review.py wrote its records to)")
    handled = EXTRACTED_SECTIONS if extracted else HAND_BUILT_SECTIONS
    not_exported = [{"section": k, "items": len(v) if isinstance(v, (list, dict)) else 1,
                     "why": "left out on purpose" if k in NOT_EXPORTED else "no export rule for this section yet"}
                    for k, v in m.items() if k not in handled]
    if extracted:
        for k, why in EXTRACTED_UNEXPORTED.items():
            v = m.get(k)
            n = sum(len(x) for x in v.values() if isinstance(x, list)) if isinstance(v, dict) else len(v or [])
            if n:
                not_exported.append({"section": k, "items": n, "why": why})
    nodes, raw_edges, src = from_extracted(m) if extracted else from_hand_built(m)
    layer_nodes, layer_edges = from_line_layers(m, src)
    nodes += layer_nodes
    raw_edges += layer_edges
    if not extracted:
        append_unplaced_controls(m, nodes, raw_edges)
    pair_net = network_of_pairs(m) if extracted else {}
    edges = []
    for n, (typ, a, b, item) in enumerate(raw_edges, 1):
        own_id = typ in ("connects",) + LINE_EDGES and item.get("id")
        e = {"id": item.get("id") if own_id else f"E{n:05d}", "type": typ,
             "from": a, "to": b, "status": status_of(item),
             "direction": item.get("direction", "known" if typ == "connects" and not extracted else
                                   "unknown" if typ == "piped_to" else None),
             "source": source_of(item, src)}
        if typ == "connects":  # a line is more than its ends: size, fluid, insulation, temperature travel with it
            e["layer"] = ("stream" if not extracted else
                          "offpage_pair" if item.get("kind") == "cross_sheet" else "network_pair")
            if pair_net.get(item.get("id")):
                e["network"] = pair_net[item["id"]]
            e["attributes"] = claims(item, src, CONSUMED["streams"])
        elif typ in LINE_EDGES:
            e["attributes"] = claims(item, src, CONSUMED["segments"])
        edges.append(e)
    events = []
    for rec in sorted(Path(reviews).glob("*.json")) if reviews else []:
        r = json.loads(rec.read_text(encoding="utf-8"))
        for a in r.get("applied", []):
            events.append({"type": "review_decision", "item": a["item"], "decision": a["decision"],
                           "changes": a.get("changes"), "notes": a.get("notes"), "by": r.get("reviewer"),
                           "on": r.get("date"), "record": rec.name})
        for x in r.get("needs_moc", []):
            events.append({"type": "change_review_needed", "item": x["item"], "request": x["request"],
                           "why": x["why"], "by": r.get("reviewer"), "on": r.get("date"), "record": rec.name})
    qs = json.loads(Path(questions).read_text(encoding="utf-8")).get("questions", []) if questions else []
    mp = Path(model_path).resolve()
    shown = mp.relative_to(ROOT).as_posix() if mp.is_relative_to(ROOT) else mp.name  # never a local absolute path
    return {"schema": SCHEMA, "source_model": shown, "model_kind":
            "extracted_twin" if extracted else "hand_built", "title": m.get("meta", {}).get("title"),
            "nodes": nodes, "edges": edges, "questions": qs, "events": events, "not_exported": not_exported,
            "counts": {"nodes": len(nodes), "edges": len(edges),
                       "claims": sum(len(n["attributes"]) for n in nodes) + sum(len(e.get("attributes", [])) for e in edges),
                       "questions": len(qs), "events": len(events)}}


# Export profiles. "full" is everything the model holds. "core" is what a system that governs changes to the plant
# needs to keep: identity, configuration a change would alter, the relations that decide impact (measures, controls,
# protects, trips, piped_to, network membership) and where each fact came from. It drops how the extraction got there
# (method names, hashes, pixel geometry, candidate lists) and the all-pairs network links, which are rebuildable from
# on_network and grow with the square of a network's size. Every dropped claim name and edge kind is counted in the
# graph's "profile" block, so nothing leaves silently; the full export stays the record.
CORE_DROP_CLAIMS = re.compile(
    r"^(extraction_\w+|\w+_method|\w*sha256|source_evidence\..+|source_manifest|source_run|source_drawing\..+|image\w*|"
    r"from_symbol|to_symbol|sheet|at_0_1000|gap_0_1000|position_nearest|parent_agrees_with_position|"
    r"parent_source\..+|linked_candidates|unit_hops|pairwise_links|arms|lines\..+|pair_description_similarity|"
    r"grid_ref_on_target|drawing_number_candidates|system_codes_seen\..+|model)$")
PROFILES = ("full", "core")


def apply_profile(g, profile):
    """Return the graph reduced to a profile ("full" returns it unchanged). See CORE_DROP_CLAIMS."""
    if profile == "full":
        return g
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; choose one of {', '.join(PROFILES)}")
    g = json.loads(json.dumps(g))
    dropped_claims, dropped_edges, on_dropped_edges = {}, {}, 0

    def keep(attrs):
        out = []
        for c in attrs:
            if CORE_DROP_CLAIMS.match(re.sub(r"\[\d+\]", "", c["name"])):
                dropped_claims[c["name"]] = dropped_claims.get(c["name"], 0) + 1
            else:
                out.append(c)
        return out

    for n in g["nodes"]:
        if n.get("kind") != "plant":  # the model's own notes (how it was made, its conventions) stay in every profile
            n["attributes"] = keep(n.get("attributes", []))
    edges = []
    for e in g["edges"]:
        if e["type"] == "connects" and e.get("layer") == "network_pair":
            k = "connects (network_pair)"
            dropped_edges[k] = dropped_edges.get(k, 0) + 1
            on_dropped_edges += len(e.get("attributes", []))
            continue
        if "attributes" in e:
            e["attributes"] = keep(e["attributes"])
        edges.append(e)
    g["edges"] = edges
    g["profile"] = {
        "name": profile,
        "rule": "identity, configuration, impact relations and sources kept; extraction internals and all-pairs "
                "network links dropped (rebuildable from on_network). The full export is the record.",
        "dropped_claims": dict(sorted(dropped_claims.items())),
        "dropped_edges": dropped_edges,
        "claims_on_dropped_edges": on_dropped_edges}
    g["counts"].update(nodes=len(g["nodes"]), edges=len(g["edges"]),
                       claims=sum(len(n["attributes"]) for n in g["nodes"])
                       + sum(len(e.get("attributes", [])) for e in g["edges"]))
    return g


def problems(g):
    out = []
    if g.get("schema") != SCHEMA:
        out.append(f"schema is {g.get('schema')!r}, not {SCHEMA}")
    ids = [n["id"] for n in g.get("nodes", [])]
    dup = {i for i in ids if ids.count(i) > 1}
    out += [f"node id {i!r} appears more than once" for i in sorted(dup)]
    known = set(ids)
    edge_ids = [e["id"] for e in g.get("edges", [])]
    out += [f"edge id {i!r} appears more than once" for i in sorted({i for i in edge_ids if edge_ids.count(i) > 1})]
    streams = {e["id"] for e in g.get("edges", []) if e.get("type") == "connects" and e.get("layer") == "stream"}
    for n in g.get("nodes", []):
        if n.get("kind") not in NODE_KINDS:
            out.append(f"node {n.get('id')}: unknown kind {n.get('kind')!r}")
        if n.get("status") not in STATUSES:
            out.append(f"node {n.get('id')}: unknown status {n.get('status')!r}")
        for c in n.get("attributes", []):
            if c.get("status") not in STATUSES:
                out.append(f"node {n['id']} attribute {c.get('name')}: status {c.get('status')!r}")
            if not isinstance(c.get("source"), dict):
                out.append(f"node {n['id']} attribute {c.get('name')}: no source")
            if not plain(c.get("value")):
                out.append(f"node {n['id']} attribute {c.get('name')}: value is not a plain value or list of them")
    kind = {n["id"]: n.get("kind") for n in g.get("nodes", [])}
    nets_of = {}
    for e in g.get("edges", []):
        if e.get("type") == "on_network":
            nets_of.setdefault(e.get("from"), set()).add(e.get("to"))
    ends_of = {t: set() for t in LINE_EDGES}
    pipe_ids = {e.get("id") for e in g.get("edges", []) if e.get("type") == "piped_to"}
    for e in g.get("edges", []):
        t, a, b = e.get("type"), e.get("from"), e.get("to")
        if t in LINE_EDGES:
            ends_of[t].update((a, b))
            bad = [x for x in (a, b) if kind.get(x) in LINE_LAYER_ENDS]
            if bad:
                out.append(f"edge {e.get('id')}: a {t} end must be an item or a junction, not {kind.get(bad[0])}")
            if a == b:
                out.append(f"edge {e.get('id')}: {t} joins {a!r} to itself")
            if t in ("actuated_by", "nozzle_of") and "junction" in (kind.get(a), kind.get(b)):
                out.append(f"edge {e.get('id')}: {t} must join two items")
        elif t == "on_network":
            if b in kind and kind.get(b) != "line_network":
                out.append(f"edge {e.get('id')}: on_network must end at a line_network node, not {kind.get(b)}")
            if kind.get(a) == "line_network":
                out.append(f"edge {e.get('id')}: a line network can't be on a network")
        elif t == "connects":
            if e.get("layer") is not None and e.get("layer") not in CONNECTS_LAYERS:
                out.append(f"edge {e.get('id')}: unknown connects layer {e.get('layer')!r}")
            if e.get("network") is not None:
                if kind.get(e["network"]) != "line_network":
                    out.append(f"edge {e.get('id')}: network {e['network']!r} is not a line_network node")
                for x in (a, b):
                    if e["network"] not in nets_of.get(x, set()):
                        out.append(f"edge {e.get('id')}: {x!r} is not on network {e['network']!r} (a network pair "
                                   "must be derivable from on_network)")
    for n in g.get("nodes", []):
        if n.get("kind") == "junction":
            if len(nets_of.get(n["id"], ())) != 1:
                out.append(f"node {n['id']}: a junction must be on exactly one line network "
                           f"(it is on {len(nets_of.get(n['id'], ()))})")
            attrs = {c.get("name"): c.get("value") for c in n.get("attributes", [])}
            jk = attrs.get("junction_kind") or "pipe_tee"
            if jk not in JUNCTION_NAMES:
                out.append(f"node {n['id']}: unknown junction_kind {jk!r}")
            elif jk in ("pipe_tee", "marked_crossing") and n["id"] not in ends_of["piped_to"]:
                out.append(f"node {n['id']}: a {JUNCTION_NAMES[jk]} with no piped_to edge")
            elif jk in ("instrument_tap", "instrument_line_junction"):
                if n["id"] not in ends_of["instrument_connection"]:
                    out.append(f"node {n['id']}: an {JUNCTION_NAMES[jk]} with no instrument_connection edge")
                if jk == "instrument_tap" and attrs.get("on_segment") not in pipe_ids:
                    out.append(f"node {n['id']}: an instrument tap must sit on a piped_to edge (on_segment "
                               f"{attrs.get('on_segment')!r} is not one)")
    for e in g.get("edges", []):
        if e.get("status") not in STATUSES:
            out.append(f"edge {e.get('id')}: unknown status {e.get('status')!r}")
        for c in e.get("attributes", []):
            if c.get("status") not in STATUSES:
                out.append(f"edge {e.get('id')} attribute {c.get('name')}: status {c.get('status')!r}")
            if not isinstance(c.get("source"), dict):
                out.append(f"edge {e.get('id')} attribute {c.get('name')}: no source")
            if not plain(c.get("value")):
                out.append(f"edge {e.get('id')} attribute {c.get('name')}: value is not a plain value or list of them")
        if e.get("type") not in EDGE_TYPES:
            out.append(f"edge {e.get('id')}: unknown type {e.get('type')!r}")
        for end in (e.get("from"), e.get("to")):
            stream_ref = str(end).startswith("stream:") and str(end)[len("stream:"):] in streams
            if end not in known and not stream_ref:
                out.append(f"edge {e.get('id')}: end {end!r} is not a node")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("model", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--reviews", help="folder of apply_review.py change records (*.json) to export as events")
    ap.add_argument("--questions", help="a questions file (question engine output) to attach")
    ap.add_argument("--check", metavar="GRAPH", help="validate an exported graph file and exit")
    ap.add_argument("--profile", choices=PROFILES, default="full",
                    help="full (default): everything; core: identity, configuration, impact relations and sources, "
                         "without extraction internals or all-pairs network links")
    a = ap.parse_args(argv)
    if a.check:
        try:
            text = Path(a.check).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"{a.check}: can't read ({exc.strerror or exc})", file=sys.stderr)
            return 1
        try:
            g = json.loads(text)
        except ValueError as exc:
            print(f"{a.check}: not JSON ({'the file is empty' if not text.strip() else exc})", file=sys.stderr)
            return 1
        if not isinstance(g, dict) or "nodes" not in g:
            print(f"{a.check}: not a graph (a {SCHEMA} file is a JSON object with 'schema' and 'nodes')",
                  file=sys.stderr)
            return 1
        bad = problems(g)
        for b in bad:
            print("FAIL:", b)
        print(f"{a.check}: {len(bad)} problem(s)")
        return 1 if bad else 0
    if not a.model:
        ap.error("give a model, or --check GRAPH")
    try:
        sources = [a.model, a.questions]
        if a.reviews:
            sources.extend(sorted(Path(a.reviews).glob("*.json")))
        g = build(a.model, a.reviews, a.questions)
        if a.out:
            protect_outputs([a.out], sources)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"{a.model}: can't export ({exc})", file=sys.stderr)
        return 1
    g = apply_profile(g, a.profile)
    for s in g["not_exported"]:
        print(f"note: section '{s['section']}' ({s['items']} item(s)) not exported: {s['why']}", file=sys.stderr)
    bad = problems(g)
    if bad:
        for b in bad:
            print("FAIL:", b, file=sys.stderr)
        return 1
    text = json.dumps(g, indent=1, ensure_ascii=False) + "\n"
    if a.out:
        try:
            Path(a.out).write_text(text, encoding="utf-8", newline="\n")
        except OSError as exc:
            print(f"can't write graph ({exc})", file=sys.stderr)
            return 1
    print(json.dumps(g["counts"]) + (f" -> {a.out}" if a.out else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
