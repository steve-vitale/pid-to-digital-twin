"""Controls for score_pid2graph.py. A scorer is only trusted after it scores known answers correctly.

  perfect     prediction built from the answer key itself      -> 1.0 everywhere
  empty       no symbols                                       -> 0.0
  wrong_class every class rotated                              -> located 1.0, classified 0.0
  shifted     every box moved far away                         -> 0.0
  half        every other symbol dropped                       -> recall ~0.5, precision 1.0
Run: python scripts/test_scorer_controls.py   (exits non-zero on any failure)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import score_pid2graph as sc  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"


def perfect_prediction(graphml, png):
    w, h = sc.png_size(png)
    nodes, adj = sc.load_key(graphml, w, h)
    syms = [{"id": k, "class": v["class"], "box": v["box"], "tag": None, "confidence": 1}
            for k, v in nodes.items() if v["class"] in sc.SCORED]
    conns = [{"from": a, "to": b} for a, b in (tuple(l) for l in sc.asset_links(nodes, adj))]
    return {"symbols": syms, "connections": conns}


def shift(box):
    w, h = box[2] - box[0], box[3] - box[1]
    x, y = (box[0] + 500) % (1000 - w), (box[1] + 500) % (1000 - h)
    return [x, y, x + w, y + h]


def main():
    failures = 0
    for graphml in sorted(DATA.glob("*.graphml")):
        png = graphml.with_suffix(".png")
        perfect = perfect_prediction(graphml, png)
        rot = {c: sc.SCORED[(i + 1) % len(sc.SCORED)] for i, c in enumerate(sc.SCORED)}
        cases = {
            "perfect": (perfect, lambda r: r["strict"]["classified"]["f1"] == 1 and r["connections"]["f1"] == 1
                        and r["review_load"]["per_100"] == 0),
            "empty": ({"symbols": [], "connections": []},
                      lambda r: r["rough"]["located"]["recall"] == 0 and r["review_load"]["per_100"] == 100),
            "wrong_class": ({"symbols": [dict(s, **{"class": rot[s["class"]]}) for s in perfect["symbols"]],
                             "connections": []},
                            lambda r: r["strict"]["located"]["f1"] == 1 and r["rough"]["classified"]["tp"] <= 0.02 * r["rough"]["classified"]["in_key"]),
            # Same-size boxes moved half a sheet away: tests location, not box size. Strict must be zero. Rough may
            # pick up chance hits on repetitive sheets: drawing 6 has two identical pump details half a sheet apart
            # and gets 8.8% rough credit when shifted, so "rough" carries a small chance floor on such sheets.
            "shifted": ({"symbols": [dict(s, box=shift(s["box"])) for s in perfect["symbols"]], "connections": []},
                        lambda r: r["strict"]["located"]["tp"] == 0 and r["rough"]["located"]["recall"] < 0.10),
            "half": ({"symbols": perfect["symbols"][::2], "connections": []},
                     lambda r: r["strict"]["classified"]["precision"] == 1 and 0.4 <= r["strict"]["classified"]["recall"] <= 0.6),
        }
        for name, (pred, ok) in cases.items():
            r = sc.score(graphml, pred, png)
            if not ok(r):
                failures += 1
                print(f"FAIL {graphml.name} {name}: strict={r['strict']['classified']} rough_located={r['rough']['located']} "
                      f"rough_classified={r['rough']['classified']} connections={r['connections']}")
    print(f"{'ALL CONTROLS PASS' if not failures else f'{failures} control failure(s)'} "
          f"across {len(list(DATA.glob('*.graphml')))} drawings")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
