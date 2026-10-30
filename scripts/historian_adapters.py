"""Turn three public historian-style sources into the normal/score CSV pairs scripts/csv_normal_bands.py reads.

Support for the generalization matrix (row 6). Each function reads downloaded files as data only (zipfile, csv,
plain-text parsing; nothing downloaded is executed or imported) and writes historian CSVs into a folder the caller
gives, normally a temporary one. The mappings below were written down before any of these sources was scored
(data/attempts.json A165) and are not changed per result.

UCI condition monitoring of hydraulic systems (CC BY 4.0; data/external/uci-hydraulic/*.zip)
  One historian row per 60-s load cycle: each of the 17 sensors (PS1-6, EPS1, FS1-2, TS1-4, VS1, CE, CP, SE)
  averaged over the cycle; time column `seconds` = (cycle - 1) x 60. Labels from profile.txt (cooler %, valve %,
  pump leakage 0-2, accumulator bar). Three runs, one per cooler grade (cycles 1-732, 733-1464, 1465-2205); each
  opens with a 200-210-cycle block at constant grades. Normal CSV = the block's first 100 cycles; score CSV = the
  rest of the section; fault start = the first cycle graded worse than the block on any component (cooler or valve
  lower, pump leakage higher, accumulator lower).
MetroPT-3 (CC BY 4.0; data/external/metropt3/metropt3.zip)
  The 7 analogue signals (TP2, TP3, H1, DV_pressure, Reservoirs, Oil_temperature, Motor_current); the 8 digital
  on/off signals and the unnamed index column are left out. Timestamps as logged (about 10 s apart). Normal CSV =
  2020-02-01 00:00 to 2020-02-08 00:00 (end exclusive). One run per failure in the dataset's own report table
  (METROPT_FAILURES): score CSV = 24 h before the start to the end (inclusive); fault start = the report's start.
BattLeDIM 2018 (CC BY 4.0; data/external/battledim)
  2018_SCADA_Pressures (33), _Flows (3) and _Levels (1) joined row by row (their timestamps must agree); ';'
  separator and decimal comma converted to ',' and '.'. 5-min samples. Normal CSV = 2018-01-01 00:00 up to the first
  leak start (2018-01-08 13:30, exclusive). One run per leak in dataset_configuration.yaml that starts in 2018: score
  CSV = 2 days before its start to the earlier of its end (repair) and 7 days after its start; fault start = the
  leak start. Leaks already running are part of later runs' pre-fault rows.
BattLeDIM 2019 (CC BY 4.0, same Zenodo record; data/external/battledim-2019) -- the cyclic method's held-out source
  (data/attempts.json A178, mapping written before any run): 2019_SCADA_Pressures, _Flows, _Levels joined as for
  2018. Normal CSV = 2019-01-01 00:00 up to the first leak that STARTS in 2019 (p523, 2019-01-15 23:00, exclusive):
  the four leaks running on from 2018 (p257, p427, p810, p654) are part of normal. One run per leak starting in 2019
  (19), windows as for 2018.

  import historian_adapters as ha
  runs = ha.metropt3_runs(zip_path, out_dir)   # [{"name", "normal", "score", "fault_start_row", "what", ...}]
"""
import csv
import io
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL = ROOT / "data" / "external"
MAX_MEMBER = 400 * 1024 * 1024  # refuse a zip member larger than this (the largest real one is 218 MB)


def _member(zf, name):
    info = zf.getinfo(name)
    if info.file_size > MAX_MEMBER:
        raise ValueError(f"{name}: {info.file_size} bytes, more than the {MAX_MEMBER} cap")
    return io.TextIOWrapper(zf.open(name), encoding="latin-1", newline="")


