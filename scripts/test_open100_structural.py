"""Controls for the OPEN100 structural deliverables: flow-direction rules, plant structure, mimic, 3D scene, LOTO
view and the deliverables matrix.

Synthetic drawings test the direction rules (no answer key involved); the committed outputs are checked for internal
consistency (counts add up, nothing undirected acquires an arrow, every claim in the matrix has its file).

Usage: python scripts/test_open100_structural.py
"""
import json
import re
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ignition"))
import flow_direction as fd  # noqa: E402
import open100_structure as st  # noqa: E402
import deliverables_matrix as dm  # noqa: E402

OUT = ROOT / "out" / "open100_structural"
FAILS = []


def check(name, ok, got=None):
    print(("PASS" if ok else "FAIL") + "  " + name + ("" if ok else "  (got %s)" % (got,)))
    if not ok:
        FAILS.append(name)


def triangle(img, tip, base_x, half, horizontal=True):
    """Filled arrowhead with its tip at `tip`, base at base_x (or base_y), half-width `half`."""
    x, y = tip
    pts = np.array([[x, y], [base_x, y - half], [base_x, y + half]] if horizontal else
                   [[x, y], [x - half, base_x], [x + half, base_x]], np.int32)
    cv2.fillPoly(img, [pts], 0)


def synthetic_rules():
    side = 40
    # classify_bump: a taper pointing +x, its mirror, and things that are not arrowheads
    up = np.array([6, 5, 5, 4, 3, 3, 2, 1, 1, 1])
    check("taper narrowing toward +x is an arrow pointing +x", fd.classify_bump(up, up, side) == 1)
    check("mirror image points -x", fd.classify_bump(up[::-1], up[::-1], side) == -1)
    check("a symmetric bump (dot, ellipse) is not an arrow",
          fd.classify_bump(np.array([1, 3, 5, 6, 6, 5, 3, 1]), np.array([1, 3, 5, 6, 6, 5, 3, 1]), side) is None)
    check("constant width (parallel lines) is not an arrow", fd.classify_bump(np.full(10, 4), np.full(10, 4), side) is None)
    check("ink on one side only (a tee, text) is not an arrow", fd.classify_bump(up, np.zeros(10, int), side) is None)
    check("too short to be an arrow", fd.classify_bump(np.array([3, 2, 1]), np.array([3, 2, 1]), side) is None)

    # arrowheads() on drawn ink: right-pointing on a horizontal line, up-pointing on a vertical, and a bow-tie
    img = np.full((400, 600), 255, np.uint8)
    cv2.line(img, (20, 100), (580, 100), 0, 3)
    triangle(img, (300, 100), 284, 7)
    cv2.line(img, (100, 380), (100, 160), 0, 3)
    xs = 100
    cv2.fillPoly(img, [np.array([[xs, 250], [xs - 7, 266], [xs + 7, 266]], np.int32)], 0)
    cv2.line(img, (200, 300), (580, 300), 0, 3)
    cv2.fillPoly(img, [np.array([[380, 300], [364, 293], [364, 307]], np.int32)], 0)   # pointing +x
    cv2.fillPoly(img, [np.array([[382, 300], [398, 293], [398, 307]], np.int32)], 0)   # pointing -x: a bow-tie
    ink = fd.tc.binarize(img)
    arrows, _ = fd.arrowheads(ink, side, max(5, int(round(0.6 * side))))
    got = sorted((a["axis"], a["dir"], round(a["x"] / 50), round(a["y"] / 50)) for a in arrows)
    check("horizontal arrow found, pointing +x", ("x", 1, 6, 2) in got, got)
    check("vertical arrow found, pointing up (-y)", ("y", -1, 2, 5) in got, got)
    check("two arrows tip to tip (an undetected valve) are dropped", not any(a["y"] > 280 for a in arrows), got)

    # flag_tip / flag_role: a pentagon flag pointing right, line attached on the left = flow leaves the sheet
    img = np.full((200, 400), 255, np.uint8)
    cv2.polylines(img, [np.array([[150, 80], [260, 80], [290, 100], [260, 120], [150, 120]], np.int32)], True, 0, 2)
    cv2.line(img, (20, 100), (150, 100), 0, 3)
    ink = fd.tc.binarize(img)
    box = (148, 78, 292, 122)
    tip = fd.flag_tip(ink, box)
    check("pentagon flag: pointed end read", tip == "right", tip)
    check("tip away from the line: flow leaves the sheet (sink)", fd.flag_role(tip, box, [(147, 100)]) == "sink")
    check("tip toward the line: flow enters the sheet (source)", fd.flag_role(tip, box, [(293, 100)]) == "source")
    img2 = np.full((200, 400), 255, np.uint8)
    cv2.rectangle(img2, (150, 80), (290, 120), 0, 2)
    check("a rectangle has no pointed end: no evidence", fd.flag_tip(fd.tc.binarize(img2), box) is None)
    check("lines on both sides of a flag: no evidence", fd.flag_role("right", box, [(147, 100), (293, 100)]) is None)

    # a whole sheet: tank -> (arrow) -> valve -> pump; the arrow orients tank->valve first hand
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "s.png"
        img = np.full((1000, 1000), 255, np.uint8)
        cv2.rectangle(img, (40, 440), (120, 560), 0, 3)                      # tank
        cv2.line(img, (120, 500), (480, 500), 0, 3)
        triangle(img, (300, 500), 284, 7)                                  # arrow on the tank-valve pipe
        cv2.line(img, (480, 485), (520, 515), 0, 2); cv2.line(img, (480, 515), (520, 485), 0, 2)   # valve bow-tie
        cv2.line(img, (480, 485), (480, 515), 0, 2); cv2.line(img, (520, 485), (520, 515), 0, 2)
        cv2.line(img, (520, 500), (860, 500), 0, 3)
        cv2.circle(img, (900, 500), 38, 0, 3)                              # pump
        cv2.imwrite(str(p), img)
        syms = [{"id": "T", "class": "tank", "box": [40, 440, 120, 560]},
                {"id": "V", "class": "valve", "box": [478, 483, 522, 517]},
                {"id": "P", "class": "pump", "box": [862, 462, 938, 538]}]
        S = fd.sheet_evidence(p, syms)
        pairs = {(u, v, e["source"]) for u, v, e in S["orient"]}
        check("synthetic sheet: tracer links tank-valve and valve-pump",
              {frozenset((l["from"], l["to"])) for l in S["links"]} == {frozenset("TV"), frozenset("VP")}, S["links"])
        check("arrow on the tank-valve pipe orients tank -> valve, first hand", ("T", "V", "arrowhead") in pairs, pairs)
        check("the arrow says nothing about valve-pump directly", not any({u, v} == {"V", "P"} for u, v, _ in pairs),
              pairs)

    # combine and propagation: tiers, conflicts, never a direction from nothing
    check("no evidence stays undirected", fd.combine([]) == ("undirected", None, None))
    check("first-hand evidence decides over the weaker via-junction reading",
          fd.combine([(1, "arrowhead", 0.8, {}), (-1, "arrowhead_via_junction", 0.6, {})])[0] == "forward")
    check("first-hand evidence that disagrees is a conflict, not a direction",
          fd.combine([(1, "arrowhead", 0.8, {}), (-1, "offpage_flag", 0.7, {})])[0] == "conflict")
    check("confidence is the deciding tier's, not a blend",
          fd.combine([(1, "arrowhead_via_junction", 0.57, {})]) == ("forward", 0.57, "via_junction"))
    streams = [{"id": "a", "from": "T", "to": "V"}, {"id": "b", "from": "P", "to": "V"}]
    added = fd.propagate_valves(streams, {"a": ("forward", 0.8, "first_hand")}, ["V"], 0.5)
    check("valve continuity: T->V carries on as V->P (stored P-V, so reverse)", added.get("b", [[0]])[0][0] == -1, added)
    check("valve continuity never seeds from a propagated direction",
          not fd.propagate_valves(streams, {"a": ("forward", 0.5, "valve_chain")}, ["V"], 0.5))
    three = streams + [{"id": "c", "from": "V", "to": "X"}]
    check("a valve with three connections is not a series valve: no propagation",
          not fd.propagate_valves(three, {"a": ("forward", 0.8, "first_hand")}, ["V"], 0.5))


