"""Digitize Figure 11 of the CSB Bayer CropScience report, and check the result against the report's own text.

Figure 11 is the residue treater's DCS trend for the evening of August 28, 2008: temperature, pressure, liquid level
and recirculation flow, from 17:58 to after the 22:33 failure. It is the published operating data the next phase
replays (docs/REAL_UNIT_SELECTION.md). The figure is a raster image inside the report's PDF, so the values have to be
read off its pixels.

How:
  fetch     download the report from csb.gov into data/external/csb/ (gitignored) and check its SHA-256.
  digitize  read the figure's embedded image (PyMuPDF), classify pixels by colour (red temperature, black pressure,
            blue level, brown flow), drop the gridlines and the annotation boxes named in the calibration, keep
            only black components of at least min_component_px (text glyphs and the dotted failure line are smaller),
            and take each column's median row. Pixels map to time and value by data/bayer_rt/fig11_calibration.json,
            which was read off the figure's own tick marks and gridlines. Steep segments keep their row range, so
            a near-vertical rise is reported as min/median/max rather than flattened.
  check     compare with every value the report's text states about the same evening (pages 38-39 and the figure's
            own labels). The text is never used to calibrate, so these are independent checks. A failed check is
            reported, not tuned away.

Outputs: data/bayer_rt/fig11_digitized.csv (one row per pixel column, about 32 s apart, with the pixel-error bound
per series) and out/bayer_rt/fig11_check.md.

The figure is not stored in the repository; only the digitized values, each cited to the figure, are. Not legal
advice: see docs/REAL_UNIT_SELECTION.md for the reuse stance.

Needs numpy, Pillow and PyMuPDF (pip install pymupdf; only this script uses it).
Usage: python scripts/digitize_bayer_fig11.py [fetch] [digitize] [check]     (no argument: all three)
"""
import csv
import hashlib
import io
import json
import statistics
import sys
import urllib.request
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAL = ROOT / "data" / "bayer_rt" / "fig11_calibration.json"
PDF = ROOT / "data" / "external" / "csb" / "Bayer_Report_Final.pdf"
CSV_OUT = ROOT / "data" / "bayer_rt" / "fig11_digitized.csv"
REPORT = ROOT / "out" / "bayer_rt" / "fig11_check.md"
SERIES = ("temperature_C", "pressure_psig", "level_pct", "recirc_flow_klbh")


def cal():
    return json.loads(CAL.read_text(encoding="utf-8"))


