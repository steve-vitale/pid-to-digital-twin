# Engineering context register

Draft for engineering review. Source match and plant truth are separate explicit verdicts; unknown is never upgraded by this tool.

## E18@model: Is heat rejected to cooling water in one place while steam heats a colder stream in another (a heat-integration question)?

State: **partial**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **Temperatures and duties of the cooled and the heated streams**
  How: For each stream: supply and target temperature and duty.
  Where: only a valve (HV-112) is drawn on this line, with no flow measurement; flow needs a meter or a calibrated valve curve
  Where: historian or DCS trend for FT-106 (no historian tag is mapped in this model for these)
  Where: site records: heat and material balance

- **Whether the duties overlap in time**
  How: Mark each duty continuous, batch or startup-only.
  Where: site records: operating sequence: are both duties needed at the same time?

- **Layout distance and fouling**
  How: Note pipe run and fouling service.
  Where: a walkdown: distance between the two exchangers
  Where: maintenance records: cleaning history

Decision rule from the screen: Worth a pinch or exchanger study only when the hot stream's temperature range sits above the cold stream's with a practical approach, both run at the same time for long hours, and they are close enough to connect. Otherwise close it.

Limits from the screen: A screen pairs any cooling-water-cooled item with any steam-heated item; the temperatures decide. On a reactive system any heat-integration change needs a hazard review first. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

- `published-control-sequence`: **current**, proposed, partial; `intended-heating-cooling-sequence` = **steam closed; recirculation redirected at setpoint**.
  The published narrative describes the intended sequence: at the temperature setpoint, steam flow closes and recirculation is redirected from the heater to the cooler. This is useful operating context, but it does not establish actual simultaneous duties, their duration, or an available heat-recovery opportunity.
  Source: CSB-2008-08-I-WV, revision final report; exact file pinned by SHA-256, PDF page 37 (printed page 29), temperature-control paragraph above Figure 10; narrative only; SHA-256 `6b4c944c7c5c8b5537c32e86d247064c164fe50c15d08ea64083975e574cf619`.
  Source match: unknown; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored proposed source interpretation; no owner, reviewer or site decision. Still collect representative temperatures/flows/duties, time alignment and overlap under comparable operating states, and layout/fouling evidence. Do not close E18 or calculate savings from this narrative.

Immutable history: 1 decisions, 0 ownership assignments. Full old evidence snapshots are in context.json.

A repeated answer_id explicitly revises that answer. Independent answers need different answer ids. Different canonical values under one claim_key remain disputed until an engineer explicitly revises or rejects an answer. Prose wording is not compared for agreement.
