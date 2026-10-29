"""Give the twin's instruments real data addresses from a plant I/O list: placeholders become live points.

Input: an I/O list CSV with columns
  tag          the instrument tag as the plant knows it (e.g. FT-1401)
  server       the Ignition OPC connection name that serves it
  base_path    the OPC UA path prefix, e.g. nsu=urn:my-plc;s=PLANT
  point        the point name under that prefix (the item path is <base_path>.<point>)
  asset_id     optional: pin a row to one twin asset when tags are ambiguous
  units, description   optional; not used to validate or populate model properties

Matching is by tag after normalizing separators and case ("FT 1401", "FT-1401" and "ft_1401" all match), or by
asset_id when given. Nothing is guessed: a tag that matches two drawing items is reported as ambiguous and is
not assigned by that row; existing mappings remain in partial mode.

The report (out/mapping/<model>-<io list>.md/.json) has four lists. Each is a worklist for a real site:
  mapped              instruments that now have a data address
  not in the I/O list drawing instruments not matched by this input (existing mappings may be preserved)
  not on the drawing  I/O points with no drawing item: the drawing may be out of date (or the I/O list is wrong)
  ambiguous           the same tag on two drawing items; pin with asset_id

Writes `data_point` onto each mapped instrument in the model, in place. scripts/generate.py then puts the address
into the Ignition tags. By default this is a partial update: unrelated mappings are preserved.
Use --replace-all for an authoritative replacement of mappings within --sheets (or all sheets if omitted).
Unknown explicit IDs, duplicate target rows, missing/empty address fields, and out-of-scope rows reject the entire update.
Dry-run writes nothing and reports complete mapping snapshots and changes; --json emits machine-readable output.

Usage: python scripts/map_points.py <plant_model.json> <io_list.csv> [--sheets 0,1] [--replace-all] [--dry-run] [--json]
"""
import argparse
import csv
import copy
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def norm(tag):
    return re.sub(r"[\s_\-./]+", "", (tag or "").upper())


def sheet_of(item):
    return str((item.get("provenance") or [{}])[0].get("sheet", "unknown"))


def mapping_snapshot(model):
    return {x["id"]: copy.deepcopy(x["data_point"]) for x in model["instruments"] if "data_point" in x}


