"""Pure 2D label geometry shared by the Blender tour script and the render verifier (stdlib only).

The generator embeds this file's source into the generated Blender script (between the markers below), so
placement in Blender and the checks in scripts/verify_3d_render.py use the same rectangle rules. Boxes are
(x0, y0, x1, y1) in pixels, origin top-left, y down.

Model use: none. Claude wrote this module; the thresholds are choices, documented in docs/3D_TOUR_PLAN.md.
"""
# --- embed-begin ---
import math as _m

# Legibility thresholds (chosen, not a standard except WCAG 2.x's 4.5:1 for normal-size text).
MIN_LINE_PX_1080 = 18.0     # text line height (box height / lines) at 1920x1080 (review requirement: >= 18 px)
MIN_CONTRAST = 4.5          # WCAG 2.x AA, normal text
OVERLAP_TOLERANCE_PX = 1.0  # boxes may touch; they may not overlap by more than this on both axes


def box_area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def overlap_area(a, b, tol=0.0):
    w = min(a[2], b[2]) - max(a[0], b[0]) - tol
    h = min(a[3], b[3]) - max(a[1], b[1]) - tol
    return w * h if w > 0 and h > 0 else 0.0


def outside_area(b, width, height):
    """Area of box b that falls outside the frame."""
    inside = (max(b[0], 0.0), max(b[1], 0.0), min(b[2], width), min(b[3], height))
    return box_area(b) - (box_area(inside) if inside[2] > inside[0] and inside[3] > inside[1] else 0.0)


def centred_box(cx, cy, w, h):
    return (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)


# Candidate directions, preferred first: above, above-right, above-left, right, left, below-right, below-left, below.
_ANGLES = (90, 60, 120, 30, 150, 0, 180, -30, -150, -90)


def place_labels(items, width, height, obstacles=(), margin=12.0, gap=6.0, max_radius=None):
    """Greedy, deterministic declutter. items: [{"id", "anchor": (x, y), "w", "h"}] in priority order.
    obstacles: boxes nothing may cover (caption band, marker dots). Returns {id: {"center", "box", "radius",
    "cost"}}; cost 0 means no overlap and fully inside the frame margin."""
    max_radius = max_radius or 0.45 * height
    frame = (margin, margin, width - margin, height - margin)
    placed, out = [], {}
    for it in items:
        ax, ay = it["anchor"]
        w, h = it["w"] + gap, it["h"] + gap
        best = None
        r = h / 2.0 + 10.0
        while r <= max_radius and (best is None or best[0] > 0):
            for ang in _ANGLES:
                rad = _m.radians(ang)
                # Elliptical step: wide labels move sideways by their half width, not their height.
                cx, cy = ax + _m.cos(rad) * (r + (w - h) / 2.0 * abs(_m.cos(rad))), ay - _m.sin(rad) * r
                b = centred_box(cx, cy, w, h)
                cost = sum(overlap_area(b, o) for o in list(obstacles) + placed)
                fx = (b[0] - frame[0], b[1] - frame[1], b[2] - frame[0], b[3] - frame[1])
                cost += 10.0 * outside_area(fx, frame[2] - frame[0], frame[3] - frame[1])
                if best is None or cost < best[0] - 1e-9:
                    best = (cost, (cx, cy), b, r)
                if cost == 0:
                    break
            r += max(12.0, h * 0.6)
        cost, centre, b, radius = best
        tight = centred_box(centre[0], centre[1], it["w"], it["h"])
        placed.append(b)
        out[it["id"]] = {"center": centre, "box": tight, "radius": radius, "cost": cost}
    return out


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    """WCAG 2.x relative luminance of an sRGB-encoded colour with channels in 0..1."""
    r, g, b = (srgb_to_linear(float(c)) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(l1, l2):
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def percentile(sorted_values, q):
    if not sorted_values:
        return float("nan")
    k = (len(sorted_values) - 1) * q
    f = int(_m.floor(k))
    c = min(f + 1, len(sorted_values) - 1)
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def text_contrast(luminances):
    """Polarity-agnostic text contrast heuristic for one label box: the background is the box's median luminance,
    the text is its brightest (97th percentile) or darkest (3rd percentile) pixels, whichever differs more.
    Valid while text strokes cover less than half the box, which holds for a tight label box."""
    v = sorted(luminances)
    bg, light, dark = percentile(v, 0.5), percentile(v, 0.97), percentile(v, 0.03)
    up, down = contrast_ratio(light, bg), contrast_ratio(dark, bg)
    return {"background": bg, "text": light if up >= down else dark, "ratio": max(up, down),
            "polarity": "light_on_dark" if up >= down else "dark_on_light"}
# --- embed-end ---


def embeddable_source():
    """The block above, for the generated Blender script (keeps it a single self-contained file)."""
    from pathlib import Path
    text = Path(__file__).read_text(encoding="utf-8")
    return text.split("# --- embed-begin ---", 1)[1].split("# --- embed-end ---", 1)[0]
