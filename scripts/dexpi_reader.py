"""A DEXPI P&ID XML file -> a process model with every attribute kept as a sourced claim (no model, no drawing).
Written for DEXPI 1.x; tested on the DEXPI 1.3 examples, the DEXPI TrainingTestCases (DEXPI 1.2 reference and
tool exports, DEXPI 1.3 single-feature cases) and synthetic files.

    python -S scripts/dexpi_reader.py --xml my_pid.xml --out my-model
    python -S scripts/dexpi_reader.py --xml my_pid.xml --out my-model --sheet-id unit-47 --compare-key KEYDIR
    python scripts/dexpi_reader.py --xml my_pid.xml --out my-model --png my_pid.png   # also an intake prediction

A plant that exports its P&IDs from a CAD tool as DEXPI XML (the Proteus / ISO 15926 exchange format) already
holds the equipment, lines, valves and instruments as data, with their sizes, specs and design limits. This reads
that file directly with the standard library and writes, into --out:

  <id>.model.json    a hand-built-style process model, the schema scripts/generate.py and scripts/graph_export.py
                     accept (meta, units, streams, instruments, final_elements, controllers, manual_valves,
                     relief_devices). Every item names the XML element it came from (dexpi_id, source). Every
                     GenericAttribute of the item, its parts (nozzles, chambers, actuators, sensors, fittings, line
                     segments) and its labels is kept as a nested record {value, uom, source} under the item, keyed
                     by the DEXPI attribute name ("Chamber-3:UpperLimitDesignPressure" for a part's attribute).
                     graph_export.py turns each into a claim sourced to that element: on the item's node, or for
                     a line on its `connects` edge. Also `line_layers`: the pipe layer (segments between units,
                     valves and PipeTee junctions; see scripts/line_layers.py) and the line networks it implies.
  <id>.report.json   what was read, kept, folded, dropped and why, with counts; also printed
  <id>.report.md     the printed report as text
  with --png (a render of the whole drawing extent): <id>.prediction.json + <id>.intake-manifest.json and an exact
                     <id>.source.png copy, referenced by filename so the intake folder can move; for
                     scripts/import_site_drawing.py, built with the same rules as dexpi_to_twin.py (needs the
                     drawing geometry; imports adapt_dexpi.py, dexpi_to_twin.py and score_pid2graph.py)

Mapping rules (each departure is written into the report):
  Equipment     top-level Equipment -> a unit. id = TagNameAssignmentClass, else the drawn tag label, else the
                element's TagName XML attribute (DEXPI 1.2 exports), else the XML ID. type: pumps -> pump;
                compressors, blowers, fans -> compressor; heat exchangers, heaters and coolers -> heat_exchanger;
                condensers -> condenser; columns -> stripper (the generator's only column symbol; approximate);
                reactors -> reactor; tanks and silos -> tank; pressure vessels -> pressure_vessel; separators ->
                separator; vessels -> vessel. Any other class is kept with its DEXPI class, drawn as a generic
                vessel, and listed as unmapped. Nested equipment (chambers, impellers, tube bundles, column
                sections) and nozzles are folded into their unit as parts.
  Lines         each PipingNetworkSystem -> one stream per pair of real ends it joins (a unit through a nozzle,
                an off-page connector, or a line end that leaves the sheet = BL). Ends are followed through other
                lines and tees in the drawn From/To direction. A line whose far end is only closed (blind,
                plug, vent valve) keeps one stream to BL and says so in to_end. Line, segment, fitting and
                off-page connector attributes ride on the stream. A segment Connection whose FromID/ToID names
                no element in the file is a broken reference: BL stands in, and the stream's from_end/to_end,
                meta.broken_references and the report say so (the real end is unknown).
  Valves        valves an ActuatingSystem operates (one of its components "refers to" the valve, or the valve "is
                referenced by" one: OperatedValveReference in DEXPI 1.3, ShutOffValveReference in 1.2) ->
                final_elements. Tag: the first that holds letters + number of the actuating system number, the
                referencing component's SubTagName, the system's drawn number label, the valve's own number or
                tag attribute or TagName, the actuating function's number. Also operated: a valve with an
                actuator drawn inside it (Comos: Equipment or Component nested in the PipingComponent), a valve an
                actuator InstrumentComponent shares a loop with (Proteus 3.3.3), and a control valve written as an
                instrument (ControlValve-class ProcessInstrumentationFunction, in-line ProcessInstrument), which is
                the valve and its tag bubble in one element. Safety and relief valves, bursting discs ->
                relief_devices; other valves -> manual_valves. Tags with no unique identifier in the file use the
                XML ID (drawn spec codes repeat).
  Instruments   a ProcessInstrumentationFunction (bubble) is a controller when it drives a valve actuator, or when
                its letters hold the control function C after the first letter (LIC, PICSA, YCS; letters =
                category + functions + modifier attributes, else the drawn label). A controller that drives no
                valve but signals another controller sets that one's point (output.setpoint_of, a cascade); one
                with no sensor of its own measures the instrument bubble that signals it. A controller's sensor
                (the ProcessSignalGeneratingFunction, nested or joined by a measuring line) -> an instrument
                tagged with the sensor's own number, which the controller measures. A bubble that is not a
                controller -> an instrument with its own tag, sensor folded in. A bubble whose tag is the operated
                valve's own tag is folded into that final element. Bubbles are ProcessInstrumentationFunction, and
                in Proteus 3.3.3 ProcessInstrument / InstrumentComponent; with no letter attributes the letters come
                from the bubble's TagName or Tag, and a letters-only tag (Comos "FIC") takes its loop's number. A
                signal line (InformationFlow, SignalLine) between a bubble and an actuator, either direction, or
                from a bubble to an operated valve, means the bubble drives that valve; a line or leader from a
                bubble to a plant element (nozzle, equipment, pipe item or segment) places it there. A pipe segment
                that ends at or holds a bubble (AutoCAD leaders, Proteus 3.3.3 instrument runs) is not process pipe:
                it places the bubble and its records ride on the bubble. A bubble wired only to bubbles takes the
                unit of the one that signals it, else of the one it signals.
  Units of instruments and valves are inferred: the first unit upstream through the piping from where the sensor
                or valve sits (else downstream); the basis is written on the item (unit_basis).
Not read: geometry, presentation, the shape catalogue, flow arrows and slope or insulation marks (attributes on
them are counted as dropped). Person names in the drawing metadata are left out on purpose.

Stdlib only, offline. No model is called. The model is a draft: nothing in it is verified by anyone.
"""
import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from pathlib import Path

TOOL = "dexpi_reader.py"
PRODUCER = {"method": "converted from DEXPI XML, no model", "tool": TOOL, "model": None}
MAX_BYTES = 256 * 1024 * 1024
INLINE_TAGS = ("PipingComponent", "PipeOffPageConnector", "PropertyBreak")
# Instrument functions (bubbles): DEXPI 1.x ProcessInstrumentationFunction; Proteus 3.3.3 (SPPID) ProcessInstrument and
# InstrumentComponent. One of these that is a valve in the line (class with "valve", or IsInline True) is read as an
# operated valve instead, and an InstrumentComponent of an actuator class as an actuator.
BUBBLE_TAGS = ("ProcessInstrumentationFunction", "ProcessInstrument", "InstrumentComponent")
LOOP_TAGS = ("InstrumentationLoopFunction", "InstrumentLoop")
FLOW_TAGS = ("InformationFlow", "SignalLine")
NOT_ITEMS = {"PipeFlowArrow": "flow arrow (direction comes from segment From/To)",
             "PipeSlopeSymbol": "slope mark", "InsulationSymbol": "insulation mark (insulation attributes are on the line)",
             "Symbol": "annotation symbol", "MetaData": "drawing metadata (kept in meta)"}
PERSON_ATTRS = re.compile(r"(Approver|Checker|Creator|Designer|Drafter|Editor|Reviewer|Owner)Name", re.I)
ISA_VARIABLE = {"A": "composition", "B": "burner/combustion", "C": "user's choice", "D": "density", "E": "voltage",
                "F": "flow", "G": "gauging/position", "H": "hand", "I": "current", "J": "power", "K": "time",
                "L": "level", "M": "moisture", "N": "user's choice", "O": "user's choice", "P": "pressure",
                "Q": "quantity", "R": "radiation", "S": "speed", "T": "temperature", "U": "multivariable",
                "V": "vibration", "W": "weight", "X": "unclassified", "Y": "event/state", "Z": "position"}
ISA_FUNCTION = {"A": "alarm", "C": "control", "E": "sensor", "G": "glass/gauge", "I": "indicate", "K": "control station",
                "L": "light", "O": "orifice", "P": "test point", "Q": "totalize", "R": "record", "S": "switch",
                "T": "transmit", "V": "valve", "W": "well", "Y": "relay/compute", "Z": "final element/safety",
                "H": "high", "D": "difference"}
# (words in the DEXPI class, generator type, basis). First match wins; checked against the class name.
UNIT_TYPES = [
    (("Pump",), "pump", "exact"),
    (("Compressor",), "compressor", "exact"),
    (("Blower", "Fan"), "compressor", "approximate: drawn with the compressor symbol"),
    (("Condenser",), "condenser", "exact"),
    (("HeatExchanger", "Heater", "Cooler", "Boiler", "Evaporator"), "heat_exchanger", "approximate: heat transfer equipment"),
    (("Column",), "stripper", "approximate: a column, drawn with the generator's only column symbol (trayed stripper)"),
    (("Reactor",), "reactor", "exact"),
    (("Tank", "Silo"), "tank", "exact"),
    (("PressureVessel",), "pressure_vessel", "exact"),
    (("Separator", "Cyclone", "Filter", "Scrubber"), "separator", "approximate: separation equipment"),
    (("Vessel",), "vessel", "exact"),
]
RESERVED = {"id", "tag", "name", "type", "unit", "stream", "from", "to", "source", "description", "variable", "uom",
            "measurement", "output", "layout", "kind", "facts", "status", "verification", "provenance", "confidence"}
BROKEN = "broken-ref:"   # chain marker for a Connection end that names an ID not in the file
RELIEF_WORDS = ("Safety", "Relief", "BurstingDisc", "RuptureDisc", "Breather", "Flame")


class DexpiError(ValueError):
    """The file cannot be read as a DEXPI P&ID; nothing was written."""


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def humanize(cls):
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", cls or "item").split()
    return " ".join([words[0]] + [w.lower() for w in words[1:]]) if words else "Item"


def label_lines(label):
    return [t.get("String", "").strip() for t in label.iter("Text") if t.get("String", "").strip()]


def split_tag(text):
    """'PV4712.02' / 'PV 4712.02' -> ('PV', '4712.02'); None if there are no leading letters."""
    m = re.match(r"\s*(\D+?)[\s-]*(\d.*)$", text or "")
    if not m or not m.group(1).strip():
        return None
    return m.group(1).strip(), m.group(2).strip()


def isa_tag(letters, number):
    """One letters-number tag with exactly one '-' (generate.py splits tags on it)."""
    letters = re.sub(r"[\s\-]", "", letters or "")
    number = re.sub(r"\s+", "", number or "").replace("-", "_")
    return f"{letters}-{number}"


