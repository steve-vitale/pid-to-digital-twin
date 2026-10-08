"""Extracted P&ID sheets -> digital twin starter kit (asset hierarchy + Ignition + PI AF + SVG + review queue).

Input is a run folder of per-sheet extraction files (runs/<label>/<tool>/<sheet>.json, the format in
extraction/prompt_v2.md) plus the sheet images. Output is a twin package under out/twin/<label>/<tool>/:

    plant_model.json    asset hierarchy, streams, off-page pairing, per-item provenance (superset of the
                        data/te_process_model.json schema; scripts/generate.py consumes it)
    review_queue.csv    one row per item, least certain first
    ignition/tags.json  Ignition 8 tag import: UDT types + instances, OPC paths as placeholders
    pi/pi_builder_af.csv  PI Builder-style AF element hierarchy with attributes per instrument
    svg/sheet_<n>.svg   tag-bound overlay drawn from the extracted geometry

Nothing here is drawing-specific: every rule works from the extracted classes, tags, boxes and connections.
Everything the converter decides is recorded with the method it used, and every item starts as "unverified".

Usage:
    python scripts/build_twin.py --label round1-v2-named-fields --sheets 0,1,2,3,4,5          # every tool
    python scripts/build_twin.py --label runs/round1-v2-named-fields/claude/ --sheets 0,1,2,3,4,5
    python scripts/build_twin.py --label round1-v2-named-fields --sheets 0,1,2,3,4,5 --score  # + score_twin
"""
import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import generate as gen  # noqa: E402
import score_pid2graph as sc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
DEV_SHEETS = {str(i) for i in range(6)}  # docs/GOAL.md: development set. Holdouts are refused by default.

EQUIPMENT = {"tank", "pump"}
LINE = {"valve", "general"}
INSTRUMENT = "instrumentation"
OFFPAGE = "inlet/outlet"
ABBR = {"tank": "TK", "pump": "PU", "valve": "VL", "general": "GN", INSTRUMENT: "IN", OFFPAGE: "OP"}

# Confidence below this goes to the top of the review queue. Set on the development set only: Claude reports
# 0.3-0.7 for symbols it is unsure of; Codex and Gemini rarely go below 0.9. Model confidences are not
# calibrated against each other, so the same number means different things per model.
LOW_CONFIDENCE = 0.75

# "XXX", "MSCV-XXX", "TBD", "?" ... a tag the drawing leaves to be assigned later. Flagged, never filled in.
PLACEHOLDER = re.compile(r"(?<![A-Z0-9])(X{2,}|\?+|#{2,}|TBD|TBA|N/A)(?![A-Z0-9])", re.I)
# ISA-5.1 style instrument tag: function letters, optional separator, loop number with optional suffix.
ISA_TAG = re.compile(r"^([A-Z]{1,6})[\s-]*([0-9][0-9A-Z]*(?:-[0-9A-Z]+)?)?$")
# Equipment-style tag, SYSTEM-TYPE-NUMBER (e.g. "ABC-TK-101"). Used to promote a "general" symbol to equipment
# and to read a sheet's system code. A plant with a different equipment convention needs this pattern changed.
EQUIP_TAG = re.compile(r"^([A-Z]{2,6})-([A-Z]{1,6})-(\d+[A-Z]?)$")
# Off-page reference: "... PID 190-1", "RCS-PID-100-2", "PID-120-01", "P&ID 12-3".
DWG_REF = re.compile(r"(?:\b([A-Z]{2,6})[\s-]+)?P\s*&?\s*ID[\s.#:-]*(\d+)\s*-\s*(\d+)")
GRID_REF = re.compile(r"\(\s*([A-Z])\s*-\s*(\d+)\s*\)")
STOP = {"TO", "FROM", "THE", "OF", "AND", "&", "PID", "P&ID", "SYSTEM", "SYS"}

ISA_FIRST = {"A": "analysis", "B": "burner/combustion", "C": "conductivity", "D": "density", "E": "voltage",
             "F": "flow", "H": "hand", "I": "current", "J": "power", "K": "time", "L": "level",
             "M": "moisture", "P": "pressure", "Q": "quantity", "R": "radiation", "S": "speed",
             "T": "temperature", "V": "vibration", "W": "weight", "Y": "event/state", "Z": "position"}


# ---------------------------------------------------------------- small helpers

def clean(text):
    return re.sub(r"\s+", " ", str(text)).strip() if text not in (None, "") else None


