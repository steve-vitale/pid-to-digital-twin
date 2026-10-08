"""Make "old scan" versions of the holdout-A drawings, to test how the declared method holds up on archive-quality
images (docs/GOAL.md, round 4).

Every operation keeps geometry fixed (no rotation, crop or resize of the canvas), so the original answer keys stay
valid. Levels are cumulative and seeded per drawing, so the images are reproducible:

  L1 photocopy   ink faded toward grey, slight blur, light speckle
  L2 old scan    plus: halved resolution (down and back up), JPEG artifacts, yellowed uneven background
  L3 bad scan    plus: 40% of the resolution, heavier JPEG and speckle, patches where the lines fade out

Not covered: skew and rotation (the keys would need transforming), handwriting, stamps over symbols, torn edges.

Writes data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100 scan-L<n>/ (images + copied keys) and a
side-by-side crop to docs/screenshots/scan-levels.png.

Usage: python scripts/degrade_scans.py
"""
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
COMPLETE = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete"
SRC = COMPLETE / "PID2Graph OPEN100"
DRAWINGS = [6, 7, 8, 9, 10, 11]  # holdout A
SEED = 20261008
LEVELS = {
    1: {"fade": 0.25, "blur": 0.8, "speckle": 0.002, "scale": 1.0, "jpeg": None, "yellow": 0.0, "dropout": 0},
    2: {"fade": 0.35, "blur": 1.0, "speckle": 0.004, "scale": 0.5, "jpeg": 45, "yellow": 0.10, "dropout": 0},
    3: {"fade": 0.45, "blur": 1.2, "speckle": 0.008, "scale": 0.4, "jpeg": 25, "yellow": 0.15, "dropout": 40},
}


def degrade(img, p, rng):
    w, h = img.size
    g = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
    # Fade: dark ink moves toward grey.
    g = 1.0 - (1.0 - g) * (1.0 - p["fade"])
    # Line dropout: rectangular patches where ink fades further (worn originals, uneven toner).
    for _ in range(p["dropout"]):
        pw, ph = int(rng.integers(w // 40, w // 12)), int(rng.integers(h // 40, h // 12))
        x, y = int(rng.integers(0, w - pw)), int(rng.integers(0, h - ph))
        g[y:y + ph, x:x + pw] = 1.0 - (1.0 - g[y:y + ph, x:x + pw]) * 0.35
    im = Image.fromarray(np.clip(g * 255, 0, 255).astype(np.uint8))
    im = im.filter(ImageFilter.GaussianBlur(p["blur"]))
    if p["scale"] < 1.0:
        small = im.resize((max(1, int(w * p["scale"])), max(1, int(h * p["scale"]))), Image.BILINEAR)
        im = small.resize((w, h), Image.BILINEAR)
    a = np.asarray(im, dtype=np.float32)
    # Speckle: random dark dots.
    mask = rng.random(a.shape) < p["speckle"]
    a[mask] = rng.uniform(40, 140, int(mask.sum()))
    rgb = np.stack([a, a, a], axis=-1)
    if p["yellow"]:
        # Yellowed, uneven paper: a smooth gradient tint over the background.
        yy, xx = np.mgrid[0:h, 0:w]
        grad = (0.6 + 0.4 * (xx / w)) * p["yellow"]
        rgb[..., 2] *= (1 - grad)
        rgb[..., 1] *= (1 - grad * 0.35)
    out = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
    if p["jpeg"]:
        import io
        buf = io.BytesIO()
        out.save(buf, "JPEG", quality=p["jpeg"])
        out = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    return out


def main():
    crops = []
    for level, p in LEVELS.items():
        dest = COMPLETE / f"PID2Graph OPEN100 scan-L{level}"
        dest.mkdir(parents=True, exist_ok=True)
        for d in DRAWINGS:
            rng = np.random.default_rng(SEED + 100 * level + d)
            img = Image.open(SRC / f"{d}.png")
            out = degrade(img, p, rng)
            out.save(dest / f"{d}.png")
            shutil.copy(SRC / f"{d}.graphml", dest / f"{d}.graphml")
            if d == 6:
                crops.append(out)
        print(f"L{level}: wrote {len(DRAWINGS)} drawings to {dest.relative_to(ROOT)}")
    # Side-by-side crop of drawing 6: clean, L1, L2, L3.
    clean = Image.open(SRC / "6.png").convert("RGB")
    w, h = clean.size
    ink = np.asarray(clean.convert("L")) < 128  # crop where the drawing is densest, so the preview shows detail
    best, box = -1, None
    for y in range(0, h - 420, 105):
        for x in range(0, int(w * 0.65) - 600, 150):  # left of the title block
            n = int(ink[y:y + 420, x:x + 600].sum())
            if n > best:
                best, box = n, (x, y, x + 600, y + 420)
    tiles = [clean.crop(box)] + [c.crop(box) for c in crops]
    sheet = Image.new("RGB", (600 * 4 + 30, 420), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * 610, 0))
    out = ROOT / "docs" / "screenshots" / "scan-levels.png"
    sheet.save(out)
    print("preview:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
