"""Generate the OPEN100 structural deliverables' screens and stills: the mimic views (as a Perspective view export
plus an offline HTML render) and the LOTO isolation view on the real drawing.

  python scripts/render_open100_structural.py            # views + HTML + LOTO stills
  python scripts/render_open100_structural.py --png      # also screenshot the HTML with a headless browser

Inputs: out/open100_structural/plant_structure.json (scripts/open100_structure.py) and the existing OPEN100 tag
provider (out/ignition/gateway/twin_provider.json), so value bindings point at the same tags the drawing screens use.
The HTML is the same offline renderer the TE preview uses (scripts/preview_mimic.py: transforms run in CPython). It
is NOT a Perspective runtime or gateway screenshot, and every still says so.
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ignition"))
import build_open100_mimic  # noqa: E402
from preview_mimic import render  # noqa: E402

OUT = ROOT / "out" / "open100_structural"
SHOTS = ROOT / "docs" / "screenshots" / "open100"
DRAWINGS = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
BANNER = "OFFLINE RENDER OF THE PERSPECTIVE VIEW / NOT A GATEWAY SCREENSHOT / STRUCTURE ONLY, NO PROCESS DATA"
LOTO_FRAME = ("DESIGN MOCKUP, NOT A PROCEDURE. Isolation points are read from the extracted symbols of this drawing and "
              "are unverified. A real lockout/tagout procedure comes from the site's energy-control program "
              "(OSHA 1910.147), its verified P&IDs and an authorized person.")
LOTO_STYLE = {  # kind -> (outline colour, legend text)
    "manual_block_valve": ((200, 30, 30), "Manual valve in a line: candidate block valve"),
    "motor_operated_valve": ((200, 30, 30), "Motor-operated valve: isolation point + its own electrical energy"),
    "motor_driven_equipment": ((150, 40, 170), "Motor-driven equipment: electrical isolation at its breaker"),
    "boundary_connection": ((30, 90, 220), "Line from another system: isolate there or at the first block valve"),
    "vent_drain_connection": ((0, 140, 60), "Line to a vent or drain system"),
    "vent_drain_or_test": ((0, 140, 60), "One-connection valve: likely vent, drain or test point"),
    "control_valve": ((120, 120, 120), "Control valve: NOT an isolation device on its own"),
    "relief_device": ((230, 140, 0), "Relief device: never use for isolation"),
}


def page(title, body, height):
    return ("<!doctype html><meta charset='utf-8'><title>%s</title><style>body{margin:0;background:#e5e5e5;"
            "font-family:Arial;color:#1f2937}aside{padding:10px 24px;background:#25313d;color:white;font-size:14px;"
            "width:1552px}#canvas{position:relative;width:1600px;height:%dpx}</style><aside>%s</aside>"
            "<main id='canvas'>%s</main><script>function navigate(r){}</script>" % (html.escape(title), height,
                                                                                  html.escape(BANNER), body))


def browser():
    for p in (os.environ.get("BROWSER_EXE"), shutil.which("msedge"), shutil.which("chrome"), shutil.which("chromium"),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if p and Path(p).exists():
            return p
    return None


def screenshot(html_path, png_path, height):
    exe = browser()
    if not exe:
        print("no headless browser found (set BROWSER_EXE); skipped", png_path.name)
        return False
    png_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--window-size=1600,%d" % (height + 42), "--screenshot=" + str(png_path),
                    html_path.resolve().as_uri()], check=True, capture_output=True, timeout=120)
    return True


def loto_still(structure, sheet, path, crop=None):
    """The isolation points of one sheet drawn on the ORIGINAL drawing, numbered, with the mockup framing."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(DRAWINGS / f"{sheet}.png").convert("RGB")
    W, H = im.size
    im = Image.blend(im, Image.new("RGB", im.size, "white"), 0.35)
    pts = [p for p in structure["isolation_points"] if p["sheet"] == sheet]
    x0, y0, x1, y1 = crop or (0, 0, 1000, 1000)
    X0, Y0, X1, Y1 = int(x0 * W / 1000), int(y0 * H / 1000), int(x1 * W / 1000), int(y1 * H / 1000)
    pts = [p for p in pts if x0 <= (p["box_0_1000"][0] + p["box_0_1000"][2]) / 2 <= x1
           and y0 <= (p["box_0_1000"][1] + p["box_0_1000"][3]) / 2 <= y1]
    order = list(LOTO_STYLE)
    pts.sort(key=lambda p: (order.index(p["kind"]), p["box_0_1000"][1], p["box_0_1000"][0]))
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arialbd.ttf", 18)
        small = ImageFont.truetype("arial.ttf", 17)
        big = ImageFont.truetype("arialbd.ttf", 22)
    except OSError:
        font = small = big = ImageFont.load_default()
    for n, p in enumerate(pts, 1):
        b = p["box_0_1000"]
        q = (b[0] * W / 1000 - 4, b[1] * H / 1000 - 4, b[2] * W / 1000 + 4, b[3] * H / 1000 + 4)
        col = LOTO_STYLE[p["kind"]][0]
        dr.rectangle(q, outline=col, width=4)
        tx, ty = q[2] + 2, q[1] - 22
        dr.rectangle((tx, ty, tx + 12 + 11 * len(str(n)), ty + 22), fill=col)
        dr.text((tx + 5, ty + 1), str(n), fill="white", font=font)
    im = im.crop((X0, Y0, X1, Y1))
    legend_rows = []
    for k in order:
        n = [i for i, p in enumerate(pts, 1) if p["kind"] == k]
        if n:
            legend_rows.append((k, "%s (%d): %s" % (LOTO_STYLE[k][1], len(n), ", ".join(map(str, n[:14])) +
                                                     (" ..." if len(n) > 14 else ""))))
    pad = 16
    top_h = 74
    leg_h = 28 * len(legend_rows) + 2 * pad
    canvas = Image.new("RGB", (im.size[0], im.size[1] + top_h + leg_h), "white")
    canvas.paste(im, (0, top_h))
    d2 = ImageDraw.Draw(canvas)
    d2.rectangle((0, 0, canvas.size[0], top_h), fill=(80, 20, 15))
    area = next(a for a in structure["areas"] if a["sheet"] == sheet)
    d2.text((pad, 10), "LOTO isolation view (design mockup) · OPEN100 sheet %s · %s" % (sheet, area["label"]),
            fill="white", font=big)
    words, line, lines = LOTO_FRAME.split(), "", []
    for w in words:
        if d2.textlength(line + " " + w, font=small) > canvas.size[0] - 2 * pad:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    lines.append(line)
    for i, l in enumerate(lines[:2]):
        d2.text((pad, 38 + i * 18), l, fill=(255, 230, 220), font=small)
    y = im.size[1] + top_h + pad
    for k, text in legend_rows:
        d2.rectangle((pad, y + 3, pad + 18, y + 21), outline=LOTO_STYLE[k][0], width=4)
        d2.text((pad + 28, y + 2), text, fill=(31, 41, 55), font=small)
        y += 28
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", action="store_true", help="screenshot the HTML renders with a headless browser")
    ap.add_argument("--area", default="7", help="area (sheet) for the level-2 still")
    ap.add_argument("--loto-sheet", default="7")
    ap.add_argument("--loto-crop", default="0,0,1000,1000", help="x0,y0,x1,y1 on the 0-1000 frame")
    a = ap.parse_args()
    structure = json.loads((OUT / "plant_structure.json").read_text(encoding="utf-8"))
    dirs = json.loads((OUT / "flow_direction.json").read_text(encoding="utf-8"))
    model = json.loads((ROOT / "out/twin/r2-tiles-trace/codex/plant_model.json").read_text(encoding="utf-8"))
    meta = json.loads((ROOT / "out/ignition/gateway/build_meta.json").read_text(encoding="utf-8"))
    provider_doc = json.loads((ROOT / "out/ignition/gateway/twin_provider.json").read_text(encoding="utf-8"))
    vs = build_open100_mimic.views(structure, model, provider_doc, meta["provider"], dirs)
    mdir = OUT / "mimic"
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / "views.json").write_text(json.dumps(vs, indent=1), encoding="utf-8")
    renders = {}
    for name, v in vs.items():
        h = v["props"]["defaultSize"]["height"]
        fn = mdir / (name.split("/")[1].lower() + ".html")
        fn.write_text(page(name, render(v, {}, {}, False), h), encoding="utf-8")
        renders[name] = (fn, h)
    print("wrote", len(vs), "views and HTML renders to", mdir)
    if a.png:
        for name, png in (("OPEN100/Plant", "mimic-plant-overview.png"),
                          ("OPEN100/Area_" + a.area, "mimic-area-sheet%s.png" % a.area)):
            fn, h = renders[name]
            if screenshot(fn, SHOTS / png, h):
                print("still", SHOTS / png)
    pts = loto_still(structure, a.loto_sheet, SHOTS / ("loto-isolation-sheet%s.png" % a.loto_sheet),
                     [float(v) for v in a.loto_crop.split(",")])
    print("LOTO still: %d isolation points on sheet %s" % (len(pts), a.loto_sheet))


if __name__ == "__main__":
    main()
