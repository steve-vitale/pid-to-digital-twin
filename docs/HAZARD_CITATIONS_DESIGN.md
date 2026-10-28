# Hazard emphasis from public incidents: design and a small offline proof

**Status: design plus a prototype heuristic, part of the 3D tour proof of concept.** Nothing here is a
hazard analysis. No external service was called and no company data was used. The matching ran once, offline,
over a local read-only checkout of a public-incident corpus. Its curated output is committed as
[`data/hazard_citations_prototype.json`](../data/hazard_citations_prototype.json). A process-safety engineer and an
operator must review it before any of it is used for training.

## The question

An orientation tour should tell a new operator which parts of the process deserve the most attention, and why.
"Why" should come from things that actually happened to people, not from Claude's opinion. So the question is: can
the twin's equipment be matched against a catalogue of real, public accident records, so that each tour stop cites
a few process-specific hazards with a source a trainee can read?

## Where the incident records come from

The catalogue is built only from public agency records:

- CSB investigation reports and their recommendations;
- about 500 EPA Risk Management Program (RMP) accident records, compiled by the Data Liberation Project under
  CC-BY-SA-4.0;
- public OSHA and NTSB reports.

Matching is deterministic and explainable: a record scores the number of its keywords found as lowercase substrings
of an equipment kind's search terms, and a **precision floor** means generic words such as "startup" or "refinery"
never surface a record on their own; at least one equipment-specific term must hit. Keeping the floor matters: a
keyword match on "tower" also finds an airport control tower (below).

## Design: matching twin equipment to public incidents

### What the twin can offer as a query

Each unit in the twin contract carries:
- its **equipment kind** (the 2D/3D symbol kind: `feed`, `reactor`, `condenser`, `separator`, `compressor`,
  `stripper`);
- its instruments, with **measured variables** (pressure, temperature, level, flow, composition);
- its **final elements** (cooling-water valves, feed valves, level valves);
- any **published limits** (TE has two Critical shutdown limits, both on the reactor);
- its **behaviour in recorded faults** (which tags leave their band first).

A query is the equipment kind plus mechanism terms derived from that kind and its instruments. Some examples:

| Kind and instruments | Mechanism terms |
|---|---|
| Reactor with temperature and a cooling valve | runaway, decomposition, loss of cooling, overpressure, relief |
| Separator with level and a level valve | drum overflow, liquid carryover, vapour-liquid disengagement |
| Column with level and steam | overfill, overheat at startup, blocked-in reboiler |
| Exchanger | rupture, blocked-in heating, overpressure |
| Feed header with valves | line opening, isolation, dead legs |

### Matching rule (prototype)

`scripts/hazard_citations.py` follows that precedent-matcher idea:

- lowercase substring hits of equipment-specific terms (`KIND_TERMS`) and generic terms;
- specific hits weigh 2 and generic hits weigh 1;
- the score is zero unless at least one specific term hits;
- duplicates of the same incident recorded under different URL slugs are collapsed;
- only agency domains are kept (csb.gov, osha.gov, dol.gov, ntsb.gov, epa.gov);
- anything that is not a public record is excluded.

The ranked shortlist is then **curated by hand** (here, by Claude): pick 3-5 per kind, drop false positives, and
write a one-line hazard summary in our own words. A summary states only what its corpus record states. Where the
record is a CSB recommendation, the summary says what the CSB asked for, not what happened. A first draft broke
this rule for seven citations (e.g. "dead legs in feed piping caused..."); they were rewritten before the
final render. The committed file records each pick's heuristic score and
matched terms so the choice can be audited.

The citation is a **mechanism analogy**, not a claim about this process. TE's chemistry is a published benchmark
with disguised components. "A runaway reaction overpressured a vessel at Bayer CropScience" says that runaway and
overpressure are real ways reactors hurt people. It does not say that the TE reactor can run away.

### Two kinds of emphasis, kept apart

