"""Check which loops in a plant's own control-loop list a P&ID actually draws, and say what is missing from the rest.

Inputs
  loops    a CSV loop list, the kind a plant can export from its DCS or PLC configuration. One row per controller:
             controller   the controller's tag (FIC-101)
             measurement  the tag of the instrument it reads (FT-101)
             output       what it moves: a final element (FV-101), or, for a cascade, the inner controller (FIC-101)
             description  optional free text, copied into the report
           Lines starting with # are skipped; other columns are ignored and listed in the report. A row with a
           missing field, a repeated controller, or a loop whose output is itself is refused with its line number (a
           controller listed as its own measurement is a combined instrument, and is allowed).
  drawing  either an answer key in this repository's key.json format (data/te_pid/key.json is the example: per
           sheet, `symbols` with printed `text`, and `signal_edges`, the signal lines), or a plant_model.json made by
           scripts/import_site_drawing.py or scripts/build_twin.py from an extraction.

What counts as drawn (answer key)
  controller   a symbol whose printed text is the controller tag
  measurement  a symbol whose printed text is the measurement tag
  output       a symbol whose printed text is the output tag
  signal in    a signal line between the measurement and the controller, on one sheet (as in te_control_loops.py, a
               measurement reaching its controller through continuation flags is not followed and reads as missing)
  signal out   a signal line between the controller and its output, either on one sheet or across sheets through a
               pair of signal continuation flags (an outbound flag whose `signal_to` names the output, joined to the
               controller; an inbound flag whose `signal_from` names the controller, joined to the output)
  Only `signal_edges` count. A process line joining an indicator to a valve is not a signal. Signal lines are
  matched without direction. Tags match on printed text, ignoring case, spaces and hyphens ('FIC 101' = 'FIC-101');
  nothing else is normalised, so strip DCS suffixes such as '.PV' before exporting.
  drawn          every check passes
  partly drawn   the controller is there, something else is not (the report names it)
  not drawn      no symbol carries the controller tag

plant_model.json
  An extracted model keeps tags but not signal lines (the extraction schema has one kind of connection, and
  scripts/build_twin.py turns it into process streams). So only controller, measurement and output presence are
  checked, the signal checks are reported as "not checked", and the best a loop can get is "tags present", never
  "drawn". Tags are read from units, instruments, final elements, line items and controllers.

What it does NOT check
  - the control strategy. The list is taken as the truth; the tool grades the drawing against it and never judges
    whether a pairing, a cascade or a tag is a good idea. A wrong list gives a confident wrong report.
  - loop numbering. scripts/te_control_loops.py also requires measurement, controller and valve to share a loop
    number; here the tags come from your own list, so that is your tagging convention, not a drawing fault.
  - controller letters, signal direction, line style (electric, pneumatic, software), fail positions, ranges,
    alarms, interlocks and anything not on the list (an extra controller on the drawing is not reported).
  - the drawing image. It reads the key or model only; whether the key matches the picture is another tool's job.

No AI is used here. Stdlib only.

Usage
  python scripts/loop_audit.py --loops examples/loop-audit/te_loops.csv --drawing data/te_pid/key.json
  python scripts/loop_audit.py --loops my_loops.csv --drawing my-bundle/plant_model.json --out out/my_loop_audit
Writes <out>.md and <out>.json (default out/loop_audit) and prints the totals. Exit code 0 when the audit ran,
whatever it found; 2 when an input is refused.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ("controller", "measurement", "output")
OPTIONAL = ("description",)
KEY_CHECKS = ("controller", "measurement", "output", "signal_in", "signal_out")
CHECK_TEXT = {
    "controller": "controller symbol", "measurement": "measurement symbol", "output": "output symbol",
    "signal_in": "signal line measurement -> controller", "signal_out": "signal line controller -> output",
}
# "unplaced" holds items read off the drawing that no unit could be found for (e.g. a valve on a line whose ends
# are open): they are on the drawing, so a loop tag found there is present.
MODEL_TAG_LISTS = ("units", "instruments", "final_elements", "line_items", "controllers", "manual_valves",
                   "relief_devices", "unplaced")


class InputError(Exception):
    """An input the audit refuses to grade."""


def compact(text):
    """Printed tag text as a lookup key: bubbles print 'FT 101' (letters over number), lists say FT-101, and a tool
    that allows one hyphen per tag writes P-4712.02 as P_4712.02."""
    return re.sub(r"[\s\-_]", "", text or "").upper()


def read_loops(path):
    """The loop list as dicts with their physical line numbers. Raises InputError naming the line."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path}: not UTF-8 text ({exc.reason} at byte {exc.start})") from None
    # Comment lines become empty lines so csv's line_num stays the physical line number.
    lines = ["\n" if ln.lstrip().startswith("#") else ln for ln in raw.splitlines(keepends=True)]
    reader = csv.reader(lines)
    header, header_line = None, None
    for row in reader:
        if row and any(c.strip() for c in row):
            header, header_line = [c.strip().lower() for c in row], reader.line_num
            break
    if header is None:
        raise InputError(f"{path}: no header row (expected columns {', '.join(REQUIRED)})")
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise InputError(f"{path} line {header_line}: header lacks column(s) {', '.join(missing)}; "
                         f"found {', '.join(header) or 'nothing'}")
    dupes = sorted({c for c in header if c and header.count(c) > 1})
    if dupes:
        raise InputError(f"{path} line {header_line}: column(s) {', '.join(dupes)} appear more than once")
    ignored = [c for c in header if c not in REQUIRED + OPTIONAL]
    loops, seen = [], {}
    for row in reader:
        if not row or not any(c.strip() for c in row):
            continue
        line = reader.line_num
        if len(row) > len(header):
            raise InputError(f"{path} line {line}: {len(row)} fields, the header has {len(header)}")
        rec = {name: (row[i].strip() if i < len(row) else "") for i, name in enumerate(header)}
        empty = [c for c in REQUIRED if not rec[c]]
        if empty:
            raise InputError(f"{path} line {line}: empty {', '.join(empty)}")
        ctl = compact(rec["controller"])
        if ctl in seen:
            raise InputError(f"{path} line {line}: controller {rec['controller']} already listed on line {seen[ctl]}")
        if compact(rec["output"]) == ctl:
            raise InputError(f"{path} line {line}: {rec['controller']} names itself as its own output")
        # measurement == controller is allowed: a combined instrument (one bubble that measures and controls, as
        # DEXPI and many P&IDs draw it, e.g. PICSA 4712.02). The measurement is then inside the controller symbol.
        seen[ctl] = line
        loops.append({"line": line, "controller": rec["controller"], "measurement": rec["measurement"],
                      "output": rec["output"], "description": rec.get("description", "")})
    if not loops:
        raise InputError(f"{path}: header but no loops")
    return loops, ignored


