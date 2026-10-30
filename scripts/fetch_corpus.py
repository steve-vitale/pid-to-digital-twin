"""Fetch a pinned subset of a public historian dataset and convert it to the CSV shape scripts/csv_normal_bands.py reads.

Why: the historian tools (csv_normal_bands.py, csv_replay_server.py) were built and checked on the Braatz Tennessee
Eastman runs only. Tools tested on one dataset can fail quietly on the next; these sources are the next ones.

Sources (docs/CORPUS_FETCH.md has what each one tests and the full commands):

  pronto   PRONTO heterogeneous benchmark (Stief et al. 2019), CC BY 4.0, Zenodo record 1341583 (1341582 redirects
           there). One 1.72 GB zip (process data, alarms, operation log, ultrasonic, high-frequency pressure, videos).
           The zip is never downloaded whole: its central directory is read with an HTTP Range request and only the
           pinned members below are fetched (about 4 MB), each checked against the zip's CRC-32 and a SHA-256
           recorded on the first fetch (2026-10-29). Then one normal and two faulty runs are written as historian CSVs.
  dtu-te   Reinartz et al. (2021) extended TE reference data, CC0 1.0, DTU Data (figshare) article 13385936. Six HDF5
           files of 23-24 GB each and a Readme. No data file fits any sensible --max-mb, and reading HDF5 needs h5py,
           which is not a dependency of this repository; so only the Readme is fetched and the receipt records why
           the data was skipped.

A changed upstream file is refused, never saved: the record's file list (name, size, checksum) must match the pin,
each fetched member must match its pinned CRC-32 and SHA-256. Downloads go to data/external/<source>/ (gitignored).
Every run writes data/external/<source>/FETCH_RECEIPT.json (what was fetched, bytes, hashes, license, skips).

Sources added 2026-10-29 for the generalization matrix (data/corpus.json). Each file is pinned by bytes and SHA-256
in data/corpus_pins.json (recorded on the first download); a file already on disk that matches its pin is not
fetched again, so a re-run with everything present needs no network:
  dexpi-ttc-all  DEXPI TrainingTestCases at a pinned commit (CC BY 4.0): all 634 members by raw URL, one pin each
                 (GitLab regenerates archives, so an archive hash is not a stable pin). DEXPI 1.2 vendor exports.
  hai            HAI ICS dataset at a pinned commit (CC BY-SA 4.0): boiler graphs and the HAI 21.03 train1/test1/test4.
  skab           Skoltech Anomaly Benchmark data folder at a pinned commit. GPL-3.0: fetched for local use only;
                 never vendored, and no derived CSV, figure or sample of it may be committed.
  pronto-more    more members of the same pinned PRONTO zip (test days 2 and 4, the technical report), found by name
                 in the zip's central directory and checked against size, CRC-32 and SHA-256.
  idaes-hda      the IDAES hydrodealkylation flowsheet JSON files at a pinned commit (IDAES BSD-style licence).
  dwsim-fossee   42 FOSSEE DWSIM flowsheet project zips (CC BY-SA 4.0); the inner flowsheet file is pinned too,
                 because the site may rebuild a zip around the same flowsheet.
  wikimedia-pid  seven P&ID images from Wikimedia Commons with their per-file licences (agent-made first-pass keys
                 for six of them are in data/agent_keys/).
  uci-hydraulic  UCI hydraulic condition monitoring zip (CC BY 4.0).           Historian sources for
  metropt3       MetroPT-3 compressor zip (CC BY 4.0).                         csv_normal_bands.py (matrix row 6),
  battledim      BattLeDIM 2018 SCADA CSVs and leak configuration (CC BY 4.0). read by historian_adapters.py.
                 These three were held out for drift, then used to develop the cyclic/auto method.
  battledim-2019 BattLeDIM 2019 SCADA CSVs, configuration, README (CC BY 4.0): held out for cyclic/auto, same network.

Model use: none. Stdlib only. No downloaded code is executed. Claude (the coding agent) wrote the code.

  python scripts/fetch_corpus.py pronto [--max-mb 500]
  python scripts/fetch_corpus.py dtu-te [--max-mb 500]
  python scripts/fetch_corpus.py dexpi-ttc-all | hai | skab | pronto-more | idaes-hda | dwsim-fossee | wikimedia-pid
  python scripts/fetch_corpus.py uci-hydraulic | metropt3 | battledim | battledim-2019
"""
import argparse
import csv
import hashlib
import io
import json
import struct
import sys
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "data" / "external"
USER_AGENT = "pid-digital-twin fetch_corpus.py (data download; https://github.com/steve-vitale/pid-to-digital-twin)"

