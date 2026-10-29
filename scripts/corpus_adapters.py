"""Adapters that turn the public sources added to the generalization matrix on 2026-10-29 into inputs the existing tools read.

Support for scripts/corpus_matrix.py. Every function reads downloaded files as data only (ElementTree, csv, json,
gzip, zipfile with size caps, ast.literal_eval for one Python-literal file); nothing downloaded is executed. Paths
are the folders scripts/fetch_corpus.py writes under data/external/ (gitignored). The rules below were written
before any scored run of the cells they feed; each departure from the source is stated here, not decided per file.

DEXPI TrainingTestCases (dexpi-ttc-all; adapters A1 of the staging report)
  Files: every *.xml under `dexpi <version>/example pids/<case>/`. Exporter = PlantInformation/@OriginatingSystem;
  "DEXPI Test", "DEXPI", "DEXPI Test Case" and "DEXPI Example" are the DEXPI initiative's own reference exports.
  Case version = the file name's leading case and version (C02V01, E01V02, I02V01). When a case version has more
  than one reference export, the one whose file name carries "VER" is the reference.
  Truth read from each file by this module, not by dexpi_reader.py:
    top-level equipment  Equipment elements outside the shape catalogue with no Equipment ancestor
    instrument functions ProcessInstrumentationFunction (DEXPI 1.x) or ProcessInstrument (Proteus 3.3.3) elements
    control functions    those whose letters hold a C after the first letter (the measured variable). Letters =
                         category + functions + modifier attributes, else the leading letters of a Tag/TagName
                         attribute, else of the drawn label
    loops                InstrumentationLoopFunction (or Proteus 3.3.3 InstrumentLoop) elements
    refusal reasons      element IDs used twice, a root other than PlantModel, nothing to read: each is checked here
                         independently, so a reader refusal can be confirmed or not
  Loop list (row 4), per InstrumentationLoopFunction with a control function among its members (members = PIFs the
  loop associates as "is a collection including", PIFs that say "is a part of" it, or PIFs nested in it):
    controller   the control function's letters + number (number attribute; else the label's number)
    measurement  the controller itself when a ProcessSignalGeneratingFunction is nested in it (one combined bubble,
                 as corpus_matrix.py already does for DEXPI 1.3); else another member function's letters + number
    output       the actuating system the controller's ActuatingFunction is fulfilled by: its number attribute, else
                 the number of the valve its OperatedValveReference / ShutOffValveReference refers to, else the
                 ActuatingFunction's own number attribute
  A loop missing any of the three is listed as incomplete in the XML, not audited.

Historians (A8 HAI, A10 SKAB, A13 PRONTO days 2 and 4)
  SKAB: ';' separated -> comma CSV, first column `datetime`, `anomaly` and `changepoint` dropped. Fault start = first
  row with anomaly = 1. GPL-3.0 data: converted into a temporary folder only, never written into the repository.
  HAI 21.03: gzip CSV -> CSV with `attack`, `attack_P1..P3` dropped; attack events = runs of attack = 1; the fault
  start of a file = its first attack row.
  PRONTO: scripts/fetch_corpus.py's own day-3 conversion (build_pronto_csvs: alignment to the raw DeltaV export,
  label checks) with the row ranges in PRONTO_DAYS below, same 17 process columns as day 3.

Process models for generate.py (A16 IDAES, A17 DWSIM)
  IDAES (HDA_solved.json): each unit model except feed/product -> a unit; feed and product nodes -> BL; each arc ->
  a stream with the solved stream-table values as facts (value, unit). Types: mixer -> feed_header, heater ->
  heat_exchanger, *reactor/cstr -> reactor, flash -> separator, separator (an IDAES splitter) -> vessel,
  pressure_changer -> compressor, tray_column -> stripper. No instruments or controllers exist in the source.
  DWSIM (.dwxmz inside each project zip): units = graphic objects that are not streams, annotations (GO_*) or solver
  blocks (OT_Recycle, OT_EnergyRecycle, OT_Adjust, OT_Spec); material streams join the units their connectors are
  attached to (an end attached to nothing is BL). A stream ending at a recycle block is joined to the stream leaving
  it (one stream, the second one listed as joined). Energy streams are dropped (counted). Types by ObjectType:
  Pump -> pump; Compressor, Expander -> compressor; Heater, Cooler, HeatExchanger -> heat_exchanger; reactors ->
  reactor; columns -> stripper; Vessel, ComponentSeparator -> separator; Tank -> tank; NodeIn (mixer), NodeOut
  (splitter) -> feed_header; Valve and every other type (CAPE-OPEN units included, opaque) -> vessel, listed.
  Unit id = the user's tag when it is filename-safe and unique (case-insensitively), else DWSIM's object name.

HAI DCS loop candidates (A7): the graphs carry no block types, so a pairing is only a candidate: a named measurement
node, the named output nodes reached from it through function blocks along a `CO` link. Listed for a person to
confirm; never audited as truth.

Stdlib only. No model is called. Claude (the coding agent) wrote the code.
"""
import ast
import contextlib
import csv
import gzip
import importlib
import io
import json
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL = ROOT / "data" / "external"
DEXPI_COMMIT = "a23d61e2e089eb2ca464cd552f9ae580a2785963"
DEXPI_ROOT = EXTERNAL / "dexpi-ttc-all" / "extracted" / f"TrainingTestCases-{DEXPI_COMMIT}-{DEXPI_COMMIT}"
REFERENCE_SYSTEMS = ("DEXPI Test", "DEXPI", "DEXPI Test Case", "DEXPI Example")
EXPORTERS = {"SPPID": "sppid", "Comos": "comos", "AVEVAPID": "aveva", "AutoCAD PnID": "autocad",
             "P&ID Toolbox": "pid-toolbox"}
MAX_XML_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
CASE_VERSION = re.compile(r"^([CEIP]\d\d)[ ._-]?(V\d\d)", re.I)


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


# ------------------------------------------------------------------ DEXPI: files, truth, loops