def load_drawing(path):
    """('key', key) or ('plant_model', model), decided by the file's shape."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: not JSON ({exc.msg}, line {exc.lineno})") from None
    if isinstance(data, dict) and isinstance(data.get("sheets"), dict):
        for name, sheet in data["sheets"].items():
            if not isinstance(sheet, dict) or not isinstance(sheet.get("symbols"), dict):
                raise InputError(f"{path}: sheet {name} has no symbols table")
        return "key", data
    if isinstance(data, dict) and isinstance(data.get("instruments"), list):
        return "plant_model", data
    raise InputError(f"{path}: neither an answer key (sheets -> symbols, signal_edges) nor a plant_model.json "
                     "(instruments list)")


def _key_index(key):
    symbols, signal, by_text, flags_out, flags_in = {}, {}, {}, {}, {}
    for name, sheet in key["sheets"].items():
        drawing = sheet.get("drawing", name)
        for sid, sym in sheet["symbols"].items():
            ref = (drawing, sid)
            symbols[ref] = sym
            by_text.setdefault(compact(sym.get("text")), []).append(ref)
            if sym.get("signal_to"):
                flags_out.setdefault(compact(sym["signal_to"]), []).append(ref)
            if sym.get("signal_from"):
                flags_in.setdefault(compact(sym["signal_from"]), []).append(ref)
        for a, b in sheet.get("signal_edges", []):
            signal.setdefault((drawing, a), set()).add((drawing, b))
            signal.setdefault((drawing, b), set()).add((drawing, a))
    by_text.pop("", None)
    return symbols, signal, by_text, flags_out, flags_in


def _status(checks):
    if not checks["controller"]:
        return "not_drawn"
    # None = not checkable from this input (signal lines in a plant_model.json); False = checked and absent.
    return "partly_drawn" if any(v is False for v in checks.values()) else "drawn"


def audit_key(loops, key):
    symbols, signal, by_text, flags_out, flags_in = _key_index(key)

    def linked(a_refs, b_refs):
        return any(b in signal.get(a, ()) for a in a_refs for b in b_refs)

    rows = []
    for lp in loops:
        ctl, meas, out = (by_text.get(compact(lp[c]), []) for c in REQUIRED)
        combined = compact(lp["measurement"]) == compact(lp["controller"])
        # Cross-sheet: controller -> outbound flag naming the output; inbound flag naming the controller -> output.
        crosses = linked(ctl, flags_out.get(compact(lp["output"]), [])) and \
            linked(flags_in.get(compact(lp["controller"]), []), out)
        checks = {"controller": bool(ctl), "measurement": bool(meas), "output": bool(out),
                  "signal_in": linked(meas, ctl) or (combined and bool(ctl)),
                  "signal_out": bool(ctl) and (linked(ctl, out) or crosses)}
        row = _row(lp, checks, sorted({d for d, _ in ctl + meas + out}))
        if combined:
            row["combined"] = True
            row["note"] = ("combined instrument: the measurement is inside the controller symbol, so the measurement "
                           "and signal-in checks pass on the controller symbol alone, with no signal line behind them")
        if not ctl:
            row["hint"] = ("no symbol carries this controller tag: check its spelling, and strip DCS suffixes "
                           "such as .PV or .OUT from the loop list")
        if row["status"] == "partly_drawn":
            # What the controller's signal lines do reach: shows a tag printed differently from the list
            # (an indicator 'FI 101' where the list says transmitter FT-101) without guessing it is the same thing.
            row["controller_signal_links"] = sorted({symbols[n].get("text") or n[1] for c in ctl
                                                      for n in signal.get(c, ())})
        rows.append(row)
    return rows


def model_tags(model):
    tags = {}
    for field in MODEL_TAG_LISTS:
        for item in model.get(field) or []:
            if isinstance(item, dict) and item.get("tag"):
                tags.setdefault(compact(item["tag"]), item.get("id") or item["tag"])
    tags.pop("", None)
    return tags


def audit_model(loops, model):
    tags = model_tags(model)
    rows = []
    for lp in loops:
        checks = {c: compact(lp[c]) in tags for c in REQUIRED}
        checks.update(signal_in=None, signal_out=None)
        row = _row(lp, checks, [])
        if row["status"] == "drawn":
            row["status"] = "tags_present"
        if compact(lp["measurement"]) == compact(lp["controller"]):
            row["combined"] = True
            row["note"] = ("combined instrument: the measurement is the controller's own tag, so only the controller "
                           "and output tags are distinct checks")
        row["found_as"] = {c: tags[compact(lp[c])] for c in REQUIRED if checks[c]}
        rows.append(row)
    return rows


def _row(lp, checks, sheets):
    status = _status(checks)
    return {"line": lp["line"], "controller": lp["controller"], "measurement": lp["measurement"],
            "output": lp["output"], "description": lp["description"], "status": status, "checks": checks,
            "missing": [CHECK_TEXT[c] for c, v in checks.items() if v is False], "sheets": sheets}


def run(loops_path, drawing_path):
    loops, ignored = read_loops(loops_path)
    kind, drawing = load_drawing(drawing_path)
    rows = audit_key(loops, drawing) if kind == "key" else audit_model(loops, drawing)
    statuses = ("drawn", "partly_drawn", "not_drawn") if kind == "key" else ("tags_present", "partly_drawn",
                                                                              "not_drawn")
    checks = KEY_CHECKS if kind == "key" else REQUIRED
    return {
        "tool": "scripts/loop_audit.py",
        "loops_file": _display(loops_path), "drawing_file": _display(drawing_path), "drawing_kind": kind,
        "ignored_columns": ignored,
        "signals_checked": kind == "key",
        "totals": {"loops": len(rows), **{s: sum(r["status"] == s for r in rows) for s in statuses}},
        "by_check": {c: sum(r["checks"][c] is True for r in rows) for c in checks},
        "loops": rows,
    }


def _display(path):
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def headline(result):
    t = result["totals"]
    k = sum(1 for r in result["loops"] if r.get("combined"))
    combined = f" ({k} combined instrument{'s' if k > 1 else ''}: measurement = controller tag)" if k else ""
    if result["drawing_kind"] == "key":
        return (f"{t['drawn']} of {t['loops']} loops drawn, {t['partly_drawn']} partly drawn, "
                f"{t['not_drawn']} not drawn{combined}")
    tags = "all their tags" if k else "all three tags"
    return (f"{t['tags_present']} of {t['loops']} loops have {tags} present{combined} (signal lines not checked: "
            f"an extracted model has none), {t['partly_drawn']} partly, {t['not_drawn']} without the controller")


# Checks a combined instrument passes on its controller symbol alone: the report must not show them as drawn lines.
COMBINED_CHECKS = {"measurement": "read from the controller symbol", "signal_in": "no line drawn"}


def _cell(row, check):
    value = row["checks"][check]
    if value and row.get("combined") and check in COMBINED_CHECKS:
        return "combined"
    return "yes" if value else "no"


def _per_check(result, check, value, n):
    text = f"{CHECK_TEXT[check]} {value}/{n}"
    k = sum(1 for r in result["loops"] if r.get("combined") and r["checks"][check] and check in COMBINED_CHECKS)
    if k:
        text += f" ({k} combined instrument{'s' if k > 1 else ''}, {COMBINED_CHECKS[check]})"
    return text


def markdown(result):
    key = result["drawing_kind"] == "key"
    n = result["totals"]["loops"]
    lines = ["# Control-loop audit", "",
             f"Loop list `{result['loops_file']}` against {'answer key' if key else 'extracted plant model'} "
             f"`{result['drawing_file']}`. Generated by `scripts/loop_audit.py`; it grades the drawing against the "
             "list and never judges the control strategy.", "",
             f"**{headline(result)}.** Per check: "
             + ", ".join(_per_check(result, c, v, n) for c, v in result["by_check"].items()) + ".", ""]
    if not key:
        lines += ["An extracted plant_model.json carries tags but no signal lines, so a loop here can show its "
                  "three tags and still be undrawn. Check the signal lines on the sheet, or audit an answer key.", ""]
    if result["ignored_columns"]:
        lines += [f"Columns ignored: {', '.join(result['ignored_columns'])}.", ""]
    cols = KEY_CHECKS if key else REQUIRED
    lines += ["| Line | Controller | Measurement | Output | Status | " + " | ".join(cols) + " | Missing |",
              "|---|---|---|---|---|" + "---|" * len(cols) + "---|"]
    for r in result["loops"]:
        cells = [_cell(r, c) for c in cols]
        lines.append(f"| {r['line']} | {r['controller']} | {r['measurement']} | {r['output']} | "
                     f"{r['status'].replace('_', ' ')} | " + " | ".join(cells) + f" | {'; '.join(r['missing'])} |")
    combined = [r["controller"] for r in result["loops"] if r.get("combined")]
    if combined:
        lines += ["", f"Combined instruments (the list names the controller as its own measurement, so the measurement "
                      f"is taken to be inside the controller symbol): {', '.join(combined)}. Their measurement and "
                      "signal_in cells read \"combined\": those checks pass on the controller symbol alone, and no "
                      "drawn signal line stands behind them. Only the controller, the output and the signal line "
                      "controller -> output are actually checked for these loops."]
    absent = [r["controller"] for r in result["loops"] if r.get("hint")]
    if absent:
        lines += ["", f"{len(absent)} controller tag(s) appear nowhere on the drawing. If the drawing should show them, "
                      "check the spelling and strip DCS suffixes such as .PV or .OUT from the loop list."]
    hints = [r for r in result["loops"] if r.get("controller_signal_links")]
    if hints:
        lines += ["", "Partly drawn loops: what each controller's signal lines reach on the drawing. A tag here that "
                      "differs from the list may be the same instrument printed under another tag; the audit does "
                      "not assume so.", ""]
        lines += [f"- {r['controller']} (list: {r['measurement']} -> {r['output']}): "
                  f"{', '.join(r['controller_signal_links'])}" for r in hints]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--loops", type=Path, required=True,
                    help="loop-list CSV: controller,measurement,output[,description]")
    ap.add_argument("--drawing", type=Path, required=True, help="answer key (key.json) or plant_model.json")
    ap.add_argument("--out", type=Path, default=ROOT / "out" / "loop_audit",
                    help="report path without extension; writes .md and .json (default out/loop_audit)")
    args = ap.parse_args(argv)
    try:
        result = run(args.loops, args.drawing)
    except (InputError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    md, js = args.out.with_suffix(".md"), args.out.with_suffix(".json")
    md.write_text(markdown(result), encoding="utf-8", newline="\n")
    js.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{headline(result)}; report {md} and {js.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