class Reader:
    def __init__(self, xml_path, sheet_id=None, attribution=None):
        self.path = Path(xml_path)
        if not self.path.is_file():
            raise DexpiError(f"{self.path.name}: no such file")
        if self.path.stat().st_size > MAX_BYTES:
            raise DexpiError(f"{self.path.name}: larger than {MAX_BYTES} bytes; refusing to parse")
        try:
            self.root = ET.parse(self.path).getroot()
        except ET.ParseError as exc:
            raise DexpiError(f"{self.path.name}: not well-formed XML ({exc}); nothing was written") from exc
        for el in self.root.iter():  # tolerate a default namespace: DEXPI 1.x files usually have none
            if isinstance(el.tag, str) and "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]
        if self.root.tag != "PlantModel":
            raise DexpiError(f"{self.path.name}: root element is <{self.root.tag}>, not <PlantModel>: not a DEXPI "
                             "(Proteus XML) P&ID file; nothing was written")
        self.sheet_id = sheet_id or re.sub(r"[^A-Za-z0-9_.-]+", "-", self.path.stem).strip("-") or "dexpi-sheet"
        self.attribution = attribution
        self.parent = {c: p for p in self.root.iter() for c in p}
        cat = self.root.find("ShapeCatalogue")
        self.catalogue = set(cat.iter()) if cat is not None else set()
        self.by_id, dup = {}, []
        for el in self.root.iter():
            if el in self.catalogue or not el.get("ID"):
                continue
            if el.get("ID") in self.by_id:
                dup.append(el.get("ID"))
            self.by_id[el.get("ID")] = el
        if dup:
            raise DexpiError(f"{self.path.name}: element IDs used more than once ({', '.join(sorted(set(dup))[:8])}); "
                             "references would be ambiguous; nothing was written")
        if not any(el.tag in ("Equipment", "PipingNetworkSystem") + BUBBLE_TAGS for el in self.by_id.values()):
            raise DexpiError(f"{self.path.name}: a <PlantModel> with no equipment, piping or instrumentation; "
                             "nothing to read")
        # Associations by the element that holds them. Proteus 3.3.3 (SPPID) names the target by TagName, its GUID
        # without the ID's letter prefix (ID "SP5539...", TagName "5539..."); resolved when exactly one ID matches.
        guid = defaultdict(list)
        for i in self.by_id:
            m = re.fullmatch(r"[A-Za-z_]*([0-9A-Fa-f]{32})", i)
            if m:
                guid[m.group(1).upper()].append(i)
        self.resolve = lambda ref: ref if ref in self.by_id else (  # noqa: E731
            guid[ref.upper()][0] if ref and len(guid.get(ref.upper(), [])) == 1 else None)
        self.assoc = defaultdict(list)
        for el in self.by_id.values():
            for a in el.findall("Association"):
                self.assoc[el.get("ID")].append((a.get("Type"), a.get("ItemID") or self.resolve(a.get("TagName"))))
        self.ga_state = {}         # GenericAttribute element -> "claim" | "meta" | "unplaced" | ("dropped", reason)
        self.element_fate = {}     # element ID -> what became of it
        self.notes = []
        self.broken_refs = []      # segment Connection FromID/ToID values that name no element in the file
        self.used_ids = {"PLANT", "BL"}

    # ------------------------------------------------------------ attributes and labels

    def own_gas(self, el):
        for gs in el.findall("GenericAttributes"):
            for ga in gs.findall("GenericAttribute"):
                yield gs.get("Set"), ga

    def records(self, el, prefix="", into=None, state="claim", what=None):
        """Every GenericAttribute directly on el -> {key: {value, uom, source}}. Empty values are dropped and counted."""
        into = {} if into is None else into
        eid = el.get("ID") or el.tag
        for set_name, ga in self.own_gas(el):
            name, value = ga.get("Name") or "unnamed", ga.get("Value")
            if value is None or value == "":
                self.ga_state[ga] = ("dropped", "no value in the file")
                continue
            if state == "claim" and PERSON_ATTRS.search(name):
                self.ga_state[ga] = ("dropped", "person name: left out on purpose")
                continue
            key = prefix + name + (f"@{ga.get('Language')}" if ga.get("Language") else "")
            if key in RESERVED:   # a custom attribute may not overwrite a model field
                key = "dexpi:" + key
            n, base = 2, key
            while key in into:
                key, n = f"{base}#{n}", n + 1
            rec = {"value": value}
            if ga.get("Units"):
                rec["uom"] = ga.get("Units")
            if set_name and set_name != "DexpiAttributes":
                rec["attribute_set"] = set_name
            rec["source"] = f"DEXPI XML {eid} GenericAttribute {name}" + (f" ({what})" if what else "")
            into[key] = rec
            self.ga_state[ga] = state
        for cp in el.findall("ConnectionPoints"):   # port sizes live on connection-point nodes
            for i, node in enumerate(cp.findall("Node")):
                nid = node.get("ID") or f"{eid}-node{i}"
                if node.get("ID"):
                    self.fate(node, f"connection point {i} of {eid}")
                if list(self.own_gas(node)):
                    self.records(node, f"{prefix}{nid}:", into, state, f"connection point {i} of {eid}")
        return into

    def label_records(self, el, prefix="", into=None):
        into = {} if into is None else into
        eid = el.get("ID") or el.tag
        for lab in el.findall("Label"):
            lines = label_lines(lab)
            if not lines:
                self.fate(lab, "empty label")
                continue
            cls = lab.get("ComponentClass") or "Label"
            key, n = f"{prefix}label:{cls}", 2
            base = key
            while key in into:
                key, n = f"{base}#{n}", n + 1
            into[key] = {"value": " | ".join(lines), "source": f"DEXPI XML {eid} {cls} (drawn label text)"}
            if lab.get("ID"):
                self.fate(lab, f"label of {eid}")
        return into

    def part(self, el, into, state="claim", what=None):
        """Fold a part (nozzle, chamber, actuator, sensor, fitting, segment...) into an item, keyed by its XML ID."""
        pid = el.get("ID")
        into[f"{pid}:dexpi_class"] = {"value": el.get("ComponentClass") or el.tag,
                                      "source": f"DEXPI XML {pid} <{el.tag}>"}
        self.records(el, f"{pid}:", into, state, what)
        self.label_records(el, f"{pid}:", into)
        return into

    def ga(self, el, name):
        for _, g in self.own_gas(el):
            if g.get("Name") == name and g.get("Value"):
                return g.get("Value")
        return None

    def labels(self, el, cls=None):
        for lab in el.findall("Label"):
            if cls is None or lab.get("ComponentClass") == cls:
                lines = label_lines(lab)
                if lines:
                    return lines
        return None

    def claim_id(self, wanted, fallback, why):
        """A unique node id: the wanted identifier, else the XML ID (case-insensitive check, as generate.py does)."""
        taken = {u.lower() for u in self.used_ids}
        for cand, basis in ((wanted, why), (fallback, "XML ID (no unique identifier in the file)")):
            if cand and cand.lower() not in taken:
                self.used_ids.add(cand)
                return cand, basis
        n = 2
        while f"{fallback}_{n}".lower() in taken:
            n += 1
        self.used_ids.add(f"{fallback}_{n}")
        return f"{fallback}_{n}", "XML ID with a suffix (identifier already used)"

    def live(self, tag):
        return [el for el in self.root.iter(tag) if el not in self.catalogue]

    def fate(self, el, what):
        if el.get("ID") and el.get("ID") not in self.element_fate:
            self.element_fate[el.get("ID")] = what

    # ------------------------------------------------------------ equipment

    def equipment(self):
        units, self.unit_of = [], {}
        for eq in self.live("Equipment"):
            p, nested = self.parent.get(eq), False
            while p is not None:
                if p.tag == "Equipment":
                    nested = True
                    break
                p = self.parent.get(p)
            if nested:
                continue
            cls = eq.get("ComponentClass") or "Equipment"
            label = self.labels(eq, "EquipmentTagNameLabel")
            # DEXPI 1.2 exports also write the tag as the element's TagName XML attribute (Proteus schema 4.0).
            ident, why = next(((v, b) for v, b in ((self.ga(eq, "TagNameAssignmentClass"), "TagNameAssignmentClass"),
                                                   (label[0] if label else None, "drawn tag label"),
                                                   (eq.get("TagName"), "TagName XML attribute")) if v and v.strip()),
                              (None, None))
            uid, id_basis = self.claim_id(ident.strip() if ident else None, eq.get("ID"), why)
            utype, basis = "vessel", f"no generator type for DEXPI class {cls}: drawn as a generic vessel"
            for words, t, b in UNIT_TYPES:
                if any(w in cls for w in words):
                    utype, basis = t, b
                    break
            desc = (self.ga_lang(eq, "EquipmentDescriptionAssignmentClass"))
            unit = {"id": uid, "name": f"{desc} ({humanize(cls)})" if desc else humanize(cls), "type": utype,
                    "type_basis": basis, "dexpi_class": cls, "dexpi_id": eq.get("ID"), "id_basis": id_basis,
                    "source": f"DEXPI XML {eq.get('ID')} ({cls})"}
            self.records(eq, "", unit)
            self.label_records(eq, "", unit)
            self.fate(eq, f"unit {uid}")
            self.unit_of[eq.get("ID")] = uid
            for sub in eq.iter():
                if sub is eq or not sub.get("ID") or sub.tag in ("Label", "Node"):
                    continue
                if sub.tag in ("Equipment", "Nozzle") or list(self.own_gas(sub)):
                    self.part(sub, unit)
                    self.unit_of[sub.get("ID")] = uid
                    self.fate(sub, f"part of unit {uid}")
            if any(w in cls for w in ("Section", "Chamber", "Impeller", "TubeBundle", "Packing", "Agitator")):
                self.notes.append(f"{eq.get('ID')} ({cls}) is top-level in the file with no link to the equipment it "
                                  f"belongs to; kept as its own unit {uid}")
            if basis.startswith("no generator type"):
                self.unmapped_classes[cls] += 1
            units.append(unit)
        return units

    def ga_lang(self, el, name):
        vals = {g.get("Language"): g.get("Value") for _, g in self.own_gas(el) if g.get("Name") == name and g.get("Value")}
        return vals.get("en") or vals.get(None) or next(iter(vals.values()), None)

    # ------------------------------------------------------------ piping

    def roles(self):
        """Which instrument-like elements are bubbles, which are valves in the line, which are actuators."""
        valve_like = lambda el: "valve" in (el.get("ComponentClass") or "").lower() or \
            (self.ga(el, "IsInline") or "").lower() == "true"  # noqa: E731
        self.inline_valves = {i for i, el in self.by_id.items() if el.tag in BUBBLE_TAGS[:2] and valve_like(el)
                              and el not in self.catalogue}
        self.actuator_valve = {}   # actuator element ID -> the valve it sits in (nested) or None (decided by its loop)
        for i, el in self.by_id.items():
            if el in self.catalogue or el.tag not in ("Equipment", "Component", "InstrumentComponent"):
                continue
            p = self.parent.get(el)
            while p is not None and not (p.tag == "PipingComponent" or p.get("ID") in self.inline_valves):
                p = self.parent.get(p)
            if p is not None:              # Comos: the actuator is drawn inside its valve
                self.actuator_valve[i] = p.get("ID")
            elif el.tag == "InstrumentComponent" and "actuator" in (el.get("ComponentClass") or "").lower():
                self.actuator_valve[i] = None
        self.bubble_ids = {i for i, el in self.by_id.items() if el.tag in BUBBLE_TAGS and el not in self.catalogue
                           and i not in self.inline_valves and i not in self.actuator_valve}

    def is_inline(self, c):
        return bool(c.get("ID")) and (c.tag in INLINE_TAGS or c.get("ID") in self.inline_valves)

    def piping(self):
        self.succ, self.pred = defaultdict(list), defaultdict(list)
        self.seg_pns, self.item_seg, self.pns_edges = {}, {}, defaultdict(list)
        self.leaders, self.leader_segs = [], set()   # (bubble ID, other end ID or None, segment) for measuring leaders
        self.pns_list = self.live("PipingNetworkSystem")
        for pns in self.pns_list:
            for seg in pns.iter("PipingNetworkSegment"):
                self.seg_pns[seg.get("ID")] = pns
                conn = seg.find("Connection")
                ends = [conn.get(k) for k in ("FromID", "ToID")] if conn is not None else []
                bubbles = [e for e in ends if e in self.bubble_ids] + \
                          [c.get("ID") for c in seg if c.get("ID") in self.bubble_ids and c.get("ID") not in ends]
                if bubbles:
                    # A segment that ends at (or holds) an instrument bubble is a leader or an instrument run, not
                    # process pipe (AutoCAD leaders, Proteus 3.3.3 instrument pipe runs): it places the bubble.
                    others = [e for e in ends if e and e not in self.bubble_ids and e in self.by_id]
                    for b in bubbles:
                        for o in others or [None]:
                            self.leaders.append((b, o, seg))
                    self.leader_segs.add(seg.get("ID"))
                    continue
                inline = [c for c in seg if self.is_inline(c)]
                chain = [self.connection_end(seg, conn, "FromID", "open-start")]
                chain += [c.get("ID") for c in inline]
                chain.append(self.connection_end(seg, conn, "ToID", "open-end"))
                for c in inline:
                    self.item_seg[c.get("ID")] = seg
                for a, b in zip(chain, chain[1:]):
                    if a == b:
                        continue
                    self.succ[a].append(b)
                    self.pred[b].append(a)
                    self.pns_edges[pns.get("ID")].append((a, b, seg.get("ID")))
                for c in seg:
                    if c.get("ID") and not self.is_inline(c) and c.tag not in NOT_ITEMS and c.tag != "Label":
                        self.notes.append(f"{seg.get('ID')}: child <{c.tag}> {c.get('ID')} has no rule; dropped")

    def connection_end(self, seg, conn, attr, open_kind):
        """A segment end: the ID its Connection names, an open end if none, or a broken-reference marker when the
        named ID is not in the file (the file is defective there; the end is unknown, not closed)."""
        ref = conn.get(attr) if conn is not None else None
        if not ref:
            return f"{open_kind}:{seg.get('ID')}"
        if ref in self.by_id:
            return ref
        self.broken_refs.append({"element": seg.get("ID"), "attribute": attr, "missing_id": ref})
        self.notes.append(f"{seg.get('ID')}: broken reference: Connection {attr}={ref!r} names no element in the file; "
                          "BL stands in for that end, which is unknown")
        return f"{BROKEN}{attr}:{ref}"

    def terminal(self, node):
        if node in self.unit_of:
            return ("unit", self.unit_of[node], node)
        el = self.by_id.get(node)
        if el is not None and el.tag == "PipeOffPageConnector":
            return ("BL", "BL", node)
        if node.startswith(("open-start:", "open-end:", BROKEN)):
            return ("BL", "BL", node)
        return None

    def walk(self, start, graph, want=lambda t: t is not None):
        """Breadth-first along graph (succ or pred) to the first terminal satisfying want."""
        seen, q, dead = {start}, deque([(start, 0)]), None
        while q:
            n, d = q.popleft()
            t = self.terminal(n)
            if t and want(t):
                return t, d
            if t and n != start:
                continue      # do not walk through a unit or off the sheet
            if not graph.get(n) and dead is None:
                dead = n
            for m in graph.get(n, []):
                if m not in seen:
                    seen.add(m)
                    q.append((m, d + 1))
        return None, dead

    def unit_for(self, node):
        """(unit id, basis) for an item on a pipe or a nozzle, or (None, reason)."""
        if node in self.unit_of:
            return self.unit_of[node], f"on {node} of the unit"
        is_unit = lambda t: t[0] == "unit"
        t, d = self.walk(node, self.pred, is_unit)
        if t:
            return t[1], f"first unit upstream through the piping from {node} ({d} step(s), via {t[2]})"
        t, d = self.walk(node, self.succ, is_unit)
        if t:
            return t[1], f"no unit upstream; first unit downstream from {node} ({d} step(s), via {t[2]})"
        return None, f"no unit reachable through the piping from {node}"

    def streams(self):
        out, self.stream_of_item, self.first_stream, self.leader_pns = [], {}, {}, []
        for pns in self.pns_list:
            pid = pns.get("ID")
            edges = self.pns_edges.get(pid, [])
            label = self.labels(pns, "PipingNetworkSystemLabel")
            base = self.ga(pns, "LineNumberAssignmentClass") or (label[0] if label else None) or pid
            segs_all = list(pns.iter("PipingNetworkSegment"))
            if not edges and segs_all and all(sg.get("ID") in self.leader_segs for sg in segs_all):
                self.leader_pns.append(pns)   # only leaders / instrument runs: folded into their bubble later
                continue
            self.fate(pns, "stream(s)")
            if not edges:
                self.notes.append(f"{pid}: line with no segments; its attributes are dropped")
                for _, g in self.own_gas(pns):
                    self.ga_state.setdefault(g, ("dropped", "line with no segments"))
                continue
            succ, targets = defaultdict(list), set()
            for a, b, s in edges:
                succ[a].append((b, s))
                targets.add(b)
            entries = list(dict.fromkeys(a for a, _, _ in edges if a not in targets)) or [edges[0][0]]
            pairs = []
            for entry in entries:
                up = self.terminal(entry) or self.walk(entry, self.pred)[0] or                     ("closed", "BL", self.walk(entry, self.pred)[1] or entry)
                stack = [(entry, [entry], [])]
                while stack:
                    n, path, segs = stack.pop()
                    nxt = [(m, s) for m, s in succ.get(n, []) if m not in path]
                    if not nxt:
                        down = self.terminal(n) or self.walk(n, self.succ)[0] or                             ("closed", "BL", self.walk(n, self.succ)[1] or n)
                        pairs.append((up, down, path, segs))
                    for m, s in reversed(nxt):
                        stack.append((m, path + [m], segs + [s]))
            real = [p for p in pairs if p[0][0] != "closed" and p[1][0] != "closed"]
            keep = real or pairs[:1]
            seen_pairs, made = set(), []
            for up, down, path, segs in keep:
                key = (up[1], down[1], up[2], down[2])
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                sid, basis = self.claim_stream_id(base if not made else f"{base}:{len(made) + 1}", pid)
                st = {"id": sid, "name": f"Line {base}: {up[1]} to {down[1]}", "from": up[1], "to": down[1],
                      "dexpi_id": pid, "dexpi_class": pns.get("ComponentClass") or "PipingNetworkSystem",
                      "source": f"DEXPI XML {pid} (PipingNetworkSystem), segments {', '.join(dict.fromkeys(segs))}",
                      "from_item": up[2], "to_item": down[2]}
                for end, t in (("from_end", up), ("to_end", down)):
                    if t[2].startswith(BROKEN):
                        attr, ref = t[2][len(BROKEN):].split(":", 1)
                        st[end] = (f"broken reference: a segment Connection {attr} names {ref!r}, which is not in the "
                                   "file; BL stands in and the real end is unknown")
                    elif t[0] == "closed":
                        st[end] = f"closed end at {t[2]}: the line stops here; BL stands in because a stream needs two ends"
                    elif t[2].startswith("open-"):
                        st[end] = f"line end with no connector ({t[2]}): leaves the sheet"
                if made:
                    st["same_line_as"] = made[0]["id"]
                st["_path"], st["_segs"] = path, set(segs)
                made.append(st)
            first = made[0]
            self.first_stream[pid] = first["id"]
            self.records(pns, "", first)
            self.label_records(pns, "", first)
            for seg in pns.iter("PipingNetworkSegment"):
                if seg.get("ID") in self.leader_segs:
                    continue   # folded into its bubble
                owner = next((m for m in made if seg.get("ID") in m["_segs"]), first)
                self.part(seg, owner)
                self.fate(seg, f"part of stream {owner['id']}")
                for c in seg:
                    if self.is_inline(c):
                        on = next((m for m in made if c.get("ID") in m["_path"]), first)
                        self.stream_of_item[c.get("ID")] = on["id"]
            for m in made:
                del m["_path"], m["_segs"]
            out += made
        return out

    def claim_stream_id(self, wanted, pid):
        taken = {s.lower() for s in self.stream_ids}
        cand = wanted if wanted.lower() not in taken else f"{wanted} ({pid})"
        self.stream_ids.add(cand)
        return cand, None

    # ------------------------------------------------------------ valves and fittings

    def actuation(self):
        """valve ID -> ActuatingSystem element; actuator/component ID -> valve ID; ActuatingFunction ID -> valve ID."""
        self.asys_of_valve, self.valve_of_component, self.valve_of_afunc = {}, {}, {}
        self.valve_ref_of = {}   # valve ID -> the ActuatingSystemComponent that references it
        is_valve = lambda i: i in self.by_id and self.by_id[i].tag == "PipingComponent"  # noqa: E731
        # Reverse associations: a valve that "is referenced by" a component, an actuating function that "is fulfilled
        # by" a system. DEXPI 1.3 writes OperatedValveReference, DEXPI 1.2 ShutOffValveReference; any component of
        # the system that refers to a piping component in the file operates it.
        referenced_by = defaultdict(list)
        for pc in self.live("PipingComponent"):
            for t, iid in self.assoc.get(pc.get("ID"), []):
                if t == "is referenced by":
                    referenced_by[iid].append(pc.get("ID"))
        fulfilled_by = defaultdict(list)
        for af in self.live("ActuatingFunction"):
            for t, iid in self.assoc.get(af.get("ID"), []):
                if t == "is fulfilled by":
                    fulfilled_by[iid].append(af.get("ID"))
        for asys in self.live("ActuatingSystem"):
            valves = []
            for comp in asys.iter("ActuatingSystemComponent"):
                refs = [iid for t, iid in self.assoc.get(comp.get("ID"), []) if t == "refers to" and is_valve(iid)]
                refs += referenced_by.get(comp.get("ID"), [])
                for v in refs:
                    self.valve_ref_of.setdefault(v, comp)
                valves += refs
            valves = list(dict.fromkeys(valves))
            afuncs = [iid for t, iid in self.assoc.get(asys.get("ID"), []) if t == "fulfills"]
            afuncs = list(dict.fromkeys(afuncs + fulfilled_by.get(asys.get("ID"), [])))
            for v in valves:
                self.asys_of_valve[v] = asys
                for comp in asys.iter("ActuatingSystemComponent"):
                    self.valve_of_component[comp.get("ID")] = v
                for iid in afuncs:
                    self.valve_of_afunc[iid] = v
            if not valves:
                self.notes.append(f"{asys.get('ID')}: actuating system operates no valve in the file")
        # Loops and their members (a loop "is a collection including" X, X "is a part of" a loop, or X nested in it).
        self.loop_members = {}
        for lp in [el for el in self.by_id.values() if el.tag in LOOP_TAGS and el not in self.catalogue]:
            m = [i for t, i in self.assoc.get(lp.get("ID"), []) if t == "is a collection including" and i]
            m += [e.get("ID") for e in lp.iter() if e is not lp and e.get("ID")]
            self.loop_members[lp.get("ID")] = set(m)
        for i in self.by_id:
            for t, lid in self.assoc.get(i, []):
                if t == "is a part of" and lid in self.loop_members:
                    self.loop_members[lid].add(i)
        # Actuators with no ActuatingSystem: drawn inside their valve (Comos), or an actuator InstrumentComponent of a
        # loop whose one valve it then operates (Proteus 3.3.3).
        self.actuators_of_valve = defaultdict(list)
        for a, v in list(self.actuator_valve.items()):
            if v is None:
                cands = {x for mem in self.loop_members.values() if a in mem for x in mem
                         if x in self.inline_valves or (x in self.by_id and self.by_id[x].tag == "PipingComponent")}
                if len(cands) == 1:
                    v = self.actuator_valve[a] = cands.pop()
                else:
                    self.notes.append(f"{a}: actuator with {len(cands)} valves in its loop; the valve it moves is unknown")
            if v:
                self.actuators_of_valve[v].append(a)
        # Operated valves: by an actuating system, by an actuator, or a control valve written as an instrument.
        self.operated = set(self.asys_of_valve) | set(self.actuators_of_valve) | set(self.inline_valves)

    def final_tag(self, valve_id):
        """The operated valve's tag: the first of these the file holds as letters + number. The actuating system's
        number, the SubTagName on the component that references the valve (DEXPI 1.2), the system's drawn number
        label, the valve's own number or tag attribute (the 1.3 single-feature cases), the actuating function's
        number."""
        asys = self.asys_of_valve.get(valve_id)
        valve, ref = self.by_id[valve_id], self.valve_ref_of.get(valve_id)
        lines = self.labels(asys, "ActuatingSystemNumberLabel") if asys is not None else None
        cands = [(self.ga(asys, "ActuatingSystemNumberAssignmentClass") if asys is not None else None,
                  "ActuatingSystemNumberAssignmentClass"),
                 (self.ga(ref, "SubTagNameAssignmentClass") if ref is not None else None,
                  f"SubTagNameAssignmentClass of {ref.get('ID') if ref is not None else ''} (the valve reference)"),
                 (" ".join(lines[:2]) if lines else None, "drawn actuating system label"),
                 (self.ga(valve, "PipingComponentNumberAssignmentClass"),
                  "PipingComponentNumberAssignmentClass of the operated valve"),
                 (self.ga(valve, "TagNameAssignmentClass"), "TagNameAssignmentClass of the operated valve"),
                 (valve.get("TagName"), "TagName XML attribute of the operated valve"),
                 (self.ga(valve, "Tag") or self.ga(valve, "TagName"), "Tag attribute of the operated valve")]
        cands += [(self.ga(self.by_id[iid], "ActuatingFunctionNumberAssignmentClass"),
                   f"ActuatingFunctionNumberAssignmentClass of {iid}")
                  for iid, v in self.valve_of_afunc.items() if v == valve_id and iid in self.by_id]
        for text, basis in cands:
            parts = split_tag(text) if text else None
            if parts:
                return isa_tag(*parts), basis
        return None, None

    def components(self):
        finals, manual, relief, unplaced = [], [], [], []
        self.final_of_valve = {}
        valves = [el for el in self.root.iter() if el not in self.catalogue and el.get("ID")
                  and (el.tag == "PipingComponent" or el.get("ID") in self.inline_valves)]
        for pc in valves:
            vid, cls = pc.get("ID"), pc.get("ComponentClass") or pc.tag
            stream = self.stream_of_item.get(vid)
            label = self.labels(pc)
            if vid in self.operated:
                tag, tag_basis = self.final_tag(vid)
                tag, tag_basis = self.claim_id(tag, vid, tag_basis) if tag else self.claim_id(None, vid, None)
                asys = self.asys_of_valve.get(vid)
                unit, ubasis = self.unit_for(vid)
                fail = None
                acts = self.actuators_of_valve.get(vid, [])
                if asys is not None:
                    by, kind = f"operated by {asys.get('ID')} (ActuatingSystem)", "actuating system"
                elif acts:
                    by, kind = f"operated by actuator {', '.join(acts)} (no ActuatingSystem in the file)", "actuator"
                else:
                    by, kind = "", "instrument in line"
                if vid in self.inline_valves:   # a control valve written as an instrument (AutoCAD, Proteus 3.3.3)
                    by = (by + "; " if by else "") + \
                        f"<{pc.tag}> in line: the operated valve and its tag bubble are one element (bubble {vid})"
                item = {"tag": tag, "unit": unit, "description": "", "dexpi_class": cls, "dexpi_id": vid,
                        "tag_basis": tag_basis, "unit_basis": ubasis, "source": f"DEXPI XML {vid} ({cls}), {by}"}
                if stream:
                    item["stream"] = stream
                self.records(pc, "", item)
                self.label_records(pc, "", item)
                for a in acts:
                    ael = self.by_id[a]
                    if a not in self.element_fate:   # an actuator the file also declares as Equipment stays a unit
                        self.part(ael, item)
                        self.fate(ael, f"actuator of final element {tag}")
                    fail = fail or self.ga(ael, "FailActionSpecialization")
                if asys is not None:
                    self.part(asys, item)
                for comp in (asys.iter("ActuatingSystemComponent") if asys is not None else []):
                    self.part(comp, item)
                    self.fate(comp, f"part of final element {tag}")
                    fail = fail or self.ga(comp, "FailActionSpecialization") or self.ga(comp, "FailActionRepresentationAssignmentClass")
                for iid, v in self.valve_of_afunc.items():
                    if v == vid and iid in self.by_id:
                        self.part(self.by_id[iid], item)
                        self.fate(self.by_id[iid], f"part of final element {tag}")
                if asys is not None:
                    self.fate(asys, f"part of final element {tag}")
                item["description"] = f"{humanize(cls)} operated by {kind} {tag}" + (f", fail action {fail}" if fail else "")
                self.final_of_valve[vid] = item
                self.fate(pc, f"final element {tag}")
                if unit:
                    finals.append(item)
                else:
                    item["unplaced_reason"] = f"final_elements need a unit; {ubasis}"
                    unplaced.append(("final_element", item))
            elif "Valve" in cls or any(w in cls for w in RELIEF_WORDS):
                is_relief = any(w in cls for w in RELIEF_WORDS)
                ident, why = None, None
                for name in ("TagNameAssignmentClass", "PositionNumberAssignmentClass"):
                    if self.ga(pc, name):
                        ident, why = self.ga(pc, name), name
                        break
                if ident is None and is_relief and label:
                    ident, why = label[0], "drawn label"
                tag, tag_basis = self.claim_id(ident, vid, why)
                item = {"tag": tag, "description": humanize(cls) + (f" (drawn label {' / '.join(label)})" if label else ""),
                        "dexpi_class": cls, "dexpi_id": vid, "tag_basis": tag_basis,
                        "source": f"DEXPI XML {vid} ({cls})"}
                if stream:
                    item["stream"] = stream
                if is_relief:
                    unit, ubasis = self.unit_for(vid)
                    if unit:
                        item["unit"], item["unit_basis"] = unit, ubasis
                self.records(pc, "", item)
                self.label_records(pc, "", item)
                (relief if is_relief else manual).append(item)
                self.fate(pc, f"{'relief device' if is_relief else 'manual valve'} {tag}")
        return finals, manual, relief, unplaced

    def fold_fittings(self, streams):
        """In-line items that are not valves (tees, reducers, flanges, blinds, orifices, off-page connectors)."""
        by_id = {s["id"]: s for s in streams}
        for el in self.by_id.values():
            if el.tag not in INLINE_TAGS or el.get("ID") in self.element_fate:
                continue
            sid = self.stream_of_item.get(el.get("ID"))
            if sid is None:
                continue
            self.part(el, by_id[sid])
            self.fate(el, f"part of stream {sid}")
            for sub in el.iter():
                if sub is not el and sub.get("ID") and sub.tag not in ("Label", "Node"):
                    self.part(sub, by_id[sid])
                    self.fate(sub, f"part of stream {sid}")
            self.folded[el.get("ComponentClass") or el.tag] += 1

    # ------------------------------------------------------------ instrumentation

    def flows(self):
        """Signal and measuring lines -> (class, start ID, end ID, element), keyed by ID (or position when the flow
        has none, as Comos writes them). InformationFlow (DEXPI 1.x) and SignalLine (Proteus 3.3.3)."""
        out = {}
        for n, fl in enumerate(el for el in self.root.iter() if el.tag in FLOW_TAGS and el not in self.catalogue):
            a = {}
            for x in fl.findall("Association"):
                if x.get("Type") in ("has logical start", "has logical end"):
                    a.setdefault(x.get("Type"), x.get("ItemID") or self.resolve(x.get("TagName")))
            conn = fl.find("Connection")
            start = a.get("has logical start") or (conn.get("FromID") if conn is not None else None) or None
            end = a.get("has logical end") or (conn.get("ToID") if conn is not None else None) or None
            out[fl.get("ID") or f"flow#{n}"] = (fl.get("ComponentClass") or fl.tag, start, end, fl)
        return out

    def is_place(self, x):
        """A plant element an instrument can sit on: a unit or nozzle, a pipe item or segment."""
        el = self.by_id.get(x)
        return el is not None and x not in self.bubble_ids and x not in self.actuator_valve and (
            x in self.unit_of or x in self.inline_valves
            or el.tag in ("Equipment", "Nozzle", "PipingComponent", "PipingNetworkSegment", "PipeOffPageConnector"))

    def loop_number(self, pid):
        for lid, mem in self.loop_members.items():
            if pid in mem:
                lp = self.by_id[lid]
                n = self.ga(lp, "InstrumentationLoopFunctionNumberAssignmentClass") or lp.get("TagName") \
                    or self.ga(lp, "TagName")
                if n and n.strip():
                    return n.strip(), f"number of the loop {lid}"
        return None, None

    def instrumentation(self, finals_by_valve):
        flows = self.flows()
        pifs = [el for el in self.root.iter() if el.get("ID") in self.bubble_ids]
        instruments, controllers, unplaced = [], [], []
        info = {}
        for pif in pifs:
            pid = pif.get("ID")
            cat = self.ga(pif, "ProcessInstrumentationFunctionCategoryAssignmentClass")
            funcs = self.ga(pif, "ProcessInstrumentationFunctionsAssignmentClass")
            mod = self.ga(pif, "ProcessInstrumentationFunctionModifierAssignmentClass")
            if mod and mod not in (funcs or ""):   # a hand switch: category H, modifier S, no functions (DEXPI 1.2)
                funcs = (funcs or "") + mod
            num = self.ga(pif, "ProcessInstrumentationFunctionNumberAssignmentClass")
            lines = self.labels(pif, "ProcessInstrumentationFunctionLabel") or self.labels(pif)
            tag_text = next((t.strip() for t in (pif.get("TagName"), self.ga(pif, "TagName"), self.ga(pif, "Tag"))
                             if t and t.strip() and re.match(r"[A-Za-z]", t.strip())), None)
            if cat and num:
                letters, number, basis = (cat + (funcs or "")), num, "category + functions + number attributes"
            elif lines and len(lines) >= 2:
                letters, number, basis = lines[0], lines[1], "drawn bubble label"
            elif tag_text and split_tag(tag_text):     # "PICSA 4712.02" (Proteus 3.3.3), "LI-123" (AutoCAD)
                (letters, number), basis = split_tag(tag_text), "the bubble's tag attribute"
            elif cat or (tag_text and re.fullmatch(r"[A-Za-z]+", tag_text)):
                # Letters only on the bubble (Comos: TagName "FIC"); the number is the loop's, as ISA tags are built.
                letters = cat + (funcs or "") if cat else tag_text
                number, nbasis = self.loop_number(pid)
                basis = ("category + functions attributes" if cat else "the bubble's tag attribute") + \
                    (f" + {nbasis}" if number else " (no number in the file)")
                if not number:
                    letters = None
            else:
                letters, number, basis = None, None, None
            sensors = [s for s in pif.iter("ProcessSignalGeneratingFunction") if s not in self.catalogue]
            for fid, (fcls, start, end, fl) in flows.items():
                if end == pid and start in self.by_id and self.by_id[start].tag == "ProcessSignalGeneratingFunction":
                    if self.by_id[start] not in sensors:
                        sensors.append(self.by_id[start])
            measuring_from = [start for fid, (fcls, start, end, fl) in flows.items()
                              if end == pid and fcls == "MeasuringLineFunction"]
            outputs, signals_to, signals_from, places = [], [], [], []
            for fid, (fcls, start, end, fl) in flows.items():
                conn = fl.find("Connection")
                to_id = conn.get("ToID") if conn is not None else None
                leader = "leader" in fcls.lower()
                if pid not in (start, end):
                    continue
                other = end if start == pid else start
                v = (self.valve_of_afunc.get(end) or self.valve_of_component.get(to_id)) if start == pid else None
                # A line between a bubble and an actuator, in either direction (Comos and SPPID draw it from the
                # actuator), or from the bubble (or a leader) to an operated valve itself: the bubble drives it.
                v = v or self.actuator_valve.get(other) or (
                    other if other in self.operated and (start == pid or leader) else None)
                if v:
                    outputs.append(v)
                elif other in self.bubble_ids:
                    (signals_to if start == pid else signals_from).append(other)
                elif self.is_place(other) and fcls != "MeasuringLineFunction":
                    places.append(other)   # a leader or line to the plant: where the bubble sits
            for b, other, seg in self.leaders:   # leaders and instrument runs drawn as pipe segments
                if b == pid and other:
                    if other in self.operated and other not in places:
                        outputs.append(other)
                    elif self.is_place(other):
                        places.append(other)
            # ISA 5.1: C as a succeeding letter is the control function (LIC, FIC, PICSA, YCS).
            control = "C" in re.sub(r"[\s\-]", "", letters or "").upper()[1:]
            info[pid] = dict(el=pif, letters=letters, number=number, basis=basis, cat=cat, funcs=funcs, control=control,
                             sensors=sensors, measuring_from=measuring_from, outputs=list(dict.fromkeys(outputs)),
                             signals_to=signals_to, signals_from=signals_from, lines=lines, places=places)
        # sensor / bubble locations -> units
        def located(sensor):
            for t, iid in self.assoc.get(sensor.get("ID"), []):
                if t == "is located in":
                    return iid
            return None

        tag_of = {}
        for pid, d in info.items():
            tag_of[pid] = isa_tag(d["letters"], d["number"]) if d["letters"] else None
        made, unit_of_pid = {}, {}
        for pid, d in info.items():
            pif = d["el"]
            loc = next((located(s) for s in d["sensors"] if located(s)), None) or next(iter(d["measuring_from"]), None) \
                or next(iter(d["places"]), None)
            unit, ubasis = self.unit_for(loc) if loc else (None, "no sensor location in the file")
            out_tags = [finals_by_valve[v]["tag"] for v in d["outputs"] if v in finals_by_valve]
            own = tag_of[pid]
            norm = lambda t: re.sub(r"[\s\-_.]", "", (t or "").upper())
            if own and any(norm(own) == norm(t) for t in out_tags):
                fe = next(finals_by_valve[v] for v in d["outputs"] if norm(finals_by_valve[v]["tag"]) == norm(own))
                self.part(pif, fe)
                fe["source"] += f"; tag bubble {pid}"
                self.fold_pif_extras(pif, fe, f"final element {fe['tag']}")
                self.fate(pif, f"tag bubble of final element {fe['tag']}")
                continue
            variable = ISA_VARIABLE.get((d["cat"] or (d["letters"] or "?")[:1])[:1].upper(), "unknown")
            words = [ISA_FUNCTION.get(c) for c in (d["funcs"] or (d["letters"] or "")[1:]) if c.upper() in ISA_FUNCTION]
            where = self.ga(pif, "LocationSpecialization")
            shown = " ".join((d["lines"] or [own or pid])[:2])
            desc = f"{shown}: {variable}" + (f", {', '.join(w for w in words if w)}" if words else "") + \
                   (f" ({humanize(where).lower()})" if where else "")
            if d["outputs"] or d["control"]:
                # A controller: a bubble that drives a valve (a hand switch too), or one whose letters say it controls
                # even when the file shows no valve it drives (its output is then a cascade, or not in the file).
                ctag, cbasis = self.claim_id(own, pid, d["basis"])
                ctrl = {"tag": ctag, "description": desc, "dexpi_class": pif.get("ComponentClass") or pif.tag,
                        "dexpi_id": pid, "tag_basis": cbasis, "source": f"DEXPI XML {pid} ({pif.tag})",
                        "measurement": None, "output": {}}
                self.records(pif, "", ctrl)
                self.label_records(pif, "", ctrl)
                if len(out_tags) == 1:
                    ctrl["output"] = {"final_element": out_tags[0]}
                elif out_tags:
                    ctrl["output"] = {"split_range": out_tags}
                self.fate(pif, f"controller {ctag}")
                if not d["sensors"] and loc:
                    ctrl["location"] = loc   # where a leader or line ties the bubble to the plant
                    unit_of_pid[pid] = unit
                if d["sensors"]:
                    s = d["sensors"][0]
                    snum = self.ga(s, "ProcessSignalGeneratingFunctionNumberAssignmentClass")
                    parts = split_tag(snum) if snum else None
                    if parts:
                        stag, sbasis = self.claim_id(isa_tag(*parts), s.get("ID"),
                                                     "ProcessSignalGeneratingFunctionNumberAssignmentClass")
                        assigned = False
                    else:
                        stag, sbasis = self.claim_id(isa_tag((d["cat"] or d["letters"][:1]) + "T", d["number"]),
                                                     s.get("ID"), "ASSIGNED here: the sensor has no number in the file")
                        assigned = True
                    inst = {"tag": stag, "unit": unit, "variable": variable, "uom": "",
                            "description": f"Sensor of {shown}: {variable}", "dexpi_class": "ProcessSignalGeneratingFunction",
                            "dexpi_id": s.get("ID"), "part_of": ctag, "tag_basis": sbasis, "unit_basis": ubasis,
                            "source": f"DEXPI XML {s.get('ID')} (ProcessSignalGeneratingFunction) in {pid}"}
                    if assigned:
                        inst["assigned_tag"] = True
                    if loc:
                        inst["location"] = loc
                        if self.stream_of_item.get(loc):
                            inst["stream"] = self.stream_of_item[loc]
                    self.records(s, "", inst)
                    self.label_records(s, "", inst)
                    for extra in d["sensors"][1:]:
                        self.part(extra, inst)
                        self.fate(extra, f"part of instrument {stag}")
                    self.fate(s, f"instrument {stag} (sensor measured by controller {ctag})")
                    ctrl["measurement"] = stag
                    unit_of_pid[pid] = unit
                    if unit:
                        instruments.append(inst)
                    else:
                        inst["unplaced_reason"] = f"instruments need a unit; {ubasis}"
                        unplaced.append(("instrument", inst))
                self.fold_pif_extras(pif, ctrl, f"controller {ctag}")
                controllers.append(ctrl)
                made[pid] = ctrl
            else:
                itag, ibasis = self.claim_id(own, pid, d["basis"])
                inst = {"tag": itag, "unit": unit, "variable": variable, "uom": "", "description": desc,
                        "dexpi_class": pif.get("ComponentClass") or pif.tag, "dexpi_id": pid, "tag_basis": ibasis,
                        "unit_basis": ubasis, "source": f"DEXPI XML {pid} ({pif.tag})"}
                if loc:
                    inst["location"] = loc
                    if self.stream_of_item.get(loc):
                        inst["stream"] = self.stream_of_item[loc]
                self.records(pif, "", inst)
                self.label_records(pif, "", inst)
                for s in d["sensors"]:
                    self.part(s, inst)
                    self.fate(s, f"sensor of instrument {itag}")
                self.fold_pif_extras(pif, inst, f"instrument {itag}")
                self.fate(pif, f"instrument {itag}")
                made[pid] = inst
                unit_of_pid[pid] = unit
                if unit:
                    instruments.append(inst)
                else:
                    inst["unplaced_reason"] = f"instruments need a unit; {ubasis}"
                    self.pending_unit.append((inst, d))
        # Signal lines between bubbles: kept as plain lists; a bubble with no sensor takes its source's unit.
        tag_by_pid = {pid: m["tag"] for pid, m in made.items()}
        for pid, d in info.items():
            m = made.get(pid)
            if not m:
                continue
            if d["signals_from"]:
                m["signal_from"] = [tag_by_pid.get(p, p) for p in d["signals_from"]]
            if d["signals_to"]:
                m["signal_to"] = [tag_by_pid.get(p, p) for p in d["signals_to"]]
        # A controller that drives no valve but signals another controller sets that controller's point (a cascade,
        # e.g. FIC 032 -> YCS 033 -> valve); one with no sensor of its own measures the instrument bubble signalling it.
        ctrl_pids = {id(c): pid for pid, c in made.items() if any(c is x for x in controllers)}
        is_ctrl = lambda p: id(made.get(p)) in ctrl_pids  # noqa: E731
        for c in controllers:
            pid = ctrl_pids[id(c)]
            d = info[pid]
            if not c["output"]:
                down = [p for p in d["signals_to"] if is_ctrl(p)]
                if down:
                    c["output"] = {"setpoint_of": made[down[0]]["tag"]}
                    c["output_basis"] = f"signal line from {pid} to the controller {down[0]}"
            if not c.get("measurement"):
                up = [p for p in d["signals_from"] if made.get(p) is not None and not is_ctrl(p)]
                if up:
                    c["measurement"] = made[up[0]]["tag"]
                    c["measurement_basis"] = f"signal line from the instrument {up[0]} to {pid}"
        for inst, d in self.pending_unit:
            src_units = [unit_of_pid[p] for p in d["signals_from"] if unit_of_pid.get(p)]
            out_units = [finals_by_valve[v]["unit"] for v in d["outputs"] if v in finals_by_valve and finals_by_valve[v].get("unit")]
            to_units = [unit_of_pid[p] for p in d["signals_to"] if unit_of_pid.get(p)]
            if src_units or out_units or to_units:
                inst["unit"] = (src_units or out_units or to_units)[0]
                inst["unit_basis"] = ("unit of the bubble that signals it" if src_units else
                                      "unit of the valve it drives" if out_units else "unit of the bubble it signals")
                del inst["unplaced_reason"]
                instruments.append(inst)
            else:
                unplaced.append(("instrument", inst))
        # Loops: the loop number rides on each bubble it includes.
        for loop in [el for el in self.root.iter() if el.tag in LOOP_TAGS and el not in self.catalogue]:
            members = [i for i in self.by_id if i in self.loop_members.get(loop.get("ID"), ()) and i in made]
            for i in members:
                self.part(loop, made[i])
            if members:
                self.fate(loop, f"loop number on {', '.join(made[i]['tag'] for i in members)}")
        # Leader segments and instrument pipe runs: their records ride on the bubble they place.
        for b, _, seg in self.leaders:
            if made.get(b) is not None and seg.get("ID") not in self.element_fate:
                self.part(seg, made[b])
                self.fate(seg, f"leader of {made[b]['tag']}")
        for pns in self.leader_pns:
            b = next((x for x, _, seg in self.leaders if self.seg_pns.get(seg.get("ID")) is pns and x in made), None)
            if b is not None:
                self.part(pns, made[b])
                self.fate(pns, f"leader line of {made[b]['tag']}")
            else:
                self.notes.append(f"{pns.get('ID')}: an instrument leader line whose bubble is not a model item")
        return instruments, controllers, unplaced

    def fold_pif_extras(self, pif, item, what):
        """Flows and actuating functions nested in a bubble that belong to no other item."""
        for sub in pif.iter():
            if sub is pif or not sub.get("ID") or sub.get("ID") in self.element_fate:
                continue
            if sub.tag == "ActuatingFunction" and sub.get("ID") in self.valve_of_afunc:
                continue   # folded into its final element
            if sub.tag == "ProcessSignalGeneratingFunction":
                continue
            self.part(sub, item)
            self.fate(sub, f"part of {what}")

    # ------------------------------------------------------------ whole file

    def meta(self):
        info = self.root.find("PlantInformation")
        md = self.root.find("MetaData")
        drawing = {}
        if md is not None:
            for _, g in self.own_gas(md):
                name, value = g.get("Name"), g.get("Value")
                if not value:
                    self.ga_state[g] = ("dropped", "no value in the file")
                elif PERSON_ATTRS.search(name or ""):
                    self.ga_state[g] = ("dropped", "person name: left out on purpose")
                else:
                    drawing[name + (f"@{g.get('Language')}" if g.get("Language") else "")] = value
                    self.ga_state[g] = "meta"
            self.fate(md, "meta.drawing")
        structure = []
        for psi in self.live("PlantStructureItem"):
            attrs = {}
            for _, g in self.own_gas(psi):
                if not g.get("Value"):
                    self.ga_state[g] = ("dropped", "no value in the file")
                elif PERSON_ATTRS.search(g.get("Name") or ""):
                    self.ga_state[g] = ("dropped", "person name: left out on purpose")
                else:
                    attrs[g.get("Name")] = g.get("Value")
                    self.ga_state[g] = "meta"
            structure.append({"dexpi_id": psi.get("ID"), "class": psi.get("ComponentClass"), "attributes": attrs})
            self.fate(psi, "meta.plant_structure")
        title_bits = [drawing.get(k) for k in ("DrawingNameAssignmentClass", "DrawingNumberAssignmentClass",
                                               "TitleAssignmentClass@en", "TitleAssignmentClass") if drawing.get(k)]
        info_attrs = info.attrib if info is not None else {}
        self.person_metadata_attributes_excluded = sum(bool(PERSON_ATTRS.search(k)) for k in info_attrs)
        meta = {"model_id": self.sheet_id,
                "title": f"{' / '.join(dict.fromkeys(title_bits))} (DEXPI XML {self.path.name})" if title_bits
                         else f"DEXPI XML {self.path.name}",
                "source_document": f"DEXPI XML file {self.path.name}, SHA-256 {sha256(self.path)}",
                "model_kind": "dexpi_import",
                "converted_by": f"scripts/{TOOL} (no model; every item cites its XML element ID)",
                "dexpi_file": {k: v for k, v in info_attrs.items() if not PERSON_ATTRS.search(k)},
                "drawing": drawing, "plant_structure": structure,
                "not_a_drawing_of_record": "Converted from an exported file. Nothing here is verified by anyone; "
                                           "units of instruments and valves are inferred through the piping (unit_basis)."}
        if self.attribution:
            meta["attribution"] = self.attribution
        return meta

    def read(self):
        self.unmapped_classes, self.folded, self.stream_ids, self.pending_unit = Counter(), Counter(), set(), []
        meta = self.meta()
        units = self.equipment()
        self.roles()
        self.piping()
        streams = self.streams()
        self.actuation()
        finals, manual, relief, unplaced = self.components()
        self.fold_fittings(streams)
        insts, ctrls, unplaced2 = self.instrumentation(self.final_of_valve)
        unplaced += unplaced2
        # References must point at nodes that exist in the exported sections.
        placed = {i["tag"] for i in insts} | {f["tag"] for f in finals}
        for c in ctrls:
            if c.get("measurement") and c["measurement"] not in placed:
                c["measurement_unplaced"] = c.pop("measurement")
            elif not c.get("measurement"):
                c.pop("measurement", None)
            out = c.get("output") or {}
            if out.get("final_element") and out["final_element"] not in placed:
                c["output_unplaced"] = out.pop("final_element")
            if out.get("split_range"):
                gone = [t for t in out["split_range"] if t not in placed]
                out["split_range"] = [t for t in out["split_range"] if t in placed]
                if gone:
                    c["output_unplaced"] = gone
                if not out["split_range"]:
                    del out["split_range"]
        unplaced_records = []
        for kind, item in unplaced:
            unplaced_records.append(dict(item, kind=kind))
            self.mark_unplaced(item)
        model = {"meta": meta, "units": units, "streams": streams, "instruments": insts, "final_elements": finals,
                 "controllers": ctrls, "manual_valves": manual, "relief_devices": relief}
        if unplaced_records:
            model["unplaced"] = unplaced_records
        if self.broken_refs:
            meta["broken_references"] = list(self.broken_refs)
        model["line_layers"] = self.line_layers(model)
        return model

    def line_layers(self, model):
        """The pipe and line-network layers as the XML defines them (scripts/line_layers.py's definitions): each
        segment chain (From item, in-line items in order, To item) is pipe; a unit's nozzles stand for the unit,
        valves are their model items, PipeTee elements are junctions, off-page connectors and open or broken ends are
        the battery limit BL, and other fittings (reducers, flanges, blinds, orifices) are passed through, as streams
        fold them. Measuring and signal lines (InformationFlow) are not pipes and are not in it. A tee with fewer than
        three pipe connections is passed through and counted."""
        import line_layers as ll
        node_of = dict(self.unit_of)
        for sec in ("final_elements", "manual_valves", "relief_devices", "unplaced"):
            for it in model.get(sec, []):
                if it.get("dexpi_id") and it.get("tag"):
                    node_of[it["dexpi_id"]] = it["tag"]
        sid = self.sheet_id
        tees = {i for i, el in self.by_id.items() if el.get("ComponentClass") == "PipeTee"}

        def node(x):
            if x in node_of:
                return node_of[x]
            if x in tees:
                return ("tee", x)
            el = self.by_id.get(x)
            if (el is not None and el.tag == "PipeOffPageConnector") or x.startswith(("open-start:", "open-end:", BROKEN)):
                return "BL"
            return ("via", x)
        adj = defaultdict(dict)
        for edges in self.pns_edges.values():
            for a, b, _seg in edges:
                na, nb = node(a), node(b)
                if na != nb:
                    adj[na][nb] = adj[nb][na] = 0
        items = {n for n in adj if isinstance(n, str)}
        segs, arms = ll.contract(adj, items)
        jid = {j: f"{sid}-JN-{j[1]}" for j in arms}
        name = lambda n: jid.get(n, n)  # noqa: E731
        seg_list = sorted(tuple(sorted((name(a), name(b)))) for a, b in segs)
        nets = ll.pipe_networks(seg_list, set(jid.values()))
        net_of = {}
        networks = []
        for n, g in enumerate(nets, 1):
            nid = f"{sid}-NET{n:03d}"
            networks.append({"id": nid, "sheet": sid, "members": g["members"], "junctions": g["junctions"],
                             "pairwise_links": len(g["members"]) * (len(g["members"]) - 1) // 2,
                             "source": "DEXPI XML piping topology (PipingNetworkSegment connections)"})
            for j in g["junctions"]:
                net_of[j] = nid
        segments = []
        for n, (a, b) in enumerate(seg_list, 1):
            net = net_of.get(a) or net_of.get(b) or next(x["id"] for x in networks if not x["junctions"]
                                                          and x["members"] == sorted((a, b)))
            segments.append({"id": f"{sid}-PS{n:03d}", "from": a, "to": b, "sheet": sid, "network": net,
                             "source": "DEXPI XML piping topology (PipingNetworkSegment connections)"})
        junctions = [{"id": jid[j], "sheet": sid, "network": net_of[jid[j]], "arms": arms[j],
                      "junction_method": "dexpi_pipe_tee", "dexpi_id": j[1],
                      "source": f"DEXPI XML {j[1]} (PipeTee)"} for j in sorted(arms, key=lambda j: jid[j])]
        return {"schema": ll.SCHEMA, "method": "scripts/dexpi_reader.py from the XML's piping topology",
                "definitions": ll.DEFINITIONS, "networks": networks, "junctions": junctions, "segments": segments,
                "tees_passed_through": len(tees - {j[1] for j in arms}),
                "note": "pipe items only: units (through their nozzles), valves and the battery limit (off-page "
                        "connectors and open ends). Instruments are joined to the piping by measuring lines, which "
                        "are not pipes; their place is in sits_on and measures."}

    def mark_unplaced(self, item):
        """Attributes of an item no export section can hold stay in the model but are not claims in the graph."""
        sources = {v["source"] for v in item.values() if isinstance(v, dict) and "source" in v}
        for ga, st in self.ga_state.items():
            if st == "claim":
                owner = self.parent.get(self.parent.get(ga))
                if owner is not None and any(s.startswith(f"DEXPI XML {owner.get('ID')} GenericAttribute {ga.get('Name')}")
                                             for s in sources):
                    self.ga_state[ga] = "unplaced"

    # ------------------------------------------------------------ report

    def key_attribute_coverage(self, key_ids):
        """Attribute values on the items an adapt_dexpi key keeps (and their nozzles/parts): how many survive here.
        'distinct' counts one per attribute name per item, as dexpi_to_twin.py's drop inventory does."""
        values = kept = distinct = distinct_kept = 0
        for kid in key_ids:
            el = self.by_id.get(kid)
            if el is None:
                continue
            names = defaultdict(list)
            for g in el.iter("GenericAttribute"):
                if g.get("Value"):
                    values += 1
                    ok = self.ga_state.get(g) in ("claim", "unplaced")
                    kept += ok
                    names[g.get("Name")].append(ok)
            distinct += len(names)
            distinct_kept += sum(all(v) for v in names.values())
        return {"values": values, "values_kept": kept, "distinct_per_item": distinct,
                "distinct_per_item_kept": distinct_kept}

    def report(self, model):
        all_ga = [g for g in self.root.iter("GenericAttribute") if g not in self.catalogue]
        cat_ga = [g for g in self.root.iter("GenericAttribute") if g in self.catalogue]
        kept, dropped = Counter(), Counter()
        for g in all_ga:
            st = self.ga_state.get(g)
            if st is None:
                owner = self.parent.get(self.parent.get(g))
                why = NOT_ITEMS.get(owner.tag) if owner is not None else None
                st = ("dropped", f"on <{owner.tag if owner is not None else '?'}>"
                                 f"{' ' + owner.get('ComponentClass') if owner is not None and owner.get('ComponentClass') else ''}: "
                                 f"{why or 'no rule for this element'}")
            if isinstance(st, tuple):
                dropped[st[1]] += 1
            else:
                kept[st] += 1
        elements = Counter()
        unread = Counter()
        for eid, el in self.by_id.items():
            if eid in self.element_fate:
                elements[el.tag] += 1
            else:
                reason = NOT_ITEMS.get(el.tag)
                if el.tag == "Drawing" or (el.tag == "Label" and self.parent.get(el) is not None
                                           and self.parent[el].tag == "Drawing"):
                    continue   # the title block is counted on its own line
                unread[f"<{el.tag}> {el.get('ComponentClass') or ''}".strip() + (f": {reason}" if reason else ": no rule")] += 1
        drawing_labels = sum(1 for d in self.live("Drawing") for _ in d.iter("Label"))
        claims = sum(1 for sec in ("units", "streams", "instruments", "final_elements", "controllers", "manual_valves",
                                   "relief_devices") for it in model.get(sec, []) for v in it.values()
                     if isinstance(v, dict) and "source" in v)
        r = {"file": self.path.name, "sha256": sha256(self.path), "sheet_id": self.sheet_id,
             "dexpi_file": model["meta"]["dexpi_file"],
             "items": {k: len(model.get(k, [])) for k in ("units", "streams", "instruments", "final_elements",
                                                         "controllers", "manual_valves", "relief_devices", "unplaced")},
             "attributes": {"in_file": len(all_ga), "kept_as_sourced_records": kept["claim"],
                            "kept_in_meta_only": kept["meta"], "kept_on_unplaced_items": kept["unplaced"],
                            "dropped": sum(dropped.values()), "dropped_by_reason": dict(dropped.most_common()),
                            "in_shape_catalogue_not_read": len(cat_ga)},
             "sourced_records_on_items": claims,
             "sourced_records_by_section": {sec: sum(1 for it in model.get(sec, []) for v in it.values()
                                                     if isinstance(v, dict) and "source" in v)
                                            for sec in ("units", "streams", "instruments", "final_elements", "controllers",
                                                        "manual_valves", "relief_devices", "unplaced")},
             "elements_read": dict(sorted(elements.items())),
             "elements_not_read": dict(unread.most_common()),
             "drawing_title_block_labels_not_read": drawing_labels,
             "unit_types": {u["id"]: f"{u['dexpi_class']} -> {u['type']} ({u['type_basis']})" for u in model["units"]},
             "unmapped_equipment_classes": dict(self.unmapped_classes),
             "fittings_folded_into_streams": dict(self.folded),
             "inferred_units": {i["tag"]: i.get("unit_basis") for sec in ("instruments", "final_elements", "relief_devices")
                                for i in model.get(sec, []) if i.get("unit_basis")},
             "unplaced": [{"tag": u["tag"], "kind": u["kind"], "why": u.get("unplaced_reason")} for u in model.get("unplaced", [])],
             "notes": self.notes,
             "broken_references": list(self.broken_refs),
             "lossy_steps": [
                 "Geometry, presentation and the shape catalogue are not read: the model has no positions (generate.py "
                 "places units automatically, display only).",
                 "Equipment classes map onto the generator's symbol types; approximate and unmapped ones say so in type_basis.",
                 "Lines become unit-to-unit streams; tees, reducers, flanges, blinds and off-page connectors are folded "
                 "into the stream they sit on (their attributes kept, keyed by XML ID), not separate nodes.",
                 "A line that ends only at a closed end (blind, plug, vent or drain valve) gets BL as its far end, said in to_end.",
                 "A segment Connection that names an ID the file does not contain (a broken reference) gets BL at that "
                 "end, said in from_end/to_end and listed under broken_references.",
                 "Units of instruments, final elements and relief devices are inferred through the piping (unit_basis).",
                 "Signal lines between bubbles are kept as signal_from/signal_to lists, not graph edges.",
                 "Items that need a unit but reach none through the piping go to 'unplaced': kept in the model "
                 "and graph export as nodes with a placement reason; not exported by generate.py.",
                 "Person names in the drawing metadata and the title block text are left out on purpose.",
                 "Values are kept as written (text); units of measure as DEXPI names (Bar, DegreeCelsius), not converted.",
             ]}
        if self.person_metadata_attributes_excluded:
            # These are direct XML attributes, not GenericAttribute occurrences.
            r["person_metadata_attributes_excluded"] = self.person_metadata_attributes_excluded
        return r


