"""Operator orientation tour: ordered stops, plain-language script, captions, SRT, optional synthetic voiceover.

Everything numeric (normal bands, published limits, fault-6 timings, counts, values) is computed here from data
files: the twin contract, out/ignition/normal_bands.json, the published setpoints in build_meta.json and the
recorded TE fault-6 replay. The connecting prose, and the one-sentence description of what each unit does
(ROLE_TEXT), were written by Claude and have NOT been reviewed by an operator; the captions say so.

Hazard emphasis has two parts, kept apart on purpose:
  * from data: a unit carrying a published Critical (shutdown) limit is marked "shutdown limits"; the unit whose tag
    leaves its band first in the recorded fault is "first warning";
  * from the prototype citation file (data/hazard_citations_prototype.json): one public incident per stop, shown as
    "Why this matters". That file is a keyword-heuristic shortlist, not a hazard analysis.

Voiceover is optional: Windows System.Speech (SAPI, offline, built into Windows) through PowerShell, one WAV per
segment, concatenated with silence to the video timeline, and muxed with ffmpeg only if an ffmpeg executable is
found. The voice is synthetic and every caption says so. Stdlib only.
"""
import json
import math
import re
import shutil
import subprocess
import wave
from pathlib import Path

AUTHORSHIP = "Script by Claude from the data files, not operator-reviewed."
VOICE_NOTE = "Narration: synthetic voice (Windows SAPI), not a person."
LEGEND = "grey in band | amber outside band | red published alarm | black not connected"
DISCLAIMER = "PROTOTYPE: placeholder geometry, source-checked topology (not operations-reviewed), recorded replay (not live)."

# Legacy one-line roles (429d7a7 tour); the redesign reads purposes through load_purposes() instead.
# What each unit does, in one or two sentences. Claude-written from the published TE description (Downs & Vogel
# 1993); no numbers here on purpose: numbers come from data.
ROLE_TEXT = {
    "feed": "Fresh gaseous feeds A, D and E enter the plant here through flow control valves, and join the recycle "
            "gas and the stripper overhead on the way to the reactor.",
    "reactor": "The reactor turns the gaseous feeds into the liquid products G and H. The reactions give off heat, "
               "which cooling water removes.",
    "condenser": "The condenser cools the reactor product with cooling water, so most of the product condenses "
                 "before the separator.",
    "separator": "The separator splits the cooled stream: vapour goes to the compressor to be recycled, liquid goes "
                 "to the stripper.",
    "compressor": "The compressor sends separator vapour back to the feed as recycle. Part of it is purged so inert "
                  "and by-product gases do not build up.",
    "stripper": "The stripper uses the A and C feed and steam to strip leftover reactants out of the liquid. The "
                "products G and H leave the plant from its base.",
}

SPOKEN_UNITS = [("kPa g", "kilopascals gauge"), ("degC", "degrees Celsius"), ("°C", "degrees Celsius"), ("kscmh", "thousand standard cubic "
                "metres per hour"), ("kg/h", "kilograms per hour"), ("m3/h", "cubic metres per hour"),
                ("mol%", "mole percent"), ("kW", "kilowatts")]


def fmt(v):
    """Readable number with about four significant figures, never scientific notation."""
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "n/a"
    if float(v).is_integer() and abs(v) >= 100:
        return f"{int(v):,}"
    a = abs(v)
    digits = 0 if a >= 1000 else 1 if a >= 100 else 2 if a >= 1 else 3 if a >= 0.01 else 4
    return f"{v:,.{digits}f}"


def spoken(text):
    """Caption text -> text for the synthetic voice (units spelled out, tag dashes dropped)."""
    out = text
    for short, longer in SPOKEN_UNITS:
        out = re.sub(r"(?<![A-Za-z])" + re.escape(short) + r"(?![A-Za-z])", longer, out)
    out = re.sub(r"\b([A-Z]{1,2})-(\d{3})\b", lambda m: " ".join(m.group(1)) + " " + m.group(2), out)
    out = re.sub(r"(\d)%", r"\1 percent", out).replace("%", " percent")
    out = out.replace("+", "plus ").replace(" -", " minus ")
    return out


def wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def classify(value, band, alarms):
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return "unknown"
    if any(value > a["setpointA"] for a in alarms):
        return "alarm"
    if band and not band["lo"] <= value <= band["hi"]:
        return "outside_band"
    return "normal"