def plan_mapping(model, rows, io_name, scope=None, replace_all=False):
    """Plan a mapping transaction without mutating the input model.

    Explicit IDs never fall back to tags. Repeated target rows are errors, even
    when their addresses agree. A failed transaction leaves every mapping intact.
    Replacement is deliberately stricter: unresolved rows cannot authorize loss.
    """
    scope = {str(s) for s in (scope or [])}
    proposed = copy.deepcopy(model)
    insts = [x for x in proposed["instruments"] if (x.get("ops_review") or {}).get("status") != "rejected"]
    by_tag = defaultdict(list)
    by_id = {}
    errors = []
    for x in proposed["instruments"]:
        if x["id"] in by_id:
            errors.append({"asset": x["id"], "reason": "duplicate model asset_id"})
        by_id[x["id"]] = x
    by_id = {x["id"]: x for x in insts}
    for x in insts:
        if x.get("tag") and x.get("tag_status") != "placeholder":
            by_tag[norm(x["tag"])].append(x)
    if scope - {sheet_of(x) for x in insts}:
        errors.append({"reason": "unknown sheets: " + ", ".join(sorted(scope - {sheet_of(x) for x in insts}))})

    mapped, not_on_drawing, ambiguous = [], [], []
    assignments = {}
    seen_targets = {}
    for n, r in enumerate(rows, 2):
        tag = (r.get("tag") or "").strip()
        pin = (r.get("asset_id") or "").strip()
        if not tag and not pin:
            errors.append({"row": n, "reason": "tag or asset_id is required"})
            continue
        if any(not (r.get(k) or "").strip() for k in ("server", "base_path", "point")):
            errors.append({"row": n, "reason": "server, base_path and point must be nonempty"})
            continue
        if pin and pin not in by_id:
            errors.append({"row": n, "asset": pin, "reason": "unknown or rejected explicit asset_id; no tag fallback"})
            continue
        targets = [by_id[pin]] if pin else by_tag.get(norm(tag), [])
        if not targets:
            not_on_drawing.append({"row": n, "tag": tag, "point": r["point"], "description": r.get("description")})
            continue
        if any(t.get("reviewed_valve_association") for t in targets):
            ambiguous.append({"row": n, "tag": tag, "assets": [t["id"] for t in targets],
                              "reason": "reviewed valve callout: signal requires separate review; asset_id cannot override"})
            continue
        if len(targets) > 1:
            ambiguous.append({"row": n, "tag": tag, "assets": [t["id"] for t in targets]})
            continue
        x = targets[0]
        if scope and sheet_of(x) not in scope:
            errors.append({"row": n, "asset": x["id"], "reason": "target is outside --sheets scope"})
            continue
        if x["id"] in seen_targets:
            errors.append({"row": n, "asset": x["id"], "reason": f"duplicate target; first assigned on row {seen_targets[x['id']]}"})
            continue
        seen_targets[x["id"]] = n
        assignments[x["id"]] = {"server": r["server"].strip(), "base_path": r["base_path"].strip(),
                                  "point": r["point"].strip(), "source": f"{io_name} row {n}"}
        mapped.append({"asset": x["id"], "drawing_tag": x.get("tag"), "io_tag": tag, "point": r["point"],
                       "how": "asset_id" if pin else ("exact" if x.get("tag") == tag else "normalized tag")})
    if replace_all and (ambiguous or not_on_drawing):
        errors.append({"reason": "--replace-all requires every row to resolve; fix ambiguous, blocked or unmatched rows first"})
    if not errors:
        for x in insts:
            if replace_all and (not scope or sheet_of(x) in scope):
                x.pop("data_point", None)
            if x["id"] in assignments:
                x["data_point"] = assignments[x["id"]]
    mapped_ids = set(assignments)
    not_in_io = [{"asset": x["id"], "tag": x.get("tag"), "tag_status": x.get("tag_status"),
                  "sheet": sheet_of(x)} for x in insts if x["id"] not in mapped_ids
                 and (not scope or sheet_of(x) in scope)]
    before = mapping_snapshot(model)
    after = mapping_snapshot(proposed)
    changes = [{"asset": key, "kind": "added" if key not in before else "removed" if key not in after else "changed",
                "before": before.get(key), "after": after.get(key)}
               for key in sorted(before.keys() | after.keys())
               if key not in before or key not in after or before[key] != after[key]]
    return proposed, {"mode": "replace-all" if replace_all else "partial", "valid": not errors,
                      "sheets_covered": sorted(scope) or "all", "mapped": mapped,
                      "not_in_io_list": not_in_io, "not_on_drawing": not_on_drawing,
                      "ambiguous": ambiguous, "errors": errors, "mapping_changes": changes,
                      "mappings_before": before, "mappings_after": after}


