"""How well do the operator screens' normal bands detect faults? All 21 published Tennessee Eastman faults, with a
false-alarm rate measured on normal runs the bands never saw.

The screens flag a value that leaves its normal band (scripts/normal_bands.py: mean +/- K sd). The fault demo shows
one fault, fault 6, which is one of the easiest. This script asks the general question with the whole Braatz set
(python scripts/fetch_te_data.py --all) and a rule written down before any fault file was scored:

  Plant flag at a sample:  any of the 52 recorded channels outside its band (what the header's "Outside band"
                           count shows when it is above 0).
  Detection:               the first post-onset sample that starts a run of RUN consecutive flagged samples
                           (RUN = 3, 9 minutes). A single flagged sample is reported too, but not counted.
  Delay:                   (detection sample - 160) x 3 minutes. The fault is switched on at sample 160 of each
                           960-sample test file.
  Detection rate:          share of the 800 post-onset samples flagged (the per-sample measure most TE papers
                           report, so the numbers can be compared).

Two band sets, neither tuned on fault data:
  shipped:  exactly the bands on the screens (fit on d00_te samples 0-479; K chosen on d00_te 480-959).
            False alarms are measured on data that played no part: the separate normal training run d00.dat
            (500 samples) and the 160 fault-free samples at the start of each of the 21 fault test runs (each is a
            separate simulation run; 3,360 samples).
  refit:    means and sds refitted on d00.dat with the same K, so the whole of d00_te (960 samples) is a held-out
            normal run, plus the same 21 fault-free starts.

Baseline: PCA with Hotelling's T^2, reimplemented here because it is short (numpy only): standardise on d00.dat,
keep the components that beat parallel analysis, 99% threshold from the F distribution, the same RUN rule. It is
a baseline, not a tuned competitor; published PCA numbers vary with these choices.

Model use: none. Statistics on published data. Claude (the coding agent) chose the rule and wrote the code.

  python scripts/fault_detection_eval.py     # writes out/fault_detection/fault_detection.json and .md
"""
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ignition"))
DATA = ROOT / "data" / "external" / "te-braatz"
OUT = ROOT / "out" / "fault_detection"
ONSET, MINUTES, RUN, ALPHA = 160, 3, 3, 0.01
FAULTS = range(1, 22)
# IDV descriptions, Downs & Vogel (1993) Table 8; 16-20 are "unknown" there.
IDV = {1: "A/C feed ratio, B composition constant (step)", 2: "B composition, A/C ratio constant (step)",
       3: "D feed temperature (step)", 4: "Reactor cooling water inlet temperature (step)",
       5: "Condenser cooling water inlet temperature (step)", 6: "A feed loss (step)",
       7: "C header pressure loss, reduced availability (step)", 8: "A, B, C feed composition (random variation)",
       9: "D feed temperature (random variation)", 10: "C feed temperature (random variation)",
       11: "Reactor cooling water inlet temperature (random variation)",
       12: "Condenser cooling water inlet temperature (random variation)", 13: "Reaction kinetics (slow drift)",
       14: "Reactor cooling water valve (sticking)", 15: "Condenser cooling water valve (sticking)",
       16: "Unknown", 17: "Unknown", 18: "Unknown", 19: "Unknown", 20: "Unknown",
       21: "Stream 4 valve fixed at steady-state position"}
# Faults the TE literature widely reports as hard or impossible to see with data-driven monitoring of these
# variables. Named before scoring, so a miss here is expected rather than explained away afterwards.
EXPECTED_HARD = (3, 9, 15)


def load(name):
    a = np.loadtxt(DATA / name)
    return a.T if a.shape[0] == 52 else a  # d00.dat is stored transposed (52 x 500)


# ------------------------------------------------------------------ detection logic (unit-tested on synthetic data)

def first_run(flags, start=0, run=RUN):
    """Index of the first sample at or after start that begins `run` consecutive True values, else None."""
    n = 0
    for i in range(start, len(flags)):
        n = n + 1 if flags[i] else 0
        if n == run:
            return i - run + 1
    return None


