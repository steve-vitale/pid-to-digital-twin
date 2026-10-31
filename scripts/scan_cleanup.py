"""Scan clean-up before line tracing: turn a degraded scan (faded grey ink, blur, speckle, yellowed or uneven paper,
JPEG noise, worn patches) into a black-on-white image the tracer's own binarization reads as drawn, and leave clean
drawings alone. No AI calls, no network; OpenCV and numpy only.

Why. On degraded copies of the OPEN100 sheets the tracer's single global (Otsu) threshold drops thin faint lines and
keeps the speckle (docs/TRIED.md, scan_robustness: A049-A052 put the round-4 failure in the code tracer). Every
quantity below comes from the image itself (its background, its noise, its stroke width, its size), never from the
damage level; the defaults were chosen on degraded copies of the development sheets OPEN100 0-5 only (data/attempts.json,
the scan_robustness entries from A176 on).

Detection ("auto"). A sheet counts as a degraded scan when either
  - it has isolated specks: ink components of at most 4 px with no other ink within 3 px, at least SPECKS_PER_MP per
    million pixels (clean renders here: 0-32; degraded copies: 1,600 and up), or
  - its paper is not one flat value: less than FLAT_MIN of the pixels within 1 grey level of the commonest value
    (clean renders: 0.77 and up; old-scan copies: below 0.2).
Otherwise the image is traced exactly as given, so clean drawings are unchanged by construction. Limit: a blurred or
faded scan on perfectly flat paper with no specks is not detected (use clean="on").

Clean-up ("on", or "auto" on a detected scan):
  1. Background: a closing wider than any stroke, smoothed, estimates the paper (tint, gradients, yellowing); each
     pixel's darkness is how far it sits below that paper.
  2. Stroke cores (half-maximum): a pixel is ink when it is at least half as dark as the darkest pixel within one
     stroke width (peaks and dips are measured on the darkness after a 3x3 median, so a speck on a line is not a peak), and that local peak clears a contrast floor (LOW_FRAC of the Otsu threshold of the darkness).
     Cutting each stroke at half its own peak keeps the gaps between blurred strokes (text beside a line, a line that
     stops short of another).
  3. Specks: components smaller than AREA_MULT x stroke width squared are dropped.
  4. Faint straight lines (hysteresis + runs): seeds are speck-free strong ink; weak pixels (HYST_LOW of the Otsu
     threshold) connected to a seed are grown; horizontal and vertical runs at least RUN_FRAC of the sheet's long
     side are taken from that grown ink and added back, each cut to the pixels at least half as dark as the
     darkest across the run (so the run is not fattened) and never through a dip: a pixel less than DIP x as dark
     as the darkest pixel on BOTH sides along the run within DIP_MULT stroke widths is a gap the drawing left (a
     line stopping short of a crossing line), not a faded stretch, so it is not bridged. Within DIP_MULT stroke
     widths of a perpendicular line, where the gap is short and blur makes its dip shallow, any pixel the stroke
     cores missed that is under DIP_NEAR x both neighbours is left unbridged too (perp_guard): the drafting
     convention that a line stopping short of another is not connected to it survives the blur, while a real tee
     (darkness rising steadily into the line it meets) is still bridged.
Output: a 0/255 image; the tracer's Otsu step reads it back unchanged.

Library:  is_degraded(gray) -> {"degraded": bool, "specks_per_mp", "flat", ...}
          clean_gray(gray, **params) -> uint8 0/255 image
          prepare(gray, clean="auto"|"on"|"off") -> (image, cleaned: bool)
          trace(image_path, symbols, clean="auto", info=None, **tracer_options) -> trace_connections.trace's links on
              the cleaned image (or on the original file when nothing is cleaned)
CLI:      python scripts/scan_cleanup.py <image> [--out cleaned.png] [--clean auto|on]   (prints the detection)
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np

SPECKS_PER_MP = 300   # isolated specks per million pixels that mark a scan (clean renders <= 32, damaged >= 1,600)
FLAT_MIN = 0.5        # share of pixels within 1 level of the commonest value below which the paper is not flat

PARAMS = {            # chosen on degraded copies of OPEN100 0-5 only (A176 split); every length scales with the image
    "bg_kernel_frac": 0.0065,  # background closing kernel, fraction of the long side (15 px on a 2,290 px sheet)
    "frac": 0.5,        # stroke core: at least this share of the local peak darkness
    "low_frac": 0.4,    # contrast floor for a stroke's peak, share of the Otsu threshold of the darkness
    "area_mult": 4.0,   # specks: components below area_mult x stroke width^2 are dropped
    "hyst_low": 0.35,   # hysteresis growth floor, share of the Otsu threshold
    "run_frac": 0.008,  # straight runs at least this share of the long side are bridged through faint stretches
    "dip": 0.6,         # ...but not through a dip: darker on neither side than dip x both neighbours
    "dip_mult": 3.0,    # ...looking dip_mult stroke widths each way along the run
    "perp_guard": True, # within dip_mult stroke widths of a perpendicular line the run is not bridged where the
    "dip_near": 0.9,    # ...stroke core is missing and the pixel is under dip_near x both neighbours (a shallow dip)
}


def _darkness(gray, k):
    bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    bg = cv2.blur(bg, (2 * k + 1, 2 * k + 1)).astype(np.float32)
    return np.clip(bg - gray.astype(np.float32), 0, None)


def _bg_kernel(gray, frac):
    return max(5, int(round(frac * max(gray.shape))) | 1)


def is_degraded(gray):
    """Whether the image looks like a damaged scan (see the module docstring); the measurements say why."""
    d = _darkness(gray, _bg_kernel(gray, PARAMS["bg_kernel_frac"]))
    d8 = np.clip(d, 0, 255).astype(np.uint8)
    _, s = cv2.threshold(d8, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    n, lab, st, _ = cv2.connectedComponentsWithStats(s, connectivity=8)
    small = st[:, 4] <= 4
    small[0] = False
    rest = (~small[lab]) & (s > 0)
    near = cv2.dilate(rest.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    specks = int((small & (np.bincount(lab[near], minlength=n) == 0)).sum())
    hist = np.bincount(gray.ravel(), minlength=256)
    m = int(hist.argmax())
    flat = float(hist[max(0, m - 1):m + 2].sum()) / gray.size
    per_mp = specks / (gray.size / 1e6)
    return {"degraded": bool(per_mp >= SPECKS_PER_MP or flat < FLAT_MIN), "specks_per_mp": round(per_mp, 1),
            "flat": round(flat, 3), "paper_value": m}


def _stroke_width(ink):
    dt = cv2.distanceTransform(ink, cv2.DIST_L2, 3)
    ridge = dt[(dt > 0) & (dt >= cv2.dilate(dt, np.ones((3, 3))) - 1e-6)]
    return max(1.0, 2 * float(np.median(ridge))) if len(ridge) else 1.0


def _side_max(d, r, axis):
    """Max of d over the r pixels before and the r pixels after each pixel along an axis (0 = x, 1 = y); outside
    the image counts as paper (0)."""
    if axis == 0:
        k = np.ones((1, r + 1), np.uint8)
        k[0, r] = 0
        return (cv2.dilate(d, k, anchor=(r, 0), borderType=cv2.BORDER_CONSTANT, borderValue=0),
                cv2.dilate(d, k[:, ::-1].copy(), anchor=(0, 0), borderType=cv2.BORDER_CONSTANT, borderValue=0))
    k = np.ones((r + 1, 1), np.uint8)
    k[r, 0] = 0
    return (cv2.dilate(d, k, anchor=(0, r), borderType=cv2.BORDER_CONSTANT, borderValue=0),
            cv2.dilate(d, k[::-1, :].copy(), anchor=(0, 0), borderType=cv2.BORDER_CONSTANT, borderValue=0))


def clean_gray(gray, info=None, **params):
    p = {**PARAMS, **params}
    d = _darkness(gray, _bg_kernel(gray, p["bg_kernel_frac"]))
    d8 = np.clip(d, 0, 255).astype(np.uint8)
    t, strong = cv2.threshold(d8, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    w = _stroke_width(strong)
    r = max(1, int(round(w)))
    min_area = p["area_mult"] * w * w
    ref = cv2.medianBlur(d, 3)  # the darkness without single-pixel specks: what peaks and dips are measured against

    # 2-3. stroke cores at half their own peak, specks dropped
    peak = cv2.dilate(ref, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    core = ((d >= p["frac"] * peak) & (peak > p["low_frac"] * t) & (d > 0.5 * p["low_frac"] * t)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(core, connectivity=8)
    keep = st[:, 4] >= min_area
    keep[0] = False
    ink = keep[lab].astype(np.uint8)

    # 4. faint straight lines: hysteresis from speck-free strong ink, then H/V runs, cut thin, never across a dip
    n, lab, st, _ = cv2.connectedComponentsWithStats(strong, connectivity=8)
    big = st[:, 4] >= min_area
    big[0] = False
    seeds = big[lab].astype(np.uint8)
    weak = (d > p["hyst_low"] * t).astype(np.uint8) | seeds
    n, lab = cv2.connectedComponents(weak, connectivity=8)
    seeded = np.zeros(n, bool)
    seeded[np.unique(lab[seeds > 0])] = True
    seeded[0] = False
    grown = seeded[lab].astype(np.uint8)
    run = max(5, int(round(p["run_frac"] * max(gray.shape))))
    rr, rg = r + 1, max(2, int(round(p["dip_mult"] * w)))
    core_ink = ink.copy()
    perp = {}
    if p["perp_guard"]:
        # straight runs of the core ink, for the guard below: a bridged run may not newly reach a perpendicular line
        perp[0] = cv2.morphologyEx(core_ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, run)))
        perp[1] = cv2.morphologyEx(core_ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (run, 1)))
    for axis, kern, across in ((0, (run, 1), (1, 2 * rr + 1)), (1, (1, run), (2 * rr + 1, 1))):
        runs = cv2.morphologyEx(grown, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, kern))
        thin = d >= p["frac"] * cv2.dilate(ref, cv2.getStructuringElement(cv2.MORPH_RECT, across))
        a, b = _side_max(ref, rg, axis)
        dip = d < p["dip"] * np.minimum(a, b)
        add = runs.astype(bool) & thin & ~dip
        if p["perp_guard"]:
            k = (2 * rg + 1, 1) if axis == 0 else (1, 2 * rg + 1)
            near = cv2.dilate(perp[axis], cv2.getStructuringElement(cv2.MORPH_RECT, k)) > 0
            add &= ~(near & (core_ink == 0) & (d < p["dip_near"] * np.minimum(a, b)))
        ink |= add.astype(np.uint8)
    if info is not None:
        info.update({"otsu": int(t), "stroke_width": round(w, 1), "run_px": run, "ink_share": round(float(ink.mean()), 4)})
    return (255 - ink * 255).astype(np.uint8)


def prepare(gray, clean="auto", info=None):
    """(image to trace, whether it was cleaned). clean: "off" never, "on" always, "auto" when is_degraded."""
    if clean not in ("off", "auto", "on"):
        raise ValueError(f"clean must be off, auto or on, not {clean!r}")
    if clean == "off":
        return gray, False
    if clean == "auto":
        det = is_degraded(gray)
        if info is not None:
            info["detection"] = det
        if not det["degraded"]:
            return gray, False
    return clean_gray(gray, info=info), True


def trace(image_path, symbols, clean="auto", info=None, **opt):
    """trace_connections.trace with the clean-up in front. When nothing is cleaned the original file is traced, so
    the links are exactly the tracer's own."""
    import trace_connections as tc
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise FileNotFoundError(image_path)
    info = {} if info is None else info
    out, cleaned = prepare(gray, clean, info)
    info["cleaned"] = cleaned
    if not cleaned:
        return tc.trace(image_path, symbols, **opt)
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        cv2.imwrite(tmp, out)  # PNG, lossless; same size, so the symbols' 0-1000 boxes still fit
        return tc.trace(tmp, symbols, **opt)
    finally:
        os.unlink(tmp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("image")
    ap.add_argument("--out")
    ap.add_argument("--clean", default="auto", choices=["auto", "on", "off"])
    a = ap.parse_args(argv)
    if a.out:
        from output_paths import protect_outputs
        try:
            protect_outputs([a.out], [a.image])
        except ValueError as exc:
            ap.exit(2, f"refused: {exc}\n")
    gray = cv2.imread(a.image, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise SystemExit(f"cannot read {a.image}")
    info = {}
    out, cleaned = prepare(gray, a.clean, info)
    info["cleaned"] = cleaned
    print(json.dumps(info))
    if a.out:
        if not cv2.imwrite(a.out, out):
            ap.exit(2, f"cannot write {a.out}\n")
        print("wrote", Path(a.out))


if __name__ == "__main__":
    main()
