# Opportunity screen: Millard historical evaporator control-bank source subset

Model: `examples/opportunity-screen/millard/model.json`. Questions: `data/questions.json`.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Energy | 1 |
| Heat grade (high-grade heat for low-grade duty) | 0 |
| Metering | 0 |
| Controls and automation | 0 |
| Emissions | 0 |
| Safety questions to verify | 0 |

## Energy

### E30: Are these evaporators defrosted on a fixed timer rather than when frost is actually there?

**About:** EVAP-GROUP  

**Evidence on the drawing / model**

- equipment EVAP-GROUP reads "EVAP-GROUP Ammonia blast freezer evaporator group" (`units[EVAP-GROUP]`)
- Defrost: final element HG-MAIN reads "HG-MAIN Hot gas main valve for defrost" at EVAP-GROUP (`final_elements[HG-MAIN]`)
- Checked, none found: no demand defrost initiation (coil differential pressure, frost sensor) drawn on this evaporator (`applies_when.without`)

**Data to collect**

- Defrost schedule per evaporator [not on drawing]. Where: DCS/PLC configuration: defrost initiation (timer or demand), defrosts per day, duration and termination (time or coil temperature) per evaporator. How: List defrosts per day by season.
- Frost on the coil when a scheduled defrost starts [not on drawing]. Where: a walkdown: look at the coil just before a few scheduled defrosts, in a dry week and a humid week. How: Note clear, light or heavy frost.
- Hot gas use and room temperature rise per defrost [not on drawing]. Where: historian or DCS trend for HG-MAIN (no historian tag is mapped in this model for these). How: The heat put in to defrost comes back as refrigeration load afterwards.

**How it is decided:** Worth a look when coils are clear at scheduled defrosts, or the count per day is the same in dry weeks as in humid ones. Close it if defrost is already started on demand.

**What the source says (S25):** Demand defrost (S25, p. 66): "Evaporators should be defrosted only when necessary, as opposed to on timed schedules where defrosting occurs regardless of need." "Too frequent defrosts." is listed among control strategies that "may compromise system energy efficiency" (S25, p. 59, citing Pearson 2003). No % stated.

**Limits:** A coil differential pressure instrument on the evaporator is taken as demand defrost; check that it is used for that. A P&ID rarely shows the defrost timer itself, so the schedule always comes from the controls.

## Sources cited above

- S25: Brush, Masanet and Worrell, Energy Efficiency Improvement and Cost Saving Opportunities for the Dairy Processing Industry: An ENERGY STAR Guide for Energy and Plant Managers (LBNL-6261E, Oct 2011). https://www.osti.gov/servlets/purl/1171534 (license: DOE-lab report sponsored by US EPA: unclear, freely citable; its figures from older sources are quoted as reported there)
