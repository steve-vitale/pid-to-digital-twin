"""Normal operating bands for any historian-style CSV: learn them from a normal-running export, then score a second export.

Two methods (--method). Both fit on the first FIT_FRACTION of the normal CSV (default: the first half) and choose K
on the rest of it, which the fit never saw.

  drift (the default; for real plant data, which drifts slowly):
           Each tag is compared with its own recent past, not with a fixed level. For every sample: the
           10-sample average (exponentially weighted, DRIFT_FAST) minus the 600-sample baseline as it stood one sample
           earlier (exponentially weighted, DRIFT_SLOW; both start as plain running averages of the export being
           scored, so the scored export sets its own level). Slow drift moves the baseline with it and is not flagged;
           a step or a fast change opens a gap between the two averages and is.
           Band on that gap = its normal mean +/- half-width, half-width = max(K x its standard deviation over the
           fit rows, DRIFT_FLOOR x |the tag's mean over the fit rows|): a gap under 1% of the reading is never
           flagged, so a band fitted on a quiet stretch cannot be narrower than a change worth a look.
           The band then follows the reading: where the baseline runs below the tag's normal mean, band and gap mean
           shrink in the same proportion, but to no less than half (DRIFT_SCALE_MIN) and never wider than fitted.
           A flow running at a quarter of its normal reading has about a quarter of the noise (percent-of-reading),
           so its band would otherwise be four times too wide; a tag whose noise does not follow its reading loses
           at most half its width.
           K: given (--k), or the smallest in DRIFT_KS (10, 12, 15, 20) whose share of held-out normal rows with ANY
           tag flagged is under 0.5% (the same 0.5% the generalization matrix allows before a fault). If none meets
           it, K = 20 and the report says so. Windows are in rows (samples), not seconds: 10 and 600 rows are 10 s
           and 10 min at 1 s sampling, 30 min and 30 h at the Tennessee Eastman 3-min sampling.
           These numbers were chosen on development runs and then frozen: first PRONTO test day 3 and half of SKAB,
           then (the scaling) all of PRONTO, SKAB, HAI 21.03 and the TE runs; UCI hydraulic, MetroPT-3 and BattLeDIM
           were scored once afterwards (data/attempts.json, docs/GENERALIZATION.md row 6).
  level (scripts/normal_bands.py's method, kept for the Tennessee Eastman comparison):
           Band per tag = mean +/- K population standard deviations of that tag's good (numeric) values. K given,
           or the smallest in (3, 4, 5, 6) whose worst per-tag false-flag rate on the held-out rows is under 0.5%
           (K = 6 and a note if none). On real data this flags slow drift as a fault (PRONTO, SKAB, HAI 21.03).

  Score:   for each tag in the second CSV, the first sample outside its band. With --fault-start N (a labelled fault
           start, as a 0-based data-row number, or a timestamp/index value from the first column), also: the first
           flag at or after the fault (detection delay), the first run of 3 consecutive flagged samples (the
           detection rule of scripts/fault_detection_eval.py), and every flag before the fault (false alarms).

CSV format (what a historian export usually looks like; comma-separated, '.' as the decimal point):
  - Row 1 is a header: the first cell names the time column, the rest are tag names (non-empty, unique, not numbers).
  - First column: a timestamp (ISO 8601, e.g. 2026-10-01 08:00:00 or 2026-10-01T08:00:00Z) or a numeric sample
    index / elapsed time. It must be filled on every row.
  - Other columns: numbers. A blank or non-numeric cell (e.g. "Bad", "I/O Timeout", "nan") is a BAD sample for that
    tag: it is left out of the fit and is never flagged. It is never replaced by a number.

What this is NOT: not an alarm system and not a fault diagnosis. A value outside its band says "this is unusual
compared with the normal export" (level) or "this tag changed faster than it does in normal running" (drift), nothing
about why. The bands are only as good as the normal export: if it contains upsets, they widen the bands; if it covers
one operating mode, other modes will flag. The drift method by design misses a fault that develops as slowly as
normal drift does, and stops flagging a level that stays wrong once its baseline has caught up (after roughly
DRIFT_SLOW samples).

Model use: none. Plain statistics (stdlib only). Claude (the coding agent) wrote the code.

  python scripts/csv_normal_bands.py --normal normal.csv --score fault.csv --fault-start 160 --out out/csv_bands
  python scripts/csv_normal_bands.py ... --method level      # the TE scripts' fixed-level bands
  writes <out>/csv_normal_bands.json and <out>/csv_normal_bands.md
"""
import argparse
import csv
import json
import math
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

