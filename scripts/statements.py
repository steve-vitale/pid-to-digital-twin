"""Turn a twin graph into plain-English statements, each with its source and evidence, for sampled human review.

    python scripts/statements.py render GRAPH.json [--image SHEET=PNG ...] [--document PDF] --out DIR
    python scripts/statements.py sample DIR/statements.json --n 60 --seed 7 --out DIR/sample.json
    python scripts/statements.py sample DIR/statements.json --n 60 --seed 7 --strata layer --floor 15 --out DIR/s.json
    python scripts/statements.py score REVIEWED_SHEET.csv [--sample DIR/sample.json]
    python scripts/statements.py apply GRAPH.json REVIEWED_SHEET.csv --reviewer NAME [--date D] --out GRAPH_OUT.json

Every node, attribute claim and edge of a twin-graph-1 file (scripts/graph_export.py) becomes one sentence such as
"FT 1401 measures flow" or "PSV-101 protects the residue treater RT-1", with a stable id, the source it cites, the
evidence (a crop of the drawing box, the cited report page and the nearest matching line, or "no source of its own"),
a consequence rank, the asset it belongs to and its relationship layer (pipe, network, network_pair, stream, item:
error rates are reported per layer, never blended). Two verdicts are kept apart and never mixed: MATCHES ITS SOURCE
(anyone can check) and TRUE IN THE PLANT (only an operator, a walkdown or live data can say, and only for a statement
that matched its source). Guide: docs/STATEMENT_REVIEW.md. Stdlib; Pillow for drawing crops; PyMuPDF or pdftotext,
when present, to quote report pages (otherwise only the page is given). No model calls.
"""
import argparse
import csv
import datetime
import hashlib
import html
import json
import math
import random
import re
import shutil
import subprocess
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "twin-graph-1"
FORMAT = "statements-1"
SHEET_COLUMNS = ("statement_id", "group", "stratum", "layer", "text", "source", "source_match", "plant_truth",
                 "reviewer", "note")
# Which relationship layer a statement belongs to. Error rates are reported per layer and never blended: a pipe
# adjacency, a network membership and a pairwise "same network" link are different facts with different error rates.
LAYERS = {"pipe": "pipe layer: a pipe segment or pipe junction (what is piped directly to what)",
          "non_pipe": "drawn lines that are not pipe: instrument connections and taps, actuator stems, nozzle stubs",
          "network": "network layer: a drawn line network and what is attached to it",
          "network_pair": "pairwise link: two items on the same drawn line network (the tracer's links)",
          "stream": "a process stream recorded in a hand-built model",
          "offpage_pair": "two off-page connectors paired across drawings",
          "item": "the items themselves: identity, attributes and other relations"}
SOURCE_VERDICTS = ("match", "mismatch", "unclear")
PLANT_VERDICTS = ("confirmed", "wrong", "unknown")
RANKS = {1: "control or safety relation", 2: "connection", 3: "value with units", 4: "identity",
         5: "descriptive text"}
Z95 = 1.959963984540054
MACHINE_NOTE = ("This only proves the export says what the model says. It does not prove the model is right: that is "
                "what the human source check and the plant check are for.")

KIND_WORDS = {
    "plant": "the plant this model describes",
    "system": "a system (one drawing area)",
    "equipment": "a piece of equipment",
    "instrument": "an instrument",
    "final_element": "a final control element (a valve or drive the control system moves)",
    "controller": "a controller",
    "line_item": "an item drawn on a line",
    "offpage_connector": "an off-page connector (the line continues on another drawing)",
    "boundary": "the battery limit (where the modelled scope ends)",
    "manual_valve": "a hand-operated valve",
    "relief_device": "a pressure relief device",
    "interlock": "an interlock",
    "limit": "an operating limit",
    "junction": "a junction (a point where three or more drawn line arms meet)",
    "line_network": "a line network (lines joined by bends, junctions or crossings with no item between)",
}
EDGE_RANK = {"controls": 1, "sets_point_of": 1, "protects": 1, "trips": 1, "applies_to": 1, "acts_on": 2,
             "contains": 2, "connects": 2, "measures": 2, "sits_on": 2, "piped_to": 2, "on_network": 2,
             "instrument_connection": 2, "actuated_by": 2, "nozzle_of": 2}
NON_PIPE_EDGES = ("instrument_connection", "actuated_by", "nozzle_of")
JUNCTION_LAYER = {"pipe_tee": "pipe", "marked_crossing": "pipe", "instrument_tap": "non_pipe",
                  "instrument_line_junction": "non_pipe"}

# Fields that are bookkeeping of the extraction or of this repository, not statements about the plant. They are
# counted in statements.json ("skipped") so nothing disappears silently.
INTERNAL = {"extraction_confidence", "layout", "id", "ids", "image", "image_sha256", "image_size_px", "model",
            "source_manifest", "source_run", "extraction_sha256", "extraction_error", "extraction_failed",
            "drawing_number_candidates", "sheet", "sheets", "system", "tag_status", "unit_hops", "position_nearest",
            "parent_agrees_with_position", "gap_0_1000", "linked_candidates", "role_reason", "pair",
            "pair_status", "pair_description_similarity", "grid_ref_on_target", "fig11_series", "isa_letters",
            "xmeas", "xmv", "at_0_1000", "pairwise_links", "arms", "junction_kind", "on_segment", "joined_only_at"}
INTERNAL_PREFIXES = ("source_drawing.", "parent_source.", "system_codes_seen.", "lines.")
INTERNAL_SUFFIXES = ("_method", "_sha256")


# ----------------------------------------------------------------------------------------------- helpers
def sid(subject, predicate, obj):
    """Stable statement id: a hash of subject|predicate|object. Status, source and evidence are not part of it."""
    key = "%s|%s|%s" % (subject, predicate, json.dumps(obj, sort_keys=True, ensure_ascii=False))
    return "st-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def fmt(v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, list):
        return ", ".join(fmt(x) for x in v)
    return str(v)


def article(w):
    return "an" if str(w)[:1].lower() in "aeiou" else "a"


def words(name):
    return name.replace(".", " ").replace("_", " ")


def blank(v):
    return v is None or v == "" or v == [] or v == {}


def load_graph(path):
    p = Path(path)
    try:
        g = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{p.name} is not a {SCHEMA} graph: can't read it as JSON ({exc})")
    if not isinstance(g, dict) or g.get("schema") != SCHEMA or not isinstance(g.get("nodes"), list):
        raise ValueError(f"{p.name} is not a {SCHEMA} graph (it needs \"schema\": \"{SCHEMA}\" and a nodes list). "
                         f"Export one first: python scripts/graph_export.py MODEL.json --out graph.json")
    return g


class Graph:
    def __init__(self, g):
        self.g = g
        self.nodes = OrderedDict((n["id"], n) for n in g["nodes"])
        self.edges = g.get("edges", [])
        self.streams = {e["id"]: e for e in self.edges if e["type"] == "connects"}
        self.parent = {}
        for e in self.edges:
            if e["type"] == "contains":
                self.parent.setdefault(e["to"], e["from"])
        self.edge_pairs = {(e["from"], e["to"]) for e in self.edges if e["type"] != "contains"}
        self.contained = {(e["to"], e["from"]) for e in self.edges if e["type"] == "contains"}
        self.tag_count = Counter(n.get("tag") for n in self.nodes.values() if n.get("tag"))
        self.on_stream = {(e["from"], e["to"].split(":", 1)[1]) for e in self.edges
                          if e["type"] == "sits_on" and str(e["to"]).startswith("stream:")}
        self.net_items = Counter(e["to"] for e in self.edges if e["type"] == "on_network"
                                 and self.nodes.get(e["from"], {}).get("kind") != "junction")
        self.tapped_by = {}  # junction -> the instruments whose lines meet it
        self.pipe_arms = Counter()
        for e in self.edges:
            if e["type"] == "instrument_connection" and self.nodes.get(e["to"], {}).get("kind") == "junction":
                self.tapped_by.setdefault(e["to"], []).append(e["from"])
            if e["type"] == "piped_to":
                self.pipe_arms.update((e["from"], e["to"]))

    def attr(self, nid, name):
        for a in self.nodes.get(nid, {}).get("attributes", []):
            if a["name"] == name:
                return a["value"]
        return None

    def name(self, nid):
        """How a node is named in a sentence: its tag, or what it is plus its id when it has no tag."""
        n = self.nodes.get(nid)
        if n is None:
            if str(nid).startswith("stream:"):
                return self.stream_words(nid.split(":", 1)[1])
            return str(nid)
        if n["kind"] == "plant":
            return "the plant"
        if n["kind"] == "boundary":
            return "the battery limit"
        if n["kind"] == "offpage_connector":
            return f"off-page connector \u201c{n.get('tag') or n.get('name') or nid}\u201d ({nid})"
        if n["kind"] in ("interlock", "limit") and not n.get("tag"):
            return nid  # their name is a whole sentence (the cause, what is limited): said by its own statement
        if n.get("tag"):
            return n["tag"] if self.tag_count[n["tag"]] == 1 else f"{n['tag']} ({nid})"
        return f"{n['name']} {nid}" if n.get("name") else nid

    def obj_name(self, nid):
        """A node as the object of a sentence: equipment gets its name in front ("the residue treater RT-1")."""
        n = self.nodes.get(nid)
        if n and n["kind"] == "equipment":
            nm = n.get("name")
            if nm and nm != n.get("tag"):
                nm = " ".join(w.lower() if w[:1].isupper() and w[1:].islower() else w for w in nm.split())
                return f"the {nm} {n.get('tag') or nid}"
            cls = self.attr(nid, "type") or self.attr(nid, "class")
            if cls and self.g.get("model_kind") == "extracted_twin":  # the extraction's class, not the plant's word
                cls = str(cls).replace('_', ' ')
                return f"{n.get('tag') or nid} (classed as {article(cls)} {cls} by the extraction)"
            if cls:
                return f"{str(cls).replace('_', ' ')} {n.get('tag') or nid}"
        if n and n["kind"] in ("controller", "interlock", "limit"):
            return f"{n['kind']} {self.name(nid)}"
        return self.name(nid)

    def stream_words(self, s):
        e = self.streams.get(s)
        if not e:
            return f"stream {s}"
        return f"stream {s} (from {self.name(e['from'])} to {self.name(e['to'])})"

    def system_of(self, nid):
        """The system an asset sits in: its containing system, else the equipment its 'unit' names, else the plant."""
        seen = set()
        p = self.parent.get(nid)
        while p and p not in seen:
            seen.add(p)
            if self.nodes.get(p, {}).get("kind") == "system":
                return p
            p = self.parent.get(p)
        u = self.attr(nid, "unit")
        if isinstance(u, str) and u in self.nodes and u != nid:
            return u
        n = self.nodes.get(nid, {})
        if n.get("kind") == "equipment":
            return nid
        return "PLANT" if "PLANT" in self.nodes else None


