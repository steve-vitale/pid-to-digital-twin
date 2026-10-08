"""Give the twin's instruments real data addresses from a plant I/O list: placeholders become live points.

Input: an I/O list CSV with columns
  tag          the instrument tag as the plant knows it (e.g. FT-1401)
  server       the Ignition OPC connection name that serves it
  base_path    the OPC UA path prefix, e.g. nsu=urn:my-plc;s=PLANT
  point        the point name under that prefix (the item path is <base_path>.<point>)
  asset_id     optional: pin a row to one twin asset when tags are ambiguous
  units, description   optional, kept for the record

Matching is by tag after normalizing separators and case ("FT 1401", "FT-1401" and "ft_1401" all match), or by
asset_id when given. Nothing is guessed: a tag that matches two drawing items is reported as ambiguous and left
unmapped.

The report (out/mapping/<model>-<io list>.md/.json) has four lists. Each is a worklist for a real site:
  mapped              instruments that now have a data address
  not in the I/O list instruments on the drawing with no point: spare, demolished, or a missing I/O row?
  not on the drawing  I/O points with no drawing item: the drawing may be out of date (or the I/O list is wrong)
  ambiguous           the same tag on two drawing items; pin with asset_id

Writes `data_point` onto each mapped instrument in the model, in place. scripts/generate.py then puts the address
into the Ignition tags. Re-running with a corrected I/O list replaces earlier mappings.

Usage: python scripts/map_points.py <plant_model.json> <io_list.csv> [--sheets 0,1] [--dry-run]
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def norm(tag):
    return re.sub(r"[\s_\-./]+", "", (tag or "").upper())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("io_list")
    ap.add_argument("--sheets", default="", help="sheets this I/O list covers (e.g. 0,1); scopes 'not in the I/O "
                                                 "list'. Default: every sheet")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    scope = {s.strip() for s in a.sheets.split(",") if s.strip()}
    model_path = Path(a.model).resolve()
    raw = model_path.read_text(encoding="utf-8")
    model = json.loads(raw)
    second = raw.splitlines()[1] if "\n" in raw else ""
    indent = len(second) - len(second.lstrip(" ")) or None
    rows = list(csv.DictReader(open(a.io_list, encoding="utf-8-sig", newline="")))
    io_name = Path(a.io_list).name

    insts = [x for x in model["instruments"] if (x.get("ops_review") or {}).get("status") != "rejected"]
    by_tag = defaultdict(list)
    for x in insts:
        if x.get("tag") and x.get("tag_status") != "placeholder":
            by_tag[norm(x["tag"])].append(x)
    by_id = {x["id"]: x for x in insts}
    for x in insts:
        x.pop("data_point", None)

    mapped, not_on_drawing, ambiguous = [], [], []
    for n, r in enumerate(rows, 2):
        pin = (r.get("asset_id") or "").strip()
        targets = [by_id[pin]] if pin in by_id else by_tag.get(norm(r["tag"]), [])
        if not targets:
            not_on_drawing.append({"row": n, "tag": r["tag"], "point": r["point"], "description": r.get("description")})
            continue
        if len(targets) > 1:
            ambiguous.append({"row": n, "tag": r["tag"], "assets": [t["id"] for t in targets]})
            continue
        x = targets[0]
        x["data_point"] = {"server": r["server"].strip(), "base_path": r["base_path"].strip(),
                           "point": r["point"].strip(), "source": f"{io_name} row {n}"}
        mapped.append({"asset": x["id"], "drawing_tag": x["tag"], "io_tag": r["tag"], "point": r["point"],
                       "how": "asset_id" if pin else ("exact" if x["tag"] == r["tag"] else "normalized tag")})
    mapped_ids = {m["asset"] for m in mapped}
    not_in_io = [{"asset": x["id"], "tag": x.get("tag"), "tag_status": x.get("tag_status"),
                  "sheet": x["provenance"][0]["sheet"]} for x in insts if x["id"] not in mapped_ids
                 and (not scope or x["provenance"][0]["sheet"] in scope)]

    report = {"model": model_path.relative_to(ROOT).as_posix(), "io_list": io_name,
              "sheets_covered": sorted(scope) or "all", "mapped": mapped,
              "not_in_io_list": not_in_io, "not_on_drawing": not_on_drawing, "ambiguous": ambiguous}
    out_dir = ROOT / "out" / "mapping"
    stem = f"{model_path.parent.parent.name}-{model_path.parent.name}-{Path(io_name).stem}"
    lines = [f"# Point mapping: {report['model']} ← {io_name}", "",
             f"Mapped: {len(mapped)} · On the drawing, not in the I/O list: {len(not_in_io)} · "
             f"In the I/O list, not on the drawing: {len(not_on_drawing)} · Ambiguous: {len(ambiguous)}", "",
             "## Mapped", "", "| Asset | Drawing tag | I/O tag | Point | Matched by |", "|---|---|---|---|---|"]
    lines += [f"| {m['asset']} | {m['drawing_tag']} | {m['io_tag']} | {m['point']} | {m['how']} |" for m in mapped]
    lines += ["", "## In the I/O list but not on the drawing (is the drawing out of date?)", "",
              "| Row | Tag | Point | Description |", "|---|---|---|---|"]
    lines += [f"| {x['row']} | {x['tag']} | {x['point']} | {x.get('description') or ''} |" for x in not_on_drawing]
    lines += ["", "## Ambiguous (pin with asset_id)", "", "| Row | Tag | Matching assets |", "|---|---|---|"]
    lines += [f"| {x['row']} | {x['tag']} | {', '.join(x['assets'])} |" for x in ambiguous]
    lines += ["", f"## On the drawing but not in the I/O list ({len(not_in_io)})", "",
              "Spare or demolished instruments, local gauges with no signal, or missing I/O rows. Listed in the JSON "
              "report; the count by sheet:", ""]
    per_sheet = defaultdict(int)
    for x in not_in_io:
        per_sheet[x["sheet"]] += 1
    lines += [", ".join(f"sheet {s}: {n}" for s, n in sorted(per_sheet.items(), key=lambda kv: int(kv[0])))]
    text = "\n".join(lines) + "\n"
    print(text)
    if not a.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{stem}.md").write_text(text, encoding="utf-8")
        (out_dir / f"{stem}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        model_path.write_text(json.dumps(model, indent=indent, ensure_ascii=raw.isascii())
                              + ("\n" if raw.endswith("\n") else ""), encoding="utf-8")
        print(f"updated {report['model']}; now regenerate (scripts/generate.py {report['model']})")


if __name__ == "__main__":
    main()