KS = (3, 4, 5, 6)
TARGET = 0.005  # worst-tag false-flag rate on held-out normal data, as in normal_bands.py
METHODS = ("drift", "level")
DEFAULT_METHOD = "drift"
DRIFT_FAST = 10  # samples: the short average each value is smoothed over before comparing
DRIFT_SLOW = 600  # samples: the baseline that follows slow drift
DRIFT_FLOOR = 0.01  # a gap under 1% of the tag's normal mean is never flagged
DRIFT_KS = (10, 12, 15, 20)
DRIFT_SCALE_MIN = 0.5  # a band follows the reading down to half its normal width, never narrower, never wider
RUN = 3  # consecutive flagged samples for a detection, as in fault_detection_eval.py
# Fewer rows than this in the fit or the held-out half and the report warns that its numbers are not to be trusted:
# the relative standard error of a standard deviation is about 1/sqrt(2n), 13% at n = 30 and 35% at n = 4, so a band
# of K sd fitted on fewer rows can be a third too wide or narrow. 30 is the usual rule-of-thumb floor for a sample sd.
MIN_ROWS = 30
FAULT_START_FORMATS = ("a 0-based data-row number (an integer, e.g. 160), or a value of the score CSV's first column: "
                       "a number with a decimal point (e.g. 480.0) or an ISO 8601 timestamp (e.g. 2026-10-01 09:40:00 "
                       "or 2026-10-01T09:40:00Z), which picks the first row at or after it")


class CsvFormatError(ValueError):
    """The CSV is not in the historian shape this tool reads; the message says what to fix."""


