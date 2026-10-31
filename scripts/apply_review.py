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
import ast
import csv
import datetime
import hashlib
import json
import math
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
NATIVE_TAGS = ("instruments", "final_elements")


def index(model):
    """Review identity -> record. Native instruments/outputs use tag, including those with auxiliary ids."""
    out = {}
    twin = model.get("meta", {}).get("model_kind") == "extracted_twin"
    for c in COLLECTIONS:
        for it in model.get(c, []):
            key = it.get("tag") if not twin and c in NATIVE_TAGS else it.get("id") or it.get("tag")
            if not isinstance(key, str) or not key or key in out:
                raise ValueError(f"missing or duplicate review identity: {key!r}")
            out[key] = (c, it)
    return out


def review_lookup(ids, twin):
    """Freeze targets for the whole sheet; historical names permit only unchanged replay."""
    current, historical = {}, {}
    def add(table, name, key):
        if isinstance(name, str) and name:
            for spelling in (name, review_csv_cell(name)):
                table.setdefault(spelling, set()).add(key)
    for key, (collection, item) in ids.items():
        add(current, key, key)
        if not twin and collection in NATIVE_TAGS:
            add(current, item.get("id"), key)
            for event in (item.get("ops_review") or {}).get("history", []):
                pair = (event.get("changes") or {}).get("tag")
                if isinstance(pair, list) and len(pair) == 2:
                    for name in pair:
                        add(historical, name, key)
    all_names = {name: current.get(name, set()) | historical.get(name, set())
                 for name in current.keys() | historical.keys()}
    return all_names, current


def native_namespace(model):
    """Exact live graph identities, separate from auxiliary ids and historical/source text."""
    entries = [("PLANT", None), ("BL", None)]
    for group, field in (("units", "id"), ("instruments", "tag"), ("final_elements", "tag"),
                         ("controllers", "tag"), ("manual_valves", "tag"), ("relief_devices", "tag"),
                         ("interlocks", "id"), ("unplaced", "tag")):
        entries += [(it[field], it) for it in model.get(group, [])]
    entries += [(f"stream:{it['id']}", it) for it in model.get("streams", [])]
    entries += [(it.get("id") or f"LIM-{i}", it) for i, it in enumerate(model.get("limits", []), 1)]
    for group in ("junctions", "networks"):
        entries += [(it["id"], it) for it in (model.get("line_layers") or {}).get(group, [])]
    names = {}
    for name, item in entries:
        if not isinstance(name, str) or not name or name.casefold() in names:
            raise ValueError(f"missing or ambiguous native graph identity: {name!r}")
        names[name.casefold()] = item
    auxiliary = {}
    for group in NATIVE_TAGS:
        for item in model.get(group, []):
            alias = item.get("id")
            if alias:
                if not isinstance(alias, str) or alias.casefold() in auxiliary:
                    raise ValueError(f"ambiguous native auxiliary identity: {alias!r}")
                auxiliary[alias.casefold()] = item
    return names


def native_references(model, collection, old, new):
    """Plan only supported live references. No source prose, history, point address or geometry edits."""
    plan = []
    def slot(obj, key, path, many=False):
        value = obj.get(key)
        if value is None or value == "" or value == []:
            return
        if many and isinstance(value, list):
            if any(not isinstance(v, str) for v in value):
                raise ValueError(f"unsupported reference shape: {path}")
            for i, v in enumerate(value):
                if v == old:
                    plan.append((value, i, f"{path}[{i}]", v, new))
        elif isinstance(value, str) and many != "list":
            if value == old:
                plan.append((obj, key, path, value, new))
        else:
            raise ValueError(f"unsupported reference shape: {path}")
    for i, controller in enumerate(model.get("controllers", [])):
        prefix = f"controllers[{i}]"
        if collection == "instruments":
            slot(controller, "measurement", prefix + ".measurement")
            slot(controller, "measurement_unplaced", prefix + ".measurement_unplaced", True)
        else:
            output = controller.get("output") or {}
            if not isinstance(output, dict):
                raise ValueError(f"unsupported reference shape: {prefix}.output")
            slot(output, "final_element", prefix + ".output.final_element")
            slot(output, "split_range", prefix + ".output.split_range", "list")
            slot(controller, "output_unplaced", prefix + ".output_unplaced", True)
    for i, interlock in enumerate(model.get("interlocks", [])):
        field = "measurement" if collection == "instruments" else "final_element"
        slot(interlock, field, f"interlocks[{i}].{field}")
    for i, limit in enumerate(model.get("limits", [])):
        slot(limit, "tag", f"limits[{i}].tag")
    layers = model.get("line_layers") or {}
    for i, network in enumerate(layers.get("networks", [])):
        slot(network, "members", f"line_layers.networks[{i}].members", "list")
    for group in ("segments", "instrument_lines", "actuator_stems", "nozzle_stubs"):
        for i, segment in enumerate(layers.get(group, [])):
            for field in ("from", "to"):
                slot(segment, field, f"line_layers.{group}[{i}].{field}")
    return plan


