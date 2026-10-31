# Corpus-driven improvement and model/task results

The contribution loop is **new case → reviewed source/key → saved model/method answers → offline scoring →
failure analysis → generalization → baseline regression check**. See [CONTRIBUTING.md](../CONTRIBUTING.md).
The corpus is a growing test bed; results describe particular tasks and methods on particular source families.
There is no universal best-model score.

## Current reproducible tasks

| Task | What is scored | Current evidence | Results |
|---|---|---|---|
| `drawing-extraction`, `pid2graph-v1` | Rough/strict six-class symbol F1 and asset-network F1 using the unchanged scorer | Existing five replicates each for Claude and Codex on six OPEN100 validation drawings. The method includes tiling and deterministic tracing. This is retrospective registration of saved runs; validation also informed method selection. | [Model comparison](results/open100-validation-report-clarified-source-preserved.md), [JSON](results/open100-validation-report-clarified-source-preserved.json), [suite](open100-validation.json) |
| `description-facts`, `native-facts-v1` | Literal selected equipment/type, stream endpoints, instrument/valve placement and controller relations against explicit fact atoms | Two authored synthetic cases with reference, empty and wrong-endpoint controls. Keys come from those same references. **Scorer development only: no AI interpretation benchmark.** | [Scorer controls](results/description-controls-recipe-preserved.md), [JSON](results/description-controls-recipe-preserved.json), [suite](description-controls-recipe-preserved.json) |
| `description-facts`, `native-facts-v1`, source review | The same selected fields against separately prepared original-source keys | [MGPI source-adapted development case](../examples/from-description/mgpi/README.md), with retained unsupported initial adaptation and an explicit source/key expansion. No held-out or original-text model trial. A planted false-shutdown claim still scores perfectly and exposes a scorer blindspot. | [Development artifacts and controls](results/mgpi-development-recipe-preserved.md), [suite](mgpi-development-recipe-preserved.json) |
| `source-support`, `claim-judgments-v1` | Labels for fixed supplied claims against a bounded key; missing claims stay in the accuracy denominator | Twelve MGPI/NIST development claims using explicit project paraphrases. Synthetic scorer controls only; reasons and source validity unscored. | [Control results](results/source-support-development.md), [suite](source-support-development.json) |

The third adapter, `source-support` / `claim-judgments-v1`, grades **fixed supplied claims** as supported,
contradicted or insufficient-evidence. Its [development suite](source-support-development.json) has twelve
claims, six each from MGPI and NIST, balanced four per label. A separate coding agent froze the original-source
key before candidate/scorer work. The public packets are project-authored paraphrases that explicitly scaffold
scope and absence distinctions; they are not original-document comprehension inputs or a blind evaluation.
The [prompt](source-support/prompt.md), [full review key](source-support/review_key.json),
[source inventory](source-support/source_inventory.json) and [projection receipt](source-support/KEY_PROVENANCE.json)
retain dates, locators and multi-source joins. Source hashes are declared metadata; this scorer does not fetch
or revalidate the original files.

[Results](results/source-support-development.md) show synthetic controls only: reference 12/12, empty 0/12,
and each uniform-label control 4/12. These validate scorer behavior, not model capability. Primary accuracy is
correct/expected claims; missing decisions remain in the denominator. Per-label F1 is diagnostic and can differ
from accuracy on incomplete answers. Citation IDs must be admitted and reasons nonempty, but **reason quality
and whether a citation supports a claim are unscored**. Readable partial answers can have status `ok`; that means
scored, not complete or reviewed. This adds no automatic claim discovery, useful-question score, question rule,
current plant truth or human acceptance. Preserve genuine model attempts separately from these controls.

Drawing cases pair a PNG input with a PID2Graph GraphML key; answers use `symbols`/`connections` or the existing
saved prediction envelope. Description cases pair UTF-8 source text, a JSON `facts` key and an expected native
model for the positive control. Submitted answers can be a native process model or the description workflow's
`model`/`layout`/`evidence` wrapper. Keep evaluation keys/reference models out of the inference packet.

