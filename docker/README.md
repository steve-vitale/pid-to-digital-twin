# The one-click demo (Docker)

This runs the whole twin on your computer: Ignition, the live Tennessee Eastman plant, and the extracted drawings.
You don't need Python, settings or keys. It's an extra option. If you'd rather not install Docker, the
[15-minute quickstart](../docs/IGNITION_QUICKSTART.md) does the same thing with an Ignition you install yourself.

## What you need

- A Windows, Mac or Linux computer with about 4 GB of free memory and 5 GB of free disk space.
- **Docker Desktop**, free for personal use: https://www.docker.com/products/docker-desktop/.
  - Install it, start it, and wait until it says *Engine running*.
  - On Windows, the installer may ask to restart the computer once.

## Start it (Windows)

1. Download this project: the green **Code** button on GitHub → **Download ZIP** → unzip it anywhere.
2. Double-click **`start-demo.bat`**.
   - The first time takes several minutes: it downloads Ignition (about 1 GB).
   - When it's ready, the plant screen opens in your browser by itself.
3. Look around:
   - **Plant screen:** http://localhost:8088/data/perspective/client/PIDTwin. Live values from the open Tennessee
     Eastman simulation.
   - **Extracted drawings:** http://localhost:8088/data/perspective/client/PIDTwin/open100/0 (through `/11`).
     - On sheet 0, 24 instruments show live values. They were mapped from a demo I/O list, and their values are
       synthetic.
     - Every other instrument shows Ignition's "not connected" marker. That's honest: no data source is connected
       to it yet.
4. **See an alarm:** double-click **`fault-demo.bat`**. In about 30 seconds the reactor pressure (PI-107) passes
   its limit and turns red. **`normal-demo.bat`** switches back.
5. **Stop:** double-click **`stop-demo.bat`**. Nothing is deleted, and `start-demo.bat` brings it back.

## Start it (Mac or Linux)

In a terminal, in the unzipped folder:
```
docker compose up -d --build                                          # start (first time: several minutes)
docker compose exec -T te-sim sh -c "echo fault6 236 > /tmp/te-run"   # fault 6: the alarm
docker compose exec -T te-sim sh -c "echo normal 0 > /tmp/te-run"     # back to normal
docker compose stop                                                   # stop
```
Then open the same addresses as above.

## Good to know

- **It runs on your computer only.** Nothing is reachable from your network.
- **Ignition runs as a free trial**, which pauses after 2 hours. To get another 2 hours:
  1. Open http://localhost:8088.
  2. Click **Log In to Reset**.
  3. Sign in with the login below.

  The trial can be reset as often as you like.
- **Gateway settings login:** `admin` / `ChangeMe-TwinDemo1`. You only need it to change Ignition's settings,
  never to look at the screens. It's a demo password, and everyone who downloads this demo has the same one, so
  change it if you keep the demo running.
- **Remove it completely** and free the disk space: `docker compose down -v` in the folder, then delete the folder.
- **Something wrong?**
  - Make sure Docker Desktop says *Engine running*, and nothing else uses port 8088.
  - Then run `stop-demo.bat` and `start-demo.bat` again.
  - `docker compose logs` shows what each part is doing.

## What's inside, and how it's checked

| Part | What it is |
|---|---|
| `gateway` | The official Ignition 8.3.10 image. On first start it restores `docker/twin-demo.gwbk`: the Twin tags, the PIDTwin screens, and read-only connections to the two data servers |
| `te-sim` | `scripts/ignition/te_sim_server.py`, replaying the open Tennessee Eastman data (normal, or fault 6) |
| `demo-points` | `scripts/ignition/demo_points_server.py`, serving synthetic values for the 24 mapped demo points |

**Checks:** every change to these files starts the whole demo from nothing on GitHub's test machines and opens the
screens in a real browser (`.github/workflows/docker-demo.yml`, `scripts/check_docker_demo.py`). It checks the
screens show live values, that sheet 0 shows 24 live and 12 not connected, and that the fault turns the alarm red.
Screenshots from each run are kept with the run. Each change is started from scratch three times in parallel, and the results are posted on
the run page. Record at release: 5 of 6 from-scratch starts passed. One early failure is unexplained, because it
happened before the check posted its reasons. If yours doesn't come up, `stop-demo.bat` then `start-demo.bat` is
the first thing to try.

## How the demo backup is made (for maintainers)

The backup comes from a **throwaway** Ignition gateway, never from a working one:
1. Install a fresh gateway and commission it with the demo login above.
2. Create a temporary security level and API key.
3. Run `build_gateway.py --demo-backup` with `IGNITION_SIM_URL=opc.tcp://te-sim:4841/te-sim` and
   `IGNITION_DEMO_POINTS_URL=opc.tcp://demo-points:4842/open100-demo`. This mode skips the verifier's user, exposed
   tags and write probe.
4. Delete the temporary key and level.
5. Download the backup from the gateway's web page (Platform → Backup & Restore).
6. Run it through `scripts/ignition/prepare_demo_backup.py`. That sets a neutral gateway name, and it refuses if any
   API key, extra user, or name of the build machine or its users remains.

The backup also holds the encryption keys that throwaway gateway generated for itself. They're shared by everyone
who runs this demo, which is one more reason it runs on your computer only and isn't meant for anything else.
