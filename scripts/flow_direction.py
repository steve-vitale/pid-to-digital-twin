"""Flow direction for the extracted OPEN100 twin, inferred from drawing evidence only. No AI calls, no network.

The extracted twin's 1,881 connections carry no direction ("unknown"), and the PID2Graph answer keys can't supply it:
every graphml is `edgedefault="undirected"`, and its `arrow` nodes have a position but no orientation. So this script
reads direction from what the drawing itself shows, gives each connection a confidence and the evidence it came from,
and leaves everything else undirected. It never guesses a direction to fill a gap.

Evidence, strongest first:
  1. arrowhead     A flow arrow drawn on a pipe. Found by code: along every straight run the line tracer uses, the ink
                   that sticks out on BOTH sides of the line is profiled; a short bump that tapers (wide base, narrow tip,
                   width centroid toward the base) is an arrowhead pointing at its narrow end. The arrow splits the line
                   network in two; every connection from a symbol behind it to a symbol ahead of it gets that direction.
                   Symbols reachable from both sides (a loop) are not oriented.
  2. offpage_flag  An off-page connector flag (pentagon) points the way the flow goes. Tip toward the attached line:
                   flow enters the sheet there; tip away from it: flow leaves the sheet. Both ends flat or both pointed:
                   no evidence.
  3. pump_ports    Centrifugal pump convention: discharge leaves the top of the casing, suction enters the side. Fires
                   only when a pump has exactly one line network at the top of its box and at least one other at a side.
  4. valve_chain   Continuity through an in-line valve with exactly two connections: what flows in one side flows out
                   the other. Applied only from directions found by 1-3, never from another propagated direction's
                   conflict, and at lower confidence.
Not used, and why:
  - tank nozzles   Where a line meets a tank says little about direction on these drawings (bottom inlets, top
                   returns), and nozzle labels (N1, N2) carry no in/out meaning without the data sheet.
  - instruments    Links with an instrument at one end are measurement or signal connections. Process flow direction
                   doesn't apply to them; they stay undirected and are marked instrument links.
  - check valves   The extraction has one "valve" class, so a check valve can't be told apart.

Detector settings (DETECT) were chosen on the development drawings (OPEN100 0-5) only. Arrow DETECTION is scored
against the answer keys' arrow nodes (position), separately for 0-5 and 6-11. Arrow ORIENTATION and link direction
can't be scored against the keys; see the spot check in docs/OPEN100_STRUCTURAL.md.

  python scripts/flow_direction.py             # writes out/open100_structural/flow_direction.json and .md
  python scripts/flow_direction.py --overlay 5 # also draws the evidence on sheet 5 (docs/screenshots/open100/)
"""
import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import trace_connections as tc  # noqa: E402

TWIN = ROOT / "out" / "twin" / "r2-tiles-trace" / "codex"
OUT = ROOT / "out" / "open100_structural"
SHOTS = ROOT / "docs" / "screenshots" / "open100"
DEV, HOLDOUT = [str(i) for i in range(6)], [str(i) for i in range(6, 12)]

# Arrowhead detector. Set on development drawings 0-5 only (sweep in the journal entry); lengths are fractions of the
# sheet's median symbol side, widths in pixels.
DETECT = {
    "reach": 0.7,       # how far from the line to look for ink sticking out, fraction of side
    "min_len": 0.1,     # bump length along the line, fraction of side (and at least 4 px)
    "max_len": 1.2,
    "min_wpx": 3,       # widest point (both sides together) at least this many pixels
    "max_w": 1.0,       # ...and no wider than this fraction of side (bigger = a symbol or a crossing structure)
    "min_off": 0.06,    # width centroid at least this far toward the base (a triangle's is 1/6 of its length)
    "min_r": 0.5,       # width must change steadily along the bump (|correlation| with position)
    "tip_ratio": 0.6,   # narrow quarter at most this share of the wide quarter
    "max_asym": 0.5,    # ink must stick out about equally on both sides (text and tees stick out on one)
    "bowtie": 0.8,      # two opposite arrows closer than this (fraction of side) facing each other = a valve, drop both
}
FLAG = {"flat_min": 0.8, "tip_max": 0.7, "probe": 0.06}

# Confidence per evidence source. These are the measured agreement rates from the blind spot check
# (docs/OPEN100_STRUCTURAL.md, "How right is it"); a source with no spot-check sample keeps the stated prior.
CONFIDENCE = json.loads((ROOT / "data" / "open100_direction_confidence.json").read_text(encoding="utf-8")) \
    if (ROOT / "data" / "open100_direction_confidence.json").exists() else {}
PRIOR = {"arrowhead": 0.8, "offpage_flag": 0.8, "pump_ports": 0.6, "arrowhead_via_junction": 0.6,
         "offpage_flag_via_junction": 0.6, "valve_chain": 0.6}


def confidence(source):
    c = CONFIDENCE.get("sources", {}).get(source, {})
    return c.get("confidence", PRIOR[source])


# ---------------------------------------------------------------- arrowheads

