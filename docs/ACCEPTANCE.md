# Prove one useful investigation and handoff

Use this with the [first-question brief](../examples/first-pilot/pilot-brief.md). It is the test plan for a real
engineer, recipient and company environment. The repository has **not run these acceptance exercises**. Software
tests and illustrative packets are supporting evidence; they cannot fill in participant observations.

Choose only the sections needed for the question. A document clarification can finish without a model, custom
assistant, process-data connection or platform import. Keep company evidence in the approved company location.

## 1. Can another engineer use the packet?

Before the exercise, record one question, intended recipient, permitted source set and versions, scope, time limit,
and what a useful result would let the recipient decide or request. Fix these before seeing the result. Record
the manual comparison method and the site's chosen quality/effort criteria; the toolkit supplies no universal
success threshold.

1. An engineer investigates the question using permitted tools. Retain the original draft, checked citations,
   corrections, unresolved claims, missing evidence and time spent on collection, authoring and review separately.
2. Give the packet and its permitted sources to a second engineer or intended recipient. Ask them to reconstruct
   the answer, find the exact evidence and identify what the packet does **not** establish. Record their actual
   corrections and unanswered requests before showing the author's explanation.
3. Record whether it changed the recipient's next decision or evidence request, with their reason. A readable
   report, agreement between agents or an accepted file upload does not establish usefulness.
4. Compare total effort and residual errors with the declared manual method under comparable scope. If one
   person already knew the answer, or the scopes differ, record that limitation rather than a time saving.

Use the [drawing-review protocol](REVIEW_EFFORT_PROTOCOL.md) for a timed drawing study. For any route, retain:

| Evidence | Record from the actual exercise |
|---|---|
| Question, recipient and intended decision | Exact scope and predeclared success/stop criteria |
| Source and tool versions | IDs, revisions, hashes, locators, configuration and permitted access |
| Effort | Collection, preparation, review, rework and recipient reconstruction time; manual comparison |
| Quality | Incorrect/unsupported/omitted claims, corrected versions, residual disagreements and missing evidence |
| Outcome | Useful / needs changes / insufficient evidence / stopped, recipient's reason and next owner |
| Acceptance | Responsible person, date, scope accepted and remaining exclusions |

Current project status: **not run; human review time and practical benefit unmeasured**.

## 2. Does the receiving company system preserve the packet?

The integration owner first selects an existing receiving system and a permitted test area. Write its declared
mapping before import. The company keeps authority over identity, released revisions, permissions and accepted
decisions; a local reviewer name or `accepted` string is imported provenance, not an organizational approval.

| Content to compare | Required readback observation |
|---|---|
| Asset and signal identity | Exact namespace/IDs; unresolved mappings and aliases remain visible |
| Relationships | Direction and type survive; line membership does not become direct pipe adjacency |
| Evidence | Original source ID/revision/hash, exact locator, scope and uncertainty survive |
| Questions and answers | Full answer/value/units, open requests, conflicts and freshness survive |
| Decisions and responsibility | Local history retained separately from receiving-system approval and authenticated owner |
| Projection losses | Every unsupported field/relationship listed, with the complete source packet retained |

Import one scoped packet, read it back through the receiving interface and compare **content**, not only asset
counts. Retain request/response identities, version and comparison results in the approved location. Repeat the
same import, introduce a changed source, reject one proposal and reconcile one manual edit. Demonstrate that
earlier decisions and the newer accepted version survive retries and an interrupted attempt. Record failures.
An export-only mock can test an adapter's serialization; label it as a mock and leave company acceptance open.

For platform staging, add the target system's actual import diagnostics and read back units, signal mapping,
quality, access and represented alarms. A structural JSON/CSV check cannot substitute for the native system.
Keep operating authorization separate. No PI import, generic plant gateway or installed-configuration acceptance
has been demonstrated here.

Current project status: **not run; receiving-system adapter and authorized native readback required**.

## 3. Can the approved assistant retrieve only permitted evidence?

First use the company-approved manual/Copilot document route. Test an MCP extension only if the company permits
that client, deployment and data path. Use the [connectivity guide](INTERNAL_CONNECTIVITY.md) and the
[local starter](../examples/internal-mcp/README.md) for their distinct boundaries. A local developer client pass
does not establish published Copilot channel support or company authorization.

The company's integration owner runs this in the **actual published client/channel**:

- Two test users with different source permissions: compare search snippets, complete records, attachments and
  follow-up answers. Neither user should gain the service account's broader access.
- A revoked permission and expired session: retained/cached content must follow the site's access policy.
- A revised document and unavailable source: show the version and aged/unavailable state rather than implying
  current evidence. Preserve earlier cited revisions in the company's retained record.
- An ambiguous asset mapping, history gap and oversized request: return explicit limits and unresolved identity.
- A selected snapshot replacement: verify the served fingerprint before and after the explicit reload/restart.

Record expected versus observed behavior, participant roles, client/channel/build, selected snapshot fingerprints
and access/audit evidence. Do not publish confidential payloads. If no cross-zone route or data transfer is
permitted, record **disconnected** and test only approved released snapshots; opening a port or tunnel is not a
completion step in this guide.

Current project status: **local snapshot protocol tests only; company/Copilot/OT acceptance not run**.

## 4. Can the team maintain the next revision?

Keep the first accepted version. Introduce one subsequent source revision and identify dependent answers and
outputs that need review. Preserve conflicting evidence and historical decisions. Have the responsible owner
settle the scope, create a new working model where needed, regenerate to a new draft location and compare it
with the earlier release. Read back the selected new snapshot and check a previously affected answer.

Separate drawing layouts, mappings and authored documents require their own reconciliation. The
[model-review guide](REVIEW_LOOP.md) describes supported corrections; the [context lifecycle](CONTEXT_LIFECYCLE.md)
describes company responsibility. If a generated section was manually edited, retain the edit and require a
reviewed merge. Automatic managed-section replacement and company synchronization are not supplied services.

Finish with a dated decision: continue, change scope, stop or insufficient evidence. Keep failures, owner and
next review trigger with the packet. Report operational benefit only after actual observations and an appropriate
comparison; source completeness or a task-completed flag is not a causal result.
