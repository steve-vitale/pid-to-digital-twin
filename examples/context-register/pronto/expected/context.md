# Engineering context register

Draft for engineering review. Source match and plant truth are separate explicit verdicts; unknown is never upgraded by this tool.

## CTX-01@PT312: What variable and unit does the report assign to PT312?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F01`: **current**, proposed, answered; `PT312.report-variable-and-unit` = **air delivery pressure; barg**.
  Table 2 assigns PT312 to air delivery pressure, with unit barg. This describes the report, not a verified present-day installation.
  Source: PRONTO-REPORT, revision zenodo-1341583-published-2019-05-16, PDF page 6 (printed 6), Table 2, PT312 row; SHA-256 `a6d5454113f86130af7f34c3fbebe1c5143d5e45ea6b10608c7c33fe961b5ba3`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-02@V10: What purpose does the report give manual valve V10 in the leakage experiment?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F02`: **current**, proposed, answered; `V10.report-purpose` = **induced input-air leakage to atmosphere**.
  The report says manually opening V10 leaks part of the input air to atmosphere to simulate developing air leakage.
  Source: PRONTO-REPORT, revision zenodo-1341583-published-2019-05-16, PDF page 11 (printed 11), Air leakage (0911 Test4/5/6), first paragraph; SHA-256 `a6d5454113f86130af7f34c3fbebe1c5143d5e45ea6b10608c7c33fe961b5ba3`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-03@PRONTO-FACILITY: Which air and water flow conditions does the report give for Test5?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F03`: **current**, proposed, answered; `Test5.report-flow-conditions` = **air 120 sm3/h; water 0.1 kg/s**.
  Table 6 gives Test5 air flow 120 sm3/h and water flow 0.1 kg/s. These are published test conditions, not current setpoints.
  Source: PRONTO-REPORT, revision zenodo-1341583-published-2019-05-16, PDF page 12 (printed 12), Table 6, Test5 column; SHA-256 `a6d5454113f86130af7f34c3fbebe1c5143d5e45ea6b10608c7c33fe961b5ba3`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-04@FIC301: Which input-measurement label is associated with FIC301 in each source, and is the pairing resolved?