# ----------------------------------------------------------------------------------------------- templates
def measure_words(gr, nid, var):
    """FT 1401 measures flow; but TCV 1401 is a valve, and TIC 104 is a controller: say so instead of 'measures'."""
    kind = str(gr.attr(nid, "instrument_kind") or "")
    letters = str(gr.attr(nid, "isa_letters") or (gr.nodes[nid].get("tag") or "").split("-")[0].split(" ")[0])
    succ = letters[1:].upper()
    n = gr.name(nid)
    if letters[:1].upper() in ("P", "T") and succ.endswith("SV"):  # PSV, TSV: self-acting, not in a loop
        return f"{n} is a {var} safety valve"
    if "valve" in kind or ("V" in succ and gr.nodes[nid]["kind"] != "controller"):
        return f"{n} is a valve in a {var} loop"
    if gr.nodes[nid]["kind"] == "final_element":
        return f"{n} acts on {var}"
    if gr.nodes[nid]["kind"] == "controller" or "C" in succ:
        return f"{n} controls {var}"
    return f"{n} measures {var}"


# How an extracted twin's instrument kind was read (scripts/build_twin.py): from the tag letters, never from the
# extraction's class (which is "instrumentation" for every bubble). Expanded only where the letters are unambiguous.
VALVE_LETTERS = {"CV": "control valve", "SV": "safety valve"}  # after the first (variable) letter: TCV, PSV
OPERATED_LETTERS = {"MOV": "motor-operated valve", "AOV": "air-operated valve", "SOV": "solenoid-operated valve",
                    "AORV": "air-operated relief valve"}
# The converter's parent / unit methods that follow drawn lines (the tracer's links or its geometry); every other
# method is said as what it is ("geometry_nearest": nearest position) or not said at all.
LINE_METHODS = ("along_line", "along_line_via_instrument_chain", "linked", "via_instrument_chain", "connection_path")


def kind_from_letters(gr, nid, kind):
    """'PSV 1405's tag letters read as a valve (PSV: pressure safety valve); the extraction classed the symbol as an
    instrument bubble.' The kind comes from the tag letters; a safety or relief valve is not called a final element."""
    S = gr.name(nid)
    letters = str(gr.attr(nid, "isa_letters") or "")
    what = "an operated valve" if kind == "operated valve" else "a valve"
    if kind == "valve (plant-coded tag)":
        code = re.search(r"system code (\S+)", str(gr.attr(nid, "variable_method") or ""))
        expl = (f"a plant tag led by system code {code.group(1)}, so only its last letter is read" if code else
                "a plant tag, so only its last letter is read")
    elif kind == "operated valve":
        expl = OPERATED_LETTERS.get(letters)
    else:
        var = gr.attr(nid, "variable")
        expl = f"{var} {VALVE_LETTERS[letters[1:]]}" if var and letters[1:] in VALVE_LETTERS else None
    cls = gr.attr(nid, "class")
    cls = "an instrument bubble" if cls == "instrumentation" else f"{article(cls)} {fmt(cls)}" if cls else None
    return (f"{S}'s tag letters read as {what} ({letters}{': ' + expl if expl else ''})" +
            (f"; the extraction classed the symbol as {cls}" if cls else ""))


def how_attributed(gr, nid):
    """How an extracted item was attributed to its equipment, from its own parent_method and unit_method:
    "by tracing the lines", "by nearest position on the drawing" (then the lines from its parent), or None when the
    method is not one of these (nothing is claimed then)."""
    pm, um = gr.attr(nid, "parent_method"), gr.attr(nid, "unit_method")
    if pm == "geometry_nearest":
        parent = gr.attr(nid, "parent")
        if um == "connection_path" and parent in gr.nodes and parent != gr.attr(nid, "unit"):
            return f"by nearest position on the drawing (to {gr.obj_name(parent)}), then by tracing the lines from it"
        return "by nearest position on the drawing"
    if pm in LINE_METHODS or (pm is None and um in LINE_METHODS):
        return "by tracing the lines"
    return None


def attributed(gr, nid, eq):
    how = how_attributed(gr, nid)
    return f"The extraction attributes {gr.name(nid)} to {gr.obj_name(eq)}" + (f" {how}" if how else "")


UNIT_SUFFIX = re.compile(r"^(?P<what>.+)_(?P<unit>psig|psia|psi|gal|C|F|K|kPa|barg|bar|pct|h|s|min|m3|kg|klbh)$")
# Sentences for unit-suffixed fields. Wording follows the field name, not what we think the source says: "mawp" is
# rendered as the model names it, so a source that says something else shows up as a mismatch, not hidden by us.
FIELD_WORDS = {"mawp": "{S}'s MAWP (maximum allowable working pressure, as the model names it) is {v} {u}",
               "volume": "{S} holds {v} {u}", "cooling_water": "{S} is cooled with water at {v} {u}",
               "scan": "{S} scans every {v} {u}", "opened_at": "{S} opened at {v} {u}"}


def attr_statement(gr, node, a):
    """(rank, predicate, text) for one attribute claim, or None to skip it (with the reason)."""
    nid, name, v = node["id"], a["name"], a["value"]
    S = gr.name(nid)
    kind = node["kind"]
    if name == "class" and kind == "interlock":
        return 1, "is_a", f"{S} is classed as {article(v)} {fmt(v)} interlock"
    if name == "instrument_kind" and gr.g.get("model_kind") == "extracted_twin" and \
            v in ("final element (valve)", "operated valve", "valve (plant-coded tag)"):
        return 4, "is_a", kind_from_letters(gr, nid, v)
    if name in ("type", "class", "instrument_kind"):
        if str(v) in ("general", "instrumentation", "measurement / control") or \
                (kind == "offpage_connector" and v == "inlet/outlet"):
            return None, "repeats what kind of item it is"
        if gr.g.get("model_kind") == "extracted_twin":
            return 4, "is_a", f"{S} is classed as {article(v)} {fmt(v).replace('_', ' ')} by the extraction"
        return 4, "is_a", f"{S} is {article(v)} {fmt(v).replace('_', ' ')}"
    if name == "variable":
        return 4, "variable", measure_words(gr, nid, fmt(v)) + "."
    if name == "assigned_tag":
        if v is True:
            return 4, "assigned_tag", (f"The tag {S} was assigned by whoever built this model; the source gives no "
                                       f"tag number for it")
        return None, "says nothing when false"
    if name == "duplicate_tag":
        return (4, "duplicate_tag", f"The tag {S} appears more than once on the drawing") if v is True else \
            (None, "says nothing when false")
    if name == "drawn_in_source_figure":
        return 5, "drawn_in_source_figure", (f"{S} is drawn in the source figure" if v else
                                            f"{S} is not drawn in the source figure; it comes from the text")
    if name in ("unit", "parent") and isinstance(v, str) and ((nid, v) in gr.edge_pairs or
                                                             (nid, v) in gr.contained):
        return None, "said by an edge statement"
    if name == "unit":
        if isinstance(v, str) and v in gr.nodes:
            return 2, "unit", attributed(gr, nid, v) \
                if kind in ("line_item", "offpage_connector", "instrument") and gr.g.get("model_kind") == \
                "extracted_twin" else f"{S} belongs to {gr.obj_name(v)}"
        return 2, "unit", f"{S} belongs to {fmt(v)}"
    if name == "stream":
        if (nid, str(v)) in gr.on_stream:
            return None, "said by an edge statement"
        return 2, "stream", f"{S} is on {gr.stream_words(str(v))}"
    if name == "parent":
        return 2, "parent", f"{S} is drawn attached to {gr.obj_name(v) if v in gr.nodes else fmt(v)}"
    if name == "refers_to_drawing":
        return 2, "refers_to_drawing", f"{S} continues on drawing {fmt(v)}"
    if name == "refers_to_system_code":
        return 2, "refers_to_system_code", f"{S} leads to system {fmt(v)}"
    if name == "loop":
        if str(v) in str(node.get("tag") or ""):
            return None, "repeats part of the tag"
        return 4, "loop", f"{S} is in loop {fmt(v)}"
    if name == "uom":
        if kind == "limit":
            return None, "said with the limit's value"
        if kind == "final_element":
            return 3, "uom", f"{S}'s position is given in {fmt(v)}"
        return 3, "uom", f"{S} reads in {fmt(v)}"
    if name in ("value", "what") and kind == "limit":
        return None, "said with the limit's value"
    if name in ("cause",):
        return 1, "cause", f"{S} trips when: {fmt(v)}"
    if name == "effect":
        return 1, "effect", f"When {S} trips: {fmt(v)}"
    if name == "bypass":
        return 1, "bypass", f"{S} can be bypassed ({fmt(v)})"
    if name == "relief_basis":
        return 1, "relief_basis", f"{S}'s relief basis: {fmt(v)}"
    if name == "as_found":
        return 5, "as_found", f"{S} as found: {fmt(v)}"
    if name == "as_operated":
        return 5, "as_operated", f"{S} as operated: {fmt(v)}"
    if name == "material":
        return 5, "material", f"{S} is made of {fmt(v)}"
    if name == "opened_at":
        return 5, "opened_at", f"{S} opened at {fmt(v)} (time of day)"
    if name == "open_question":
        return 5, "open_question", f"Open question about {S}: {fmt(v)}"
    if name == "mode":
        return 4, "mode", f"{S} runs in {fmt(v)} mode"
    if name == "component":
        return 4, "component", f"{S} analyses {fmt(v)}"
    if name in ("name", "description", "text"):
        if str(v).strip() == str(node.get("tag") or "").strip():
            return None, "repeats the tag"
        if kind in ("interlock", "limit") and v == node.get("name"):
            return None, "said by another statement about this item"
        if str(v).startswith("untagged "):
            return None, "says only that the item has no tag"
        return 5, "described_as", f"{S} is described as \u201c{fmt(v)}\u201d"
    if name == "system_name" and v == node.get("name"):
        return None, "repeats the name"
    if name in ("system_code", "system_name", "drawing_number"):
        return 4, name, f"{S}'s {words(name)} is {fmt(v)}"
    if name.startswith("sampling."):
        return 3, name, f"{S}'s sampling {words(name.split('.', 1)[1]).replace(' h', '')} is {fmt(v)} h"
    m = UNIT_SUFFIX.match(name)
    if m and isinstance(v, (int, float)) and not isinstance(v, bool):
        unit = {"pct": "%", "klbh": "klb/h"}.get(m["unit"], m["unit"])
        tpl = FIELD_WORDS.get(m["what"], "{S}'s " + words(m["what"]) + " is {v} {u}")
        return 3, name, tpl.format(S=S, v=fmt(v), u=unit)
    rank = 3 if isinstance(v, (int, float)) and not isinstance(v, bool) else 5
    return rank, name, f"{S}'s {words(name)} is {fmt(v)}"


