"""Before/after image for the README: a crop of a real OPEN100 drawing, and the same crop with what the twin
extracted drawn over it. Symbols are boxes coloured by their review risk tier (red / amber / green), and connections
are lines between symbol centres.

The drawing is from PID2Graph / OPEN100 (CC BY-SA 4.0), so this derived image is shared under CC BY-SA 4.0 too
(see NOTICE.md).

Usage: python scripts/make_before_after.py [--sheet 0] [--twin out/twin/r2-tiles-trace/codex]
Writes docs/screenshots/before-after-sheet<N>.png
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
TIER = {"red": (220, 38, 38), "amber": (217, 119, 6), "green": (22, 163, 74)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default="0")
    ap.add_argument("--twin", default="out/twin/r2-tiles-trace/codex")
    ap.add_argument("--crop", default="0.12,0.05,0.62,0.45", help="crop as fractions x0,y0,x1,y1 of the sheet")
    a = ap.parse_args()
    m = json.loads((ROOT / a.twin / "plant_model.json").read_text(encoding="utf-8"))
    img = Image.open(DATA / f"{a.sheet}.png").convert("RGB")
    W, H = img.size
    fx0, fy0, fx1, fy1 = map(float, a.crop.split(","))
    box = (int(fx0 * W), int(fy0 * H), int(fx1 * W), int(fy1 * H))

    over = img.copy()
    d = ImageDraw.Draw(over, "RGBA")
    centres, counts = {}, {"red": 0, "amber": 0, "green": 0}
    items = m["units"] + m["instruments"] + m["line_items"] + m["offpage_connectors"]
    for it in items:
        for p in it["provenance"]:
            if p["sheet"] != a.sheet:
                continue
            b = p["box_0_1000"]
            x0, y0, x1, y1 = b[0] / 1000 * W, b[1] / 1000 * H, b[2] / 1000 * W, b[3] / 1000 * H
            centres[p["symbol"]] = ((x0 + x1) / 2, (y0 + y1) / 2)
            tier = (it.get("risk") or {}).get("tier", "amber")
            if box[0] <= (x0 + x1) / 2 <= box[2] and box[1] <= (y0 + y1) / 2 <= box[3]:
                counts[tier] += 1
            d.rectangle([x0 - 3, y0 - 3, x1 + 3, y1 + 3], outline=TIER[tier] + (255,), width=4)
    for st in m["streams"]:
        if st.get("sheet") != a.sheet:
            continue
        p, q = centres.get(st.get("from_symbol")), centres.get(st.get("to_symbol"))
        if p and q:
            # Faint on purpose: the tracer links every symbol on a shared pipe network to every other one, so a
            # network with many symbols becomes a dense web of centre-to-centre lines. The symbols are the subject.
            d.line([p, q], fill=(100, 116, 139, 45), width=2)

    left, right = img.crop(box), over.crop(box)
    w, h = left.size
    scale = 1200 / w
    left = left.resize((1200, int(h * scale)), Image.LANCZOS)
    right = right.resize((1200, int(h * scale)), Image.LANCZOS)
    pad, band = 20, 70
    sheet = Image.new("RGB", (2 * 1200 + 3 * pad, left.height + band + 60), "white")
    sheet.paste(left, (pad, band))
    sheet.paste(right, (2 * pad + 1200, band))
    t = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 30)
        small = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = small = ImageFont.load_default()
    t.text((pad, 18), "Before: the drawing (OPEN100, public)", fill=(31, 41, 55), font=font)
    t.text((2 * pad + 1200, 18), "After: what the twin extracted, coloured by review risk", fill=(31, 41, 55), font=font)
    x = 2 * pad + 1200
    for tier in ("red", "amber", "green"):
        label = {"red": "red: look closely", "amber": "amber: check quickly", "green": "green: spot-check"}[tier]
        t.rectangle([x, left.height + band + 20, x + 18, left.height + band + 38], outline=TIER[tier], width=4)
        t.text((x + 26, left.height + band + 16), label, fill=TIER[tier], font=small)
        x += 300
    t.text((pad, left.height + band + 16), "Grey lines: extracted connections, drawn centre to centre",
           fill=(100, 116, 139), font=small)
    out = ROOT / "docs" / "screenshots" / f"before-after-sheet{a.sheet}.png"
    sheet.save(out, optimize=True)
    print(f"wrote {out.relative_to(ROOT).as_posix()} ({sheet.size[0]}x{sheet.size[1]}); in crop: {counts}")


if __name__ == "__main__":
    main()
