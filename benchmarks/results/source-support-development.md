# Task results: source-support-development

Task: `source-support`. 12 fixed claims in two source families, balanced 4 supported/4 contradicted/4 insufficient-evidence. Only synthetic scorer controls; no model trial, raw-document comprehension, useful-question result or plant validation. Paraphrases explicitly scaffold scope/absence distinctions.

Only rows with the same cohort are directly comparable. See JSON for exact cases, failures, fingerprints and configurations.

## Fixed-claim label accuracy

Correct / expected is the primary metric. Missing judgments remain in the denominator. A case contains several fixed claims; this is not a count of independent source families or model trials. Reasons and source support are not automatically assessed.

| Run | Family | Correct / expected claims | Provided / expected claims | Exact label accuracy | Incorrect supported labels |
|---|---|---|---|---|---|
| source-support-reference | csb-mgpi | 6 / 6 | 6 / 6 | 1.0000 | 0 |
| source-support-reference | nist-smstestbed | 6 / 6 | 6 / 6 | 1.0000 | 0 |
| source-support-empty | csb-mgpi | 0 / 6 | 0 / 6 | 0.0000 | 0 |
| source-support-empty | nist-smstestbed | 0 / 6 | 0 / 6 | 0.0000 | 0 |
| source-support-all-supported | csb-mgpi | 2 / 6 | 6 / 6 | 0.3333 | 4 |
| source-support-all-supported | nist-smstestbed | 2 / 6 | 6 / 6 | 0.3333 | 4 |
| source-support-all-contradicted | csb-mgpi | 2 / 6 | 6 / 6 | 0.3333 | 0 |
| source-support-all-contradicted | nist-smstestbed | 2 / 6 | 6 / 6 | 0.3333 | 0 |
| source-support-all-insufficient | csb-mgpi | 2 / 6 | 6 / 6 | 0.3333 | 0 |
| source-support-all-insufficient | nist-smstestbed | 2 / 6 | 6 / 6 | 0.3333 | 0 |

The label F1 rows below are companion diagnostics. F1 differs from exact accuracy when judgments are missing. Inspect each claim and its reason; a correct label can accompany a false explanation.

## Per-label diagnostics

| Model / version | Method / interface | Family / split / evidence | Cohort | Cases | Replicates | Metric | Mean F1 | Min–max | SD |
|---|---|---|---|---|---|---|---|---|---|
| synthetic-control / 1 | all-contradicted / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | supported | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-contradicted / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | contradicted | 0.5000 | 0.5000–0.5000 | unavailable |
| synthetic-control / 1 | all-contradicted / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | insufficient-evidence | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-contradicted / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | supported | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-contradicted / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | contradicted | 0.5000 | 0.5000–0.5000 | unavailable |
| synthetic-control / 1 | all-contradicted / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | insufficient-evidence | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-insufficient / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | supported | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-insufficient / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | contradicted | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-insufficient / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | insufficient-evidence | 0.5000 | 0.5000–0.5000 | unavailable |
| synthetic-control / 1 | reference / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | supported | 1.0000 | 1.0000–1.0000 | unavailable |
| synthetic-control / 1 | reference / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | contradicted | 1.0000 | 1.0000–1.0000 | unavailable |
| synthetic-control / 1 | reference / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | insufficient-evidence | 1.0000 | 1.0000–1.0000 | unavailable |
| synthetic-control / 1 | all-insufficient / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | supported | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-insufficient / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | contradicted | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-insufficient / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | insufficient-evidence | 0.5000 | 0.5000–0.5000 | unavailable |
| synthetic-control / 1 | reference / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | supported | 1.0000 | 1.0000–1.0000 | unavailable |
| synthetic-control / 1 | reference / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | contradicted | 1.0000 | 1.0000–1.0000 | unavailable |
| synthetic-control / 1 | reference / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | insufficient-evidence | 1.0000 | 1.0000–1.0000 | unavailable |
| synthetic-control / 1 | all-supported / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | supported | 0.5000 | 0.5000–0.5000 | unavailable |
| synthetic-control / 1 | all-supported / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | contradicted | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-supported / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | insufficient-evidence | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | empty / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | supported | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | empty / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | contradicted | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | empty / deterministic authored control | nist-smstestbed / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 452fc3e5dae2 | 1 | 1 | insufficient-evidence | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-supported / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | supported | 0.5000 | 0.5000–0.5000 | unavailable |
| synthetic-control / 1 | all-supported / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | contradicted | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | all-supported / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | insufficient-evidence | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | empty / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | supported | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | empty / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | contradicted | 0.0000 | 0.0000–0.0000 | unavailable |
| synthetic-control / 1 | empty / deterministic authored control | csb-mgpi / development / Independent coding-agent original-source key; fixed claims and explicit paraphrases, exposed development sources; no model trial or human approval | 18b8fbef4198 | 1 | 1 | insufficient-evidence | 0.0000 | 0.0000–0.0000 | unavailable |