def edge_text(gr, e):
    t, a, b = e["type"], e["from"], e["to"]
    A, B = gr.name(a), gr.obj_name(b)
    ka = gr.nodes.get(a, {}).get("kind")
    kb = gr.nodes.get(b, {}).get("kind")
    if t == "contains":
        if a == "PLANT":
            return f"{gr.name(b)} is part of the plant"
        if ka in ("line_item", "instrument", "final_element"):
            if gr.attr(b, "parent_method") == "geometry_nearest" and gr.g.get("model_kind") == "extracted_twin":
                return (f"The extraction attaches {gr.name(b)} to {gr.obj_name(a)}, the nearest item by position on "
                        f"the drawing")
            return f"{gr.name(b)} is drawn attached to {gr.obj_name(a)}"
        if ka == "equipment" and kb != "equipment" and gr.g.get("model_kind") == "extracted_twin":
            return attributed(gr, b, a)
        if ka == "system":
            return f"{gr.name(b)} is in system {gr.name(a)}"
        return f"{gr.name(b)} is part of {gr.obj_name(a)}"
    if t == "connects":
        label = f"Stream {e['id']}" if e.get("id") and not re.match(r"^(E\d+|L\d+-\d+)$", e["id"]) else "A line"
        if e.get("direction") in ("known", "forward"):
            return f"{label} runs from {gr.obj_name(a)} to {gr.obj_name(b)}"
        layer = connects_layer(gr, e)
        if layer == "network_pair":
            net = f" ({gr.name(e['network'])})" if e.get("network") else ""
            at = [x for x in (gr.attr(e.get("network"), "joined_only_at") or []) if x not in (a, b)]
            if at:  # the tracer joined this network where its lines meet only at an item's edge
                return (f"{gr.obj_name(a)} and {gr.obj_name(b)} are on the same drawn line network{net} as the tracer "
                        f"joins it, but its lines meet only at the edge of {', '.join(gr.obj_name(x) for x in at)}: "
                        f"they are joined through that item, not by line alone. This does not say a pipe runs "
                        f"directly from one to the other")
            return (f"{gr.obj_name(a)} and {gr.obj_name(b)} are on the same drawn line network{net}: lines, bends, "
                    f"junctions or crossings join them with no item between. This does not say a pipe runs directly "
                    f"from one to the other")
        if layer == "offpage_pair":
            return f"{gr.obj_name(a)} and {gr.obj_name(b)} are paired: the line continues from one drawing to the other"
        return f"{gr.obj_name(a)} and {gr.obj_name(b)} are joined by a line (direction not shown)"
    if t == "piped_to":
        what = "A line is drawn" if {ka, kb} & {"instrument", "controller"} else "A pipe runs"
        taps = [x for x in (edge_attr(e, "taps") or []) if x in gr.nodes]
        by = [i for x in taps for i in gr.tapped_by.get(x, [])]
        on = (f"; the instrument tap{'s' if len(taps) > 1 else ''} of {', '.join(gr.name(i) for i in by)} "
              f"{'are' if len(taps) > 1 else 'is'} on it") if by else ""
        return (f"{what} directly from {gr.obj_name(a)} to {gr.obj_name(b)}, with no "
                f"{'pipe tee' if taps else 'junction'} or other item between{on}")
    if t == "instrument_connection":
        return (f"An instrument line, not a pipe, runs directly from {gr.obj_name(a)} to {gr.obj_name(b)}, with no "
                f"junction or other item between")
    if t == "actuated_by":
        return (f"{gr.name(b)} is the actuator drawn on {gr.obj_name(a)}: the short line between them is its stem, "
                f"not a pipe")
    if t == "nozzle_of":
        return (f"{A} is a nozzle on {gr.obj_name(b)}: the short stub between them is part of the vessel, not a "
                f"pipe")
    if t == "on_network":
        drawn = "drawn " if gr.g.get("model_kind") == "extracted_twin" else ""
        if ka == "junction":
            return f"{A} is on {drawn}{gr.name(b)}"
        return f"{A} is attached to {drawn}{gr.name(b)}"
    if t == "measures":
        var = gr.attr(a, "variable")
        return f"{A} measures {var} for {B}" if var else f"{A} measures {B}"
    if t == "controls":
        if kb == "controller":
            return f"{A} is read by controller {gr.name(b)}"
        if ka == "controller":
            return f"Controller {A} moves {gr.name(b)}"
        return f"{A} controls {gr.name(b)}"
    if t == "acts_on":
        if ka == "interlock":
            return f"Interlock {A}, when it trips, acts on {gr.name(b)}"
        if ka == "manual_valve":
            return f"Hand valve {A} isolates or throttles flow at {B}"
        return f"{A} acts on {B}"
    if t == "sets_point_of":
        return f"Controller {A} sets the setpoint of controller {gr.name(b)} (cascade)"
    if t == "sits_on":
        return f"{A} sits on {gr.stream_words(b.split(':', 1)[1]) if str(b).startswith('stream:') else B}"
    if t == "protects":
        return f"{A} protects {B} against overpressure"
    if t == "trips":
        return f"A reading from {A} can trip interlock {gr.name(b)}"
    if t == "applies_to":
        return f"Limit {A} applies to {gr.name(b)}"
    return None


IDENTITY_SPECIAL = {"plant": lambda gr, n: f"This model describes {n.get('name') or n.get('tag') or 'a plant'}",
                    "boundary": lambda gr, n: "The model has a battery limit, where its scope ends",
                    "offpage_connector": lambda gr, n: (
                        f"There is an off-page connector reading \u201c{n.get('tag') or n.get('name')}\u201d "
                        f"({n['id']}): the line continues on another drawing")}


def edge_attr(e, name):
    for c in e.get("attributes") or []:
        if c.get("name") == name:
            return c.get("value")
    return None


def junction_kind(gr, nid):
    return gr.attr(nid, "junction_kind") or "pipe_tee"


def junction_text(gr, n):
    """Said by kind: a pipe tee, an instrument tap (a pipe passes it), a marked crossing, instrument lines meeting."""
    nid, arms = n["id"], gr.attr(n["id"], "arms")
    where = "on the drawing " if gr.g.get("model_kind") == "extracted_twin" else ""
    kind = junction_kind(gr, nid)
    if kind == "instrument_tap":
        by = ", ".join(gr.name(i) for i in gr.tapped_by.get(nid, [])) or "an instrument"
        return (f"{gr.name(nid)} is the point {where}where {by}'s instrument line meets a pipe, which carries on "
                f"through it (an instrument tap, not a pipe tee)")
    if kind == "marked_crossing":
        return (f"{gr.name(nid)} is a point {where}where two lines cross and the drawing marks them joined with a "
                f"dot (a marked crossing)")
    if kind == "instrument_line_junction":
        return f"{gr.name(nid)} is a point {where}where instrument lines meet, away from any pipe"
    p = gr.pipe_arms.get(nid, 0)
    arms_words = f"{p} pipe" if p >= 3 else f"{fmt(arms) if arms else 'three or more'} line"
    return f"{gr.name(nid)} is a point {where}where {arms_words} arms meet (a pipe tee or branch)"


LINE_WORDS = {"pipe": ("pipe segment", "pipe segments"), "instrument": ("instrument line", "instrument lines"),
              "actuator": ("actuator stem", "actuator stems"), "nozzle": ("nozzle stub", "nozzle stubs")}


def network_text(gr, n):
    k = gr.net_items.get(n["id"], 0)
    if gr.g.get("model_kind") == "extracted_twin":
        nid = n["id"]
        at = gr.attr(nid, "joined_only_at") or []
        held = {x: gr.attr(nid, f"lines.{x}") or 0 for x in LINE_WORDS}
        what = [f"{v} {LINE_WORDS[x][v != 1]}" for x, v in held.items() if v and x != "pipe"]
        no_pipe = (f"; it holds no pipe, only {' and '.join(what)}" if what and not held["pipe"]
                   and gr.attr(nid, "lines.pipe") is not None else "")
        if at:
            return (f"{gr.name(nid)} is what the tracer joins as one drawn line network, with {k} "
                    f"item{'s' if k != 1 else ''} attached: its lines meet only at the edge of "
                    f"{', '.join(gr.obj_name(x) for x in at)}, which the line layers count as part of that item"
                    f"{no_pipe}")
        return (f"{gr.name(nid)} is one drawn line network: lines joined by bends, junctions or crossings with no "
                f"item between, with {k} item{'s' if k != 1 else ''} attached{no_pipe}")
    return (f"{gr.name(n['id'])} is one piece of piping with no item in it (joined only through tees), with {k} "
            f"item{'s' if k != 1 else ''} at its ends")


