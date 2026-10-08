"""Apply an operations review back to the asset model: the return half of the review loop.

The reviewer fills in the OPS_ columns of a review sheet (out/ops_review_sheet.csv for Tennessee Eastman, or a
twin's review_queue.csv) and hands it back. This script:
  1. checks every row against the model (unknown item, unknown field, missing correction value: refused, listed);
  2. writes each decision onto the item as `ops_review` (status, reviewer, date, notes, show on screen, alarm
     priority) and applies corrections, keeping every old value in `ops_review.history`;
  3. writes a dated change record (out/review/<date>-<model>.md and .json): what changed, who decided, what was
     refused, and requests that need a change review (MOC) instead of a direct edit.

The model file is updated in place. Version control is the change history, and the change record is the human-
readable summary. Run with --dry-run first to see what would change.

Reviewer's columns:
  OPS_confirm_or_correct   confirm | correct | reject (blank = not reviewed yet)
  OPS_correct_value        for "correct": field=value pairs separated by ";", e.g. "tag=FT-1401; uom=kg/h".
                           A bare value corrects the item's main field (the tag; for TE instruments the description).
  OPS_show_on_operator_screen_Y_N   Y | N (blank = no opinion)
  OPS_alarm_priority_H_M_L_none     H | M | L | none (blank = no opinion)
  OPS_notes                free text, kept with the decision

Re-applying the same sheet changes nothing. The generators print earlier decisions back into the OPS_ columns, so a
regenerated sheet picks up where the reviewer left off.

Usage:
  python scripts/apply_review.py <model.json> <reviewed.csv> --reviewer "Name, role" [--dry-run]
Then regenerate: python scripts/generate.py [<model.json>]  (and scripts/ignition/build_gateway.py for Ignition)
"""
import argparse
import csv
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = {"confirm": "confirmed", "confirmed": "confirmed", "ok": "confirmed", "y": "confirmed", "yes": "confirmed",
           "correct": "corrected", "corrected": "corrected", "fix": "corrected",
           "reject": "rejected", "rejected": "rejected", "remove": "rejected", "not real": "rejected"}
PRIORITY = {"h": "High", "high": "High", "m": "Medium", "medium": "Medium", "l": "Low", "low": "Low",
            "none": "none", "no": "none", "-": "none"}
EDITABLE = {"tag", "name", "description", "uom", "class", "unit", "parent", "from", "to", "variable", "text"}
COLLECTIONS = ("units", "instruments", "final_elements", "line_items", "offpage_connectors", "streams")


def index(model):
    """item id -> (collection, item). TE instruments are keyed by tag; everything else by id."""
    out = {}
    for c in COLLECTIONS:
        for it in model.get(c, []):
            key = it.get("id") or it.get("tag")
            out[key] = (c, it)
    return out


def main_field(collection, item, twin):
    if collection == "streams":
        return None
    if twin:
        return "tag"
    return "description" if collection in ("instruments", "final_elements") else "name"


def parse_corrections(text, collection, item, twin):
    text = (text or "").strip()
    if not text:
        return {}, "correct needs OPS_correct_value"
    if "=" not in text:
        f = main_field(collection, item, twin)
        return ({f: text}, None) if f else ({}, "connections take field=value (from=..., to=...)")
    changes = {}
    for part in [p for p in re.split(r";", text) if p.strip()]:
        if "=" not in part:
            return {}, f"cannot read '{part.strip()}' (use field=value)"
        k, v = [x.strip() for x in part.split("=", 1)]
        if k not in EDITABLE:
            return {}, f"field '{k}' can't be edited here (allowed: {', '.join(sorted(EDITABLE))})"
        changes[k] = v
    return changes, None


def apply(model, rows, reviewer, today, ids):
    twin = model.get("meta", {}).get("model_kind") == "extracted_twin"
    log = {"applied": [], "unchanged": 0, "refused": [], "needs_moc": []}
    for n, r in enumerate(rows, 2):
        item_id = (r.get("item_id") or "").strip()
        act = (r.get("OPS_confirm_or_correct") or "").strip().lower()
        show = (r.get("OPS_show_on_operator_screen_Y_N") or "").strip().upper()
        prio = (r.get("OPS_alarm_priority_H_M_L_none") or "").strip().lower()
        notes = (r.get("OPS_notes") or "").strip()
        if not (act or show or prio or notes):
            continue
        if item_id not in ids:
            log["refused"].append({"row": n, "item": item_id, "reason": "no such item in the model"})
            continue
        collection, item = ids[item_id]
        if act and act not in ACTIONS:
            log["refused"].append({"row": n, "item": item_id, "reason": f"unknown decision '{act}' (confirm/correct/reject)"})
            continue
        if prio and prio not in PRIORITY:
            log["refused"].append({"row": n, "item": item_id, "reason": f"unknown alarm priority '{prio}' (H/M/L/none)"})
            continue
        if show and show not in ("Y", "N"):
            log["refused"].append({"row": n, "item": item_id, "reason": f"show on screen must be Y or N, not '{show}'"})
            continue
        prev = item.get("ops_review") or {}
        status = ACTIONS.get(act, prev.get("status", "unverified"))
        if status == "confirmed" and prev.get("status") == "corrected":
            status = "corrected"  # confirming a corrected item (as a regenerated sheet prints it) keeps the correction
        changes = {}
        if ACTIONS.get(act) == "corrected":  # only when the reviewer wrote "correct" on this row
            changes, err = parse_corrections(r.get("OPS_correct_value"), collection, item, twin)
            if err:
                log["refused"].append({"row": n, "item": item_id, "reason": err})
                continue
            changes = {k: v for k, v in changes.items() if str(item.get(k)) != v}
        new = {"status": status, "show_on_screen": {"Y": True, "N": False}.get(show, prev.get("show_on_screen")),
               "alarm_priority": PRIORITY.get(prio, prev.get("alarm_priority")), "notes": notes or prev.get("notes")}
        same = all(prev.get(k) == v for k, v in new.items()) and not changes
        if same:
            log["unchanged"] += 1
            continue
        history = list(prev.get("history", []))
        history.append({"on": today, "by": reviewer, "decision": status,
                        "changes": {k: [item.get(k), v] for k, v in changes.items()}, "notes": notes or None})
        for k, v in changes.items():
            item[k] = v
        item["ops_review"] = {**new, "by": reviewer, "on": today, "history": history}
        log["applied"].append({"item": item_id, "kind": collection, "decision": status,
                               "changes": {k: v for k, v in history[-1]["changes"].items()},
                               "show_on_screen": new["show_on_screen"], "alarm_priority": new["alarm_priority"],
                               "notes": notes or None})
        # Requests the reviewer can make but that must not be applied silently: they change what alarms exist.
        has_alarm = bool(item.get("alarm_setpoints"))  # TE alarm setpoints live in build_gateway.ALARMS
        asked = PRIORITY.get(prio)
        if asked and collection in ("instruments", "final_elements", "units"):
            if asked == "none" and has_alarm:
                log["needs_moc"].append({"item": item_id, "request": "remove alarm",
                                         "why": "removing a published alarm is a change review (MOC), not an edit; "
                                                "the alarm stays"})
            elif asked != "none" and not has_alarm:
                log["needs_moc"].append({"item": item_id, "request": f"new {asked} alarm",
                                         "why": "no published setpoint exists; a new alarm needs one set and approved "
                                                "through a change review, so none is created"})
    return log