def bump_candidates(ink, labels, n, side, reach):
    """Along each horizontal run (label in `labels`), intervals where ink sticks out on both sides of the line.
    Returns (run label, first x, last x, line centre y, out_up[], out_down[])."""
    H, W = ink.shape
    R = max(3, int(round(reach * side)))
    ext = max(2, int(round(0.3 * side)))
    out = []
    ys_all, xs_all = np.nonzero(labels)
    order = np.argsort(labels[ys_all, xs_all], kind="stable")
    ys_all, xs_all = ys_all[order], xs_all[order]
    bounds = np.searchsorted(labels[ys_all, xs_all], np.arange(1, n + 1))
    for i in range(1, n):
        ys, xs = ys_all[bounds[i - 1]:bounds[i]], xs_all[bounds[i - 1]:bounds[i]]
        if not len(ys):
            continue
        yt, yb = int(ys.min()), int(ys.max())
        if yb - yt > max(6, 0.25 * side):
            continue
        xa, xb = max(0, int(xs.min()) - ext), min(W, int(xs.max()) + ext + 1)
        ya, yz = max(0, yt - R), min(H, yb + R + 1)
        win = ink[ya:yz, xa:xb]
        _, wl = cv2.connectedComponents(win, connectivity=8)
        ids = np.unique(wl[(labels[ya:yz, xa:xb] == i) & (wl > 0)])
        comp = np.isin(wl, ids) & (wl > 0)
        ly0, ly1 = yt - ya, yb - ya
        up = np.zeros(xb - xa, int)
        dn = np.zeros(xb - xa, int)
        above, below = comp[:ly0, :], comp[ly1 + 1:, :]
        if above.shape[0]:
            up = np.where(above.any(axis=0), ly0 - np.argmax(above, axis=0), 0)
        if below.shape[0]:
            dn = np.where(below.any(axis=0), below.shape[0] - np.argmax(below[::-1, :], axis=0), 0)
        good = (up >= 1) & (dn >= 1)
        j = 0
        while j < len(good):
            if not good[j]:
                j += 1
                continue
            k = j
            while k + 1 < len(good) and good[k + 1]:
                k += 1
            out.append((i, xa + j, xa + k, (yt + yb) / 2, up[j:k + 1].copy(), dn[j:k + 1].copy()))
            j = k + 1
    return out


def classify_bump(up, dn, side, cfg=DETECT):
    """+1: arrow points toward larger x (the bump narrows that way), -1: toward smaller x, None: not an arrowhead."""
    ln = len(up)
    if ln < max(4, cfg["min_len"] * side) or ln > cfg["max_len"] * side:
        return None
    w = (np.asarray(up) + np.asarray(dn)).astype(float)
    if w.max() < cfg["min_wpx"] or w.max() > cfg["max_w"] * side or np.std(w) == 0:
        return None
    xs = np.arange(ln)
    r = float(np.corrcoef(xs, w)[0, 1])
    off = float(((xs * w).sum() / w.sum() - (ln - 1) / 2) / ln)
    if abs(off) < cfg["min_off"] or abs(r) < cfg["min_r"] or np.sign(r) != np.sign(off):
        return None
    q = max(1, ln // 4)
    head, tail = w[:q].mean(), w[-q:].mean()
    narrow, wide = (tail, head) if r < 0 else (head, tail)
    if narrow > cfg["tip_ratio"] * wide:
        return None
    if np.median(np.abs(np.asarray(up) - np.asarray(dn))) / max(1.0, float(np.median(w))) > cfg["max_asym"]:
        return None
    return 1 if r < 0 else -1


def arrowheads(ink, side, line_len, cfg=DETECT):
    """Arrowheads on the straight runs of `ink` (symbol boxes already erased). Each: axis ('x' or 'y'), centre (x, y),
    dir (+1 = toward larger coordinate on that axis), run label on that axis, length in px."""
    hor = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1)))
    ver = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, line_len)))
    nh, lh = cv2.connectedComponents(hor, connectivity=8)
    nv, lv = cv2.connectedComponents(ver, connectivity=8)
    found = []
    for i, a, b, yc, up, dn in bump_candidates(ink, lh, nh, side, cfg["reach"]):
        d = classify_bump(up, dn, side, cfg)
        if d:
            found.append({"axis": "x", "x": (a + b) / 2, "y": yc, "dir": d, "run": int(i), "len": int(b - a + 1),
                          "box_px": [int(a), int(yc - max(up.max(), 1)), int(b), int(yc + max(dn.max(), 1))]})
    for i, a, b, xc, left, right in bump_candidates(ink.T.copy(), lv.T.copy(), nv, side, cfg["reach"]):
        d = classify_bump(left, right, side, cfg)
        if d:
            found.append({"axis": "y", "x": xc, "y": (a + b) / 2, "dir": d, "run": int(i), "len": int(b - a + 1),
                          "box_px": [int(xc - max(left.max(), 1)), int(a), int(xc + max(right.max(), 1)), int(b)]})
    keep = []
    for a in found:  # an undetected valve bow-tie looks like two arrows pointing at each other
        along, across = ("x", "y") if a["axis"] == "x" else ("y", "x")
        facing = any(b is not a and b["axis"] == a["axis"] and abs(b[across] - a[across]) < 3
                     and abs(b[along] - a[along]) < cfg["bowtie"] * side and b["dir"] != a["dir"]
                     and (b[along] - a[along]) * a["dir"] > 0 for b in found)
        if not facing:
            keep.append(a)
    return keep, (nh, lh, nv, lv)