IDENTITY_SPECIAL["junction"] = junction_text
IDENTITY_SPECIAL["line_network"] = network_text


def connects_layer(gr, e):
    """What a connects edge means: its own `layer`, else (a graph exported before layers) by the model kind."""
    if e.get("layer"):
        return e["layer"]
    return "network_pair" if gr.g.get("model_kind") == "extracted_twin" else "stream"


def layer_of(gr, kind, edge=None, nid=None):
    if edge is not None:
        t = edge["type"]
        if t == "piped_to":
            return "pipe"
        if t in NON_PIPE_EDGES:
            return "non_pipe"
        if t == "on_network":
            return "network"
        if t == "connects":
            return connects_layer(gr, edge)
        return "item"
    if kind == "junction":
        return JUNCTION_LAYER.get(junction_kind(gr, nid), "pipe")
    return {"line_network": "network"}.get(kind, "item")


def identity_text(gr, n):
    if n["kind"] in IDENTITY_SPECIAL:
        return IDENTITY_SPECIAL[n["kind"]](gr, n)
    return f"{gr.name(n['id'])} is {KIND_WORDS[n['kind']]}"


def merged_value_statements(gr, n):
    """Statements made of two claims read together: a setpoint (value + unit), a limit (what + value + unit)."""
    by = {a["name"]: a for a in n["attributes"]}
    out, used = [], set()
    S = gr.name(n["id"])
    if "setpoint.value" in by:
        u = by.get("setpoint.uom")
        names = ["setpoint.value"] + (["setpoint.uom"] if u else [])
        text = f"{S} is set to hold {fmt(by['setpoint.value']['value'])}{' ' + fmt(u['value']) if u else ''} " \
               f"(its setpoint)"
        out.append((3, "setpoint", [by[x]["value"] for x in names], text, names))
        used.update(names)
    if n["kind"] == "limit" and "value" in by:
        names = [x for x in ("what", "value", "uom") if x in by]
        what = by["what"]["value"] if "what" in by else n.get("name")
        what = what[0].lower() + what[1:] if what and not what[:2].isupper() else what
        text = f"Limit {S}, {what}: {fmt(by['value']['value'])}{' ' + fmt(by['uom']['value']) if 'uom' in by else ''}"
        out.append((1, "limit_value", [by[x]["value"] for x in names], text, names))
        used.update(names)
    return out, used


# ----------------------------------------------------------------------------------------------- statements
def source_kind(src):
    return (src or {}).get("kind") or "model"


def doc_text(doc):
    """A source's document: a string, or a list of documents (the TE model cites two codes) joined."""
    return "; ".join(str(d) for d in doc) if isinstance(doc, list) else (doc or "")


def source_pointer(src):
    """One line a reviewer can follow to the source."""
    k = source_kind(src)
    if k == "drawing":
        b = src.get("box_0_1000")
        return (f"drawing sheet {src.get('sheet')}, box {[round(x) for x in b] if b else '?'} (0-1000 scale), "
                f"read as \u201c{src.get('read_as')}\u201d" if src.get("read_as") else
                f"drawing sheet {src.get('sheet')}, box {[round(x) for x in b] if b else '?'} (0-1000 scale)")
    if k == "document":
        doc = doc_text(src.get("document"))
        return f"document: {doc}" + (f" (evidence: {src['evidence']})" if src.get("evidence") else "")
    if k == "review":
        return f"review by {src.get('by')} on {src.get('on')} (was {fmt(src.get('was'))})"
    return "no source of its own" + (f" (the model's source document: {src.get('document')})"
                                     if src.get("document") else "")


def build(g):
    """Every statement in a graph, without evidence. Deterministic: the same graph gives the same ids and order."""
    gr = Graph(g)
    out = OrderedDict()
    skipped = Counter()

    def add(subject, predicate, obj, rank, stype, text, src, targets, kind, key=None, layer="item"):
        i = sid(subject, predicate, obj if key is None else key)
        if i in out:  # the same thing said twice (e.g. class and type both "tank"): one statement, every target
            out[i]["targets"] += [t for t in targets if t not in out[i]["targets"]]
            return
        system = gr.system_of(subject)
        group = gr.name(subject) if subject in gr.nodes else str(subject)
        text = text.rstrip(".") + "."
        text = text[0].upper() + text[1:]
        out[i] = {"id": i, "subject": subject, "predicate": predicate, "object": obj, "text": text,
                  "type": stype, "rank": rank, "rank_label": RANKS[rank], "stratum": f"{stype}|{rank}",
                  "layer": layer,
                  "group": group, "system": gr.name(system) if system and system != subject else None,
                  "subject_kind": kind, "source": src, "source_kind": source_kind(src),
                  "source_pointer": source_pointer(src), "targets": targets}

    for n in g["nodes"]:
        nid = n["id"]
        first_src = n["attributes"][0]["source"] if n.get("attributes") else \
            {"kind": "model", "note": "the item cites no source of its own"}
        nl = layer_of(gr, n["kind"], nid=nid)
        add(nid, "kind", n["kind"], 4, "identity", identity_text(gr, n), first_src, [["node", nid]], n["kind"],
            layer=nl)
        for al in n.get("aliases") or []:
            add(nid, "alias", al, 4, "identity", f"{gr.name(nid)} was also tagged {al} (an earlier tag)", first_src,
                [["node", nid]], n["kind"])
        merged, used = merged_value_statements(gr, n)
        for rank, pred, obj, text, names in merged:
            src = next(a["source"] for a in n["attributes"] if a["name"] == names[0])
            add(nid, pred, obj, rank, "attribute", text, src, [["claim", nid, x] for x in names], n["kind"],
                layer=nl)
        for a in n.get("attributes", []):
            name, v = a["name"], a["value"]
            if name in used:
                continue
            if (name in INTERNAL or name.startswith(INTERNAL_PREFIXES) or name.endswith(INTERNAL_SUFFIXES)):
                skipped["internal field: " + re.sub(r"\..*", ".*", name)] += 1
                continue
            if blank(v):
                skipped["empty value (nothing stated)"] += 1
                continue
            r = attr_statement(gr, n, a)
            if r[0] is None:
                skipped[r[1]] += 1
                continue
            rank, pred, text = r
            add(nid, pred, v, rank, "attribute", text, a["source"], [["claim", nid, name]], n["kind"], layer=nl)
    for e in g.get("edges", []):
        text = edge_text(gr, e)
        if text is None:
            raise ValueError(f"no sentence template for edge type {e['type']!r}")
        subject = e["to"] if e["type"] == "contains" else e["from"]
        obj = e["from"] if e["type"] == "contains" else e["to"]
        kind = gr.nodes.get(subject, {}).get("kind")
        rank = 1 if e["type"] == "acts_on" and gr.nodes.get(e["from"], {}).get("kind") == "interlock" \
            else EDGE_RANK[e["type"]]
        # Two streams between the same ends (a vent line and a relief line) are two statements: the stream's own
        # id is part of what is said, so it is part of the key.
        key = [obj, e["id"]] if e["type"] == "connects" and e.get("id") else None
        add(subject, "edge:" + e["type"], obj, rank, "relation", text, e.get("source"),
            [["edge", e["id"]]], kind, key, layer=layer_of(gr, kind, e))
    return list(out.values()), dict(sorted(skipped.items())), gr


# ----------------------------------------------------------------------------------------------- evidence
def parse_images(pairs):
    imgs = {}
    for p in pairs or []:
        if "=" not in p:
            raise ValueError(f"--image wants SHEET=PNG, got {p!r}")
        k, v = p.split("=", 1)
        imgs[k] = Path(v)
    return imgs


class Crops:
    """Crops of drawing boxes, saved once per box as small JPEGs under DIR/evidence/."""

    def __init__(self, images, out_dir, max_side=280):
        self.images, self.out, self.max_side, self.cache, self.opened = images, Path(out_dir), max_side, {}, {}

    def _img(self, sheet):
        if sheet not in self.opened:
            p = self.images.get(str(sheet))
            if p is None or not p.exists():
                self.opened[sheet] = None
            else:
                from PIL import Image
                self.opened[sheet] = Image.open(p).convert("RGB")
        return self.opened[sheet]

    def crop(self, sheet, boxes, margin_frac=0.8, min_margin=36):
        key = (str(sheet), tuple(tuple(round(x, 1) for x in b) for b in boxes))
        if key in self.cache:
            return self.cache[key]
        im = self._img(str(sheet))
        if im is None:
            self.cache[key] = None
            return None
        from PIL import ImageDraw
        W, H = im.size
        px = [(b[0] * W / 1000, b[1] * H / 1000, b[2] * W / 1000, b[3] * H / 1000) for b in boxes]
        x0, y0 = min(p[0] for p in px), min(p[1] for p in px)
        x1, y1 = max(p[2] for p in px), max(p[3] for p in px)
        m = max(min_margin, margin_frac * max(x1 - x0, y1 - y0)) if len(boxes) == 1 else min_margin
        X0, Y0, X1, Y1 = max(0, int(x0 - m)), max(0, int(y0 - m)), min(W, int(x1 + m)), min(H, int(y1 + m))
        c = im.crop((X0, Y0, X1, Y1)).copy()
        d = ImageDraw.Draw(c)
        for n, p in enumerate(px):
            d.rectangle((p[0] - X0 - 3, p[1] - Y0 - 3, p[2] - X0 + 3, p[3] - Y0 + 3),
                        outline=(220, 30, 30) if n == 0 else (30, 90, 220), width=3)
        side = self.max_side if len(boxes) == 1 else int(self.max_side * 1.3)
        c.thumbnail((side, side))
        name = "s%s_%s.jpg" % (re.sub(r"\W", "", str(sheet)) or "x",
                               hashlib.sha1(repr(key).encode()).hexdigest()[:10])
        (self.out / "evidence").mkdir(parents=True, exist_ok=True)
        c.save(self.out / "evidence" / name, "JPEG", quality=62, optimize=True)
        rel = "evidence/" + name
        self.cache[key] = rel
        return rel


