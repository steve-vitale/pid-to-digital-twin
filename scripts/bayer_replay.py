"""The Bayer residue treater replayed: the digitized Figure 11 trend run through the model's interlocks and limits.

python scripts/bayer_replay.py            # writes data/bayer_rt/replay.csv and out/bayer_rt/replay_states.{json,md}
python scripts/bayer_replay.py --check    # exit 1 if the committed outputs are stale

Input: data/bayer_rt/fig11_digitized.csv (one row per pixel column, about 32 s apart, with each series' column range
and the digitizing error) and data/bayer_rt/replay_rules.json (every interlock and limit, cited to the report).

For each column up to the failure at 22:33, every tag gets a value and bounds (the column range widened by the
digitizing error). Each interlock condition is then:
  met         the whole bound is on the condition's side of the bound the report supports (the feed valve would be
              held closed, if the interlock weren't bypassed)
  clear       the whole bound is on the other side
  cannot tell the bound straddles the gap between them, or the setpoint lies in that gap, or the tag has no reading
Each operating limit is crossed / not crossed / cannot tell the same way.

Then the derived states are checked against the report's own statements about the evening (pump start, flow loss,
high-pressure alarm, relief valve, safe operating limit). Agreement and disagreement are both written up; nothing is
tuned to agree. Stdlib only.
"""
import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import digitize_bayer_fig11 as dg  # noqa: E402  (stdlib at import)

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "data" / "bayer_rt" / "replay_rules.json"
REPLAY = ROOT / "data" / "bayer_rt" / "replay.csv"
OUT = ROOT / "out" / "bayer_rt"
MET, CLEAR, UNSURE, NONE = "met", "clear", "cannot tell", "no reading"


def error_bounds():
    """The pixel-error bound per series, as the digitizer wrote it in the CSV header."""
    head = next(ln for ln in dg.CSV_OUT.read_text(encoding="utf-8").splitlines() if ln.startswith("# Date"))
    items = head.split("(+/-): ")[1].split(". _min")[0].split(", ")
    return {k: float(v) for k, v in (item.rsplit(" ", 1) for item in items)}


def hhmm(t):
    return datetime.strptime(t, "%H:%M:%S")


def replay_rows(rules):
    err = error_bounds()
    end = hhmm(rules["replay_ends"]["time"])
    out = []
    for r in dg.load_rows():
        if hhmm(r["time"]) > end:
            break
        row = {"time": r["time"]}
        for tag, series in rules["series_tags"].items():
            if r[series] == "":
                row[tag] = row[f"{tag}_lo"] = row[f"{tag}_hi"] = None
                continue
            e = err[series]
            row[tag] = float(r[series])
            row[f"{tag}_lo"] = round(float(r[series + "_min"]) - e, 2)
            row[f"{tag}_hi"] = round(float(r[series + "_max"]) + e, 2)
        out.append(row)
    return out


def interlock_state(il, row):
    lo, hi = row[f"{il['tag']}_lo"], row[f"{il['tag']}_hi"]
    if lo is None:
        return NONE
    if "met_if_below" in il:                          # met when low
        return MET if hi < il["met_if_below"] else CLEAR if lo >= il["clear_if_at_or_above"] else UNSURE
    if "met_if_at_or_below" in il:
        return MET if hi <= il["met_if_at_or_below"] else CLEAR if lo >= il["clear_if_at_or_above"] else UNSURE
    return MET if lo >= il["met_if_at_or_above"] else CLEAR if hi < il["clear_if_below"] else UNSURE


def limit_state(lim, row):
    lo, hi = row[f"{lim['tag']}_lo"], row[f"{lim['tag']}_hi"]
    if lo is None:
        return NONE
    if "at_or_above" in lim:
        return "crossed" if lo >= lim["at_or_above"] else "not crossed" if hi < lim["at_or_above"] else UNSURE
    return "crossed" if hi < lim["below"] else "not crossed" if lo >= lim["below"] else UNSURE


