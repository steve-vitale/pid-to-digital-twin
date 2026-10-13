# Current-source Ignition handoff — 2026-10-10

Desktop continuation: see [Claude resume — 2026-10-12](CLAUDE_RESUME.md) for
current local branches, preservation commits and desktop offline checks. This
October 10 report retains its historical environment observations and acceptance
contract; the desktop becoming available does not complete native acceptance.

## Update 2026-10-12/13: native run in a disposable gateway

The contract below was exercised in a **disposable Ignition 8.3.10 Docker container** (trial, localhost only,
removed afterwards) on commit `485f000` ([journal entry 38](JOURNAL.md#38-import-the-current-project-into-a-real-gateway-and-watch-what-the-offline-checks-could-not),
receipt [`native-current-20261013.json`](../out/ignition/gateway/receipts/native-current-20261013.json)). The first
import exposed two defects that offline checks had missed: every script transform failed to parse, and no-data
values rendered as `null`. A third, TI-109's invisible band, was found on screen. All three were fixed with
regression tests. After the fixes: V1–V8 PASS; 23/23 routes load and reload; 277/277 click targets, Back, Back/Forward
and repeated clicks pass; quality census 52 + 24 Good, SC-212 and 334 placeholders Bad, 0 false-good; the
stopped-replay and recovery transitions and the recorded fault 6 behave as specified. The 390 px viewport is
**partial**: reachable by scrolling, not a phone layout. Still not established: operator/site acceptance, actual
write rejection beyond V7's two refused writes, licensed PI import, responsive physics and production readiness.
The October 10 text below is kept as the historical contract.

## Status and exact scope

**Local artifacts regenerated; runtime and browser acceptance NOT RUN.** Reviewed model source:
`3205ce8ea203d5e6e36fa8174cd58d85d40bf07e`. The accompanying local commit adds current
provider/project exports, offline predicate alignment, tests and this handoff. It does not import or
start Ignition, authorize a deployment, create accounts, expose OPC, or change access/security.

**ZIP provenance:** the committed `out/ignition/gateway/PIDTwin.zip` is the historical public export.
The 23-view ZIP described below was generated locally with `--write-only`; it is not that committed ZIP.
Regenerate in a disposable checkout before current-source testing/import, and record its exact hash.
Current provider/build metadata do not turn the historical ZIP into a matched current-source kit.

Current-source artifacts after local regeneration:
- `out/ignition/gateway/PIDTwin.zip`: 23 Perspective views, 23 routes; overview, legacy `/mimic`
  alias, six spatial unit/detail screens, alarms, schematic, drawing index and 12 drawing views.
- `out/ignition/gateway/twin_provider.json`: 53 TE instances (52 recorded channels and SC-212,
  explicitly unavailable), 910 OPEN100 instances including the metadata-only valve callout.
- `out/ignition/gateway/build_meta.json`: sources, alarms, ranges, review state and mappings.
Local receipt manifests and browser-contract JSON are not included in this publication. The checklist below
describes the acceptance scope; regenerate and identify the exact candidate before runtime testing.

Reproduction was limited to:

```sh
env -u IGNITION_ENV_FILE -u IGNITION_API_TOKEN \
  python scripts/ignition/build_gateway.py --write-only --twin out/twin/r2-tiles-trace/codex
```

`--write-only` returns before constructing `Gateway`, backing up/importing a gateway, creating a
verifier account, changing OPC exposure or connections, or configuring history. It does generate
local normal-band outputs as well as the provider/project files. The offline regression regenerates
into a temporary directory and demands byte-identical provider, project and build metadata, with
network entry points and `Gateway` construction blocked. Imports in the test do not load a private
`IGNITION_ENV_FILE`. This is a path-specific offline control, not a blanket claim that every tool in
this repository is network-free or safe to run.

## Important: the Docker backup is historical

**`docker compose up` restores `docker/twin-demo.gwbk`, NOT these regenerated files.** Compose mounts
that backup at `/restore.gwbk`; it does not run the current source builder or import the ZIP/provider.
The backup remains untouched and retains its exact recorded hash. It cannot establish current-source
runtime acceptance. A pre-existing `gateway-data` volume can also retain old state.

`check_docker_demo.py` is a historical Docker-demo test: its numeric screen counts and fault-control
command do not constitute this current-source browser contract. Do not run it as a substitute for
current-source validation. Historical gateway receipts, screenshots and tests in this repository stay
historical. Starting compose also entails the configured Ignition EULA acceptance; that action has
not been taken in this task.

## Reviewed semantics that must survive import

- S0-IN019 / MS 14010 remains an unverified drawing callout associated by field-scoped review with
  existing valve S0-VL013. It uses `Callout_Valve`, with AssetId/SourceTag and ReviewStatus metadata.
  There is **no PV, OPC address, I/O assignment, inferred moisture measurement, actuator type,
  control signal, new physical valve or symbol merge**. Identifier and valve-association review
  lineage are retained in the source. The original drawing raster itself is not rewritten.
- S0-IN002 and S0-IN003 both retain FT 1401, unverified/NEEDS CLARIFICATION, separate source records
  and placeholder addresses. Neither gets the ambiguous synthetic FT-1401 mapping. No physical
  identity/count is inferred and no clarification message has been sent.
- Existing synthetic OPEN100 mappings remain 24. They are demonstration data, not plant I/O.
  Of 358 OPEN100 PV instances, 334 remain placeholders; the callout is not a 359th PV.
- TE has 52 recorded channels, including all expanded analyzer components, and one unavailable
  SC-212. Reactor detail shows NOT CONNECTED and a spatial UNKNOWN / no replay source marker.
  Its schematic may bind the unavailable PV only to show bad quality, never a healthy number.
- Level fill represents measured percent, not volume; output indicators represent recorded output,
  not measured valve position. Flow values stay on their reviewed stream boundary/leader.
  Missing/invalid quality must not become a healthy-looking number or filled equipment shape.

## Isolated development gateway prerequisites (not executed)

This workspace has Java 21 and Chromium, but no Docker/Podman/container engine or running Ignition.
The desktop is offline and no saved coding environment is available. Runtime work is blocked;
Chromium alone does not provide a Perspective gateway.

Before any runtime step, obtain an approved isolated development target and authorization for the
specific startup/import/configuration actions. Do not use a production gateway. Resolve license
acceptance, account/access changes, credentials and port/security settings separately as required.
Do not run normal or `--fresh` build mode under this file-only approval: they have broader effects,
including verifier-user creation and OPC provider exposure. No credential is included here.

A qualified authorized operator should:
1. Record target identity, Ignition version (the previous demo used 8.3.10), installed Perspective/
   OPC/historian modules, timezone, license/trial state, and an approved rollback backup.
2. Verify the exact local commit and every artifact hash before transfer/import. Use isolated
   provider `Twin` and project `PIDTwin`; identify any pre-existing resources and reconcile stale
   members/views rather than silently overlaying incompatible old state.
3. Import the current provider JSON and project ZIP using an approved path. Configure only the
   authorized synthetic TE-Sim and OPEN100-Demo sources and TwinHistory as needed; never infer
   permission to expose providers, weaken transport security, or create verifier credentials.
4. Export the held provider/project back from that gateway. Run import-fidelity, source reconciliation
   and binding checks against these exact artifacts. Record counts and any default normalization;
   abort on semantic drift or missing resources. The revised V2/V3 predicates can be exercised
   read-only once an authorized connection exists; their local pass is not a gateway pass.
5. Exercise the browser contract below, recording actual state/quality/timestamps and screenshots.
   Fault injection, simulator switching, write probes and destructive negative controls require
   their own approved test plan/target. Do not point historical `--controls` at any gateway casually.

## Current-source browser acceptance checklist

Runtime result as of October 10: **NOT RUN / blocked on authorized isolated gateway**. Results from the
disposable-container run on October 12/13 are in journal entry 38: items 1–7 pass in that environment,
except the narrow viewport (partial) and the write-probe and operator parts that remain unrun. The project
opens without a login, so the login-interruption case did not apply. Item 8's
evidence is the receipt above.
Use project base `/data/perspective/client/PIDTwin` on the verified target; do not assume the
historical localhost endpoint exists. Derive and record all exact routes from the regenerated candidate.

1. **Identity and loading:** export hashes/configuration prove the candidate before opening pages.
   Load all 23 routes directly, reload them, and reject missing views, binding/script errors, stale
   resources or login/permission pages masquerading as loaded views. Capture overview and all six
   spatial detail screens at normal desktop and narrower viewport sizes; check scrolling/readability.
2. **Navigation:** click each header destination, every equipment overview target, stream cross-link,
   Back to Overview, drawing thumbnail, `/schematic` and `/alarms`. Repeated clicks, browser Back/
   Forward and direct bookmarked detail routes must land on the correct view. `/mimic` must display
   the same overview, with no second competing process-mimic tab. Test interruptions after login or
   page load; no hidden overlay or obsolete view should trap navigation.
3. **Live/read-only data:** all 52 TE recorded PVs read Good and update, with unique expected replay
   channels; all 24 pre-existing mapped OPEN100 PVs may read Good only with the approved synthetic
   source running. Match paths to the regenerated candidate inventory, not numeric-label counts. Missing samples do not
   masquerade as data. Read-only configuration is checked offline; actual write rejection remains
   separately untested until an explicitly approved isolated write-probe test is performed.
4. **Unavailable quality:** SC-212 stays bad/not connected; the reactor shows both NOT CONNECTED
   and UNKNOWN / no replay source. All 334 OPEN100 placeholders stay non-Good, and neither FT 1401
   record is silently mapped. Disconnect/reconnect or bad/uncertain/nonfinite data tests on the
   isolated replay must show UNKNOWN/hatching and recover without a false healthy state. Runtime
   quality observations are distinct from the fabricated Good/Bad objects used in offline controls.
5. **Callout:** MS 14010 is present as source drawing/metadata, without a live number, PV member,
   OPC address, moisture label or inferred signal. Confirm the held callout type and source review
   scope, not just the screen pixels. Do not treat unverified metadata as operator approval.
6. **Spatial detail:** equipment, stream direction, external endpoints, leaders and values match the
   reviewed layouts on Feed, Reactor, Condenser, Separator, Compressor and Stripper. No flows appear
   centered on the wrong vessel; no unresolved point gets a physical anchor. Analyzer inventories,
   history rows and existing navigation remain accessible below the spatial graphic.
7. **Display semantics:** verify normal, outside-band and existing alarm states separately. No new
   setpoint, alarm, inferred process value, flow animation or valve-position claim is introduced.
   Percent-level and output gauges must preserve units and bad-quality behavior. Existing alarm
   pipeline and liveness/plausibility checks require actual runtime evidence, not static exports.
8. **Evidence and sign-off:** save gateway exports, tested commit/hashes, browser version, routes,
   viewport/screenshots, per-tag quality/timestamps, console/gateway errors and pass/fail results.
   Report failures and restore the approved isolated state. Browser/runtime success still does not
   establish operator usability acceptance, site approval or production readiness.

## Offline verification meaning

`test_current_gateway_artifacts.py` checks JSON/resource shape, ZIP integrity, deterministic generation,
source-derived reconciliation, every actual tag binding, all routes/navigation targets, six spatial
views, reviewed semantics, and synthetic quality decisions. Negative controls reject a missing analyzer
channel, omitted ordinary FT 1401 binding, fabricated callout PV/address, missing/numeric SC-212 markers,
missing required value binding, false-Good placeholders/SC-212 and bad fed data. It does not use an
Ignition-native schema validator, browser or gateway. The full aggregate suite includes this test.
