"""Assign supplied OPC addresses locally and retain their I/O source; no signal connection is verified.

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
  not on the drawing  supplied I/O rows with no matching model item: reconcile both sources
  ambiguous           the same tag on two drawing items; pin with asset_id

Writes `data_point` onto each mapped instrument in the model, in place. scripts/generate.py then puts the address
into the Ignition tags. By default this is a partial update: unrelated mappings are preserved.
Use --replace-all for an authoritative replacement of mappings within --sheets (or all sheets if omitted).
Unknown explicit IDs, duplicate target rows, missing/empty address fields, and out-of-scope rows reject the entire update.
Dry-run writes nothing and reports complete mapping snapshots and changes; --json emits machine-readable output.
The CLI hashes the exact CSV bytes it parses and retains 1-based physical line spans, including multiline records.
Keep that original with the packet. A fingerprint/locator identifies supplied evidence, not source authority,
valid OPC syntax, connectivity, signal identity, units or scaling.

Usage: python scripts/map_points.py <plant_model.json> <io_list.csv> [--sheets 0,1] [--replace-all] [--dry-run] [--json]
"""
import argparse
import csv
import copy
import hashlib
import io
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


def read_io_list(path):
    """Read once: fingerprint raw bytes and locate records in that same snapshot.

    Blank lines between records are skipped; quoted newlines remain inside the
    record's physical span. Locator metadata never comes from CSV columns.
    """
    raw = Path(path).read_bytes()
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    fields = next(reader, [])
    records, locations = [], []
    while True:
        start = reader.line_num + 1
        try:
            values = next(reader)
        except StopIteration:
            break
        if not values:  # DictReader's existing blank-record behavior
            continue
        record = {field: values[i] if i < len(values) else None for i, field in enumerate(fields)}
        if len(values) > len(fields):
            record[None] = values[len(fields):]
        records.append(record)
        locations.append((start, reader.line_num))
    return fields, records, locations, {"file": Path(path).name, "bytes": len(raw),
                                        "sha256": hashlib.sha256(raw).hexdigest()}


