"""Operator screens for the twin, in the ISA-101 style: grey and calm when the plant is normal, so colour means
something when it is not.

  /               TE level-1 overview: one tile per unit, in process order. Each tile shows the unit's key values, with
                  a moving analog indicator (where the value sits against its normal band and alarm limits) and a
                  10-minute trend. The alarm list sits at the bottom.
  /unit/<id>      Level 2: every value in one unit, with its band, a 30-minute trend and its review status.
  /schematic      The process schematic with live values (scripts/ignition/build_views.py).
  /alarms         The full alarm list.
  /drawings       The 12 extracted drawings, and /open100/<n>: each ORIGINAL drawing (greyed) with live values on top.

Every screen has the same summary bar: navigation, the count of active alarms and the count of values outside their
normal band. Colour, everywhere: no fill = normal; amber = outside the normal band (a display aid, not an alarm);
red = an alarm is active. The colours come from each tag's State member, set in the gateway (build_gateway.py), so the
screens and anything else reading the tags agree.

WHERE EACH PART CAME FROM (which used several models, which only Claude):
  - The tags, units and drawing positions are the twin itself. The Tennessee Eastman model was transcribed from the
    published process (checked against teprob.f). The OPEN100 instruments were EXTRACTED from the drawings: that is
    the multi-model part (Claude, GPT and Gemini compared on the same sheets; the published twin uses GPT's output,
    risk-tiered by agreement across all three). See docs/EVALUATION.md and docs/MODELS.md.
  - Normal bands: plain statistics on the published normal run (scripts/normal_bands.py), no model.
  - Alarm limits: published sources only (build_gateway.ALARMS), no model.
  - Everything on these screens that is a JUDGEMENT rather than data was made by one model, Claude (the coding agent
    that wrote this file), and has not been reviewed by operations or compared against another model:
      * KEY_VALUES: which 2-4 values represent each unit on the overview;
      * the display spans of the indicators and trends (DISPLAY_SPAN below);
      * the layout, the process order of the tiles, and the colour scheme.
    A plant would have its operators choose the key values and spans; scripts/apply_review.py can carry them.
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W, HEAD = 1600, 56

# Claude's first-pass choice, in process order (feed -> reaction -> cooling -> separation -> recycle -> product).
# Rule used: the values that say whether the unit is doing its job and is safe (pressure and temperature first where
# a shutdown limit exists), at most four. Not reviewed by operations.
UNIT_ORDER = ["U-100", "R-101", "E-101", "V-101", "K-101", "C-101"]
KEY_VALUES = {
    "U-100": ["FI-101", "FI-102", "FI-103"],
    "R-101": ["PI-107", "TI-109", "LI-108", "TI-121"],
    "E-101": ["TI-122", "TV-211"],
    "V-101": ["PI-113", "TI-111", "LI-112", "FI-114"],
    "K-101": ["FI-105", "FI-110", "JI-120", "HV-205"],
    "C-101": ["PI-116", "TI-118", "LI-115", "FI-117"],
}
DISPLAY_SPAN = 2.5  # indicator and trend span = the normal band widened 2.5x about its centre (plus alarm limits)

GREY_BG, PANEL, EDGE, INK, MUTED = "#e5e5e5", "#f2f2f2", "#a3a3a3", "#1f2937", "#6b7280"
AMBER, RED = "#fcd34d", "#dc2626"
STATE_BG = [{"input": 1, "output": AMBER}, {"input": 2, "output": RED}]
STATE_FG = [{"input": 2, "output": "#ffffff"}]
FOOT = ("Read-only monitoring. Normal bands are learned from the normal run (scripts/normal_bands.py), not site "
        "limits; amber is not an alarm. Key values, spans and layout: first pass by the screen generator, not yet "
        "reviewed by operations.")


# ---------------------------------------------------------------- components

def tag_binding(path, transforms=()):
    return {"binding": {"type": "tag", "config": {"mode": "direct", "tagPath": path, "fallbackDelay": 2.5},
                        "transforms": list(transforms)}}


def color_map(mappings, fallback):
    return {"type": "map", "inputType": "scalar", "outputType": "color", "mappings": mappings, "fallback": fallback}


def label(name, x, y, w, h, text, style=None, page=None, tooltip=None):
    c = {"type": "ia.display.label", "meta": {"name": name},
         "position": {"x": round(x, 1), "y": round(y, 1), "width": w, "height": h},
         "props": {"text": text, "style": {"fontFamily": "Arial", "fontSize": 13, "color": INK, **(style or {})}}}
    if page:
        c["events"] = {"dom": {"onClick": {"type": "nav", "scope": "C", "config": {"page": page}}}}
        c["props"]["style"]["cursor"] = "pointer"
    if tooltip:
        c["meta"]["tooltip"] = {"enabled": True, "text": tooltip}
    return c


def decimals(band):
    width = band[1] - band[0]
    return 0 if width >= 50 else 1 if width >= 5 else 2 if width >= 0.5 else 3


def value_box(name, x, y, w, h, base, band, size=15):
    """The value, coloured by the tag's State: no fill normal, amber outside the band, red in alarm."""
    fmt = "#,##0" + ("." + "0" * decimals(band) if band and decimals(band) else "") if band else "#,##0.0"
    c = label(name, x, y, w, h, "", {"fontSize": size, "fontWeight": "bold", "textAlign": "right",
                                      "paddingRight": 6, "borderStyle": "solid", "borderWidth": 1,
                                      "borderColor": EDGE, "backgroundColor": "#ffffff"})
    c["propConfig"] = {
        "props.text": tag_binding(base + "/PV", [{"type": "format", "formatType": "numeric", "formatValue": fmt}]),
        "props.style.backgroundColor": tag_binding(base + "/State", [color_map(STATE_BG, "#ffffff")]),
        "props.style.color": tag_binding(base + "/State", [color_map(STATE_FG, INK)])}
    return c