def alarm_events(flags, run=RUN):
    """How many separate times the rule would fire: runs of at least `run` consecutive flags."""
    events, n = 0, 0
    for f in flags:
        n = n + 1 if f else 0
        events += n == run
    return events


def band_flags(x, lo, hi):
    """Per-sample, per-channel: outside the band. Matches the gateway expression PV < NormalLo || PV > NormalHi."""
    return (x < lo) | (x > hi)


def _betacf(a, b, x):
    # Continued fraction for the regularised incomplete beta function (Numerical Recipes, betacf).
    tiny, qab, qap, qam = 1e-300, a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 1e-14:
            break
    return h


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def f_quantile(p, d1, d2):
    """Inverse CDF of the F distribution, by bisection on the regularised incomplete beta."""
    cdf = lambda f: betainc(d1 / 2, d2 / 2, d1 * f / (d1 * f + d2))
    lo, hi = 0.0, 1.0
    while cdf(hi) < p:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) < p else (lo, mid)
    return (lo + hi) / 2


class PCAT2:
    """Hotelling's T^2 on standardised data; components kept by parallel analysis (fixed seed)."""

    def __init__(self, train, alpha=ALPHA, seed=0):
        self.mu, self.sd = train.mean(0), train.std(0, ddof=1)
        z = (train - self.mu) / self.sd
        n, m = z.shape
        vals, vecs = np.linalg.eigh(np.cov(z, rowvar=False))
        order = np.argsort(vals)[::-1]
        vals, vecs = vals[order], vecs[:, order]
        rng = np.random.default_rng(seed)
        rand = np.mean([np.sort(np.linalg.eigvalsh(np.cov(rng.standard_normal((n, m)), rowvar=False)))[::-1]
                        for _ in range(50)], axis=0)
        self.a = max(1, int(np.argmax(vals <= rand)) if (vals <= rand).any() else m)
        self.P, self.lam = vecs[:, :self.a], vals[:self.a]
        a = self.a
        self.limit = a * (n - 1) * (n + 1) / (n * (n - a)) * f_quantile(1 - alpha, a, n - a)

    def t2(self, x):
        t = ((x - self.mu) / self.sd) @ self.P
        return (t * t / self.lam).sum(1)

    def flags(self, x):
        return self.t2(x) > self.limit


# ------------------------------------------------------------------ evaluation

def score_fault(any_flag, per_channel=None, tags=None):
    det = first_run(any_flag, ONSET)
    single = next((i for i in range(ONSET, len(any_flag)) if any_flag[i]), None)
    row = {"detected": det is not None,
           "delay_min": None if det is None else (det - ONSET) * MINUTES,
           "first_single_flag_min": None if single is None else (single - ONSET) * MINUTES,
           "detection_rate": round(float(np.mean(any_flag[ONSET:])), 4),
           "pre_onset_flag_rate": round(float(np.mean(any_flag[:ONSET])), 4)}
    if per_channel is not None:
        first = {}
        for j, tag in enumerate(tags):
            hit = np.flatnonzero(per_channel[ONSET:, j])
            if hit.size:
                first[tag] = int(hit[0]) * MINUTES
        row["first_tags"] = [{"tag": t, "min": m} for t, m in sorted(first.items(), key=lambda kv: (kv[1], kv[0]))[:3]]
        row["tags_flagged_ever"] = len(first)
    return row


def normal_stats(flag_sets):
    """False alarms on normal data: per-sample rate and how often the RUN rule would fire."""
    samples = sum(len(f) for f in flag_sets.values())
    flagged = sum(int(np.sum(f)) for f in flag_sets.values())
    events = sum(alarm_events(f) for f in flag_sets.values())
    hours = samples * MINUTES / 60
    return {"sets": {k: {"samples": len(f), "flagged_samples": int(np.sum(f)), "alarm_events": alarm_events(f)}
                     for k, f in flag_sets.items()},
            "samples": samples, "flag_rate_per_sample": round(flagged / samples, 4),
            "alarm_events": events, "plant_hours": round(hours, 1),
            "alarm_events_per_day": round(events / hours * 24, 3),
            # Zero events is not zero risk: the 95% upper bound for a Poisson count of 0 is 3 events (rule of three).
            "alarm_events_per_day_95_upper": round(max(events, 3) / hours * 24 if events == 0 else
                                                   (events + 1.96 * math.sqrt(events) + 1) / hours * 24, 3),
            # Chance alarms expected in one fault run's 800-sample (40 h) post-onset window, at this normal rate.
            "chance_events_per_40h": round(events / hours * 40, 2)}


