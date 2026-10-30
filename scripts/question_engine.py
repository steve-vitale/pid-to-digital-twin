"""Ask a plant model the questions an engineer asks (energy, heat grade, controls) and say what to collect, and where.

    python -S scripts/question_engine.py --list
    python -S scripts/question_engine.py --model data/te_process_model.json \
        --loops examples/loop-audit/te_loops.csv --out out/screen-te
    python -S scripts/question_engine.py --model data/bayer_rt/process_model.json --question E1 --question H4
    python -S scripts/question_engine.py --model my-bundle/plant_model.json \
        --schedule data/open100_equipment_schedule.json \
        --schedule examples/opportunity-screen/open100_schedule_fields.json --out out/screen-site
    python -S scripts/question_engine.py --rollup out/screen-site-a --rollup out/screen-site-b --out out/rollup

--rollup combines several sites' screens (their --out folders) into one list: per question, the sites and assets it
fired on and the data requests merged across sites. It ranks nothing by value and computes no savings.

The questions live in data/questions.json, as data, so an engineer can add one without touching this file. Each
question says when it applies (triggers over the model), what evidence to quote, what to collect and where, how the
collected data settles it, and what a public source says the typical benefit is. For each model item a question
applies to, the engine writes the evidence it found (by tag and asset id, with the model field that shows it) and a
data request for everything still missing. A data request is one of three states: (a) the value is on the drawing
or model, so it is quoted as evidence; (b) the drawing prints a field for it but leaves it blank, so the request
names that field on that sheet's equipment schedule; (c) the drawing has no place for it, so the request names where
it lives instead (nameplate, historian tag if one is mapped, control system configuration, records, a walkdown).

Accepts a hand-built process model (data/te_process_model.json, data/bayer_rt/process_model.json) or an extracted
twin (plant_model.json). --loops adds controllers from a loop list CSV (controller,measurement,output,...);
--schedule adds equipment schedule entries (tag + service per sheet; optional printed fields, null = blank).

Writes questions.json (the graph-export questions shape: scripts/graph_export.py --questions accepts it) and
screen.md (grouped by family, readable on its own).

What it does not do: it computes no savings, dollars or energy figures for the plant, and ranks nothing by value.
The typical benefits are the cited sources' own general wording. A finding is a question worth asking, not an
audit result: it says the drawing shows a pattern, never that the plant wastes energy. Stdlib only; no network.
"""
import argparse
import csv
import json
import re
import sys
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "questions.json"
SCHEMA = "opportunity-questions-1"
PLACEHOLDER = re.compile(r"^\s*(X+|TBD|TBA|N/?A|unknown|none|-+|\?+)\s*$", re.I)
CONTROL_VALVE = re.compile(r"^([FLPTH]CV|[FLPTAH]V|PRV)$")
MEDIA = OrderedDict([
    ("steam", r"\bSTEAM\b|\bSTM\b"),
    ("cooling water", r"COOLING WATER|\bCW[SR]?\b|\bWATER \(\d+ ?C\)"),
    ("compressed air", r"INSTRUMENT AIR|PLANT AIR|COMPRESSED AIR"),
    ("make-up water", r"MAKE-?UP WATER"),
    ("service water", r"SERVICE WATER"),
    ("fuel", r"FUEL (GAS|OIL)\b|NATURAL GAS"),
    ("nitrogen", r"NITROGEN|\bN2\b"),
])


def shown_path(p):
    """A path as it may appear in committed output: repository-relative, else just the file name."""
    rp = Path(p).resolve()
    try:
        return rp.relative_to(ROOT).as_posix()
    except ValueError:
        return rp.name


def norm_tag(t):
    if not t:
        return None
    t = re.sub(r"[\s‐-―�_]+", "-", str(t).strip())
    return re.sub(r"-+", "-", t).upper()


def isa_of(tag):
    m = re.match(r"^([A-Z]+)", norm_tag(tag) or "")
    return m.group(1) if m else None


def media_of(text):
    return {name for name, rx in MEDIA.items() if re.search(rx, text or "", re.I)}


class InputError(Exception):
    """A file the engine cannot use; main() prints the message and exits 2."""


def read_json(path, what):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise InputError(f"cannot read the {what} {shown_path(path)}: {e.strerror or e}")
    try:
        d = json.loads(text)
    except ValueError as e:
        raise InputError(f"the {what} {shown_path(path)} is not valid JSON ({e})")
    if not isinstance(d, dict):
        raise InputError(f"the {what} {shown_path(path)} is not a JSON object: is this the right file?")
    return d


class Item(dict):
    """One model thing the questions can look at. Keys: id, tag, kind, type, isa, variable, text, unit, stream,
    sheet, system, facts, signal, field (where in the model it was read)."""

    def label(self):
        if not self.get("tag") and self.get("kind") == "offpage":
            return f"\"{self['text']}\" ({self['id']})"
        return self.get("tag") or self["id"]


# ---------------------------------------------------------------- reading models

def load_schedule(paths):
    """{(sheet, tag): entry}; later files add printed fields to earlier entries for the same sheet and tag."""
    out = {}
    for p in paths or []:
        d = read_json(p, "equipment schedule")
        if not isinstance(d.get("sheets"), dict):
            raise InputError(f"the equipment schedule {shown_path(p)} has no 'sheets' object; expected "
                             '{"sheets": {"<sheet>": [{"tag": ..., "service": ..., "fields": {...}}]}}')
        for sheet, rows in d.get("sheets", {}).items():
            for r in rows:
                key = (str(sheet), norm_tag(r["tag"]))
                e = out.setdefault(key, {"tag": norm_tag(r["tag"]), "sheet": str(sheet), "service": None,
                                         "fields": None, "file": shown_path(p)})
                if r.get("service"):
                    e["service"] = r["service"]
                if r.get("fields") is not None:
                    e["fields"] = dict(r["fields"])
                    e["fields_file"] = shown_path(p)
    return out


def load_loops(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            lines = [ln for ln in f if not ln.lstrip().startswith("#") and ln.strip()]
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"cannot read the loop list {shown_path(path)}: {getattr(e, 'strerror', None) or e}")
    reader = csv.DictReader(lines)
    head = [h.strip() for h in reader.fieldnames or []]
    missing = [c for c in ("controller", "measurement", "output") if c not in head]
    if missing:
        raise InputError(f"the loop list {shown_path(path)} has no column(s) {', '.join(missing)}; its header is "
                         f"'{','.join(head) or '(empty)'}'. Expected controller,measurement,output[,description]")
    rows = []
    for n, r in enumerate(reader, 1):
        row = {(k or "").strip(): (v or "").strip() if isinstance(v, str) else "" for k, v in r.items() if k}
        if not row.get("controller"):
            raise InputError(f"the loop list {shown_path(path)}: data row {n} has no controller")
        rows.append(row)
    return rows