| | Source | In this prototype |
|---|---|---|
| **Shutdown limits** | Data: a unit carrying a published Critical (shutdown) limit, where the simulator trips the plant | R-101 (PI-107 > 3000 kPa g, TI-109 > 175 degC, from `build_meta.json`) |
| **First warning** | Data: the unit whose tag leaves its normal band first in the recorded fault | U-100 (FI-101 and FV-101 at the fault-6 start) |
| **Why this matters** | Prototype citation file: public incidents matched to the equipment kind | One citation per stop, in the caption and narration |

The public catalogue never makes a unit "highest risk" by itself. At a real plant, risk ranking comes from the
PHA/HAZOP and LOPA; the tour should import that ranking, not invent one. Public incidents are severe outliers (a
selection bias), so they explain why a hazard matters; they do not show how likely it is.

## How it surfaces in the tour

- **Emphasis stops.** A ring on the ground around the unit (red for shutdown limits, amber for first warning)
  and a coloured label stating the reason and the numbers, e.g. "PUBLISHED SHUTDOWN LIMITS:
  PI-107 > 3000 kPa g, TI-109 > 175 degC". The numbers come from data files.
- **Caption line** on each stop's still: "Why this matters: \<one line\> (\<agency\>)".
- **Narration sentence** with the source: "Why this matters: \<hazard\>. Source: CSB, 2008." The full citation (title,
  URL, matched terms) is in `out/3d/te_scene.json` under `tour_script.stops[].citation`.
- **Later:** carry the citation ids in the GLB node extras, so a browser viewer can show the source when a trainee
  clicks a unit.

## The offline proof: what was actually run

`python scripts/hazard_citations.py --corpus-repo <corpus repository checkout> --ref origin/main` scanned **972 public
records**. The curated picks:

| Twin kind (unit) | Public incident | Agency | Score (matched terms) | URL as recorded |
|---|---|---|---|---|
| feed (U-100) | TPC Group Port Neches explosions and fire (2019) | CSB | 7 (dead leg, piping) | https://www.csb.gov/tpc-port-neches-explosions-and-fire/ |
| | PEMEX Deer Park chemical release (2024) | CSB | 5 (blind, piping) | https://www.csb.gov/pemex-deer-park-chemical-release-/ |
| | LyondellBasell La Porte fatal chemical release (2021) | CSB | 4 (plug valve) | https://www.csb.gov/lyondellbasell-la-porte-fatal-chemical-release-/ |
| | Safety study: remote isolation of process equipment (2024) | CSB | 4 (remote isolation) | https://www.csb.gov/csb-safety-study-remote-isolation-of-process-equipment/ |
| reactor (R-101) | Kuraray America EVAL plant release and fire (2018), shown first | CSB | 6 (pressure-relief, reactor) | https://www.csb.gov/kuraray-pasadena-release-and-fire/ |
| | Bayer CropScience runaway reaction and explosion (2008), cited for runaway exothermic reactions in general | CSB | 8 (overpressur, runaway) | https://www.csb.gov/bayer-cropscience-pesticide-waste-tank-explosion/ |
| | PolyCarbon Industries vessel explosion, Newburyport MA (2023; PSM citations) | OSHA (US DOL) | 4 (decomposition, temperature limit) | https://www.dol.gov/newsroom/releases/osha/osha20231116 |
| | Arkema Crosby chemical plant fire (2017), a loss-of-cooling case | CSB | 2 (refrigeration) | https://www.csb.gov/arkema-inc-chemical-plant-fire-/ |
| condenser (E-101) | Tesoro Anacortes refinery explosion and fire (2010) | CSB | 11 (exchanger, heat exchanger) | https://www.csb.gov/tesoro-anacortes-refinery-fatal-explosion-and-fire-/ |
| | EPA RMP accident 1000086158: chlorine release from a heat exchanger (2024) | EPA RMP | 6 | facility 100000053014 (corpus URL does not resolve; see note) |
| | EPA RMP accident 1000086219: ammonia release, heat exchanger overpressurization (2022) | EPA RMP | 5 | facility 100000123724 (corpus URL does not resolve; see note) |
| | Williams Olefins Geismar reboiler rupture (2013) | CSB | 2 (reboiler) | https://www.csb.gov/williams-olefins-plant-explosion-and-fire-/ |
| separator (V-101) | Cuisine Solutions ammonia release (2024) | CSB | 10 (knockout, surge drum, two-phase, vapor-liquid) | https://www.csb.gov/cuisine-solutions-ammonia-release-/ |
| | BP-Husky Toledo (Oregon, Ohio) chemical release and fire (2022) | CSB | 8 (drum overflow, mix drum) | https://www.csb.gov/bp---husky-oregon-chemical-release-and-fire-/ |
| | EPA RMP accident 1000085523: separator relief valve lifted for 10 h (2023) | EPA RMP | 3 (separator) | facility 100000029346 (corpus URL does not resolve; see note) |
| compressor (K-101) | EPA RMP accident 1000086318: compressor release, fire and explosion (2024) | EPA RMP | 5 (compressor) | facility 100000060667 (corpus URL does not resolve; see note) |
| | EPA RMP accident 1000085901: compressor release and fire, 6,395 sheltered (2022) | EPA RMP | 4 | facility 100000231536 (corpus URL does not resolve; see note) |
| | EPA RMP accident 1000085297: compressor discharge-bottle fitting fire (2017) | EPA RMP | 4 | facility 100000227248 (corpus URL does not resolve; see note) |
| stripper (C-101) | BP Texas City refinery explosion (2005) | CSB | 10 (distillation, splitter, tower) | https://www.csb.gov/bp-america-refinery-explosion/ |
| | BP-Husky Toledo (2022): CSB asks for overflow prevention for towers and drums | CSB | 6 (tower) | https://www.csb.gov/bp---husky-oregon-chemical-release-and-fire-/ |
| | Williams Olefins Geismar: heat into a blocked-in reboiler (2013) | CSB | 2 (reboiler) | https://www.csb.gov/williams-olefins-plant-explosion-and-fire-/ |

**Aptness check for the reactor (review, 2026-10-12).** The TE reactor is a gas-phase exothermic reactor. A
search of the same 972 records for gas-phase, exothermic, temperature-excursion, polymerization and runaway cases
found no gas-phase reactor incident. Bayer CropScience's vessel was a waste-treatment vessel, not a gas-phase reactor, so it no longer leads.
Kuraray now leads: a reactor was taken above its pressure limit, and the CSB asked for that limit to be made clear in
operator training and the control interface. That is the closest fit to the PI-107 high alarm the tour shows.
Bayer stays, phrased generally as an example of runaway exothermic reactions.

What the run also showed:
- **False positives are real.** NTSB's Asiana 214 report matched "tower" (an airport control tower). An EPA record
  matched "column" in "sight column". An FCC-unit isolation failure ranked third for "reactor". All three were dropped
  by hand and are listed in the JSON. A keyword shortlist needs a human.
- **Coverage is uneven.** No CSB investigation in this corpus centres on a compressor, so the three compressor
  citations are EPA RMP records.