def load_xml(path):
    path = Path(path)
    if path.stat().st_size > MAX_XML_BYTES:
        raise ValueError(f"{path.name}: over {MAX_XML_BYTES} bytes")
    root = ET.parse(path).getroot()
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def dexpi_files(version, case_prefixes=None):
    """[{rel, case, case_version, system, exporter, schema}] for every XML of one DEXPI version folder."""
    base = DEXPI_ROOT / f"dexpi {version}" / "example pids"
    out = []
    if not base.is_dir():
        return out
    for case_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        if case_prefixes and not case_dir.name.startswith(tuple(case_prefixes)):
            continue
        for x in sorted(case_dir.rglob("*")):
            if not (x.is_file() and x.suffix.lower() == ".xml"):
                continue
            try:
                root = load_xml(x)
                info = root.find("PlantInformation")
                system = (info.get("OriginatingSystem") if info is not None else None) or "?"
                schema = (info.get("SchemaVersion") if info is not None else None) or "?"
            except (ET.ParseError, ValueError):
                system, schema = "?", "?"
            m = CASE_VERSION.match(x.name)
            cv = (m.group(1) + m.group(2)).upper() if m else case_dir.name[:3]
            out.append({"rel": x.relative_to(DEXPI_ROOT).as_posix(), "file": x.name, "case": case_dir.name,
                        "case_version": cv, "system": system, "schema": schema,
                        "exporter": "reference" if system in REFERENCE_SYSTEMS else EXPORTERS.get(system, system)})
    return out


def own_attrs(el):
    out = {}
    for g in el.findall("./GenericAttributes/GenericAttribute"):
        if g.get("Name") and g.get("Value") and g.get("Name") not in out:
            out[g.get("Name")] = g.get("Value")
    return out


def label_texts(el):
    return [t.get("String", "").strip() for lab in el.findall("Label") for t in lab.iter("Text")
            if t.get("String", "").strip()]


def letters_and_number(el):
    """(letters, number) of an instrument function from its attributes, else a Tag attribute, else its label."""
    a = own_attrs(el)
    cat = a.get("ProcessInstrumentationFunctionCategoryAssignmentClass") or ""
    fns = a.get("ProcessInstrumentationFunctionsAssignmentClass") or ""
    mod = a.get("ProcessInstrumentationFunctionModifierAssignmentClass") or ""
    num = a.get("ProcessInstrumentationFunctionNumberAssignmentClass") or ""
    letters = cat
    for extra in (fns, mod):
        if extra and extra not in letters[1:]:
            letters += extra
    if not letters:
        for k in ("Tag", "TagName", "TagNameAssignmentClass"):
            m = re.match(r"\s*([A-Za-z]+)[\s-]*(.*)$", a.get(k) or "")
            if m:
                letters, num = m.group(1), num or m.group(2).strip()
                break
    if not letters:
        lines = label_texts(el)
        if lines:
            m = re.match(r"\s*([A-Za-z]+)[\s-]*(.*)$", lines[0])
            if m:
                letters = m.group(1)
                num = num or m.group(2).strip() or (lines[1] if len(lines) > 1 else "")
    return letters.upper().replace(" ", ""), num.strip()


def is_control(letters):
    return "C" in (letters or "")[1:]


def dexpi_truth(root):
    """Reader-independent counts read straight from one DEXPI file (see the module docstring)."""
    cat = root.find("ShapeCatalogue")
    catalogue = set(cat.iter()) if cat is not None else set()
    parent = {c: p for p in root.iter() for c in p}
    ids, dup = set(), set()
    for el in root.iter():
        if el in catalogue or not el.get("ID"):
            continue
        (dup if el.get("ID") in ids else ids).add(el.get("ID"))

    def top_level(eq):
        p = parent.get(eq)
        while p is not None:
            if p.tag == "Equipment":
                return False
            p = parent.get(p)
        return True

    live = [el for el in root.iter() if el not in catalogue]
    equipment = [e for e in live if e.tag == "Equipment" and top_level(e)]
    pifs = [e for e in live if e.tag in ("ProcessInstrumentationFunction", "ProcessInstrument")]
    control = [e for e in pifs if is_control(letters_and_number(e)[0])]
    return {"root": root.tag, "duplicate_ids": sorted(dup),
            "equipment": len(equipment), "instrument_functions": len(pifs), "control_functions": len(control),
            "control_function_labels": [" ".join(letters_and_number(e)).strip() for e in control],
            "control_function_ids": [e.get("ID") for e in control],
            "instrument_function_ids": [e.get("ID") for e in pifs],
            "loops": sum(e.tag in ("InstrumentationLoopFunction", "InstrumentLoop") for e in live),
            "segments": sum(e.tag == "PipingNetworkSegment" for e in live),
            "piping_systems": sum(e.tag == "PipingNetworkSystem" for e in live)}


def refusal_confirmed(message, truth):
    """Does this module see the reason the reader gave for refusing the file?"""
    if "more than once" in message:
        return bool(truth and truth["duplicate_ids"])
    if "root element" in message:
        return bool(truth and truth["root"] != "PlantModel")
    if "nothing to read" in message:
        return bool(truth and not (truth["equipment"] or truth["piping_systems"] or truth["instrument_functions"]))
    if "not well-formed" in message:
        return truth is None
    return False


def run_reader(xml_path, out_dir):
    """dexpi_reader.run on one file -> (model, None) or (None, refusal message). Other exceptions propagate."""
    # Imported by name: only the cells that run the reader should hash it (corpus_matrix.py lists it for them),
    # not every cell that uses this module.
    dr = importlib.import_module("dexpi_reader")
    try:
        model, _ = quiet(dr.run, str(xml_path), str(out_dir), quiet=True)
        return model, None
    except dr.DexpiError as e:
        return None, str(e)


def model_counts(model):
    return {k: len(model.get(k) or []) for k in ("units", "streams", "instruments", "controllers", "final_elements",
                                                 "manual_valves")}


def _by_id(root):
    return {el.get("ID"): el for el in root.iter() if el.get("ID")}


def _assoc(el, kind):
    return [a.get("ItemID") for a in el.findall("Association") if a.get("Type") == kind]