def signal_hand(it):
    if it.get("xmeas"):
        return f"recorded signal XMEAS({it['xmeas']}) in the TE data files"
    if it.get("xmv"):
        return f"recorded signal XMV({it['xmv']}) in the TE data files"
    if it.get("fig11_series"):
        return f"digitized series '{it['fig11_series']}' (from the source report's Fig 11)"
    return None


SECTIONS = ("units", "streams", "instruments", "final_elements", "controllers", "manual_valves", "relief_devices",
            "interlocks", "limits", "unplaced", "line_items", "offpage_connectors", "systems")
TEXT_FIELDS = ("id", "tag", "unit", "type", "name", "description", "stream", "from", "to", "measurement", "class",
               "variable", "uom", "parent")


def check_shapes(m, path):
    """Refuse a model whose records have the wrong shape, naming the record and field, before anything reads it: a
    wrong-typed id or facts block would otherwise crash deep inside the screen or be screened half-read."""
    bad = []
    for sec in SECTIONS:
        if sec not in m:
            continue
        recs = m[sec]
        if not isinstance(recs, list):
            bad.append(f"'{sec}' must be a list of records, not {type(recs).__name__}")
            continue
        seen = set()
        for i, r in enumerate(recs):
            where = f"{sec}[{i}]"
            if not isinstance(r, dict):
                bad.append(f"{where} must be an object, not {type(r).__name__}")
                continue
            for f in TEXT_FIELDS:
                if f in r and r[f] is not None and not isinstance(r[f], str):
                    bad.append(f"{where}.{f} must be text, not {type(r[f]).__name__} ({json.dumps(r[f])[:40]})")
            if sec == "controllers" and r.get("output") is not None:
                o = r["output"]
                if not isinstance(o, dict):
                    bad.append(f"{where}.output must be an object, not {type(o).__name__}")
                else:
                    for f in ("final_element", "setpoint_of", "controller"):
                        if o.get(f) is not None and not isinstance(o[f], str):
                            bad.append(f"{where}.output.{f} must be a tag (text), not {type(o[f]).__name__}")
                    sr = o.get("split_range")
                    if sr is not None and not (isinstance(sr, list) and all(isinstance(x, str) for x in sr)):
                        bad.append(f"{where}.output.split_range must be a list of tags, not "
                                   f"{json.dumps(sr)[:40]}")
            if "facts" in r and r["facts"] is not None and not isinstance(r["facts"], dict):
                bad.append(f"{where}.facts must be an object of named values, not {type(r['facts']).__name__}")
            key = r.get("id") if sec == "units" else None
            if isinstance(key, str):
                if key in seen:
                    bad.append(f"{where}: unit id {key!r} appears more than once")
                seen.add(key)
    if bad:
        raise InputError(f"can't read {shown_path(path)}: " + "; ".join(bad[:8])
                         + (f"; and {len(bad) - 8} more" if len(bad) > 8 else ""))


def from_hand(m):
    items = []
    for u in m.get("units", []):
        items.append(Item(id=u["id"], tag=u["id"], kind="equipment", type=u.get("type"), isa=None,
                          text=" ".join(filter(None, [u["id"], u.get("name")])), unit=u["id"],
                          stream=None, facts=dict(u.get("facts") or {}), field=f"units[{u['id']}]"))
    for s in m.get("streams", []):
        uu = (s.get("to") if s.get("from") == "BL" else s.get("from")) if s.get("utility") else None
        items.append(Item(id=f"stream:{s['id']}", tag=s["id"], kind="stream", type="utility" if s.get("utility")
                          else "process", text=s.get("name", ""), unit=uu, stream=s["id"],
                          src=s.get("from"), dst=s.get("to"), facts=dict(s.get("facts") or {}),
                          field=f"streams[{s['id']}]"))
    groups = (("instrument", "instruments"), ("valve", "final_elements"), ("hand_valve", "manual_valves"),
              ("relief", "relief_devices"))
    for kind, group in groups:
        for it in m.get(group, []):
            isa = isa_of(it["tag"])
            k = kind
            if kind == "valve" and not CONTROL_VALVE.match(isa or ""):
                k = "final_element"
            items.append(Item(id=it["tag"], tag=it["tag"], kind=k, type=None, isa=isa, variable=it.get("variable"),
                              text=" ".join(filter(None, [it["tag"], it.get("description")])), unit=it.get("unit"),
                              stream=it.get("stream"), facts=dict(it.get("facts") or {}),
                              signal=signal_hand(it), field=f"{group}[{it['tag']}]"))
    for c in m.get("controllers", []):
        out = c.get("output") or {}
        outs = [out["final_element"]] if out.get("final_element") else list(out.get("split_range") or [])
        sets = [x for x in [out.get("setpoint_of"), out.get("controller")] if x]
        sp = c.get("setpoint") or {}
        spt = (f"(setpoint {sp['value']} {sp.get('uom', '')}".strip() + ")") if sp.get("value") is not None else None
        notes = [f"As found: {c['as_found']}." if c.get("as_found") else None,
                 f"As operated: {c['as_operated']}." if c.get("as_operated") else None]
        items.append(Item(id=c["tag"], tag=c["tag"], kind="controller", isa=isa_of(c["tag"]),
                          text=" ".join(filter(None, [c["tag"], c.get("description"), spt])),
                          notes=" ".join(filter(None, notes)) or None, unit=c.get("unit"),
                          measurement=c.get("measurement"), outputs=outs, sets=sets, facts={},
                          field=f"controllers[{c['tag']}]"))
    for il in m.get("interlocks", []):
        items.append(Item(id=il["id"], tag=il["id"], kind="interlock", isa=None,
                          text=" ".join(filter(None, [il["id"], il.get("cause"), il.get("effect")])),
                          measurement=il.get("measurement"), outputs=[il.get("final_element")], facts={},
                          field=f"interlocks[{il['id']}]"))
    stream_unit = {i["stream"]: i["unit"] for i in items if i["kind"] == "stream" and i.get("unit")}
    for i in items:
        if not i.get("unit") and i.get("stream") in stream_unit:
            i["unit"] = stream_unit[i["stream"]]
    return items


