# Native Ignition acceptance of the current project

This page covers the current 23-view Perspective project and its tag provider: which files belong together, what
had to survive the import, how it was tested in a real gateway, and what that test doesn't cover. The full story,
including the bugs the gateway found, is [journal entry 38](JOURNAL.md#38-import-the-current-project-into-a-real-gateway-and-watch-what-the-offline-checks-could-not).

## Result

**Passed on 2026-10-13 in a disposable Ignition 8.3.10 gateway**, except the 390 px width, which is partial.

The gateway was the official `inductiveautomation/ignition:8.3.10` image on the trial license, in a fresh container
with a fresh volume, its port bound to localhost only, and removed afterwards. It was fed by the replay image built
from `docker/sim.Dockerfile` (recorded Tennessee Eastman replay plus 24 synthetic OPEN100 points). No real plant,
controls or site gateway was involved. Commit under test: `485f000`. Receipt:
[`native-current-20261013.json`](../out/ignition/gateway/receipts/native-current-20261013.json).

The first import found two defects that every offline check had missed: all 580 script transforms failed to parse,
and no-data values rendered as the text `null`. A third, TI-109's invisible normal band, was found on screen. All
three were fixed with regression tests before the final run.

| Check | Result |
|---|---|
| Import fidelity (V1), both directions | PASS: 1,253 tag nodes and 23 views sent, 0 differences; the 23 exported views are identical JSON |
| Reconciliation (V2) | PASS: 53/53 TE, 910/910 OPEN100; MS 14010 stays metadata-only |
| Binding resolution (V3) | PASS: 1,082 bindings on 23 views |
| Quality honesty (V4) | PASS: 76 fed values Good; SC-212 and 334 placeholders Bad; 0 false-good |
| Liveness (V5), plausibility (V6) | PASS: 76 of 76 changed; 52 inside range |
| Read-only (V7) | PASS: two writes to twin tags refused (BadUserAccessDenied) |
| Alarm pipeline (V8), recorded fault 6 | PASS: A feed flagged first; PI-107 alarm active 0.5 s after crossing 2,895 kPa |
| Direct load and reload of all 23 routes | PASS 23/23 |
| Every navigation target clicked | PASS 277/277; Back after each 277/277; Back/Forward chain 6/6; repeated clicks; 0 console errors |
| Replay stopped, then restarted | PASS: 52 TE values went Uncertain and the screens read UNKNOWN; Good again within about 14 s |
| Fault replay on screen | PASS: amber values before the alarm, PI-107 red at the alarm, alarm table populated |
| Desktop layout, 1600 × 930 | PASS |
| 390 px width | **PARTIAL:** every route is reachable by scrolling and touch, but it is a fixed 1600 px control-room layout, not a phone layout |

**Not established by this run:** operator usability or site acceptance, responsive process physics (the data is
recorded replay), PI import, write rejection beyond V7's two attempts, and production readiness. V9 (the git change
record) belongs to the normal scripted build and doesn't apply to a disposable archive.

**Set up differently from a site, on purpose:** the API key was provisioned into the disposable gateway's config
files, HTTP was used on localhost, and the verifier ran inside the container's network namespace so the OPC UA server
could stay bound to localhost.

## Which files belong together

The committed `out/ignition/gateway/PIDTwin.zip` is the older historical export. It does not match the current
provider and build metadata. Before testing the current project, regenerate all three files together in a disposable
checkout and record their hashes:

```sh
pip install -r requirements.txt
python scripts/fetch_te_data.py
python scripts/ignition/build_gateway.py --write-only
```

- `out/ignition/gateway/PIDTwin.zip`: 23 Perspective views and routes: overview, the `/mimic` alias of it, six unit
  screens, alarms, schematic, drawing index and 12 drawing views.
- `out/ignition/gateway/twin_provider.json`: 53 TE instances (52 recorded channels plus SC-212, which has no data)
  and 910 OPEN100 instances, including one metadata-only valve callout.
- `out/ignition/gateway/build_meta.json`: sources, alarms, ranges, review state and mappings.

`--write-only` returns before it connects to a gateway, takes a backup, creates the verifier account, changes OPC
exposure or configures history. It does write the local normal-band outputs. An offline test regenerates into a
temporary folder and requires byte-identical provider, project and build metadata, with network calls blocked.

**The Docker demo is a different, older generation.** `docker compose up` restores `docker/twin-demo.gwbk`, the
October 8 backup, not these regenerated files. Its CI checks (`check_docker_demo.py`) cover that backup only. A
pre-existing `gateway-data` volume can also hold old state.

## What has to survive the import

- **MS 14010 (S0-IN019)** stays an unverified drawing callout, associated with the existing valve S0-VL013. It uses
  `Callout_Valve` with AssetId, SourceTag and ReviewStatus metadata. It has no PV, OPC address, I/O assignment,
  inferred measurement, actuator type or control signal, and no new valve is created.
