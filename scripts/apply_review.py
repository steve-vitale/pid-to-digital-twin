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
  OPS_scope                optional identifier_text or valve_association; retains whole-record status
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
from generate import review_csv_cell

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
        if not v:  # "tag=" is a typo, not a request to blank the tag: refuse rather than erase a value
            return {}, f"'{k}=' has no value; give the corrected value, or reject the item instead"
        changes[k] = v
    return changes, None


def identifier_corrections(changes, item):
    """Text-only correction: preserve semantics, keep a matching derived loop in sync."""
    def parts(tag):
        # Same bounded ISA tag grammar as build_twin; no extraction/image dependencies.
        match = re.fullmatch(r"([A-Z]{1,6})[\s-]*([0-9][0-9A-Z]*(?:-[0-9A-Z]+)?)", str(tag or "").strip().upper())
        return match.groups() if match else (None, None)
    if set(changes) - {"tag", "description"} or "tag" not in changes:
        return {}, "identifier_text scope requires tag (and optional mirrored description) only"
    old_tag, new_tag = item.get("tag"), changes["tag"]
    old_letters, old_loop = parts(old_tag)
    letters, loop = parts(new_tag)
    if not old_loop or not loop or letters != old_letters or item.get("loop") != old_loop:
        return {}, "identifier_text requires unchanged letters and a matching existing derived loop"
    if "description" in changes and (item.get("description") != old_tag or changes["description"] != new_tag):
        return {}, "identifier_text can only update a description that exactly mirrors the tag"
    changes = dict(changes)
    changes["loop"] = loop
    if item.get("description") == old_tag:
        changes["description"] = new_tag
    return changes, None


def valve_association_corrections(changes, collection, item, ids):
    """Review an existing valve callout link, never merge symbols or infer valve function."""
    if collection != "instruments" or set(changes) != {"parent", "variable"} or changes["variable"] != "unknown":
        return {}, "valve_association requires an instrument callout with parent=<existing valve>;variable=unknown only"
    target_collection, target = ids.get(changes["parent"], (None, {}))
    if target_collection != "line_items" or target.get("class") != "valve" or item.get("parent") != changes["parent"]:
        return {}, "valve_association must refer to the existing parent valve; reassignment needs separate review"
    if "data_point" in item or "pi_point" in item:
        return {}, "valve_association cannot change an already mapped item; mapping requires separate review"
    return {"reviewed_valve_association": changes["parent"], "instrument_kind": "valve callout",
            "variable": "unknown", "variable_method": "reviewed unknown; source legend pending"}, None


def sync_hierarchy_tag(node, item_id, tag):
    """Refresh only this identifier's display cache; never rebuild inferred hierarchy."""
    if isinstance(node, dict):
        if node.get("id") == item_id and "tag" in node:
            node["tag"] = tag
        for child in node.get("children", []):
            sync_hierarchy_tag(child, item_id, tag)


def apply(model, rows, reviewer, today, ids):
    twin = model.get("meta", {}).get("model_kind") == "extracted_twin"
    log = {"applied": [], "unchanged": 0, "refused": [], "needs_moc": []}
    csv_ids = {}
    for key in ids:
        for spelling in (key, review_csv_cell(key)):
            csv_ids.setdefault(spelling, set()).add(key)
    for n, r in enumerate(rows, 2):
        item_id = (r.get("item_id") or "").strip()
        act = (r.get("OPS_confirm_or_correct") or "").strip().lower()
        show = (r.get("OPS_show_on_operator_screen_Y_N") or "").strip().upper()
        prio = (r.get("OPS_alarm_priority_H_M_L_none") or "").strip().lower()
        notes = (r.get("OPS_notes") or "").strip()
        if not (act or show or prio or notes):
            continue
        # Accept a raw identifier or its exported CSV text representation only when
        # it identifies exactly one record. Never guess across an encoding collision.
        matches = csv_ids.get(r.get("item_id"), csv_ids.get(item_id, set()))
        if len(matches) > 1:
            log["refused"].append({"row": n, "item": item_id, "reason": "ambiguous raw/CSV-encoded item_id"})
            continue
        if matches:
            item_id = next(iter(matches))
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
        scope = (r.get("OPS_scope") or "").strip()
        if scope and (scope not in {"identifier_text", "valve_association"} or not twin or ACTIONS.get(act) != "corrected" or show or prio):
            log["refused"].append({"row": n, "item": item_id, "reason": "invalid scope or action: scoped reviews require a twin correction without screen/alarm changes"})
            continue
        prev = item.get("ops_review") or {}
        # Only undo serialization of an unchanged known note, not a newly entered
        # literal apostrophe. Keep engineering text and repeat-review idempotence.
        previous_notes = prev.get("notes")
        if isinstance(previous_notes, str) and r.get("OPS_notes") == review_csv_cell(previous_notes):
            notes = previous_notes
        status = ACTIONS.get(act, prev.get("status", "unverified"))
        if status == "confirmed" and prev.get("status") == "corrected":
            status = "corrected"  # confirming a corrected item (as a regenerated sheet prints it) keeps the correction
        changes = {}
        if ACTIONS.get(act) == "corrected":  # only when the reviewer wrote "correct" on this row
            changes, err = parse_corrections(r.get("OPS_correct_value"), collection, item, twin)
            if err:
                log["refused"].append({"row": n, "item": item_id, "reason": err})
                continue
            if scope:
                changes, err = (identifier_corrections(changes, item) if scope == "identifier_text"
                                else valve_association_corrections(changes, collection, item, ids))
                if err:
                    log["refused"].append({"row": n, "item": item_id, "reason": err})
                    continue
                status = prev.get("status", "unverified")
            changes = {k: v for k, v in changes.items() if str(item.get(k)) != v}
            if "tag" in changes and item.get("tag_status") in ("placeholder", "missing"):
                # The tag now comes from a person, not the drawing: a corrected placeholder (or a supplied missing tag)
                # is no longer one, and the generators (review queue reason, SVG colour, point matching) read
                # tag_status, not the history. Scoped identifier corrections never reach here (they need a real tag).
                changes["tag_status"] = "reviewed"
        new = {"status": status, "show_on_screen": {"Y": True, "N": False}.get(show, prev.get("show_on_screen")),
               "alarm_priority": PRIORITY.get(prio, prev.get("alarm_priority")), "notes": notes or prev.get("notes")}
        same = all(prev.get(k) == v for k, v in new.items()) and not changes
        if same:
            log["unchanged"] += 1
            continue
        history = list(prev.get("history", []))
        history.append({"on": today, "by": reviewer, "decision": status,
                        "changes": {k: [item.get(k), v] for k, v in changes.items()}, "notes": notes or None})
        if scope:
            history[-1].update(decision="corrected", scope=scope, fields=sorted(changes))
        for k, v in changes.items():
            item[k] = v
        if scope and "tag" in changes:
            sync_hierarchy_tag(model.get("hierarchy"), item_id, changes["tag"])
        item["ops_review"] = {**prev, **new, "by": reviewer, "on": today, "history": history}
        if scope:
            fields = dict(prev.get("field_decisions", {}))
            for k in changes:
                fields[k] = {"status": "corrected", "by": reviewer, "on": today, "scope": scope, "notes": notes or None}
            item["ops_review"]["field_decisions"] = fields
        log["applied"].append({"item": item_id, "kind": collection, "decision": status,
                               "changes": {k: v for k, v in history[-1]["changes"].items()},
                               "show_on_screen": new["show_on_screen"], "alarm_priority": new["alarm_priority"],
                               "notes": notes or None})
        if scope:
            log["applied"][-1].update(decision="corrected", scope=scope, record_status=status)
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
    # Outside the repository, keep only the folder and file name: a change record gets shared, a home path shouldn't.
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else f"{path.parent.name}/{path.name}"


