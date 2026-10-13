"""Operator screens for the twin, in the ISA-101 style: grey and calm when the plant is normal, so colour means
something when it is not.

  /               Whole-process equipment overview with six units, seed-model boundaries and selected values.
  /mimic          Legacy alias for the same Overview; no separate tab.
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
import textwrap
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
DISPLAY_SPAN = 2.5  # indicator and trend span = the normal band widened 2.5x about its centre (plus nearby alarm limits)

GREY_BG, PANEL, EDGE, INK, MUTED = "#e5e5e5", "#f2f2f2", "#a3a3a3", "#1f2937", "#6b7280"
AMBER, RED = "#fcd34d", "#dc2626"
STATE_BG = [{"input": 1, "output": AMBER}, {"input": 2, "output": RED}]
STATE_FG = [{"input": 2, "output": "#ffffff"}]
FOOT = ("Read-only monitoring. Normal bands are learned from the normal run (scripts/normal_bands.py), not site "
        "limits; amber is not an alarm. Key values, spans and layout: first pass by the screen generator, not yet "
        "reviewed by operations.")


# ---------------------------------------------------------------- components

# Perspective stores a script transform as the BODY of this function and compiles TRANSFORM_SIGNATURE + "\n" + body
# exactly as written. An unindented body is a Jython parse error ("Error_Configuration: Parse Error in script
# transform"): the label shows null under an error overlay, even though its tag reads Good. Seen in the first native
# import of the 23-view project (journal entry 38); every offline check had re-indented the code before running it.
TRANSFORM_SIGNATURE = "def transform(self, value, quality, timestamp):"


def script_body(code):
    """Author-form transform code (written at column 0) -> the indented body Perspective stores. Idempotent."""
    return textwrap.indent(textwrap.dedent(code), "    ")


def script_transform(code):
    return {"type": "script", "code": script_body(code)}


# Drawing-sheet value: the number when the gateway has Good data, otherwise the honest state (%s), never "null".
SHEET_VALUE_SCRIPT = '''import math
if not quality.isGood() or value is None:
    return "%s"
try:
    number = float(value)
except (TypeError, ValueError):
    return "UNKNOWN"
if math.isnan(number) or math.isinf(number):
    return "UNKNOWN"
return "{:,.1f}".format(number)
'''


def tag_binding(path, transforms=()):
    # Every view builder goes through here, so every script transform gets the stored-body form.
    transforms = [script_transform(t["code"]) if t.get("type") == "script" else t for t in transforms]
    return {"binding": {"type": "tag", "config": {"mode": "direct", "tagPath": path, "fallbackDelay": 2.5},
                        "transforms": transforms}}


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
    precision = decimals(band) if band else 1
    code = ('import math\nif not quality.isGood() or value is None:\n    return "UNKNOWN"\n'
            'try:\n    number = float(value)\nexcept (TypeError, ValueError):\n    return "UNKNOWN"\n'
            'if math.isnan(number) or math.isinf(number):\n    return "UNKNOWN"\n'
            'return "%.' + str(precision) + 'f" % number')
    c["propConfig"] = {
        "props.text": tag_binding(base + "/PV", [{"type": "script", "code": code}]),
        "props.style.backgroundColor": tag_binding(base + "/State", [{"type": "script", "code": 'if not quality.isGood() or value is None:\n    return "#d4d4d4"\nreturn {1: "#fcd34d", 2: "#dc2626"}.get(value, "#ffffff")'}]),
        "props.style.color": tag_binding(base + "/State", [{"type": "script", "code": 'if not quality.isGood() or value is None:\n    return "#6b7280"\nreturn "#ffffff" if value == 2 else "#1f2937"'}])}
    return c


ALARM_SPAN_LIMIT = 10  # widen an indicator to show an alarm limit only if it is within 10 band half-widths


def shown_limits(band, limits):
    """Alarm limits close enough to the band to draw on the indicator without hiding the band."""
    mid, half = (band[0] + band[1]) / 2, (band[1] - band[0]) / 2 or 1.0
    return [v for v in limits if abs(v - mid) <= ALARM_SPAN_LIMIT * half]


def span(band, limits):
    mid, half = (band[0] + band[1]) / 2, (band[1] - band[0]) / 2 or 1.0
    lo, hi = mid - DISPLAY_SPAN * half, mid + DISPLAY_SPAN * half
    # A far limit would shrink the band to a sliver that reads as missing data: TI-109's real band is 0.24 degC
    # wide, its alarm 175 degC (journal entry 38). Such a limit stays in the "Normal band" text and in State colour.
    for v in shown_limits(band, limits):
        hi = max(hi, v + 0.05 * (v - lo))
    if band[0] >= 0 > lo:
        lo = 0.0  # flows, levels and outputs don't go negative
    return round(lo, 4), round(hi, 4)


def indicator(name, x, y, w, h, base, band, limits):
    lo, hi = span(band, limits)
    props = {"minValue": lo, "maxValue": hi, "desiredLow": band[0], "desiredHigh": band[1],
             "desiredRangeColor": "#c4c4c4", "defaultRangeColor": "#f5f5f5", "indicatorColor": INK,
             "level1AlarmColor": RED, "level2AlarmColor": "#7f1d1d", "sectionOutline": {"color": EDGE, "width": 1}}
    limits = shown_limits(band, limits)
    if limits:
        props["highAlarm"] = limits[0]
        if len(limits) > 1:
            props["highHighAlarm"] = limits[1]
    return {"type": "ia.display.moving-analog-indicator", "meta": {"name": name},
            "position": {"x": x, "y": y, "width": w, "height": h}, "props": props,
            "propConfig": {"props.processValue": tag_binding(base + "/PV", [{"type": "script", "code": 'import math\nif not quality.isGood() or value is None:\n    return None\ntry:\n    number = float(value)\nexcept (TypeError, ValueError):\n    return None\nreturn None if math.isnan(number) or math.isinf(number) else number'}])}}


def trend(name, x, y, w, h, base, band, minutes):
    # Scaled to the normal band, not to the alarm limits: a far-off shutdown limit would flatten the trend into a line
    # (TI-109's 175 degC against a 0.24 degC band). The indicator shows only nearby limits, for the same reason.
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
           ("Alarms", "/alarms"), ("Drawings", "/drawings")]
    x = 350
    for text, page in nav:
        w = 8 * len(text) + 22
        on = page == active
        kids.append(label(f"Nav_{text}", x, 14, w, 28, text, {
            "textAlign": "center", "borderRadius": 3, "fontWeight": "bold" if on else "normal",
            "backgroundColor": "#ffffff" if on else "transparent",
            "borderStyle": "solid", "borderWidth": 1, "borderColor": EDGE if on else "transparent"}, page=page))
        x += w + 4
    for name, x, member, title, color in [('AlarmSummary', 1248, 'AlarmsActive', 'Alarms', '#b91c1c'),
                                           ('BandSummary', 1410, 'OutOfNormal', 'Outside band', '#8a5d00')]:
        c = label(name, x, 17, 170, 26, title + ': unknown', {'fontSize': 12, 'fontWeight': 'bold'})
        code = 'if not quality.isGood() or value is None:\n    return %r\nreturn %r + str(value)' % (title + ': unknown', title + ': ')
        color_code = 'if not quality.isGood() or value is None:\n    return "#6b7280"\nreturn %r if value > 0 else "#1f2937"' % color
        c['propConfig'] = {'props.text': tag_binding(s + member, [{'type': 'script', 'code': code}]),
                           'props.style.color': tag_binding(s + member, [{'type': 'script', 'code': color_code}])}
        kids.append(c)
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
    import build_mimic
    return build_mimic.mimic(provider, model, hidden)


def unit_screen(provider, model, ranges, uid, hidden):
    unit = next(u for u in model["units"] if u["id"] == uid)
    from te_channels import expanded_items
    tags = [ranges.get(i["tag"], {}).get("source_item", i) for i in expanded_items(model)
            if i["unit"] == uid and i["tag"] in ranges and i["tag"] not in hidden]
    kids = header(provider, f"{unit['name']}  ·  {uid}", f"/unit/{uid}")
    import build_mimic
    kids += build_mimic.unit_context(provider, model, uid, hidden)
    y = build_mimic.detail_table_top(model, uid)
    cols = [("Tag", 16, 90), ("Description", 110, 300), ("Value", 414, 110), ("", 528, 64),
            ("Position against normal band and alarms", 596, 260), ("Normal band", 862, 150),
            ("Last 30 minutes", 1018, 380), ("Gateway state / review", 1404, 180)]
    kids += [label(f"Col_{i}", x, y, w, 18, t, {"fontSize": 11, "color": MUTED, "fontWeight": "bold"})
             for i, (t, x, w) in enumerate(cols)]
    y += 24
    for it in tags:
        tag, r = it["tag"], ranges[it["tag"]]
        base = f"[{provider}]TE_Plant/{uid}/{tag}"
        desc = it["description"] + (" (first component only)" if "-" in str(it.get("xmeas", "")) and not it.get("component") else "")
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
        else:  # no replay source: explicit unavailable label, without a fabricated numeric binding
            box = value_box(tag, 414, y + 10, 110, 32, base, None, 16)
            box.pop("propConfig", None)
            box["props"]["text"] = "NOT CONNECTED"
            box["props"]["style"]["fontSize"] = 11
            kids += [box, label(f"Uom_{tag}", 528, y + 18, 64, 18, it["uom"], {"fontSize": 12, "color": MUTED}),
                     label(f"NoData_{tag}", 596, y + 16, 790, 20,
                           "Not in the open replay data set, so it reads as not connected rather than inventing a value.",
                           {"fontSize": 12, "color": MUTED, "fontStyle": "italic"})]
        if 'xmv' in it and r['normal']:
            for c in kids:
                if c['meta']['name'] == 'Ind_' + tag:
                    c['position']['x'], c['position']['width'] = 746, 110
            kids.append(build_mimic.image('DetailOutput_' + tag, 596, y + 12, 140, 28, 'output', base))
        rs = label(f"Review_{tag}", 1404, y + 16, 180, 20, "", {"fontSize": 12, "color": MUTED})
        rs["propConfig"] = {"props.text": tag_binding(base + "/ReviewStatus")}
        kids.append(rs)
        if r["normal"]:
            import build_mimic
            state = label('State_' + tag, 1404, y - 1, 180, 17, 'State unknown', {'fontSize': 11})
            state['propConfig'] = {'props.text': tag_binding(base + '/State', [{'type': 'script', 'code': build_mimic.STATE_SCRIPT}])}
            kids.append(state)
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
        # A numeric format transform turns a Bad (no data) value into the literal text "null", which reads as a broken
        # screen rather than an honest state (journal entry 38). The script returns plain text, so Perspective's red
        # quality overlay no longer appears; the words carry the state instead. The tag binding stays: a placeholder
        # that ever read Good would show its number (and fail V4) rather than be hidden.
        if not mapped:
            c["props"]["style"].update(fontSize=8, fontStyle="italic", color=MUTED, whiteSpace="nowrap",
                                       paddingLeft=1)
        c["propConfig"] = {"props.text": tag_binding(path + "/PV", [script_transform(
            SHEET_VALUE_SCRIPT % ("UNKNOWN" if mapped else "not connected"))])}
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
    from te_channels import expanded_items
    hidden = set(hidden) | {i["tag"] for i in expanded_items(model) if i["tag"] not in ranges}
    hidden |= {i["tag"] for i in expanded_items(model) if i.get("analyzer_parent") in hidden}
    for tag, r in ranges.items():
        r["alarm_limits"] = [a["setpointA"] for a in alarms.get(tag, [])]
    views = {"TE/Overview": overview(provider, model, ranges, hidden), "TE/Alarms": alarms_screen(provider)}
    for uid in UNIT_ORDER:
        views[f"TE/Unit_{uid}"] = unit_screen(provider, model, ranges, uid, hidden)
    import build_mimic
    views["TE/ProcessMimic"] = views["TE/Overview"]  # safe legacy bookmark alias
    pages = {"/mimic": ("Plant overview (legacy alias)", "TE/ProcessMimic"), "/": ("Plant overview", "TE/Overview"), "/alarms": ("Alarms", "TE/Alarms")}
    pages.update({f"/unit/{u}": (f"Unit {u}", f"TE/Unit_{u}") for u in UNIT_ORDER})
    return views, pages