def rel(path):
    path = Path(path)
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


def write_record(log, model_path, reviewer, today, dry, rec_dir=None):
    rec_dir = Path(rec_dir) if rec_dir else ROOT / "out" / "review"
    rec_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{today}-{model_path.parent.name if model_path.name == 'plant_model.json' else model_path.stem}"
    lines = [f"# Review applied: {rel(model_path)}", "",
             f"Reviewer: {reviewer} · Date: {today}{' · DRY RUN (nothing written)' if dry else ''}", "",
             f"Applied: {len(log['applied'])} · Unchanged: {log['unchanged']} · Refused: {len(log['refused'])} · "
             f"Need a change review: {len(log['needs_moc'])}", ""]
    if log["applied"]:
        lines += ["## Applied", "", "| Item | Decision | Changes | Screen | Alarm priority | Notes |", "|---|---|---|---|---|---|"]
        for a in log["applied"]:
            ch = "; ".join(f"{k}: {o!r} → {v!r}" for k, (o, v) in a["changes"].items()) or ""
            scr = {True: "show", False: "hide", None: ""}[a["show_on_screen"]]
            lines.append(f"| {a['item']} | {a['decision']} | {ch} | {scr} | {a['alarm_priority'] or ''} | {a['notes'] or ''} |")
        lines.append("")
    if log["refused"]:
        lines += ["## Refused (fix the sheet and re-apply)", "", "| Row | Item | Reason |", "|---|---|---|"]
        lines += [f"| {r['row']} | {r['item']} | {r['reason']} |" for r in log["refused"]] + [""]
    if log["needs_moc"]:
        lines += ["## Needs a change review (not applied to alarms)", "", "| Item | Request | Why |", "|---|---|---|"]
        lines += [f"| {m['item']} | {m['request']} | {m['why']} |" for m in log["needs_moc"]] + [""]
    if not dry:
        (rec_dir / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")
        (rec_dir / f"{stem}.json").write_text(json.dumps({"model": rel(model_path),
                                                          "reviewer": reviewer, "date": today, **log}, indent=1),
                                              encoding="utf-8")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("sheet")
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--record-dir", default=None, help="where the change record goes (default out/review)")
    a = ap.parse_args()
    model_path = Path(a.model).resolve()
    raw = model_path.read_text(encoding="utf-8")
    model = json.loads(raw)
    # Keep the file's own formatting, so the git diff shows only what the review changed.
    second = raw.splitlines()[1] if "\n" in raw else ""
    indent = len(second) - len(second.lstrip(" ")) or None
    ascii_only = raw.isascii()
    trailing = "\n" if raw.endswith("\n") else ""
    rows = list(csv.DictReader(open(a.sheet, encoding="utf-8-sig", newline="")))
    if "item_id" not in (rows[0] if rows else {}):
        sys.exit("not a review sheet: no item_id column")
    # TE alarm setpoints come from the gateway build; mark which TE items carry one so requests are judged right.
    try:
        sys.path.insert(0, str(ROOT / "scripts" / "ignition"))
        from build_gateway import ALARMS
        for c in ("instruments", "final_elements"):
            for it in model.get(c, []):
                if it.get("tag") in ALARMS:
                    it["alarm_setpoints"] = [x["setpointA"] for x in ALARMS[it["tag"]]]
    except Exception:  # noqa: BLE001  (twin models have no published setpoints)
        pass
    log = apply(model, rows, a.reviewer, a.date, index(model))
    for c in ("instruments", "final_elements"):
        for it in model.get(c, []):
            it.pop("alarm_setpoints", None)
    print(write_record(log, model_path, a.reviewer, a.date, a.dry_run, a.record_dir))
    if not a.dry_run and log["applied"]:
        model_path.write_text(json.dumps(model, indent=indent, ensure_ascii=ascii_only) + trailing, encoding="utf-8")
        print(f"\nupdated {rel(model_path)}; now regenerate (scripts/generate.py)")
    sys.exit(1 if log["refused"] else 0)


if __name__ == "__main__":
    main()
