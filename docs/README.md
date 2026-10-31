# Documentation map

Start with the [project overview](../README.md). This page routes you to instructions, reference or evidence;
you do not need to read the research record to try a first investigation.

For an implementation audit, start with [the state of the toolkit](STATUS.md): working parts, open defects,
manual bridges and the recommended order of work. Numerical research evidence lives separately in RESULTS.

## Follow one path

1. **Frame a question.** Use the [first-question brief](../examples/first-pilot/README.md), including the
   company-approved Copilot/manual route without a local installation.
2. **Choose the starting records.** The [README selector](../README.md#start-wherever-you-are) links the input guides.
   [Follow one pump](../examples/from-description/assisted/PUMP_WALKTHROUGH.md) to see an actual illustrative bundle.
3. **Check the claims and missing evidence.** Use the selected guide's review steps. If you have a supported
   model, the [question engine](OPPORTUNITY_SCREEN.md) can suggest investigations; it does not perform a process audit.
4. **Hand off one finding.** Keep the sources, qualifications and next owner together in the brief.
   [Company pilot guidance](AT_YOUR_PLANT.md) explains how to evaluate practical value and access at your site.

## Continue a task

| Task | Guide |
|---|---|
| Correct a draft model and assign supplied signal addresses | [Model review](REVIEW_LOOP.md) · [PI mapping](PI_MAPPING.md) |
| Calculate impact from an actual measured change | [Impact estimate](IMPACT_ESTIMATE.md) |
| Prepare a portable graph or inspect sourced statements | [Graph format](GRAPH_EXPORT.md) · [Statement review](STATEMENT_REVIEW.md) |
| Retain answers and source-revision dependencies in a local packet | [Context register](CONTEXT_REGISTER.md) |
| Follow a revised source through questions, review history and snapshot readback | [Worked revision example](../examples/pump-revision/README.md) |
| Keep department scopes and cross-team dependencies explicit | [Four owned packets](../examples/team-context/README.md) |
| Retrieve a selected snapshot through an approved local MCP client | [MCP starter](../examples/internal-mcp/README.md) |
| Plan team ownership, published dependencies and company access | [Lifecycle](CONTEXT_LIFECYCLE.md) · [Connectivity](INTERNAL_CONNECTIVITY.md) |
| Choose an implementation for separated IT/OT, no-port plants or approved hybrid access | [Environment choices and tradeoffs](INTERNAL_CONNECTIVITY.md#choose-the-data-path-before-the-assistant) |
| Test a real recipient, company handoff and next revision | [Acceptance exercise](ACCEPTANCE.md) |

These tasks are optional branches, not prerequisites for every investigation. A plain source-question brief may
be enough. Exact file contracts belong in the [workflow map](WORKFLOWS.md); all tools are in [FEATURES.md](FEATURES.md).

## Reference and research records

| Read this when… | Canonical reference |
|---|---|
| You need to know which formats and steps actually connect | [Supported workflows and formats](WORKFLOWS.md) |
| You need one script's role and guide | [Script reference](SCRIPTS.md), generated from the script registry |
| You need a tool's example files, tests and review status | [Feature reference](FEATURES.md), generated from the feature/review registries |
| You need research results and their limitations | [Results](RESULTS.md), checked against committed evidence |
| You need to distinguish three types of testing | [Workflow generalization](GENERALIZATION.md) · [Saved task/model comparisons](../benchmarks/README.md) · [Example reviews](FEATURES.md) |
| You want to reproduce or challenge a published result | [Reviewer checks](REVIEWING.md) · [Advanced reproduction](REPLICATE_AT_YOUR_PLANT.md) · [Predictions](../predictions/README.md) |
| You need the source/confidence lineage of the demonstrations | [Data lineage](DATA_LINEAGE.md) · [Demo deliverables](DELIVERABLES.md) |

**Historical research:** [PLAN.md](PLAN.md) is the dated original plan; [GOAL.md](GOAL.md) retains experiment
protocols and later acceptance notes; [JOURNAL.md](JOURNAL.md) is chronological development history;
[TRIED.md](TRIED.md) is the generated attempt ledger. These are records, not the current user journey.
Use [CONTRIBUTING.md](../CONTRIBUTING.md) before adding a case or changing a method.

**Demonstrations:** [OPEN100 structure](OPEN100_STRUCTURAL.md), [Bayer reconstruction](BAYER_RT.md),
[MGPI source clarification](../examples/from-description/mgpi/README.md), [operator screens](OPERATOR_SCREENS.md)
and [Ignition acceptance](IGNITION_ACCEPTANCE.md) explain scoped examples. For Ignition setup use the
[manual quickstart](IGNITION_QUICKSTART.md) or [build reference](IGNITION_BUILD.md).
The [Docker package](../docker/README.md) restores a historical demo. None is a generic plant deployment.

## Where files live

| Location | Role |
|---|---|
| `examples/` | Runnable guides and public/example packets. Each guide declares the role of its data. |
| `scripts/`, `data/` | Implementation, registries and source/model fixtures; see the script reference before reusing research code. |
| `out/`, `predictions/`, `benchmarks/` | Published outputs, saved model answers and offline comparisons. Keep historical evidence intact. |
| `pipeline/` | Dependencies/freshness for the configured research demonstrations; not company orchestration. |
| `drafts/` | Prototype visualizations and tours. |
| `docs/` | Guides, reference, evidence and research history, distinguished above. |

Attribution and licensing are in [NOTICE.md](../NOTICE.md). Model-assisted authorship is in [MODELS.md](MODELS.md).