def compare_key(model, key_dir, sheet_id):
    """Agreement with an adapt_dexpi.py answer key for the same sheet: items, tags and unit-to-unit links."""
    key_dir = Path(key_dir)
    gml, tags_file = key_dir / f"{sheet_id}.graphml", key_dir / f"{sheet_id}.tags.json"
    if not gml.is_file() or not tags_file.is_file():
        return {"skipped": f"no key for {sheet_id} in the key folder"}
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    root = ET.parse(gml).getroot()
    keymap = {k.get("id"): k.get("attr.name") for k in root.findall("g:key", ns)}
    cls = {}
    for n in root.iter("{http://graphml.graphdrawing.org/xmlns}node"):
        d = {keymap.get(x.get("key")): x.text for x in n.findall("g:data", ns)}
        cls[n.get("id")] = d.get("label")
    edges = [(e.get("source"), e.get("target")) for e in root.iter("{http://graphml.graphdrawing.org/xmlns}edge")]
    tags = json.loads(tags_file.read_text(encoding="utf-8"))["tags"]
    where = {}
    for sec in ("units", "instruments", "final_elements", "controllers", "manual_valves", "relief_devices", "streams", "unplaced"):
        for it in model.get(sec, []):
            ident = it.get("id") or it.get("tag")
            where.setdefault(it["dexpi_id"], (sec, ident, it))
            for k, v in it.items():
                if isinstance(k, str) and ":" in k and k.endswith(":dexpi_class"):
                    where.setdefault(k.split(":")[0], (f"{sec} (folded part)", ident, it))
    norm = lambda t: re.sub(r"[\s\-_.]", "", (t or "").upper())
    items, tag_rows = Counter(), []
    for nid, c in cls.items():
        if c == "connector" and nid not in where:
            items["tee in key, folded into a stream in the model"] += 1
            continue
        w = where.get(nid)
        items[("own item" if w and "folded" not in w[0] else "folded into " + w[0].split(" ")[0]) if w else "MISSING"] += 1
        if c == "connector" or not tags.get(nid):
            continue
        sec, ident, it = w if w else (None, None, {})
        drawn = [v["value"].split(" | ") for k, v in it.items() if isinstance(v, dict) and "label:" in k
                 and (k.startswith(f"{nid}:") or (it.get("dexpi_id") == nid and k.startswith("label:"))
                      or "ActuatingSystemNumberLabel" in k)] if w else []
        drawn_match = any(norm(" ".join(lines[:2])) == norm(tags[nid]) or norm(lines[0]) == norm(tags[nid]) for lines in drawn)
        tag_rows.append({"dexpi_id": nid, "key_tag": tags[nid], "model": f"{sec} {ident}" if w else "missing",
                         "model_tag_equals_key_tag": bool(ident) and norm(ident) == norm(tags[nid]),
                         "drawn_label_kept": drawn_match})
    # unit-level links: key edges through non-equipment, non-instrument nodes
    unit_of = {}
    for u in model["units"]:
        unit_of[u["dexpi_id"]] = u["id"]
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    def term(n):
        if n in unit_of:
            return unit_of[n]
        if cls.get(n) == "inlet/outlet":
            return "BL"
        return None
    key_links = set()
    for start in [n for n in cls if term(n)]:
        seen, q = {start}, deque([start])
        while q:
            n = q.popleft()
            for m in adj[n]:
                if m in seen or cls.get(m) == "instrumentation":
                    continue
                seen.add(m)
                if term(m):
                    if not (term(start) == "BL" and term(m) == "BL"):
                        key_links.add(frozenset((term(start), term(m))))
                else:
                    q.append(m)
    ends = lambda s: s.get("from_end", "") + s.get("to_end", "")
    model_links = {frozenset((s["from"], s["to"])) for s in model["streams"]
                   if not (s["from"] == "BL" and s["to"] == "BL") and not ends(s)}
    not_compared = sorted(f"{s['id']}: {s['from']} - {s['to']} ({ends(s)})" for s in model["streams"] if ends(s))
    siblings = {}
    for x in sorted(key_links - model_links, key=sorted):  # sorted: the report is the same on every run
        if len(x) == 2:
            a, b = sorted(x)
            fed = lambda x: {s["from"] for s in model["streams"] if s["to"] == x and not ends(s)}
            src = fed(a) & fed(b)
            if src:
                siblings[f"{a} - {b}"] = (f"both fed from {', '.join(sorted(src))}: branches of one tee, which the key "
                                          "links pairwise (undirected); the model keeps the drawn direction")
    fmt = lambda s: sorted(" - ".join(sorted(x)) if len(x) == 2 else f"{next(iter(x))} (self)" for x in s)
    return {"_key_ids": sorted(cls), "key_nodes": len(cls), "items": dict(items),
            "tags_compared": len(tag_rows), "tags_model_id_equal": sum(r["model_tag_equals_key_tag"] for r in tag_rows),
            "tags_drawn_label_kept": sum(r["drawn_label_kept"] for r in tag_rows),
            "tag_rows": tag_rows,
            "unit_links": {"key": fmt(key_links), "model": fmt(model_links), "both": fmt(key_links & model_links),
                           "key_only": fmt(key_links - model_links), "model_only": fmt(model_links - key_links),
                           "model_streams_not_compared": not_compared, "key_only_explained": siblings}}