def rename_conflicts(model, rows, ids, lookup):
    """Original-sheet targets only. Refuse chains/swaps, colliding destinations and contradictory edits."""
    namespace = native_namespace(model)
    conflicts, planned, edits = {}, {}, {}
    auxiliary = {it.get("id"): key for key, (_, it) in ids.items() if it.get("id")}
    for row in rows:
        matches = lookup.get(row.get("item_id"), lookup.get((row.get("item_id") or "").strip(), set()))
        if len(matches) != 1 or ACTIONS.get((row.get("OPS_confirm_or_correct") or "").strip().lower()) != "corrected":
            continue
        key = next(iter(matches))
        group, item = ids[key]
        if group not in NATIVE_TAGS:
            continue
        changes, error = parse_corrections(row.get("OPS_correct_value"), group, item, False)
        if error:
            continue
        for field, value in changes.items():
            previous = edits.setdefault(key, {}).setdefault(field, value)
            if previous != value:
                conflicts[key] = "conflicting corrections for the same original native record"
        tag = changes.get("tag")
        if tag is None or tag == item["tag"]:
            continue
        owner = namespace.get(tag.casefold(), item)
        alias_owners = set().union(*(keys for name, keys in lookup.items() if name.casefold() == tag.casefold()))
        if (tag in {"PLANT", "BL"} or tag.casefold().startswith("stream:")
                or owner is not item or (tag in auxiliary and auxiliary[tag] != key) or alias_owners - {key}):
            conflicts[key] = "native tag destination collides with an existing or reserved identity; chains/swaps are refused"
        destination = planned.setdefault(tag.casefold(), set())
        destination.add(key)
    for keys in planned.values():
        if len(keys) > 1:
            conflicts.update({key: "multiple original records request the same native tag destination" for key in keys})
    return conflicts


def sheet_conflicts(rows, ids, lookup, twin):
    """Refuse contradictory instructions for one frozen target, including review metadata."""
    intents, conflicts = {}, {}
    for row in rows:
        matches = lookup.get(row.get("item_id"), lookup.get((row.get("item_id") or "").strip(), set()))
        if len(matches) != 1:
            continue
        key = next(iter(matches))
        group, item = ids[key]
        action = (row.get("OPS_confirm_or_correct") or "").strip().lower()
        wanted = {}
        if action in ACTIONS:
            wanted["decision"] = ACTIONS[action]
        for column in ("OPS_show_on_operator_screen_Y_N", "OPS_alarm_priority_H_M_L_none", "OPS_notes"):
            value = (row.get(column) or "").strip()
            if value:
                if column == "OPS_alarm_priority_H_M_L_none":
                    value = PRIORITY.get(value.lower(), value)
                wanted[column] = value
        if wanted:
            wanted["scope"] = (row.get("OPS_scope") or "").strip()
        if ACTIONS.get(action) == "corrected":
            changes, error = parse_corrections(row.get("OPS_correct_value"), group, item, twin)
            if not error:
                wanted.update({"field:" + field: value for field, value in changes.items()})
        for field, value in wanted.items():
            old = intents.setdefault(key, {}).setdefault(field, value)
            if old != value:
                conflicts[key] = "conflicting instructions for the same original record; reconcile the sheet before applying"
    return conflicts


