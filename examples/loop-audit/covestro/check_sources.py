"""Verify this fixed public-source transcription; optional fetch reuses existing corpus pins.

Reads XLSM ZIP/XML as data only. Does not execute macros, evaluate formulas, edit a
workbook, infer control logic, or create an input for loop_audit.py. Stdlib only.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = "dexpi 1.3/example pids/C08 Two connected P&IDs (Covestro)/C08V01/"
FILES = ("LICENSE", SOURCE + "COV PCS Connections List.xlsm", SOURCE + "COV Instrument List.xlsm")
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def sheet_values(path, name):
    """Literal cell values, preserving source coordinates and missing versus empty cells."""
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(t.text or "" for t in si.findall(".//s:t", NS))
                      for si in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = {r.attrib["Id"]: r.attrib["Target"]
                for r in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        sheet = next(s for s in workbook.find("s:sheets", NS) if s.attrib["name"] == name)
        target = rels[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
        member = target.lstrip("/") if target.startswith("/") else "xl/" + target
        result = {}
        for cell in ET.fromstring(archive.read(member)).findall("s:sheetData/s:row/s:c", NS):
            if cell.find("s:f", NS) is not None:
                raise ValueError(f"{path.name}: {name}!{cell.attrib['r']}: formula not supported")
            value = cell.find("s:v", NS)
            text = value.text if value is not None else None
            if cell.attrib.get("t") == "s" and text is not None:
                text = shared[int(text)]
            elif cell.attrib.get("t") == "inlineStr":
                text = "".join(t.text or "" for t in cell.findall(".//s:t", NS))
            if text is not None:
                result[cell.attrib["r"]] = text
        return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=ROOT / "data/external/dexpi-ttc-all")
    ap.add_argument("--csv", type=Path, default=HERE / "connections.csv")
    ap.add_argument("--fetch", action="store_true", help="fetch only the three pinned originals if missing")
    ap.add_argument("--max-mb", type=float, default=1, help="maximum missing-source download, decimal MB")
    args = ap.parse_args()
    if not math.isfinite(args.max_mb) or args.max_mb < 0:
        raise ValueError("--max-mb must be finite and nonnegative")
    spec = importlib.util.spec_from_file_location("covestro_fetch", ROOT / "scripts/fetch_corpus.py")
    fetcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetcher)
    pins = json.loads((ROOT / "data/corpus_pins.json").read_text(encoding="utf-8"))["dexpi-ttc-all"]
    selected = {name: pins[name] for name in FILES}
    if args.fetch:
        try:
            receipt = fetcher.fetch_pinned("dexpi-ttc-all", args.max_mb, args.cache,
                                           pins={"dexpi-ttc-all": selected})
        except fetcher.PinError as exc:
            raise ValueError(str(exc)) from None
        print(f"Fetched {receipt['fetched_mb']} MB; scope: three originals only, not the full DEXPI corpus.")
    originals = {}
    for name, pin in selected.items():
        path = args.cache / fetcher.DEXPI_PREFIX / name
        if not path.is_file():
            raise ValueError(f"Missing original: {name}; no source check ran. Use --fetch or --cache.")
        raw = path.read_bytes()
        if len(raw) != pin["bytes"] or hashlib.sha256(raw).hexdigest() != pin["sha256"]:
            raise ValueError(f"Original differs from pin: {name}")
        originals[name] = path
    cells = sheet_values(originals[FILES[1]], "Sheet1")
    # Fixed-case transcription, not a generic workbook or controls-export importer.
    columns = "ABCDEFGHIJKLMNOPQRS"
    expected = [["source_sheet", "source_row"] + [cells[c + "1"] for c in columns]]
    for row in range(2, 9):
        expected.append(["Sheet1", str(row)] + [cells.get(c + str(row), "") for c in columns])
    if set(cells) - {c + str(r) for c in columns for r in range(1, 9)}:
        raise ValueError("Unexpected populated connection cells outside A1:S8")
    actual = list(csv.reader(io.StringIO(args.csv.read_text(encoding="utf-8-sig"))))
    if actual != expected:
        raise ValueError("CSV differs from all seven original connection rows/headings; no match claimed")
    instruments = sheet_values(originals[FILES[2]], "Sheet1")
    # Verify the exact source observations cited in README, without interpreting their engineering meaning.
    observations = {"J8": "S", "AP8": "COVPIL1-V999-LA01-U0001", "P8": "UER-2345678",
                    "J66": "C", "AP66": "COVPIL1-V999-TA99-U0020", "P66": "UER-1234567"}
    for cell, value in observations.items():
        if instruments.get(cell) != value:
            raise ValueError(f"Instrument source observation differs: Sheet1!{cell}")
    print("Three pinned originals verified; CSV matches all seven connection records and 19 source columns.")
    print("Six cited instrument cells match. No control logic, drawing match or loop-audit score established.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration, zipfile.BadZipFile, ET.ParseError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