def fault_profile(tags, replay, bands, alarms, fault_start, alarm_sample):
    """Per tag: first sample at/after the fault start that is not normal, minutes after the fault, the value and
    state at the alarm sample. Tags without a replay column are left out (not inferred)."""
    if not replay:
        return {}
    rows, cols = replay["rows"], replay["columns"]
    out = {}
    for tag in tags:
        col = cols.get(tag)
        if col is None:
            continue
        first = None
        for s in range(fault_start, min(alarm_sample, len(rows) - 1) + 1):
            if col < len(rows[s]) and classify(rows[s][col], bands.get(tag), alarms.get(tag, [])) != "normal":
                first = s
                break
        at = rows[alarm_sample][col] if alarm_sample < len(rows) and col < len(rows[alarm_sample]) else None
        out[tag] = {"first_off_sample": first, "minutes_after_fault": None if first is None else (first - fault_start) * 3,
                    "value_at_alarm": at, "state_at_alarm": classify(at, bands.get(tag), alarms.get(tag, []))}
    return out


def first_alarm_sample(replay, alarms, fault_start, tag="PT-107"):
    if not replay or tag not in replay["columns"]:
        return None
    col = replay["columns"][tag]
    for s in range(fault_start, len(replay["rows"])):
        if classify(replay["rows"][s][col], None, alarms.get(tag, [])) == "alarm":
            return s
    return None


def emphasis(scene, alarms, profile):
    """Data-backed emphasis. Returns {unit: [{"style", "reason", "label"}]}."""
    by_unit = {}
    for m in scene["markers"]:
        crit = [a for a in alarms.get(m["tag"], []) if a.get("priority") == "Critical"]
        for a in crit:
            by_unit.setdefault(m["unit"], {}).setdefault("crit", []).append((m["tag"], a["setpointA"], m["uom"]))
    out = {}
    for unit, d in by_unit.items():
        limits = ", ".join(f"{t} > {fmt(v)} {u}" for t, v, u in d["crit"])
        out.setdefault(unit, []).append({"style": "consequence", "reason": "published shutdown limits: " + limits,
                                         "label": "Published shutdown limits\n" + limits})
    firsts = [(p["first_off_sample"], t) for t, p in profile.items() if p["first_off_sample"] is not None]
    if firsts:
        sample, tag = min(firsts)
        unit = next(m["unit"] for m in scene["markers"] if m["tag"] == tag)
        same = sorted(t for s, t in firsts if s == sample)
        mins = profile[tag]["minutes_after_fault"]
        out.setdefault(unit, []).append({"style": "first_warning", "reason": f"first band flag in fault 6: {', '.join(same)} at +{mins} min",
                                         "sentence": f"{' and '.join(same)} left {'their bands' if len(same) > 1 else 'its band'} "
                                                     + ("at the fault start." if mins == 0 else f"{mins} minutes after the fault started."),
                                         "label": f"First warning in fault 6\n{', '.join(same)} left band at +{mins} min"})
    return out


BADGE = "Prototype · placeholder geometry · recorded replay"
FULL_DISCLAIMER = ("Prototype. A published benchmark process, the Tennessee Eastman process, stands in for a plant. "
                   "Shapes, sizes, positions and pipe routes are placeholders; the stream connections are "
                   "checked against the simulator code but not reviewed by an operator; tag colours come from a recorded replay, not a live plant. The script "
                   "was written by Claude from the repository's data files and has not been reviewed by an operator.")
SERVICE_LABELS = {"gas_feed": "gas feed", "reactor_effluent": "reactor effluent", "liquid_product": "liquid product",
                  "recycle": "recycle", "purge": "purge", "cooling_water": "cooling water (inferred)",
                  "steam": "steam (inferred)"}
STATE_ROWS = [("normal", "in normal band"), ("outside_band", "outside normal band"),
              ("alarm", "above high alarm"), ("not_connected", "not connected")]
MAX_STOP_WORDS = 70


def disp_uom(u):
    return (u or "").replace("degC", "°C")


def _short(m, layout_labels):
    """Short name: the 2D screens' label, else the model description without its parenthetical. Analyzer markers
    carry only the first component's channel, and say which."""
    name = layout_labels.get(m["tag"]) or re.sub(r"\s*\(.*?\)", "", m.get("description") or "")
    comp = re.search(r"\(components ([A-Z])", m.get("description") or "")
    return (f"{name}, component {comp.group(1)}" if comp else name).rstrip(" ?")


def split_limits(tag, alarms):
    """Operating alarms (what the Ignition screens alarm on) vs published shutdown limits (priority Critical)."""
    op = [a["setpointA"] for a in alarms.get(tag, []) if a.get("priority") != "Critical"]
    sd = [a["setpointA"] for a in alarms.get(tag, []) if a.get("priority") == "Critical"]
    return op, sd