def from_twin(m, schedule):
    systems = {s["id"]: s for s in m.get("systems", [])}
    items = []
    for u in m.get("units", []):
        sheets = u.get("sheets") or [u.get("layout", {}).get("sheet")]
        tag = norm_tag(u.get("tag"))
        sch = schedule.get((str(sheets[0]), tag)) if tag else None
        if not sch and tag:
            sch = next((schedule[(s, tag)] for s in sheets[1:] if (str(s), tag) in schedule), None)
        text = " ".join(filter(None, [tag, u.get("name") if u.get("name") != u.get("tag") else None,
                                      sch and sch.get("service")]))
        items.append(Item(id=u["id"], tag=tag, kind="equipment", type=u.get("class"), isa=None, text=text,
                          unit=u["id"], stream=None, sheet=str(sheets[0]), system=u.get("system"),
                          schedule=sch, facts={}, field=f"units[{u['id']}]",
                          raw_tag=u.get("tag")))
    for it in m.get("instruments", []):
        isa, kindtxt = it.get("isa_letters") or isa_of(it.get("tag")), it.get("instrument_kind") or ""
        if isa in ("PSV", "RV", "AORV") or (isa or "").startswith("PSE"):
            kind = "relief"
        elif "final element" in kindtxt and CONTROL_VALVE.match(isa or ""):
            kind = "valve"
        elif "valve" in kindtxt or isa in ("MOV", "MSV", "MSIV", "MSBV"):
            kind = "final_element"
        else:
            kind = "instrument"
        dp = it.get("data_point") or {}
        sig = None
        if dp.get("point"):
            what = point_description(dp.get("source"))
            sig = f"mapped data point {dp['point']} on {dp.get('server')} ({dp.get('source')}"
            sig += (f": {what})" if what else ")")
            if what and "synthetic" in what.lower():
                sig = "SYNTHETIC " + sig + ", not plant data"
        items.append(Item(id=it["id"], tag=norm_tag(it.get("tag")), kind=kind, isa=isa, variable=it.get("variable"),
                          text=norm_tag(it.get("tag")) or "", unit=it.get("unit"), parent=it.get("parent"),
                          stream=None, sheet=str((it.get("provenance") or [{}])[0].get("sheet")),
                          system=it.get("system"), facts={}, signal=sig, field=f"instruments[{it['id']}]",
                          raw_tag=it.get("tag")))
    for it in m.get("line_items", []):
        items.append(Item(id=it["id"], tag=norm_tag(it.get("tag")), kind="line_item", type=it.get("class"),
                          text=it.get("description") or "", unit=it.get("unit"), stream=None,
                          sheet=str((it.get("provenance") or [{}])[0].get("sheet")), system=it.get("system"),
                          facts={}, field=f"line_items[{it['id']}]"))
    for it in m.get("offpage_connectors", []):
        items.append(Item(id=it["id"], tag=None, kind="offpage", text=norm_text(it.get("text")),
                          unit=it.get("unit"), stream=None, system=it.get("system"),
                          sheet=str((it.get("provenance") or [{}])[0].get("sheet")), facts={},
                          field=f"offpage_connectors[{it['id']}].text"))
    for it in items:
        it["system_code"] = (systems.get(it.get("system")) or {}).get("system_code")
    return items


_IO_ROWS = {}


def point_description(source):
    """The description column of the I/O list row a data point came from ('<file>.csv row N'), if the file is in
    data/io_lists/; that is where a synthetic demo point says it is synthetic."""
    m = re.match(r"^(.+\.csv) row (\d+)$", source or "")
    if not m:
        return None
    f = ROOT / "data" / "io_lists" / Path(m.group(1)).name
    if f not in _IO_ROWS:
        try:
            with open(f, encoding="utf-8", newline="") as h:
                _IO_ROWS[f] = list(csv.reader(h))
        except OSError:
            _IO_ROWS[f] = []
    rows, n = _IO_ROWS[f], int(m.group(2)) - 1
    if not rows or n >= len(rows) or "description" not in rows[0]:
        return None
    i = rows[0].index("description")
    return rows[n][i].strip() if i < len(rows[n]) else None


def norm_text(t):
    return re.sub(r"\s*[‐-―�]\s*", "-", t or "")


class Model:
    def __init__(self, path, loops=None, schedule_paths=None):
        self.path = path
        self.m = read_json(path, "model")
        if "meta" in self.m and self.m["meta"] is None:
            self.m["meta"] = {}  # an empty meta is no meta
        if self.m.get("meta") is not None and not isinstance(self.m["meta"], dict):
            raise InputError(f"can't read {shown_path(path)}: 'meta' must be an object, not "
                             f"{type(self.m['meta']).__name__}")
        self.twin = (self.m.get("meta") or {}).get("model_kind") == "extracted_twin"
        if not (self.m.get("units") or self.m.get("instruments")):
            raise InputError(f"the model {shown_path(path)} has no units or instruments: is this the right file? "
                             "Expected a process model (units, streams, instruments, ...) or an extracted twin "
                             "(plant_model.json)")
        check_shapes(self.m, path)
        try:
            self.schedule = load_schedule(schedule_paths)
            self.items = from_twin(self.m, self.schedule) if self.twin else from_hand(self.m)
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            # A record inside the model or schedule is missing a field or has the wrong shape: refuse and name it,
            # rather than crash or screen a model that was only partly read.
            what = f"a record has no {e.args[0]!r} field" if isinstance(e, KeyError) else f"a record has the wrong shape ({e})"
            raise InputError(f"can't read {shown_path(path)}"
                             + (f" with schedule(s) {', '.join(shown_path(s) for s in schedule_paths)}"
                                if schedule_paths else "")
                             + f": {what}. Every unit needs an id, every instrument and valve a tag, and every "
                               "schedule entry a tag")
        self.loop_source = None
        self.loop_unmatched = []
        if loops:
            self.loop_source = shown_path(loops)
            have = {norm_tag(i["tag"]) for i in self.items if i["kind"] == "controller"}
            known = {norm_tag(i["tag"]) for i in self.items if i.get("tag")}
            rows = load_loops(loops)
            # A loop list naming none of the model's tags is the wrong list or a typo: screening with it would
            # report every instrument as unread by any controller, so refuse it instead of answering confidently.
            self.loop_unmatched = [r["controller"] for r in rows
                                   if not {norm_tag(r.get(k)) for k in ("controller", "measurement", "output")} & known]
            if rows and len(self.loop_unmatched) == len(rows):
                raise InputError(f"none of the {len(rows)} row(s) in the loop list {self.loop_source} names a tag in "
                                 f"the model {shown_path(path)} (controller, measurement or output): is it the list "
                                 "for this unit, and are the tags spelt as on the drawing?")
            for r in rows:
                if norm_tag(r.get("controller")) in have:
                    continue
                out = r.get("output", "")
                is_ctrl = bool(re.match(r"^[A-Z]+I?C-", norm_tag(out) or ""))
                self.items.append(Item(id=r["controller"], tag=r["controller"], kind="controller",
                                       isa=isa_of(r["controller"]), text=" ".join([r["controller"],
                                                                                    r.get("description", "")]),
                                       measurement=r.get("measurement"), outputs=[] if is_ctrl else [out],
                                       sets=[out] if is_ctrl else [], facts={},
                                       field=f"loop list {self.loop_source} row {r['controller']}"))
        self.by_id = {i["id"]: i for i in self.items}
        self.by_tag = defaultdict(list)
        for i in self.items:
            if i.get("tag"):
                self.by_tag[norm_tag(i["tag"])].append(i)
        self._adj = None

    # twin graph: asset ids joined by extracted links; instruments hang off their parent line item
    def adj(self):
        if self._adj is None:
            a = defaultdict(set)
            for s in self.m.get("streams", []):
                a[s["from"]].add(s["to"])
                a[s["to"]].add(s["from"])
            for i in self.items:
                if i.get("parent"):
                    a[i["parent"]].add(i["id"])
                    a[i["id"]].add(i["parent"])
            self._adj = a
        return self._adj

    def near(self, anchor_id, hops, sheet):
        """Asset ids within `hops` drawn links of the anchor on its sheet, not passing through other equipment."""
        seen, q = {anchor_id: 0}, deque([anchor_id])
        while q:
            x = q.popleft()
            if seen[x] >= hops:
                continue
            for y in self.adj().get(x, ()):
                it = self.by_id.get(y)
                if y in seen or (it and sheet and it.get("sheet") not in (None, "None", sheet)):
                    continue
                seen[y] = seen[x] + 1
                if not (it and it["kind"] == "equipment"):  # a path does not run through other equipment
                    q.append(y)
        return seen

    def out_streams(self, unit):
        return {i["stream"] for i in self.items if i["kind"] == "stream" and i.get("src") == unit}

    def linked_streams(self, unit):
        return {i["stream"] for i in self.items if i["kind"] == "stream" and unit in (i.get("src"), i.get("dst"))}


