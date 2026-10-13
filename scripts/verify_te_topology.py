"""Check the TE model's units, stream topology, flow directions and tag ownership against the simulator source.

scripts/verify_te_source.py checks each tag's name and units against the header comments of teprob.f. This script
checks the rest of the model, which until now was a hand-built seed: which units exist, which stream connects which
units in which direction, and which unit and stream each measurement and manipulated variable belongs to.

Primary source: teprob.f, the original Downs & Vogel Fortran code (Braatz group mirror, the same file
verify_te_source.py uses). The facts are read out of the code itself, not out of a hand-typed table:
  - the component balances  YP(I+k) = sum(+/- FCM(I,n))  say which internal stream enters or leaves which holdup;
  - the state mapping  UC..(I) = YY(I+k)  and the variable-name suffixes R/S/C/V say which holdup is which unit;
  - the pressure-driven flow lines  DLP = P_from - P_to; IF (DLP < 0) DLP = 0  fix each flow's direction;
  - the XMEAS(n) = ..., XCMP(n) = XST(i,k) and VPOS(k) lines say what each measurement and valve acts on;
  - the header comments give the published stream number for each internal stream.
Second source: the revised TE code by Bathelt, Ricker & Jelali (2015), temexd_mod.c from N. L. Ricker's TE
archive. Its header documents the states, the 41 measurements and the stream names in plain words. It is used as a
cross-check (holdup names, stream numbers, measurement names) and for one fact teprob.f does not state: the
published numbers of the two streams that carry no instrument (5, stripper overhead; 7, reactor effluent). Without
it, those streams are reported unresolvable and the TI-122 name vote has one witness fewer.

Each element gets one result:
  confirmed     the source agrees with the model
  corrected     the source clearly disagrees; the model is updated and the old value kept under "previous"
  unresolvable  the source itself is split (code and documented names point at different units); the model value is
                kept and the element stays flagged for a process expert
"caveats" record what the source cannot tell (for example, physical tap positions, which the simulator never models).

Downloads go to data/external/ (gitignored) and are not redistributed.
Usage:  python scripts/verify_te_topology.py [--write]
Without --write it only reports. The report goes to out/te_topology_check.md either way.
"""
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "te_process_model.json"
REPORT = ROOT / "out" / "te_topology_check.md"

TEPROB = ROOT / "data" / "external" / "te-braatz" / "teprob.f"
TEPROB_URL = "https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/master/teprob.f"
TEPROB_SHA256 = "409975e070780a3b197d37125dddeca64e46c11d8c99028528a56a1f238d45e3"
TEPROB_REF = "teprob.f (Downs & Vogel TE code, Braatz group mirror)"

REVISED_ZIP = ROOT / "data" / "external" / "te-ricker" / "temexd_mod.zip"
REVISED_URL = "https://depts.washington.edu/control/LARRY/TE/temexd_mod.zip"
REVISED_SHA256 = "e43227aaded739cfeba1ec281c54ac8a549f60753e064305a669b906c4b16b0d"
REVISED_MEMBER = "temexd_mod/temexd_mod.c"
REVISED_REF = "temexd_mod.c header (Bathelt, Ricker & Jelali 2015 revised TE code)"

BOUNDARY = "BL"
# Model unit "type" -> source role. The model's own type field picks the unit; no unit IDs are hard-coded.
TYPE_ROLE = {"feed_header": "header", "reactor": "reactor", "separator": "separator", "stripper": "stripper",
             "compressor": "compressor", "condenser": "condenser"}
# Words a documented name uses for each role (header comments of teprob.f and the revised-code header).
ROLE_WORDS = {"reactor": {"reactor", "agitator"}, "separator": {"separator", "sep"}, "stripper": {"stripper"},
              "compressor": {"compressor"}, "condenser": {"condenser"}}
# Holdup variable suffix -> role. The suffix convention (UCLR/UCVR = reactor, UCLS/UCVS = separator,
# UCLC = stripper, UCVV = header vapour) is confirmed against the revised code's state list when it is available.
SUFFIX_ROLE = {"R": "reactor", "S": "separator", "C": "stripper", "V": "header"}
PRESSURE_ROLE = {"PTR": "reactor", "PTS": "separator", "PTV": "header", "760.0": BOUNDARY}


# ----------------------------------------------------------------------------------------------- sources
def _fetch(path, url, sha):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as r:
            path.write_bytes(r.read())
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != sha:
        raise SystemExit(f"{path.name}: checksum mismatch (got {got[:16]}..., pinned {sha[:16]}...). "
                         "The upstream file changed; re-check before trusting this report.")
    return path.read_bytes()


def load_teprob():
    return _fetch(TEPROB, TEPROB_URL, TEPROB_SHA256).decode("latin-1")


def load_revised():
    """Return the revised code's header text, or None when it cannot be downloaded (cross-check then skipped)."""
    try:
        data = _fetch(REVISED_ZIP, REVISED_URL, REVISED_SHA256)
    except (OSError, ValueError):
        return None
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(REVISED_MEMBER).decode("latin-1")


