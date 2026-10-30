# Engineering context register

Draft for engineering review. Source match and plant truth are separate explicit verdicts; unknown is never upgraded by this tool.

## MPT-COLUMNS@MPT-APU: Which named CSV columns carry oil temperature and motor current?

State: **partial**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **Reviewed channel-to-meaning mapping**
  Field: Exact export column names and dictionary revision, engineering units and any transformation; explicitly check Oil_temperature and Motor_current against their names rather than the PDF enumeration.
  How: Compare the original header and source dictionary, then obtain the export owner's mapping verification before joining channels to plant identities. Keep the exact DV_eletric spelling.
  Where: CSV header, source dictionary and controlled channel-mapping record

Decision rule from the screen: Do not pair values by the PDF item order. Keep source definitions, literal column names and recorded values distinct.

Limits from the screen: Development packet. No human owner, approval, plant truth or effectiveness claim; suggested custodians are evidence locations, not assignments.

- `MPT-M07`: **current**, proposed, partial; `description.analogue-enumeration` = **item 6: Motor Current (A); item 7: Oil Temperature (C)**.
  The description enumerates Motor Current in amperes as item 6 and Oil Temperature in degrees Celsius as item 7. These are definitions in the PDF enumeration, not a verified plant channel mapping.
  Source: MPT-DESCRIPTION, revision uci-791/zip-aab991a970e58210, PDF page 2, Attribute Information, numbered items 6 (Motor Current) and 7 (Oil Temperature); SHA-256 `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

- `MPT-M08`: **current**, proposed, partial; `released-file.column-identities` = **H: Oil_temperature; I: Motor_current; K: DV_eletric**.
  The raw header places Oil_temperature before Motor_current and spells the electrical column DV_eletric. Preserve these names. These are literal file column identities; units and physical channel mapping need separate review.
  Source: MPT-CSV, revision uci-791/zip-aab991a970e58210, CSV physical line 1; named columns H:I (one-based, including the unnamed leading field), plus exact DV_eletric header; SHA-256 `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

- `MPT-M09`: **current**, proposed, partial; `released-file.first-record.analogue-values` = **Oil_temperature=53.60000000000001; Motor_current=0.04**.
  The first record contains these literal values under Oil_temperature and Motor_current respectively. These literal fields alone do not establish units, calibration or current plant truth.
  Source: MPT-CSV, revision uci-791/zip-aab991a970e58210, CSV physical lines 1-2; header H:I and first data record at timestamp 2020-02-01 00:00:00; SHA-256 `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## MPT-COVERAGE@MPT-APU: What time/population scope can the released CSV support?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **Release/export provenance and usable observation windows**
  Field: Original acquisition cadence, export/transformation history, unnamed-field meaning, timezone and documented missing intervals; reconcile the description with the released file.
  How: Ask the dataset or historian custodian for the versioned export recipe and original timebase. Retain the file profile as observations, without inferring downsampling or treating unreported periods as healthy.
  Where: Versioned acquisition/export records held by the data custodian

Decision rule from the screen: Separate published acquisition claims from released-file observations. Do not impose a uniform period, invent a timezone or silently interpolate gaps.

Limits from the screen: Development packet. No human owner, approval, plant truth or effectiveness claim; suggested custodians are evidence locations, not assignments.

- `MPT-M01`: **current**, proposed, needs_data; `description.acquisition-scope` = **15169480 instances; 1Hz; February-August 2020**.
  The description reports 15,169,480 instances/data points and acquisition at 1 Hz during February-August 2020. This is a documentation claim; the acquisition/export history is not verified here.
  Source: MPT-DESCRIPTION, revision uci-791/zip-aab991a970e58210, PDF pages 1-2; summary Number of Instances, Data Set Information and Attribute Information opening paragraph; SHA-256 `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