def te_alarm_items(model):
    """Reference knowledge for declared TE simulator channels; never inject fields into source records."""
    if model.get("meta", {}).get("model_id") != "te-process" or model.get("meta", {}).get("model_kind") == "extracted_twin":
        return set()
    # Read the literal reference without importing the gateway module (which loads local gateway configuration).
    source = ROOT / "scripts" / "ignition" / "build_gateway.py"
    assignments = ast.parse(source.read_text(encoding="utf-8"))
    values = [ast.literal_eval(n.value) for n in assignments.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "ALARMS" for t in n.targets)]
    if len(values) != 1 or not isinstance(values[0], dict):
        raise ValueError("TE alarm reference is unavailable or has changed shape; no review applied")
    alarms = values[0]
    # The gateway reference's two process alarms are on TE XMEAS(7) and XMEAS(9), not arbitrary equal tag text.
    channels = {7: "PT-107", 9: "TT-109"}
    return {id(item) for item in model.get("instruments", [])
            if type(item.get("xmeas")) is int and item["xmeas"] in channels and alarms.get(channels[item["xmeas"]])}


def alarm_basis(item, published):
    """Recorded/reference setpoints or unresolved; missing metadata never proves no installed alarm."""
    if "alarm_setpoints" in item:
        values = item["alarm_setpoints"]
        if (isinstance(values, list) and values and
                all(type(v) in (int, float) and math.isfinite(v) for v in values)):
            return "supplied-setpoints"
        return "unresolved"
    return "te-reference" if id(item) in published else "unresolved"


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
        if k in changes and changes[k] != v:
            return {}, f"conflicting values for field '{k}' in one correction cell"
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


