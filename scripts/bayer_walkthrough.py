"""Walk through the report's timeline beside the replayed overview screen.

python scripts/bayer_walkthrough.py            # writes out/bayer_rt/walkthrough.{json,md}
python scripts/bayer_walkthrough.py --check    # exit 1 if a check is unplaced or a derived change is unaccounted

For each event the report times on the evening (process_model.json events_2008_08_28, pp. 38-40), this takes the
replayed column nearest that time (data/bayer_rt/replay.csv: what the overview screen shows then) and the checks
that test the event (data/bayer_rt/walkthrough_steps.json names them): the figure-against-text checks
(out/bayer_rt/fig11_check.json) and the report-statement checks (out/bayer_rt/replay_states.json). Nothing is
derived again here; the walk-through only puts what is already checked in the report's order.

Two lists close it, so nothing the replay derives goes unaccounted:
- where the figure and the report's text disagree (the failed checks, with their recorded explanations);
- every change of an interlock or limit state that no report statement tests, with its time. These are not
  disagreements: the report doesn't time them.

Stdlib only.
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "bayer_rt" / "process_model.json"
STEPS = ROOT / "data" / "bayer_rt" / "walkthrough_steps.json"
RULES = ROOT / "data" / "bayer_rt" / "replay_rules.json"
REPLAY = ROOT / "data" / "bayer_rt" / "replay.csv"
FIG11 = ROOT / "out" / "bayer_rt" / "fig11_check.json"
STATES = ROOT / "out" / "bayer_rt" / "replay_states.json"
OUT_JSON = ROOT / "out" / "bayer_rt" / "walkthrough.json"
OUT_MD = ROOT / "out" / "bayer_rt" / "walkthrough.md"
TAGS = ["TI-104", "PI-101", "LI-102", "FI-103"]


def secs(t):
    t = t if t.count(":") == 2 else t + ":00"
    d = datetime.strptime(t, "%H:%M:%S")
    return d.hour * 3600 + d.minute * 60 + d.second


def load_rows():
    lines = [ln for ln in REPLAY.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def nearest(rows, t):
    """Index of the replayed column nearest a time; the earlier one on a tie."""
    return min(range(len(rows)), key=lambda i: (abs(secs(rows[i]["time"]) - secs(t)), i))


def unstated_changes(states, statements, rules):
    """Every interlock or limit state change that no report statement's derived time lands on."""
    tested = {(k["rule"], k["got"]) for k in statements if k.get("rule") and k.get("got")}
    names = {il["id"]: il["condition"] for il in rules["interlocks"]}
    names.update({lim["id"]: f"{lim['what']} ({lim['tag']})" for lim in rules["limits"]})
    out = []
    for group in ("interlocks", "limits"):
        for rid, runs in states[group].items():
            for prev, cur in zip(runs, runs[1:]):
                if prev["state"] == "no reading":
                    continue  # the figure's first column has no reading; its end is not a process change
                out.append({"rule": rid, "what": names[rid], "from": prev["state"], "to": cur["state"],
                            "time": cur["from"], "tested": (rid, cur["from"]) in tested})
    return sorted(out, key=lambda c: (secs(c["time"]), c["rule"]))


def build():
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    steps = json.loads(STEPS.read_text(encoding="utf-8"))["steps"]
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    fig11 = {c["name"]: c for c in json.loads(FIG11.read_text(encoding="utf-8"))["checks"]}
    states = json.loads(STATES.read_text(encoding="utf-8"))
    kchecks = {k["id"]: k for k in states["checks"]}
    for k in rules["report_statements"]:
        kchecks[k["id"]] = dict(kchecks[k["id"]], rule=k.get("rule"))
    rows = load_rows()
    events = {e["time"]: e for e in model["events_2008_08_28"]}
    out_steps = []
    for st in steps:
        e = events[st["event"]]
        i = nearest(rows, st["event"])
        r = rows[i]
        checks = [{"kind": "figure vs text", "id": n, "says": fig11[n]["source"], "stated": fig11[n]["stated"],
                   "got": fig11[n]["digitized"], "agrees": fig11[n]["ok"], "note": fig11[n]["note"]} for n in st["fig11"]]
        checks += [{"kind": "report statement", "id": k, "says": f"{kchecks[k]['statement']} ({kchecks[k]['source']})",
                    "stated": kchecks[k]["test"], "got": kchecks[k]["got"], "agrees": kchecks[k]["ok"], "note": None}
                   for k in st["replay"]]
        out_steps.append({
            "event": e["time"], "what": e["what"], "source": e["source"], "row": i, "screen_time": r["time"],
            "seconds_from_event": secs(r["time"]) - secs(e["time"]),
            "screen": {"values": {t: (float(r[t]) if r[t] else None) for t in TAGS},
                       "interlocks": {il["id"]: r[il["id"]] for il in rules["interlocks"]},
                       "limits": {lim["id"]: r[lim["id"]] for lim in rules["limits"]}},
            "checks": checks,
            "end_note": i == len(rows) - 1,
        })
    disagreements = [dict(c, event=s["event"]) for s in out_steps for c in s["checks"] if not c["agrees"]]
    unstated = unstated_changes(states, list(kchecks.values()), rules)
    return {"steps": out_steps, "disagreements": disagreements, "unstated_changes": unstated,
            "counts": {"events": len(out_steps), "checks": sum(len(s["checks"]) for s in out_steps),
                       "agree": sum(c["agrees"] for s in out_steps for c in s["checks"]),
                       "disagree": len(disagreements), "state_changes": len(unstated),
                       "state_changes_tested": sum(c["tested"] for c in unstated)}}, fig11, kchecks, events


