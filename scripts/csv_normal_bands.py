"""Normal operating bands for any historian-style CSV: learn them from a normal-running export, then score a second export.

Three methods (--method), and a default that picks one. Each fits on the first FIT_FRACTION of the normal CSV
(default: the first half) and chooses K on the rest of it, which the fit never saw.

  auto (the default): cyclic when the data has a daily cycle, else drift. A daily cycle: the first column is a
           timestamp, the fit rows span at least CYCLIC_MIN_DAYS (2) days, and a time-of-day profile fitted on them
           explains at least CYCLIC_MIN_R2 (0.1) of the held-out rows' variation (median over tags; each tag's level
           may move between the halves). The report's method_choice says which was chosen and why.
  drift (for real plant data, which drifts slowly):
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
  cyclic (for a daily cycle: water demand, shifts, day/night load):
           Each value minus its tag's time-of-day profile: the fit rows' mean in each of CYCLIC_SLOTS (48) slots of
           30 minutes (a slot with fewer than CYCLIC_MIN_SLOT good fit values uses the tag's fit mean). Then a median
           of 3 samples, so a single-sample spike never reaches the averages, then the drift method's gap on that
           residual, with the drift method's band (K x the gap's fit sd, never under 1% of the tag's fit mean) not
           scaled with the reading (the residual's baseline is not a reading). The daily swing no longer sets the
           band's width, so a step it would hide shows. The profile is the fit rows' clock profile only: a cycle not
           tied to the clock (a compressor's load/unload) is not removed, and a mode taken from a process tag was
           rejected because the fault can move that tag (data/attempts.json A183). Without timestamps the profile is
           flat (one slot) and the report warns. Developed on BattLeDIM 2018, UCI hydraulic and MetroPT-3 with the
           earlier sources kept unchanged; BattLeDIM 2019 scored once afterwards (A178, A184).
  level (scripts/normal_bands.py's method, kept for the Tennessee Eastman comparison; never chosen by auto):
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
    index / elapsed time. It must be filled on every row and strictly increase (oldest first, no duplicate instants).
  - Other columns: numbers. A blank or non-numeric cell (e.g. "Bad", "I/O Timeout", "nan") is a BAD sample for that
    tag: it is left out of the fit and is never flagged. It is never replaced by a number.

What this is NOT: not an alarm system and not a fault diagnosis. A value outside its band says "this is unusual
compared with the normal export" (level) or "this tag changed faster than it does in normal running" (drift), nothing
about why. The cyclic method needs normal running covering the times of day it scores (a slot never seen in the fit
uses the tag's mean). The bands are only as good as the normal export: if it contains upsets, they widen the bands; if it covers
one operating mode, other modes will flag. The drift method by design misses a fault that develops as slowly as
normal drift does, and stops flagging a level that stays wrong once its baseline has caught up (after roughly
DRIFT_SLOW samples).

Model use: none. Plain statistics (stdlib only). Claude (the coding agent) wrote the code.

  python scripts/csv_normal_bands.py --normal normal.csv --score fault.csv --fault-start 160 --out out/csv_bands
  python scripts/csv_normal_bands.py ... --method level      # the TE scripts' fixed-level bands
  python scripts/csv_normal_bands.py ... --method cyclic     # time-of-day profile even if auto would not pick it
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
from output_paths import protect_outputs

KS = (3, 4, 5, 6)
TARGET = 0.005  # worst-tag false-flag rate on held-out normal data, as in normal_bands.py
METHODS = ("auto", "drift", "cyclic", "level")
DEFAULT_METHOD = "auto"
DRIFT_FAST = 10  # samples: the short average each value is smoothed over before comparing
DRIFT_SLOW = 600  # samples: the baseline that follows slow drift
DRIFT_FLOOR = 0.01  # a gap under 1% of the tag's normal mean is never flagged
DRIFT_KS = (10, 12, 15, 20)
DRIFT_SCALE_MIN = 0.5  # a band follows the reading down to half its normal width, never narrower, never wider
CYCLIC_SLOTS = 48  # time-of-day profile: 48 slots of 30 minutes
CYCLIC_MIN_SLOT = 3  # a slot with fewer good fit values than this uses the tag's fit mean
CYCLIC_MIN_DAYS = 2  # the fit rows must span at least this many days before a daily profile is tried
CYCLIC_MIN_R2 = 0.1  # auto picks cyclic when the profile explains at least this share of held-out variance (median tag)
CYCLIC_EVAL_ROWS = 20000  # the auto check reads at most about this many fit and held-out rows (evenly spaced)
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
        value = float(text)
    except ValueError:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    if not math.isfinite(value):
        raise ValueError("time/index must be finite")
    return value


def parse_value(text):
    """A tag cell: a finite float, or None for a bad sample (blank, non-numeric, nan, inf)."""
    try:
        v = float(text)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _historian_records(stream):
    """Nonempty CSV records and their physical spans; quoted newlines count as lines."""
    reader = csv.reader(stream)
    start = 1
    for row in reader:
        end = reader.line_num
        location = f"line {start}" if start == end else f"lines {start}-{end}"
        start = end + 1
        if any(c.strip() for c in row):
            yield location, row


def read_historian_csv(path, with_text=False):
    """Returns (time_name, tags, times, rows), plus the first-column texts if with_text. rows[i][j] is a float or None
    (bad). Times must strictly increase as parsed; no sorting, deduplication or resampling.
    Raises CsvFormatError with physical source locations."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as f:
        records = _historian_records(f)
        try:
            _, raw_header = next(records)
        except StopIteration:
            raise CsvFormatError(f"{path.name}: empty file; expected a header row then data rows") from None
        header = [h.strip() for h in raw_header]
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
        times, rows, texts, kind = [], [], [], None
        previous_location = previous_text = None
        for location, r in records:
            if len(r) != len(header):
                raise CsvFormatError(f"{path.name}: {location} has {len(r)} cells, the header has {len(header)}")
            try:
                t = parse_time(r[0])
            except ValueError:
                raise CsvFormatError(f"{path.name}: {location}: first column '{r[0]}' is neither a number nor an ISO 8601 "
                                     "timestamp (numeric times must be finite)") from None
            k = (type(t), getattr(t, "tzinfo", None) is not None)
            if kind is None:
                kind = k
            elif k != kind:
                raise CsvFormatError(f"{path.name}: {location}: first column mixes timestamps and numbers, or timestamps "
                                     "with and without a time zone")
            text = r[0].strip()
            if times and t <= times[-1]:
                raise CsvFormatError(f"{path.name}: {location}: time/index must be strictly increasing "
                                     f"(oldest first, no duplicate instants); {text!r} is not after "
                                     f"{previous_text!r} at {previous_location}")
            times.append(t)
            rows.append([parse_value(c) for c in r[1:]])
            if with_text:
                texts.append(text)
            previous_location, previous_text = location, text
        if not rows:
            raise CsvFormatError(f"{path.name}: header only, no data rows")
    if with_text:
        return header[0], tags, times, rows, texts
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