PAGE_RE = re.compile(r"\bpp?\.\s*(\d+)(?:\s*[-\u2013]\s*(\d+))?")
FIG_RE = re.compile(r"\bFig(?:ure)?\.?\s*(\d+)")
# Words too common in a process description to tell one item from another when finding the subject on a page.
GENERIC = {"control", "controller", "valve", "system", "automatic", "unit", "line"}
STOP = set("the a an and or of to in on at by for with from is are was were be as it its this that not no into "
           "than then when which while only also has had have per about".split())


class Report:
    """The cited report, read page by page with whatever is installed (PyMuPDF, else pdftotext), to give the PDF
    page for a printed page number or figure, and the line on it that best matches a statement. Without either
    reader, only the cited page is given."""

    def __init__(self, pdf, out_dir=None):
        self.pdf, self.pages, self.reader = Path(pdf) if pdf else None, None, None
        self.out, self.fig_images = Path(out_dir) if out_dir else None, {}
        if self.pdf and self.pdf.exists():
            self.pages, self.reader = self._read()
        self.printed, self.figures = {}, {}
        for i, t in enumerate(self.pages or []):
            lines = [x.strip() for x in t.splitlines() if x.strip()]
            if lines and re.fullmatch(r"\d{1,3}", lines[0]):
                self.printed.setdefault(int(lines[0]), i)
            for x in lines:
                m = re.match(r"^Figure\s+(\d+)\.\s", x)
                if m and "...." not in x:
                    self.figures.setdefault(int(m.group(1)), i)

    def _read(self):
        try:
            import fitz  # PyMuPDF
            with fitz.open(str(self.pdf)) as d:
                return [p.get_text() for p in d], "PyMuPDF"
        except ImportError:
            pass
        if shutil.which("pdftotext"):
            try:
                r = subprocess.run(["pdftotext", "-layout", str(self.pdf), "-"], capture_output=True, timeout=120)
                return r.stdout.decode("utf-8", "replace").split("\f"), "pdftotext"
            except (OSError, subprocess.SubprocessError):
                pass
        return None, None

    def figure_image(self, f):
        """A figure is a drawing, not text: with PyMuPDF, render its page once as a small JPEG under evidence/."""
        if f in self.fig_images:
            return self.fig_images[f]
        rel = None
        if self.reader == "PyMuPDF" and self.out and f in self.figures:
            import fitz
            i = self.figures[f]
            done = [v for k, v in self.fig_images.items() if v and v.endswith(f"_pdfpage{i + 1}.jpg")]
            if done:  # two figures on one page: one image
                self.fig_images[f] = done[0]
                return done[0]
            with fitz.open(str(self.pdf)) as d:
                pix = d[i].get_pixmap(dpi=80)
                (self.out / "evidence").mkdir(parents=True, exist_ok=True)
                name = f"fig{f}_pdfpage{i + 1}.jpg"
                from PIL import Image
                Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(
                    self.out / "evidence" / name, "JPEG", quality=60, optimize=True)
                rel = "evidence/" + name
        self.fig_images[f] = rel
        return rel

    def cited(self, document):
        """Printed pages and figures a source string cites."""
        pages, figs = [], []
        document = doc_text(document)
        for m in PAGE_RE.finditer(document):
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else a
            pages += [p for p in range(a, min(b, a + 5) + 1) if p not in pages]
        for m in FIG_RE.finditer(document or ""):
            f = int(m.group(1))
            if f not in figs:
                figs.append(f)
        return pages, figs

    def evidence(self, document, value_tokens, subject_tokens):
        pages, figs = self.cited(document)
        ev = {"kind": "document", "cited_pages": pages, "cited_figures": figs}
        if not self.pages:
            ev["note"] = ("cited page(s) only: no PDF text reader available" if self.pdf else
                          "cited page(s) only: no report PDF given (--document)")
            return ev
        ev["reader"] = self.reader
        ev["pdf_pages"] = {str(p): self.printed[p] + 1 for p in pages if p in self.printed}
        ev["figure_pdf_pages"] = {str(f): self.figures[f] + 1 for f in figs if f in self.figures}
        imgs = [x for x in (self.figure_image(f) for f in figs) if x]
        if imgs:
            ev["figure_images"] = imgs
        best = None
        for p in pages:
            i = self.printed.get(p)
            if i is None:
                continue
            text = re.sub(r"\s+", " ", self.pages[i])
            for sent in re.split(r"(?<=[a-z0-9)\u201d\"][.;])\s+", text):
                if len(sent) > 600:
                    continue
                low = sent.lower()
                hit = sum(1 for t in value_tokens if re.search(r"(?<![\w.])" + re.escape(t) + r"(?![\w])", low))
                if not value_tokens or hit == 0:
                    continue
                need = 1 if all(re.fullmatch(r"[\d.,]+", t) for t in value_tokens) else \
                    max(2, math.ceil(len(value_tokens) / 2)) if len(value_tokens) > 1 else 1
                if hit < min(need, len(value_tokens)):
                    continue
                sub = sum(1 for t in subject_tokens if t in low)
                if sub < min(2, len(subject_tokens)):  # a line about something else would mislead: say nothing
                    continue
                score = hit / len(value_tokens) + 0.25 * min(sub, 3)
                if best is None or score > best[0]:
                    best = (score, p, sent.strip())
        if best:
            q = best[2]
            if len(q) > 320:
                first = min((q.lower().find(t) for t in value_tokens if q.lower().find(t) >= 0), default=0)
                start = max(0, first - 140)
                q = ("\u2026" if start else "") + q[start:start + 300] + "\u2026"
            ev["quote"] = q
            ev["quote_page"] = best[1]
            ev["quote_note"] = ("the line on the cited page that best matches the statement's words, found by word "
                                "match: read it, don't trust it")
        else:
            ev["note"] = ("no line on the cited page(s) matches the statement's words: read the page"
                          if value_tokens else "read the cited page(s)") + \
                ("; figures are drawings, look at them" if figs else "")
        return ev


def tokens(v):
    out = []
    for x in (v if isinstance(v, list) else [v]):
        if isinstance(x, bool) or x is None:
            continue
        if isinstance(x, (int, float)):
            f = float(x)
            forms = {fmt(x)}
            if f.is_integer() and abs(f) >= 1000:
                forms.add(f"{int(f):,}")
            out += sorted(forms)
        else:
            out += [w for w in re.findall(r"[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z]{3,}", str(x).lower().replace("_", " "))
                    if w not in STOP and len(w) >= 3 or re.fullmatch(r"\d+", w or "")]
    return list(dict.fromkeys(out))


def statement_tokens(st, gr):
    """Words to look for on the cited page: the value for a claim, the other end's name for a relation."""
    if st["type"] == "relation":
        n = gr.nodes.get(st["object"]) or {}
        return tokens(n.get("name") or "") or tokens(st["text"])
    if st["type"] == "identity":
        return []  # "X is an instrument" has no words of its own to find; a name match would point at the wrong item
    return tokens(st["object"])


def subject_tokens(st, gr):
    n = gr.nodes.get(st["subject"]) or {}
    return [w for w in tokens(n.get("name") or "") if not re.fullmatch(r"[\d.,]+", w) and w not in GENERIC][:4]


def add_evidence(statements, gr, crops, report):
    boxes = {}
    for n in gr.g["nodes"]:
        for a in n.get("attributes", []):
            s = a.get("source") or {}
            if s.get("kind") == "drawing" and s.get("box_0_1000"):
                boxes.setdefault(n["id"], (s.get("sheet"), s["box_0_1000"]))
                break
    for st in statements:
        src = st["source"] or {}
        k = st["source_kind"]
        if k == "drawing" and src.get("box_0_1000"):
            rel = crops.crop(src.get("sheet"), [src["box_0_1000"]]) if crops else None
            st["evidence"] = {"kind": "drawing_crop", "sheet": src.get("sheet"), "box_0_1000": src["box_0_1000"],
                              "image": rel, "note": None if rel else "no sheet image given (--image SHEET=PNG)"}
        elif k == "document":
            st["evidence"] = report.evidence(src.get("document"), statement_tokens(st, gr), subject_tokens(st, gr))
        elif k == "review":
            st["evidence"] = {"kind": "review", "note": source_pointer(src)}
        else:
            ev = {"kind": "none", "note": "no source of its own"}
            # A traced line cites nothing itself; show both ends on the drawing so the reviewer can follow it.
            if st["type"] == "relation":
                a, b = boxes.get(st["subject"]), boxes.get(st["object"])
                if a and b and a[0] == b[0] and crops:
                    rel = crops.crop(a[0], [a[1], b[1]])
                    if rel:
                        ev.update({"kind": "endpoints_on_drawing", "sheet": a[0], "image": rel,
                                   "note": ("no source of its own: the line was traced, not read from a box. The "
                                            "crop shows both ends (red, blue) so you can follow it on the sheet")})
            st["evidence"] = ev


# ----------------------------------------------------------------------------------------------- machine check
SECTION = {"equipment": ("units", "id"), "instrument": ("instruments", "tag"),
           "final_element": ("final_elements", "tag"), "controller": ("controllers", "tag"),
           "manual_valve": ("manual_valves", "tag"), "relief_device": ("relief_devices", "tag"),
           "interlock": ("interlocks", "id"), "limit": ("limits", "id")}


def find_model(g, model_arg=None):
    if model_arg:
        p = Path(model_arg)
    else:
        sm = g.get("source_model") or ""
        p = ROOT / sm if sm else None
    if g.get("model_kind") != "hand_built" or not p or not p.is_file():
        return None, None
    return json.loads(p.read_text(encoding="utf-8")), (p.resolve().relative_to(ROOT).as_posix()
                                                         if p.resolve().is_relative_to(ROOT) else p.name)


def model_item(m, kind, nid):
    sec, key = SECTION.get(kind, (None, None))
    if not sec:
        return None, None
    for n, it in enumerate(m.get(sec, []), 1):
        ident = it.get(key) or (f"LIM-{n}" if kind == "limit" else None)
        if ident == nid:
            return it, f"{sec}[{nid}]"
    return None, None


def model_field(it, name):
    if name in it:
        return True, it[name]
    if "." in name:
        a, b = name.split(".", 1)
        if isinstance(it.get(a), dict) and b in it[a]:
            return True, it[a][b]
    if isinstance(it.get("facts"), dict) and name in it["facts"]:
        return True, it["facts"][name]
    return False, None