# ----------------------------------------------------------------------------------------------- teprob.f parsing
def statements(text, subroutine="TEFUNC"):
    """Code statements of one subroutine, continuation lines joined, comments dropped, upper-cased."""
    out, inside = [], False
    for raw in text.splitlines():
        if raw[:1] in ("C", "c", "*"):
            continue
        line = raw.rstrip()
        if re.match(r"\s+SUBROUTINE\s+(\w+)", line, re.I):
            inside = re.match(r"\s+SUBROUTINE\s+(\w+)", line, re.I).group(1).upper() == subroutine
            continue
        if not inside or not line.strip():
            continue
        if len(line) > 5 and line[:5].strip() == "" and line[5] not in (" ", "\t") and out:
            out[-1] += line[6:].strip().upper()  # Fortran continuation (column 6)
        else:
            out.append(line[6:].strip().upper() if len(line) > 6 else line.strip().upper())
    return [re.sub(r"\s+", "", s) for s in out]


def header_names(text):
    """{('XMEAS'|'XMV'|'IDV', n): (name, stream-or-None)} and analyzer groups {first_xmeas: stream} from comments."""
    names, groups, group = {}, {}, None
    for raw in text.splitlines():
        if raw[:1] not in ("C", "c"):
            continue
        body = raw[1:].strip()
        m = re.match(r".+Analysis \(Stream (\d+)\)", body)
        if m:
            group = int(m.group(1))
            continue
        m = re.match(r"(XMEAS|XMV|IDV)\((\d+)\)\s+(.*)$", body)
        if not m:
            continue
        key = (m.group(1), int(m.group(2)))
        rest = m.group(3).replace("(Corrected Order)", "")
        stream = re.search(r"\(stream (\d+)\)", rest, re.I)
        name = re.split(r"\s{2,}|\(stream", rest, flags=re.I)[0].strip()
        if key not in names:
            names[key] = (name, int(stream.group(1)) if stream else None)
            if key[0] == "XMEAS" and key[1] >= 23 and group is not None:
                groups.setdefault(group, []).append(key[1])
    return names, groups


def terms(expr, var="FCM"):
    """Signed FCM(I,n) terms of a balance right-hand side: {n: +1/-1}."""
    out = {}
    for sign, n in re.findall(r"([+-]?)" + var + r"\(I,(\d+)\)", expr):
        out[int(n)] = -1 if sign == "-" else 1
    return out