PRONTO_ZIP_MEMBERS_ROOT = "PRONTO benchmark case study/"
SOURCES = {
    "pronto": {
        "name": "PRONTO heterogeneous benchmark dataset (multiphase flow facility, Cranfield University)",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": ("A. Stief, R. Tan, Y. Cao, J. R. Ottewill, N. F. Thornhill, J. Baranowski, A heterogeneous "
                        "benchmark dataset for data analytics: Multiphase flow facility case study, Journal of Process "
                        "Control 79 (2019) 41-55, doi:10.1016/j.jprocont.2019.04.009. Data: doi:10.5281/zenodo.1341583"),
        "landing_url": "https://zenodo.org/record/1341582",
        "api_url": "https://zenodo.org/api/records/1341583",
        "kind": "zenodo-zip-members",
        "zip": {"key": "PRONTO benchmark case study.zip", "size": 1720560937,
                "checksum": "md5:13b7464b88bd0a011c20cb26712e48e5",
                "url": "https://zenodo.org/api/records/1341583/files/PRONTO%20benchmark%20case%20study.zip/content",
                "central_directory_offset": 1720480438, "central_directory_size": 80477, "entries": 477},
        # Each member: where it sits in the zip (local header offset, compressed size), what it inflates to, the zip's
        # own CRC-32 and the SHA-256 of the inflated bytes recorded on the first fetch (2026-10-29).
        "members": {
            "README.txt": {
                "offset": 1720479663, "compressed": 707, "size": 1254, "crc32": "b7af597b",
                "sha256": "13b0cb0a1534e7f9e84564e1fea5a6d92169458055f357cced4a1eeb117787b6", "why": "the dataset's license and citation"},
            "Pre-processed data/Aligned and labelled alarm and process data/readme.txt": {
                "offset": 1257604579, "compressed": 515, "size": 1113, "crc32": "d45a4e0b", "sha256": "1efa39c7cf68d8bb7435992d01d06193a2e90f7e0c9328a1a3610554ebd4e1b1",
                "why": "how the authors aligned alarms with process data and labelled health from the operation log"},
            "Pre-processed data/Aligned and labelled alarm and process data/Testday3_merged.csv": {
                "offset": 1258429490, "compressed": 1382584, "size": 5045921, "crc32": "222928a4", "sha256": "abe1d895945a1e19a4025a7081abd159b06f27e4cdfe53a5610b327b95518540",
                "why": "test day 3 (2017-09-11) at 1 s: 17 process variables, 12 binary alarm columns, and the "
                       "authors' Fault label (Normal / Air leakage / Diverted flow): the fault starts come from it"},
            "C2 Air Leakage/Test5/Process Data/0911Testday3.csv": {
                "offset": 822499213, "compressed": 2519653, "size": 8724815, "crc32": "19e58b93", "sha256": "1d210163647600b7bb4273e1a01476508b8390cb84fbeed189f1978d91c703af",
                "why": "the raw DeltaV export of the same day, with timestamps: used only to put clock times on the "
                       "merged rows (they have none) and as the as-exported-format test"},
            "C2 Air Leakage/Test5/Alarms and Events/0911Testday3_Alm_Evt.txt": {
                "offset": 807292348, "compressed": 7754, "size": 119508, "crc32": "edc12534", "sha256": "5b302d6c599c3550759824c11d17ba31db234014acab7df56500155ed7189961",
                "why": "the DeltaV alarm and event journal of the same day (real alarms to compare with)"},
            "Operation logs/Operation log.xlsx": {
                "offset": 1169302876, "compressed": 30153, "size": 35692, "crc32": "575941cc", "sha256": "36676c5e73b91b0d029e96643d7b3f9d7748df802c367fe785cee16734a2ab82",
                "why": "the operators' log: when each fault was introduced (valve positions and times)"},
            "Technical documents/Alarm settings in DeltaV.xlsx": {
                "offset": 1719333562, "compressed": 10108, "size": 12811, "crc32": "71d02058", "sha256": "07d019fbde971ace8ab389d0b30d229d2db9847a76d1b0cc71ede7b012522fb0",
                "why": "the plant's configured alarm limits (most marked 'not enabled')"},
        },
        "skipped": "videos, ultrasonic and high-frequency pressure files (about 1.7 GB of the zip), the other test "
                   "days, the .mat files and the technical report PDF: not needed for the historian tools",
    },
    "dtu-te": {
        "name": "Tennessee Eastman Reference Data for Fault-Detection and Decision Support Systems (Reinartz et al. 2021)",
        "license": "CC0 1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution": ("C. Reinartz, M. Kulahci, O. Ravn, Tennessee Eastman Reference Data for Fault-Detection and "
                        "Decision Support Systems, DTU Data, doi:10.11583/DTU.13385936.v1"),
        "landing_url": ("https://data.dtu.dk/articles/dataset/Tennessee_Eastman_Reference_Data_for_Fault-Detection_"
                        "and_Decision_Support_Systems/13385936"),
        "api_url": "https://api.figshare.com/v2/articles/13385936",
        "kind": "figshare-files",
        # The record's whole file list as of 2026-10-29: name -> (bytes, md5 published by figshare).
        "files": {
            "TEP_Mode1.h5": {"size": 23924710848, "md5": "c79ecc6d12a5ccb49caffcd8f531feae", "data": True},
            "TEP_Mode2.h5": {"size": 23897125720, "md5": "72ee75fdf6da8e59327f04fd4fd49662", "data": True},
            "TEP_Mode3.h5": {"size": 23921551744, "md5": "5f4bf0d87e7f9ff81ee632f84f2d9050", "data": True},
            "TEP_Mode4.h5": {"size": 23219369960, "md5": "c1e76a74022230450dc14fe904451236", "data": True},
            "TEP_Mode5.h5": {"size": 23890304712, "md5": "8f3c1a1ebeb80ad78089f82a7d521fda", "data": True},
            "TEP_Mode6.h5": {"size": 23907566544, "md5": "d01e032a1f3ff9ca3afaa1f74c52e1a6", "data": True},
            "Readme.html": {"size": 8493, "md5": "963359b135036c0b19951929798a8b46", "data": False,
                            "url": "https://ndownloader.figshare.com/files/26775368",
                            "sha256": "68f3b03ea10732ec631a720be614b44267e7b61c10eb2f141d95c8fb1293b460"},
        },
    },
}

