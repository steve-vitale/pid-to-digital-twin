# Known role, unresolved equipment placement

This example preserves known instrument and valve roles, and controller references, when a DEXPI reader
cannot find the owning equipment. It contains two complete deterministic reader models from actual public
DEXPI TrainingTestCases XML exports and their expected graphs. No model service is used.

Before the repair, graph export changed both `FT-04` (an instrument) and `FV-04` (a final control element)
into generic line items, despite the reader retaining their roles. It also left the controller's explicit
`measurement_unplaced` and `output_unplaced` references as attributes without typed graph edges. The repaired
export keeps those roles and represents `FT-04 -> FIC-04 -> FV-04` with controls edges. Missing equipment
placement remains unresolved. These are source interpretations requiring review, with unverified status;
they establish neither operational plant truth nor independently confirmed physical signal direction.

Run from the repository root, Python 3.10+, standard library only:

```sh
python examples/graph-export/unplaced-dexpi/check_packet.py --check
```

This works from a clean clone without accounts, network, downloaded XML or commercial tools. It reproduces
both expected graphs, validates them, checks the readable role statements, and exercises six labelled
synthetic refusal controls. Invalid controller references leave an existing output file unchanged. An
explicit unknown role remains generic; the older model format's no-role valve fallback is retained.
Temporary mutation files stay under ignored `.work/` and are removed after the check. No packet input is changed.

Expected output includes:

```text
PASS: 2 complete derived models reproduce exact graphs; types, references, sources, statements and unknown placement retained
PASS: 6 synthetic refusal controls preserve existing output; explicit unknown and legacy fallback retained
NOT CHECKED: original XML bytes/locators; add --verify-originals after the documented fetch
```

The committed models are derived evidence for this graph conversion check. To verify the original XML bytes,
primary locators and whole reader conversion as well, use the existing pinned public-source fetcher and then
the optional check:

```sh
python scripts/fetch_corpus.py dexpi-ttc-all
python examples/graph-export/unplaced-dexpi/check_packet.py --verify-originals
```

The fetcher downloads the existing full pinned TrainingTestCases corpus (about 92 MB unpacked). The packet
checker never downloads anything. Missing or changed originals cause the optional check to fail clearly.
It independently parses XML IDs/classes/associations using ElementTree, checks physical line locators, and
then requires complete regenerated reader models to equal the committed models. No source XML is redistributed.

| Case and original | Primary locators and retained result |
|---|---|
| [I04V01-VER.EX01, DEXPI 1.3](https://gitlab.com/dexpi/TrainingTestCases/-/blob/a23d61e2e089eb2ca464cd552f9ae580a2785963/dexpi%201.3/example%20pids/I04%20Measurement%20and%20Control/I04V01-VER.EX01.xml) | `GlobeValve-1` (line 29), operated by `ActuatingSystem-1` through `OperatedValveReference-1`; `ProcessSignalGeneratingFunction-1` (line 74) is located in `FlowMeasuringElement-1`. `MeasuringLineFunction-1` and `SignalLineFunction-1` (lines 78/82) record the logical reference chain. Reader tags are `FV-04`, `FT-04`, `FIC-04`. No equipment exists in this file; both unplaced roles and their reasons remain. Graph: 6 nodes, 9 edges, 83 claims. |
| [I01V01-SAG.EX01, DEXPI 1.2](https://gitlab.com/dexpi/TrainingTestCases/-/blob/a23d61e2e089eb2ca464cd552f9ae580a2785963/dexpi%201.2/example%20pids/I01%20Measurement/I01V01-SAG.EX01.xml) | `ProcessInstrumentationFunction` ID `XMP_6` (line 1149), and its nested `InformationFlow` ID `XMP_18` (line 1282), declare instrument classes. Neither has an Association; the reader cannot locate the sensor. `XMP_6` stays an instrument, variable `unknown`, unit `null`, reason `no sensor location in the file`. Equipment elsewhere does not justify assigning it. Graph: 4 nodes, 2 edges, 730 claims. |

Exact byte hashes, source URLs, cache paths, element attributes, associations, line locators and manually
specified assertions are in [source_key.json](source_key.json). The files' original exporter names are
recorded in the models' `meta.dexpi_file.OriginatingSystem` as source provenance. The source's own IDs are
kept; `XMP_6` is an ID fallback, not a newly established operating tag.

The readable identity statements include “FT-04 is an instrument”, “FV-04 is a final control element” and
“XMP_6 is an instrument”. The graph still carries the original source, unplaced reference fields and
placement reasons. No owning-equipment edge is added to these three items. The packet does not promote
`unknown` variable to level merely because other source properties include level-related text; correcting
that reader interpretation is separate work.

The optional larger diagnostic uses only the already fetched originals:

```sh
python examples/graph-export/unplaced-dexpi/audit_corpus.py
```

It checks every original XML against the repository's existing byte pins and examines the same 220 DEXPI
1.2/1.3 files already seen during diagnosis. It reproduces 214 reader models and independently confirms the
same six duplicate-ID refusals in the XML. Among 88 unplaced items in 56 models, the old graph role rule
would downgrade 87; the repaired graph downgrades zero. The 44 controller references absent as controls edges
before the repair are now retained, with no new graph errors. The script reconstructs the small old role
rule and checks the references explicitly; it does not run an old extractor or a new extraction benchmark.
All current graphs are built through `graph_export.build` and validated.

[ACCEPTANCE.md](ACCEPTANCE.md) records criteria declared before saving expected graphs and measurements for
this packet. Source examples and the corpus baseline were already examined: this is a seen-data diagnostic
of retained reader meaning, not held-out evidence, independent engineering truth, or drawing extraction
accuracy. It changes no generalization-matrix criterion. The six malformed original exports still refuse.
No person has approved these outputs or supplied plant data.

The DEXPI initiative and contributing members published TrainingTestCases at commit
`a23d61e2e089eb2ca464cd552f9ae580a2785963` under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
The [original LICENSE](https://gitlab.com/dexpi/TrainingTestCases/-/blob/a23d61e2e089eb2ca464cd552f9ae580a2785963/LICENSE)
has SHA-256 `7e7170e3cebf88a9f60c7b8421418323c09304da1af4d5e90f4da1dc1c8a2661`.
Credit: DEXPI example P&IDs from the DEXPI TrainingTestCases repository, DEXPI initiative and contributing
members, CC BY 4.0. Changes: XML converted to this repository's complete reader models, graph projections
and selected assertions. Those derived models, graphs and source-key material are shared under CC BY 4.0;
the checker code uses the repository's MIT license. This does not imply upstream endorsement.
