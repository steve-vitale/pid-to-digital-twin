# State of the toolkit

Audit refreshed: **2026-10-30, Central time**. Code baseline: `3d93c5f8eec9602f6cfe90f06cd3a33dd964a26d`
(committed at 20:19 Central). The earlier functional audit began at `e8277779f7a30f526740a58af9bdb5088555fa4d`;
its repairs remain recorded below. This refresh reports additional failures, rather than treating those repairs
as completion of the toolkit.

**Substantial working local software, with an incomplete engineering investigation and maintenance workflow.**
The strongest starting use is one source-backed question and a reviewable evidence packet. This is not yet a
turnkey document-to-digital-twin product or a company context service. Most unfinished work is at the joints:
engineering meaning, corrections between formats, current evidence, company handoff and human acceptance.

The [script registry](SCRIPTS.md) classifies 131 scripts: **31 tools, 12 checks, 12 support modules and 76 research
scripts**, with tests listed separately. Twenty feature groups have **reviewed example outputs**; that label
does not certify the current implementation or every input. The registry binds example-output hashes, rather
than implementation/test hashes. The [workflow map](WORKFLOWS.md) gives the actual format contracts.

## Known defects

These remain **open after the N072 follow-up**. The reproductions use disposable fictional/public inputs;
no production records were changed. Priorities describe impact within this starter toolkit, not plant risk.

| Priority / tracking | Reproduced behavior | Consequence and completion criterion |
|---|---|---|
| **P1 — N073: catalog fields can falsely settle a larger collection task** | E1 drops pump-curve and motor-efficiency requests after CAPACITY/DISCHARGE/HP/RPM. E2 labels generic rated CAPACITY/DISCHARGE as best-efficiency-point evidence and removes curve collection. E4 drops its efficiency/nameplate request with HP alone although its decision formula needs efficiency. All commands exit successfully. | Review the full collection task against its encoded fields. Keep scalar candidates distinct from curves, efficiency and operating evidence; do not use these screens to declare collection complete. N071 repaired E5/H3 only. Audit the remaining catalog with negative controls before claiming adequate coverage. |
| **P2 — N074: matrix freshness misses ordinary input/key changes** | Changing OPEN100 `0.graphml` bytes in a private copy still lets `corpus_matrix.py --check` pass. Of 95 cells, 83 bind code only; 12 additionally bind agent-made keys. | Bind each cell to the sources, keys and configuration it actually consumed, then test changed/removed inputs. Current metrics are not thereby shown wrong; the present check establishes recorded code freshness, not complete input freshness. |
| **P2 — N075: rejection freshness policy is incomplete** | An accepted illustrative context answer remains `answered/current` after its supplied graph asset and attribute statuses change to `rejected`. `context_register.py` excludes record-level status from evidence fingerprints. | Define which rejection/status transitions invalidate a dependency and which are bookkeeping. Test that distinction without making every review event invalidate every answer. This observation does not establish that a historical source answer becomes false when an asset is rejected. |
| **P2 — N076: context-to-MCP readback is partial** | Enriched graph questions carry answer IDs/freshness and a `context.json` pointer; answer text, canonical values and decision/source verdicts remain in that sidecar. The snapshot server never loads it. Context's virtual `stream:S1` identity is also unavailable through node-only MCP asset/filter lookups, though its question can be read by question ID. | Document or implement one bounded, evidence-preserving readback contract, including stream identities. A served enriched graph alone does not expose the complete investigation answer packet. No shared governance service is needed to demonstrate this local boundary. |

