"""Run selected workflows across registered public inputs and publish the pass/fail matrix (docs/GENERALIZATION.md).

The eight rows below cover selected workflows, not every tool in docs/SCRIPTS.md. This script runs each row on its
applicable registered public inputs and records one cell per (workflow, input): pass, fail, n/a
(the tool can't apply to this input, with the reason), needs data (the input isn't cached; the cell names the fetch
command) or needs deps (a third-party module is missing). A red cell is the point: it says where a tool has not been
shown to carry over.

Rows (all model-free, offline):
  1  scan_cleanup.trace(clean="auto") with the answer key's symbols (the --oracle diagnostic): connection F1 by
     score_pid2graph, per keyed sheet set. Pass = F1 >= TRACER_PASS_F1, fixed before the first run.
  2  evaluate_vendor's known-answer controls (perfect, every class wrong, every box moved, empty) on every keyed set.
     Pass = evaluate_vendor's own control check (wrong answers <= symbol F1 0.10 on every sheet and overall).
  3  intake + report: the key as a prediction -> import_site_drawing -> deliverable_report on one sheet per set.
     Pass = no error, bundle item and link counts equal the key's, REPORT.html written.
  4  loop_audit on TE revisions A/C/D (published 0/19, 0+19 partly, 19/19), the Bayer sheet (loop list exported
     from the Bayer model's controllers) and DEXPI C01-C03 (loop list read from the XML's control functions).
  5  generate.py --out on each hand-built model. Pass = exit 0 and the files land in --out.
  6  csv_normal_bands on TE d00 vs each of d01-d21 (XMEAS 1-22 exported as in examples/historian-csv, fault start
     row 160), compared fault by fault with out/fault_detection/fault_detection.json.
  7  dexpi_to_twin on C01-C03: zero corrections against its own key, and the intake runs.
  8  line_layers.py's PIPE layer (what is piped directly to what) with the answer key's symbols, scored against the
     topology where the source holds it: the DEXPI XML (tees are elements), the current TE / Bayer drawer's own
     routes, and a truth derived from the OPEN100 key graph (line_layers.pid2graph_truth). A separate metric from
     row 1, which scores the network layer (all pairs on a line network). Pass = pipe-segment F1 >= PIPE_PASS_F1.

Inputs added 2026-10-29 (scripts/corpus_adapters.py turns each source into what the tool reads): DEXPI 1.2 exports
from four commercial P&ID tools and the DEXPI reference solutions, and the 1.3 single-feature cases (rows 7 and 4,
through dexpi_reader.py); SKAB, HAI 21.03 and PRONTO test days 2 and 4 (row 6); the IDAES HDA flowsheet and 42 DWSIM
flowsheets (row 5). Sheets that still need a hand-made key, and the HAI DCS loop graphs whose pairing needs a person
to confirm, are registered with an n/a cell that says so (kind needs_key / needs_confirmation); nothing is scored on
them. Every criterion for these cells was written here before the cells first ran (see NEW_CRITERIA_SET).

Usage
  python scripts/corpus_matrix.py                 # every row; writes out/generalization/matrix.json + docs/GENERALIZATION.md
  python scripts/corpus_matrix.py --rows 2,4      # only those rows; other rows are kept from the existing JSON
  python scripts/corpus_matrix.py --check         # docs/GENERALIZATION.md matches the JSON and no cell is stale
  python scripts/corpus_matrix.py --rows 4 --out-dir <scratch>   # write matrix.json + GENERALIZATION.md there instead
  python scripts/corpus_matrix.py --rows 6 --inputs skab,hai-21.03  # only those cells; every other cell is kept as is
Intermediate files go to temporary folders; nothing is written into data/ or other out/ folders.

Each cell records when it ran (`ran_at`) and a hash of every tool file it exercised (`tool_files`). `--check` fails
when a recorded hash no longer matches the file on disk, or a cell has none, so a cell left over from an older version
of a tool can't pass silently. corpus_matrix.py itself is not hashed (a wording change in the page would otherwise
stale every cell); a change to a row's runner here needs that row re-run by hand.
"""
import argparse
import contextlib
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
CORPUS = ROOT / "data" / "corpus.json"
OUT_JSON = ROOT / "out" / "generalization" / "matrix.json"
DOC = ROOT / "docs" / "GENERALIZATION.md"

# Row 1 pass threshold, fixed before the first run: the published oracle-tracer connection F1 on the development
# set (0.93, out/scorecard_r2-trace-oracle_dev.md) minus 0.05. A set that scores below it has lost more than a
# twentieth of the tracer's links relative to the drawings it was tuned on.
TRACER_PASS_F1 = 0.88
# Row 8 pass threshold, fixed 2026-10-29 before this row's first matrix run: the same bar as row 1, now on the pipe
# layer (pipe-segment F1, junctions matched by position). Not set from results, though the scorer had been run on these
# inputs while line_layers.py was written (DEXPI 0.68, TE and Bayer 1.0; data/attempts.json A139-A143).
PIPE_PASS_F1 = 0.88
FAULT_START = 160
STATUSES = ("pass", "fail", "n/a", "needs data", "needs deps")

ROWS = {
    1: {"tool": "trace_connections.py with scan clean-up (auto; oracle symbols)", "short": "Line tracer",
        "question": "Does the tracer tuned on OPEN100 0-5 hold on other styles and scans?"},
    2: {"tool": "evaluate_vendor.py controls", "short": "Scorer controls",
        "question": "Does a deliberately wrong answer stay at or below symbol F1 0.10 on every style?"},
    3: {"tool": "import_site_drawing.py + deliverable_report.py", "short": "Intake + report",
        "question": "Does the plumbing run on every style, with bundle counts equal to the key's?"},
    4: {"tool": "loop_audit.py", "short": "Loop audit",
        "question": "Does the loop audit give the right answer on loop lists and drawings it wasn't built on?"},
    5: {"tool": "generate.py --out", "short": "Exports",
        "question": "Does every hand-built model validate and write its platform files where asked?"},
    6: {"tool": "csv_normal_bands.py", "short": "Historian bands",
        "question": "Does the CSV route agree fault by fault with the TE fault-detection result, and on real facility "
                    "data (PRONTO) does it catch the fault without flagging normal running first?"},
    7: {"tool": "dexpi_to_twin.py / dexpi_reader.py", "short": "DEXPI route",
        "question": "Is the DEXPI conversion lossless against its key on every sheet, does the intake take it, and does "
                    "the reader keep what other tools' DEXPI exports hold?"},
    8: {"tool": "line_layers.py (pipe layer, oracle symbols)", "short": "Pipe layer",
        "question": "Where the source holds the real pipe topology, does the traced pipe layer (what is piped "
                    "directly to what, through which junctions) match it?"},
}
KEYED = ["open100-dev", "open100-holdout", "open100-scan-L1", "open100-scan-L2", "open100-scan-L3",
         "pid2graph-synthetic", "dexpi", "te-rev-a", "te-rev-c", "te-rev-d", "te-rev-c-scan-L3", "bayer-rt1"]
DEXPI_READER_INPUTS = {  # input id -> (DEXPI version folder, exporter, case prefixes or None for all)
    "dexpi-1.3-small-cases": ("1.3", "pid-toolbox", ("E", "I", "P")),
    "dexpi-1.2-reference": ("1.2", "reference", None),
    "dexpi-1.2-sppid": ("1.2", "sppid", None),
    "dexpi-1.2-comos": ("1.2", "comos", None),
    "dexpi-1.2-aveva": ("1.2", "aveva", None),
    "dexpi-1.2-autocad": ("1.2", "autocad", None),
}
NOT_SCORED_KINDS = ("needs_key", "needs_confirmation")
# Inputs keyed by a coding agent (data/agent_keys/, attempt A172): first-pass keys no person has reviewed. Their cells
# are scored with the row's own criterion but labelled on every surface and never pooled with human-keyed results or
# counted as an independent source family.
AGENT_KIND = "agent-keyed-sheets"
AGENT_KEYED = ["omre-1958-pid", "commons-pid-sheets", "pronto-fig1"]
AGENT_KEY_MARK = "(agent-made key)"
AGENT_KEY_LABEL = "agent-made key, first pass, not reviewed by a person"
# Adapter sources: the original three were held out for drift, then used to develop cyclic. Only 2019 remains
# held out for the default auto/cyclic method (A178 split, A183 method, A184 run).
HELDOUT_HISTORIAN = ["uci-hydraulic", "metropt3", "battledim", "battledim-2019"]
ROW_INPUTS = {
    1: KEYED + ["dexpi-1.2-vendor-renders"] + AGENT_KEYED,
    2: KEYED + AGENT_KEYED,
    3: [i for i in KEYED if i != "te-rev-c-scan-L3"] + ["own-drawing-extraction"] + AGENT_KEYED,
    4: ["te-rev-a", "te-rev-c", "te-rev-d", "bayer-rt1", "dexpi"] + list(DEXPI_READER_INPUTS)
       + ["hai-dcs-loops", "omre-1958-pid", "pronto-fig1"],
    5: ["te-model", "bayer-model", "water-fixture", "idaes-hda", "dwsim-fossee"],
    6: ["te-braatz-runs", "pronto-day3", "pronto-day2", "pronto-day4", "skab", "hai-21.03"] + HELDOUT_HISTORIAN,
    7: ["dexpi"] + list(DEXPI_READER_INPUTS) + ["dexpi-1.2-cross-vendor"],
    8: ["open100-dev", "open100-holdout", "dexpi", "te-rev-a", "te-rev-c", "te-rev-d", "bayer-rt1",
        "dexpi-1.2-vendor-renders"] + AGENT_KEYED,
}
# The tool files each row's cells exercise (roots; the scripts/ modules they import are added by tool_files), hashed
# into every cell so --check can tell a stale cell.
# Known dynamic imports need explicit roots: build_twin calls confidence through __import__.
# These declarations cover the intake routes below; native-reader overrides do not call it.
ROW_TOOL_FILES = {
    1: ["scripts/scan_cleanup.py", "scripts/trace_connections.py", "scripts/score_pid2graph.py"],
    2: ["scripts/evaluate_vendor.py", "scripts/score_pid2graph.py"],
    3: ["scripts/import_site_drawing.py", "scripts/deliverable_report.py", "scripts/test_scorer_controls.py",
        "scripts/confidence.py"],
    4: ["scripts/loop_audit.py"],
    5: ["scripts/generate.py"],
    6: ["scripts/csv_normal_bands.py"],
    7: ["scripts/dexpi_to_twin.py", "scripts/adapt_dexpi.py", "scripts/import_site_drawing.py",
        "scripts/score_pid2graph.py", "scripts/confidence.py"],
    8: ["scripts/line_layers.py", "scripts/trace_connections.py", "scripts/score_pid2graph.py"],
}
# Cells that exercise other files than their row's roots (the 2026-10-29 inputs): exactly these, plus their imports.
ADAPTER = "scripts/corpus_adapters.py"
ROW_TOOL_FILES_ONLY = {
    **{(7, i): ["scripts/dexpi_reader.py", ADAPTER] for i in list(DEXPI_READER_INPUTS) + ["dexpi-1.2-cross-vendor"]},
    **{(4, i): ["scripts/dexpi_reader.py", "scripts/loop_audit.py", ADAPTER] for i in DEXPI_READER_INPUTS},
    (4, "hai-dcs-loops"): [ADAPTER],
    **{(5, i): ["scripts/generate.py", ADAPTER] for i in ("idaes-hda", "dwsim-fossee")},
    **{(6, i): ["scripts/csv_normal_bands.py", ADAPTER] for i in ("pronto-day2", "pronto-day4", "skab", "hai-21.03")},
    **{(6, i): ["scripts/csv_normal_bands.py", "scripts/historian_adapters.py"] for i in HELDOUT_HISTORIAN},
    **{(r, "dexpi-1.2-vendor-renders"): [ADAPTER, "scripts/adapt_dexpi.py", "scripts/line_layers.py",
                                         "scripts/trace_connections.py", "scripts/score_pid2graph.py"]
                                         + (["scripts/scan_cleanup.py"] if r == 1 else []) for r in (1, 8)},
}
ROW_TOOL_FILES_BY_INPUT = {(4, "dexpi"): ["scripts/dexpi_to_twin.py", "scripts/adapt_dexpi.py",
                                          "scripts/import_site_drawing.py", "scripts/confidence.py"],
                           (8, "dexpi"): ["scripts/adapt_dexpi.py", "scripts/dexpi_to_twin.py"],
                           (8, "te-rev-d"): ["scripts/draw_pid_from_model.py"],
                           (8, "bayer-rt1"): ["scripts/draw_pid_from_model.py"]}
# Row 8: which line_layers.py truth each input has, or why it has none.
PIPE_SETS = {"dexpi": "dexpi", "te-rev-d": "te", "bayer-rt1": "bayer", "open100-dev": "open100",
             "open100-holdout": "open100", "dexpi-1.2-vendor-renders": "dexpi-1.2-vendor"}
VENDOR = "dexpi-1.2-vendor-renders"
VENDOR_HELD_OUT = ("initial baseline held out (A173 mapping and scoring plan, A174 scored once). For the later pipe "
                   "changes A191-A195, A177 made SPPID development data and kept Comos and AVEVA held out, seen once "
                   "before as a baseline (frozen run A196); the pooled vendor result mixes those splits. A192 fixes "
                   "junction matching in the scorer: SPPID 0.679 to 0.852 without a tracing change, about two thirds "
                   "of its total development gain to 0.939. The row-1 tracer is unchanged on these renders by the "
                   "auto scan clean-up (A189). Matrix re-runs are deterministic checks of the frozen rules")
OPEN100_HOLDOUT_PIPE_NOTE = ("A177 held these sheets out for the frozen A191-A195 rules (A196, seen once before as a "
                             "baseline); not fully blind overall: A170's crossing error class was first noticed on "
                             "sheet 6, then confirmed on development DEXPI C01. A191 changes the derived truth too "
                             "(388 to 386 segments), so the change from 0.898 to 0.912 is not pure tracing gain")
PIPE_NA = {"te-rev-a": "drawn by an earlier generator, model and layout (data/te_pid/rev-a/manifest.json); the pipe "
                       "truth comes from the current drawer's own routes, so it can't be re-derived for this revision",
           "te-rev-c": "drawn by an earlier generator, model and layout (data/te_pid/rev-c/manifest.json); the pipe "
                       "truth comes from the current drawer's own routes, so it can't be re-derived for this revision"}
# Input families this repository generated from its own process model (drawing, key and loop list all come from the
# same model), so a pass on them is circular evidence: it shows the tools agree with the generator, not that they
# carry over to someone else's drawing.
SELF_GENERATED_FAMILIES = ("te-generated", "bayer-generated")
SELF_GENERATED_MARK = "(self-generated)"
TE_LOOPS = "examples/loop-audit/te_loops.csv"
TE_LOOP_EXPECTED = {"te-rev-a": "0 of 19 loops drawn, 0 partly drawn, 19 not drawn",
                    "te-rev-c": "0 of 19 loops drawn, 19 partly drawn, 0 not drawn",
                    "te-rev-d": "19 of 19 loops drawn, 0 partly drawn, 0 not drawn"}


# ------------------------------------------------------------------ registry and inputs