- **EPA RMP URLs built by the corpus's fetcher do not resolve to a record.** `https://www.epa.gov/rmp?facility=<id>`
  returns the RMP landing page and ignores the id (checked 2026-10-13). The citation file now links EPA's RMP Public
  Data Sharing search (https://cdxapps.epa.gov/olem-rmp-pds/) and gives the accident and facility ids, so the record
  can be looked up there or in the Data Liberation Project mirror (CC-BY-SA-4.0, attribution required). The table
  below keeps the facility ids as the corpus recorded them.
- Years were first given only where the corpus record stated them. The source check added the years the agency pages
  state (BP-Husky Toledo, 2022; PolyCarbon, 2023).
- Low scores (Arkema at 2, Williams at 2) were kept as honest weak matches and labelled as such in the summaries.

## Source check against the agency pages (2026-10-13)

Each citation's date, location, casualty count and quoted recommendation was read against the agency page. What changed:

| Citation | Draft said | Agency page says | Change |
|---|---|---|---|
| Tesoro Anacortes (2010) | ruptured "during a restart" | during a maintenance operation to switch a process stream between two parallel banks of exchangers; 7 died | wording corrected |
| Williams Olefins Geismar (2013) | URL `.../williams-geismar-olefins-plant-reboiler-rupture-and-fire/` | that URL returns 404; the live page is `/williams-olefins-plant-explosion-and-fire-/`; 2 died, 167 injured | URL and injury count |
| Bayer CropScience (2008) | "liquid-phase residue treater", "restart before its controls and safety systems were ready" | the cited page supports a runaway reaction destroying a waste-treatment vessel, 2 deaths; the other details are not on it | summary narrowed to what the page says |
| PolyCarbon Industries | no date or place | Newburyport, Massachusetts, May 4, 2023 (OSHA release) | added |
| Cuisine Solutions (2024) | "knockout drums" | Loudoun County, Virginia, July 31, 2024; 40 evaluated at hospitals; final report September 25, 2025; recommendations name horizontal surge vessels with little vapor space and vapor-liquid disengagement, not knockout drums | wording corrected |
| BP-Husky Toledo | no year | September 20, 2022; 2 died | added |
| CSB remote-isolation safety study | no year | published July 25, 2024 | added |
| EPA RMP (6 records) | `epa.gov/rmp?facility=<id>` | does not resolve to a record | replaced, see above |

Confirmed as drafted: TPC Port Neches (2019), PEMEX Deer Park (October 10, 2024: workers removing an isolation blind
from hydrogen sulfide piping; 2 died, 13 injured), LyondellBasell La Porte (2021),
Kuraray (May 19, 2018, 21 injured; the lower-design-pressure recommendation is quoted verbatim), Arkema Crosby (2017) and BP Texas City (2005, 15 died). EPA RMP record contents were not re-checked
against EPA data.

## Integration path (later, not built)

1. **Now (this repo):** a static, curated JSON beside the twin, regenerated when the twin's equipment changes;
   tests check the file's shape, domains and the prototype label (`scripts/test_build_3d_scene.py`).
2. **A read-only precedent lookup in the plant's own permit/hazard or MOC tooling:** `find_public_precedents(equipment_kind,
   mechanisms, limit)`, returning cards with source URL, matched terms and score under the same precision floor.
   It writes nothing.
3. **Equipment kinds:** reactor, compressor, column, exchanger and separator as first-class kinds in whatever
   equipment model the plant uses, so rule-based checks and precedent matching can use them.
4. **Management of change:** when the twin changes, regenerate the tour and re-run the matching, and route the
   updated training material through the site's management-of-change approval, so the training record shows which
   plant state and citations it was built from.
5. **The plant's own history first:** a site's own incidents and near misses, rank above public precedents. That
   stays inside the plant's own systems.
6. **LOTO isolation permits:** the lockout/tagout mode designed in [3D_TOUR_PLAN.md](3D_TOUR_PLAN.md) would link
   each isolation point to the site's isolation permit. The procedure itself comes from the
   site's energy-control program, never from this scene.
7. **Import the PHA, don't invent risk:** if the site has HAZOP/LOPA records, the tour's emphasis should come from
   them (node, deviation, consequence, safeguards). Public incidents then only illustrate them.

## Not claimed

- That any cited incident's mechanism applies to the TE process or to any real plant.
- That the curated list is complete or the best available; it is a 972-record keyword shortlist.
- That the emphasis ranks risk. It marks published limits and recorded first warnings, both from data.
- Any review by a process-safety engineer, an operator, or a second model.
