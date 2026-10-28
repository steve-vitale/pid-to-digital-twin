"""Does a generated sheet look like the house style it claims? Compare generated TE sheets with the 12 OPEN100 sheets.

The same measurements run on every sheet, OPEN100 and generated alike, and nothing here was tuned per sheet:
  from the answer keys (box sizes are relative to the sheet width, so sheets of different pixel sizes compare):
    instrument bubble width, valve width, off-page flag width and height, equipment (tank) width;
    scored symbols per sheet, off-page connectors per sheet, instruments as a share of scored symbols;
  from the images (binarized at 128):
    light and heavy line width in px (median and 90th percentile of the vertical thickness of horizontal line
    runs), small-text height as a share of sheet height (median height of character-sized blobs left after the
    long lines are removed), and ink coverage.
A generated value "sits inside" the style when it falls between the OPEN100 minimum and maximum per-sheet values.
Outside is reported, not hidden: the generated sheets draw only what the process model holds, so they are sparser
than OPEN100 sheets, which carry every drain, vent and manual valve.

Writes out/te_pid/style_fidelity.{json,md} and docs/screenshots/te-pid-style-side-by-side.png (an OPEN100 crop
next to a generated crop at the same pixel scale).

Usage: python scripts/style_fidelity.py
"""
import json
import statistics as st
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import score_pid2graph as sc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OPEN100 = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
TE = ROOT / "data" / "te_pid"
OUT = ROOT / "out" / "te_pid"


def key_metrics(png, graphml):
    w, h = sc.png_size(png)
    nodes, _ = sc.load_key(graphml, w, h)
    by = {}
    for n in nodes.values():
        b = n["box"]
        by.setdefault(n["class"], []).append(((b[2] - b[0]) / 1000, (b[3] - b[1]) / 1000 * h / w))
    med = lambda cls, k: round(st.median(v[k] for v in by[cls]), 4) if by.get(cls) else None  # noqa: E731
    scored = sum(len(by.get(c, [])) for c in sc.SCORED)
    return {"bubble_w": med("instrumentation", 0), "valve_w": med("valve", 0), "flag_w": med("inlet/outlet", 0),
            "flag_h": med("inlet/outlet", 1), "tank_w": med("tank", 0), "scored_symbols": scored,
            "offpage_flags": len(by.get("inlet/outlet", [])),
            "instrument_share": round(len(by.get("instrumentation", [])) / scored, 3) if scored else None}


def image_metrics(png):
    g = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    h, w = g.shape
    ink = (g < 128).astype(np.uint8)
    hor = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 60), 1)))
    runs = []
    for x in range(0, w, 3):
        d = np.diff(np.concatenate([[0], hor[:, x], [0]]))
        runs += list(np.where(d == -1)[0] - np.where(d == 1)[0])
    runs = np.array([r for r in runs if r <= 12])  # longer vertical runs are filled shapes, not lines
    ver = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, h // 40))))
    rest = ink & ~(hor | ver)
    n, _, stats, _ = cv2.connectedComponentsWithStats(rest)
    hs = [s[3] for s in stats[1:] if 0.003 * h < s[3] < 0.02 * h and 1 < s[2] < 1.5 * s[3]]
    return {"line_light_px": float(np.median(runs)), "line_heavy_px": float(np.percentile(runs, 90)),
            "text_h": round(float(np.median(hs)) / h, 4) if hs else None,
            "ink_pct": round(100 * float(ink.mean()), 2)}


def sheet_metrics(png, graphml):
    return {**key_metrics(png, graphml), **image_metrics(png)}