def centre(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def dist(a, b):
    (ax, ay), (bx, by) = centre(a), centre(b)
    return math.hypot(ax - bx, ay - by)


def gap(a, b):
    """Edge-to-edge distance between two boxes (0 when they touch or overlap), 0-1000 units."""
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy)


def read_box(s):
    box = s.get("box")
    b = s.get("bbox")
    if box is None and isinstance(b, dict):
        box = [b.get("x_min"), b.get("y_min"), b.get("x_max"), b.get("y_max")]
    if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)):
        return None, False
    x0, y0, x1, y1 = (float(v) for v in box)
    swapped = x0 > x1 or y0 > y1
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], swapped


def isa_parts(tag):
    """('TE', '14084A') from 'TE 14084A'; letters only for placeholders ('AORV', None)."""
    if not tag:
        return None, None
    m = ISA_TAG.match(PLACEHOLDER.sub("", tag).strip(" -").upper())
    return (m.group(1), m.group(2)) if m else (None, None)


def tag_tokens(text):
    t = re.sub(r"(?<=[A-Z])-(?=[A-Z])", "", text.upper())  # BY-PASS -> BYPASS
    return {w for w in re.findall(r"[A-Z][A-Z0-9.&]*", t) if w not in STOP and len(w) > 1}


# ---------------------------------------------------------------- load

def resolve_run_dirs(label, tools):
    """--label may be a tool folder (runs/x/claude/) or a label (x or runs/x) holding tool folders."""
    p = Path(label)
    for cand in (p, ROOT / p, ROOT / "runs" / p):
        if cand.is_dir():
            p = cand
            break
    else:
        sys.exit(f"run folder not found for label {label!r}")
    if any(p.glob("*.json")) and not any(c.is_dir() for c in p.iterdir()):
        return p.parent.name, {p.name: p}
    dirs = {c.name: c for c in sorted(p.iterdir()) if c.is_dir() and (not tools or c.name in tools)}
    return p.name, dirs


def load_sheet(run_dir, sheet, images_dir):
    path = run_dir / f"{sheet}.json"
    r = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    pred = r.get("prediction") or {}
    img = images_dir / f"{sheet}.png"
    size = sc.png_size(img) if img.exists() else None
    items, dropped = [], []
    for s in pred.get("symbols", []):
        box, swapped = read_box(s)
        sid = s.get("id")
        if box is None or s.get("class") not in sc.SCORED or sid is None:
            dropped.append({"symbol": sid, "class": s.get("class"), "reason": "missing id, unknown class or bad box"})
            continue
        tag = clean(s.get("tag"))
        conf = s.get("confidence")
        items.append({"sheet": sheet, "symbol": str(sid), "class": s["class"], "tag": tag,
                      "box": [round(v, 1) for v in box], "box_was_swapped": swapped,
                      "confidence": float(conf) if isinstance(conf, (int, float)) else None,
                      "placeholder": bool(tag and PLACEHOLDER.search(tag))})
    links = [(str(c.get("from")), str(c.get("to"))) for c in pred.get("connections", [])]
    return {"sheet": sheet, "run_file": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
            "model": r.get("model"), "tool": r.get("tool"), "failed": not r.get("prediction"),
            "error": r.get("error") or r.get("parse_error"), "image": img.name, "image_size": size,
            "items": items, "links": links, "dropped": dropped}


# ---------------------------------------------------------------- sheet identity (system code, drawing number)

def parse_offpage(text):
    t = (text or "").upper()
    m = DWG_REF.search(t)
    ref = f"{int(m.group(2))}-{int(m.group(3))}" if m else None
    code = m.group(1) if m and m.group(1) else None
    g = GRID_REF.search(t)
    rest = t
    for pat in (DWG_REF, GRID_REF):
        rest = pat.sub(" ", rest)
    words = tag_tokens(rest)
    if code is None and m:  # "HPD PID 190-1" style handled above; also "COND PID 160-1 ..." -> word before PID
        before = re.findall(r"([A-Z]{2,6})\s*$", t[:m.start()])
        code = before[0] if before else None
    words.discard(code)
    return {"ref": ref, "code": code, "grid": f"{g.group(1)}-{g.group(2)}" if g else None,
            "words": sorted(words)}


