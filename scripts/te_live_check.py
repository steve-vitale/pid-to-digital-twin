"""Live values for the extracted TE twin: do the tags read off the generated drawings resolve to moving replay points?

This is the I/O-list step of the chain, done against the repo's own OPC UA replay server (scripts/ignition/
te_sim_server.py, the Braatz group's recorded TE runs) instead of a plant historian. It starts the replay server on
a private port, browses the points it serves, matches each extracted instrument tag to a point by tag only
(upper-cased, separators dropped: "FI 101" = "FI-101"), reads every matched point twice a few samples apart, and
reports which values moved. A tag read off an older drawing revision (the recorded runs read revision A) is matched
through the model's `former_tag` and reported as such: the replay serves current tags. Nothing is written to the server (it refuses writes anyway) and no gateway is involved:
importing the extracted twin's tags.json into Ignition is a separate step that was not repeated here.

Needs the TE data (python scripts/fetch_te_data.py) and asyncua.

Usage: python scripts/te_live_check.py out/te_pid/twin/codex/plant_model.json [--name codex-clean-r1] [--port 4851]
Writes out/te_pid/live_<name>.{json,md}.
"""
import argparse
import asyncio
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "te_process_model.json"
NS = "urn:pid-digital-twin:te-sim"


def norm(tag):
    return re.sub(r"[^A-Z0-9]", "", str(tag or "").upper())


async def read_points(url, wait_s):
    from asyncua import Client, ua
    async with Client(url) as c:
        idx = await c.get_namespace_index(NS)
        folder = c.get_node(ua.NodeId("TE", idx))
        points = {}
        for node in await folder.get_children():
            name = (await node.read_browse_name()).Name
            if not name.startswith("_"):
                points[name] = node
        first = {n: await p.read_value() for n, p in points.items()}
        await asyncio.sleep(wait_s)
        second = {n: await p.read_value() for n, p in points.items()}
    return first, second


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("twin")
    ap.add_argument("--name", default=None)
    ap.add_argument("--port", type=int, default=4851)
    ap.add_argument("--wait", type=float, default=5.0, help="seconds between the two reads (replay: 1 sample/s)")
    a = ap.parse_args()
    twin_path = Path(a.twin) if Path(a.twin).is_absolute() else ROOT / a.twin
    twin = json.loads(twin_path.read_text(encoding="utf-8"))
    name = a.name or twin_path.parent.name
    server = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "ignition" / "te_sim_server.py"),
                               "--port", str(a.port), "--rate", "1.0"], cwd=ROOT / "scripts" / "ignition",
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        line = server.stdout.readline()  # the server prints one line when it is serving
        if "TE replay" not in line:
            sys.exit(f"replay server did not start: {line.strip()}")
        time.sleep(1.0)
        first, second = asyncio.run(read_points(f"opc.tcp://localhost:{a.port}/te-sim", a.wait))
    finally:
        server.terminate()
        server.wait(timeout=10)
    by_norm = {norm(p): p for p in first}
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    renamed = {norm(i["former_tag"]): i["tag"] for i in model["instruments"] + model["final_elements"]
               if i.get("former_tag")}
    rows = []
    for x in twin["instruments"]:
        point = by_norm.get(norm(x.get("tag")))
        via = None
        if point is None and norm(x.get("tag")) in renamed:
            via = renamed[norm(x.get("tag"))]
            point = by_norm.get(norm(via))
        rows.append({"id": x["id"], "tag": x.get("tag"), "point": point, "via_former_tag": via is not None and point is not None,
                     "first": first.get(point), "second": second.get(point),
                     "moved": point is not None and first[point] != second[point]})
    mapped = [r for r in rows if r["point"]]
    moved = [r for r in mapped if r["moved"]]
    served_unmatched = sorted(set(first) - {r["point"] for r in mapped})
    out = ROOT / "out" / "te_pid"
    out.mkdir(parents=True, exist_ok=True)
    summary = {"twin": twin_path.relative_to(ROOT).as_posix() if twin_path.is_relative_to(ROOT) else twin_path.name,
               "instruments": len(rows), "mapped_to_a_replay_point": len(mapped), "values_moved": len(moved),
               "served_points": len(first), "served_points_not_on_the_drawings": served_unmatched,
               "wait_s": a.wait, "rows": rows}
    (out / f"live_{name}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    md = [f"# Live values for the extracted twin ({name})", "",
          f"`scripts/te_live_check.py` against the TE replay server (normal run), reads {a.wait:g} s apart.", "",
          f"- Extracted instrument symbols (bubbles, including valve tags): **{len(rows)}**",
          f"- Matched by tag to a replay point: **{len(mapped)}** ({sum(r['via_former_tag'] for r in mapped)} through "
          "the tag's earlier name, `former_tag`: the drawings were read before a retag); value moved between reads: "
          f"**{len(moved)}**",
          f"- Replay points with no matching tag on the drawings: {', '.join(served_unmatched) or 'none'}", "",
          "| Extracted tag | Replay point | First read | Second read | Moved |", "|---|---|---|---|---|"]
    for r in rows:
        f = lambda v: "" if v is None else f"{v:.4g}"  # noqa: E731
        pt = (r['point'] + (" (earlier name)" if r['via_former_tag'] else "")) if r['point'] else "(no point)"
        md.append(f"| {r['tag']} | {pt} | {f(r['first'])} | {f(r['second'])} | "
                  f"{'yes' if r['moved'] else 'no'} |")
    md.append("")
    (out / f"live_{name}.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:7]))


if __name__ == "__main__":
    main()
