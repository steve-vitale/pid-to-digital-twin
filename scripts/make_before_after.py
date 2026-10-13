"""Before/after image for the README: a crop of a real OPEN100 drawing, and the same crop with what the twin
extracted drawn over it. Symbols are boxes coloured by their review risk tier (red / amber / green), and connections
are lines between symbol centres.

The drawing is from PID2Graph / OPEN100 (CC BY-SA 4.0), so this derived image is shared under CC BY-SA 4.0 too
(see NOTICE.md).

Usage: python scripts/make_before_after.py [--sheet 0] [--twin out/twin/r2-tiles-trace/codex]
Writes docs/screenshots/before-after-sheet<N>.png

  python scripts/make_before_after.py --social
Writes docs/social-preview.png instead: the 1280x640 GitHub social preview card (the "after" view of a crop of
sheet 0, plus the title and the round-2 headline number from docs/GOAL.md). Upload it in the repository's
Settings, under Social preview.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
TIER = {"red": (220, 38, 38), "amber": (217, 119, 6), "green": (22, 163, 74)}
SOCIAL_CROP = "0.30,0.08,0.52,0.40"   # fractions of sheet 0; keeps the boxes readable at thumbnail size


def font(size, bold=False):
    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def social_card(after):
    """1280x640 card: the extracted overlay on the left 55%, plain text on white on the right. The text makes no
    claim beyond the scored benchmark: no operations review, PI import or live plant data."""
    W, H, split = 1280, 640, 704
    card = Image.new("RGB", (W, H), "white")
    w, h = after.size
    scale = max(split / w, H / h)
    after = after.resize((int(w * scale) + 1, int(h * scale) + 1), Image.LANCZOS)
    x0, y0 = (after.width - split) // 2, (after.height - H) // 2
    card.paste(after.crop((x0, y0, x0 + split, y0 + H)), (0, 0))
    t = ImageDraw.Draw(card)
    t.line([(split, 0), (split, H)], fill=(209, 213, 219), width=2)
    x, right = split + 44, W - 40
    grey, dark = (75, 85, 99), (17, 24, 39)

    def fit(text, size, bold=False):
        f = font(size, bold)
        while t.textlength(text, font=f) > right - x and size > 12:
            size -= 2
            f = font(size, bold)
        return f

    y = 120
    f = fit("P&ID to digital twin", 60, bold=True)
    t.text((x, y), "P&ID to digital twin", fill=dark, font=f)
    y += 92
    for line in ("AI reads the symbols. Code traces the lines.", "Scored on sealed public drawings."):
        t.text((x, y), line, fill=grey, font=fit(line, 28))
        y += 40
    y += 40
    t.text((x, y), "48.8 → 17.8", fill=dark, font=font(44, bold=True))
    y += 58
    for line in ("corrections per 100 items, sealed set A,", "best model alone vs. with tiling + tracing"):
        t.text((x, y), line, fill=grey, font=fit(line, 20))
        y += 28
    t.text((x, H - 122), "review risk:", fill=grey, font=font(20))
    for i, tier in enumerate(("red", "amber", "green")):
        bx = x + 128 + i * 110
        t.rectangle([bx, H - 118, bx + 16, H - 102], outline=TIER[tier], width=4)
        t.text((bx + 24, H - 122), tier, fill=TIER[tier], font=font(20))
    t.text((x, H - 70), "github.com/steve-vitale/pid-to-digital-twin", fill=(107, 114, 128),
           font=fit("github.com/steve-vitale/pid-to-digital-twin", 20))
    out = ROOT / "docs" / "social-preview.png"
    card.save(out, optimize=True)
    print(f"wrote {out.relative_to(ROOT).as_posix()} ({W}x{H}, {out.stat().st_size // 1024} KB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default="0")
    ap.add_argument("--twin", default="out/twin/r2-tiles-trace/codex")
    ap.add_argument("--crop", default=None, help="crop as fractions x0,y0,x1,y1 of the sheet")
    ap.add_argument("--social", action="store_true", help="write the 1280x640 social preview card instead")
    a = ap.parse_args()
    if a.crop is None:
        a.crop = SOCIAL_CROP if a.social else "0.12,0.05,0.62,0.45"
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

    if a.social:
        return social_card(over.crop(box))
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