def span(band, limits):
    mid, half = (band[0] + band[1]) / 2, (band[1] - band[0]) / 2 or 1.0
    lo, hi = mid - DISPLAY_SPAN * half, mid + DISPLAY_SPAN * half
    for v in limits:
        hi = max(hi, v + 0.05 * (v - lo))
    if band[0] >= 0 > lo:
        lo = 0.0  # flows, levels and outputs don't go negative
    return round(lo, 4), round(hi, 4)


def indicator(name, x, y, w, h, base, band, limits):
    lo, hi = span(band, limits)
    props = {"minValue": lo, "maxValue": hi, "desiredLow": band[0], "desiredHigh": band[1],
             "desiredRangeColor": "#c4c4c4", "defaultRangeColor": "#f5f5f5", "indicatorColor": INK,
             "level1AlarmColor": RED, "level2AlarmColor": "#7f1d1d", "sectionOutline": {"color": EDGE, "width": 1}}
    if limits:
        props["highAlarm"] = limits[0]
        if len(limits) > 1:
            props["highHighAlarm"] = limits[1]
    return {"type": "ia.display.moving-analog-indicator", "meta": {"name": name},
            "position": {"x": x, "y": y, "width": w, "height": h}, "props": props,
            "propConfig": {"props.processValue": tag_binding(base + "/PV")}}


def trend(name, x, y, w, h, base, band, minutes):
    # Scaled to the normal band, not to the alarm limits: the indicator already shows how far away a limit is, and a
    # far-off shutdown limit would flatten the trend into a line (TI-109's 175 degC against a 0.24 degC band).
    lo, hi = span(band, [])
    no_marker = {"shape": "circle", "size": 0, "stroke": {"color": "", "width": 0, "opacity": 0, "dashArray": ""},
                 "fill": {"color": "", "opacity": 0}, "style": {"classes": ""}}
    last = dict(no_marker, size=4, fill={"color": INK, "opacity": 1})
    return {"type": "ia.display.sparkline", "meta": {"name": name},
            "position": {"x": x, "y": y, "width": w, "height": h},
            "props": {"color": "#374151", "width": 1.2, "range": {"low": lo, "high": hi},
                      "marker": {"first": no_marker, "last": last, "low": no_marker, "high": no_marker},
                      "desired": {"low": band[0], "high": band[1], "fill": {"color": "#9ca3af", "opacity": 0.25},
                                  "stroke": {"color": "#9ca3af", "width": 0.5, "opacity": 1, "dashArray": 3}}},
            "propConfig": {"props.points": {"binding": {"type": "tag-history", "config": {
                "tags": [{"path": base + "/PV", "alias": "v"}],
                "dateRange": {"mostRecent": minutes, "mostRecentUnits": "min"},
                # Raw stored points, bad quality left out: fixed-size buckets drew empty buckets and the gaps left
                # by a stopped data source as drops to zero, which looked like process upsets that never happened.
                "returnFormat": "wide", "returnSize": {"type": "raw"}, "ignoreBadQuality": True,
                "polling": {"enabled": True, "rate": 5}, "valueFormat": "dataset"}}}}}