- **FT 1401 (S0-IN002 and S0-IN003)** stay two separate, unverified records that need clarification, each with a
  placeholder address. Neither gets the ambiguous synthetic FT-1401 mapping.
- **24 synthetic OPEN100 mappings** stay demonstration data, not plant I/O. Of 358 OPEN100 PV instances, 334 remain
  placeholders.
- **TE:** 52 recorded channels, including the expanded analyzer components, plus SC-212 with no data. The reactor
  screen shows NOT CONNECTED and UNKNOWN / no replay source for it, never a healthy number.
- **Display meaning:** level fill is measured percent, not volume; output indicators show recorded controller
  output, not measured valve position. Missing or bad quality must never look like a healthy value or a filled
  vessel.

## How to repeat it

Use an isolated, non-production gateway that you are authorized to change. Imports, account setup and fault
controls change its state. Never point these tools at a production gateway.

1. **Record the target:** Ignition version (this run used 8.3.10), modules, license or trial state, and a rollback
   backup.
2. **Identify the candidate:** the commit and the SHA-256 of all three files above. Use provider `Twin` and project
   `PIDTwin`, and clear stale resources rather than overlaying old state.
3. **Import** the provider JSON and project ZIP from the same build. Configure only the synthetic TE-Sim and
   OPEN100-Demo sources and the `TwinHistory` historian.
4. **Export back** the provider and project from the gateway and compare them with what was sent.
5. **Run the verifier and census** with `scripts/ignition/acceptance/live_checks.py` (V1–V8 and a per-path quality
   census through the gateway's own OPC UA server; it switches a separately running replay through its control
   file).
6. **Run the browser contract:** `python scripts/ignition/acceptance/nav_contract.py PIDTwin.zip > contract.json`
   derives every route and click target from the exact ZIP, then
   `node scripts/ignition/acceptance/browser_contract.js contract contract.json out.json` loads, reloads and clicks
   all of them (needs Node and Playwright with Chromium). The `capture` mode takes screenshots at desktop and
   390 px widths.
7. **Watch it like an operator:** normal replay, the recorded fault, the replay stopped and restarted. Check that
   "no data source" and "broken" look different.
8. **Keep the evidence:** exports, commit and hashes, browser version, routes, screenshots, per-tag quality and
   timestamps, console and gateway errors, and pass/fail per check. Then restore or remove the test gateway.

The offline preflight (`scripts/ignition/acceptance_preflight.py`, see
[the replication guide](REPLICATE_AT_YOUR_PLANT.md#offline-exact-candidate-ignition-preflight)) checks a candidate's
files before any of this. It cannot replace the gateway run.

## The acceptance checklist

1. **Identity and loading:** export hashes prove the candidate before pages are opened. All 23 routes load directly
   and on reload, with no missing views, binding or script errors, or login pages posing as loaded views.
2. **Navigation:** every header destination, equipment target, stream cross-link, Back to Overview, drawing
   thumbnail, `/schematic` and `/alarms`. Repeated clicks, Back/Forward and bookmarked detail routes land on the
   right view. `/mimic` shows the same overview, with no second competing tab.
3. **Live, read-only data:** all 52 TE recorded values read Good and update; the 24 mapped OPEN100 values read Good
   only while the synthetic source runs. Missing samples never pass as data.
4. **Unavailable quality:** SC-212 stays Bad and not connected. All 334 OPEN100 placeholders stay non-Good, and
   neither FT 1401 record is silently mapped. Stopping the replay shows UNKNOWN and hatching, then recovers without
   a false healthy state.
5. **Callout:** MS 14010 appears as drawing metadata only, with no live number, PV, OPC address or inferred signal.
6. **Unit screens:** equipment, stream direction, endpoints, leaders and values match the layouts on Feed, Reactor,
   Condenser, Separator, Compressor and Stripper. No unresolved point gets a physical position.
7. **Display meaning:** normal, outside-band and alarm states are checked separately. No new setpoint, alarm,
   inferred value, flow animation or valve-position claim appears.
8. **Evidence:** everything in step 8 above. A browser and runtime pass still doesn't establish operator
   usability, site approval or production readiness.

## What the offline test covers

`scripts/test_current_gateway_artifacts.py` checks JSON and resource shape, ZIP integrity, deterministic generation,
source reconciliation, every tag binding, all routes and navigation targets, the six unit screens, the callout and
FT 1401 rules, and synthetic quality decisions. It parses every exported script transform under Perspective's own
function signature, so the parse bug the gateway found now fails offline too. Negative controls reject a missing analyzer channel, an
omitted FT 1401 binding, a fabricated callout PV or address, missing SC-212 markers, a missing value binding,
false-good placeholders and bad fed data. It uses no Ignition schema validator, browser or gateway, which is why the
native run above was still needed. The full suite includes it.
