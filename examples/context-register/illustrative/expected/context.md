# Engineering context register

Draft for engineering review. Source match and plant truth are separate explicit verdicts; unknown is never upgraded by this tool.

## pressure@P-101: What upper operating pressure do these documents specify?

State: **disputed**; owner: **needs owner**; present in current input: yes.

- `basis-pressure`: **current**, proposed, partial; `upper-operating-pressure` = **50 kPa**.
  Illustrative basis says 50 kPa; the conflicting note needs reconciliation.
  Source: BASIS, revision A, line 2; SHA-256 `e20e0c89e1f4147841f1f2d6144ff4e5aa119bf9c7eb81d13168271b0958c7ac`.
  Source match: unknown; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: ILLUSTRATIVE training record; no real person or plant review.

- `later-pressure`: **current**, proposed, partial; `upper-operating-pressure` = **60 kPa**.
  Illustrative note says 60 kPa. No governing document has been selected.
  Source: LATER-NOTE, revision B, line 2; SHA-256 `b0413ec04581fda66cb1184cdc6f22026d77c235c54bb2d39b5366dcb71652a3`.
  Source match: unknown; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: ILLUSTRATIVE training record; no real person or plant review.

## range@P-101: Has the normal operating range been checked against a trend?

State: **needs_data**; owner: **needs owner**; present in current input: yes.

- `range-request`: **current**, proposed, needs_data; `range-check` = **not checked**.
  Collect a representative trend and have an engineer check the range.
  Source: SERVICE, revision A, line 3; SHA-256 `b489ff65912ee117f69a0cca70fb3bb02c83d0d40f36e069a05ff22c5be61c20`.
  Source match: unknown; plant truth: unknown; reviewer: not recorded, reviewed on: not recorded; owner at decision: needs owner.
  Note: ILLUSTRATIVE training record; no real person or plant review.

## service@P-102: What service is named in the training sheet?

State: **answered**; owner: **Fictional training maintainer**; present in current input: yes.

Owner assigned by Fictional training coordinator on 2026-10-29.

- `service`: **current**, accepted, answered; `service` = **water**.
  The illustrative sheet names water service. This is only a source interpretation.
  Source: SERVICE, revision A, line 2; SHA-256 `b489ff65912ee117f69a0cca70fb3bb02c83d0d40f36e069a05ff22c5be61c20`.
  Source match: match; plant truth: unknown; reviewer: Fictional training reviewer, reviewed on: 2026-10-29; owner at decision: Fictional training maintainer.
  Note: ILLUSTRATIVE training record; no real person or plant review.

## walkdown@P-101: Has the equipment identity been checked in the plant?

State: **unanswered**; owner: **needs owner**; present in current input: yes.

No answer recorded. The question remains visible.

Immutable history: 4 decisions, 1 ownership assignments. Full old evidence snapshots are in context.json.

A repeated answer_id explicitly revises that answer. Independent answers need different answer ids. Different canonical values under one claim_key remain disputed until an engineer explicitly revises or rejects an answer. Prose wording is not compared for agreement.
