# Engineering context register

Draft for engineering review. Source match and plant truth are separate explicit verdicts; unknown is never upgraded by this tool.

## BASIS@P-1: What pressure basis did E&I receive from Process, pending configuration review?

State: **partial**; owner: **training-controls-owner**; present in current input: yes.

Owner assigned by training-assignment-coordinator on 2026-10-31.

- `basis-source`: **current**, accepted, partial; `supplied-pressure-kPa` = **220 kPa**.
  Received Process revision B states 220 kPa; no logic/plant correction or suitability acceptance follows.
  Source: PROCESS-BASIS, revision B, process-basis revision B:L1-L4; SHA-256 `cb425dc294fcf498991b5e5cff5150c85d6ccb37126f2c1b731c882cad52d6cc`.
  Source match: match; plant truth: unknown; reviewer: training-source-reviewer, reviewed on: 2026-10-31; owner at decision: training-controls-owner.
  Note: Fictional local source/proposal record; no company authority or observed plant truth.

## LOOP@P-1: What measurement is named in the independent loop note?

State: **answered**; owner: **training-controls-owner**; present in current input: yes.

Owner assigned by training-assignment-coordinator on 2026-10-31.

- `loop-source`: **current**, accepted, answered; `listed-measurement` = **flow**.
  Independent loop note lists flow indication; actual configuration remains unknown.
  Source: LOOP-NOTE, revision A, loop-note.txt:L1-L3; SHA-256 `8f37eaca002bd7b7bdbdeda1df4773a2cf42e339e95d3306c8f6437e4e1b258d`.
  Source match: match; plant truth: unknown; reviewer: training-source-reviewer, reviewed on: 2026-10-31; owner at decision: training-controls-owner.
  Note: Fictional local source/proposal record; no company authority or observed plant truth.

## PROPOSAL@P-1: Which proposed pressure basis in kPa must the owner reconcile? Both options remain unresolved.

State: **unanswered**; owner: **needs owner**; present in current input: yes.

No answer recorded. The question remains visible.

Immutable history: 3 decisions, 2 ownership assignments. Full old evidence snapshots are in context.json.

A repeated answer_id explicitly revises that answer. Independent answers need different answer ids. Different canonical values under one claim_key remain disputed until an engineer explicitly revises or rejects an answer. Prose wording is not compared for agreement.