def apply(model, rows, reviewer, today, ids, published_alarm_items=()):
    twin = model.get("meta", {}).get("model_kind") == "extracted_twin"
    log = {"applied": [], "unchanged": 0, "refused": [], "needs_moc": []}
    csv_ids, current_ids = review_lookup(ids, twin)
    conflicts = sheet_conflicts(rows, ids, csv_ids, twin)
    if not twin:
        conflicts.update(rename_conflicts(model, rows, ids, csv_ids))
    alarms = {id(item): alarm_basis(item, published_alarm_items)
              for _, item in ids.values()}
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
        if item_id in conflicts:
            log["refused"].append({"row": n, "item": item_id, "reason": conflicts[item_id]})
            continue
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
        spelling = r.get("item_id") or ""
        if item_id not in current_ids.get(spelling, current_ids.get(spelling.strip(), set())) and not same:
            log["refused"].append({"row": n, "item": item_id,
                                   "reason": "historical identity permits only unchanged replay; use the current item_id for new decisions"})
            continue
        if same:
            log["unchanged"] += 1
            continue
        references = []
        if not twin and collection in NATIVE_TAGS and "tag" in changes:
            try:
                references = native_references(model, collection, item["tag"], changes["tag"])
            except ValueError as error:
                log["refused"].append({"row": n, "item": item_id, "reason": str(error)})
                continue
        history = list(prev.get("history", []))
        history.append({"on": today, "by": reviewer, "decision": status,
                        "changes": {k: [item.get(k), v] for k, v in changes.items()}, "notes": notes or None})
        if scope:
            history[-1].update(decision="corrected", scope=scope, fields=sorted(changes))
        if references:
            history[-1]["reference_changes"] = [{"path": path, "old": old, "new": new}
                                               for _, _, path, old, new in references]
        for k, v in changes.items():
            item[k] = v
        for container, key, _, _, value in references:
            container[key] = value
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
        if references:
            log["applied"][-1]["reference_changes"] = history[-1]["reference_changes"]
        if not twin and collection in NATIVE_TAGS and "tag" in changes:
            log["applied"][-1]["identity_change"] = {"old": history[-1]["changes"]["tag"][0], "new": item["tag"],
                "external_companions": "not updated: reconcile authored drawing/display layouts and external loop/mapping records; regenerate dependent outputs and refresh context"}
        # Requests the reviewer can make but that must not be applied silently: they change what alarms exist.
        basis = alarms[id(item)]
        asked = PRIORITY.get(prio)
        if asked and collection in ("instruments", "final_elements", "units"):
            log["applied"][-1]["alarm_basis"] = basis
            if basis == "unresolved":
                log["needs_moc"].append({"item": item_id, "request": f"verify {asked} alarm request",
                                         "why": "setpoint basis is unresolved; missing, empty or unrecognized metadata "
                                                "does not establish which alarms exist. Reconcile the applicable record "
                                                "through a change review; no alarm is created or removed here"})
            elif asked == "none":
                log["needs_moc"].append({"item": item_id, "request": "remove alarm",
                                         "why": "removing a recorded/reference alarm is a change review (MOC), not an edit; "
                                                "the alarm stays"})
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
        for a in log["applied"]:
            if a.get("identity_change"):
                lines += [f"### Native identity: {a['identity_change']['old']} → {a['identity_change']['new']}", "",
                          a["identity_change"]["external_companions"], ""]
                for ref in a.get("reference_changes", []):
                    lines.append(f"- `{ref['path']}`: `{ref['old']}` → `{ref['new']}`")
                lines.append("")
    if log["refused"]:
        lines += ["## Refused (fix the sheet and re-apply)", "", "| Row | Item | Reason |", "|---|---|---|"]
        lines += [f"| {r['row']} | {r['item']} | {r['reason']} |" for r in log["refused"]] + [""]
    if log["needs_moc"]:
        lines += ["## Needs a change review (not applied to alarms)", "", "| Item | Request | Why |", "|---|---|---|"]
        lines += [f"| {m['item']} | {m['request']} | {m['why']} |" for m in log["needs_moc"]] + [""]
    record_name = None
    if not dry:  # Existing standalone records remain immutable, including during unchanged replay.
        md = "\n".join(lines)
        doc = json.dumps({"model": rel(model_path), "reviewer": reviewer, "date": today, **log}, indent=1)
        def destinations(stem):
            return {rec_dir / f"{stem}.md": md, rec_dir / f"{stem}.json": doc}
        def identical(payloads):
            return all(path.is_file() and path.read_text(encoding="utf-8") == value for path, value in payloads.items())
        payloads = destinations(stem)
        if any(path.exists() for path in payloads) and not identical(payloads):
            fingerprint = hashlib.sha256((doc + "\0" + md).encode("utf-8")).hexdigest()
            payloads = destinations(stem + "-" + fingerprint[:16])
            if any(path.exists() for path in payloads) and not identical(payloads):
                raise ValueError("review record fingerprint collision or partial record; preserve it and choose another record directory")
        protect_outputs(payloads, [model_path, *source_paths])
        rec_dir.mkdir(parents=True, exist_ok=True)
        if not identical(payloads):
            for path, value in payloads.items():
                with path.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(value)
        record_name = next(path.name for path in payloads if path.suffix == ".json")
    return "\n".join(lines) + (f"\nRecord: {record_name}\n" if record_name else "")


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
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON field: {key!r}")
                result[key] = value
            return result
        def invalid_constant(value):
            raise ValueError(f"nonfinite JSON value: {value}")
        model = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
        with open(a.sheet, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, strict=True)
            fields = reader.fieldnames or []
            if len(fields) != len(set(fields)):
                raise ValueError("duplicate CSV column names; each review field must be unambiguous")
            rows = list(reader)
            if any(any(str(value).strip() for value in row.get(None, [])) for row in rows):
                raise ValueError("review row has nonempty fields beyond the CSV header")
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
    try:
        log = apply(model, rows, a.reviewer, a.date, index(model), te_alarm_items(model))
    except (ValueError, KeyError, TypeError, AttributeError, OSError, SyntaxError) as exc:
        ap.exit(2, f"review not applied; nothing written: {exc}\n")
    try:
        print(write_record(log, model_path, a.reviewer, a.date, a.dry_run, a.record_dir,
                           source_paths=[a.sheet, *([ROOT / 'scripts/ignition/build_gateway.py']
                               if model.get('meta', {}).get('model_id') == 'te-process' else [])],
                           model_write=bool(log['applied'])))
    except (ValueError, OSError) as exc:
        ap.exit(2, f"review model not updated: {exc}\n")
    if not a.dry_run and log["applied"]:
        model_path.write_text(json.dumps(model, indent=indent, ensure_ascii=ascii_only) + trailing, encoding="utf-8",
                              newline=newline)
        print(f"\nupdated {rel(model_path)}; now regenerate (scripts/generate.py)")
    sys.exit(1 if log["refused"] else 0)


if __name__ == "__main__":
    main()