def dexpi_loop_list(root):
    """(loops, incomplete): loop-list rows [controller, measurement, output, description] from the file's loop
    functions, and the control loops that lack a measurement or an output in the XML (see the module docstring)."""
    ids = _by_id(root)
    pif_tags = ("ProcessInstrumentationFunction", "ProcessInstrument")
    loops, incomplete, seen = [], [], set()
    for lf in [e for e in root.iter() if e.tag in ("InstrumentationLoopFunction", "InstrumentLoop")]:
        members = [ids.get(i) for i in _assoc(lf, "is a collection including")]
        members += [e for e in lf.iter() if e is not lf and e.tag in pif_tags]
        members += [e for e in root.iter() if e.tag in pif_tags and lf.get("ID") in _assoc(e, "is a part of")]
        members = [m for m in dict.fromkeys(members) if m is not None and m.tag in pif_tags]
        for c in members:
            letters, num = letters_and_number(c)
            if not is_control(letters) or c.get("ID") in seen:
                continue
            seen.add(c.get("ID"))
            ctag = f"{letters} {num}".strip()
            if c.find(".//ProcessSignalGeneratingFunction") is not None:
                meas = ctag
            else:
                others = [f"{l} {n}".strip() for l, n in (letters_and_number(m) for m in members if m is not c) if l and n]
                meas = others[0] if others else ""
            out = ""
            for af in c.iter("ActuatingFunction"):
                for sys_id in _assoc(af, "is fulfilled by"):
                    sysel = ids.get(sys_id)
                    if sysel is None:
                        continue
                    out = own_attrs(sysel).get("ActuatingSystemNumberAssignmentClass") or ""
                    for comp in sysel.iter("ActuatingSystemComponent"):
                        if out:
                            break
                        out = own_attrs(comp).get("SubTagNameAssignmentClass") or ""
                        for ref in _assoc(comp, "refers to"):
                            v = ids.get(ref)
                            if v is not None and not out:
                                out = own_attrs(v).get("PipingComponentNumberAssignmentClass") or ""
                out = out or own_attrs(af).get("ActuatingFunctionNumberAssignmentClass") or ""
                if out:
                    break
            row = [ctag, meas, out.strip(), f"loop function {lf.get('ID')}"]
            if num and meas and out.strip():
                loops.append(row)
            else:
                incomplete.append({"controller": ctag, "measurement": meas or None, "output": out.strip() or None,
                                   "loop": lf.get("ID")})
    return loops, incomplete


def write_loops(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["controller", "measurement", "output", "description"])
        w.writerows(rows)


# ------------------------------------------------------------------ historians

def skab_runs(base):
    """[(group, name, path)] for every labelled SKAB run (valve1, valve2, other)."""
    base = Path(base)
    out = []
    for group in ("valve1", "valve2", "other"):
        d = base / group
        if d.is_dir():
            out += [(group, p.stem, p) for p in sorted(d.glob("*.csv"), key=lambda p: (len(p.stem), p.stem))]
    return out


def skab_to_csv(src, dest):
    """SKAB ';' CSV -> historian CSV (labels dropped). Returns {rows, fault_start_row, first_changepoint_row}."""
    with Path(src).open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    head, data = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
    ia = head.index("anomaly") if "anomaly" in head else None  # the anomaly-free run has no label columns
    ic = head.index("changepoint") if "changepoint" in head else None
    keep = [j for j in range(len(head)) if j not in (ia, ic)]
    with Path(dest).open("w", encoding="utf-8", newline="") as g:
        w = csv.writer(g, lineterminator="\n")
        w.writerow([head[j] for j in keep])
        w.writerows([[r[j] for j in keep] for r in data])
    lab = lambda r, j: j is not None and float(r[j] or 0) == 1.0
    fault = next((i for i, r in enumerate(data) if lab(r, ia)), None)
    change = next((i for i, r in enumerate(data) if lab(r, ic)), None)
    return {"rows": len(data), "fault_start_row": fault, "first_changepoint_row": change}


def head_csv(src, dest, rows):
    """The first `rows` data rows of a historian CSV (a run's own normal start, for the self-fit variant)."""
    with Path(src).open(encoding="utf-8", newline="") as f, Path(dest).open("w", encoding="utf-8", newline="") as g:
        r, w = csv.reader(f), csv.writer(g, lineterminator="\n")
        w.writerow(next(r))
        for i, row in enumerate(r):
            if i >= rows:
                break
            w.writerow(row)


HAI_LABELS = ("attack", "attack_P1", "attack_P2", "attack_P3")


def hai_to_csv(src_gz, dest):
    """HAI 21.03 gzip CSV -> historian CSV without the attack labels. Returns {rows, events [(start, end)]}."""
    events, start, n = [], None, 0
    with gzip.open(src_gz, "rt", encoding="utf-8", newline="") as f, Path(dest).open("w", encoding="utf-8",
                                                                                      newline="") as g:
        r, w = csv.reader(f), csv.writer(g, lineterminator="\n")
        head = [h.strip() for h in next(r)]
        drop = {head.index(h) for h in HAI_LABELS if h in head}
        ia = head.index("attack") if "attack" in head else None
        keep = [j for j in range(len(head)) if j not in drop]
        w.writerow([head[j] for j in keep])
        for i, row in enumerate(r):
            w.writerow([row[j] for j in keep])
            on = ia is not None and float(row[ia] or 0) == 1.0
            if on and start is None:
                start = i
            if not on and start is not None:
                events.append((start, i - 1))
                start = None
            n = i + 1
    if start is not None:
        events.append((start, n - 1))
    return {"rows": n, "events": events}


PRONTO_BASE = EXTERNAL / "pronto-more" / "PRONTO benchmark case study"
PRONTO_MERGED = "Pre-processed data/Aligned and labelled alarm and process data/Testday{day}_merged.csv"
# Rows are 0-based rows of the day's merged file; every label boundary is checked by build_pronto_csvs.
# "overlap": the run's pre-fault rows are part of the normal CSV's held-out half (used to choose K), so its pre-fault
# false alarms are not an independent count; such runs are scored for detection only (set before the first run).
PRONTO_DAYS = {
    "2": {"raw": "C1 Air Blockage/Test2/Process Data/0907Testday2.csv", "pairs": {
        "normal": {"rows": (0, 361), "label": "Normal",
                   "what": "the day's only normal running before the first fault (6 min)"},
        "blockage": {"rows": (180, 9241), "fault_label": "Air blockage", "fault_row": 361, "overlap": True,
                     "what": "air blockage test; its 181 pre-fault rows are the normal CSV's held-out half"},
        "leakage": {"rows": (9241, 12420), "fault_label": "Air leakage", "fault_row": 9602,
                    "what": "6 min of normal running 2.5 h later, then air leakage: scored against the morning bands"}}},
    "4": {"raw": "C0 Normal and Slugging conditions/Test10/Process Data/0912Testday4.csv", "pairs": {
        "normal": {"rows": (1559, 3540), "label": "Normal", "what": "the day's first normal block (33 min)"},
        "slugging1": {"rows": (2549, 4544), "fault_label": "Slugging", "fault_row": 3540, "overlap": True,
                      "what": "slugging right after the normal block; its pre-fault rows are the held-out half"},
        "slugging2": {"rows": (4544, 9594), "fault_label": "Slugging", "fault_row": 7314,
                      "what": "46 min of normal running not in the normal CSV, then slugging"}}},
}


