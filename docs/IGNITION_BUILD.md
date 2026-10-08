# Ignition build and verification (plan written before the build; results at the end)

Committed before any Ignition configuration exists. The checks below are the acceptance test. The build is done when
they pass, and when the verifier has itself been shown to catch deliberately broken configurations.

## What gets built

| Piece | Ignition concept | Source |
|---|---|---|
| A dedicated tag provider, `Twin` | Realtime tag provider. It keeps twin tags separate from any production provider, the same separation a site uses between environments | This repo |
| UDT definitions per equipment and instrument type | UDTs with parameters (`BasePath`, `OPCServer`) and members carrying engineering units, ranges and documentation | `generate.py` / `build_twin.py` |
| UDT instances, one per asset | UDT instances, foldered by system/sheet | The twin's asset hierarchy |
| Live values for the TE plant | An OPC UA device (simulator) replaying the open Tennessee Eastman simulation data (normal operation plus a fault case): `scripts/ignition/te_sim_server.py` | Braatz group data files, fetched by `scripts/fetch_te_data.py` |
| Perspective views, one per sheet | A Drawing component built from the generated SVG, with element styles bound to tags | Generated SVGs |
| Alarms on key members | Alarm configuration on UDT members, from engineering limits | TE model ranges |
| Read-only access | Tag security plus a read-only OPC path: monitoring, not control | `AT_YOUR_PLANT.md` §5 |

**Two twins, two purposes:**
- **Tennessee Eastman** is the live demo, with values, alarms and plausibility checks.
- **The extracted OPEN100 twin** shows the extraction-to-Ignition path. Its tags have no live source, so the honest
  expected state is "not connected", and the verifier checks for exactly that.

## The verification system (based on how Ignition itself judges data)

Every check reads the running gateway, not our generated files. That's the difference between "we produced an
import file" and "the gateway holds what we meant".

| # | Check | Ignition principle | Pass condition |
|---|---|---|---|
| V1 | **Import fidelity** | Configuration is what the gateway holds, not what was sent | Export the `Twin` provider's configuration back from the gateway and diff it against what we generated. Every UDT type, instance, member and parameter is present and unchanged. Nothing was silently dropped or renamed |
| V2 | **Reconciliation** | One asset, one tag | Every twin asset and instrument maps to exactly one UDT instance or member, and every instance maps back to a twin item. No orphans either way |
| V3 | **Binding resolution** | A broken binding shows as a quality error on screen | Every tag-bound element in every Perspective view resolves to an existing tag path, and every tagged SVG element has a binding |
| V4 | **Quality honesty** | Tag quality codes (Good / Bad / Uncertain) carry the truth | Simulator-fed TE tags read Good. Placeholder tags (no real data source yet) read a Bad "not connected / not found" quality. **No placeholder tag ever reads Good**: a Good quality on a tag with no source would be a false-good |
| V5 | **Liveness** | A Good value that never changes is stale | Simulator-fed tags' timestamps advance and values change within a few scan periods |
| V6 | **Plausibility** | Engineering limits belong on the tag | Live values stay inside each member's engineering range. Out-of-range values are reported, never clipped |
| V7 | **Read-only enforcement** | Monitoring, not control | Write attempts to twin tags from an external client are rejected. A twin that can write back to the process fails the build |
| V8 | **Alarm pipeline** | Alarms are configured on the tag and proven, not assumed | During the fault-case replay, the configured alarm becomes active. During normal replay it stays clear |
| V9 | **Change record** | Gateway backups and versioned configuration | A gateway backup is taken before each import, the configuration is versioned in git, and every verification run writes a dated receipt (what was checked, pass/fail, counts) |

## Testing the verifier (negative controls)

The verifier is tested the way the scorer was (journal entry 7). Before its results are trusted, it must catch each
of these deliberately planted faults:
1. a UDT member deleted after import (caught by V1);
2. a twin instrument with no tag (V2);
3. a Perspective binding pointing at a misspelled tag path (V3);
4. a placeholder tag forced to read Good from a memory value (V4);
5. a twin tag left writable (V7).

A verifier that passes a broken build is worse than none.

## What this does not prove

- Real plant connectivity. Data addresses for the extracted twin stay placeholders until mapped from a site's I/O
  list.
- Operator usability of the screens. That needs the operator review, deferred by the project owner.
- Production-grade security. Read-only here is the minimum; a site adds its own role model and network zoning
  (`AT_YOUR_PLANT.md` §5).

---

## Results (2026-10-08)

Built on a local Ignition 8.3.10 gateway (trial mode, started from the ZIP in console mode, no Windows service). Every
number below comes from a verification receipt in [`out/ignition/gateway/receipts/`](../out/ignition/gateway/receipts/).

**Verifier: all nine checks pass. The verifier catches all five planted faults, and the gateway is restored after
each one.**

| Check | Result |
|---|---|
| V1 Import fidelity | PASS: 1,204 tag nodes and 13 screens sent; 0 differences, both directions |
| V2 Reconciliation | PASS: 37 of 37 TE items, 910 of 910 extracted twin items, one tag each |
| V3 Binding resolution | PASS: 398 bindings on 13 screens, all resolve; every drawn instrument is bound |
| V4 Quality honesty | PASS: 36 fed tags Good; SC-212 (no data in the replay) Bad; 359 placeholders Bad; 0 false-good |
| V5 Liveness | PASS: 36 of 36 fed tags advanced and changed in 6 s |
| V6 Plausibility | PASS: 36 live values inside the ranges the gateway holds |
| V7 Read-only | PASS: no writable process tag in the config; outside writes refused (BadUserAccessDenied), while the same client's write to a probe tag succeeded |
| V8 Alarm pipeline | PASS: no alarm in normal replay; in fault 6 the reactor pressure alarm went active within a second of the gateway seeing 2,895 kPa crossed (0.5 s and 0.0 s in the two runs) |
| V9 Change record | PASS: backup checksum matches the build record; the gateway config matches a commit; receipt written |

