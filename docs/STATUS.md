# State of the toolkit

Audit date: 2026-10-30. Original functional baseline: `e8277779f7a30f526740a58af9bdb5088555fa4d`.
The evidence-preservation repairs below follow that audit; company integrations remain incomplete.

**This is a collection of working local prototypes and research demonstrations, with a partially connected user
workflow. It is not a turnkey document-to-digital-twin product or a company context service.** The strongest
starting use is one source-backed engineering investigation. Most utilities have real implementations; the
unfinished work is concentrated in evidence preservation, conversion between formats, semantic evaluation and
company integration. There are also reproducible defects, listed first.

The [script registry](SCRIPTS.md) distinguishes 31 scripts classified as tools, 12 repository checks, eleven support modules and
76 research scripts. Research scripts reproduce this project's demonstrations; their presence is not evidence
that the same output is available for arbitrary company inputs. Test scripts are listed separately by the runner.

## Known defects

| Finding | Observed behavior | Current boundary and next repair |
|---|---|---|
| **Vendor report prose overstates what scores establish** | The historical generated report calls review-load counts equivalent work and overlapping run ranges a tie. Neither labor savings nor equivalence follows from those values. | The user guide is corrected. The report generator and historical report still need a separately checked wording repair. Scores and statistical methods have not been changed in this audit. |

The vendor interpretation finding remains open. Correcting that report and validating a bounded investigation
journey take priority over adding outputs or more corpus cases.