def write_record(log, model_path, reviewer, today, dry, rec_dir=None, source_paths=(), model_write=False):
    rec_dir = Path(rec_dir) if rec_dir else ROOT / "out" / "review"
    stem = f"{today}-{model_path.parent.name if model_path.name == 'plant_model.json' else model_path.stem}"
    if not dry:
        from output_paths import protect_outputs
        targets = [rec_dir / f"{stem}.md", rec_dir / f"{stem}.json"]
        protect_outputs(targets, [model_path, *source_paths])
        if model_write:
            protect_outputs([model_path, *targets], source_paths)
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
    if not dry:  # LF on every OS, so a record is byte-identical wherever it is made
        rec_dir.mkdir(parents=True, exist_ok=True)
        (rec_dir / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
        (rec_dir / f"{stem}.json").write_text(json.dumps({"model": rel(model_path),
                                                          "reviewer": reviewer, "date": today, **log}, indent=1),
                                              encoding="utf-8", newline="\n")
    return "\n".join(lines)


def main():
    if hasattr(sys.stdout, "reconfigure"):  # a Windows console is cp1252: print arrows and units, don't crash;
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="\n")  # and LF when redirected
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("sheet")
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--record-dir", default=None, help="where the change record goes (default out/review)")
    a = ap.parse_args()
    model_path = Path(a.model).resolve()
    try:
        raw = model_path.read_text(encoding="utf-8")
        model = json.loads(raw)
        with open(a.sheet, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except (OSError, ValueError, csv.Error) as exc:  # a missing or unreadable file: say which, no traceback
        ap.exit(2, f"review not applied; nothing written: {exc}\n")
    # Keep the file's own formatting, so the git diff shows only what the review changed.
    second = raw.splitlines()[1] if "\n" in raw else ""
    indent = len(second) - len(second.lstrip(" ")) or None
    ascii_only = raw.isascii()
    trailing = "\n" if raw.endswith("\n") else ""
    newline = "\r\n" if b"\r\n" in model_path.read_bytes() else "\n"  # read_text hides the line endings
    if "item_id" not in (reader.fieldnames or []):
        sys.exit("not a review sheet: no item_id column")
    if not rows:
        sys.exit("the review sheet has no rows: nothing to apply")
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
    try:
        print(write_record(log, model_path, a.reviewer, a.date, a.dry_run, a.record_dir,
                           source_paths=[a.sheet], model_write=bool(log['applied'])))
    except (ValueError, OSError) as exc:
        ap.exit(2, f"review not applied; nothing written: {exc}\n")
    if not a.dry_run and log["applied"]:
        model_path.write_text(json.dumps(model, indent=indent, ensure_ascii=ascii_only) + trailing, encoding="utf-8",
                              newline=newline)
        print(f"\nupdated {rel(model_path)}; now regenerate (scripts/generate.py)")
    sys.exit(1 if log["refused"] else 0)


if __name__ == "__main__":
    main()
