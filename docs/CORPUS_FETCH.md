# Fetching more public historian data

**Why it matters:** tools tested on one dataset can fail quietly on the next. The historian tools here were built and
checked on the Braatz Tennessee Eastman runs only; these sources test them on data they were not built on.

`scripts/fetch_corpus.py SOURCE [--max-mb N]` downloads a pinned subset of one public source into
`data/external/<source>/` (gitignored, never committed) and writes `FETCH_RECEIPT.json` there: what was fetched, bytes,
SHA-256, license, and anything skipped with the reason. Stdlib only; nothing is installed and no downloaded code is
run. Every file is pinned (record listing: name, size, published checksum; each file: size, CRC-32 where the zip gives
one, and a SHA-256 recorded on the first fetch, 2026-10-29). A file that no longer matches its pin is refused, not
saved. `--max-mb` (default 500) caps what one run may download. Tests: `python scripts/test_fetch_corpus.py`
(offline; no network).

| Source | License | Fetched by default | What it tests |
|---|---|---|---|
| `pronto` | CC BY 4.0 | 7 files of one 1.72 GB zip, 4.0 MB downloaded (13.9 MB unpacked) | Historian bands and the replay server on real pilot-plant data (not simulated, not TE), with the plant's own alarm journal and operator log |
| `dtu-te` | CC0 1.0 | `Readme.html` only (8 KB) | Would test historian bands across TE operating modes; the data is skipped (below) |
| `dexpi-ttc-all` | CC BY 4.0 | all 634 members of the pinned commit, one SHA-256 each (92 MB unpacked) | DEXPI reader and loop audit on four commercial tools' DEXPI 1.2 exports and the 1.3 single-feature cases (matrix rows 7 and 4) |
| `hai` | CC BY-SA 4.0 | boiler graphs, HAI 21.03 train1/test1/test4, README, technical PDF (45 MB) | Historian bands on a real control testbed with labelled attacks (row 6); DCS loop candidates (row 4, needs a person) |
| `skab` | GPL-3.0, **local use only** | 35 CSV + LICENSE + READMEs (4.4 MB) | Historian bands on a real pump/valve rig (row 6). Never vendored: no derived CSV, figure or sample is committed; the matrix converts it into a temporary folder only |
| `pronto-more` | CC BY 4.0 | 7 more members of the pinned PRONTO zip (test days 2 and 4, technical report) | Historian bands on two more test days of the same rig (row 6) |
| `idaes-hda` | IDAES BSD-style | 7 files of IDAES/examples at a pinned commit | Exports (row 5) from a flowsheet nobody here wrote |
| `dwsim-fossee` | CC BY-SA 4.0 | 42 flowsheet project zips (inner flowsheet pinned too) | Exports (row 5) from 42 independent student flowsheets |
| `wikimedia-pid` | per file (public domain / CC BY-SA 3.0) | 7 Commons images | Rows 1, 2, 3 and 8 on six of them, scored against agent-made first-pass keys (`data/agent_keys/`; marked as such in the matrix) |
| `uci-hydraulic` | CC BY 4.0 | one zip (77 MB) | Historian bands (row 6) on a hydraulic test rig's load cycles: held out for drift, now development for auto/cyclic |
| `metropt3` | CC BY 4.0 | one zip (218 MB) | Historian bands (row 6) on a train compressor with reported air leaks: held out for drift, now development for auto/cyclic |
| `battledim` | CC BY 4.0 | 2018 pressures, flows, level, leak configuration, README (29 MB) | Historian bands (row 6) on a simulated water network with 14 leaks: held out for drift, now development for auto/cyclic |
| `battledim-2019` | CC BY 4.0 | 2019 pressures, flows, level, leak configuration, README (29.5 MB) | Held-out year for auto/cyclic (19 leaks), same simulated L-Town network as 2018; carry-over across years only |

