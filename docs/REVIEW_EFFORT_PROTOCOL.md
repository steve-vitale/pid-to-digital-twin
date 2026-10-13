# Prospective engineering review-effort protocol

**Status: administration kit only. No human study has been run here. No measured time saving, quality equivalence, ROI, or operator-usability improvement is established.** The unit tests use explicitly synthetic records to test arithmetic and rejection behavior; their numbers are not study results. This is a bounded offline two-workflow study, not another model comparison or extraction benchmark.

## Decision and scope

The intended question is whether a specified AI-assisted draft workflow changes engineering labor needed to produce a specified reviewed P&ID asset deliverable, while retaining acceptable residual critical-error performance against an independent reference. Measure both time and errors; a faster result with worse errors cannot establish the intended benefit. Do not turn benchmark correction counts into minutes or assume a passed structural validator means a correct process model.

Operator screen usability, situational awareness, alarm response, and process safety are separate questions requiring their own qualified evaluation. This kit authorizes no participant contact, external model calls, plant access, publication, deployment, or operation of equipment. Any actual trial needs its owner's approval and applicable site governance. Use only eligible nonpersonal source material and pseudonymous study role IDs; keep any participant identity roster separately under the administrator's controls. Do not place personal or clinical data in these files.

**Ready-to-run first step:** [`out/review_kit/sheet-8/`](../out/review_kit/sheet-8/README.md) packages one holdout
sheet's review queue (88 rows) with the drawing, the overlay, a timer (`scripts/review_kit.py`) and a draft protocol
whose study decisions are left blank. One timed review there gives the first measured minutes for one reviewer on
one sheet. It is a pilot observation, not the two-arm comparison below.

## 1. Freeze before observations

Create and fill a protocol privately:

```sh
python -S scripts/review_effort.py template > review-protocol.json
python -S scripts/review_effort.py validate review-protocol.json
```

The blank template deliberately fails validation until completed. There are no prefilled participants, timings, quality thresholds, sample sizes, or claims. All nonempty textual fields need a substantive preregistered plan, not placeholders. Save the immutable protocol and returned canonical `protocol_sha256` with a trusted timestamp/version history before anyone starts the trial. The hash detects changed protocol content in submitted records; it cannot prove when freezing occurred. A protocol change creates a separately labeled study/version; preserve original assignments and records.

Required protocol fields:

- `schema`: `review-effort-1`; `study_id`: an administrator-selected identifier; `synthetic`: false only for genuine human observations; `frozen_at`: timezone-aware ISO timestamp.
- `baseline_workflow`: exact current manual/current-tool workflow, including available templates, experience, software, documentation and access to historical work. Do not artificially weaken the baseline.
- `assisted_workflow`: exact already selected AI draft workflow and version/artifact provenance. Include draft failures, fallback, setup, corrections and validation. Keep prompts/recipe and eligibility frozen; no tuning from study answer keys, no new model contest.
- `task_definition`: eligible drawing population and sampling, deliverable fields, completion/stopping rules, prerequisites, equivalent task boundary and time cap. Identify what is unknowable from the available drawing.
- `eligible_information_rule`: both workflows receive the same eligible source information (including history, legends, approved contextual documents and tool-access policies where specified). Record genuine tool differences as treatment; never let the assisted arm access a hidden answer key. Hash the eligible source-bundle manifest including each content hash, relevant version and allowed history/access statement. Equality of a supplied hash is not proof of equal real-world access, participant expertise, or an unbiased comparison.
- `timing_rule`: timer boundaries, active labor vs elapsed wait, pauses/interruption log, retry/failure accounting, audit time and shared setup allocation. Fix these before collection.
- `assignment_rule`: task matching, counterbalancing, randomization/allocation method, period/order, qualifications/training, prior exposure restrictions and contamination handling.
- `critical_error_rubric`: domain-approved critical-error definition, severity, field-level examples, omissions, fabricated information, duplicate counting policy, reference coverage and handling of unresolved/abstained items. No industry threshold is supplied by this kit.
- `quality_acceptance_rule`: independently justified quality acceptance/noninferiority rule and, if a later confirmatory analysis is intended, the margin and uncertainty method. The tool does not test or endorse that rule.
- `analysis_plan`, `exclusion_rule`, `sample_size_rationale`: prespecified endpoints, unit of analysis and repeated-reviewer effects, missing-data sensitivity, precision/sample-size justification and all exclusions. An unsupported sample size or small pilot cannot establish equivalence. Keep failures and exclusions visible in the original assignment denominator.

`tasks` is an array of objects with `task_id`, `source_bundle_sha256` (64 lowercase hexadecimal characters), and `truth_reference` (a frozen reference/audit specification identifier). `assignments` contains `assignment_id`, `task_id`, `arm` (`baseline` or `ai_assisted`), `reviewer_id` and positive integer `period`. The tool supports exactly one assignment per task per arm, with different task reviewers for those two arms. Use additional task IDs for truly distinct tasks; do not disguise repeated measurements as independent replications.

## 2. Allocate without teaching the task twice

Prefer different qualified reviewers for the two arms of each identical task, balanced across expertise. Reviewers may cross over between workflows only on *different*, appropriately matched drawings: balance baseline-first and assisted-first order, randomize eligible task allocation, and record period. Standardize training using separate practice material. Hold deliverable expectations, eligible inputs and time caps constant. Mask final artifacts to the independent auditor where feasible and record failures of masking.

