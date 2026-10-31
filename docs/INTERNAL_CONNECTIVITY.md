# Connect a first packet to company systems

An engineer should be able to ask one useful question across drawings, procedures, asset records and operating
history, then return an evidence-backed finding to the people responsible for the decision. Start with the
company-approved Microsoft 365 Copilot experience and approved document locations. A company-operated Model
Context Protocol (MCP) server is a later, optional access layer. The company still needs a system that retains
source authority, ownership, decisions and history as people and projects change.

This page is an integration sequence, checked against the primary specifications linked below. The optional
[snapshot MCP starter](../examples/internal-mcp/README.md) is runnable over local stdio or loopback Streamable
HTTP and tested with public data. Company deployment, shared authentication, receiving-system adapters and
process-data connections remain proposed integration work.

## Default path: Copilot within a strict company boundary

The assumed reader has a work Copilot account, limited installation rights and sensitive manufacturing data.
This path does not require a coding agent, Python on the reader's computer, a personal AI subscription or a custom
server. A designated engineer or IT team can run the toolkit separately in an approved environment and publish
cleared, readable results alongside the source documents. Preserve JSON and CSV for later integrations; do not
assume Copilot indexes the full graph or executes this repository's scripts.

Some drawing-extraction commands call commercial model services through their CLIs. Running a script locally
does not make that extraction local-only, and those commands are not a Copilot integration. Start with the
committed example extraction or synthetic records. Company drawings require a separately approved intake route
and processing endpoint; do not run the example subscription-based extraction on them by default.

