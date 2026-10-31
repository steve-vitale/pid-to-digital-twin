"""Layered line relationships for a drawing: the drawn pipe topology, the line networks, and the pairwise links.

The line tracer (scripts/trace_connections.py) links every PAIR of symbols attached to the same drawn line network
(lines, bends, junctions or crossings join them with no symbol between). That is how this repository's connection
scorer (scripts/score_pid2graph.py) reads the PID2Graph answer key: the key itself is a graph (symbol nodes joined
through `connector` and `crossing` nodes), and the scorer collapses those line points into all-pairs network
co-membership. Every connection score here uses that pairwise definition, but it is not pipe adjacency: on OPEN100
sheet 0 an independent review found 22 of 27 sampled links ran through one or more tees. This script keeps that
pairwise layer exactly as it is and adds the facts it was standing in for, computed from the same traced geometry:

  pipe layer     nodes: items (symbols) and junctions; edges: process pipe segments between consecutive nodes along
                 a run, through bends and past instrument taps, never through another item or a pipe tee. "A is
                 piped to B" = one segment joins them directly.
  other lines    drawn lines that are not pipe, each its own kind: instrument connections (a bubble's leader or
                 impulse line, to a tap on a pipe, an item or another instrument line), actuator stems (a valve and
                 the actuator stacked on it) and nozzle stubs (a nozzle mark and its vessel). See item_roles() and
                 classify() for the rules and their limits.
  network layer  each traced line network as a node, with its member items and its junctions.
  pairwise       the tracer's existing links, unchanged: all pairs of members of one network (network
                 co-membership), so they are derivable from the network layer.

Definitions (fixed here; tests in scripts/test_line_layers.py):
  junction       a point where three or more line arms meet: a tee (a run ending on another run that continues
                 both ways), a short stroke that joins three or more runs, or an item drawn beside a run that keeps
                 going on both sides of it. Its kind: pipe_tee (three or more pipe arms), instrument_tap (an
                 instrument line meets a pipe that carries on through it: the tap sits on that pipe segment and does
                 not split it), marked_crossing, instrument_line_junction (instrument lines meeting off any pipe).
  crossing       two runs crossing with arms on all four sides. The tracer JOINS them into one network (its default
                 split_crossings=False: the answer key passes connectivity through crossings, and splitting them lost
                 recall on the development set), so the network and pairwise layers keep that. In the pipe layer a
                 crossing is NOT a junction: each run passes straight through and nothing on one run is piped to the
                 other at the crossing. Only a crossing the drawing marks as connected (a dot: ink beyond the two
                 runs that touches both, within a quarter of a symbol side of the crossing, and fills all four corners
                 between the arms; stray pixels in some corners are not a dot) is a 4-arm junction. A slanted stroke
                 that carries on straight across a run (a label's leader, a dashed outline, hatching) crosses it too:
                 in the pipe layer it does not join that run (slanted_crossings lists where).
  bend           a horizontal and a vertical run meeting with two arms: passed through, not a node.
  dead end       a line end with no item on it: pruned (a stub is not a branch).
  closed shape   a junction meets three or more DIFFERENT neighbours: line that leaves a point and comes back to it, or
  on a line      two lines between the same two places (a filled arrowhead, an unkeyed symbol's outline, a box drawn
                 on a stem), is passed through or pruned, not a junction (contract()).
  touching       two process items drawn against each other with no line between (a blind flange on a valve, a
                 reducer against a valve, a flange on a vessel's shell): consecutive, so piped directly; no line is
                 drawn, so the segment is on no line network unless both ends already share one (TOUCH_FRAC).
  item's own     a meeting point inside an item's box, or just outside it, is the item's own drawing, unless the
  drawing        points there have two or more arms leading away to other items from one point, and one into the item
                 (a tee drawn beside the box; two pipes landing apart on a vessel's shell are not one). An actuator
                 and its valve count as one assembly here.
Junction ids: <sheet>-JN-<x>-<y> with the position on the 0-1000 sheet scale; network ids: <sheet>-NET<n> numbered
by their sorted member ids; segment ids: <sheet>-PS<n> (pipe), -IL<n> (instrument line), -AS<n> (actuator stem),
-NZ<n> (nozzle stub), numbered by their sorted ends.

Ground truth for the pipe layer: DEXPI XML (tees are explicit PipeTee elements; dexpi_truth), this repository's
generated TE and Bayer drawings (the drawer's own routes, valves, taps and tee points; drawn_truth, current drawer
only), and a truth DERIVED from the PID2Graph key graph for the OPEN100 development sheets (symbol, connector /
crossing / arrow chains, symbol; pid2graph_truth). Each truth is split into pipe and instrument lines by the symbols'
classes, as the traced side is (classify_truth). See docs/EVALUATION.md, "Which layer each evaluation measures".

    python scripts/line_layers.py enrich my-bundle/plant_model.json --image 0=sheet0.png --out my-bundle/plant_model.json
    python scripts/line_layers.py score --set dexpi                 # tracer (key symbols) vs DEXPI XML topology
    python scripts/line_layers.py score --set te --set bayer --set open100 --json out.json

No model calls, no network. Needs OpenCV and numpy (as the tracer does).
"""
import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from output_paths import protect_outputs

SCHEMA = "line-layers-2"
ARM_FRAC = 0.25         # a run continuing at least this share of a symbol side past an overlap is an arm there
DOT_FRAC = 0.25          # a residual stroke within this share of a symbol side of a crossing that touches both runs
CLUSTER_FRAC = 0.15      # line-meeting points closer than this share of a symbol side are one place (as flow_direction)
JUNCTION_BOX_FRAC = 0.4  # half-size of a junction's evidence box, share of a symbol side
ACTUATOR_GAP_FRAC = 0.25  # an actuator box is at most this share of a symbol side from its valve's box
NOZZLE_GAP_FRAC = 0.5     # a nozzle mark's box is at most this share of a symbol side from its vessel's box
SAME_PLACE_FRAC = 0.5     # a tee beside a box: its arms leading away leave within this share of a symbol side
TOUCH_FRAC = 0.1          # process items whose boxes are this share of a symbol side apart or closer are drawn touching
NOZZLE_TAG = re.compile(r"^N\d{1,2}[A-Z]?$")  # how a nozzle is marked on the drawing (N1, N2, N12A)
VESSEL_CLASSES = ("tank",)                    # classes a nozzle can belong to (and any item from the model's units)
JUNCTION_KINDS = ("pipe_tee", "instrument_tap", "marked_crossing", "instrument_line_junction")
DEFINITIONS = {
    "piped_to": "a process pipe segment joins the two directly: consecutive along a drawn run, through bends and "
                "past instrument taps, with no pipe tee or other item between; or two items drawn against each other "
                "with nothing between (touching: no line is drawn, so the segment is on no line network unless both "
                "ends already share one)",
    "junction": "a point where three or more drawn line arms meet. junction_kind says which: pipe_tee (three or more "
                "pipe arms: a tee or branch), instrument_tap (an instrument line meets a pipe that carries on through "
                "it: the tap sits on the pipe segment named by on_segment and does not split it), marked_crossing (a "
                "4-arm crossing the drawing marks connected with a dot), instrument_line_junction (instrument lines "
                "meeting away from a pipe)",
    "instrument_connection": "a drawn line that joins an instrument (its bubble) to a pipe at a tap, to an item, or "
                             "to another instrument line: a leader, impulse or signal line, not a process pipe",
    "actuated_by": "a valve and the actuator drawn stacked on it (a small symbol beside the valve box, joined only "
                   "by a short stem): the stem is part of the valve, not a pipe",
    "nozzle_of": "a nozzle mark (N1, N2...) and the vessel it sits on: the short stub between them is part of the "
                 "vessel, not a pipe",
    "line_network": "drawn lines that touch one another outside the item boxes, through bends, junctions or "
                    "crossings, as the tracer joins them (its network). Lines that meet only at an item's edge can "
                    "be joined: such a network names that item in joined_only_at",
    "network_pair": "the tracer's pairwise link: both items are on the same line network (not pipe adjacency)",
}


# ------------------------------------------------------------------ the generic pipe graph

class _UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a


def contract(adj, items):
    """Collapse a line graph to its pipe layer. adj: {node: {neighbour: network}} (undirected), items: the item
    nodes. Dead ends that are not items are pruned; nodes of degree 2 that are not items (bends, pass points) are
    walked through; non-item nodes of degree >= 3 are junctions. Returns (segments {(a, b) sorted: network},
    junction arms {node: arms})."""
    adj = {u: {v: n for v, n in vs.items() if v != u} for u, vs in adj.items()}
    for u, vs in list(adj.items()):
        for v, n in vs.items():
            adj.setdefault(v, {})[u] = n
    stack = [u for u in adj if u not in items and len(adj[u]) <= 1]
    while stack:
        u = stack.pop()
        if u not in adj or u in items or len(adj[u]) > 1:
            continue
        for v in adj.pop(u):
            adj[v].pop(u, None)
            if v not in items and len(adj[v]) <= 1:
                stack.append(v)
    key = {u for u in adj if u in items or len(adj[u]) >= 3}
    segs = {}
    for u in sorted(key, key=str):
        for v, net in adj[u].items():
            prev, cur = u, v
            while cur not in key:
                nxt = [w for w in adj[cur] if w != prev]
                if not nxt:
                    cur = None
                    break
                prev, cur = cur, nxt[0]
            if cur is None or cur == u:
                continue
            segs.setdefault(tuple(sorted((u, cur), key=str)), net)
    # A junction joins three or more DIFFERENT things. Line that leaves a junction and comes back to it, or two lines
    # between the same two places (a filled arrowhead or an unkeyed symbol's outline drawn on a run, a box drawn on a
    # stem), makes points with three arms that meet fewer than three neighbours: such a point is passed through (two
    # neighbours) or is a dead end (one), until every junction left meets three or more.
    nb = defaultdict(dict)
    for (a, b), net in segs.items():
        nb[a][b] = net
        nb[b][a] = net
    todo = [u for u in nb if u not in items]
    while todo:
        u = todo.pop()
        if u in items or u not in nb or len(nb[u]) >= 3:
            continue
        vs = nb.pop(u)
        for v in vs:
            nb[v].pop(u, None)
        if len(vs) == 2:
            (x, n1), (y, _) = sorted(vs.items(), key=lambda kv: str(kv[0]))
            if y not in nb[x]:
                nb[x][y] = nb[y][x] = n1
        todo += [v for v in vs if v not in items]
    now = {tuple(sorted((a, b), key=str)) for a in nb for b in nb[a]}
    segs = {**{k: n for k, n in segs.items() if k in now},
            **{k: nb[k[0]][k[1]] for k in sorted(now - set(segs), key=str)}}
    # Line that joins fewer than two items (a closed loop of lines, a table grid, an item's own outline or internals
    # drawn outside its box): not pipe between items. Drop it with its junctions.
    uf = _UF()
    for a, b in segs:
        uf.union(a, b)
    count = defaultdict(int)
    for i in items:
        if i in uf.p:
            count[uf.find(i)] += 1
    keep = {r for r, n in count.items() if n >= 2}
    segs = {s: n for s, n in segs.items() if uf.find(s[0]) in keep}
    arms = {u: len(nb[u]) for u in nb if u not in items and u in uf.p and uf.find(u) in keep}
    return segs, arms