The fact task grades identities and the fields in `benchmark.FIELDS`, plus controller output targets. It does not
grade names, narrative equivalence, source support, physical dimensions, operating limits, interlocks, drawing
layout or engineering completeness. A wrong name citing a real source can still pass. Use independent source
inventories, explicit unknowns and the [description evaluation plan](../docs/EVALUATION.md#8-description-to-pid-evaluation-gap)
before claiming interpretation accuracy. Results show fact categories separately and list missing/unexpected
facts: one wrong stream endpoint must not disappear behind a high score on unrelated equipment fields.
The [description workflow](../examples/from-description/README.md)
provides separate structure/quotation/drawing checks; those are not substituted for this task's source truth.

## Extend coverage across the toolkit

| Function family | Existing evidence | Next benchmark contribution |
|---|---|---|
| Drawing reading, tags and topology | Saved predictions, frozen geometry/tag scorers, replicate analysis and corpus matrix | More independent styles, tag truth and model/version runs; add a tag-task adapter using the existing tag scorer |
| Description/model generation and detailed drafting | Assisted workflow fixtures; selected fact-task adapter; TE/Bayer worked examples | Independently keyed unfamiliar descriptions, missing/unsupported facts and separately reviewed rendered layouts |
| Questions and evidence/decision packets | Feature tests, sourced worked examples and independent software reviews | A reviewed question/grounding rubric with source-backed expected and unacceptable claims; keep usefulness separate from format checks |
| Graph/export/CAD/platform preservation | Corpus matrix and native-field regression checks | Semantic fidelity cases for each format, including omissions, unknowns, ownership and source/status preservation |
| Historian analysis and impact estimates | Separate public-data matrix runs and calculation tests | Labelled detection conditions, false alarms, measurement uncertainty and calculation truth; distinguish deterministic methods from AI models |
| MCP, maintenance and other integrations | Bounded protocol/feature tests and selected lab acceptance | Task-specific retrieval/coverage and compatibility tests; no performance claim about an untested company deployment |

These rows identify work to add. Only the three task adapters above are implemented in this runner; every feature
does not yet have a generalization benchmark. New tasks require a tested evaluator contract and known-answer
controls, rather than importing an arbitrary score column into a leaderboard. See the full
[feature inventory](../docs/FEATURES.md) and [eight-workflow matrix](../docs/GENERALIZATION.md).

## Reproduce or extend

```sh
python scripts/benchmark.py --registry benchmarks/registry.json
python scripts/test_benchmark.py
```

No models, subscriptions, downloads or servers are used. Registered files and saved model identities/prompts are
checked before scoring. Changed source/key/prediction fingerprints fail validation; they are not counted as a
model's failure. Python scoring-code fingerprints normalize CRLF to LF, so equivalent Windows/Linux checkouts
share a cohort; actual source edits still change it. Other declared text extensions use the same normalization.
Missing/invalid attempted answers remain scored failures. New unattempted cases remain a visible
coverage gap. Comparisons group by task, scorer-code/contract, exact selected inputs/keys/protocol, family, split
and evidence type; model versions, interfaces and method settings remain separate rows. Five model replicates
on one drawing family do not establish five independent source families or a new held-out experiment.
An answer status of `ok` means it was readable and scored, not that its engineering claims were correct. Inspect
the category scores and missing/unexpected facts; execution failures and semantic mistakes are different findings.

The machine-readable [registry](registry.json) lists the current reproducible snapshots. Their JSON retains exact
counts, failed answers, coverage, dates, model/configuration declarations, recipe hashes and optional reported
resources. Mean F1 pools counts within each replicate, then averages across repeats. Range/SD describe those
repeats; they do not establish statistical significance or a winner. Unknown model builds, cost and timing stay
unknown. For a new method, retain the old answer artifacts and score both on the same baseline before expanding
the corpus. This makes improvements inspectable and keeps failures useful to the next contributor.

## Report implementation revisions

The registry selects new offline scores of the three earlier suites after the source-preservation and
fixed-claim adapter edits. Counts, metrics, controls, source/key/prediction/recipe bindings and model declarations
are unchanged. Implementation fingerprints and cohort/group identities change because the evaluator changed;
these are not new model trials or performance improvements.

All eight earlier JSON/Markdown files remain byte-identical historical snapshots, including the earlier
vendor-interpretation revision. They are outside the current registry and do not byte-reproduce under the
changed implementation. The source-preserved report pairs are actual re-scores, not hand-rehashed receipts.
Retain previous reports and register a new prefix whenever the implementation changes.

The current description-control and MGPI suites separately preserve their historical recipes after the live
description guide and workflow gained interpretation-review sheets. The exact guide and code bytes from
commit `bdf1b41` are retained as [recipe text](recipes/description-workflow-20261030.txt) and
[code text](recipes/description-workflow-20261030.py.txt), with the original pinned content hashes. These are
historical sources, not the current guide or executable workflow. New `*-recipe-preserved` manifests relocate
those recipe references and explain the provenance; their original run IDs, dates, predictions, model declarations,
case inputs and keys remain unchanged. The registry selects actual offline re-scores under new report prefixes.
Counts, controls, metrics and scoring cohorts are unchanged; recipe paths change submission/group identities
and may reorder the summary. This is no new model attempt, method improvement or interpretation result.

The original suites, run manifests and report pairs remain unchanged. Their references to the former live
guide/code require the corresponding historical checkout; use the current registry for reproducible checks
against the archived recipes. Keeping an old result does not authorize rewriting its original recipe or date.