First establish which work experience is enabled. Microsoft distinguishes Copilot Chat from Copilot grounded in
organizational content; a Chat license alone does not promise tenant-wide document retrieval. Where company
policy permits, use explicitly selected source files; otherwise work with synthetic examples until the approved
source-access route exists. See [Microsoft's current privacy and grounding description](https://learn.microsoft.com/en-us/copilot/privacy-and-protections).

| Path | What the reader can do | What the company must supply |
|---|---|---|
| **Approved Copilot Chat, no custom agent** | Investigate a question using a small, explicitly selected set of permitted documents and a copied question brief. Open and check each cited source. | An approved work account, permitted content-handling method and an existing place to save the reviewed result. File inclusion depends on the enabled experience and policy. |
| **Approved SharePoint agent or organizational grounding** | Reuse a selected engineering knowledge collection without assembling the same files for every question. | Required licensing or approved billing, agent availability, correct source permissions and a content owner. [SharePoint agents respect the user's source access](https://learn.microsoft.com/en-us/sharepoint/manage-access-agents-in-sharepoint); broad existing permissions still need review. |
| **Copilot Studio with approved connectors or MCP** | Retrieve bounded asset, history or event data as part of an investigation. | An approved environment, connector and data policies, authentication, network reachability, ownership and an operational support plan. This is an IT-backed extension, not a capability every Copilot user already has. |

Keep the first collection small: a current drawing, relevant procedure, reviewed asset/tag crosswalk and a question
brief. Record the source ID, revision, effective date, owner and original location; mark missing metadata as unknown.
Keep obsolete material identifiable if the investigation needs it, and make the governing revision explicit.
Return a draft finding with source locations and unresolved questions to the existing engineering review process.

A starting prompt for cleared examples or company-approved sources is:

> Investigate [one engineering question] using only the selected sources. For each factual statement, identify
> the document, revision and page, section or table supporting it. Separate reported observations, inferences,
> conflicting records and missing evidence. Do not invent operating limits or resolve a revision conflict by
> guessing. Produce a draft finding, the evidence still needed and the person or role needed to review it.

This prompt helps organize a review; it does not enforce permissions or guarantee accurate citations. Check the
sources manually. If the available Copilot experience cannot retrieve them reliably, use a manual evidence brief
instead of treating the answer as grounded.

For food and beverage, start with a bounded utility or equipment question using synthetic or explicitly cleared
records. Recipes, formulations, supplier information, production records and plant layouts may need different
access scopes. Decide permitted content with the company's data owner before including it. Retain original
quality and production records in their controlled systems. AI drafts must not silently revise a sanitation
procedure, validated process limit, food-safety decision or product-release record; route proposed changes through
the existing engineering and quality approval process. This guide does not establish regulatory compliance.

Have the administrator check sensitivity labels, retention, audit settings, permitted model processing locations,
web grounding and connector data flows for the chosen experience. Microsoft documents enterprise protections,
but those commitments do not replace a company's content restrictions. In particular, generated web queries have
a separate data flow; for a closed-corpus investigation, use a company-approved configuration with web grounding
disabled. In Copilot Studio, [data policies](https://learn.microsoft.com/en-us/microsoft-copilot-studio/admin-data-loss-prevention)
can classify or block connectors. Do not move data to a personal account, tunnel or alternate connector to evade
a policy block. No company content or tenant has been accessed to write this guide.

## Give each interface a job

| Interface | Job | Current position here |
|---|---|---|
| JSON, CSV and the [typed graph](GRAPH_EXPORT.md) | Carry exact engineering records, identifiers, relationships, evidence and unresolved states between tools. | Existing exports. Import into a company system still needs a checked adapter. |
| [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md) | Carry linked, readable knowledge as Markdown with structured metadata. Retain the exact engineering JSON alongside it. | Candidate additional export; not implemented. Google has announced OKF import/export for Knowledge Catalog context sets in its [October 22, 2026 preview announcement](https://cloud.google.com/blog/products/data-analytics/knowledge-catalog-self-learning-context-enrichment-for-ai-agents). No Google import has been tested here. |
| [MCP resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources) and bounded tools | Retrieve records from a selected snapshot through an approved assistant client. | The [local read-only starter](../examples/internal-mcp/README.md) ships. It does not run analyses or fetch live process data; shared authentication, Copilot deployment and live connectors remain integration work. |
| Historian APIs and OPC UA | Retrieve operating observations and their metadata through site-approved interfaces. OPC UA also defines [historical access](https://reference.opcfoundation.org/specs/OPC-10000-11/4); a particular server's supported services must be checked. | CSV analysis and recorded-data replay exist. Replay is not an authenticated connection to a live plant historian. |
| The company's context and decision system | Retain accepted context, decisions, accountable owners, source revisions and access rules. | Company responsibility; no shared governance application is supplied here. |

OKF and MCP complement each other: one packages knowledge, the other provides access. Neither establishes that
an engineering claim is correct. An OKF export must preserve draft and unresolved states; it must not turn a
generated answer or an unverified reviewer name into a human verification event. Untyped document links also
cannot replace the graph's distinction between direct pipe adjacency and membership of a line network.

## Start with one area and one question

For example: **Why has this pump's energy use increased after maintenance?** This is an illustrative question,
not a diagnosis from this repository's data.

1. Retrieve the relevant drawing and operating procedure with their revisions and source locations. If two
   revisions conflict, show the conflict and identify who can settle which governs.
2. Resolve the pump's company asset ID and the reviewed signal mappings for power, flow, pressure and running
   state. A similar tag name is not enough to establish identity.
3. Retrieve a bounded history window and maintenance events. Check units, scaling, timestamps, time zone,
   quality flags, gaps and operating mode before comparing like conditions. A recorded event occurring first
   does not establish that it caused the change.
4. Use a suitable analysis or the [question engine](OPPORTUNITY_SCREEN.md) to identify missing evidence and possible
   explanations. The question engine screens a supplied model using a catalog; it does not already query
   company systems or diagnose arbitrary natural-language questions.
5. Return the finding, exact source references, calculation inputs, uncertainty and requested next decision to
   the company system. Keep a draft distinct from an accepted decision. The responsible people decide what
   happens next in their existing work systems.

The first success criterion is another authorized engineer reconstructing the finding from those references.
Then measure whether it helped settle the question and how much effort it took. Connecting more data sources
alone does not demonstrate value.

## Connectivity to share next

These are recommended targets in order, not connectors already shipped. Use an export before building a live
integration when it can answer the pilot question.

| Target | Small first connection | What it makes possible | Existing starting point / remaining work |
|---|---|---|---|
| Document repository, such as SharePoint or an existing engineering document system | Retrieve approved documents and revision metadata for one area, with durable source links. | Answers cite the applicable records; a revised source can identify findings needing review. | [First question and pilot](../examples/first-pilot/README.md). Repository authentication, permissions, revision retrieval and change handling need implementation. |
| Asset register and signal dictionary | A reviewed CSV joining company asset IDs to document identifiers and historian points. | Drawings, questions and observations refer to the same asset. | [Review and mapping](../examples/review-and-mapping/README.md). Address assignment does not verify signal identity, units or scaling. |
| Historian or reporting API | A limited CSV export, then a read-only query for specified points and time bounds. | Test a question against observed behavior and quantify a baseline. | [Historian CSV tools](../examples/historian-csv/README.md). A live adapter must preserve quality, time semantics and data gaps; current CSV tools do not establish those metadata contracts. |
| Maintenance and event records | A dated export of work orders, downtime or alarm events for the same assets. | Compare behavior before and after an intervention and identify competing explanations. | New adapter needed. Preserve event identity, actual versus planned times, status and source links. |
| Company context and decision system | Retrieve a released packet; submit a new finding through the system's existing review process. | Retain why the team acted, who accepted it, and which new evidence reopens it. | [Context lifecycle](CONTEXT_LIFECYCLE.md). This receiving-system round trip is still unimplemented and untested. |

Further CAD formats, streaming subscriptions and new sensor feeds should follow a demonstrated question they
help answer. Direct control writes, arbitrary database queries and generic remote command execution are outside
this first integration. Process data adds observations; identity, interpretation and accountable decisions are
what tie those observations to engineering work.

## What an internal MCP setup would expose

### Let the operations network boundary determine the data path

The internal MCP service is the intended integration direction. It must fit the site's approved architecture:
"read-only" describes allowed operations, not permission to open a connection into the operations network.
Start by identifying where the approved historian, replica or export actually lives and who controls that zone.
Do not place an assistant-facing service on a controller or assume corporate credentials permit OT access.

| Site boundary | Feasible first path | Consequence for Copilot |
|---|---|---|
| **No permitted network connection across IT/OT** | Use an existing, approved export and controlled transfer process if data release is allowed. If no data may leave, keep analysis within OT using approved existing tools. | Cloud Copilot cannot query an isolated OT MCP service. Work only on explicitly released snapshots outside OT, or defer that connection. No new port, tunnel or reverse connection is assumed. |
| **An approved one-way replication path already exists** | Read a released historian replica or snapshot on the permitted receiving side. Preserve the original source, acquisition interval, quality and last-successful-transfer time. | MCP can serve the receiving copy if the client is authorized to access it. Requests do not travel back through the one-way path. A new historian query cannot conjure observations that were never replicated. |
| **A reviewed cross-zone service path is permitted** | The OT owner defines the collector's host, read-only historian identity, exact endpoints, allowed operations, query limits and boundary controls. Serve an approved IT/DMZ copy where possible. | An authenticated MCP service can expose the permitted copy or brokered results through the approved route. Network approval and published-client testing are prerequisites. |

For example, an approved path could be **OT historian → existing controlled replication/export → released
IT-side data copy → internal MCP → approved assistant client**. This is a proposed topology, not a deployed
connector. An OT-side collector or local MCP service can stay inside the approved OT zone; its presence does not
create a route for cloud Copilot. If there is no permitted route or transfer, that part of the workflow stays
disconnected.

Follow the site's security design and [NIST's OT security guidance](https://csrc.nist.gov/pubs/sp/800/82/r3/final).
NIST distinguishes a [unidirectional gateway](https://csrc.nist.gov/glossary/term/unidirectional_gateway) from a
bidirectional connection. A software flag called read-only is not a data diode. An outbound-only relay can still
receive commands in its responses; it is not a workaround for a prohibition on cross-boundary communication.
This guide prescribes no firewall port or change to a site's network configuration.

Every returned history result should identify its event-time window, retrieval time and latest available source
sample, plus gaps, quality and replication delay. A disconnected or failed transfer returns unavailable or
explicitly aged snapshot data; never label the last successful copy as live. Keep control writes, historian
configuration changes and arbitrary queries outside this proposed read-only service.

### Connect the approved client

For the Copilot route, use Copilot Studio only after the company approves the extension. Microsoft currently
documents [connecting an existing MCP server](https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-add-existing-server-to-agent)
through its onboarding wizard or a custom connector, using Streamable transport with authentication options.
A local stdio server is not a drop-in endpoint for that route. Establish approved network reachability before
promising an internal-only service will work with a cloud-hosted client; do not expose it through a public tunnel
as a workaround. Verify tools, resource handling and end-user authorization in the actual published Copilot
channel, not only a developer test client. No such end-to-end Copilot test has been performed here.

An IT developer can first run the [snapshot starter](../examples/internal-mcp/README.md) over the public example
or a cleared graph packet with the pinned MCP SDK and a test client. It exposes nine bounded tools for snapshot
identity, asset/stream search and readback, typed relations, existing questions, and complete answer/ownership
history from an explicitly selected, hash-bound context sidecar, plus a summary resource. It reads the
selected files once; sources are returned as references and are not fetched. Graph-only use explicitly reports
that complete context is unavailable. A new source revision needs a preserved-register refresh, explicit review
and [snapshot restart/readback](CONTEXT_LIFECYCLE.md#maintain-one-local-packet-between-reviews). Its local transport tests are
separate from the default Copilot-only reader path and a company shared deployment.

Future source-document and process-data connectors could add `search_sources`, `get_source` and
`get_history_window`; those operations are not implemented. They should return source identity, revision or
content fingerprint, retrieval time, evidence location and unresolved mappings with each result. Keep history
queries bounded by approved points, dates and result size. Do not offer arbitrary SQL, filesystem paths or
user-supplied fetch URLs as a shortcut to these operations.

For a shared service, the company chooses a host, service owner and approved assistant clients. A central MCP
endpoint can route to several existing systems; it need not copy them all into one database. Follow the MCP
[HTTP authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
and [security guidance](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices).
Authenticate the caller and enforce the caller's authorized source scope for search snippets, full documents,
attachments and history queries. A broadly privileged service account must not silently broaden each user's
access. Include permission changes and cache invalidation in the test plan. A read-only tool annotation describes
intent; the server and upstream systems must enforce it.

Test with two users who have different source permissions, a revoked permission, an expired session, a revised
document, an ambiguous asset mapping and a history gap. Keep retrieved document text as evidence, not instructions
that grant access or trigger writes. Record access and source versions without unnecessarily logging confidential
payloads. An internal server does not by itself keep model processing inside the company: check where each
assistant client sends retrieved content and apply the company's approved data policy.

Only after retrieval is useful should an integration submit draft findings into an existing review queue. A
separate, authorized workflow must accept decisions and execute changes. This keeps the toolkit focused on
starting a coherent engineering investigation while the company system maintains its continuing record.