def fetch(c):
    if PDF.exists() and hashlib.sha256(PDF.read_bytes()).hexdigest() == c["source"]["sha256"]:
        print(f"{PDF.relative_to(ROOT)}: present, checksum OK")
        return
    req = urllib.request.Request(c["source"]["url"], headers={"User-Agent": "pid-to-digital-twin (research)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    got = hashlib.sha256(data).hexdigest()
    if got != c["source"]["sha256"]:
        raise SystemExit(f"report checksum {got[:16]}... does not match the calibrated copy; not saved")
    PDF.parent.mkdir(parents=True, exist_ok=True)
    PDF.write_bytes(data)
    print(f"{PDF.relative_to(ROOT)}: downloaded, {len(data):,} bytes, checksum OK")


def figure_pixels(c):
    import fitz  # PyMuPDF
    import numpy as np
    from PIL import Image
    doc = fitz.open(str(PDF))
    xref = doc[c["source"]["pdf_page_index"]].get_images(full=True)[0][0]
    pm = fitz.Pixmap(doc, xref)
    if pm.n != 3:
        pm = fitz.Pixmap(fitz.csRGB, pm)
    img = np.asarray(Image.open(io.BytesIO(pm.tobytes("png"))).convert("RGB")).astype(int)
    if list(img.shape[1::-1]) != c["source"]["image_px"]:
        raise SystemExit(f"figure image is {img.shape[1]}x{img.shape[0]}, calibrated for {c['source']['image_px']}")
    return img


def masks(img, c):
    import numpy as np
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    red = (r > 200) & (g < 60) & (b < 120)
    brown = (r > 110) & (r < 245) & (g > 25) & (g < 150) & (b < 120) & (r - b > 60) & (r - g > 35) & ~red
    blue = (b > 70) & (b - r > 50) & (b - g > 50)
    black = (img.max(2) - img.min(2) < 40) & (img.sum(2) < 450)
    for y in c["gridline_rows"]:
        black[y, :] = False
    for x0, y0, x1, y1 in (v for k, v in c["annotation_boxes"].items() if not k.startswith("_")):
        black[y0:y1 + 1, x0:x1 + 1] = False
    black = _keep_large(black, c["min_component_px"])
    # The red trace's anti-aliased edges include brownish pixels; the flow trace itself is one connected line.
    brown = _keep_large(brown, c["min_component_px"])
    # Black text labels have blue anti-aliased fringes; the level trace is the only large blue component.
    blue = _keep_large(blue, c["level_min_component_px"])
    x0, x1 = c["plot_frame_x"]
    out = {"temperature_C": red, "pressure_psig": black, "level_pct": blue, "recirc_flow_klbh": brown}
    top, bottom = c["left_axis"]["y_at_160"], c["left_axis"]["y_at_0"]
    for m in out.values():
        m[:, :x0 + 1] = False
        m[:, x1:] = False
        m[:top, :] = False
        m[bottom + 2:, :] = False
    return out


def _keep_large(mask, min_px):
    import numpy as np
    keep = np.zeros_like(mask)
    seen = np.zeros_like(mask)
    H, W = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        q, pts = deque([(y0, x0)]), []
        seen[y0, x0] = True
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
        if len(pts) >= min_px:
            for y, x in pts:
                keep[y, x] = True
    return keep


def time_of(x, c):
    """Least-squares line through the labelled tick marks: seconds after the first tick."""
    t0 = datetime.fromisoformat(f"{c['date']}T{next(iter(c['time_ticks']))}")
    pts = [((datetime.fromisoformat(f"{c['date']}T{k}") - t0).total_seconds(), v) for k, v in c["time_ticks"].items()]
    n = len(pts)
    mt, mx = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    slope = sum((t - mt) * (px - mx) for t, px in pts) / sum((t - mt) ** 2 for t, _ in pts)   # px per second
    return t0 + timedelta(seconds=mt + (x - mx) / slope), 1 / slope


def value_of(y, axis, c):
    if axis == "right":
        a = c["right_axis"]
        return (a["y_at_0"] - y) / (a["y_at_0"] - a["y_at_60"]) * 60
    a = c["left_axis"]
    return (a["y_at_0"] - y) / (a["y_at_0"] - a["y_at_160"]) * 160


def digitize(c):
    img = figure_pixels(c)
    ms = masks(img, c)
    x0, x1 = c["plot_frame_x"]
    rows = []
    for x in range(x0 + 1, x1):
        t, s_per_px = time_of(x, c)
        row = {"time": t.strftime("%H:%M:%S"), "x_px": x}
        for name in SERIES:
            ys = [int(y) for y in ms[name][:, x].nonzero()[0]]
            axis = c["series"][name]["axis"]
            if ys:
                row[name] = round(value_of(statistics.median(ys), axis, c), 2)
                row[name + "_min"] = round(value_of(max(ys), axis, c), 2)
                row[name + "_max"] = round(value_of(min(ys), axis, c), 2)
            else:
                row[name] = row[name + "_min"] = row[name + "_max"] = ""
        rows.append(row)
    err = c["pixel_error"]
    bounds = {"time_s": round(err * s_per_px), "temperature_C": round(err * 160 / 452, 2),
              "pressure_psig": round(err * 60 / 452, 2), "level_pct": round(err * 160 / 452, 2),
              "recirc_flow_klbh": round(err * 160 / 452, 2)}
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", newline="", encoding="utf-8") as f:
        f.write(f"# Digitized from {c['source']['figure']}, {c['source']['url']} "
                f"(sha256 {c['source']['sha256'][:16]}...), by scripts/digitize_bayer_fig11.py.\n")
        f.write(f"# Date {c['date']}, local time. Pixel-error bound (+/-): "
                + ", ".join(f"{k} {v}" for k, v in bounds.items())
                + ". _min/_max give the row range in a column (wide on steep segments). Blank: no trace pixel.\n")
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {CSV_OUT.relative_to(ROOT)}: {len(rows)} columns; bounds {bounds}")
    return rows, bounds


def load_rows():
    lines = [ln for ln in CSV_OUT.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def at(rows, hhmm, name, kind=""):
    """The value in the column nearest a time; kind '_max' / '_min' for the row range."""
    target = datetime.strptime(hhmm, "%H:%M:%S" if hhmm.count(":") == 2 else "%H:%M")
    best = min((r for r in rows if r[name + kind] != ""),
               key=lambda r: abs((datetime.strptime(r["time"], "%H:%M:%S") - target).total_seconds()))
    return float(best[name + kind]), best["time"]


def check(c, bounds):
    rows = load_rows()
    fail_t, _ = time_of(c["failure_line_x"], c)
    checks = []

    def add(what, source, stated, got, tol, unit):
        ok = abs(got - stated) <= tol
        checks.append((what, source, f"{stated:g} {unit}", f"{got:.1f} {unit}", f"±{tol:g}", "pass" if ok else "FAIL"))

    add("Failure line position (the figure's dotted line)", "Fig 11 caption: failure at 22:33",
        0, (fail_t - datetime.fromisoformat(f"{c['date']}T22:33:00")).total_seconds() / 60, 1, "min from 22:33")
    add("Temperature at failure", "Fig 11 label: 150.3 C", 150.3, at(rows, "22:33", "temperature_C", "_max")[0], 1.5, "°C")
    add("Pressure at failure", "Fig 11 label: 51.2 psig", 51.2, max(
        float(r["pressure_psig_max"]) for r in rows if r["pressure_psig_max"] != ""
        and "22:30:00" <= r["time"] <= "22:34:00"), 1.0, "psig")
    add("Pressure when the relief valve opened", "Fig 11 label: 44 psig at 22:27", 44,
        at(rows, "22:27", "pressure_psig")[0], 1.5, "psig")
    add("Level when recirculation stopped", "p. 39: 51 percent at 10:21 p.m.", 51, at(rows, "22:21", "level_pct")[0], 2, "%")
    flow_gap = [float(r["recirc_flow_klbh"]) for r in rows if "22:23:00" <= r["time"] <= "22:32:00"
                and r["recirc_flow_klbh"] != ""]
    add("Recirculation flow, 22:23 to 22:32", "p. 39: flow dropped to zero at 10:21 p.m.", 0,
        max(flow_gap) if flow_gap else 0.0, 1.5, "klb/h")
    add("Temperature less than 3 minutes after 22:21", "p. 39: 141 C in less than 3 minutes", 141,
        at(rows, "22:24", "temperature_C")[0], 2, "°C")
    add("Level when the pump started", "p. 38: about 30 percent at 6:14 p.m.", 30, at(rows, "18:14", "level_pct")[0], 3, "%")
    t1, t2 = at(rows, "18:45", "temperature_C")[0], at(rows, "20:30", "temperature_C")[0]
    add("Heating rate from 18:38", "p. 39: about 0.6 degrees per minute", 0.6, (t2 - t1) / 105, 0.15, "°C/min")
    early = [float(r["temperature_C"]) for r in rows if "18:16:00" <= r["time"] <= "18:38:00" and r["temperature_C"]]
    add("Temperature after the pump started, before heating (18:16 to 18:38, mean)",
        "p. 38: pump started 6:14 p.m.; temperature between 60 and 65 C", 62.5, statistics.fmean(early), 2.5, "°C")
    steady = [float(r["pressure_psig"]) for r in rows if "18:30:00" <= r["time"] <= "21:30:00" and r["pressure_psig"]]
    add("Pressure while steady (18:30 to 21:30, mean)", "p. 39: remained constant at 22 psig", 22,
        statistics.fmean(steady), 1.5, "psig")
    passed = sum(c_[5] == "pass" for c_ in checks)
    lines = ["# Figure 11, digitized: checks against the report's own text", "",
             f"Generated by `scripts/digitize_bayer_fig11.py`. Source: {c['source']['figure']}, {c['source']['url']}. "
             "The calibration comes only from the figure's axes, gridlines and tick marks "
             "(`data/bayer_rt/fig11_calibration.json`); the values below come from the report's text and the figure's "
             "labels and were never used to calibrate.", "",
             f"Pixel-error bounds: time ±{bounds['time_s']} s, temperature ±{bounds['temperature_C']} °C, "
             f"pressure ±{bounds['pressure_psig']} psig, level ±{bounds['level_pct']} %, "
             f"flow ±{bounds['recirc_flow_klbh']} klb/h.", "",
             f"**{passed} of {len(checks)} checks pass.**", "",
             "| Check | Stated by the report | Stated | Digitized | Tolerance | Result |", "|---|---|---|---|---|---|"]
    lines += [f"| {a} | {b} | {s} | {g} | {t} | {r} |" for a, b, s, g, t, r in checks]
    failed = {row[0] for row in checks if row[5] != "pass"}
    notes = {
        "Pressure while steady (18:30 to 21:30, mean)":
            "The figure's own pressure trace sits about 3 psig above the text's 22 psig for the whole steady period, "
            "about 22 pixels, far outside the pixel error. The pressure scale itself is confirmed by the two labelled "
            "pressures (44 psig at the relief, 51.2 psig at failure), which both pass. The figure and the text "
            "disagree; the replay uses the figure and states the difference.",
        "Temperature at failure":
            "The trace reaches the failure line about 1.6 °C below the figure's own 150.3 °C label, about 4.5 pixels. "
            "The trace was rising about 1 °C per 30-second column there, so the label may be a later reading than the "
            "last drawn point, which the dotted failure line partly covers.",
        "Temperature less than 3 minutes after 22:21":
            "The trace reaches 141 °C at about 22:27, not before 22:24. The report says the control system measured "
            "both the bulk liquid and the recirculation loop (p. 28); the text may quote the other sensor. Not "
            "verified: the report does not say which temperature the figure plots.",
    }
    if failed:
        lines += ["", "## Where the figure and the text disagree", ""]
        lines += [f"- **{k}.** {v}" for k, v in notes.items() if k in failed]
        lines += [f"- **{k}.** No explanation recorded yet." for k in sorted(failed - set(notes))]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{passed}/{len(checks)} checks pass; report {REPORT.relative_to(ROOT)}")
    for row in checks:
        if row[5] != "pass":
            print("  FAIL:", row[0], "stated", row[2], "digitized", row[3])
    return checks


def main(argv):
    steps = argv or ["fetch", "digitize", "check"]
    c = cal()
    bounds = None
    if "fetch" in steps:
        fetch(c)
    if "digitize" in steps:
        _, bounds = digitize(c)
    if "check" in steps:
        if bounds is None:
            err = c["pixel_error"]
            bounds = {"time_s": round(err * time_of(0, c)[1]), "temperature_C": round(err * 160 / 452, 2),
                      "pressure_psig": round(err * 60 / 452, 2), "level_pct": round(err * 160 / 452, 2),
                      "recirc_flow_klbh": round(err * 160 / 452, 2)}
        check(c, bounds)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
