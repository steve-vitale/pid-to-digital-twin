"""Read the Tennessee Eastman control loops out of the closed-loop source code, check them against the recorded
data, and score how much of that control a P&ID answer key actually draws.

Why this exists: the generated TE sheets (journal entry 44) draw every transmitter and every valve, but no
controller and no signal line. A practitioner looking at them sees indicators beside valves with unrelated
numbers (revision A: FI-102 next to FV-201) and no way to tell what controls what. That is the difference between a PFD with
bubbles on it and a P&ID. This script makes the gap measurable before anyone fixes it.

Source of truth: temain_mod.f, the closed-loop simulation code in the Braatz group's TE archive
(https://web.mit.edu/braatzgroup/TE_process.zip, member TE_process/temain_mod.f.txt; the GitHub mirror
scripts/fetch_te_data.py uses is byte-identical, checked 2026-10-28). Each controller is a subroutine CONTRLn
whose error line names its measurement and setpoint, ERRn = (SETPT(j) - XMEAS(m)) ..., and whose update line
moves either a valve, XMV(k) = XMV(k) + DXMV, or another loop's setpoint, SETPT(j) = SETPT(j) + DXMV (a cascade).
Which controllers actually run, and how often, comes from the CALL lines in the simulation loop. The comments in
the file are NOT used: several are copied from one subroutine to the next ("Stripper Level Controller" sits on
the purge loop and the reactor cooling loop).

The archive's copy of temain_mod.f is configured for one fault run (it switches IDV(12) on after 8 hours), so the
code alone doesn't prove the published data files were made with these loops. --check therefore also compares
each loop's coded setpoint with its measurement's mean in d00_te.dat, the normal-operation run the replay server
plays. Every controlled variable should sit on its setpoint; a wrong pairing would not.

Outputs:
  data/te_control_loops.json   the loop table (committed): measurement tag, output tag or inner loop, mode,
                               tuning, scan period, source line, and the source file's SHA-256
  out/te_loop_audit.md         the data check and the drawing audit (--check)

Drawing audit. For each running loop, a key passes when it draws:
  measured   the measuring instrument (its tag printed)
  controller a controller symbol for the loop (ISA-5.1 letters with C as a function, e.g. FIC, TIC, AIC)
  signal     signal lines from the measurement to the controller and from the controller to its valve, or to the
             inner loop's controller for a cascade. Only edges the key lists in `signal_edges` count; a process
             line joining an indicator to a valve is not a signal
  numbering  measurement, controller and valve share a loop number (a cascade's outer loop shares it with its
             measurement)
A loop counts as correct only if every check passes. The audit reads keys only; it never edits a drawing.

No AI is used here. Stdlib only.

Usage:  python scripts/te_control_loops.py [--write] [--check] [--key data/te_pid/key.json]
Without --write the loop table is rebuilt in memory and compared with the committed one.
"""
import argparse
import ast
import hashlib
import json
import operator
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "external" / "te-braatz" / "temain_mod.f"
DATA = ROOT / "data" / "external" / "te-braatz" / "d00_te.dat"
MODEL = ROOT / "data" / "te_process_model.json"
LOOPS = ROOT / "data" / "te_control_loops.json"
KEY = ROOT / "data" / "te_pid" / "key.json"
REPORT = ROOT / "out" / "te_loop_audit.md"
SOURCE_SHA256 = "31b83c17f8d52332d6f6fe46d9da3ee7131de2d018bb83945453350bf635c8b6"
ARCHIVE = {"url": "https://web.mit.edu/braatzgroup/TE_process.zip", "member": "TE_process/temain_mod.f.txt"}
MIRROR = "https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/master/temain_mod.f"

# Analyzer channels: which component each XMEAS index reports (teprob.f header; model analyzers AT-123/129/137).
ANALYZER_COMPONENTS = {**{23 + i: c for i, c in enumerate("ABCDEF")},
                       **{29 + i: c for i, c in enumerate("ABCDEFGH")},
                       **{37 + i: c for i, c in enumerate("DEFGH")}}