def side_by_side(dest):
    """OPEN100 sheet 6 (3196 px wide, densest 1000x700 window) next to generated sheet 101 (3200 px): same scale."""
    def densest(img, xmax):
        a = np.asarray(img.convert("L")) < 128
        best, box = -1, None
        for y in range(80, a.shape[0] - 780, 70):
            for x in range(80, xmax - 1000, 70):
                v = int(a[y:y + 700, x:x + 1000].sum())
                if v > best:
                    best, box = v, (x, y, x + 1000, y + 700)
        return img.crop(box).convert("RGB")
    left = densest(Image.open(OPEN100 / "6.png"), 2600)
    right = Image.open(TE / "101.png").crop((120, 230, 1120, 930)).convert("RGB")  # feed lines: flags, valves, bubbles
    sheet = Image.new("RGB", (2030, 760), "white")
    sheet.paste(left, (0, 60))
    sheet.paste(right, (1030, 60))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.load_default(size=26)
    d.text((10, 15), "OPEN100 sheet 6 (PID2Graph, CC BY-SA 4.0)", fill=0, font=f)
    d.text((1040, 15), "Generated from the TE model (sheet 101)", fill=0, font=f)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, optimize=True)


def main():
    o = {str(i): sheet_metrics(OPEN100 / f"{i}.png", OPEN100 / f"{i}.graphml") for i in range(12)}
    te_ids = sorted(p.stem for p in TE.glob("*.graphml"))
    t = {s: sheet_metrics(TE / f"{s}.png", TE / f"{s}.graphml") for s in te_ids}
    rows, inside, total = [], 0, 0
    for k in o["0"]:
        vals = [v[k] for v in o.values() if v[k] is not None]
        lo, hi = min(vals), max(vals)
        te_vals = [v[k] for v in t.values()]
        ok = [lo <= x <= hi for x in te_vals if x is not None]
        inside += sum(ok)
        total += len(ok)
        rows.append({"metric": k, "open100_min": lo, "open100_median": round(st.median(vals), 4), "open100_max": hi,
                     "generated": te_vals, "inside": f"{sum(ok)}/{len(ok)}"})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "style_fidelity.json").write_text(json.dumps({"open100": o, "generated": t, "summary": rows,
                                                         "inside": [inside, total]}, indent=1), encoding="utf-8")
    labels = {"bubble_w": "Instrument bubble width / sheet width", "valve_w": "Valve width / sheet width",
              "flag_w": "Off-page flag width / sheet width", "flag_h": "Off-page flag height / sheet width",
              "tank_w": "Equipment (tank) width / sheet width", "scored_symbols": "Scored symbols per sheet",
              "offpage_flags": "Off-page flags per sheet", "instrument_share": "Instruments / scored symbols",
              "line_light_px": "Light line width, px", "line_heavy_px": "Heavy line width (90th pct), px",
              "text_h": "Small-text height / sheet height", "ink_pct": "Ink coverage, %"}
    md = ["# Style fidelity: generated TE sheets vs the 12 OPEN100 sheets", "",
          "Generated by `scripts/style_fidelity.py`. Same measurements on every sheet; a generated value is inside "
          "the style when it lies between the OPEN100 per-sheet minimum and maximum.", "",
          f"**{inside} of {total} generated-sheet measurements sit inside the OPEN100 range.**", "",
          f"| Measure | OPEN100 min | median | max | Generated ({', '.join(te_ids)}) | Inside |", "|---|---|---|---|---|---|"]
    for r in rows:
        g = ", ".join("n/a" if x is None else f"{x:g}" for x in r["generated"])
        md.append(f"| {labels[r['metric']]} | {r['open100_min']:g} | {r['open100_median']:g} | {r['open100_max']:g} | "
                  f"{g} | {r['inside']} |")
    md += ["", "Reading it: symbol sizes, line weights and text height are the drafting style and should sit inside. "
           "Counts and ink coverage describe how much is on a sheet; the generated sheets draw only what the process "
           "model holds plus the drafting additions the layout declares (control valve stations: block valves and "
           "a bypass); they still have no drains, vents or reducers, so they can fall below the OPEN100 range there "
           "without being a style mismatch.", ""]
    (OUT / "style_fidelity.md").write_text("\n".join(md), encoding="utf-8")
    side_by_side(ROOT / "docs" / "screenshots" / "te-pid-style-side-by-side.png")
    print("\n".join(md))


if __name__ == "__main__":
    main()