State: **disputed**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F04`: **current**, proposed, partial; `FIC301.input-measurement-label` = **FT302**.
  Figure 1 draws FT302 beside FIC301 on the lower parallel air branch, joined by a dashed control-signal line. This figure alone does not establish the authoritative pairing or whether any FIR and FT identifiers are equivalent.
  Source: PRONTO-REPORT, revision zenodo-1341583-published-2019-05-16, PDF page 5 (printed 5), Figure 1, lower of the two green parallel inlet-air branches: FT302 and FIC301 with dashed signal line; SHA-256 `a6d5454113f86130af7f34c3fbebe1c5143d5e45ea6b10608c7c33fe961b5ba3`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

- `PRONTO-F18`: **current**, proposed, partial; `FIC301.input-measurement-label` = **FIR305**.
  Record 216 names FIC301 as Air Flowrate Controller via FIR305 (High). FIR305 is retained verbatim; this module description alone does not establish that it is an alias of FT305 or resolve the authoritative measurement pairing.
  Source: PRONTO-EVENTS-D3, revision zenodo-1341583-published-2019-05-16, Physical line 217 (header is line 1), record 216; Module and Module Description fields; SHA-256 `5b302d6c599c3550759824c11d17ba31db234014acab7df56500155ed7189961`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-05@FIC301: Which setpoint channel and unit does the report document for FIC301?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F05`: **current**, proposed, answered; `FIC301.report-setpoint-channel` = **FIC301/PID1/SP.CV; Sm3/h**.
  The report lists FIC301/PID1/SP.CV as inlet air flow rate controller 2 set point, in Sm3/h. It gives no current setpoint value here.
  Source: PRONTO-REPORT, revision zenodo-1341583-published-2019-05-16, PDF page 7 (printed 7), Table 2 continuation, FIC301/PID1/SP.CV row; SHA-256 `a6d5454113f86130af7f34c3fbebe1c5143d5e45ea6b10608c7c33fe961b5ba3`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-06@PT312: What Hi and HiHi values are entered for PT312, and what limits their interpretation?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F06`: **current**, proposed, answered; `PT312.settings-entered-HH-H` = **95; 90**.
  The workbook enters HiHi 95 and Hi 90 for PT312 (bar). G16 also says scale 0-15 bar and not enabled. Preserve the entered numbers and the scale inconsistency; do not turn them into enabled physical-pressure limits.
  Source: PRONTO-ALARMS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Sheet1', B16:D16 (tag, HiHi, Hi); remarks G16 must be read with the numbers; SHA-256 `07d019fbde971ace8ab389d0b30d229d2db9847a76d1b0cc71ede7b012522fb0`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-07@PT312: Does the settings workbook mark the PT312 limit row as enabled?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F07`: **current**, proposed, answered; `PT312.settings-enabled-state` = **not enabled**.
  G16 explicitly says not enabled. This negative control prevents treating numeric cells C16:F16 as enabled process alarms. It does not describe the separate historical module-health alarms.
  Source: PRONTO-ALARMS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Sheet1', B16 and G16; SHA-256 `07d019fbde971ace8ab389d0b30d229d2db9847a76d1b0cc71ede7b012522fb0`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-08@FIC301: Does the settings workbook support an enabled high limit for FIC301?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F08`: **current**, proposed, answered; `FIC301.settings-enabled-state` = **not enabled**.
  The row enters HiHi 100 and Hi 95, while G13 says air inputs; scale 0-4250, not enabled, no units. It supports no assertion that a high process alarm is enabled.
  Source: PRONTO-ALARMS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Sheet1', B13:D13 and G13; SHA-256 `07d019fbde971ace8ab389d0b30d229d2db9847a76d1b0cc71ede7b012522fb0`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-09@FT305: What does the settings workbook say about FT305 limit entries and enablement?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F09`: **current**, proposed, answered; `FT305.settings-enabled-state` = **not enabled**.
  The FT305 row enters HiHi 95, Hi 90, Lo 10 and LoLo 5. Its remark gives scale 0-200 sm3/h and not enabled. No conversion or enabled-limit inference has been made.
  Source: PRONTO-ALARMS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Sheet1', B15:F15 and G15; SHA-256 `07d019fbde971ace8ab389d0b30d229d2db9847a76d1b0cc71ede7b012522fb0`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-10@LI101: What LI101 level limits are entered, and does this row establish enablement?