def tag_body(m, layout_labels, state=None, value=None, band=None, alarms=(), show_shutdown=False):
    """One-line tag pill. Normal stills: name plus the operating (high) alarm. Fault stills: the recorded value,
    the operating alarm and, only there, the published shutdown limit."""
    alarms = alarms if isinstance(alarms, dict) else {m["tag"]: list(alarms or [])}
    op, sd = split_limits(m["tag"], alarms)
    if not m["connected"]:
        return f"{m['tag']}  {_short(m, layout_labels)} · not connected"
    with_value = value is not None and (show_shutdown or state in ("outside_band", "alarm"))
    parts = [f"{m['tag']}  {fmt(value)} {disp_uom(m['uom'])}" if with_value else f"{m['tag']}  {_short(m, layout_labels)}"]
    if op:
        parts.append(f"high alarm {fmt(max(op))}" + ("" if with_value else f" {disp_uom(m['uom'])}"))
    if show_shutdown and sd:
        parts.append(f"shutdown {fmt(min(sd))}" + ("" if with_value else f" {disp_uom(m['uom'])}"))
    if with_value and band and state == "outside_band" and not op:
        parts.append(f"band {fmt(band['lo'])}–{fmt(band['hi'])}")
    if m.get("disputed"):
        parts.append("owner disputed")
    return " · ".join(parts)


def natural_list(items):
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def flow_sentences(unit, model, kinds, short=False):
    """'It takes ... and sends ...' from the contract's streams (the model's source-checked topology)."""
    names = {u["id"]: u["name"].lower() for u in model["units"]}

    def stream_name(s, other_kind=None):
        n = s["name"]
        if other_kind == "feed":
            n = re.sub(r" to feed$", "", n)
        return n[0].lower() + n[1:] if not re.match(r"^[A-Z] ", n) else n

    ins = [s for s in model["streams"] if s["to"] == unit]
    outs = [s for s in model["streams"] if s["from"] == unit]
    fresh = [s for s in ins if s["from"] == "BL"]
    parts_in = []
    if fresh:
        letters = [re.match(r"^(.*) feed$", s["name"]) for s in fresh]
        if all(letters):
            ids = natural_list([x.group(1) for x in letters])
            parts_in.append(f"fresh {ids} feed{'s' if len(fresh) > 1 else ''} from outside the plant")
        else:
            parts_in.append(natural_list([stream_name(s) for s in fresh]) + " from outside the plant")
    for s in ins:
        if s["from"] != "BL":
            parts_in.append(f"the {stream_name(s)} from " + (s["from"] if short else f"the {names[s['from']]}"))
    parts_out = []
    for s in outs:
        dest = "out of the plant" if s["to"] == "BL" else "to " + (s["to"] if short else f"the {names[s['to']]}")
        nm = stream_name(s, kinds.get(s["to"]))
        parts_out.append(f"{'the ' if not nm.startswith(('fresh',)) else ''}{nm} {dest}")
    if short:
        text = f"Takes {natural_list(parts_in) or 'nothing'}; sends {natural_list(parts_out) or 'nothing'}."
        if len(text) <= 140:
            return text
        src = list(dict.fromkeys("outside the plant" if s["from"] == "BL" else s["from"] for s in ins))
        dst = list(dict.fromkeys("out of the plant" if s["to"] == "BL" else s["to"] for s in outs))
        return f"Receives from {natural_list(src)}; sends to {natural_list(dst)}.".replace("to out of", "out of")
    return f"It takes {natural_list(parts_in)}, and sends {natural_list(parts_out)}."


def _lower_first(text):
    keep = len(text) > 1 and (text[1].isupper() or re.match(r"^[A-Z]( |$)", text))
    return text if keep else text[:1].lower() + text[1:]


def tag_sentence(m, bands, alarms, layout_labels, lead="Watch"):
    op, _ = split_limits(m["tag"], alarms)
    b = bands[m["tag"]]
    name = ", ".join(_lower_first(w) if i == 0 else w for i, w in enumerate(_short(m, layout_labels).split(", ")))
    s = (f"{lead} {m['tag']}, {name}: normally {fmt(b['lo'])} to {fmt(b['hi'])} "
         f"{disp_uom(m['uom'])}")
    return s + (f", with a high alarm at {fmt(max(op))}." if op else ".")