def machine_check(statements, g, m, model_name):
    """For a hand-built model: is each statement exactly what the model's own field says? Only proves the export
    is faithful to the model."""
    gr = Graph(g)
    edges = {e["id"]: e for e in g.get("edges", [])}
    streams = {s["id"]: s for s in (m or {}).get("streams", [])}
    for st in statements:
        if m is None:
            st["machine_check"] = {"result": "not checked", "why": "no structured source in the repository to "
                                   "check against (an extracted drawing is checked by eye)"}
            continue
        results, fields = [], []
        for t in st["targets"]:
            if t[0] == "claim":
                node = gr.nodes[t[1]]
                it, where = model_item(m, node["kind"], t[1])
                if it is None:
                    results.append(None)
                    continue
                ok, val = model_field(it, t[2])
                claim = next(a for a in node["attributes"] if a["name"] == t[2])
                results.append(ok and val == claim["value"])
                fields.append(f"{where}.{t[2]}")
            elif t[0] == "node":
                node = gr.nodes[t[1]]
                it, where = model_item(m, node["kind"], t[1])
                if it is None and node["kind"] in ("plant", "boundary"):
                    results.append(None)
                    continue
                ok = it is not None
                if st["predicate"] == "alias":
                    ok = ok and it.get("former_tag") == st["object"]
                    fields.append(f"{where}.former_tag")
                else:
                    fields.append(where or f"{SECTION.get(node['kind'], ('?',))[0]}[{t[1]}]")
                results.append(ok)
            elif t[0] == "edge":
                e = edges[t[1]]
                ok, where = edge_in_model(m, gr, e, streams)
                results.append(ok)
                if where:
                    fields.append(where)
        if not results or all(r is None for r in results):
            st["machine_check"] = {"result": "not checked", "why": "no model field holds this statement"}
        elif all(r is True for r in results if r is not None):
            st["machine_check"] = {"result": "matches its model field", "fields": fields, "model": model_name,
                                   "note": MACHINE_NOTE}
        else:
            st["machine_check"] = {"result": "differs from its model field", "fields": fields, "model": model_name,
                                   "note": MACHINE_NOTE}


def edge_in_model(m, gr, e, streams):
    t, a, b = e["type"], e["from"], e["to"]
    kind_a = gr.nodes.get(a, {}).get("kind")
    if t == "connects":
        s = streams.get(e["id"])
        return (s is not None and s.get("from") == a and s.get("to") == b), f"streams[{e['id']}]"
    if t == "contains":
        it, where = model_item(m, gr.nodes.get(b, {}).get("kind"), b)
        return it is not None, where
    it, where = model_item(m, kind_a, a)
    if it is None:
        return False, None
    if t in ("measures", "protects") or (t == "acts_on" and kind_a != "interlock"):
        return it.get("unit") == b, f"{where}.unit"
    if t == "acts_on":
        return it.get("final_element") == b, f"{where}.final_element"
    if t == "sits_on":
        return f"stream:{it.get('stream')}" == b, f"{where}.stream"
    if t == "applies_to":
        return it.get("tag") == b, f"{where}.tag"
    if t == "controls":
        if gr.nodes.get(b, {}).get("kind") == "controller":
            c, w = model_item(m, "controller", b)
            return c is not None and c.get("measurement") == a, f"{w}.measurement"
        out = it.get("output") or {}
        return b == out.get("final_element") or b in (out.get("split_range") or []), f"{where}.output"
    if t == "sets_point_of":
        return (it.get("output") or {}).get("controller") == b, f"{where}.output.controller"
    if t == "trips":
        il, w = model_item(m, "interlock", b)
        return il is not None and il.get("measurement") == a, f"{w}.measurement"
    return False, None