def pipe_networks(segments, junctions):
    """Line networks of a pipe layer that has no crossings: connected pieces of line with no item in them. Each is
    a group of junctions joined by junction-junction segments plus the items on them, or one item-item segment.
    segments: [(a, b)]; junctions: set of junction nodes. Returns [{"members": [...], "junctions": [...]}]."""
    uf = _UF()
    for j in junctions:
        uf.find(("j", j))
    lone = []
    for a, b in segments:
        ja, jb = a in junctions, b in junctions
        if ja and jb:
            uf.union(("j", a), ("j", b))
        elif not ja and not jb:
            lone.append((a, b))
    groups = defaultdict(lambda: {"members": set(), "junctions": set()})
    for j in junctions:
        groups[uf.find(("j", j))]["junctions"].add(j)
    for a, b in segments:
        for j, other in ((a, b), (b, a)):
            if j in junctions and other not in junctions:
                groups[uf.find(("j", j))]["members"].add(other)
    out = [{"members": sorted(g["members"], key=str), "junctions": sorted(g["junctions"], key=str)}
           for g in groups.values()]
    out += [{"members": sorted((a, b), key=str), "junctions": []} for a, b in lone]
    return sorted(out, key=lambda g: (g["members"], g["junctions"]))


# ------------------------------------------------------------------ what a line is: pipe, instrument, actuator, nozzle

def box_gap(a, b):
    """Gap between two boxes (x0, y0, x1, y1): the larger of the x and y gaps, negative when they overlap."""
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def item_roles(symbols, boxes, side):
    """What each item is to the lines it touches, from its class, its tag and its box alone (before any line is
    read). symbols: {id: {"class", "tag", "unit"}}; boxes: {id: (x0, y0, x1, y1)} in one scale; side: a symbol side in
    that scale. Returns {id: "instrument" | ("actuator", valve) | ("nozzle", vessel)}; any other item is a process
    item.
      instrument  class "instrumentation" (a bubble).
      actuator    class "general" stacked on a valve: its box at most ACTUATOR_GAP_FRAC of a side from the valve's,
                  centred within the valve's extent across the gap and no wider than the valve that way (the H, M or
                  diaphragm box drawn on a valve's stem). The nearest such valve.
      nozzle      a tag that reads as a nozzle mark (N1, N2, N12A), not an instrument or valve, its box at most
                  NOZZLE_GAP_FRAC of a side from a vessel's (class tank, or one of the model's units). The nearest.
    Limits: an actuator drawn inside its valve's box, or one classed other than "general", is not seen; an untagged
    nozzle, or one whose label was read as something else, is not seen (its stub stays a pipe segment)."""
    roles = {}
    cls = {k: str((symbols.get(k) or {}).get("class") or "") for k in boxes}
    for k in boxes:
        if cls[k] == "instrumentation":
            roles[k] = "instrument"
    valves = [k for k in boxes if cls[k] == "valve"]
    for k in sorted(boxes):
        if cls[k] != "general":
            continue
        a, best = boxes[k], None
        for v in valves:
            b = boxes[v]
            g = box_gap(a, b)
            if g > ACTUATOR_GAP_FRAC * side:
                continue
            cx, cy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
            above_or_below = (a[3] <= b[1] + 1 or a[1] >= b[3] - 1) and b[0] <= cx <= b[2] and a[2] - a[0] <= b[2] - b[0]
            beside = (a[2] <= b[0] + 1 or a[0] >= b[2] - 1) and b[1] <= cy <= b[3] and a[3] - a[1] <= b[3] - b[1]
            if (above_or_below or beside) and (best is None or g < best[0]):
                best = (g, v)
        if best:
            roles[k] = ("actuator", best[1])
    vessels = [k for k in boxes if cls[k] in VESSEL_CLASSES or (symbols.get(k) or {}).get("unit")]
    for k in sorted(boxes):
        tag = str((symbols.get(k) or {}).get("tag") or "").strip()
        if k in roles or cls[k] in ("instrumentation", "valve") or not NOZZLE_TAG.match(tag):
            continue
        near = sorted((box_gap(boxes[k], boxes[u]), u) for u in vessels if u != k)
        if near and near[0][0] <= NOZZLE_GAP_FRAC * side:
            roles[k] = ("nozzle", near[0][1])
    return roles


def classify(segs, arms, roles):
    """Split a line graph's segments by what they join. segs: {(a, b): network} (contract()'s output), arms: {junction:
    arms}, roles: item_roles(). Rules, in order:
      1. a junction that joins an actuator and its own valve is the valve assembly (the stem meets the valve there):
         it folds into the valve, its other arms going to the valve;
      2. a segment between an actuator and its valve is the actuator stem; between a nozzle and its vessel, the
         nozzle stub; one with an instrument or an actuator at an end (a leader, or a signal line to an actuator) is
         an instrument line; the rest is process pipe;
      3. at a junction where instrument lines meet and a single process arm is left, that arm carries the
         instrument line on (repeated until nothing changes);
      4. junction kinds: three or more pipe arms, a pipe tee; two pipe arms and an instrument line, an instrument tap;
         fewer than two pipe arms, an instrument line junction;
      5. pipe segments are joined through instrument taps: the pipe passes the tap, which sits on that segment.
    Returns {"pipe": {(a, b): {"network", "taps" (in order from a to b)}}, "instrument": {(from, to): network} (from
    the instrument side), "actuator": {(valve, actuator): network}, "nozzle": {(nozzle, vessel): network}, "kinds":
    {junction: kind}, "tap_on": {tap: pipe key}, "arms": {junction: arms} (after rule 1)}."""
    key = lambda a, b: tuple(sorted((a, b), key=str))  # noqa: E731
    segs, arms = dict(segs), dict(arms)
    act = {n: r[1] for n, r in roles.items() if isinstance(r, tuple) and r[0] == "actuator"}
    noz = {n: r[1] for n, r in roles.items() if isinstance(r, tuple) and r[0] == "nozzle"}
    inst = {n for n, r in roles.items() if r == "instrument"}

    def at(j):
        return sorted((s for s in segs if j in s), key=str)

    def other(s, j):
        return s[1] if s[0] == j else s[0]
    for j in sorted(arms, key=str):  # 1. valve assemblies
        nb = {other(s, j) for s in at(j)}
        hit = sorted((a, v) for a, v in act.items() if a in nb and v in nb)
        if not hit:
            continue
        v = hit[0][1]
        for s in at(j):
            net, o = segs.pop(s), other(s, j)
            if o != v:
                segs.setdefault(key(o, v), net)
        del arms[j]
    line, orient = {}, {}
    for s in segs:  # 2. by the ends
        a, b = s
        if act.get(a) == b or act.get(b) == a:
            line[s], orient[s] = "actuator", ((b, a) if act.get(a) == b else (a, b))
        elif noz.get(a) == b or noz.get(b) == a:
            line[s], orient[s] = "nozzle", ((a, b) if noz.get(a) == b else (b, a))
        elif a in inst or b in inst or a in act or b in act:
            line[s] = "instrument"
            orient[s] = (a, b) if a in inst else (b, a) if b in inst else (a, b) if a in act else (b, a)
        else:
            line[s], orient[s] = "process", s
    changed = True
    while changed:  # 3. instrument lines carried on through their own junctions
        changed = False
        for j in sorted(arms, key=str):
            ss = at(j)
            p = [s for s in ss if line[s] == "process"]
            if len(p) == 1 and len(ss) == arms[j] and any(line[s] == "instrument" for s in ss):
                line[p[0]], orient[p[0]] = "instrument", (j, other(p[0], j))
                changed = True
    kinds = {}
    for j in arms:  # 4. junction kinds
        ss = at(j)
        p = sum(line[s] == "process" for s in ss)
        i = sum(line[s] == "instrument" for s in ss)
        kinds[j] = "pipe_tee" if p >= 3 or not i else "instrument_tap" if p == 2 else "instrument_line_junction"
    taps = {j for j, k in kinds.items() if k == "instrument_tap"}
    padj = defaultdict(list)
    for s in segs:
        if line[s] == "process":
            padj[s[0]].append(s)
            padj[s[1]].append(s)
    pipe, tap_on, seen = {}, {}, set()
    for s in sorted((s for s in segs if line[s] == "process"), key=str):  # 5. through the taps
        if s in seen:
            continue
        seen.add(s)
        ends, walked = [], [s]
        for node in s:
            prev, path = s, []
            while node in taps:
                nxt = [t for t in padj[node] if t != prev]
                if len(nxt) != 1 or nxt[0] in seen:
                    break
                path.append(node)
                prev = nxt[0]
                seen.add(prev)
                walked.append(prev)
                node = other(prev, node)
            ends.append((node, path))
        (a, pa), (b, pb) = ends
        order = list(reversed(pa)) + pb
        if a == b:  # a closed loop through taps: keep its pieces as they are (its taps become tees below)
            for t in walked:
                pipe.setdefault(t, {"network": segs[t], "taps": []})
            continue
        k = key(a, b)
        if k != (a, b):
            order.reverse()
        if k in pipe:  # two pipes between the same ends: one segment, every tap on it
            pipe[k]["taps"] += [t for t in order if t not in pipe[k]["taps"]]
        else:
            pipe[k] = {"network": segs[s], "taps": order}
        for t in order:
            tap_on[t] = k
    for j in taps - set(tap_on):  # a tap the walk could not pass (a loop): it splits the pipe after all
        kinds[j] = "pipe_tee"
    return {"pipe": pipe, "kinds": kinds, "tap_on": tap_on, "arms": arms,
            "instrument": {orient[s]: segs[s] for s in segs if line[s] == "instrument"},
            "actuator": {orient[s]: segs[s] for s in segs if line[s] == "actuator"},
            "nozzle": {orient[s]: segs[s] for s in segs if line[s] == "nozzle"}}