def parse_source(text):
    st = statements(text)
    src = {"holdup_offset": {}, "balance": {}, "energy": {}, "alias": {}, "flow": {}, "xmeas": {}, "xcmp": {},
           "vpos": {}, "heat": {}, "circuit": {}, "idv_sets": {}, "lines": st}
    for s in st:
        m = re.match(r"UC[LV]([RSCV])\(I\)=YY\(I(?:\+(\d+))?\)$", s)
        if m:
            src["holdup_offset"][int(m.group(2) or 0)] = SUFFIX_ROLE[m.group(1)]
    for s in st:
        m = re.match(r"YP\(I(?:\+(\d+))?\)=(.*)$", s)
        if m and "FCM" in m.group(2):
            src["balance"][int(m.group(1) or 0)] = terms(m.group(2))
        m = re.match(r"YP\((\d+)\)=(.*)$", s)
        if m:
            src["energy"][int(m.group(1))] = m.group(2)
        m = re.match(r"FTM\((\d+)\)=FTM\((\d+)\)$", s)
        if m:
            src["alias"][int(m.group(1))] = int(m.group(2))
        m = re.match(r"XMEAS\((\d+)\)=(.*)$", s)
        if m:
            src["xmeas"][int(m.group(1))] = m.group(2)  # XMEAS(20) is assigned twice; both lines use CPDH
        m = re.match(r"XCMP\((\d+)\)=XST\(\d+,(\d+)\)", s)
        if m:
            src["xcmp"][int(m.group(1))] = int(m.group(2))
        m = re.match(r"(Q[A-Z]+)=(UA[A-Z]+)\*\(?(.*)$", s)
        if m:
            src["heat"][m.group(1)] = m.group(0)
        m = re.match(r"(TCW[A-Z])=.*IDV\((\d+)\)", s)
        if m:
            src["idv_sets"][m.group(1)] = int(m.group(2))
    # Stripper: FIN collects its feeds, then the split gives overhead and the liquid that drops to the sump.
    src["stripper_in"] = sorted({int(n) for s in st for n in re.findall(r"^FIN\(I\)=FIN\(I\)\+FCM\(I,(\d+)\)$", s)})
    src["stripper_split"] = sorted({int(n) for s in st for n in re.findall(r"^FCM\(I,(\d+)\)=.*FIN\(I\)", s)})
    # Flow lines: the last DLP / compressor ratio / valve position seen before FTM(n) is assigned drives FTM(n).
    dlp, clamped, ratio, last_vpos = None, False, None, None
    for s in st:
        m = re.match(r"DLP=(PT[A-Z]|760\.0)-(PT[A-Z]|760\.0)$", s)
        if m:
            dlp, clamped = (m.group(1), m.group(2)), False
            continue
        if s == "IF(DLP.LT.0.0)DLP=0.0":
            clamped = True
            continue
        m = re.match(r"PR=(PT[A-Z])/(PT[A-Z])$", s)
        if m:
            ratio = (m.group(2), m.group(1))  # suction / discharge: PR = discharge / suction
            continue
        m = re.search(r"VPOS\((\d+)\)", s)
        if m and s.startswith("FLMS"):
            last_vpos = int(m.group(1))
        m = re.match(r"FTM\((\d+)\)=(.*)$", s)
        if not m or m.group(1) in map(str, src["alias"]):
            continue
        n, rhs = int(m.group(1)), m.group(2)
        v = re.match(r"VPOS\((\d+)\)", rhs)
        if v:
            src["flow"][n] = {"driver": "valve", "xmv": int(v.group(1)), "line": s}
        elif "FLMS" in rhs and ratio and "CPDH" in " ".join(st) and n not in src["flow"] and dlp == (ratio[1], ratio[0]):
            src["flow"][n] = {"driver": "compressor", "from_p": ratio[0], "to_p": ratio[1], "xmv": last_vpos,
                              "line": f"PR={ratio[1]}/{ratio[0]} (compressor curve), spill-back VPOS({last_vpos})"}
            ratio = None
        elif "FLMS" in rhs and dlp:
            src["flow"][n] = {"driver": "pressure", "from_p": dlp[0], "to_p": dlp[1], "clamped": clamped,
                              "xmv": last_vpos if last_vpos and f"VPOS({last_vpos})" in " ".join(
                                  x for x in st if x.startswith("FLMS")) else None,
                              "line": f"DLP={dlp[0]}-{dlp[1]}" + ("; clamped at 0" if clamped else "")}
        last_vpos = None
    # The compressor curve shares the "PR=" line; record the work term on the compressor stream.
    src["compressor_floor"] = any(s == "IF(FLMS.LT.1.D-3)FLMS=1.D-3" for s in st)
    for s in st:
        m = re.match(r"(F[A-Z]+)=VPOS\((\d+)\)", s)
        if m:
            src["vpos"][int(m.group(2))] = m.group(1)
        m = re.match(r"(UA[A-Z])=VPOS\((\d+)\)", s)
        if m:
            src["vpos"][int(m.group(2))] = m.group(1)
        m = re.match(r"(AGSP)=\(VPOS\((\d+)\)", s)
        if m:
            src["vpos"][int(m.group(2))] = m.group(1)
    # Cooling-water circuits: YP(k) = (FW?*...(TCW?-TW?)-QU?*...)/HW?
    for k, expr in src["energy"].items():
        m = re.match(r"\((FW[A-Z])\*[\d.]+\*\((TCW[A-Z])-(TW[A-Z])\)-(QU[A-Z])", expr)
        if m:
            src["circuit"][m.group(3)] = {"flow": m.group(1), "inlet": m.group(2), "duty": m.group(4)}
    return src


# ----------------------------------------------------------------------------------------------- derived topology
def derive(src, names, groups):
    """Source-side facts: internal stream -> published number, endpoints, direction; tag -> what it acts on."""
    role_of_offset = src["holdup_offset"]
    energy_role = {k + 9: role for k, role in role_of_offset.items()}  # energy balance follows the 8 components
    ends = {}  # internal stream -> {"from": role, "to": role}
    for k, bal in src["balance"].items():
        role = role_of_offset[k]
        for n, sign in bal.items():
            ends.setdefault(n, {})["to" if sign > 0 else "from"] = role
    for n in src["stripper_in"]:
        ends.setdefault(n, {})["to"] = "stripper"
    for n in src["stripper_split"]:
        ends.setdefault(n, {})["from"] = "stripper"
    for a, b in src["alias"].items():  # FTM(7)=FTM(6): the reactor-inlet copy of the reactor feed
        ends.setdefault(b, {}).update({k: v for k, v in ends.pop(a, {}).items() if k == "to"})
    internal = {n for n, e in ends.items() if e.get("from") == e.get("to") == "stripper"}  # 12: inside the stripper
    for n in ends:
        ends[n].setdefault("from", BOUNDARY)
        ends[n].setdefault("to", BOUNDARY)

    # Published stream numbers from header comments + the XMEAS/VPOS lines that read the same internal stream.
    number = {}
    for (kind, idx), (_, stream) in names.items():
        if stream is None:
            continue
        if kind == "XMEAS":
            m = re.search(r"FTM\((\d+)\)", src["xmeas"].get(idx, ""))
        elif kind == "XMV":
            m = next((re.match(r"(\d+)", str(n)) for n, f in src["flow"].items() if f.get("xmv") == idx), None)
        else:
            continue
        if m:
            number.setdefault(int(m.group(1)), set()).add(stream)
    for stream, members in groups.items():
        k = src["xcmp"].get(members[0])
        if k:
            number.setdefault(src["alias"].get(k, k), set()).add(stream)
    conflicts = {n: v for n, v in number.items() if len(v) != 1}
    number = {n: next(iter(v)) for n, v in number.items() if len(v) == 1}

    # Inline equipment with no holdup: the compressor (work CPDH on the compressor-driven flow) and the condenser
    # (the heat term whose temperature is that of a stream entering the separator).
    inline = {}
    for n, f in src["flow"].items():
        if f["driver"] == "compressor":
            inline[n] = "compressor"
    for duty, line in src["heat"].items():
        m = re.search(r"TST\((\d+)\)", line)
        circuit = next((c for c in src["circuit"].values() if c["duty"] == duty), None)
        if m and circuit:
            n = int(m.group(1))
            booked = next((energy_role[k] for k, e in src["energy"].items() if duty in e and k in energy_role), None)
            if ends.get(n, {}).get("to") == booked:
                inline[n] = "condenser"
    return {"ends": ends, "number": number, "number_conflicts": conflicts, "internal": internal,
            "inline": inline, "energy_role": energy_role}