# ---------------------------------------------------------------- matching

def matches(item, sel):
    if sel.get("kind") and item["kind"] not in sel["kind"]:
        return False
    if sel.get("type") and (item.get("type") or "") not in sel["type"]:
        return False
    if sel.get("type_text") and not re.search(sel["type_text"], " ".join([item.get("type") or "", item["text"]]),
                                              re.I):
        return False
    if sel.get("isa") and not re.search(sel["isa"], item.get("isa") or ""):
        return False
    if sel.get("variable") and item.get("variable") not in sel["variable"]:
        return False
    if sel.get("text") and not re.search(sel["text"], item["text"], re.I):
        return False
    for rx in sel.get("text_all", []):
        if not re.search(rx, item["text"], re.I):
            return False
    if sel.get("not_text") and re.search(sel["not_text"], item["text"], re.I):
        return False
    if sel.get("tagged") and not item.get("tag"):
        return False
    if "control_valve" in sel and (item["kind"] == "valve") != sel["control_valve"]:
        return False
    if sel.get("fact_C_min") is not None or sel.get("fact_C_max") is not None:
        temps = [v for k, v in item.get("facts", {}).items() if re.search(r"(_C$|temperature)", k)
                 and isinstance(v, (int, float))]
        if not temps:
            return False
        if sel.get("fact_C_min") is not None and max(temps) < sel["fact_C_min"]:
            return False
        if sel.get("fact_C_max") is not None and min(temps) > sel["fact_C_max"]:
            return False
    if sel.get("schedule_field") and not field_state(item, sel["schedule_field"])[0] in ("present", "blank"):
        return False
    return True


def anchor_unit(item):
    return item["id"] if item["kind"] == "equipment" else item.get("unit")


def related(model, anchor, cand, clause):
    rel = clause.get("relation", "same_unit")
    if cand["id"] == anchor["id"]:
        return False
    if rel == "anywhere":
        return True
    if rel == "same_stream":
        return bool(anchor.get("stream")) and cand.get("stream") == anchor.get("stream")
    if rel == "same_unit":
        u = anchor_unit(anchor)
        return bool(u) and (cand.get("unit") == u or cand["id"] == u)
    if rel == "same_unit_same_medium":
        u = anchor_unit(anchor)
        same = bool(u) and (cand.get("unit") == u or (anchor.get("stream") and cand.get("stream") ==
                                                       anchor.get("stream")))
        return same and bool(media_of(anchor["text"]) & media_of(cand["text"]))
    if rel == "other_unit":
        return bool(anchor_unit(anchor)) and bool(cand.get("unit")) and cand.get("unit") != anchor_unit(anchor)
    if rel == "drives":  # cand is a controller writing straight to the anchor valve
        return cand["kind"] == "controller" and norm_tag(anchor["tag"]) in {norm_tag(x) for x in cand.get("outputs",
                                                                                                          [])}
    if rel == "reads":  # cand is a controller or interlock reading the anchor measurement
        return cand["kind"] in ("controller", "interlock") and norm_tag(cand.get("measurement")) == \
            norm_tag(anchor["tag"])
    if rel == "linked":  # joined to the anchor's unit by a drawn stream (an exhaust to a recovery exchanger)
        if model.twin:
            return cand["id"] in model.near(anchor["id"], clause.get("max_hops", 2), anchor.get("sheet"))
        u = anchor_unit(anchor)
        if not u:
            return False
        streams = model.linked_streams(u)
        if cand["kind"] == "equipment":
            return any({s.get("from"), s.get("to")} >= {u, cand["id"]} for s in model.m.get("streams", []))
        return cand.get("stream") in streams
    if rel in ("discharge_side", "near"):
        if model.twin:
            hops = model.near(anchor["id"], clause.get("max_hops", 2), anchor.get("sheet"))
            return cand["id"] in hops
        if rel == "near":
            return related(model, anchor, cand, {"relation": "same_unit"}) or \
                related(model, anchor, cand, {"relation": "same_stream"})
        outs = model.out_streams(anchor_unit(anchor))
        return bool(cand.get("stream")) and cand["stream"] in outs
    raise ValueError(f"unknown relation {rel!r}")


def find(model, anchor, clause, pool):
    if clause.get("twin_only") and not model.twin:
        return []
    if clause.get("hand_only") and model.twin:
        return []
    if clause.get("anchor_kind") and anchor["kind"] not in clause["anchor_kind"]:
        return []
    return [c for c in pool if matches(c, clause["select"]) and related(model, anchor, c, clause)]


# ---------------------------------------------------------------- evidence states

def field_state(item, name):
    """('present', value, where) | ('blank', None, where) | ('absent', None, None) for a named field."""
    for k, v in (item.get("facts") or {}).items():
        if k.lower() == name.lower():
            if v is None or (isinstance(v, str) and (not v.strip() or PLACEHOLDER.match(v))):
                return ("blank", v, f"{item['field']}.facts.{k}")  # a field with no value is not a known value
            return ("present", v, f"{item['field']}.facts.{k}")
    sch = item.get("schedule")
    if sch and sch.get("fields") is not None:
        for k, v in sch["fields"].items():
            if k.upper() == name.upper():
                where = f"sheet {sch['sheet']} equipment schedule, entry {sch['tag']}, field {k}"
                if v is None or (isinstance(v, str) and PLACEHOLDER.match(v)):
                    return ("blank", v, where)
                return ("present", v, where)
    return ("absent", None, None)


