# From starting documents to a first context packet

A model can give an engineer useful questions. This workflow keeps the answers, responsibility and evidence
beside those questions, then reopens affected answers when a supporting source changes. It works locally with
standard-library Python. The starting model and source documents stay unchanged.

Use these examples to start the process on one problem. When the company needs to retain and coordinate this
knowledge across people and projects, take the packet into a shared organizational system. The
[next step after a pilot](../first-pilot/README.md#after-the-first-packet) describes what that home needs to retain.

There are five examples:

- **[Illustrative, offline](illustrative/README.md):** three small invented documents, four questions and a filled
  answer sheet. It shows an unresolved conflict, a fictional dated review, missing data and an unanswered walkdown.
  No downloads, accounts or subscriptions are needed.
- **[Public PRONTO packet](pronto/README.md):** 22 proposed statements and 21 questions link a technical report,
  alarm settings, an operation log and an event journal from the same experimental facility. It uses pinned public
  originals, with disagreements and disabled-alarm caveats retained. Fetching those originals is explicit.
- **[Question-engine bridge](bayer/README.md):** the real E18 screen joins to a proposed partial answer from a
  public operating narrative. Its original collection prompts, decision rule and limits remain visible; the
  historical source does not settle actual duty overlap or savings.
- **[NIST manufacturing testbed](nist-smstestbed/README.md):** two original device configurations publish the same
  machine UUID while reusing a signal ID for different meanings across revisions. The associated Hurco04 archive
  log does not identify its deployed configuration. The packet keeps the meanings revision-scoped and deployment
  unresolved. This source family is examined as development evidence rather than a held-out score.
  Start with its [plain configuration question](nist-smstestbed/first-question.md) before the optional register setup.
- **[MetroPT-3 maintenance evidence](metropt3/README.md):** reported failures, maintenance notes and the actual
  released measurement CSV stay distinct. The packet preserves duplicate event numbers, a date ambiguity,
  acquisition/release scope differences and a column-order trap, with explicit requests for execution records
  and comparable observations. It extends context coverage on an existing historian family; no successful
  repair, root cause, current asset identity or new anomaly result is inferred.

For a first document question, the [plain brief](../first-pilot/README.md) is enough; no model or register is needed.
If you choose the optional local register route, start with a draft model/graph and question list from the existing
tools. Keep stable asset
identities, register the supporting document revisions and exact locations, assign owners, and fill the answer CSV.
A second independently sourced answer stays separate. The tool compares only explicitly named claim slots and
canonical values; an engineer decides whether documents disagree and which one governs.

While preparing the local packet, explicitly refresh the register when a source or model changes. Read the
questions that need an owner, more data or a new review. Keep the JSON sidecar with the source pack so the next
engineer inherits the reasons and earlier decisions. Once teams depend on that context, the shared company system
should retain the ongoing record; use the specialist tools against its released snapshots and return findings for
review. The [full guide](../../docs/CONTEXT_REGISTER.md) gives the commands,
schema, review requirements, conservative document-level staleness, exact-reversion behavior and export limits.

The portable output can be transferred to another engineering or change-management system through an explicit
adapter. No hosted connector, live sync, authenticated approval or plant verification is supplied by this example.
The [context lifecycle](../../docs/CONTEXT_LIFECYCLE.md) describes how a central organizational authority could
release snapshots for generation and receive proposed changes back for review. Local acceptance fields stay
provenance on transfer; they do not grant organizational authority.