def stop_script(i, n, stop, scene, model, kind, bands, alarms, profile, cites, layout_labels, purposes):
    unit = stop["unit"]
    kinds = {e["id"]: e["kind"] for e in scene["equipment"]}
    marker = {m["tag"]: m for m in scene["markers"]}
    eq = next(e for e in scene["equipment"] if e["id"] == unit)
    key = [marker[t] for t in eq.get("key_tags", [])]
    purpose = (purposes.get("kinds", {}).get(kind) or {})
    p1 = f"Stop {i}: the {stop['name'].lower()}, {unit}. {purpose.get('purpose', '')}".strip()
    p2 = flow_sentences(unit, model, kinds)
    tags = [tag_sentence(m, bands, alarms, layout_labels, "Watch" if k == 0 else "Also")
            for k, m in enumerate([m for m in key[:3] if m["tag"] in bands])]
    mine = {t: profile[t] for t in [m["tag"] for m in scene["markers"] if m["unit"] == unit] if t in profile}
    off = sorted((p["first_off_sample"], t) for t, p in mine.items() if p["first_off_sample"] is not None)
    if off:
        t = off[0][1]
        mins = mine[t]["minutes_after_fault"]
        p4 = (f"In fault 6, its first sign was {t}, " +
              ("right at the fault start." if mins == 0 else f"{mins} minutes after the fault started."))
    elif mine:
        p4 = "In fault 6, its tags stayed in band until the reactor pressure alarm."
    else:
        p4 = ""
    c = cites[0] if cites else None
    p5 = f"The card shows a public example: {c['title']}, {c['agency']}" + (f", {c['year']}." if c.get("year") else ".") if c else ""
    priority = [("p1", p1), ("t0", tags[0] if tags else ""), ("p4", p4), ("t1", tags[1] if len(tags) > 1 else ""),
                ("p2", p2), ("p5", p5), ("t2", tags[2] if len(tags) > 2 else "")]
    chosen, words = set(), 0
    for k, text in priority:
        w = len(text.split())
        if text and (words + w <= MAX_STOP_WORDS or k == "p1"):
            chosen.add(k)
            words += w
    order = ["p1", "p2", "t0", "t1", "t2", "p4", "p5"]   # spoken order; priority above decides what fits
    narration = " ".join(t for k, t in zip(order, [p1, p2] + (tags + ["", "", ""])[:3] + [p4, p5]) if k in chosen and t)
    return {"unit": unit, "kind": kind, "tags": [m["tag"] for m in scene["markers"] if m["unit"] == unit],
            "key_tags": [m["tag"] for m in key], "narration": narration, "words": len(narration.split()),
            "purpose": purpose, "citation": c, "caption_flow": flow_sentences(unit, model, kinds, short=True)}


def why_card(c):
    if not c:
        return None
    when = f", {c['year']}" if c.get("year") else ""
    return "\n".join(["Why this matters"] + wrap(c["caption"], 44) + [f"Source: {c['agency']}{when} · prototype match"])


def purpose_card(p):
    if not p:
        return None
    return "\n".join(["Purpose"] + wrap(p["purpose"], 46) + wrap(p["function"], 46))


def load_purposes(cards_path, purposes_path):
    """The tour's cards (function line, highlights, inferred items per equipment kind, data/te_tour_cards.json)
    joined with the purpose sentence and citations of the same unit from data/te_unit_purposes.json, the only
    source of purpose text (each sentence cites teprob.f lines; scripts/test_te_topology.py checks them)."""
    cards = json.loads(Path(cards_path).read_text(encoding="utf-8"))
    units = json.loads(Path(purposes_path).read_text(encoding="utf-8"))["units"]
    kinds = {}
    for kind, card in cards["kinds"].items():
        if "purpose" in card:
            raise ValueError(f"{cards_path}: {kind} carries its own purpose text; purposes come only from {purposes_path}")
        unit = units[card["unit"]]
        kinds[kind] = {**card, "purpose": unit["purpose"], "citations": unit["citations"]}
    return {**{k: v for k, v in cards.items() if k != "kinds"}, "kinds": kinds}