State: **partial**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **LI101**
  Field: Obtain the alarm enable flags and configuration revision for LI101 from a controlled DeltaV export.
  How: The requested evidence resolves the stated unknown; no decision is accepted by this example.
  Where: controlled engineering record: Obtain the missing controlled source and its revision.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F10`: **current**, proposed, partial; `LI101.settings-entered-limits` = **HH 1.6; H 1.4; L 0.2; LL 0.1; m**.
  The LI101 (m) row enters HiHi 1.6, Hi 1.4, Lo 0.2 and LoLo 0.1. Its remark says water tank level, scale 0-2m. The absence of not enabled does not positively establish enablement; confirm against an authoritative configuration export.
  Source: PRONTO-ALARMS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Sheet1', B39:G39; SHA-256 `07d019fbde971ace8ab389d0b30d229d2db9847a76d1b0cc71ede7b012522fb0`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation. Obtain the alarm enable flags and configuration revision for LI101 from a controlled DeltaV export. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-11@TT402: Does TT402 have a documented enabled high-temperature process alarm?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **TT402**
  Field: Obtain TT402 enabled-state flags, measurement units and a controlled configuration revision.
  How: The requested evidence resolves the stated unknown; no decision is accepted by this example.
  Where: controlled engineering record: Obtain the missing controlled source and its revision.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F11`: **current**, proposed, needs_data; `TT402.settings-enabled-state` = **not stated**.
  The TT402 row enters HiHi 95, Hi 90, Lo 10 and LoLo 5 and describes mixing-zone temperature with scale 0-100 degrees C. No enabled flag is given in this row. Obtain configuration evidence before asserting enablement.
  Source: PRONTO-ALARMS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Sheet1', B19:G19; SHA-256 `07d019fbde971ace8ab389d0b30d229d2db9847a76d1b0cc71ede7b012522fb0`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation. Obtain TT402 enabled-state flags, measurement units and a controlled configuration revision. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-12@LI503: Which uncertainty in the LI503 settings row requires an engineering check?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **LI503**
  Field: Request the LI503 interface measurement basis, scaling and enabled-state flags from controlled configuration and instrument documentation.
  How: The requested evidence resolves the stated unknown; no decision is accepted by this example.
  Where: controlled engineering record: Obtain the missing controlled source and its revision.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F12`: **current**, proposed, needs_data; `LI503.settings-unit-certainty` = **source says not sure**.
  G41 describes the water-coalescer interface as in percentage and explicitly says not sure. The row enters HiHi 70, Hi 55, Lo 45 and LoLo 30. Its engineering basis and enablement remain unconfirmed.
  Source: PRONTO-ALARMS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Sheet1', B41:G41; SHA-256 `07d019fbde971ace8ab389d0b30d229d2db9847a76d1b0cc71ede7b012522fb0`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation. Request the LI503 interface measurement basis, scaling and enabled-state flags from controlled configuration and instrument documentation. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-13@PRONTO-FACILITY: What air flow condition is recorded for the 10:34 Test5_0 measurement?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F13`: **current**, proposed, answered; `Test5_0.ops-air-flow` = **120 sm^3/h**.
  The 2017-09-11 log names Air leakage, run 0911Test5_0, at 10:34 and records air flow 120 sm^3/h. It records a historical experiment condition.
  Source: PRONTO-OPS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Operation Log 0911', A11:C11 and G11:H11; date B1; SHA-256 `36676c5e73b91b0d029e96643d7b3f9d7748df802c367fe785cee16734a2ab82`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-14@PRONTO-FACILITY: What water flow condition is recorded for Test5_0?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F14`: **current**, proposed, answered; `Test5_0.ops-water-flow` = **0.1 kg/s**.
  The Test5_0 section records water flow rate 0.1 kg/s. It does not establish the current plant flow.
  Source: PRONTO-OPS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Operation Log 0911', G12:H12 in run 0911Test5_0 (B11); SHA-256 `36676c5e73b91b0d029e96643d7b3f9d7748df802c367fe785cee16734a2ab82`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-15@V10: Which first V10 movement is explicitly recorded in the day-3 log?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F15`: **current**, proposed, answered; `V10.ops-movement-20170911-1040` = **0 to 5 degree**.
  J18:M18 records Manual valve V10 at 10:40, from 0 to 5 degree on 2017-09-11. This is a log entry, not independent confirmation of valve travel.
  Source: PRONTO-OPS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Operation Log 0911', J18:M18; date B1; SHA-256 `36676c5e73b91b0d029e96643d7b3f9d7748df802c367fe785cee16734a2ab82`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-16@V10: Which next V10 movement is explicitly recorded in the day-3 log?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F16`: **current**, proposed, answered; `V10.ops-movement-20170911-1050` = **5 to 10 degree**.
  J27:M27 records Manual valve V10 at 10:50, from 5 to 10 degree on 2017-09-11.
  Source: PRONTO-OPS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Operation Log 0911', J27:M27; date B1; SHA-256 `36676c5e73b91b0d029e96643d7b3f9d7748df802c367fe785cee16734a2ab82`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-17@V11: Which valve is named in the opening field of Test5_0, and may it be silently joined to V10?

State: **partial**; owner: **needs owner**; present in current input: yes.

Collection prompts from the screen. These are not per-request completion records; an answer does not automatically satisfy or clear them.

