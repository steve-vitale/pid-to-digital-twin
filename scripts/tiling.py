"""Tiled extraction: cut a sheet into overlapping tiles, map each tile's answer back to the sheet, and merge.

Why: vision models downscale big images internally (Claude to about 1,568 px on the long edge), so on a 2,000–3,300 px
P&ID the small symbols and tag text lose detail. Each tile is sent at (close to) native resolution.

Geometry (no drawing-specific numbers): a `cols x rows` grid of equal tiles. Neighbouring tiles overlap by
`overlap` x tile size, so tile width = W / (cols - (cols - 1) * overlap). The grid can be fixed ("2x2") or "auto":
the fewest tiles whose long edge fits `AUTO_TARGET_PX`, so a sheet of a different size gets a grid sized to it.

Merge rules (stated before any tiled run; thresholds are generic, in sheet-relative units, not tuned per drawing):
  1. Map each tile box from tile 0–1000 to sheet 0–1000 coordinates.
  2. Duplicates can only come from different tiles (each tile's own list is kept as the model gave it, as in the
     whole-sheet baseline). A pair of symbols from different tiles is the same symbol when
       a. same class and IoU >= SAME_CLASS_IOU, or
       b. same class and the overlap covers >= CONTAIN_FRAC of the smaller box (a symbol cut by a tile edge, i.e. a
          fragment lying inside the whole symbol seen by the neighbour), or
       c. same class, both boxes touch an inner tile edge (a seam), the boxes intersect, and they share >= half of
          the smaller box's extent along the seam (one big symbol, e.g. a vessel, split across a seam), or
       d. different class and IoU >= CROSS_CLASS_IOU (the two tiles disagree on what one symbol is; keep one).
     Pairs are merged greedily, strongest first, and a merged group never holds two symbols from the same tile, so
     two distinct neighbouring symbols can't be chained together through a third.
  3. Each merged group keeps: the box of a member that does not touch an inner tile edge (a complete view),
     highest confidence first; if every member touches a seam, the union of their boxes. Class and tag come from the
     highest-confidence member; confidence is the group's max.
  4. Connections: each tile's links are kept when both ends survive (they always do: merging renames, never drops),
     mapped to merged ids, de-duplicated, self-links dropped. Links that cross a seam are only recovered when a
     symbol in the overlap zone is seen by both tiles and so joins the two tiles' link graphs. Nothing else is done
     for cross-tile connections (a separate round-2 method traces lines with computer vision).
"""
import math

AUTO_TARGET_PX = 1568   # Claude's documented internal long-edge limit; the smallest common one of the three tools
SAME_CLASS_IOU = 0.3
CONTAIN_FRAC = 0.6
CROSS_CLASS_IOU = 0.5
EDGE_EPS = 20           # a box within 2% (of 1000) of a tile edge "touches" it
MERGE_PARAMS = {"same_class_iou": SAME_CLASS_IOU, "contain_frac": CONTAIN_FRAC,
                "cross_class_iou": CROSS_CLASS_IOU, "edge_eps_per_1000": EDGE_EPS}


def parse_grid(spec, width, height, overlap):
    """'2x2' -> (2, 2) as (cols, rows); 'auto' -> fewest tiles whose long edge fits AUTO_TARGET_PX."""
    if spec == "auto":
        def need(size):
            n = 1
            while size / (n - (n - 1) * overlap) > AUTO_TARGET_PX:
                n += 1
            return n
        return need(width), need(height)
    c, r = spec.lower().split("x")
    return int(c), int(r)


def tile_boxes(width, height, cols, rows, overlap):
    """Pixel boxes (x0, y0, x1, y1) of the tiles, row-major. Edge tiles are flush with the sheet border."""
    tw = width / (cols - (cols - 1) * overlap)
    th = height / (rows - (rows - 1) * overlap)
    out = []
    for r in range(rows):
        for c in range(cols):
            x0 = 0 if cols == 1 else c * (width - tw) / (cols - 1)
            y0 = 0 if rows == 1 else r * (height - th) / (rows - 1)
            out.append((int(round(x0)), int(round(y0)), int(round(min(width, x0 + tw))),
                        int(round(min(height, y0 + th)))))
    return out