def pronto_day(day, dest):
    """Write the day's historian CSVs into dest. Returns {name: info} (fault_start_row, rows, overlap, what)."""
    import fetch_corpus as fc
    cfg = PRONTO_DAYS[day]
    merged = fc.read_rows((PRONTO_BASE / PRONTO_MERGED.format(day=day)).read_text(encoding="utf-8-sig"))
    raw = fc.read_rows((PRONTO_BASE / cfg["raw"]).read_text(encoding="utf-8-sig"))
    pairs = {k: {kk: vv for kk, vv in v.items() if kk != "overlap"} for k, v in cfg["pairs"].items()}
    out, meta = fc.build_pronto_csvs(merged, raw, pairs=pairs)
    info = {}
    for name, (text, i) in out.items():
        (Path(dest) / f"day{day}_{name}.csv").write_text(text, encoding="utf-8", newline="")
        info[name] = {"file": f"day{day}_{name}.csv", "rows": i["rows"], "fault_start_row": i.get("fault_start_row"),
                      "fault_start_time": i.get("fault_start_time"), "overlap": bool(cfg["pairs"][name].get("overlap")),
                      "what": cfg["pairs"][name]["what"]}
    info["_alignment"] = meta["alignment"]
    return info


# ------------------------------------------------------------------ process models for generate.py

IDAES_TYPES = (("mixer", "feed_header"), ("heater", "heat_exchanger"), ("reactor", "reactor"), ("cstr", "reactor"),
               ("flash", "separator"), ("separator", "vessel"), ("pressure_changer", "compressor"),
               ("tray_column", "stripper"))