def report_text(r):
    a = r["attributes"]
    out = [f"# DEXPI XML read: {r['file']} -> {r['sheet_id']}", "",
           f"File: {r['dexpi_file'].get('OriginatingSystem', '?')} {r['dexpi_file'].get('OriginatingSystemVersion', '')}, "
           f"DEXPI {r['dexpi_file'].get('ApplicationVersion', '?')}, schema {r['dexpi_file'].get('SchemaVersion', '?')}; "
           f"SHA-256 {r['sha256']}", "",
           "Items: " + ", ".join(f"{v} {k}" for k, v in r["items"].items() if v), "",
           f"Attributes (GenericAttribute values): {a['in_file']} in the file; {a['kept_as_sourced_records']} kept as sourced "
           f"records on model items, {a['kept_in_meta_only']} kept in meta only, {a['kept_on_unplaced_items']} kept on "
           f"unplaced items, {a['dropped']} dropped. ({a['in_shape_catalogue_not_read']} in the shape catalogue, not plant data.)",
           "Sourced records (attributes, labels, part classes) by section: "
           + ", ".join(f"{k} {v}" for k, v in r["sourced_records_by_section"].items() if v)
           + ". graph_export.py makes each item's records claims on its node, and each stream's line, segment and "
             "fitting records claims on its `connects` edge; the graph file's counts give the total."]
    if r.get("person_metadata_attributes_excluded"):
        out.append(f"PlantInformation person-field XML attributes deliberately excluded: "
                   f"{r['person_metadata_attributes_excluded']} (separate from GenericAttribute counts).")
    if r.get("broken_references"):
        out += ["", "Broken references (a segment Connection names an ID the file does not contain; BL stands in, "
                    "the real end is unknown):"]
        out += [f"- {b['element']} {b['attribute']}={b['missing_id']!r}" for b in r["broken_references"]]
    for why, n in a["dropped_by_reason"].items():
        out.append(f"- dropped {n}: {why}")
    out += ["", "Unit types:"] + [f"- {k}: {v}" for k, v in r["unit_types"].items()]
    if r["unmapped_equipment_classes"]:
        out.append("Unmapped equipment classes (kept with their DEXPI class, drawn as a generic vessel): "
                   + ", ".join(f"{k} x{v}" for k, v in r["unmapped_equipment_classes"].items()))
    if r["fittings_folded_into_streams"]:
        out.append("Folded into streams: " + ", ".join(f"{v} {k}" for k, v in r["fittings_folded_into_streams"].items()))
    if r["inferred_units"]:
        out += ["", "Inferred units (through the piping):"] + [f"- {k}: {v}" for k, v in r["inferred_units"].items()]
    if r["unplaced"]:
        out += ["", "Unplaced (kept in the model and graph export; not in generate.py exports):"] + [f"- {u['kind']} {u['tag']}: {u['why']}" for u in r["unplaced"]]
    if r["elements_not_read"]:
        out += ["", "Elements with an ID not read:"] + [f"- {v} x {k}" for k, v in r["elements_not_read"].items()]
    out.append(f"Drawing title block labels not read: {r['drawing_title_block_labels_not_read']}")
    for n in r["notes"]:
        out.append(f"- note: {n}")
    c = r.get("comparison")
    if isinstance(c, dict) and "skipped" not in c:
        out += ["", "Against the adapt_dexpi.py answer key for this sheet:",
                f"- key nodes {c['key_nodes']}: " + ", ".join(f"{v} {k}" for k, v in c["items"].items()),
                f"- tags: {c['tags_compared']} drawn key tags; model id equals the key tag on {c['tags_model_id_equal']}; "
                f"the drawn label is kept on {c['tags_drawn_label_kept']}",
                f"- unit-to-unit links: key {len(c['unit_links']['key'])}, model {len(c['unit_links']['model'])}, "
                f"both {len(c['unit_links']['both'])}; key only {c['unit_links']['key_only']}; model only {c['unit_links']['model_only']}"]
        out += [f"  - key only {k}: {v}" for k, v in c["unit_links"]["key_only_explained"].items()]
        ka = c.get("key_item_attributes") or {}
        if ka:
            out.append(f"- attribute values on the key's items and their parts: {ka['values']} ({ka['distinct_per_item']} "
                       f"distinct names per item, the count dexpi_to_twin.py reports as not carried); kept here: "
                       f"{ka['values_kept']} values, {ka['distinct_per_item_kept']} distinct")
        out += [f"  - not compared (end not in the key): {x}" for x in c["unit_links"]["model_streams_not_compared"]]
        for row in c["tag_rows"]:
            if not row["model_tag_equals_key_tag"]:
                out.append(f"  - {row['dexpi_id']}: key tag {row['key_tag']!r}, model {row['model']}"
                           f"{' (drawn label kept)' if row['drawn_label_kept'] else ' (DRAWN LABEL NOT KEPT)'}")
    elif isinstance(c, dict):
        out += ["", f"Key comparison: {c['skipped']}"]
    out += ["", "Lossy steps:"] + [f"- {s}" for s in r["lossy_steps"]]
    return "\n".join(out) + "\n"


