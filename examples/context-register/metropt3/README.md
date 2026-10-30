# From a reported failure to a reviewable maintenance question

An anomaly flag and a maintenance note leave an engineer several questions: which asset and event, what was
actually done, which measurements mean what, and whether the observations support an effectiveness review.
This packet keeps those questions beside the original MetroPT-3 compressor records, with exact evidence and
concrete requests for the missing records. Read the [expected report](expected/context.md) without downloading data.

Six AI-authored questions have twelve proposed answers. Five questions need more data; the column-mapping
question remains partial. All six need an owner. Every response remains **proposed**, with **unknown plant truth**
and no human assignment, reviewer or approval. Suggested custodians identify where to request evidence; they
are not assigned owners. These are historical public records, not instructions to operate a train or compressor.

The sources are the actual description PDF and measurement CSV in the pinned UCI release. `MPT-APU` is an
authored scope for the APU described by that release, not a known serial number or verified current train.
There is no invented plant topology or cross-system asset join. [ACCEPTANCE.md](ACCEPTANCE.md) declares the checks
and prior observations. This is development evidence on a family already used by the historian matrix, not
a new source family, held-out result or maintenance-effectiveness finding.

## What stays separate

| Evidence | What the packet retains | What remains to collect |
|---|---|---|
| Description versus released measurements | The PDF reports 15,169,480 instances at 1 Hz, February-August 2020. The actual CSV has 1,516,948 data rows, timestamps through September 1, and nonuniform adjacent gaps (8/10/172918 seconds min/median/max). The first gaps are 10, 9 and 10 seconds. | Acquisition/export provenance, timebase/timezone and missing-span interpretation. No downsampling explanation, uniform resampling rule or healthy-state label is inferred. |
| Failure table identity | Rows 1 and 2 both print `#1`, with distinct April and May windows. Internal row ordinals stay distinct from printed report numbers. | Original event/work-record IDs and revisions, affected train/APU and their verified links. |
| May failure window and maintenance note | The second row reports May 29-30 but literally says `Maintenance on 30Apr at 12:00`. | Original execution record and date clarification. The packet does not change April to May or turn interval end into repair completion. |
| June/July maintenance notes | The reported windows and later named maintenance dates remain attributed table entries. | Work performed, actual completion/configuration and return-to-service disposition, then comparable before/after observations, a criterion and attributed effectiveness review. A maintenance note does not establish successful repair. |
| Signal meanings and recorded values | PDF items 6/7 enumerate motor current/oil temperature; the CSV puts `Oil_temperature` before `Motor_current`. Header spelling `DV_eletric` stays exact. | Reviewed name-to-meaning and plant-channel mapping. Positional pairing would swap meanings. |
| Electrical state | The first record has `COMP=1.0`, `DV_eletric=0.0` and `Motor_current=0.04`. The source definitions permit off or offloaded conditions. | Applicable configuration and time-aligned operating-state records. No unique mode, root cause or present asset state is inferred. |

The report's collection prompts say which record to request, the fields it needs and how the evidence would
settle the question. For an organization keeping execution in an existing system, return that system's record ID,
revision, affected asset, actual action/times/configuration and disposition with the observations. Review it through
the existing authority. The local register retains reasons and pending evidence; it provides no connector,
authenticated approval, task completion or causal effectiveness assessment.

## Run against the originals

From the repository root, explicitly fetch the pinned archive once, then extract its two exact members offline:

```sh
python -S scripts/fetch_corpus.py metropt3 --max-mb 250
python -S examples/context-register/metropt3/prepare_sources.py
```

The archive is about 218 MB; extraction adds another 218 MB. The checks also need space for disposable source
copies. The originals remain in the ignored cache. Preparation verifies the ZIP and member sizes/hashes,
preserves the original filenames and refuses to replace a changed or incomplete destination. Preserve such a
folder and choose a fresh one with `--out`; use that same folder as `--source-root` in subsequent commands.
There is no implicit download, repair, concurrent-writer lock or authenticated provenance.

Then run with standard-library Python, offline:

```sh
python -S scripts/context_register.py prepare --model examples/context-register/metropt3/model.json --questions examples/context-register/metropt3/questions.json --sources examples/context-register/metropt3/sources.json --source-root data/external/metropt3/context --out examples/context-register/metropt3/run
python -S scripts/context_register.py apply --model examples/context-register/metropt3/model.json --questions examples/context-register/metropt3/questions.json --sources examples/context-register/metropt3/sources.json --source-root data/external/metropt3/context --answers examples/context-register/metropt3/proposed_answers.csv --out examples/context-register/metropt3/run
python -S examples/context-register/metropt3/verify_sources.py
python -S examples/context-register/metropt3/check_packet.py
```

The first apply follows an empty prepared register. Later applies into `run` must include
`--register examples/context-register/metropt3/run/context.json`. Refresh with the current sources and no answer
CSV to assess staleness. Prepare a new evidence sheet into a fresh folder before recording a reviewed revision;
do not resubmit old fingerprints as new decisions. `prepare` refuses to overwrite an existing answer sheet.
See the [context guide](../../../docs/CONTEXT_REGISTER.md) for continuing versus deliberately forking history.

`verify_sources.py` checks both actual original hashes and independently computes the complete CSV profile. It
does not read the derived key or proposal CSV. Its default explicitly reports that PDF semantic checks were not
run. Add `--pdf-text` with the optional [render dependencies](../../../requirements-render.txt) installed to check
the three pages' text; the table's visual layout remains a separate check. Independent coding-agent source review
inspected all three rendered pages and the full CSV. This is not a person's sign-off.

`check_packet.py` uses actual prepare/apply CLIs in a temporary directory. It checks all twelve source bindings,
current report/history, unchanged repetition and preserved original bytes. Labelled synthetic PDF/CSV revisions
make exactly eight/four dependent answers stale; changing only the effectiveness collection request reopens its
two answers. Stale-answer resubmission and missing originals refuse without output changes. These synthetic byte
revisions do not represent new maintenance events. `--write` regenerates the two expected files after the checks.
Raw hashes bind whole documents, so even an unrelated change in a cited CSV reopens its dependent answers.

`source_key.json` is a derived transcription, not a substitute for missing originals. The committed
`expected/context.json` retains immutable local decisions and their evidence snapshots. Current means inputs
match that snapshot; it does not mean the 2020 equipment is currently verified. Real usability and engineering
effort still need an observed site pilot. The existing MetroPT anomaly-band result remains a failing development
result in the [matrix](../../../docs/GENERALIZATION.md); this packet changes no model, labels, method or score.

## Attribution

Dataset: N. Davari, B. Veloso, R. Ribeiro and J. Gama, *MetroPT-3 Dataset*, UCI Machine Learning Repository,
[doi:10.24432/C5VW3R](https://doi.org/10.24432/C5VW3R), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The [UCI source page](https://archive.ics.uci.edu/dataset/791/metropt+3+dataset) was checked on 2026-10-30.
The description cites Davari et al., DSAA 2021, [doi:10.1109/DSAA53316.2021.9564181](https://doi.org/10.1109/DSAA53316.2021.9564181),
and Veloso et al., *The MetroPT dataset for predictive maintenance*, Scientific Data 9, 764 (2022),
[doi:10.1038/s41597-022-01877-3](https://doi.org/10.1038/s41597-022-01877-3).
Those papers are references supplied by the original description, not separately verified evidence for this packet.
Original bytes remain unchanged. The packet adds selected transcriptions, computed released-file observations,
questions, collection requests and proposed interpretations under the same attribution license.