def idaes_model(path):
    """IDAES flowsheet visualizer JSON -> (process model, source summary)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    m = d["model"]
    boundary = {k for k, v in m["unit_models"].items() if v["type"] in ("feed", "product")}
    units, unmapped = [], []
    for uid, u in m["unit_models"].items():
        if uid in boundary:
            continue
        t = next((gen for word, gen in IDAES_TYPES if word in u["type"]), None)
        if t is None:
            t = "vessel"
            unmapped.append(f"{uid} ({u['type']})")
        units.append({"id": uid, "name": f"{u['type'].replace('_', ' ')} {uid}", "type": t,
                      "type_basis": f"IDAES unit type {u['type']}", "source": f"IDAES flowsheet {m.get('id')} unit {uid}"})
    st = m.get("stream_table") or {}
    cols = st.get("columns") or []
    facts = defaultdict(dict)
    for row in st.get("data") or []:
        var, unit = row[0], (row[1].get("raw") if isinstance(row[1], dict) else row[1])
        for col, cell in zip(cols[2:], row[2:]):
            val = cell[0] if isinstance(cell, list) else cell
            if isinstance(val, (int, float)):
                facts[col][var] = {"value": val, "uom": unit}
    streams = [{"id": sid, "name": sid, "from": "BL" if a["source"] in boundary else a["source"],
                "to": "BL" if a["dest"] in boundary else a["dest"], "facts": facts.get(sid, {}),
                "source": f"IDAES flowsheet {m.get('id')} arc {sid}"} for sid, a in m["arcs"].items()]
    model = {"meta": {"model_id": f"idaes-{m.get('id')}", "title": f"IDAES flowsheet {m.get('id')} (converted)",
                      "source_document": "IDAES examples, flowsheet visualizer JSON (BSD-style IDAES licence)"},
             "units": units, "streams": streams, "instruments": [], "final_elements": [], "controllers": []}
    summary = {"unit_models": len(m["unit_models"]), "boundary_nodes": sorted(boundary), "arcs": len(m["arcs"]),
               "units": len(units), "streams": len(streams), "unmapped_types": unmapped,
               "streams_with_values": sum(1 for s in streams if s["facts"]),
               "mixer_balance": idaes_mixer_balance(m, facts)}
    return model, summary


def idaes_mixer_balance(m, facts):
    """Each mixer: outlet component flows minus the sum of inlet flows (largest relative difference)."""
    out = {}
    for uid, u in m["unit_models"].items():
        if u["type"] != "mixer":
            continue
        ins = [s for s, a in m["arcs"].items() if a["dest"] == uid]
        outs = [s for s, a in m["arcs"].items() if a["source"] == uid]
        worst = 0.0
        for var in facts.get(outs[0], {}) if outs else {}:
            if not var.startswith("flow_mol"):
                continue
            o = facts[outs[0]][var]["value"]
            i = sum(facts.get(s, {}).get(var, {}).get("value", 0.0) for s in ins)
            worst = max(worst, abs(o - i) / max(abs(o), 1e-9))
        out[uid] = round(worst, 6)
    return out


DWSIM_SKIP = ("MaterialStream", "EnergyStream", "OT_Recycle", "OT_EnergyRecycle", "OT_Adjust", "OT_Spec")
DWSIM_LOGICAL = ("OT_Recycle", "OT_EnergyRecycle")
DWSIM_TYPES = (("Pump", "pump"), ("Compressor", "compressor"), ("Expander", "compressor"),
               ("HeatExchanger", "heat_exchanger"), ("Heater", "heat_exchanger"), ("Cooler", "heat_exchanger"),
               ("Reactor", "reactor"), ("RCT_", "reactor"), ("Column", "stripper"), ("Absorber", "stripper"),
               ("ComponentSeparator", "separator"), ("Vessel", "separator"), ("Tank", "tank"),
               ("NodeIn", "feed_header"), ("NodeOut", "feed_header"))


def dwsim_xml(zip_path):
    """The flowsheet XML bytes inside a FOSSEE project zip (outer zip -> .dwxmz zip -> one .xml)."""
    with zipfile.ZipFile(zip_path) as outer:
        dw = [i for i in outer.infolist() if i.filename.lower().endswith((".dwxmz", ".dwxml"))]
        if not dw:
            raise ValueError("no .dwxmz/.dwxml flowsheet in the project zip")
        if dw[0].file_size > MAX_MEMBER_BYTES:
            raise ValueError(f"{dw[0].filename}: over {MAX_MEMBER_BYTES} bytes")
        data = outer.read(dw[0])
    if dw[0].filename.lower().endswith(".dwxmz"):
        with zipfile.ZipFile(io.BytesIO(data)) as inner:
            xs = [i for i in inner.infolist() if i.filename.lower().endswith(".xml")]
            if not xs or xs[0].file_size > MAX_MEMBER_BYTES:
                raise ValueError("no flowsheet XML (or one over the size cap) inside the .dwxmz")
            data = inner.read(xs[0])
    return data


def _attached(conn):
    return (conn.get("IsAttached") or "").lower() == "true"


def dwsim_model(zip_path):
    """FOSSEE DWSIM project zip -> (process model, source summary)."""
    root = ET.fromstring(dwsim_xml(zip_path))
    objs = {}
    for go in root.iter("GraphicObject"):
        name = go.findtext("Name")
        if name:
            objs[name] = {"type": go.findtext("ObjectType") or "?", "tag": (go.findtext("Tag") or "").strip(),
                          "ins": [c.get("AttachedFromObjID") for c in go.findall("InputConnectors/Connector")
                                  if _attached(c) and c.get("AttachedFromObjID")],
                          "outs": [c.get("AttachedToObjID") for c in go.findall("OutputConnectors/Connector")
                                   if _attached(c) and c.get("AttachedToObjID")]}
    unit_names = [n for n, o in objs.items() if o["type"] not in DWSIM_SKIP and not o["type"].startswith("GO_")]
    ids, used = {}, set()
    for n in unit_names:
        tag = objs[n]["tag"]
        ok = tag and not any(c in tag for c in '/\\\0') and tag.lower() not in used and tag not in (".", "..")
        ids[n] = tag if ok else n
        used.add(ids[n].lower())
    units, opaque = [], []
    for n in unit_names:
        t = objs[n]["type"]
        gen = next((g for word, g in DWSIM_TYPES if word in t), None)
        if gen is None:
            gen = "vessel"
            opaque.append(t)
        units.append({"id": ids[n], "name": f"{t} {objs[n]['tag'] or n}"[:120], "type": gen,
                      "type_basis": f"DWSIM ObjectType {t}", "source": f"DWSIM graphic object {n}"})
    mats = {n: o for n, o in objs.items() if o["type"] == "MaterialStream"}
    logical = {n for n, o in objs.items() if o["type"] in DWSIM_LOGICAL}
    joined, streams, sids = set(), [], set()

    def end(obj_ids, side, depth=0):
        for x in obj_ids:
            if x in ids:
                return ids[x]
            if x in logical and depth < 10:  # through a recycle block to the stream on its other side
                nxt = [s for s, o in mats.items() if x in (o["ins"] if side == "to" else o["outs"])]
                for s in nxt:
                    joined.add(s)
                    return end(mats[s]["outs"] if side == "to" else mats[s]["ins"], side, depth + 1)
        return "BL"

    for n, o in mats.items():
        if n in joined:
            continue
        if any(x in logical for x in o["ins"]) and not any(x in ids for x in o["ins"]):
            continue  # leaves a recycle block: it is joined to the stream entering that block
        sid = o["tag"] or n
        sid = sid if sid not in sids else f"{sid} ({n[:12]})"
        sids.add(sid)
        streams.append({"id": sid, "name": sid, "from": end(o["ins"], "from"), "to": end(o["outs"], "to"),
                        "source": f"DWSIM material stream {n}"})
    controllers = sum(o["type"] in ("OT_Adjust", "OT_Spec") or "PID" in o["type"] for o in objs.values())
    model = {"meta": {"model_id": f"dwsim-{Path(zip_path).stem}", "title": f"DWSIM flowsheet {Path(zip_path).stem}",
                      "source_document": "FOSSEE DWSIM Flowsheeting Project (CC BY-SA 4.0)"},
             "units": units, "streams": streams, "instruments": [], "final_elements": [], "controllers": []}
    summary = {"units": len(units), "streams": len(streams), "material_streams": len(mats),
               "joined_through_recycle": len(mats) - len(streams), "energy_streams":
               sum(o["type"] == "EnergyStream" for o in objs.values()),
               "solver_blocks": sorted(o["type"] for o in objs.values() if o["type"] in DWSIM_SKIP[2:]),
               "opaque_or_generic_units": sorted(opaque), "controller_like_blocks": controllers}
    return model, summary


# ------------------------------------------------------------------ HAI DCS loop candidates

def hai_dcs_candidates(folder):
    """Per DCS sheet: named measurement nodes, named outputs fed by a CO link, and the (measurement, output) pairs
    joined through function blocks. Candidates only; the graphs carry no block types."""
    out = {}
    for f in sorted(Path(folder).glob("dcs_*.json")):
        g = ast.literal_eval(f.read_text(encoding="utf-8"))
        nodes = [n["id"] for n in g["nodes"]]
        block = re.compile(r"^\d+\.\d+$")
        named = [n for n in nodes if not block.match(n) and n not in ("HMI", "EWS", "GATEOPEN")]
        adj = defaultdict(list)
        for l in g["links"]:
            adj[l["source"]].append((l["target"], (l.get("label") or "").strip()))
        outputs = sorted({l["target"] for l in g["links"] if (l.get("label") or "").strip() == "CO"})
        sp_blocks = sorted({l["target"] for l in g["links"] if l["source"] == "HMI" and l.get("label") == "SP"})
        pairs = []
        for m in named:
            if m in outputs:
                continue
            seen, q, hit = {m}, deque([m]), set()
            while q:
                x = q.popleft()
                for y, lab in adj[x]:
                    if y in outputs and lab == "CO":
                        hit.add(y)
                    if y not in seen and block.match(y):
                        seen.add(y)
                        q.append(y)
            pairs += [[m, o] for o in sorted(hit)]
        out[f.stem] = {"measurement_nodes": [n for n in named if n not in outputs], "co_outputs": outputs,
                       "setpoint_blocks": sp_blocks, "candidate_pairs": pairs}
    return out


def temp_dir():
    return tempfile.TemporaryDirectory()


# ------------------------------------------------------------------ DEXPI 1.2 vendor renders -> keyed sheets (A2)

# Rules, fixed before any tracer or scorer ran on these renders (data/attempts.json):
#   Which files: every DEXPI 1.2 XML exported by SPPID, Comos, AVEVA or AutoCAD (dexpi_files) that has the exporting
#     tool's own render beside it: a PNG, JPG or PDF with the XML's own file stem (C02V01-AVV.EX01.xml ->
#     C02V01-AVV.EX01.png). Renders made by another tool on import (-AUD.IM01, -VTT.IM01, -SAG.IM01...) have another
#     stem and are not used. A PNG/JPG is preferred to a PDF of the same stem; a PDF's first page is rasterised with
#     PyMuPDF, long side RENDER_PDF_LONG_SIDE px (as scripts/adapt_dexpi.py renders the DEXPI 1.3 sheets).
#   The map: drawing coordinates (x right, y up) -> render pixels by u = a*x + c, v = e*y + f (a scale and offset per
#     axis; no rotation or shear). Fitted by iterated closest points from the XML's own drawn geometry (every
#     primitive outside the shape catalogue and outside labels, catalogue shapes placed by Position/Scale, piping and
#     signal centre lines), densified, onto the render's ink (Otsu, as the tracer binarises), from three starts (the
#     geometry's bounding box onto the ink's, onto the ink's without frame-sized pieces, each also shrunk about its
#     centre by MAP_START_SCALES since labels beside a drawing widen its ink, and the Drawing's Extent onto the whole
#     image); the start whose fit leaves the most points on ink is kept.
#   Clean: at least MAP_MIN_ON_INK of the geometry points land within max(MAP_TOL_MIN, MAP_TOL_FRAC x long side) px
#     of ink, at least MAP_MIN_ABOVE_CHANCE more than land on ink with the map moved MAP_CHANCE_SHIFT tolerances
#     diagonally (a dot grid or dense background puts points on ink anywhere), and the two axis scales agree within
#     MAP_ASPECT (a render is not stretched). Anything else is n/a with
#     the reason; so is a file whose key scripts/adapt_dexpi.py cannot build (convert_xml refuses), one with fewer than
#     two scored symbols, or a render that will not decode. A dark-background render (a CAD screen capture) is first
#     made dark ink on white by colour distance from its background (read_render), since the tracer reads dark ink on
#     light paper; the application's own window around the drawing stays in the image. An overlay of the mapped
#     geometry (red) and key boxes (blue) on each render is written for a person to check.
#   The key: scripts/adapt_dexpi.py's conversion rules (convert_xml: classes, boxes, links), its boxes put through
#     the fitted map and clipped to the image, its minimum box side (0.005 of the long side), written as <id>.png (the
#     render, decoded and written as PNG) + <id>.graphml in the PID2Graph key layout, plus <id>.json with the XML
#     path, the map and its check. The pipe-layer truth is read from the XML itself (line_layers.dexpi_truth).
#   Needs OpenCV and numpy (PyMuPDF for PDF renders); the rest of this module is stdlib.
RENDER_EXT = (".png", ".jpg", ".jpeg", ".pdf")
VENDOR_EXPORTERS = ("sppid", "comos", "aveva", "autocad")
VENDOR_KEYS = EXTERNAL / "dexpi-ttc-all" / "vendor-keys"
RENDER_PDF_LONG_SIDE = 3200
MAP_TOL_MIN, MAP_TOL_FRAC = 2.0, 0.003
MAP_MIN_ON_INK = 0.85
MAP_ASPECT = (0.8, 1.25)
KEY_MIN_BOX_FRAC = 0.005
DARK_INK_DIST = 60
MAP_START_SCALES = (0.6, 0.75, 0.9)
MAP_CHANCE_SHIFT = 5
MAP_MIN_ABOVE_CHANCE = 0.5


def vendor_renders(exporters=VENDOR_EXPORTERS):
    """[{id, exporter, case_version, xml (Path), render (Path), rel}] for every vendor DEXPI 1.2 export with its own
    render."""
    out = []
    for f in dexpi_files("1.2"):
        if f["exporter"] not in exporters:
            continue
        x = DEXPI_ROOT / f["rel"]
        same = sorted(p for p in x.parent.iterdir()
                      if p.is_file() and p.stem.lower() == x.stem.lower() and p.suffix.lower() in RENDER_EXT)
        if not same:
            continue
        r = next((p for p in same if p.suffix.lower() != ".pdf"), same[0])
        out.append({"id": re.sub(r"[^A-Za-z0-9._-]", "_", x.stem), "exporter": f["exporter"],
                    "case_version": f["case_version"], "xml": x, "render": r, "rel": f["rel"]})
    return out


def read_render(path):
    """The render as a grey image (numpy uint8) and whether it was normalised. PDF: first page at
    RENDER_PDF_LONG_SIDE px. A dark-background render (a CAD screen capture: mean grey below 128) is normalised to dark
    ink on white: the background is its most common colour, and a pixel is ink when its colour is more than
    DARK_INK_DIST from it (RGB distance, 0-441), which keeps coloured lines (a blue pipe on black has almost the
    background's grey) and drops a dim display grid."""
    import cv2
    import numpy as np
    path = Path(path)
    if path.stat().st_size > MAX_MEMBER_BYTES:
        raise ValueError(f"{path.name}: over {MAX_MEMBER_BYTES} bytes")
    if path.suffix.lower() == ".pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        page = doc[0]
        zoom = RENDER_PDF_LONG_SIDE / max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, colorspace=fitz.csRGB)
        img = cv2.cvtColor(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3), cv2.COLOR_RGB2BGR)
        return _light(img)
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"{path.name}: not a readable image")
    if img.dtype != np.uint8:
        img = (img / 257).astype(np.uint8)
    if img.ndim == 3 and img.shape[2] == 4:  # transparent background: composite on white
        a = img[:, :, 3:4].astype(np.float32) / 255
        img = (img[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
    return _light(img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))


def _light(bgr):
    import cv2
    import numpy as np
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if float(gray.mean()) >= 128:
        return gray, False
    px = bgr.reshape(-1, 3)
    vals, counts = np.unique(px[::7], axis=0, return_counts=True)
    bg = vals[counts.argmax()].astype(float)
    d = np.sqrt(((bgr.astype(float) - bg) ** 2).sum(axis=2))
    return np.where(d > DARK_INK_DIST, 0, 255).astype(np.uint8), True


def xml_geometry(xml_path, step_frac=1 / 1500):
    """The XML's drawn geometry as points in drawing coordinates (numpy N x 2), densified to steps of step_frac of
    the geometry's diagonal: primitives outside the shape catalogue and labels, catalogue shapes placed on their
    items, centre lines. Labels and text are left out (their glyphs are not in the file)."""
    import numpy as np
    import adapt_dexpi as ad
    root = load_xml(xml_path)
    cat_el = root.find("ShapeCatalogue")
    catalogue = {e.get("ComponentName"): e for e in (cat_el if cat_el is not None else [])}
    skip = set(cat_el.iter()) if cat_el is not None else set()
    for lab in root.iter("Label"):
        skip |= set(lab.iter())
    arc_parts = {c for tc in root.iter("TrimmedCurve") for c in tc.iter() if c is not tc}  # drawn by their arc
    polys = []
    for el in root.iter():
        if el in skip or el in arc_parts:
            continue
        if el.tag in ad.GEOMETRY or el.tag == "CenterLine":
            pts = ad.primitive_points(el) if el.tag != "CenterLine" else [
                (ad.fnum(c, "X"), ad.fnum(c, "Y")) for c in el.iter("Coordinate")]
            if pts:
                polys.append(pts)
        if el.get("ComponentName") in catalogue and el.find("Position") is not None:
            for g in catalogue[el.get("ComponentName")].iter():
                if g.tag in ad.GEOMETRY and g not in arc_parts:
                    pts = ad.place(ad.primitive_points(g), el)
                    if pts:
                        polys.append(pts)
    if not polys:
        return np.zeros((0, 2))
    allp = np.array([p for q in polys for p in q], float)
    diag = float(np.hypot(*(allp.max(0) - allp.min(0)))) or 1.0
    step = diag * step_frac
    out = []
    for q in polys:
        q = np.array(q, float)
        out.append(q[:1])
        for a, b in zip(q, q[1:]):
            n = int(np.hypot(*(b - a)) // step)
            if n:
                t = (np.arange(1, n + 1) / (n + 1))[:, None]
                out.append(a + (b - a) * t)
            out.append(b[None])
    return np.vstack(out)


def _ink(gray):
    import cv2
    _, ink = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return ink.astype("uint8")


def fit_render_map(points, gray, extent=None, iters=60):
    """Fit u = a*x + c, v = e*y + f from drawing points onto the render's ink (iterated closest points, from each
    start; extent: the Drawing's (xmin, ymin, xmax, ymax), a start onto the whole image). Returns {"map": [a, c, e,
    f], "on_ink", "tol", "start", "aspect"} for the best start, or None."""
    import cv2
    import numpy as np
    ink = _ink(gray)
    H, W = ink.shape
    tol = max(MAP_TOL_MIN, MAP_TOL_FRAC * max(W, H))
    ys, xs = np.nonzero(ink)
    if not len(ys) or not len(points):
        return None
    dist, lab = cv2.distanceTransformWithLabels(1 - ink, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    near = np.zeros((int(lab.max()) + 1, 2))
    near[lab[ys, xs]] = np.stack([xs, ys], 1)
    px, py = points[:, 0], points[:, 1]
    gx0, gx1, gy0, gy1 = px.min(), px.max(), py.min(), py.max()

    def from_boxes(bx0, by0, bx1, by1, g=None):  # a drawing box (the geometry's by default) onto a pixel box, y flipped
        x0, y0, x1, y1 = g or (gx0, gy0, gx1, gy1)
        a = (bx1 - bx0) / max(x1 - x0, 1e-9)
        e = -(by1 - by0) / max(y1 - y0, 1e-9)
        return a, bx0 - a * x0, e, by0 - e * y1

    def place(a, c, e, f):
        u, v = a * px + c, e * py + f
        inside = (u >= 0) & (u < W) & (v >= 0) & (v < H)
        ui, vi = np.clip(u.round().astype(int), 0, W - 1), np.clip(v.round().astype(int), 0, H - 1)
        return ui, vi, np.where(inside, dist[vi, ui], np.inf)

    starts = {"geometry onto ink": from_boxes(xs.min(), ys.min(), xs.max(), ys.max())}
    n, _, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    keep = ~((st[:, 2] > 0.8 * W) | (st[:, 3] > 0.8 * H))
    keep[0] = False
    if keep.any() and not keep[1:].all():
        k = st[keep]
        starts["geometry onto ink without frame"] = from_boxes(k[:, 0].min(), k[:, 1].min(),
                                                               (k[:, 0] + k[:, 2]).max() - 1,
                                                               (k[:, 1] + k[:, 3]).max() - 1)
    if extent and extent[2] > extent[0] and extent[3] > extent[1]:
        starts["extent onto image"] = from_boxes(0, 0, W - 1, H - 1, tuple(extent))
    # labels beside the drawing widen the ink's box: the box starts again at other scales about the same centre
    for name in [n for n in starts if n != "extent onto image"]:
        a, c, e, f = starts[name]
        cx, cy = a * (gx0 + gx1) / 2 + c, e * (gy0 + gy1) / 2 + f
        for k in MAP_START_SCALES:
            starts[f"{name} x{k}"] = (a * k, cx - a * k * (gx0 + gx1) / 2, e * k, cy - e * k * (gy0 + gy1) / 2)
    best = None
    for name, (a, c, e, f) in starts.items():
        thr = 0.05 * max(W, H)
        for _ in range(iters):
            ui, vi, d = place(a, c, e, f)
            sel = d <= thr
            if sel.sum() < 10:
                break
            nx, ny = near[lab[vi[sel], ui[sel]], 0], near[lab[vi[sel], ui[sel]], 1]
            one = np.ones(int(sel.sum()))
            a2, c2 = np.linalg.lstsq(np.stack([px[sel], one], 1), nx, rcond=None)[0]
            e2, f2 = np.linalg.lstsq(np.stack([py[sel], one], 1), ny, rcond=None)[0]
            if not (np.isfinite([a2, c2, e2, f2]).all() and a2 > 0 and e2 < 0):
                break
            a, c, e, f = a2, c2, e2, f2
            thr = max(tol, thr * 0.8)
        _, _, d = place(a, c, e, f)
        # by chance: the same map moved diagonally by MAP_CHANCE_SHIFT x tol each way (a dense background, a dot
        # grid or a screen's chrome puts points on ink wherever they land)
        s = MAP_CHANCE_SHIFT * tol
        chance = float(np.mean([(place(a, c + dx, e, f + dy)[2] <= tol).mean()
                                for dx in (-s, s) for dy in (-s, s)]))
        r = {"map": [float(a), float(c), float(e), float(f)], "on_ink": round(float((d <= tol).mean()), 4),
             "on_ink_by_chance": round(chance, 4), "tol": round(tol, 2), "start": name,
             "aspect": round(float(a / -e), 4)}
        if best is None or r["on_ink"] > best["on_ink"]:
            best = r
    return best


def map_box(box, m):
    """A drawing-coordinate box (xmin, ymin, xmax, ymax) through the map: a pixel box (x0, y0, x1, y1)."""
    a, c, e, f = m
    x0, y0, x1, y1 = box
    return a * x0 + c, e * y1 + f, a * x1 + c, e * y0 + f


def key_graphml(model, m, size):
    """adapt_dexpi.convert_xml's model as a PID2Graph-layout key, its boxes through map m (clipped to the image,
    widened to KEY_MIN_BOX_FRAC of the long side). Tees with no drawn shape keep a zero box, as in adapt_dexpi."""
    import adapt_dexpi as ad
    W, H = size
    min_side = KEY_MIN_BOX_FRAC * max(W, H)
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
             '  <key id="d0" for="node" attr.name="label" attr.type="string" />',
             '  <key id="d1" for="node" attr.name="xmin" attr.type="double" />',
             '  <key id="d2" for="node" attr.name="xmax" attr.type="double" />',
             '  <key id="d3" for="node" attr.name="ymin" attr.type="double" />',
             '  <key id="d4" for="node" attr.name="ymax" attr.type="double" />',
             '  <graph edgedefault="undirected">']
    for nid, n in model["nodes"].items():
        if n["box"] is None:
            px = (0.0, 0.0, 0.0, 0.0)
        else:
            px = ad.min_size(map_box(n["box"], m), min_side)
            px = (max(0.0, px[0]), max(0.0, px[1]), min(W - 1.0, px[2]), min(H - 1.0, px[3]))
        lines.append(f'    <node id="{nid}"><data key="d0">{n["class"]}</data>'
                     f'<data key="d1">{px[0]:.2f}</data><data key="d2">{px[2]:.2f}</data>'
                     f'<data key="d3">{px[1]:.2f}</data><data key="d4">{px[3]:.2f}</data></node>')
    for i, (p, q) in enumerate(model["edges"]):
        lines.append(f'    <edge id="e{i}" source="{p}" target="{q}" />')
    return "\n".join(lines + ["  </graph>", "</graphml>", ""])


def write_overlay(path, gray, points, model, m):
    import cv2
    a, c, e, f = m
    H, W = gray.shape
    ov = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for n in model["nodes"].values():
        if n["box"] is not None and n["class"] != "connector":
            b = map_box(n["box"], m)
            cv2.rectangle(ov, (int(b[0]), int(b[1])), (int(round(b[2])), int(round(b[3]))), (255, 120, 0), 1)
    for x, y in points:
        u, v = int(round(a * x + c)), int(round(e * y + f))
        if 0 <= u < W and 0 <= v < H:
            ov[v, u] = (0, 0, 255)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(cv2.imencode(".png", ov)[1].tobytes())


def build_vendor_key(entry, out_dir=VENDOR_KEYS, overlay_dir=None):
    """Map one vendor render (a vendor_renders() entry) and, when the map is clean, write <id>.png, <id>.graphml and
    <id>.json into out_dir. Returns the record: {"id", "exporter", "status": "mapped" | "n/a", "reason", "xml",
    "render", "fit", ...}."""
    import cv2
    import adapt_dexpi as ad
    out_dir = Path(out_dir)
    xml, render = Path(entry["xml"]), Path(entry["render"])
    rel = lambda p: p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()  # noqa: E731
    rec = {"id": entry["id"], "exporter": entry["exporter"], "case_version": entry.get("case_version"),
           "xml": rel(xml), "render": rel(render), "status": "n/a", "reason": ""}
    for ext in (".png", ".graphml", ".json"):  # a key from an earlier build must not outlive a failed map
        (out_dir / f"{entry['id']}{ext}").unlink(missing_ok=True)
    try:
        gray, normalised = read_render(render)
    except Exception as exc:  # noqa: BLE001 - a render that won't decode is n/a with its reason
        rec["reason"] = f"render not readable ({type(exc).__name__}: {exc})"
        return rec
    H, W = gray.shape
    rec["size"] = [W, H]
    rec["dark_background_normalised"] = normalised
    try:
        model = ad.convert_xml(xml)
    except (ValueError, AttributeError, TypeError, KeyError, ET.ParseError) as exc:
        rec["reason"] = f"no key: adapt_dexpi.convert_xml refused ({type(exc).__name__}: {exc})"
        return rec
    scored = [n for n in model["nodes"].values() if n["class"] != "connector"]
    rec["key_symbols"] = len(scored)
    if len(scored) < 2:
        rec["reason"] = f"nothing to link: {len(scored)} scored symbol(s) in the XML"
        return rec
    pts = xml_geometry(xml)
    fit = fit_render_map(pts, gray, model["extent"]) if len(pts) >= 20 else None
    if fit is None:
        rec["reason"] = "too little drawn geometry in the XML (or no ink in the render) to fit a map"
        return rec
    rec["fit"] = fit
    if overlay_dir:
        write_overlay(Path(overlay_dir) / f"{entry['exporter']}__{entry['id']}.png", gray, pts, model, fit["map"])
    problems = []
    if fit["on_ink"] < MAP_MIN_ON_INK:
        problems.append(f"{fit['on_ink']:.0%} of the XML's drawn geometry lands on ink (needs {MAP_MIN_ON_INK:.0%})")
    if fit["on_ink"] - fit["on_ink_by_chance"] < MAP_MIN_ABOVE_CHANCE:
        problems.append(f"{fit['on_ink_by_chance']:.0%} would land on ink by chance (the map moved {MAP_CHANCE_SHIFT} "
                        f"tolerances diagonally), so {fit['on_ink']:.0%} does not show it is right")
    if not MAP_ASPECT[0] <= fit["aspect"] <= MAP_ASPECT[1]:
        problems.append(f"x and y scales disagree (ratio {fit['aspect']})")
    if problems:
        rec["reason"] = "the map fails its check: " + "; ".join(problems)
        return rec
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{entry['id']}.png").write_bytes(cv2.imencode(".png", gray)[1].tobytes())
    (out_dir / f"{entry['id']}.graphml").write_bytes(key_graphml(model, fit["map"], (W, H)).encode("utf-8"))
    rec.update(status="mapped", key_links=len(model["edges"]))
    (out_dir / f"{entry['id']}.json").write_bytes((json.dumps(rec, indent=1) + "\n").encode("utf-8"))
    return rec


def build_vendor_keys(out_dir=VENDOR_KEYS, overlay_dir=None, exporters=VENDOR_EXPORTERS):
    """build_vendor_key for every vendor render; returns every record, mapped or n/a."""
    return [build_vendor_key(e, out_dir, overlay_dir) for e in vendor_renders(exporters)]