CONTROLLER_TEXT = re.compile(r"^([A-Z])[A-Z]?C\b|^([A-Z])IC\b")
TAG_NUMBER = re.compile(r"(\d+)")
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _number(expression):
    """Evaluate a Fortran constant expression such as '-83.2 / 5. /3.' (numbers and + - * / only)."""
    def walk(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return -walk(node.operand) if isinstance(node.op, ast.USub) else walk(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        raise ValueError(f"not a constant expression: {expression!r}")
    return walk(ast.parse(expression.strip(), mode="eval").body)


def code_lines(text):
    """(line number, statement) for every non-comment line. Fortran 77 comments have C, c or * in column 1."""
    return [(n, line.strip()) for n, line in enumerate(text.splitlines(), 1)
            if line.strip() and line[:1] not in ("C", "c", "*")]


def parse_source(text):
    lines = code_lines(text)
    stmts = [s for _, s in lines]
    assigned = {}
    for _, s in lines:
        m = re.match(r"(SETPT\(\d+\)|GAIN\d+|TAUI\d+)\s*=\s*(.+)$", s)
        if m and m.group(1) not in assigned and "SETPT" not in m.group(2) and "DXMV" not in m.group(2):
            assigned[m.group(1)] = (m.group(2).strip(), _number(m.group(2)))

    # Which controllers the simulation loop calls, and every how many integration steps (1 step = 1 s).
    period, calls = None, {}
    loop_start = next(i for i, s in enumerate(stmts) if re.match(r"DO \d+ I = 1, NPTS", s))
    for s in stmts[loop_start:]:
        m = re.search(r"MOD\(I,(\d+)\)", s)
        if m:
            period = int(m.group(1))
        for name in re.findall(r"CALL (CONTRL\d+)", s):
            calls.setdefault(name, period)
        if s.startswith("CALL INTGTR"):
            break

    loops, overrides, starts = [], [], [i for i, (_, s) in enumerate(lines) if s.startswith("SUBROUTINE CONTRL")]
    for a, b in zip(starts, starts[1:] + [len(lines)]):
        body = lines[a:b]
        name = body[0][1].split()[1]
        number = int(name[len("CONTRL"):])
        err = out = None
        mode = "P"
        for n, s in body:
            m = re.match(r"ERR\d+\s*=\s*\(?\s*SETPT\((\d+)\)\s*-\s*XMEAS\((\d+)\)\s*\)?\s*(?:\*\s*100\.\s*/\s*([\d.]+))?", s)
            if m:
                err = {"line": n, "setpoint_index": int(m.group(1)), "xmeas": int(m.group(2)),
                       "span": float(m.group(3)) if m.group(3) else None}
            m = re.match(r"XMV\((\d+)\)\s*=\s*XMV\(\1\)\s*\+\s*DXMV", s)
            if m:
                out = {"kind": "final_element", "xmv": int(m.group(1)), "line": n}
            m = re.match(r"SETPT\((\d+)\)\s*=\s*SETPT\(\1\)\s*\+\s*DXMV", s)
            if m:
                out = {"kind": "setpoint", "setpoint_index": int(m.group(1)), "line": n}
            if s.startswith("DXMV") and "TAUI" in s:
                mode = "PI"
            m = re.match(r"(?:ELSE)?IF \((FLAG\.EQ\.(\d)\.AND\.)?XMEAS\((\d+)\)\.(GE|LE)\.([\d.]+)\) THEN", s)
            if m:
                forced = next((float(x.group(1)) for k, t in body
                               if k > n and (x := re.match(r"XMV\(\d+\)\s*=\s*([\d.]+)", t))), None)
                overrides.append({"controller": name, "xmeas": int(m.group(3)),
                                  "condition": f"{'>=' if m.group(4) == 'GE' else '<='} {float(m.group(5)):g}",
                                  "only_after_trip": int(m.group(2)) if m.group(2) else None,
                                  "forces_output_to": forced, "line": n})
        if not err or not out:
            raise ValueError(f"{name}: could not read its error or update line")
        gain = assigned.get(f"GAIN{number}")
        taui = assigned.get(f"TAUI{number}")
        sp = assigned.get(f"SETPT({err['setpoint_index']})")
        loops.append({
            "id": f"C{number}", "subroutine": name, "runs": name in calls,
            "scan_s": calls.get(name), "mode": mode,
            "measurement": {"xmeas": err["xmeas"], "span": err["span"], "line": err["line"]},
            "setpoint_index": err["setpoint_index"], "initial_setpoint": sp[1] if sp else None,
            "output": out,
            "gain": {"expression": gain[0], "value": round(gain[1], 6)} if gain else None,
            "reset_s": round(taui[1] * 3600, 3) if taui and mode == "PI" else None,
        })
    by_setpoint = {lp["setpoint_index"]: lp["id"] for lp in loops if lp["runs"]}
    for lp in loops:
        if lp["output"]["kind"] == "setpoint":
            lp["output"]["inner_loop"] = by_setpoint.get(lp["output"]["setpoint_index"])
    return loops, overrides


def attach_tags(loops, overrides, model):
    by_xmeas, by_xmv = {}, {f["xmv"]: f for f in model["final_elements"]}
    for inst in model["instruments"]:
        lo, _, hi = str(inst["xmeas"]).partition("-")
        for m in range(int(lo), int(hi or lo) + 1):
            by_xmeas[m] = inst
    for lp in loops:
        inst = by_xmeas[lp["measurement"]["xmeas"]]
        lp["measurement"].update(tag=inst["tag"], description=inst["description"], unit=inst["unit"])
        if lp["measurement"]["xmeas"] in ANALYZER_COMPONENTS:
            lp["measurement"]["component"] = ANALYZER_COMPONENTS[lp["measurement"]["xmeas"]]
        if lp["output"]["kind"] == "final_element":
            fe = by_xmv[lp["output"]["xmv"]]
            lp["output"].update(tag=fe["tag"], description=fe["description"])
    for ov in overrides:
        ov["tag"] = by_xmeas[ov["xmeas"]]["tag"]
    # Controller tags: the measurement's first letter + IC + its number (ISA-5.1). An analyzer that feeds more than
    # one controller gets the component as a suffix (AIC-123A, AIC-123D, AIC-123E).
    shared = {}
    for lp in loops:
        if lp["runs"]:
            shared[lp["measurement"]["tag"]] = shared.get(lp["measurement"]["tag"], 0) + 1
    for lp in loops:
        meas = lp["measurement"]
        suffix = meas.get("component", "") if shared.get(meas["tag"], 0) > 1 else ""
        lp["controller_tag"] = f"{meas['tag'][0]}IC-{meas['tag'].split('-')[1]}{suffix}" if lp["runs"] else None
    by_id = {lp["id"]: lp for lp in loops}
    for lp in loops:
        if lp["output"]["kind"] == "setpoint" and lp["output"].get("inner_loop"):
            lp["output"]["tag"] = by_id[lp["output"]["inner_loop"]]["controller_tag"]
    return loops, overrides


def model_controllers(table, check):
    """The controllers as model items: what scripts/draw_pid_from_model.py draws and the exports can name."""
    dev = {r["loop"]: r for r in check["rows"]}
    out = []
    for lp in table["loops"]:
        if not lp["runs"]:
            continue
        meas, o = lp["measurement"], lp["output"]
        out.append({
            "tag": lp["controller_tag"], "loop": lp["id"], "unit": meas["unit"],
            "measurement": meas["tag"], **({"component": meas["component"]} if "component" in meas else {}),
            "output": ({"final_element": o["tag"]} if o["kind"] == "final_element" else {"setpoint_of": o["tag"]}),
            "mode": lp["mode"], "scan_s": lp["scan_s"],
            "description": f"{meas['description']}{' (' + meas['component'] + ')' if 'component' in meas else ''}"
                           f" controller",
            "verification": {
                "status": "confirmed",
                "checked_against": [f"temain_mod.f (Braatz group closed-loop TE code, sha256 {SOURCE_SHA256[:16]}...)",
                                    "d00_te.dat (recorded normal run)"],
                "evidence": (f"{lp['subroutine']}: error line {meas['line']} reads XMEAS({meas['xmeas']}) against "
                             f"SETPT({lp['setpoint_index']}); update line {o['line']} moves "
                             + (f"XMV({o['xmv']})" if o["kind"] == "final_element" else f"SETPT({o['setpoint_index']})")
                             + f"; recorded mean {dev[lp['id']]['mean']:.4g} vs setpoint {lp['initial_setpoint']:g} "
                             f"({dev[lp['id']]['dev_sd']:.2f} SD)"),
                "checked_by": "scripts/te_control_loops.py",
            },
        })
    return out


def build(source_path=SOURCE):
    raw = source_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise SystemExit(f"{source_path.name}: checksum {digest[:16]}... is not the verified archive copy")
    loops, overrides = parse_source(raw.decode("latin-1"))
    loops, overrides = attach_tags(loops, overrides, json.loads(MODEL.read_text(encoding="utf-8")))
    running = [lp for lp in loops if lp["runs"]]
    return {
        "about": ("Tennessee Eastman control loops read by scripts/te_control_loops.py from the closed-loop code "
                  "distributed with the Braatz group's TE data. Measurements and valves are named with this "
                  "project's assigned tags (data/te_process_model.json); xmeas/xmv keep the source indices. "
                  "Cascade loops move an inner loop's setpoint instead of a valve. Loops with runs=false are "
                  "defined in the code but never called."),
        "source": {"file": "temain_mod.f", "sha256": SOURCE_SHA256, "archive": ARCHIVE, "mirror": MIRROR,
                   "license": "Braatz group NCSA-style notice (data/external/te-braatz/readme.txt)"},
        "summary": {"running": len(running),
                    "valve_loops": sum(lp["output"]["kind"] == "final_element" for lp in running),
                    "cascades": sum(lp["output"]["kind"] == "setpoint" for lp in running),
                    "defined_not_called": [lp["id"] for lp in loops if not lp["runs"]]},
        "loops": loops,
        "overrides": overrides,
    }


def data_check(table, data_path=DATA):
    """Each running loop's coded setpoint against its measurement's mean in the normal-operation run."""
    rows = [list(map(float, line.split())) for line in data_path.read_text().splitlines() if line.strip()]
    out = []
    for lp in table["loops"]:
        if not lp["runs"]:
            continue
        x = [r[lp["measurement"]["xmeas"] - 1] for r in rows]
        mean, sd = statistics.fmean(x), statistics.pstdev(x)
        out.append({"loop": lp["id"], "tag": lp["measurement"]["tag"], "setpoint": lp["initial_setpoint"],
                    "mean": mean, "sd": sd, "dev_sd": abs(mean - lp["initial_setpoint"]) / sd})
    return {"samples": len(rows), "rows": out}


def _compact(text):
    """Printed tag text as a lookup key: bubbles print 'FT 101' (letters over number), the model says FT-101."""
    return re.sub(r"[\s\-]", "", text or "").upper()


def _number_of(tag):
    m = TAG_NUMBER.search(tag or "")
    return m.group(1) if m else None


def audit(table, key):
    """Score one answer key (the schema draw_pid_from_model.py emits) against the running loops."""
    symbols, signal = {}, {}
    for sheet in key["sheets"].values():
        for sid, sym in sheet["symbols"].items():
            symbols[(sheet["drawing"], sid)] = sym
        for a, b in sheet.get("signal_edges", []):
            signal.setdefault((sheet["drawing"], a), set()).add((sheet["drawing"], b))
            signal.setdefault((sheet["drawing"], b), set()).add((sheet["drawing"], a))
    by_text = {}
    for ref, sym in symbols.items():
        by_text.setdefault(_compact(sym.get("text")), []).append(ref)
    controllers = {ref for ref, sym in symbols.items() if CONTROLLER_TEXT.match((sym.get("text") or ""))}
    # Signal continuation flags carry a loop to another sheet: signal_to names what the line drives there,
    # signal_from names the controller it comes from.
    flags_out, flags_in = {}, {}
    for ref, sym in symbols.items():
        if sym.get("signal_to"):
            flags_out.setdefault(_compact(sym["signal_to"]), []).append(ref)
        if sym.get("signal_from"):
            flags_in.setdefault(_compact(sym["signal_from"]), []).append(ref)

    def linked(a_refs, b_refs):
        return any(b in signal.get(a, ()) for a in a_refs for b in b_refs)

    running = {lp["id"]: lp for lp in table["loops"] if lp["runs"]}
    rows = []
    for lp in running.values():
        meas_tag = lp["measurement"]["tag"]
        meas_refs = by_text.get(_compact(meas_tag), [])
        own = [c for c in controllers if linked(meas_refs, [c])
               and symbols[c]["text"][0] == meas_tag[0]]
        # Several controllers can read one analyzer; a key that says which loop a symbol draws narrows it.
        if any(symbols[c].get("loop") == lp["id"] for c in own):
            own = [c for c in own if symbols[c].get("loop") == lp["id"]]
        if lp["output"]["kind"] == "final_element":
            target_tag = lp["output"]["tag"]
            target_refs = by_text.get(_compact(target_tag), [])
            target_texts = {_compact(target_tag)}
        else:
            inner = running[lp["output"]["inner_loop"]]
            target_tag = f"{inner['id']} controller"
            target_refs = [c for c in controllers if linked(by_text.get(_compact(inner["measurement"]["tag"]), []), [c])
                           and (symbols[c].get("loop") in (None, inner["id"]))]
            target_texts = {_compact(symbols[c]["text"]) for c in target_refs}

        def crosses(c):
            """Controller -> outbound flag naming the target; inbound flag naming the controller -> target."""
            outs = [f for t in target_texts for f in flags_out.get(t, [])]
            ins = flags_in.get(_compact(symbols[c]["text"]), [])
            return linked([c], outs) and linked(ins, target_refs)
        numbers = {_number_of(meas_tag)} | {_number_of(symbols[c]["text"]) for c in own}
        if lp["output"]["kind"] == "final_element":
            numbers.add(_number_of(target_tag))
        checks = {
            "measured": bool(meas_refs),
            "controller": bool(own),
            "signal": bool(own) and (linked(own, target_refs) or any(crosses(c) for c in own)),
            "numbering": bool(own) and len(numbers) == 1,
        }
        rows.append({"loop": lp["id"], "measurement": meas_tag, "target": target_tag,
                     "checks": checks, "correct": all(checks.values()),
                     "printed_numbers": sorted(n for n in numbers if n)})
    names = ("measured", "controller", "signal", "numbering")
    return {"loops": len(rows), "correct": sum(r["correct"] for r in rows),
            "by_check": {n: sum(r["checks"][n] for r in rows) for n in names}, "rows": rows}


def naming_findings(table):
    """Tag problems visible without drawing anything: valve numbers and letters that don't match their loop."""
    out = []
    for lp in table["loops"]:
        if not lp["runs"] or lp["output"]["kind"] != "final_element":
            continue
        meas, valve = lp["measurement"]["tag"], lp["output"]["tag"]
        if _number_of(meas) != _number_of(valve):
            out.append(f"{valve} is moved by the loop that measures {meas}: different loop numbers")
        if valve[0] != meas[0]:
            out.append(f"{valve}'s first letter says {valve[0]} control, but its loop controls {meas} ({meas[0]})")
    return out


def describe(lp, table):
    if lp["output"]["kind"] == "final_element":
        return lp["output"]["tag"]
    inner = next(x for x in table["loops"] if x["id"] == lp["output"]["inner_loop"])
    return f"setpoint of {inner['id']} ({inner['measurement']['tag']})"


def report(table, check, result, key_path):
    lines = ["# Tennessee Eastman control loops: source, data check and drawing audit", "",
             f"Generated by `scripts/te_control_loops.py --check`. Source: `temain_mod.f` "
             f"(SHA-256 `{table['source']['sha256'][:16]}...`), the closed-loop code in the Braatz group's TE "
             "archive. Comments in that file are not used; several are copied between subroutines.", "",
             f"**{table['summary']['running']} loops run**: {table['summary']['valve_loops']} move a valve and "
             f"{table['summary']['cascades']} move another loop's setpoint. Defined but never called: "
             f"{', '.join(table['summary']['defined_not_called']) or 'none'}.", "",
             "| Loop | Measures | Moves | Mode | Scan | Line |", "|---|---|---|---|---|---|"]
    for lp in table["loops"]:
        if not lp["runs"]:
            continue
        meas = lp["measurement"]
        comp = f" ({meas['component']})" if "component" in meas else ""
        lines.append(f"| {lp['id']} | {meas['tag']}{comp}: {meas['description']} | {describe(lp, table)} | "
                     f"{lp['mode']} | {lp['scan_s']} s | {meas['line']} |")
    if table["overrides"]:
        first = table["overrides"][0]
        lines += ["", f"Override in {first['controller']}, checked before the controller runs (a latched trip with "
                      "a hand-back):", ""]
        for ov in table["overrides"]:
            when = f"after trip {ov['only_after_trip']}, " if ov["only_after_trip"] else ""
            lines.append(f"- line {ov['line']}: {when}when {ov['tag']} {ov['condition']}, the output is set to "
                         f"{ov['forces_output_to']:g}%")
    lines += ["", "## Do the recorded data follow these loops?", "",
              f"Coded setpoint against the measurement's mean over the {check['samples']} samples of "
              "`d00_te.dat` (normal operation). A wrong pairing would leave a measurement far from a setpoint "
              "it never tracked.", "", "| Loop | Tag | Setpoint | Mean | SD | |mean - setpoint| / SD |",
              "|---|---|---|---|---|---|"]
    for r in check["rows"]:
        lines.append(f"| {r['loop']} | {r['tag']} | {r['setpoint']:g} | {r['mean']:.4f} | {r['sd']:.4f} | "
                     f"{r['dev_sd']:.2f} |")
    worst = max(check["rows"], key=lambda r: r["dev_sd"])
    lines += ["", f"Largest deviation: {worst['loop']} ({worst['tag']}) at {worst['dev_sd']:.2f} SD. Loops whose "
              "setpoint a cascade moves can sit a little off their starting setpoint; that is expected.", "",
              f"## Drawing audit: `{key_path.as_posix()}`", "",
              f"**{result['correct']} of {result['loops']} loops drawn correctly.** Per check: "
              + ", ".join(f"{k} {v}/{result['loops']}" for k, v in result["by_check"].items()) + ".", "",
              "| Loop | Measurement | Should drive | measured | controller | signal | numbering |",
              "|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        c = r["checks"]
        lines.append(f"| {r['loop']} | {r['measurement']} | {r['target']} | "
                     + " | ".join("yes" if c[k] else "no" for k in ("measured", "controller", "signal",
                                                                     "numbering")) + " |")
    findings = naming_findings(table)
    if findings:
        lines += ["", "Tag problems the audit finds without any drawing:", ""] + [f"- {f}" for f in findings]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="write data/te_control_loops.json")
    ap.add_argument("--check", action="store_true", help="data check + drawing audit -> out/te_loop_audit.md")
    ap.add_argument("--write-model", action="store_true",
                    help="write the controllers into data/te_process_model.json (the model the drawing is made from)")
    ap.add_argument("--key", type=Path, default=KEY)
    args = ap.parse_args(argv)
    table = build()
    text = json.dumps(table, indent=1) + "\n"
    if args.write:
        LOOPS.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {LOOPS.relative_to(ROOT)}: {table['summary']}")
    elif LOOPS.exists() and LOOPS.read_text(encoding="utf-8") != text:
        print(f"{LOOPS.relative_to(ROOT)} differs from the source; rerun with --write")
        return 1
    if args.write_model:
        model = json.loads(MODEL.read_text(encoding="utf-8"))
        model["controllers"] = model_controllers(table, data_check(table))
        MODEL.write_text(json.dumps(model, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {len(model['controllers'])} controllers into {MODEL.relative_to(ROOT)}")
    if args.check:
        key_path = args.key if args.key.is_absolute() else ROOT / args.key
        result = audit(table, json.loads(key_path.read_text(encoding="utf-8")))
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report(table, data_check(table), result, key_path.relative_to(ROOT)),
                          encoding="utf-8", newline="\n")
        print(f"{result['correct']}/{result['loops']} loops drawn correctly; report {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