def badge(name, x, y, w, h, path, color):
    c = label(name, x, y, w, h, "", {"fontWeight": "bold", "textAlign": "center", "borderRadius": 3,
                                      "backgroundColor": "#d4d4d4"})
    c["propConfig"] = {"props.text": tag_binding(path),
                       "props.style.backgroundColor": tag_binding(path, [color_map(
                           [{"input": 0, "output": "#d4d4d4"}], color)]),
                       "props.style.color": tag_binding(path, [color_map([{"input": 0, "output": INK}],
                                                                         "#ffffff" if color == RED else INK)])}
    return c


def header(provider, title, active):
    s = f"[{provider}]TE_Plant/_Summary/"
    kids = [label("HeaderBar", 0, 0, W, HEAD, "", {"backgroundColor": "#d4d4d4", "borderBottom": f"1px solid {EDGE}"}),
            label("Title", 16, 8, 330, 20, title, {"fontSize": 16, "fontWeight": "bold"}),
            label("Subtitle", 16, 30, 330, 18, "Tennessee Eastman · live replay · read-only",
                  {"fontSize": 11, "color": MUTED})]
    nav = [("Overview", "/"), ("Feed", "/unit/U-100"), ("Reactor", "/unit/R-101"), ("Condenser", "/unit/E-101"),
           ("Separator", "/unit/V-101"), ("Compressor", "/unit/K-101"), ("Stripper", "/unit/C-101"),
           ("Schematic", "/schematic"), ("Alarms", "/alarms"), ("Drawings", "/drawings")]
    x = 350
    for text, page in nav:
        w = 8 * len(text) + 22
        on = page == active
        kids.append(label(f"Nav_{text}", x, 14, w, 28, text, {
            "textAlign": "center", "borderRadius": 3, "fontWeight": "bold" if on else "normal",
            "backgroundColor": "#ffffff" if on else "transparent",
            "borderStyle": "solid", "borderWidth": 1, "borderColor": EDGE if on else "transparent"}, page=page))
        x += w + 4
    kids += [label("AlarmsLabel", 1250, 18, 60, 20, "Alarms", {"textAlign": "right", "color": MUTED}),
             badge("AlarmsCount", 1316, 15, 40, 26, s + "AlarmsActive", RED),
             label("OutOfNormalLabel", 1366, 18, 170, 20, "Outside normal band", {"textAlign": "right",
                                                                                   "color": MUTED}),
             badge("OutOfNormalCount", 1542, 15, 40, 26, s + "OutOfNormal", AMBER)]
    return kids


def footer(y):
    return label("Footer", 16, y, W - 32, 18, FOOT, {"fontSize": 11, "color": MUTED})


def view(h, children):
    return {"custom": {}, "params": {}, "props": {"defaultSize": {"width": W, "height": int(h)}},
            "root": {"type": "ia.container.coord", "meta": {"name": "root"},
                     "props": {"mode": "fixed", "style": {"backgroundColor": GREY_BG}}, "children": children}}


def alarm_table(name, x, y, w, h, compact):
    props = {"toolbar": {"enabled": not compact}, "pager": {"enabled": not compact},
             "enableDetails": not compact, "enableShelve": False, "refreshRate": 2000}
    if compact:  # the overview's list is "Active alarms": cleared ones belong on the Alarms screen
        props["filters"] = {"active": {"states": {"activeUnacked": True, "activeAcked": True,
                                                  "clearUnacked": False, "clearAcked": False}}}
    return {"type": "ia.display.alarmstatustable", "meta": {"name": name},
            "position": {"x": x, "y": y, "width": w, "height": h}, "props": props}