**Repaired after the audit — N072/N077:** supplied alarm metadata survives review; native instrument/final-
element corrections migrate supported live references with auditable paths. Unknown alarm basis stays unresolved.
Frozen sheet targets and input/collision refusals prevent ambiguous retargeting. Earlier dated records stay intact,
including on replay. The [fictional native correction](../examples/review-and-mapping/native-identity/README.md)
and [review guide](REVIEW_LOOP.md) explain the bounded behavior and explicit companion reconciliation. Twenty
CLI-based regressions and 71 independent actual CLI invocations cover preservation and consumers; no engineering,
plant, company or human-usefulness acceptance is inferred. See [JOURNAL §114](JOURNAL.md#114-preserve-evidence-and-references-through-model-review).

The relevant implementations are [model review](../scripts/apply_review.py), the
[question catalog](../data/questions.json) and [resolver](../scripts/question_engine.py),
[matrix freshness](../scripts/corpus_matrix.py), [context binding/output](../scripts/context_register.py) and
[snapshot retrieval](../scripts/serve_snapshot.py). [JOURNAL §113](JOURNAL.md#113-refresh-the-whole-toolkit-audit-with-failing-handoffs)
records the observations. The [attempt ledger](TRIED.md) records open and completed follow-ups.

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
| [Vendor evaluation](FEATURES.md#vendor-evaluation) | Scores saved drawing answers with planted controls and per-sheet results. | Limited ontology and graph layer; no review-time study or between-vendor comparison test. |
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
| [Task/model benchmarks](FEATURES.md#task-benchmarks) | Re-scores saved attempts on matching task/source/key/scorer cohorts. | Three adapters: drawing extraction, selected native description facts, and fixed-claim labels. Claim-label results are synthetic controls on explicit paraphrases; reasons and source validity remain unscored. No automatic model execution or general model ranking. |

## Demonstrations are a separate track

The [TE/OPEN100 comparison](DELIVERABLES.md) records screens, mimics, recorded replay, tours and isolation mockups.
The Ignition lab builder is TE-specific; PI staging has never been imported into a PI System here. OPEN100 views
use project-specific models, keys and inferences. 3D geometry is proposed; keyword hazard matching is not hazard
analysis, and isolation views are not operating procedures. Replay does not make equipment commands drive a
physical process simulation. The Docker backup is a historical package, not the current generic deployment path.

## Company handoff: external responsibilities and missing adapters

The toolkit does not demonstrate a general round trip from company records through accepted context, generation,
an executed intervention and a measured outcome. These boundaries are already documented and remain unfinished:

- **Description interpretation:** an engineer or approved assistant authors the model and detailed layout.
  Quote/structure checks can accept a wrong interpretation; selected-field scores do not catch every false claim.
- **Useful questions:** the catalog screens supported patterns; it does not answer arbitrary questions or perform
  a process audit. The source-authored MGPI model produces zero findings despite a useful source clarification.
  N065 remains open. Fixed-claim label controls do not evaluate free-form reasoning or question usefulness.
- **Maintenance:** graph export is one-way; statement/context answers do not correct generator facts. Regeneration,
  source refresh and snapshot restart require explicit work. Schedule replacement and conflicting facts/schedules
  are unresolved. The 52-stage pipeline covers configured research demonstrations, not every toolkit output.
- **Company integration:** source repositories, historian/maintenance systems, accepted imports/readback,
  authenticated ownership and managed document updates need scoped adapters and company acceptance (N063).
  These company responsibilities are intentionally external; the repository should not become a replacement
  governance or execution application.
- **Approved access:** MCP serves one startup snapshot, without source fetching, live process data or per-user
  company authorization. No Copilot tenant/channel has been accepted here. A cloud client cannot reach an isolated
  OT server without an allowed path. OKF is a proposed additional export, not implemented.
- **Practical value:** no engineer adoption trial, timed review, operator acceptance, real-plant validation or
  measured operational benefit has been run (N062). A readable agent walkthrough is a different kind of evidence.

The [lifecycle](CONTEXT_LIFECYCLE.md) describes the intended company handoff;
[connectivity](INTERNAL_CONNECTIVITY.md) describes approved access options. Neither proves those integrations exist.

## Recommended order of work

1. **Repair the remaining collection defects (N073) and retain the N072 preservation controls.** Keep failing cases, show
   before/after behavior, and check related paths rather than closing the issue on one passing example.
2. **Close the bounded maintenance contracts.** Bind matrix inputs; define rejection freshness and context/MCP
   readback. Keep original sources, prior decisions and unresolved states intact.
3. **Validate one investigation with an engineer and recipient.** Fix the question, permitted sources, output and
   acceptance criteria first; record omissions, corrections, effort and whether the packet helped its recipient.
4. **Expand source-backed evaluation and corpus coverage.** Use independently reviewed expected/unacceptable
   questions and claims, with unfamiliar sources reserved before tuning. Preserve wrong-reason and field-only
   controls. Add failures and source families, rather than increasing file counts or a global pass percentage.
5. **Prove one authorized company handoff.** Import and read back one scoped packet; process a source change.
   Add operating data through an approved route only when the investigation needs it.

Defer extra connectors, visualization formats and broader synchronization until their needed boundary is shown.
The useful public description today is: **a toolkit for turning engineering records into a sourced investigation
packet and draft model/graph outputs, with optional local read-only retrieval.** It prepares context for future
manufacturing applications; it does not establish a complete digital twin, process audit or maintained company system.

## How this audit was checked

At the code baseline above, fresh offline checks confirm: 41 matching registered numerical claims plus one
prose-only claim; current feature/attempt/script registries; 52/52 configured pipeline stages fresh; all four
registered benchmark suites reproduce. Saved-prediction rescoring reproduces 30 tables (seven with explicit
historical formatting rules), retaining five missing-prediction gaps. The unchanged matrix records **64 pass,
23 fail and 8 n/a**; this refresh checks its code bindings and does not rerun all 95 cells. Six passes duplicate
key-only OPEN100 checks and add no scan evidence. These are not whole-toolkit completion percentages.

Three fresh independent coding agents reviewed entry paths, implementation contracts and evaluation. Actual
offline CLI probes retained before/after files and failure logs for the defects above. The reader checked 285
local link paths across 22 guides, with none missing; anchors were not checked. Prior output reviews remain
bounded to their recorded examples. Fresh checks do not erase the new failing probes.

The audit-refresh local cached-data suite reported **63/63 scripts passed, five unittest cases skipped, two explanatory
platform notices and zero additional skipped-check notices**. Notices are not extra skipped cases. The run
establishes the exercised regressions, not complete coverage or a repair of the audit failures. MCP runtime was
not rerun for this audit; its existing SDK/stdio/loopback evidence is separate.

The N072 follow-up rerun passes **64/64 scripts**, with five unittest skips, two explanatory platform
notices and no additional skipped-check notices. Its first 63/64 example-test ownership failure is
retained in the journal. This repair adds no matrix/model-performance or human-acceptance result.

Model calls, original-source downloads, company systems, plant imports and live gateways were not exercised.
These are software and agent-reader observations, not human engineering sign-off. For numerical research
evidence see [RESULTS.md](RESULTS.md); for runnable paths see [WORKFLOWS.md](WORKFLOWS.md).

## Earlier repairs and their scope

<details>
<summary>Preservation and collection repairs preceding this refresh</summary>

**Question-request completeness (N070):** repaired field accounting keeps each triggering subject's bundle
separate, including entirely unknown siblings. Explicit unit-scoped requests use only the finding's owning
equipment. Field coverage survives readable screens, graph/context handoff and per-site roll-up; empty schedule
strings count as blanks. The [two-supply control](../examples/opportunity-screen/field-coverage/README.md) shows
the failure this fixes. It establishes software accounting, without validating supplied values or useful questions.

**Repaired collection contracts (N071):** E5 now separates curves, rating/drive basis and actual input/load
history; H3 separates stated rating from actual hours/load and heat-source compatibility. Supplied scalars,
references and flags remain unverified candidates, with their qualifiers and exact locators retained through
handoff. They cannot remove those collection/review tasks. See the [fan/heater control](../examples/opportunity-screen/collection-basis/README.md).
This fixes two known false-completion cases, without certifying the whole catalog, document suitability or
engineer usefulness. Schedule replacement, conflicting facts/schedules and case-variant keys remain unresolved.

**Repaired additional output writers (N069):** actual copied-input probes first reproduced collisions in the
report, loop-audit and line-enrichment commands, then eleven more tools. The fourteen repaired writers now
preflight their consumed source files, generated/retired targets and companion aliases before writing. Tests
and independent CLI probes preserve source/companion bytes for direct paths, hardlinks and directory aliases.
Intentional review/mapping/model-in-place updates remain explicit. Review-kit generation refuses to reset
review/timer history; the pipeline can explicitly refresh an untouched blank kit. Ordinary outputs retain their
prior content; newly generated drawing manifests record the changed generator fingerprint. See
[JOURNAL §109](JOURNAL.md#109-preserve-sources-across-the-remaining-output-writers).

These are bounded checks on stable local files, not a transactional publication system or a concurrent-writer
lock. The sweep does not make every research script safe for arbitrary inputs. The external-extraction skip
message was also repaired; no model extraction was executed.

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

**Repaired report interpretation:** the vendor renderer now distinguishes counted differences from labor,
intervals for a mean from a future-run prediction, and observed-sample resampling from unfamiliar-drawing
performance. Overlapping ranges do not establish a tie; strict box overlap does not establish drawing readiness.
The saved JSON and all numeric rows remain unchanged, with the original Markdown retained. An actual benchmark
re-score records the changed implementation/cohort identities in a new report; earlier reports remain intact.
See the [report revision](../examples/vendor-evaluation/README.md#report-interpretation-revision).

</details>