def flow_direction_ok(src, topo, n):
    """Direction evidence for internal stream n: the flow cannot reverse, and its sign matches the balances."""
    f = src["flow"].get(src["alias"].get(n, n)) or src["flow"].get(n)
    e = topo["ends"][n]
    if f is None:
        if n in src["stripper_split"]:
            return True, "computed split of the stripper feed (non-negative fractions SFR of FIN)"
        return False, "no flow line found"
    if f["driver"] == "valve":
        return True, f"FTM({n}) = VPOS({f['xmv']})*VRNG/100: valve-set, never negative"
    from_role, to_role = PRESSURE_ROLE.get(f["from_p"]), PRESSURE_ROLE.get(f["to_p"])
    if f["driver"] == "compressor":
        ok = (from_role, to_role) == (e["from"], e["to"]) and src["compressor_floor"]
        return ok, f"{f['line']}; flow floored at 1e-3, never reverses ({from_role} -> {to_role})"
    ok = f.get("clamped") and (from_role, to_role) == (e["from"], e["to"])
    return ok, f"{f['line']} ({from_role} -> {to_role})"


# ----------------------------------------------------------------------------------------------- the checks
def role_units(model):
    roles = {}
    for u in model["units"]:
        role = TYPE_ROLE.get(u.get("type"))
        if role:
            roles.setdefault(role, []).append(u["id"])
    return {r: ids[0] for r, ids in roles.items() if len(ids) == 1}


def base_number(stream_id):
    m = re.match(r"S(\d+)", stream_id)
    return int(m.group(1)) if m else None


def expected_segments(topo, unit_of):
    """Published stream number -> list of (from_unit, to_unit) segments the model may draw for it."""
    out = {}
    for n, e in topo["ends"].items():
        if n in topo["internal"] or n not in topo["number"]:
            continue
        a = unit_of.get(e["from"], BOUNDARY) if e["from"] != BOUNDARY else BOUNDARY
        b = unit_of.get(e["to"], BOUNDARY) if e["to"] != BOUNDARY else BOUNDARY
        mid = unit_of.get(topo["inline"].get(n))
        out[topo["number"][n]] = {"internal": n, "full": (a, b), "segments": [(a, mid), (mid, b)] if mid else [],
                                  "inline": mid}
    return out


def check_units(model, src, topo):
    rows = []
    offsets = {role: k for k, role in src["holdup_offset"].items()}
    for u in model["units"]:
        role = TYPE_ROLE.get(u.get("type"))
        if role in offsets:
            k = offsets[role]
            rows.append((u, "confirmed", f"holdup with states YY({k + 1})-YY({k + 9}) in TEFUNC "
                         f"(component balance YP(I+{k}), energy YP({k + 9}))", [], None))
        elif role == "compressor" and "compressor" in topo["inline"].values():
            n = next(k for k, v in topo["inline"].items() if v == "compressor")
            rows.append((u, "confirmed", f"compressor curve drives FTM({n}) from separator to header; work CPDH = "
                         "XMEAS(20)", ["no holdup in the simulator: flow and work are algebraic"], None))
        elif role == "condenser" and "condenser" in topo["inline"].values():
            n = next(k for k, v in topo["inline"].items() if v == "condenser")
            rows.append((u, "confirmed", f"heat term QUS = UAS*(TWS - TST({n})) cools the reactor effluent "
                         "FTM(%d); cooling-water flow XMV(11) 'Condenser Cooling Water Flow'" % n,
                         ["no holdup in the simulator: its duty is booked into the separator energy balance YP(18)"],
                         None))
        else:
            rows.append((u, "unresolvable", "no matching element found in teprob.f", [], None))
    return rows


