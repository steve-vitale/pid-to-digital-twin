"""Controls for the tile merge (scripts/tiling.py), run before trusting any tiled score.

1. Geometry: tiles cover the sheet, are flush with its border, and neighbours overlap by the stated fraction.
2. Synthetic round trip (no drawing data): random symbols on random sheet sizes and shapes; each tile reports exactly
   what it can see (cut symbols clipped to the tile). The merge must give back one symbol per original, close to its
   true box. This is the "perfect tile extractor" case, so any loss here is the merge's fault.
3. Oracle on the development keys (OPEN100 0-5 only, --oracle-dev): the answer key itself is cut into tiles (every
   symbol visible in a tile, links only when both ends are visible in the same tile), merged, and scored by the
   frozen scorer. That is the ceiling tiling can reach with a perfect model, and shows how many connections are lost
   at seams by construction.

Usage: python scripts/test_tiling.py [--oracle-dev]
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tiling  # noqa: E402

CLASSES = ["tank", "pump", "valve", "instrumentation", "inlet/outlet", "general"]


def visible_in_tiles(sheet_boxes_px, classes, tiles, links=()):
    """Perfect tile extractor: report each symbol clipped to every tile it overlaps by >= 25% of its area."""
    preds = []
    for (x0, y0, x1, y1) in tiles:
        tw, th = x1 - x0, y1 - y0
        syms, seen = [], set()
        for i, (b, cls) in enumerate(zip(sheet_boxes_px, classes)):
            cx0, cy0, cx1, cy1 = max(b[0], x0), max(b[1], y0), min(b[2], x1), min(b[3], y1)
            if cx1 <= cx0 or cy1 <= cy0:
                continue
            if (cx1 - cx0) * (cy1 - cy0) < 0.25 * (b[2] - b[0]) * (b[3] - b[1]):
                continue
            seen.add(i)
            syms.append({"id": f"k{i}", "class": cls, "confidence": 0.9,
                         "bbox": {"x_min": (cx0 - x0) / tw * 1000, "y_min": (cy0 - y0) / th * 1000,
                                  "x_max": (cx1 - x0) / tw * 1000, "y_max": (cy1 - y0) / th * 1000}})
        conns = [{"from": f"k{a}", "to": f"k{b}"} for a, b in links if a in seen and b in seen]
        preds.append({"symbols": syms, "connections": conns})
    return preds


def test_geometry():
    for (w, h) in [(3300, 2200), (1994, 1330), (4961, 3508), (1200, 1700)]:
        for grid in ["1x1", "2x2", "3x2", "auto"]:
            for ov in [0.0, 0.15, 0.2]:
                cols, rows = tiling.parse_grid(grid, w, h, ov)
                tb = tiling.tile_boxes(w, h, cols, rows, ov)
                assert len(tb) == cols * rows
                assert min(t[0] for t in tb) == 0 and min(t[1] for t in tb) == 0
                assert max(t[2] for t in tb) == w and max(t[3] for t in tb) == h
                if cols > 1:
                    a, b = tb[0], tb[1]
                    got = (a[2] - b[0]) / (a[2] - a[0])
                    assert abs(got - ov) < 0.01, (w, h, grid, ov, got)
                if grid == "auto":
                    assert all(max(t[2] - t[0], t[3] - t[1]) <= tiling.AUTO_TARGET_PX + 1 for t in tb)
    print("geometry: ok")


def test_round_trip(seed=1):
    rng = random.Random(seed)
    worst = 1.0
    for trial in range(200):
        w, h = rng.randint(1500, 5000), rng.randint(1000, 3600)
        n = rng.randint(20, 120)
        boxes, classes = [], []
        while len(boxes) < n:   # non-overlapping symbols, small to vessel-sized
            sw = rng.choice([rng.randint(15, 60), rng.randint(15, 60), rng.randint(100, 500)])
            sh = rng.choice([sw, rng.randint(15, 60), rng.randint(100, 500)])
            x, y = rng.randint(0, w - sw), rng.randint(0, h - sh)
            b = (x, y, x + sw, y + sh)
            if all(b[2] + 8 < o[0] or o[2] + 8 < b[0] or b[3] + 8 < o[1] or o[3] + 8 < b[1] for o in boxes):
                boxes.append(b)
                classes.append(rng.choice(CLASSES))
        grid = rng.choice(["2x2", "3x2", "auto"])
        ov = rng.choice([0.15, 0.2])
        cols, rows = tiling.parse_grid(grid, w, h, ov)
        tb = tiling.tile_boxes(w, h, cols, rows, ov)
        merged, _ = tiling.merge_tiles(visible_in_tiles(boxes, classes, tb), tb, w, h)
        got = len(merged["symbols"])
        assert got >= n * 0.97, (trial, grid, n, got)          # nothing lost (vessels may lose a corner)
        assert got <= n * 1.03, (trial, grid, n, got)          # duplicates removed
        worst = min(worst, n / got if got > n else got / n)
    print(f"round trip: ok over 200 random sheets (worst count ratio {worst:.3f})")


def oracle_dev():
    import score_pid2graph as sc
    root = Path(__file__).resolve().parent.parent
    data = root / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
    for grid in ["2x2", "3x2", "auto"]:
        corr = items = 0
        sym = {}
        conn = {"tp": 0, "predicted": 0, "in_key": 0}
        for d in range(6):     # development set only (docs/GOAL.md)
            w, h = sc.png_size(data / f"{d}.png")
            nodes, adj = sc.load_key(data / f"{d}.graphml", w, h)
            keys = [(k, v) for k, v in nodes.items() if v["class"] in sc.SCORED]
            idx = {k: i for i, (k, _) in enumerate(keys)}
            boxes = [(v["box"][0] * w / 1000, v["box"][1] * h / 1000, v["box"][2] * w / 1000, v["box"][3] * h / 1000)
                     for _, v in keys]
            links = [tuple(idx[x] for x in l) for l in sc.asset_links(nodes, adj)]
            cols, rows = tiling.parse_grid(grid, w, h, 0.15)
            tb = tiling.tile_boxes(w, h, cols, rows, 0.15)
            merged, st = tiling.merge_tiles(visible_in_tiles(boxes, [v["class"] for _, v in keys], tb, links), tb, w, h)
            s = sc.score(data / f"{d}.graphml", merged, data / f"{d}.png")
            for kk in ("false_symbols", "missed_symbols", "relabels"):
                sym[kk] = sym.get(kk, 0) + s["review_load"][kk]
            corr += s["review_load"]["corrections"]
            items += s["review_load"]["key_items"]
            for k in conn:
                conn[k] += s["connections"][k]
        print(f"oracle {grid} @0.15 on dev: review load {100 * corr / items:.1f}; connections recall "
              f"{conn['tp'] / conn['in_key']:.2f}, precision {conn['tp'] / max(conn['predicted'], 1):.2f}; symbol errors {sym}")


if __name__ == "__main__":
    test_geometry()
    test_round_trip()
    if "--oracle-dev" in sys.argv:
        oracle_dev()