def derive(rules):
    rows = replay_rows(rules)
    for row in rows:
        for il in rules["interlocks"]:
            row[il["id"]] = interlock_state(il, row)
        for lim in rules["limits"]:
            row[lim["id"]] = limit_state(lim, row)
    return rows


def transitions(rows, key):
    """Runs of one state, ignoring single 'no reading' columns inside a run."""
    runs = []
    for row in rows:
        s = row[key]
        if s == NONE and runs:
            continue
        if not runs or runs[-1]["state"] != s:
            runs.append({"state": s, "from": row["time"], "to": row["time"]})
        else:
            runs[-1]["to"] = row["time"]
    return runs


def minutes(a, b):
    return (hhmm(a) - hhmm(b)).total_seconds() / 60


def check(stmt, rows):
    after = [r for r in rows if r["time"] >= stmt.get("first_after", "00:00:00")]
    if "rule" in stmt and "from" in stmt:
        prev = None
        for r in after:
            s = r[stmt["rule"]]
            if s == NONE:
                continue
            if prev == stmt["from"] and s != stmt["from"]:
                got = r["time"]
                break
            prev = s
        else:
            return {"got": None, "ok": False}
        if "expect" in stmt:
            d = minutes(got, stmt["expect"])
            return {"got": got, "minutes_off": round(d, 1), "ok": abs(d) <= stmt["tolerance_min"]}
        return {"got": got, "ok": hhmm(got) < hhmm(stmt["before"])}
    if "rule" in stmt and "to" in stmt:
        got = next((r["time"] for r in after if r[stmt["rule"]] == stmt["to"]), None)
        if got is None:
            return {"got": None, "ok": False}
        d = minutes(got, stmt["expect"])
        return {"got": got, "minutes_off": round(d, 1), "ok": abs(d) <= stmt["tolerance_min"]}
    if "peak_of" in stmt:
        tag = stmt["peak_of"]
        vals = [(r["time"], r[tag]) for r in after if r[tag] is not None]
        for i in range(1, len(vals) - 1):
            if vals[i][1] > vals[i - 1][1] and vals[i][1] >= vals[i + 1][1] + 0.27:   # falls by more than the error
                got = vals[i][0]
                d = minutes(got, stmt["expect"])
                return {"got": got, "value": vals[i][1], "minutes_off": round(d, 1), "ok": abs(d) <= stmt["tolerance_min"]}
        return {"got": None, "ok": False}
    if stmt.get("never"):
        hit = next((r["time"] for r in rows if r[stmt["limit"]] == "crossed"), None)
        peak = max(r["TT-104"] for r in rows if r["TT-104"] is not None)
        return {"got": hit or f"never (highest {peak} C)", "ok": hit is None}
    raise ValueError(f"statement {stmt['id']}: no test of a known shape")


def summarize(rules, rows):
    res = {"rows": len(rows), "from": rows[0]["time"], "to": rows[-1]["time"],
           "interlocks": {il["id"]: transitions(rows, il["id"]) for il in rules["interlocks"]},
           "limits": {lim["id"]: transitions(rows, lim["id"]) for lim in rules["limits"]},
           "checks": []}
    for stmt in rules["report_statements"]:
        res["checks"].append({"id": stmt["id"], "statement": stmt["statement"], "source": stmt["source"],
                              "test": stmt["test"], **check(stmt, rows)})
    res["checks_passed"] = sum(c["ok"] for c in res["checks"])
    return res


