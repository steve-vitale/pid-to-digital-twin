# Which normal records apply to this investigation?

Work type: **Initial source investigation**. Manual reference: **PRONTO-BASELINE-CONTEXT**.
Disposition: **Insufficient evidence to qualify a baseline for company use**.
Investigator, reviewer/date, receiving owner and acceptance: **Unassigned / not recorded**.
Trial and operational benefit: **Not run / not measured**.

## Question and partial evidence

Which operating/configuration records explain the supplied labels and conditions, establish comparability for
the intended investigation, and identify the responsible reviewer?

The generated comparison shows that changing the baseline and score interval can change flags and delay without
changing the detector. A recent labeled-normal candidate helps one case and worsens others. The original labels
are retrospective; they do not establish a prospective baseline-selection policy or present plant state.

| Evidence reference | What it supports | What remains unresolved |
|---|---|---|
| `plan.json`; `expected/results.json`, each case's normal/fit/K/score ranges and source hashes | Exact records used, chronology, independent scoring population and every result. | Whether those records represent the operating conditions the intended user needs. |
| Merged source files, exact physical lines in `normal_blocks` | Normal labels coexist with different observed flow values. | Mode/configuration interpretation, sensor identity and health-label scope. |
| Original workbook, `Operation Log 0907!A18`, `H18:H19`, `G20`, `A98`, `H98:H99`, `G100` | Distinct nominal settings and separate health/flow descriptions in the log. | Exact time/identity joins to the merged blocks; no row-to-test match is inferred from a similar value. |
| Authors' aligned-data readme, numbered steps 4 and 5 | Input-column combination and health labeling use the operation log. | Reviewed raw-channel mapping and the basis for using each condition as a baseline. |

All originals belong to the pinned Zenodo 1341583 release. The result JSON lists the unchanged-byte hashes and
original member paths; the guide provides attribution. A matching hash does not make a source governing company evidence.

## Next evidence request and handoff

Request the intended asset/measurement scope, raw-to-prepared channel mapping, applicable control/configuration
revisions, normal/abnormal definitions, operating-point changes, known interventions and missing-coverage notes.
Ask a qualified reviewer to state which windows are comparable and why, before adopting a baseline or collecting
a longer one. Keep contrary observations and unsuccessful choices with that decision.

Responsible owner / due date: **Unassigned / not set**. Company destination / accepted handoff: **Not recorded**.
Reopen the question when the mapping, labels, configuration or intended operating scope changes.
The company's shared system should retain those decisions and source revisions. The toolkit supplies this
starting packet; no site qualification, operating action, measured pilot or company adapter is demonstrated.
