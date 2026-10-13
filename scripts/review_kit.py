"""Timed-review kit: one drawing's review queue, a timer log, and a summary. No measured result is shipped.

This prepares the first real measurement of review effort described in docs/REVIEW_EFFORT_PROTOCOL.md. It does not
make one. Minutes come only from a person running the timer while reviewing.

  python scripts/review_kit.py make --twin out/twin/r2-tiles-trace/codex --sheet 8 --out out/review_kit/sheet-8
      Copies the sheet's rows of review_queue.csv (OPS_ columns blank), the drawing, the twin's overlay SVG,
      an empty timer log, a manifest with SHA-256 of every packet file, and a draft protocol for
      review_effort.py whose study-specific fields are left blank on purpose (it fails validation until an
      administrator completes and freezes it).
  python scripts/review_kit.py timer start|pause|resume|stop --kit out/review_kit/sheet-8 --reviewer R1 [--note ...]
      Appends one UTC timestamp row to timer_log.csv. Nothing else is recorded about the reviewer.
  python scripts/review_kit.py summarize --kit out/review_kit/sheet-8 --queue <filled review_queue.csv>
      Active minutes (start/resume to pause/stop), rows decided, decisions by kind, minutes per row and per
      correction. Refuses an unfinished or out-of-order timer log, and a queue whose rows differ from the packet.

Rules the summary keeps: unanswered rows are reported, not treated as confirmed; a pause is not active time; a
summary is a pilot observation by one reviewer on one drawing, not a comparison with manual work and not a
critical-error audit. The independent audit and the baseline arm are separate steps in the protocol.
"""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMER_FIELDS = ["utc", "event", "reviewer", "note"]
EVENTS = ("start", "pause", "resume", "stop")
DECISIONS = ("confirm", "correct", "reject")
OPS_COLUMNS = ("OPS_confirm_or_correct", "OPS_correct_value", "OPS_show_on_operator_screen_Y_N",
               "OPS_alarm_priority_H_M_L_none", "OPS_notes")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_queue(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def make(twin, sheet, out, drawing_dir):
    twin, out = Path(twin), Path(out)
    fields, rows = read_queue(twin / "review_queue.csv")
    mine = [r for r in rows if r.get("sheet") == str(sheet)]
    if not mine:
        raise ValueError(f"no review-queue rows for sheet {sheet}")
    for r in mine:
        for c in OPS_COLUMNS:
            r[c] = ""
    out.mkdir(parents=True, exist_ok=True)
    queue = out / f"review_queue_sheet{sheet}.csv"
    with open(queue, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(mine)
    shutil.copyfile(Path(drawing_dir) / f"{sheet}.png", out / f"drawing_sheet{sheet}.png")
    # LF line endings whatever the checkout's own, so the manifest hashes match on every OS (.gitattributes keeps
    # the committed packet byte-for-byte).
    svg = (twin / "svg" / f"sheet_{sheet}.svg").read_bytes().replace(b"\r\n", b"\n")
    (out / f"extracted_overlay_sheet{sheet}.svg").write_bytes(svg)
    with open(out / "timer_log.csv", "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow(TIMER_FIELDS)
    tiers = {t: sum(1 for r in mine if r.get("tier") == t) for t in ("red", "amber", "green")}
    files = sorted(p.name for p in out.iterdir() if p.name not in ("manifest.json", "timer_log.csv",
                                                                     "protocol_draft.json", "README.md"))
    try:
        source = twin.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        source = twin.name   # outside the repository: keep only the folder name, never a local path
    manifest = {"sheet": str(sheet), "source_twin": source, "rows": len(mine), "tiers": tiers,
                "item_types": {t: sum(1 for r in mine if r.get("item_type") == t)
                               for t in sorted({r.get("item_type") for r in mine})},
                "files": {name: sha(out / name) for name in files}}
    manifest["source_bundle_sha256"] = hashlib.sha256(
        json.dumps(manifest["files"], sort_keys=True).encode()).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (out / "protocol_draft.json").write_text(json.dumps(protocol_draft(sheet, manifest), indent=1), encoding="utf-8")
    return manifest


def protocol_draft(sheet, manifest):
    """A review_effort.py protocol with the kit's fixed design drafted and study-specific fields left blank."""
    return {
        "schema": "review-effort-1", "study_id": "", "synthetic": False, "frozen_at": None,
        "baseline_workflow": "",
        "assisted_workflow": (f"Review the extracted draft for OPEN100 sheet {sheet}: one row per item in "
                              f"review_queue_sheet{sheet}.csv ({manifest['rows']} rows), riskiest first, using the "
                              "drawing and the overlay SVG in this packet. Fill the OPS_ columns as described in "
                              "docs/REVIEW_LOOP.md. Draft produced by the declared method M3 (GPT, 2x2 tiles + code "
                              "line tracing); no re-extraction during the review."),
        "task_definition": (f"Deliverable: every row of the sheet {sheet} review queue has a decision (confirm, "
                            "correct with a value, or reject). Rows left blank are reported as unanswered. Items the "
                            "draft missed entirely are not in the queue; noting them in OPS_notes of the nearest "
                            "row is allowed and counted separately."),
        "timing_rule": ("Active minutes only, from timer start to stop with pauses excluded "
                        "(scripts/review_kit.py timer). Reading these instructions is before start. Breaks and "
                        "interruptions are paused. The timer is never stopped early in one arm only."),
        "assignment_rule": "",
        "analysis_plan": "",
        "critical_error_rubric": "",
        "quality_acceptance_rule": "",
        "exclusion_rule": "",
        "sample_size_rationale": "",
        "eligible_information_rule": (f"The reviewer sees only the packet files listed in manifest.json (drawing, "
                                      "overlay, queue). The answer key (.graphml) is withheld from the reviewer "
                                      "and used only by the independent auditor."),
        "tasks": [{"task_id": f"open100-sheet-{sheet}", "source_bundle_sha256": manifest["source_bundle_sha256"],
                   "truth_reference": f"PID2Graph OPEN100 {sheet}.graphml (symbols and links only; no tag text)"}],
        "assignments": [],
        "_kit_note": ("Blank fields are the administrator's decisions (baseline workflow, assignment, rubric, "
                      "acceptance rule, exclusions, sample size). review_effort.py validate refuses this file "
                      "until they are filled, frozen and given both arms with different reviewers."),
    }


def timer(kit, event, reviewer, note="", now=None):
    if event not in EVENTS:
        raise ValueError(f"event must be one of {EVENTS}")
    log = Path(kit) / "timer_log.csv"
    if not log.exists():
        raise ValueError(f"{log} not found; run make first")
    rows = read_timer(log)
    last = rows[-1]["event"] if rows else None
    allowed = {None: ("start",), "start": ("pause", "stop"), "resume": ("pause", "stop"), "pause": ("resume", "stop"),
               "stop": ()}
    if event not in allowed[last]:
        raise ValueError(f"'{event}' cannot follow '{last or 'nothing'}'")
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    with open(log, "a", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow([stamp, event, reviewer, note])
    return stamp


def read_timer(log):
    with open(log, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def active_minutes(rows):
    """Sum of start/resume -> pause/stop intervals. Requires a complete, ordered log ending in stop."""
    if not rows or rows[0]["event"] != "start" or rows[-1]["event"] != "stop":
        raise ValueError("timer log must begin with start and end with stop")
    total, running_since, pauses = 0.0, None, 0
    previous = None
    for r in rows:
        t = datetime.fromisoformat(r["utc"])
        if previous and t < previous:
            raise ValueError("timer log goes backwards in time")
        previous = t
        if r["event"] in ("start", "resume"):
            if running_since is not None:
                raise ValueError("timer started twice without a pause")
            running_since = t
        else:
            if r["event"] == "pause":
                pauses += 1
            if running_since is not None:
                total += (t - running_since).total_seconds()
            running_since = None
    return round(total / 60, 2), pauses


def summarize(kit, queue_path):
    kit = Path(kit)
    manifest = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    minutes, pauses = active_minutes(read_timer(kit / "timer_log.csv"))
    reviewers = sorted({r["reviewer"] for r in read_timer(kit / "timer_log.csv")})
    _, rows = read_queue(queue_path)
    _, packet = read_queue(next(kit.glob("review_queue_sheet*.csv")))
    if [r["item_id"] for r in rows] != [r["item_id"] for r in packet]:
        raise ValueError("filled queue rows differ from the packet (added, removed or reordered rows)")
    counts = {d: 0 for d in DECISIONS}
    unanswered, unreadable = 0, 0
    for r in rows:
        d = (r.get("OPS_confirm_or_correct") or "").strip().lower()
        if not d:
            unanswered += 1
        elif d in counts:
            counts[d] += 1
        else:
            unreadable += 1
    decided = sum(counts.values())
    changes = counts["correct"] + counts["reject"]
    return {"label": "PILOT OBSERVATION: one reviewer, one drawing; not a comparison with manual work, not an audit",
            "sheet": manifest["sheet"], "rows": manifest["rows"], "reviewers_in_log": reviewers,
            "active_minutes": minutes, "pauses": pauses, "decided": decided, "decisions": counts,
            "unanswered": unanswered, "unreadable_decisions": unreadable,
            "minutes_per_decided_row": round(minutes / decided, 3) if decided else None,
            "minutes_per_correction_or_rejection": round(minutes / changes, 3) if changes else None,
            "source_bundle_sha256": manifest["source_bundle_sha256"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--twin", default="out/twin/r2-tiles-trace/codex")
    m.add_argument("--sheet", default="8")
    m.add_argument("--out", required=True)
    m.add_argument("--drawings", default="data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100")
    t = sub.add_parser("timer")
    t.add_argument("event", choices=EVENTS)
    t.add_argument("--kit", required=True)
    t.add_argument("--reviewer", required=True, help="a pseudonymous role id such as R1, never a name")
    t.add_argument("--note", default="")
    s = sub.add_parser("summarize")
    s.add_argument("--kit", required=True)
    s.add_argument("--queue", required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "make":
            print(json.dumps(make(ROOT / a.twin, a.sheet, ROOT / a.out, ROOT / a.drawings), indent=1))
        elif a.cmd == "timer":
            print(f"{a.event} at {timer(a.kit, a.event, a.reviewer, a.note)}")
        else:
            print(json.dumps(summarize(a.kit, a.queue), indent=1))
        return 0
    except (ValueError, OSError, StopIteration) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