def summarise(rows):
    det = [r for r in rows.values() if r["detected"]]
    return {"detected": len(det), "of": len(rows),
            "median_delay_min": statistics.median(r["delay_min"] for r in det) if det else None,
            "mean_detection_rate": round(statistics.fmean(r["detection_rate"] for r in rows.values()), 4),
            "missed": [int(k) for k, r in rows.items() if not r["detected"]]}


def evaluate():
    import normal_bands
    from build_gateway import te_columns
    model = json.loads((ROOT / "data" / "te_process_model.json").read_text(encoding="utf-8"))
    cols = te_columns(model)
    tags = sorted(cols, key=cols.get)
    idx = [cols[t] for t in tags]
    shipped = normal_bands.main(quiet=True)
    k = shipped["k"]
    lo_s = np.array([shipped["bands"][t]["lo"] for t in tags])
    hi_s = np.array([shipped["bands"][t]["hi"] for t in tags])
    d00_train, d00_test = load("d00.dat")[:, idx], load("d00_te.dat")[:, idx]
    m, s = d00_train.mean(0), d00_train.std(0)  # population sd, as normal_bands uses
    lo_r, hi_r = m - k * s, m + k * s
    faults = {f: load(f"d{f:02d}_te.dat")[:, idx] for f in FAULTS}
    pca = PCAT2(load("d00.dat"))  # all 52 columns; idx is the identity permutation here, asserted below
    assert idx == list(range(52)), "channel order changed; PCA and bands would see different columns"

    methods = {
        "shipped_bands": lambda x: band_flags(x, lo_s, hi_s),
        "refit_bands": lambda x: band_flags(x, lo_r, hi_r),
    }
    result = {"rule": {"onset_sample": ONSET, "minutes_per_sample": MINUTES, "run": RUN,
                       "plant_flag": "any of 52 channels outside its band", "k": k,
                       "expected_hard": list(EXPECTED_HARD)},
              "methods": {}}
    for name, fl in methods.items():
        per = {f: fl(x) for f, x in faults.items()}
        rows = {str(f): dict(score_fault(p.any(1), p, tags), idv=IDV[f]) for f, p in per.items()}
        normal = {"d00.dat (training run)": fl(d00_train).any(1)} if name == "shipped_bands" else \
                 {"d00_te.dat (test run, all 960)": fl(d00_test).any(1)}
        normal["fault runs, samples 0-159 (21 runs)"] = np.concatenate([p.any(1)[:ONSET] for p in per.values()])
        result["methods"][name] = {"faults": rows, "summary": summarise(rows), "false_alarms": normal_stats(normal)}
    per = {f: pca.flags(x) for f, x in faults.items()}
    rows = {str(f): dict(score_fault(p), idv=IDV[f]) for f, p in per.items()}
    normal = {"d00_te.dat (test run, all 960)": pca.flags(d00_test),
              "fault runs, samples 0-159 (21 runs)": np.concatenate([p[:ONSET] for p in per.values()])}
    result["methods"]["pca_t2"] = {"faults": rows, "summary": summarise(rows), "false_alarms": normal_stats(normal),
                                   "components": pca.a, "t2_limit": round(float(pca.limit), 3),
                                   "fit": "d00.dat, standardised; parallel analysis; F threshold alpha 0.01"}
    return result