def committed_outputs():
    fdoc = json.loads((OUT / "flow_direction.json").read_text(encoding="utf-8"))
    recs, summ = fdoc["streams"], fdoc["summary"]
    check("every one of the twin's 1,881 connections has a record", len(recs) == 1881 == summ["connections"])
    check("directed + undirected + conflict = all connections",
          summ["directed"] + summ["undirected"] + summ["conflict"] == summ["connections"])
    directed = [r for r in recs if r["direction"] in ("forward", "reverse")]
    check("every directed link has evidence, a confidence and a flow_from/flow_to",
          all(r["evidence"] and r["confidence"] and r.get("flow_from") and r.get("flow_to") for r in directed))
    check("no link without evidence has a direction", all(r["direction"] == "undirected" for r in recs
                                                           if not r["evidence"]))
    check("instrument links never get a process-flow direction",
          all(r["direction"] == "undirected" for r in recs if r["instrument_link"]))
    check("the keys are recorded as undirected (no direction score is claimed)", summ["keys_directed"] is False)
    det = summ["arrow_detection_vs_keys"]
    check("arrow detection is reported separately for tuning sheets 0-5 and held-out sheets 6-11",
          det["dev"]["sheets"] == fd.DEV and det["holdout"]["sheets"] == fd.HOLDOUT)
    conf = json.loads((ROOT / "data" / "open100_direction_confidence.json").read_text(encoding="utf-8"))
    tier = {"first_hand": lambda x: x not in fd.WEAK + ("valve_chain",), "via_junction": lambda x: x in fd.WEAK,
            "valve_chain": lambda x: x == "valve_chain"}
    wrong = [r["id"] for r in directed if abs(r["confidence"] - max(
        fd.confidence(e["source"]) for e in r["evidence"] if tier[r["basis"]](e["source"]))) > 1e-6]
    check("each link's confidence is its deciding source's spot-check lower bound (or stated prior)", not wrong, wrong[:5])
    check("spot-check confidences are lower bounds, never the raw agreement",
          all(v.get("confidence", 0) <= v.get("agreement", 1) for v in conf["sources"].values()))

    sdoc = json.loads((OUT / "plant_structure.json").read_text(encoding="utf-8"))
    sheets = sorted(a["sheet"] for a in sdoc["areas"])
    check("tour order visits each of the 12 sheets once", sorted(sdoc["tour_order"]) == sheets and len(sheets) == 12)
    check("area links join real, different sheets",
          all(e["a"] in sheets and e["b"] in sheets and e["a"] != e["b"] for e in sdoc["area_links"]))
    sched = st.load_schedule()
    bad = [e["id"] for e in sdoc["equipment"] if e["purpose"]["source"] == "equipment_schedule"
           and (e["sheet"], (e["tag"] or "").replace(" ", "").upper()) not in sched]
    check("a purpose credited to the drawing's schedule is in the transcribed schedule", not bad, bad)
    check("every purpose names its source", all(e["purpose"]["source"] in sdoc["meta"]["sources"]
                                                 for e in sdoc["equipment"]))
    pts = sdoc["isolation_points"]
    kinds = {"manual_block_valve", "motor_operated_valve", "control_valve", "relief_device", "vent_drain_or_test",
             "motor_driven_equipment", "boundary_connection", "vent_drain_connection"}
    check("every isolation point has a sheet, a box on the drawing and a known kind",
          all(p["sheet"] in sheets and p["kind"] in kinds and len(p["box_0_1000"]) == 4
              and all(0 <= v <= 1000 for v in p["box_0_1000"]) for p in pts))
    check("control valves and relief devices are never listed as isolation points",
          all("not an energy-isolating device" in p["note"] or "never be used for isolation" in p["note"]
              for p in pts if p["kind"] in ("control_valve", "relief_device")))
    check("every extracted pump is listed as motor-driven equipment",
          {e["id"] for e in sdoc["equipment"] if e["class"] == "pump"} ==
          {p["id"] for p in pts if p["kind"] == "motor_driven_equipment"})

    # mimic: arrows exactly where a direction is known, values all "not connected"
    import build_open100_mimic as bm
    import base64
    views = json.loads((OUT / "mimic" / "views.json").read_text(encoding="utf-8"))
    for sheet in ("7", "3"):
        v = views["OPEN100/Area_" + sheet]
        img = next(c for c in v["root"]["children"] if c["meta"]["name"] == "AreaMimic_" + sheet)
        svg = base64.b64decode(img["props"]["source"].split(",", 1)[1]).decode()
        links = [l for l in sdoc["unit_links"] if l["sheet"] == sheet]
        n_arrows = svg.count('marker-end="url(#arrow)"')
        n_dashed = svg.count('stroke-dasharray="6 5"')
        check("area %s mimic: one line per drawn connection, arrows only on directed ones" % sheet,
              n_arrows + n_dashed > 0 and n_arrows <= sum(l["direction"] in ("a_to_b", "b_to_a") for l in links))
    texts = [c["props"].get("text", "") for v in views.values() for c in v["root"]["children"]
             if c["meta"]["name"].startswith("Value_")]
    check("every value on the OPEN100 mimic reads 'not connected'", texts and set(texts) == {"not connected"})
    bound = [c for v in views.values() for c in v["root"]["children"] if c["meta"]["name"].startswith("Value_")
             and c.get("propConfig")]
    check("value labels bind through the same 'not connected' transform as the drawing screens",
          bound and all("not connected" in c["propConfig"]["props.text"]["binding"]["transforms"][0]["code"]
                        for c in bound))
    check("unknown direction never authorizes an arrow (shared display contract)",
          not bm.stream_is_directed(bm.directed_pair({"a": "x", "b": "y", "direction": "undirected"}))
          and not bm.stream_is_directed(bm.directed_pair({"a": "x", "b": "y", "direction": "conflict"})))

    # 3D scene: chevrons only where directed, no live values, structure-only badge on every still
    import build_open100_3d as b3
    scene = b3.build(sdoc)
    again = b3.build(sdoc)
    check("3D scene is deterministic", json.dumps(scene, sort_keys=True) == json.dumps(again, sort_keys=True))
    ul = {"P-%s-%s" % ((l["a"], l["b"]) if l["direction"] != "b_to_a" else (l["b"], l["a"])): l
          for l in sdoc["unit_links"]}
    check("a 3D pipe has chevrons only if its path has a direction read from the drawing",
          all((p["directed"] == (ul[p["id"]]["direction"] in ("a_to_b", "b_to_a"))) for p in scene["pipes"]
              if p["id"].startswith("P-")))
    check("no 3D marker is connected and no shot carries replay states",
          all(not m["connected"] for m in scene["markers"]) and scene["replay_states"] == [])
    check("every 3D shot says structure only, no process data",
          all(any("NO PROCESS DATA" in o.get("text", "") for o in s["overlays"]) for s in scene["shots"]))
    check("tour stops follow the inferred tour order",
          [s["name"].split("sheet")[-1] for s in scene["shots"][1:]] ==
          [x for x in sdoc["tour_order"] if any(e["area"] == x for e in scene["equipment"])])
    # The renderer was first copied byte for byte from the 3D tour prototype; with the tour merged, both tours
    # render through the one file (the label font and sizes changed there, for both).
    import build_3d_scene as te3d
    import build_open100_3d as o3d
    check("both 3D tours render through the one shared renderer, scripts/blender_tour_template.py",
          te3d.TEMPLATE == o3d.TEMPLATE == ROOT / "scripts" / "blender_tour_template.py" and o3d.TEMPLATE.is_file())


