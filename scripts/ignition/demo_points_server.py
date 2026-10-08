"""A small OPC UA server for the mapped OPEN100 demo points (scripts/map_points.py, data/io_lists/).

OPEN100 is a design with no plant behind it, so these values are SYNTHETIC: a seeded, slow random walk around a
plausible value for each unit. They exist to show placeholders becoming live points in Ignition, not to describe a
real process. Like te_sim_server.py it is read-only by construction (clients cannot write).

Every row of the I/O list whose `server` matches --server is served at the node <s-prefix>.<point> in the namespace
named by base_path (nsu=...;s=<s-prefix>), exactly the address map_points.py writes into the twin.

Usage: python scripts/ignition/demo_points_server.py [--io data/io_lists/open100_sheet0_demo.csv]
       [--server OPEN100-Demo] [--port 4842] [--rate 1.0]
"""
import argparse
import asyncio
import csv
import logging
import random
import re
from pathlib import Path

from asyncua import Server, ua

ROOT = Path(__file__).resolve().parents[2]
TYPICAL = {"degC": (285.0, 0.4), "kPa": (6800.0, 6.0), "mSv/h": (0.05, 0.002), "%": (50.0, 0.6), "kg/s": (400.0, 1.5)}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--io", default="data/io_lists/open100_sheet0_demo.csv")
    ap.add_argument("--server", default="OPEN100-Demo", help="serve the I/O rows assigned to this connection name")
    ap.add_argument("--port", type=int, default=4842)
    ap.add_argument("--rate", type=float, default=1.0)
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    rows = [r for r in csv.DictReader(open(ROOT / a.io, encoding="utf-8-sig")) if r["server"].strip() == a.server]
    if not rows:
        raise SystemExit(f"no I/O rows for server {a.server}")
    m = re.match(r"nsu=([^;]+);s=(.*)$", rows[0]["base_path"].strip())
    if not m:
        raise SystemExit("base_path must look like nsu=<namespace uri>;s=<prefix>")
    uri, prefix = m.groups()

    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{a.port}/open100-demo")
    server.set_server_name("OPEN100 demo points (synthetic values)")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    idx = await server.register_namespace(uri)
    folder = await server.nodes.objects.add_folder(ua.NodeId(prefix, idx), prefix)
    rng = random.Random(20261008)
    points = []
    for r in rows:
        center, step = TYPICAL.get(r.get("units", "").strip(), (100.0, 0.5))
        value = center + rng.uniform(-10, 10) * step
        node = await folder.add_variable(ua.NodeId(f"{prefix}.{r['point'].strip()}", idx), r["point"].strip(),
                                         ua.Variant(value, ua.VariantType.Double))
        points.append([node, value, center, step])
    print(f"OPEN100 demo points: {len(points)} synthetic points on opc.tcp://localhost:{a.port}/open100-demo "
          f"({uri}, s={prefix}.<point>)", flush=True)
    async with server:
        while True:
            for p in points:
                node, value, center, step = p
                value += rng.gauss(0, step) + (center - value) * 0.05  # random walk, pulled back toward typical
                p[1] = value
                await node.write_value(ua.Variant(value, ua.VariantType.Double))
            await asyncio.sleep(a.rate)


if __name__ == "__main__":
    asyncio.run(main())