# ----------------------------------------------------------------------------------------------- outputs
CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--line:#dcd9d0;--card:#fff;--accent:#9a3412;--ok:#166534;--warn:#92400e}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171716;--fg:#ecebe6;--muted:#a3a29b;
--line:#3a3935;--card:#21201e;--accent:#fb923c;--ok:#4ade80;--warn:#fbbf24}}
:root[data-theme="dark"]{--bg:#171716;--fg:#ecebe6;--muted:#a3a29b;--line:#3a3935;--card:#21201e;--accent:#fb923c;
--ok:#4ade80;--warn:#fbbf24}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:16px}h1{font-size:1.5rem;margin:.2em 0}h2{font-size:1.1rem;margin:1.6em 0
.4em;border-bottom:1px solid var(--line);padding-bottom:.2em}h2 small{color:var(--muted);font-weight:400}
.why{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.st{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) 170px;gap:10px;background:var(--card);
border:1px solid var(--line);border-radius:8px;padding:10px;margin:8px 0}
.st .text{font-weight:600}.meta,.src{color:var(--muted);font-size:.85rem}.ev img{max-width:100%;height:auto;
border:1px solid var(--line);border-radius:4px}.quote{border-left:3px solid var(--accent);padding-left:8px;font-size:.88rem}
.mc.ok{color:var(--muted)}.mc.bad{color:var(--warn)}label{display:block;font-size:.8rem;color:var(--muted);margin-top:4px}
select,input{width:100%;font:inherit;font-size:.85rem;background:var(--bg);color:var(--fg);border:1px solid var(--line);
border-radius:4px;padding:3px}button{font:inherit;padding:6px 12px;border-radius:6px;border:1px solid var(--accent);
background:var(--accent);color:#fff;cursor:pointer}code{font-size:.8rem}
.st>div,h1,h2,p{min-width:0;overflow-wrap:anywhere}a{color:var(--accent)}
@media (max-width:760px){.st{grid-template-columns:1fr}}
"""

WHY_HTML = """<div class="why"><p><b>Why this page exists.</b> Everything this model says can be said as a plain
statement, and every statement points at where it came from: a box on a drawing sheet, a page of a report, a field of
a model. Checking a sample of statements against their sources turns \u201cdoes this look right?\u201d into a measured
error rate, and lets someone who knows the unit check it in plain language without reading JSON.</p>
<p><b>Two separate verdicts, never mixed.</b> <i>Matches its source</i>: does the drawing box or report page say
this? Anyone can check that. <i>True in the plant</i>: is it actually so on the unit today? Only an operator, a
walkdown or live data can say, and only for a statement that matched its source (the second box stays locked until
the first says <i>match</i>). The \u201cmachine\u201d line, where shown, only proves the export says what the model
says, not that the model is right.</p></div>"""

JS = """
const rows=[...document.querySelectorAll('.st')];
function sync(r){const s=r.querySelector('.sm'),p=r.querySelector('.pt');p.disabled=s.value!=='match';
 if(p.disabled)p.value='';}
rows.forEach(r=>{r.querySelector('.sm').addEventListener('change',()=>sync(r));sync(r);});
function q(v){v=String(v??'');return /[",\\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;}
document.getElementById('dl').addEventListener('click',()=>{
 const who=document.getElementById('who').value;const cols=%s;
 const lines=[cols.join(',')];rows.forEach(r=>{const d=r.dataset;
 lines.push([d.id,d.group,d.stratum,d.layer,d.text,d.source,r.querySelector('.sm').value,r.querySelector('.pt').value,
 who,r.querySelector('.nt').value].map(q).join(','));});
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\n')+'\\n'],{type:'text/csv'}));
 a.download='review_sheet_reviewed.csv';a.click();});
"""


def evidence_html(ev, prefix):
    if not ev:
        return "<div class='src'>no evidence</div>"
    k = ev.get("kind")
    parts = []
    if ev.get("image"):
        parts.append(f"<img loading='lazy' src='{html.escape(prefix + ev['image'])}' alt='drawing crop'>")
    for im in ev.get("figure_images", []):
        parts.append(f"<a href='{html.escape(prefix + im)}'>{html.escape(im.split('/')[-1].split('_')[0])}"
                     f" (the figure page: open it)</a> ")
    if k == "document":
        pages = ", ".join(f"p. {p}" + (f" (PDF page {ev['pdf_pages'][str(p)]})" if str(p) in
                                         ev.get("pdf_pages", {}) else "") for p in ev.get("cited_pages", []))
        figs = ", ".join(f"Fig {f}" + (f" (PDF page {ev['figure_pdf_pages'][str(f)]})" if str(f) in
                                         ev.get("figure_pdf_pages", {}) else "") for f in ev.get("cited_figures", []))
        parts.append(f"<div class='src'>Cited: {html.escape('; '.join(x for x in (pages, figs) if x)) or 'no page'}"
                     "</div>")
        if ev.get("quote"):
            parts.append(f"<div class='quote'>p. {ev['quote_page']}: \u201c{html.escape(ev['quote'])}\u201d</div>"
                         f"<div class='src'>{html.escape(ev['quote_note'])}</div>")
    if ev.get("note"):
        parts.append(f"<div class='src'>{html.escape(ev['note'])}</div>")
    return "".join(parts)


def html_page(title, statements, prefix="", intro=""):
    groups = OrderedDict()
    for st in sorted(statements, key=lambda s: (s.get("system") or "", s["group"], s["rank"], s["text"])):
        groups.setdefault((st.get("system") or "", st["group"]), []).append(st)
    body = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>{CSS}</style>"
            f"</head><body><main><h1>{html.escape(title)}</h1>{intro}{WHY_HTML}"
            f"<p><label for='who' style='display:inline'>Reviewer</label> <input id='who' style='width:220px'> "
            f"<button id='dl'>Download the review sheet (CSV)</button></p>"]
    for (system, group), sts in groups.items():
        body.append(f"<h2>{html.escape(group)} <small>{html.escape('in ' + system) if system else ''} "
                    f"\u00b7 {len(sts)} statement(s)</small></h2>")
        for st in sts:
            mc = st.get("machine_check") or {}
            mch = ""
            if mc.get("result") in ("matches its model field", "differs from its model field"):
                cls = "ok" if mc["result"].startswith("matches") else "bad"
                mch = (f"<div class='mc {cls}' title='{html.escape(MACHINE_NOTE)}'>machine: {mc['result']} "
                       f"(<code>{html.escape(', '.join(mc.get('fields', [])))}</code>); proves only that the export "
                       f"is faithful to the model</div>")
            d = {"id": st["id"], "group": f"{system} \u203a {group}" if system else group, "stratum": st["stratum"],
                 "layer": st.get("layer", ""), "text": st["text"], "source": st["source_pointer"]}
            attrs = " ".join(f"data-{k}='{html.escape(str(v), quote=True)}'" for k, v in d.items())
            body.append(
                f"<div class='st' {attrs}><div><div class='text'>{html.escape(st['text'])}</div>"
                f"<div class='meta'>{html.escape(st['rank_label'])} \u00b7 layer: "
                f"{html.escape(st.get('layer') or 'n/a')} \u00b7 <code>{st['id']}</code></div>"
                f"<div class='src'>Source: {html.escape(st['source_pointer'])}</div>{mch}</div>"
                f"<div class='ev'>{evidence_html(st.get('evidence'), prefix)}</div>"
                f"<div><label>1. Matches its source?</label><select class='sm'><option value=''></option>"
                + "".join(f"<option>{v}</option>" for v in SOURCE_VERDICTS) +
                "</select><label>2. True in the plant? (after a match)</label><select class='pt'>"
                "<option value=''></option>" + "".join(f"<option>{v}</option>" for v in PLANT_VERDICTS) +
                "</select><label>Note</label><input class='nt'></div></div>")
    body.append(f"</main><script>{JS % json.dumps(list(SHEET_COLUMNS))}</script></body></html>")
    return "\n".join(body)


def write_sheet(path, statements):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(SHEET_COLUMNS)
        for st in statements:
            grp = f"{st['system']} \u203a {st['group']}" if st.get("system") else st["group"]
            w.writerow([st["id"], grp, st["stratum"], st.get("layer", ""), st["text"], st["source_pointer"], "", "",
                        "", ""])


def summary(statements):
    return {"statements": len(statements),
            "by_type": dict(sorted(Counter(s["type"] for s in statements).items())),
            "by_rank": {f"{r} {RANKS[r]}": n for r, n in sorted(Counter(s["rank"] for s in statements).items())},
            "by_stratum": dict(sorted(Counter(s["stratum"] for s in statements).items())),
            "evidence": dict(sorted(Counter(s["evidence"]["kind"] + (" (quoted line)" if s["evidence"].get("quote")
                                                                      else "")
                                            for s in statements).items())),
            "source_kind": dict(sorted(Counter(s["source_kind"] for s in statements).items())),
            "machine_check": dict(sorted(Counter(s.get("machine_check", {}).get("result", "not checked")
                                                 for s in statements).items()))}


def cmd_render(a):
    g = load_graph(a.graph)
    statements, skipped, gr = build(g)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    crops = Crops(parse_images(a.image), out)
    report = Report(a.document, out)
    add_evidence(statements, gr, crops, report)
    m, mname = find_model(g, a.model)
    machine_check(statements, g, m, mname)
    gp = Path(a.graph).resolve()
    doc = {"format": FORMAT, "graph": gp.relative_to(ROOT).as_posix() if gp.is_relative_to(ROOT) else gp.name,
           "graph_sha256": hashlib.sha256(gp.read_bytes()).hexdigest(), "title": g.get("title"),
           "verdicts": {"source_match": list(SOURCE_VERDICTS), "plant_truth": list(PLANT_VERDICTS),
                        "rule": "plant_truth only for a statement whose source_match is 'match'"},
           "ranks": {str(k): v for k, v in RANKS.items()},
           "report_reader": report.reader, "summary": summary(statements), "skipped": skipped,
           "statements": statements}
    (out / "statements.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                         newline="\n")
    write_sheet(out / "review_sheet.csv", statements)
    if not a.no_html:
        (out / "review.html").write_text(html_page(f"Statement review: {g.get('title') or doc['graph']}",
                                                   statements), encoding="utf-8", newline="\n")
    print(json.dumps(doc["summary"]))
    return 0


# ----------------------------------------------------------------------------------------------- sample
def allocate(sizes, n, floor=2):
    """Stratified allocation: every stratum gets min(floor, size), the rest proportionally (largest remainder)."""
    keys = sorted(sizes)
    total = sum(sizes.values())
    n = min(n, total)
    alloc = {k: min(floor, sizes[k]) for k in keys}
    while sum(alloc.values()) > n:  # too many strata for the floor: trim the largest allocations first
        k = max(keys, key=lambda k: (alloc[k], k))
        alloc[k] -= 1
    left = n - sum(alloc.values())
    while left > 0:
        room = {k: sizes[k] - alloc[k] for k in keys if sizes[k] > alloc[k]}
        if not room:
            break
        rt = sum(room.values())
        want = {k: left * room[k] / rt for k in room}
        add = {k: min(room[k], int(want[k])) for k in room}
        if sum(add.values()) == 0:
            for k in sorted(room, key=lambda k: (-(want[k] - int(want[k])), k))[:left]:
                add[k] = 1
        for k, v in add.items():
            alloc[k] += v
        left = n - sum(alloc.values())
    return alloc


def draw_sample(statements, n, seed, floor=2):
    by = {}
    for st in statements:
        by.setdefault(st["stratum"], []).append(st)
    sizes = {k: len(v) for k, v in by.items()}
    alloc = allocate(sizes, n, floor)
    picked = []
    for k in sorted(by):
        pool = sorted(by[k], key=lambda s: s["id"])
        rng = random.Random(f"{seed}:{k}")
        picked += rng.sample(pool, alloc[k])
    def described(k):
        if "|" in k:
            t, r = k.split("|", 1)
            return {"type": t, "rank": int(r), "rank_label": RANKS[int(r)]}
        return {"type": None, "rank": None, "rank_label": LAYERS.get(k, k)}
    strata = [{"stratum": k, **described(k), "population": sizes[k], "sampled": alloc[k],
               "weight": round(sizes[k] / alloc[k], 4) if alloc[k] else None} for k in sorted(by)]
    return picked, strata


def cmd_sample(a):
    sp = Path(a.statements)
    doc = json.loads(sp.read_text(encoding="utf-8"))
    if doc.get("format") != FORMAT:
        print(f"{sp.name} is not a statements file (format {FORMAT}); make one with: statements.py render",
              file=sys.stderr)
        return 2
    pool = doc["statements"]
    if a.strata == "layer":
        missing = [x["id"] for x in pool if not x.get("layer")]
        if missing:
            print(f"{sp.name}: {len(missing)} statement(s) have no layer (render it again with this version)",
                  file=sys.stderr)
            return 2
        pool = [dict(x, stratum=x["layer"]) for x in pool]
    picked, strata = draw_sample(pool, a.n, a.seed, a.floor)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    s = {"format": "statement-sample-1", "statements_file": sp.name,
         "statements_sha256": hashlib.sha256(sp.read_bytes()).hexdigest(), "graph": doc.get("graph"),
         "seed": a.seed, "n": len(picked), "floor": a.floor,
         "strata_by": a.strata,
         "method": (f"stratified random sample; strata = "
                    f"{'relationship layer' if a.strata == 'layer' else 'statement type x consequence rank'}; "
                    f"every stratum gets "
                    f"min({a.floor}, its size), the rest is split in proportion to stratum size (largest "
                    f"remainder); within a stratum, random.Random('{a.seed}:<stratum>').sample over statements "
                    f"sorted by id. Small strata are over-sampled on purpose: use each stratum's weight "
                    f"(population / sampled) for a plant-wide estimate."),
         "strata": strata, "statements": sorted(picked, key=lambda x: (x["stratum"], x["id"]))}
    out.write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    write_sheet(out.with_suffix(".csv"), s["statements"])
    # The sample's page is self-contained: the evidence images it shows are copied next to it.
    missing = 0
    if sp.parent.resolve() != out.parent.resolve():
        for st in s["statements"]:
            ev = st.get("evidence") or {}
            for rel in ([ev["image"]] if ev.get("image") else []) + ev.get("figure_images", []):
                src, dst = sp.parent / rel, out.parent / rel
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
                elif not dst.exists():
                    missing += 1
    if missing:
        print(f"note: {missing} evidence image(s) named in {sp.name} were not found beside it", file=sys.stderr)
    prefix = ""
    intro = (f"<p>A stratified random sample of {len(picked)} of {len(doc['statements'])} statements "
             f"(seed {a.seed}). Strata: " + ", ".join(f"{x['stratum']} ({x['rank_label']}) {x['sampled']}/"
                                                      f"{x['population']}" for x in strata) + "</p>")
    out.with_suffix(".html").write_text(html_page(f"Statement review sample: {doc.get('title') or doc.get('graph')}",
                                                  s["statements"], prefix, intro), encoding="utf-8", newline="\n")
    print(f"{len(picked)} statements, seed {a.seed}, {len(strata)} strata -> {out}, "
          f"{out.with_suffix('.csv').name}, {out.with_suffix('.html').name}")
    for x in strata:
        print(f"  {x['stratum']:<14} {x['rank_label']:<28} {x['sampled']:>3} of {x['population']}")
    return 0


# ----------------------------------------------------------------------------------------------- score
def wilson(k, n, z=Z95):
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def read_sheet(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows and not Path(path).read_text(encoding="utf-8-sig").strip():
        raise ValueError(f"{Path(path).name} is empty")
    need = {"statement_id", "source_match", "plant_truth"}
    with open(path, encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f), [])
    if not need <= set(header):
        raise ValueError(f"{Path(path).name} is not a review sheet: it needs columns {sorted(need)}")
    return rows


def score(rows, strata_weights=None, layer_of_id=None):
    """Error rates for MATCHES ITS SOURCE, per relationship layer (the row's `layer`, else layer_of_id[statement]).
    With more than one layer in the rows there is no overall rate: each layer is its own number."""
    bad_values, ignored_plant = [], []
    tally = {}
    plant = Counter()
    layer_of_id = layer_of_id or {}
    for r in rows:
        sm = (r.get("source_match") or "").strip().lower()
        pt = (r.get("plant_truth") or "").strip().lower()
        lay = ((r.get("layer") or "").strip() or layer_of_id.get((r.get("statement_id") or "").strip())
               or "unlabelled")
        st = (lay, (r.get("stratum") or "all").strip() or "all")
        if sm and sm not in SOURCE_VERDICTS:
            bad_values.append((r.get("statement_id"), "source_match", sm))
            sm = ""
        if pt and pt not in PLANT_VERDICTS:
            bad_values.append((r.get("statement_id"), "plant_truth", pt))
            pt = ""
        t = tally.setdefault(st, Counter())
        t[sm or "not reviewed"] += 1
        if pt:
            if sm == "match":
                plant[pt] += 1
            else:
                ignored_plant.append(r.get("statement_id"))
        elif sm == "match":
            plant["not given"] += 1

    def block(c):
        n = c["match"] + c["mismatch"]
        lo, hi = wilson(c["mismatch"], n)
        return {"checked": n, "mismatch": c["mismatch"], "match": c["match"], "unclear": c["unclear"],
                "not_reviewed": c["not reviewed"], "error_rate": round(c["mismatch"] / n, 4) if n else None,
                "wilson95": [round(lo, 4), round(hi, 4)] if n else None}
    layers = sorted({k[0] for k in tally})
    by_layer = {}
    for lay in layers:
        strata = {k[1]: v for k, v in sorted(tally.items()) if k[0] == lay}
        b = {"overall": block(sum(strata.values(), Counter())), "by_stratum": {k: block(v) for k, v in strata.items()}}
        if strata_weights:
            num = den = 0.0
            for k, x in b["by_stratum"].items():
                if k in strata_weights and x["checked"]:
                    num += strata_weights[k] * x["error_rate"]
                    den += strata_weights[k]
            b["weighted_by_population"] = round(num / den, 4) if den else None
        by_layer[lay] = b
    sm_res = {"by_layer": by_layer}
    if len(layers) == 1:  # one layer: its numbers are the sheet's numbers (an older sheet has no layer column)
        sm_res.update(by_layer[layers[0]])
    else:
        sm_res["overall"] = None
        sm_res["overall_note"] = (f"not reported: the rows hold {len(layers)} relationship layers "
                                  f"({', '.join(layers)}), each a different fact; see by_layer")
    res = {"source_match": sm_res,
           "plant_truth": dict(plant), "plant_truth_note": ("counted only for statements that matched their source; "
                                                            "never mixed into the source error rate"),
           "ignored_plant_verdicts": ignored_plant, "bad_values": bad_values}
    return res


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def cmd_score(a):
    try:
        rows = read_sheet(a.sheet)
    except (OSError, ValueError) as exc:
        print(f"can't score: {exc}", file=sys.stderr)
        return 2
    weights, layer_ids = None, {}
    if a.sample:
        s = json.loads(Path(a.sample).read_text(encoding="utf-8"))
        weights = {x["stratum"]: x["population"] for x in s["strata"]}
        layer_ids = {x["id"]: x["layer"] for x in s.get("statements", []) if x.get("layer")}
    r = score(rows, weights, layer_ids)
    if a.json:
        print(json.dumps(r, indent=1))
        return 0
    by_layer = r["source_match"]["by_layer"]
    if len(by_layer) > 1:
        print(f"MATCHES ITS SOURCE, per relationship layer (no blended rate: {len(by_layer)} layers are different "
              f"facts)")
    for lay, L in by_layer.items():
        o = L["overall"]
        head = "MATCHES ITS SOURCE" if len(by_layer) == 1 else f"[{lay}] {LAYERS.get(lay, lay)}\n "
        print(f"{head}: {o['mismatch']} mismatch of {o['checked']} checked = error rate {pct(o['error_rate'])}"
              + (f" (Wilson 95%: {pct(o['wilson95'][0])} to {pct(o['wilson95'][1])})" if o["wilson95"] else "")
              + f"; unclear {o['unclear']}; not reviewed {o['not_reviewed']}")
        if "weighted_by_population" in L:
            print(f"  weighted to the whole population (stratum sizes from the sample file): "
                  f"{pct(L['weighted_by_population'])}")
        for k, b in L["by_stratum"].items():
            ci = f"{pct(b['wilson95'][0])}-{pct(b['wilson95'][1])}" if b["wilson95"] else "n/a"
            print(f"  {k:<14} {b['mismatch']:>3}/{b['checked']:<3} error {pct(b['error_rate']):>6}  95% {ci:<15} "
                  f"unclear {b['unclear']}")
    print(f"TRUE IN THE PLANT (separate; only statements that matched their source): "
          + (", ".join(f"{k} {v}" for k, v in sorted(r["plant_truth"].items())) or "none given"))
    if r["ignored_plant_verdicts"]:
        print(f"  ignored {len(r['ignored_plant_verdicts'])} plant verdict(s) on statements that did not match their "
              f"source: {', '.join(r['ignored_plant_verdicts'][:10])}")
    for b in r["bad_values"]:
        print(f"  unknown {b[1]} value {b[2]!r} on {b[0]} (ignored)")
    return 0


# ----------------------------------------------------------------------------------------------- apply
def new_status(sm, pt):
    """Status a target takes from a verdict pair, or None to leave it. A source match alone confirms nothing about
    the plant, so it leaves the status as it was."""
    if sm == "mismatch":
        return "rejected"
    if sm == "match" and pt == "confirmed":
        return "confirmed"
    if sm == "match" and pt == "wrong":
        return "rejected"
    return None


def apply(g, rows, reviewer=None, date=None, record=None):
    """Write verdicts onto the graph's claims, nodes and edges as checks + statuses, plus one event per verdict.
    Values are never touched. Returns (graph, applied, refused)."""
    g = json.loads(json.dumps(g))
    statements, _, gr = build(g)
    by_id = {s["id"]: s for s in statements}
    nodes = {n["id"]: n for n in g["nodes"]}
    edges = {e["id"]: e for e in g["edges"]}
    applied, refused = [], []
    for r in rows:
        i = (r.get("statement_id") or "").strip()
        sm = (r.get("source_match") or "").strip().lower()
        pt = (r.get("plant_truth") or "").strip().lower()
        who = (r.get("reviewer") or "").strip() or reviewer
        if not sm and not pt:
            continue
        if i not in by_id:
            refused.append((i, "no such statement in this graph (was the sheet made from another graph?)"))
            continue
        if sm not in SOURCE_VERDICTS or (pt and pt not in PLANT_VERDICTS):
            refused.append((i, f"unknown verdict source_match={sm!r} plant_truth={pt!r}"))
            continue
        if pt and sm != "match":
            refused.append((i, "a plant verdict needs the statement to match its source first; the two are never "
                               "mixed"))
            continue
        if not who:
            refused.append((i, "no reviewer (fill the reviewer column or pass --reviewer)"))
            continue
        st = by_id[i]
        status = new_status(sm, pt)
        check = {"statement": i, "source_match": sm, "plant_truth": pt or None, "by": who, "on": date}
        for t in st["targets"]:
            if t[0] == "claim":
                obj = next(a for a in nodes[t[1]]["attributes"] if a["name"] == t[2])
            elif t[0] == "node":
                obj = nodes[t[1]]
            else:
                obj = edges[t[1]]
            obj.setdefault("checks", []).append(check)
            if status and not (t[0] == "node" and st["predicate"] == "alias"):
                obj["status"] = status
        g.setdefault("events", []).append(
            {"type": "statement_review", "item": st["targets"][0][1], "statement": i, "text": st["text"],
             "source_match": sm, "plant_truth": pt or None, "status_set": status, "by": who, "on": date,
             "record": record})
        applied.append(i)
    g.setdefault("counts", {})["events"] = len(g.get("events", []))
    return g, applied, refused


def cmd_apply(a):
    try:
        g = load_graph(a.graph)
        rows = read_sheet(a.sheet)
    except (OSError, ValueError) as exc:
        print(f"can't apply: {exc}", file=sys.stderr)
        return 2
    date = a.date or datetime.date.today().isoformat()
    out, applied, refused = apply(g, rows, a.reviewer, date, Path(a.sheet).name)
    sys.path.insert(0, str(ROOT / "scripts"))
    import graph_export
    bad = graph_export.problems(out)
    if bad:
        for b in bad:
            print("FAIL:", b, file=sys.stderr)
        return 1
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(applied)} verdict(s) applied, {len(refused)} refused -> {a.out}")
    for i, why in refused:
        print(f"  refused {i}: {why}")
    return 1 if refused else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="graph -> statements.json, review.html, review_sheet.csv")
    r.add_argument("graph")
    r.add_argument("--image", action="append", metavar="SHEET=PNG", help="sheet image for drawing crops")
    r.add_argument("--document", metavar="PDF", help="the report the document sources cite (for page quotes)")
    r.add_argument("--model", help="the hand-built model to machine-check against (default: the graph's "
                                   "source_model, when it is in this repository)")
    r.add_argument("--no-html", action="store_true", help="skip review.html (for a very large graph)")
    r.add_argument("--out", required=True)
    s = sub.add_parser("sample", help="stratified random sample for an independent reviewer")
    s.add_argument("statements")
    s.add_argument("--n", type=int, default=60)
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--floor", type=int, default=2, help="minimum per stratum (default 2)")
    s.add_argument("--strata", choices=("type-rank", "layer"), default="type-rank",
                   help="type-rank (default): statement type x consequence rank; layer: one stratum per relationship "
                        "layer (pipe, network, network_pair, item, ...), so each layer gets its own error rate")
    s.add_argument("--out", required=True)
    c = sub.add_parser("score", help="error rate per stratum with Wilson 95%% intervals")
    c.add_argument("sheet")
    c.add_argument("--sample", help="the sample file, to weight strata back to the whole population")
    c.add_argument("--json", action="store_true")
    p = sub.add_parser("apply", help="write verdicts back onto the graph (statuses + events, values untouched)")
    p.add_argument("graph")
    p.add_argument("sheet")
    p.add_argument("--reviewer", help="used for rows with an empty reviewer column")
    p.add_argument("--date", help="date of the review (default today)")
    p.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        return {"render": cmd_render, "sample": cmd_sample, "score": cmd_score, "apply": cmd_apply}[a.cmd](a)
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
