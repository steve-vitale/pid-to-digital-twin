# PID2Graph Synthetic sheets 2 and 3: prospective results

On 2026-10-11, a two-sheet synthetic transfer trial required **73 published-label corrections across 158 key items: 46.20 per 100**. Missing connections dominated. This measures agreement with a published answer key, not verified engineering accuracy or an operationally approved twin.

## Method and evidence boundary

The selected model was `gpt-6.1-sol`, using the original `extraction/prompt.md`, one whole image per fresh native session, without tiling or tracing. The method and scoring policy were fixed before inference. Both first outputs were retained before label acquisition, and scoring ran once. No answer repair, retry, substitution or post-label tuning was recorded. Reasoning was unverified/inherited; isolation was procedural. Model selection and timing are orchestration records, not independently authenticated provider telemetry.

Approximate observed session durations were 103 and 111 seconds, not inference-only latency. Execution used an existing subscription with no separately invoked paid API; token/compute cost was unmetered and unknown. Both sheets are now consumed evaluation data, so a changed method needs different prospectively reserved data.

The public checkout includes the summary below, but **does not include the local sealed raw outputs, acquisition evidence, trial protocol/configuration, or trial-specific harness**. Historical hashes in the summary identify local evidence; they are not public download links or proof of availability. This publication cannot reproduce the exact sealed trial or independently establish its acquisition chronology. Do not treat a new inference run as a reproduction of those first outputs.

## Primary counts

| Measure | Sheet 2 | Sheet 3 | Micro aggregate |
|---|---:|---:|---:|
| Key symbols | 23 | 26 | 49 |
| Key collapsed links | 74 | 35 | 109 |
| False symbols | 0 | 0 | 0 |
| Missed symbols | 1 | 1 | 2 |
| Source-class relabels | 5 | 12 | 17 |
| False links | 0 | 3 | 3 |
| Missed links | 43 | 8 | 51 |
| Total corrections / key items | 49 / 97 | 24 / 61 | **73 / 158** |
| Corrections per 100 key items | 50.5 | 39.3 | **46.20** |

Aggregate review load is computed from summed counts, not an average of the two sheet percentages. These are corrections to match the published key under the frozen scoring rules, not counts of independently verified engineering mistakes or actual reviewer actions.

## Secondary metrics

| Measure | Precision | Recall | F1 |
|---|---:|---:|---:|
| Rough location, IoU >=0.1 | 1.000 | 0.959 | 0.979 |
| Rough location + source class | 0.638 | 0.612 | 0.625 |
| Strict location, IoU >=0.5 | 0.915 | 0.878 | 0.896 |
| Strict location + source class | 0.617 | 0.592 | 0.604 |
| Collapsed undirected connections | 0.951 | 0.532 | 0.682 |

The model located 47 of 49 key symbols, with 30 rough source-class matches. It produced 61 links: 58 matched 109 key links. Sheet 2 recovered 31/74 links with no false links; sheet 3 recovered 27/35 with three false links. Missing links dominate this label-based review-load proxy; interpreting them as physical process errors still requires engineering review of the source/scorer's graph semantics.

Full per-sheet, per-class and strict/rough results are in [the machine-readable summary](../out/pid2graph_reserved23_summary.json). Source key classes total 10 tank, 2 pump, 3 valve and 34 general. There are **no instrumentation or off-page positive examples**, so zeros for those class metrics do not establish recall performance. All three source valves were either missed or assigned a different source class; the five model valve predictions matched source `general` items. This is an unresolved source/model classification discrepancy, not an automatic determination of physical component identity.

## Interpretation and limits

Seventeen source/model class disagreements remain unchanged; fourteen involve the source's broad `general` class. No domain adjudication or answer-key remapping was performed. An ontology disagreement is not automatically a physical engineering error.

The source graphs contain 234 solid and 51 non-solid edges. The scorer collapses them into 109 undirected asset links and discards style. Style is not assumed to identify process versus signal. Tag text, units, direction, ownership, operating envelopes, live mapping and actual human review minutes were not measured.

The full source archive checksum was not verified; image/label entry integrity checks were reported locally. Historical regression results were 15/15 source-only scripts, 19/19 cached-data scripts and 18/18 separate trial-specific tests. The last group is not included in this public checkout. These are recorded offline checks, not current public-CI or native gateway/PI acceptance.

Two artificial drawings sharing one ontology cannot establish reliability on real plants, saved human effort, or operational readiness. Public pretraining exposure cannot be excluded. No OPEN100 confidence calibration or operational export was applied in this trial.

Source: [PID2Graph, Zenodo record 14803338](https://zenodo.org/records/14803338), by Jan Marius Stürmer, Marius Graumann and Tobias Koch. Synthetic symbols: copyright 2023 Steven Baltakatei Sandoval. Dataset-derived material retains [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) attribution; repository code remains MIT.