def main():
    import sys
    if hasattr(sys.stdout, "reconfigure"):  # a Windows console is cp1252: print arrows and units, don't crash;
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="\n")  # and LF when redirected
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("io_list")
    ap.add_argument("--sheets", default="", help="limit target updates and replacement to these sheets (e.g. 0,1); tag ambiguity remains global. Default: every sheet")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--replace-all", action="store_true", help="replace all mappings in scope; default is a partial update")
    ap.add_argument("--json", action="store_true", help="print the complete JSON report instead of Markdown")
    a = ap.parse_args()
    scope = {s.strip() for s in a.sheets.split(",") if s.strip()}
    model_path = Path(a.model).resolve()
    try:
        raw = model_path.read_text(encoding="utf-8")
        model = json.loads(raw)
        with open(a.io_list, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames or []
            rows = list(reader)
    except (OSError, ValueError, csv.Error) as exc:  # a missing or unreadable file: say which, no traceback
        ap.exit(2, f"point mapping rejected; no model update: {exc}\n")
    second = raw.splitlines()[1] if "\n" in raw else ""
    indent = len(second) - len(second.lstrip(" ")) or None
    newline = "\r\n" if b"\r\n" in model_path.read_bytes() else "\n"  # read_text hides the line endings
    required = {"tag", "server", "base_path", "point"}
    if not required.issubset(fields):
        ap.error("I/O CSV must contain tag, server, base_path and point columns")
    if len(fields) != len(set(fields)):
        ap.error("I/O CSV has duplicate column names")
    if any(None in r for r in rows):
        ap.error("I/O CSV contains rows with extra fields")
    io_name = Path(a.io_list).name
    model, report = plan_mapping(model, rows, io_name, scope, a.replace_all)
    try:
        model_name = model_path.relative_to(ROOT).as_posix()
    except ValueError:
        model_name = f"{model_path.parent.name}/{model_path.name}"  # reports get shared; a home path shouldn't
    report.update(model=model_name, io_list=io_name, dry_run=a.dry_run)
    mapped = report["mapped"]
    not_in_io = report["not_in_io_list"]
    not_on_drawing = report["not_on_drawing"]
    ambiguous = report["ambiguous"]
    out_dir = ROOT / "out" / "mapping"
    stem = f"{model_path.parent.parent.name}-{model_path.parent.name}-{Path(io_name).stem}"
    lines = [f"# Point mapping: {report['model']} ← {io_name}", "",
             "Status: " + ("valid plan" if report["valid"] else "REJECTED; mapped rows below are candidates only; no changes will be written"), "",
             f"Mapped: {len(mapped)} · On the drawing, not in the I/O list: {len(not_in_io)} · "
             f"In the I/O list, not on the drawing: {len(not_on_drawing)} · Ambiguous: {len(ambiguous)}", "",
             "## Mapped", "", "| Asset | Drawing tag | I/O tag | Point | Matched by |", "|---|---|---|---|---|"]
    lines += [f"| {m['asset']} | {m['drawing_tag']} | {m['io_tag']} | {m['point']} | {m['how']} |" for m in mapped]
    lines += ["", "## In the I/O list but not on the drawing (is the drawing out of date?)", "",
              "| Row | Tag | Point | Description |", "|---|---|---|---|"]
    lines += [f"| {x['row']} | {x['tag']} | {x['point']} | {x.get('description') or ''} |" for x in not_on_drawing]
    lines += ["", "## Ambiguous / blocked (valve callouts need signal review; other duplicates can be pinned)", "", "| Row | Tag | Matching assets |", "|---|---|---|"]
    lines += [f"| {x['row']} | {x['tag']} | {', '.join(x['assets'])}{': ' + x['reason'] if x.get('reason') else ''} |" for x in ambiguous]
    lines += ["", f"## On the drawing but not in the I/O list ({len(not_in_io)})", "",
              "Spare or demolished instruments, local gauges with no signal, or missing I/O rows. Listed in the JSON "
              "report; the count by sheet:", ""]
    per_sheet = defaultdict(int)
    for x in not_in_io:
        per_sheet[x["sheet"]] += 1
    lines += [", ".join(f"sheet {s}: {n}" for s, n in sorted(per_sheet.items(), key=lambda kv: kv[0]))]
    lines += ["", f"Mode: {report['mode']}; sheets: {report['sheets_covered']}",
              "Status: " + ("valid plan" if report["valid"] else "REJECTED; no changes will be written"), ""]
    for error in report["errors"]:
        lines.append("- " + json.dumps(error, sort_keys=True))
    lines += ["", "## Complete mapping changes (before → after)", ""]
    lines += [f"- {c['asset']} ({c['kind']}): {json.dumps(c['before'], sort_keys=True)} → {json.dumps(c['after'], sort_keys=True)}"
              for c in report["mapping_changes"]] or ["No mapping changes."]
    lines += ["", "## All mappings before", "", json.dumps(report["mappings_before"], sort_keys=True),
              "", "## All mappings after", "", json.dumps(report["mappings_after"], sort_keys=True)]
    text = "\n".join(lines) + "\n"
    print(json.dumps(report, indent=1) if a.json else text, end="\n" if a.json else "")
    if not report["valid"]:
        raise SystemExit(1)
    if not a.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{stem}.md").write_text(text, encoding="utf-8", newline="\n")
        (out_dir / f"{stem}.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
        model_path.write_text(json.dumps(model, indent=indent, ensure_ascii=raw.isascii())
                              + ("\n" if raw.endswith("\n") else ""), encoding="utf-8", newline=newline)
        if not a.json:
            print(f"updated {model_path}; now regenerate (scripts/generate.py {model_path})")


if __name__ == "__main__":
    main()