# ---------------------------------------------------------------- off-page connector flags

def flag_tip(ink, box):
    """Which end of an off-page flag is pointed: 'left', 'right', 'up', 'down', or None (rectangle, double-ended or
    unreadable). box = pixel (x0, y0, x1, y1). Text inside the flag doesn't matter: only the outer ends are probed."""
    x0, y0, x1, y1 = box
    sub = ink[max(0, y0 - 2):y1 + 3, max(0, x0 - 2):x1 + 3]
    if sub.size == 0 or not sub.any():
        return None
    horizontal = (x1 - x0) >= (y1 - y0)
    a = sub if horizontal else sub.T
    hb = a.shape[0]
    rows = np.arange(hb)[:, None]
    has = a.any(axis=0)
    top = np.where(has, np.argmax(a, axis=0), hb)
    bot = np.where(has, hb - 1 - np.argmax(a[::-1, :], axis=0), -1)
    ext = np.where(has, bot - top + 1, 0)
    span = (np.nonzero(a.any(axis=1))[0].max() - np.nonzero(a.any(axis=1))[0].min() + 1) if a.any() else 0
    valid = np.nonzero(ext > max(6, 0.2 * span))[0]
    if len(valid) < 6 or span < 8:
        return None
    lo, hi = valid[0], valid[-1]
    k = max(2, int(round(FLAG["probe"] * (hi - lo + 1))))
    e_lo, e_hi = float(np.median(ext[lo:lo + k])), float(np.median(ext[hi - k + 1:hi + 1]))
    del rows
    if e_lo >= FLAG["flat_min"] * span and e_hi <= FLAG["tip_max"] * e_lo:
        tip = "hi"
    elif e_hi >= FLAG["flat_min"] * span and e_lo <= FLAG["tip_max"] * e_hi:
        tip = "lo"
    else:
        return None
    if horizontal:
        return "right" if tip == "hi" else "left"
    return "down" if tip == "hi" else "up"


def flag_role(tip, box, attach_points):
    """'source' (flow enters the sheet here), 'sink' (flow leaves), or None. attach_points: where lines meet the box."""
    if tip is None or not attach_points:
        return None
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sides = set()
    for x, y in attach_points:
        if tip in ("left", "right"):
            sides.add("left" if x < cx else "right")
        else:
            sides.add("up" if y < cy else "down")
    if len(sides) != 1:
        return None
    return "source" if sides.pop() == tip else "sink"


# ---------------------------------------------------------------- the line graph, with arrows as nodes

