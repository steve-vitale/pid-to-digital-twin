"""Controls for the along-line instrument parent rule (trace_connections.line_geometry / along_line, and
build_twin --parent-rule). Synthetic drawing only: no answer key, no drawing data.

The sheet: a pipe from a tank, interrupted by a valve.
  I1  instrument whose leader runs right-angled back along to the pipe: by position and by centre distance the
      valve is nearer, but following the line the tank is nearer. along_line -> tank; linked and nearest -> valve.
  I2  instrument wired only to I3 (a signal chain); I3 sits on the pipe beyond the valve.
      along_line -> valve, through I3 (method along_line_via_instrument_chain).
  I4  instrument on no line at all -> falls back, and says so.
Also checks that asking for the geometry never changes trace()'s links.

Usage: python scripts/test_along_line.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import build_twin as bt  # noqa: E402
import trace_connections as tc  # noqa: E402

SYMBOLS = [  # 1000 x 1000 px sheet, so pixel = 0-1000 unit
    {"id": "T", "class": "tank", "box": [40, 470, 100, 530], "tag": "TK-1"},
    {"id": "V", "class": "valve", "box": [600, 485, 640, 515], "tag": "V-1"},
    {"id": "I1", "class": "instrumentation", "box": [520, 380, 560, 420], "tag": "PT 1"},
    {"id": "I2", "class": "instrumentation", "box": [700, 200, 740, 240], "tag": "PIC 2"},
    {"id": "I3", "class": "instrumentation", "box": [700, 300, 740, 340], "tag": "PT 2"},
    {"id": "I4", "class": "instrumentation", "box": [100, 800, 140, 840], "tag": "TI 4"},
]


def draw(path):
    img = np.full((1000, 1000), 255, np.uint8)
    line = lambda a, b: cv2.line(img, a, b, 0, 3)  # noqa: E731
    cv2.rectangle(img, (40, 470), (100, 530), 0, 3)               # tank
    line((100, 500), (600, 500)); line((640, 500), (900, 500))    # pipe, interrupted by the valve
    line((600, 485), (640, 515)); line((600, 515), (640, 485))    # valve bow-tie
    line((600, 485), (600, 515)); line((640, 485), (640, 515))
    for x0, y0 in ((520, 380), (700, 200), (700, 300), (100, 800)):
        cv2.circle(img, (x0 + 20, y0 + 20), 19, 0, 2)             # instrument bubbles
    line((520, 400), (330, 400)); line((330, 400), (330, 500))    # I1's leader, back along to the pipe
    line((720, 240), (720, 300))                                  # I2 -> I3 (signal chain)
    line((720, 340), (720, 500))                                  # I3 -> pipe beyond the valve
    cv2.imwrite(str(path), img)


def main():
    fails = []

    def check(name, ok, got=None):
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  (got {got})"))
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        confidence_cache_revision(tmp, check)
        img = tmp / "0.png"
        draw(img)
        links = tc.trace(img, SYMBOLS)
        g = tc.line_geometry(img, SYMBOLS)
        check("geometry request leaves trace() links unchanged", g["links"] == links, (links, g["links"]))
        targets = {"T", "V"}
        r = tc.along_line(g, "I1", targets)
        check("I1: tank is nearest along the line", bool(r) and r[0][0] == "T", r)
        r = tc.along_line(g, "I2", targets)
        check("I2: no asset reached without passing an instrument", r == [], r)
        r = tc.along_line(g, "I2", targets, passable={"I1", "I2", "I3", "I4"})
        check("I2: valve reached through I3", bool(r) and r[0][0] == "V" and r[0][2] == ["I3"], r)
        check("I4: not on any traced line", tc.along_line(g, "I4", targets) == [], g["attach"].get("I4"))

        run = tmp / "run"
        run.mkdir()
        (run / "0.json").write_text(json.dumps({"tool": "synthetic", "drawing": "0", "prediction": {
            "symbols": SYMBOLS, "connections": links}}), encoding="utf-8")
        par = {}
        for rule in bt.PARENT_RULES:
            m = bt.build("synthetic", run, ["0"], tmp, {}, "test", rule)
            par[rule] = {i["provenance"][0]["symbol"]: (i["parent_source"] or {}).get("symbol") for i in
                         m["instruments"]}
            par[rule + "_method"] = {i["provenance"][0]["symbol"]: i["parent_method"] for i in m["instruments"]}
            par[rule + "_status"] = {i["provenance"][0]["symbol"]: i.get("along_line_status")
                                     for i in m["instruments"]}
        check("build along_line: I1 -> tank", par["along_line"]["I1"] == "T", par["along_line"])
        check("build linked: I1 -> valve (the ambiguity this rule fixes)", par["linked"]["I1"] == "V", par["linked"])
        check("build nearest: I1 -> valve", par["nearest"]["I1"] == "V", par["nearest"])
        check("build along_line: I2 -> valve via instrument chain",
              par["along_line"]["I2"] == "V" and par["along_line_method"]["I2"] == "along_line_via_instrument_chain",
              (par["along_line"]["I2"], par["along_line_method"]["I2"]))
        check("build along_line: I4 falls back and records why",
              par["along_line_status"]["I4"] == "not_on_traced_line"
              and par["along_line_method"]["I4"] == "geometry_nearest",
              (par["along_line_method"]["I4"], par["along_line_status"]["I4"]))
        plant_coded_tags(tmp, check)
    print(f"{len(fails)} failed" if fails else "all passed")
    sys.exit(1 if fails else 0)


def confidence_cache_revision(tmp, check):
    """A real drawing revision must retrace even at the same filename and timestamp."""
    import confidence
    image = tmp / "cache-sheet.png"
    draw(image)
    old_cache = confidence.CACHE
    confidence.CACHE = tmp / "isolated-cache"
    try:
        with patch.object(tc, "trace", wraps=tc.trace) as tracing:
            original = confidence.trace_info(image, SYMBOLS, None)
            repeated = confidence.trace_info(image, SYMBOLS, None)
            check("identical drawing reuses its real line trace", original == repeated and tracing.call_count == 1)
            stat = image.stat()
            check("control drawing has real line networks", bool(original["networks"]))
            cv2.imwrite(str(image), np.full((1000, 1000), 255, np.uint8))
            os.utime(image, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            revised = confidence.trace_info(image, SYMBOLS, None)
            check("same filename and retained timestamp retraces changed bytes", tracing.call_count == 2)
            check("revised blank drawing does not inherit old networks",
                  revised["networks"] == {} and revised != original)
            repeated_revision = confidence.trace_info(image, SYMBOLS, None)
            check("unchanged revised drawing reuses only its new trace",
                  repeated_revision == revised and tracing.call_count == 2)
            image.unlink()
            try:
                confidence.trace_info(image, SYMBOLS, None)
            except FileNotFoundError:
                missing_refused = True
            else:
                missing_refused = False
            check("missing drawing cannot be masked by an existing trace cache", missing_refused)
    finally:
        confidence.CACHE = old_cache


def plant_coded_tags(tmp, check):
    """A letter group that starts with a system code seen on its own sheet (MS... on an MSS sheet) is the plant's
    own tag, not ISA-5.1 letters: no measured variable, and a ...V is still a valve. The same tags on a sheet with
    another system code are read as ISA letters, as before (the rule rests on the sheet's own evidence)."""
    tags = ["MSBV 1407", "MSIV 2", "MS 4010", "MOV 5", "PT 6", "PSV 7", "TCV 8"]
    for code in ("MSS", "ACC"):
        run = tmp / f"plant-{code}"
        run.mkdir()
        syms = [{"id": "E", "class": "tank", "box": [40, 40, 100, 100], "tag": f"{code}-TK-1"}] + \
               [{"id": f"I{n}", "class": "instrumentation", "box": [200 + 60 * n, 500, 240 + 60 * n, 540], "tag": t}
                for n, t in enumerate(tags)]
        (run / "0.json").write_text(json.dumps({"tool": "synthetic", "drawing": "0", "prediction": {
            "symbols": syms, "connections": []}}), encoding="utf-8")
        m = bt.build("synthetic", run, ["0"], tmp, {}, "test", "nearest")
        got = {i["tag"]: (i["variable"], i["instrument_kind"], i["variable_method"]) for i in m["instruments"]}
        if code == "MSS":
            for t in ("MSBV 1407", "MSIV 2"):
                v, k, how = got[t]
                check(f"MSS sheet: {t} is a plant tag, no measured variable, still a valve",
                      v is None and k == "valve (plant-coded tag)" and "MSS" in (how or ""), got[t])
            v, k, how = got["MS 4010"]
            check("MSS sheet: MS 4010 is a plant tag with no ISA kind or variable",
                  v is None and k is None and "MSS" in (how or ""), got["MS 4010"])
            check("MSS sheet: ISA tags keep their first-letter variable",
                  got["PT 6"][0] == "pressure" and got["PSV 7"][0] == "pressure" and
                  got["TCV 8"][0] == "temperature" and got["PT 6"][2] == "ISA-5.1 first letter", got)
            check("MSS sheet: MOV stays an operated valve", got["MOV 5"][:2] == (None, "operated valve"), got["MOV 5"])
        else:
            check("ACC sheet: with no MS system code the letters are read as ISA, as before",
                  got["MSBV 1407"][0] == "moisture" and got["MSBV 1407"][1] == "final element (valve)",
                  got["MSBV 1407"])
        safety = {i["tag"]: (i.get("safety") or {}).get("function") for i in m["instruments"]}
        want = {"PSV 7": "relief device", "MSBV 1407": None, "MOV 5": None, "PT 6": None, "TCV 8": None,
                "MS 4010": None, "MSIV 2": "isolation valve" if code == "MSS" else None}
        check(f"{code} sheet: safety marks follow the tag as read (MSIV isolation only where MS is the plant code)",
              safety == want, safety)
    safety_floor(check)


def safety_floor(check):
    """The floor never changes a score, lifts only green to amber, and leaves unmarked items alone."""
    import confidence
    rule = [("PSV 1", "PSV", "final element (valve)", "relief device"), ("PSE 2", "PSE", "measurement / control",
            "relief device"), ("RD 3", "RD", "measurement / control", "relief device"),
            ("XV 4", "XV", "final element (valve)", "shutdown / on-off valve"),
            ("PSHH 5", "PSHH", "measurement / control", "trip switch (possible interlock input)"),
            ("AORV 6", "AORV", "operated valve", "relief device"), ("MOV 7", "MOV", "operated valve", None),
            ("PSC 8", "PSC", "measurement / control", None), ("FCV 9", "FCV", "final element (valve)", None),
            ("PT 10", "PT", "measurement / control", None)]
    model = {"meta": {"risk_model": {"tiers": {}}}, "systems": [{"id": "SYS-0", "system_code": None}],
             "instruments": [{"id": f"I{n}", "class": "instrumentation", "system": "SYS-0", "tag": t,
                              "isa_letters": lt, "instrument_kind": k,
                              "risk": {"risk_score": 0.01 * n, "tier": ["green", "amber", "red"][n % 3], "why": "w"}}
                             for n, (t, lt, k, _) in enumerate(rule)],
             "line_items": [{"id": "L1", "class": "general", "system": "SYS-0", "tag": "RUPTURE DISK",
                             "risk": {"risk_score": 0.02, "tier": "green", "why": "w"}},
                            {"id": "L2", "class": "valve", "system": "SYS-0", "tag": "NC",
                             "risk": {"risk_score": 0.02, "tier": "green", "why": "w"}}]}
    confidence.mark_safety(model)
    got = {x["tag"]: (x.get("safety") or {}).get("function") for x in model["instruments"]}
    check("safety rule: relief / shutdown / trip letters marked; MOV, PSC, FCV, PT not",
          got == {t: f for t, _, _, f in rule}, got)
    check("safety rule: RUPTURE DISK text marked, NC valve not",
          [(x.get("safety") or {}).get("function") for x in model["line_items"]] == ["relief device", None])
    before = {x["id"]: dict(x["risk"]) for x in model["instruments"] + model["line_items"]}
    rep = confidence.safety_floor(model)
    after = {x["id"]: x for x in model["instruments"] + model["line_items"]}
    check("floor: no marked item stays green; unmarked items untouched; scores never change",
          all(after[i]["risk"]["tier"] != "green" for i in after if after[i].get("safety"))
          and all(after[i]["risk"] == before[i] for i in after if not after[i].get("safety"))
          and all(after[i]["risk"]["risk_score"] == before[i]["risk_score"] for i in after),
          {i: after[i]["risk"] for i in after})
    check("floor: red stays red, green becomes amber with the reason first",
          after["I2"]["risk"]["tier"] == "red" and after["I0"]["risk"]["tier"] == "amber"
          and after["I0"]["risk"]["tier_before_floor"] == "green"
          and after["I0"]["risk"]["why"].startswith("safety-relevant (relief device): always checked"),
          (after["I0"]["risk"], after["I2"]["risk"]))
    check("floor report counts the moves by class",
          rep["raised_green_to_amber"] == {"general": 1, "instrumentation": 2}
          and model["meta"]["risk_model"]["safety_floor"]["marked"] == {"general": 1, "instrumentation": 6}, rep)


if __name__ == "__main__":
    main()