def matrix():
    doc = dm.load()
    check("deliverables matrix follows its own rules (status, reason, evidence on disk)", not dm.problems(doc),
          dm.problems(doc))
    page = dm.TARGET.read_text(encoding="utf-8").replace("\r\n", "\n")
    a, b = page.index(dm.START) + len(dm.START), page.index(dm.END)
    check("docs/DELIVERABLES.md table is exactly the generated matrix", page[a:b].strip() == dm.markdown(doc).strip())
    check("docs/DELIVERABLES.md is exactly what deliverables_matrix.py writes", page == dm.page(doc))
    check("docs/DELIVERABLES.md section heading is present",
          "# What you can do with only drawings, only process knowledge, or both" in page)
    links = re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", page[a:b])
    check("every evidence link in docs/DELIVERABLES.md resolves from docs/",
          bool(links) and all((dm.TARGET.parent / p).resolve().exists() for p in links),
          [p for p in links if not (dm.TARGET.parent / p).resolve().exists()])
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    check("README links to docs/DELIVERABLES.md and no longer carries the full matrix",
          "](docs/DELIVERABLES.md)" in readme and dm.START not in readme and dm.END not in readme)
    rows = {r["deliverable"]: r for r in doc["rows"]}
    check("OPEN100 cannot show values, bands, alarms or replay without process data, and says why",
          all(rows[k]["open100"]["status"] == "not_possible" and any(
              w in rows[k]["open100"]["note"] for w in ("process data", "historian"))
              for k in ("Values on the screens", "Normal bands and early warning", "Alarms",
                        "Fault replay and live process tour")))
    summ = json.loads((OUT / "flow_direction.json").read_text(encoding="utf-8"))["summary"]
    note = rows["Flow direction on connections"]["open100"]["note"]
    m = re.search(r"on ([\d,]+) of ([\d,]+) process links", note)
    check("matrix flow-direction numbers match flow_direction.json",
          m and int(m.group(1).replace(",", "")) == summ["process_links_directed"]
          and int(m.group(2).replace(",", "")) == summ["process_links"], note)
    sdoc = json.loads((OUT / "plant_structure.json").read_text(encoding="utf-8"))
    note = rows["Sheets stitched into one plant"]["open100"]["note"]
    m = re.search(r"(\d+) sheet-to-sheet connections, (\d+) with a direction", note)
    check("matrix stitching numbers match plant_structure.json",
          m and int(m.group(1)) == len(sdoc["area_links"])
          and int(m.group(2)) == sum(e["direction"] in ("a_to_b", "b_to_a") for e in sdoc["area_links"]), note)
    plant = (ROOT / "docs" / "AT_YOUR_PLANT.md").read_text(encoding="utf-8")
    check("AT_YOUR_PLANT says what drawings without historian access still give",
          "What you can do with only drawings, only process knowledge, or both" in plant
          and all(w in plant for w in ("asset", "mimic", "tour", "isolation")))


def main():
    synthetic_rules()
    committed_outputs()
    matrix()
    print("\n%d failed" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