def problems(w, fig11, kchecks, events):
    placed = [c["id"] for s in w["steps"] for c in s["checks"]]
    out = []
    for name in list(fig11) + list(kchecks):
        n = placed.count(name)
        if n != 1:
            out.append(f"check {name!r} is placed under {n} events (must be exactly 1)")
    for t in events:
        if t not in {s["event"] for s in w["steps"]}:
            out.append(f"report event {t} has no step")
    for s in w["steps"]:
        if abs(s["seconds_from_event"]) > 60:
            out.append(f"event {s['event']}: nearest replayed column {s['screen_time']} is over a minute away")
    return out


def render(w):
    c = w["counts"]
    L = ["# Walking through the report's timeline beside the replay", "",
         "Generated by `scripts/bayer_walkthrough.py`. Each event the report times on the evening (pp. 38-40) is paired "
         "with the replayed column nearest it (what the overview screen shows then) and with the checks that test it. "
         "Nothing is derived again here.", "",
         f"**{c['events']} events, {c['checks']} checks: {c['agree']} agree, {c['disagree']} disagree.** "
         f"{c['state_changes']} interlock or limit state changes in the replay; {c['state_changes_tested']} of them are "
         "tested by a report statement, and the rest are listed below.", ""]
    for s in w["steps"]:
        v = s["screen"]["values"]
        L += [f"## {s['event']}: {s['what']} ({s['source']})", "",
              f"Screen at {s['screen_time']}: " + ", ".join(f"{t} {'no reading' if v[t] is None else v[t]}" for t in TAGS)
              + "; interlocks " + ", ".join(f"{k} {x}" for k, x in s["screen"]["interlocks"].items()) + ".", ""]
        if s["end_note"]:
            L += ["The screen's end note shows here: the replay stops at the failure.", ""]
        L += ["| Check | Report says | Stated | Replay or figure | Agrees |", "|---|---|---|---|---|"]
        L += [f"| {k['id']} | {k['says']} | {k['stated']} | {k['got']} | {'yes' if k['agrees'] else 'NO'} |"
              for k in s["checks"]]
        if not s["checks"]:
            L += ["| | no check tests this event | | | |"]
        L += [""]
    L += ["## Where the figure and the report's text disagree", ""]
    L += [f"- **{d['event']}, {d['id']}.** Stated {d['stated']}, figure {d['got']}. {d['note'] or ''}".rstrip()
          for d in w["disagreements"]] or ["- none"]
    L += ["", "## State changes in the replay that no report statement tests", "",
          "Not disagreements: the report doesn't time these. Each is a change of a derived state, with the time of the "
          "first column in its new state.", "", "| Time | Rule | From | To |", "|---|---|---|---|"]
    L += [f"| {x['time']} | {x['rule']}: {x['what']} | {x['from']} | {x['to']} |"
          for x in w["unstated_changes"] if not x["tested"]]
    return "\n".join(L) + "\n"


def main(argv):
    w, fig11, kchecks, events = build()
    bad = problems(w, fig11, kchecks, events)
    if "--check" in argv:
        for p in bad:
            print("FAIL:", p)
        print(f"{w['counts']['agree']} of {w['counts']['checks']} checks agree; {len(bad)} problems")
        return 1 if bad else 0
    if bad:
        for p in bad:
            print("FAIL:", p)
        return 1
    OUT_JSON.write_text(json.dumps(w, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    OUT_MD.write_text(render(w), encoding="utf-8", newline="\n")
    c = w["counts"]
    print(f"{c['events']} events, {c['checks']} checks ({c['agree']} agree, {c['disagree']} disagree); "
          f"{c['state_changes'] - c['state_changes_tested']} of {c['state_changes']} state changes untested by the report")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
