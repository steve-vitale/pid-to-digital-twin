"""Run the repository's gateway verifier (V1-V8) and a per-path quality census against an authorized test gateway.

verify_gateway.py starts and stops its own replay processes on this machine. Here the replay runs elsewhere (for
example the Docker replay container) and is switched by writing "<run> <start>" to its --control file, which this
process must be able to write (a shared mount). V9, the git change record, belongs to verify_gateway.py's normal
use on a committed checkout and is not run here.

Reads tags through the gateway's own OPC UA server with the verifier's credentials (scripts/ignition/ua_client.py);
V7 attempts the same refused writes verify_gateway.py does. Use only on a disposable or explicitly authorized gateway.

Usage (from the repository root, IGNITION_* configured as for verify_gateway.py):
  python scripts/ignition/acceptance/live_checks.py verify --replay-control /shared/te-run --out receipt.json
  python scripts/ignition/acceptance/live_checks.py census LABEL --out census.json
"""
import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gw  # noqa: E402
import ua_client  # noqa: E402
import verify_gateway as vg  # noqa: E402


class ControlFileReplay:
    """The Sim interface verify_gateway.v8 drives, implemented by the replay server's --control file."""

    def __init__(self, path):
        self.path = Path(path)

    def start(self, run, start=0, rate=1.0):
        # The replay keeps its own sample rate; v8 asks for 0.5 s but its timing limits do not depend on it.
        self.path.write_text(f"{run} {start}\n")

    def stop(self):
        self.path.write_text("normal 0\n")


async def verify(replay_control):
    g = gw.Gateway()
    sim = ControlFileReplay(replay_control) if replay_control else None
    checks = {"V1", "V2", "V3", "V4", "V5", "V6", "V7"} | ({"V8"} if sim else set())
    if sim:
        sim.start("normal", 0)
        time.sleep(4)
    try:
        return await vg.run_all(g, only=checks, sim=sim)
    finally:
        if sim:
            sim.stop()


async def census(label):
    g = gw.Gateway()
    held = vg.Held(g)
    meta = json.loads((vg.OUT / "build_meta.json").read_text(encoding="utf-8"))
    te, te_nodata, tw = vg.live_sets(held, meta)
    states = [f"[{vg.P}]{p}/State" for p, _ in held.instances("TE_Plant")]
    # Header counts, plus the data-source diagnostics (journal entry 39): the count of fed values without Good
    # quality per connection and the number of active diagnostic alarms.
    summary = [f"[{vg.P}]TE_Plant/_Summary/{m}" for m in ("OutOfNormal", "AlarmsActive", "DiagnosticAlarmsActive",
                                                          "ReplayValuesNotGood", "DemoPointsNotGood")]
    c = await ua_client.connect()
    async with c:
        ns = await ua_client.tag_ns(c)
        r = await vg.read_many(c, ns, [x[0] for x in te + te_nodata + tw] + states + summary)
    groups = {"te_recorded": [x[0] for x in te if x[0].startswith(f"[{vg.P}]TE_Plant")],
              "open100_mapped": [x[0] for x in te if x[0].startswith(f"[{vg.P}]OPEN100")],
              "te_unavailable": [x[0] for x in te_nodata], "open100_placeholder": [x[0] for x in tw]}
    return {"label": label,
            "groups": {k: {"n": len(v), "status": dict(Counter(r[p].StatusCode.name for p in v)),
                           "null_values": sum(r[p].Value.Value is None for p in v)} for k, v in groups.items()},
            "te_state": {f"{q}={v}": n for (q, v), n in
                         Counter((r[p].StatusCode.name, r[p].Value.Value) for p in states).most_common()},
            "summary": {p: [r[p].StatusCode.name, r[p].Value.Value] for p in summary},
            "callout_instances": [p for p, inst in held.instances("OPEN100") if inst["typeId"] == "Callout_Valve"],
            "unavailable_samples": {p: [r[p].StatusCode.name, r[p].Value.Value] for p in groups["te_unavailable"]}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["verify", "census"])
    ap.add_argument("label", nargs="?", default="census")
    ap.add_argument("--replay-control", help="replay --control file to switch normal/fault (enables V8)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.mode == "verify":
        results = asyncio.run(verify(args.replay_control))
        vg.print_results(results)
        body = {"passed": all(x["passed"] for x in results), "checks": results}
    else:
        body = asyncio.run(census(args.label))
        print(json.dumps(body["groups"]), json.dumps(body["te_state"]))
    Path(args.out).write_text(json.dumps(body, indent=1, default=str), encoding="utf-8")
    sys.exit(0 if args.mode == "census" or body["passed"] else 1)


if __name__ == "__main__":
    main()