def _is_number(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


def parse_time(text):
    """A first-column value: a float (sample index / elapsed time) or an ISO 8601 timestamp (returned as datetime)."""
    text = text.strip()
    if not text:
        raise ValueError("empty")
    try:
        return float(text)
    except ValueError:
        pass
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def parse_value(text):
    """A tag cell: a finite float, or None for a bad sample (blank, non-numeric, nan, inf)."""
    try:
        v = float(text)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def read_historian_csv(path, with_text=False):
    """Returns (time_name, tags, times, rows), plus the first-column texts if with_text. rows[i][j] is a float or None
    (bad). Raises CsvFormatError."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as f:
        lines = [r for r in csv.reader(f) if any(c.strip() for c in r)]
    if not lines:
        raise CsvFormatError(f"{path.name}: empty file; expected a header row then data rows")
    header = [h.strip() for h in lines[0]]
    if len(header) < 2:
        raise CsvFormatError(f"{path.name}: header has {len(header)} column(s); expected a time/index column "
                             "followed by at least one tag column")
    tags = header[1:]
    problems = []
    for j, t in enumerate(tags, start=2):
        if not t:
            problems.append(f"column {j} has an empty tag name")
        elif _is_number(t):
            problems.append(f"column {j} header '{t}' is a number (is the header row missing?)")
    dupes = sorted({t for t in tags if t and tags.count(t) > 1})
    if dupes:
        problems.append("duplicate tag names: " + ", ".join(dupes))
    if problems:
        raise CsvFormatError(f"{path.name}: malformed header: " + "; ".join(problems) +
                             ". Row 1 must be: <time column name>,<tag 1>,<tag 2>,...")
    if len(lines) < 2:
        raise CsvFormatError(f"{path.name}: header only, no data rows")
    times, rows, kind = [], [], None
    for n, r in enumerate(lines[1:], start=2):
        if len(r) != len(header):
            raise CsvFormatError(f"{path.name}: line {n} has {len(r)} cells, the header has {len(header)}")
        try:
            t = parse_time(r[0])
        except ValueError:
            raise CsvFormatError(f"{path.name}: line {n}: first column '{r[0]}' is neither a number nor an ISO 8601 "
                                 "timestamp") from None
        k = (type(t), getattr(t, "tzinfo", None) is not None)
        if kind is None:
            kind = k
        elif k != kind:
            raise CsvFormatError(f"{path.name}: line {n}: first column mixes timestamps and numbers, or timestamps "
                                 "with and without a time zone")
        times.append(t)
        rows.append([parse_value(c) for c in r[1:]])
    if with_text:
        return header[0], tags, times, rows, [r[0].strip() for r in lines[1:]]
    return header[0], tags, times, rows


def elapsed(times, a, b):
    """Time from row a to row b in the first column's units (seconds for timestamps)."""
    d = times[b] - times[a]
    return d.total_seconds() if isinstance(d, timedelta) else d


def fit_bands(tags, rows, k):
    """Per tag: mean, population sd and band over the good values of rows. Tags with no good value get no band."""
    bands = {}
    for j, t in enumerate(tags):
        vals = [r[j] for r in rows if r[j] is not None]
        if not vals:
            bands[t] = None
            continue
        m, s = statistics.fmean(vals), statistics.pstdev(vals)
        sd = s or 1e-9  # a constant tag (as normal_bands.py): any change at all flags it
        bands[t] = {"mean": m, "sd": s, "lo": m - k * sd, "hi": m + k * sd, "fit_good": len(vals),
                    "fit_bad": len(rows) - len(vals), "constant_in_fit": s == 0}
    return bands


def outside(v, band):
    """Strictly outside (a value on the limit is inside, as the gateway's PV < Lo || PV > Hi). Bad is never outside."""
    return v is not None and band is not None and (v < band["lo"] or v > band["hi"])


def flag_matrix(tags, rows, bands):
    return [[outside(r[j], bands[t]) for j, t in enumerate(tags)] for r in rows]


# ------------------------------------------------------------------ drift method

def drift_gaps(values, fast=DRIFT_FAST, slow=DRIFT_SLOW, levels=None):
    """For one tag's series (floats, None = bad): per sample, the fast average minus the slow baseline as it stood
    one sample earlier. Both are exponentially weighted averages that start as running averages (weight max(1/T,
    1/n) on the n-th good sample), so the start of the series sets the level. None for bad samples and the first
    good one (no baseline yet). Bad samples are skipped: they neither move the averages nor get a gap. If `levels`
    is a list, the baseline each gap was taken against is appended to it (None where the gap is None)."""
    f = base = None
    n = 0
    out = []
    for x in values:
        if x is None:
            out.append(None)
            if levels is not None:
                levels.append(None)
            continue
        n += 1
        if base is None:
            f = base = x
            out.append(None)
            if levels is not None:
                levels.append(None)
            continue
        f += max(1.0 / fast, 1.0 / n) * (x - f)
        out.append(f - base)
        if levels is not None:
            levels.append(base)
        base += max(1.0 / slow, 1.0 / n) * (x - base)
    return out


def gap_columns(tags, rows):
    """Per tag: (gaps, baselines), as drift_gaps."""
    out = []
    for j in range(len(tags)):
        lv = []
        out.append((drift_gaps([r[j] for r in rows], levels=lv), lv))
    return out


def level_scale(level, normal_mean):
    """How much of its normal width a band keeps at this baseline: the baseline as a share of the tag's normal mean,
    kept between DRIFT_SCALE_MIN and 1 (1 when the normal mean is 0). A flow running at a quarter of its normal
    reading has proportionally less noise; a tag whose noise does not follow its reading loses at most half."""
    if not normal_mean:
        return 1.0
    return min(1.0, max(DRIFT_SCALE_MIN, abs(level) / abs(normal_mean)))


def fit_drift(tags, rows):
    """Per tag, over the fit rows: the level (mean, sd of the good values) and the gap's mean and sd. No K yet."""
    gaps = gap_columns(tags, rows)
    stats = {}
    for j, t in enumerate(tags):
        vals = [r[j] for r in rows if r[j] is not None]
        g = [x for x in gaps[j][0] if x is not None]
        if not g:
            stats[t] = None
            continue
        m, sd = statistics.fmean(vals), statistics.pstdev(vals)
        stats[t] = {"mean": m, "sd": sd, "gap_mean": statistics.fmean(g), "resid_sd": statistics.pstdev(g),
                    "floor": DRIFT_FLOOR * abs(m), "fit_good": len(vals), "fit_bad": len(rows) - len(vals),
                    "constant_in_fit": sd == 0}
    return stats


def drift_bands(stats, k):
    bands = {}
    for t, s in stats.items():
        if s is None:
            bands[t] = None
            continue
        half = max(k * s["resid_sd"], s["floor"]) or k * 1e-9  # a constant zero tag: any change flags it
        bands[t] = dict(s, half_width=half, limited_by="floor" if s["floor"] >= k * s["resid_sd"] else "spread")
    return bands


def drift_flags(tags, gaps, bands):
    """Flag matrix [row][tag] from precomputed (gaps, baselines) columns. The band (gap mean and half-width) is
    scaled by level_scale of the baseline the gap was taken against."""
    n = len(gaps[0][0]) if gaps else 0
    cols = []
    for j, t in enumerate(tags):
        b = bands[t]
        if b is None:
            cols.append([False] * n)
            continue
        col = []
        for g, lv in zip(*gaps[j]):
            if g is None:
                col.append(False)
                continue
            r = level_scale(lv, b["mean"])
            col.append(abs(g - b["gap_mean"] * r) > b["half_width"] * r)
        cols.append(col)
    return [[c[i] for c in cols] for i in range(n)]


def choose_k_drift(tags, stats, held_gaps):
    """Smallest K in DRIFT_KS whose share of held-out rows with any tag flagged is under TARGET."""
    table = {}
    for k in DRIFT_KS:
        fl = drift_flags(tags, held_gaps, drift_bands(stats, k))
        per = {t: sum(f[j] for f in fl) / len(fl) for j, t in enumerate(tags)}
        worst = max(per, key=per.get)
        table[k] = {"worst_tag_rate": per[worst], "worst_tag": worst, "mean_tag_rate": statistics.fmean(per.values()),
                    "any_tag_rate": sum(any(f) for f in fl) / len(fl)}
    for k in DRIFT_KS:
        if table[k]["any_tag_rate"] < TARGET:
            return k, table, True
    return DRIFT_KS[-1], table, False


def choose_k(tags, fit_rows, held_rows):
    """Smallest K in KS whose worst-tag false-flag rate on held_rows is under TARGET. Returns (k, table, met)."""
    table = {}
    for k in KS:
        b = fit_bands(tags, fit_rows, k)
        fl = flag_matrix(tags, held_rows, b)
        per = {t: sum(f[j] for f in fl) / len(fl) for j, t in enumerate(tags)}
        worst = max(per, key=per.get)
        table[k] = {"worst_tag_rate": per[worst], "worst_tag": worst, "mean_tag_rate": statistics.fmean(per.values()),
                    "any_tag_rate": sum(any(f) for f in fl) / len(fl)}
    for k in KS:
        if table[k]["worst_tag_rate"] < TARGET:
            return k, table, True
    return KS[-1], table, False


def first_run(flags, start, run=RUN):
    n = 0
    for i in range(start, len(flags)):
        n = n + 1 if flags[i] else 0
        if n == run:
            return i - run + 1
    return None


def alarm_events(flags, run=RUN):
    events, n = 0, 0
    for f in flags:
        n = n + 1 if f else 0
        events += n == run
    return events


def resolve_fault_start(text, times):
    """--fault-start: an integer is a 0-based data-row number; anything else (a timestamp, or a number written with a
    decimal point such as 480.0) picks the first row whose first-column value is at or after it."""
    try:
        i = int(text)
    except ValueError:
        i = None
    if i is not None:
        if not 0 <= i < len(times):
            raise SystemExit(f"--fault-start {i} is outside the {len(times)} data rows (0-based row number)")
        return i
    try:
        t = parse_time(text)
    except ValueError:
        raise SystemExit(f"error: --fault-start '{text}' is not understood. It takes {FAULT_START_FORMATS}.") from None
    try:
        for i, x in enumerate(times):
            if x >= t:
                return i
    except TypeError:  # a timestamp against a numeric first column (or the reverse, or time zone vs none)
        kind = "timestamps" if isinstance(times[0], datetime) else "numbers"
        raise SystemExit(f"error: --fault-start '{text}' does not match the score CSV's first column, which holds "
                         f"{kind}"
                         f"{' (with a time zone)' if kind == 'timestamps' and times[0].tzinfo else ''}"
                         f". It takes {FAULT_START_FORMATS}.") from None
    raise SystemExit(f"--fault-start {text}: no row at or after that time")


def score(tags, times, rows, bands, fault_start=None, flags=None):
    fl = flag_matrix(tags, rows, bands) if flags is None else flags
    any_flag = [any(f) for f in fl]
    first = {}
    for j, t in enumerate(tags):
        hit = next((i for i in range(fault_start or 0, len(rows)) if fl[i][j]), None)
        first[t] = hit
    per_tag = {t: {"first_outside_row": first[t],
                   "first_outside_time": None if first[t] is None else str(times[first[t]]),
                   "flagged_samples": sum(f[j] for f in fl),
                   "bad_samples": sum(r[j] is None for r in rows)} for j, t in enumerate(tags)}
    result = {"rows": len(rows), "per_tag": per_tag,
              "flagged_samples_any_tag": sum(any_flag), "alarm_events_run3": alarm_events(any_flag)}
    if fault_start is not None:
        pre = any_flag[:fault_start]
        single = next((i for i in range(fault_start, len(rows)) if any_flag[i]), None)
        det = first_run(any_flag, fault_start)
        order = sorted((i, t) for t, i in first.items() if i is not None)
        result["fault"] = {
            "fault_start_row": fault_start, "fault_start_time": str(times[fault_start]),
            "first_flag_row": single, "first_flag_delay": None if single is None else elapsed(times, fault_start, single),
            "detection_run3_row": det, "detection_run3_delay": None if det is None else elapsed(times, fault_start, det),
            "first_tags": [{"tag": t, "row": i, "delay": elapsed(times, fault_start, i)} for i, t in order],
            "false_alarms_before_fault": {
                "samples": len(pre), "flagged_samples": sum(pre), "alarm_events_run3": alarm_events(pre),
                "tags": sorted({t for j, t in enumerate(tags) for f in fl[:fault_start] if f[j]})},
            "post_fault_detection_rate": round(sum(any_flag[fault_start:]) / (len(rows) - fault_start), 4)}
    return result


def small_sample_warnings(n_fit, n_held, k_chosen, bands):
    """Plain-language warnings when the fit or the K-choice rows are too few to trust (see MIN_ROWS)."""
    w = []
    if n_fit < MIN_ROWS:
        w.append(f"only {n_fit} fit rows (fewer than {MIN_ROWS}): each band's mean and sd are rough estimates, so the "
                 "bands may be much too wide or too narrow. Use a longer normal export.")
    if k_chosen and n_held < MIN_ROWS:
        w.append(f"only {n_held} held-out rows (fewer than {MIN_ROWS}) to choose K on: the false-flag rates in the K "
                 f"table rest on too few samples, and with fewer than {round(1 / TARGET)} rows a single flag already "
                 f"exceeds the {TARGET:.1%} target, so K is effectively 'the smallest K with no flag at all'. "
                 "Use a longer normal export or pass --k.")
    thin = sorted(t for t, b in bands.items() if b is not None and b["fit_good"] < MIN_ROWS)
    if thin and n_fit >= MIN_ROWS:
        w.append(f"fewer than {MIN_ROWS} good fit values for: {', '.join(thin)} (the rest are bad cells); "
                 "their bands are rough estimates.")
    return w


METHOD_TEXT = {
    "level": "band = mean +/- K population sd over the fit rows' good values (scripts/normal_bands.py method)",
    "drift": f"gap = {DRIFT_FAST}-sample average minus the {DRIFT_SLOW}-sample baseline one sample earlier (both "
             f"exponentially weighted, starting as running averages of the export scored); band on the gap = its "
             f"fit mean +/- max(K x its fit sd, {DRIFT_FLOOR:.0%} of the tag's fit mean), both scaled by the "
             f"baseline's share of the fit mean, kept between {DRIFT_SCALE_MIN} and 1; slow drift moves the "
             f"baseline and is not flagged, a step or fast change is",
}


def run(normal, score_csv=None, fault_start=None, fit_fraction=0.5, k=None, method=DEFAULT_METHOD):
    if method not in METHODS:
        raise SystemExit(f"error: --method must be one of {', '.join(METHODS)}, got {method!r}")
    tname, tags, times, rows = read_historian_csv(normal)
    n_fit = int(len(rows) * fit_fraction)
    if n_fit < 2:
        raise SystemExit(f"fit portion has {n_fit} rows; need at least 2")
    fit_rows, held = rows[:n_fit], rows[n_fit:]
    if k is None and not held:
        raise SystemExit("--fit-fraction 1 leaves nothing to choose K on; pass --k")
    table = met = None
    if method == "level":
        if k is None:
            k, table, met = choose_k(tags, fit_rows, held)
        bands = fit_bands(tags, fit_rows, k)
        rule = f"smallest K in {list(KS)} with worst-tag false-flag rate < {TARGET:.1%} on held-out rows"

        def flags_for(tg, rs, bd):
            return None  # score() applies the fixed bands
    else:
        stats = fit_drift(tags, fit_rows)
        if k is None:
            k, table, met = choose_k_drift(tags, stats, gap_columns(tags, held))
        bands = drift_bands(stats, k)
        rule = f"smallest K in {list(DRIFT_KS)} with the share of held-out rows with any tag flagged < {TARGET:.1%}"

        def flags_for(tg, rs, bd):
            return drift_flags(tg, gap_columns(tg, rs), bd)
    out = {"method_name": method, "method": METHOD_TEXT[method],
           "normal_csv": Path(normal).name, "time_column": tname,
           "time_kind": "timestamp" if isinstance(times[0], datetime) else "number", "tags": tags, "k": k,
           "k_selection": None if table is None else {
               "rule": rule,
               "target_met": met, "by_k": {str(kk): {a: (round(b, 4) if isinstance(b, float) else b)
                                                     for a, b in v.items()} for kk, v in table.items()}},
           "fit_rows": f"0-{n_fit - 1}", "held_out_rows": f"{n_fit}-{len(rows) - 1}" if held else None,
           "bands": {t: None if b is None else {a: (round(v, 6) if isinstance(v, float) else v) for a, v in b.items()}
                     for t, b in bands.items()},
           "no_band": [t for t, b in bands.items() if b is None]}
    warnings = small_sample_warnings(n_fit, len(held), table is not None, bands)
    if warnings:  # the key only appears when there is something to warn about
        out["warnings"] = warnings
    if held:
        out["held_out_normal"] = score(tags, times[n_fit:], held, bands, flags=flags_for(tags, held, bands))
        out["held_out_normal"].pop("per_tag")
    if score_csv:
        sname, stags, stimes, srows = read_historian_csv(score_csv)
        missing = [t for t in tags if t not in stags]
        extra = [t for t in stags if t not in tags]
        common = [t for t in tags if t in stags]
        if not common:
            raise SystemExit("the score CSV shares no tag names with the normal CSV")
        pick = [stags.index(t) for t in common]
        srows = [[r[j] for j in pick] for r in srows]
        fs = None if fault_start is None else resolve_fault_start(str(fault_start), stimes)
        cb = {t: bands[t] for t in common}
        out["scored"] = dict(score(common, stimes, srows, cb, fs, flags=flags_for(common, srows, cb)),
                             csv=Path(score_csv).name, tags_missing=missing, tags_not_in_normal=extra)
    return out


def _fmt(v):
    return "-" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v))