def drift_flags(tags, gaps, bands, follow_reading=True):
    """Flag matrix [row][tag] from precomputed (gaps, baselines) columns. The band (gap mean and half-width) is
    scaled by level_scale of the baseline the gap was taken against (unless follow_reading is False: the cyclic
    method's gaps are taken on residuals, whose baseline is not a reading)."""
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
            r = level_scale(lv, b["mean"]) if follow_reading else 1.0
            col.append(abs(g - b["gap_mean"] * r) > b["half_width"] * r)
        cols.append(col)
    return [[c[i] for c in cols] for i in range(n)]


# ------------------------------------------------------------------ cyclic method

def day_slot(t):
    """The time-of-day slot (0 .. CYCLIC_SLOTS-1) of a timestamp."""
    s = t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6
    return min(CYCLIC_SLOTS - 1, int(s * CYCLIC_SLOTS / 86400))


def row_slots(times, daily):
    """Per row, its profile slot: the time-of-day slot when `daily`, else 0 (a flat profile)."""
    return [day_slot(t) for t in times] if daily else [0] * len(times)


def slot_profile(tags, rows, slots):
    """Per tag: {"mean": mean of its good values, "slots": {slot: mean}} over the rows given; a slot is kept only
    with at least CYCLIC_MIN_SLOT good values. None for a tag with no good value."""
    out = {}
    for j, t in enumerate(tags):
        by, allv = {}, []
        for r, s in zip(rows, slots):
            if r[j] is not None:
                by.setdefault(s, []).append(r[j])
                allv.append(r[j])
        out[t] = None if not allv else {
            "mean": statistics.fmean(allv),
            "slots": {s: statistics.fmean(v) for s, v in sorted(by.items()) if len(v) >= CYCLIC_MIN_SLOT}}
    return out