def infer_sheet_identity(sheets, register):
    """Each sheet's system code and own drawing number. A sheet register (the plant's drawing index) wins;
    otherwise both are inferred, and marked so:
      system code  = most common SYSTEM prefix of the sheet's equipment-style tags (SYS-TYPE-NUM);
      drawing no.  = a drawing number that off-page connectors elsewhere in the set pair with one of the sheet's
                     system codes ("ACC PID 150-1"), that the sheet does not itself point to, scored by how many
                     of the sheet's equipment tags carry that code; ties stay unknown rather than guessed."""
    code_counts, self_refs, code_ref = {}, {}, Counter()
    for s, sh in sheets.items():
        code_counts[s] = Counter(EQUIP_TAG.match(i["tag"].upper()).group(1) for i in sh["items"]
                                 if i["tag"] and EQUIP_TAG.match(i["tag"].upper()) and i["role"] == "equipment")
        self_refs[s] = set()
        for i in sh["items"]:
            if i["class"] == OFFPAGE:
                p = parse_offpage(i["tag"])
                if p["ref"]:
                    self_refs[s].add(p["ref"])
                    if p["code"]:
                        code_ref[(p["code"], p["ref"])] += 1
    referenced_by = defaultdict(set)
    for s, refs in self_refs.items():
        for r in refs:
            referenced_by[r].add(s)

    ident, scored = {}, []
    for s in sheets:
        reg = register.get(s)
        codes = code_counts[s]
        code = codes.most_common(1)[0][0] if codes else None
        if codes and len(codes) > 1 and codes.most_common(2)[1][1] == codes.most_common(1)[0][1]:
            code_method = "inferred_tag_prefix_tie"
        else:
            code_method = "inferred_tag_prefix" if code else "none"
        ident[s] = {"system_code": code, "system_code_method": code_method, "system_codes_seen": dict(codes),
                    "system_name": None, "drawing_number": None, "drawing_number_method": "unknown",
                    "drawing_number_candidates": []}
        if reg:
            ident[s].update({"drawing_number": reg.get("drawing_number") or None,
                             "drawing_number_method": "sheet_register" if reg.get("drawing_number") else "unknown",
                             "system_name": reg.get("system_name") or None})
            if reg.get("system_code"):
                ident[s].update({"system_code": reg["system_code"], "system_code_method": "sheet_register"})
            if reg.get("drawing_number"):
                continue
        # Only the sheet's dominant code(s) count: a single stray tag from a neighbouring system (an exchanger
        # drawn on two sheets) must not name the sheet. Set on the development set, where it removed one wrong guess.
        top = max(codes.values(), default=0)
        cands, via = Counter(), {}
        for (c, r), _ in code_ref.items():
            if codes.get(c) == top and r not in self_refs[s]:
                cands[r] += codes[c]
                via[r] = c
        for r, v in cands.items():
            scored.append((-v, -len(referenced_by[r] - {s}), s, r))
        ident[s]["drawing_number_candidates"] = sorted(cands)
        ident[s]["_via"] = via
    # Greedy one-to-one: best-supported (sheet, number) first; a sheet whose top two candidates tie stays unknown.
    scored.sort()
    best = defaultdict(list)
    for v, o, s, r in scored:
        best[s].append((v, o, r))
    taken = {i["drawing_number"] for i in ident.values() if i["drawing_number"]}
    for v, o, s, r in scored:
        if ident[s]["drawing_number"] or r in taken:
            continue
        top = [c for c in best[s] if c[2] not in taken]
        if len(top) > 1 and top[0][:2] == top[1][:2]:
            ident[s]["drawing_number_method"] = "ambiguous"
            continue
        if (v, o, r) != top[0]:
            continue
        ident[s]["drawing_number"] = r
        ident[s]["drawing_number_method"] = "inferred_offpage_refs"
        if ident[s]["system_code_method"] == "inferred_tag_prefix_tie":  # the number settles which code it is
            ident[s].update({"system_code": ident[s]["_via"][r], "system_code_method": "inferred_tag_prefix+offpage_refs"})
        taken.add(r)
    for i in ident.values():
        i.pop("_via", None)
    return ident


# ---------------------------------------------------------------- the converter