def render_place(place, ctx):
    p = place.get("place")
    if p == "schedule":
        return None  # handled by the field states
    if p == "historian":
        return render_historian(place, ctx)
    if p == "nameplate":
        return f"the {place.get('what', 'equipment')} nameplate on {ctx['label']}"
    if p == "dcs":
        return "DCS/PLC configuration: " + place.get("what", "the loop's configuration")
    texts = {"maintenance": "maintenance records: ", "bills": "utility bills or the site energy report: ",
             "walkdown": "a walkdown: ", "vendor": "the vendor datasheet: ", "records": "site records: "}
    if p in texts:
        return texts[p] + place.get("what", "")
    return place.get("text", "")


VALVE_KINDS = ("valve", "final_element", "hand_valve")


def render_historian(place, ctx):
    """Name recorded signals for the place's role, but only ones that measure the quantity asked for: a valve's
    position or output is never offered as a flow, temperature or power reading."""
    want = place.get("quantity")
    want = [want] if isinstance(want, str) else list(want or [])
    items = [i for i in ctx["roles"].get(place.get("for"), []) or ctx["anchors"]
             if i["kind"] not in ("equipment", "offpage", "controller", "interlock", "stream")]
    if place.get("match"):
        items = [i for i in items if re.search(place["match"], i["text"], re.I)]
    if place.get("not_match"):
        items = [i for i in items if not re.search(place["not_match"], i["text"], re.I)]
    usable, position_only = [], []
    for i in items:
        if i["kind"] in VALVE_KINDS:
            if not want or "position" in want:
                usable.append(i)
            elif "flow" in want:
                position_only.append(i)
        elif not want or i.get("variable") in want:
            usable.append(i)
    sigs = sorted({f"{i.label()}: {i['signal']}" for i in usable if i.get("signal")})
    bare = sorted({i.label() for i in usable if not i.get("signal")})
    parts = []
    if sigs:
        parts.append("historian / recorded data: " + "; ".join(sigs)
                     + (f" (no historian tag is mapped in this model for {', '.join(bare)})" if bare else ""))
    elif bare:
        parts.append(f"historian or DCS trend for {', '.join(bare)} (no historian tag is mapped in this model for "
                     "these)")
    if position_only and not any(i.get("variable") == "flow" for i in usable):  # a drawn flow meter answers it
        rec =sorted({f"{i.label()}: {i['signal']}" for i in position_only if i.get("signal")})
        names = ", ".join(sorted({i.label() for i in position_only}))
        lead = (f"only the valve position is recorded ({'; '.join(rec)})" if rec
                else f"only a valve ({names}) is drawn on this line, with no flow measurement")
        parts.append(lead + "; flow needs a meter or a calibrated valve curve")
    return "; ".join(parts) or None


def resolve_requests(q, ctx):
    evidence, reqs = [], []
    for r in q.get("data_requests", []):
        state, where_fields, found, have = "not_on_drawing", [], [], set()
        for fname in r.get("fields", []):
            for it in OrderedDict((i["id"], i) for i in ctx["anchors"] + ctx["roles"].get("equipment", [])).values():
                st, val, where = field_state(it, fname)
                if st == "present":
                    found.append((f"{r['item']}: {it.label()} {fname} = {val}", where))
                    have.add(fname)
                elif st == "blank":
                    shown = f" (printed as {val!r})" if val else ""
                    where_fields.append(f"the blank {fname} field{shown} on the {where.rsplit(', field', 1)[0]}")
        evidence += [{"item": r["item"], "text": t, "where": w} for t, w in found]
        if r.get("fields") and have >= set(r["fields"]) and not r.get("also_needs") and not where_fields:
            continue  # every part is on the drawing
        places = list(dict.fromkeys(where_fields))
        if places:
            state = "blank_on_drawing"
        for pl in r.get("where", []):
            txt = render_place(pl, ctx)
            if txt and txt not in places:
                places.append(txt)
        req = {"item": r["item"], "state": state, "where": places, "how": r["how"]}
        if have:
            req["already_on_drawing"] = sorted(have)
            req["still_needed"] = [f for f in r["fields"] if f not in have] + list(r.get("also_needs") or [])
        reqs.append(req)
    return evidence, reqs


# ---------------------------------------------------------------- running questions

def excluded(item, catalog):
    for ex in catalog.get("screen_exclusions", []):
        if ex.get("system_code") and re.search(ex["system_code"], item.get("system_code") or ""):
            return ex
        if ex.get("text") and re.search(ex["text"], item["text"] or "", re.I):
            return ex
    return None


def evidence_line(model, it, role):
    bits = [f"{it['kind'].replace('_', ' ')} {it.label()}"]
    if it.get("tag") and it["id"] != it.get("tag"):
        bits.append(f"(asset {it['id']})")
    if it.get("tag") and re.search(r"\bX{2,}\b|\bTBD\b", it["tag"]):
        bits.append("[placeholder tag on the drawing]")
    if it["text"] and it["text"] != it.label() and it["kind"] != "offpage":
        bits.append(f"reads \"{it['text']}\"")
    if it.get("notes"):
        bits.append(it["notes"])
    if it.get("sheet") not in (None, "None"):
        bits.append(f"on sheet {it['sheet']}")
    if it.get("unit") and it["kind"] != "equipment":
        u = model.by_id.get(it["unit"])
        bits.append(f"at {u.label() if u else it['unit']}" + (" (by the extraction's attribution)" if model.twin
                                                                 else ""))
    return {"role": role, "id": it["id"], "tag": it.get("tag"), "text": " ".join(bits), "field": it["field"]}


def ruled_out_by_unit(model, aw, key, anchors):
    """True when the equipment a finding is about matches the question's unit_not_text. A line has no owning unit,
    so its drawn ends stand in: it is ruled out only when every equipment end it touches matches (a line from the
    air cooler to a real product cooler still counts)."""
    rx = aw.get("unit_not_text")
    if not rx:
        return False
    def hit(uid):
        u = model.by_id.get(uid)
        return u is not None and u["kind"] == "equipment" and bool(re.search(rx, u["text"], re.I))
    u = model.by_id.get(key) if key else None
    if u is not None and u["kind"] == "equipment":
        return hit(key)
    for a in anchors:
        ends = [e for e in (a.get("src"), a.get("dst")) if e and model.by_id.get(e, {}).get("kind") == "equipment"]
        if not ends or not all(hit(e) for e in ends):
            return False
    return True