# Sources whose files are pinned one by one in data/corpus_pins.json (name -> {bytes, sha256[, crc32]}).
PINS = ROOT / "data" / "corpus_pins.json"
DEXPI_COMMIT = "a23d61e2e089eb2ca464cd552f9ae580a2785963"
DEXPI_PREFIX = f"extracted/TrainingTestCases-{DEXPI_COMMIT}-{DEXPI_COMMIT}/"  # the layout GitLab's archive unpacks to
FILE_SOURCES = {
    "dexpi-ttc-all": {
        "name": "DEXPI TrainingTestCases, all folders (DEXPI 1.2 vendor exports and 1.3 cases)",
        "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "DEXPI example P&IDs from the DEXPI TrainingTestCases repository (DEXPI initiative and "
                       "contributing members), CC BY 4.0",
        "landing_url": "https://gitlab.com/dexpi/TrainingTestCases",
        "api_url": f"https://gitlab.com/dexpi/TrainingTestCases/-/tree/{DEXPI_COMMIT}",
        "kind": "pinned-files", "commit": DEXPI_COMMIT,
        "url": "https://gitlab.com/dexpi/TrainingTestCases/-/raw/" + DEXPI_COMMIT + "/{path}", "dest_prefix": DEXPI_PREFIX,
        "skipped": "nothing: every member of the pinned commit is fetched (92 MB unpacked, mostly renders and PDFs)"},
    "hai": {
        "name": "HAI industrial control system security dataset (boiler graphs, HAI 21.03 train1/test1/test4)",
        "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": "H.-K. Shin, W. Lee, J.-H. Yun, B.-G. Min, HAI dataset, https://github.com/icsdataset/hai "
                       "(cite as the README asks)",
        "landing_url": "https://github.com/icsdataset/hai",
        "api_url": "https://github.com/icsdataset/hai/tree/2a814cebc9a66b06c9e5cd545e2d72e65d383737",
        "kind": "pinned-files", "commit": "2a814cebc9a66b06c9e5cd545e2d72e65d383737",
        "url": "https://raw.githubusercontent.com/icsdataset/hai/2a814cebc9a66b06c9e5cd545e2d72e65d383737/{path}",
        "skipped": "HAI 22.04, 23.05 and HAIEnd 23.05 (Git LFS objects, 10x larger) and the other 21.03 runs"},
    "skab": {
        "name": "SKAB Skoltech Anomaly Benchmark, data folder",
        "license": "GPL-3.0 (local use only: never vendored; no derived CSV, figure or sample may be committed)",
        "license_url": "https://www.gnu.org/licenses/gpl-3.0.html",
        "attribution": "I. D. Katser, V. O. Kozitsin, Skoltech Anomaly Benchmark (SKAB), 2020, "
                       "doi:10.34740/KAGGLE/DSV/1693952",
        "landing_url": "https://github.com/waico/SKAB",
        "api_url": "https://github.com/waico/SKAB/tree/b2c0d46c2971dcbfe71e26087b6d231998bb91c2",
        "kind": "pinned-files", "commit": "b2c0d46c2971dcbfe71e26087b6d231998bb91c2",
        "url": "https://raw.githubusercontent.com/waico/SKAB/b2c0d46c2971dcbfe71e26087b6d231998bb91c2/{path}",
        "skipped": "the notebooks, figures and benchmark code (not data)"},
    "pronto-more": {
        "name": "PRONTO benchmark, more members of the same pinned zip (test days 2 and 4, technical report)",
        "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": SOURCES["pronto"]["attribution"],
        "landing_url": SOURCES["pronto"]["landing_url"], "api_url": SOURCES["pronto"]["api_url"],
        "kind": "pinned-zip-members", "zip_of": "pronto", "dest_prefix": PRONTO_ZIP_MEMBERS_ROOT,
        "skipped": "everything else in the zip (as for pronto)"},
    "idaes-hda": {
        "name": "IDAES examples: hydrodealkylation (HDA) flowsheet visualizer JSON files",
        "license": "IDAES license (BSD-3-Clause style with a DOE notice; LICENSE.md at the pinned commit)",
        "license_url": "https://github.com/IDAES/examples/blob/c4fe326d32614f3bc2814c5fd261d3eb1ae0276c/LICENSE.md",
        "attribution": "IDAES Process Systems Engineering Framework examples, https://github.com/IDAES/examples",
        "landing_url": "https://github.com/IDAES/examples",
        "api_url": "https://github.com/IDAES/examples/tree/c4fe326d32614f3bc2814c5fd261d3eb1ae0276c",
        "kind": "pinned-files", "commit": "c4fe326d32614f3bc2814c5fd261d3eb1ae0276c",
        "url": "https://raw.githubusercontent.com/IDAES/examples/c4fe326d32614f3bc2814c5fd261d3eb1ae0276c/{path}",
        "skipped": "every other example (the notebook is fetched as data and never run)"},
    "dwsim-fossee": {
        "name": "FOSSEE DWSIM Flowsheeting Project: 42 completed flowsheets",
        "license": "CC BY-SA 4.0 (site footer); each flowsheet credits its contributor",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": "FOSSEE DWSIM Flowsheeting Project, IIT Bombay, https://dwsim.fossee.in (credit each "
                       "flowsheet's contributor as listed on its page)",
        "landing_url": "https://dwsim.fossee.in/flowsheeting-project/completed-flowsheet",
        "api_url": "https://dwsim.fossee.in/flowsheeting-project/completed-flowsheet",
        "kind": "pinned-files",
        "url": "https://dwsim.fossee.in/flowsheeting-project/full-download/project/{project}",
        "skipped": "233 more completed flowsheets (this is the first 42 with a downloadable flowsheet file)"},
    "wikimedia-pid": {
        "name": "Wikimedia Commons P&ID images (OMRE 1958 scan and textbook sheets)",
        "license": "per file (public domain or CC BY-SA 3.0; recorded per file in data/corpus_pins.json)",
        "license_url": "https://commons.wikimedia.org/wiki/Commons:Licensing",
        "attribution": "per file: the author named on each Commons file page (pins carry artist and page URL)",
        "landing_url": "https://commons.wikimedia.org/wiki/Category:Piping_and_instrumentation_diagrams",
        "api_url": "https://commons.wikimedia.org/w/api.php",
        "kind": "pinned-files", "url": "{url}",
        "skipped": "other Commons sheets (no per-file licence check yet)"},
    # The original three historian sources were held out for drift (A165, A171), then used to develop cyclic;
    # BattLeDIM 2019 was held out for cyclic (A178, A183, A184). All are read by
    # scripts/historian_adapters.py. Pinned from the copies staged 2026-10-29 (bytes and SHA-256 of each file).
    # The original three sources' URLs were not re-checked when their pins were written (no network); 2019's
    # URLs and published MD5s are from its download receipt. Different upstream bytes are refused, never saved.
    "uci-hydraulic": {
        "name": "UCI condition monitoring of hydraulic systems (Helwig, Pignanelli, Schutze 2015)",
        "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "N. Helwig, E. Pignanelli, A. Schutze, Condition monitoring of hydraulic systems, UCI Machine "
                       "Learning Repository, CC BY 4.0",
        "landing_url": "https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems",
        "api_url": "https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems",
        "kind": "pinned-files", "url": "{url}",
        "skipped": "nothing: the dataset is one zip (77 MB)"},
    "metropt3": {
        "name": "MetroPT-3 air compressor dataset (Veloso, Ribeiro, Gama, Pereira)",
        "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "B. Veloso, R. P. Ribeiro, J. Gama, P. M. Pereira, MetroPT-3 Dataset, UCI Machine Learning "
                       "Repository, CC BY 4.0",
        "landing_url": "https://archive.ics.uci.edu/dataset/791/metropt+3+dataset",
        "api_url": "https://archive.ics.uci.edu/dataset/791/metropt+3+dataset",
        "kind": "pinned-files", "url": "{url}",
        "skipped": "nothing: the dataset is one zip (218 MB)"},
    "battledim": {
        "name": "BattLeDIM 2020 dataset: L-Town 2018 SCADA (pressures, flows, tank level) and the leak configuration",
        "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "S. G. Vrachimis et al., BattLeDIM: Battle of the Leakage Detection and Isolation Methods "
                       "dataset (KIOS Research and Innovation Center of Excellence, University of Cyprus), Zenodo "
                       "record 4017659, CC BY 4.0",
        "landing_url": "https://zenodo.org/records/4017659",
        "api_url": "https://zenodo.org/api/records/4017659",
        "kind": "pinned-files", "url": "{url}",
        "skipped": "the 2018 demands, the 2019 evaluation year, the .xlsx copies and the EPANET models: the row-6 "
                   "adapter reads the 2018 pressures, flows and level and the leak table only"},
    "battledim-2019": {
        "name": "BattLeDIM 2020 dataset: L-Town 2019 SCADA (pressures, flows, tank level) and the leak configuration",
        "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "S. G. Vrachimis et al., BattLeDIM: Battle of the Leakage Detection and Isolation Methods "
                       "dataset (KIOS Research and Innovation Center of Excellence, University of Cyprus), Zenodo "
                       "record 4017659, CC BY 4.0",
        "landing_url": "https://zenodo.org/records/4017659",
        "api_url": "https://zenodo.org/api/records/4017659",
        "kind": "pinned-files", "url": "{url}",
        "skipped": "the demands, the 2018 development year, the .xlsx copies and the EPANET models: the row-6 "
                   "adapter reads the 2019 pressures, flows and level and the leak table only"},
}


def load_pins(path=PINS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_file_pins(pins, sources=FILE_SOURCES):
    """Problems with the per-file pin table (empty list = well formed)."""
    problems = []
    for sid, s in sources.items():
        for k in ("name", "license", "license_url", "attribution", "landing_url", "api_url", "kind", "url"
                  if s.get("kind") == "pinned-files" else "zip_of"):
            if not s.get(k):
                problems.append(f"{sid}: missing {k}")
        files = pins.get(sid)
        if not isinstance(files, dict) or not files:
            problems.append(f"{sid}: no pins in {PINS.name}")
            continue
        for name, p in files.items():
            pp = PurePosixPath(name)
            if pp.is_absolute() or ".." in pp.parts:
                problems.append(f"{sid}: {name!r} is not a safe relative path")
            if not (isinstance(p.get("bytes"), int) and p["bytes"] >= 0):  # three upstream files are empty
                problems.append(f"{sid}: {name}: bytes malformed")
            if len(p.get("sha256") or "") != 64 or any(c not in "0123456789abcdef" for c in p["sha256"]):
                problems.append(f"{sid}: {name}: sha256 must be 64 lowercase hex digits")
            if s["kind"] == "pinned-zip-members" and len(p.get("crc32") or "") != 8:
                problems.append(f"{sid}: {name}: crc32 must be 8 hex digits")
            if s["kind"] == "pinned-files":
                try:
                    url = file_url(s, name, p)
                except (KeyError, IndexError):
                    url = ""
                if not url.startswith("https://"):
                    problems.append(f"{sid}: {name}: no https URL")
    return problems


def file_url(s, name, pin):
    from urllib.parse import quote
    return s["url"].format(path=quote(name), url=pin.get("url", ""), project=pin.get("project", ""))


def fetch_pinned(sid, max_mb, dest, fetch=None, today=None, pins=None):
    """Fetch every pinned file of a FILE_SOURCES entry that is missing or does not match its pin."""
    fetch = fetch or http_get
    s = FILE_SOURCES[sid]
    files = (pins or load_pins())[sid]
    receipt = {"source": sid, "license": s["license"], "attribution": s["attribution"], "landing_url": s["landing_url"],
               "fetched": today or datetime.now(timezone.utc).isoformat(timespec="seconds"), "files": [],
               "skipped": s["skipped"]}
    prefix = s.get("dest_prefix", "")
    todo = []
    for name, pin in files.items():
        out = safe_dest(dest, prefix + name)
        if out.is_file():
            try:
                sha = check_bytes(name, out.read_bytes(), pin["bytes"], pin["sha256"], pin.get("crc32"))
                receipt["files"].append({"path": name, "bytes": pin["bytes"], "sha256": sha, "fetched_bytes": 0,
                                         "status": "already present, checks OK"})
                continue
            except PinError:
                pass  # re-fetch; the bad local copy is overwritten only by bytes that pass
        todo.append((name, pin, out))
    need = sum(p["bytes"] for _, p, _ in todo)
    if need > max_mb * 1e6:
        raise SystemExit(f"{sid}: {len(todo)} missing files need {need / 1e6:.1f} MB, over --max-mb {max_mb}")
    entries, zurl = None, None
    if todo and s["kind"] == "pinned-zip-members":
        z = SOURCES[s["zip_of"]]["zip"]
        zurl = z["url"]
        cd = fetch(zurl, (z["central_directory_offset"], z["central_directory_offset"] + z["central_directory_size"] - 1))
        entries = parse_central_directory(cd)
        if len(entries) != z["entries"]:
            raise PinError(f"{sid}: central directory has {len(entries)} entries, pinned {z['entries']}")
    got = 0
    for name, pin, out in todo:
        if entries is not None:
            e = entries.get(prefix + name)
            if e is None or e["size"] != pin["bytes"] or e["crc32"] != pin["crc32"]:
                raise PinError(f"{sid}: {name}: central directory says {e}, pinned {pin}")
            data = fetch_zip_member(fetch, zurl, name, e)
        else:
            data = fetch(file_url(s, name, pin), None)
            if pin.get("flowsheet"):  # a DWSIM project zip: also check the flowsheet file inside it
                check_inner(name, data, pin["flowsheet"])
        sha = check_bytes(name, data, pin["bytes"], pin["sha256"], pin.get("crc32"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        got += len(data)
        receipt["files"].append({"path": name, "bytes": len(data), "sha256": sha, "fetched_bytes": len(data),
                                 "status": "fetched"})
    receipt["fetched_mb"] = round(got / 1e6, 3)
    return receipt


def check_inner(name, data, inner, max_bytes=64 * 1024 * 1024):
    """A DWSIM project zip's flowsheet member: present, not oversized, same SHA-256 as pinned."""
    import zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        try:
            info = z.getinfo(inner["member"])
        except KeyError:
            raise PinError(f"{name}: flowsheet member {inner['member']!r} missing; the project zip changed") from None
        if info.file_size != inner["bytes"] or info.file_size > max_bytes:
            raise PinError(f"{name}: flowsheet member is {info.file_size} bytes, pinned {inner['bytes']}")
        if hashlib.sha256(z.read(info)).hexdigest() != inner["sha256"]:
            raise PinError(f"{name}: flowsheet member changed (sha256). Not saved.")

# PRONTO conversion: which rows of Testday3_merged.csv become which CSV. Rows are 0-based data rows of the merged
# file (1 s apart). The Fault label changes from Normal to "Air leakage" at row 900 and to "Diverted flow" at row 9301;
# both are checked against the file at conversion time, never assumed.
PRONTO_DAY = "Testday3_merged.csv"
PRONTO_RAW = "0911Testday3.csv"
PRONTO_PAIRS = {
    # Bands are fitted on the first half of the normal CSV and K chosen on its second half (csv_normal_bands.py).
    "normal": {"rows": (0, 600), "label": "Normal",
               "what": "120 sm3/h air, 0.1 kg/s water, 10 min before the first fault of the day"},
    "leakage": {"rows": (600, 3781), "fault_label": "Air leakage", "fault_row": 900,
                "what": "the next 5 min of normal running (not in the normal CSV), then the air-leakage test at the "
                        "same flows: manual valve V10 opened in steps of 5 degrees (operation log, test 5)"},
    "diverted": {"rows": (8701, 16621), "fault_label": "Diverted flow", "fault_row": 9301,
                 "what": "10 min of normal running at the same flows 2.5 h later, then the diverted-flow test "
                         "(test 7): scored against the morning bands, so it also tests drift over the day"},
}
PRONTO_PROCESS_COLUMNS = ("AirIn", "Air.T", "Air.P", "WaterIn", "Water.T", "Water.Density", "Mixture.zone.P",
                          "riser.outlet.P", "P.topsep", "FR.topsep.gas", "FR.topsep.liquid", "P_3phase", "Air.Valve",
                          "Water.level", "Water.coalescer", "Water.level.valve", "water.tank.level")
# Columns used to align the merged rows to the raw export (both files carry them with the same digits).
PRONTO_ALIGN = (("Air.T", "Air T"), ("Air.P", "Air P"))


class PinError(RuntimeError):
    """Upstream does not match the pin: refuse instead of saving."""


# ---------------------------------------------------------------- network (the only two places that touch it)

def http_get(url, byte_range=None, timeout=120):
    """GET url (optionally bytes a-b inclusive). Tests replace this function; nothing else opens a connection."""
    headers = {"User-Agent": USER_AGENT}
    if byte_range is not None:
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if byte_range is not None:
            if r.status != 206:
                raise PinError(f"{url}: server ignored the Range request (HTTP {r.status}); refusing to read a "
                               f"whole file")
            want = byte_range[1] - byte_range[0] + 1
            if len(data) != want:
                raise PinError(f"{url}: asked for {want} bytes, got {len(data)}")
    return data


def get_json(url):
    return json.loads(http_get(url).decode("utf-8"))


# ---------------------------------------------------------------- pins and checks

def validate_pins(sources=SOURCES):
    """Problems with the pin table itself (empty list = well formed). Run by the tests."""
    problems = []
    for sid, s in sources.items():
        for k in ("name", "license", "license_url", "attribution", "landing_url", "api_url", "kind"):
            if not s.get(k):
                problems.append(f"{sid}: missing {k}")
        if not str(s.get("api_url", "")).startswith("https://"):
            problems.append(f"{sid}: api_url is not https")
        if s.get("kind") == "zenodo-zip-members":
            z = s["zip"]
            if not (isinstance(z["size"], int) and z["size"] > 0 and z["checksum"].startswith("md5:")):
                problems.append(f"{sid}: zip size/checksum malformed")
            if z["central_directory_offset"] + z["central_directory_size"] > z["size"]:
                problems.append(f"{sid}: central directory runs past the end of the zip")
            for name, m in s["members"].items():
                p = PurePosixPath(name)
                if p.is_absolute() or ".." in p.parts:
                    problems.append(f"{sid}: member path {name!r} is not a safe relative path")
                if not (0 <= m["offset"] < z["central_directory_offset"]):
                    problems.append(f"{sid}: {name}: offset outside the zip's data area")
                if not (isinstance(m["compressed"], int) and isinstance(m["size"], int) and m["size"] > 0):
                    problems.append(f"{sid}: {name}: sizes malformed")
                if len(m["crc32"]) != 8 or any(c not in "0123456789abcdef" for c in m["crc32"]):
                    problems.append(f"{sid}: {name}: crc32 must be 8 lowercase hex digits")
                if m["sha256"] is not None and (len(m["sha256"]) != 64 or
                                                any(c not in "0123456789abcdef" for c in m["sha256"])):
                    problems.append(f"{sid}: {name}: sha256 must be 64 lowercase hex digits or None")
        elif s.get("kind") == "figshare-files":
            for name, f in s["files"].items():
                if not (isinstance(f["size"], int) and f["size"] > 0 and len(f["md5"]) == 32):
                    problems.append(f"{sid}: {name}: size/md5 malformed")
                if f.get("sha256") is not None and len(f["sha256"]) != 64:
                    problems.append(f"{sid}: {name}: sha256 malformed")
        else:
            problems.append(f"{sid}: unknown kind {s.get('kind')!r}")
    return problems


def check_bytes(name, data, size, sha256=None, crc32=None):
    """Refuse bytes that do not match the pin. Returns the sha256 seen (to record when the pin is None)."""
    if len(data) != size:
        raise PinError(f"{name}: {len(data):,} bytes, pinned {size:,}. Upstream changed; not saved.")
    if crc32 is not None and f"{zlib.crc32(data) & 0xffffffff:08x}" != crc32:
        raise PinError(f"{name}: CRC-32 {zlib.crc32(data) & 0xffffffff:08x}, pinned {crc32}. Not saved.")
    got = hashlib.sha256(data).hexdigest()
    if sha256 is not None and got != sha256:
        raise PinError(f"{name}: sha256 {got[:16]}..., pinned {sha256[:16]}.... Upstream changed; not saved.")
    return got


def safe_dest(base, relpath):
    """base / relpath, refusing anything that would land outside base."""
    p = PurePosixPath(relpath)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise PinError(f"refusing unsafe path {relpath!r}")
    out = (base / Path(*p.parts)).resolve()
    if base.resolve() not in out.parents:
        raise PinError(f"refusing path outside {base}: {relpath!r}")
    return out


# ---------------------------------------------------------------- zip members over HTTP ranges

def parse_central_directory(blob):
    """{name: {offset, compressed, size, crc32, method}} from the raw bytes of a zip central directory."""
    out, p = {}, 0
    while p + 46 <= len(blob) and blob[p:p + 4] == b"PK\x01\x02":
        (_, _, _, flags, method, _, _, crc, csize, usize, nlen, xlen, clen, _, _, _, offset) = \
            struct.unpack("<IHHHHHHIIIHHHHHII", blob[p:p + 46])
        raw = blob[p + 46:p + 46 + nlen]
        name = raw.decode("utf-8" if flags & 0x800 else "cp437")
        out[name] = {"offset": offset, "compressed": csize, "size": usize, "crc32": f"{crc:08x}", "method": method}
        p += 46 + nlen + xlen + clen
    return out


def fetch_zip_member(fetch, url, name, pin):
    """Read one member's local header, then its compressed bytes, by Range; inflate and return the bytes."""
    head = fetch(url, (pin["offset"], pin["offset"] + 29))
    if head[:4] != b"PK\x03\x04":
        raise PinError(f"{name}: no local file header at offset {pin['offset']}; the zip changed")
    method = struct.unpack("<H", head[8:10])[0]
    nlen, xlen = struct.unpack("<HH", head[26:30])
    start = pin["offset"] + 30 + nlen + xlen
    body = fetch(url, (start, start + pin["compressed"] - 1)) if pin["compressed"] else b""
    if method == 8:
        data = zlib.decompress(body, -15)
    elif method == 0:
        data = body
    else:
        raise PinError(f"{name}: compression method {method} is not deflate/stored")
    return data


def fetch_pronto(max_mb, dest, fetch=None, today=None):
    fetch = fetch or http_get
    s = SOURCES["pronto"]
    z = s["zip"]
    receipt = {"source": "pronto", "license": s["license"], "attribution": s["attribution"],
               "landing_url": s["landing_url"], "fetched": today or datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "files": [], "skipped": s["skipped"]}
    rec = get_json_via(fetch, s["api_url"])
    lic = (rec.get("metadata", {}).get("license") or {}).get("id", "")
    if lic.lower() != "cc-by-4.0":
        raise PinError(f"pronto: record license is {lic!r}, pinned CC BY 4.0. Not fetching.")
    listed = {f["key"]: f for f in rec.get("files", [])}
    zf = listed.get(z["key"])
    if zf is None or zf["size"] != z["size"] or zf["checksum"] != z["checksum"]:
        raise PinError(f"pronto: record lists {z['key']!r} as "
                       f"{None if zf is None else (zf['size'], zf['checksum'])}, pinned {(z['size'], z['checksum'])}")
    need = sum(m["compressed"] + 30 for m in s["members"].values()) + z["central_directory_size"]
    if need > max_mb * 1e6:
        raise SystemExit(f"pronto: the pinned subset needs {need / 1e6:.1f} MB, over --max-mb {max_mb}")
    cd = fetch(z["url"], (z["central_directory_offset"], z["central_directory_offset"] + z["central_directory_size"] - 1))
    entries = parse_central_directory(cd)
    if len(entries) != z["entries"]:
        raise PinError(f"pronto: central directory has {len(entries)} entries, pinned {z['entries']}")
    got_bytes = len(cd)
    for rel, pin in s["members"].items():
        full = PRONTO_ZIP_MEMBERS_ROOT + rel
        e = entries.get(full)
        if e is None or any(e[k] != pin[k] for k in ("offset", "compressed", "size", "crc32")):
            raise PinError(f"pronto: {rel}: central directory says {e}, pinned {pin}")
        out = safe_dest(dest / "zip", rel)
        if out.exists():
            data = out.read_bytes()
            try:
                sha = check_bytes(rel, data, pin["size"], pin["sha256"], pin["crc32"])
                receipt["files"].append({"path": rel, "bytes": len(data), "sha256": sha, "fetched_bytes": 0,
                                         "status": "already present, checks OK"})
                continue
            except PinError:
                pass  # re-fetch; the bad local copy is overwritten only by bytes that pass
        data = fetch_zip_member(fetch, z["url"], rel, pin)
        sha = check_bytes(rel, data, pin["size"], pin["sha256"], pin["crc32"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        got_bytes += pin["compressed"] + 30
        receipt["files"].append({"path": rel, "bytes": len(data), "sha256": sha, "fetched_bytes": pin["compressed"],
                                 "status": "fetched" if pin["sha256"] else "fetched; sha256 UNPINNED, record it"})
    receipt["fetched_mb"] = round(got_bytes / 1e6, 3)
    receipt["converted"] = convert_pronto(dest)
    return receipt


def get_json_via(fetch, url):
    return json.loads(fetch(url, None).decode("utf-8"))


def fetch_dtu(max_mb, dest, fetch=None, today=None, have_h5py=None):
    fetch = fetch or http_get
    s = SOURCES["dtu-te"]
    if have_h5py is None:
        import importlib.util
        have_h5py = importlib.util.find_spec("h5py") is not None
    receipt = {"source": "dtu-te", "license": s["license"], "attribution": s["attribution"],
               "landing_url": s["landing_url"], "fetched": today or datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "files": [], "skipped": []}
    rec = get_json_via(fetch, s["api_url"])
    lic = (rec.get("license") or {}).get("name", "")
    if lic != "CC0":
        raise PinError(f"dtu-te: record license is {lic!r}, pinned CC0 1.0. Not fetching.")
    listed = {f["name"]: f for f in rec.get("files", [])}
    if set(listed) != set(s["files"]):
        raise PinError(f"dtu-te: record lists {sorted(listed)}, pinned {sorted(s['files'])}")
    for name, pin in s["files"].items():
        f = listed[name]
        if f["size"] != pin["size"] or f.get("computed_md5") != pin["md5"]:
            raise PinError(f"dtu-te: {name}: record says {f['size']} bytes md5 {f.get('computed_md5')}, pinned "
                           f"{pin['size']} md5 {pin['md5']}")
    data_files = {n: p for n, p in s["files"].items() if p["data"]}
    fits = {n: p for n, p in data_files.items() if p["size"] <= max_mb * 1e6}
    smallest = min(data_files.items(), key=lambda kv: kv[1]["size"])
    if not fits:
        receipt["skipped"].append({
            "what": "all data files", "reason": (
                f"no data file fits --max-mb {max_mb}: the smallest is {smallest[0]}, "
                f"{smallest[1]['size'] / 1e6:,.0f} MB; the record has no smaller split or sample. Each file is one "
                f"operating mode (28 faults x 500 seeds, 100 h at 3 min)")})
    if not have_h5py:
        receipt["skipped"].append({"what": "conversion", "reason": (
            "h5py is not installed (not in requirements.txt) and HDF5 cannot be read with the standard library; "
            "nothing was installed")})
    if fits and have_h5py:  # not reached with the pinned record; kept explicit rather than silently partial
        receipt["skipped"].append({"what": "conversion", "reason": "a data file fits but HDF5 conversion is not "
                                   "implemented here; add it, with a pinned dataset path, before using this data"})
    rm = s["files"]["Readme.html"]
    out = safe_dest(dest, "Readme.html")
    try:
        data = fetch(rm["url"], None)
    except (urllib.error.URLError, OSError) as e:  # never retried with verification off
        receipt["skipped"].append({"what": "Readme.html", "reason": (
            f"download failed: {getattr(e, 'reason', e)}. The figshare link redirects to DTU's own S3 host "
            "(s3q.ait.dtu.dk:9000); on 2026-10-29 one of two attempts from the test machine failed certificate "
            "verification there (chain ends in HARICA TLS RSA Root CA 2021). TLS checking is never turned off; "
            "run again. The skip decision above comes from the record's metadata and does not need the Readme")})
        receipt["fetched_mb"] = 0.0
        return receipt
    sha = check_bytes("Readme.html", data, rm["size"], rm["sha256"])
    if hashlib.md5(data).hexdigest() != rm["md5"]:
        raise PinError("dtu-te: Readme.html md5 differs from the record's. Not saved.")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    receipt["files"].append({"path": "Readme.html", "bytes": len(data), "sha256": sha,
                             "status": "fetched" if rm["sha256"] else "fetched; sha256 UNPINNED, record it"})
    receipt["fetched_mb"] = round(len(data) / 1e6, 3)
    return receipt


# ---------------------------------------------------------------- PRONTO conversion (pure functions; tested offline)

def read_rows(text):
    return [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]


def parse_us_minute(text):
    """'09/11/2017 10:00' (the DeltaV export's timestamp: month/day/year, minute resolution) -> datetime."""
    return datetime.strptime(text.strip(), "%m/%d/%Y %H:%M")


EXCEL_EPOCH = datetime(1899, 12, 30)


def export_time_matches(text, t):
    """Does a raw-export timestamp cell agree with the computed time t? The export writes 'm/d/Y H:M' (minutes only)
    for most rows and, from 16:20:01 on test day 3, Excel serial days with 5 decimals (0.864 s resolution)."""
    text = text.strip()
    if "/" in text:
        return parse_us_minute(text) == t.replace(second=0)
    serial = EXCEL_EPOCH + timedelta(days=float(text))
    return abs((serial - t).total_seconds()) <= 1.0


def raw_export_times(raw_rows):
    """The raw DeltaV export: row 0 metadata ('Start Time,<m/d/Y H:M>,...,Interval,1s'), row 1 DeltaV tags, row 2
    descriptions (the merged file's names come from these), then data. Its timestamps carry minutes only (or are
    Excel serial days), so each row's time is the start time + row number x the interval, checked against every row.
    Returns (descriptions, data_rows, times)."""
    meta = raw_rows[0]
    if meta[0].strip() != "Start Time" or "Interval" not in meta:
        raise ValueError("raw export: row 1 is not the 'Start Time ... Interval' metadata row")
    start = parse_us_minute(meta[1])
    interval = meta[meta.index("Interval") + 1].strip()
    if interval != "1s":
        raise ValueError(f"raw export: interval {interval!r}, expected 1s")
    desc, data = [c.strip() for c in raw_rows[2]], raw_rows[3:]
    times = [start + timedelta(seconds=i) for i in range(len(data))]
    for i, (r, t) in enumerate(zip(data, times)):
        if not export_time_matches(r[0], t):
            raise ValueError(f"raw export: data row {i} is stamped {r[0]!r}, but start + {i} s = {t}")
    return desc, data, times


def align_offset(merged_header, merged_rows, raw_desc, raw_rows, pairs=PRONTO_ALIGN):
    """The raw row where merged row 0 sits: the unique offset at which every merged row's alignment columns equal the
    raw ones, as text. Raises ValueError if there is none or more than one."""
    mi = [merged_header.index(m) for m, _ in pairs]
    ri = [raw_desc.index(r) for _, r in pairs]
    first = tuple(merged_rows[0][j] for j in mi)
    cands = [o for o in range(len(raw_rows) - len(merged_rows) + 1) if tuple(raw_rows[o][j] for j in ri) == first]
    good = [o for o in cands
            if all(tuple(merged_rows[k][j] for j in mi) == tuple(raw_rows[o + k][j] for j in ri)
                   for k in range(len(merged_rows)))]
    if len(good) != 1:
        raise ValueError(f"alignment: {len(good)} raw offsets match every merged row (need exactly 1)")
    return good[0]


def label_changes(labels):
    """[(row, label)] at row 0 and wherever the label changes."""
    return [(i, x) for i, x in enumerate(labels) if i == 0 or x != labels[i - 1]]


def historian_csv_text(times, header, rows):
    """The historian CSV shape: 'time,<tags>' then ISO 8601 times and the cells' text unchanged."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["time", *header])
    for t, r in zip(times, rows):
        w.writerow([t.isoformat(sep=" "), *r])
    return buf.getvalue()


def alarm_onsets(header, rows, alarm_cols, start):
    """Per alarm column of the merged file: its state at `start`, and the first row at/after `start` where it turns
    1 having been 0 (a new alarm), or None."""
    out = {}
    for a in alarm_cols:
        j = header.index(a)
        state = rows[start][j]
        hit = next((i for i in range(start + 1, len(rows)) if rows[i][j] == "1" and rows[i - 1][j] == "0"), None)
        out[a] = {"state_at_fault": state, "first_new_activation_row": hit}
    return out


def build_pronto_csvs(merged_rows, raw_rows, pairs=PRONTO_PAIRS, process_cols=PRONTO_PROCESS_COLUMNS):
    """From the parsed merged and raw files: {name: (csv_text, info)}. Pure; checks every assumption it relies on."""
    header, data = [c.strip() for c in merged_rows[0]], merged_rows[1:]
    if header[-1] != "Fault":
        raise ValueError("merged file: last column is not 'Fault'")
    missing = [c for c in process_cols if c not in header]
    if missing:
        raise ValueError(f"merged file: process columns missing: {missing}")
    alarm_cols = [c for c in header[:header.index(process_cols[0])]]
    desc, raw_data, raw_times = raw_export_times(raw_rows)
    off = align_offset(header, data, desc, raw_data)
    times = [raw_times[off + k] for k in range(len(data))]
    labels = [r[-1] for r in data]
    pick = [header.index(c) for c in process_cols]
    out = {}
    for name, p in pairs.items():
        a, b = p["rows"]
        if not 0 <= a < b <= len(data):
            raise ValueError(f"{name}: rows {a}-{b} outside the {len(data)} merged rows")
        seg_labels = labels[a:b]
        info = {"merged_rows": [a, b - 1], "rows": b - a, "first_time": times[a].isoformat(sep=" "),
                "last_time": times[b - 1].isoformat(sep=" "), "what": p["what"],
                "label_changes": [(i + a, x) for i, x in label_changes(seg_labels)]}
        if "fault_label" in p:
            fr = p["fault_row"]
            if not (a < fr < b and labels[fr] == p["fault_label"] and labels[fr - 1] == "Normal"
                    and set(labels[a:fr]) == {"Normal"} and set(labels[fr:b]) == {p["fault_label"]}):
                raise ValueError(f"{name}: expected Normal for rows {a}-{fr - 1} and {p['fault_label']!r} for rows "
                                 f"{fr}-{b - 1}; the labels are {info['label_changes']}")
            info.update(fault_label=p["fault_label"], fault_start_row=fr - a, fault_start_merged_row=fr,
                        fault_start_time=times[fr].isoformat(sep=" "),
                        real_alarms=alarm_onsets(header, data[a:b], alarm_cols, fr - a))
        elif set(seg_labels) != {p["label"]}:
            raise ValueError(f"{name}: expected only {p['label']!r}, the labels are {info['label_changes']}")
        rows = [[r[j] for j in pick] for r in data[a:b]]
        out[name] = (historian_csv_text(times[a:b], list(process_cols), rows), info)
    meta = {"alignment": {"merged_row_0_is_raw_row": off, "merged_row_0_time": times[0].isoformat(sep=" ")},
            "alarm_columns": alarm_cols, "process_columns": list(process_cols)}
    return out, meta


def convert_pronto(dest):
    zdir = dest / "zip"
    merged = read_rows((zdir / "Pre-processed data/Aligned and labelled alarm and process data" / PRONTO_DAY)
                       .read_text(encoding="utf-8-sig"))
    raw = read_rows((zdir / "C2 Air Leakage/Test5/Process Data" / PRONTO_RAW).read_text(encoding="utf-8-sig"))
    out, meta = build_pronto_csvs(merged, raw)
    hdir = dest / "historian"
    hdir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, (text, info) in out.items():
        path = hdir / f"pronto_{name}.csv"
        path.write_text(text, encoding="utf-8", newline="")
        files[path.name] = dict(info, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
    summary = {"files": files, **meta, "source_files": [PRONTO_DAY, PRONTO_RAW]}
    (hdir / "pairs.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return {"dir": str(hdir.relative_to(ROOT)).replace("\\", "/"), "files": sorted(files)}


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", choices=sorted(SOURCES) + sorted(FILE_SOURCES))
    ap.add_argument("--max-mb", type=float, default=500, help="refuse to fetch more than this (default 500)")
    a = ap.parse_args(argv)
    problems = validate_pins() + (validate_file_pins(load_pins()) if a.source in FILE_SOURCES else [])
    if problems:
        raise SystemExit("pin table malformed: " + "; ".join(problems))
    dest = EXTERNAL / a.source
    dest.mkdir(parents=True, exist_ok=True)
    try:
        if a.source in FILE_SOURCES:
            receipt = fetch_pinned(a.source, a.max_mb, dest)
        else:
            receipt = (fetch_pronto if a.source == "pronto" else fetch_dtu)(a.max_mb, dest)
    except PinError as e:
        raise SystemExit(f"refused: {e}") from None
    (dest / "FETCH_RECEIPT.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(json.dumps(receipt, indent=1))
    return receipt


if __name__ == "__main__":
    main()
