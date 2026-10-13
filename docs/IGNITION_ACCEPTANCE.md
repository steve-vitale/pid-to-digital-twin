# Native Ignition acceptance of the current project

This page covers the current Perspective project (24 views: the 23 control-room views plus the narrow `/m`
overview) and its tag provider: which files belong together, what had to survive the import, how it was tested in a
real gateway, and what that test doesn't cover. The full stories, including the bugs each gateway run found, are
[journal entry 38](JOURNAL.md#38-import-the-current-project-into-a-real-gateway-and-watch-what-the-offline-checks-could-not)
(first import) and [journal entry 47](JOURNAL.md#47-count-what-the-bands-detect-and-make-lost-data-an-alarm) (this run).

## Result

**Passed on 2026-10-13 in a disposable Ignition 8.3.10 gateway, on commit `4a00c35`.** This build includes the
topology correction ([journal entry 42](JOURNAL.md#42-verify-the-te-topology-against-the-simulator-source): the
purge and its tags on the separator), the data-source diagnostic alarms, the active-alarm count and the narrow
overview. The 390 px width is now a real narrow layout at `/m`; the control-room screens are still fixed 1600 px
layouts that scroll on a phone.

The gateway was the official `inductiveautomation/ignition:8.3.10` image (re-pulled for this run, digest in the
receipt) on the trial license, in a fresh container with a fresh volume and network, its port bound to localhost
only. It was fed by the replay image built from `docker/sim.Dockerfile` at the commit (recorded Tennessee Eastman
replay plus 24 synthetic OPEN100 points). No real plant, controls or site gateway was involved. Containers, volume,
network, both images and the build cache were removed afterwards; the rollback is recorded in the receipt. Receipt:
[`native-current-20261013-alarms.json`](../out/ignition/gateway/receipts/native-current-20261013-alarms.json).

**Commit identity.** The candidate was a `git archive` of local commit `4a00c35` on the working branch. A
`--write-only` build of it reproduced the committed project ZIP byte for byte (SHA-256 `8982ccd2…`; provider
`3ae2621c…`), so the file hashes identify the candidate even if the commit is later rebased or squashed before
publishing. After the branches were integrated (journal entry 49), a `--write-only` build of the merged source
reproduced the same ZIP byte for byte, so this acceptance applies to the merged build.

The first import of this candidate found one defect the offline tests had missed: both data-source alarms stayed
active with a count of 0, because Ignition's AboveValue alarm mode is inclusive and the setpoint was 0. The setpoint
is now 0.5, with a regression test. The first walk of the screens with the replay stopped found a second: every band
indicator drew its pointer at the scale minimum with no Good value, which reads as a real low reading. The pointer is
now hidden without Good data, also with a test. The run below is of the fixed commit.

| Check | Result |
|---|---|
| Import fidelity (V1), both directions | PASS: 1,256 tag nodes and 24 views sent, 0 differences; the 24 exported views are identical JSON |
| Reconciliation (V2) | PASS: 53/53 TE, 910/910 OPEN100; MS 14010 stays metadata-only |
| Binding resolution (V3) | PASS: 1,448 bindings on 24 views |
| Quality honesty (V4) | PASS: 76 fed values Good; SC-212 and 334 placeholders Bad; 0 false-good |
| Liveness (V5), plausibility (V6) | PASS: 76 of 76 changed; 52 inside range |
| Read-only (V7) | PASS: two writes to twin tags refused (BadUserAccessDenied) |
| Alarm pipeline (V8), recorded fault 6 | PASS: A feed flagged first; PI-107 alarm active 0.5 s after crossing 2,895 kPa |
| Direct load and reload of all 24 routes | PASS 24/24 |
| Every navigation target clicked | PASS 284/284 (277 control-room targets plus 7 on `/m`); Back after each 284/284; Back/Forward chain 6/6; repeated clicks; 0 console errors |
| **Data source lost: TE replay stopped** | PASS: 52 TE values went Uncertain, `ReplayValuesNotGood` read 52, the "Data source lost: TE replay" diagnostic alarm went active and every header read DATA SOURCE LOST |
| **Data source recovered** | PASS: 52 Good again and the diagnostic alarm cleared within about 25 s of restarting the replay |
| **Data source lost: OPEN100 demo points stopped** | PASS: 24 mapped values went Uncertain, the second diagnostic alarm fired, then cleared within about 25 s of restart |
| **Header count = active alarms in the table** | PASS with a timing caveat: sampled every 3 s, 40/40 matches through the fault (0, 1, then 2 active process alarms) and 29/30 through a replay loss and recovery. The one mismatch, and one capture during the fault, came within about 2 s of an alarm changing state: the header's count polls every second, the table refreshes every two |
| **Process alarm active when the data is lost** | Observed, unchanged: PI-107's high-pressure alarm stayed active on its last value while PI-107 read UNKNOWN and DATA SOURCE LOST was raised. Header and table agreed (1 process + 1 diagnostic = 2 active) |
| **390 px narrow overview (`/m`)** | PASS: 390 px wide with no horizontal scroll; alarm count, data source and active alarm list first, then the six units with their key values; UNKNOWN on grey with the replay stopped; DATA SOURCE LOST and the diagnostic alarm row at the top |
| Fault replay on screen | PASS: amber values before the alarm, PI-107 red at the alarm, alarm table populated |
| Desktop layout, 1600 × 930 | PASS; the control-room screens are unchanged in layout. At 390 px they still scroll in both directions |

Screenshots: [narrow, normal](screenshots/native-narrow-m-normal.png),
[narrow, replay stopped](screenshots/native-narrow-m-replay-disconnected.png),
[overview, replay stopped](screenshots/native-overview-replay-disconnected.png),
[alarms, replay stopped](screenshots/native-alarms-replay-disconnected.png),
[alarms, process alarm during data loss](screenshots/native-alarms-alarm-during-data-loss.png),
[reactor, replay stopped](screenshots/native-reactor-replay-disconnected.png),
[separator with the corrected purge](screenshots/native-separator-normal.png).

**Not established by this run:** operator usability or site acceptance, the narrow view on real phones (checked in
headless Chromium at 390 × 844 only), operations approval of the diagnostic alarms' priority (Medium, a first-pass
choice) or of how process alarms should behave on stale data, responsive process physics (the data is recorded
replay), PI import, write rejection beyond V7's two attempts, and production readiness. V9 (the git change record)
belongs to the normal scripted build and doesn't apply to a disposable archive.

**Also observed, not changed:**
- Both diagnostic alarms activate for a moment when the tag provider first loads (no value is Good yet) and clear
  by themselves. They stay in the alarm history as Cleared, Unacknowledged.
- The alarm table colours rows by Ignition's default priority colours, so the Medium diagnostic row is red like a
  process alarm. The header keeps the two apart; the table styling was left at the default.
- At 390 px the alarm table shows only its first two columns (time and display path). The display path names the
  alarm ("Data source lost: TE replay"), so the row is readable, but priority and state are off-screen.
- The gateway again logged "Received event for missing view TE/Alarms" after navigating away from the alarm table,
  with no visible effect.

**Set up differently from a site, on purpose:** the API key was provisioned into the disposable gateway's config
files, HTTP was used on localhost, and the verifier ran inside the container's network namespace so the OPC UA server
could stay bound to localhost.

**The earlier run** (2026-10-13, commit `485f000`, published as `34b4ef5`, 23 views, before the topology
correction) is kept as [`native-current-20261013.json`](../out/ignition/gateway/receipts/native-current-20261013.json).
It does not cover the current build.

## Which files belong together

The committed provider, project ZIP and build metadata are regenerated with each change; for the candidate above a
`--write-only` build reproduced the committed ZIP byte for byte. Still, before testing, regenerate all three files
together in a disposable checkout and record their hashes:

```sh
pip install -r requirements.txt
python scripts/fetch_te_data.py
python scripts/ignition/build_gateway.py --write-only
```

- `out/ignition/gateway/PIDTwin.zip`: 24 Perspective views and routes: overview, the `/mimic` alias of it, the
  narrow `/m` overview, six unit screens, alarms, schematic, drawing index and 12 drawing views.
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
   390 px widths; the `count` mode samples the header's alarm count against the alarm table.
7. **Watch it like an operator:** normal replay, the recorded fault, the replay stopped and restarted, the demo
   points stopped and restarted, and the replay stopped while a process alarm is active. Check that the data-source
   alarm fires and clears, that the header's count matches the alarm table, and that "no data source" (not
   connected) and "no Good data now" (UNKNOWN) look different.
8. **Keep the evidence:** exports, commit and hashes, browser version, routes, screenshots, per-tag quality and
   timestamps, console and gateway errors, and pass/fail per check. Then restore or remove the test gateway.

The offline preflight (`scripts/ignition/acceptance_preflight.py`, see
[the replication guide](REPLICATE_AT_YOUR_PLANT.md#offline-exact-candidate-ignition-preflight)) checks a candidate's
files before any of this. It cannot replace the gateway run.

## The acceptance checklist

1. **Identity and loading:** export hashes prove the candidate before pages are opened. All 24 routes load directly
   and on reload, with no missing views, binding or script errors, or login pages posing as loaded views.
2. **Navigation:** every header destination, equipment target, stream cross-link, Back to Overview, drawing
   thumbnail, `/schematic` and `/alarms`. Repeated clicks, Back/Forward and bookmarked detail routes land on the
   right view. `/mimic` shows the same overview, with no second competing tab.
3. **Live, read-only data:** all 52 TE recorded values read Good and update; the 24 mapped OPEN100 values read Good
   only while the synthetic source runs. Missing samples never pass as data.
4. **Unavailable quality:** SC-212 stays Bad and not connected. All 334 OPEN100 placeholders stay non-Good, and
   neither FT 1401 record is silently mapped. Stopping the replay shows UNKNOWN and hatching and raises the
   "Data source lost" diagnostic alarm, then recovers without a false healthy state and the alarm clears.
5. **Callout:** MS 14010 appears as drawing metadata only, with no live number, PV, OPC address or inferred signal.
6. **Unit screens:** equipment, stream direction, endpoints, leaders and values match the layouts on Feed, Reactor,
   Condenser, Separator, Compressor and Stripper. No unresolved point gets a physical position.
7. **Display meaning:** normal, outside-band and alarm states are checked separately. The header counts active
   alarms, matching the alarm table, with process and diagnostic alarms shown apart. No new process setpoint,
   process alarm, inferred value, flow animation or valve-position claim appears; the two data-source diagnostics
   are the only alarms not taken from a published source.
8. **Evidence:** everything in step 8 above. A browser and runtime pass still doesn't establish operator
   usability, site approval or production readiness.

## What the offline test covers

`scripts/test_current_gateway_artifacts.py` checks JSON and resource shape, ZIP integrity, deterministic generation,
source reconciliation, every tag binding, all routes and navigation targets, the six unit screens, the callout and
FT 1401 rules, and synthetic quality decisions. It parses every exported script transform under Perspective's own
function signature, so the parse bug the gateway found now fails offline too. Negative controls reject a missing analyzer channel, an
omitted FT 1401 binding, a fabricated callout PV or address, missing SC-212 markers, a missing value binding,
false-good placeholders and bad fed data. Since journal entry 47 it also checks that the header counts each configured
alarm once, that each data-source diagnostic counts exactly the fed values of its connection with a 0.5 setpoint,
that "not connected" and UNKNOWN each have one style on every screen (two alarmed schematic labels keep their
alarm colour instead), that band pointers hide without Good data, and
that `/m` fits 390 px with alarms first. It uses no Ignition schema validator, browser or gateway, which is why the
native run above was still needed. The full suite includes it.
