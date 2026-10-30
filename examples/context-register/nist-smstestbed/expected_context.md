# Engineering context register

Draft for engineering review. Source match and plant truth are separate explicit verdicts; unknown is never upgraded by this tool.

## SMS-DEPLOYED-REVISION@mtc_adapter008: Which configuration revision was deployed during the recorded capture?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **mtc_adapter008**
  Field: Request the configuration and adapter deployment record applicable to the 2017-02-17 capture; a later Git commit date does not supply a deployment date.
  How: Resolve the specific unknown before using this historical draft as operating knowledge.
  Where: controlled engineering record: Applicable configuration, deployment or collection record.

Decision rule from the screen: Retain version-scoped source observations and explicit unknowns. An engineer must supply applicable controlled evidence and review.

Limits from the screen: AI-authored illustrative question; no assigned human owner, reviewer or approval.

- `SMS-N09`: **current**, proposed, needs_data; `capture.deployed-configuration-revision` = **unknown**.
  This raw file contains timestamp, item name and value records. It contains no UUID or deployed configuration revision. Its Hurco04 path and signal names provide a bounded document association, while the configuration active at capture remains unknown.
  Source: SMS-RAW-20170217, revision git-968279f14ebe96c03c8877eeb1901cf6b4c8fbab, Whole 363-line archived raw file; three pipe-delimited fields per line; exact example at physical line 81; SHA-256 `093a80ace21094a6c164e5ab8879ffd893c90fdf5902e18677f57d8bfa679b6a`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation. Request the configuration and adapter deployment record applicable to the 2017-02-17 capture; a later Git commit date does not supply a deployment date.

## SMS-EXECUTION-GAPS@mtc_adapter008: Do these raw records establish a named job and complete execution-state coverage?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **mtc_adapter008**
  Field: Obtain the collection completeness policy and a controlled job/execution record before asserting production status or a named job.
  How: Resolve the specific unknown before using this historical draft as operating knowledge.
  Where: controlled engineering record: Applicable configuration, deployment or collection record.

Decision rule from the screen: Retain version-scoped source observations and explicit unknowns. An engineer must supply applicable controlled evidence and review.

Limits from the screen: AI-authored illustrative question; no assigned human owner, reviewer or approval.

- `SMS-N08`: **current**, proposed, needs_data; `raw.program-status.recorded-evidence` = **blank running name; READY; later UNAVAILABLE**.
  At 09:18:51.4531250Z the running-program field is a single blank space and Program_Status is READY. At 09:40:46.755688Z Program_Status is UNAVAILABLE. These sparse records do not establish a named production job or uninterrupted execution-state coverage.
  Source: SMS-RAW-20170217, revision git-968279f14ebe96c03c8877eeb1901cf6b4c8fbab, Physical lines 37, 45 and 359; Program_Name_Running and Program_Status records; SHA-256 `093a80ace21094a6c164e5ab8879ffd893c90fdf5902e18677f57d8bfa679b6a`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation. Obtain the collection completeness policy and a controlled job/execution record before asserting production status or a named job.

## SMS-IDENTITY@mtc_adapter008: Which published machine identity joins the two device configurations?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain version-scoped source observations and explicit unknowns. An engineer must supply applicable controlled evidence and review.

Limits from the screen: AI-authored illustrative question; no assigned human owner, reviewer or approval.

- `SMS-N01`: **current**, proposed, answered; `machine.identity.at-2016-config` = **Hurco04; mtc_adapter008; Hurco; VMX24**.
  The 2016 configuration identifies device Hurco04 with UUID mtc_adapter008 and description Hurco VMX 24 #4, manufacturer Hurco, model VMX24. This is the published configuration identity.
  Source: SMS-DEV-2016, revision git-1dab3278e05e4074c6cf3c5f167acce94f30a5a8, Physical lines 691-692; MTConnectDevices/Devices/Device[@id='Hurco04'] attributes and Description; SHA-256 `c696155196da9a783efc1f5be6618db561a4f5a6dc8998a1120c3077e60c9998`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation.

