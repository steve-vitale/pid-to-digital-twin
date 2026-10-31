# Task results: open100-r5-validation

Task: `drawing-extraction`. Retrospective registration on2026-10-30 of the existing round5 runs. This is not a new preregistered, held-out or model-execution experiment.

Only rows with the same cohort are directly comparable. See JSON for exact cases, failures, fingerprints and configurations.

| Model / version | Method / interface | Family / split / evidence | Cohort | Cases | Replicates | Metric | Mean F1 | Min–max | SD |
|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5[1m] / provider build not recorded beyond the saved model identifier | 2x2 tiled model extraction + deterministic trace replacement / claude CLI | pid2graph-open100 / validation / historical same-plant validation also used for method selection; third-party keys | 9ad9efbd1de5 | 6 | 5 | symbols_rough | 0.8984 | 0.8939–0.9040 | 0.0049 |
| claude-opus-5-5[1m] / provider build not recorded beyond the saved model identifier | 2x2 tiled model extraction + deterministic trace replacement / claude CLI | pid2graph-open100 / validation / historical same-plant validation also used for method selection; third-party keys | 9ad9efbd1de5 | 6 | 5 | symbols_strict | 0.8316 | 0.8247–0.8522 | 0.0117 |
| claude-opus-5-5[1m] / provider build not recorded beyond the saved model identifier | 2x2 tiled model extraction + deterministic trace replacement / claude CLI | pid2graph-open100 / validation / historical same-plant validation also used for method selection; third-party keys | 9ad9efbd1de5 | 6 | 5 | networks | 0.7950 | 0.7807–0.8124 | 0.0129 |
| gpt-6.1-sol / provider build not recorded beyond the saved model identifier | 2x2 tiled model extraction + deterministic trace replacement / codex CLI | pid2graph-open100 / validation / historical same-plant validation also used for method selection; third-party keys | 9ad9efbd1de5 | 6 | 5 | symbols_rough | 0.9290 | 0.9192–0.9401 | 0.0091 |
| gpt-6.1-sol / provider build not recorded beyond the saved model identifier | 2x2 tiled model extraction + deterministic trace replacement / codex CLI | pid2graph-open100 / validation / historical same-plant validation also used for method selection; third-party keys | 9ad9efbd1de5 | 6 | 5 | symbols_strict | 0.8900 | 0.8815–0.8995 | 0.0069 |
| gpt-6.1-sol / provider build not recorded beyond the saved model identifier | 2x2 tiled model extraction + deterministic trace replacement / codex CLI | pid2graph-open100 / validation / historical same-plant validation also used for method selection; third-party keys | 9ad9efbd1de5 | 6 | 5 | networks | 0.8717 | 0.8661–0.8789 | 0.0063 |

## Coverage and failures

- claude-r5-hA-rep1-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.
- claude-r5-hA-rep2-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.
- claude-r5-hA-rep3-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.
- claude-r5-hA-rep4-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.
- claude-r5-hA-rep5-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.
- codex-r5-hA-rep1-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.
- codex-r5-hA-rep2-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.
- codex-r5-hA-rep3-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.
- codex-r5-hA-rep4-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.
- codex-r5-hA-rep5-trace (pid2graph-open100 / validation): 6 cases in this family/cohort; suite total 6; suite-wide unattempted: none; failed attempted answers: none.

## Limits

- Compare only the same cohort and scoring contract; model identity is contributor-declared, not provider-attested.
- Each replicate pools counts over its cases; summary reports mean/range/stdev over replicates, not a significance test or winner.
- Missing/failed attempted answers score empty; unattempted cases remain visible and create different comparison cohorts.
- Public keys and retrospective registration do not establish blindness. Synthetic controls and corrected/development results are separate.
- Description facts grade literal selected fields only: no prose names, source validity, dimensions, limits, layout quality or plant truth.
