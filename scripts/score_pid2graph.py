"""Score a P&ID extraction against a PID2Graph answer key (.graphml).

Scoring rules (fixed 2026-10-07, before any model run; see docs/JOURNAL.md entry 7):

Classes scored (asset-relevant for a digital twin):
    tank, pump, valve, instrumentation, inlet/outlet, general
Not scored (drawing plumbing, not assets): connector, crossing, arrow, background.

Detection: a predicted symbol matches an answer-key symbol by box overlap, IoU (intersection over union), greedy
by highest IoU, one-to-one. Two thresholds are reported:
  - strict  IoU >= 0.5  (the usual object-detection standard)
  - rough   IoU >= 0.1  ("in roughly the right place"; vision models give imprecise coordinates)
Each is reported as "located" (any class: did it find the thing?) and "classified" (class must also agree).
A first centre-in-grown-box rule was rejected after its controls failed: a mislabeled symbol still scored by
landing inside a neighbouring or enclosing symbol's zone (journal entry 7).

Connectivity: the key's graph is collapsed to asset-to-asset links. Two scored symbols are linked when a path joins them
through only connector/crossing/arrow nodes. A predicted connection counts when both ends matched key symbols and those
key symbols are linked. Predicted connections with an unmatched end count as wrong.

Usage: python scripts/score_pid2graph.py <answer_key.graphml> <prediction.json> [--png <image>]
Prints a JSON score. The prediction format is defined in extraction/prompt.md.
"""
import json
import struct
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path

NS = {"g": "http://graphml.graphdrawing.org/xmlns"}
SCORED = ["tank", "pump", "valve", "instrumentation", "inlet/outlet", "general"]
PASS_THROUGH = {"connector", "crossing", "arrow"}
THRESHOLDS = {"strict": 0.5, "rough": 0.1}


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def load_key(graphml, width, height):
    root = ET.parse(graphml).getroot()
    keys = {k.get("id"): k.get("attr.name") for k in root.findall("g:key", NS)}
    g = root.find("g:graph", NS)
    nodes = {}
    for n in g.findall("g:node", NS):
        a = {keys[d.get("key")]: d.text for d in n.findall("g:data", NS)}
        box = [float(a["xmin"]) / width * 1000, float(a["ymin"]) / height * 1000,
               float(a["xmax"]) / width * 1000, float(a["ymax"]) / height * 1000]
        nodes[n.get("id")] = {"class": a["label"], "box": box}
    adj = defaultdict(set)
    for e in g.findall("g:edge", NS):
        s, t = e.get("source"), e.get("target")
        adj[s].add(t)
        adj[t].add(s)
    return nodes, adj


def asset_links(nodes, adj):
    """Undirected asset-to-asset links through pass-through nodes only."""
    links = set()
    for start, n in nodes.items():
        if n["class"] not in SCORED:
            continue
        seen, queue = {start}, deque([start])
        while queue:
            cur = queue.popleft()
            for nxt in adj[cur]:
                if nxt in seen:
                    continue
                seen.add(nxt)
                cls = nodes[nxt]["class"]
                if cls in SCORED:
                    links.add(frozenset((start, nxt)))
                elif cls in PASS_THROUGH:
                    queue.append(nxt)
    return links


def centre(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match(preds, keys, need_class, threshold):
    """Greedy one-to-one match by highest IoU at or above threshold. Returns {pred_id: key_id}."""
    pairs = []
    for p in preds:
        for kid, k in keys.items():
            if need_class and p["class"] != k["class"]:
                continue
            v = iou(p["box"], k["box"])
            if v >= threshold:
                pairs.append((-v, p["id"], kid))
    pairs.sort()
    out, used = {}, set()
    for _, pid, kid in pairs:
        if pid in out or kid in used:
            continue
        out[pid] = kid
        used.add(kid)
    return out


def prf(tp, n_pred, n_key):
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_key if n_key else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "predicted": n_pred, "in_key": n_key,
            "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def valid_symbols(pred):
    out = []
    for s in pred.get("symbols", []):
        box = s.get("box")
        b = s.get("bbox")  # prompt v2: named fields, so axis order can't be ambiguous
        if box is None and isinstance(b, dict):
            box = [b.get("x_min"), b.get("y_min"), b.get("x_max"), b.get("y_max")]
        if (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)
                and s.get("class") in SCORED and s.get("id") is not None):
            out.append({"id": str(s["id"]), "class": s["class"], "box": [float(v) for v in box]})
    return out


def score(graphml, prediction, png):
    width, height = png_size(png)
    nodes, adj = load_key(graphml, width, height)
    keys = {k: v for k, v in nodes.items() if v["class"] in SCORED}
    preds = valid_symbols(prediction)

    result = {"malformed_symbols": len(prediction.get("symbols", [])) - len(preds)}
    for name, t in THRESHOLDS.items():
        result[name] = {
            "located": prf(len(match(preds, keys, False, t)), len(preds), len(keys)),
            "classified": prf(len(match(preds, keys, True, t)), len(preds), len(keys)),
            "by_class": {cls: prf(len(match([p for p in preds if p["class"] == cls],
                                            {k: v for k, v in keys.items() if v["class"] == cls}, True, t)),
                                  sum(1 for p in preds if p["class"] == cls),
                                  sum(1 for v in keys.values() if v["class"] == cls)) for cls in SCORED},
        }
    # Connections are judged on rough location: the question is "which assets connect", not box precision.
    located = match(preds, keys, False, THRESHOLDS["rough"])
    key_links = asset_links(nodes, adj)
    pred_links = set()
    for c in prediction.get("connections", []):
        a, b = located.get(str(c.get("from"))), located.get(str(c.get("to")))
        pred_links.add(frozenset((a, b)) if a and b and a != b else ("unmatched", str(c)))
    hits = sum(1 for l in pred_links if l in key_links)
    result["connections"] = prf(hits, len(pred_links), len(key_links))
    return result


if __name__ == "__main__":
    graphml, pred_path = sys.argv[1], sys.argv[2]
    png = sys.argv[sys.argv.index("--png") + 1] if "--png" in sys.argv else str(Path(graphml).with_suffix(".png"))
    print(json.dumps(score(graphml, json.loads(Path(pred_path).read_text(encoding="utf-8")), png), indent=1))