# ------------------------------------------------------------------ from a drawing image (the tracer's geometry)

def traced_layers(image_path, symbols, exclude=(), **opt):
    """The three layers of one sheet from the tracer's own geometry. symbols: [{id, box (0-1000), class, tag, unit}]
    (class, tag and unit are optional: they decide which lines are pipe, see item_roles). exclude: symbol ids left out
    of the pipe layer only (their lines become dead ends and are pruned, a branch they made is passed through): used
    to score process piping alone against a truth that has no instrument lines.
    Returns {"links", "networks" {root: [ids]}, "junctions" {jid: {x, y, arms, basis, kind, network, on_segment}},
    "segments" [(a, b, network)] (process pipe only; network None for items drawn touching on no shared network),
    "touching" [(a, b)] (pairs joined by being drawn against each other), "segment_taps" {(a, b): [taps]},
    "instrument_lines"
    [(from, to, network)], "actuator_stems" [(valve, actuator, network)], "nozzle_stubs" [(nozzle, vessel, network)],
    "crossings" {...}, "side", "size", "problems"}. The links are exactly trace()'s."""
    import cv2
    import numpy as np
    import trace_connections as tc
    g = {}
    links = tc.trace(image_path, symbols, geometry=g, **opt)
    out = {"links": links, "networks": {}, "junctions": {}, "segments": [], "segment_taps": {}, "instrument_lines": [],
           "actuator_stems": [], "nozzle_stubs": [], "side": g.get("side"),
           "single_item_networks": 0, "crossings": {"pass_through": 0, "marked_connected": 0},
           "slanted_crossings": [], "touching": [], "problems": []}
    if not g:
        return out
    o = {**tc.DEFAULTS, **opt}
    W, H, side = g["width"], g["height"], g["side"]
    out["size"] = (W, H)
    kind, pnet, frame = g["piece_kind"], g["piece_network"], set(g["frame_networks"])
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    ink = tc.binarize(gray)
    for x0, y0, x1, y1 in g["symbols"].values():
        ink[y0:y1 + 1, x0:x1 + 1] = 0
    L = max(5, int(round(o["line_frac"] * side)))
    hor = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (L, 1)))
    ver = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, L)))
    nh, lh = cv2.connectedComponents(hor, connectivity=8)  # the same calls trace() makes: the same labels
    nv, lv = cv2.connectedComponents(ver, connectivity=8)
    if (nh > 1 and kind(nh - 2) != "h") or (nv > 1 and kind(nh - 2 + nv - 1) != "v"):
        raise RuntimeError("run labels do not line up with trace()'s pieces")

    def extents(lab, n):
        ys, xs = np.nonzero(lab)
        ids = lab[ys, xs]
        lo_x, lo_y = np.full(n, 1 << 30), np.full(n, 1 << 30)
        hi_x, hi_y = np.full(n, -1), np.full(n, -1)
        np.minimum.at(lo_x, ids, xs)
        np.minimum.at(lo_y, ids, ys)
        np.maximum.at(hi_x, ids, xs)
        np.maximum.at(hi_y, ids, ys)
        return lo_x, lo_y, hi_x, hi_y
    hext, vext = extents(lh, nh), extents(lv, nv)

    def run_label(p):  # piece id -> ("h"|"v", label)
        return ("h", p + 1) if kind(p) == "h" else ("v", p - (nh - 2))

    # Horizontal/vertical overlaps: the same components trace() joined, with their arms counted.
    both = ((hor > 0) & (ver > 0)).astype(np.uint8)
    nb, lb, stats, _ = cv2.connectedComponentsWithStats(both, connectivity=8)
    # An arm counts only if its run carries on at least ARM_FRAC of a symbol side past the overlap: a run that stops a
    # line-width past the other (or a junction dot's stub) is not a fourth arm, so a tee is not read as a crossing.
    a0 = max(3, int(round(ARM_FRAC * side)))
    reach = a0 + max(2, L // 2)
    hv = []
    for i in range(1, nb):
        x, y, w, h = (int(v) for v in stats[i, :4])
        m = lb[y:y + h, x:x + w] == i
        hid = int(np.bincount(lh[y:y + h, x:x + w][m]).argmax())
        vid = int(np.bincount(lv[y:y + h, x:x + w][m]).argmax())
        if hid == 0 or vid == 0:
            continue
        hp, vp = hid - 1, vid + nh - 2
        if pnet(hp) in frame:
            continue
        arms = sum((bool((lh[y:y + h, max(0, x - reach):max(0, x - a0 + 1)] == hid).any()),
                    bool((lh[y:y + h, min(W, x + w + a0 - 1):min(W, x + w + reach)] == hid).any()),
                    bool((lv[max(0, y - reach):max(0, y - a0 + 1), x:x + w] == vid).any()),
                    bool((lv[min(H, y + h + a0 - 1):min(H, y + h + reach), x:x + w] == vid).any())))
        hv.append((hp, vp, x + (w - 1) / 2, y + (h - 1) / 2, arms, (x, y, w, h)))

    # Residual strokes: each touches runs at the points trace() recorded; one that touches fewer than two things
    # (runs or items) is a decoration on one line (arrowhead wings, text), not a branch.
    touch = defaultdict(dict)
    for a, b, x, y in g["joins"]:
        if kind(a) == "r" and kind(b) != "r":
            px, py, n = touch[a].get(b, (0.0, 0.0, 0))
            touch[a][b] = (px + x, py + y, n + 1)
    touch = {r: {p: (sx / n, sy / n) for p, (sx, sy, n) in d.items()} for r, d in touch.items()}
    r_att = defaultdict(list)
    run_att = []
    for sid, p, x, y in g["attachments"]:
        (r_att[p].append((sid, x, y)) if kind(p) == "r" else run_att.append((sid, p, x, y)))
    # A slanted stroke that carries on straight across a run is a line crossing it (a label's leader drawn across a
    # pipe to the next line), not a branch of it: in the pipe layer it does not join that run (the tracer's network
    # still does). Seen as: residual ink on both sides of the run where the stroke touches it, each side reaching at
    # least an arm's length (ARM_FRAC of a symbol side) from the run, and the two sides on one straight line.
    res = ink & (1 - (hor | ver))  # the residual ink, as trace() splits it (before its missed-symbol barrier)
    _, lres = cv2.connectedComponents(res, connectivity=8)

    def crosses(p, x, y):
        ax, lab = run_label(p)
        rl, rr = (lh, lres) if ax == "h" else (lv.T, lres.T)  # rows across the run, columns along it
        u, v = (int(round(x)), int(round(y))) if ax == "h" else (int(round(y)), int(round(x)))
        n_across, n_along = rl.shape
        if not 0 <= u < n_along:
            return False
        col = np.nonzero(rl[max(0, v - a0):v + a0 + 1, u] == lab)[0]
        if not len(col):
            return False
        top, bot = max(0, v - a0) + int(col.min()), max(0, v - a0) + int(col.max())
        lo, hi = max(0, u - 2 * a0), min(n_along, u + 2 * a0 + 1)
        sides = []
        for edge, rows in ((top - 1, slice(max(0, top - 2 * a0), top)), (bot + 1, slice(bot + 1, bot + 1 + 2 * a0))):
            if not 0 <= edge < n_across:
                return False
            labs = set(np.unique(rr[edge, max(0, u - 3):u + 4]).tolist()) - {0}
            if not labs:
                return False
            win = rr[rows, lo:hi]
            ys, xs = np.nonzero(np.isin(win, list(labs)))
            if len(ys) < 3:
                return False
            ys = ys + rows.start
            if np.abs(ys - (top if edge < top else bot)).max() < a0:
                return False  # does not reach an arm's length from the run: a dot, an arrowhead's barb, a stub
            sides.append(np.stack([xs + lo, ys], 1).astype(float))
        pts = np.vstack(sides)
        c = pts.mean(axis=0)
        w, vec = np.linalg.eigh(np.cov((pts - c).T))
        # one straight line: almost all the spread along one direction, and no point far off it
        off = np.abs((pts - c) @ vec[:, 0])
        return bool(w[1] > 0 and w[0] <= 0.05 * w[1] and off.max() <= max(3.0, (bot - top + 1)))
    for r in sorted(touch):
        for p in [p for p, (x, y) in touch[r].items() if crosses(p, x, y)]:
            out["slanted_crossings"].append(tuple(round(v, 1) for v in touch[r].pop(p)))
    keep_r = {r for r in set(touch) | set(r_att) if len(touch.get(r, {})) + len(r_att.get(r, [])) >= 2}

    pos, nkind, nnet, owner = [], [], [], {}
    adj = defaultdict(dict)
    stops = defaultdict(list)

    def new(x, y, k, net):
        pos.append((float(x), float(y)))
        nkind.append(k)
        nnet.append(net)
        return len(pos) - 1

    def link(a, b, net):
        if a != b:
            adj[a][b] = net
            adj[b][a] = net

    dot_r = max(4.0, DOT_FRAC * side)

    def dot_fills_corners(x, y, w, h):
        # A dot is a filled disc wider than the lines: it fills all four corners between the arms. Stray pixels at a
        # crossing (anti-aliasing, a thin line's ragged edge) touch both runs too, but fill only some corners.
        r = int(math.ceil(dot_r))
        need = max(2, min(w, h))  # pixels per corner: the thinner run's width (the overlap's width and height)
        return all(int(res[ys, xs].sum()) >= need
                   for ys in (slice(max(0, y - r), y), slice(y + h, min(H, y + h + r)))
                   for xs in (slice(max(0, x - r), x), slice(x + w, min(W, x + w + r))))
    crossing_ink = set()
    for hp, vp, cx, cy, arms, (bx, by, bw, bh) in hv:
        net = pnet(hp)
        if arms >= 4:
            at_x = [r for r in keep_r if r in touch and hp in touch[r] and vp in touch[r]
                    and math.dist(touch[r][hp], (cx, cy)) <= dot_r and math.dist(touch[r][vp], (cx, cy)) <= dot_r]
            marked = bool(at_x) and dot_fills_corners(bx, by, bw, bh)
            if not marked:
                # strokes there that touch only these two runs are the crossing's own ink: they join nothing
                crossing_ink.update(r for r in at_x if set(touch[r]) == {hp, vp} and not r_att.get(r))
                out["crossings"]["pass_through"] += 1
                stops[hp].append((cx, new(cx, cy, "crossing", net)))
                stops[vp].append((cy, new(cx, cy, "crossing", net)))
                continue
            out["crossings"]["marked_connected"] += 1
        n = new(cx, cy, "marked_crossing" if arms >= 4 else "tee" if arms == 3 else "bend", net)
        stops[hp].append((cx, n))
        stops[vp].append((cy, n))
    for r in sorted(keep_r - crossing_ink):
        net = pnet(r)
        pts = list(touch.get(r, {}).values()) + [(x, y) for _, x, y in r_att.get(r, [])]
        hub = new(sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), "stroke", net)
        for p, (x, y) in sorted(touch.get(r, {}).items()):
            t = new(x, y, "touch", net)
            stops[p].append((x if kind(p) == "h" else y, t))
            link(t, hub, net)
        for sid, x, y in r_att.get(r, []):
            a = new(x, y, "attach", net)
            owner[a] = sid
            link(a, hub, net)
    tol = (g.get("band") or 2) + 2
    for sid, p, x, y in run_att:
        net = pnet(p)
        a = new(x, y, "attach", net)
        owner[a] = sid
        sx0, sy0, sx1, sy1 = g["symbols"][sid]
        ax, lab = run_label(p)
        lo_x, lo_y, hi_x, hi_y = hext if ax == "h" else vext
        lo, hi = (lo_x[lab], hi_x[lab]) if ax == "h" else (lo_y[lab], hi_y[lab])
        s0, s1 = (sx0, sx1) if ax == "h" else (sy0, sy1)
        along = x if ax == "h" else y
        if hi <= s0 + tol:        # the run ends at the item's near side: the item is at that end of the run
            along = hi + 1
        elif lo >= s1 - tol:
            along = lo - 1
        stops[p].append((along, a))
    for p, st in stops.items():
        st.sort()
        for (_, a), (_, b) in zip(st, st[1:]):
            link(a, b, pnet(p))

    # Points closer together than a line is thick are one place (a corner where runs and a stroke overlap).
    uf = _UF()
    radius = max(3.0, CLUSTER_FRAC * side)
    cells = defaultdict(list)
    for i, k in enumerate(nkind):
        uf.find(i)
        if k in ("tee", "bend", "marked_crossing", "touch", "stroke"):
            cells[(int(pos[i][0] // radius), int(pos[i][1] // radius))].append(i)
    for (cx, cy), members in cells.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cells.get((cx + dx, cy + dy), ()):
                    for i in members:
                        if i < j and abs(pos[i][0] - pos[j][0]) <= radius and abs(pos[i][1] - pos[j][1]) <= radius:
                            uf.union(i, j)
    rep = {i: uf.find(i) for i in range(len(pos))}
    members_of = defaultdict(list)
    for i, r in rep.items():
        members_of[r].append(i)
    cadj = defaultdict(dict)
    for u, vs in adj.items():
        for v, net in vs.items():
            if rep[u] != rep[v]:
                cadj[rep[u]][rep[v]] = net
                cadj[rep[v]][rep[u]] = net
    exclude = set(exclude)
    # What each item is to its lines (instrument bubble, actuator on a valve, nozzle on a vessel): item_roles().
    info = {str(s["id"]): s for s in symbols}
    roles = {k: r for k, r in item_roles(info, g["symbols"], side).items() if k not in exclude}
    rep0, members0 = rep, members_of

    def build(roles):
        # Items: an attachment point at a run's end IS the item; one with line on both sides is a branch point (the item
        # sits beside a run that carries on), so the item hangs off it.
        rep = dict(rep0)
        members_of = defaultdict(list, {k: list(v) for k, v in members0.items()})
        final = defaultdict(dict)
        tap = set()
        for u, vs in cadj.items():
            for v, net in vs.items():
                final[u][v] = net
        assembly = {a: r[1] for a, r in roles.items() if isinstance(r, tuple) and r[0] == "actuator"}
        # A meeting point inside an item's box, or on its outline just outside it, is the item's own drawing (an outline
        # stroke, an actuator stem, a nozzle stub): lines meeting there meet at the item, not at a junction. An actuator
        # and its valve are one assembly here: a meeting point at either is the valve's (a leader drawn to the valve
        # meets the stem only there). The smallest box that holds the point decides.
        grow = max(radius, g.get("band") or 2)
        inside, strict = {}, set()
        for u in set(rep.values()):
            if any(nkind[i] == "attach" for i in members_of[u]):
                continue
            x = sum(pos[i][0] for i in members_of[u]) / len(members_of[u])
            y = sum(pos[i][1] for i in members_of[u]) / len(members_of[u])
            hits = [((b[2] - b[0]) * (b[3] - b[1]), sid) for sid, b in g["symbols"].items()
                    if b[0] - grow <= x <= b[2] + grow and b[1] - grow <= y <= b[3] + grow]
            if hits:
                sid = min(hits)[1]
                b = g["symbols"][sid]
                if b[0] <= x <= b[2] and b[1] <= y <= b[3]:
                    strict.add(u)
                inside[u] = assembly.get(sid, sid)
        # ...except a tee drawn beside a box (not inside it): meeting points just outside an item that, together, have
        # two or more arms leading away to other items and one into the item are a junction next to the item. Each such
        # group of points becomes one junction node.
        own = defaultdict(set)
        for a, sid in owner.items():
            own[assembly.get(sid, sid)].add(rep[a])

        def leads(prev, cur, sid, comp):
            """Where an arm of a group of meeting points near item sid goes: "own" (into the item, or into an item
            drawn against it, like a nozzle on its vessel), "away" (to another item or a junction), or "stub". It
            passes an attachment of the item that the line carries on past (the item drawn beside that line)."""
            seen = {prev} | comp
            while cur not in seen:
                seen.add(cur)
                nxt = [w for w in final.get(cur, {}) if w not in seen]
                if cur in own[sid]:
                    if not nxt:
                        return "own"
                elif inside.get(cur) == sid:
                    return "own"
                elif cur in owner or cur in inside:  # another item: away, unless drawn against this one
                    other = owner.get(cur) or inside.get(cur)
                    return "own" if box_gap(g["symbols"][other], g["symbols"][sid]) <= grow else "away"
                elif len(final.get(cur, {})) >= 3:
                    return "away"
                if not nxt:
                    return "stub"
                prev, cur = cur, nxt[0]
            return "stub"
        def centre(u):
            return (sum(pos[i][0] for i in members_of[u]) / len(members_of[u]),
                    sum(pos[i][1] for i in members_of[u]) / len(members_of[u]))
        done = set()
        for u0 in sorted(inside):
            if u0 in done:
                continue
            sid, comp, stack = inside[u0], {u0}, [u0]
            while stack:
                for v in final.get(stack.pop(), {}):
                    if v not in comp and inside.get(v) == sid:
                        comp.add(v)
                        stack.append(v)
            done |= comp
            if comp & strict:
                continue
            # ...where two of those arms leave from one place (within SAME_PLACE_FRAC of a symbol side): pipes landing
            # on the item's outline well apart (two nozzles side by side on a vessel's shell, joined only along the
            # shell) each go to the item
            at = [centre(u) for u in comp for v in final.get(u, {})
                  if v not in comp and leads(u, v, sid, comp) == "away"]
            if (not any(math.dist(p, q) <= SAME_PLACE_FRAC * side for i, p in enumerate(at) for q in at[i + 1:])
                    or not any(v in own[sid] for u in comp for v in final.get(u, {}))):
                continue
            r = min(comp)
            for u in sorted(comp - {r}):
                for v, net in final.pop(u, {}).items():
                    final[v].pop(u, None)
                    if v != r:
                        final[r][v] = net
                        final[v][r] = net
                members_of[r] += members_of.pop(u)
                for i in members_of[r]:
                    rep[i] = r
            for a in [v for v in final[r] if v in own[sid]]:  # the item's attachments here: the line carrying on
                for w, net in list(final[a].items()):       # past one now carries on from the junction
                    if w != r:
                        final[a].pop(w)
                        final[w].pop(a, None)
                        final[r][w] = net
                        final[w][r] = net
            for u in comp:
                inside.pop(u, None)
        for u, sid in inside.items():
            for v, net in final.pop(u, {}).items():
                final[v].pop(u, None)
                if v != sid and sid not in exclude:  # inside a left-out item, the line just ends
                    final[v][sid] = net
                    final[sid][v] = net
        for a, sid in owner.items():
            u = rep[a]
            nbrs = {v: n for v, n in final.pop(u, {}).items() if v != sid}
            final.get(sid, {}).pop(u, None)
            if sid in exclude:
                final[u] = nbrs
                continue
            if len(nbrs) >= 2:
                final[u] = nbrs
                tap.add(u)
                final[u][sid] = nnet[a]
                final[sid][u] = nnet[a]
                continue
            for v, net in nbrs.items():
                final[v].pop(u, None)
                final[v][sid] = net
                final[sid][v] = net
            final.setdefault(sid, {})
        items = set(owner.values()) - exclude
        segs, arms = contract(final, items)
        return classify(segs, arms, roles), tap, rep, members_of

    # An actuator is taken as one only if, read without that role, every line it has goes to its valve, to an
    # instrument bubble, or to a point where only those meet (the stem and a leader touching at the valve), and one of
    # them reaches the valve. A flange or reducer drawn beside a valve on its own pipe has a line to something else.
    acts = {k: r[1] for k, r in roles.items() if isinstance(r, tuple) and r[0] == "actuator"}
    if acts:
        plain, *_ = build({k: r for k, r in roles.items() if k not in acts})
        lines = [e for part in ("pipe", "instrument", "actuator", "nozzle") for e in plain[part]]
        nbr = defaultdict(set)
        for x, y in lines:
            nbr[x].add(y)
            nbr[y].add(x)
        for k, v in acts.items():
            fine = lambda x: x == v or roles.get(x) == "instrument"  # noqa: E731
            ok = [x for x in nbr[k] if fine(x) or (x in plain["arms"] and all(fine(y) for y in nbr[x] - {k}))]
            reach = v in nbr[k] or any(v in nbr[x] for x in ok if x in plain["arms"])
            if len(ok) < len(nbr[k]) or not reach:
                del roles[k]
    c, tap, rep, members_of = build(roles)

    # Junctions: position, arms, how they were found, kind, network; ids on the 0-1000 scale.
    jname = {}
    for u in sorted(c["arms"], key=lambda n: (pos[n][1], pos[n][0])):
        ks = {nkind[i] for i in members_of[u]}
        xs = [pos[i][0] for i in members_of[u]]
        ys = [pos[i][1] for i in members_of[u]]
        x, y = sum(xs) / len(xs), sum(ys) / len(ys)
        basis = ("marked_crossing" if "marked_crossing" in ks else "item_beside_run" if u in tap else
                 "tee" if "tee" in ks else "short_stroke" if "stroke" in ks else "branch")
        kind = c["kinds"][u]
        if kind == "pipe_tee" and basis == "marked_crossing":
            kind = "marked_crossing"
        jid = f"J{len(jname) + 1:04d}"
        jname[u] = jid
        out["junctions"][jid] = {"x": x, "y": y, "arms": c["arms"][u], "basis": basis, "kind": kind,
                                 "network": nnet[u]}
    nm = lambda n: jname.get(n, n)  # noqa: E731
    for (a, b), v in c["pipe"].items():
        k = tuple(sorted((nm(a), nm(b))))
        taps = [nm(t) for t in v["taps"]]
        if k != (nm(a), nm(b)):
            taps.reverse()
        out["segments"].append(k + (v["network"],))
        if taps:
            out["segment_taps"][k] = taps
        for t in taps:
            out["junctions"][t]["on_segment"] = k
    out["roles"] = roles
    for name, part in (("instrument_lines", "instrument"), ("actuator_stems", "actuator"),
                       ("nozzle_stubs", "nozzle")):
        out[name] = sorted((nm(a), nm(b), net) for (a, b), net in c[part].items())
    # Items drawn against each other (a blind flange on a valve's end, a reducer against a valve, a nozzle or flange
    # on a vessel's shell): no line between them and nothing between them either, so they are consecutive on the
    # pipe. Process items only (not a bubble or an actuator); a nozzle mark against its own vessel is its nozzle.
    # Such a segment has no traced line, so it is on no line network (network None) unless both ends already share
    # one; out["touching"] lists them.
    joined = {frozenset(x[:2]) for part in ("segments", "instrument_lines", "actuator_stems", "nozzle_stubs")
              for x in out[part]}
    nets_of = defaultdict(set)
    for r, ms in g["networks"].items():
        for x in ms:
            nets_of[x].add(int(r))
    proc = sorted(k for k in g["symbols"] if k not in exclude and roles.get(k) is None
                  or isinstance(roles.get(k), tuple) and roles[k][0] == "nozzle" and k not in exclude)
    out["touching"] = []
    for i, a in enumerate(proc):
        for b in proc[i + 1:]:
            if frozenset((a, b)) in joined or box_gap(g["symbols"][a], g["symbols"][b]) > TOUCH_FRAC * side:
                continue
            common = nets_of[a] & nets_of[b]
            net = min(common) if len(common) == 1 else None
            noz = [x for x, y in ((a, b), (b, a)) if roles.get(x) == ("nozzle", y)]
            if noz:
                out["nozzle_stubs"].append((noz[0], b if noz[0] == a else a, net))
            elif not any(isinstance(roles.get(x), tuple) for x in (a, b)):
                out["segments"].append((a, b, net))
            else:
                continue
            out["touching"].append((a, b))
    out["segments"].sort(key=lambda s: (s[0], s[1]))
    out["nozzle_stubs"].sort(key=lambda s: (s[0], s[1]))
    # The network layer: networks joining two or more items. One with a single item (a line leaving the sheet with
    # no connector, the unerased edge of a symbol's own outline) carries no link and is only counted.
    out["networks"] = {int(r): list(ms) for r, ms in g["networks"].items() if len(ms) >= 2}
    out["single_item_networks"] = sum(1 for ms in g["networks"].values() if len(ms) < 2)
    for a, b, net in out["segments"] + out["instrument_lines"] + out["actuator_stems"] + out["nozzle_stubs"]:
        for e in (a, b):
            if net is None and ((a, b) in out["touching"] or (b, a) in out["touching"]):
                continue  # drawn against each other: no traced line, so on no network
            if e in out["junctions"]:
                if out["junctions"][e]["network"] != net:
                    out["problems"].append(f"segment {a}-{b}: junction {e} is on another network")
            elif e not in out["networks"].get(net, ()):
                out["problems"].append(f"segment {a}-{b}: {e} is not a member of network {net}")
    pairs = {frozenset((l["from"], l["to"])) for l in links}
    derived = {frozenset((a, b)) for ms in out["networks"].values() for i, a in enumerate(ms) for b in ms[i + 1:]}
    if o.get("emit") == "all" and o.get("max_clique", 10 ** 9) >= 10 ** 9 and pairs != derived:
        out["problems"].append(f"pairwise links differ from network co-membership ({len(pairs ^ derived)} differ)")
    return out


# ------------------------------------------------------------------ an extracted twin

def _sheet_symbols(model):
    out = defaultdict(dict)
    for key in ("units", "instruments", "line_items", "offpage_connectors"):
        for item in model.get(key, []):
            for p in item.get("provenance") or []:
                out[str(p["sheet"])][p["symbol"]] = {"id": p["symbol"], "class": p.get("class"),
                                                     "box": p["box_0_1000"], "asset": item["id"],
                                                     "tag": item.get("tag"), "unit": key == "units"}
    return out


def line_pieces(lines, junctions):
    """The pieces a network's lines (all kinds) make when items are line ends, not pass-through points: groups of
    junctions joined by lines, with the items on them, and each item-to-item line alone. More than one piece means the
    tracer joined lines that meet only at an item's edge. Returns (pieces, items shared by two or more pieces)."""
    groups = pipe_networks([tuple(x[:2]) for x in lines], set(junctions))
    seen = defaultdict(int)
    for g in groups:
        for m in g["members"]:
            seen[m] += 1
    return len(groups), sorted(m for m, n in seen.items() if n >= 2)


def enrich(model, images, **opt):
    """Add model["line_layers"] to an extracted twin (plant_model.json). images: {sheet: png path}. Refuses when the
    re-traced links are not exactly the twin's own extracted links: the layers must come from the same geometry."""
    if (model.get("meta") or {}).get("model_kind") != "extracted_twin":
        raise ValueError("not an extracted twin (meta.model_kind != extracted_twin); a hand-built model's streams are "
                         "already pipe-level, and a DEXPI model gets its layers from scripts/dexpi_reader.py")
    syms = _sheet_symbols(model)
    by_pair = defaultdict(set)
    for s in model.get("streams", []):
        if s.get("kind") == "extracted_link":
            by_pair[str(s["sheet"])].add(frozenset((s["from_symbol"], s["to_symbol"])))
    nets, juncs, segs, sheets = [], [], [], {}
    other = {"instrument_lines": [], "actuator_stems": [], "nozzle_stubs": []}
    prefix = {"instrument_lines": "IL", "actuator_stems": "AS", "nozzle_stubs": "NZ"}
    for sheet in sorted(syms, key=lambda s: (len(s), s)):
        if sheet not in images:
            raise ValueError(f"no image for sheet {sheet} (give --image {sheet}=PNG)")
        img = Path(images[sheet])
        S = traced_layers(img, list(syms[sheet].values()), **opt)
        traced = {frozenset((l["from"], l["to"])) for l in S["links"]}
        if traced != by_pair.get(sheet, set()):
            raise ValueError(f"sheet {sheet}: re-traced links differ from the twin's ({len(traced ^ by_pair.get(sheet, set()))} "
                             "differ); the layers would not describe the same lines")
        if S["problems"]:
            raise ValueError(f"sheet {sheet}: " + "; ".join(S["problems"][:5]))
        W, H = S["size"]
        side = S["side"]
        asset = {k: v["asset"] for k, v in syms[sheet].items()}
        box = {k: v["box"] for k, v in syms[sheet].items()}
        jid, used = {}, set()
        for j, v in sorted(S["junctions"].items()):
            x, y = 1000 * v["x"] / W, 1000 * v["y"] / H
            name = f"S{sheet}-JN-{round(x):03d}-{round(y):03d}"
            k = 1
            while name in used:
                k += 1
                name = f"S{sheet}-JN-{round(x):03d}-{round(y):03d}-{k}"
            used.add(name)
            jid[j] = name
        net_ids = {}
        for n, (root, ms) in enumerate(sorted(S["networks"].items(), key=lambda kv: sorted(asset[m] for m in kv[1])), 1):
            net_ids[root] = f"S{sheet}-NET{n:03d}"
        name = lambda e: jid.get(e) or asset[e]  # noqa: E731
        first = len(segs)
        touch = {frozenset(x) for x in S["touching"]}
        for a, b, root in S["segments"]:
            taps = [jid[t] for t in S["segment_taps"].get((a, b), [])]
            segs.append({"from": name(a), "to": name(b), "sheet": sheet, "network": net_ids.get(root),
                         **({"taps": taps} if taps else {}),
                         **({"touching": True} if frozenset((a, b)) in touch else {}), "_key": (a, b)})
        sheet_segs = segs[first:]
        for part in other:
            for a, b, root in S[part]:
                other[part].append({"from": name(a), "to": name(b), "sheet": sheet, "network": net_ids.get(root),
                                    **({"touching": True} if frozenset((a, b)) in touch else {})})
        hb = JUNCTION_BOX_FRAC * side
        for j, v in sorted(S["junctions"].items(), key=lambda kv: jid[kv[0]]):
            bx = [round(1000 * (v["x"] - hb) / W, 1), round(1000 * (v["y"] - hb) / H, 1),
                  round(1000 * (v["x"] + hb) / W, 1), round(1000 * (v["y"] + hb) / H, 1)]
            on = next(s for s in sheet_segs if s["_key"] == v["on_segment"]) if v.get("on_segment") else None
            juncs.append({"id": jid[j], "sheet": sheet, "network": net_ids[v["network"]],
                          "at_0_1000": [round(1000 * v["x"] / W, 1), round(1000 * v["y"] / H, 1)],
                          "arms": v["arms"], "junction_kind": v["kind"], "junction_method": v["basis"],
                          **({"_on": on} if on else {}),
                          "provenance": [{"sheet": sheet, "box_0_1000": bx, "source_run": "scripts/line_layers.py",
                                          "model": None}]})
        lines_of = defaultdict(list)
        for kind, rows in (("pipe", S["segments"]), ("instrument", S["instrument_lines"]),
                           ("actuator", S["actuator_stems"]), ("nozzle", S["nozzle_stubs"])):
            for row in rows:
                lines_of[row[2]].append((kind,) + tuple(row[:2]))
        for root, ms in S["networks"].items():
            mem = sorted({asset[m] for m in ms})
            bs = [box[m] for m in ms]
            mine = [j for j, v in S["junctions"].items() if v["network"] == root]
            count = {k: sum(x[0] == k for x in lines_of[root]) for k in ("pipe", "instrument", "actuator", "nozzle")}
            pieces, shared = line_pieces([x[1:] for x in lines_of[root]], mine)
            nets.append({"id": net_ids[root], "sheet": sheet, "members": mem,
                         "junctions": sorted(jid[j] for j in mine),
                         "pairwise_links": len(ms) * (len(ms) - 1) // 2,
                         "lines": count,
                         **({"joined_only_at": sorted(asset[m] for m in shared)} if pieces > 1 and shared else {}),
                         "provenance": [{"sheet": sheet, "box_0_1000": [min(b[0] for b in bs), min(b[1] for b in bs),
                                                                        max(b[2] for b in bs), max(b[3] for b in bs)],
                                         "source_run": "scripts/line_layers.py", "model": None}]})
        kinds = defaultdict(int)
        for v in S["junctions"].values():
            kinds[v["kind"]] += 1
        sheets[sheet] = {"image_sha256": hashlib.sha256(img.read_bytes()).hexdigest(), "side_px": round(side, 1),
                         "crossings": S["crossings"], "networks": len(S["networks"]),
                         "single_item_networks": S["single_item_networks"],
                         "junctions": len(S["junctions"]), "junction_kinds": dict(sorted(kinds.items())),
                         "segments": len(S["segments"]), "instrument_lines": len(S["instrument_lines"]),
                         "actuator_stems": len(S["actuator_stems"]), "nozzle_stubs": len(S["nozzle_stubs"]),
                         "pairwise_links": len(S["links"])}
    nets.sort(key=lambda n: n["id"])
    order = lambda s: (len(s["sheet"]), s["sheet"], sorted((s["from"], s["to"])))  # noqa: E731
    segs.sort(key=order)
    for n, s in enumerate(segs, 1):
        s["id"] = f"S{s['sheet']}-PS{n:03d}"
    for j in juncs:
        if "_on" in j:
            j["on_segment"] = j.pop("_on")["id"]
    for part, rows in other.items():
        rows.sort(key=order)
        for n, s in enumerate(rows, 1):
            s["id"] = f"S{s['sheet']}-{prefix[part]}{n:03d}"
    first = lambda s: {"id": s["id"], **{k: v for k, v in s.items() if k not in ("id", "_key")}}  # noqa: E731
    model["line_layers"] = {
        "schema": SCHEMA, "method": "scripts/line_layers.py on the tracer's own geometry (trace_connections.trace, "
                                   "default options): the pairwise links are unchanged",
        "definitions": DEFINITIONS,
        "crossings": "a 4-arm crossing joins the two runs' networks (the tracer's default) but is not a pipe "
                     "junction unless the drawing marks it connected (a dot)",
        "line_kinds": "which line is which (item_roles, classify): a line to an instrument bubble is an instrument "
                      "connection; a short stem from a valve to the small symbol stacked on it is an actuator stem; "
                      "the stub from a nozzle mark (N1, N2...) to its vessel is part of the vessel; the rest is pipe",
        "sheets": sheets, "networks": nets, "junctions": juncs,
        "segments": [first(s) for s in segs],
        **{part: [first(s) for s in rows] for part, rows in other.items()}}
    return model


# ------------------------------------------------------------------ ground truth: DEXPI XML

def dexpi_truth(xml_path, graphml_path, png_path):
    """The pipe layer as the DEXPI XML defines it, in the answer key's node ids (scripts/adapt_dexpi.py keys): each
    PipingNetworkSegment's chain (From item, in-line items in order, To item), nozzles standing for their equipment,
    PipeTee elements as junctions. Measuring and signal lines (InformationFlow) are not pipes and are left out.
    Returns {"items", "junctions" {id: (x, y) px or None}, "segments" {(a, b)}, "tees_not_branching"}."""
    import adapt_dexpi as ad
    import score_pid2graph as sc
    model = ad.convert_xml(Path(xml_path))
    nodes = model["nodes"]
    root = ET.parse(xml_path).getroot()
    parent = {c: p for p in root.iter() for c in p}
    by_id = {e.get("ID"): e for e in root.iter() if e.get("ID")}

    def resolve(i):
        if i in nodes:
            return i
        e = by_id.get(i)
        while e is not None:
            e = parent.get(e)
            if e is not None and e.get("ID") in nodes and e.tag == "Equipment":
                return e.get("ID")
        return None
    adj = defaultdict(dict)
    for seg in root.iter("PipingNetworkSegment"):
        conn = seg.find("Connection")
        chain = ([conn.get("FromID")] if conn is not None and conn.get("FromID") else [])
        chain += [c.get("ID") for c in seg if c.tag in ("PipingComponent", "PipeOffPageConnector")]
        chain += ([conn.get("ToID")] if conn is not None and conn.get("ToID") else [])
        res = []
        for i in chain:
            r = resolve(i)
            if r is not None and (not res or res[-1] != r):
                res.append(r)
        for a, b in zip(res, res[1:]):
            adj[a][b] = 0
            adj[b][a] = 0
    tees = {k for k, v in nodes.items() if v["class"] == "connector"}
    items = {k for k, v in nodes.items() if v["class"] in sc.SCORED}
    segs, arms = contract(adj, items)
    w, h = sc.png_size(png_path)
    key_nodes, _ = sc.load_key(graphml_path, w, h)
    gx = {}
    g = ET.parse(graphml_path).getroot()
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    keys = {k.get("id"): k.get("attr.name") for k in g.iter(ns + "key")}
    for n in g.iter(ns + "node"):
        d = {keys.get(x.get("key")): x.text for x in n}
        if d.get("label") == "connector":
            b = [float(d.get(k) or 0) for k in ("xmin", "ymin", "xmax", "ymax")]
            gx[n.get("id")] = None if b == [0.0, 0.0, 0.0, 0.0] else ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    return {"items": items, "junctions": {j: gx.get(j) for j in arms}, "arms": dict(arms), "segments": set(segs),
            "tees_not_branching": len(tees - set(arms)), "source": "DEXPI XML PipingNetworkSegment chains"}


# ------------------------------------------------------------------ ground truth: the PID2Graph key graph (derived)

def pid2graph_truth(graphml_path, png_path):
    """A DERIVED pipe-level truth from a PID2Graph key graph. The key is a graph, not a list of pairs: symbol nodes
    plus `connector` nodes (always 2 edges: a point along a line) and `crossing` nodes (1 to 4 edges; with 3 they are
    where lines meet, a tee) and `arrow` nodes on the lines. Derivation (the same contract() as every other truth):
    symbols (score_pid2graph.SCORED) are items; connector, crossing and arrow nodes are line points, walked through
    when they have 2 edges and junctions when they have 3 or more; a line point that ends with no symbol is pruned;
    `background` nodes are left out. Limits: a 4-edge crossing is taken as a 4-arm junction (the key does not say
    whether the two lines pass or join; 2 on OPEN100 sheets 0-5, both on sheet 5); the key does not say which lines
    are pipe and which are instrument lines, so the split is made by the symbols' classes (classify_truth), exactly as
    on the traced side; actuator symbols and nozzles are in-line items here. Junction positions are the crossing
    boxes' centres. Also returns whether the line networks it implies give exactly the key's all-pairs links (the
    pairs every OPEN100 connection score uses), as a check that the derivation read the graph whole."""
    import score_pid2graph as sc
    w, h = sc.png_size(png_path)
    nodes, adj = sc.load_key(graphml_path, w, h)
    items = {k for k, v in nodes.items() if v["class"] in sc.SCORED}
    line = items | {k for k, v in nodes.items() if v["class"] in sc.PASS_THROUGH}
    g = {u: {v: 0 for v in adj[u] if v in line} for u in line}
    segs, arms = contract(g, items)
    pos = {j: ((nodes[j]["box"][0] + nodes[j]["box"][2]) / 2 * w / 1000,
               (nodes[j]["box"][1] + nodes[j]["box"][3]) / 2 * h / 1000) for j in arms}
    nets = pipe_networks(list(segs), set(arms))
    implied = {frozenset((a, b)) for n in nets for i, a in enumerate(n["members"]) for b in n["members"][i + 1:]}
    return {"items": items, "junctions": pos, "arms": dict(arms), "segments": set(segs),
            "networks_match_key_pairs": implied == sc.asset_links(nodes, adj),
            "source": "derived from the PID2Graph key graph (symbol, connector/crossing/arrow chains, symbol)"}


def all_lines(pred):
    """Every drawn line a traced sheet reads, whatever its kind, with each pipe segment split again at its instrument
    taps: what a truth that does not tell pipe from instrument lines has."""
    out = []
    for a, b, *_ in pred["segments"]:
        chain = [a] + pred.get("segment_taps", {}).get((a, b), []) + [b]
        out += list(zip(chain, chain[1:]))
    for part in ("instrument_lines", "actuator_stems", "nozzle_stubs"):
        out += [tuple(x[:2]) for x in pred.get(part, [])]
    return {"junctions": pred["junctions"], "segments": [tuple(sorted(x)) for x in out]}


# ------------------------------------------------------------------ ground truth: this repository's drawer

def drawn_truth(model_path, layout_path, manifest_path=None, key_path=None):
    """The pipe layer of the TE / Bayer sheets as scripts/draw_pid_from_model.py drew them, in the key's node ids:
    each route's points with its valves (in-line items), instrument taps (a junction on the line plus the bubble),
    unit and flag ends, and tee / header ("net") ends landing on another route; unit-mounted bubbles joined to their
    unit by their leader. Signal lines are not pipes and are left out. Refuses when the manifest's generator, model
    or layout hash differs using the writer's CRLF-to-LF text identity (other bytes remain significant), and, given the sheets'
    key.json, when the line networks this truth implies are not exactly the key's (a check that the routes were read
    right). Returns {sheet: truth}."""
    import draw_pid_from_model as dp
    if manifest_path:
        man = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        for f, k in ((dp.__file__, "generator_sha256"), (model_path, "model_sha256"), (layout_path, "layout_sha256")):
            if dp.sha_file(f) != man.get(k):
                raise ValueError(f"{Path(manifest_path).parent.name}: drawn by another version ({k} differs from "
                                 f"{Path(f).name} now); its pipe topology can't be re-derived")
    seen, mounts = {}, defaultdict(list)
    orig_connect, orig_group = dp.Sheet.connect, dp.Sheet.link_group

    def spy_connect(self, routes, unit_nodes, flag_nodes):
        seen[self.spec["id"]] = (self, routes, unit_nodes, flag_nodes)
        self._in_connect = True
        return orig_connect(self, routes, unit_nodes, flag_nodes)

    def spy_group(self, members, at):
        if not getattr(self, "_in_connect", False):
            mounts[self.spec["id"]].append([m for m in members if m])
        return orig_group(self, members, at)
    dp.Sheet.connect, dp.Sheet.link_group = spy_connect, spy_group
    try:
        dp.generate(model_path, layout_path, None, write=False)
    finally:
        dp.Sheet.connect, dp.Sheet.link_group = orig_connect, orig_group
    out = {}
    for sid, (sh, routes, unit_nodes, flag_nodes) in seen.items():
        all_routes = sh.spec["routes"] + sh.extra_routes
        anchors = defaultdict(list)        # route id -> [(t, node)]
        adj = defaultdict(dict)
        items, pos = set(), {}

        def joint(p):
            k = ("pt", round(p[0]), round(p[1]))
            pos[k] = (p[0], p[1])
            return k

        def end_node(end, p):
            if "unit" in end:
                items.add(unit_nodes[end["unit"]])
                return unit_nodes[end["unit"]]
            if "flag" in end:
                items.add(flag_nodes[end["flag"]])
                return flag_nodes[end["flag"]]
            return joint(p)
        net_routes = defaultdict(list)
        for r in all_routes:
            for key in ("from", "to"):
                if "net" in r[key]:
                    net_routes[r[key]["net"]].append(r["id"])
        for r in all_routes:
            rid, rr = r["id"], routes[r["id"]]
            pts, L = rr["pts"], dp.length(rr["pts"])
            anchors[rid].append((0.0, end_node(r["from"], pts[0])))
            anchors[rid].append((L, end_node(r["to"], pts[-1])))
            for t, nid in rr["valves"]:
                anchors[rid].append((t, nid))
                items.add(nid)
            for t, bid in rr["taps"]:
                j = joint(dp.point_at(pts, t)[0])
                anchors[rid].append((t, j))
                adj[j][bid] = adj[bid][j] = rid
                items.add(bid)
            for key, p in (("from", pts[0]), ("to", pts[-1])):
                end = r[key]
                targets = [end["tee"]] if "tee" in end else net_routes.get(end.get("net"), []) if "net" in end else []
                for tid in targets:
                    if tid == rid:
                        continue
                    loc = dp.locate(routes[tid]["pts"], tuple(end["at"]) if "at" in end else tuple(p))
                    if loc is not None:
                        anchors[tid].append((loc[0], joint(end["at"] if "at" in end else p)))
        for rid, an in anchors.items():
            an.sort(key=lambda x: x[0])
            for (_, a), (_, b) in zip(an, an[1:]):
                if a != b:
                    adj[a][b] = adj[b][a] = rid
        for ms in mounts[sid]:
            for a in ms[1:]:
                adj[ms[0]][a] = adj[a][ms[0]] = "mount"
                items.update((ms[0], a))
        segs, arms = contract(adj, items)
        names = {j: f"T{n + 1:03d}" for n, j in enumerate(sorted(arms, key=lambda k: (pos[k][1], pos[k][0])))}
        out[sid] = {"items": items, "junctions": {names[j]: pos[j] for j in arms},
                    "arms": {names[j]: n for j, n in arms.items()},
                    "segments": {tuple(sorted((names.get(a, a), names.get(b, b)))) for a, b in segs},
                    "networks": pipe_networks([tuple(s) for s in segs], set(arms)),
                    "source": "scripts/draw_pid_from_model.py routes, valves, taps and tee points (current version)"}
    if key_path:
        key = json.loads(Path(key_path).read_text(encoding="utf-8"))
        for sid, t in out.items():
            groups = defaultdict(set)
            for a, b in key["sheets"][sid]["edges"]:
                c, m = (a, b) if a.startswith("connector") else (b, a)
                groups[c].add(m)
            if {frozenset(v) for v in groups.values()} != {frozenset(n["members"]) for n in t["networks"]}:
                raise ValueError(f"sheet {sid}: the pipe truth's line networks are not the key's; the routes were "
                                 "not read as drawn")
    return out


# ------------------------------------------------------------------ the scorer

def classify_truth(truth, roles):
    """A truth (dexpi_truth / drawn_truth, every drawn line) split the way classify() splits a traced sheet, by the
    traced sheet's instrument roles (the answer key's instrumentation class): "segments" becomes the process pipe
    alone (through instrument taps), "instrument_lines" the instrument connections, "kinds" each junction's kind.
    Actuator and nozzle roles are read from boxes, so they are not imposed on a truth: an actuator the truth has as an
    in-line item stays a pipe end there, and a stem the tracing took for an actuator counts as a missed segment."""
    c = classify({tuple(x): 0 for x in truth["segments"]}, truth.get("arms") or {j: 3 for j in truth["junctions"]},
                 {k: r for k, r in roles.items() if r == "instrument"})
    return {**truth, "all_segments": set(truth["segments"]), "segments": set(c["pipe"]),
            "instrument_lines": {frozenset(x) for x in c["instrument"]},
            "junctions": {j: truth["junctions"][j] for j in c["arms"]}, "kinds": c["kinds"]}


def match_junctions(pred, truth, side):
    """{predicted junction: truth junction}, one to one. Nearest first, within half a symbol side (both must have a
    position); then each truth junction with no position (a DEXPI tee with no drawn shape) goes to the unmatched
    predicted junction with the most neighbours in common, items or junctions already matched, at least two."""
    pj = {j: (v["x"], v["y"]) for j, v in pred["junctions"].items()}
    tj = dict(truth["junctions"])
    pairs = sorted((math.dist(p, t), a, b) for a, p in pj.items() for b, t in tj.items()
                   if t is not None and math.dist(p, t) <= 0.5 * side)
    match, used = {}, set()
    for d, a, b in pairs:
        if a not in match and b not in used:
            match[a] = b
            used.add(b)

    def nbrs(segs, j):
        return {b if a == j else a for a, b in segs if j in (a, b)}
    psegs = {tuple(sorted(s[:2])) for s in pred["segments"]}
    tsegs = set(truth["segments"])
    # A truth junction with no position: the unmatched predicted junction with the most neighbours in common, items
    # or junctions already matched (a tee between two tees has one item neighbour), at least two; repeated until no
    # new match, as each match can place the next.
    found = True
    while found:
        found = False
        for b in sorted(j for j, t in tj.items() if t is None and j not in used):
            tn = {x for x in nbrs(tsegs, b) if x not in tj or x in used}
            best = max(((len(tn & {match.get(x, x) for x in nbrs(psegs, a) if x not in pj or x in match}), a)
                        for a in pj if a not in match), default=(0, None))
            if best[0] >= 2:
                match[best[1]] = b
                used.add(b)
                found = True
    return match


def score_pipe(pred, truth, side):
    """Precision / recall of the pipe layer. pred: traced_layers() output; truth: dexpi_truth / drawn_truth, through
    classify_truth() when its lines are not all pipe. Junctions are matched by match_junctions(). A predicted segment
    is right when its two ends, after junction matching, are a truth segment. Also reported: item-to-item segments
    alone (no junction matching involved), junction counts, instrument connections (when the truth has them) and how
    many matched junctions are of the same kind."""
    pj = {j: (v["x"], v["y"]) for j, v in pred["junctions"].items()}
    tj = dict(truth["junctions"])
    match = match_junctions(pred, truth, side)
    psegs = {tuple(sorted(s[:2])) for s in pred["segments"]}
    tsegs = set(truth["segments"])
    m = lambda x: match.get(x, "pred:" + x if x in pj else x)  # noqa: E731
    mapped = {tuple(sorted((m(a), m(b)))) for a, b in psegs}
    tp = len(mapped & tsegs)

    def prf(t, p, k):
        P, R = (t / p if p else 0.0), (t / k if k else 0.0)
        return {"tp": t, "predicted": p, "truth": k, "precision": round(P, 3), "recall": round(R, 3),
                "f1": round(2 * t / (p + k), 3) if p + k else 0.0}
    ii_p = {s for s in psegs if s[0] not in pj and s[1] not in pj}
    ii_t = {s for s in tsegs if s[0] not in tj and s[1] not in tj}
    out = {"segments": prf(tp, len(psegs), len(tsegs)), "item_to_item": prf(len(ii_p & ii_t), len(ii_p), len(ii_t)),
           "junctions": prf(len(match), len(pj), len(tj)),
           "crossings": pred.get("crossings"), "truth_source": truth.get("source")}
    if "instrument_lines" in truth:
        pi = {frozenset((m(a), m(b))) for a, b, *_ in pred.get("instrument_lines", [])}
        out["instrument_lines"] = prf(len(pi & truth["instrument_lines"]), len(pi), len(truth["instrument_lines"]))
    if "kinds" in truth:
        same = sum(pred["junctions"][a].get("kind") == truth["kinds"].get(b) for a, b in match.items())
        out["junction_kinds"] = {"matched": len(match), "same_kind": same,
                                 "truth": dict(sorted(Counter(truth["kinds"].values()).items())),
                                 "predicted": dict(sorted(Counter(v.get("kind") for v in pred["junctions"].values())
                                                          .items()))}
    return out


def total(scores):
    out = {}
    for k in ("segments", "item_to_item", "junctions", "instrument_lines", "all_lines"):
        if not all(k in s for s in scores):
            continue
        t, p, n = (sum(s[k][x] for s in scores) for x in ("tp", "predicted", "truth"))
        out[k] = {"tp": t, "predicted": p, "truth": n, "precision": round(t / p, 3) if p else 0.0,
                  "recall": round(t / n, 3) if n else 0.0, "f1": round(2 * t / (p + n), 3) if p + n else 0.0}
    return out


# scope "all": the truth has every drawn line (pipes, instrument taps, mounted instruments' leaders), so everything
# traced is scored. scope "process": the truth has the piping only (DEXPI's measuring and signal lines are
# InformationFlow, not pipes, and where they meet a pipe is no element of the file), so instrument symbols are left
# out of the traced pipe layer before scoring (their lines become dead ends; a branch they made is passed through).
SETS = {
    "dexpi": {"dir": "data/external/dexpi/sheets", "sheets": ["dexpi-c01", "dexpi-c02", "dexpi-c03"],
              "scope": "process"},
    "te": {"dir": "data/te_pid", "sheets": ["101", "102", "103"], "model": "data/te_process_model.json",
           "layout": "data/te_pid_layout.json", "scope": "all"},
    "bayer": {"dir": "data/bayer_rt/pid", "sheets": ["RT1"], "model": "data/bayer_rt/process_model.json",
              "layout": "data/bayer_rt/pid_layout.json", "scope": "all"},
    # OPEN100 development sheets: a truth DERIVED from the key graph (pid2graph_truth), labelled as such
    "open100": {"dir": "data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100",
                "sheets": ["0", "1", "2", "3", "4", "5"], "scope": "all", "truth": "pid2graph"},
    # DEXPI 1.2 vendor exports keyed on their own renders (scripts/corpus_adapters.py build_vendor_keys, adapter A2):
    # every <id>.json sidecar there with status "mapped" is a sheet; its "xml" is the truth
    "dexpi-1.2-vendor": {"dir": "data/external/dexpi-ttc-all/vendor-keys", "sheets": None, "scope": "process",
                         "truth": "dexpi_sidecar"},
}


def sidecar(base, sheet, source_paths=None):
    """A keyed sheet's <sheet>.json (corpus_adapters.build_vendor_key), or {}."""
    f = Path(base) / f"{sheet}.json"
    if source_paths is not None and f.is_file():
        source_paths.append(f)
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def set_sheets(name, base=None, source_paths=None):
    cfg = SETS[name]
    if cfg["sheets"] is not None:
        return list(cfg["sheets"])
    base = Path(base) if base else ROOT / cfg["dir"]
    return sorted(f.stem for f in base.glob("*.json")
                  if sidecar(base, f.stem, source_paths).get("status") == "mapped")


def dexpi_xml(sheet, source_paths=None):
    import adapt_dexpi as A
    import dexpi_to_twin as d2t
    if source_paths is not None:
        source_paths.append(A.CONFIG)
    _, spec = d2t.sheet_spec(sheet)
    return A.local_path(spec["xml"])


def key_symbols(graphml, png):
    import score_pid2graph as sc
    w, h = sc.png_size(png)
    nodes, _ = sc.load_key(graphml, w, h)
    return [{"id": k, "class": v["class"], "box": v["box"]} for k, v in nodes.items() if v["class"] in sc.SCORED]


def score_set(name, sheets=None, base=None, source_paths=None):
    """Trace each sheet of a set with the answer key's symbols and score its pipe layer against the topology truth.
    base: the set's folder, if not its usual one (a set read from sidecars). Returns {"set", "sheets": {sheet:
    score}, "total"}."""
    cfg = SETS[name]
    base = Path(base) if base else ROOT / cfg["dir"]
    source_paths = source_paths if source_paths is not None else []
    sheets = sheets or set_sheets(name, base, source_paths)
    if "model" in cfg:
        source_paths.extend([ROOT / cfg["model"], ROOT / cfg["layout"],
                             base / "manifest.json", base / "key.json", ROOT / "scripts/draw_pid_from_model.py"])
    truth_all = (drawn_truth(ROOT / cfg["model"], ROOT / cfg["layout"], base / "manifest.json", base / "key.json")
                 if "model" in cfg else None)
    per = {}
    for s in sheets:
        png, gml = base / f"{s}.png", base / f"{s}.graphml"
        source_paths.extend([png, gml])
        syms = key_symbols(gml, png)
        skip = {x["id"] for x in syms if x["class"] == "instrumentation"} if cfg["scope"] == "process" else ()
        pred = traced_layers(png, syms, exclude=skip)
        if truth_all:
            raw = truth_all[s]
        elif cfg.get("truth") == "pid2graph":
            raw = pid2graph_truth(gml, png)
        else:
            xml = (dexpi_xml(s, source_paths) if cfg.get("truth") != "dexpi_sidecar"
                   else Path(sidecar(base, s, source_paths)["xml"]))
            source_paths.append(xml if Path(xml).is_absolute() else ROOT / xml)
            raw = dexpi_truth(xml if Path(xml).is_absolute() else ROOT / xml, gml, png)
        truth = classify_truth(raw, pred["roles"])
        per[s] = score_pipe(pred, truth, pred["side"] or 20)
        if cfg["scope"] == "all":  # every drawn line, whatever its kind: the geometry alone
            per[s]["all_lines"] = score_pipe(all_lines(pred), raw, pred["side"] or 20)["segments"]
        if "networks_match_key_pairs" in raw:
            per[s]["truth_networks_match_key_pairs"] = raw["networks_match_key_pairs"]
        per[s]["counts"] = {"pred_networks": len(pred["networks"]), "pred_junctions": len(pred["junctions"]),
                            "pred_segments": len(pred["segments"]), "pairwise_links": len(pred["links"]),
                            "pred_instrument_lines": len(pred["instrument_lines"]),
                            "pred_actuator_stems": len(pred["actuator_stems"]),
                            "truth_junctions": len(truth["junctions"]), "truth_segments": len(truth["segments"]),
                            "truth_instrument_lines": len(truth["instrument_lines"])}
        if "tees_not_branching" in truth:
            per[s]["counts"]["truth_tees_with_fewer_than_3_arms"] = truth["tees_not_branching"]
    return {"set": name, "scope": cfg["scope"], "sheets": per, "total": total(list(per.values()))}


# ------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enrich", help="add line_layers to an extracted twin (plant_model.json)")
    e.add_argument("model")
    e.add_argument("--image", action="append", default=[], help="SHEET=PNG, once per sheet")
    e.add_argument("--out", required=True)
    s = sub.add_parser("score", help="pipe layer vs topology ground truth (key symbols, so only tracing is measured)")
    s.add_argument("--set", action="append", choices=sorted(SETS), required=True)
    s.add_argument("--json", help="also write the scores here")
    a = ap.parse_args(argv)
    if a.cmd == "enrich":
        images = {}
        supplied_images = []
        for p in a.image:
            if "=" not in p:
                ap.error(f"--image wants SHEET=PNG, got {p!r}")
            k, v = p.split("=", 1)
            images[k] = v
            supplied_images.append(v)
        try:
            # Updating the model in place is supported. Supplied drawings are always preserved,
            # including an earlier --image later replaced by another entry for the same sheet.
            protect_outputs([a.out], supplied_images)
            m = json.loads(Path(a.model).read_text(encoding="utf-8"))
            enrich(m, images)
            Path(a.out).write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        except (OSError, ValueError) as exc:
            print(f"{a.model}: can't add line layers ({exc})", file=sys.stderr)
            return 1
        ll = m["line_layers"]
        print(json.dumps({"networks": len(ll["networks"]), "junctions": len(ll["junctions"]),
                          "segments": len(ll["segments"]),
                          "pairwise_links": sum(v["pairwise_links"] for v in ll["sheets"].values()),
                          "crossings": {s: v["crossings"] for s, v in ll["sheets"].items()}}) + f" -> {a.out}")
        return 0
    results, source_paths = [], []
    for name in a.set:
        try:
            r = score_set(name, source_paths=source_paths)
        except (OSError, ValueError) as exc:
            print(f"{name}: can't score ({exc})", file=sys.stderr)
            return 1
        results.append(r)
        t = r["total"]
        print(f"{name}: pipe segments P {t['segments']['precision']} R {t['segments']['recall']} F1 "
              f"{t['segments']['f1']} ({t['segments']['tp']}/{t['segments']['predicted']} predicted, "
              f"{t['segments']['truth']} true); item-to-item F1 {t['item_to_item']['f1']}; junctions found "
              f"{t['junctions']['tp']} of {t['junctions']['truth']} ({t['junctions']['predicted']} predicted)")
        if (t.get("instrument_lines") or {}).get("truth") or (t.get("instrument_lines") or {}).get("predicted"):
            il = t["instrument_lines"]
            print(f"  instrument connections F1 {il['f1']} ({il['tp']}/{il['predicted']} predicted, {il['truth']} true)")
        if "all_lines" in t:
            al = t["all_lines"]
            print(f"  every drawn line, any kind, F1 {al['f1']} ({al['tp']}/{al['predicted']} predicted, {al['truth']} "
                  f"true)")
        for sh, v in r["sheets"].items():
            jk = v.get("junction_kinds") or {}
            print(f"  {sh}: segments F1 {v['segments']['f1']} (P {v['segments']['precision']} R "
                  f"{v['segments']['recall']}), item-to-item F1 {v['item_to_item']['f1']}, junctions "
                  f"{v['junctions']['tp']}/{v['junctions']['truth']} (same kind {jk.get('same_kind')}), "
                  f"crossings {v['crossings']}")
    if a.json:
        try:
            protect_outputs([a.json], source_paths)
            Path(a.json).write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8", newline="\n")
        except (OSError, ValueError) as exc:
            print(f"can't write scores ({exc})", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
