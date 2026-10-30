# Opportunity screen: Bayer CropScience methomyl residue treater (Institute, West Virginia), as described by the CSB

Model: `data/bayer_rt/process_model.json`. Questions: `data/questions.json`.

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

### E18: Is heat rejected to cooling water in one place while steam heats a colder stream in another (a heat-integration question)?

**About:** U2, HV-112  

**Evidence on the drawing / model**

- stream U2 (asset stream:U2) reads "Cooling water (80 C) supply to the cooler" at E-3 (`streams[U2]`)
- hand valve HV-112 reads "HV-112 Cooling water supply valve" at E-3 (`manual_valves[HV-112]`)
- Steam-heated user: stream U1 (asset stream:U1) reads "Steam supply to the heater" at E-2 (`streams[U1]`)
- Steam-heated user: instrument FT-106 reads "FT-106 Indicated steam flow to the heater" at E-2 (`instruments[FT-106]`)
- Steam-heated user: valve TV-104C reads "TV-104C Steam flow valve to the heater (Fig 10: Temperature Control Valve)" at E-2 (`final_elements[TV-104C]`)
- Steam-heated user: hand valve HV-108 reads "HV-108 Steam block valve, heater steam supply" at E-2 (`manual_valves[HV-108]`)

**Data to collect**

- Temperatures and duties of the cooled and the heated streams [not on drawing]. Where: only a valve (HV-112) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve; then historian or DCS trend for FT-106 (no historian tag is mapped in this model for these); then site records: heat and material balance. How: For each stream: supply and target temperature and duty.
- Whether the duties overlap in time [not on drawing]. Where: site records: operating sequence: are both duties needed at the same time?. How: Mark each duty continuous, batch or startup-only.
- Layout distance and fouling [not on drawing]. Where: a walkdown: distance between the two exchangers; then maintenance records: cleaning history. How: Note pipe run and fouling service.

**How it is decided:** Worth a pinch or exchanger study only when the hot stream's temperature range sits above the cold stream's with a practical approach, both run at the same time for long hours, and they are close enough to connect. Otherwise close it.

**What the source says (S19, S24):** Pinch potential "far exceeds that from well-known conventional techniques such as heat recovery from boiler flue gas, insulation and steam trap management." No % stated in that section.
IAC/ITAC recommendation code: 2.243x; 2.244x (IAC/ITAC browse page: 2.243x: 3,673 recommendations, 1.4 yr average payback, 31.2% implemented; 2.244x: 1,466 recommendations, 1.7 yr, 28.6%; average dollar figure omitted).

**Limits:** A screen pairs any cooling-water-cooled item with any steam-heated item; the temperatures decide. On a reactive system any heat-integration change needs a hazard review first. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

## Sources cited above

- S19: Worrell & Galitsky, Energy Efficiency Improvement and Cost Saving Opportunities for Petroleum Refineries: An ENERGY STAR Guide (LBNL-56183, Feb 2005). https://www.osti.gov/servlets/purl/862119 (license: DOE-lab (contractor) report: unclear, but freely citable. Its tables quote older secondary sources, so figures are cited as reported in LBNL-56183)
- S24: DOE IAC/ITAC database: browse pages, download, schema document. https://itac.university/index/arc/2. (license: No license or terms stated: unclear)
