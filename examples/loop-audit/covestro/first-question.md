# A first question with partial evidence and no assigned owner

**Worked source-investigation brief.** This example is authored from the existing public Covestro records.
It shows a useful draft handoff, not a completed engineering review, site assignment or measured pilot.

Work type: **Initial source investigation**

Source-review disposition: **Partial evidence; intended behavior unresolved**

Handoff: **Needs owner; recipient acceptance not recorded**

## One problem and one question

- Intended recipient: a controls/document owner who can explain the supplied function records. **No actual recipient is assigned.**
- Scope: explain the records for `COVPIL1-V999-LA01-U0001`; no equipment instruction or operating change.
- Manual question reference: **C08-U0001-context** (a label for this example, not a generated finding ID).
- Question: **What reviewed logic and drawing revisions establish the inputs, outputs and intended behavior of
  `COVPIL1-V999-LA01-U0001`, including the two connections referred to the legend?**
- Asset model / context register: **Not used.** The source identities are sufficient to ask this document question.
- Investigator, engineering reviewer and review date: **Unassigned / not recorded.**

## Evidence and qualified partial explanation

The local source labels below refer to the original files in the **C08V01** example at DEXPI TrainingTestCases
commit `a23d61e2e089eb2ca464cd552f9ae580a2785963`. That collection revision does not identify a current governing
plant revision. The [intake guide](README.md#source-and-attribution) supplies attribution and the original location.

| Source label and original | Exact location | What the record says |
|---|---|---|
| C08-CONN: `COV PCS Connections List.xlsm` | `Sheet1!A2:S5` | Four connection records for full item tag `COVPIL1-V999-LA01-U0001`, scoped to industrial complex `COVPIL1`, process area `V999`, subprocess area `LA01`. Connected technical items are `P0001`, `L0001`, `F0001` and `Y0001` in that same scope. |
| C08-CONN | `Sheet1!Q2:Q3` | The connected P&ID field says `Legend Sheet 5 of 5` for the `P0001` and `L0001` records. |
| C08-CONN | `Sheet1!G2:G5` and `Q4:Q5` | Function is `S`; the `F0001` and `Y0001` records reference connected P&ID `UER-2345678`. |
| C08-INSTR: `COV Instrument List.xlsm` | `Sheet1!AP8`, `J8` and `P8` | The item tag is `COVPIL1-V999-LA01-U0001`, Loop Function is `S`, and P&ID is `UER-2345678`. |

**Qualified partial explanation:** these records agree on U0001's scoped identity and function label, and retain
four connections. The legend references are present in the export. They do not, by themselves, establish an
error, signal direction, logic, setpoint or intended behavior. A technical-item or function label is not a logic
specification. The main question remains unresolved.

The complete [connections.csv](connections.csv) preserves all seven records around both system functions,
including their separate `SP_ID` identities and blank fields. Do not replace it with only the four rows above.
The raw original fingerprints, also pinned in [corpus_pins.json](../../../data/corpus_pins.json), are:

| Original | Bytes | SHA-256 of unchanged source bytes |
|---|---:|---|
| `COV PCS Connections List.xlsm` | 249988 | `76e3757103f9204558e86e9290e55c986b7f26a95dc26e2997d3e3f1e32fd44b` |
| `COV Instrument List.xlsm` | 60373 | `b3efe5b9938846c667962a6129c8c2a11a95c9b8d314c5d6243c489d2fd1326f` |
| Collection `LICENSE` | 18650 | `7e7170e3cebf88a9f60c7b8421418323c09304da1af4d5e90f4da1dc1c8a2661` |

## Next evidence request and handoff

| Request | Why it remains open | Responsible person / due date |
|---|---|---|
| Applicable drawing revisions and an explanation of the two legend references | The supplied table does not explain their meaning; the drawings have not been reviewed in this brief. | Unassigned / not set |
| Reviewed cause-and-effect or function-block records, with relevant setpoints and test evidence | The export's connection and function labels do not define the intended behavior. | Unassigned / not set |
| Site/document owner and the applicable source authority | A public example and matching bytes do not establish current installed state or governing authority. | Unassigned / not set |

- Next action: identify the responsible controls/document owner and request those records; this action has **not been assigned or completed**.
- Current installed-state check and accountable authority: **Unknown.**
- Receiving owner and acceptance/date: **Unassigned — needs owner; not recorded.**
- Next review date: **Not set.** Revisit the explanation when the missing records or a changed source revision arrive.
- Pilot extension: **Trial not run; benefit not measured.** No baseline, observation or operating permission is implied.

Keep this brief, the complete transcription, unchanged originals and licence, and the toolkit revision used for
checking together in the team's chosen document location. Record that actual packet location and recipient when
assigned. This repository copy has no company destination or accepted handoff.

A colleague with a checkout can obtain just the three pinned originals and check the transcription from the
repository root (Python 3.10+, standard library; network needed only for missing originals):

```sh
python -S examples/loop-audit/covestro/check_sources.py --cache data/external/covestro-first-question --fetch --max-mb 1
```

Afterward, repeat offline against that same cache:

```sh
python -S examples/loop-audit/covestro/check_sources.py --cache data/external/covestro-first-question
```

The checker verifies exact source bytes, the complete transcription and six cited instrument cells. It does not
validate this prose, the drawings, control strategy or recipient acceptance. When adapting the
[blank brief](../../first-pilot/pilot-brief.md), retain unknowns until the responsible people supply evidence.
As several people rely on the result, transfer the packet into the company's shared context and decision system
under its access, ownership and review rules. The toolkit supplies the starting example and files; the company
system supplies ongoing stewardship. No receiving-system adapter or human adoption is demonstrated here.