def plan_mapping(model, rows, io_name, scope=None, replace_all=False, *, source_rows=None, source_sha256=None):
    """Plan a mapping transaction without mutating the input model.

    Explicit IDs never fall back to tags. Repeated target rows are errors, even
    when their addresses agree. A failed transaction leaves every mapping intact.
    Replacement is deliberately stricter: unresolved rows cannot authorize loss.
    Direct dict callers have logical rows only unless they explicitly supply
    locations. No file fingerprint or physical span is inferred from dicts.
    """
    if source_rows is not None:
        if not isinstance(source_rows, (list, tuple)) or len(source_rows) != len(rows):
            raise ValueError("source_rows must contain one ordered physical line span per record")
        previous_end = 1  # the header occupies at least line 1
        for span in source_rows:
            if (not isinstance(span, (list, tuple)) or len(span) != 2
                    or any(type(n) is not int for n in span)
                    or span[0] <= previous_end or span[1] < span[0]):
                raise ValueError("source_rows must contain one ordered physical line span per record")
            previous_end = span[1]
    if source_sha256 is not None and (not isinstance(source_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)):
        raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
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
    for index, r in enumerate(rows):
        n, end = source_rows[index] if source_rows is not None else (index + 2, index + 2)
        location = {"row": n, "row_end": end}
        tag = (r.get("tag") or "").strip()
        pin = (r.get("asset_id") or "").strip()
        if not tag and not pin:
            errors.append({**location, "reason": "tag or asset_id is required"})
            continue
        if any(not (r.get(k) or "").strip() for k in ("server", "base_path", "point")):
            errors.append({**location, "reason": "server, base_path and point must be nonempty"})
            continue
        if pin and pin not in by_id:
            errors.append({**location, "asset": pin, "reason": "unknown or rejected explicit asset_id; no tag fallback"})
            continue
        targets = [by_id[pin]] if pin else by_tag.get(norm(tag), [])
        if not targets:
            not_on_drawing.append({**location, "tag": tag, "point": r["point"], "description": r.get("description")})
            continue
        if any(t.get("reviewed_valve_association") for t in targets):
            ambiguous.append({**location, "tag": tag, "assets": [t["id"] for t in targets],
                              "reason": "reviewed valve callout: signal requires separate review; asset_id cannot override"})
            continue
        if len(targets) > 1:
            ambiguous.append({**location, "tag": tag, "assets": [t["id"] for t in targets]})
            continue
        x = targets[0]
        if scope and sheet_of(x) not in scope:
            errors.append({**location, "asset": x["id"], "reason": "target is outside --sheets scope"})
            continue
        if x["id"] in seen_targets:
            errors.append({**location, "asset": x["id"], "reason": f"duplicate target; first assigned on {seen_targets[x['id']]}"})
            continue
        locator = f"line {n}" if n == end else f"lines {n}-{end}"
        if source_rows is None:
            locator = f"logical row {n} (no file locator)"
        seen_targets[x["id"]] = locator
        assignments[x["id"]] = {"server": r["server"].strip(), "base_path": r["base_path"].strip(),
                                  "point": r["point"].strip(), "source": f"{io_name} {locator}"}
        if source_rows is not None:
            assignments[x["id"]]["source_lines"] = [n, end]
        if source_sha256 is not None:
            assignments[x["id"]]["source_sha256"] = source_sha256
        mapped.append({**location, "asset": x["id"], "drawing_tag": x.get("tag"), "io_tag": tag, "point": r["point"],
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
                      "row_locator_kind": "physical CSV lines (1-based)" if source_rows is not None else "logical rows (header counted; no file locator)",
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
        fields, rows, source_rows, io_evidence = read_io_list(a.io_list)
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
    model, report = plan_mapping(model, rows, io_name, scope, a.replace_all,
                                 source_rows=source_rows, source_sha256=io_evidence["sha256"])
    try:
        model_name = model_path.relative_to(ROOT).as_posix()
    except ValueError:
        model_name = f"{model_path.parent.name}/{model_path.name}"  # reports get shared; a home path shouldn't
    report.update(model=model_name, io_list=io_name, io_list_evidence=io_evidence, dry_run=a.dry_run)
    mapped = report["mapped"]
    not_in_io = report["not_in_io_list"]
    not_on_drawing = report["not_on_drawing"]
    ambiguous = report["ambiguous"]
    out_dir = ROOT / "out" / "mapping"
    stem = f"{model_path.parent.parent.name}-{model_path.parent.name}-{Path(io_name).stem}"
    lines = [f"# Point mapping: {report['model']} ← {io_name}", "",
             "Status: " + ("valid plan" if report["valid"] else "REJECTED; mapped rows below are candidates only; no changes will be written"), "",
             f"I/O source: {io_name}; {io_evidence['bytes']} bytes; SHA-256 `{io_evidence['sha256']}`.",
             "Locators are 1-based physical CSV lines, including quoted newlines. Retain the original file.",
             "Address assignment does not verify OPC syntax, connectivity, signal identity, units or scaling.", "",
             f"Mapped: {len(mapped)} · On the drawing, not in the I/O list: {len(not_in_io)} · "
             f"In the I/O list, not on the drawing: {len(not_on_drawing)} · Ambiguous: {len(ambiguous)}", "",
             "## Mapped", "", "| Asset | Drawing tag | I/O tag | Point | Matched by | Source lines |", "|---|---|---|---|---|---|"]
    lines += [f"| {m['asset']} | {m['drawing_tag']} | {m['io_tag']} | {m['point']} | {m['how']} | {m['row']}-{m['row_end']} |" for m in mapped]
    lines += ["", "## In the I/O list but not matched to a model item (reconcile both sources)", "",
              "| Source lines | Tag | Point | Description |", "|---|---|---|---|"]
    lines += [f"| {x['row']}-{x['row_end']} | {x['tag']} | {x['point']} | {(x.get('description') or '').replace(chr(13), '').replace(chr(10), '<br>')} |" for x in not_on_drawing]
    lines += ["", "## Ambiguous / blocked (valve callouts need signal review; other duplicates can be pinned)", "", "| Source lines | Tag | Matching assets |", "|---|---|---|"]
    lines += [f"| {x['row']}-{x['row_end']} | {x['tag']} | {', '.join(x['assets'])}{': ' + x['reason'] if x.get('reason') else ''} |" for x in ambiguous]
    lines += ["", f"## On the drawing but not in the I/O list ({len(not_in_io)})", "",
              "Model instruments not matched by this I/O input. Reconcile missing rows, local gauges and stale "
              "identities; omitted older mappings may remain in partial mode. Listed in the JSON report; count by sheet:", ""]
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