def build_tour(scene, model, layout, bands, alarms, replay, hazards, fault_start, sample_index, emphasis_on=True,
               purposes=None):
    """Pure: scene + data -> stills (shots), narrated segments and extra labels (LOTO mockup)."""
    purposes = purposes or {"kinds": {}}
    kinds = {e["id"]: e["kind"] for e in scene["equipment"]}
    labels = layout.get("labels", {})
    states = scene["replay_states"]
    alarm_sample = states[sample_index["alarm"]]["sample"] if states else None
    connected = [m["tag"] for m in scene["markers"] if m["connected"]]
    profile = fault_profile(connected, replay, bands, alarms, fault_start, alarm_sample) if states else {}
    emph = emphasis(scene, alarms, profile) if emphasis_on else {}
    n = len(scene["tour"])
    stops = [stop_script(i, n, s, scene, model, kinds[s["unit"]], bands, alarms, profile,
                         (hazards.get("kinds", {}).get(kinds[s["unit"]]) or {}).get("citations", []), labels, purposes)
             for i, s in enumerate(scene["tour"], 1)]
    marker = {m["tag"]: m for m in scene["markers"]}
    unit_ids = [e["id"] for e in scene["equipment"]]
    overview = {"camera": scene["overview"]["camera"], "target": scene["overview"]["target"]}
    services = sorted({p["service"] for p in scene["pipes"]} | {u["service"].split("_supply")[0].split("_return")[0]
                                                               for u in scene.get("utilities", [])},
                      key=lambda s: list(SERVICE_LABELS).index(s) if s in SERVICE_LABELS else 99)

    def bodies(idx, ids, show_shutdown=False):
        st = states[idx] if states else {"states": {}, "values": {}}
        out = {}
        for lid in ids:
            if lid.startswith("tag:"):
                m = marker[lid[4:]]
                out[lid] = tag_body(m, labels, st["states"].get(m["tag"]), st.get("values", {}).get(m["tag"]),
                                    bands.get(m["tag"]), alarms, show_shutdown)
        return out

    def badge():
        return {"id": "overlay:badge", "kind": "badge", "corner": "top_right", "text": BADGE}

    def caption(title, sentence):
        return {"id": "overlay:caption", "kind": "caption", "text": title + "\n" + sentence}

    def state_legend():
        return {"id": "overlay:legend", "kind": "legend", "corner": "bottom_right", "title": "Tag markers (replay)",
                "rows": [{"text": t, "swatch": "state:" + s} for s, t in STATE_ROWS]}

    def service_legend():
        return {"id": "overlay:legend", "kind": "legend", "corner": "bottom_right", "title": "Process flow by service",
                "rows": [{"text": SERVICE_LABELS.get(s, s), "swatch": "service:" + s} for s in services]}

    def shot(name, view, title, sentence, **kw):
        base = {"name": name, "camera": view["camera"], "target": view["target"],
                "camera_candidates": view.get("camera_candidates"), "state_index": sample_index["normal"],
                "focus": None, "visible": [], "bodies": {}, "markers": [], "utilities": [], "chevrons": True,
                "highlight": [], "level_bands": [], "overlays": [badge()], "caption": title + "\n" + sentence}
        base.update(kw)
        base["overlays"] = base["overlays"] + [caption(title, sentence)]
        return base

    shots = [shot("00_overview_normal", overview, f"Overview: {scene['title']}",
                  "A published benchmark process standing in for a plant; the tour follows the material in flow order.",
                  visible=["unit:" + u for u in unit_ids])]
    for i, (stop, sc) in enumerate(zip(scene["tour"], stops), 1):
        unit = stop["unit"]
        hl = sc["purpose"].get("highlight", [])
        lvl = [t for t in sc["tags"] if t.startswith("LT-") and t in bands] if "level" in hl else []
        ids = ["unit:" + unit] + ["tag:" + t for t in sc["key_tags"]]
        ov = [badge()]
        if purpose_card(sc["purpose"]):
            ov.append({"id": "overlay:purpose", "kind": "card", "corner": "top_left", "text": purpose_card(sc["purpose"])})
        if why_card(sc["citation"]):
            ov.append({"id": "overlay:why", "kind": "card", "corner": "top_right_below", "text": why_card(sc["citation"])})
        shots.append(shot(f"{i:02d}_{unit.lower()}_normal", stop, f"Stop {i} of {n}: {unit} {stop['name']}",
                          sc["caption_flow"], focus=unit, visible=ids, bodies=bodies(sample_index["normal"], ids),
                          markers=sc["key_tags"], utilities="focus", highlight=hl, level_bands=lvl, overlays=ov))
        everything = ["unit:" + unit] + ["tag:" + t for t in sc["tags"]]
        shots.append(shot(f"{i:02d}b_{unit.lower()}_all_tags", stop, f"Stop {i} of {n}: {unit} {stop['name']}, all tags",
                          f"All {len(sc['tags'])} tags the contract assigns to {unit}; the narrated stop shows only "
                          f"{len(sc['key_tags'])}.", focus=unit, visible=everything,
                          bodies=bodies(sample_index["normal"], everything), markers=sc["tags"], utilities="focus",
                          optional=True))
    counts = {}
    if states:
        for key in ("normal", "early", "alarm"):
            st = states[sample_index[key]]["states"]
            counts[key] = {s: sorted(t for t, v in st.items() if v == s) for s in ("outside_band", "alarm", "normal")}
        early, al = counts["early"], counts["alarm"]
        all_tags = [m["tag"] for m in scene["markers"]]
        shots.append(shot("20_overview_fault_early", overview, "Fault 6 (loss of A feed): +%d min" %
                          states[sample_index["early"]]["minutes_after_fault"],
                          f"{len(early['outside_band'])} tags have left their normal band (amber); none is in alarm yet.",
                          state_index=sample_index["early"], visible=["unit:" + u for u in unit_ids], markers=all_tags,
                          overlays=[badge(), state_legend()]))
        pi = states[sample_index["alarm"]].get("values", {}).get("PT-107")
        op, _ = split_limits("PT-107", alarms)
        alarm_ids = ["tag:" + t for t in sorted(set(al["alarm"]) | {t for t in ("PT-107", "TT-109") if t in marker})]
        shots.append(shot("21_overview_fault_alarm", overview, "Fault 6 (loss of A feed): +%d min" %
                          states[sample_index["alarm"]]["minutes_after_fault"],
                          f"PT-107 reaches {fmt(pi)} kPa g, above its {fmt(max(op))} kPa g high alarm; "
                          f"{len(al['outside_band'])} tags are outside their normal band.",
                          state_index=sample_index["alarm"], visible=["unit:" + u for u in unit_ids] + alarm_ids,
                          bodies=bodies(sample_index["alarm"], alarm_ids, show_shutdown=True), markers=all_tags,
                          overlays=[badge(), state_legend()]))
        reactor = next((k for k, s in enumerate(scene["tour"]) if kinds[s["unit"]] == "reactor"), None)
        if reactor is not None:
            stop, sc = scene["tour"][reactor], stops[reactor]
            ids = ["unit:" + stop["unit"]] + ["tag:" + t for t in sc["key_tags"]]
            shots.append(shot("22_reactor_fault_alarm", stop, f"Fault 6 at the reactor: sample {alarm_sample}",
                              "Values at the first sample above the PT-107 high alarm, with the published shutdown limits.",
                              focus=stop["unit"], visible=ids, bodies=bodies(sample_index["alarm"], ids, True),
                              markers=sc["key_tags"], state_index=sample_index["alarm"], utilities="focus",
                              overlays=[badge(), state_legend()]))
    shots.append(shot("30_flow_legend", overview, "Process flow (source-checked topology)",
                      "Feeds and recycle meet at the feed system, react in R-101, condense, separate; gas recycles "
                      "through K-101 and liquid is stripped to product.", visible=["unit:" + u for u in unit_ids],
                      utilities="all", overlays=[badge(), service_legend()], flow_strong=True))
    loto, loto_labels = loto_mockup(scene, model)
    shots.append(shot("40_loto_mockup", overview, "Lockout/tagout view: design mockup only",
                      "Numbered tags mark isolation points inferred from the seed model; this is not a LOTO procedure.",
                      visible=["unit:" + u for u in unit_ids] + [l["id"] for l in loto_labels], utilities="all",
                      chevrons=False, ghost_all=True,
                      overlays=[badge(), {"id": "overlay:loto", "kind": "card", "corner": "top_left", "text": "\n".join(
                          ["Design mockup, not a procedure"] + wrap(
                              "Isolation points are inferred from the TE seed model (marked *). A real lockout/tagout "
                              "procedure comes from the site's energy-control program (OSHA 1910.147), its verified "
                              "P&IDs and an authorized person.", 46))}], optional=True))

    segs = []

    def seg(sid, base, narration, title, sentence):
        b = dict(base)
        b["overlays"] = [o for o in base["overlays"] if o["id"] != "overlay:caption"] + [caption(title, sentence)]
        segs.append(dict(b, id=sid, narration=narration, caption=title + "\n" + sentence))

    seg("intro", shots[0], f"This is an orientation tour of the {scene['title']}. " + FULL_DISCLAIMER +
        f" The camera visits the {n} units in the order the material flows.",
        f"Orientation tour: {scene['title']}",
        "Prototype: placeholder geometry, source-checked topology, recorded replay; script by Claude, not operator-reviewed.")
    stop_shots = [s for s in shots if re.match(r"^\d\d_[a-z]-\d+_normal$", s["name"])]
    for i, (sc, sh) in enumerate(zip(stops, stop_shots), 1):
        seg(f"stop{i}", sh, sc["narration"], sh["caption"].split("\n")[0], sh["caption"].split("\n")[1])
    if states and counts:
        by = {s["name"]: s for s in shots}
        e, al = counts["early"], counts["alarm"]
        n_conn = len(connected)
        first4 = sorted(e["outside_band"], key=lambda t: (profile.get(t, {}).get("first_off_sample") or 10 ** 9, t))[:4]
        seg("fault_intro", dict(shots[0], markers=[m["tag"] for m in scene["markers"]]),
            f"Now a recorded fault: fault 6, the loss of the A feed. Thirty minutes before it starts, "
            f"{len(counts['normal']['normal'])} of the {n_conn} connected tags are inside their normal bands.",
            "Fault 6 (loss of A feed): before the fault", "All connected tags are inside their normal bands.")
        seg("fault_early", by["20_overview_fault_early"],
            f"Two hours in, {len(e['outside_band'])} tags have left their band, shown amber. The earliest were "
            f"{natural_list(first4)}. Nothing has reached an alarm yet.",
            *by["20_overview_fault_early"]["caption"].split("\n"))
        op, sd = split_limits("PT-107", alarms)
        seg("fault_alarm", by["21_overview_fault_alarm"],
            f"About five hours in, reactor pressure PT-107 crosses {fmt(max(op))} kilopascals: that is the high alarm "
            f"the operator screens use. The {fmt(min(sd))} figure on its tag is different: it is the published limit "
            f"at which the simulator shuts down.", *by["21_overview_fault_alarm"]["caption"].split("\n"))
        if "22_reactor_fault_alarm" in by:
            first_flag = min((p["minutes_after_fault"] for p in profile.values() if p["minutes_after_fault"] is not None), default=None)
            lead = states[sample_index["alarm"]]["minutes_after_fault"] - first_flag if first_flag is not None else None
            seg("fault_reactor", by["22_reactor_fault_alarm"],
                f"The first amber flag came {lead} minutes before this alarm. That lead time is what the normal-band "
                "display is for.", *by["22_reactor_fault_alarm"]["caption"].split("\n"))
    seg("outro", shots[0], "End of tour. Before anyone trains on this, an operator must review the script, and the "
        "placeholder shapes and positions must be replaced with the plant's real geometry and instrument locations.",
        "End of tour", "Operator review and real plant geometry come before any training use.")
    return {"shots": shots, "segments": segs, "stops": stops, "emphasis": emph, "fault_profile": profile,
            "authorship": AUTHORSHIP, "voice_note": VOICE_NOTE, "extra_labels": loto_labels, "loto": loto}