def check_streams(model, src, topo, unit_of):
    exp = expected_segments(topo, unit_of)
    rows, by_number = [], {}
    for s in model["streams"]:
        by_number.setdefault(base_number(s["id"]), []).append(s)
    for s in model["streams"]:
        n_pub = base_number(s["id"])
        e = exp.get(n_pub)
        if e is None:
            rows.append((s, "unresolvable", f"no stream {n_pub} found in teprob.f", [], None))
            continue
        ok_dir, dir_ev = flow_direction_ok(src, topo, e["internal"])
        here, caveats = (s["from"], s["to"]), []
        allowed = [e["full"]] + e["segments"]
        evidence = (f"stream {n_pub} = internal FTM({e['internal']}): {e['full'][0]} -> {e['full'][1]}"
                    + (f" through {e['inline']}" if e["inline"] else "") + f"; direction: {dir_ev}")
        if not ok_dir:
            rows.append((s, "unresolvable", evidence + " (direction evidence incomplete)", [], None))
            continue
        if here in allowed:
            if e["inline"] and here != e["full"]:
                caveats.append(f"the split at {e['inline']} is the published flowsheet's drawing; the simulator "
                               f"computes one flow FTM({e['internal']}) for the whole of stream {n_pub}")
            rows.append((s, "confirmed", evidence, caveats, None))
            continue
        if (here[1], here[0]) in allowed:
            rows.append((s, "corrected", evidence + " (model had the direction reversed)", [],
                         {"from": here[1], "to": here[0]}))
            continue
        # One end wrong: repair it only when exactly one allowed segment shares the other end.
        fits = [seg for seg in allowed if seg[0] == here[0] or seg[1] == here[1]]
        siblings = len(by_number[n_pub])
        if siblings == 1 and not e["inline"]:
            fits = [e["full"]]
        if len(fits) == 1:
            fix = {k: v for k, v, old in zip(("from", "to"), fits[0], here) if v != old}
            rows.append((s, "corrected", evidence, [], fix))
        else:
            rows.append((s, "unresolvable", evidence + "; model endpoints match no unique segment", [], None))
    return rows


def name_roles(text):
    words = {w for w in re.findall(r"[a-z]+", (text or "").lower())}
    return {role for role, ws in ROLE_WORDS.items() if words & ws}


def code_roles(expr, src, topo):
    """What a measurement/valve expression physically acts on, from the variables it reads."""
    roles, notes, stream = set(), [], None
    m = re.search(r"FTM\((\d+)\)", expr)
    if m:
        stream = int(m.group(1))
        return roles, notes, stream
    for var in re.findall(r"[A-Z][A-Z0-9]*", expr):
        if re.match(r"(PT|TC|VL)([RSCV])$", var):
            roles.add(SUFFIX_ROLE[var[-1]])
            notes.append(f"{var} is the {SUFFIX_ROLE[var[-1]]} variable")
        elif var == "CPDH":
            roles.add("compressor")
            notes.append("CPDH is the compressor work term")
        elif var.startswith("QU") and var != "QUR" and var != "QUS":
            booked = next((topo["energy_role"][k] for k, e in src["energy"].items()
                           if var in e and k in topo["energy_role"]), None)
            if booked:
                roles.add(booked)
                notes.append(f"{var} enters the {booked} energy balance")
        elif var in src["circuit"] or var in ("FWR", "FWS", "AGSP") or var.startswith("UA"):
            roles |= circuit_roles(var, src, topo, notes)
    return roles, notes, stream


def circuit_roles(var, src, topo, notes):
    """Cooling-water / agitator / steam variables -> the unit whose heat term they act on."""
    duty = None
    if var in src["circuit"]:
        duty = src["circuit"][var]["duty"]
    for tw, c in src["circuit"].items():
        if var == c["flow"]:
            duty = c["duty"]
    if var == "AGSP" or var == "UAR":
        duty = "QUR"
    if var == "UAC":
        duty = "QUC"
    if not duty:
        return set()
    roles = set()
    line = src["heat"].get(duty, "")
    m = re.search(r"TST\((\d+)\)", line)
    booked = next((topo["energy_role"][k] for k, e in src["energy"].items() if duty in e and k in topo["energy_role"]),
                  None)
    if m and topo["inline"].get(int(m.group(1))) == "condenser":
        roles.add("condenser")
        notes.append(f"{duty} cools the reactor effluent FTM({m.group(1)}) (the condenser position)")
        if booked:
            notes.append(f"{duty} is booked into the {booked} energy balance")
    elif booked:
        roles.add(booked)
        notes.append(f"{duty} enters the {booked} energy balance")
    return roles


def circuit_names(var, src, names):
    """Documented names of everything on the same cooling-water circuit (valve, inlet disturbances)."""
    out = []
    c = src["circuit"].get(var)
    if not c:
        return out
    xmv = next((k for k, f in src["vpos"].items() if f == c["flow"]), None)
    if xmv and ("XMV", xmv) in names:
        out.append(f"XMV({xmv}) '{names[('XMV', xmv)][0]}'")
    idv = src["idv_sets"].get(c["inlet"])
    if idv and ("IDV", idv) in names:
        out.append(f"IDV({idv}) '{names[('IDV', idv)][0]}'")
    return out


def revised_xmeas_names(revised):
    """{n: name} from the revised code's 'Output 1 - Measured Values' table."""
    if not revised:
        return {}
    block = revised.split("Output 1 - Measured Values", 1)[-1].split("a d d i t i o n a l", 1)[0]
    out = {}
    for n, name in re.findall(r"^\s+(\d+)\s+\|([^|]+)\|", block, re.M):
        out.setdefault(int(n), name.strip())
    return out