def profile_value(prof, slot):
    return prof["slots"].get(slot, prof["mean"])


def residual_rows(tags, rows, slots, prof):
    """Each value minus its tag's profile at the row's slot (None for bad cells and tags with no profile)."""
    return [[None if r[j] is None or prof[t] is None else r[j] - profile_value(prof[t], s)
             for j, t in enumerate(tags)] for r, s in zip(rows, slots)]


def median3(col):
    """Median of each value and the two good values before it (None stays None; the first two pass through), so a
    single-sample spike never reaches the averages; a change lasting 2 samples or more does."""
    out, last = [], []
    for x in col:
        if x is None:
            out.append(None)
            continue
        last = (last + [x])[-3:]
        out.append(sorted(last)[1] if len(last) == 3 else x)
    return out


def cyclic_gap_columns(tags, rrows):
    """Per tag: (gaps, baselines) of the residual series after median3, as drift_gaps."""
    out = []
    for j in range(len(tags)):
        lv = []
        out.append((drift_gaps(median3([r[j] for r in rrows]), levels=lv), lv))
    return out


def fit_cyclic(tags, rows, gaps):
    """Per tag, over the fit rows: the reading's mean and sd, and the residual gap's mean and sd (the floor is a
    share of the reading's mean, as the drift method's)."""
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