def loto_mockup(scene, model):
    """Inferred isolation points for the LOTO design mockup. NOT a procedure: no sequence is claimed to be correct."""
    points = []
    for b in scene["boundaries"]:
        s = next(x for x in model["streams"] if x["id"] == b["stream"])
        points.append(("bl:" + b["stream"], f"{s['name']}: battery-limit block valve*",
                       [b["position"][0], b["position"][1], 1.0]))
    for e in scene["equipment"]:
        if e["shape"] == "compressor":
            points.append(("motor:" + e["id"], f"{e['id']} motor: electrical*",
                           [e["position"][0] + e["dims"][2] * 0.4, e["position"][1], 0.3 + e["dims"][0] * 0.8]))
        if e.get("agitator"):
            points.append(("agitator:" + e["id"], f"{e['id']} agitator motor: electrical*",
                           [e["position"][0], e["position"][1], e["extent"][2]]))
    for u in scene.get("utilities", []):
        if u["role"] in ("supply", "steam"):
            what = "cooling water in/out" if u["role"] == "supply" else "steam"
            points.append(("utility:" + u["id"], f"{u['unit']} {what}*", u["post"][:2] + [0.9]))
    labels, out = [], []
    for k, (pid, text, anchor) in enumerate(points, 1):
        out.append({"n": k, "point": pid, "text": text, "anchor": anchor, "basis": "inferred from the seed model"})
        labels.append({"id": f"loto:{k}", "kind": "loto", "body": f"{k}  {text}", "anchor": anchor})
    return out, labels


