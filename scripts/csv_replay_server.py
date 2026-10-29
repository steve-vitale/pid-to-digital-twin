"""A small OPC UA server that replays any historian-style CSV export, one row per step, so Ignition (or any OPC UA
client) can read a plant's own recorded data the way it would read the live PLC/OPC server.

What it is NOT: not a simulator and not a process model. The values are the recorded ones, played back in order; they
do not respond to anything a client does (nodes are read-only), and nothing is interpolated or filled in.

CSV shape (the same reader as scripts/csv_normal_bands.py): row 1 is a header (time/index column name, then tag
names); the first column is a timestamp or a sample index; every other column is a numeric tag. A blank or non-numeric
cell ("", "Bad", "I/O Timeout", "nan") is served as that tag's value for that step with status BadNoData and a null
value, never as a made-up number. A malformed header is refused with a message that says what is wrong.

Nodes (same conventions as scripts/ignition/te_sim_server.py): one read-only Double node per tag column, node id
`ns=<idx>;s=<Folder>/<column>` (e.g. `ns=2;s=CSV/PT-107`; ns is 2 on a fresh server), plus `<Folder>/_sample`
(Int32, the 0-based data row being served) and `<Folder>/_time` (String, that row's first-column text). Source
timestamps are the server's clock, not the CSV's: the CSV time is in `_time`.

Usage:
  python scripts/csv_replay_server.py --csv export.csv [--port 4851] [--rate 1.0] [--folder CSV] [--loop] [--start N]
  --rate   seconds between rows (default 1.0; the CSV's own time spacing is not used).
  --loop   go back to row 0 after the last row. Without it the server keeps serving the last row and says so.
  --host   interface to listen on (default 0.0.0.0, as te_sim_server.py; use 127.0.0.1 for a private test).
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from asyncua import Server, ua

sys.path.insert(0, str(Path(__file__).resolve().parent))
from csv_normal_bands import CsvFormatError, read_historian_csv  # noqa: E402

RESERVED = ("_sample", "_time")
BAD = ua.StatusCode(ua.StatusCodes.BadNoData)


def load(path):
    """(time_name, tags, time_texts, rows); refuses reserved tag names. Raises CsvFormatError."""
    tname, tags, _, rows, texts = read_historian_csv(path, with_text=True)
    clash = [t for t in tags if t in RESERVED]
    if clash:
        raise CsvFormatError(f"{Path(path).name}: tag name(s) {', '.join(clash)} are reserved for the server's own nodes")
    return tname, tags, texts, rows


def data_value(v):
    if v is None:
        return ua.DataValue(ua.Variant(None, ua.VariantType.Null), StatusCode=BAD)
    return ua.DataValue(ua.Variant(v, ua.VariantType.Double))


async def serve(args, stop=None):
    try:
        tname, tags, texts, rows = load(args.csv)
    except OSError as e:  # a missing or unreadable --csv: say so, exit nonzero, no traceback
        raise SystemExit(f"error: can't read {args.csv}: {e.strerror or e}") from None
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://{args.host}:{args.port}/csv-replay")
    server.set_server_name(f"CSV replay ({Path(args.csv).name})")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    idx = await server.register_namespace("urn:pid-digital-twin:csv-replay")  # ns=2 on a fresh server
    f = args.folder
    folder = await server.nodes.objects.add_folder(ua.NodeId(f, idx), f)
    nodes = []
    for tag in tags:
        node = await folder.add_variable(ua.NodeId(f"{f}/{tag}", idx), tag, ua.Variant(0.0, ua.VariantType.Double))
        nodes.append(node)  # not set_writable(): clients can read, not write
    sample = await folder.add_variable(ua.NodeId(f"{f}/_sample", idx), "_sample", ua.Variant(0, ua.VariantType.Int32))
    when = await folder.add_variable(ua.NodeId(f"{f}/_time", idx), "_time", ua.Variant("", ua.VariantType.String))
    bad = sum(v is None for r in rows for v in r)
    print(f"CSV replay '{Path(args.csv).name}' on opc.tcp://localhost:{args.port}/csv-replay, ns={idx}, "
          f"folder {f}, {len(tags)} tags, {len(rows)} rows ({bad} bad cells) at {args.rate}s"
          f"{', looping' if args.loop else ''}", flush=True)
    async with server:
        if not 0 <= args.start < len(rows):  # never wrap silently onto a different row than was asked for
            raise SystemExit(f"--start {args.start} is outside the {len(rows)} rows of {Path(args.csv).name}")
        i, held = args.start, False
        while stop is None or not stop.is_set():
            row = rows[i]
            for node, v in zip(nodes, row):
                await node.write_value(data_value(v))
            await sample.write_value(ua.Variant(i, ua.VariantType.Int32))
            await when.write_value(ua.Variant(texts[i], ua.VariantType.String))
            if i + 1 < len(rows):
                i += 1
            elif args.loop:
                i = 0
            elif not held:
                held = True
                print(f"end of CSV at row {i}; holding the last row (use --loop to restart)", flush=True)
            await asyncio.sleep(args.rate)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--csv", required=True, help="historian-style CSV: header row, time/index column, tag columns")
    ap.add_argument("--port", type=int, default=4851)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--rate", type=float, default=1.0, help="seconds between rows")
    ap.add_argument("--folder", default="CSV", help="folder name; node ids are ns=<idx>;s=<folder>/<column>")
    ap.add_argument("--loop", action="store_true", help="restart at row 0 after the last row")
    ap.add_argument("--start", type=int, default=0, help="first data row to serve (0-based)")
    args = ap.parse_args(argv)
    if not args.folder or "/" in args.folder:
        ap.error("--folder must be a non-empty name without '/'")
    if args.rate <= 0:
        ap.error("--rate must be > 0")
    return args


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    try:
        asyncio.run(serve(args))
    except CsvFormatError as e:
        raise SystemExit(f"error: {e}") from None
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