def load_corpus(path=CORPUS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inputs_by_id(corpus):
    return {i["id"]: i for i in corpus["inputs"]}


def sheet_sort(name):
    return (0, int(name), "") if name.isdigit() else (1, 0, name)


def sheets_of(inp):
    base = ROOT / inp["local_path"]
    if str(inp.get("sheets", "")).startswith("set:"):  # a line_layers set read from its sidecars (mapped sheets only)
        import line_layers as ll
        return ll.set_sheets(inp["sheets"][4:], base)
    if inp.get("sheets") == "all":
        return sorted((g.stem for g in base.glob("*.graphml")), key=sheet_sort)
    return list(inp.get("sheets") or [])


def missing_files(inp):
    """Repo-relative paths an input needs that are absent (empty list = available)."""
    base = ROOT / inp["local_path"]
    if inp["kind"] in NOT_SCORED_KINDS:
        return []
    if inp["kind"] == AGENT_KIND:
        return ([f"{inp['local_path']}/{s}.graphml" for s in inp["sheets"] if not (base / f"{s}.graphml").is_file()]
                + sorted({x["source"] for x in inp["stage"].values() if not (ROOT / x["source"]).is_file()}))
    if inp["kind"] != "keyed-sheets":
        return [] if base.exists() else [inp["local_path"]]
    if not base.is_dir():
        return [inp["local_path"]]
    sheets = sheets_of(inp)
    if not sheets:
        return [inp["local_path"] + "/*.graphml"]
    return [f"{inp['local_path']}/{s}.{e}" for s in sheets for e in ("png", "graphml")
            if not (base / f"{s}.{e}").is_file()]


def tool_files(row, input_id):
    """Explicit roots (including known dynamic imports), plus scripts/ imports found in source text."""
    todo = list(ROW_TOOL_FILES_ONLY.get((row, input_id))
                or ROW_TOOL_FILES[row] + ROW_TOOL_FILES_BY_INPUT.get((row, input_id), []))
    seen = []
    while todo:
        rel = todo.pop(0)
        if rel in seen:
            continue
        seen.append(rel)
        path = ROOT / rel
        if not path.is_file():
            continue
        for mod in re.findall(r"^[ \t]*(?:from|import)[ \t]+([A-Za-z_]\w*)", path.read_text(encoding="utf-8"),
                              flags=re.M):
            if (SCRIPTS / f"{mod}.py").is_file():
                todo.append(f"scripts/{mod}.py")
    return sorted(seen)


def file_hash(rel):
    """sha256 of a repo file with CRLF folded to LF (a Windows checkout hashes the same), or None if absent."""
    path = ROOT / rel
    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def stale_cells(matrix):
    """One line per cell whose recorded tool hashes are missing or differ from the files on disk now."""
    out = []
    for c in matrix.get("cells", []):
        where = f"row {c['row']} x {c['input']}"
        recorded = c.get("tool_files")
        if not recorded:
            out.append(f"{where}: no tool hash recorded (the cell predates per-cell hashes)")
            continue
        missing = sorted(set(tool_files(c["row"], c["input"])) - set(recorded))
        if missing:
            out.append(f"{where}: required tool hash missing: {', '.join(missing)}")
            continue
        changed = [f for f, h in recorded.items() if file_hash(f) != h]
        if changed:
            out.append(f"{where}: {', '.join(changed)} changed since the cell ran ({c.get('ran_at', 'time unknown')})")
    return out


def self_generated(c_or_inp):
    return c_or_inp.get("family") in SELF_GENERATED_FAMILIES


def agent_keyed(c_or_inp):
    """A cell scored against (or an input carrying) an agent-made key."""
    return c_or_inp.get("key") == "agent-made" or c_or_inp.get("kind") == AGENT_KIND


def cell(row, inp, status, value="", reason="", detail=None, published=None):
    assert status in STATUSES, status
    return {"row": row, "input": inp["id"], "family": inp["family"], "status": status, "value": value,
            "reason": reason, "detail": detail or {}, "published": published or []}


def add_note(c, text):
    """An honest-labelling note on a cell that changes neither its criterion nor its verdict; the page shows it next
    to the reason or detail (and in Gaps for a failed cell)."""
    c["note"] = (c["note"] + "; " if c.get("note") else "") + text


# Rows 2 and 3 read only the answer key (row 2 builds its controls from the key, row 3 converts the key to a
# prediction); the scan inputs share open100-holdout's keys, so their cells repeat that cell exactly.
KEY_ONLY_SCAN_CELLS = {(r, f"open100-scan-L{n}"): "open100-holdout" for r in (2, 3) for n in (1, 2, 3)}
KEY_ONLY_SCAN_NOTE = ("key-only input: this row reads only the answer key, which is open100-holdout's, so the cell is "
                      "the same computation as open100-holdout and carries no scan-specific information (the scan "
                      "pixels are not exercised here)")


def needs_data(row, inp, missing):
    shown = ", ".join(missing[:2]) + (f" (+{len(missing) - 2} more)" if len(missing) > 2 else "")
    return cell(row, inp, "needs data", reason=f"needs data: {inp.get('fetch') or 'not fetchable'} (missing {shown})")


def published(file, needle, says, ours, agrees):
    """A published number and where it is: file:line found by searching for `needle` now, so the line stays right."""
    line = None
    p = ROOT / file
    if p.is_file():
        for n, text in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if needle in text:
                line = n
                break
    return {"file": file, "line": line, "says": says, "ours": ours, "agrees": bool(agrees)}


def quiet(fn, *a, **k):
    """Run a tool function with its stdout captured (the matrix reports results, not tool chatter)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return fn(*a, **k)


# ------------------------------------------------------------------ row 1: tracer with oracle symbols

def key_symbols(graphml, png):
    import score_pid2graph as sc
    w, h = sc.png_size(png)
    nodes, adj = sc.load_key(graphml, w, h)
    return [{"id": k, "class": v["class"], "box": v["box"]} for k, v in nodes.items() if v["class"] in sc.SCORED]


def row1(inp):
    try:
        import scan_cleanup
    except ImportError as e:
        return cell(1, inp, "needs deps", reason=f"needs deps: pip install -r requirements.txt ({e.name})")
    import score_pid2graph as sc
    base = ROOT / inp["local_path"]
    per, tp, npred, nkey, corr, items = {}, 0, 0, 0, 0, 0
    for s in sheets_of(inp):
        png, g = base / f"{s}.png", base / f"{s}.graphml"
        syms = key_symbols(g, png)
        t0 = time.time()
        cleanup_info = {}
        links = scan_cleanup.trace(png, syms, clean="auto", info=cleanup_info)
        r = sc.score(g, {"symbols": syms, "connections": links}, png)
        c = r["connections"]
        per[s] = {"connection_f1": round(c["f1"], 3), "precision": round(c["precision"], 3),
                  "recall": round(c["recall"], 3), "key_links": c["in_key"], "tp": c["tp"], "predicted": c["predicted"],
                  "truth": c["in_key"], "review_load_per_100": r["review_load"]["per_100"],
                  "seconds": round(time.time() - t0, 1), "scan_cleaned": cleanup_info["cleaned"]}
        tp, npred, nkey = tp + c["tp"], npred + c["predicted"], nkey + c["in_key"]
        corr, items = corr + r["review_load"]["corrections"], items + r["review_load"]["key_items"]
    f1 = 2 * tp / (npred + nkey) if npred + nkey else 0.0
    p, rc = (tp / npred if npred else 0.0), (tp / nkey if nkey else 0.0)
    rl = round(100 * corr / items, 1) if items else 0.0
    worst = min(per, key=lambda s: per[s]["connection_f1"])
    detail = {"sheets": per, "connection_f1": round(f1, 3), "precision": round(p, 3), "recall": round(rc, 3),
              "review_load_per_100": rl, "key_links": nkey, "worst_sheet": worst, "scan_cleanup": "auto"}
    pub = []
    if inp["id"] == "open100-dev":
        ours = f"{f1:.2f} (P {p:.2f} / R {rc:.2f}), review load {rl}"
        pub.append(published("out/scorecard_r2-trace-oracle_dev.md", "| oracle | answer-key-symbols",
                             "connection F1 0.93 (P 0.96 / R 0.90), review load 9.6", ours,
                             f"{f1:.2f}" == "0.93" and f"{p:.2f}" == "0.96" and f"{rc:.2f}" == "0.90" and rl == 9.6))
    ok = f1 >= TRACER_PASS_F1
    reason = "" if ok else (f"connection F1 {f1:.3f} < {TRACER_PASS_F1} (precision {p:.3f}, recall {rc:.3f}; worst "
                            f"sheet {worst} at {per[worst]['connection_f1']})")
    return cell(1, inp, "pass" if ok else "fail", f"F1 {f1:.3f}", reason, detail, pub)


# ------------------------------------------------------------------ row 2: scorer controls

def row2(inp):
    import evaluate_vendor as ev
    base = ROOT / inp["local_path"]
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "no-vendor-run"
        empty.mkdir()
        r = quiet(ev.evaluate, base, [empty], sheets_of(inp), name="controls only")
    agg = r["controls"]
    wrong = {n: round(agg[n]["symbol_f1_rough_classified"], 3) for n in ("wrong_class", "shifted")}
    per_sheet_max = max(r["per_sheet"][s]["controls"][n]["symbol_f1_rough_classified"]
                        for s in r["sheets"] for n in ("wrong_class", "shifted"))
    detail = {"sheets": len(r["sheets"]), "wrong_answer_symbol_f1_overall": wrong,
              "wrong_answer_symbol_f1_max_one_sheet": round(per_sheet_max, 3),
              "review_load_per_100": {n: round(agg[n]["review_load_per_100"], 1) for n in ev.CONTROL_ORDER},
              "control_failures": r["control_failures"]}
    pub = []
    if inp["id"] == "open100-holdout":
        for name, label, needle in (("wrong_class", "every class wrong", "| Every class wrong |"),
                                    ("shifted", "every box moved half a sheet", "| Every box moved half a sheet |")):
            line = next(l for l in (ROOT / "examples/vendor-evaluation/README.md").read_text(encoding="utf-8").splitlines()
                        if needle in l)
            cols = [c.strip() for c in line.strip("|").split("|")]
            ours_rl, ours_f1 = round(agg[name]["review_load_per_100"], 1), f"{agg[name]['symbol_f1_rough_classified']:.3f}"
            pub.append(published("examples/vendor-evaluation/README.md", needle,
                                 f"{label}: review load {cols[1]}, symbol F1 {cols[2]}",
                                 f"review load {ours_rl}, symbol F1 {ours_f1}",
                                 str(ours_rl) == cols[1] and ours_f1 == cols[2]))
    ok = r["controls_ok"]
    reason = "" if ok else "; ".join(r["control_failures"])
    if not ok and all("still matched at strict IoU" in f for f in r["control_failures"]):
        reason += (f". The F1 limit holds (no wrong answer above {per_sheet_max:.3f} on any sheet); what fails is "
                   f"evaluate_vendor's separate rule that a box moved half a sheet must never match at strict IoU, so "
                   f"the kit would print CONTROLS FAILED and exit 2 on this set")
    return cell(2, inp, "pass" if ok else "fail", f"wrong max {per_sheet_max:.3f}", reason, detail, pub)


# ------------------------------------------------------------------ row 3: intake + report

def intake_and_report(manifest, bundle):
    """-> (summary, plant_model, report_written, review_rows). Raises whatever the tools raise."""
    import deliverable_report as dr
    import import_site_drawing as isd
    result = quiet(isd.import_drawing, manifest, bundle)
    code = quiet(dr.main, [str(bundle)])
    model = json.loads((Path(bundle) / "plant_model.json").read_text(encoding="utf-8"))
    with (Path(bundle) / "review_queue.csv").open(encoding="utf-8", newline="") as f:
        review_rows = sum(1 for _ in csv.reader(f)) - 1
    return result["summary"], model, code == 0 and (Path(bundle) / "REPORT.html").is_file(), review_rows


def bundle_items(summary):
    return summary["equipment"] + summary["instruments"] + summary["line_items"] + summary["offpage_connectors"]


def row3(inp):
    if inp["id"] == "own-drawing-extraction":
        return row3_recorded(inp)
    from test_scorer_controls import perfect_prediction
    base = ROOT / inp["local_path"]
    sheet = sheets_of(inp)[0]
    pred = perfect_prediction(base / f"{sheet}.graphml", base / f"{sheet}.png")
    c = row3_once(inp, base, sheet, pred)
    if c["status"] == "fail" and "unsafe or empty id" in c["reason"]:
        # Say whether the plumbing itself works once the ids are made safe; the cell stays a FAIL, because the key's
        # own ids (and evaluate_vendor's perfect control built from them) are what a user would feed it.
        safe = {s["id"]: s["id"].replace("/", "_") for s in pred["symbols"]}
        retry = row3_once(inp, base, sheet, {
            "symbols": [dict(s, id=safe[s["id"]]) for s in pred["symbols"]],
            "connections": [{"from": safe[x["from"]], "to": safe[x["to"]]} for x in pred["connections"]]})
        bad = sorted(i for i in safe if i != safe[i])
        c["reason"] += (f". The key's node ids contain '/' ({len(bad)} ids, e.g. {bad[0]}), which the intake refuses; "
                        f"with '/' replaced by '_' the same sheet gives: {retry['status']}"
                        + (f" ({retry['value']})" if retry["status"] == "pass" else f" ({retry['reason']})"))
        c["detail"]["retry_with_safe_ids"] = {"status": retry["status"], "value": retry["value"],
                                             "detail": retry["detail"]}
    return c


def row3_once(inp, base, sheet, pred):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copyfile(base / f"{sheet}.png", tmp / "sheet.png")
        (tmp / "prediction.json").write_text(json.dumps(pred), encoding="utf-8")
        manifest = {"schema_version": "site-drawing-intake-1", "drawing_id": f"{inp['id']}-{sheet}",
                    "revision": "public", "page": 1, "image": "sheet.png", "extraction": "prediction.json",
                    "extraction_format": "prediction",
                    "producer": {"method": "answer key as prediction, no model", "tool": "corpus_matrix.py",
                                 "model": None}}
        (tmp / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        try:
            summary, model, report_ok, review_rows = intake_and_report(tmp / "manifest.json", tmp / "bundle")
        except Exception as e:  # any crash is the finding
            return cell(3, inp, "fail", "crash", f"sheet {sheet}: {type(e).__name__}: {str(e)[:300]}",
                        {"sheet": sheet})
    n_sym, n_links = len(pred["symbols"]), len(pred["connections"])
    items, streams = bundle_items(summary), summary["streams_extracted"]
    detail = {"sheet": sheet, "key_symbols": n_sym, "key_links": n_links, "bundle_items": items,
              "bundle_links": streams, "equipment": summary["equipment"], "instruments": summary["instruments"],
              "line_items": summary["line_items"], "offpage_connectors": summary["offpage_connectors"],
              "review_rows": review_rows, "report_written": report_ok}
    problems = []
    if items != n_sym:
        problems.append(f"bundle has {items} items, key has {n_sym} symbols")
    if streams != n_links:
        problems.append(f"bundle has {streams} links, key has {n_links}")
    if not report_ok:
        problems.append("REPORT.html not written")
    return cell(3, inp, "fail" if problems else "pass", f"{items} items, {streams} links", "; ".join(problems),
                detail)


def row3_recorded(inp):
    manifest = ROOT / "examples" / "own-drawing" / "manifest.json"
    record = json.loads((ROOT / inp["local_path"]).read_text(encoding="utf-8"))
    pred = record.get("prediction", record)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            summary, model, report_ok, review_rows = intake_and_report(manifest, Path(tmp) / "bundle")
        except Exception as e:
            return cell(3, inp, "fail", "crash", f"{type(e).__name__}: {str(e)[:300]}")
    items, streams = bundle_items(summary), summary["streams_extracted"]
    ours = (f"{summary['equipment']} equipment, {summary['instruments']} instruments, {summary['line_items']} line "
            f"items, {summary['offpage_connectors']} off-page connectors, {streams} links")
    says = "2 equipment, 36 instruments, 53 line items, 9 off-page connectors, 345 links"
    pub = [published("examples/own-drawing/README.md", "| `plant_model.json` |", says, ours, ours == says),
           published("examples/own-drawing/README.md", "| `review_queue.csv` |", "445 rows", f"{review_rows} rows",
                     review_rows == 445)]
    detail = {"recorded_symbols": len(pred["symbols"]), "recorded_connections": len(pred["connections"]),
              "bundle_items": items, "bundle_links": streams, "review_rows": review_rows, "report_written": report_ok}
    problems = [f"published {p['says']}, got {p['ours']}" for p in pub if not p["agrees"]]
    if not report_ok:
        problems.append("REPORT.html not written")
    note = ("bundle counts are compared with the README, not with the recorded extraction: the converter drops "
            "unsupported symbols and duplicate links by design") if not problems else ""
    return cell(3, inp, "fail" if problems else "pass", f"{items} items, {streams} links",
                "; ".join(problems) or note, detail, pub)


# ------------------------------------------------------------------ row 4: loop audit

def write_loops(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["controller", "measurement", "output", "description"])
        w.writerows(rows)


def audit(loops_csv, drawing):
    import loop_audit as la
    r = la.run(loops_csv, drawing)
    return r, la.headline(r)


def loop_rows_summary(r):
    return [{"controller": l.get("controller"), "status": l["status"],
             "missing": l.get("missing") or [k for k, v in (l.get("checks") or {}).items() if v is False]}
            for l in r["loops"]]


def row4(inp):
    if inp["id"].startswith("te-rev-"):
        r, head = audit(ROOT / TE_LOOPS, ROOT / inp["local_path"] / "key.json")
        expected = TE_LOOP_EXPECTED[inp["id"]]
        pub = [published("examples/loop-audit/README.md", f"# {expected}", expected, head, head == expected)]
        detail = {"loop_list": TE_LOOPS, "drawing": f"{inp['local_path']}/key.json", "headline": head,
                  "by_check": r["by_check"]}
        t = r["totals"]
        counts = f"{t['drawn']}/{t['loops']} drawn" + (f", {t['partly_drawn']} partly" if t["partly_drawn"] else "")
        # "pass 0/19 drawn" would read as a success; the pass is that the audit reproduces the published result.
        value = f"matches the published result ({counts})" if head == expected else counts
        return cell(4, inp, "pass" if head == expected else "fail", value,
                    "" if head == expected else f"expected '{expected}', got '{head}'", detail, pub)
    if inp["id"] == "bayer-rt1":
        return row4_bayer(inp)
    if inp["id"] in DEXPI_READER_INPUTS:
        return row4_reader(inp)
    return row4_dexpi(inp)


def bayer_loop_lists():
    """The Bayer model's controllers as loop lists. loop_audit refuses a controller listed twice, so a split-range
    controller (TIC-104 -> TV-104A/B/C) gets one list per leg; every other controller is in the first list."""
    model = json.loads((ROOT / "data/bayer_rt/process_model.json").read_text(encoding="utf-8"))
    lists = [[]]
    for c in model["controllers"]:
        out = c["output"]
        legs = [out["final_element"]] if "final_element" in out else list(out.get("split_range") or [])
        for i, leg in enumerate(legs):
            while len(lists) <= i:
                lists.append([])
            lists[i].append([c["tag"], c["measurement"], leg, c["description"][:60]])
    return lists


def row4_bayer(inp):
    key = ROOT / inp["local_path"] / "key.json"
    legs, results = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for n, rows in enumerate(bayer_loop_lists()):
            path = Path(tmp) / f"bayer_loops_{n}.csv"
            write_loops(path, rows)
            r, head = audit(path, key)
            results.append(head)
            legs += [dict(s, output=row[2]) for s, row in zip(loop_rows_summary(r), rows)]
    drawn = sum(l["status"] == "drawn" for l in legs)
    detail = {"loop_list": "exported from data/bayer_rt/process_model.json controllers (one list per split-range "
                           "leg)", "drawing": f"{inp['local_path']}/key.json", "legs": legs, "headlines": results}
    bad = [f"{l['controller']} -> {l['output']}: {l['status']} (missing {', '.join(l['missing'])})"
           for l in legs if l["status"] != "drawn"]
    return cell(4, inp, "fail" if bad else "pass", f"{drawn}/{len(legs)} loop legs drawn", "; ".join(bad), detail)


def dexpi_xml(sheet):
    import adapt_dexpi as A
    import dexpi_to_twin as d2t
    _, spec = d2t.sheet_spec(sheet)
    return A.local_path(spec["xml"])


def dexpi_control_loops(xml_path):
    """Control loops in a DEXPI file: ProcessInstrumentationFunctions whose function letters include C (control).
    controller = drawn label (category + function letters + number), measurement = the signal-generating function's
    number, output = the actuating function's number."""
    root = ET.parse(xml_path).getroot()
    loops = []
    for p in root.iter("ProcessInstrumentationFunction"):
        a = {g.get("Name"): g.get("Value") for g in p.iter("GenericAttribute") if g.get("Value")}
        cat = a.get("ProcessInstrumentationFunctionCategoryAssignmentClass")
        fns = a.get("ProcessInstrumentationFunctionsAssignmentClass") or ""
        num = a.get("ProcessInstrumentationFunctionNumberAssignmentClass")
        if not (cat and num and "C" in fns):
            continue
        label = f"{cat}{fns} {num}"
        # When the sensor (ProcessSignalGeneratingFunction) is nested inside this function, DEXPI draws one combined
        # bubble with no separate transmitter label: list the controller as its own measurement (loop_audit treats
        # that as a combined instrument). Otherwise the measurement is the separately drawn transmitter.
        nested = p.find("ProcessSignalGeneratingFunction") is not None
        meas = label if nested else (a.get("ProcessSignalGeneratingFunctionNumberAssignmentClass") or "")
        loops.append([label, meas, a.get("ActuatingFunctionNumberAssignmentClass") or "", p.get("ID")])
    return loops


def dexpi_bundle(sheet, tmp):
    """dexpi_to_twin -> prediction + manifest in tmp -> intake bundle. Returns (prediction, bundle path, summary)."""
    import dexpi_to_twin as d2t
    import import_site_drawing as isd
    cfg, spec = d2t.sheet_spec(sheet)
    pred, _ = quiet(d2t.convert, sheet, None, dexpi_xml(sheet))
    png = d2t.key_paths(sheet)["png"]
    _, man = d2t.write_outputs(sheet, pred, Path(tmp), cfg, spec, png)
    bundle = Path(tmp) / f"{sheet}-bundle"
    result = quiet(isd.import_drawing, man, bundle)
    return pred, bundle, result["summary"]


def row4_dexpi(inp):
    per, legs = {}, []
    with tempfile.TemporaryDirectory() as tmp:
        for sheet in sheets_of(inp):
            xml = dexpi_xml(sheet)
            if not Path(xml).is_file():
                return needs_data(4, inp, [f"DEXPI XML for {sheet}"])
            loops = dexpi_control_loops(xml)
            if not loops:
                per[sheet] = "no control loop in the XML (no instrumentation function with a C letter)"
                continue
            _, bundle, _ = dexpi_bundle(sheet, tmp)
            path = Path(tmp) / f"{sheet}_loops.csv"
            write_loops(path, [l[:3] + [l[3]] for l in loops])
            r, head = audit(path, bundle / "plant_model.json")
            per[sheet] = head
            legs += [dict(s, sheet=sheet, measurement=l[1], output=l[2]) for s, l in zip(loop_rows_summary(r), loops)]
    import loop_audit as la
    combined = [l for l in legs if la.compact(l["measurement"]) == la.compact(l["controller"])]
    tags = sorted({t for l in legs for t in (l["controller"], l["measurement"], l["output"])},
                  key=la.compact)
    detail = {"loop_list": "read from each DEXPI XML: control functions (C in the function letters)",
              "drawing": "plant_model.json from the DEXPI intake bundle (tags only; the bundle has no signal lines)",
              "per_sheet": per, "loops": legs, "combined_instruments": len(combined),
              "distinct_tags_checked": len(tags), "tags_checked": tags,
              "not_checked": "signal lines (the bundle has none)" + (
                  "; a separate measurement symbol (every loop here is a combined instrument: DEXPI nests the sensor "
                  "in the controller bubble, so the measurement is the controller's own tag)"
                  if len(combined) == len(legs) else "")}
    if not legs:
        return cell(4, inp, "n/a", "no loop list", "not applicable: no control loop in any DEXPI XML", detail)
    ok = [l for l in legs if l["status"] == "tags_present"]
    bad = [f"{l['sheet']} {l['controller']}: {l['status']} (missing {', '.join(l['missing'])})"
           for l in legs if l["status"] != "tags_present"]
    what = ("controller + output tags present" if len(combined) == len(legs) else "tags present")
    value = (f"{len(ok)}/{len(legs)} loops {what}; {len(combined)} combined instrument"
             f"{'s' if len(combined) != 1 else ''}, {len(tags)} distinct tags checked")
    return cell(4, inp, "fail" if bad else "pass", value, "; ".join(bad), detail)


# ------------------------------------------------------------------ row 5: exports

def row5(inp):
    if inp["id"] == "idaes-hda":
        return row5_idaes(inp)
    if inp["id"] == "dwsim-fossee":
        return row5_dwsim(inp)
    src = ROOT / inp["local_path"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        model_dir, out = tmp / "model", tmp / "out"
        model_dir.mkdir()
        model = model_dir / src.name  # a copy: an extracted twin is written next to its model file
        shutil.copyfile(src, model)
        p = subprocess.run([sys.executable, str(SCRIPTS / "generate.py"), str(model), "--out", str(out)],
                           capture_output=True, text=True, cwd=ROOT, timeout=300)
        in_out = sorted(x.relative_to(out).as_posix() for x in out.rglob("*") if x.is_file()) if out.exists() else []
        beside = sorted(x.relative_to(model_dir).as_posix() for x in model_dir.rglob("*")
                        if x.is_file() and x.name != src.name)
        for t in (str(tmp), tmp.as_posix(), str(tmp.resolve())):  # never publish a local temp path
            p.stdout, p.stderr = p.stdout.replace(t, "<tmp>"), p.stderr.replace(t, "<tmp>")
    last = (p.stdout.strip().splitlines() or [""])[0] if p.returncode == 0 else ""
    detail = {"exit": p.returncode, "files_in_out": len(in_out), "files_written_beside_model": beside,
              "stdout_first_line": last, "stderr": p.stderr.strip()[-300:]}
    pub = []
    if inp["id"] == "bayer-model" and p.returncode == 0:
        ours = last.replace("model: ", "")
        pub.append(published("examples/from-description/README.md", "On the Bayer model it writes",
                             "5 units, 15 streams, 6 instruments and 5 valves", ours,
                             ours == "5 units, 15 streams, 6 instruments, 5 final elements"))
    if p.returncode != 0:
        return cell(5, inp, "fail", f"exit {p.returncode}", f"generate.py failed: {p.stderr.strip()[-300:]}", detail, pub)
    if not in_out:
        where = f"{len(beside)} files written next to the model instead ({', '.join(beside[:3])}...)" if beside else \
            "nothing written"
        return cell(5, inp, "fail", "--out ignored",
                    f"exit 0 but --out is empty: {where}. On the committed path that is "
                    f"{Path(inp['local_path']).parent.as_posix()}/", detail, pub)
    return cell(5, inp, "pass", f"{len(in_out)} files", "", detail, pub)


# ------------------------------------------------------------------ row 6: historian bands

def te_csv_header():
    with (ROOT / "examples/historian-csv/te_normal_d00.csv").open(encoding="utf-8", newline="") as f:
        return next(csv.reader(f))


def export_te_csv(dat, dest, header):
    """Same export as examples/historian-csv: every row, XMEAS 1-22, repr(float(text)), minutes = row x 3."""
    n = len(header) - 1
    with Path(dat).open(encoding="utf-8") as f, Path(dest).open("w", encoding="utf-8", newline="") as g:
        w = csv.writer(g)
        w.writerow(header)
        for i, line in enumerate(l for l in f if l.strip()):
            w.writerow([i * 3] + [repr(float(t)) for t in line.split()[:n]])


PRONTO_MAX_PRE = 0.005  # same target K is chosen for: at most 0.5% of rows flagged before the fault


HISTORIAN_README = "examples/historian-csv/README.md"
# Where examples/historian-csv/README.md states the fault-6 result for each method: the section heading it is under.
README_FAULT6_SECTION = {"drift": "## Results on the TE export", "level": "### (a)"}


def readme_fault6_check(method, d6, path=HISTORIAN_README):
    """The fault-6 detection delay and pre-fault flag count the README states for `method`, read from the README now
    (the section README_FAULT6_SECTION names), against this run. Nothing is hard-coded: a README that changes its
    statement changes what is checked."""
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    head = README_FAULT6_SECTION.get(method)
    start = next((n for n, l in enumerate(lines) if head and l.startswith(head)), None)
    ours = (f"fault 6 ({method}): detection at {d6['delay_min']} minutes, {d6['false_alarm_samples_before_fault']} of "
            f"160 pre-fault samples flagged")
    if start is None:
        return {"file": path, "line": None, "says": f"no section '{head}' stating the {method} method's fault-6 result",
                "ours": ours, "agrees": False}
    end = next((n for n in range(start + 1, len(lines)) if re.match(r"#{2,3} ", lines[n])), len(lines))
    text = "\n".join(lines[start:end])
    m = re.search(r"detection by the 3-consecutive rule at (\d+(?:\.\d+)?) minutes.{0,80}?(\d+) of the 160 "
                  r"pre-fault\s+samples flagged", text, flags=re.S)
    if not m:
        return {"file": path, "line": start + 1, "says": f"no fault-6 detection statement under '{head}'",
                "ours": ours, "agrees": False}
    line = start + 1 + text[:m.start()].count("\n")
    delay, pre = float(m.group(1)), int(m.group(2))
    return {"file": path, "line": line,
            "says": f"fault 6 ({method}): detection at {m.group(1)} minutes, {pre} of the 160 pre-fault samples flagged",
            "ours": ours, "agrees": d6["delay_min"] == delay and d6["false_alarm_samples_before_fault"] == pre}


def row6_pronto(inp):
    """Real facility data (PRONTO test day 3): learn bands on the normal CSV, score each fault run. Pass = detected
    by the 3-in-a-row rule at or after the labelled start AND at most 0.5% of pre-fault rows flagged. This criterion
    was set after the first run had been seen (it failed with the level bands), and the page says so."""
    import csv_normal_bands as cnb
    base = ROOT / inp["local_path"]
    pairs_path = base / "pairs.json"
    if not pairs_path.is_file():
        return needs_data(6, inp, [f"{inp['local_path']}/pairs.json"])
    pairs = json.loads(pairs_path.read_text(encoding="utf-8"))["files"]
    runs, verdicts, method = {}, [], None
    for name, info in sorted(pairs.items()):
        if "fault_start_row" not in info:
            continue
        r = cnb.run(base / "pronto_normal.csv", base / name, fault_start=str(info["fault_start_row"]))
        method = r["method_name"]
        s = r["scored"]["fault"]
        pre = s["false_alarms_before_fault"]["flagged_samples"]
        n_pre = info["fault_start_row"]
        ok = s["detection_run3_row"] is not None and pre <= PRONTO_MAX_PRE * n_pre
        runs[name] = {"k": r["k"], "fault_start_row": n_pre, "pre_fault_flagged": pre, "pre_fault_rows": n_pre,
                      "detected": s["detection_run3_row"] is not None,
                      "detection_run3_delay": s["detection_run3_delay"],
                      "pre_fault_tags": s["false_alarms_before_fault"]["tags"][:5], "pass": ok}
        verdicts.append((name.removeprefix("pronto_").removesuffix(".csv"), pre, n_pre, ok))
    value = ", ".join(f"{n} {pre}/{n_pre} pre-fault flagged" for n, pre, n_pre, _ in verdicts)
    detail = {"method": method,
              "fit": "pronto_normal.csv (10 minutes of normal running before the first fault of the day)",
              "criterion": "detected by 3 in a row at or after the labelled start, and at most 0.5% of pre-fault rows "
                           "flagged; set after the first run had been seen", "runs": runs,
              "development_data": DRIFT_DEVELOPMENT_NOTE if method == "drift" else None}
    if all(v[3] for v in verdicts):
        return cell(6, inp, "pass", value, "", detail)
    bad = [(n, runs[f"pronto_{n}.csv"]) for n, _, _, ok in verdicts if not ok]
    why = "; ".join(f"{n}: " + ("not detected" if not v["detected"] else
                                f"{v['pre_fault_flagged']}/{v['pre_fault_rows']} pre-fault rows flagged (tags "
                                f"{', '.join(v['pre_fault_tags'][:3]) or 'none'})") for n, v in bad)
    if method == "level":
        why += ("; level bands learned from 10 minutes of real normal running are far too narrow for slow drift, so "
                "normal running is flagged long before the fault; the TE simulator never drifts, which hid this")
    return cell(6, inp, "fail", value, f"{method} method: {why}", detail)


# The sources the drift method was developed and frozen on (data/attempts.json A163, A165, A171): its passes there are
# not held-out evidence.
DRIFT_DEVELOPMENT_NOTE = ("development data for the drift method (it was tuned and frozen on PRONTO days 2-4, SKAB, "
                          "HAI 21.03 and the TE runs; data/attempts.json A163, A165, A171), so a pass here is not a "
                          "held-out result")
HELDOUT_NOTE = ("held-out source for the drift method's second iteration: the split and the label mapping were fixed "
                "before any run (data/attempts.json A165) and the method was frozen on the development sources before "
                "this source was first scored, once (A171); the matrix re-runs that same frozen method "
                "(deterministic), nothing was tuned on the result")
CYCLIC_DEVELOPMENT_NOTE = ("development data for the auto/cyclic method (A178, A183): this source was held out for "
                           "the earlier drift method (A165, A171), then used to choose the cyclic method, so the "
                           "current result is not held-out evidence")
CYCLIC_HELDOUT_NOTE = ("held-out year for the auto/cyclic method: the split and label mapping were fixed in A178, "
                       "the method frozen in A183 and scored once in A184; the matrix re-runs that method "
                       "deterministically. This is the same L-Town network as 2018 development, so it tests "
                       "carry-over across years only. Detections arrive 14 hours to 5 days after leak start, "
                       "and tank level T1 drives most flags; it does not show prompt leak isolation")


def tool_flags(normal_csv, score_csv, k, method):
    """Per row of score_csv, whether any tag is flagged: csv_normal_bands.run's own fit and flags (first half of the
    normal CSV fits, the tags both CSVs share are scored) for the method it ran at the K it chose."""
    import csv_normal_bands as cnb
    _, tags, _, _ = cnb.read_historian_csv(normal_csv)
    return cnb.score_flags(normal_csv, score_csv, k, method), tags


def row6(inp):
    if inp["id"] in ("pronto-day2", "pronto-day4"):
        return row6_pronto_day(inp)
    if inp["id"] == "skab":
        return row6_skab(inp)
    if inp["id"] == "hai-21.03":
        return row6_hai(inp)
    if inp["id"] in HELDOUT_HISTORIAN:
        return row6_heldout(inp)
    if inp["family"] == "pronto":
        return row6_pronto(inp)
    import csv_normal_bands as cnb
    te = ROOT / inp["local_path"]
    need = [f"{inp['local_path']}/d{i:02d}_te.dat" for i in range(22) if not (te / f"d{i:02d}_te.dat").is_file()]
    if need:
        return needs_data(6, inp, need)
    ref = json.loads((ROOT / "out/fault_detection/fault_detection.json").read_text(encoding="utf-8"))
    ref_faults = ref["methods"]["shipped_bands"]["faults"]
    header = te_csv_header()
    faults, export_check = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i in range(22):
            export_te_csv(te / f"d{i:02d}_te.dat", tmp / f"d{i:02d}.csv", header)
        for name, committed in (("d00", "te_normal_d00.csv"), ("d06", "te_fault6_d06.csv")):
            export_check[name] = (tmp / f"{name}.csv").read_bytes() == (ROOT / "examples/historian-csv" / committed).read_bytes()
        k = method = None
        for f in range(1, 22):
            r = cnb.run(tmp / "d00.csv", tmp / f"d{f:02d}.csv", fault_start=str(FAULT_START))
            k, method = r["k"], r["method_name"]
            s = r["scored"]["fault"]
            rf = ref_faults[str(f)]
            det = s["detection_run3_delay"] is not None
            first = [t["tag"] for t in rf.get("first_tags", [])]
            faults[f] = {"detected": det, "delay_min": s["detection_run3_delay"],
                         "first_flag_min": s["first_flag_delay"],
                         "false_alarm_samples_before_fault": s["false_alarms_before_fault"]["flagged_samples"],
                         "false_alarm_events_before_fault": s["false_alarms_before_fault"]["alarm_events_run3"],
                         "post_fault_flag_rate": s["post_fault_detection_rate"],
                         "ref_detected": rf["detected"], "ref_delay_min": rf["delay_min"],
                         "ref_first_tags": first,
                         "ref_first_tags_in_csv": [t for t in first if t in header[1:]],
                         "agrees": det == rf["detected"]}
    n_det = sum(v["detected"] for v in faults.values())
    n_ref = sum(v["ref_detected"] for v in faults.values())
    agree = sum(v["agrees"] for v in faults.values())
    fa = sum(v["false_alarm_events_before_fault"] for v in faults.values())
    missed = [f for f, v in faults.items() if not v["detected"]]
    ref_missed = [f for f, v in faults.items() if not v["ref_detected"]]
    detail = {"method": method, "normal": "d00 exported (XMEAS 1-22)", "fault_start_row": FAULT_START, "k": k,
              "export_matches_committed_csv": export_check, "faults": faults, "detected": n_det,
              "reference_detected": n_ref, "agree": agree, "missed": missed, "reference_missed": ref_missed,
              "false_alarm_events_before_fault_total": fa}
    d6 = faults[6]
    pub = [published("docs/OPERATOR_SCREENS.md", "They flag **17 of 21**", "17 of 21 flagged on 52 channels; misses 3, 9, 15, 19",
                     f"{n_det} of 21 flagged on XMEAS 1-22; misses {', '.join(map(str, missed)) or 'none'}",
                     n_det == 17 and missed == [3, 9, 15, 19]),
           readme_fault6_check(method, d6)]
    bad = [f for f, v in faults.items() if not v["agrees"]]
    problems = []
    if bad:
        problems.append("disagrees with fault_detection.json on fault(s) " + ", ".join(
            f"{f} (CSV {'detected' if faults[f]['detected'] else 'missed'}, reference "
            f"{'detected' if faults[f]['ref_detected'] else 'missed'}; reference's first tags "
            f"{', '.join(faults[f]['ref_first_tags']) or 'none'}, of which in the 22 CSV columns: "
            f"{', '.join(faults[f]['ref_first_tags_in_csv']) or 'none'}; CSV first single flag "
            f"{faults[f]['first_flag_min']} min, post-fault flag rate {faults[f]['post_fault_flag_rate']})" for f in bad)
            + ". The reference flags on any of 52 channels (XMEAS 1-41 and XMV 1-11); this export has XMEAS 1-22 "
              "only, as examples/historian-csv does, so a fault seen first in a valve output or analyzer can be "
              "missed here. Not a contradiction of the published 17 of 21, which is for the 52 channels")
        if method == "drift":
            problems[-1] += (". This cell scores the default drift method, which flags fast change against each "
                             "tag's own 600-sample baseline, not a fixed level: a fault that moves a tag slowly or by "
                             "less than its band (1% of the reading at least) is missed; examples/historian-csv/"
                             "README.md explains the faults it misses and recommends --method level for a stationary "
                             "simulation like the TE")
    if not all(export_check.values()):
        problems.append(f"on-the-fly export differs from the committed CSVs: {export_check}")
    return cell(6, inp, "fail" if problems else "pass", f"{agree}/21 agree ({n_det}/21 detected, ref {n_ref})",
                "; ".join(problems), detail, pub)


# ------------------------------------------------------------------ row 7: DEXPI route

def row7(inp):
    if inp["id"] in DEXPI_READER_INPUTS:
        return row7_reader(inp)
    if inp["id"] == "dexpi-1.2-cross-vendor":
        return row7_cross_vendor(inp)
    import score_pid2graph as sc
    base = ROOT / inp["local_path"]
    per, problems, pub = {}, [], []
    with tempfile.TemporaryDirectory() as tmp:
        for sheet in sheets_of(inp):
            try:
                pred, bundle, summary = dexpi_bundle(sheet, tmp)
            except Exception as e:
                problems.append(f"{sheet}: {type(e).__name__}: {str(e)[:200]}")
                continue
            s = sc.score(base / f"{sheet}.graphml", pred, base / f"{sheet}.png")
            items = bundle_items(summary)
            per[sheet] = {"corrections": s["review_load"]["corrections"], "classified_f1": s["rough"]["classified"]["f1"],
                          "symbols": len(pred["symbols"]), "connections": len(pred["connections"]),
                          "tags": sum(1 for x in pred["symbols"] if x.get("tag")), "bundle_items": items,
                          "bundle_links": summary["streams_extracted"],
                          "bundle": {k: summary[k] for k in ("equipment", "instruments", "line_items", "offpage_connectors")}}
            if s["review_load"]["corrections"]:
                problems.append(f"{sheet}: {s['review_load']['corrections']} corrections against its own key")
            if items != len(pred["symbols"]) or summary["streams_extracted"] != len(pred["connections"]):
                problems.append(f"{sheet}: bundle {items} items / {summary['streams_extracted']} links vs prediction "
                                f"{len(pred['symbols'])} / {len(pred['connections'])}")
            if sheet == "dexpi-c01":
                b = per[sheet]["bundle"]
                ours = (f"{b['equipment']} equipment, {b['instruments']} instruments, {b['line_items']} line items, "
                        f"{b['offpage_connectors']} off-page connectors, {per[sheet]['bundle_links']} links")
                says = "5 equipment, 4 instruments, 14 line items, 2 off-page connectors, 37 links"
                pub.append(published("examples/from-dexpi/README.md", "| Bundle |", says, ours, ours == says))
                ours_p = f"{per[sheet]['symbols']} symbols, {per[sheet]['tags']} tags, {per[sheet]['connections']} connections"
                pub.append(published("examples/from-dexpi/README.md", "| Prediction |",
                                     "25 symbols, 20 tags, 37 connections", ours_p,
                                     ours_p == "25 symbols, 20 tags, 37 connections"))
    problems += [f"published {p['says']}, got {p['ours']}" for p in pub if not p["agrees"]]
    total = sum(v["corrections"] for v in per.values())
    return cell(7, inp, "fail" if problems else "pass", f"{total} corrections on {len(per)} sheets",
                "; ".join(problems), {"sheets": per}, pub)


# ------------------------------------------------------------------ row 8: the pipe layer

def row8(inp):
    if inp["id"] in PIPE_NA:
        return cell(8, inp, "n/a", reason=f"n/a: {PIPE_NA[inp['id']]}")
    try:
        import line_layers as ll
        import cv2  # noqa: F401
    except ImportError as e:
        return cell(8, inp, "needs deps", reason=f"needs deps: pip install -r requirements.txt ({e.name})")
    if inp.get("kind") == AGENT_KIND:  # staged agent-keyed sheets: a set registered for this call only
        name = f"agent-key:{inp['id']}"
        ll.SETS[name] = {"dir": inp["local_path"], "sheets": sheets_of(inp), "scope": "all", "truth": "pid2graph"}
        try:
            r = ll.score_set(name, sheets_of(inp))
        finally:
            ll.SETS.pop(name, None)
    else:
        r = ll.score_set(PIPE_SETS[inp["id"]], sheets_of(inp))
    t = r["total"]["segments"]
    per = {s: {"segment_f1": v["segments"]["f1"], "tp": v["segments"]["tp"], "predicted": v["segments"]["predicted"],
               "truth": v["segments"]["truth"], "precision": v["segments"]["precision"],
               "recall": v["segments"]["recall"], "item_to_item_f1": v["item_to_item"]["f1"],
               "junctions_found": v["junctions"]["tp"], "junctions_true": v["junctions"]["truth"],
               "junctions_predicted": v["junctions"]["predicted"], "crossings": v["crossings"], **v["counts"]}
           for s, v in r["sheets"].items()}
    worst = min(per, key=lambda s: per[s]["segment_f1"])
    detail = {"sheets": per, "scope": r["scope"], "segment_f1": t["f1"], "precision": t["precision"],
              "recall": t["recall"], "item_to_item_f1": r["total"]["item_to_item"]["f1"],
              "junctions": r["total"]["junctions"], "truth": r["sheets"][worst].get("truth_source"), "worst_sheet": worst}
    if inp.get("kind") == AGENT_KIND or PIPE_SETS[inp["id"]] == "open100":
        detail["truth"] = ("derived from the PID2Graph key graph (line_layers.pid2graph_truth): connector and crossing "
                           "nodes walked as line points, 3+-edge crossings as junctions")
        detail["truth_networks_match_key_pairs"] = {s: v.get("truth_networks_match_key_pairs")
                                                    for s, v in r["sheets"].items()}
    ok = t["f1"] >= PIPE_PASS_F1
    reason = "" if ok else (f"pipe-segment F1 {t['f1']:.3f} < {PIPE_PASS_F1} (precision {t['precision']:.3f}, "
                            f"recall {t['recall']:.3f}; worst sheet {worst} at {per[worst]['segment_f1']})")
    return cell(8, inp, "pass" if ok else "fail", f"F1 {t['f1']:.3f}", reason, detail)


# ------------------------------------------------------------------ inputs added 2026-10-29 (scripts/corpus_adapters.py)

# Every criterion below (and its text in ROW_CRITERIA) was written on 2026-10-29 before any of these cells first ran.
# Not blind: the staging pilot had already run dexpi_reader.py over the DEXPI files and reported preliminary counts
# (0 controllers on any DEXPI 1.2 file), and the truth definitions were checked on the DEXPI 1.3 C01-C03 files the
# reader was built on (where PICSA/TICSA are controllers and a hand switch HS driving a valve is also one, so check (c)
# is "every control function is a controller", not "equal counts"). Nothing was tuned on the new inputs.
NEW_CRITERIA_SET = "2026-10-29, before the first run of these cells"
IDAES_BALANCE_TOL = 1e-4


def not_scored(row, inp):
    detail = {"not_scored": True}
    if inp["id"] == "hai-dcs-loops" and (ROOT / inp["local_path"]).is_dir():
        import corpus_adapters as ca
        detail["candidates"] = ca.hai_dcs_candidates(ROOT / inp["local_path"])
    return cell(row, inp, "n/a", "", f"n/a: {inp['not_scored']}", detail)


def dexpi_selection(inp):
    import corpus_adapters as ca
    version, exporter, cases = DEXPI_READER_INPUTS[inp["id"]]
    return [f for f in ca.dexpi_files(version, cases) if f["exporter"] == exporter]


def reader_file_check(f, tmp):
    """dexpi_reader.py on one file, checked against the file's own XML (corpus_adapters.dexpi_truth).
    -> (record, (model, out_dir) or None, xml root or None)."""
    import corpus_adapters as ca
    path = ca.DEXPI_ROOT / f["rel"]
    try:
        root = ca.load_xml(path)
        truth = ca.dexpi_truth(root)
    except (ET.ParseError, ValueError):
        root, truth = None, None
    rec = {"file": f["file"], "case_version": f["case_version"], "exporter": f["exporter"], "schema": f["schema"]}
    if truth:
        rec["truth"] = {k: truth[k] for k in ("equipment", "instrument_functions", "control_functions", "loops",
                                              "segments")}
    out = Path(tmp) / f"r{abs(hash(f['rel'])) % 10 ** 9}"
    try:
        model, refusal = ca.run_reader(path, out)
    except Exception as e:  # a crash is the finding
        rec.update(status="fail", problems=[f"crash: {type(e).__name__}: {str(e)[:160]}"])
        return rec, None, root
    if refusal:
        ok = ca.refusal_confirmed(refusal, truth)
        rec.update(status="pass" if ok else "fail", refused=refusal[:200],
                   problems=[] if ok else [f"refused, reason not seen in the XML: {refusal[:160]}"])
        return rec, None, root
    counts = ca.model_counts(model)
    ctrl = {c.get("dexpi_id") for c in model.get("controllers") or []}
    kept = ctrl | {i.get("dexpi_id") for i in model.get("instruments") or []}
    fe_src = " ".join(str(x.get("source", "")) for x in model.get("final_elements") or [])
    # Second reading (set after the primary results were seen): an item the reader lists in `unplaced` with a reason
    # (it reached no unit through the piping, e.g. on a line with both ends open) counts as present.
    unplaced = [u for u in model.get("unplaced") or [] if str(u.get("unplaced_reason") or "").strip()]
    unplaced_ids = {u.get("dexpi_id") for u in unplaced} - {None}
    unplaced_src = " ".join(str(u.get("source", "")) for u in unplaced)
    problems, second = [], []
    if truth is None:
        problems.append("read by the reader but not by ElementTree here (no truth)")
        second = list(problems)
    else:
        if counts["units"] != truth["equipment"]:
            problems.append(f"units: {counts['units']} for {truth['equipment']} top-level equipment")
            second.append(problems[-1])
        miss = [i for i in truth["control_function_ids"] if i not in ctrl]
        if miss:
            problems.append(f"controllers: {len(miss)} of {truth['control_functions']} control functions not read as "
                            "a controller")
        miss2 = [i for i in miss if i not in unplaced_ids and f"bubble {i}" not in unplaced_src]
        if miss2:
            second.append(f"controllers: {len(miss2)} of {truth['control_functions']} control functions neither a "
                          "controller nor unplaced with a reason")
        lost = [i for i in truth["instrument_function_ids"] if i not in kept and f"bubble {i}" not in fe_src]
        if lost:
            problems.append(f"instruments: {len(lost)} of {truth['instrument_functions']} instrument functions not in "
                            "the model")
        lost2 = [i for i in lost if i not in unplaced_ids and f"bubble {i}" not in unplaced_src]
        if lost2:
            second.append(f"instruments: {len(lost2)} of {truth['instrument_functions']} instrument functions neither "
                          "in the model nor unplaced with a reason")
        rec["unplaced_counted_in_second_reading"] = (len(miss) - len(miss2)) + (len(lost) - len(lost2))
    rec.update(status="fail" if problems else "pass", problems=problems, reader=counts,
               second_reading={"status": "fail" if second else "pass", "problems": second})
    return rec, (model, out), root


def problem_counts(recs):
    kinds = Counter()
    for r in recs:
        for p in r.get("problems", []):
            kinds[p.split(":", 1)[0].split(",", 1)[0]] += 1
    return dict(kinds)


def row7_reader(inp):
    files = dexpi_selection(inp)
    if not files:
        return needs_data(7, inp, [inp["local_path"]])
    with tempfile.TemporaryDirectory() as tmp:
        recs = [reader_file_check(f, tmp)[0] for f in files]
    bad = [r for r in recs if r["status"] != "pass"]
    cf = sum(r.get("truth", {}).get("control_functions", 0) for r in recs if "reader" in r)
    cf_ok = sum(r["truth"]["control_functions"] - int(next((p.split(" ")[1] for p in r["problems"]
                                                          if p.startswith("controllers:")), 0))
                for r in recs if "reader" in r and "truth" in r)
    refused = [r for r in recs if "refused" in r]
    per_case = defaultdict(lambda: [0, 0])
    for r in recs:
        per_case[r["case_version"]][0] += r["status"] == "pass"
        per_case[r["case_version"]][1] += 1
    second_ok = sum((r.get("second_reading") or {"status": r["status"]})["status"] == "pass" for r in recs)
    second_bad = [r for r in recs if (r.get("second_reading") or {"status": r["status"]})["status"] != "pass"]
    detail = {"files": recs, "by_problem": problem_counts(recs), "refused": len(refused),
              "control_functions": cf, "control_functions_read_as_controllers": cf_ok,
              "per_case": {k: f"{v[0]}/{v[1]}" for k, v in sorted(per_case.items())},
              "schemas": dict(Counter(r["schema"] for r in recs)),
              "second_reading": {"criterion": SECOND_READING_7, "set": "after the primary results had been seen",
                                 "files_pass": f"{second_ok}/{len(recs)}",
                                 "items_counted_as_unplaced": sum(r.get("unplaced_counted_in_second_reading", 0)
                                                                  for r in recs),
                                 "still_failing": [f"{r['file']}: {r['second_reading']['problems'][0]}"
                                                   if r.get("second_reading") else f"{r['file']}: {r['problems'][0]}"
                                                   for r in second_bad][:10]}}
    limits = [v for f, v in TRUTH_LIMITS_7.items() if any(r["file"] == f for r in recs)]
    if limits:
        detail["truth_definition_limits"] = limits
    refused_ok = [r for r in refused if r["status"] == "pass"]
    dup = sum("used more than once" in r["refused"] for r in refused_ok)
    counted = ""
    if refused_ok:
        why = ("duplicate element IDs" if dup == len(refused_ok) else
               f"{dup} for duplicate element IDs" if dup else "a reason seen in the XML")
        counted = f" ({len(refused_ok)} of them correct refusals: {why}, nothing written)"
    value = (f"{len(recs) - len(bad)}/{len(recs)} files pass{counted}; {cf_ok}/{cf} control functions read as "
             f"controllers; second reading {second_ok}/{len(recs)}" + (" (same refusals counted)" if counted else ""))
    reason = ""
    if bad:
        reason = (f"{len(bad)} of {len(recs)} files fail: " +
                  ", ".join(f"{k} on {n}" for k, n in sorted(detail["by_problem"].items(), key=lambda kv: -kv[1]))
                  + "; e.g. " + "; ".join(f"{r['file']}: {r['problems'][0]}" for r in bad[:3])
                  + f". Second reading (set after these results were seen; unplaced items with a reason count as "
                    f"present): {second_ok}/{len(recs)} files pass")
        if limits:
            reason += ". Truth-definition limit: " + " ".join(limits)
    c = cell(7, inp, "fail" if bad else "pass", value, reason, detail)
    if refused_ok:
        add_note(c, f"the pass counts (primary and second reading) include {len(refused_ok)} files the reader "
                    f"refused for a reason seen in the XML ({', '.join(r['file'] for r in refused_ok)}); the "
                    f"criterion counts a confirmed refusal as a pass, so these files show the refusal is right, "
                    f"not that their content was read")
    return c


SECOND_READING_7 = ("items with no unit to place them on count as present when the reader lists them in `unplaced` "
                    "with a reason (an item on a line with both ends open genuinely has no unit); checks (a) and (b) "
                    "unchanged")
# Where the truth (corpus_adapters.dexpi_truth) is known to be wrong for a file; stated, not silently changed.
TRUTH_LIMITS_7 = {
    "I05V01_AUD.EX01.xml": "AutoCAD I05V01_AUD.EX01: the truth reads a C anywhere after the first letter of the "
                           "category plus function letters as a control function, so the IEC category 'IEC-?' of a "
                           "control valve's function counts as one; the file's failing control-function check rests "
                           "on that, not on a controller the reader missed. The truth is left as it is.",
}


CROSS_KEYS = ("units", "instruments_and_controllers", "controllers", "streams")
CROSS_TRUTH = ("equipment", "instrument_functions", "control_functions", "segments")


def row7_cross_vendor(inp):
    import corpus_adapters as ca
    files = ca.dexpi_files("1.2")
    if not files:
        return needs_data(7, inp, [inp["local_path"]])
    groups = defaultdict(list)
    with tempfile.TemporaryDirectory() as tmp:
        for f in files:
            groups[f["case_version"]].append((f, reader_file_check(f, tmp)[0]))

    def rkey(rec):
        c = rec.get("reader")
        return None if c is None else (c["units"], c["instruments"] + c["controllers"], c["controllers"], c["streams"])

    def tkey(rec):
        t = rec.get("truth")
        return None if t is None else tuple(t[k] for k in CROSS_TRUTH)

    cases, compared, agree, tagree, unref = {}, 0, 0, 0, {}
    for cv, items in sorted(groups.items()):
        refs = [x for x in items if x[0]["exporter"] == "reference"]
        if not refs or len(items) < 2:
            profiles = {rkey(r) for _, r in items}
            unref[cv] = {"exports": len(items), "exporters": sorted({f["exporter"] for f, _ in items}),
                         "distinct_reader_profiles": len(profiles),
                         "why": "no reference export" if not refs else "no other export"}
            continue
        ref = next((x for x in refs if "VER" in x[0]["file"].upper()), refs[0])
        rows = []
        for x in items:
            if x is ref:
                continue
            f, r = x
            same, tsame = rkey(r) == rkey(ref[1]) and rkey(r) is not None, tkey(r) == tkey(ref[1])
            compared, agree, tagree = compared + 1, agree + same, tagree + tsame
            rows.append({"file": f["file"], "exporter": f["exporter"], "reader": rkey(r), "xml": tkey(r),
                         "reader_agrees": same, "xml_agrees": tsame, "refused": "refused" in r})
        cases[cv] = {"reference": ref[0]["file"], "reference_reader": rkey(ref[1]), "reference_xml": tkey(ref[1]),
                     "exports": rows}
    detail = {"reader_counts": list(CROSS_KEYS), "xml_counts": list(CROSS_TRUTH), "cases": cases,
              "without_reference": unref, "compared": compared, "reader_agrees": agree, "xml_agrees": tagree}
    value = (f"{agree}/{compared} exports match the reference's reader counts ({tagree}/{compared} match its XML "
             f"counts); {len(cases)} case versions with a reference")
    if not compared:
        return cell(7, inp, "n/a", "no case with a reference and another export", "n/a: nothing to compare", detail)
    reason = "" if agree == compared else (
        f"{compared - agree} of {compared} vendor exports give the reader different counts from the reference export "
        f"of the same case; in {compared - tagree} the XML itself already differs (equipment, instrument functions, "
        f"control functions or segments), so most of the disagreement is in the exports, not only in the reader")
    return cell(7, inp, "pass" if agree == compared else "fail", value, reason, detail)


def row4_reader(inp):
    import corpus_adapters as ca
    import loop_audit as la
    files = dexpi_selection(inp)
    if not files:
        return needs_data(4, inp, [inp["local_path"]])
    legs, excluded, refusals, incomplete = [], Counter(), [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for n, f in enumerate(files):
            rec, mm, root = reader_file_check(f, tmp)
            if mm is None:
                excluded["not read by the reader (refused or crashed; row 7)"] += 1
                continue
            model, out = mm
            if not model.get("controllers"):
                excluded["the reader found no controller (row 7)"] += 1
                continue
            loops, inc = ca.dexpi_loop_list(root)
            incomplete += len(inc)
            if not loops:
                excluded["no complete control loop in the XML's loop functions"] += 1
                continue
            path = Path(tmp) / f"loops_{n}.csv"
            ca.write_loops(path, loops)
            try:
                r = la.run(path, next(out.glob("*.model.json")))
            except Exception as e:
                refusals.append(f"{f['file']}: {type(e).__name__}: {str(e)[:160]}")
                continue
            legs += [dict(s, file=f["file"], measurement=l[1], output=l[2]) for s, l in zip(loop_rows_summary(r), loops)]
    detail = {"files": len(files), "excluded": dict(excluded), "incomplete_loops_in_xml": incomplete,
              "loop_list_refused": refusals, "loops": legs,
              "loop_list": "read from each file's InstrumentationLoopFunction elements (corpus_adapters.dexpi_loop_list)",
              "drawing": "the reader's model.json for the same file (tags only; no signal lines)"}
    if not legs and not refusals:
        return cell(4, inp, "n/a", "no loop audited", "n/a: no file has both a controller in the reader's model and a "
                    "complete control loop in the XML (" + "; ".join(f"{k}: {v} files" for k, v in excluded.items())
                    + ")", detail)
    ok = sum(l["status"] == "tags_present" for l in legs)
    bad = [f"{l['file']} {l['controller']}: {l['status']} (missing {', '.join(l['missing'])})" for l in legs
           if l["status"] != "tags_present"] + [f"loop list refused: {x}" for x in refusals]
    value = f"{ok}/{len(legs)} loops tags present; {sum(excluded.values())} of {len(files)} files not auditable"
    return cell(4, inp, "fail" if bad else "pass", value, "; ".join(bad[:6]) + (f" (+{len(bad) - 6} more)" if len(bad) > 6
                                                                              else ""), detail)


def generate_into(model, tmp, name):
    """generate.py on a model written into tmp. -> (CompletedProcess, files in --out, text of every output)."""
    model_dir, out = Path(tmp) / name, Path(tmp) / f"{name}-out"
    model_dir.mkdir()
    (model_dir / "model.json").write_text(json.dumps(model), encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "generate.py"), str(model_dir / "model.json"), "--out", str(out)],
                       capture_output=True, text=True, cwd=ROOT, timeout=300)
    files = sorted(x for x in out.rglob("*") if x.is_file()) if out.exists() else []
    text = "\n".join(x.read_text(encoding="utf-8", errors="ignore") for x in files)
    for s in (str(tmp), Path(tmp).as_posix()):
        p.stdout, p.stderr = p.stdout.replace(s, "<tmp>"), p.stderr.replace(s, "<tmp>")
    return p, [x.relative_to(out).as_posix() for x in files], text


def generate_checks(model, p, files):
    problems = []
    if p.returncode != 0:
        return [f"generate.py exit {p.returncode}: {p.stderr.strip()[-200:]}"]
    want = (f"model: {len(model['units'])} units, {len(model['streams'])} streams, 0 instruments, "
            f"0 final elements")
    first = (p.stdout.strip().splitlines() or [""])[0]
    if first != want:
        problems.append(f"generate.py says '{first}', the model has '{want[7:]}'")
    if "structural validation: OK" not in p.stdout:
        problems.append("no 'structural validation: OK'")
    svg = [f for f in files if f.startswith("svg/") and f.endswith(".svg")]
    if len(svg) != len(model["units"]) + 1:
        problems.append(f"{len(svg)} SVG files for {len(model['units'])} units (+1 overview expected)")
    return problems


def row5_idaes(inp):
    import corpus_adapters as ca
    model, summary = ca.idaes_model(ROOT / inp["local_path"])
    with tempfile.TemporaryDirectory() as tmp:
        p, files, text = generate_into(model, tmp, "idaes")
    problems = generate_checks(model, p, files)
    if p.returncode == 0:
        gone_u = [u["id"] for u in model["units"] if u["id"] not in text]
        gone_s = [s["id"] for s in model["streams"] if s["id"] not in text]
        if gone_u:
            problems.append(f"unit ids in no output file: {', '.join(gone_u)}")
        if gone_s:
            problems.append(f"{len(gone_s)} of {len(model['streams'])} stream ids in no output file "
                            f"({', '.join(gone_s[:4])})")
    worst = max(summary["mixer_balance"].values() or [0.0])
    if worst > IDAES_BALANCE_TOL:
        problems.append(f"adapter check: mixer balance off by {worst} (> {IDAES_BALANCE_TOL}); the stream table was "
                        "misread")
    detail = {"source": summary, "exit": p.returncode, "files_in_out": len(files),
              "stdout_first_line": (p.stdout.strip().splitlines() or [""])[0], "stderr": p.stderr.strip()[-300:],
              "not_tested": "instruments, controllers, valves and PI/Ignition tag content: the flowsheet has none"}
    return cell(5, inp, "fail" if problems else "pass",
                f"{summary['units']} units, {summary['streams']} streams" + ("" if problems else f", {len(files)} files"),
                "; ".join(problems), detail)


def row5_dwsim(inp):
    import corpus_adapters as ca
    zips = sorted((ROOT / inp["local_path"]).glob("fs_*.zip"), key=lambda z: int(z.stem[3:]))
    if not zips:
        return needs_data(5, inp, [inp["local_path"] + "/fs_*.zip"])
    per, ctrl_like = {}, 0
    with tempfile.TemporaryDirectory() as tmp:
        for z in zips:
            try:
                model, summary = ca.dwsim_model(z)
            except Exception as e:
                per[z.stem] = {"status": "fail", "problems": [f"adapter could not read it: {type(e).__name__}: "
                                                              f"{str(e)[:120]}"]}
                continue
            ctrl_like += summary["controller_like_blocks"]
            p, files, _ = generate_into(model, tmp, z.stem)
            problems = generate_checks(model, p, files)
            per[z.stem] = {"status": "fail" if problems else "pass", "problems": problems, "units": summary["units"],
                           "streams": summary["streams"], "joined_through_recycle": summary["joined_through_recycle"],
                           "generic_units": summary["opaque_or_generic_units"], "files": len(files)}
    bad = {k: v for k, v in per.items() if v["status"] != "pass"}
    detail = {"flowsheets": per, "controller_like_blocks": ctrl_like,
              "units_total": sum(v.get("units", 0) for v in per.values()),
              "streams_total": sum(v.get("streams", 0) for v in per.values()),
              "not_tested": "instruments, controllers and valves: DWSIM flowsheets are steady-state process models "
                            f"with no instrumentation; {ctrl_like} solver Adjust/Spec blocks in all {len(per)} "
                            "(solver targets, not plant controllers) are not mapped"}
    value = f"{len(per) - len(bad)}/{len(per)} flowsheets; {detail['units_total']} units, {detail['streams_total']} streams"
    reason = "; ".join(f"{k}: {v['problems'][0]}" for k, v in list(bad.items())[:5]) + (
        f" (+{len(bad) - 5} more)" if len(bad) > 5 else "")
    return cell(5, inp, "fail" if bad else "pass", value, reason, detail)


def band_runs(normal, runs):
    """csv_normal_bands on each (name, csv, fault_start_row, overlap). The PRONTO criterion: detected by 3 in a row at
    or after the start, and at most PRONTO_MAX_PRE of pre-fault rows flagged (detection only for an overlap run)."""
    import csv_normal_bands as cnb
    out = {}
    for name, path, fs, overlap in runs:
        try:
            r = cnb.run(normal, path, fault_start=str(fs))
        except (SystemExit, cnb.CsvFormatError, ValueError) as e:
            out[name] = {"pass": False, "error": str(e)[:200]}
            continue
        s = r["scored"]["fault"]
        pre = s["false_alarms_before_fault"]["flagged_samples"]
        det = s["detection_run3_row"] is not None
        ok = det and (overlap or pre <= PRONTO_MAX_PRE * fs)
        out[name] = {"method": r["method_name"], "k": r["k"],
                     "k_target_met": (r.get("k_selection") or {}).get("target_met"),
                     "fault_start_row": fs, "pre_fault_flagged": pre, "pre_fault_rows": fs,
                     "detected": det, "detection_run3_row": s["detection_run3_row"],
                     "detection_run3_delay": s["detection_run3_delay"],
                     "first_tags": [t["tag"] for t in s["first_tags"][:3]],
                     "pre_fault_tags": s["false_alarms_before_fault"]["tags"][:5],
                     "overlap_detection_only": bool(overlap), "pass": ok}
    return out


def band_cell(inp, runs, fit, extra=None, criterion_set=NEW_CRITERIA_SET, note=""):
    ok = [n for n, v in runs.items() if v["pass"]]
    errors = {n: v["error"] for n, v in runs.items() if "error" in v}
    det = sum(v.get("detected", False) for v in runs.values())
    clean = [v for v in runs.values() if "error" not in v and not v["overlap_detection_only"]]
    fa = sum(v["pre_fault_flagged"] > PRONTO_MAX_PRE * v["pre_fault_rows"] for v in clean)
    methods = sorted({v["method"] for v in runs.values() if "method" in v})
    detail = {"method": ", ".join(methods), "fit": fit,
              "criterion": f"PRONTO criterion: detected by 3 in a row at or after the labelled start, and at most "
                           f"{PRONTO_MAX_PRE:.1%} of pre-fault rows flagged; set {criterion_set}", "runs": runs,
              **(extra or {})}
    if "drift" in methods and inp["id"] not in HELDOUT_HISTORIAN:
        detail["development_data"] = DRIFT_DEVELOPMENT_NOTE
    value = f"{len(ok)}/{len(runs)} runs pass; detected {det}/{len(runs)}, too many pre-fault flags {fa}/{len(clean)}"
    missed = [n for n, v in runs.items() if v.get("k_target_met") is False]
    k_note = ""
    if missed:
        import csv_normal_bands as cnb
        ks = sorted({runs[n]["k"] for n in missed})
        largest = {"drift": max(cnb.DRIFT_KS), "cyclic": max(cnb.DRIFT_KS), "level": max(cnb.KS)}
        top = all(runs[n]["k"] == largest.get(runs[n].get("method")) for n in missed)
        value += f"; K target not met {len(missed)}/{len(runs)}"
        k_note = (f"`k_target_met` is false on {len(missed)} of {len(runs)} runs ({', '.join(missed)}): K="
                  f"{', '.join(map(str, ks))}{' (the largest K the tool tries)' if top else ''} did not bring "
                  f"held-out normal flags under the tool's {cnb.TARGET:.1%} target, so the bands ran with a K that "
                  f"misses the tool's own selection rule; the verdict uses the row's criterion, which does not "
                  f"include that target")
    if len(ok) == len(runs):
        c = cell(6, inp, "pass", value, "", detail)
        if k_note:
            add_note(c, k_note)
        return c
    worst = sorted((v for v in runs.values() if "error" not in v), key=lambda v: -v["pre_fault_flagged"])[:1]
    reason = (f"{', '.join(methods)} method: {len(runs) - len(ok)} of {len(runs)} runs fail: {len(runs) - det} not "
              f"detected, {fa} with more than {PRONTO_MAX_PRE:.1%} of pre-fault rows flagged"
              + (f", {len(errors)} errors" if errors else ""))
    if worst and worst[0]["pre_fault_flagged"]:
        w = worst[0]
        reason += (f"; worst pre-fault: {w['pre_fault_flagged']}/{w['pre_fault_rows']} rows flagged (tags "
                   f"{', '.join(w['pre_fault_tags'][:3]) or 'none'})")
    c = cell(6, inp, "fail", value, reason + note, detail)
    if k_note:
        add_note(c, k_note)
    return c


def row6_pronto_day(inp):
    import corpus_adapters as ca
    day = inp["id"][-1]
    with tempfile.TemporaryDirectory() as tmp:
        info = ca.pronto_day(day, tmp)
        runs = [(n, Path(tmp) / v["file"], v["fault_start_row"], v["overlap"]) for n, v in info.items()
                if n not in ("normal", "_alignment")]
        res = band_runs(Path(tmp) / info["normal"]["file"], runs)
    for n, v in res.items():
        v["what"] = info[n]["what"]
    return band_cell(inp, res, f"day {day} normal block ({info['normal']['rows']} rows: {info['normal']['what']})",
                     {"alignment": info["_alignment"]})


def row6_skab(inp):
    import corpus_adapters as ca
    base = ROOT / inp["local_path"]
    runs = ca.skab_runs(base)
    with tempfile.TemporaryDirectory() as tmp:  # SKAB is GPL-3.0: converted copies live only in this temp folder
        tmp = Path(tmp)
        ca.skab_to_csv(base / "anomaly-free" / "anomaly-free.csv", tmp / "normal.csv")
        todo, self_fit = [], {}
        for group, name, path in runs:
            dest = tmp / f"{group}_{name}.csv"
            i = ca.skab_to_csv(path, dest)
            if i["fault_start_row"] is None:
                continue
            todo.append((f"{group}/{name}", dest, i["fault_start_row"], False))
            cp = i["first_changepoint_row"] or i["fault_start_row"]
            if cp >= 60:  # the run's own normal start, for the drift-separating variant (reported, not scored)
                ca.head_csv(dest, tmp / f"{group}_{name}_head.csv", cp)
                self_fit[f"{group}/{name}"] = (tmp / f"{group}_{name}_head.csv", dest, i["fault_start_row"])
        res = band_runs(tmp / "normal.csv", todo)
        variant = band_runs_variant(self_fit)
    groups = defaultdict(lambda: [0, 0])
    for n, v in res.items():
        groups[n.split("/")[0]][0] += v["pass"]
        groups[n.split("/")[0]][1] += 1
    vp = sum(v["pass"] for v in variant.values())
    return band_cell(inp, res, "anomaly-free.csv (a normal run recorded on a different day, 2020-02-08)",
                     {"by_group": {g: f"{a}/{b}" for g, (a, b) in groups.items()},
                      "variant_fit_on_each_runs_own_start": {
                          "what": "bands fitted on the rows before each run's first changepoint (reported, not the "
                                  "criterion): separates detecting the fault from flagging day-to-day drift",
                          "pass": f"{vp}/{len(variant)}", "runs": variant}})


def band_runs_variant(pairs):
    out = {}
    for name, (normal, score, fs) in pairs.items():
        out.update({name: v for v in band_runs(normal, [(name, score, fs, False)]).values()})
    return out


def row6_hai(inp):
    import corpus_adapters as ca
    import csv_normal_bands as cnb
    base = ROOT / inp["local_path"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ca.hai_to_csv(base / "train1.csv.gz", tmp / "train1.csv")
        files, events = [], {}
        for name in ("test1", "test4"):
            i = ca.hai_to_csv(base / f"{name}.csv.gz", tmp / f"{name}.csv")
            events[name] = i["events"]
            files.append((name, tmp / f"{name}.csv", i["events"][0][0], False))
        res = band_runs(tmp / "train1.csv", files)
        tags = []
        for name, path, fs, _ in files:
            if "k" not in res[name]:
                continue
            # The attack events are scored with the method the cell scored, at the K the tool chose for it.
            flags, tags = tool_flags(tmp / "train1.csv", path, res[name]["k"], res[name]["method"])
            ev = []
            for a, b in events[name]:
                hit = cnb.first_run(flags, a)
                ev.append({"rows": [a, b], "detected_in_event": hit is not None and hit <= b,
                           "delay_rows": None if hit is None or hit > b else hit - a})
            res[name]["attack_events"] = ev
            res[name]["attack_events_method"] = res[name]["method"]
            res[name]["events_detected"] = f"{sum(e['detected_in_event'] for e in ev)}/{len(ev)}"
            # Co-check: the event flags reproduce the tool's own detection (same first 3-in-a-row from the start).
            res[name]["event_flags_match_tool"] = cnb.first_run(flags, fs) == res[name]["detection_run3_row"]
    return band_cell(inp, res, "train1 (60 h of normal running at 1 s; first half fits, second half picks K)",
                     {"tags": len(tags)})


HELDOUT_FIT = {
    "uci-hydraulic": "per run, the first 100 load cycles of its section, all at the section's opening grades",
    "metropt3": "2020-02-01 to 2020-02-08 (a normal week, before any reported failure)",
    "battledim": "2018-01-01 00:00 up to the first leak start (2018-01-08 13:30)",
    "battledim-2019": "2019-01-01 00:00 up to the first leak starting in 2019 (2019-01-15 23:00); the four "
                      "leaks carried over from 2018 are part of normal",
}


def row6_heldout(inp):
    """Historian adapter sources, with the same criterion as every real row-6 source. The original three are now
    development data for auto/cyclic; BattLeDIM 2019 alone is held out for that method (A178, A183, A184)."""
    import historian_adapters as ha
    make = {"uci-hydraulic": ha.uci_hydraulic_runs, "metropt3": ha.metropt3_runs,
            "battledim": ha.battledim_runs, "battledim-2019": ha.battledim_2019_runs}[inp["id"]]
    res = {}
    with tempfile.TemporaryDirectory() as tmp:  # converted CSVs live only here
        for r in make(tmp):
            one = band_runs(r["normal"], [(r["name"], r["score"], r["fault_start_row"], False)])
            one[r["name"]]["what"] = r["what"]
            res.update(one)
    cyc = inp.get("cyclic", "")
    heldout = inp["id"] == "battledim-2019"
    evidence_note = CYCLIC_HELDOUT_NOTE if heldout else CYCLIC_DEVELOPMENT_NOTE
    split = "A178" if heldout else "A165"
    extra = {"held_out" if heldout else "development_data": evidence_note,
             "cyclic_process": cyc, "adapter": "scripts/historian_adapters.py"}
    if not heldout:
        extra["earlier_drift_split"] = HELDOUT_NOTE
    return band_cell(inp, res, HELDOUT_FIT[inp["id"]], extra,
                     criterion_set=f"before any run on this source (data/attempts.json {split}: the same criterion "
                                   "as the other real sources, label mapping fixed with it)",
                     note=f". {evidence_note}; a cyclic process ({cyc})")


RUNNERS = {1: row1, 2: row2, 3: row3, 4: row4, 5: row5, 6: row6, 7: row7, 8: row8}


class StagingError(Exception):
    """A source image does not match the image its agent-made key was drawn on."""


def stage_agent_sheets(inp, dest):
    """Write <sheet>.png (at the key's pixel size) and <sheet>.graphml for an agent-keyed input into dest, from the
    gitignored source images (corpus.json `stage`). Each source is checked against the SHA-256 in the key's
    key_meta.json; the staged size must equal the key's size_px. Returns {sheet: staging note}."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    meta = json.loads((ROOT / inp["local_path"] / "key_meta.json").read_text(encoding="utf-8"))["sheets"]
    notes = {}
    for s in inp["sheets"]:
        spec, m = inp["stage"][s], meta[s]
        src = ROOT / spec["source"]
        png = Path(dest) / f"{s}.png"
        note = spec["how"]
        if spec["how"] == "pdf_image":
            import fitz  # PyMuPDF
            with fitz.open(src) as doc:
                img = doc.extract_image(spec["xref"])
            data = img["image"]
            if hashlib.sha256(data).hexdigest() != m["image_sha256"]:
                raise StagingError(f"{s}: PDF image xref {spec['xref']} is not the image the key was drawn on (sha256)")
            if img["ext"] != "png":
                raise StagingError(f"{s}: PDF image xref {spec['xref']} is {img['ext']}, expected png")
            png.write_bytes(data)
            note = f"PDF image xref {spec['xref']}, bytes unchanged"
        else:
            if hashlib.sha256(src.read_bytes()).hexdigest() != m["image_sha256"]:
                raise StagingError(f"{s}: {spec['source']} is not the image the key was drawn on (sha256)")
            if spec["how"] == "svg":
                import fitz  # PyMuPDF
                with fitz.open(src) as doc:
                    pix = doc[0].get_pixmap()
                    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                w, h = m["size_px"]
                note = f"SVG rasterised by PyMuPDF at zoom 1 ({im.width} x {im.height})"
                if (im.width, im.height) != (w, h) and 0 <= im.width - w <= 1 and 0 <= im.height - h <= 1:
                    im = im.crop((0, 0, w, h))  # SVG user units are pixels; the extra row/column is rounding
                    note += f", cropped to the key's {w} x {h} (the last row/column is rounding of the SVG size)"
            else:
                im = Image.open(src).convert("RGB")
                if spec["how"] == "crop":
                    im = im.crop(tuple(spec["crop"]))
                    note = f"crop box {tuple(spec['crop'])} of the scan"
                else:
                    note = "image as is, saved as PNG"
            im.save(png)
        import score_pid2graph as sc
        if list(sc.png_size(png)) != list(m["size_px"]):
            raise StagingError(f"{s}: staged image is {sc.png_size(png)}, the key is in {m['size_px']} pixels")
        shutil.copyfile(ROOT / inp["local_path"] / f"{s}.graphml", Path(dest) / f"{s}.graphml")
        notes[s] = note
    return notes


def run_agent_keyed(row, inp):
    """A row-1/2/3/8 cell on an agent-keyed input: stage the images, run the row's own runner on the staged folder,
    label the cell. Row 4: n/a with the input's reason."""
    if row == 4:
        return cell(4, inp, "n/a", "", f"n/a: {inp['row4_na']}")
    try:
        import PIL  # noqa: F401
        import fitz  # noqa: F401
    except ImportError as e:
        return cell(row, inp, "needs deps", reason=f"needs deps: Pillow and PyMuPDF to stage the images ({e.name})")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            notes = stage_agent_sheets(inp, tmp)
        except StagingError as e:
            return cell(row, inp, "needs data", reason=f"needs data: {e}; re-fetch with {inp['fetch']}")
        staged = dict(inp, local_path=str(Path(tmp).resolve()))
        c = RUNNERS[row](staged)
    c["key"] = "agent-made"
    c["detail"]["key"] = {"made_by": AGENT_KEY_LABEL, "keys": inp["local_path"], "staging": notes,
                          "attempt": "A172", **({"not_independent": inp["not_independent"]}
                                                if inp.get("not_independent") else {}),
                          **({"scope": inp["scope"]} if inp.get("scope") else {})}
    for k in ("sheet", "drawing"):  # never publish the temp path
        if isinstance(c["detail"].get(k), str):
            c["detail"][k] = c["detail"][k].replace(str(Path(tmp).resolve()), "<staged>")
    return c


_VENDOR_BUILD = {}


def vendor_build():
    """Build the DEXPI 1.2 vendor-render keys once per process (corpus_adapters.build_vendor_keys, adapter A2) and
    return {"records": n, "mapped": n, "by_reason": {...}, "by_exporter": {...}}. Needs the fetched TrainingTestCases."""
    if "summary" not in _VENDOR_BUILD:
        import corpus_adapters as ca
        recs = ca.build_vendor_keys()
        def kind(r):
            why = r.get("reason") or ""
            if "nothing to link" in why:
                return "too few scored symbols in the XML"
            if "convert_xml refused" in why:
                return "refused by adapt_dexpi.convert_xml"
            if "map fails its check" in why or "too little drawn geometry" in why:
                return "map fails its check"
            return why.split(":", 1)[0] or "other"
        by_exp = defaultdict(lambda: [0, 0])
        for r in recs:
            by_exp[r["exporter"]][0] += r["status"] == "mapped"
            by_exp[r["exporter"]][1] += 1
        _VENDOR_BUILD["summary"] = {
            "renders": len(recs), "mapped": sum(r["status"] == "mapped" for r in recs),
            "not_mapped_by_reason": dict(Counter(kind(r) for r in recs if r["status"] != "mapped")),
            "mapped_by_exporter": {k: f"{a}/{b}" for k, (a, b) in sorted(by_exp.items())}}
    return _VENDOR_BUILD["summary"]


def vendor_split(c, base, part):
    """Pool a vendor-render cell's per-sheet counts by exporter (the sidecar's `exporter`)."""
    import line_layers as ll
    pools = defaultdict(lambda: [0, 0, 0, 0])
    for s, v in c["detail"].get("sheets", {}).items():
        e = ll.sidecar(base, s).get("exporter", "?")
        p = pools[e]
        p[0] += 1
        p[1] += v.get("tp", 0)
        p[2] += v.get("predicted", 0)
        p[3] += v.get("truth", 0)
    return {e: {"sheets": n, part + "_f1": round(2 * tp / (pr + tr), 3) if pr + tr else None, "tp": tp,
                "predicted": pr, "truth": tr} for e, (n, tp, pr, tr) in sorted(pools.items())}


def run_cell(row, inp):
    agent_na = inp["kind"] == AGENT_KIND and row == 4  # n/a by registration: needs neither key nor image
    built = None
    if inp["id"] == VENDOR and (ROOT / "data/external/dexpi-ttc-all/extracted").is_dir():
        try:
            built = vendor_build()
        except Exception as e:  # a build crash is reported in the cell, not a crashed matrix
            built = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    missing = [] if agent_na else missing_files(inp)
    if missing:
        return needs_data(row, inp, missing)
    t0 = time.time()
    ran_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    hashes = {f: file_hash(f) for f in tool_files(row, inp["id"])}  # before the run: what this run exercised
    if inp["kind"] == AGENT_KIND and row != 4:  # an edited agent-made key stales its cells too
        hashes.update({f"{inp['local_path']}/{s}.graphml": file_hash(f"{inp['local_path']}/{s}.graphml")
                       for s in inp["sheets"]})
    try:
        if inp["kind"] in NOT_SCORED_KINDS:
            c = not_scored(row, inp)
        elif inp["kind"] == AGENT_KIND:
            c = run_agent_keyed(row, inp)
        else:
            c = RUNNERS[row](inp)
    except Exception as e:  # an unexpected crash in a tool is a red cell, not a crashed matrix
        c = cell(row, inp, "fail", "crash", f"{type(e).__name__}: {str(e)[:300]}")
        if inp["kind"] == AGENT_KIND and row != 4:
            c["key"] = "agent-made"
    if inp["id"] == VENDOR:
        c["detail"]["build"] = built
        c["detail"]["held_out"] = VENDOR_HELD_OUT
        if c["status"] in ("pass", "fail"):
            c["detail"]["by_exporter"] = vendor_split(c, ROOT / inp["local_path"], "pipe" if row == 8 else "network")
            if built and "not_mapped_by_reason" in built:
                c["reason"] = (c["reason"] + ("; " if c["reason"] else "") +
                               f"{built['mapped']} of {built['renders']} renders mapped cleanly (by exporter "
                               f"{built['mapped_by_exporter']}); not mapped: " +
                               ", ".join(f"{n} {k}" for k, n in built["not_mapped_by_reason"].items()) +
                               "; by exporter: " + ", ".join(
                                   f"{e} {v['sheets']} sheets F1 {v[('pipe' if row == 8 else 'network') + '_f1']}"
                                   for e, v in c["detail"]["by_exporter"].items()) +
                               ("; A177/A196 split: SPPID development, Comos/AVEVA held out; pooled result mixes "
                                "splits and includes the A192 scorer fix" if row == 8 else
                                "; initial held-out tracer baseline A174; auto clean-up leaves these renders "
                                "unchanged (A189)"))
    if (row, inp["id"]) in KEY_ONLY_SCAN_CELLS and c["status"] in ("pass", "fail"):
        c["key_only_duplicate_of"] = KEY_ONLY_SCAN_CELLS[(row, inp["id"])]
        add_note(c, KEY_ONLY_SCAN_NOTE)
    if row == 8 and inp["id"] == "open100-holdout":
        c["detail"]["blindness"] = OPEN100_HOLDOUT_PIPE_NOTE
        if c["reason"]:
            c["reason"] += "; " + OPEN100_HOLDOUT_PIPE_NOTE
    c["seconds"] = round(time.time() - t0, 1)
    c["ran_at"] = ran_at
    c["tool_files"] = hashes
    return c


# ------------------------------------------------------------------ gaps and rendering

def gaps(matrix, corpus):
    cells = matrix["cells"]
    failed = [c for c in cells if c["status"] == "fail"]
    waiting = [c for c in cells if c["status"] in ("needs data", "needs deps")]
    single = []
    for row in sorted({c["row"] for c in cells}):
        ran = [c for c in cells if c["row"] == row and c["status"] in ("pass", "fail")]
        fams = sorted({c["family"] for c in ran if not self_generated(c) and not agent_keyed(c)})
        own = sorted({c["family"] for c in ran if self_generated(c)})
        agent = sorted({c["family"] for c in ran if agent_keyed(c)} - set(fams))
        if len(fams) <= 1:
            single.append({"row": row, "tool": ROWS[row]["tool"], "families": fams, "self_generated": own,
                           "agent_keyed": agent})
    return {"failed": failed, "waiting": waiting, "single_source": single}


def esc(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def cell_text(c):
    if c is None:
        return ""
    if c["status"] in ("pass", "fail"):
        text = f"{c['status'].upper() if c['status'] == 'fail' else 'pass'} {c['value']}".strip()
        if agent_keyed(c):
            text = f"{text} {AGENT_KEY_MARK}"
        return f"{text} {SELF_GENERATED_MARK}" if self_generated(c) else text
    return c["status"]


def run_times(matrix):
    """'row 1: <time>; row 6: <from> to <to>; ...' from the cells' own ran_at (cells without one say so)."""
    parts = []
    for r in sorted({c["row"] for c in matrix["cells"]}):
        times = sorted({c.get("ran_at") for c in matrix["cells"] if c["row"] == r} - {None})
        legacy = any(not c.get("ran_at") for c in matrix["cells"] if c["row"] == r)
        when = (times[0] if len(times) == 1 else f"{times[0]} to {times[-1]}") if times else ""
        if legacy:
            when = (when + ", some cells " if when else "") + "no run time recorded"
        parts.append(f"row {r}: {when}")
    return "; ".join(parts)


def render(matrix, corpus):
    inputs = inputs_by_id(corpus)
    by = {(c["row"], c["input"]): c for c in matrix["cells"]}
    rows = sorted(ROWS)
    order = []
    for r in rows:
        for i in ROW_INPUTS[r]:
            if i not in order:
                order.append(i)
    counts = {s: sum(c["status"] == s for c in matrix["cells"]) for s in STATUSES}
    L = ["# Where the selected workflows generalize: the corpus matrix", "",
         "Generated by `scripts/corpus_matrix.py` from `out/generalization/matrix.json`; the inputs are registered in",
         "`data/corpus.json`. Do not edit by hand: `python scripts/corpus_matrix.py` re-runs it and",
         "`python scripts/corpus_matrix.py --check` confirms this page matches the JSON.", "",
         "These eight workflows cover tracing, scorer controls, intake/report, loop audit, exports, historian bands, "
         "DEXPI conversion and pipe topology. They do not cover every tool: point mapping, applying reviews, the "
         "question engine, impact estimates and live replay have their own feature tests and examples. Each cell "
         "runs one selected workflow on one registered public input it applies "
         "to, with no model and no network. **pass** and **FAIL** use the criterion stated for each row below; each "
         "was fixed before that row's first run unless the row says otherwise. **n/a** means the tool can't apply to "
         "that input (the reason is given); **needs data** names the "
         "fetch command for an input that isn't cached (a clean clone has the committed inputs only); **needs deps** "
         "means a module from `requirements.txt` is missing. A FAIL is a finding, not an error in the matrix. "
         f"**{SELF_GENERATED_MARK}** marks an input this repository generated from its own process model (the TE and "
         "Bayer sheets): a pass there is circular evidence, showing the tool agrees with the generator, not that it "
         "carries over to someone else's drawing. "
         f"**{AGENT_KEY_MARK}** marks a cell scored against an answer key a coding agent made (data/agent_keys/, a "
         "first pass no person has reviewed): weaker evidence than a hand key, kept apart from the human-keyed results "
         "and never counted as an independent source family.", "",
         "Rows are not always run together, so each cell records its own run time and a hash of the tool files it "
         "exercised; `--check` fails when a tool has changed since its cells ran. Cells ran at: "
         f"{run_times(matrix)}. Last written {matrix['ran_at']}; the cells' run times add up to "
         f"{round(sum(c.get('seconds', 0) for c in matrix['cells']), 1)} s. Cells: " +
         ", ".join(f"{counts[s]} {s}" for s in STATUSES) + "." + key_only_count_text(matrix), "",
         "## The matrix", "",
         "| Input | " + " | ".join(f"{r}. {ROWS[r]['short']}" for r in rows) + " |",
         "|---|" + "---|" * len(rows)]
    for i in order:
        name = inputs[i]["id"] if i in inputs else i
        L.append(f"| `{name}` | " + " | ".join(esc(cell_text(by.get((r, i)))) if i in ROW_INPUTS[r] else "" for r in rows) + " |")
    L += ["", "Blank: the row does not apply to that input by design. Input details (source, license, path, fetch "
          "command) are in the last section.", ""]
    L += ["## By row", ""]
    for r in rows:
        meta = ROWS[r]
        L += [f"### {r}. {meta['short']}: `{meta['tool']}`", "", meta["question"], ""]
        L += [ROW_CRITERIA[r], ""]
        L += ["| Input | Result | Key number | Why / detail |", "|---|---|---|---|"]
        for i in ROW_INPUTS[r]:
            c = by.get((r, i))
            if c is None:
                L.append(f"| `{i}` | not run | | |")
                continue
            why = c["reason"] or detail_line(c)
            if c.get("note"):
                why = f"{why}; **note:** {c['note']}" if why else f"**note:** {c['note']}"
            if self_generated(c):
                why = f"{SELF_GENERATED_MARK} {why}".strip()
            if agent_keyed(c):
                k = c["detail"].get("key") or {}
                why = (f"**scored against an {AGENT_KEY_LABEL}** {why}".strip()
                       + "".join(f"; {s}: {v}" for s, v in (k.get("not_independent") or {}).items())
                       + (f"; scope: {k['scope']}" if k.get("scope") else ""))
            L.append(f"| `{i}` | {c['status']} | {esc(c['value'])} | {esc(why)} |")
        pubs = [(c, p) for i in ROW_INPUTS[r] for c in [by.get((r, i))] if c for p in c["published"]]
        if pubs:
            L += ["", "Against the numbers the repository publishes:", "",
                  "| Input | Published (file:line) | Says | This run | Same? |", "|---|---|---|---|---|"]
            for c, p in pubs:
                L.append(f"| `{c['input']}` | [{p['file']}:{p['line']}](../{p['file']}) | {esc(p['says'])} | "
                         f"{esc(p['ours'])} | {'yes' if p['agrees'] else '**no**'} |")
        extra = ROW_EXTRA.get(r)
        if extra:
            L += [""] + extra(by, r)
        L.append("")
    g = gaps(matrix, corpus)
    L += ["## Gaps", "", "### Cells that failed", ""]
    L += [f"- **{ROWS[c['row']]['short']} x `{c['input']}`**: "
          + (f"{AGENT_KEY_MARK} " if agent_keyed(c) else "") + esc(c['reason'])
          + (f"; note: {esc(c['note'])}" if c.get("note") else "") for c in g["failed"]] or ["- none"]
    L += ["", "### Cells waiting for data or dependencies", ""]
    L += [f"- {ROWS[c['row']]['short']} x `{c['input']}`: {esc(c['reason'])}" for c in g["waiting"]] or ["- none"]
    L += ["", "### Tools exercised on only one source family", "",
          "A tool that has only ever run on one family of inputs has not been shown to generalize, whatever its "
          "pass rate there. Self-generated families (made by this repository from its own model) and families scored "
          "only against an agent-made key do not count as a second source.", ""]
    L += [f"- {s['row']}. `{s['tool']}`: only {', '.join(s['families']) or 'no independent family'}"
          + (f" (plus self-generated: {', '.join(s['self_generated'])})" if s.get("self_generated") else "")
          + (f" (plus agent-keyed: {', '.join(s['agent_keyed'])})" if s.get("agent_keyed") else "")
          for s in g["single_source"]] or ["- none"]
    disagree = [(c, p) for c in matrix["cells"] for p in c["published"] if not p["agrees"]]
    L += ["", "### Numbers that disagree with what the repository publishes", ""]
    L += [f"- {ROWS[c['row']]['short']} x `{c['input']}`: {p['file']}:{p['line']} says {esc(p['says'])}; this run "
          f"gives {esc(p['ours'])}" for c, p in disagree] or ["- none"]
    L += ["", "## Inputs", "", "| Id | What | License | Local path | In a clean clone? | Fetch |", "|---|---|---|---|---|---|"]
    for x in corpus["inputs"]:
        L.append(f"| `{x['id']}` | [{esc(x['name'])}]({x['source_url']}) | {esc(x['license'])} | `{x['local_path']}` | "
                 f"{'yes' if x['committed'] else 'no'} | {('`' + esc(x['fetch']) + '`') if x.get('fetch') else ''} |")
    L += ["", "## Public sources not yet added", "",
          "From a license check done 2026-10-29; license words as found, not legal advice.", "",
          "| Source | License | What | Would exercise |", "|---|---|---|---|"]
    for x in corpus["candidates"]:
        L.append(f"| [{esc(x['name'])}]({x['url']}) | {esc(x['license'])} | {esc(x['what'])} | {esc(x['would_exercise'])} |")
    L += ["", "Excluded:", ""] + [f"- {x['name']}: {x['reason']}" for x in corpus["excluded"]]
    L += [""] + [f"{n}" for n in corpus.get("notes", [])] + [""]
    return "\n".join(L)


def key_only_count_text(matrix):
    dups = [c for c in matrix["cells"] if c.get("key_only_duplicate_of") and c["status"] == "pass"]
    if not dups:
        return ""
    rows = sorted({c["row"] for c in dups})
    return (f" {len(dups)} of the passes (rows {', '.join(map(str, rows))} on the `open100-scan-L*` inputs) repeat "
            f"`open100-holdout` on key-only inputs and add no scan evidence.")


def detail_line(c):
    d = c["detail"]
    if c["row"] == 1 and "sheets" in d:
        return (f"P {d['precision']} / R {d['recall']}, review load {d['review_load_per_100']}, {len(d['sheets'])} "
                f"sheets, worst {d['worst_sheet']} ({d['sheets'][d['worst_sheet']]['connection_f1']})" +
                (f"; scan clean-up (auto), {sum(bool(s.get('scan_cleaned')) for s in d['sheets'].values())} "
                 f"of {len(d['sheets'])} sheets cleaned" if d.get("scan_cleanup") == "auto" else ""))
    if c["row"] == 2 and "wrong_answer_symbol_f1_overall" in d:
        w = d["wrong_answer_symbol_f1_overall"]
        return (f"{d['sheets']} sheets; overall wrong class {w['wrong_class']}, moved {w['shifted']}; perfect review load "
                f"{d['review_load_per_100']['perfect']}")
    if c["row"] == 3 and "bundle_items" in d:
        if "key_symbols" in d:
            return (f"sheet {d['sheet']}: key {d['key_symbols']} symbols / {d['key_links']} links; bundle "
                    f"{d['equipment']} equipment, {d['instruments']} instruments, {d['line_items']} line items, "
                    f"{d['offpage_connectors']} off-page; report written")
    if c["row"] == 4 and "headline" in d:
        return d["headline"]
    if c["row"] == 4 and "legs" in d:
        split = sorted({l["controller"] for l in d["legs"]
                        if sum(x["controller"] == l["controller"] for x in d["legs"]) > 1})
        n = len(d["legs"])
        return (f"{n} leg{'s' if n != 1 else ''} from {len(d.get('headlines', []))} loop list(s) exported from the "
                f"Bayer model" + (f"; split-range {', '.join(split)} audited one leg per list" if split else "")
                + "; " + " / ".join(d.get("headlines", [])))
    if c["row"] == 4 and "distinct_tags_checked" in d:
        return (f"{len(d['loops'])} loops, {d['combined_instruments']} combined instruments, "
                f"{d['distinct_tags_checked']} distinct tags checked ({', '.join(d['tags_checked'])}); not checked: "
                f"{d['not_checked']}")
    if c["row"] == 5 and "stdout_first_line" in d:
        return d["stdout_first_line"]
    if c["row"] == 8 and "segment_f1" in d:
        j = d["junctions"]
        return (f"{d['scope']} lines; P {d['precision']} / R {d['recall']}; item-to-item F1 {d['item_to_item_f1']}; "
                f"junctions found {j['tp']} of {j['truth']} ({j['predicted']} predicted); worst {d['worst_sheet']} "
                f"({d['sheets'][d['worst_sheet']]['segment_f1']})" + (f"; {d['blindness']}" if d.get("blindness") else ""))
    if c["row"] == 4 and "excluded" in d:
        return (f"{d['files']} files; not auditable: " + (", ".join(f"{v} {k}" for k, v in d["excluded"].items()) or
                                                          "none") + f"; {d['incomplete_loops_in_xml']} incomplete loops "
                "in the XML")
    if c["row"] == 5 and "flowsheets" in d:
        return d["not_tested"]
    if c["row"] == 5 and "not_tested" in d:
        return f"{d['stdout_first_line']}; not tested: {d['not_tested']}"
    if c["row"] == 6 and "runs" in d and "criterion" in d and "PRONTO criterion" in d["criterion"]:
        extra = ""
        if "by_group" in d:
            v = d["variant_fit_on_each_runs_own_start"]
            extra = f"; by group {d['by_group']}; fitted on each run's own start instead: {v['pass']} pass"
        if any("events_detected" in v for v in d["runs"].values()):
            extra = "; attack events detected " + ", ".join(f"{n} {v.get('events_detected')}" for n, v in d["runs"].items())
        if d.get("held_out"):
            extra += f"; held out (A165/A171), scored once; cyclic process ({d.get('cyclic_process')})"
        elif d.get("development_data"):
            extra += "; development data for the drift method (not a held-out pass)"
        return f"{d.get('method', '')} method; fit: {d['fit']}{extra}"
    if c["row"] == 6 and "runs" in d:
        return f"{d.get('method', '')} method; fit: {d.get('fit')}" + (
            "; development data for the drift method (not a held-out pass)" if d.get("development_data") else "")
    if c["row"] == 7 and "by_problem" in d:
        return (f"refused (confirmed) {d['refused']}; per case {d['per_case']}" +
                (f"; second reading (set after results): {d['second_reading']['files_pass']} files pass"
                 if "second_reading" in d else ""))
    if c["row"] == 7 and "sheets" in d:
        return "; ".join(f"{s}: {v['symbols']} symbols, {v['connections']} links, {v['corrections']} corrections"
                         for s, v in d["sheets"].items())
    return ""


VENDOR_TEXT = ("`dexpi-1.2-vendor-renders` (added 2026-10-29): each DEXPI 1.2 vendor export with the exporting tool's "
               "own render beside it is keyed from its own XML by adapter A2 (`corpus_adapters.build_vendor_keys`, "
               "run by the matrix before the cell: a per-axis scale-and-offset map from drawing coordinates onto the "
               "render's ink, kept only when it passes its own check); only the renders that map cleanly are scored, "
               "and the cell's detail counts the others by reason. The original baseline was held out: mapping and "
               "scoring plan fixed before any scored run (A173), scored once (A174). For the later pipe rules "
               "A191-A195, A177 made the 14 SPPID renders development data; the 7 Comos and 1 AVEVA renders stayed "
               "held out, seen once before as a baseline (A196). The pooled vendor score mixes development and "
               "held-out data and includes the A192 scorer fix (SPPID 0.679 to 0.852 with tracing unchanged, about "
               "two thirds of its development gain to 0.939). Same pass bar as the row; detail splits by exporter. "
               "The row-1 auto scan clean-up leaves these renders unchanged (A189).")


AGENT_KEYED_TEXT = ("`omre-1958-pid` (bottom-right quadrant), `commons-pid-sheets` (5 sheets) and `pronto-fig1` are "
                    "scored against agent-made first-pass keys (data/agent_keys/, attempt A172; no person has "
                    "reviewed them), with this row's criterion unchanged, fixed before these cells first ran. Every "
                    "such cell is marked (agent-made key); it is weaker evidence than a hand key and is not pooled "
                    "with the human-keyed results. The images are fetched, checked against the SHA-256 the key "
                    "records and staged as PNG at the key's pixel size (the OMRE scan cropped to its keyed "
                    "quadrant, the SVG rasterised by PyMuPDF, Figure 1 taken unchanged from the report PDF). "
                    "`Sch_ma_P_ID1` is a second scan of the same drawing as `Sch_ma_P_ID`, keyed by an affine map "
                    "of the first key: not independent data.")


ROW_CRITERIA = {
    1: f"{VENDOR_TEXT} {AGENT_KEYED_TEXT} Symbols come from the answer key (ids, classes, boxes), so only the line tracing is measured. Connection F1 "
       f"is micro-averaged over the set's sheets by `score_pid2graph`. Pass: F1 >= {TRACER_PASS_F1}, i.e. within "
       f"0.05 of the published development-set figure (0.93). The `--oracle` command line refuses sheets outside "
       f"OPEN100 0-5 (docs/GOAL.md); this row calls `scan_cleanup.trace(..., clean=\"auto\")`, which cleans detected "
       f"scans before calling the tracer and otherwise uses the original image. The tracer's own default is "
       f"unchanged. Clean-up was chosen on synthetic damage to development sheets 0-5 (A176, A185-A189), then "
       f"frozen for holdout sheets 6-11 (A190): L1 0.877 to 0.894, L2 0.566 to 0.818, L3 0.387 to 0.753. Only "
       f"L1 reaches the bar. Both splits use the same damage generator; on the one real archive scan, agent-keyed "
       f"OMRE, F1 falls 0.561 to 0.522. Clean renders' links are unchanged (A189). These re-runs check the frozen "
       f"method, not new held-out samples.",
    2: "The four known answers of `evaluate_vendor.py` on every sheet of the set. Pass: its own check "
       "(`check_controls`): perfect scores perfect, empty scores zero, and neither wrong answer earns symbol F1 above "
       "0.10 on any sheet or overall. Key number: the highest wrong-answer symbol F1 on any one sheet. The controls are "
       "built from the answer key alone, so the `open100-scan-L1/L2/L3` cells (which share `open100-holdout`'s keys) "
       "repeat the `open100-holdout` cell: their passes add no scan evidence. "
       f"{AGENT_KEYED_TEXT}",
    3: "The answer key converted to a prediction (`test_scorer_controls.perfect_prediction`, no tags), imported with "
       "`import_site_drawing.py`, then `deliverable_report.py`, on the first sheet of each set. Pass: no error, "
       "bundle items (equipment + instruments + line items + off-page) = key symbols, bundle links = key links, "
       "REPORT.html written. The recorded-extraction row is compared with the published bundle counts instead. The "
       "prediction is the answer key, so the `open100-scan-L1/L2/L3` cells (which share `open100-holdout`'s keys) "
       "repeat the `open100-holdout` cell: their passes add no scan evidence. "
       f"{AGENT_KEYED_TEXT}",
    4: "TE: `examples/loop-audit/te_loops.csv` against each revision's `key.json`; pass = the published headline. "
       "Bayer: a loop list exported from the Bayer model's `controllers` (a split-range controller gets one list per "
       "leg, since a controller may be listed only once) against `data/bayer_rt/pid/key.json`; pass = every leg drawn "
       "(the sheet is generated from that model). DEXPI: control functions (a C in the function letters) read from "
       "the XML, audited against the intake bundle's `plant_model.json` (tags only); pass = every loop's tags are "
       "present. Where DEXPI nests the sensor in the controller bubble (a combined instrument, e.g. PICSA 4712.02) the "
       "loop list names the controller as its own measurement, so only the controller and output are distinct tags: "
       "the cell counts the distinct tags actually checked. Signal lines are not checked on DEXPI (the bundle has "
       "none), so \"all three tags drawn\" is not tested there.\n\n"
       "Added 2026-10-29, criterion set before the first run: `dexpi-1.3-small-cases` and the `dexpi-1.2-*` exporter "
       "inputs. The loop list is read from each file's InstrumentationLoopFunction elements "
       "(`corpus_adapters.dexpi_loop_list`: the member with a C after its first letter is the controller; the "
       "measurement is the controller itself when a sensor is nested in it, else another member; the output is the "
       "actuating system's or operated valve's number) and audited against `dexpi_reader.py`'s model of the same "
       "file. Only files where the reader found at least one controller and the XML has a complete loop are audited "
       "(the loop audit is the tool under test; a reader that finds no controller is a row 7 finding, counted here as "
       "not auditable). Pass = every audited loop's tags present. No file auditable = n/a with the counts. "
       "`loop_audit.py` now also reads the model's `unplaced` items and treats `_` like `-` in tags; the criterion is "
       "unchanged. `hai-dcs-loops`: n/a; an agent-made loop list of the loops the HAI PDF states now exists, but "
       "there is no drawing to audit it against without circularity (the cell says why). `omre-1958-pid`, "
       "`pronto-fig1`: n/a, no loop list (their agent-made keys are drawings only; the cells say why).",
    5: "`python scripts/generate.py <model> --out <tmp>` on a copy of each model. Pass: exit 0 and the files are in "
       "`--out`.\n\n"
       "Added 2026-10-29, criteria set before the first run. `idaes-hda`: the IDAES HDA flowsheet (HDA_solved.json) "
       "made into a model by `corpus_adapters.idaes_model` (feed and product nodes become BL). Pass: exit 0, "
       "'structural validation: OK', generate.py's own count line equals the model's units and streams, one SVG per "
       "unit plus the overview, every unit id and every stream id appears in at least one output file, and (an "
       "adapter check) the mixer's outlet equals the sum of its inlets in the stream table within 1e-4. "
       "`dwsim-fossee`: 42 FOSSEE DWSIM flowsheets through `corpus_adapters.dwsim_model`; pass per flowsheet: exit 0, "
       "'structural validation: OK', counts equal, one SVG per unit plus the overview; the cell passes if every "
       "flowsheet does. Neither source has instruments, valves or controllers (DWSIM has two solver Adjust blocks in "
       "42 flowsheets), so this row tests units, streams and the export plumbing on models nobody here wrote, not "
       "the instrument, tag or controller exports.",
    6: "TE runs exported to CSV exactly as `examples/historian-csv` was (XMEAS 1-22; the export is checked byte for "
       "byte against the two committed CSVs), bands fitted on d00 with K chosen by the tool, each fault run scored "
       "with fault start row 160. Detection = the 3-consecutive rule. Pass: detected or missed on every fault exactly "
       "as `out/fault_detection/fault_detection.json` (shipped bands, 52 channels) says. That criterion was fixed "
       "before the first run.\n\n"
       "`pronto-day3` (real facility data, PRONTO test day 3): bands fitted on `pronto_normal.csv`, each fault run "
       f"scored from its labelled start row. Pass: detected by the 3-consecutive rule at or after the start, and at "
       f"most {PRONTO_MAX_PRE:.1%} of pre-fault rows flagged (the same target the tool chooses K by). **This criterion "
       "was set after the first run had been seen** (that run failed it), so it is not a pre-registered test.\n\n"
       "Added 2026-10-29: `pronto-day2`, `pronto-day4`, `skab` and `hai-21.03` use the same PRONTO criterion, "
       "**fixed for them before their first run** (it was set after day 3's run, which these runs do not change). "
       "PRONTO days 2 and 4: the day's first normal block fits (day 2: 6 min; day 4: 33 min), converted by "
       "fetch_corpus.py's day-3 rules; a run whose pre-fault rows are the normal CSV's held-out half (day 2 "
       "blockage, day 4 first slugging) is scored on detection only. SKAB: fitted on the anomaly-free run (a "
       "different day), each of the 34 labelled runs scored from its first anomaly row; the cell's detail also gives "
       "a variant fitted on each run's own pre-changepoint rows (reported, not the criterion). HAI 21.03: fitted on "
       "train1, test1 and test4 scored from their first attack row; detail lists every attack event and whether 3 "
       "flagged rows in a row fall inside it. SKAB is GPL-3.0 data: it is converted only into a temporary folder.\n\n"
       "**Method.** Every cell runs `csv_normal_bands.py` with its default, `--method auto` (each cell's detail "
       "records the chosen method). It picks `cyclic` when timestamps cover at least 2 days in the fit half and "
       "a time-of-day profile explains at least 0.1 of held-out variation (median over tags, allowing each tag's "
       "level to move); otherwise it picks `drift`. `--method drift`: per tag, the gap between a 10-sample and a "
       "600-sample exponentially weighted average, flagged when wider than K times its normal spread (never under "
       "1% of the tag's normal reading; the band shrinks with the reading to no less than half). `--method cyclic`: "
       "subtract each tag's mean in 48 half-hour slots, take a median of 3 samples, then apply the same drift gap; "
       "its band does not shrink with the reading. For either, K is the smallest of 10, 12, 15, 20 that flags under "
       "0.5% of held-out normal rows. The median of 3 is used only by cyclic. The older fixed level bands "
       "(`--method level`, mean +/- K sd) flagged normal running before almost every real fault. Drift was "
       "developed on PRONTO days 2-4, SKAB, HAI 21.03 and TE (A163, A165, A171); cyclic and auto were developed "
       "on those sources plus `uci-hydraulic`, `metropt3` and `battledim` (A178, A183). A pass there is development "
       "evidence. On TE, auto still chooses drift and detects later than level; the README's matching fault-6 "
       "statement is what the published-number check reads. The criterion is unchanged.\n\n"
       "**Split.** `uci-hydraulic`, `metropt3` and `battledim` were held out for drift's second iteration "
       "(A165 split and label mappings, A171 frozen-method run); they became development data when their cyclic "
       "failures informed A183. **Held out for auto/cyclic:** `battledim-2019`, split and mapping fixed in A178, "
       "method frozen in A183, scored once in A184 under the same criterion (3 flagged rows in a row at or after "
       "the start; at most 0.5% of pre-fault rows flagged). This is the same L-Town water network as 2018, so it "
       "tests carry-over across years only: 2018 development improves from 0/14 to 8/14, 2019 from 0/19 to 6/19. "
       "Detections arrive **14 hours to 5 days late**, and **tank level T1 drives most flags**; these results do "
       "not establish prompt leak isolation or performance on a different network. UCI's cycle-averaged rows and "
       "MetroPT-3's compressor duty cycle are not daily clock cycles, so auto leaves them on drift.",
    7: "`dexpi_to_twin.convert` on each geometry sheet, scored against its own key, then the intake. Pass: zero "
       "corrections on every sheet and bundle counts equal to the prediction's.\n\n"
       "Added 2026-10-29, criteria set before the first run (not blind: the staging pilot's reader counts had been "
       "seen): `dexpi_reader.py` on every DEXPI 1.2 export of the TrainingTestCases, one input per exporting tool "
       "(SPPID, Comos, AVEVA P&ID, AutoCAD P&ID, and the DEXPI initiative's reference solutions), and on the 1.3 "
       "single-feature cases (E, I, P). Truth is read from the same file by `corpus_adapters.dexpi_truth`, not by the "
       "reader. A file passes when (a) the reader writes a model, or refuses it for a reason seen in the XML "
       "(duplicate IDs, wrong root, nothing to read); a crash or an unconfirmed refusal fails; (b) units = top-level "
       "equipment; (c) every control function (a C after the first letter) is a controller in the model; (d) every "
       "instrument function is in the model (an instrument, a controller, or the tag bubble of a valve). The input "
       "passes when every file does. `dexpi-1.2-cross-vendor`: for each case version with a reference export, every "
       "other export's reader counts (units, instruments + controllers, controllers, streams) must equal the "
       "reference's; the XML's own counts are reported beside them, so a disagreement can be placed in the export or "
       "in the reader. Pass = all equal.\n\n"
       "The reader changed after these criteria were set (data/attempts.json A157, A166: other tools' DEXPI "
       "dialects). The pre-registered criterion above and its results stay primary. **Second reading, set after the "
       "results were seen:** items with no unit to place them on count as present when the reader lists them in "
       "`unplaced` with a reason (an item on a line with both ends open genuinely has no unit); the cells report it "
       "beside the primary result, never instead of it. Truth-definition limit, stated rather than changed: the "
       "truth counts a C after the first letter of category plus function letters as a control function, so the "
       "IEC category `IEC-?` of AutoCAD I05V01_AUD.EX01's control valve reads as one. The cross-vendor cell is as "
       "before.",
    8: f"A different layer from row 1. Row 1 scores the NETWORK layer: every pair of symbols on one drawn line "
       f"network, the answer key's definition. This row scores the PIPE layer of `line_layers.py`: which item or "
       f"junction is piped directly to which, with the answer key's symbols, so only the tracing is measured. Truth: "
       f"the DEXPI XML's piping segments (tees are elements; measuring and signal lines are not pipes, so instrument "
       f"symbols are left out of the traced pipe layer before scoring) and, for the generated sheets, the current "
       f"drawer's own routes, valves, taps and tee points (checked to give exactly the key's line networks). "
       f"Junctions are matched by position, within half a symbol side. Pass: pipe-segment F1 >= {PIPE_PASS_F1} (the "
       f"same bar as row 1). **Criterion fixed 2026-10-29 before this row's first matrix run; the scorer had already "
       f"been run on these inputs while the tool was written** (data/attempts.json), so it is not a blind test. "
       f"The older TE revisions have no pipe truth: n/a, with the reason. `open100-dev` and `open100-holdout` "
       f"(added 2026-10-29, same criterion, fixed before these cells' first matrix run): the truth is DERIVED from "
       f"the PID2Graph key graph (`line_layers.pid2graph_truth`: connector and crossing nodes as line points, 3+-edge "
       f"crossings as junctions; the key does not say which lines are pipe), not drawn by a source; the development "
       f"sheets 0-5 are the ones the tracer was tuned on and the scorer had been run on them while it was written "
       f"(data/attempts.json A149), so that cell is not a blind test; holdout sheets 6-11 were not. "
       f"{VENDOR_TEXT} Its truth is the XML's piping segments, process piping only, as for `dexpi` "
       f"(`line_layers.score_set('dexpi-1.2-vendor')`, sheets from the build's sidecars). Re-run 2026-10-29 for every "
       f"input after line_layers.py changed (A191-A196): closed shapes are contracted using distinct neighbours, "
       f"nearby landing points are separated, touching process items gain a marked segment, and position-less "
       f"junction matching is fixed in the scorer (A192). DEXPI C01-C03, SPPID, OPEN100 0-5, TE and Bayer were "
       f"development data; Comos, AVEVA, OPEN100 6-11 and the agent-keyed sets were held out for these changes, "
       f"seen once before as baselines. A191 changes derived truth too (OPEN100 holdout 388 to 386 segments), "
       f"so score movement is not pure tracing gain. The `open100-holdout` cell also records why the earlier A170 "
       f"result was only partly blind. {AGENT_KEYED_TEXT} Their pipe truth is derived from the agent-made key graph as for OPEN100 "
       f"(`pid2graph_truth`; the key's networks reproduce its all-pairs links on every sheet), and the agent-keyed "
       f"sheets are scored with the set registered for that call only (`line_layers.SETS` itself is not edited).",
}


def row6_table(by, r):
    c = by.get((6, "te-braatz-runs"))
    if not c or "faults" not in c["detail"]:
        return []
    m = c["detail"].get("method") or "level"
    out = [f"Fault by fault (delays in minutes after the fault; CSV route = `--method {m}` on XMEAS 1-22; reference = "
           f"shipped bands, 52 channels):", "",
           "| Fault | CSV route: detected, delay | False alarms before the fault (samples, events) | Reference: "
           "detected, delay | Agree? |", "|---|---|---|---|---|"]
    for f, v in sorted(c["detail"]["faults"].items(), key=lambda kv: int(kv[0])):
        out.append(f"| {f} | {'yes' if v['detected'] else 'no'}, {v['delay_min'] if v['delay_min'] is not None else '-'} | "
                   f"{v['false_alarm_samples_before_fault']}, {v['false_alarm_events_before_fault']} | "
                   f"{'yes' if v['ref_detected'] else 'no'}, {v['ref_delay_min'] if v['ref_delay_min'] is not None else '-'} | "
                   f"{'yes' if v['agrees'] else '**no**'} |")
    return out


def row1_table(by, r):
    out = ["Per sheet (connection F1):", "", "| Input | Sheets |", "|---|---|"]
    for i in ROW_INPUTS[1]:
        c = by.get((1, i))
        if c and "sheets" in c["detail"]:
            out.append(f"| `{i}`{' ' + AGENT_KEY_MARK if agent_keyed(c) else ''} | "
                       + ", ".join(f"{s}: {v['connection_f1']}" for s, v in c["detail"]["sheets"].items()) + " |")
    return out if len(out) > 4 else []


def row8_table(by, r):
    out = ["Per sheet (pipe-segment F1; item-to-item F1; junctions found / true / predicted):", "",
           "| Input | Sheets |", "|---|---|"]
    for i in ROW_INPUTS[8]:
        c = by.get((8, i))
        if c and "sheets" in c["detail"]:
            out.append(f"| `{i}`{' ' + AGENT_KEY_MARK if agent_keyed(c) else ''} | " + ", ".join(
                f"{s}: {v['segment_f1']}; {v['item_to_item_f1']}; {v['junctions_found']}/{v['junctions_true']}/"
                f"{v['junctions_predicted']}" for s, v in c["detail"]["sheets"].items()) + " |")
    return out if len(out) > 4 else []


ROW_EXTRA = {1: row1_table, 6: row6_table, 8: row8_table}


# ------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rows", help="comma-separated row numbers (default: all)")
    ap.add_argument("--check", action="store_true",
                    help="only verify docs/GENERALIZATION.md matches the JSON and no cell's tool has changed since it ran")
    ap.add_argument("--inputs", help="comma-separated input ids: run only those cells of the chosen rows and keep every "
                                     "other cell exactly as recorded (needs an existing matrix.json)")
    ap.add_argument("--out-dir", type=Path,
                    help="read/write matrix.json and GENERALIZATION.md here instead of out/generalization/ and docs/ "
                         "(a scratch run; with --rows, the other rows are copied from the committed matrix.json)")
    a = ap.parse_args(argv)
    corpus = load_corpus()
    out_json = a.out_dir / "matrix.json" if a.out_dir else OUT_JSON
    doc = a.out_dir / "GENERALIZATION.md" if a.out_dir else DOC
    if a.check:
        if not out_json.is_file():
            print(f"missing {show(out_json)}; run python scripts/corpus_matrix.py")
            return 1
        matrix = json.loads(out_json.read_text(encoding="utf-8"))
        problems = []
        if (doc.read_text(encoding="utf-8") if doc.is_file() else "") != render(matrix, corpus):
            problems.append(f"{show(doc)} does not match {show(out_json)} (or data/corpus.json)")
        stale = stale_cells(matrix)
        if stale:
            problems.append(f"{len(stale)} of {len(matrix.get('cells', []))} cells are stale (their tool changed "
                            "since they ran, or they carry no tool hash):\n  " + "\n  ".join(stale))
        if problems:
            print("\n".join(problems) + "\nre-run python scripts/corpus_matrix.py (all rows, or --rows for the stale "
                  "ones)")
            return 1
        print(f"{show(doc)} matches {show(out_json)}; every cell's tool hashes match the files on disk")
        return 0
    rows = sorted(int(x) for x in a.rows.split(",")) if a.rows else sorted(ROWS)
    unknown = [r for r in rows if r not in ROWS]
    if unknown:
        ap.error(f"unknown rows {unknown}; rows are {sorted(ROWS)}")
    inputs = inputs_by_id(corpus)
    only = set(a.inputs.split(",")) if a.inputs else None
    if only and not only <= set(inputs):
        ap.error(f"unknown inputs {sorted(only - set(inputs))}")
    old_src = out_json if out_json.is_file() else OUT_JSON
    old = json.loads(old_src.read_text(encoding="utf-8")) if old_src.is_file() and (a.rows or only) else None
    if only and old is None:
        ap.error("--inputs merges into an existing matrix.json; none found")
    t0 = time.time()
    cells = [c for c in (old or {}).get("cells", [])
             if c["row"] not in rows or (only and c["input"] not in only)]
    for r in rows:
        for i in ROW_INPUTS[r]:
            if only and i not in only:
                continue
            c = run_cell(r, inputs[i])
            print(f"row {r} {ROWS[r]['short']:<16} {i:<24} {c['status']:<10} {c['value']}  {c['reason'][:140]}",
                  flush=True)
            cells.append(c)
    cells = [c for c in cells if c["input"] in ROW_INPUTS[c["row"]]]  # a cell whose input left its row is dropped
    cells.sort(key=lambda c: (c["row"], ROW_INPUTS[c["row"]].index(c["input"])))
    took = round(time.time() - t0, 1)
    matrix = {"about": "Generalization matrix written by scripts/corpus_matrix.py; rendered as docs/GENERALIZATION.md.",
              "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
              "seconds": round(sum(c.get("seconds", 0) for c in cells), 1),
              "rows_run_this_time": rows, **({"inputs_run_this_time": sorted(only)} if only else {}), "tracer_pass_f1": TRACER_PASS_F1, "pipe_pass_f1": PIPE_PASS_F1,
              "cells": cells}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    doc.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(matrix, indent=1) + "\n", encoding="utf-8", newline="\n")
    doc.write_text(render(matrix, corpus), encoding="utf-8", newline="\n")
    print(f"wrote {show(out_json)} and {show(doc)} ({took} s)")
    return 0


def show(path):
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