def check_items(model, src, topo, names, unit_of, revised_names):
    exp = expected_segments(topo, unit_of)
    stream_by_number = {}
    for s in model["streams"]:
        stream_by_number.setdefault(base_number(s["id"]), []).append(s["id"])
    rows = []
    for item in model["instruments"] + model["final_elements"]:
        kind = "XMV" if "xmv" in item else "XMEAS"
        idx = item.get("xmv", item.get("xmeas"))
        caveats, notes, stream_internal = [], [], None
        doc = []
        if isinstance(idx, str):  # analyzer range
            first = int(idx.split("-")[0])
            k = src["xcmp"].get(first)
            stream_internal = src["alias"].get(k, k)
            notes.append(f"XCMP({first}...) = XST(i,{k})" + (f", the copy of FTM({stream_internal})"
                                                             if k != stream_internal else ""))
            roles = set()
        elif kind == "XMEAS":
            expr = src["xmeas"].get(idx, "")
            roles, notes, stream_internal = code_roles(expr, src, topo)
            notes = [f"XMEAS({idx}) = {expr[:40]}"] + notes
            if re.search(r"QU[A-Z]", expr):
                caveats.append("computed from the unit's heat duty; there is no steam stream in the source or the model")
            doc.append(("teprob.f", names.get(("XMEAS", idx), ("", None))[0]))
            if revised_names.get(idx):
                doc.append(("revised code", revised_names[idx]))
            var = re.match(r"(TW[A-Z])$", expr)
            if var:
                doc += [("teprob.f, same circuit", n) for n in circuit_names(var.group(1), src, names)]
        else:
            target = src["vpos"].get(idx)
            flow = next((n for n, f in src["flow"].items() if f.get("xmv") == idx), None)
            if flow is not None and src["flow"][flow]["driver"] in ("valve", "pressure"):
                stream_internal, roles = flow, set()
                notes.append(f"VPOS({idx}) sets FTM({flow})")
            elif flow is not None:  # compressor spill-back valve
                roles = {"compressor"}
                notes.append(f"VPOS({idx}) spills flow back around the compressor (reduces FTM({flow}))")
                caveats.append("the spill-back path around the compressor is not a stream in the model; the source "
                               "computes it only as a reduction of the net compressor flow")
            else:
                roles = circuit_roles(target, src, topo, notes) if target else set()
                notes.insert(0, f"VPOS({idx}) -> {target}")
            doc.append(("teprob.f", names.get(("XMV", idx), ("", None))[0]))
        stream_ok = None
        if stream_internal is not None:
            n_pub = topo["number"].get(stream_internal)
            e = exp.get(n_pub)
            if e:
                candidates = {u for seg in [e["full"]] + e["segments"] for u in seg if u not in (BOUNDARY, None)}
                model_stream_n = base_number(item["stream"]) if item.get("stream") else None
                stream_ok = model_stream_n == n_pub
                notes.append(f"stream {n_pub}: {e['full'][0]} -> {e['full'][1]}"
                             + (f" through {e['inline']}" if e["inline"] else ""))
                roles = candidates
                if e["inline"] and item.get("stream") and len(stream_by_number.get(n_pub, [])) > 1:
                    caveats.append(f"which segment of stream {n_pub} carries the tap is a model choice; the "
                                   f"simulator has one flow FTM({stream_internal})")
        # Documented-name votes, only for unit-level tags (stream tags are settled by the stream).
        votes = Counter()
        for _, text in doc:
            for r in name_roles(text):
                votes[r] += 1
        model_unit = item["unit"]
        model_role = next((r for r, u in unit_of.items() if u == model_unit), None)
        evidence = "; ".join(notes)
        if doc:
            evidence += "; documented as " + ", ".join(f"{src_} '{t}'" for src_, t in doc if not t.startswith(("XMV", "IDV"))) \
                + "".join(f", {t}" for _, t in doc if t.startswith(("XMV", "IDV")))
        fix, status = None, "confirmed"
        if stream_internal is not None:
            unit_ids = {unit_of.get(r, r) for r in roles}
            if stream_ok is False:
                status, evidence = "unresolvable", evidence + "; model stream disagrees with the source stream"
            elif model_unit in unit_ids:
                status = "confirmed"
            elif len(unit_ids) == 1:
                status, fix = "corrected", {"unit": next(iter(unit_ids))}
            else:
                status = "unresolvable"
        else:
            code_set = roles
            top = votes.most_common()
            majority = {r for r, c in top if c == top[0][1]} if top else set()
            agreed = code_set & majority if code_set and majority else (code_set or majority)
            if code_set and majority and not (code_set & majority):
                status = "unresolvable"
                caveats.append("the code computes it from the " + "/".join(sorted(code_set))
                               + " but the documented name says " + "/".join(sorted(majority)))
            elif len(agreed) == 1:
                role = next(iter(agreed))
                if role == model_role:
                    status = "confirmed"
                elif role in unit_of:
                    status, fix = "corrected", {"unit": unit_of[role]}
                else:
                    status = "unresolvable"
            elif model_role in agreed:
                status = "confirmed"
            else:
                status = "unresolvable"
            if status == "confirmed" and votes and len(votes) > 1:
                caveats.append("documented names disagree (" + ", ".join(f"{r} x{c}" for r, c in top)
                               + "); the code locus and the majority agree on " + "/".join(sorted(agreed)))
        rows.append((item, status, evidence, caveats, fix))
    return rows


