"""Tests for scripts/fault_detection_eval.py: the detection rule and the PCA baseline on synthetic data, then (when
the full Braatz set is cached) that the committed results regenerate exactly and still say what the docs say."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fault_detection_eval as fde  # noqa: E402

failures = []


def check(name, ok):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        failures.append(name)


# The rule: a run of RUN consecutive flags, starting at or after the onset.
f = [False, True, True, False, True, True, True, False]
check("first_run finds the first full run, not the first flag", fde.first_run(f, 0, 3) == 4)
check("first_run ignores runs that start before the search start", fde.first_run([True] * 5, 3, 3) is None)
check("first_run returns None without a full run", fde.first_run([True, True, False] * 5, 0, 3) is None)
check("alarm_events counts separate runs once each", fde.alarm_events([1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1], 3) == 2)

# Band flags match the gateway's strict comparison: a value equal to a limit is inside.
x = np.array([[1.0, 5.0], [0.0, 6.0]])
fl = fde.band_flags(x, np.array([0.0, 4.0]), np.array([1.0, 5.5]))
check("band_flags: equal-to-limit is inside, beyond is outside", fl.tolist() == [[False, False], [False, True]])

# F quantiles against standard table values.
for p, d1, d2, want in ((0.99, 5, 10, 5.636), (0.95, 2, 10, 4.103), (0.99, 1, 20, 8.096)):
    got = fde.f_quantile(p, d1, d2)
    check(f"F quantile {p} ({d1},{d2}) = {want}", abs(got - want) < 0.002)

# PCA T^2 on synthetic data: few strong components, about alpha false alarms in normal data, a large shift caught.
rng = np.random.default_rng(1)
latent = rng.standard_normal((2000, 3))
mix = rng.standard_normal((3, 10)) * 3
train = latent[:1000] @ mix + rng.standard_normal((1000, 10))
normal = latent[1000:] @ mix + rng.standard_normal((1000, 10))
pca = fde.PCAT2(train)
check(f"parallel analysis keeps the 3 real components (got {pca.a})", pca.a == 3)
rate = pca.flags(normal).mean()
check(f"PCA T^2 false-alarm rate near alpha on fresh normal data ({rate:.3f})", 0.002 < rate < 0.03)
shifted = normal + 8 * mix[0]  # an 8-sd move of the first latent variable
check("PCA T^2 flags a large shift along a retained direction", pca.flags(shifted).mean() > 0.9)

# score_fault: delay in minutes from sample 160, pre-onset flags reported separately.
flags = np.zeros(960, bool)
flags[100] = True
flags[170:180] = True
row = fde.score_fault(flags)
check("score_fault delay = (170 - 160) x 3 min", row["detected"] and row["delay_min"] == 30)
check("score_fault keeps pre-onset flags out of detection", row["pre_onset_flag_rate"] > 0 and row["first_single_flag_min"] == 30)

# Regenerate against the committed results, when the full data set is cached (CI fetches it with --all).
needed = ["d00.dat"] + [f"d{i:02d}_te.dat" for i in fde.FAULTS]
if all((fde.DATA / n).exists() for n in needed):
    committed = json.loads((ROOT / "out/fault_detection/fault_detection.json").read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(fde.evaluate()))
    check("committed fault_detection.json regenerates exactly", fresh == committed)
    sb, pc = fresh["methods"]["shipped_bands"], fresh["methods"]["pca_t2"]
    check("expected-hard faults 3, 9, 15 are reported as misses by the bands",
          all(not sb["faults"][str(i)]["detected"] for i in fde.EXPECTED_HARD))
    check("shipped bands: no false alarm events on held-out normal data", sb["false_alarms"]["alarm_events"] == 0)
    check("docs' claim: PCA's detections of 3, 4 and 15 sit near its false-alarm level (<10% detection rate)",
          all(pc["faults"][str(i)]["detected"] and pc["faults"][str(i)]["detection_rate"] < 0.10 for i in (3, 4, 15)))
    md = fde.markdown(fresh)
    check("committed fault_detection.md regenerates exactly",
          md == (ROOT / "out/fault_detection/fault_detection.md").read_text(encoding="utf-8"))
else:
    print("SKIP full TE evaluation set not cached (python scripts/fetch_te_data.py --all); regeneration not checked")

print(f"{'FAILED' if failures else 'OK'}: fault detection eval tests, {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
