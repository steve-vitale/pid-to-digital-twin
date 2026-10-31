# Ratings are candidates, not completed investigations

This fictional software control keeps four collection obligations visible: a pump/system curve, the curve's
best-efficiency point (BEP), motor efficiency and actual cooler heat duty. It is not a new drawing family,
model evaluation, engineering acceptance or measured usefulness result.

From the repository root, offline:

```sh
python scripts/question_engine.py --model examples/opportunity-screen/pump-motor-basis/model.json --question E1 --question E2 --question E4 --question H4 --out out/pump-motor-basis
```

Compare the resulting `questions.json` and `screen.md` with the files here. All four findings remain questions.
The original supplied values and model-field locators remain available as **unverified candidates**.

| Supplied record | What remains to collect or review |
|---|---|
| Pump CAPACITY/DISCHARGE | Matching curve, installed configuration, units, BEP and system operating points. Rated duty is not necessarily BEP. |
| A curve URI naming another pump, marked unreadable | Document readability, correct equipment/configuration and semantic suitability. Neither a URI nor a Boolean proves usable evidence. |
| Motor HP/RPM and an efficiency transcription with unknown identity | Matched nameplate, rated shaft-output basis and efficiency; representative electrical-input/load records remain separate. |
| Cooler CAPACITY of `100 gpm` | Heat-duty units and basis, coincident temperatures/flow and a stated operating period or documented heat balance. Flow capacity alone is not heat duty. |

The engine retains these requests even if more scalar fields are supplied. An engineer's answer and review
belong in the separate [context workflow](../../context-register/README.md), or the organization's existing
records process; candidate field presence cannot approve an investigation.

These collection distinctions were informed by the DOE [pumping sourcebook](https://www.energy.gov/sites/prod/files/2014/05/f16/pump.pdf)
(printed pp.37–39,55–61), [pump matching sheet](https://www.energy.gov/sites/prod/files/2014/05/f16/match_pumps_to_system.pdf)
(p.1) and [motor load guide](https://www.energy.gov/sites/default/files/2014/04/f15/10097517.pdf)
(printed pp.3–4). They support further review, not a drive recommendation, resize decision or saving for this case.

The remaining catalog field requests were checked for the same class of mismatch. E11's named temperature,
H1's station rating, H2's named supply conditions and H4's supply temperature remain narrow field-accounting
tasks. Their presence is not independent validation of units, period, source truth or engineering adequacy.
All 50 original triggers and cited benefit objects are retained. Broader catalog coverage and human usefulness
still require source-backed cases and an engineer trial; adding this regression does not establish either.
