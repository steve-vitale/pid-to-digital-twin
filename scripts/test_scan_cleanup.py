"""Scan clean-up before tracing (scripts/scan_cleanup.py), on small drawn images: a clean drawing is detected as clean
and traced exactly as without the step; speckle or an uneven background marks a sheet as a degraded scan; on a
degraded copy the step removes isolated specks, carries a faded line through a worn patch, and keeps the gap a line
leaves where it stops short of another line (so two networks the drawing keeps apart stay apart). Needs OpenCV and
numpy (as the tracer does); no model calls, no network."""
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import scan_cleanup as scl  # noqa: E402
import trace_connections as tc  # noqa: E402

SIZE = 1000


def pairs(links):
    return {tuple(sorted((x["from"], x["to"]))) for x in links}


def drawing(lines, boxes, width=1):
    img = np.full((SIZE, SIZE), 255, np.uint8)
    for a, b in lines:
        cv2.line(img, a, b, 0, width)
    for x0, y0, x1, y1 in boxes.values():
        cv2.rectangle(img, (x0, y0), (x1, y1), 0, width)
    return img


def symbols(boxes):
    return [{"id": k, "class": "valve", "box": [v / SIZE * 1000 for v in b]} for k, b in boxes.items()]


def degrade(img, seed=1, fade=0.45, blur=1.2, speckle=0.008, patches=(), tint=0.0, scale=1.0):
    """The same kinds of damage as scripts/degrade_scans.py, applied directly so each test controls them."""
    rng = np.random.default_rng(seed)
    if scale < 1:  # resolution loss first here (degrade_scans.py halves after the blur; either way strokes spread)
        small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        img = cv2.resize(small, (SIZE, SIZE), interpolation=cv2.INTER_LINEAR)
    g = img.astype(np.float32) / 255.0
    g = 1.0 - (1.0 - g) * (1.0 - fade)
    for x0, y0, x1, y1 in patches:
        g[y0:y1, x0:x1] = 1.0 - (1.0 - g[y0:y1, x0:x1]) * 0.35
    a = cv2.GaussianBlur(g * 255, (0, 0), blur)
    if tint:
        a = a * (1 - tint * (0.6 + 0.4 * np.mgrid[0:SIZE, 0:SIZE][1] / SIZE))
    m = rng.random(a.shape) < speckle
    a[m] = rng.uniform(40, 140, int(m.sum()))
    return np.clip(a, 0, 255).astype(np.uint8)


class Detect(unittest.TestCase):
    def test_clean_drawing_is_clean(self):
        img = drawing([((100, 500), (900, 500)), ((500, 100), (500, 900))], {"A": (60, 480, 100, 520)})
        self.assertFalse(scl.is_degraded(img)["degraded"])

    def test_speckle_marks_a_scan(self):
        img = drawing([((100, 500), (900, 500))], {})
        self.assertTrue(scl.is_degraded(degrade(img, fade=0.25, blur=0.8, speckle=0.002))["degraded"])

    def test_uneven_background_marks_a_scan(self):
        img = drawing([((100, 500), (900, 500))], {})
        self.assertTrue(scl.is_degraded(degrade(img, fade=0.3, blur=1.0, speckle=0.0, tint=0.15))["degraded"])


class Clean(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, img):
        p = Path(self.tmp.name) / name
        cv2.imwrite(str(p), img)
        return p

    def test_auto_on_a_clean_drawing_traces_the_original(self):
        boxes = {"A": (60, 480, 100, 520), "B": (900, 480, 940, 520), "C": (480, 60, 520, 100)}
        img = drawing([((100, 500), (900, 500)), ((500, 100), (500, 500))], boxes)
        p = self.write("clean.png", img)
        info = {}
        self.assertEqual(scl.trace(p, symbols(boxes), clean="auto", info=info), tc.trace(p, symbols(boxes)))
        self.assertFalse(info["cleaned"])

    def test_specks_removed(self):
        img = degrade(drawing([((100, 500), (900, 500))], {}), speckle=0.004)
        out = scl.clean_gray(img)
        ink = (out == 0).astype(np.uint8)
        n, _, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
        self.assertLessEqual(n - 1, 3, "only the line (and nothing speck-sized) should be left")
        self.assertTrue(ink[495:506, 150:850].any(axis=0).all(), "the line itself must survive whole")

    def test_faded_patch_is_bridged(self):
        # A thin line with a worn patch in its middle; four heavier lines elsewhere set the sheet's ink contrast,
        # as the rest of a real sheet does.
        boxes = {"A": (60, 480, 100, 520), "B": (900, 480, 940, 520)}
        img = drawing([((100, 500), (900, 500))], boxes)
        for y in (150, 250, 750, 850):
            cv2.line(img, (100, y), (900, y), 0, 3)
        img = degrade(img, patches=[(400, 470, 600, 530)], fade=0.35, blur=1.0, speckle=0.004)
        p = self.write("worn.png", img)
        self.assertNotIn(("A", "B"), pairs(tc.trace(p, symbols(boxes))), "the uncleaned tracer must lose this line")
        self.assertIn(("A", "B"), pairs(scl.trace(p, symbols(boxes), clean="on")))

    def crossing(self, gap):
        """A horizontal line that stops `gap` px short of a vertical line on each side (drawn as not connected),
        at old-scan damage (half resolution, faded, blurred, speckled)."""
        boxes = {"A": (110, 480, 150, 520), "B": (850, 480, 890, 520), "C": (480, 110, 520, 150),
                 "D": (480, 850, 520, 890)}
        lines = [((150, 500), (500 - gap - 1, 500)), ((500 + gap + 1, 500), (850, 500)), ((500, 150), (500, 850))]
        img = drawing(lines, boxes, width=2)
        for y in (200, 300, 700, 800):
            cv2.line(img, (150, y), (400, y), 0, 3)
        img = degrade(img, scale=0.5, fade=0.35, blur=1.0, speckle=0.004)
        return pairs(scl.trace(self.write(f"gap{gap}.png", img), symbols(boxes), clean="on"))

    def test_gap_before_a_crossing_line_is_kept(self):
        # dip rule: the faint stretch between the line end and the crossing line is darker on neither side
        self.assertEqual(self.crossing(5), {("C", "D")})

    def test_short_gap_beside_a_perpendicular_line_is_kept(self):
        # perp_guard: a 4 px gap blurs to a shallow dip that the plain dip rule bridges
        self.assertEqual(self.crossing(4), {("C", "D")})

    def test_thin_line_into_a_thick_line_stays_a_tee(self):
        # An instrument leader (1 px) meeting a heavy header (6 px): the stroke cores cut the thin line where the
        # header's darkness dominates, and the bridged run must still reach the header (no dip there).
        boxes = {"P": (480, 200, 520, 240), "A": (110, 480, 150, 520), "B": (850, 480, 890, 520)}
        img = drawing([((500, 240), (500, 496))], boxes, width=1)
        cv2.line(img, (150, 500), (850, 500), 0, 6)
        img = degrade(img, fade=0.25, blur=0.8, speckle=0.002)
        got = pairs(scl.trace(self.write("tee.png", img), symbols(boxes), clean="on"))
        self.assertIn(("A", "P"), got)
        self.assertIn(("A", "B"), got)

    def test_modes(self):
        with self.assertRaises(ValueError):
            scl.prepare(np.full((10, 10), 255, np.uint8), "sometimes")


if __name__ == "__main__":
    unittest.main()