def build(tool, run_dir, sheet_list, images_dir, register, label):
    sheets = {s: load_sheet(run_dir, s, images_dir) for s in sheet_list}

    # 1. role per symbol. A "general" symbol becomes equipment only when its tag follows the equipment pattern.
    for sh in sheets.values():
        for it in sh["items"]:
            if it["class"] in EQUIPMENT:
                it["role"], it["role_reason"] = "equipment", f"class {it['class']}"
            elif it["class"] == "general" and it["tag"] and EQUIP_TAG.match(it["tag"].upper()):
                it["role"], it["role_reason"] = "equipment", "class general, tag follows SYSTEM-TYPE-NUMBER pattern"
            elif it["class"] in LINE:
                it["role"], it["role_reason"] = "line_item", f"class {it['class']}"
            elif it["class"] == INSTRUMENT:
                it["role"], it["role_reason"] = "instrument", "class instrumentation"
            else:
                it["role"], it["role_reason"] = "offpage", "class inlet/outlet"

    ident = infer_sheet_identity(sheets, register)

    # 2. assets. Equipment with the same real tag on several sheets is one asset; everything else is per symbol.
    assets, app2asset, counters = {}, {}, Counter()
    equip_by_tag = {}
    for s, sh in sheets.items():
        seen_here = set()
        for it in sh["items"]:
            key = (s, it["symbol"])
            norm = re.sub(r"[\s_]+", "-", it["tag"].upper()) if it["tag"] else None
            mergeable = (it["role"] == "equipment" and norm and not it["placeholder"]
                         and re.search(r"\d", norm) and norm not in seen_here)
            if mergeable and norm in equip_by_tag:
                aid = equip_by_tag[norm]
                assets[aid]["appearances"].append(it)
                app2asset[key] = aid
                seen_here.add(norm)
                continue
            counters[(s, it["class"])] += 1
            aid = f"S{s}-{ABBR[it['class']]}{counters[(s, it['class'])]:03d}"
            assets[aid] = {"id": aid, "class": it["class"], "role": it["role"], "role_reason": it["role_reason"],
                           "tag": it["tag"], "placeholder_tag": it["placeholder"], "appearances": [it]}
            app2asset[key] = aid
            if mergeable:
                equip_by_tag[norm] = aid
                seen_here.add(norm)

    # 3. per-sheet graph over appearances; streams over assets.
    adj = defaultdict(set)
    streams, dropped_links, seen_pairs = [], [], set()
    by_key = {(s, it["symbol"]): it for s, sh in sheets.items() for it in sh["items"]}
    for s, sh in sheets.items():
        for a, b in sh["links"]:
            ka, kb = (s, a), (s, b)
            if ka not in by_key or kb not in by_key:
                dropped_links.append({"sheet": s, "from": a, "to": b, "reason": "endpoint is not a kept symbol"})
                continue
            if a == b:
                dropped_links.append({"sheet": s, "from": a, "to": b, "reason": "self-link"})
                continue
            adj[ka].add(kb)
            adj[kb].add(ka)
            pair = (s, frozenset((a, b)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            ia, ib = by_key[ka], by_key[kb]
            confs = [c for c in (ia["confidence"], ib["confidence"]) if c is not None]
            streams.append({"id": f"L{s}-{len([x for x in streams if x['sheet'] == s]) + 1:03d}",
                            "name": f"{app2asset[ka]} - {app2asset[kb]}", "kind": "extracted_link",
                            "from": app2asset[ka], "to": app2asset[kb], "sheet": s,
                            "from_symbol": a, "to_symbol": b, "direction": "unknown",
                            "confidence": min(confs) if confs else None,
                            "verification": {"status": "unverified"}})

    def role(k):
        return by_key[k]["role"]

    def owner(start):
        """Nearest equipment through process links (line items only), fewest hops, then closest."""
        if role(start) == "equipment":
            return app2asset[start], 0, "self"
        seen, frontier, hops = {start}, [start], 0
        while frontier:
            hops += 1
            found, nxt = [], []
            for cur in frontier:
                for n in adj[cur]:
                    if n in seen:
                        continue
                    seen.add(n)
                    if role(n) == "equipment":
                        found.append(n)
                    elif role(n) == "line_item":
                        nxt.append(n)
            if found:
                best = min(found, key=lambda n: dist(by_key[n]["box"], by_key[start]["box"]))
                return app2asset[best], hops, "connection_path"
            frontier = nxt
        return None, None, "no_connection_path"

    # 4. instrument parent: linked neighbour > via instrument chain > nearest symbol by geometry.
    parents = {}
    for s, sh in sheets.items():
        for it in sh["items"]:
            if it["role"] != "instrument":
                continue
            k = (s, it["symbol"])
            direct = [n for n in adj[k] if role(n) != "instrument"]
            method, cand, extra = None, None, {}
            if direct:
                cand = min(direct, key=lambda n: dist(by_key[n]["box"], it["box"]))
                method, extra = "linked", {"linked_candidates": len(direct)}
            else:
                seen, q = {k}, deque([k])
                chain = []
                while q and not chain:
                    cur = q.popleft()
                    for n in adj[cur]:
                        if n in seen:
                            continue
                        seen.add(n)
                        (chain if role(n) != "instrument" else q).append(n)
                if chain:
                    cand = min(chain, key=lambda n: dist(by_key[n]["box"], it["box"]))
                    method = "via_instrument_chain"
                else:
                    others = [(s, o["symbol"]) for o in sh["items"] if o["role"] != "instrument"]
                    if others:
                        cand = min(others, key=lambda n: gap(by_key[n]["box"], it["box"]))
                        method = "geometry_nearest"
                        extra = {"gap_0_1000": round(gap(by_key[cand]["box"], it["box"]), 1)}
            # Second opinion by position alone. On the development set, when the two agree the parent was right
            # about 9 times in 10 (Claude, Codex); when they disagree, about 3 in 10. Disagreement goes to review.
            others = [(s, o["symbol"]) for o in sh["items"] if o["role"] != "instrument"]
            near = min(others, key=lambda n: gap(by_key[n]["box"], it["box"])) if others else None
            extra["position_nearest"] = app2asset[near] if near else None
            extra["parent_agrees_with_position"] = bool(cand and near and cand == near)
            parents[k] = (cand, method or "no_candidate", extra)

    # 5. off-page connectors and cross-sheet pairing.
    connectors = []
    for s, sh in sheets.items():
        for it in sh["items"]:
            if it["role"] == "offpage":
                p = parse_offpage(it["tag"])
                connectors.append({"id": app2asset[(s, it["symbol"])], "sheet": s, "text": it["tag"], **p,
                                   "pair": None, "pair_method": None, "status": None})
    own = {s: ident[s]["drawing_number"] for s in sheets}
    by_number = defaultdict(list)
    for s, n in own.items():
        if n:
            by_number[n].append(s)
    cand_pairs = []
    for x in connectors:
        targets = [b for b in by_number.get(x["ref"], []) if b != x["sheet"]] if x["ref"] else []
        for y in connectors:
            if y["sheet"] not in targets:
                continue
            a_own = own[x["sheet"]]
            if a_own and y["ref"] == a_own:
                method = "reciprocal_drawing_refs"
            elif not a_own and y["ref"] not in by_number and y["code"] and \
                    y["code"] == ident[x["sheet"]]["system_code"]:
                method = "one_way_ref_plus_system_code"
            else:
                continue
            wx, wy = set(x["words"]), set(y["words"])
            sim = len(wx & wy) / len(wx | wy) if wx | wy else 0.0
            cand_pairs.append((-sim, method != "reciprocal_drawing_refs", x["id"], y["id"], method, sim))
    cand_pairs.sort()
    cmap = {c["id"]: c for c in connectors}
    options = Counter()
    for _, _, xi, yi, _, _ in cand_pairs:
        options[xi] += 1
    pairs = []
    for neg, _, xi, yi, method, sim in cand_pairs:
        x, y = cmap[xi], cmap[yi]
        if x["pair"] or y["pair"] or xi == yi:
            continue
        x["pair"], y["pair"] = yi, xi
        x["pair_method"] = y["pair_method"] = method
        x["pair_sim"] = y["pair_sim"] = round(sim, 2)
        pairs.append({"id": f"XP-{len(pairs) + 1:03d}", "a": xi, "b": yi, "sheet_a": x["sheet"],
                      "sheet_b": y["sheet"], "text_a": x["text"], "text_b": y["text"], "method": method,
                      "description_similarity": round(sim, 2),
                      "alternatives": max(options[xi], options[yi]) - 1,
                      "verification": {"status": "unverified"}})
        streams.append({"id": pairs[-1]["id"], "name": f"off-page {x['text']} <-> {y['text']}",
                        "kind": "cross_sheet", "from": xi, "to": yi, "sheet": None, "direction": "unknown",
                        "confidence": None, "verification": {"status": "unverified"}})
    for c in connectors:
        if c["pair"]:
            c["status"] = "paired"
        elif not c["ref"]:
            c["status"] = "unpaired: no drawing number read from the text"
        elif c["ref"] in by_number and c["sheet"] not in by_number[c["ref"]]:
            c["status"] = "unpaired: target sheet is in this set but no matching connector was found"
        elif c["ref"] in by_number:
            c["status"] = "unpaired: points to its own sheet number"
        else:
            c["status"] = "unpaired: target drawing is not in this sheet set"

    # 6. assemble the model (TE schema superset: meta / units / streams / instruments / final_elements).
    site = {"id": "SITE", "name": f"Site (from {label})"}
    systems = []
    for s in sheets:
        i = ident[s]
        if i["system_name"]:
            name = i["system_name"]
        elif i["system_code"] and (i["drawing_number"] or i["system_code_method"] == "sheet_register"):
            name = f"{i['system_code']} (sheet {s})"
        elif i["system_code"]:  # only a tag-prefix majority: say it is a guess
            name = f"Sheet {s} (mostly {i['system_code']} tags)"
        else:
            name = f"Sheet {s}"
        systems.append({"id": f"SYS-{s}", "sheet": s, "name": name, **i, "image": sheets[s]["image"],
                        "image_size_px": sheets[s]["image_size"], "source_run": sheets[s]["run_file"],
                        "model": sheets[s]["model"], "extraction_failed": sheets[s]["failed"],
                        "extraction_error": sheets[s]["error"]})
    code_to_sheet = {}
    for sy in systems:
        if sy["system_code"] and sy["system_code"] not in code_to_sheet:
            code_to_sheet[sy["system_code"]] = sy["sheet"]

    def prov(it):
        return {"sheet": it["sheet"], "symbol": it["symbol"], "class": it["class"], "box_0_1000": it["box"],
                "tag_as_extracted": it["tag"], "confidence": it["confidence"],
                "source_run": sheets[it["sheet"]]["run_file"], "tool": tool, "model": sheets[it["sheet"]]["model"],
                **({"box_axes_were_swapped": True} if it["box_was_swapped"] else {})}

    units, instruments, line_items, offpage = [], [], [], []
    for aid, a in assets.items():
        first = a["appearances"][0]
        apps = [prov(x) for x in a["appearances"]]
        conf = min((x["confidence"] for x in a["appearances"] if x["confidence"] is not None), default=None)
        base = {"id": aid, "tag": a["tag"], "tag_status": ("placeholder" if a["placeholder_tag"] else
                                                          "as_extracted" if a["tag"] else "missing"),
                "class": a["class"], "confidence": conf, "provenance": apps,
                "verification": {"status": "unverified"}}
        if a["role"] == "equipment":
            m = EQUIP_TAG.match((a["tag"] or "").upper())
            home = code_to_sheet.get(m.group(1)) if m else None
            home = home if home in [x["sheet"] for x in a["appearances"]] else first["sheet"]
            units.append({**base, "name": a["tag"] or f"untagged {a['class']}", "type": a["class"],
                          "role_reason": a["role_reason"], "system": f"SYS-{home}",
                          "layout": {"x": round(centre(first["box"])[0], 1), "y": round(centre(first["box"])[1], 1),
                                     "sheet": first["sheet"], "frame": "sheet_0_1000"},
                          "source": f"{tool} extraction, sheet {first['sheet']} symbol {first['symbol']}",
                          "sheets": sorted({x["sheet"] for x in a["appearances"]}, key=int)})
        elif a["role"] == "instrument":
            k = (first["sheet"], first["symbol"])
            cand, method, extra = parents[k]
            pid = app2asset[cand] if cand else None
            unit, hops, umethod = owner(cand) if cand else (None, None, "no_parent")
            letters, loop = isa_parts(a["tag"])
            # MOV / AOV / SOV / AORV are common plant shorthand for operated valves, not ISA measured variables
            # (ISA would read MOV's "M" as moisture). Don't guess a variable for them.
            operated_valve = bool(letters and re.search(r"OR?V$", letters))
            kind = ("operated valve" if operated_valve else "final element (valve)" if letters and
                    letters.endswith("V") else "measurement / control" if letters else None)
            instruments.append({**base, "unit": unit, "unit_method": umethod, "unit_hops": hops,
                                "parent": pid, "parent_method": method,
                                "parent_source": {"sheet": cand[0], "symbol": cand[1]} if cand else None, **extra,
                                "system": f"SYS-{first['sheet']}", "isa_letters": letters, "loop": loop,
                                "instrument_kind": kind,
                                "variable": ISA_FIRST.get(letters[0]) if letters and not operated_valve else None,
                                "variable_method": "ISA-5.1 first letter" if letters and not operated_valve else None,
                                "uom": "", "description": a["tag"] or "untagged instrument",
                                "stream": None})
        elif a["role"] == "line_item":
            unit, hops, umethod = owner((first["sheet"], first["symbol"]))
            line_items.append({**base, "unit": unit, "unit_method": umethod, "unit_hops": hops,
                               "system": f"SYS-{first['sheet']}",
                               "description": a["tag"] or f"untagged {a['class']}"})
        else:
            c = cmap[aid]
            unit, hops, umethod = owner((first["sheet"], first["symbol"]))
            offpage.append({**base, "system": f"SYS-{first['sheet']}", "text": c["text"], "refers_to_drawing":
                            c["ref"], "refers_to_system_code": c["code"], "grid_ref_on_target": c["grid"],
                            "pair": c["pair"], "pair_method": c["pair_method"], "pair_status": c["status"],
                            "pair_description_similarity": c.get("pair_sim"),
                            "unit": unit, "unit_method": umethod})

    # duplicate tags among non-merged items (instruments, valves): flag, never rename
    tag_count = Counter(re.sub(r"\s+", " ", x["tag"].upper()) for x in instruments + line_items
                        if x["tag"] and x["tag_status"] == "as_extracted")
    for x in instruments + line_items:
        x["duplicate_tag"] = bool(x["tag"] and tag_count[re.sub(r"\s+", " ", x["tag"].upper())] > 1)

    model = {
        "meta": {
            "model_id": f"twin-{label}-{tool}", "model_kind": "extracted_twin", "schema_version": "twin-1",
            "title": f"Digital twin starter kit: {label} / {tool}",
            "source_document": f"Extraction run {label}/{tool}, sheets {', '.join(sheet_list)}",
            "extraction_method": f"{tool} ({', '.join(sorted({str(sh['model']) for sh in sheets.values()}))}), "
                                 "prompt per run file; converted by scripts/build_twin.py",
            "tag_convention": "Tags are the extracted text, unchanged except whitespace. Asset ids (S<sheet>-<class>"
                              "<n>) are converter keys, NOT plant tags. Placeholder tags (XXX, TBD) are flagged.",
            "verification_note": "Every item is unverified until a person checks it in review_queue.csv.",
            "low_confidence_threshold": LOW_CONFIDENCE,
            "superset_of": "data/te_process_model.json (meta/units/streams/instruments/final_elements)",
        },
        "site": site, "systems": systems,
        "units": units, "streams": streams, "instruments": instruments, "final_elements": [],
        "line_items": line_items, "offpage_connectors": offpage, "offpage_pairs": pairs,
        "dropped": {"symbols": [d | {"sheet": s} for s, sh in sheets.items() for d in sh["dropped"]],
                    "connections": dropped_links},
    }
    model["hierarchy"] = hierarchy(model)
    model["summary"] = summary(model)
    return model


def hierarchy(model):
    """Site -> System -> Equipment -> line items -> instruments (instruments hang off whatever they attach to)."""
    node = {}
    for u in model["units"]:
        node[u["id"]] = {"id": u["id"], "kind": "equipment", "tag": u["tag"], "class": u["class"], "children": []}
    for x in model["line_items"]:
        node[x["id"]] = {"id": x["id"], "kind": "line_item", "tag": x["tag"], "class": x["class"], "children": []}
    for x in model["offpage_connectors"]:
        node[x["id"]] = {"id": x["id"], "kind": "offpage", "tag": x["tag"], "class": x["class"], "children": []}
    for x in model["instruments"]:
        node[x["id"]] = {"id": x["id"], "kind": "instrument", "tag": x["tag"], "class": x["class"],
                         "attach": x["parent_method"], "children": []}
    systems = {s["id"]: {"id": s["id"], "kind": "system", "name": s["name"], "sheet": s["sheet"],
                         "children": [], "unassigned": [], "offpage_connectors": []} for s in model["systems"]}
    for u in model["units"]:
        systems[u["system"]]["children"].append(node[u["id"]])
    for x in model["line_items"]:
        (node[x["unit"]]["children"] if x["unit"] else systems[x["system"]]["unassigned"]).append(node[x["id"]])
    for x in model["offpage_connectors"]:
        systems[x["system"]]["offpage_connectors"].append(node[x["id"]])
    for x in model["instruments"]:
        (node[x["parent"]]["children"] if x["parent"] else systems[x["system"]]["unassigned"]).append(node[x["id"]])
    return {"id": model["site"]["id"], "kind": "site", "name": model["site"]["name"],
            "children": list(systems.values())}


def summary(model):
    inst = model["instruments"]
    oc = model["offpage_connectors"]
    return {
        "systems": len(model["systems"]), "equipment": len(model["units"]),
        "equipment_on_several_sheets": sum(1 for u in model["units"] if len(u["sheets"]) > 1),
        "instruments": len(inst), "line_items": len(model["line_items"]), "offpage_connectors": len(oc),
        "streams_extracted": sum(1 for s in model["streams"] if s["kind"] == "extracted_link"),
        "instrument_parent_method": dict(Counter(i["parent_method"] for i in inst)),
        "instruments_without_equipment": sum(1 for i in inst if not i["unit"]),
        "line_items_without_equipment": sum(1 for x in model["line_items"] if not x["unit"]),
        "placeholder_tags": sum(1 for x in model["units"] + inst + model["line_items"] + oc
                                if x["tag_status"] == "placeholder"),
        "offpage_pairs": len(model["offpage_pairs"]),
        "offpage_status": dict(Counter(x["pair_status"] for x in oc)),
        "sheet_drawing_numbers": {s["sheet"]: [s["drawing_number"], s["drawing_number_method"]]
                                  for s in model["systems"]},
    }


def load_register(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(line for line in f if not line.startswith("#"))]
    return {str(r["sheet"]).strip(): {k: (v or "").strip() for k, v in r.items()} for r in rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True, help="run label (runs/<label>) or one tool folder")
    ap.add_argument("--sheets", default="0,1,2,3,4,5")
    ap.add_argument("--tools", default="", help="comma list; default every tool folder under the label")
    ap.add_argument("--images", default=str(DATA), help="folder holding <sheet>.png")
    ap.add_argument("--sheet-register", default="", help="optional CSV: sheet,drawing_number,system_code,system_name")
    ap.add_argument("--out", default="", help="default out/twin/<label>/<tool>")
    ap.add_argument("--svg-background", action="store_true", help="link the sheet image under the SVG overlay")
    ap.add_argument("--score", action="store_true", help="also run scripts/score_twin.py on the result")
    ap.add_argument("--holdout-ok", action="store_true", help="allow sheets outside the development set 0-5")
    args = ap.parse_args()

    sheet_list = [s.strip() for s in args.sheets.split(",") if s.strip()]
    outside = [s for s in sheet_list if s not in DEV_SHEETS]
    if outside and not args.holdout_ok:
        sys.exit(f"refusing sheets {outside}: outside the development set 0-5 (docs/GOAL.md). "
                 "Holdouts are scored once per finished method; pass --holdout-ok only for that run.")
    tools = {t.strip() for t in args.tools.split(",") if t.strip()}
    label, run_dirs = resolve_run_dirs(args.label, tools)
    register = load_register(args.sheet_register)
    built = []
    for tool, run_dir in run_dirs.items():
        model = build(tool, run_dir, sheet_list, Path(args.images), register, label)
        __import__("confidence").annotate_model(model, run_dir, sheet_list, Path(args.images))  # round-3 risk tiers
        out = Path(args.out) / tool if args.out and len(run_dirs) > 1 else Path(args.out) if args.out \
            else ROOT / "out" / "twin" / label / tool
        out.mkdir(parents=True, exist_ok=True)
        (out / "plant_model.json").write_text(json.dumps(model, indent=1), encoding="utf-8")
        written = gen.export_twin(model, out, images_dir=Path(args.images) if args.svg_background else None)
        s = model["summary"]
        print(f"[{tool}] {s['equipment']} equipment, {s['instruments']} instruments, {s['line_items']} line items, "
              f"{s['offpage_connectors']} off-page ({s['offpage_pairs']} pairs), {s['streams_extracted']} links "
              f"-> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
        print(f"        wrote plant_model.json, {', '.join(written)}")
        built.append(out)
    if args.score:
        import score_twin
        score_twin.main_for(built, sheet_list, Path(args.images), holdout_ok=args.holdout_ok)


if __name__ == "__main__":
    main()