**Repaired source-output collisions:** graph export, impact estimation and CSV-band generation now check all
their active input paths and every output before creating directories or writing files. Exact/resolved names,
native case aliases, directory links and existing hardlink identities are checked; aliased sibling outputs also
refuse. Regression tests verify unchanged source and companion bytes. This is a preflight for stable local files,
not a concurrent-writer lock or a transactional guarantee for later I/O failures. See [JOURNAL §105](JOURNAL.md#105-refuse-source-output-collisions-before-publication).

**Repaired source-locator loss:** full and core graphs now retain every supplied item appearance, including
ordered duplicates, empty records and unknown metadata. Claim-specific sources remain separate. Statement
packets expose the recorded appearances and explicit image gaps; context bindings detect changes to later
appearances. Refreshed examples retain earlier decisions and require new evidence-bound proposals or exercises.
The [offline regression packet](../examples/graph-export/multi-appearance/README.md) uses one of seven affected
OPEN100 items. This preserves supplied evidence; it does not verify that a source supports an engineering claim.

## What exists, and what remains manual

Each link opens the tool's examples and test/review evidence. **Reviewed example** means a check of particular
files, not product readiness, source completeness, usefulness or plant acceptance.

| Capability | What runs today | What is incomplete or external |
|---|---|---|
| [Drawing intake](FEATURES.md#drawing-to-bundle) | PNG plus a supplied extraction produces a draft model, review queue and staging. Separate extraction/tracing commands exist. | Approved model interface, extraction recipe choice and engineering review. The simpler site workflow does not reproduce the tiled/traced research method. |
| [Review report](FEATURES.md#client-report) | Generates an HTML view of a supported drawing bundle and its remaining review queue. | Requires the bundle and review decisions; no company delivery/acceptance workflow. |
| [Converted-key DEXPI route](FEATURES.md#dexpi-to-bundle) | Converts the supported adapted DEXPI key/sheet representation. | Bound to that adapter contract; not an arbitrary CAD/XML importer. |
| [Direct DEXPI XML reader](FEATURES.md#dexpi-xml-to-model) | Reads supported XML and reports omissions and unresolved placement. | Coverage varies by exporter. A parsed model may still be ineligible for downstream questions; C03 demonstrates this boundary. |
| [Model drawing/export](FEATURES.md#description-to-model) | Generates outputs from authored process-model JSON; detailed P&IDs use an authored layout. | No automatic description interpretation or detailed layout. Drafting style adaptation is separate work. |
| [Portable graph](FEATURES.md#graph-export) | Exports supported identities, relationships, claims and complete supplied item appearances; line-layer tools distinguish selected connection meanings. | One-way conversion. Source correctness still needs review; no generic inverse into a generator model. |
| [Platform staging](FEATURES.md#platform-exports) | Generates Ignition tags and PI AF staging; offline checks inspect conventions. | Reviewed signal mapping, real import/readback and plant acceptance. PI has never been imported here. The gateway demo builder is TE-specific. |
| [Loop audit](FEATURES.md#loop-audit) | Compares supplied loop records against supported drawings/models. | Loop truth must be supplied; matching an inventory does not verify wiring, settings or installed safeguards. |
| [Vendor evaluation](FEATURES.md#vendor-evaluation) | Scores saved drawing answers with planted controls and per-sheet results. | Limited ontology and graph layer; no review-time study. Report interpretation defects are listed above. |
| [Repository checks](FEATURES.md#repo-checks) | Checks claims, configured freshness, registries and test results. | Repository-specific, not engineering truth. Test exits can contain omissions; inspect the actual coverage summary. |
| [Historian CSV tools](FEATURES.md#historian-csv) | Analyze recorded CSVs; a separate server can replay rows. | Qualified operating baseline, site metadata/mapping and live data access. Replay is not a historian connector or process simulator. |
| [Review and point mapping](FEATURES.md#review-and-mapping) | Applies supported supplied decisions; separate commands stage OPC and PI mappings. | Human identity/source review, native signal checks and explicit regeneration. Valid review rows can persist when another row refuses. |
| [Generalization matrix](FEATURES.md#generalization-matrix) | Runs eight selected workflows on registered public inputs and retains failures. | Does not evaluate every feature or complete journey. New sources need explicit applicability, adapters and independently reviewed truth. |
| [Question engine](FEATURES.md#opportunity-screen) | Screens supported models with catalog rules and emits investigations and evidence requests. | No broad usefulness/coverage benchmark or natural-language answering. The MGPI case produces zero findings. Missing model data does not prove missing plant safeguards. |
| [Impact estimate](FEATURES.md#impact-estimate) | Calculates a draft result from supplied measurements and constants, refusing required omissions. | No measurement collection, causal result or site decision. |
| [Statement review](FEATURES.md#statement-review) | Renders and samples graph claims, scores supplied verdicts and records bound review events. | A person supplies source/plant judgments. A blank review correctly has no error rate. Verdicts do not correct the working model's values. |
| [Context register](FEATURES.md#context-register) | Local files retain supplied answers, disputes and ownership history; explicit refresh checks source revisions. | No automatic source watcher, shared authentication or company acceptance. Answers do not update the generator model. |
| [Snapshot MCP](FEATURES.md#snapshot-mcp) | Read-only access to one selected startup snapshot; SDK/stdio/loopback checks exist. | No live process connector, analysis execution, shared company authentication or verified Copilot tenant. |
| [Description workflow](FEATURES.md#description-workflow) | Prepare → authored answer → check → build joins a draft drawing, questions, graph and staging. | Interpretation and geometry remain authored. Quote/structure checks cannot establish correct engineering interpretation. No unfamiliar-description accuracy result. |
| [Task/model benchmarks](FEATURES.md#task-benchmarks) | Re-scores saved attempts on matching task/source/key/scorer cohorts. | Only drawing extraction and selected native description facts have adapters. The false-shutdown control exposes unscored semantics. No automatic model execution or general model ranking. |

## Demonstrations are a separate track

The [TE/OPEN100 comparison](DELIVERABLES.md) records screens, mimics, replay, tours and isolation mockups.
Those are not additional general-purpose tools hidden behind the input guides:

- The [Ignition project](IGNITION_ACCEPTANCE.md) has dated lab acceptance for particular TE candidates.
  Its build uses the repository's model/configuration; it does not build a new plant from an arbitrary packet.
- The [OPEN100 structural views](OPEN100_STRUCTURAL.md) use project-specific models, keys and inference rules.
- [3D tours](3D_TOUR_PLAN.md) use proposed geometry; the [hazard-citation prototype](HAZARD_CITATIONS_DESIGN.md)
  is keyword matching, not a hazard analysis. Isolation views are not operating procedures.
- Recorded TE/Bayer replay supplies observations from fixed files; equipment commands do not change a physical
  simulation. The Docker backup is a historical package, not the current generic deployment path.

## Company handoff: external responsibilities and missing adapters

The toolkit does not yet demonstrate a general round trip from company records through accepted context,
generation, an executed intervention and a measured outcome. In particular:

1. The source model, portable graph and context register have different contracts and correction paths.
   A graph or reviewed answer cannot regenerate every spoke.
2. Company import/export adapters, authenticated acceptance, concurrent ownership and managed document updates
   remain integration work. Local review records are supplied data, not authenticated approvals.
3. Historian/maintenance connectors and Copilot tenant deployment are unimplemented or unverified. An internal
   MCP server alone cannot cross a prohibited network boundary or supply operational context.
4. No engineer adoption study, timed review, real-plant validation or measured operational benefit has been run.

Keep the company's current systems responsible for their records and execution. The [lifecycle](CONTEXT_LIFECYCLE.md)
describes the intended handoff; [connectivity](INTERNAL_CONNECTIVITY.md) describes approved access options.
Neither document is evidence that those integrations exist. Shared company governance and operational execution
are external responsibilities by design, not a proposed replacement application in this repository.

## Recommended order of work

1. **Correct report interpretation.** Repair the vendor-report prose without changing scores. Retain the
   source-preservation and multi-appearance regression controls.
2. **Finish one bounded investigation journey.** Specify the supported files, human decisions and acceptance
   checks. Measure whether an engineer can complete it and whether the resulting packet helps its recipient.
3. **Evaluate semantics.** Add independent source/claim keys and useful/unacceptable question rubrics before
   increasing generalization claims. Preserve negative controls that a field-only score misses.
4. **Prove one company handoff.** Build and read back a scoped adapter in an approved environment, with source
   permissions and an accountable owner. Add operating data only through an allowed path.

Defer wider synchronization, more visualization formats and extra connectors until the relevant boundary is
demonstrated. A larger corpus and more generated files do not substitute for those steps.

## How this audit was checked

Two independent coding agents inspected the implementations, guides and tests across all twenty catalog
features and ran representative offline CLI chains on public/fictional fixtures. Private disposable copies
preserved before/after bytes for the overwrite defects. The maintainer separately re-scored the saved prediction
tables: 30 reproduce (seven with explicit historical formatting rules), while five report missing-prediction gaps.
The current matrix was checked for freshness; it was not wholly rerun for this audit. Model calls, original-source
downloads, live gateways, plant imports and company systems were not exercised. These checks establish bounded
software observations, not a human engineering sign-off.

For numerical research evidence see [RESULTS.md](RESULTS.md); for runnable paths see [WORKFLOWS.md](WORKFLOWS.md).
