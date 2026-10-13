"""Offline check of a PI Builder-style staging CSV against the vendor-published conventions we could read.

This is NOT a PI Builder import and it cannot say a file will import. It compares the file with
data/pi_builder_reference.json: sheet headers, ObjectType values, the Parent convention, attribute value
types and default UOMs seen in vendor workbooks and in a vendor-published AF export. Every finding says
which evidence it rests on. The only things it calls errors are internal inconsistencies (duplicate rows,
attribute rows with no element, element rows carrying attribute fields, a PI Point reference with no config
string) and values outside what the documented sheets show for a required column.

    python scripts/check_pi_export.py out/pi/pi_builder_af.csv
    python scripts/check_pi_export.py out/pi/pi_builder_af.csv --json   # full report
Exit codes: 0 no errors (warnings may remain), 1 errors, 2 unreadable input.
"""
import argparse
import csv
import io
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "pi_builder_reference.json"
REQUIRED = ("Selected(x)", "Parent", "Name", "ObjectType")
ATTRIBUTE_FIELDS = ("AttributeType", "AttributeValueType", "AttributeDefaultUOM",
                    "AttributeDataReference", "AttributeConfigString")
# Spellings that are not the vendor abbreviation but obviously mean one (ASCII stand-ins).
SPELLING_VARIANTS = {"degC": "°C", "degF": "°F", "deg C": "°C", "deg F": "°F", "m^3/h": "m3/h"}
# Repo mapper allowlist (scripts/pi_mapping.py); kept here so the check can say which entries lack vendor evidence.
REPO_TYPE_ALLOWLIST = ("Double", "Single", "Int32", "Int16", "String")