def prediction(xml_path, png_path, sheet_id, title):
    """Intake prediction + manifest for import_site_drawing.py, via the adapt_dexpi/dexpi_to_twin rules."""
    import shutil
    import tempfile
    import adapt_dexpi as A
    import dexpi_to_twin as D
    import score_pid2graph as sc
    try:
        key = A.convert_xml(Path(xml_path))
    except (ValueError, AttributeError) as exc:
        raise DexpiError(f"--png needs drawing geometry for every symbol: {exc}") from exc
    w, h = sc.png_size(png_path)
    ext = key["extent"]
    scale = w / (ext[2] - ext[0])
    if abs(h - (ext[3] - ext[1]) * scale) > max(2, 0.01 * h):
        raise DexpiError(f"{Path(png_path).name}: {w}x{h} px does not match the drawing extent {ext}; "
                         "--png must be a render of the whole drawing")
    with tempfile.TemporaryDirectory() as tmp:
        A.write_graphml(Path(tmp) / f"{sheet_id}.graphml", key, scale, 0.005 * max(w, h))
        Path(tmp, f"{sheet_id}.tags.json").write_text(json.dumps(
            {"tags": {n: v["tag"] for n, v in key["nodes"].items() if v["class"] != "connector"},
             "dexpi_class": {n: v["dexpi_class"] for n, v in key["nodes"].items()}}), encoding="utf-8")
        shutil.copyfile(png_path, Path(tmp) / f"{sheet_id}.png")
        pred, rep = D.convert(sheet_id, tmp, xml_path)
    pred["producer"] = PRODUCER
    pred["source"] = {"xml": Path(xml_path).name, "xml_sha256": sha256(xml_path), "image_sha256": sha256(png_path)}
    return pred, rep