# ------------------------------------------------------------------ timing, SRT, voice, mux

def estimate_seconds(text, wpm=150):
    return max(2.5, len(text.split()) / wpm * 60.0)


def timeline(segments, durations, move=1.5, tail=0.6):
    """Segment i: camera move (except the first), then a hold for its narration plus a short tail."""
    t, out = 0.0, []
    for i, (s, d) in enumerate(zip(segments, durations)):
        start = t
        hold = t + (move if i else 0.0)
        end = hold + d + tail
        out.append(dict(s, start=round(start, 3), hold=round(hold, 3), end=round(end, 3), speech=round(d, 3)))
        t = end
    return out


def _ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def balanced_lines(text, max_chars):
    """One line if it fits; otherwise two lines split at the word boundary that best balances them (no orphans)."""
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    best = min(range(1, len(words)), key=lambda k: max(len(" ".join(words[:k])), len(" ".join(words[k:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]


def cue_chunks(sentence, limit):
    """Split a long sentence at clause boundaries (, ; :) into pieces of at most `limit` characters."""
    if len(sentence) <= limit:
        return [sentence]
    parts = re.split(r"(?<=[,;:])\s+", sentence)
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + 1 + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        out.append(cur)
    fixed = []
    for c in out:  # a single clause still too long: fall back to word wrap at the limit
        fixed += wrap(c, limit) if len(c) > limit else [c]
    return fixed


def srt(timed, max_chars=84):
    """Subtitle cues: each segment's narration split into sentences, timed by character share of its speech."""
    cues = []
    for seg in timed:
        sentences = [s for s in re.split(r"(?<=[.;])\s+", seg["narration"]) if s]
        total = sum(len(s) for s in sentences) or 1
        t = seg["hold"]
        for s in sentences:
            dur = seg["speech"] * len(s) / total
            for chunk in cue_chunks(s, 2 * max_chars):
                share = dur * len(chunk) / max(1, len(s))
                cues.append((t, t + share, "\n".join(balanced_lines(chunk, max_chars))))
                t += share
    if cues:  # the synthetic-voice notice rides on the first cue, so no two cues overlap
        a, b, text = cues[0]
        cues[0] = (a, b, "[" + VOICE_NOTE.rstrip(".") + "]\n" + text)
    out = []
    for k, (a, b, text) in enumerate(cues, 1):
        out.append(f"{k}\n{_ts(a)} --> {_ts(max(b, a + 0.4))}\n{text}\n")
    return "\n".join(out)


PS_SAPI = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.Rate = 0
Get-Content -LiteralPath $args[0] -Encoding UTF8 | ForEach-Object {
  $parts = $_ -split "`t", 2
  $s.SetOutputToWaveFile($parts[0], $fmt)
  $s.Speak($parts[1])
}
$s.SetOutputToNull()
Write-Output ("VOICE " + $s.Voice.Name)
$s.Dispose()
"""


def synthesize(segments, out_dir):
    """One WAV per segment with Windows SAPI. Returns (paths, durations, voice name). Raises if unavailable."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = out_dir / "jobs.tsv"
    paths = [out_dir / f"{i:02d}_{s['id']}.wav" for i, s in enumerate(segments)]
    jobs.write_text("\n".join(f"{p.resolve()}\t{spoken(s['narration'])}" for p, s in zip(paths, segments)) + "\n",
                    encoding="utf-8")
    script = out_dir / "sapi.ps1"
    script.write_text(PS_SAPI, encoding="utf-8")
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        raise RuntimeError("no PowerShell: synthetic voice unavailable")
    res = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(jobs)],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("SAPI failed: " + res.stderr[-500:])
    voice = next((l[6:] for l in res.stdout.splitlines() if l.startswith("VOICE ")), "unknown")
    return paths, [wav_seconds(p) for p in paths], voice


def wav_seconds(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def concat_wavs(paths, timed, out_path):
    """Place each segment's WAV at its hold time on one track, silence elsewhere."""
    with wave.open(str(paths[0]), "rb") as w:
        params = w.getparams()
    rate, width, ch = params.framerate, params.sampwidth, params.nchannels
    total = int(math.ceil(timed[-1]["end"] * rate)) + rate
    buf = bytearray(total * width * ch)
    for p, seg in zip(paths, timed):
        with wave.open(str(p), "rb") as w:
            if (w.getframerate(), w.getsampwidth(), w.getnchannels()) != (rate, width, ch):
                raise ValueError("narration WAVs differ in format")
            data = w.readframes(w.getnframes())
        at = int(seg["hold"] * rate) * width * ch
        buf[at:at + len(data)] = data[:max(0, len(buf) - at)]
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(bytes(buf))
    return out_path


def find_ffmpeg():
    return shutil.which("ffmpeg")


def mux(video, audio, subtitles, out_path, ffmpeg=None):
    """Video + synthetic narration + soft subtitles. Returns the command run, or None if no ffmpeg."""
    ffmpeg = ffmpeg or find_ffmpeg()
    if not ffmpeg:
        return None
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio), "-i", str(subtitles),
           "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
           "-c:s", "mov_text", "-metadata:s:a:0", "title=Synthetic voice (Windows SAPI), not a person",
           "-metadata:s:s:0", "language=eng", "-metadata", "comment=" + VOICE_NOTE + " " + AUTHORSHIP,
           "-shortest", str(out_path)]
    subprocess.run(cmd, check=True)
    return cmd


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")