- `SMS-N02`: **current**, proposed, answered; `machine.identity.at-later-config` = **Hurco04; mtc_adapter008; Hurco; VMX24**.
  The later configuration also identifies Hurco04 with UUID mtc_adapter008, manufacturer Hurco and model VMX24. Matching published identities support a document join; they do not prove which configuration was deployed during the archived recording.
  Source: SMS-DEV-2017, revision git-968279f14ebe96c03c8877eeb1901cf6b4c8fbab, Physical lines 463-464; MTConnectDevices/Devices/Device[@id='Hurco04'] attributes and Description; SHA-256 `bb54e4eca7b65e50b026d02b785c3f905b66bd38493456569272540296f68166`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation.

## SMS-OLD-FEED-SEMANTICS@mtc_adapter008: Which feed-rate semantic uncertainty remains in the older configuration?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **mtc_adapter008**
  Field: Confirm the actual-versus-commanded measurement semantics from an applicable controlled adapter/configuration record; no person is assigned by this example.
  How: Resolve the specific unknown before using this historical draft as operating knowledge.
  Where: controlled engineering record: Applicable configuration, deployment or collection record.

Decision rule from the screen: Retain version-scoped source observations and explicit unknowns. An engineer must supply applicable controlled evidence and review.

Limits from the screen: AI-authored illustrative question; no assigned human owner, reviewer or approval.

- `SMS-N10`: **current**, proposed, needs_data; `Hurco04-path_10.uncertainty.at-2016-config` = **source comment Actual?**.
  The 2016 feed_rate data item is typed PATH_FEEDRATE with subtype ACTUAL and units MILLIMETER/SECOND, but the same source line retains an Actual? comment. The packet preserves that author uncertainty and does not assign an owner from a comment.
  Source: SMS-DEV-2016, revision git-1dab3278e05e4074c6cf3c5f167acce94f30a5a8, Physical line 727; Device[@id='Hurco04']//DataItem[@id='Hurco04-path_10'] and its trailing Actual? XML comment; SHA-256 `c696155196da9a783efc1f5be6618db561a4f5a6dc8998a1120c3077e60c9998`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation. Confirm the actual-versus-commanded measurement semantics from an applicable controlled adapter/configuration record; no person is assigned by this example.

## SMS-RAW-SPINDLE@mtc_adapter008: Which spindle-speed value is actually recorded at the selected timestamp?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain version-scoped source observations and explicit unknowns. An engineer must supply applicable controlled evidence and review.

Limits from the screen: AI-authored illustrative question; no assigned human owner, reviewer or approval.

- `SMS-N06`: **current**, proposed, answered; `raw.Spindle_Speed.at-20170217T092608` = **1000.000000**.
  The archived Hurco04 file records 2017-02-17T09:26:08.0468750Z \| Spindle_Speed \| 1000.000000. The raw record supplies no unit or deployed configuration revision; those remain separate source questions.
  Source: SMS-RAW-20170217, revision git-968279f14ebe96c03c8877eeb1901cf6b4c8fbab, Physical line 81; pipe-delimited timestamp, item name and value; source path raw/Hurco04/Hurco04-20170217-20170218.txt; SHA-256 `093a80ace21094a6c164e5ab8879ffd893c90fdf5902e18677f57d8bfa679b6a`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation.

## SMS-REUSED-ID@mtc_adapter008: What does Hurco04-path_7 mean in each configuration revision?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain version-scoped source observations and explicit unknowns. An engineer must supply applicable controlled evidence and review.

Limits from the screen: AI-authored illustrative question; no assigned human owner, reviewer or approval.