def run(xml, out, sheet_id=None, png=None, attribution=None, compare=None, quiet=False):
    reader = Reader(xml, sheet_id, attribution)
    model = reader.read()
    rep = reader.report(model)
    if compare:
        rep["comparison"] = compare_key(model, compare, reader.sheet_id)
        if "skipped" not in rep["comparison"]:
            rep["comparison"]["key_item_attributes"] = reader.key_attribute_coverage(rep["comparison"].pop("_key_ids"))
    out = Path(out)
    sid = reader.sheet_id
    pred = None
    if png:
        import dexpi_to_twin as D
        try:
            image = D.intake_image_name(sid)
            pred, _ = prediction(xml, png, sid, model["meta"]["title"])
        except (ValueError, OSError) as exc:
            raise DexpiError(str(exc)) from exc
    pending = {}
    for name, obj in ((f"{sid}.model.json", model), (f"{sid}.report.json", rep)):
        pending[name] = json.dumps(obj, indent=1, ensure_ascii=False) + "\n"
    text = report_text(rep)
    pending[f"{sid}.report.md"] = text
    if pred is not None:
        pp = out / f"{sid}.prediction.json"
        pending[pp.name] = json.dumps(pred, indent=1, allow_nan=False) + "\n"
        man = {"schema_version": "site-drawing-intake-1", "drawing_id": sid, "revision": "as exported", "page": 1,
               "image": image, "extraction": pp.name, "extraction_format": "prediction", "producer": PRODUCER,
               "drawing_number": Path(xml).stem, "system_name": model["meta"]["title"][:200]}
        pending[f"{sid}.intake-manifest.json"] = json.dumps(man, indent=1) + "\n"
    from output_paths import protect_outputs
    sources = [xml, png]
    if compare:
        sources.extend(Path(compare) / f"{sid}.{ext}" for ext in ('graphml', 'tags.json'))
    retained = out / image if pred is not None else None
    if retained is not None and retained.exists():
        sources.append(retained)
    try:
        protect_outputs([*(out / name for name in pending),
                         *([retained] if retained is not None and not retained.exists() else [])], sources)
    except ValueError as exc:
        raise DexpiError(str(exc)) from exc
    if pred is not None:
        try:
            D.retain_intake_image(png, out, sid, pred["source"]["image_sha256"])
        except (ValueError, OSError) as exc:
            raise DexpiError(str(exc)) from exc
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in pending.items():
        (out / name).write_text(content, encoding="utf-8", newline="\n")
        written.append(out / name)
    if pred is not None:
        rep["prediction"] = {"symbols": len(pred["symbols"]), "connections": len(pred["connections"])}
    if not quiet:
        sys.stdout.write(text)
        for p in written:
            print(f"wrote {p.name}")
    return model, rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xml", required=True, help="a DEXPI P&ID XML file (DEXPI 1.x)")
    ap.add_argument("--out", required=True, help="output folder (created if missing)")
    ap.add_argument("--sheet-id", help="model id and file prefix (default: from the file name)")
    ap.add_argument("--png", help="a render of the whole drawing: also write an intake prediction + manifest")
    ap.add_argument("--attribution", help="licence/attribution text to carry in meta.attribution")
    ap.add_argument("--compare-key", metavar="KEYDIR",
                    help="folder with <sheet-id>.graphml + .tags.json from adapt_dexpi.py: report agreement")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # a Windows console is cp1252: print units like m\u207a, don't crash
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        run(a.xml, a.out, a.sheet_id, a.png, a.attribution, a.compare_key)
    except DexpiError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