- `MPT-M02`: **current**, proposed, needs_data; `released-file.observed-scope` = **1516948 data rows; 17 fields; 2020-02-01 00:00:00 to 2020-09-01 03:59:50; gaps min/median/max 8/10/172918 s**.
  The actual release contains 1,516,948 data rows and 17 fields. Its timestamps run from 2020-02-01 00:00:00 to 2020-09-01 03:59:50 and strictly increase; adjacent gaps have minimum/median/maximum 8/10/172918 seconds. The first gaps are 10, 9 and 10 seconds. These are released-file observations, not a uniform period, timezone or explanation of the acquisition/export history.
  Source: MPT-CSV, revision uci-791/zip-aab991a970e58210, CSV physical lines 1-1516949; header and all timestamp fields, first/last records and adjacent-gap profile; SHA-256 `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## MPT-EFFECTIVENESS@MPT-APU: Is there enough evidence to review the June/July maintenance effectiveness?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **Intervention identity, comparable outcomes and attributed effectiveness review**
  Field: Verified work-record revision, affected asset and action/configuration; before/after operating conditions and exposure window; usable measurement coverage, chosen metric, uncertainty and dated reviewer disposition.
  How: First reconcile the original execution record with operations. Then prepare comparable observations under a defined criterion for an authorized reviewer. A copied completed status or maintenance note alone leaves insufficient evidence.
  Where: Maintenance, operations and measurement custodians in the existing execution system

Decision rule from the screen: Retain insufficient evidence until the intervention and comparable observations are linked and reviewed. Do not infer successful repair, root cause, downtime or causal improvement from the table.

Limits from the screen: Development packet. No human owner, approval, plant truth or effectiveness claim; suggested custodians are evidence locations, not assignments.

- `MPT-M05`: **current**, proposed, needs_data; `failure-table.row3.report` = **6/5/2020 10:00-6/7/2020 14:30; Air Leak; High stress; Maintenance on 8Jun at 16:00**.
  Table row 3 gives this reported failure interval and a maintenance note naming 8Jun at 16:00. The note lacks a year/timezone and does not identify the executed action or an effectiveness criterion/result. The interval end is not a verified repair-completion or return-to-service time.
  Source: MPT-DESCRIPTION, revision uci-791/zip-aab991a970e58210, PDF page 3, Failure Information table, data row 3, all six columns (printed Nr. #3); SHA-256 `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