- **V11**
  Field: Ask a qualified reviewer to reconcile the log fields against the experiment procedure; do not alias V11 to V10.
  How: The requested evidence resolves the stated unknown; no decision is accepted by this example.
  Where: controlled engineering record: Obtain the missing controlled source and its revision.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F17`: **current**, proposed, partial; `V11.ops-Test5_0-opening` = **0 deg**.
  The Valve opening field names V11 and 0 deg. This field provides no authority to alias V11 to V10; the packet retains V11 as a distinct ID.
  Source: PRONTO-OPS, revision zenodo-1341583-published-2019-05-16, Worksheet 'Operation Log 0911', F16:H16 in run 0911Test5_0 (B11); SHA-256 `36676c5e73b91b0d029e96643d7b3f9d7748df802c367fe785cee16734a2ab82`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation. Ask a qualified reviewer to reconcile the log fields against the experiment procedure; do not alias V11 to V10. AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-19@FIC302: What measurement label is named for FIC302 in the journal?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F19`: **current**, proposed, answered; `FIC302.journal-measurement-label` = **FIR302**.
  Record 1 names FIC302 as Air Flowrate Controller via FIR302 (Low). This is a module description in the journal; it does not resolve the separate Figure 1 label discrepancy or name a distinct output tag.
  Source: PRONTO-EVENTS-D3, revision zenodo-1341583-published-2019-05-16, Physical line 2 (header is line 1), record 1; Module and Module Description fields; SHA-256 `5b302d6c599c3550759824c11d17ba31db234014acab7df56500155ed7189961`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-20@FIC301: What FIC301 alarm state is recorded at 14:41:01.928 on day 3, and is it a process high-limit alarm?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F20`: **current**, proposed, answered; `FIC301.journal-state-record216` = **MODULE_ALM; ACT/UNACK; 15-CRITICAL**.
  Record 216 is an INSTRUMENT ALARM at 2017-09-11 14:41:01.928, parameter MODULE_ALM, state ACT/UNACK, level 15-CRITICAL. It is a historical module-health alarm record; it does not establish enablement of a process high-limit alarm.
  Source: PRONTO-EVENTS-D3, revision zenodo-1341583-published-2019-05-16, Physical line 217 (header is line 1), record 216; Date/Time*, Event Type, Category, Parameter, State and Level fields; SHA-256 `5b302d6c599c3550759824c11d17ba31db234014acab7df56500155ed7189961`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-21@FIC301: Which later FIC301 module-alarm state is recorded, without inferring present state?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F21`: **current**, proposed, answered; `FIC301.journal-state-record212` = **MODULE_ALM; INACT/UNACK**.
  Record 212 at 2017-09-11 14:41:41.928 records MODULE_ALM as INACT/UNACK. The file is reverse chronological; this later record does not make the present alarm state known.
  Source: PRONTO-EVENTS-D3, revision zenodo-1341583-published-2019-05-16, Physical line 213 (header is line 1), record 212; Date/Time*, Parameter and State fields; SHA-256 `5b302d6c599c3550759824c11d17ba31db234014acab7df56500155ed7189961`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

## CTX-22@PRONTO-FACILITY: What timing basis does the report give for joining process data and event records?

State: **partial**; owner: **needs owner**; present in current input: yes.

Decision rule from the screen: Retain the exact source statement. A qualified engineer must resolve disagreements and unknowns before using it as plant truth.

Limits from the screen: Illustrative AI-authored question and proposed answer. No assigned human owner, reviewer or sign-off.

- `PRONTO-F22`: **current**, proposed, answered; `PRONTO.report-data-grains` = **process 1 Hz continuous; logs event driven discrete**.
  Table 1 lists process variables as continuous 1 Hz DeltaV data and alarm/event/change logs as event-driven discrete DeltaV events. The two grains differ; a time join needs an explicit time policy.
  Source: PRONTO-REPORT, revision zenodo-1341583-published-2019-05-16, PDF page 6 (printed 6), Table 1, Process variables and Alarm/event/change logs rows; SHA-256 `a6d5454113f86130af7f34c3fbebe1c5143d5e45ea6b10608c7c33fe961b5ba3`.
  Source match: match; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: Illustrative AI-authored proposal; no human owner, reviewer, approval or plant-truth confirmation.  AI-authored re-proposal against expanded item evidence; prior proposal retained. No new human or plant review.

Immutable history: 44 decisions, 0 ownership assignments. Full old evidence snapshots are in context.json.

A repeated answer_id explicitly revises that answer. Independent answers need different answer ids. Different canonical values under one claim_key remain disputed until an engineer explicitly revises or rejects an answer. Prose wording is not compared for agreement.