def _evenly(seq, n):
    step = max(1, len(seq) // n)
    return seq[::step]


def daily_profile_r2(tags, fit_times, fit_rows, held_times, held_rows):
    """How much of the held-out rows' variation a time-of-day profile fitted on the fit rows explains: per tag,
    1 - SS(held - its mean - (profile - the profile's mean over those rows)) / SS(held - its mean), so a level that
    moved between fit and held-out is not counted against the profile; the median over tags. At most about
    CYCLIC_EVAL_ROWS rows of each part are read (evenly spaced)."""
    ft, fr = _evenly(fit_times, CYCLIC_EVAL_ROWS), _evenly(fit_rows, CYCLIC_EVAL_ROWS)
    ht, hr = _evenly(held_times, CYCLIC_EVAL_ROWS), _evenly(held_rows, CYCLIC_EVAL_ROWS)
    prof = slot_profile(tags, fr, row_slots(ft, True))
    hs = row_slots(ht, True)
    scores = []
    for j, t in enumerate(tags):
        if prof[t] is None:
            continue
        pv = [(r[j], profile_value(prof[t], s)) for r, s in zip(hr, hs) if r[j] is not None]
        if len(pv) < MIN_ROWS:
            continue
        m = statistics.fmean(v for v, _ in pv)
        pm = statistics.fmean(p for _, p in pv)
        sst = sum((v - m) ** 2 for v, _ in pv)
        if sst <= 0:
            continue
        scores.append(1 - sum((v - m - (p - pm)) ** 2 for v, p in pv) / sst)
    return statistics.median(scores) if scores else None


def choose_method(requested, tags, times, n_fit, rows):
    """The method to run and why. auto: cyclic when the first column is a timestamp, the fit rows span at least
    CYCLIC_MIN_DAYS days and a time-of-day profile fitted on them explains at least CYCLIC_MIN_R2 of the held-out
    rows' variation (median tag); otherwise drift."""
    out = {"requested": requested}
    if requested != "auto":
        return dict(out, chosen=requested, why="requested")
    if not isinstance(times[0], datetime):
        return dict(out, chosen="drift", why="the first column is not a timestamp, so there is no time of day to "
                                             "profile; drift")
    span = elapsed(times, 0, n_fit - 1) / 86400 if n_fit > 1 else 0.0
    if span < CYCLIC_MIN_DAYS or n_fit >= len(rows):
        return dict(out, chosen="drift", why=f"the fit rows span {span:.2f} days, fewer than the {CYCLIC_MIN_DAYS} "
                                             f"days a daily profile needs (or nothing is held out to test it); drift")
    r2 = daily_profile_r2(tags, times[:n_fit], rows[:n_fit], times[n_fit:], rows[n_fit:])
    if r2 is None or r2 < CYCLIC_MIN_R2:
        return dict(out, chosen="drift", daily_profile_r2=None if r2 is None else round(r2, 4),
                    why=f"a time-of-day profile fitted on the fit rows explains {'-' if r2 is None else f'{r2:.2f}'} "
                        f"of the held-out rows' variation (median tag), under {CYCLIC_MIN_R2}; drift")
    return dict(out, chosen="cyclic", daily_profile_r2=round(r2, 4),
                why=f"a time-of-day profile fitted on the fit rows explains {r2:.2f} of the held-out rows' variation "
                    f"(median tag), at least {CYCLIC_MIN_R2}; cyclic")


def choose_k_drift(tags, stats, held_gaps, follow_reading=True):
    """Smallest K in DRIFT_KS whose share of held-out rows with any tag flagged is under TARGET."""
    table = {}
    for k in DRIFT_KS:
        fl = drift_flags(tags, held_gaps, drift_bands(stats, k), follow_reading)
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
    "cyclic": f"each value minus its tag's time-of-day profile (the fit rows' mean in each of {CYCLIC_SLOTS} slots of "
              f"{1440 // CYCLIC_SLOTS} min; a flat profile if the first column is not a timestamp), then a median of "
              f"3 samples so a single-sample spike is ignored, then the drift method's gap on that residual "
              f"({DRIFT_FAST}-sample average minus the {DRIFT_SLOW}-sample baseline one sample earlier); band on the "
              f"gap = its fit mean +/- max(K x its fit sd, {DRIFT_FLOOR:.0%} of the tag's fit mean), not scaled; "
              f"the daily swing is removed, so a step that the swing would hide is flagged",
}


