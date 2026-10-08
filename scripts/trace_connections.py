"""Traced connections: deterministic computer-vision line tracing between detected symbols (round-2 method).

Given a P&ID image and a list of detected symbols (class + box on the 0-1000 scale, from any extraction run), output
asset-to-asset connections by tracing the drawn lines between symbol boxes. No AI calls, no network.

How it works. Every length is relative to the median symbol box side on the sheet (or to the sheet size); nothing is
drawing-specific. Defaults were set on the development set only (OPEN100 0-5).
  1. Binarize the sheet (Otsu).
  2. Through-line check: a drawn symbol interrupts the line it sits on, so a box crossed edge to edge by one unbroken
     straight line is mis-placed. Shrink it to the ink left after removing that line, or drop it if nothing is left.
  3. Erase every symbol box, so lines end at symbol borders and a symbol's own ink never joins two pipes.
  4. Split the remaining ink into horizontal runs, vertical runs (morphological opening with a line-length kernel)
     and a residual (text, arrowheads, diagonals, short stubs, symbols the detector missed).
  5. Missed-symbol barrier: residual blobs that are symbol-sized, open (not solid like an arrowhead) and drawn mostly
     with slanted/curved strokes (a valve bow-tie, a bubble) are removed, so an undetected valve can't merge the
     pipes on its two sides into one network.
  6. Join touching pieces into line networks (union-find). Line crossings are joined too by default: on the
     development set the answer key treats crossings as pass-through, and splitting them lost recall
     (split_crossings=True keeps 4-arm crossings apart).
  7. Ignore networks spanning most of the sheet in both directions (frame / title-block grid).
  8. Attach each symbol to every network with ink inside a thin band just outside its box.
  9. Emit links per network. Default: all pairs of attached symbols, which is the answer key's own definition (two
     assets are linked when lines, bends, junctions or crossings alone join them). emit="tree" (nearest-neighbour
     spanning tree) and max_clique are kept as measured, worse-on-dev alternatives.

Library:  trace(image_path, symbols, **options) -> list of {"from": id, "to": id}
CLI:      python scripts/trace_connections.py --src-label round1-v2-named-fields --tool claude --drawings 0,1,2,3,4,5 \\
              --label r2-trace [--mode replace|union] [--options '{"emit": "tree"}']
          python scripts/trace_connections.py --oracle --drawings 0,1,2,3,4,5 --label r2-trace-oracle
              (answer-key symbols, development drawings only: isolates tracing quality from detection quality)
Writes runs/<label>/<tool>/<d>.json: same record shape and same symbols as the source run, with the connections
replaced by the traced ones (replace) or traced plus the model's own (union), plus a "tracer" block saying how.
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
RUNS = ROOT / "runs"
SCORED = ["tank", "pump", "valve", "instrumentation", "inlet/outlet", "general"]

DEFAULTS = {  # tuned on the development set (OPEN100 0-5) only; see the journal entry for every variant tried
    "band_frac": 0.05,      # attachment band outside each box, fraction of the median symbol short side (min 2 px)
    "line_frac": 0.6,       # min straight run counted as a line, fraction of the median symbol short side
    "split_crossings": False,  # True: don't join an H and a V run that cross with arms on all four sides
    "frame_frac": 0.8,      # ignore networks spanning more than this share of the sheet in BOTH directions
    "max_box_frac": 0.25,   # ignore symbol boxes covering more than this share of the sheet
    "emit": "all",          # "all": every pair on a network (the key's link definition); "tree": nearest-neighbour tree
    "max_clique": 10 ** 9,  # with emit=all, networks touching more symbols than this fall back to the tree
    "through_ext": 0.1,     # through-line test reach past the box, fraction of side (0 = off)
    "snap": True,           # through-line boxes: True = shrink to the ink left (drop if ~none), False = drop
    "snap_min_frac": 0.05,  # min ink left to keep a snapped box, fraction of side^2
    "blob_frac": 0.3,       # open residual blobs at least this big (fraction of side, both axes) don't conduct; 0 = off
    "blob_fill": 0.4,       # ...unless solid (ink/bbox fill >= this), like arrowheads and junction dots
    "blob_orth": 0.6,       # ...and only when less than this share of their ink is in horizontal/vertical strokes
}


def symbol_box(s):
    box = s.get("box")
    b = s.get("bbox")
    if box is None and isinstance(b, dict):
        box = [b.get("x_min"), b.get("y_min"), b.get("x_max"), b.get("y_max")]
    if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)):
        return None
    x0, y0, x1, y1 = (float(v) for v in box)
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a


def binarize(gray):
    _, ink = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return ink.astype(np.uint8)


def trace(image_path, symbols, debug=None, **opt):
    o = {**DEFAULTS, **opt}
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise FileNotFoundError(image_path)
    H, W = gray.shape
    ink = binarize(gray)

    # Symbols in pixel space.
    syms = []
    for s in symbols:
        b = symbol_box(s)
        if b is None or s.get("id") is None:
            continue
        x0, y0 = int(np.floor(b[0] / 1000 * W)), int(np.floor(b[1] / 1000 * H))
        x1, y1 = int(np.ceil(b[2] / 1000 * W)), int(np.ceil(b[3] / 1000 * H))
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W - 1, x1), min(H - 1, y1)
        if x1 <= x0 or y1 <= y0:
            continue
        if (x1 - x0) * (y1 - y0) > o["max_box_frac"] * W * H:
            continue
        syms.append({"id": str(s["id"]), "px": (x0, y0, x1, y1)})
    if len(syms) < 2:
        return []
    side = float(np.median([min(s["px"][2] - s["px"][0], s["px"][3] - s["px"][1]) for s in syms]))
    band = max(2, int(round(o["band_frac"] * side)))
    L = max(5, int(round(o["line_frac"] * side)))

    # A drawn symbol interrupts the line it sits on. A box crossed side to side by one unbroken straight line
    # (continuing past both edges) is not sitting on a symbol, so it neither cuts the line nor gets links.
    if o["through_ext"]:
        ext = max(2, int(round(o["through_ext"] * side)))
        keep = []
        for s in syms:
            x0, y0, x1, y1 = s["px"]
            if x0 - ext >= 0 and y0 - ext >= 0 and x1 + ext < W and y1 + ext < H and (
                    ink[y0:y1 + 1, x0 - ext:x1 + ext + 1].all(axis=1).any()
                    or ink[y0 - ext:y1 + ext + 1, x0:x1 + 1].all(axis=0).any()):
                if o["snap"]:
                    # snap instead of drop: remove the through-running rows/columns, shrink to the ink left
                    rows = ink[y0:y1 + 1, max(0, x0 - ext):x1 + ext + 1].all(axis=1)
                    cols = ink[max(0, y0 - ext):y1 + ext + 1, x0:x1 + 1].all(axis=0)
                    sub = ink[y0:y1 + 1, x0:x1 + 1].copy()
                    sub[rows, :] = 0
                    sub[:, cols] = 0
                    yy, xx = np.nonzero(sub)
                    if len(yy) >= o["snap_min_frac"] * side * side:
                        s = {**s, "px": (x0 + xx.min(), y0 + yy.min(), x0 + xx.max(), y0 + yy.max())}
                        keep.append(s)
                    elif o["snap"] == "keep":
                        keep.append(s)
                continue
            keep.append(s)
        syms = keep

    # Erase symbol interiors.
    for s in syms:
        x0, y0, x1, y1 = s["px"]
        ink[y0:y1 + 1, x0:x1 + 1] = 0

    hor = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (L, 1)))
    ver = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, L)))
    res = ink & (1 - (hor | ver))
    nh, lh = cv2.connectedComponents(hor, connectivity=8)
    nv, lv = cv2.connectedComponents(ver, connectivity=8)
    nr, lr, rstats, _ = cv2.connectedComponentsWithStats(res, connectivity=8)
    if o["blob_frac"]:
        # A large, open (outline) blob that is not a straight line is probably a symbol the detector missed.
        # Don't let it conduct: drop it, so it can't merge the pipes on either side of it.
        bw, bh, ba = rstats[:, 2], rstats[:, 3], rstats[:, 4]
        barrier = (np.minimum(bw, bh) >= o["blob_frac"] * side) & (ba < o["blob_fill"] * bw * bh)
        if o["blob_orth"] < 1:
            # ...and that is drawn with slanted or curved strokes (valve bow-ties, bubbles), not only with short
            # horizontal/vertical strokes (nozzle stubs, small boxes on the line, which do carry flow).
            k = max(3, int(round(0.15 * side)))
            orth = (cv2.morphologyEx(res, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1)))
                    | cv2.morphologyEx(res, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, k))))
            orth_px = np.bincount(lr[orth > 0], minlength=nr)
            barrier &= orth_px < o["blob_orth"] * ba
        barrier[0] = False
        if barrier.any():
            res = res * (~barrier[lr]).astype(np.uint8)
            nr, lr = cv2.connectedComponents(res, connectivity=8)
    # Global piece ids: h 1..nh-1 -> 0.., v -> offset, r -> offset.
    oh, ov, orr = -1, nh - 1 - 1, nh - 1 + nv - 1 - 1
    total = (nh - 1) + (nv - 1) + (nr - 1)
    uf = UF(max(total, 1))
    gid = np.full((H, W), -1, dtype=np.int64)
    gid[lh > 0] = lh[lh > 0] + oh
    # (pixels in both h and v keep their h id here; h/v joins are decided below)
    onlyv = (lv > 0) & (lh == 0)
    gid[onlyv] = lv[onlyv] + ov
    gid[lr > 0] = lr[lr > 0] + orr

    # 4. Join h and v runs where they overlap, unless the overlap is a 4-arm crossing.
    crossings = []
    both = ((hor > 0) & (ver > 0)).astype(np.uint8)
    nb, lb, stats, _ = cv2.connectedComponentsWithStats(both, connectivity=8)
    reach = max(2, L // 2)
    for i in range(1, nb):
        x, y, w, h = stats[i, :4]
        hid = int(np.bincount(lh[lb == i]).argmax())
        vid = int(np.bincount(lv[lb == i]).argmax())
        if hid == 0 or vid == 0:
            continue
        if o["split_crossings"]:
            left = (lh[y:y + h, max(0, x - reach):x] == hid).any()
            right = (lh[y:y + h, x + w:min(W, x + w + reach)] == hid).any()
            up = (lv[max(0, y - reach):y, x:x + w] == vid).any()
            down = (lv[y + h:min(H, y + h + reach), x:x + w] == vid).any()
            if left and right and up and down:
                crossings.append((x + w // 2, y + h // 2))
                continue
        uf.union(hid + oh, vid + ov)

    # Residual pieces join whatever they touch (8-neighbourhood); h/v touching each other only via overlaps above.
    if nr > 1:
        k3 = np.ones((3, 3), np.uint8)
        # residual label next to each pixel (max and min over the 3x3 neighbourhood catch up to two residual ids)
        lrmax = cv2.dilate(lr.astype(np.float32), k3).astype(np.int64)
        lrmin = -cv2.dilate(-np.where(lr > 0, lr, 1 << 30).astype(np.float32), k3).astype(np.int64)
        for lab_img, off in ((lh, oh), (lv, ov)):
            for near in (lrmax, lrmin):
                m = (lab_img > 0) & (near > 0) & (near < (1 << 30))
                for r, lab in np.unique(np.stack([near[m], lab_img[m]], 1), axis=0):
                    uf.union(int(r) + orr, int(lab) + off)

    # 5. Networks and their extents.
    ys, xs = np.nonzero(gid >= 0)
    ids = gid[ys, xs]
    rootarr = np.array([uf.find(int(i)) for i in range(total)], dtype=np.int64) if total else np.zeros(0, np.int64)
    rr = rootarr[ids]
    ext = {}
    if len(rr):
        uniq, inv = np.unique(rr, return_inverse=True)
        mnx = np.full(len(uniq), W); mny = np.full(len(uniq), H); mxx = np.zeros(len(uniq), int); mxy = np.zeros(len(uniq), int)
        np.minimum.at(mnx, inv, xs); np.minimum.at(mny, inv, ys); np.maximum.at(mxx, inv, xs); np.maximum.at(mxy, inv, ys)
        ext = {int(u): (mnx[i], mny[i], mxx[i], mxy[i]) for i, u in enumerate(uniq)}
    frame = {r for r, (a, b, c, d) in ext.items()
             if (c - a) > o["frame_frac"] * W and (d - b) > o["frame_frac"] * H}

    # 6. Attach symbols through a band just outside each box.
    rootimg = np.full((H, W), -1, dtype=np.int64)
    rootimg[ys, xs] = rr
    attach = {}
    for s in syms:
        x0, y0, x1, y1 = s["px"]
        bx0, by0, bx1, by1 = max(0, x0 - band), max(0, y0 - band), min(W - 1, x1 + band), min(H - 1, y1 + band)
        win = rootimg[by0:by1 + 1, bx0:bx1 + 1]
        hit = set(np.unique(win[win >= 0]).tolist()) - frame
        for r in hit:
            attach.setdefault(r, []).append(s)

    # 7. Emit links.
    links = set()
    for r, members in attach.items():
        uniq = {m["id"]: m for m in members}
        ms = list(uniq.values())
        if len(ms) < 2:
            continue
        if o["emit"] == "all" and len(ms) <= o["max_clique"]:
            for i in range(len(ms)):
                for j in range(i + 1, len(ms)):
                    links.add(tuple(sorted((ms[i]["id"], ms[j]["id"]))))
        else:  # nearest-neighbour spanning tree on box-centre distance (Prim)
            c = [((m["px"][0] + m["px"][2]) / 2, (m["px"][1] + m["px"][3]) / 2) for m in ms]
            inside, rest = {0}, set(range(1, len(ms)))
            while rest:
                best = min(((i, j) for i in inside for j in rest),
                           key=lambda p: (c[p[0]][0] - c[p[1]][0]) ** 2 + (c[p[0]][1] - c[p[1]][1]) ** 2)
                links.add(tuple(sorted((ms[best[0]]["id"], ms[best[1]]["id"]))))
                inside.add(best[1])
                rest.discard(best[1])
    if debug is not None:
        debug["_rootimg"] = rootimg
        debug["_syms"] = syms
        debug["_attach"] = {r: sorted({m["id"] for m in ms}) for r, ms in attach.items()}
        debug["_ext"] = {r: ext[r] for r in attach}
        debug.update({"side": side, "band": band, "L": L, "crossings": crossings, "frame_networks": len(frame),
                      "networks_with_links": sum(1 for m in attach.values() if len({x["id"] for x in m}) > 1)})
    return [{"from": a, "to": b} for a, b in sorted(links)]


def oracle_symbols(d):
    """Answer-key symbols as a prediction (development diagnostic only)."""
    sys.path.insert(0, str(Path(__file__).parent))
    import score_pid2graph as sc
    w, h = sc.png_size(DATA / f"{d}.png")
    nodes, _ = sc.load_key(DATA / f"{d}.graphml", w, h)
    return [{"id": k, "class": v["class"], "box": v["box"]} for k, v in nodes.items() if v["class"] in SCORED]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-label", default="round1-v2-named-fields")
    ap.add_argument("--tool", default="claude")
    ap.add_argument("--oracle", action="store_true", help="use the answer key's symbols (dev diagnostic)")
    ap.add_argument("--drawings", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--mode", choices=["replace", "union"], default="replace")
    ap.add_argument("--options", default="{}", help="JSON object overriding DEFAULTS, e.g. '{\"emit\": \"tree\"}'")
    a = ap.parse_args()
    opts = json.loads(a.options)
    unknown = set(opts) - set(DEFAULTS)
    if unknown:
        sys.exit(f"unknown options: {sorted(unknown)}")
    drawings = [x for x in a.drawings.split(",") if x]
    if a.oracle and any(d not in {str(i) for i in range(6)} for d in drawings):
        sys.exit("--oracle reads answer-key symbols: development drawings 0-5 only (docs/GOAL.md)")
    tool = "oracle" if a.oracle else a.tool
    for d in drawings:
        image = DATA / f"{d}.png"
        if a.oracle:
            src = {"tool": "oracle", "drawing": d, "model": "answer-key-symbols",
                   "prediction": {"symbols": oracle_symbols(d), "connections": []}}
        else:
            src = json.loads((RUNS / a.src_label / a.tool / f"{d}.json").read_text(encoding="utf-8"))
        pred = src.get("prediction") or {"symbols": [], "connections": []}
        t0 = time.time()
        dbg = {}
        traced = trace(image, pred.get("symbols", []), debug=dbg, **opts)
        conns = traced
        if a.mode == "union":
            seen = {frozenset((str(c["from"]), str(c["to"]))) for c in traced}
            conns = traced + [c for c in pred.get("connections", [])
                              if frozenset((str(c.get("from")), str(c.get("to")))) not in seen]
        record = {k: v for k, v in src.items() if k not in ("prediction", "raw_text")}
        record.update({
            "label": a.label, "source_label": None if a.oracle else a.src_label,
            "tracer": {"script": "scripts/trace_connections.py", "mode": a.mode, "options": {**DEFAULTS, **opts},
                       "seconds": round(time.time() - t0, 1), "traced_links": len(traced),
                       "model_links": len(pred.get("connections", [])),
                       "stats": {k: (len(v) if k == "crossings" else v) for k, v in dbg.items()
                                 if not k.startswith("_")},
                       "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                       "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            "prediction": {"symbols": pred.get("symbols", []), "connections": conns},
        })
        out = RUNS / a.label / tool / f"{d}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=1), encoding="utf-8")
        print(f"{tool} drawing {d}: {len(traced)} traced links ({a.mode} -> {len(conns)}), {record['tracer']['seconds']}s")


if __name__ == "__main__":
    main()