# ----------------------------------------------------------------------------------------------- run
def cross_check_revised(src, topo, revised):
    """Second witness: the revised code's state list and stream-name list must agree with what teprob.f gave."""
    if not revised:
        return {"ran": False, "notes": ["revised TE code not available; cross-check skipped"]}
    notes, ok = [], True
    states = dict((int(n), d.strip()) for n, d in re.findall(r"^\s+(\d+)\s+\|(Holdup of component A[^|]+)\|", revised, re.M))
    spelled = {"reactor": "reactor", "separator": "seperator", "stripper": "stripper", "header": "header"}  # sic
    for offset, role in sorted(src["holdup_offset"].items()):
        d = states.get(offset + 1, "")
        agree = spelled[role] in d.lower()
        ok = ok and agree
        notes.append(f"state {offset + 1} ({role} in teprob.f): '{d}'" + ("" if agree else " MISMATCH"))
    block = revised.split("Output 4 - Concentration within the process units", 1)[-1].split("Version", 1)[0]
    listed = re.findall(r"^\s+\d+\s*-\s*\d+\s*\|([^|]+)\|", block, re.M)
    listed = [x.strip() for x in listed]
    nums = [int(m.group(1)) if (m := re.search(r"\(stream (\d+)\)", x)) else None for x in listed]
    # The list follows the internal stream order 1..13 without the reactor-inlet copy (7).
    order = [n for n in range(1, 14) if n != 7]
    if len(nums) != len(order):
        return {"ran": True, "ok": False, "inferred_numbers": {},
                "notes": [f"revised stream list has {len(nums)} entries, expected {len(order)}; not used"]}
    for internal, pub in zip(order, nums):
        known = topo["number"].get(internal)
        if pub is not None and known is not None and pub != known:
            ok = False
            notes.append(f"MISMATCH internal {internal}: teprob.f says stream {known}, revised list says {pub}")
    inferred = {internal: pub for internal, pub in zip(order, nums)
                if pub is not None and internal not in topo["number"]}
    notes.append("stream names: " + "; ".join(listed))
    return {"ran": True, "ok": ok, "inferred_numbers": inferred, "notes": notes}


def apply_numbers(topo, cross):
    """Streams 5 and 7 have no tagged flow in teprob.f; take their numbers from the revised list (else they stay unnumbered)."""
    for internal, pub in cross.get("inferred_numbers", {}).items():
        topo["number"].setdefault(internal, pub)


def main():
    write = "--write" in sys.argv
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    teprob, revised = load_teprob(), load_revised()
    result = full_run(model, teprob, revised)
    today = date.today().isoformat()
    report = render(result, today, revised is not None)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    if write:
        apply(model, result, today, revised is not None)
        MODEL.write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(totals(result)), "written" if write else "(report only)")
    for group in ("units", "streams", "items"):
        for el, status, evidence, caveats, fix in result[group]:
            if status != "confirmed" or fix:
                print(f"  {status}: {ident(el)} {fix or ''} :: {evidence[:160]}")


def full_run(model, teprob_text, revised_text):
    src = parse_source(teprob_text)
    names, groups = header_names(teprob_text)
    topo = derive(src, names, groups)
    cross = cross_check_revised(src, topo, revised_text)
    apply_numbers(topo, cross)
    unit_of = role_units(model)
    revised_names = revised_xmeas_names(revised_text)
    rows = {"units": check_units(model, src, topo),
            "streams": check_streams(model, src, topo, unit_of),
            "items": check_items(model, src, topo, names, unit_of, revised_names),
            "topology": topo, "cross_check": cross, "unit_of": unit_of}
    return keep_history(model, rows)


def keep_history(model, rows):
    """An element corrected on an earlier --write now matches; it stays 'corrected' so the history is not lost."""
    for group, key in (("units", "verification"), ("streams", "verification"), ("items", "topology_verification")):
        new = []
        for el, status, evidence, caveats, fix in rows[group]:
            prior = el.get(key, {}) if isinstance(el.get(key), dict) else {}
            if status == "confirmed" and prior.get("previous"):
                status = "corrected"
            new.append((el, status, evidence, caveats, fix))
        rows[group] = new
    return rows


def ident(el):
    return el.get("tag") or el.get("id")


def totals(result):
    c = Counter(status for g in ("units", "streams", "items") for _, status, *_ in result[g])
    return {s: c.get(s, 0) for s in ("confirmed", "corrected", "unresolvable")}


