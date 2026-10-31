# Keep each supply's missing evidence visible

Two fictional steam supplies feed one heater. TV-101 records header A's pressure; TV-102 records header B's
temperature. Neither supply has both values. One finding groups the investigation, while its collection request
stays open for each supply:

| Subject | Supplied | Still needed |
|---|---|---|
| TV-101 | Pressure: 8 bar | Temperature |
| TV-102 | Temperature: 140 C | Pressure |

```sh
python -S scripts/question_engine.py --model examples/opportunity-screen/field-coverage/model.json --question H2 --out out/field-coverage
```

Read [screen.md](screen.md) or inspect `field_coverage` in [questions.json](questions.json). Each field retains
its subject, state and source locator. A complete sibling cannot answer an unknown supply. Grouping by heater
does not establish that two headers have the same conditions. The [request contract](../../../docs/OPPORTUNITY_SCREEN.md#the-three-evidence-states)
also explains explicitly unit-scoped requests.

This is a software regression example with invented assets and values. It establishes field accounting, not
source correctness, physical plausibility, question usefulness or engineering acceptance. The test suite also
checks complete/unknown siblings, blanks, reversed ordering and retention through graph and cross-site roll-up.
