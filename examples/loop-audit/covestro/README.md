# Start with a controls export that does not fit a simple loop list

An engineer may already have a vendor export and two drawings. The first useful result can be a precise question
about what those records establish. This example keeps a small source packet intact and prepares that question
for the controls owner.

The public DEXPI C08 Covestro example has **seven connection records around two system functions**. These are
engineering-tool example records, not a live DCS configuration or verified installed-plant data. They are not two
independently verified simple control loops. The collection was already inspected; this is a development intake
case within the existing DEXPI family, with no new accuracy score or generalization-matrix cell.

## Inspect the records

[connections.csv](connections.csv) transcribes every column in `COV PCS Connections List.xlsm`, `Sheet1!A1:S8`,
and adds the original sheet and row. Blank values stay blank, IDs stay strings and Excel report-date serials stay
as source text. Source column headings identify the original columns in order. No workbook macros are run.

| System function | Original rows | Connected technical items | What remains open |
|---|---|---|---|
| `COVPIL1-V999-LA01-U0001` | `Sheet1!2:5` | `P0001`, `L0001`, `F0001`, `Y0001` | Direction and logic are not established by this transcription. Rows 2–3 name `Legend Sheet 5 of 5` as the connected P&ID; rows 4–5 name `UER-2345678`. |
| `COVPIL1-V999-TA99-U0020` | `Sheet1!6:8` | `F0017`, `F0018`, `Y0015` | These three connections cannot be reduced to one measurement and one output without an interpretation. |

Keep the full identities in the CSV. A bare technical item is scoped by the industrial complex, process area and
subprocess area. The two sides retain separate `SP_ID` values, function fields and drawing references. `Branch`,
`Symbol` and the row-4 `SHH` value are source labels, not a logic specification produced by this toolkit.

The second source supports the identity check. The instrument list records `U0020`'s `Loop Function` as `C` at
`COV Instrument List.xlsm`, `Sheet1!J66`, agreeing with the connections report's `Function` at `G6:G8`.
`U0001` has `S` in both (`J8` and `G2:G5`). These codes do not supply a cause-and-effect specification.
The instrument list locates `U0001` on `UER-2345678` (`P8`); that does not establish why the connections report
references a legend for two connected items. Keep that as a request for context, not a demonstrated drawing fault.

## Check against the originals

With this repository's existing DEXPI cache, run offline with Python 3.10+ and the standard library:

```sh
python -S examples/loop-audit/covestro/check_sources.py
```

Without that cache, explicitly fetch only the three pinned originals (329,011 bytes total), then check:

```sh
python -S examples/loop-audit/covestro/check_sources.py --fetch --max-mb 1
```

`--cache PATH` selects another cache with the same directory layout. The optional fetch reuses the repository's
existing downloader and pins; it checks matching cached files without network. Network access to the original
host is still required when files are missing. After any requested fetch, a missing or mismatched original or
changed transcription refuses with exit 2. Success verifies exact source transcription and six cited instrument cells. It does not read the
drawings or establish a control strategy. [ACCEPTANCE.md](ACCEPTANCE.md) states the scope and checks.

## One first investigation

Copy this question and the source packet into the team's working documents or [pilot brief](../../first-pilot/pilot-brief.md):

> What reviewed logic and drawing revisions establish the inputs, outputs and intended behavior of
> `COVPIL1-V999-LA01-U0001`, including the two connections referred to the legend?

The public packet supports **partial evidence**: four connection rows and an instrument-list location. It supplies
no cause-and-effect matrix, function-block implementation, setpoints, approved test evidence or current governing
revision. Request those records from the controls/document owner and reconcile their asset identities. The owner,
reviewer, applicable site and resolution date remain **unassigned/unknown** in this example. Do not invent a
customer or an approval to finish the story.

The [filled first-question brief](first-question.md) assembles those ingredients into one draft handoff, including
the original fingerprints, exact cells, partial explanation, outstanding requests and **needs owner** status.
It demonstrates how to start the document; the main behavior question and actual recipient remain unresolved.

A useful next result is a reviewed explanation, or a specific unresolved discrepancy with a named recipient.
Record what evidence settled the question, what remains unknown and who takes it forward. An operating change
needs the site's own engineering and change process; this question supplies no equipment instruction.

The [question engine](../../../docs/OPPORTUNITY_SCREEN.md) helps identify investigations when a supported asset
model exists. It does not parse this workbook or infer its logic. Here a source-reading question is already
useful; the [pilot guide](../../first-pilot/README.md) accepts manually authored questions too. There is no need
to invent a model solely to obtain a generated finding ID.

## What the loop audit can do next

[loop_audit.py](../../../scripts/loop_audit.py) expects one supplied controller, measurement and output per row.
It checks a key's recorded symbols/signals, or only tag presence in an extracted model. It never validates
interlock logic. Do not split a function into fake duplicate controllers, omit extra connections, or call a tag
match a verified control loop. Once an engineer supplies an appropriate simple-loop list and corresponding
reviewed key/model, use the [existing loop-audit route](../README.md).

As colleagues add answers and revisions, put the packet and decisions in the company's shared context and decision
system. Keep the incumbent controls system responsible for execution. This example leaves a portable starting
packet; the receiving system must supply company access, authoritative revisions, ownership and decision history.
It introduces no company-governance application or ready hosted connector.

## Source and attribution

DEXPI initiative and contributing members, Covestro C08 example in
[TrainingTestCases at commit a23d61e](https://gitlab.com/dexpi/TrainingTestCases/-/tree/a23d61e2e089eb2ca464cd552f9ae580a2785963/dexpi%201.3/example%20pids/C08%20Two%20connected%20P%26IDs%20%28Covestro%29/C08V01),
licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The cached repository `LICENSE` is verified
alongside the two workbooks. Byte/SHA-256 pins are in [corpus_pins.json](../../../data/corpus_pins.json).
The CSV is a transcription with row locators added; the interpretation and investigation question were authored
for this example. Original workbooks and their macros are not redistributed here.
