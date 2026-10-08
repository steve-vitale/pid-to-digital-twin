"""Assemble the README demo animation (docs/demo.gif) from slides and live Ignition frames.

GitHub plays a GIF inline in a README; a video file only shows as a link. The story, about 30 seconds:
  1. the drawing, and what the twin extracted (docs/screenshots/before-after-sheet0.png)
  2. the extracted sheet in Ignition: mapped points live, the rest honestly not connected
  3. the live Tennessee Eastman screen through a fault-6 replay, until the reactor pressure alarm turns red
  4. how it was verified

The live frames are screenshots of the Perspective overview taken once a second while
`scripts/ignition/te_sim_server.py --run fault6 --start 236` runs (docs/IGNITION_QUICKSTART.md, step 6).

Usage: python scripts/make_demo_gif.py --frames <folder of f000.png ...> [--first 6] [--last 39]
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "screenshots"
W = 1000


def font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def frame(img, caption, sub=""):
    img = img.convert("RGB")
    h = int(img.height * W / img.width)
    img = img.resize((W, h), Image.LANCZOS)
    band = 64
    out = Image.new("RGB", (W, h + band), (15, 23, 42))
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    d.text((16, h + 8), caption, fill="white", font=font(22))
    if sub:
        d.text((16, h + 36), sub, fill=(148, 163, 184), font=font(16))
    return out


def card(title, lines, height):
    out = Image.new("RGB", (W, height), (15, 23, 42))
    d = ImageDraw.Draw(out)
    d.text((40, 60), title, fill="white", font=font(38))
    for i, line in enumerate(lines):
        d.text((40, 140 + 44 * i), line, fill=(203, 213, 225), font=font(24))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--last", type=int, default=10 ** 6)
    a = ap.parse_args()
    live = sorted(p for p in Path(a.frames).glob("f*.png") if a.first <= int(p.stem[1:]) <= a.last)
    if not live:
        raise SystemExit("no frames")
    seq = []
    ba = frame(Image.open(SHOTS / "before-after-sheet0.png"),
               "1. AI reads the symbols; code traces the lines; every item gets a risk tier",
               "A public OPEN100 drawing. Green: spot-check, amber: check quickly, red: look closely.")
    H = None
    sheet = frame(Image.open(SHOTS / "ignition-open100-sheet0-mapped.png").crop((0, 0, 1400, 760)),
                  "2. In Ignition: points mapped from an I/O list read live; the rest show 'not connected'",
                  "Nothing is invented: a placeholder never reads Good. (I/O list and values are a labeled demo.)")
    lives = []
    for i, p in enumerate(live):
        lives.append(frame(Image.open(p), "3. Live replay of the Tennessee Eastman plant, fault 6: loss of A feed",
                           "Reactor pressure (PI-107) crosses its 2,895 kPa limit; the label turns red from the "
                           "gateway's own alarm."))
    H = max(x.height for x in [ba, sheet] + lives)
    title = card("P&ID  →  digital twin in Ignition",
                 ["AI drafts the asset model from drawings, with honest scoring.",
                  "Operations review it; corrections flow back into the twin.",
                  "Ignition holds it, live, read-only, and a verifier proves it."], H)
    end = card("Verified, not assumed",
               ["9 checks against the running gateway, all pass:",
                "what it holds = what was sent · no false 'Good' · writes refused",
                "the alarm fires on the fault replay · every build backed up and in git.",
                "5 faults planted on purpose: all caught.",
                "github.com/steve-vitale/pid-to-digital-twin"], H)

    def fit(img):
        if img.height == H:
            return img
        out = Image.new("RGB", (W, H), (15, 23, 42))
        out.paste(img, (0, (H - img.height) // 2))
        return out

    seq = [(title, 3500), (fit(ba), 4500), (fit(sheet), 4500)]
    seq += [(fit(x), 400) for x in lives[:-1]] + [(fit(lives[-1]), 2500), (end, 5000)]
    frames = [img.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for img, _ in seq]
    out = ROOT / "docs" / "demo.gif"
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=[d for _, d in seq], loop=0,
                   optimize=True, disposal=1)
    print(f"wrote {out.relative_to(ROOT).as_posix()}: {len(frames)} frames, "
          f"{sum(d for _, d in seq) / 1000:.1f} s, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