- `MPT-M06`: **current**, proposed, needs_data; `failure-table.row4.report` = **7/15/2020 14:30-7/15/2020 19:00; Air Leak; High stress; Maintenance on 16Jul at 00:00**.
  Table row 4 gives this reported failure interval and a maintenance note naming 16Jul at 00:00. It does not establish which repair occurred, its configuration, actual completion, recovery or causal improvement. Comparable observations and attributed review remain missing.
  Source: MPT-DESCRIPTION, revision uci-791/zip-aab991a970e58210, PDF page 3, Failure Information table, data row 4, all six columns (printed Nr. #4); SHA-256 `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## MPT-EVENT-IDENTITY@MPT-APU: How are the two printed #1 failure records kept separate?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **Stable external event and asset identities**
  Field: Original failure/work-record IDs and revisions, affected train/APU identifier, event dates and links to this dataset release.
  How: Ask the failure-record custodian for the original records. Use document hash and table-row locator until a verified external identity is supplied; a printed number alone is insufficient.
  Where: Original failure reports or maintenance system, with its record custodian

Decision rule from the screen: Keep table rows 1 and 2 separate while preserving their identical printed number. Internal row ordinals are locators, not corrected report numbers.

Limits from the screen: Development packet. No human owner, approval, plant truth or effectiveness claim; suggested custodians are evidence locations, not assignments.

- `MPT-M03`: **current**, proposed, needs_data; `failure-table.printed-identities` = **row 1: #1, 4/18/2020 0:00-4/18/2020 23:59; row 2: #1, 5/29/2020 23:30-5/30/2020 6:00**.
  The first and second table rows both print #1 but have different reported time windows. Keep them as separate row-scoped records. This packet supplies neither a corrected report number nor verified external work-record or physical-asset identity.
  Source: MPT-DESCRIPTION, revision uci-791/zip-aab991a970e58210, PDF page 3, Failure Information table, data rows 1-2 including Nr., Start Time and End Time; SHA-256 `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## MPT-MAY-WORK@MPT-APU: What intervention, if any, belongs to the May 29-30 reported interval?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **Original execution record and date clarification**
  Field: Work-record ID/revision, affected APU, work performed, actual start/completion, year/timezone, resulting configuration and return-to-service disposition; clarify the literal 30Apr note.
  How: Request the original work record and date clarification from its custodian. Preserve both the May interval and April note until reviewed evidence explains their relationship.
  Where: Maintenance execution record and operational return-to-service record

Decision rule from the screen: Do not change April to May, equate a reported interval ending with repair completion, or infer which work was executed.

Limits from the screen: Development packet. No human owner, approval, plant truth or effectiveness claim; suggested custodians are evidence locations, not assignments.

- `MPT-M04`: **current**, proposed, needs_data; `failure-table.row2.report` = **5/29/2020 23:30-5/30/2020 6:00; Air Leak; High stress; Maintenance on 30Apr at 12:00**.
  Table row 2 reports a May 29-30 air-leak interval and separately says Maintenance on 30Apr at 12:00. Preserve both literal dates. The note does not establish a May repair completion, performed work, resulting configuration, timezone or return to service; the original execution record and date clarification are needed.
  Source: MPT-DESCRIPTION, revision uci-791/zip-aab991a970e58210, PDF page 3, Failure Information table, data row 2, all six columns (printed Nr. #1); SHA-256 `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## MPT-MODE@MPT-APU: Does the first recorded electrical state identify a unique operating mode?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **Time-aligned operating-state and configuration evidence**
  Field: Applicable control/configuration revision, timestamp/timezone mapping, state transitions and operational observations distinguishing off from offloaded conditions.
  How: Ask the controls/operational counterpart to reconcile the state timing and applicable configuration. Retain raw flags and motor-current values without assigning a unique operating mode.
  Where: Applicable controls export and operational state/event records

Decision rule from the screen: A source-described COMP/DV flag combination permits more than one condition. A near-zero current is an observation, not a verified unique mode or failure diagnosis.

Limits from the screen: Development packet. No human owner, approval, plant truth or effectiveness claim; suggested custodians are evidence locations, not assignments.

- `MPT-M10`: **current**, proposed, partial; `description.COMP.meaning` = **active: no air intake; compressor off or offloaded**.
  The description says an active COMP intake-valve signal indicates no air intake and permits either off or offloaded operation. It does not select one of those conditions for the observed record.
  Source: MPT-DESCRIPTION, revision uci-791/zip-aab991a970e58210, PDF page 2, Attribute Information, item 8 COMP, complete definition; SHA-256 `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

- `MPT-M11`: **current**, proposed, partial; `description.DV-electric.meaning` = **active: under load; inactive: off or offloaded**.
  The description associates active DV electric with under-load operation and inactive with off or offloaded operation. This published meaning does not verify the applicable configuration or a unique observed mode.
  Source: MPT-DESCRIPTION, revision uci-791/zip-aab991a970e58210, PDF page 3, Attribute Information, item 9 DV electric, complete definition; SHA-256 `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

- `MPT-M12`: **current**, proposed, needs_data; `released-file.first-record.electrical-values` = **2020-02-01 00:00:00; Motor_current=0.04; COMP=1.0; DV_eletric=0.0**.
  The first record has Motor_current 0.04, COMP 1.0 and DV_eletric 0.0. Keep those raw observations. They do not by themselves identify a unique mode, failure cause or current asset condition; applicable control logic and time-aligned operating evidence are still needed.
  Source: MPT-CSV, revision uci-791/zip-aab991a970e58210, CSV physical lines 1-2; timestamp and named Motor_current, COMP, DV_eletric columns; SHA-256 `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: AI-authored development proposal; no human owner, assignment, reviewer, approval or effectiveness verdict. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

Immutable history: 24 decisions, 0 ownership assignments. Full old evidence snapshots are in context.json.

A repeated answer_id explicitly revises that answer. Independent answers need different answer ids. Different canonical values under one claim_key remain disputed until an engineer explicitly revises or rejects an answer. Prose wording is not compared for agreement.