def markdown(r):
    sb, rb, pc = (r["methods"][k] for k in ("shipped_bands", "refit_bands", "pca_t2"))
    fmt = lambda v: "-" if v is None else f"{v:g}"
    md = ["# Fault detection with the normal bands: all 21 Tennessee Eastman faults", "",
          "Generated by `scripts/fault_detection_eval.py` from the Braatz data set "
          "(`python scripts/fetch_te_data.py --all`). One sample = 3 minutes; each fault switches on at sample 160.",
          "", f"**Rule (fixed before scoring):** the plant is flagged when any of the 52 channels is outside its band "
              f"(K = {r['rule']['k']}). A fault counts as detected at the first post-onset sample that starts "
              f"{RUN} consecutive flagged samples (9 minutes). Detection rate = share of the 800 post-onset samples "
              f"flagged.", "",
          "| Method | Detected | Median delay (detected faults) | Mean detection rate | False-alarm rate per sample "
          "| Alarm events on normal data |", "|---|---|---|---|---|---|"]
    for name, m in (("Shipped bands", sb), ("Bands refit on d00.dat", rb), (f"PCA T² ({pc['components']} PCs)", pc)):
        s, fa = m["summary"], m["false_alarms"]
        md.append(f"| {name} | {s['detected']}/{s['of']} | {fmt(s['median_delay_min'])} min | "
                  f"{s['mean_detection_rate']:.1%} | {fa['flag_rate_per_sample']:.2%} ({fa['samples']:,} samples) | "
                  f"{fa['alarm_events']} in {fa['plant_hours']:g} h |")
    md += ["", "False-alarm data, all normal operation the method never fitted on:", ""]
    upper = sb["false_alarms"]["alarm_events_per_day_95_upper"]
    md_chance = pc["false_alarms"]["chance_events_per_40h"]
    for name, m in (("Shipped bands", sb), ("Refit bands", rb), ("PCA T²", pc)):
        md.append(f"- {name}: " + "; ".join(f"{k}: {v['flagged_samples']}/{v['samples']} flagged samples, "
                                             f"{v['alarm_events']} alarm events" for k, v in m["false_alarms"]["sets"].items()))
    md += ["", f"Zero false alarms is a measurement on {sb['false_alarms']['plant_hours']:g} plant hours, not a guarantee: "
               f"the 95% upper bound is about {upper:g} alarm events per day. PCA T² would raise about {md_chance:g} "
               f"chance alarm events in a 40-hour post-onset window, so a late PCA detection with a detection rate "
               f"near its {pc['false_alarms']['flag_rate_per_sample']:.1%} normal flag rate (faults 3, 4 and 15 "
               f"below) is probably chance rather than a real detection.",
           "", "## Per fault (shipped bands)", "",
           "| Fault | Disturbance (Downs & Vogel 1993) | Detected | Delay | First single flag | Detection rate | "
           "First tags to leave their band (minutes after onset) | Refit bands | PCA T² |",
           "|---|---|---|---|---|---|---|---|---|"]
    for f in FAULTS:
        a, b, c = sb["faults"][str(f)], rb["faults"][str(f)], pc["faults"][str(f)]
        first = ", ".join(f"{x['tag']} ({x['min']})" for x in a["first_tags"]) or "none"
        hard = " (expected hard)" if f in EXPECTED_HARD else ""
        cell = lambda x: (f"yes, {x['delay_min']} min" if x["detected"] else "no") + f", {x['detection_rate']:.0%}"
        md.append(f"| {f}{hard} | {a['idv']} | {'yes' if a['detected'] else '**no**'} | "
                  f"{fmt(a['delay_min'])}{' min' if a['detected'] else ''} | {fmt(a['first_single_flag_min'])} | "
                  f"{a['detection_rate']:.1%} | {first} | {cell(b)} | {cell(c)} |")
    md += ["", f"Missed by the shipped bands: {', '.join(map(str, sb['summary']['missed'])) or 'none'}. "
               f"Missed by PCA T²: {', '.join(map(str, pc['summary']['missed'])) or 'none'}.", ""]
    return "\n".join(md) + "\n"


def main():
    missing = [f"d{f:02d}_te.dat" for f in FAULTS if not (DATA / f"d{f:02d}_te.dat").exists()]
    if missing or not (DATA / "d00.dat").exists():
        raise SystemExit("missing TE evaluation files; run: python scripts/fetch_te_data.py --all")
    r = evaluate()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fault_detection.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    md = markdown(r)
    (OUT / "fault_detection.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
