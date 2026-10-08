"""A small OPC UA server that replays the open Tennessee Eastman simulation data, standing in for a plant's PLC/OPC
server so Ignition can connect to it the way it would on site.

Data: the Braatz group's TE test runs (open license), 960 samples per run at 3 simulated minutes each. Columns 1-41 are
XMEAS 1-41 and columns 42-52 are XMV 1-11 (XMV 12, agitator speed, is constant in this data set and isn't included).
The replay runs faster than real time (default: one sample per second).

Each model tag gets a node `TE/<tag>`, e.g. `TE/PI-107`. The node id is the string `ns=2;s=TE/<tag>`. Values are read-only
from the client side: the server never accepts writes.

Usage:
  python scripts/ignition/te_sim_server.py [--run normal|fault6] [--rate 1.0] [--port 4841]
  --run fault6 replays IDV(6), loss of A feed. Reactor pressure rises after sample 160, crosses the 2895 kPa
  operating limit at sample 258 and holds at exactly 3000 kPa (the recorded run stops at the shutdown limit).
  --start N begins the replay at sample N.
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path

from asyncua import Server, ua

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "external" / "te-braatz"
MODEL = ROOT / "data" / "te_process_model.json"
RUNS = {"normal": "d00_te.dat", "fault6": "d06_te.dat"}


def load_rows(name):
    path = DATA / RUNS[name]
    return [list(map(float, line.split())) for line in path.read_text().splitlines() if line.strip()]


def column_map(model):
    """Model tag -> 0-based data column. Analyzers (XMEAS ranges) map to their first component."""
    cols = {}
    for item in model["instruments"]:
        x = item["xmeas"]
        first = int(str(x).split("-")[0])
        cols[item["tag"]] = first - 1
    for item in model["final_elements"]:
        if item["xmv"] <= 11:
            cols[item["tag"]] = 41 + item["xmv"] - 1
    return cols


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", choices=RUNS, default="normal")
    ap.add_argument("--rate", type=float, default=1.0, help="seconds between samples")
    ap.add_argument("--port", type=int, default=4841)
    ap.add_argument("--start", type=int, default=0, help="first sample to replay (fault6 crosses 2895 kPa at 258)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    model = json.loads(MODEL.read_text(encoding="utf-8"))
    cols = column_map(model)
    rows = load_rows(args.run)

    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{args.port}/te-sim")
    server.set_server_name("TE replay (open Tennessee Eastman data)")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    idx = await server.register_namespace("urn:pid-digital-twin:te-sim")  # becomes ns=2 on a fresh server
    folder = await server.nodes.objects.add_folder(ua.NodeId("TE", idx), "TE")
    nodes = {}
    for tag, col in cols.items():
        node = await folder.add_variable(ua.NodeId(f"TE/{tag}", idx), tag, ua.Variant(rows[0][col], ua.VariantType.Double))
        nodes[tag] = (node, col)  # not set_writable(): clients can read, not write
    sample = await folder.add_variable(ua.NodeId("TE/_sample", idx), "_sample", ua.Variant(0, ua.VariantType.Int32))
    run_name = await folder.add_variable(ua.NodeId("TE/_run", idx), "_run", ua.Variant(args.run, ua.VariantType.String))

    print(f"TE replay '{args.run}' on opc.tcp://localhost:{args.port}/te-sim, ns={idx}, {len(nodes)} tags, "
          f"{len(rows)} samples at {args.rate}s", flush=True)
    async with server:
        i = args.start
        while True:
            row = rows[i % len(rows)]
            for node, col in nodes.values():
                await node.write_value(ua.Variant(row[col], ua.VariantType.Double))
            await sample.write_value(ua.Variant(i % len(rows), ua.VariantType.Int32))
            await run_name.write_value(ua.Variant(args.run, ua.VariantType.String))
            i += 1
            await asyncio.sleep(args.rate)


if __name__ == "__main__":
    asyncio.run(main())