def fit_method(method, tags, times, rows, n_fit, k=None):
    """Fit `method` (level, drift or cyclic) on rows[:n_fit], choosing K on the rest unless k is given. Returns
    {k, table, met, rule, bands, flags_for(tags, times, rows, bands) -> flag matrix or None, profile}."""
    fit_rows, held = rows[:n_fit], rows[n_fit:]
    table = met = profile = None
    if method == "level":
        if k is None:
            k, table, met = choose_k(tags, fit_rows, held)
        bands = fit_bands(tags, fit_rows, k)
        rule = f"smallest K in {list(KS)} with worst-tag false-flag rate < {TARGET:.1%} on held-out rows"

        def flags_for(tg, ts, rs, bd):
            return None  # score() applies the fixed bands
    elif method == "drift":
        stats = fit_drift(tags, fit_rows)
        if k is None:
            k, table, met = choose_k_drift(tags, stats, gap_columns(tags, held))
        bands = drift_bands(stats, k)
        rule = f"smallest K in {list(DRIFT_KS)} with the share of held-out rows with any tag flagged < {TARGET:.1%}"

        def flags_for(tg, ts, rs, bd):
            return drift_flags(tg, gap_columns(tg, rs), bd)
    else:
        daily = isinstance(times[0], datetime)
        profile = slot_profile(tags, fit_rows, row_slots(times[:n_fit], daily))

        def gaps(tg, ts, rs):
            return cyclic_gap_columns(tg, residual_rows(tg, rs, row_slots(ts, daily), {t: profile[t] for t in tg}))
        stats = fit_cyclic(tags, fit_rows, gaps(tags, times[:n_fit], fit_rows))
        if k is None:
            k, table, met = choose_k_drift(tags, stats, gaps(tags, times[n_fit:], held), follow_reading=False)
        bands = drift_bands(stats, k)
        rule = f"smallest K in {list(DRIFT_KS)} with the share of held-out rows with any tag flagged < {TARGET:.1%}"

        def flags_for(tg, ts, rs, bd):
            return drift_flags(tg, gaps(tg, ts, rs), bd, follow_reading=False)
    return {"k": k, "table": table, "met": met, "rule": rule, "bands": bands, "flags_for": flags_for,
            "profile": profile}


def _common(tags, score_csv):
    """The score CSV read and cut to the tags it shares with the normal CSV: (common, missing, extra, times, rows)."""
    _, stags, stimes, srows = read_historian_csv(score_csv)
    common = [t for t in tags if t in stags]
    if not common:
        raise SystemExit("the score CSV shares no tag names with the normal CSV")
    pick = [stags.index(t) for t in common]
    return (common, [t for t in tags if t not in stags], [t for t in stags if t not in tags], stimes,
            [[r[j] for j in pick] for r in srows])


def score_flags(normal, score_csv, k, method, fit_fraction=0.5):
    """Per row of score_csv, whether any tag is flagged: the same fit and flags run() uses for `method` (level, drift
    or cyclic, as run() reports in method_name) at K = k, on the tags both CSVs share. For a caller that needs the
    per-row flags (e.g. to score several labelled events in one export)."""
    _, tags, times, rows = read_historian_csv(normal)
    n_fit = int(len(rows) * fit_fraction)
    f = fit_method(method, tags, times, rows, n_fit, k)
    common, _, _, stimes, srows = _common(tags, score_csv)
    cb = {t: f["bands"][t] for t in common}
    fl = f["flags_for"](common, stimes, srows, cb)
    if fl is None:
        fl = flag_matrix(common, srows, cb)
    return [any(x) for x in fl]


