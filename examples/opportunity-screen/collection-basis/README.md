# A rating is a starting point for an investigation

This fictional model records a fan's HP/RPM and a heater's kW/HP. The former engine dropped its fan-curve and
heater-hours requests when those scalars were present. Neither a matching curve nor an operating history had
been supplied. The corrected screen retains the values as **unverified candidates**, with their model locators,
and separates the collection tasks:

| Investigation | Supplied candidates | Still collect or review |
|---|---|---|
| E5: damper-controlled fan | F-1: 15 HP, 1780 RPM | Actual control mode/period; matching fan curves and system points; nameplate/drive basis; representative electrical-input and load history |
| H3: low-temperature electric heating | EH-1: 20 kW, 26.8 HP; stated load 60 C | Heating/rating basis in original units; actual energized hours/load over a stated period; candidate heat-source conditions, timing and compatibility |

```sh
python -S scripts/question_engine.py --model examples/opportunity-screen/collection-basis/model.json --question E5 --question H3 --out out/collection-basis
```

Read [screen.md](screen.md) or [questions.json](questions.json). A curve filename, Boolean flag or hours scalar
can be shown without establishing document suitability, period coverage or a settled answer. Supplying more
candidate values does not remove these review requests. Their `not_on_drawing` state concerns the complete
collection/review requirement, without denying the candidate information shown alongside it.

For an optional local handoff:

```sh
python -S scripts/graph_export.py examples/opportunity-screen/collection-basis/model.json --questions out/collection-basis/questions.json --out out/collection-graph.json
python -S scripts/context_register.py prepare --model out/collection-graph.json --questions out/collection-basis/questions.json --sources examples/opportunity-screen/collection-basis/sources.json --out out/collection-context
```

The source manifest deliberately contains no operating records. The resulting `context.md` retains the candidate
facts and collection prompts; both investigations remain unanswered and need an owner. No decision is created.
Use the [plain first-question brief](../../first-pilot/README.md) to choose one evidence request and take the
result into the company's own review and record system. These commands do not collect process data or verify it.

The collection design is informed by DOE's [fan sourcebook](https://www.energy.gov/sites/prod/files/2014/05/f16/fan_sourcebook.pdf)
(printed pp. 6–7, 43–45, 55–56), its [motor-load guidance](https://www.energy.gov/sites/default/files/2014/04/f15/10097517.pdf)
(printed pp. 3, 7–8), and the Australian Government's [heat-recovery guide](https://www.energy.gov.au/business/equipment-guides/waste-heat-recovery).
These inform the questions; they are not sources for the invented equipment or approval of a proposed change.

This is a software development control, with no plant data, new source-family accuracy result or human usefulness
trial. H3's 150 C trigger remains a catalog heuristic. No automatic unit equivalence, energy calculation, curve
validation, recovered-heat feasibility or savings claim is added.