def line_graph(g, extra=()):
    """trace_connections.line_geometry's graph rebuilt from trace(geometry=...) output, with extra nodes placed on
    pieces. extra: [(piece id, x, y, key)]. Returns points, adj, attach {sid: [node]}, owner {node: sid},
    extra_nodes {key: node}, chain {node: (prev node or None, next node or None)} for the extra nodes."""
    points, on_piece, attach, extra_nodes = [], defaultdict(list), defaultdict(list), {}
    # A residual piece (arrowhead wings, text touching a line, a short stub) that touches only ONE line piece is a
    # decoration on that line, not a branch: its joins would only add shortcut edges that look like junctions.
    partners = defaultdict(set)
    for a, b, x, y in g["joins"]:
        if g["piece_kind"](a) == "r":
            partners[a].add(b)
    joins = sorted({(a, b, round(x, 1), round(y, 1)) for a, b, x, y in g["joins"]
                    if not (g["piece_kind"](a) == "r" and len(partners[a]) < 2)})
    for a, b, x, y in joins:
        points.append((x, y))
        on_piece[a].append(len(points) - 1)
        on_piece[b].append(len(points) - 1)
    for sid, p, x, y in g["attachments"]:
        points.append((x, y))
        on_piece[p].append(len(points) - 1)
        attach[sid].append(len(points) - 1)
    for p, x, y, key in extra:
        points.append((x, y))
        on_piece[p].append(len(points) - 1)
        extra_nodes[key] = len(points) - 1
    adj = {i: set() for i in range(len(points))}
    chain = {}
    extra_set = set(extra_nodes.values())
    for p, nodes in on_piece.items():
        nodes = sorted(set(nodes))
        kind = g["piece_kind"](p)
        if kind == "r" and len(nodes) <= 12:
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    adj[nodes[i]].add(nodes[j])
                    adj[nodes[j]].add(nodes[i])
            continue
        if kind in ("h", "v"):
            axis = 0 if kind == "h" else 1
        else:
            xs, ys = [points[n][0] for n in nodes], [points[n][1] for n in nodes]
            axis = 0 if max(xs) - min(xs) >= max(ys) - min(ys) else 1
        nodes.sort(key=lambda n: points[n][axis])
        for i in range(len(nodes) - 1):
            adj[nodes[i]].add(nodes[i + 1])
            adj[nodes[i + 1]].add(nodes[i])
        for i, n in enumerate(nodes):
            if n in extra_set:
                chain[n] = (nodes[i - 1] if i > 0 else None, nodes[i + 1] if i + 1 < len(nodes) else None)
    owner = {n: sid for sid, ns in attach.items() for n in ns}
    # Joins closer together than a line is thick are one place on the drawing (a corner where a horizontal run, a
    # vertical run and a residual bit all overlap). Count them as one point, or a plain corner looks like a junction.
    radius = max(3.0, 0.15 * (g.get("side") or 20))
    joins_idx = [i for i in range(len(points)) if i not in owner and i not in extra_set]
    parent = {i: i for i in range(len(points))}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    cells = defaultdict(list)
    for i in joins_idx:
        cells[(int(points[i][0] // radius), int(points[i][1] // radius))].append(i)
    for (cx, cy), members in cells.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cells.get((cx + dx, cy + dy), ()):
                    for i in members:
                        if i < j and abs(points[i][0] - points[j][0]) <= radius and                                 abs(points[i][1] - points[j][1]) <= radius:
                            parent[find(j)] = find(i)
    rep = {i: find(i) for i in range(len(points))}
    cadj = defaultdict(set)
    for u, vs in adj.items():
        cadj[rep[u]]
        for v in vs:
            if rep[u] != rep[v]:
                cadj[rep[u]].add(rep[v])
    chain = {n: (rep[a] if a is not None else None, rep[b] if b is not None else None) for n, (a, b) in chain.items()}
    return points, dict(cadj), dict(attach), owner, extra_nodes, chain


def reach(adj, start, blocked):
    seen, q = {start}, deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in seen and v not in blocked:
                seen.add(v)
                q.append(v)
    return seen


def nearest(adj, start, blocked, owner):
    """Symbols reached first along the line from `start`, without passing a junction (a point where three or more
    line pieces meet) or another symbol. Empty if the line branches before reaching any symbol."""
    if start in owner:
        return {owner[start]}
    if len(adj[start]) >= 3:
        return set()
    found, seen, q = set(), {start} | set(blocked), deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v in seen:
                continue
            seen.add(v)
            if v in owner:
                found.add(owner[v])
            elif len(adj[v]) < 3:
                q.append(v)
    return found


def prune(adj, owner, signal_symbols, keep=()):
    """The process-line graph: drop instrument attachments, then repeatedly drop dead-end points that belong to no
    process symbol. What's left branches only where process lines branch, so an instrument tap or a dangling stub is
    not counted as a junction."""
    keep = set(keep)
    alive = {n for n in adj if owner.get(n) not in signal_symbols}
    padj = {n: {m for m in adj[n] if m in alive} for n in alive}
    stack = [n for n in padj if len(padj[n]) <= 1 and n not in owner and n not in keep]
    while stack:
        n = stack.pop()
        if n not in padj or len(padj[n]) > 1:
            continue
        for m in padj.pop(n):
            padj[m].discard(n)
            if len(padj[m]) <= 1 and m not in owner and m not in keep:
                stack.append(m)
    return padj


# ---------------------------------------------------------------- one sheet

def sheet_evidence(image_path, symbols):
    """All direction evidence on one sheet. symbols: [{id, class, box (0-1000)}]. Returns a dict with the traced
    links, arrows, flags, pumps and per-pair orientations [(upstream symbol, downstream symbol, evidence)].
    Evidence sources ending in "_via_junction" are the weaker reading: the arrow or flag is on one symbol's own pipe,
    but the other symbol is beyond a branch point, so the flow that passes the arrow may not be the flow between them."""
    g = {}
    links = tc.trace(image_path, symbols, geometry=g)
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    H, W = gray.shape
    raw = tc.binarize(gray)
    ink = raw.copy()
    for x0, y0, x1, y1 in g["symbols"].values():
        ink[y0:y1 + 1, x0:x1 + 1] = 0
    side = g["side"]
    L = max(5, int(round(tc.DEFAULTS["line_frac"] * side)))
    arrows, (nh, lh, nv, lv) = arrowheads(ink, side, L)
    frame = set(g["frame_networks"])
    extra = []
    for k, a in enumerate(arrows):
        # the run's piece id in trace(): horizontal runs are lh - 1, vertical ones lv + nh - 2 (same labelling)
        a["piece"] = a["run"] - 1 if a["axis"] == "x" else a["run"] + nh - 2
        a["network"] = g["piece_network"](a["piece"])
        if a["network"] in frame:
            a["status"] = "on the drawing frame"
            continue
        extra.append((a["piece"], a["x"], a["y"], ("arrow", k)))
    points, adj, attach, owner, extra_nodes, chain = line_graph(g, extra)
    signal = {str(x["id"]) for x in symbols if x.get("class") == "instrumentation"}
    adj = prune(adj, owner, signal, keep=extra_nodes.values())
    orient = []

    def vote(behind, ahead, near_behind, near_ahead, ev):
        """near x near: the arrow or flag is on the pipe between the two symbols. One side near, the other beyond
        a branch: the weaker reading. Neither near: no claim."""
        for u in behind:
            for v in ahead:
                if u in near_behind and v in near_ahead:
                    orient.append((u, v, ev))
                elif u in near_behind or v in near_ahead:
                    orient.append((u, v, {**ev, "source": ev["source"] + "_via_junction"}))

    for k, a in enumerate(arrows):
        node = extra_nodes.get(("arrow", k))
        if node is None:
            continue
        prev, nxt = chain.get(node, (None, None))
        fwd, back = (nxt, prev) if a["dir"] > 0 else (prev, nxt)
        if node not in adj or fwd not in adj.get(node, ()) or back not in adj.get(node, ()):
            a["status"] = "at a line end with nothing beyond it"
            continue
        ahead = {owner[n] for n in reach(adj, fwd, {node}) if n in owner}
        behind = {owner[n] for n in reach(adj, back, {node}) if n in owner}
        loop = ahead & behind
        ahead, behind = ahead - loop, behind - loop
        if not ahead or not behind:
            a["status"] = "no symbol on one side" if not loop else "loop: symbols reachable from both sides"
            continue
        na, nb = nearest(adj, fwd, {node}, owner) - loop, nearest(adj, back, {node}, owner) - loop
        if not na and not nb:
            a["status"] = "branches on both sides before any symbol"
            continue
        a["status"] = "orients links"
        a.update(ahead=sorted(ahead), behind=sorted(behind), loop=sorted(loop), near_ahead=sorted(na),
                 near_behind=sorted(nb))
        vote(behind, ahead, nb, na, {"source": "arrowhead", "box_px": a["box_px"],
                                     "points": ("+" if a["dir"] > 0 else "-") + a["axis"]})
    # off-page flags
    flags = {}
    by_id = {str(s["id"]): s for s in symbols}
    att_xy = defaultdict(list)
    for sid, p, x, y in g["attachments"]:
        if g["piece_network"](p) not in frame:
            att_xy[sid].append((x, y))
    for sid, px in g["symbols"].items():
        if by_id.get(sid, {}).get("class") != "inlet/outlet":
            continue
        b = tc.symbol_box(by_id[sid])
        box = (int(b[0] / 1000 * W), int(b[1] / 1000 * H), int(np.ceil(b[2] / 1000 * W)), int(np.ceil(b[3] / 1000 * H)))
        tip = flag_tip(raw, box)
        role = flag_role(tip, box, att_xy.get(sid))
        flags[sid] = {"tip": tip, "role": role, "box_px": list(box)}
        if not role or sid not in attach:
            continue
        mine = set(attach[sid]) & set(adj)
        others, near = set(), set()
        for n in mine:
            others |= {owner[m] for m in reach(adj, n, mine - {n}) if m in owner}
            for m in adj[n]:
                if m not in mine:
                    near |= nearest(adj, m, mine, owner)
        others.discard(sid)
        near.discard(sid)
        ev = {"source": "offpage_flag", "box_px": list(box), "tip": tip, "role": role}
        if role == "source":
            vote({sid}, others, {sid}, near, ev)
        else:
            vote(others, {sid}, near, {sid}, ev)
    # pumps: discharge at the top of the casing, suction at a side; nearest symbols only
    pumps = {}
    for sid, px in g["symbols"].items():
        if by_id.get(sid, {}).get("class") != "pump" or sid not in attach:
            continue
        x0, y0, x1, y1 = px
        w, h = x1 - x0, y1 - y0
        mine = set(attach[sid]) & set(adj)
        groups = {"top": set(), "side": set()}
        nets = {"top": set(), "side": set()}
        for n in mine:
            x, y = points[n]
            if y <= y0 + 0.2 * h:
                pos = "top"
            elif (x <= x0 + 0.2 * w or x >= x1 - 0.2 * w) and y0 + 0.3 * h <= y <= y0 + 0.8 * h:
                pos = "side"
            else:
                continue
            for m in adj[n]:
                if m not in mine:
                    groups[pos] |= nearest(adj, m, mine, owner)
            nets[pos].add(frozenset(reach(adj, n, mine - {n})))
        top, sides = groups["top"] - {sid}, groups["side"] - groups["top"] - {sid}
        fires = bool(top) and bool(sides) and len(nets["top"]) == 1
        pumps[sid] = {"fires": fires, "discharge_to": sorted(top) if fires else [],
                      "suction_from": sorted(sides) if fires else [], "box_px": list(px)}
        if fires:
            ev = {"source": "pump_ports", "box_px": list(px)}
            vote({sid}, top, {sid}, top, {**ev, "port": "discharge (top)"})
            vote(sides, {sid}, sides, {sid}, {**ev, "port": "suction (side)"})
    return {"links": links, "side": side, "size": (W, H), "arrows": arrows, "flags": flags, "pumps": pumps,
            "orient": orient, "geometry": g}


# ---------------------------------------------------------------- the whole twin

def model_symbols(model):
    """Per sheet: symbol id -> {id, class, box, asset}; from the twin's provenance (exactly what was traced)."""
    out = defaultdict(dict)
    for key in ("units", "instruments", "line_items", "offpage_connectors"):
        for item in model[key]:
            for p in item["provenance"]:
                out[p["sheet"]][p["symbol"]] = {"id": p["symbol"], "class": p["class"], "box": p["box_0_1000"],
                                                "asset": item["id"]}
    return out


WEAK = ("arrowhead_via_junction", "offpage_flag_via_junction")


def combine(evidence):
    """evidence: [(+1 from->to / -1 to->from, source, confidence, detail)] -> (direction, confidence, basis).
    First-hand evidence on the pipe itself (arrowhead, offpage_flag, pump_ports) decides when present; otherwise the
    weaker via-junction readings; otherwise valve continuity. Within the deciding tier any disagreement is a conflict
    and stays undirected. Confidence is the deciding tier's strongest source."""
    if not evidence:
        return "undirected", None, None
    tiers = ([e for e in evidence if e[1] not in WEAK + ("valve_chain",)], [e for e in evidence if e[1] in WEAK],
             [e for e in evidence if e[1] == "valve_chain"])
    for name, tier in zip(("first_hand", "via_junction", "valve_chain"), tiers):
        if not tier:
            continue
        signs = {e[0] for e in tier}
        if len(signs) > 1:
            return "conflict", None, name
        return ("forward" if signs.pop() > 0 else "reverse"), round(max(e[2] for e in tier), 3), name
    return "undirected", None, None


def propagate_valves(streams, result, valve_ids, conf):
    """Continuity through in-line valves with exactly two process connections. Seeds only from first-hand evidence
    on the pipe (arrowhead, offpage_flag, pump_ports); a propagated direction never seeds another.
    result: {stream id: (direction, confidence, basis)}."""
    by_node = defaultdict(list)
    for s in streams:
        by_node[s["from"]].append(s)
        by_node[s["to"]].append(s)
    added = defaultdict(list)
    for v in valve_ids:
        ss = by_node.get(v, [])
        if len(ss) != 2:
            continue
        for known, other in ((ss[0], ss[1]), (ss[1], ss[0])):
            d = result.get(known["id"])
            if not d or d[0] not in ("forward", "reverse") or d[2] != "first_hand":
                continue
            into_valve = (known["to"] if d[0] == "forward" else known["from"]) == v
            # the other link carries it on: valve -> far end if it flowed into the valve, else far end -> valve
            sign = 1 if ((other["from"] == v) == into_valve) else -1
            added[other["id"]].append((sign, "valve_chain", conf, {"source": "valve_chain", "through": v,
                                                                   "from_link": known["id"], "_sign": sign}))
    return added


def infer(model, drawings, sheets=None):
    syms = model_symbols(model)
    streams = model["streams"]
    by_pair = {}
    for s in streams:
        if s["kind"] == "extracted_link":
            by_pair[(s["sheet"], frozenset((s["from_symbol"], s["to_symbol"])))] = s
    classes = {x["id"]: x["class"] for k in ("units", "instruments", "line_items", "offpage_connectors")
               for x in model[k]}
    ev = defaultdict(list)
    per_sheet = {}
    flags_by_asset = {}
    for sheet in sorted(syms, key=int):
        if sheets and sheet not in sheets:
            continue
        S = sheet_evidence(drawings / f"{sheet}.png", list(syms[sheet].values()))
        traced = {frozenset((l["from"], l["to"])) for l in S["links"]}
        expected = {k[1] for k in by_pair if k[0] == sheet}
        if traced != expected:
            raise SystemExit(f"sheet {sheet}: re-traced links differ from the twin ({len(traced ^ expected)} differ)")
        seen = set()
        for u, v, e in S["orient"]:
            s = by_pair.get((sheet, frozenset((u, v))))
            key = (s["id"] if s else None, u, v, e["source"], tuple(e["box_px"]), e.get("port"))
            if s is None or key in seen:
                continue
            seen.add(key)
            sign = 1 if s["from_symbol"] == u else -1
            ev[s["id"]].append((sign, e["source"], confidence(e["source"]), {**e, "sheet": sheet, "_sign": sign}))
        for sid, f in S["flags"].items():
            flags_by_asset[syms[sheet][sid]["asset"]] = {**f, "sheet": sheet}
        per_sheet[sheet] = {"side_px": S["side"], "size_px": S["size"], "arrows": S["arrows"], "flags": S["flags"],
                            "pumps": S["pumps"]}
    # cross-sheet pairs: both flags must agree
    for s in streams:
        if s["kind"] != "cross_sheet":
            continue
        fa, fb = flags_by_asset.get(s["from"]), flags_by_asset.get(s["to"])
        roles = (fa or {}).get("role"), (fb or {}).get("role")
        if roles in (("sink", "source"), ("source", "sink")):
            sign = 1 if roles == ("sink", "source") else -1
            ev[s["id"]].append((sign, "offpage_flag", confidence("offpage_flag"),
                                {"source": "offpage_flag", "pair": [s["from"], s["to"]], "roles": list(roles),
                                 "_sign": sign}))
    # Instrument links are measurement/signal connections: process flow direction doesn't apply, so no evidence is
    # attached to them even when an arrowhead's line network reaches the instrument.
    inst = {s["id"] for s in streams if any(classes.get(x) == "instrumentation" for x in (s["from"], s["to"]))}
    for sid in inst:
        ev.pop(sid, None)
    first = {sid: combine(e) for sid, e in ev.items()}
    valves = [x["id"] for x in model["line_items"] if x["class"] == "valve"]
    process_streams = [s for s in streams if s["id"] not in inst]
    for sid, more in propagate_valves(process_streams, first, valves, confidence("valve_chain")).items():
        ev[sid].extend(more)
    out = []
    for s in streams:
        e = ev.get(s["id"], [])
        direction, conf, basis = combine(e)
        rec = {"id": s["id"], "from": s["from"], "to": s["to"], "sheet": s.get("sheet"), "kind": s["kind"],
               "direction": direction, "confidence": conf, "basis": basis, "instrument_link": s["id"] in inst,
               "evidence": [x[3] for x in e],
               # same field names as the data-lineage provenance record (provenance.element), plus the direction's
               "provenance": {"source_check": (s.get("verification") or {}).get("status", "unverified"),
                              "ops_review": "unverified", "risk_tier": (s.get("risk") or {}).get("tier"),
                              "direction_source": basis or "none", "direction_confidence": conf}}
        if direction in ("forward", "reverse"):
            rec["flow_from"], rec["flow_to"] = (s["from"], s["to"]) if direction == "forward" else (s["to"], s["from"])
        out.append(rec)
    return out, per_sheet


def summarize(records, per_sheet, model, drawings):
    from collections import Counter
    total = len(records)
    directed = [r for r in records if r["direction"] in ("forward", "reverse")]
    srcs = Counter()
    for r in directed:
        tier = {"first_hand": lambda e: e["source"] not in WEAK + ("valve_chain",),
                "via_junction": lambda e: e["source"] in WEAK, "valve_chain": lambda e: e["source"] == "valve_chain"}
        for src in sorted({e["source"] for e in r["evidence"] if tier[r["basis"]](e)}):
            srcs[src] += 1
    process = [r for r in records if not r["instrument_link"]]
    det = {"dev": score_arrows(per_sheet, drawings, DEV), "holdout": score_arrows(per_sheet, drawings, HOLDOUT)}
    arrow_status = Counter(a.get("status", "?") for p in per_sheet.values() for a in p["arrows"])
    flag_roles = Counter(str(f["role"]) for p in per_sheet.values() for f in p["flags"].values())
    # independent sources on the same link: do they agree? (an arrowhead and a flag are read by different code
    # from different ink, so agreement between them is evidence neither is reading noise)
    cross = Counter()
    for r in records:
        by = defaultdict(set)
        for e in r["evidence"]:
            base = e["source"].replace("_via_junction", "")
            if base != "valve_chain":
                by[base].add(e.get("_sign"))
        srcs_here = [k for k, v in by.items() if None not in v and len(v) == 1]
        if len(srcs_here) >= 2:
            signs = {next(iter(by[k])) for k in srcs_here}
            cross["agree" if len(signs) == 1 else "disagree"] += 1
    return {
        "cross_source_agreement": dict(cross),
        "connections": total,
        "directed": len(directed),
        "undirected": sum(r["direction"] == "undirected" for r in records),
        "conflict": sum(r["direction"] == "conflict" for r in records),
        "directed_by_basis": dict(Counter(r["basis"] for r in directed)),
        "conflict_by_basis": dict(Counter(r["basis"] for r in records if r["direction"] == "conflict")),
        "directed_links_per_deciding_source": dict(srcs),
        "process_links": len(process),
        "process_links_directed": sum(r["direction"] in ("forward", "reverse") for r in process),
        "instrument_links": total - len(process),
        "instrument_links_directed": sum(r["direction"] in ("forward", "reverse") for r in records
                                         if r["instrument_link"]),
        "confidence_histogram": dict(Counter(str(r["confidence"]) for r in directed)),
        "arrowheads_found": sum(len(p["arrows"]) for p in per_sheet.values()),
        "arrowhead_status": dict(arrow_status),
        "offpage_flags": dict(flag_roles),
        "pumps_rule_fired": sum(p["fires"] for s in per_sheet.values() for p in s["pumps"].values()),
        "pumps": sum(len(s["pumps"]) for s in per_sheet.values()),
        "arrow_detection_vs_keys": det,
        "keys_directed": False,
        "keys_note": "Every PID2Graph OPEN100 graphml is edgedefault=\"undirected\"; its arrow nodes have a position "
                     "and no orientation. Direction accuracy can't be scored against the keys.",
        "detector_settings": DETECT, "detector_tuned_on": "development drawings 0-5 only",
        "confidence_source": CONFIDENCE.get("method", "priors (no spot check loaded)"),
    }


def score_arrows(per_sheet, drawings, sheets):
    """Detected arrowheads vs the key's arrow nodes (position only): precision, recall. A detection counts when its
    centre is inside a key arrow box grown by 0.3 symbol sides. Includes detections on the frame, which never orient
    anything, and key arrows that are text leaders rather than flow arrows (the key doesn't separate them)."""
    import score_pid2graph as sc
    tp = n_det = hit = n_key = 0
    for d in sheets:
        if d not in per_sheet:
            continue
        W, H = per_sheet[d]["size_px"]
        side = per_sheet[d]["side_px"]
        nodes, _ = sc.load_key(drawings / f"{d}.graphml", W, H)
        keys = [[v["box"][0] * W / 1000, v["box"][1] * H / 1000, v["box"][2] * W / 1000, v["box"][3] * H / 1000]
                for v in nodes.values() if v["class"] == "arrow"]
        tol = 0.3 * side
        got = set()
        for a in per_sheet[d]["arrows"]:
            m = [k for k, b in enumerate(keys) if b[0] - tol <= a["x"] <= b[2] + tol and b[1] - tol <= a["y"] <= b[3] + tol]
            tp += bool(m)
            got |= set(m)
        n_det += len(per_sheet[d]["arrows"])
        hit += len(got)
        n_key += len(keys)
    return {"sheets": sheets, "detections": n_det, "detections_on_a_key_arrow": tp, "key_arrows": n_key,
            "key_arrows_found": hit, "precision": round(tp / n_det, 3) if n_det else None,
            "recall": round(hit / n_key, 3) if n_key else None}


def overlay(sheet, records, per_sheet, model, path):
    """The evidence drawn on one sheet: arrowheads (red), flags (blue), pumps (purple), directed links (green)."""
    from PIL import Image, ImageDraw
    im = Image.open(tc.DATA / f"{sheet}.png").convert("RGB")
    W, H = im.size
    faded = Image.blend(im, Image.new("RGB", im.size, "white"), 0.55)
    dr = ImageDraw.Draw(faded)
    centre = {}
    for key in ("units", "instruments", "line_items", "offpage_connectors"):
        for x in model[key]:
            for p in x["provenance"]:
                if p["sheet"] == sheet:
                    b = p["box_0_1000"]
                    centre[x["id"]] = ((b[0] + b[2]) / 2000 * W, (b[1] + b[3]) / 2000 * H)
    for r in records:
        if r.get("sheet") != sheet or r["direction"] not in ("forward", "reverse"):
            continue
        a, b = centre.get(r["flow_from"]), centre.get(r["flow_to"])
        if not a or not b:
            continue
        dr.line((a, b), fill=(0, 140, 60), width=3)
        vx, vy = b[0] - a[0], b[1] - a[1]
        n = max(1e-6, (vx * vx + vy * vy) ** 0.5)
        ux, uy = vx / n, vy / n
        tip = (a[0] + vx * 0.6, a[1] + vy * 0.6)
        dr.polygon([tip, (tip[0] - 14 * ux + 7 * uy, tip[1] - 14 * uy - 7 * ux),
                    (tip[0] - 14 * ux - 7 * uy, tip[1] - 14 * uy + 7 * ux)], fill=(0, 140, 60))
    for a in per_sheet[sheet]["arrows"]:
        col = (220, 30, 30) if a.get("status") == "orients links" else (240, 160, 160)
        dr.rectangle(a["box_px"], outline=col, width=3)
    for f in per_sheet[sheet]["flags"].values():
        dr.rectangle(f["box_px"], outline=(30, 80, 220) if f["role"] else (160, 180, 230), width=3)
    for p in per_sheet[sheet]["pumps"].values():
        dr.rectangle(p["box_px"], outline=(130, 40, 160) if p["fires"] else (200, 170, 210), width=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    faded.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--twin", default=str(TWIN))
    ap.add_argument("--overlay", default="", help="comma list of sheets to draw the evidence on")
    a = ap.parse_args()
    model = json.loads((Path(a.twin) / "plant_model.json").read_text(encoding="utf-8"))
    records, per_sheet = infer(model, tc.DATA)
    summary = summarize(records, per_sheet, model, tc.DATA)
    OUT.mkdir(parents=True, exist_ok=True)
    slim = {s: {"side_px": p["side_px"], "size_px": p["size_px"],
                "arrows": [{k: v for k, v in x.items() if k in ("axis", "x", "y", "dir", "box_px", "status", "ahead",
                                                                 "behind", "loop")} for x in p["arrows"]],
                "flags": p["flags"], "pumps": p["pumps"]} for s, p in per_sheet.items()}
    doc = {"meta": {"model_id": model["meta"]["model_id"], "script": "scripts/flow_direction.py",
                    "direction_values": {"forward": "flow goes from -> to", "reverse": "flow goes to -> from",
                                         "undirected": "no drawing evidence; shown without an arrow",
                                         "conflict": "evidence disagrees; shown without an arrow"}},
           "summary": summary, "streams": records, "sheets": slim}
    (OUT / "flow_direction.json").write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    for s in [x for x in a.overlay.split(",") if x]:
        overlay(s, records, per_sheet, model, SHOTS / f"flow-evidence-sheet{s}.png")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("detector_settings",)}, indent=1))


if __name__ == "__main__":
    main()
