# Which configuration explains this machine archive?

**Worked source-investigation brief.** This is an AI-authored development example from published NIST records,
with no human engineering approval, assigned company recipient or measured benefit.

Work type: **Initial source investigation**. Disposition: **Partial evidence; deployment revision unresolved**.
Investigator, evidence owner, engineering reviewer/date and receiving owner: **Unassigned / not recorded**.

## One problem and one question

- Intended recipient: a controls/configuration or manufacturing-data owner who can provide the deployment record.
  **No actual recipient is assigned.**
- Question: **Which deployed device configuration and adapter mapping should interpret the selected Hurco04
  archive, and what evidence links that revision to the recording time?**
- Manual question reference: **SMS-CONFIG-FIRST** (a local label for this brief, not a generated finding).
- Source machine identities: `Hurco04`, UUID `mtc_adapter008` in both published configurations.
- Scope: establish the source-to-configuration link for interpretation. Current machine condition, production
  performance and equipment changes are outside this desk-based question.
- Generated-question catalog, asset model and context register: **Not used for this brief.**

## Evidence and qualified partial explanation

The original identities, immutable URLs, byte counts and SHA-256 hashes are retained in
[sources.json](sources.json). Keep those exact original files with the brief. The labels below identify published
snapshots; they do not identify a released or deployed company configuration.

| Original and exact location | What the cited record supports | What remains unresolved |
|---|---|---|
| `SMS-DEV-2016`, commit `1dab3278e05e4074c6cf3c5f167acce94f30a5a8`, `mtconnect/agent/Devices.xml`, physical lines 691-692 and 724 | The device has name/ID `Hurco04` and UUID `mtc_adapter008`. Within this revision, DataItem `Hurco04-path_7` has name `current_tool`, type `TOOL_NUMBER`, category `EVENT`. | Whether this configuration, or another one, was deployed during the selected recording. |
| `SMS-DEV-2017`, commit `968279f14ebe96c03c8877eeb1901cf6b4c8fbab`, same upstream path, physical lines 463-464 and 496 | The published device has the same name/ID and UUID. Within this later snapshot, `Hurco04-path_7` has name `Program_Runtime_Seconds`, type `ACCUMULATED_TIME`, category `SAMPLE`, units `SECOND`. | A shared DataItem ID cannot by itself establish a stable meaning across these revisions. No permanent tool-number/runtime alias is established. |
| `SMS-RAW-20170217`, same later commit, `raw/Hurco04/Hurco04-20170217-20170218.txt`, physical line 46; structure checked across all 363 lines | The exact row is `2017-02-17T09:18:51.4531250Z\|Program_Runtime_Seconds\|0`: timestamp, item name and literal value. The supplied raw file does not name a deployed `Devices.xml` revision. | The row identifies its signal by name. Associating it with a particular revision-scoped DataItem, units and deployment needs the configuration/mapping record. |

The published configurations show a real identifier-meaning change. The archive contains a runtime-named
observation, but these records do not establish the deployed configuration at that time. Matching a name to a
later XML snapshot does not supply the missing deployment evidence. The literal `0` is retained as a source value;
it is not interpreted here as a job result, missing value or present machine condition.

## Missing records and next owner

Request the device/agent configuration and adapter revision actually deployed for the selected recording, with
their effective interval and the record linking them to this archive. Ask for the reviewed mapping from raw item
names to revision-scoped DataItems, including units and missing-state semantics. Keep any unavailable or competing
records explicit rather than selecting a configuration from the filename or a reused ID.

Receiving owner, due date, next review date and handoff acceptance: **Unassigned / not set / not recorded**.
Next action: **Request those records from a controls/configuration or manufacturing-data owner.**
Source-review answer: **Partial; no governing revision or deployment link established**.
Trial: **Not run; benefit not measured**.

Keep the originals, source manifest, this brief and toolkit revision together. As colleagues contribute, take the
packet into the company's shared context and decision system so the mapping, evidence, reasons, responsible owner
and later revisions have a company home. The [plain brief](../../first-pilot/pilot-brief.md) supports that first
handoff. The optional local register example can demonstrate dependency refresh; it is not required to ask this
question or request its missing records.

Source credit: National Institute of Standards and Technology, Smart Manufacturing Systems Test Bed, official
`usnistgov/smstestbed` archive. The [intake guide](README.md#source-and-attribution) identifies the pinned reuse
notice and its qualifications. No original file is redistributed in this brief.
