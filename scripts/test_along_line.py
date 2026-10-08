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
import sys
import tempfile
from pathlib import Path

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
    print(f"{len(fails)} failed" if fails else "all passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