The tool rejects the same reviewer doing both arms of the same task. A washout does not reliably erase memory of tags/topology; same-task crossover risks substantial contamination. Different-task crossover still has learning, carryover, difficulty and order effects. Discuss those limits and use a separately planned analysis if needed; per-task differences below do not adjust for them. Reviewers must not share drafts, keys or discoveries during the trial. Log prior exposure, interruptions and protocol deviations rather than silently replacing inconvenient records.

## 3. Collect measured observations

Keep a timer log and final artifact for every registered assignment. Separate:

1. `preparation_minutes`: active engineering labor from the specified task start until first reviewable draft, including applicable drafting/setup and recovery. Count all contributors' person-minutes according to the frozen allocation rule.
2. `review_minutes`: active inspection, verification, correction and rechecking labor from first draft until the common completion boundary. Use actual observations, not provider latency, tokens, benchmark score, or an estimate.
3. `residual_critical_errors`: count remaining in the final artifact according to the frozen rubric, supplied by an independent qualified auditor against the specified reference. Include omissions and unresolved critical items under the preregistered rule. An abstention is not automatically a correct answer.

`total_labor_minutes` is preparation plus review. It is bounded production engineering labor, not automatically all-in cost: if independent study audit, training or shared overhead is excluded, disclose it and keep separate logs. Record model waiting/elapsed time separately if important; never substitute it for active person-minutes. Do not stop the timer early in only one arm. Timed-out, crashed, abstained and unfinished work stays in the denominator, with actual consumed time when available.

The independent reference may be source ground truth with adequate field/severity coverage plus qualified adjudication. Existing GraphML labels generally lack tag/ISA, direction, ranges, live-point correctness and operational consequence truth. They do not alone establish critical-error absence. Resolve reference ambiguity independently, preserve disagreement and disclose uncovered fields. Never score the drafting reviewer's own sign-off as independent truth.

## 4. Record schema and offline report

Store a JSON array in `review-records.json`, initially `[]`. For each actual observation add:

- `assignment_id`, `protocol_sha256`, `source_bundle_sha256` matching the frozen registration.
- `evidence_kind`: `human_observation` for a real protocol, `synthetic` for test-only protocols. Mixed kinds are refused.
- `status`: `complete`, `abstained`, `failed` or `missing`.
- `preparation_minutes`, `review_minutes`: finite nonnegative numbers, or null when unobserved. Zero means measured zero, not missing. Boolean and string values are refused.
- `residual_critical_errors`: nonnegative integer, or null when unaudited/unknown.
- `reason`: required for every noncomplete record; explain the status and missing fields.
- `audit`: when an error count is supplied, an object with `reviewer_id` distinct from the assigned reviewer, matching `truth_reference`, `artifact_reference` identifying the exact final reviewed artifact/version, and `evidence_reference` identifying the retained item-level audit/adjudication. These references are administrator assertions, not fetched or verified by the tool.

`complete` requires both observed timings and audited errors. A missing audit/time must use `missing` with a reason, even if the deliverable was produced. No supplied record becomes an explicit missing assignment. Keep partial times on failed/abstained records rather than deleting them. Preserve audit/timer provenance outside the summarized fields.

```sh
python -S scripts/review_effort.py report review-protocol.json review-records.json > review-report.json
python -S scripts/test_review_effort.py
```

Commands only read local inputs and write JSON to stdout; no network, models, installation, auto-approval or edits to the source model. Invalid input exits 2 with an error on stderr and no report. Shell redirection is controlled by the administrator; avoid redirecting onto an input or earlier result file.

The report retains every registered assignment, status, measured value and missing value. Each arm shows assigned/status counts plus observed and missing counts, sums and medians for each metric. These available-observation summaries can mix complete and partially measured cases; inspect rows/statuses, never present them as complete-case or intention-to-treat estimates. Missing error counts are unknown, not zero. There is no invented failure penalty or time imputation.

For tasks with both arms complete, report per-task `ai_minus_baseline` differences in review minutes, total labor minutes and residual critical errors. Negative time differences describe less observed time; positive error differences describe more residual critical errors. Both directions must be shown together. Incomplete pair count is explicit; complete-pair differences are subject to survivorship bias and reviewer/period confounding. Do not headline a favorable subset while hiding failures. Preserve full assignment-level results and apply any later preregistered missing-data/sensitivity analysis separately.

The tool makes no statistical-significance, causal, ROI, quality-equivalence, safety or deployment-readiness claim. A `human_observation` label means supplied records assert that provenance; code cannot authenticate people, clocks, source access, frozen dates or auditor independence. A `synthetic` report is prominently marked **SYNTHETIC TOOL TEST ONLY; NOT HUMAN RESULTS**.

## Relationship to the existing benchmark

Keep [EVALUATION.md](EVALUATION.md), `score_pid2graph.py` and scorer controls unchanged. Existing `review_load` is source-label disagreement/correction proxy under fixed symbol/connection matching rules. It is neither measured review labor nor a domain-severity critical-error count. It can be retained as separately labeled diagnostic context with scorer version and coverage limits; this tool does not rescore drawings or infer human benefits from it. The [review loop](REVIEW_LOOP.md) records real decisions, while this protocol measures a future bounded workflow comparison. Neither replaces operator usability evaluation or site approval.