def markdown(r, units):
    md = ["# Normal bands from a historian CSV", "",
          f"Generated by `scripts/csv_normal_bands.py` (method `{r['method_name']}`). " + r["method"] + ".", "",
          f"- Normal CSV: `{r['normal_csv']}`; fit rows {r['fit_rows']}; held-out rows {_fmt(r['held_out_rows'])}; "
          f"{len(r['tags'])} tags.", f"- K = {r['k']}" +
          ("" if r["k_selection"] is None else
           f" ({r['k_selection']['rule']}; target {'met' if r['k_selection']['target_met'] else 'NOT met'})") + "."]
    if r["no_band"]:
        md.append(f"- No good values in the fit, so no band: {', '.join(r['no_band'])}.")
    for w in r.get("warnings", []):
        md.append(f"- **Warning (small sample):** {w}")
    if r["k_selection"]:
        md += ["", "| K | False flags, worst tag | Mean tag | Any tag flagged |", "|---|---|---|---|"]
        md += [f"| {k} | {v['worst_tag_rate']:.1%} ({v['worst_tag']}) | {v['mean_tag_rate']:.2%} | "
               f"{v['any_tag_rate']:.1%} |" for k, v in r["k_selection"]["by_k"].items()]
    if r["method_name"] == "drift":
        md += ["", "Band half-width on the gap, per tag, at the normal reading (set by the floor where the fit rows "
                   f"vary less than {DRIFT_FLOOR:.0%} of the reading allows; where the baseline runs lower, the band "
                   f"shrinks in proportion, to no less than {DRIFT_SCALE_MIN:.0%} of this):", "",
               "| Tag | Fit mean | Gap sd | Half-width | Set by |", "|---|---|---|---|---|"]
        md += [f"| {t} | {b['mean']:.6g} | {b['resid_sd']:.3g} | {b['half_width']:.3g} | {b['limited_by']} |"
               for t, b in r["bands"].items() if b is not None]
    if "held_out_normal" in r:
        h = r["held_out_normal"]
        md += ["", f"Held-out normal rows at K = {r['k']}: {h['flagged_samples_any_tag']}/{h['rows']} samples with any "
                   f"tag outside its band; {h['alarm_events_run3']} run-of-{RUN} events."]
    s = r.get("scored")
    if s:
        md += ["", f"## Scored: `{s['csv']}` ({s['rows']} rows)", ""]
        if s["tags_missing"] or s["tags_not_in_normal"]:
            md.append(f"Tags missing from the scored CSV: {', '.join(s['tags_missing']) or 'none'}; "
                      f"not in the normal CSV (unscored): {', '.join(s['tags_not_in_normal']) or 'none'}.")
            md.append("")
        f = s.get("fault")
        if f:
            fa = f["false_alarms_before_fault"]
            md += [f"Labelled fault start: row {f['fault_start_row']} ({r['time_column']} = {f['fault_start_time']}). "
                   f"Delays are in {units}.", "",
                   f"- First flag at or after the fault: row {_fmt(f['first_flag_row'])}, delay "
                   f"{_fmt(f['first_flag_delay'])}.",
                   f"- Detection ({RUN} consecutive flagged samples, any tag): row {_fmt(f['detection_run3_row'])}, delay "
                   f"{_fmt(f['detection_run3_delay'])}.",
                   f"- Before the fault (false alarms): {fa['flagged_samples']}/{fa['samples']} flagged samples, "
                   f"{fa['alarm_events_run3']} run-of-{RUN} events; tags: {', '.join(fa['tags']) or 'none'}.",
                   f"- Share of post-fault samples flagged: {f['post_fault_detection_rate']:.1%}.", "",
                   "| Tag | First row outside band (at/after fault) | Delay | Flagged samples | Bad samples |",
                   "|---|---|---|---|---|"]
            delay = {x["tag"]: x["delay"] for x in f["first_tags"]}
            order = sorted(s["per_tag"], key=lambda t: (s["per_tag"][t]["first_outside_row"] is None,
                                                        s["per_tag"][t]["first_outside_row"] or 0, t))
            md += [f"| {t} | {_fmt(s['per_tag'][t]['first_outside_row'])} | {_fmt(delay.get(t))} | "
                   f"{s['per_tag'][t]['flagged_samples']} | {s['per_tag'][t]['bad_samples']} |" for t in order]
        else:
            md += ["| Tag | First row outside band | Flagged samples | Bad samples |", "|---|---|---|---|"]
            md += [f"| {t} | {_fmt(v['first_outside_row'])} | {v['flagged_samples']} | {v['bad_samples']} |"
                   for t, v in s["per_tag"].items()]
    return "\n".join(md) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--normal", required=True, help="CSV of normal running (bands are fitted on it)")
    ap.add_argument("--score", help="CSV to check against the bands")
    ap.add_argument("--fault-start", help="labelled fault start: an integer is a 0-based data row; a timestamp or a "
                                          "number with a decimal point (480.0) is matched against the first column")
    ap.add_argument("--fit-fraction", type=float, default=0.5, help="share of the normal CSV used to fit (default 0.5)")
    ap.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD,
                    help="drift (default): each tag against its own slow baseline, for real data that drifts; "
                         "level: fixed mean +/- K sd bands, the Tennessee Eastman scripts' method")
    ap.add_argument("--k", type=float, help="band half-width in sd; default: chosen on the held-out normal rows")
    ap.add_argument("--units", default=None, help="label for delays (default: 'seconds' for timestamps, else the "
                                                   "first column's units)")
    ap.add_argument("--out", default="out/csv_normal_bands", help="output directory for the .md and .json")
    a = ap.parse_args(argv)
    if a.fault_start is not None and not a.score:
        ap.error("--fault-start needs --score")
    if a.k is not None and not (a.k > 0 and math.isfinite(a.k)):
        ap.error(f"--k must be a positive number of standard deviations, got {a.k}")
    try:
        r = run(a.normal, a.score, a.fault_start, a.fit_fraction, a.k, a.method)
    except CsvFormatError as e:
        raise SystemExit(f"error: {e}") from None
    except OSError as e:
        raise SystemExit(f"error: can't read {e.filename}: {e.strerror}") from None
    except ValueError as e:  # a --fault-start that is neither a row number nor a time in the first column
        raise SystemExit(f"error: {e}") from None
    units = a.units or ("seconds" if r["time_kind"] == "timestamp" else f"'{r['time_column']}' units")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    # LF on every OS, so the committed example regenerates byte for byte on Windows too
    (out / "csv_normal_bands.json").write_text(json.dumps(r, indent=1), encoding="utf-8", newline="\n")
    md = markdown(r, units)
    (out / "csv_normal_bands.md").write_text(md, encoding="utf-8", newline="\n")
    print(md)
    return r


if __name__ == "__main__":
    main()
