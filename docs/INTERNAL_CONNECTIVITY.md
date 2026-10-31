# Choose a company IT/OT path

An engineer should be able to ask one useful question across drawings, procedures, asset records and operating
history, then return an evidence-backed finding to the people responsible for the decision. Start with the
company-approved Microsoft 365 Copilot experience and approved document locations. A company-operated Model
Context Protocol (MCP) server is a later, optional access layer. The company still needs a system that retains
source authority, ownership, decisions and history as people and projects change.

This guide starts from **approved work Copilot, strict data policies and separate IT/OT systems**. That is a
design assumption, not a measured claim about how many companies use Copilot. Choose a path for each site and
data class; a company can use several paths at once. More connectivity is useful only when it answers a question
that the simpler path cannot.

The recommendations below are engineering choices informed by the primary sources linked here, not a surveyed
ranking of deployment prevalence. Product documentation was checked on **October 31, 2026**. The optional
[snapshot MCP starter](../examples/internal-mcp/README.md) is runnable over local stdio or loopback Streamable
HTTP and tested with public data. Company deployment, shared authentication, receiving-system adapters and
process-data connections remain proposed integration work.

For a first pilot, choose a row in each of the next two tables, then follow
[one question](#start-with-one-area-and-one-question). Service builders can continue to the
[MCP implementation reference](#mcp-implementation-reference-for-itot).

## Choose the data path before the assistant

First ask the source owner and IT/OT team: **May this content leave its current zone? May an approved cloud
service process it? Which transfer or service route already exists? How fresh must the evidence be?** Include
drawings, tag dictionaries, recipes and derived findings in that decision, not just raw historian samples.
On-premises storage and a private network route do not imply local model processing.

| Operational environment | First path to follow | Advantages | Costs and limits |
|---|---|---|---|
| **IT documents are approved for work Copilot; OT remains separate** | Start with selected, cleared drawing/procedure copies and the [question brief](../examples/first-pilot/README.md). Request operating evidence from its OT owner only when needed. | No new OT connection or custom agent. Useful document reconciliation and evidence requests can start immediately. | Cannot test operating behavior without observations. File selection, citations and revisions need human checking; cloud permission is required for the actual content. |
| **No cross-zone network ports; controlled exports are permitted** | OT owner exports a bounded time window through the site's existing approved transfer process. Review the released copy in the permitted IT or analysis environment. | Works without a live network bridge. Fixed inputs are easy to preserve and reconstruct. | Release review and transfer take effort; evidence ages between exports. New points or windows require another request. Approved media handling and import controls still apply. |
| **An approved one-way replication path exists** | Query only the historian replica or released snapshots on the receiving side. Add Copilot or MCP there only if processing and access policies allow it. | Repeated investigations can reuse observations without an assistant request crossing back into OT. | Replication has cost, delay and a fixed scope. Missing signals cannot be fetched on demand through the one-way link. A replica still contains sensitive operational information. |
| **A managed DMZ or hybrid service route is approved** | Prefer a released reporting copy. If that is insufficient, IT/OT can design a bounded, authenticated broker through the approved zones to the required source. | Can support fresher, repeatable queries and existing enterprise tools without manual exports for each question. | Greatest integration/support burden here: identities, per-user access, query load, availability and boundary monitoring. Query traffic can affect a source even when writes are prohibited. |
| **Operating data already reaches an approved cloud analytics platform** | Reuse its sanctioned reporting API or bounded export with reviewed asset mappings; retain the existing OT publishing boundary. | Avoids a second plant collector and can reuse managed identity, history and support. | Confirm that approval includes the chosen assistant, content and processing region. Provider limits, cost and availability apply; cloud data can still be delayed or incomplete. |
| **Cloud processing is prohibited, or restricted data cannot leave OT** | Keep review inside the authorized IT or OT zone with existing approved tools. Use offline scripts on staged files only if installation is allowed; an approved local model/client is optional. Otherwise use the manual brief. | Preserves the required boundary; document and evidence discipline still works without AI. | Cloud Copilot cannot examine this content. Local inference needs approved hardware, models and support; its extraction quality has not been measured here. Sharing restricted findings needs separate clearance. |

**Recommended starting point for the assumed reader:** the first row for documents, plus the second row if an
operating-data question justifies a permitted export. An isolated plant can stay on that path indefinitely.
If no transfer is permitted, choose the last row for that plant's restricted material; public examples can
still teach the workflow outside it. An existing flat or loosely separated network is a reason for IT/OT to
assess boundaries, not evidence that connecting an assistant directly to control systems is appropriate.

These choices follow the segmentation and controlled-flow principles in
[NIST SP 800-82 Rev. 3, sections 5.2.3.1 and 5.4](https://doi.org/10.6028/NIST.SP.800-82r3).
Rev. 3 is the final publication used here; [NIST lists Rev. 4 as a public draft](https://csrc.nist.gov/pubs/sp/800/82/r3/final).
The table is a proposed decision guide, not a site security design or a tested plant deployment.

## Match the client to that path

Network access and assistant choice are separate decisions. Any receiving copy may still be barred from cloud
processing. Conversely, cleared IT documents can be used with approved cloud Copilot while OT stays disconnected.

### Default: approved Copilot and released documents

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

| Client / implementation | Benefit | Requirements and tradeoffs | Toolkit status |
|---|---|---|---|
| **Approved Copilot Chat, no custom agent** | One engineer can investigate selected permitted documents using a copied brief. | Approved work account and content-handling method. Repeated file assembly and citation checks are manual; file inclusion depends on the enabled experience. | Manual brief ships; no Copilot integration or tenant test. |
| **SharePoint agent or organizational grounding** | A team can reuse an owned collection rather than assemble files each time. | Required licensing or billing, enabled agent and correct source permissions. Cloud processing must be permitted; indexing and retrieval need checking. Broad source access remains broad access. | Company configuration; no deployed agent supplied. |
| **Company-managed Copilot connector to an incumbent system** | Reuse an existing document or business system without replacing it. | Synced connectors index content in Microsoft Graph; federated connectors retrieve through MCP at query time. Choose based on permitted copying, freshness and availability; both need access controls and cloud-processing approval. | Microsoft platform options; no connector supplied or tested here. |
| **Approved local client with stdio MCP** | A developer can retrieve structured records from one selected packet without a listening network port. | Approved Python/SDK/client and cleared files. Check where the client sends results for inference. This is one local process, not a company access service. | [Snapshot starter](../examples/internal-mcp/README.md) ships and has public-data SDK tests. |
| **Copilot Studio with company connectors or authenticated MCP** | Repeated, bounded lookups can join approved context and observations across existing systems. | IT-owned service, authentication, source-scoped authorization, approved network route, data policies, licensing/capacity and support. Higher setup and continuing operating cost. | Reference integration direction; adapters, shared service and published-client acceptance remain company work. |
| **Manual review or approved offline analysis** | Restricted teams can use the same evidence/decision discipline without cloud processing. | Existing approved tools and human reviewers; any installation needs approval. More manual work; local models have a separate unmeasured quality/capacity requirement. | Brief and documented offline script routes exist; no local inference package supplied. |

[SharePoint agents respect each user's source access](https://learn.microsoft.com/en-us/sharepoint/manage-access-agents-in-sharepoint).
Giving access to an agent does not grant access to every referenced document. Check both the collection's
permissions and which revision governs; retrieval alone does not settle conflicting records.

Microsoft's [connector comparison](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/overview-copilot-connector)
distinguishes indexed search from query-time retrieval. Indexing adds a maintained copy and refresh/permission
synchronization work; federation depends on source availability and query performance. **No Graph indexing does
not mean no content reaches cloud inference or interaction records.** For a custom federated connector, IT must
follow [its own authentication, network and rollout requirements](https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/set-up-custom-Federated-connectors).
Do not transfer assumptions between a connector, a Studio agent and a local MCP client.

Keep the first collection small: a current drawing, relevant procedure, reviewed asset/tag crosswalk and a question
brief. Record the source ID, revision, effective date, owner and original location; mark missing metadata as unknown.
Keep obsolete material identifiable if the investigation needs it, and make the governing revision explicit.
Return a draft finding with source locations and unresolved questions to the existing engineering review process.

Use the [copyable first-question brief](../examples/first-pilot/README.md) to separate source observations,
inferences, conflicts and missing evidence. Check every citation manually; prompts do not enforce access or
guarantee source accuracy. If retrieval is unreliable, use the manual brief.

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

1. Identify governing drawing/procedure revisions and who can settle conflicts.
2. Verify the company asset ID and signal mappings for power, flow, pressure and running state; matching names
   alone do not establish identity.
3. Obtain the permitted history window and maintenance events through the chosen data path. Check units,
   scaling, time zone, quality, gaps and operating mode. Sequence alone does not establish causation.
4. Analyze the evidence and missing inputs. The [question engine](OPPORTUNITY_SCREEN.md) screens a supplied model
   using a catalog; it does not retrieve company data or diagnose arbitrary natural-language questions.
5. Return a draft finding with exact references, calculation inputs, uncertainty and next owner to the existing
   company review process. Record the eventual decision and outcome there.

The first success criterion is another authorized engineer reconstructing the finding from those references.
Then measure whether it helped settle the question and how much effort it took. Connecting more data sources
alone does not demonstrate value.

## Connectivity to share next

These are recommended targets in order, not connectors already shipped. Use an export before building a live
integration when it can answer the pilot question.

1. **Document repository:** retrieve one area's approved records with revisions and durable links. The
   [first-pilot brief](../examples/first-pilot/README.md) works manually; authentication, revision retrieval and
   change handling need adapters.
2. **Asset register and signal dictionary:** use a reviewed CSV joining asset IDs, drawing IDs and historian
   points. [Review and mapping tools](../examples/review-and-mapping/README.md) help; address assignment alone
   does not verify identity, units or scaling.
3. **Historian/reporting data:** start with a limited export to the [CSV tools](../examples/historian-csv/README.md).
   A live adapter must preserve time semantics, quality and gaps; those contracts are not established by the CSV tools.
4. **Maintenance/events:** add dated work-order, downtime or alarm exports for the same assets. A new adapter
   must preserve actual/planned times, status, event identity and source links.
5. **Context and decision system:** return draft findings to existing review and read back accepted records.
   The [lifecycle](CONTEXT_LIFECYCLE.md) defines the intended handoff; this receiving-system round trip is untested
   and unimplemented.

Further CAD formats, streaming subscriptions and new sensor feeds should follow a demonstrated question they
help answer. Direct control writes, arbitrary database queries and generic remote command execution are outside
this first integration. Process data adds observations; identity, interpretation and accountable decisions are
what tie those observations to engineering work.

## Scale ownership across teams and sites

Use one owned area or discipline packet as the publication unit. Each team retains its source records and
publishes an approved revision plus explicit dependencies; consumers pin the revisions they actually used.
A utility team, E&I team and quality team need not share all their files or use the same data path.
For example, one site can supply a cleared CSV, another an approved historian replica, and a third only a
released engineering finding. Missing access remains missing evidence; a central assistant must not bypass it.

| Responsibility | Company operating pattern | Benefit / cost |
|---|---|---|
| Area or discipline publisher | Own IDs, source scope, governing revisions and a named review/backup owner. Publish a bounded packet to an approved location. | Teams work independently; they must maintain cross-team mappings and dependencies. |
| Shared IT access layer, if needed | Route authorized requests to permitted published scopes or existing systems; enforce access before returning snippets or full results. | One client setup can serve many teams; service operations, permission changes, caching and capacity become company responsibilities. |
| Cross-team consumer | Record consumed revision, unanswered dependencies and a receipt showing another authorized engineer reconstructed the finding. Request refresh when cited evidence changes. | Avoids silent overwrites and preserves disagreement; selective refresh still needs coordination. |
| Existing document, maintenance and decision systems | Retain canonical records, accepted decisions, work execution and outcome evidence. Return durable IDs/status to the investigation. | Incumbents can remain in place; checked adapters or manual handoffs are still required. |

See the [four owned packets](../examples/team-context/README.md) and
[context lifecycle](CONTEXT_LIFECYCLE.md). The local register has no concurrent-write protection; do not put
every department into one shared writable JSON file. The MCP starter serves one selected packet, has no company
authentication and does not route user permissions across team scopes. Its limits are **32 MiB per graph/context
input and 2 MiB per serialized result**. They are bounds, not proof of large-team capacity. Moving it to a VM
or container does not supply authorization, high availability, release management or live refresh.

## MCP implementation reference for IT/OT

### Fit the service to the chosen boundary

The source owner and IT/OT team approve which zone may host a collector or service. Read-only access is not permission to
connect to OT. Do not place an assistant-facing service on a controller or assume corporate credentials permit OT access.

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

For a company-approved hybrid route, Microsoft documents
[Virtual Network support for specific Copilot Studio calls and supported connectors](https://learn.microsoft.com/en-us/microsoft-copilot-studio/admin-network-isolation-vnet)
and [on-premises data gateways for supported services](https://learn.microsoft.com/en-us/data-integration/gateway/service-gateway-onprem).
These are options for IT to evaluate, not interchangeable bridges or an assertion that this MCP starter works
through either. Confirm the exact connector, environment, region, identity flow and published channel.
A gateway can receive cloud requests over an outbound-initiated connection. **No inbound ports is not no
cross-boundary communication**, and neither private routing nor a gateway moves cloud model processing on site.
Where all cross-zone connections are prohibited, use the permitted export/local path instead.

Every returned history result should identify its event-time window, retrieval time and latest available source
sample, plus gaps, quality and replication delay. A disconnected or failed transfer returns unavailable or
explicitly aged snapshot data; never label the last successful copy as live. Keep control writes, historian
configuration changes and arbitrary queries outside this proposed read-only service.

### Connect the approved client

For a Copilot Studio route, proceed only after the company approves the extension. Microsoft currently
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