def references(revised_ok):
    refs = [f"{TEPROB_REF}: {TEPROB_URL} (sha256 {TEPROB_SHA256[:12]}...)"]
    if revised_ok:
        refs.append(f"{REVISED_REF}: {REVISED_URL} (sha256 {REVISED_SHA256[:12]}...); paper: Bathelt, A., Ricker, N. L. "
                    "& Jelali, M. (2015), Revision of the Tennessee Eastman process model, IFAC-PapersOnLine 48(8), "
                    "309-314, https://doi.org/10.1016/j.ifacol.2015.08.199")
    return refs


def render(result, today, revised_ok):
    t = totals(result)
    lines = [f"# TE model topology vs. simulator source ({today})", "",
             "Generated by `scripts/verify_te_topology.py`. Every row is read out of the simulator code, not typed by "
             "hand. Statuses: **confirmed** (source agrees), **corrected** (source clearly disagrees; model updated, "
             "old value kept), **unresolvable** (the source itself is split; kept and flagged for a process expert).",
             "", "Sources:", ""] + [f"- {r}" for r in references(revised_ok)] + [
             "", f"**Totals:** {t['confirmed']} confirmed · {t['corrected']} corrected · {t['unresolvable']} "
             f"unresolvable (of {sum(t.values())}: {len(result['units'])} units, {len(result['streams'])} streams, "
             f"{len(result['items'])} instruments and final elements)", ""]
    topo = result["topology"]
    lines += ["## Streams found in the code", "", "| Internal | Published stream | From | To | Inline element |",
              "|---|---|---|---|---|"]
    for n in sorted(topo["ends"]):
        e = topo["ends"][n]
        pub = topo["number"].get(n, "internal to stripper" if n in topo["internal"] else "?")
        lines.append(f"| FTM({n}) | {pub} | {e['from']} | {e['to']} | {topo['inline'].get(n, '')} |")
    for title, group in (("Units", "units"), ("Streams", "streams"), ("Instruments and final elements", "items")):
        lines += ["", f"## {title}", "", "| Element | Model | Result | Source evidence | Caveats |", "|---|---|---|---|---|"]
        for el, status, evidence, caveats, fix in result[group]:
            if group == "units":
                model_says = f"{el['name']} ({el.get('type')})"
            elif group == "streams":
                model_says = f"{el['from']} → {el['to']}"
            else:
                model_says = f"{el['unit']}" + (f" / {el['stream']}" if el.get("stream") else "")
            prior = (el.get("verification" if group != "items" else "topology_verification") or {}).get("previous")
            if fix:
                change = ", ".join(f"{k} {el.get(k)} → {v}" for k, v in fix.items())
            elif prior:
                change = "previously " + ", ".join(f"{k} {v}" for k, v in prior.items())
            else:
                change = ""
            res = f"**{status}**" + (f" ({change})" if change else "")
            lines.append(f"| {ident(el)} | {model_says} | {res} | {evidence.replace('|', '/')} | "
                         f"{'; '.join(caveats).replace('|', '/')} |")
    cross = result["cross_check"]
    lines += ["", "## Cross-check against the revised TE code", ""]
    if cross.get("ran"):
        lines.append("Agreement with teprob.f on every holdup and every stream number both name: **%s**."
                     % ("yes" if cross["ok"] else "NO"))
        lines.append("")
        lines += [f"- {n}" for n in cross["notes"]]
    else:
        lines += [f"- {n}" for n in cross["notes"]]
    lines += ["", "## What the simulator source cannot tell", "",
              "- Physical tap positions and the order of instruments along a line: the simulator has no pipe geometry.",
              "- Equipment sizes, elevations and pipe routes: not in the source.",
              "- Utility endpoints (cooling-water supply/return, steam, condensate): the source models only a "
              "cooling-water outlet temperature state per circuit and a steam heat term.", ""]
    return "\n".join(lines)


def apply(model, result, today, revised_ok):
    refs = [TEPROB_REF] + ([REVISED_REF] if revised_ok else [])
    for group, key in (("units", "verification"), ("streams", "verification"), ("items", "topology_verification")):
        for el, status, evidence, caveats, fix in result[group]:
            prior = el.get(key) if isinstance(el.get(key), dict) else {}
            v = {"status": status, "checked_against": refs, "checked_on": today, "evidence": evidence}
            if caveats:
                v["caveats"] = caveats
            if fix:
                v["previous"] = {k: el.get(k) for k in fix}
                el.update(fix)
            elif prior.get("previous"):
                v["previous"] = prior["previous"]
            if group == "streams" and status in ("confirmed", "corrected"):
                el["direction"] = "forward"
            if group == "items" and el.get("open_question") and status != "unresolvable":
                v["resolved_question"] = el.pop("open_question")
            el[key] = v
    t = totals(result)
    model["meta"]["topology_verification_note"] = (
        f"Units, streams, flow directions and tag ownership were checked {today} against the simulator source "
        f"(teprob.f, cross-checked with the revised TE code) by scripts/verify_te_topology.py: {t['confirmed']} "
        f"confirmed, {t['corrected']} corrected, {t['unresolvable']} unresolvable. Report: out/te_topology_check.md. "
        "Physical tap positions, sizes and pipe routes are not in the source and remain unverified.")


if __name__ == "__main__":
    main()
