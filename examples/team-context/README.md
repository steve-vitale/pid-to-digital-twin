# Keep context owned as teams join

Four fictional investigations show how Process, E&I, Maintenance and a separate site can exchange a bounded
source revision while keeping their own evidence and responsibility. Native P-1 is local in each packet. A supplied
teaching map explicitly relates the three Site A references and keeps Site B separate. It is not an identity resolver.

The Process note changes its draft pressure basis from `200 kPa` to `220 kPa`. Controls must revisit the answer
that cites it; an independently sourced loop answer stays current in this source-only example. Neither version
establishes an installed setting or authorizes a plant change.

Read the [worked change review](worked/CHANGE-REVIEW.md), then the [receiving brief](worked/HANDOFF.md).
The packet retains exact original notes, authored graphs/questions, source versions, selected snapshots, disputes
and full decision/owner histories. Every person, mapping review, source and decision here is invented. Local
source acceptance grants no company authority; no real recipient or operating plant has accepted the result.

## Use approved Copilot or manual review without an installation

1. Copy the [first-question brief](../first-pilot/README.md#first-investigate-the-existing-sources) for each owned
   scope. Give each brief one question, its source owner, responsible reviewer and intended use. Use only sources
   your company permits Copilot to process; the same brief works with manual source review.
2. Record controlled source IDs, revisions, exact page/section references and their approved locations. Identify
   which other brief relies on a published source. A matching equipment tag alone does not establish identity.
3. Agree who checks for the next source revision, who sends it to dependent reviewers, and where they record
   receipt and review disposition. Use the table below in the company's existing controlled record.
4. Exchange the brief and permitted source references through the approved company location. Keep the earlier
   version and unresolved claims; ask the receiving owner to acknowledge what arrived and what needs review.
   If an approved technical owner later creates a tool packet, they add/check its required raw-byte hashes.

Copy this manual dependency row for each transfer; fill the roles and cadence before relying on it:

| Publisher and source | Dependent scope and reviewer | Approved record location | Next check and sender | Receipt and disposition |
|---|---|---|---|---|
| Source owner; document ID/revision | Receiving scope; responsible role | Controlled reference | Named person; publication event or review cadence | Received revision/date; awaiting review, rejected or reviewed with reason |

For this fictional example, the Process owner checks for a later basis publication and sends its released
reference to the E&I owner. The E&I owner records receipt, revisits the dependent basis answer and records the
review outcome. Maintenance keeps its own source owner and review trigger. These are responsibilities to agree
in the company process, not notifications implemented by the toolkit. Local source acceptance is not company release.

## Reproduce the local software exercise

On Windows, use a short clone path such as `C:\work\pid-twin`. Default Git rejected the nested worked
paths in a deeply nested review folder; the same files checked out successfully under a shorter path.

From the repository root, produce a fresh result with Python 3.10+ (standard library):

```sh
python examples/team-context/reproduce.py --out out/team-context
```

Open `out/team-context/worked/CHANGE-REVIEW.md`. The full private run folder also records commands, prepared
fingerprints, filled sheets, refusal controls and checks. Use a new output directory; earlier runs stay intact.
The script respects caller TEMP/TMP and uses the operating system defaults when they are absent.

| Part | Contribution |
|---|---|
| Process publication | Supplies revision A then B as exact bytes; its old source answer becomes stale after explicit refresh. |
| E&I investigation | Explicitly receives that publication beside its own loop note; only its basis answer stales in this source-only fixture. A fresh partial B answer leaves configuration unresolved. |
| Maintenance and Site B | Actually refresh unchanged independent records; their complete histories and selected outputs stay exact. This is declared software dependency behavior, not proof that a real Process change cannot affect them. |
| Two proposed pressures | Distinct attributed answers cite the same unresolved source/base and units. Both input orders stay disputed with no accepted winner. This compares literal strings, not engineering unit semantics or simultaneous writers. |
| Composition and handoff | Shows supplied identities, responsible roles, exact graph/context/source pins and the next owner action; it does not merge graphs or release company records. |
| Selected snapshot MCP | Reads two packets independently, retaining complete questions, sources, owners and paginated decisions. Cross-pair refusal checks integrity, not company namespace or access permission. |

All graph snapshots and questions are visibly authored fixtures. No catalog finding or model extraction is
invented. The selected graphs, asset content, relationships and questions remain unchanged across this source-only
revision; a physical/configuration change could legitimately reopen more answers. Whole-document pins are not
field-level impact analysis. Keep original bytes and unresolved scope with any projection.

For actual optional local stdio readback, use an approved existing environment with the pinned dependencies
in `requirements-mcp.txt`, then continue the same completed result:

```sh
python examples/team-context/reproduce.py --out out/team-context --sdk-only
```

Two selected packets are served independently; no network port opens. The service does not fetch original sources,
observe the plant, authenticate company users, search across packets or synchronize them. Manual/Copilot review
and approved disconnected packet transfer remain usable. Source pins and selected worked bytes use local Git
attributes; a fresh regeneration records its own actual hashes.

The worked observations are a tiny fictional workload on one Windows environment: packet/source byte sizes,
command wall times and dependency fanout. They do not establish throughput, large-company capacity, labor saving,
concurrent editing, company approval or Linux/macOS execution. Company stale-base checks, authenticated releases,
revocation, retry/recovery and actual human acceptance remain external work.

See the [context register guide](../../docs/CONTEXT_REGISTER.md), [organizational lifecycle](../../docs/CONTEXT_LIFECYCLE.md)
and [internal connectivity boundaries](../../docs/INTERNAL_CONNECTIVITY.md).
