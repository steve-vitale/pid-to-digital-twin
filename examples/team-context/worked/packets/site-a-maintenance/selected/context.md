# Engineering context register

Draft for engineering review. Source match and plant truth are separate explicit verdicts; unknown is never upgraded by this tool.

## MAINT@P-1: What inspection date does the independent Maintenance record state?

State: **partial**; owner: **training-maintenance-owner**; present in current input: yes.

Owner assigned by training-assignment-coordinator on 2026-10-31.

- `inspection-source`: **current**, accepted, partial; `stated-inspection-date` = **unknown**.
  Independent record leaves inspection date unspecified; actual inspection remains unknown.
  Source: INSPECTION-NOTE, revision A, inspection-note.txt:L1-L3; SHA-256 `9721180a211ddacd6204c1b25f9bf959bfab78ffdd283e248a0c901b8a4ee018`.
  Source match: match; plant truth: unknown; reviewer: training-source-reviewer, reviewed on: 2026-10-31; owner at decision: training-maintenance-owner.
  Note: Fictional local source/proposal record; no company authority or observed plant truth.

Immutable history: 1 decisions, 1 ownership assignments. Full old evidence snapshots are in context.json.

A repeated answer_id explicitly revises that answer. Independent answers need different answer ids. Different canonical values under one claim_key remain disputed until an engineer explicitly revises or rejects an answer. Prose wording is not compared for agreement.