def run_question(model, q, catalog):
    aw = q["applies_when"]
    pool = [i for i in model.items if not excluded(i, catalog)]
    for need in aw.get("needs_model", []):
        if not any(i["kind"] == need for i in model.items):
            return [], {"question_id": q["id"], "reason": aw.get("needs_reason", f"the model has no {need}")}
    anchors_sel = aw["anchor"] if isinstance(aw["anchor"], list) else [aw["anchor"]]
    hits = []
    for a in pool:
        if not any(matches(a, sel) for sel in anchors_sel):
            continue
        roles, ok = defaultdict(list), True
        for cl in aw.get("with", []):
            got = find(model, a, cl, pool)
            if not got:
                ok = False
                break
            roles[cl.get("as", "related")] += got
        if not ok:
            continue
        if any(find(model, a, cl, pool) for cl in aw.get("without", [])):
            continue
        for cl in aw.get("also_show", []):
            roles[cl.get("as", "related")] += find(model, a, cl, pool)
        hits.append((a, roles))
    groups = OrderedDict()
    how = aw.get("group_by", "unit")
    for a, roles in hits:
        by_unit = how == "unit" and not (model.twin and a["kind"] == "offpage")
        key = "model" if how == "model" else (anchor_unit(a) or a["id"]) if by_unit else a["id"]
        g = groups.setdefault(key, {"anchors": [], "roles": defaultdict(list)})
        g["anchors"].append(a)
        for r, its in roles.items():
            g["roles"][r] += its
    findings = []
    for key, g in groups.items():
        if len({a["id"] for a in g["anchors"]}) < aw.get("min_anchors", 1):
            continue
        if ruled_out_by_unit(model, aw, key if how == "unit" else None, g["anchors"]):
            continue  # the unit itself rules the question out, whichever line, valve or instrument triggered it
        anchors = list(OrderedDict((a["id"], a) for a in g["anchors"]).values())
        shown_ids = {a["id"] for a in g["anchors"]}
        roles = {}
        for r, its in g["roles"].items():
            keep = [i for i in OrderedDict((i["id"], i) for i in its).values() if i["id"] not in shown_ids]
            shown_ids |= {i["id"] for i in keep}
            if keep:
                roles[r] = keep
        u = model.by_id.get(key) if how == "unit" else None
        unit = u if u and u["kind"] == "equipment" else None
        if unit and unit["kind"] == "equipment":
            roles.setdefault("equipment", [unit])
        label = unit.label() if unit else ", ".join(a.label() for a in anchors[:6]) + \
            (f" and {len(anchors) - 6} more" if len(anchors) > 6 else "")
        ctx = {"anchors": anchors, "roles": roles, "label": label}
        ev = [evidence_line(model, a, aw.get("anchor_role", "trigger")) for a in anchors]
        for r, its in roles.items():
            ev += [evidence_line(model, i, r) for i in its if i["id"] not in {a["id"] for a in anchors}]
        if aw.get("absent_note"):
            ev.append({"role": "checked, none found", "text": aw["absent_note"], "field": "applies_when.without"})
        if model.twin and any(cl.get("relation") in ("discharge_side", "near") for cl in aw.get("with", [])):
            ev.append({"role": "caveat", "text": "the extracted links have no recorded flow direction, so 'near' "
                       "means within the stated number of drawn links on the same sheet; which side of the "
                       "equipment it is on is not established by the model", "field": "streams[].direction"})
        extra, reqs = resolve_requests(q, ctx)
        ev += [{"role": "on drawing", "text": e["text"], "field": e["where"]} for e in extra]
        assets = OrderedDict()
        for it in ([unit] if unit else []) + anchors + [i for its in roles.values() for i in its]:
            assets.setdefault(it["id"], {"id": it["id"], "tag": it.get("tag")})
        fid = f"{q['id']}@{key if how != 'model' else 'model'}"
        findings.append({"id": fid, "question_id": q["id"], "family": q["family"], "question": q["question"],
                         "about": label, "assets": list(assets.values()), "evidence": ev, "data_requests": reqs,
                         "decision_rule": q["decision_rule"], "typical_benefit": benefit(q, catalog),
                         "limits": q.get("limits"), "status": "asked"})
    return findings, None


def benefit(q, catalog):
    tb = dict(q["typical_benefit"])
    srcs = tb.get("source") or []
    tb["source_titles"] = [f"{s}: {catalog['sources'][s]['title']}" for s in srcs if s in catalog["sources"]]
    return tb


def screen(model, catalog, only=None):
    qs = [q for q in catalog["questions"] if not only or q["id"] in only]
    found, not_checked, quiet = [], [], []
    for q in qs:
        f, why = run_question(model, q, catalog)
        if why:
            not_checked.append(why)
        elif not f:
            quiet.append(q["id"])
        found += f
    excl = defaultdict(list)
    for i in model.items:
        ex = excluded(i, catalog)
        if ex and i["kind"] == "equipment":
            excl[ex["reason"]].append(i.label())
    return found, not_checked, quiet, excl


# ---------------------------------------------------------------- output

HOW_TO_READ = """**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened."""