# ---------------------------------------------------------------- screens

def te_items(model):
    return {i["tag"]: i for i in model["instruments"] + model["final_elements"]}


def overview(provider, model, ranges, hidden):
    items, units = te_items(model), {u["id"]: u for u in model["units"]}
    kids = header(provider, "Plant overview", "/")
    tw, th, gap = 512, 304, 16
    for n, uid in enumerate(UNIT_ORDER):
        x, y = gap + (n % 3) * (tw + gap), HEAD + 12 + (n // 3) * (th + 12)
        kids += [label(f"Tile_{uid}", x, y, tw, th, "", {"backgroundColor": PANEL, "borderStyle": "solid",
                                                          "borderWidth": 1, "borderColor": EDGE}),
                 label(f"TileTitle_{uid}", x + 12, y + 8, 300, 22, f"{units[uid]['name']}  ·  {uid}  ›",
                       {"fontSize": 15, "fontWeight": "bold"}, page=f"/unit/{uid}",
                       tooltip="Open the unit screen"),
                 label(f"TileDevLabel_{uid}", x + 300, y + 10, 158, 18, "outside normal",
                       {"fontSize": 11, "color": MUTED, "textAlign": "right"}),
                 badge(f"TileDev_{uid}", x + 464, y + 8, 36, 22,
                       f"[{provider}]TE_Plant/_Summary/OutOfNormal_{uid}", AMBER)]
        row_y = y + 42
        for tag in [t for t in KEY_VALUES[uid] if t not in hidden]:
            it, r = items[tag], ranges[tag]
            base, band = f"[{provider}]TE_Plant/{uid}/{tag}", r["normal"]
            limits = [a for a in r.get("alarm_limits", [])]
            kids += [label(f"Tag_{tag}", x + 12, row_y, 120, 18, tag, {"fontWeight": "bold"}),
                     label(f"Desc_{tag}", x + 12, row_y + 19, 150, 30, it["description"],
                           {"fontSize": 11, "color": MUTED, "lineHeight": 1.1}),
                     value_box(tag, x + 166, row_y + 4, 92, 28, base, band),
                     label(f"Uom_{tag}", x + 262, row_y + 10, 54, 18, it["uom"], {"fontSize": 11, "color": MUTED}),
                     indicator(f"Ind_{tag}", x + 318, row_y + 6, 84, 24, base, band, limits),
                     trend(f"Trend_{tag}", x + 410, row_y, 90, 40, base, band, 10)]
            row_y += 62
    y = HEAD + 12 + 2 * (th + 12)
    kids += [label("AlarmTitle", 16, y, 300, 18, "Active alarms", {"fontWeight": "bold"}),
             alarm_table("AlarmList", 16, y + 22, W - 32, 150, True), footer(y + 178)]
    return view(y + 200, kids)


def unit_screen(provider, model, ranges, uid, hidden):
    unit = next(u for u in model["units"] if u["id"] == uid)
    tags = [i for i in model["instruments"] + model["final_elements"]
            if i["unit"] == uid and i["tag"] in ranges and i["tag"] not in hidden]
    kids = header(provider, f"{unit['name']}  ·  {uid}", f"/unit/{uid}")
    y = HEAD + 14
    cols = [("Tag", 16, 90), ("Description", 110, 300), ("Value", 414, 110), ("", 528, 64),
            ("Position against normal band and alarms", 596, 260), ("Normal band", 862, 150),
            ("Last 30 minutes", 1018, 380), ("Review", 1404, 180)]
    kids += [label(f"Col_{i}", x, y, w, 18, t, {"fontSize": 11, "color": MUTED, "fontWeight": "bold"})
             for i, (t, x, w) in enumerate(cols)]
    y += 24
    for it in tags:
        tag, r = it["tag"], ranges[it["tag"]]
        base = f"[{provider}]TE_Plant/{uid}/{tag}"
        desc = it["description"] + (" (first component only)" if "-" in str(it.get("xmeas", "")) else "")
        kids.append(label(f"Row_{tag}", 8, y - 4, W - 16, 60, "", {"backgroundColor": PANEL, "borderStyle": "solid",
                                                                    "borderWidth": 1, "borderColor": "#d4d4d4"}))
        kids += [label(f"Tag_{tag}", 16, y + 14, 90, 20, tag, {"fontWeight": "bold"}),
                 label(f"Desc_{tag}", 110, y + 6, 300, 36, desc, {"fontSize": 12, "lineHeight": 1.2})]
        if r["normal"]:
            band, limits = r["normal"], r.get("alarm_limits", [])
            d = decimals(band)
            kids += [value_box(tag, 414, y + 10, 110, 32, base, band, 16),
                     label(f"Uom_{tag}", 528, y + 18, 64, 18, it["uom"], {"fontSize": 12, "color": MUTED}),
                     indicator(f"Ind_{tag}", 596, y + 12, 260, 28, base, band, limits),
                     label(f"Band_{tag}", 862, y + 8, 150, 36,
                           f"{band[0]:,.{d}f} – {band[1]:,.{d}f}" + (
                               "\nalarm " + " / ".join(f"{v:g}" for v in limits) if limits else ""),
                           {"fontSize": 12, "whiteSpace": "pre-line", "lineHeight": 1.3}),
                     trend(f"Trend_{tag}", 1018, y + 2, 380, 48, base, band, 30)]
        else:  # no data source: the value box still binds, so the screen shows it as not connected
            box = value_box(tag, 414, y + 10, 110, 32, base, None, 16)
            del box["propConfig"]["props.style.backgroundColor"], box["propConfig"]["props.style.color"]
            kids += [box, label(f"Uom_{tag}", 528, y + 18, 64, 18, it["uom"], {"fontSize": 12, "color": MUTED}),
                     label(f"NoData_{tag}", 596, y + 16, 790, 20,
                           "Not in the open replay data set, so it reads as not connected rather than inventing a value.",
                           {"fontSize": 12, "color": MUTED, "fontStyle": "italic"})]
        rs = label(f"Review_{tag}", 1404, y + 16, 180, 20, "", {"fontSize": 12, "color": MUTED})
        rs["propConfig"] = {"props.text": tag_binding(base + "/ReviewStatus")}
        kids.append(rs)
        y += 64
    kids.append(footer(y + 8))
    return view(y + 30, kids)


def alarms_screen(provider):
    kids = header(provider, "Alarms", "/alarms")
    kids += [alarm_table("AlarmTable", 16, HEAD + 16, W - 32, 640, False),
             label("AlarmNote", 16, HEAD + 668, W - 32, 36,
                   "The only alarms are the published ones: reactor pressure high (2895 kPa) and the simulator's "
                   "shutdown limits (3000 kPa, 175 °C). Adding or removing an alarm is a change review, not a "
                   "screen edit.", {"fontSize": 12, "color": MUTED})]
    return view(HEAD + 720, kids)


def data_uri(path, mime):
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def drawings_index(provider, sheets):
    kids = header(provider, "Extracted drawings", "/drawings")
    kids.append(label("DrawIntro", 16, HEAD + 12, W - 32, 36,
                      "Twelve public drawings (PID2Graph OPEN100, CC BY-SA 4.0). Each screen shows the original drawing "
                      "with a live value beside every extracted instrument. Instruments mapped to a data point read "
                      "live; the rest show as not connected.", {"fontSize": 12, "color": MUTED}))
    tw, th = 372, 250
    for n, (sheet, title, img) in enumerate(sheets):
        x, y = 16 + (n % 4) * (tw + 16), HEAD + 60 + (n // 4) * (th + 16)
        kids.append({"type": "ia.display.image", "meta": {"name": f"Thumb_{sheet}"},
                     "position": {"x": x, "y": y, "width": tw, "height": th - 26},
                     "props": {"source": img, "fit": {"mode": "contain"},
                               "style": {"borderStyle": "solid", "borderWidth": 1, "borderColor": EDGE,
                                         "cursor": "pointer"}},
                     "events": {"dom": {"onClick": {"type": "nav", "scope": "C",
                                                    "config": {"page": f"/open100/{sheet}"}}}}})
        kids.append(label(f"ThumbTitle_{sheet}", x, y + th - 24, tw, 20, f"Sheet {sheet}  ·  {title}  ›",
                          {"fontSize": 12, "fontWeight": "bold"}, page=f"/open100/{sheet}"))
    return view(HEAD + 60 + 3 * (th + 16), kids)


def sheet_screen(provider, sheet, title, img_uri, size, instruments, counts):
    """instruments: (asset_id, tag text, x, y, r in drawing coordinates, PV tag path, mapped?)."""
    sw, sh = size
    kids = header(provider, f"Drawing {sheet}  ·  {title}", "/drawings")
    kids.append({"type": "ia.display.image", "meta": {"name": "Drawing"},
                 "position": {"x": 0, "y": HEAD, "width": sw, "height": sh},
                 "props": {"source": img_uri, "fit": {"mode": "fill"}}})
    placed, lw, lh = [], 50, 15

    def free(x, y):
        return all(x + lw <= a or a + lw <= x or y + lh <= b or b + lh <= y for a, b in placed)
    for asset, tag, cx, cy, r, path, mapped in instruments:
        # Right of the bubble if there is room; otherwise below, above, left, then stepping down. Instruments on a
        # P&ID often sit in a row, and overlapping labels would hide each other's values.
        spots = [(cx + r + 2, cy - 8), (cx - lw / 2, cy + r + 2), (cx - lw / 2, cy - r - lh - 2), (cx - r - lw - 2, cy - 8)]
        spots += [(cx - lw / 2, cy + r + 2 + k * (lh + 1)) for k in range(1, 6)]
        lx, ly = next((s for s in spots if free(*s)), spots[0])
        placed.append((lx, ly))
        c = label(asset, lx, HEAD + ly, lw, lh, "", {
            "fontSize": 10, "fontWeight": "bold" if mapped else "normal", "paddingLeft": 2,
            "borderStyle": "solid", "borderWidth": 1, "borderColor": INK if mapped else EDGE,
            "backgroundColor": "#ffffff"}, tooltip=f"{tag} ({asset}): " + (
                "mapped to a data point" if mapped else "extracted from the drawing; no data point yet"))
        c["propConfig"] = {"props.text": tag_binding(path + "/PV", [
            {"type": "format", "formatType": "numeric", "formatValue": "#,##0.0"}])}
        kids.append(c)
    x = sw + 16
    kids += [label("Legend", x, HEAD + 12, W - x - 16, 20, "This drawing", {"fontWeight": "bold"}),
             label("LegendLive", x, HEAD + 40, W - x - 16, 40,
                   f"{counts[0]} instruments mapped to a data point: live values (bold).", {"fontSize": 12}),
             label("LegendDark", x, HEAD + 84, W - x - 16, 56,
                   f"{counts[1]} extracted, not mapped yet: shown as not connected until the I/O list maps them.",
                   {"fontSize": 12}),
             label("LegendSrc", x, HEAD + 148, W - x - 16, 160,
                   "Instruments and positions were extracted from this drawing by GPT, risk-checked against Claude "
                   "and Gemini, and are unverified until reviewed. Drawing: PID2Graph OPEN100, CC BY-SA 4.0.",
                   {"fontSize": 11, "color": MUTED})]
    return view(HEAD + sh, kids)


# ---------------------------------------------------------------- assembly

def te_views(provider, ranges, alarms, hidden):
    model = json.loads((ROOT / "data" / "te_process_model.json").read_text(encoding="utf-8"))
    for tag, r in ranges.items():
        r["alarm_limits"] = [a["setpointA"] for a in alarms.get(tag, [])]
    views = {"TE/Overview": overview(provider, model, ranges, hidden), "TE/Alarms": alarms_screen(provider)}
    for uid in UNIT_ORDER:
        views[f"TE/Unit_{uid}"] = unit_screen(provider, model, ranges, uid, hidden)
    pages = {"/": ("Plant overview", "TE/Overview"), "/alarms": ("Alarms", "TE/Alarms")}
    pages.update({f"/unit/{u}": (f"Unit {u}", f"TE/Unit_{u}") for u in UNIT_ORDER})
    return views, pages
