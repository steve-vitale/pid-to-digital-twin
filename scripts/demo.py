"""One command from a clone to a live twin in your Ignition gateway.

  python scripts/demo.py                 fetch the TE data, start both data servers, keep the twin live (Ctrl+C stops)
  python scripts/demo.py --build         ...and first build the twin into the gateway (needs the IGNITION_* settings)
  python scripts/demo.py --build --verify   ...and run the nine checks before going live
  python scripts/demo.py --fault         replay fault 6 (loss of A feed) instead of normal operation

Without --build, load the twin by hand first (docs/IGNITION_QUICKSTART.md). With --build, the gateway needs an API
key and the other settings in scripts/ignition/gw.py (docs/IGNITION_BUILD.md).

The data servers:
  scripts/ignition/te_sim_server.py        Tennessee Eastman replay (open data), port 4841
  scripts/ignition/demo_points_server.py   synthetic values for the mapped OPEN100 demo points, port 4842
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
URL = os.environ.get("IGNITION_HTTP_URL", "http://localhost:8088")


def step(msg):
    print(f"\n== {msg}", flush=True)


def run(args):
    p = subprocess.run([PY, *args], cwd=ROOT)
    if p.returncode:
        raise SystemExit(f"failed: {' '.join(args)} (exit {p.returncode})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="build the twin into the gateway first (scripted)")
    ap.add_argument("--verify", action="store_true", help="run the nine checks after building")
    ap.add_argument("--fault", action="store_true", help="replay fault 6 instead of normal operation")
    ap.add_argument("--seconds", type=float, default=0, help="stop after this long (0 = until Ctrl+C)")
    a = ap.parse_args()

    step("TE simulation data")
    run(["scripts/fetch_te_data.py"])
    if a.build:
        step("Build the twin into the gateway (backup first)")
        run(["scripts/ignition/build_gateway.py", "--fresh"])
    if a.verify:
        step("Verify: nine checks against the running gateway (it drives the data servers itself)")
        run(["scripts/ignition/verify_gateway.py"])

    step("Start the data servers")
    te_args = ["--run", "fault6", "--start", "236"] if a.fault else ["--run", "normal"]
    procs = [subprocess.Popen([PY, "scripts/ignition/te_sim_server.py", *te_args], cwd=ROOT),
             subprocess.Popen([PY, "scripts/ignition/demo_points_server.py"], cwd=ROOT)]
    time.sleep(3)
    for p in procs:
        if p.poll() is not None:
            raise SystemExit("a data server stopped at startup (is port 4841 or 4842 already in use?)")
    print(f"""
The twin is live. Open:
  {URL}/data/perspective/client/PIDTwin            Tennessee Eastman overview{' (fault 6: watch PI-107 turn red in ~25 s)' if a.fault else ''}
  {URL}/data/perspective/client/PIDTwin/open100/0  extracted sheet 0: 24 mapped points live, the rest not connected
  {URL}/data/perspective/client/PIDTwin/open100/N  sheets 1-11
Ctrl+C stops the data servers.""", flush=True)
    try:
        t0 = time.time()
        while not a.seconds or time.time() - t0 < a.seconds:
            if any(p.poll() is not None for p in procs):
                raise SystemExit("a data server stopped")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
                p.wait(10)
        print("data servers stopped")


if __name__ == "__main__":
    main()
