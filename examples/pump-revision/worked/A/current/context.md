# Engineering context register

Draft for engineering review. Source match and plant truth are separate explicit verdicts; unknown is never upgraded by this tool.

## E1@P-1: Is this pump throttled by a control valve when it could run on a variable speed drive?

State: **unanswered**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **Control valve position (% open) over normal operation**
  How: Take a month or more of valve output at normal sampling; note the typical and the lowest % open, and the hours at each.
  Where: historian or DCS trend for FV-101 (no historian tag is mapped in this model for these)
  Where: DCS/PLC configuration: the valve's controller output
  Where: a walkdown: read the positioner stroke indicator at several rates

- **Flow over the same period (a flow-duration curve)**
  How: Bin the flow into ranges and count the hours in each.
  Where: historian or DCS trend for FT-101 (no historian tag is mapped in this model for these)
  Where: site records: production rate records

- **Pump rated flow and head**
  Field scope: anchors
  Subject: P-1 (P-1)
  CAPACITY: absent
  DISCHARGE: absent
  Still needed for this subject: CAPACITY, DISCHARGE
  Remaining across subjects (including additional evidence): CAPACITY, DISCHARGE
  How: Copy the stated rated flow/head and units. These scalar fields do not establish a matching performance curve or actual operating duty.
  Where: the vendor datasheet: pump curve and rated duty point
  Where: the pump nameplate on P-1

- **Motor rating and speed**
  Field scope: anchors
  Subject: P-1 (P-1)
  HP: absent
  RPM: absent
  Still needed for this subject: HP, RPM
  Remaining across subjects (including additional evidence): HP, RPM
  How: Copy stated rated output and speed in their original units. Efficiency, identity and drive basis are separate review tasks.
  Where: the motor nameplate on P-1
  Where: maintenance records: motor record card

- **Static head versus friction head**
  How: Static head = lift plus pressure difference between source and destination; the rest of the pump head at duty is friction plus the valve drop.
  Where: a walkdown: elevations and pressures at the suction source and the delivery point
  Where: site records: line list or isometrics for pipe lengths and sizes

- **Matched pump curve, rated duty and system operating points**
  Candidate scope: anchors
  Supplied candidate facts; meaning and suitability unverified. The collection/review request remains open.
  No candidate values found in the selected model records.
  How: Retain supplied ratings as unverified candidates. Review the curve against pump identity, installed impeller, speed, fluid, axes/units and revision; distinguish rated duty, BEP and actual operating points. A rating, URI or readability flag does not establish a matching curve or system suitability.
  Where: the vendor datasheet: pump curve and rated duty point
  Where: the pump nameplate on P-1

- **Motor nameplate, efficiency and drive basis**
  Candidate scope: anchors
  Supplied candidate facts; meaning and suitability unverified. The collection/review request remains open.
  No candidate values found in the selected model records.
  How: Review existing nameplate or motor records for identity, rated shaft output in original units, speed, full-load efficiency and drive/bypass basis. HP/RPM alone do not establish efficiency or measured electrical input; retain missing or ambiguous evidence.
  Where: the motor nameplate on P-1
  Where: maintenance records: motor record card

Decision rule from the screen: Worth a drive quote when the valve normally runs well throttled for long hours and most of the head is friction rather than static lift (VSDs suit friction-dominated systems best). Close it if the valve normally runs near fully open, the head is mostly static, or the pump runs few hours.

Limits from the screen: On a hand-built model the valve sits on a stream leaving the pump. On an extracted drawing the links have no direction, so the rule takes a control valve within four drawn links that do not pass through other equipment; it may still be on a branch or the suction side, so check the drawing. IAC/ITAC figures are browse-page averages read through a summarizing fetch and not re-verified against the downloadable database; averages are skewed by outliers.

No answer recorded. The question remains visible.

## PUMP-NOTE@P-1: What does the supplied pump note state, and what remains unresolved?

State: **partial**; owner: **training-pump-owner**; present in current input: yes.

Owner assigned by training-coordinator on 2026-10-31.

- `pump-note`: **current**, accepted, partial; `supplied-head` = **12 m**.
  Invented source says12m; typed zero/false/null/unknown remain supplied records. BX-UNKNOWN is unmapped. Operating suitability is unresolved.
  Source: PUMP-NOTE, revision A, pump-note.txt lines2-8; supplied values and unresolved scope; SHA-256 `95511507159507c8b194e3fa542b1faa580c5ffbfa8488667814e5ff2483ecba`.
  Source match: match; plant truth: unknown; reviewer: training-source-reviewer, reviewed on: 2026-10-31; owner at decision: training-pump-owner.
  Note: Synthetic local source decision; no company authorization or observed plant truth.

## TANK-SERVICE@TK-1: What service is stated in the separate tank note?

State: **answered**; owner: **training-pump-owner**; present in current input: yes.

Owner assigned by training-coordinator on 2026-10-31.

- `tank-service`: **current**, accepted, answered; `service` = **water**.
  The separate invented tank note states water; installed service is not checked.
  Source: TANK-NOTE, revision A, tank-note.txt lines2-3; supplied service, plant check absent; SHA-256 `40ad4bca4f5e87aa9eab5e9216a45e45da417979e5b680389a60dd4666de53a8`.
  Source match: match; plant truth: unknown; reviewer: training-source-reviewer, reviewed on: 2026-10-31; owner at decision: training-pump-owner.
  Note: Synthetic local source decision; no company authorization or observed plant truth.

Immutable history: 2 decisions, 2 ownership assignments. Full old evidence snapshots are in context.json.

A repeated answer_id explicitly revises that answer. Independent answers need different answer ids. Different canonical values under one claim_key remain disputed until an engineer explicitly revises or rejects an answer. Prose wording is not compared for agreement.