def load_reference(path=REFERENCE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_csv_text(text):
    text = text[1:] if text.startswith("﻿") else text
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = list(reader)
    if not rows:
        raise ValueError("empty file")
    return rows[0], [dict(zip(rows[0], r)) for r in rows[1:]]


def uom_finding(value, units):
    if value == "":
        return {"status": "none", "note": "no default UOM"}
    for u in units:
        if value in (u["abbreviation"], u["name"]):
            return {"status": "in_vendor_sample", "class": u["class"], "name": u["name"], "abbreviation": u["abbreviation"]}
    variant = SPELLING_VARIANTS.get(value)
    if variant:
        match = next((u for u in units if u["abbreviation"] == variant), None)
        return {"status": "spelling_differs", "vendor_abbreviation": variant,
                "class": match and match["class"], "name": match and match["name"],
                "note": "not the vendor name or abbreviation; whether AF accepts this spelling is unknown"}
    return {"status": "not_in_vendor_sample",
            "note": "not in the vendor sample (a subset of the default UOM database); check the site's UOM "
                    "database, or define a custom UOM before import"}


def config_finding(value):
    if value == "":
        return "empty"
    if "placeholder" in value.lower():
        return "placeholder"
    if value.startswith("\\\\%Server%\\"):
        rest = value[len("\\\\%Server%\\"):]
        return "default_archive_substitution" if "%" not in rest else "other_substitution"
    if value.startswith("\\\\") and "%" not in value:
        return "literal_archive_and_point"
    return "other"


def check(header, rows, ref=None):
    ref = ref or load_reference()
    documented = set(ref["columns"])
    report = {"status": "OFFLINE CONVENTION CHECK ONLY; not a PI Builder import, not proof the file will import",
              "rows": len(rows), "errors": [], "warnings": [], "columns": {}}
    for column in header:
        if column in documented:
            report["columns"][column] = "documented"
        elif column in ref["columns_unconfirmed"]:
            report["columns"][column] = "unconfirmed"
            report["warnings"].append(f"column {column}: {ref['columns_unconfirmed'][column]}")
        elif column in ref["columns_not_documented"]:
            report["columns"][column] = "not_documented"
            report["warnings"].append(f"column {column}: {ref['columns_not_documented'][column]}")
        else:
            report["columns"][column] = "unknown"
            report["warnings"].append(f"column {column}: not in the reference file")
    if len(set(header)) != len(header):
        report["errors"].append("duplicate column headers")
    for column in REQUIRED:
        if column not in header:
            report["errors"].append(f"required column {column} missing")
    if report["errors"]:
        return report
    type_column = next((c for c in ("AttributeType", "AttributeValueType") if c in header), None)
    elements, keys = set(), Counter()
    templates_defined = {r["Name"] for r in rows if r["ObjectType"] == "ElementTemplate"}
    for r in rows:
        if r["ObjectType"] == "Element":
            elements.add(r["Name"] if not r["Parent"] else r["Parent"] + "\\" + r["Name"])
    object_types, types, uoms, configs, templates = Counter(), Counter(), Counter(), Counter(), Counter()
    for n, r in enumerate(rows, 2):
        kind = r["ObjectType"]
        object_types[kind] += 1
        keys[(r["Parent"], r["Name"], kind)] += 1
        if kind not in ref["object_types"]:
            report["errors"].append(f"row {n}: ObjectType {kind!r} is not one the documented sheets show")
            continue
        if r["Selected(x)"] not in ("x", ""):
            report["errors"].append(f"row {n}: Selected(x) must be 'x' or empty")
        if not r["Name"]:
            report["errors"].append(f"row {n}: empty Name")
        if kind == "Element":
            filled = [c for c in ATTRIBUTE_FIELDS if r.get(c)]
            if filled:
                report["errors"].append(f"row {n}: element row carries attribute fields {filled}")
            if r.get("Template"):
                templates[r["Template"]] += 1
        elif kind == "Attribute":
            if r["Parent"] not in elements:
                report["errors"].append(f"row {n}: attribute parent {r['Parent']!r} is not an element in this file")
            if type_column:
                types[r[type_column]] += 1
            uoms[r.get("AttributeDefaultUOM", "")] += 1
            if r.get("AttributeDataReference") == "PI Point":
                kind_cfg = config_finding(r.get("AttributeConfigString", ""))
                configs[kind_cfg] += 1
                if kind_cfg == "empty":
                    report["errors"].append(f"row {n}: PI Point data reference with no config string")
            elif r.get("AttributeDataReference"):
                if r["AttributeDataReference"] not in ref["data_references"]:
                    report["warnings"].append(f"row {n}: data reference {r['AttributeDataReference']!r} not in the reference file")
    for (parent, name, kind), count in keys.items():
        if count > 1:
            report["errors"].append(f"{count} rows share Parent {parent!r}, Name {name!r}, ObjectType {kind}")
    report["object_types"] = dict(object_types)
    report["attribute_types"] = {
        t: ("documented" if t in ref["attribute_types"] else
            "repo_allowlist_only (no vendor evidence read)" if t in REPO_TYPE_ALLOWLIST else
            "empty" if t == "" else "unknown")
        for t in sorted(types)}
    report["attribute_type_counts"] = dict(types)
    for t, status in report["attribute_types"].items():
        if status not in ("documented",):
            report["warnings"].append(f"attribute type {t!r}: {status}")
    units = ref["uom_sample"]["units"]
    report["uoms"] = {u: dict(uom_finding(u, units), rows=c) for u, c in sorted(uoms.items())}
    for u, f in report["uoms"].items():
        if f["status"] in ("spelling_differs", "not_in_vendor_sample"):
            report["warnings"].append(f"UOM {u!r} ({f['rows']} rows): {f['status']}")
    if uoms.get(""):
        report["warnings"].append(f"{uoms['']} attributes have no default UOM ({ref['uom_guidance']})")
    report["config_strings"] = dict(configs)
    if configs.get("placeholder"):
        report["warnings"].append(f"{configs['placeholder']} PI Point references are placeholders: exclude them from any import")
    undefined = sorted(set(templates) - templates_defined)
    report["element_templates_referenced_not_defined"] = undefined
    if undefined:
        report["warnings"].append(f"element templates {undefined} are referenced but not defined in this file; "
                                  "they must already exist in the target AF database")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--json", action="store_true", help="print the full JSON report")
    args = ap.parse_args(argv)
    try:
        header, rows = read_csv_text(Path(args.csv).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, csv.Error) as exc:
        print(f"cannot read {args.csv}: {exc}", file=sys.stderr)
        return 2
    report = check(header, rows)
    if args.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        print(report["status"])
        print(f"{report['rows']} rows; object types {report.get('object_types', {})}")
        for e in report["errors"]:
            print("ERROR  ", e)
        for w in report["warnings"]:
            print("WARN   ", w)
        print("no errors" if not report["errors"] else f"{len(report['errors'])} errors")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