def _write(path, header, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return Path(path)


# ------------------------------------------------------------------ UCI hydraulic

UCI_SENSORS = ("PS1", "PS2", "PS3", "PS4", "PS5", "PS6", "EPS1", "FS1", "FS2", "TS1", "TS2", "TS3", "TS4", "VS1",
               "CE", "CP", "SE")
UCI_SECTIONS = ((1, 732), (733, 1464), (1465, 2205))  # cooler 3 %, 20 %, 100 %
UCI_NORMAL_CYCLES = 100


def uci_cycle_means(lines):
    """Lines of one sensor file (one cycle per line, tab-separated samples) -> per-cycle means."""
    out = []
    for line in lines:
        vals = [float(x) for x in line.split()]
        if vals:
            out.append(sum(vals) / len(vals))
    return out


def uci_profile(lines):
    """profile.txt lines -> [(cooler, valve, pump, accumulator, stable)] per cycle."""
    return [tuple(int(float(x)) for x in line.split()) for line in lines if line.strip()]


def uci_worse(a, b):
    """True if grades b are worse than a on any component (cooler/valve lower, pump higher, accumulator lower)."""
    return b[0] < a[0] or b[1] < a[1] or b[2] > a[2] or b[3] < a[3]


def uci_runs_from(means, profile, dest):
    """means: {sensor: [per-cycle mean]}; profile: per-cycle grades. Writes the three runs' CSVs into dest."""
    header = ["seconds"] + list(UCI_SENSORS)
    rows = [[float(i * 60)] + [repr(means[s][i]) for s in UCI_SENSORS] for i in range(len(profile))]
    runs = []
    for n, (a, b) in enumerate(UCI_SECTIONS, start=1):
        lo, hi = a - 1, b  # 0-based, end exclusive
        block = profile[lo][:4]
        if any(profile[i][:4] != block for i in range(lo, lo + UCI_NORMAL_CYCLES)):
            raise ValueError(f"UCI section {n}: grades change inside the first {UCI_NORMAL_CYCLES} cycles")
        fault = next((i for i in range(lo + UCI_NORMAL_CYCLES, hi) if uci_worse(block, profile[i][:4])), None)
        if fault is None:
            raise ValueError(f"UCI section {n}: no cycle graded worse than its opening block")
        start = lo + UCI_NORMAL_CYCLES
        normal = _write(Path(dest) / f"uci_s{n}_normal.csv", header, rows[lo:start])
        score = _write(Path(dest) / f"uci_s{n}_score.csv", header, rows[start:hi])
        runs.append({"name": f"section{n}", "normal": normal, "score": score, "fault_start_row": fault - start,
                     "fault_cycle": fault + 1, "block_grades": list(block), "fault_grades": list(profile[fault][:4]),
                     "what": f"cycles {a}-{b}: normal = cycles {a}-{a + UCI_NORMAL_CYCLES - 1} at grades {block}; "
                             f"fault = cycle {fault + 1} at {profile[fault][:4]}"})
    return runs


def uci_hydraulic_runs(dest, zip_path=None):
    zip_path = Path(zip_path or next((EXTERNAL / "uci-hydraulic").glob("*.zip")))
    with zipfile.ZipFile(zip_path) as zf:
        profile = uci_profile(_member(zf, "profile.txt"))
        means = {s: uci_cycle_means(_member(zf, f"{s}.txt")) for s in UCI_SENSORS}
    for s, m in means.items():
        if len(m) != len(profile):
            raise ValueError(f"UCI {s}: {len(m)} cycles, profile.txt has {len(profile)}")
    return uci_runs_from(means, profile, dest)


# ------------------------------------------------------------------ MetroPT-3

METROPT_ANALOGUE = ("TP2", "TP3", "H1", "DV_pressure", "Reservoirs", "Oil_temperature", "Motor_current")
METROPT_NORMAL = ("2020-02-01 00:00:00", "2020-02-08 00:00:00")
# The failure table of the dataset's "Data Description_Metro.pdf" (start, end, failure).
METROPT_FAILURES = (("2020-04-18 00:00:00", "2020-04-18 23:59:00", "air leak"),
                    ("2020-05-29 23:30:00", "2020-05-30 06:00:00", "air leak"),
                    ("2020-06-05 10:00:00", "2020-06-07 14:30:00", "air leak"),
                    ("2020-07-15 14:30:00", "2020-07-15 19:00:00", "air leak"))
METROPT_BEFORE = timedelta(hours=24)


def metropt_runs_from(rows_iter, dest):
    """rows_iter: csv rows of the MetroPT-3 file (header first). Writes normal + one score CSV per failure."""
    it = iter(rows_iter)
    head = [h.strip() for h in next(it)]
    it_ = head.index("timestamp")
    pick = [head.index(c) for c in METROPT_ANALOGUE]
    n0, n1 = (datetime.fromisoformat(x) for x in METROPT_NORMAL)
    wins = [(datetime.fromisoformat(a) - METROPT_BEFORE, datetime.fromisoformat(a), datetime.fromisoformat(b), w)
            for a, b, w in METROPT_FAILURES]
    header = ["timestamp"] + list(METROPT_ANALOGUE)
    normal, scores = [], [[] for _ in wins]
    fault_rows = [None] * len(wins)
    for r in it:
        if not r:
            continue
        t = datetime.fromisoformat(r[it_].strip())
        row = [r[it_].strip()] + [r[j] for j in pick]
        if n0 <= t < n1:
            normal.append(row)
        for k, (a, s, b, _) in enumerate(wins):
            if a <= t <= b:
                if fault_rows[k] is None and t >= s:
                    fault_rows[k] = len(scores[k])
                scores[k].append(row)
    runs = []
    npath = _write(Path(dest) / "metropt_normal.csv", header, normal)
    for k, (a, s, b, what) in enumerate(wins):
        if fault_rows[k] is None:
            raise ValueError(f"MetroPT failure {k + 1}: no row at or after its start {s}")
        runs.append({"name": f"failure{k + 1}", "normal": npath,
                     "score": _write(Path(dest) / f"metropt_failure{k + 1}.csv", header, scores[k]),
                     "fault_start_row": fault_rows[k], "rows": len(scores[k]),
                     "what": f"{what} {s:%Y-%m-%d %H:%M} to {b:%Y-%m-%d %H:%M} (report); scored from {a:%Y-%m-%d %H:%M}"})
    return runs


def metropt3_runs(dest, zip_path=None):
    zip_path = Path(zip_path or EXTERNAL / "metropt3" / "metropt3.zip")
    with zipfile.ZipFile(zip_path) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        return metropt_runs_from(csv.reader(_member(zf, name)), dest)


# ------------------------------------------------------------------ BattLeDIM 2018

BATTLEDIM_FILES = ("2018_SCADA_Pressures.csv", "2018_SCADA_Flows.csv", "2018_SCADA_Levels.csv")
BATTLEDIM_BEFORE = timedelta(days=2)
BATTLEDIM_AFTER = timedelta(days=7)


def decimal_comma(text):
    return text.strip().replace(",", ".")


def battledim_leaks(config_text, year=2018):
    """dataset_configuration.yaml text -> [(link, start, end, type)] for leaks starting in `year` (a plain-text read
    of the '- link, start, end, diameter, type, peak' lines under 'leakages:'; no YAML library)."""
    out, inside = [], False
    for line in config_text.splitlines():
        s = line.strip()
        if s.startswith("leakages:"):
            inside = True
            continue
        if inside:
            if not s.startswith("-"):
                if s and not s.startswith("#"):
                    break
                continue
            parts = [p.strip() for p in s.lstrip("-").split(",")]
            if len(parts) < 5 or parts[0].startswith("#"):
                continue
            start, end = (datetime.fromisoformat(p) for p in parts[1:3])
            if start.year == year:
                out.append((parts[0], start, end, parts[4]))
    return out


def battledim_join(tables):
    """tables: list of csv-row lists (';'-separated files already split). Joins columns row by row."""
    heads = [t[0] for t in tables]
    n = len(tables[0])
    if any(len(t) != n for t in tables):
        raise ValueError("BattLeDIM SCADA files have different row counts")
    header = ["Timestamp"] + [h for hd in heads for h in hd[1:]]
    rows = []
    for i in range(1, n):
        ts = {t[i][0].strip() for t in tables}
        if len(ts) != 1:
            raise ValueError(f"BattLeDIM row {i}: timestamps disagree: {sorted(ts)}")
        rows.append([tables[0][i][0].strip()] + [decimal_comma(c) for t in tables for c in t[i][1:]])
    return header, rows


def battledim_files(year=2018):
    """The SCADA files of one BattLeDIM year (pressures, flows, level)."""
    return tuple(f"{year}{n[4:]}" for n in BATTLEDIM_FILES)


def battledim_runs_from(tables, config_text, dest, year=2018):
    """The normal CSV (the export's start up to the first leak that STARTS in `year`; leaks running on from an
    earlier year are part of it) and one score CSV per leak starting in `year`. File names carry the year after
    2018 (battledim2019_normal.csv ...); 2018's keep their original names."""
    header, rows = battledim_join(tables)
    times = [datetime.fromisoformat(r[0]) for r in rows]
    leaks = battledim_leaks(config_text, year)
    first = min(s for _, s, _, _ in leaks)
    stem = "battledim" if year == 2018 else f"battledim{year}"
    normal = _write(Path(dest) / f"{stem}_normal.csv", header, [r for r, t in zip(rows, times) if t < first])
    runs = []
    for link, s, e, kind in sorted(leaks, key=lambda x: x[1]):
        a, b = s - BATTLEDIM_BEFORE, min(e, s + BATTLEDIM_AFTER)
        sel = [i for i, t in enumerate(times) if a <= t <= b]
        fs = next(k for k, i in enumerate(sel) if times[i] >= s)
        runs.append({"name": link, "normal": normal, "kind": kind,
                     "score": _write(Path(dest) / f"{stem}_{link}.csv", header, [rows[i] for i in sel]),
                     "fault_start_row": fs, "rows": len(sel),
                     "what": f"leak {link} ({kind}) from {s:%Y-%m-%d %H:%M}; scored {a:%Y-%m-%d %H:%M} to "
                             f"{b:%Y-%m-%d %H:%M}"})
    return runs


def battledim_runs(dest, folder=None, year=2018):
    folder = Path(folder or EXTERNAL / ("battledim" if year == 2018 else f"battledim-{year}"))
    tables = []
    for name in battledim_files(year):
        with (folder / name).open(encoding="utf-8-sig", newline="") as f:
            tables.append([r for r in csv.reader(f, delimiter=";") if r])
    config = (folder / "dataset_configuration.yaml").read_text(encoding="utf-8")
    return battledim_runs_from(tables, config, dest, year)


def battledim_2019_runs(dest, folder=None):
    """The held-out source of the cyclic method (data/attempts.json A178): BattLeDIM's 2019 evaluation year."""
    return battledim_runs(dest, folder, year=2019)