def _box(s):
    b = s.get("bbox")
    if isinstance(b, dict):
        v = [b.get("x_min"), b.get("y_min"), b.get("x_max"), b.get("y_max")]
    else:
        v = s.get("box")
    if not (isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) for x in v)):
        return None
    x0, y0, x1, y1 = (float(x) for x in v)
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _contain(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return ix * iy / small if small > 0 else 0.0


def _seam_split(a, b, ea, eb):
    """One symbol split across a seam: both touch an inner edge, boxes intersect, and they share >= half of the
    smaller extent along the seam direction."""
    if not (ea and eb):
        return False
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix < 0 or iy < 0:
        return False
    vertical_seam = bool({"left", "right"} & (ea | eb))   # seam runs up-down: compare vertical extents
    horizontal_seam = bool({"top", "bottom"} & (ea | eb))
    ok = False
    if vertical_seam:
        ok |= iy >= 0.5 * min(a[3] - a[1], b[3] - b[1])
    if horizontal_seam:
        ok |= ix >= 0.5 * min(a[2] - a[0], b[2] - b[0])
    return ok


def merge_tiles(tile_preds, tiles_px, width, height):
    """tile_preds: list (one per tile, None if the tile failed) of {"symbols": [...], "connections": [...]} in tile
    0–1000 coordinates. Returns (merged prediction in sheet 0–1000 coordinates, stats)."""
    items = []          # one per tile symbol: dict with sheet box, tile index, original id
    id_map = {}         # (tile, original id) -> item index
    for t, pred in enumerate(tile_preds):
        if not pred:
            continue
        x0, y0, x1, y1 = tiles_px[t]
        inner = {"left": x0 > 0, "top": y0 > 0, "right": x1 < width, "bottom": y1 < height}
        for s in pred.get("symbols") or []:
            b = _box(s)
            if b is None or s.get("id") is None:
                continue
            edges = set()
            if inner["left"] and b[0] <= EDGE_EPS:
                edges.add("left")
            if inner["right"] and b[2] >= 1000 - EDGE_EPS:
                edges.add("right")
            if inner["top"] and b[1] <= EDGE_EPS:
                edges.add("top")
            if inner["bottom"] and b[3] >= 1000 - EDGE_EPS:
                edges.add("bottom")
            sb = [(x0 + b[0] / 1000 * (x1 - x0)) / width * 1000, (y0 + b[1] / 1000 * (y1 - y0)) / height * 1000,
                  (x0 + b[2] / 1000 * (x1 - x0)) / width * 1000, (y0 + b[3] / 1000 * (y1 - y0)) / height * 1000]
            conf = s.get("confidence")
            id_map[(t, str(s["id"]))] = len(items)
            items.append({"tile": t, "id": str(s["id"]), "class": s.get("class"), "tag": s.get("tag"),
                          "conf": float(conf) if isinstance(conf, (int, float)) else 0.0,
                          "box": sb, "edges": edges})

    # Candidate pairs from different tiles, with a strength used for greedy order.
    pairs = []
    for i in range(len(items)):
        a = items[i]
        for j in range(i + 1, len(items)):
            b = items[j]
            if a["tile"] == b["tile"]:
                continue
            v = _iou(a["box"], b["box"])
            if a["class"] == b["class"]:
                c = _contain(a["box"], b["box"])
                if v >= SAME_CLASS_IOU or c >= CONTAIN_FRAC:
                    pairs.append((max(v, c), i, j))
                elif _seam_split(a["box"], b["box"], a["edges"], b["edges"]):
                    pairs.append((max(v, 0.01), i, j))
            elif v >= CROSS_CLASS_IOU:
                pairs.append((v - 0.5, i, j))   # rank cross-class merges below same-class ones
    pairs.sort(reverse=True)

    group = list(range(len(items)))
    members = {i: [i] for i in range(len(items))}

    def find(i):
        while group[i] != i:
            group[i] = group[group[i]]
            i = group[i]
        return i

    for _, i, j in pairs:
        gi, gj = find(i), find(j)
        if gi == gj:
            continue
        if {items[k]["tile"] for k in members[gi]} & {items[k]["tile"] for k in members[gj]}:
            continue    # one symbol per tile per group
        group[gj] = gi
        members[gi] += members.pop(gj)

    symbols, rename = [], {}
    stats = {"tile_symbols": len(items), "merged_groups": 0, "seam_unions": 0, "cross_class_merges": 0}
    for n, (root, ms) in enumerate(sorted(members.items(), key=lambda kv: min(kv[1]))):
        ms_items = [items[k] for k in ms]
        best = max(ms_items, key=lambda it: it["conf"])
        complete = [it for it in ms_items if not it["edges"]]
        if complete:
            box = max(complete, key=lambda it: it["conf"])["box"]
        else:
            box = [min(it["box"][0] for it in ms_items), min(it["box"][1] for it in ms_items),
                   max(it["box"][2] for it in ms_items), max(it["box"][3] for it in ms_items)]
            stats["seam_unions"] += len(ms) > 1
        if len(ms) > 1:
            stats["merged_groups"] += 1
            stats["cross_class_merges"] += len({it["class"] for it in ms_items}) > 1
        sid = f"s{n + 1}"
        for k in ms:
            rename[k] = sid
        tag = best["tag"] or next((it["tag"] for it in ms_items if it["tag"]), None)
        symbols.append({"id": sid, "class": best["class"], "tag": tag,
                        "bbox": {"x_min": round(box[0], 1), "y_min": round(box[1], 1),
                                 "x_max": round(box[2], 1), "y_max": round(box[3], 1)},
                        "confidence": round(max(it["conf"] for it in ms_items), 3),
                        "tiles_seen": sorted({it["tile"] for it in ms_items}),
                        "merged_from": [f't{it["tile"]}:{it["id"]}' for it in ms_items]})

    links, tile_links, dropped = set(), 0, 0
    link_tiles = {}     # merged symbol id -> tiles whose links touch it
    for t, pred in enumerate(tile_preds):
        for c in (pred or {}).get("connections") or []:
            tile_links += 1
            a, b = id_map.get((t, str(c.get("from")))), id_map.get((t, str(c.get("to"))))
            if a is None or b is None or rename[a] == rename[b]:
                dropped += 1
                continue
            links.add(tuple(sorted((rename[a], rename[b]), key=lambda s: int(s[1:]))))
            for s in (rename[a], rename[b]):
                link_tiles.setdefault(s, set()).add(t)
    stats.update({"symbols_out": len(symbols), "tile_links": tile_links, "links_dropped": dropped,
                  "links_out": len(links),
                  # Seam "stitches": merged symbols carrying links from 2+ tiles, which join the tiles' link graphs.
                  "stitch_symbols": sum(1 for v in link_tiles.values() if len(v) > 1)})
    return {"symbols": symbols, "connections": [{"from": a, "to": b} for a, b in sorted(links)]}, stats


OVERVIEW_MIN_IOU = 0.1   # same "roughly the same place" bar the round-1 scorer uses; any class


def add_overview_links(merged, overview):
    """Optional second view: the same model's whole-sheet answer contributes CONNECTIONS only.

    Tiles see symbols at full resolution but cut long lines at seams; the whole sheet sees every line end to end but
    loses small symbols. Each whole-sheet symbol is paired one-to-one with a tiled symbol (greedy by IoU, >=
    OVERVIEW_MIN_IOU, any class); a whole-sheet link is added when both ends pair with different tiled symbols.
    Whole-sheet symbols that pair with nothing are not added (the symbol list stays the tiles' list)."""
    tiled = [(s["id"], _box(s)) for s in merged["symbols"]]
    over = [(str(s.get("id")), _box(s)) for s in (overview or {}).get("symbols") or [] if s.get("id") is not None]
    pairs = sorted(((_iou(ob, tb), oid, tid) for oid, ob in over if ob for tid, tb in tiled if tb), reverse=True)
    to_tiled, used = {}, set()
    for v, oid, tid in pairs:
        if v < OVERVIEW_MIN_IOU:
            break
        if oid in to_tiled or tid in used:
            continue
        to_tiled[oid] = tid
        used.add(tid)
    links = {tuple(sorted((c["from"], c["to"]))) for c in merged["connections"]}
    before, added, unpaired = len(links), 0, 0
    for c in (overview or {}).get("connections") or []:
        a, b = to_tiled.get(str(c.get("from"))), to_tiled.get(str(c.get("to")))
        if not a or not b or a == b:
            unpaired += 1
            continue
        key = tuple(sorted((a, b)))
        if key not in links:
            links.add(key)
            added += 1
    key_order = lambda s: int(s[1:]) if s[1:].isdigit() else 0  # noqa: E731
    out = dict(merged, connections=[{"from": a, "to": b} for a, b in
                                    sorted(links, key=lambda ab: (key_order(ab[0]), key_order(ab[1])))])
    return out, {"overview_symbols": len(over), "overview_paired": len(to_tiled), "tile_links": before,
                 "overview_links_added": added, "overview_links_unpaired": unpaired, "links_out": len(links)}