| Fault planted on purpose | Caught by | Caught | Restored |
|---|---|---|---|
| UDT member deleted after import | V1 | yes | yes |
| Twin instrument with no tag | V2 | yes | yes |
| Screen binding to a misspelled tag path | V3 | yes | yes |
| Placeholder tag forced Good with a memory value | V4 | yes | yes |
| Twin tag left writable | V7 | yes | yes |

The first full run failed V9, correctly: the gateway's configuration was not committed yet. That receipt is kept.

**Also verified when loaded by hand.** The twin was deleted from the gateway, then rebuilt through the web UI plus
one tag import, using only the committed files. All nine checks passed again, including V8 (receipt
`20261008T163955Z`). Steps: [IGNITION_QUICKSTART.md](IGNITION_QUICKSTART.md).

Screens: the live overview ([normal](screenshots/ignition-te-normal.png), [fault 6](screenshots/ignition-te-fault6-alarm.png))
and an extracted sheet whose instruments all show Ignition's not-connected overlay
([OPEN100 sheet 0](screenshots/ignition-open100-sheet0-not-connected.png)).

### How it is secured (the minimum, at lab scale)

- **API access:** one API key, HTTPS only, holding a dedicated security level (`TwinBuild`). That level is granted
  gateway read and write, but not Designer access. The gateway's HTTPS certificate comes from a local CA, so scripts
  verify it rather than skipping the check.
- **Data access:** the verifier reads through Ignition's own OPC UA server, which listens on localhost only. It uses
  Basic256Sha256 with SignAndEncrypt and a client certificate that was trusted only after its fingerprint was checked.
- **No write path:** read-only is enforced three times: the replay server, the OPC connection, and every process tag.
  The extracted twin's `ReviewStatus` fields are review workflow, not process data, and stay writable by design
  (910 of them, counted in the V7 receipt).
- **Lab-only deviation:** the replay server itself uses no OPC UA security. A real device connection would use the
  site's certificates.
- **Secrets:** API key, admin password, keys and backups live in a private folder outside the repo.

### Where the build differs from the plan, and why

- **Screens:** the drawing is an image, with a live value label bound over each instrument, instead of SVG
  elements restyled by bindings. It's simpler and works for any generated drawing, and the bindings are still
  exactly what V3 checks.
- **Engineering ranges:** percentages use 0–100. Everything else is ASSUMED: 0 to twice the normal-run mean, labeled
  as assumed in each tag's documentation. No published instrument spans exist for this process. Alarm setpoints come
  only from published sources (2,895 kPa from Downs & Vogel; 3,000 kPa and 175 °C from the simulator code).
- **PressureShutdown (above 3,000 kPa) never activates.** The recorded fault run holds at exactly 3,000.0 when the
  simulator shuts down. Reported, not tuned.
- **Analyzer tags** carry their first component only.

### What the gateway taught us (each one is now a comment in the code)

1. **"Accepted" is not "working".** The API saved an OPC connection missing a settings block (HTTP 200), which then
   failed at runtime, one missing block at a time. The build now copies the gateway's own loopback connection and
   changes only the endpoint and login.
2. **Re-saving a tag provider restarts it.** An import sent in that window fails, so unchanged resources are left
   alone and the import waits for the provider to report healthy.
3. **UDT parameters are not substituted inside string literals.** Concatenate outside the quotes.
4. **Expression tags only re-run when a referenced tag changes.** `isAlarmActive("…")` references none, so by default
   it ran once at startup and would never have turned true in a fault. It now runs every second. On the way there I
   blamed a gateway bug for this ("changing a UDT instance's type breaks it"). A clean reproduction disproved that,
   and the claim was removed.
5. **`isAlarmActive` on a tag with no alarms reads Bad,** so only alarmed instruments carry the member. Wrapping it
   in `try()` would also have hidden a broken path.
6. **Writing a memory tag, even with its current value, changes the configuration.** The verifier's own write test
   made the next fidelity check fail. The test now writes a probe tag in a separate provider. The verifier must not
   change what it verifies.
7. **OPC UA certificate details matter.** A self-signed application certificate needs keyCertSign, or the server
   rejects it as "use not allowed". Strict TLS clients also need key identifiers on the local CA.

### Reproduce

```
python scripts/fetch_te_data.py                                       # the TE runs the replay uses
python scripts/ignition/make_local_ca.py <private-folder>/pki         # then install it on the gateway's HTTPS
python scripts/ignition/build_gateway.py --fresh                      # backup, connection, provider, tags, screens
python scripts/ignition/te_sim_server.py --run normal                 # live values for the screens
python scripts/ignition/ua_client.py                                  # prints the cert fingerprint to trust
python scripts/ignition/verify_gateway.py --controls                  # stop the replay first; plant 5 faults, restore, verify V1-V9
```
Credentials are read from the environment or a private `IGNITION_ENV_FILE` (see `scripts/ignition/gw.py`).
