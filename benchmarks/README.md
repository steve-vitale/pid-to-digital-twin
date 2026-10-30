# Corpus-driven improvement and model/task results

The contribution loop is **new case → reviewed source/key → saved model/method answers → offline scoring →
failure analysis → generalization → baseline regression check**. See [CONTRIBUTING.md](../CONTRIBUTING.md).
The corpus is a growing test bed; results describe particular tasks and methods on particular source families.
There is no universal best-model score.

## Current reproducible tasks

| Task | What is scored | Current evidence | Results |
|---|---|---|---|
| `drawing-extraction`, `pid2graph-v1` | Rough/strict six-class symbol F1 and asset-network F1 using the unchanged scorer | Existing five replicates each for Claude and Codex on six OPEN100 validation drawings. The method includes tiling and deterministic tracing. This is retrospective registration of saved runs; validation also informed method selection. | [Model comparison](results/open100-validation.md), [JSON](results/open100-validation.json), [suite](open100-validation.json) |
| `description-facts`, `native-facts-v1` | Literal selected equipment/type, stream endpoints, instrument/valve placement and controller relations against explicit fact atoms | Two authored synthetic cases with reference, empty and wrong-endpoint controls. Keys come from those same references. **Scorer development only: no AI interpretation benchmark.** | [Scorer controls](results/description-controls.md), [JSON](results/description-controls.json), [suite](description-controls.json) |

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

These rows identify work to add. Only the two task adapters above are implemented in this runner; every feature
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
model's failure. Missing/invalid attempted answers remain scored failures. New unattempted cases remain a visible
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