## Coverage and failures

- source-support-reference (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
- source-support-reference (nist-smstestbed / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
- source-support-empty (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
  mgpi-source-claims missing_judgments: ["SJ001", "SJ002", "SJ003", "SJ004", "SJ005", "SJ006"].
- source-support-empty (nist-smstestbed / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
  nist-source-claims missing_judgments: ["SJ007", "SJ008", "SJ009", "SJ010", "SJ011", "SJ012"].
- source-support-all-supported (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
  mgpi-source-claims incorrect_judgments: [{"id": "SJ003", "expected": "contradicted", "predicted": "supported"}, {"id": "SJ004", "expected": "contradicted", "predicted": "supported"}, {"id": "SJ005", "expected": "insufficient-evidence", "predicted": "supported"}, {"id": "SJ006", "expected": "insufficient-evidence", "predicted": "supported"}].
- source-support-all-supported (nist-smstestbed / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
  nist-source-claims incorrect_judgments: [{"id": "SJ009", "expected": "contradicted", "predicted": "supported"}, {"id": "SJ010", "expected": "contradicted", "predicted": "supported"}, {"id": "SJ011", "expected": "insufficient-evidence", "predicted": "supported"}, {"id": "SJ012", "expected": "insufficient-evidence", "predicted": "supported"}].
- source-support-all-contradicted (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
  mgpi-source-claims incorrect_judgments: [{"id": "SJ001", "expected": "supported", "predicted": "contradicted"}, {"id": "SJ002", "expected": "supported", "predicted": "contradicted"}, {"id": "SJ005", "expected": "insufficient-evidence", "predicted": "contradicted"}, {"id": "SJ006", "expected": "insufficient-evidence", "predicted": "contradicted"}].
- source-support-all-contradicted (nist-smstestbed / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
  nist-source-claims incorrect_judgments: [{"id": "SJ007", "expected": "supported", "predicted": "contradicted"}, {"id": "SJ008", "expected": "supported", "predicted": "contradicted"}, {"id": "SJ011", "expected": "insufficient-evidence", "predicted": "contradicted"}, {"id": "SJ012", "expected": "insufficient-evidence", "predicted": "contradicted"}].
- source-support-all-insufficient (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
  mgpi-source-claims incorrect_judgments: [{"id": "SJ001", "expected": "supported", "predicted": "insufficient-evidence"}, {"id": "SJ002", "expected": "supported", "predicted": "insufficient-evidence"}, {"id": "SJ003", "expected": "contradicted", "predicted": "insufficient-evidence"}, {"id": "SJ004", "expected": "contradicted", "predicted": "insufficient-evidence"}].
- source-support-all-insufficient (nist-smstestbed / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: none; failed attempted answers: none.
  nist-source-claims incorrect_judgments: [{"id": "SJ007", "expected": "supported", "predicted": "insufficient-evidence"}, {"id": "SJ008", "expected": "supported", "predicted": "insufficient-evidence"}, {"id": "SJ009", "expected": "contradicted", "predicted": "insufficient-evidence"}, {"id": "SJ010", "expected": "contradicted", "predicted": "insufficient-evidence"}].

## Limits

- Compare only the same cohort and scoring contract; model identity is contributor-declared, not provider-attested.
- Each replicate pools counts over its cases; summary reports mean/range/stdev over replicates, not a significance test or winner.
- Missing/failed attempted answers score empty; unattempted cases remain visible and create different comparison cohorts.
- Public keys and retrospective registration do not establish blindness. Synthetic controls and corrected/development results are separate.
- Source-support grades labels for fixed supplied claims against a supplied key. It does not judge free-form reasoning, source validity, question usefulness or plant truth; cited IDs are checked structurally.