- `SMS-N03`: **current**, proposed, answered; `Hurco04-path_7.meaning.at-2016-config` = **current_tool; TOOL_NUMBER; EVENT**.
  In the 2016 document, Hurco04-path_7 is named current_tool and has type TOOL_NUMBER in category EVENT. This meaning is scoped to this configuration revision.
  Source: SMS-DEV-2016, revision git-1dab3278e05e4074c6cf3c5f167acce94f30a5a8, Physical line 724; Device[@id='Hurco04']//DataItem[@id='Hurco04-path_7']; SHA-256 `c696155196da9a783efc1f5be6618db561a4f5a6dc8998a1120c3077e60c9998`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation.

- `SMS-N04`: **current**, proposed, answered; `Hurco04-path_7.meaning.at-later-config` = **Program_Runtime_Seconds; ACCUMULATED_TIME; SAMPLE; SECOND**.
  In the later document, Hurco04-path_7 is named Program_Runtime_Seconds, type ACCUMULATED_TIME, category SAMPLE, unit SECOND. Reusing the ID across revisions does not make tool number and elapsed runtime equivalent signals.
  Source: SMS-DEV-2017, revision git-968279f14ebe96c03c8877eeb1901cf6b4c8fbab, Physical line 496; Device[@id='Hurco04']//DataItem[@id='Hurco04-path_7']; SHA-256 `bb54e4eca7b65e50b026d02b785c3f905b66bd38493456569272540296f68166`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation.

## SMS-SPINDLE-DEFINITION@mtc_adapter008: How does the later configuration define the spindle-speed field?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain version-scoped source observations and explicit unknowns. An engineer must supply applicable controlled evidence and review.

Limits from the screen: AI-authored illustrative question; no assigned human owner, reviewer or approval.

- `SMS-N05`: **current**, proposed, answered; `Hurco04-C_1.definition.at-later-config` = **Spindle_Speed; ROTARY_VELOCITY; ACTUAL; REVOLUTION/MINUTE**.
  The later document names Hurco04-C_1 Spindle_Speed, type ROTARY_VELOCITY, subtype ACTUAL, with units REVOLUTION/MINUTE and Source spindle_speed. This supplies this document revision's measurement definition.
  Source: SMS-DEV-2017, revision git-968279f14ebe96c03c8877eeb1901cf6b4c8fbab, Physical lines 473-475; Device[@id='Hurco04']//DataItem[@id='Hurco04-C_1'] attributes and Source; SHA-256 `bb54e4eca7b65e50b026d02b785c3f905b66bd38493456569272540296f68166`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation.

## SMS-UNAVAILABLE@mtc_adapter008: How should unavailable and zero observations stay distinct?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain version-scoped source observations and explicit unknowns. An engineer must supply applicable controlled evidence and review.

Limits from the screen: AI-authored illustrative question; no assigned human owner, reviewer or approval.

- `SMS-N07`: **current**, proposed, answered; `raw.Spindle_Speed.unavailable-versus-zero` = **UNAVAILABLE at 2017-02-14T16:12:54.968217Z; 0 at 2017-02-17T09:18:51.4531250Z**.
  Line 3 records Spindle_Speed as UNAVAILABLE. Line 34 records a numeric 0 at a different timestamp. Preserve both values and their times; the unavailable observation cannot be replaced with zero. The filename date range also does not bound every timestamp in this file.
  Source: SMS-RAW-20170217, revision git-968279f14ebe96c03c8877eeb1901cf6b4c8fbab, Physical lines 3 and 34; Spindle_Speed records at 2017-02-14T16:12:54.968217Z and 2017-02-17T09:18:51.4531250Z; SHA-256 `093a80ace21094a6c164e5ab8879ffd893c90fdf5902e18677f57d8bfa679b6a`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored development proposal; no human owner, assignment, reviewer, approval or plant-truth confirmation.

Immutable history: 10 decisions, 0 ownership assignments. Full old evidence snapshots are in context.json.

A repeated answer_id explicitly revises that answer. Independent answers need different answer ids. Different canonical values under one claim_key remain disputed until an engineer explicitly revises or rejects an answer. Prose wording is not compared for agreement.
