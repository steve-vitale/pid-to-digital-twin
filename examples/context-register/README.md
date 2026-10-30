# From starting documents to maintained engineering context

A model can give an engineer useful questions. This workflow keeps the answers, responsibility and evidence
beside those questions, then reopens affected answers when a supporting source changes. It works locally with
standard-library Python. The starting model and source documents stay unchanged.

There are four examples:

- **[Illustrative, offline](illustrative/README.md):** three small invented documents, four questions and a filled
  answer sheet. It shows an unresolved conflict, a fictional dated review, missing data and an unanswered walkdown.
  No downloads, accounts or subscriptions are needed.
- **[Public PRONTO packet](pronto/README.md):** 22 proposed statements and 21 questions link a technical report,
  alarm settings, an operation log and an event journal from the same experimental facility. It uses pinned public
  originals, with disagreements and disabled-alarm caveats retained. Fetching those originals is explicit.
- **[Question-engine bridge](bayer/README.md):** the real E18 screen joins to a proposed partial answer from a
  public operating narrative. Its original collection prompts, decision rule and limits remain visible; the
  historical source does not settle actual duty overlap or savings.
- **[NIST manufacturing testbed](nist-smstestbed/README.md):** two original device configurations and an archived
  operating log share a machine UUID while reusing a signal ID for different meanings across revisions. The packet
  keeps the meanings revision-scoped and the deployed configuration unknown. This is a new public source family
  for the context workflow, examined as development evidence rather than a held-out score.

For your own work, start with a draft model/graph and question list from the existing tools. Keep stable asset
identities, register the supporting document revisions and exact locations, assign owners, and fill the answer CSV.
A second independently sourced answer stays separate. The tool compares only explicitly named claim slots and
canonical values; an engineer decides whether documents disagree and which one governs.

At each document release or engineering change, rerun the register against the current files. Read the questions
that need an owner, more data or a new review. Keep the JSON sidecar with the source pack so the next engineer
inherits the reasons and earlier decisions. The [full guide](../../docs/CONTEXT_REGISTER.md) gives the commands,
schema, review requirements, conservative document-level staleness, exact-reversion behavior and export limits.

The portable output can be transferred to another engineering or change-management system through an explicit
adapter. No hosted connector, live sync, authenticated approval or plant verification is supplied by this example.
The [context lifecycle](../../docs/CONTEXT_LIFECYCLE.md) describes how a central organizational authority could
release snapshots for generation and receive proposed changes back for review. Local acceptance fields stay
provenance on transfer; they do not grant organizational authority.
