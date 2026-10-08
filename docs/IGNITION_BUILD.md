# Ignition build and verification plan (written before the build)

Committed before any Ignition configuration exists. The checks below are the acceptance test. The build is done when
they pass, and when the verifier has itself been shown to catch deliberately broken configurations.

## What gets built

| Piece | Ignition concept | Source |
|---|---|---|
| A dedicated tag provider, `Twin` | Realtime tag provider. It keeps twin tags separate from any production provider, the same separation a site uses between environments | This repo |
| UDT definitions per equipment and instrument type | UDTs with parameters (`BasePath`, `OPCServer`) and members carrying engineering units, ranges and documentation | `generate.py` / `build_twin.py` |
| UDT instances, one per asset | UDT instances, foldered by system/sheet | The twin's asset hierarchy |
| Live values for the TE plant | An OPC UA device (simulator) replaying the open Tennessee Eastman simulation data (normal operation plus a fault case) | `teprob` data files (Braatz group, open license) |
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
