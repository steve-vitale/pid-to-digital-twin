"""Background images for the drawing screens: the original OPEN100 sheets, greyed and downscaled.

The operator screens show each extracted sheet on top of the ORIGINAL drawing, not a redrawn one, so an operator
sees the drawing they know. Following ISA-101 practice, the drawing is pushed back to mid-grey on a light grey
background, so the live values are what stands out.

Source: PID2Graph, OPEN100 subset (CC BY-SA 4.0; see NOTICE). These are derived images under the same licence.
No model is involved: plain image processing.

  python scripts/ignition/prepare_drawings.py      # writes data/drawings/open100_<n>.jpg and thumb_<n>.jpg

Size matters more than it looks. Perspective has no image store reachable from the build, so the images go inside
the views as data URIs, and the gateway serializes the whole project for every browser that connects. At 1.5x
resolution with full-size thumbnails (5.2 MB of views) the trial gateway's 1 GB heap ran out while building that
update, and open screens silently kept their old views. Screen resolution and small thumbnails fixed it.
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
TWIN = ROOT / "out" / "twin" / "r2-tiles-trace" / "codex" / "plant_model.json"
OUT = ROOT / "data" / "drawings"
WIDTH, THUMB = 1400, 360  # the width the screen draws it at; the drawings index thumbnail
INK, PAPER = 80, 229  # black lines -> #505050, white paper -> #e5e5e5 (the screens' background grey)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for s in json.loads(TWIN.read_text(encoding="utf-8"))["systems"]:
        src = Image.open(SRC / s["image"]).convert("L").point(lambda v: INK + v * (PAPER - INK) // 255)
        for width, name, quality in ((WIDTH, "open100", 70), (THUMB, "thumb", 60)):
            im = src.resize((width, round(src.height * width / src.width)), Image.LANCZOS)
            path = OUT / f"{name}_{s['sheet']}.jpg"
            im.save(path, quality=quality, optimize=True)
            print(path.relative_to(ROOT).as_posix(), path.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
