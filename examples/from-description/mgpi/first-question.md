# Worked first question: notification versus unloading shutdown

Work type: **Initial source investigation**. Local reference: `MGPI-MANUAL-01`.
Status: **Agent-authored draft; needs owner and source review**. Date: 2026-10-30.
This uses the existing [first-question brief](../../first-pilot/pilot-brief.md); it is not a question-engine finding.

**Question:** In the cited historical record, did the sodium hypochlorite level alarm stop unloading into bulk
storage, or notify operators? What evidence would settle that question for a company's current installation?

The CSB's [2017 MGPI report](https://www.csb.gov/file.aspx?DocumentId=6047), printed page 23 §5.2, describes the
level alarm as notification and states that detected deviations did not automatically stop the transfer.
The same section distinguishes downstream bulk-to-day-tank emergency stopping from unloading-to-bulk stopping.
Keep those endpoints separate. This is an agent's bounded source interpretation, awaiting human review.

| Evidence to retain or request | Identity and locator | State / owner |
|---|---|---|
| Historical narrative | Report `2017-01-I-KS`, December 2017, printed pp.7–8 §2.3 and p.23 §5.2; raw SHA-256 `2e8f0ef9db7b9c65b790dbb3c1a2f12f90a9a7051e531189b5868ce2c2e6a07e` | Pinned original available through the optional local fetcher; no human source reviewer recorded |
| Working interpretation | [Expanded-source model](model-expanded-source.json), [authored answer](answer.json), [V2 source inventory](v2/source_inventory.json) | Draft; tags such as `LI_HYPO` are project aliases |
| Current installed action and endpoints | Company's released cause-and-effect/control narrative, logic revision, signal mapping and applicable test records | Not supplied; receiving controls/document owner unassigned |
| Competing evidence and change history | Approved revisions, unresolved discrepancies and records that would reopen this answer | Not supplied; due date and reviewer unassigned |

**Qualified answer:** notification only is supported within the cited report-era scope. Present-day logic,
settings, protective functions and operating safety are unknown. Silence in these passages does not establish
that a pH sensor or any other unmentioned instrument is absent. The generated drawing and matching selected
facts do not establish installed behavior.

**Next action:** a receiving engineering/document owner should verify the bounded reading, select the relevant
company scope and request the released records and endpoint-specific evidence through its existing process.
Record that person's answer, exact revisions, unresolved differences, reviewer/date and next review trigger in
the company's maintained information and decision system. Reopen when a governing source or installed revision
changes. No recipient, acceptance, company import or operating action is recorded here.

**Trial not run; benefit not measured.** No baseline, observations or decision-maker are invented. The draft
remains a source-investigation handoff with **needs owner**, rather than a completed pilot. The separate
[claim-label exercise](../../../benchmarks/source-support-development.json) tests a scorer contract; it does not
review this brief, prove question usefulness or improve the question engine's current zero findings.
