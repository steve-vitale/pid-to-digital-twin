"""Normal operating bands for any historian-style CSV: learn them from a normal-running export, then score a second export.

This is the same method as scripts/normal_bands.py (which does it for the Tennessee Eastman files), made general:

  Fit:     the first FIT_FRACTION of the normal CSV (default: the first half). Band per tag = mean +/- K population
           standard deviations of that tag's good (numeric) values.
  K:       either given (--k 5), or chosen as normal_bands.py chooses it: the smallest K in (3, 4, 5, 6) whose worst
           per-tag false-flag rate on the rest of the normal CSV, which the fit never saw, is under 0.5%. If no K meets
           that, K = 6 and the report says the target was not met.
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
compared with the normal export", nothing about why. The bands are only as good as the normal export: if it contains
upsets, they widen the bands; if it covers one operating mode, other modes will flag.

Model use: none. Plain statistics (stdlib only). Claude (the coding agent) wrote the code.

  python scripts/csv_normal_bands.py --normal normal.csv --score fault.csv --fault-start 160 --out out/csv_bands
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
RUN = 3  # consecutive flagged samples for a detection, as in fault_detection_eval.py


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
    t = parse_time(text)
    for i, x in enumerate(times):
        if x >= t:
            return i
    raise SystemExit(f"--fault-start {text}: no row at or after that time")


def score(tags, times, rows, bands, fault_start=None):
    fl = flag_matrix(tags, rows, bands)
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


def run(normal, score_csv=None, fault_start=None, fit_fraction=0.5, k=None):
    tname, tags, times, rows = read_historian_csv(normal)
    n_fit = int(len(rows) * fit_fraction)
    if n_fit < 2:
        raise SystemExit(f"fit portion has {n_fit} rows; need at least 2")
    fit_rows, held = rows[:n_fit], rows[n_fit:]
    if k is None:
        if not held:
            raise SystemExit("--fit-fraction 1 leaves nothing to choose K on; pass --k")
        k, table, met = choose_k(tags, fit_rows, held)
    else:
        table, met = None, None
    bands = fit_bands(tags, fit_rows, k)
    out = {"method": "band = mean +/- K population sd over the fit rows' good values (scripts/normal_bands.py method)",
           "normal_csv": Path(normal).name, "time_column": tname,
           "time_kind": "timestamp" if isinstance(times[0], datetime) else "number", "tags": tags, "k": k,
           "k_selection": None if table is None else {
               "rule": f"smallest K in {list(KS)} with worst-tag false-flag rate < {TARGET:.1%} on held-out rows",
               "target_met": met, "by_k": {str(kk): {a: (round(b, 4) if isinstance(b, float) else b)
                                                     for a, b in v.items()} for kk, v in table.items()}},
           "fit_rows": f"0-{n_fit - 1}", "held_out_rows": f"{n_fit}-{len(rows) - 1}" if held else None,
           "bands": {t: None if b is None else {a: (round(v, 6) if isinstance(v, float) else v) for a, v in b.items()}
                     for t, b in bands.items()},
           "no_band": [t for t, b in bands.items() if b is None]}
    if held:
        out["held_out_normal"] = score(tags, times[n_fit:], held, bands)
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
        out["scored"] = dict(score(common, stimes, srows, {t: bands[t] for t in common}, fs),
                             csv=Path(score_csv).name, tags_missing=missing, tags_not_in_normal=extra)
    return out


def _fmt(v):
    return "-" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v))


def markdown(r, units):
    md = ["# Normal bands from a historian CSV", "",
          "Generated by `scripts/csv_normal_bands.py`. " + r["method"] + ".", "",
          f"- Normal CSV: `{r['normal_csv']}`; fit rows {r['fit_rows']}; held-out rows {_fmt(r['held_out_rows'])}; "
          f"{len(r['tags'])} tags.", f"- K = {r['k']}" +
          ("" if r["k_selection"] is None else
           f" ({r['k_selection']['rule']}; target {'met' if r['k_selection']['target_met'] else 'NOT met'})") + "."]
    if r["no_band"]:
        md.append(f"- No good values in the fit, so no band: {', '.join(r['no_band'])}.")
    if r["k_selection"]:
        md += ["", "| K | False flags, worst tag | Mean tag | Any tag flagged |", "|---|---|---|---|"]
        md += [f"| {k} | {v['worst_tag_rate']:.1%} ({v['worst_tag']}) | {v['mean_tag_rate']:.2%} | "
               f"{v['any_tag_rate']:.1%} |" for k, v in r["k_selection"]["by_k"].items()]
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
    ap.add_argument("--k", type=float, help="band half-width in sd; default: chosen on the held-out normal rows")
    ap.add_argument("--units", default=None, help="label for delays (default: 'seconds' for timestamps, else the "
                                                   "first column's units)")
    ap.add_argument("--out", default="out/csv_normal_bands", help="output directory for the .md and .json")
    a = ap.parse_args(argv)
    if a.fault_start is not None and not a.score:
        ap.error("--fault-start needs --score")
    try:
        r = run(a.normal, a.score, a.fault_start, a.fit_fraction, a.k)
    except CsvFormatError as e:
        raise SystemExit(f"error: {e}") from None
    units = a.units or ("seconds" if r["time_kind"] == "timestamp" else f"'{r['time_column']}' units")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "csv_normal_bands.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    md = markdown(r, units)
    (out / "csv_normal_bands.md").write_text(md, encoding="utf-8")
    print(md)
    return r


if __name__ == "__main__":
    main()