The sources added 2026-10-29 are pinned file by file in `data/corpus_pins.json` (bytes, SHA-256, and CRC-32 or the
inner flowsheet's SHA-256 where there is one). A file already on disk that matches its pin is not fetched again, so
re-running a fetch with everything present needs no network and doubles as a check of the local copy.

## `pronto`: PRONTO heterogeneous benchmark

Stief, Tan, Cao, Ottewill, Thornhill, Baranowski, *A heterogeneous benchmark dataset for data analytics: Multiphase
flow facility case study*, Journal of Process Control 79 (2019) 41-55. Data: Zenodo record
[1341582](https://zenodo.org/record/1341582) (resolves to 1341583), CC BY 4.0: credit the authors and the DOI above
when reusing it.

The record is one 1.72 GB zip (videos, ultrasonic and high-frequency pressure files make up nearly all of it). The
script reads the zip's directory with an HTTP Range request and fetches only these members, about 4 MB:

| Member | Used for |
|---|---|
| `README.txt` | license and citation |
| `Pre-processed data/.../readme.txt` | how the authors aligned alarms with process data and labelled health from the operation log |
| `Pre-processed data/.../Testday3_merged.csv` | test day 3 (2017-09-11) at 1 s: 17 process variables, 12 binary alarm columns, the authors' `Fault` label |
| `C2 Air Leakage/Test5/Process Data/0911Testday3.csv` | the raw DeltaV export of the same day: clock times for the merged rows (which have none), and the as-exported format |
| `C2 Air Leakage/Test5/Alarms and Events/0911Testday3_Alm_Evt.txt` | the DeltaV alarm and event journal |
| `Operation logs/Operation log.xlsx` | when each fault was introduced (valve and time) |
| `Technical documents/Alarm settings in DeltaV.xlsx` | the configured alarm limits |

It then writes three historian CSVs to `data/external/pronto/historian/` (17 tags, ISO timestamps, cell text
unchanged) and `pairs.json` (rows, times, fault starts, alarm onsets). The merged rows are placed on the clock by
finding the one offset at which every merged row's `Air.T` and `Air.P` equal the raw export's (merged row 0 = raw row
1500 = 10:25:00); each raw row's stamp is checked against start time + row number.

| CSV | Rows | What |
|---|---|---|
| `pronto_normal.csv` | 600 | 10:25:00-10:34:59, 120 sm3/h air, 0.1 kg/s water, labelled Normal |
| `pronto_leakage.csv` | 3181 | 10:35:00-11:28:00: 5 min Normal (not in the normal CSV), then Air leakage from row 300 (10:40:00) |
| `pronto_diverted.csv` | 7920 | 12:50:01-15:02:00: 10 min Normal at the same flows, then Diverted flow from row 600 (13:00:01) |

Fault starts are the rows where the authors' `Fault` label changes, checked at conversion time. For air leakage it
matches the operation log (manual valve V10 opened 0 to 5 degrees at 10:40, 5 to 10 at 10:50). For diverted flow the
log's first entry is at 13:07 (valve U39 at 5 degrees) and it says 13:45-14:45 is "either Diverted flow ... or
Normal", so that start is less certain.

```sh
python scripts/fetch_corpus.py pronto
H=data/external/pronto/historian
python scripts/csv_normal_bands.py --normal $H/pronto_normal.csv --score $H/pronto_leakage.csv \
    --fault-start 300 --out data/external/pronto/results/leakage
python scripts/csv_normal_bands.py --normal $H/pronto_normal.csv --score $H/pronto_diverted.csv \
    --fault-start 600 --out data/external/pronto/results/diverted
python scripts/csv_replay_server.py --csv $H/pronto_leakage.csv --host 127.0.0.1 --port 4881 --rate 2 --start 299
```

### Results (2026-10-29)

These were measured with the bands as they were then, now `--method level`. The tool's default is now the drift
method (gap between a 10-sample and a 600-sample average, half-width at least 1% of the reading and following the
reading down to half when the tag runs lower), developed on day 3 and SKAB and then on all of PRONTO, SKAB, HAI 21.03
and TE: with it neither day-3 run flags a pre-fault row (0 of 300 and 0 of 600) and both faults are detected, 631 s
and 1922 s after their labelled starts. Results on every source, with the held-out runs
reported separately, are in `docs/GENERALIZATION.md` row 6 and `docs/TRIED.md`.

| | TE fault 6 (`examples/historian-csv`) | PRONTO air leakage | PRONTO diverted flow |
|---|---|---|---|
| K chosen | 6 | 6 (worst-tag held-out rate 0.0%; K = 5 would be 6.0%, Water.Density) | 6 (same bands) |
| Held-out normal rows flagged | 0 | 0 of 300 | 0 of 300 |
| Pre-fault rows flagged (rows the fit never saw) | 0 of 160 | **231 of 300** (first at 10:36:08, 68 s after the normal CSV ends) | **600 of 600** |
| Tags behind the pre-fault flags | none | WaterIn 232, Water.Density 231, Air.T 230, Air.P 2, FR.topsep.liquid 1 | Air.T, Water.T, Water.Density, WaterIn (all 600) |
| Reported detection delay (3 in a row) | 0 min | 0 s | 0 s |

**The reported 0 s detection means nothing here**: the bands were already flagging before the fault. They are too
narrow for slow real drift (Air.T band 19.130-19.141 degC, 0.011 degC wide; by the afternoon run Air.T is 17.9-18.0
and Water.T 24.2-24.7 against a band of 18.8-19.8). K is chosen on the second half of the same 10 minutes, which
drifts very little, so the held-out check passes (0 of 300) and does not see it. On TE, which is a stationary
simulation, this never shows. The tool reports the pre-fault flags, so nothing is hidden, but a reader of the
detection-delay line alone would be misled. Contradicts the TE result in kind (0 false flags there); agrees on K.

Diagnostic only (chosen after seeing the results, so not a test): keeping the 12 tags with no pre-fault flags, air
leakage is detected at 10:50:25 (Mixture.zone.P, then Air.Valve, P.topsep, riser.outlet.P), 25 s after V10 went from 5
to 10 degrees; the 5-degree step was not seen. Diverted flow: 13 such tags, first run of 3 at 13:02:54
(water.tank.level), before the log's first diverted entry.

Real alarms: in the plant's alarm settings almost every limit is marked "not enabled"; the journal's alarms are
instrument alarms (MODULE_ALM, "I/O Input Failure"), not process limits. The first after the leakage start is PT312
at 10:41:31 (journal); in the authors' binary columns it appears at 10:41:00, and all onsets there fall on whole
minutes, so those columns are minute-resolution. So there is no process alarm to compare the bands with.

The as-exported raw file is refused by `csv_normal_bands.py`, with a message naming 26 empty tag names: it has three
header rows (metadata, DeltaV tags, descriptions), duplicate descriptions, `m/d/Y H:M` timestamps with minutes only,
and from 16:20:01 Excel serial days instead. The refusal is correct; the message does not say that row 1 is metadata.

Replay (`data/external/pronto/results/replay_smoke.txt`): server on 127.0.0.1:4881 from row 299, an asyncua client
read `_sample`, `_time`, AirIn, Air.P, Mixture.zone.P and Water.Density twice, 2 s apart: rows 299 then 300
(10:39:59, 10:40:00), every value equal to the CSV cell, all Good. Server stopped; nothing listening on 4881
afterwards.

## `dtu-te`: Reinartz et al. extended TE reference data

Reinartz, Kulahci, Ravn, *Tennessee Eastman Reference Data for Fault-Detection and Decision Support Systems*, DTU
Data, [doi:10.11583/DTU.13385936](https://data.dtu.dk/articles/dataset/Tennessee_Eastman_Reference_Data_for_Fault-Detection_and_Decision_Support_Systems/13385936),
CC0 1.0. 28 faults and setpoint and mode changes in six operating modes, 100 h runs at 3 min.

The figshare API lists six HDF5 files, one per mode, 23,219-23,925 MB each, and a Readme; there is no smaller split.
Not one data file fits `--max-mb 500`, and HDF5 needs `h5py`, which is not in `requirements.txt` and was not
installed. So the script checks the listing against its pins, fetches `Readme.html` (8,493 bytes) and records both
skip reasons in the receipt. Nothing about the tools was tested on this source. Reading one mode's runs would need
h5py (and either the whole file or remote partial reads); that is a dependency decision, not a fetch.

```sh
python scripts/fetch_corpus.py dtu-te
```

On 2026-10-29 the Readme download failed once with a certificate error from DTU's file host (`s3q.ait.dtu.dk:9000`)
and worked on the next try. A failure is recorded in the receipt as a skip; TLS checking is never turned off.

## Sources added 2026-10-29 (generalization matrix)

What each feeds and how it is converted is in `scripts/corpus_adapters.py` (rules written before the matrix cells
first ran) and the matrix's own page, `docs/GENERALIZATION.md`, which has the results.

```sh
python scripts/fetch_corpus.py dexpi-ttc-all
python scripts/fetch_corpus.py hai
python scripts/fetch_corpus.py skab          # GPL-3.0: local use only
python scripts/fetch_corpus.py pronto-more
python scripts/fetch_corpus.py idaes-hda
python scripts/fetch_corpus.py dwsim-fossee
python scripts/fetch_corpus.py wikimedia-pid
```

- `dexpi-ttc-all`: GitLab regenerates archives, so the archive hash is not a stable pin; every member is fetched by
  raw URL at commit `a23d61e2` and pinned on its own. Files land where the archive unpacks
  (`extracted/TrainingTestCases-<commit>-<commit>/`). Six AutoCAD P&ID exports reuse element IDs; the reader refuses
  them, and the matrix counts that as correct only when the duplicate IDs are found in the XML independently.
- `hai`: HAI 22.04, 23.05 and HAIEnd 23.05 are Git LFS objects (raw URLs return pointers) and about ten times larger:
  not fetched.
- `skab`: GPL-3.0 is unusual for data. Local use is fine; the repository only ever references it by this command.
- `dwsim-fossee`: the site may rebuild a project zip around the same flowsheet, so the inner `.dwxmz` is pinned too.
- `wikimedia-pid`: per-file licences are in the pins (public domain for the 1958 OMRE scan; CC BY-SA 3.0 for the
  textbook sheets). Commons answered HTTP 429 to a fast fetch on 2026-10-29; fetch slowly.

- `uci-hydraulic`, `metropt3`, `battledim`: pinned from the copies staged on 2026-10-29 (bytes and SHA-256 of each
  staged file). The download URLs (UCI's static zips; Zenodo record 4017659's file links) were not re-checked when the
  pins were written, so a first fetch that receives different bytes is refused, not saved. `scripts/historian_adapters.py`
  turns them into historian CSVs in a temporary folder; nothing derived is committed.
- `battledim-2019`: S. G. Vrachimis et al., *BattLeDIM: Battle of the Leakage Detection and Isolation Methods*,
  KIOS Research and Innovation Center of Excellence, University of Cyprus,
  [Zenodo record 4017659](https://zenodo.org/records/4017659), CC BY 4.0. The three 2019 SCADA CSVs, shared
  `dataset_configuration.yaml` and `README.txt` were downloaded on 2026-10-29 without login or click-through;
  every file has its exact size, SHA-256, published Zenodo MD5 and direct URL in `data/corpus_pins.json`.
  `python scripts/fetch_corpus.py battledim-2019` checks matching local files without network. The split and
  mapping were fixed before scoring (A178), the method frozen in A183 and scored once in A184: 6/19 pass
  against drift's 0/19. Detection takes 14 hours to 5 days, and tank level T1 drives most flags. This tests
  another year of the development network, not a different network or real plant. See the
  [historian guide](../examples/historian-csv/README.md) for the baseline, overlapping leak windows and criterion.

Staged locally but not integrated (data in `data/external/`, not yet a fetch source): the HAI boiler physical graph and
the Covestro PCS list. They are listed as candidates in `data/corpus.json`.

## Needs a human decision

Nothing below was downloaded by a script here. Each needs a person to accept terms, log in, or decide a licence
question; the size and value are what was known on 2026-10-29.

| Source | Blocker | Size | Value |
|---|---|---|---|
| Rieth et al. additional TE data, Harvard Dataverse doi:10.7910/DVN/6C3JR1 | a terms dialog ("by accessing or downloading ... you agree"); RData format | 24.7 + 47.3 + 494 + 837 MB | row 6: 500 runs per fault, so detection and false-alarm rates with confidence intervals (same TE family, not independent) |
| Cranfield three-phase flow facility, IEEE DataPort doi:10.21227/0b7j-q780 | IEEE DataPort login; licence not confirmed on the page | 16 data sets | row 6: the PRONTO rig in another campaign (3 normal, 13 faults) |
| SWaT / WADI (iTrust, SUTD) | request form and terms | several GB | rows 6 and 4: a real water-treatment testbed with PLC loops and attack labels |
| Ricker multiloop TE model (MultiLoop_mode3.mdl inside pytep) | licence decision: N. L. Ricker's file inside a BSD-3 repository that otherwise excludes his files | 0.4 MB (staged for inspection only) | row 4: an independent TE control structure to audit the Braatz-based drawings against |
| ASU PID_dataset (Zenodo 8028570) beyond internal notes | CC BY 4.0 on the record, but the drawings are "from industry and webscraping": the depositor may not hold the rights | 18.8 MB staged of 6.7 GB | rows 2 and 3 on 92 heterogeneous real rasters (symbol boxes only) |

Hand keys are a separate human job, not a decision. The OMRE 1958 scan (one quadrant), five Commons sheets and PRONTO's
Figure 1 now have agent-made first-pass keys (`data/agent_keys/`, kind `agent-keyed-sheets` in `data/corpus.json`):
the matrix scores them and marks every such cell, but no person has reviewed those keys, so a person's key is still
the stronger test. PRONTO's DeltaV loop list and the DEXPI 1.2 vendor renders (which need an XML-to-pixel map checked
by overlay) still need a person.