def run(normal, score_csv=None, fault_start=None, fit_fraction=0.5, k=None, method=DEFAULT_METHOD):
    if method not in METHODS:
        raise SystemExit(f"error: --method must be one of {', '.join(METHODS)}, got {method!r}")
    tname, tags, times, rows = read_historian_csv(normal)
    n_fit = int(len(rows) * fit_fraction)
    if n_fit < 2:
        raise SystemExit(f"fit portion has {n_fit} rows; need at least 2")
    held = rows[n_fit:]
    if k is None and not held:
        raise SystemExit("--fit-fraction 1 leaves nothing to choose K on; pass --k")
    choice = choose_method(method, tags, times, n_fit, rows)
    method = choice["chosen"]
    f = fit_method(method, tags, times, rows, n_fit, k)
    k, table, met, rule, bands = f["k"], f["table"], f["met"], f["rule"], f["bands"]
    flags_for = f["flags_for"]
    if f["profile"] is not None:  # cyclic: each band carries its tag's time-of-day profile
        bands = {t: None if b is None else dict(b, profile=None if f["profile"][t] is None else {
            "mean": round(f["profile"][t]["mean"], 6),
            "slots": {str(s): round(v, 6) for s, v in f["profile"][t]["slots"].items()}})
            for t, b in bands.items()}
    out = {"method_name": method, "method": METHOD_TEXT[method], "method_choice": choice,
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
    if method == "cyclic":
        daily = isinstance(times[0], datetime)
        out["cyclic_profile"] = (f"time of day ({CYCLIC_SLOTS} slots of {1440 // CYCLIC_SLOTS} min)" if daily
                                 else "flat")
        if not daily:
            warnings.append("no time-of-day profile: the first column is not a timestamp, so the profile is each "
                            "tag's fit mean (one slot); the method then differs from drift only by the 3-sample "
                            "median and by the band not following the reading")
    if warnings:  # the key only appears when there is something to warn about
        out["warnings"] = warnings
    if held:
        out["held_out_normal"] = score(tags, times[n_fit:], held, bands,
                                       flags=flags_for(tags, times[n_fit:], held, bands))
        out["held_out_normal"].pop("per_tag")
    if score_csv:
        common, missing, extra, stimes, srows = _common(tags, score_csv)
        fs = None if fault_start is None else resolve_fault_start(str(fault_start), stimes)
        cb = {t: bands[t] for t in common}
        out["scored"] = dict(score(common, stimes, srows, cb, fs, flags=flags_for(common, stimes, srows, cb)),
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
    c = r.get("method_choice")
    if c and c["requested"] == "auto":
        md.append(f"- Method chosen automatically: {c['why']}.")
    if r.get("cyclic_profile"):
        md.append(f"- Profile: {r['cyclic_profile']}.")
    if r["no_band"]:
        md.append(f"- No good values in the fit, so no band: {', '.join(r['no_band'])}.")
    for w in r.get("warnings", []):
        md.append(f"- **Warning{'' if w.startswith('no time-of-day profile') else ' (small sample)'}:** {w}")
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
    if r["method_name"] == "cyclic":
        md += ["", "Band half-width on the gap of each tag's residual from its time-of-day profile (set by the floor "
                   f"where the residual varies less than {DRIFT_FLOOR:.0%} of the reading allows; not scaled with the "
                   "reading). Profile range = the lowest and highest slot means:", "",
               "| Tag | Fit mean | Profile range | Gap sd | Half-width | Set by |", "|---|---|---|---|---|---|"]
        for t, b in r["bands"].items():
            if b is None:
                continue
            sl = list((b.get("profile") or {}).get("slots", {}).values())
            rng = f"{min(sl):.6g} to {max(sl):.6g}" if sl else "-"
            md.append(f"| {t} | {b['mean']:.6g} | {rng} | {b['resid_sd']:.3g} | {b['half_width']:.3g} | "
                      f"{b['limited_by']} |")
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
                    help="auto (default): cyclic when the export has timestamps over at least "
                         f"{CYCLIC_MIN_DAYS} fit days and a time-of-day profile explains at least {CYCLIC_MIN_R2} of "
                         "the held-out variation, else drift; drift: each tag against its own slow baseline, for real "
                         "data that drifts; cyclic: the drift method on each tag's residual from its time-of-day "
                         "profile, for daily cycles; level: fixed mean +/- K sd bands, the Tennessee Eastman scripts' "
                         "method")
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
    try:
        serialized = json.dumps(r, indent=1, allow_nan=False)
    except ValueError:
        raise SystemExit("error: computed result contains a nonfinite value; check sample times and magnitudes") from None
    out = Path(a.out)
    md = markdown(r, units)
    try:
        targets = [out / "csv_normal_bands.json", out / "csv_normal_bands.md"]
        protect_outputs(targets, [a.normal, a.score])
        out.mkdir(parents=True, exist_ok=True)
        # LF on every OS, so the committed example regenerates byte for byte on Windows too
        targets[0].write_text(serialized, encoding="utf-8", newline="\n")
        targets[1].write_text(md, encoding="utf-8", newline="\n")
    except (ValueError, OSError) as exc:
        raise SystemExit(f"error: {exc}") from None
    print(md)
    return r


if __name__ == "__main__":
    main()