def render(rules, res):
    il_by = {il["id"]: il for il in rules["interlocks"]}
    lim_by = {lim["id"]: lim for lim in rules["limits"]}
    out = ["# The residue treater replayed through its interlocks and limits",
           "",
           "Generated by `scripts/bayer_replay.py` from the digitized Figure 11 (`data/bayer_rt/fig11_digitized.csv`) "
           "and the cited rules in `data/bayer_rt/replay_rules.json`. "
           f"{res['rows']} columns from {res['from']} to {res['to']}; the replay stops at the failure, 22:33.",
           "",
           "**What a state means.** A value's bounds are its column range in the figure widened by the digitizing "
           "error. An interlock condition is *met* (the condition the interlock acts on is true; its design action is "
           "to hold the feed valve closed, p. 30) or *clear* only when the whole bound is on one side of the bound the report supports; "
           "otherwise *cannot tell*. The report publishes no interlock setpoints, so each rule says which pages "
           "bound it.",
           "",
           f"**{res['checks_passed']} of {len(res['checks'])} checks against the report's own statements agree.**",
           "",
           "| | Report says | Test | Replay gives | Agrees |",
           "|---|---|---|---|---|"]
    for c in res["checks"]:
        got = c["got"] if c["got"] else "not found"
        if c.get("minutes_off") is not None:
            got += f" ({c['minutes_off']:+} min)"
        out.append(f"| {c['id']} | {c['statement']} ({c['source']}) | {c['test']} | {got} | "
                   f"{'yes' if c['ok'] else 'NO'} |")
    out += ["", "## Interlock conditions over the evening", ""]
    for iid, runs in res["interlocks"].items():
        il = il_by[iid]
        out += [f"**{iid}: {il['condition']}.** As operated: {il['as_operated']}.", ""]
        out += [f"- {r['from']} to {r['to']}: {r['state']}" for r in runs]
        out += ["", f"Bounds: {il['why_these_bounds']}", ""]
    out += ["## Operating limits", ""]
    for lid, runs in res["limits"].items():
        lim = lim_by[lid]
        out += [f"**{lim['what']}** ({lim['tag']}, {lim.get('at_or_above', lim.get('below'))}; {lim['source']}): "
                + "; ".join(f"{r['from']}-{r['to']} {r['state']}" for r in runs), ""]
    return "\n".join(out) + "\n"


def write_csv(rules, rows):
    tags = list(rules["series_tags"])
    cols = ["time"] + [f"{t}{s}" for t in tags for s in ("", "_lo", "_hi")] \
        + [il["id"] for il in rules["interlocks"]] + [lim["id"] for lim in rules["limits"]]
    lines = ["# Residue treater replay from the digitized Figure 11 (CSB report, p. 39), by scripts/bayer_replay.py. "
             "Tags are this project's (data/bayer_rt/process_model.json). _lo/_hi: the column range widened by the "
             "digitizing error. Interlock and limit states from data/bayer_rt/replay_rules.json. Ends at the "
             "failure, 22:33.",
             ",".join(cols)]
    for r in rows:
        lines.append(",".join("" if r.get(c) is None else str(r[c]) for c in cols))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed outputs are stale")
    a = ap.parse_args()
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    rows = derive(rules)
    res = summarize(rules, rows)
    files = {REPLAY: write_csv(rules, rows), OUT / "replay_states.json": json.dumps(res, indent=1) + "\n",
             OUT / "replay_states.md": render(rules, res)}
    if a.check:
        stale = [p.name for p, txt in files.items() if not p.exists() or p.read_text(encoding="utf-8") != txt]
        if stale:
            sys.exit(f"stale: {stale}; run python scripts/bayer_replay.py")
        print("replay outputs are current")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for p, txt in files.items():
        p.write_text(txt, encoding="utf-8", newline="\n")
    print(f"{res['rows']} columns {res['from']}-{res['to']}; {res['checks_passed']} of {len(res['checks'])} "
          f"report checks agree")
    for c in res["checks"]:
        print(f"  {c['id']} {'ok  ' if c['ok'] else 'FAIL'} {c['test']}: {c['got']}")
    for iid, runs in res["interlocks"].items():
        print(f"  {iid}: " + "; ".join(f"{r['from']}-{r['to']} {r['state']}" for r in runs))


if __name__ == "__main__":
    main()