def write_outputs(model, catalog, found, not_checked, quiet, excl, out, only=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    doc = {"schema": SCHEMA, "source_model": shown_path(model.path), "catalog": shown_path(CATALOG),
           "loops": model.loop_source, "loop_rows_unmatched": model.loop_unmatched, "schedules": sorted({e["file"] for e in model.schedule.values()} |
                                                           {e["fields_file"] for e in model.schedule.values()
                                                            if e.get("fields_file")}),
           "questions_run": [q["id"] for q in catalog["questions"] if not only or q["id"] in only],
           "note": "A screen, not an audit: questions worth asking and the data needed to answer them. No savings "
                   "are computed; typical benefits are the cited sources' general wording.",
           "counts": {"findings": len(found), "by_family": dict(sorted(count_by(found, "family").items()))},
           "questions": found, "not_checked": not_checked, "did_not_fire": quiet,
           "left_out": {k: sorted(set(v)) for k, v in sorted(excl.items())}}
    (out / "questions.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                        newline="\n")
    (out / "screen.md").write_text(render_md(model, catalog, doc), encoding="utf-8", newline="\n")
    return doc


def count_by(found, key):
    c = defaultdict(int)
    for f in found:
        c[f[key]] += 1
    return c


def render_md(model, catalog, doc):
    title = (f"extracted drawing set, {len(model.m.get('systems', []))} sheets" if model.twin
             else model.m.get("meta", {}).get("title", doc["source_model"]))
    L = [f"# Opportunity screen: {title}", "",
         f"Model: `{doc['source_model']}`. Questions: `{doc['catalog']}`"
         + (f". Loop list: `{doc['loops']}`" if doc["loops"] else "")
         + ("".join(f". Schedule: `{s}`" for s in doc["schedules"])) + ".", ""]
    if doc.get("loop_rows_unmatched"):
        L += [f"**Loop list rows naming no tag in the model** (not used to judge what is read or driven): "
              f"{', '.join(doc['loop_rows_unmatched'])}.", ""]
    L += [HOW_TO_READ, "",
         "| Family | Findings |", "|---|---|"]
    fams = catalog["families"]
    for fam in fams:
        L.append(f"| {fams[fam]} | {doc['counts']['by_family'].get(fam, 0)} |")
    L.append("")
    for fam in fams:
        fs = [f for f in doc["questions"] if f["family"] == fam]
        if not fs:
            continue
        L += [f"## {fams[fam]}", ""]
        for f in fs:
            L += [f"### {f['question_id']}: {f['question']}", "", f"**About:** {f['about']}  ", "",
                  "**Evidence on the drawing / model**", ""]
            L += [f"- Caveat: {e['text']}" if e["role"] == "caveat" else
                  f"- {'' if e['role'] == 'trigger' else e['role'].capitalize() + ': '}{e['text']} (`{e['field']}`)"
                  for e in f["evidence"]]
            L += ["", "**Data to collect**", ""]
            for r in f["data_requests"]:
                part = (f" Already on the drawing: {', '.join(r['already_on_drawing'])}; still needed: "
                        f"{', '.join(r['still_needed'])}." if r.get("already_on_drawing") else "")
                L.append(f"- {r['item']} [{r['state'].replace('_', ' ')}].{part} Where: " + "; then ".join(r["where"])
                         + f". How: {r['how']}")
            tb = f["typical_benefit"]
            src = ", ".join(tb.get("source") or []) or "no source"
            L += ["", f"**How it is decided:** {f['decision_rule']}", "",
                  f"**What the source says ({src}):** {tb['wording']}"]
            if tb.get("arc"):
                L.append(f"IAC/ITAC recommendation code: {tb['arc']}.")
            if f.get("limits"):
                L += ["", f"**Limits:** {f['limits']}"]
            L.append("")
    if doc["not_checked"]:
        L += ["## Not checked", ""] + [f"- {n['question_id']}: {n['reason']}" for n in doc["not_checked"]] + [""]
    if doc["did_not_fire"]:
        L += ["## Questions that found nothing to ask here", "",
              "No item in this model matched these questions' triggers. That is not a clean bill of health: the "
              "model may simply not show what the question looks for. " + ", ".join(doc["did_not_fire"]) + ".", ""]
    if doc["left_out"]:
        L += ["## Left out of the screen", ""]
        for reason, tags in doc["left_out"].items():
            L.append(f"- {reason}: {', '.join(tags)}")
        L.append("")
    used = sorted({s for f in doc["questions"] for s in (f["typical_benefit"].get("source") or [])},
                  key=lambda s: int(s[1:]))
    if used:
        L += ["## Sources cited above", ""]
        for s in used:
            src = catalog["sources"][s]
            L.append(f"- {s}: {src['title']}. {src['url']} (license: {src['license']})")
        L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- roll-up across sites

ROLLUP_SCHEMA = "opportunity-rollup-1"


def load_site(arg, catalog):
    """'NAME=FOLDER' or 'FOLDER' (the site is then the folder's name) holding a screen's questions.json."""
    name, _, folder = arg.rpartition("=") if "=" in arg else ("", "", arg)
    folder = Path(folder)
    name = name or folder.resolve().name
    f = folder / "questions.json" if folder.is_dir() else folder
    if not f.is_file():
        raise InputError(f"no questions.json in {shown_path(folder)}: give the --out folder of a screen run")
    d = read_json(f, "screen")
    if d.get("schema") != SCHEMA or not isinstance(d.get("questions"), list):
        raise InputError(f"{shown_path(f)} is not an opportunity screen (schema {d.get('schema')!r}, expected "
                         f"{SCHEMA!r}): run question_engine.py --model ... --out first")
    unknown = sorted({q.get("question_id") for q in d["questions"]} - {q["id"] for q in catalog["questions"]})
    if unknown:
        raise InputError(f"{shown_path(f)} has question ids this catalog does not know ({', '.join(unknown)}): "
                         "was it made with another version of data/questions.json?")
    return name, shown_path(f), d


def rollup(site_args, catalog):
    """Combine several sites' screens: per question, the sites and assets it fired on and the data requests merged
    by item (each site's places kept, duplicates dropped). Ordered by how many sites a question fired at, then by
    findings, then catalog order. Nothing is ranked by value and no saving is computed."""
    sites, seen = [], {}
    for a in site_args:
        name, path, d = load_site(a, catalog)
        if name in seen:
            raise InputError(f"site {name!r} is named twice ({seen[name]} and {path}); name them with NAME=FOLDER")
        seen[name] = path
        sites.append((name, path, d))
    order = {q["id"]: n for n, q in enumerate(catalog["questions"])}
    qmap = {q["id"]: q for q in catalog["questions"]}
    per = OrderedDict()
    for name, _, d in sites:
        for f in d["questions"]:
            e = per.setdefault(f["question_id"], {"sites": OrderedDict(), "requests": OrderedDict()})
            e["sites"].setdefault(name, []).append(
                {"finding_id": f["id"], "about": f["about"],
                 "assets": [{"id": a["id"], "tag": a.get("tag")} for a in f["assets"]]})
            for r in f["data_requests"]:
                req = e["requests"].setdefault(r["item"], {"item": r["item"], "how": r["how"], "sites": OrderedDict()})
                s = req["sites"].setdefault(name, {"site": name, "states": [], "per": OrderedDict()})
                if r["state"] not in s["states"]:
                    s["states"].append(r["state"])
                s["per"].setdefault(f["id"], [])
                s["per"][f["id"]] += [w for w in r["where"] if w not in s["per"][f["id"]]]
    for e in per.values():  # places every finding at a site shares are listed once; the rest per finding
        for req in e["requests"].values():
            for s in req["sites"].values():
                lists = list(s.pop("per").items())
                common = [w for w in lists[0][1] if all(w in ws for _, ws in lists)]
                s["where"] = common
                s["where_by_finding"] = [{"finding_id": fid, "where": [w for w in ws if w not in common]}
                                         for fid, ws in lists if [w for w in ws if w not in common]]
    out = []
    for qid, e in per.items():
        q = qmap[qid]
        fired = list(e["sites"])
        out.append({
            "question_id": qid, "question": q["question"], "family": q["family"],
            "sites": [{"site": s, "findings": fs} for s, fs in e["sites"].items()],
            "findings": sum(len(fs) for fs in e["sites"].values()),
            "quiet_at": [n for n, _, d in sites if n not in fired and qid in d.get("did_not_fire", [])],
            "not_checked_at": [n for n, _, d in sites if qid in {x["question_id"] for x in d.get("not_checked", [])}],
            "not_run_at": [n for n, _, d in sites if n not in fired and qid not in d.get("questions_run", [qid])],
            "data_requests": [dict(r, sites=list(r["sites"].values())) for r in e["requests"].values()],
            "decision_rule": q["decision_rule"], "typical_benefit": benefit(q, catalog)})
    out.sort(key=lambda x: (-len(x["sites"]), -x["findings"], order[x["question_id"]]))
    quiet_everywhere = [q["id"] for q in catalog["questions"] if q["id"] not in per
                        and all(q["id"] in d.get("did_not_fire", []) for _, _, d in sites)]
    return {"schema": ROLLUP_SCHEMA, "catalog": shown_path(CATALOG),
            "note": "Several sites' opportunity screens combined: where each question fired and the data to collect "
                    "at each. A screen, not an audit: no savings are computed and nothing is ranked by value; the "
                    "order is only how many sites a question fired at, then how many findings.",
            "sites": [{"site": n, "screen": p, "source_model": d.get("source_model"),
                       "findings": len(d["questions"]), "questions_run": len(d.get("questions_run", []))}
                      for n, p, d in sites],
            "counts": {"questions_fired": len(out), "findings": sum(q["findings"] for q in out),
                       "fired_at_every_site": sum(len(q["sites"]) == len(sites) for q in out)},
            "questions": out, "quiet_at_every_site": quiet_everywhere}


def render_rollup_md(doc, catalog):
    names = [s["site"] for s in doc["sites"]]
    L = [f"# Opportunity screen roll-up: {', '.join(names)}", "",
         "**How to read this.** Each site's screen, combined. A question is listed once, with every site and "
         "asset it fired on and the data to collect at each site, so the same request can be planned across "
         "sites. The order is only how many sites a question fired at, then how many findings: it is not a "
         "ranking by value, and no savings are computed. The \"what the source says\" lines are the sources' "
         "general figures, quoted as written. Read each site's own screen for the evidence behind a finding.", "",
         "| Site | Screen | Model | Findings |", "|---|---|---|---|"]
    L += [f"| {s['site']} | `{s['screen']}` | `{s['source_model']}` | {s['findings']} |" for s in doc["sites"]]
    L += ["", "| Question | Family | Sites | Findings |", "|---|---|---|---|"]
    fams = catalog["families"]
    for q in doc["questions"]:
        L.append(f"| {q['question_id']}: {q['question']} | {fams.get(q['family'], q['family'])} | "
                 f"{', '.join(s['site'] for s in q['sites'])} | {q['findings']} |")
    L.append("")
    for q in doc["questions"]:
        L += [f"## {q['question_id']}: {q['question']}", "",
              f"Fired at {len(q['sites'])} of {len(names)} sites."
              + (f" Asked and quiet at: {', '.join(q['quiet_at'])}." if q["quiet_at"] else "")
              + (f" Not checked at: {', '.join(q['not_checked_at'])}." if q["not_checked_at"] else "")
              + (f" Not run at: {', '.join(q['not_run_at'])}." if q["not_run_at"] else ""), ""]
        for s in q["sites"]:
            for f in s["findings"]:
                tags = ", ".join(sorted({a["tag"] or a["id"] for a in f["assets"]}))
                L.append(f"- **{s['site']}**, {f['about']} (`{f['finding_id']}`): {tags}")
        L += ["", "**Data to collect**", ""]
        for r in q["data_requests"]:
            L.append(f"- {r['item']}. How: {r['how']}")
            for s in r["sites"]:
                parts = [f"For `{b['finding_id']}`: " + "; then ".join(b["where"]) for b in s["where_by_finding"]]
                if s["where"]:
                    parts.append(("Then, for all of them: " if parts else "") + "; then ".join(s["where"]))
                L.append(f"  - {s['site']} [{', '.join(x.replace('_', ' ') for x in s['states'])}]: "
                         + ". ".join(parts))
        tb = q["typical_benefit"]
        L += ["", f"**How it is decided:** {q['decision_rule']}", "",
              f"**What the source says ({', '.join(tb.get('source') or []) or 'no source'}):** {tb['wording']}", ""]
    if doc["quiet_at_every_site"]:
        L += ["## Asked at every site, fired at none", "",
              "Not a clean bill of health: the models may not show what these questions look for. "
              + ", ".join(doc["quiet_at_every_site"]) + ".", ""]
    used = sorted({s for q in doc["questions"] for s in (q["typical_benefit"].get("source") or [])},
                  key=lambda s: int(s[1:]))
    if used:
        L += ["## Sources cited above", ""]
        L += [f"- {s}: {catalog['sources'][s]['title']}. {catalog['sources'][s]['url']} "
              f"(license: {catalog['sources'][s]['license']})" for s in used]
        L.append("")
    return "\n".join(L)


def write_rollup(doc, catalog, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rollup.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                     newline="\n")
    (out / "rollup.md").write_text(render_rollup_md(doc, catalog), encoding="utf-8", newline="\n")


def list_questions(catalog):
    lines = []
    for fam, name in catalog["families"].items():
        qs = [q for q in catalog["questions"] if q["family"] == fam]
        lines.append(f"{name} ({len(qs)})")
        lines += [f"  {q['id']:<4} {q['question']}" for q in qs]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model")
    ap.add_argument("--loops", help="loop list CSV: controller,measurement,output[,description]")
    ap.add_argument("--schedule", action="append", help="equipment schedule JSON (repeatable)")
    ap.add_argument("--question", action="append", help="run only this question id (repeatable)")
    ap.add_argument("--catalog", default=str(CATALOG))
    ap.add_argument("--out", help="folder for questions.json and screen.md (default: print the screen)")
    ap.add_argument("--list", action="store_true", help="print the questions and exit")
    ap.add_argument("--rollup", action="append", metavar="[NAME=]FOLDER",
                    help="combine screens from several sites (repeatable): each a --out folder holding questions.json; "
                         "the site is named after the folder unless NAME= is given. Writes rollup.json and rollup.md")
    a = ap.parse_args(argv)
    catalog = json.loads(Path(a.catalog).read_text(encoding="utf-8"))
    if a.list:
        print(list_questions(catalog))
        return 0
    if a.rollup:
        if a.model:
            ap.error("give --model (one site's screen) or --rollup (several screens), not both")
        try:
            doc = rollup(a.rollup, catalog)
        except InputError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        if a.out:
            write_rollup(doc, catalog, a.out)
            print(json.dumps(doc["counts"]) + f" -> {shown_path(a.out)}")
        else:
            sys.stdout.reconfigure(encoding="utf-8")
            print(render_rollup_md(doc, catalog))
        return 0
    if not a.model:
        ap.error("give --model, or --list")
    known = {q["id"] for q in catalog["questions"]}
    bad = [q for q in a.question or [] if q not in known]
    if bad:
        ap.error(f"unknown question id(s): {', '.join(bad)}")
    try:
        model = Model(a.model, a.loops, a.schedule)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    found, nc, quiet, excl = screen(model, catalog, a.question)
    if a.out:
        doc = write_outputs(model, catalog, found, nc, quiet, excl, a.out, a.question)
        print(json.dumps(doc["counts"]) + f" -> {shown_path(a.out)}")
    else:
        doc = {"schema": SCHEMA, "source_model": shown_path(model.path), "catalog": shown_path(CATALOG),
               "loops": model.loop_source, "loop_rows_unmatched": model.loop_unmatched,
               "schedules": sorted({e["file"] for e in model.schedule.values()} |
                                   {e["fields_file"] for e in model.schedule.values() if e.get("fields_file")}),
               "questions": found, "not_checked": nc,
               "did_not_fire": quiet, "left_out": {k: sorted(set(v)) for k, v in excl.items()},
               "counts": {"findings": len(found), "by_family": dict(count_by(found, "family"))}}
        sys.stdout.reconfigure(encoding="utf-8")
        print(render_md(model, catalog, doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
