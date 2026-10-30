"""Actual offline review/generation CLI controls on a TE simulation model copy. No native import or plant review.

Default checks the committed projection, unassigned SVG and result JSON; --write deliberately refreshes them.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / "data/te_process_model.json"
ORPHANS = {"FT-102", "FT-103", "FV-102", "FV-103", "FV-101"}
EXCLUDED = {"FT-101", "FV-119"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def resolved_ignition(document):
    """Resolve the exported seed's parameter claims locally; does not connect to or validate a gateway."""
    types = {n["name"]: n for n in document["tags"][0]["tags"]}
    found, units = {}, set()

    def prop(value, params):
        if isinstance(value, dict):
            return re.sub(r"\{([^{}]+)\}", lambda m: str(params[m[1]]), value["binding"])
        return value

    def walk(node, path="", params=None):
        path = path + ("/" if path and node["name"] else "") + node["name"]
        if node.get("tagType") == "UdtInstance":
            units.add(node["name"])
            definition = types[node["typeId"]]
            values = {k: v["value"] for k, v in definition.get("parameters", {}).items()}
            values.update({k: v["value"] for k, v in node.get("parameters", {}).items()})
            for child in definition["tags"]:
                walk(child, path, values)
        elif node.get("tagType") == "AtomicTag":
            tag = node["documentation"].split(" | ")[0]
            found[tag] = {"path": path, "server": prop(node["opcServer"], params or {}),
                          "item": prop(node["opcItemPath"], params or {}), "uom": node["engUnit"],
                          "read_only": node["readOnly"]}
        else:
            for child in node.get("tags", []):
                walk(child, path, params)

    walk(document["tags"][1])
    return found, units


def demonstrate(write=False):
    original = SOURCE.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        model, output = base / "model.json", base / "exports"
        model.write_bytes(original)

        def command(script, *args, success=True):
            p = subprocess.run([sys.executable, "-S", str(ROOT / "scripts" / script), *map(str, args)], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8")
            assert (p.returncode == 0) == success, p.stdout + p.stderr
            return p

        def generate():
            command("generate.py", model, "--out", output)
            return resolved_ignition(read(output / "ignition/te_tags.json"))

        def review(csv_name, record):
            command("apply_review.py", model, HERE / csv_name,
                    "--reviewer", "Illustrative software control, not a plant review", "--date", "2026-10-30",
                    "--record-dir", base / record)

        before, before_units = generate()
        original_files = {name: (output / name).read_text(encoding="utf-8")
                          for name in read(output / "seed_export_manifest.json")["files"]
                          if name != "seed_review_projection.json"}
        for name, content in original_files.items():
            assert content == (ROOT / "out" / name).read_text(encoding="utf-8"), f"Historical output changed: {name}"
        review("reject.csv", "first-records")
        reviewed_bytes = model.read_bytes()
        after, units_after = generate()
        assert model.read_bytes() == reviewed_bytes
        assert "U-100" not in units_after and "U-100" in before_units
        assert not EXCLUDED & set(after)
        assert ORPHANS <= set(after)
        for tag in set(after):
            assert {k: after[tag][k] for k in ("server", "item", "uom", "read_only")} == {
                k: before[tag][k] for k in ("server", "item", "uom", "read_only")}, tag
        for tag in ORPHANS:
            assert "/_Unassigned/" in after[tag]["path"]
        assert not (output / "svg/U-100.svg").exists()
        overview = ET.fromstring((output / "svg/overview.svg").read_text(encoding="utf-8"))
        assert not any(n.get("data-asset") == "U-100" or n.get("data-tag") in EXCLUDED
                       or n.get("data-stream") in {"S1", "S2", "S3", "S5", "S6", "S9"} for n in overview.iter())
        pi_rows = list(csv.DictReader(io.StringIO((output / "pi/pi_builder_af.csv").read_text(encoding="utf-8-sig"))))
        assert not any(r["ObjectType"] == "Element" and r["Name"] == "U-100" for r in pi_rows)
        for tag in ORPHANS:
            row = next(r for r in pi_rows if r["AttributeConfigString"].endswith(f".{tag}.PV"))
            assert row["Parent"] == "TE Plant\\_Unassigned" and row["Selected(x)"] == "x"
        assert not any(r["AttributeConfigString"].endswith(tuple(f".{tag}.PV" for tag in EXCLUDED)) for r in pi_rows)
        projection = (output / "seed_review_projection.json").read_text(encoding="utf-8")
        orphan_svg = (output / "svg/_Unassigned.svg").read_text(encoding="utf-8")
        packet = {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob("*") if p.is_file()}
        review("reject.csv", "repeat-records")
        assert model.read_bytes() == reviewed_bytes
        generate()
        assert packet == {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob("*") if p.is_file()}
        # A manual edit in a managed file must survive a refused refresh.
        edited = output / "svg/_Unassigned.svg"
        edited.write_text(orphan_svg + "<!-- manual annotation -->", encoding="utf-8")
        snapshot = {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}
        refused = command("generate.py", model, "--out", output, success=False)
        assert "differs from its inventory" in refused.stderr
        assert snapshot == {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}
        edited.write_bytes(packet["svg/_Unassigned.svg"])
        review("reconfirm.csv", "reconfirmed-records")
        restored, restored_units = generate()
        assert restored == before and restored_units == before_units
        assert not (output / "svg/_Unassigned.svg").exists()
        assert (output / "svg/U-100.svg").exists()
        review_rows = list(csv.DictReader(io.StringIO((output / "ops_review_sheet.csv").read_text(encoding="utf-8-sig"))))
        assert all(next(r for r in review_rows if r["item_id"] == tag)["OPS_confirm_or_correct"] == "confirm"
                   for tag in {"U-100", "FT-101", "FV-119", "S9"})
        source = read(model)
        records = {r.get("id") or r.get("tag"): r for sec in ("units", "streams", "instruments", "final_elements")
                   for r in source[sec]}
        assert all(len(records[tag]["ops_review"]["history"]) >= 1 for tag in {"U-100", "FT-101", "FV-119", "S9"})
        assert SOURCE.read_bytes() == original
        result = {"scope": "Fictional decisions on a TE simulation model copy; no plant review or native import.",
                  "historical_artifact_contents_unchanged": len(original_files),
                  "new_bundle_files": ["seed_export_manifest.json", "seed_review_projection.json"],
                  "rejected_unit_absent": "U-100", "rejected_signals_absent": sorted(EXCLUDED),
                  "unassigned_signals": sorted(ORPHANS), "all_surviving_signal_address_claims_unchanged": True,
                  "repeat_review_and_generation_unchanged": True, "manual_edit_refusal_preserves_all_bytes": True,
                  "reconfirmation_restores_paths_and_addresses": True, "obsolete_unassigned_svg_removed": True,
                  "source_and_intervening_review_history_retained": True,
                  "source_semantic_sha256": hashlib.sha256(json.dumps(json.loads(original), sort_keys=True,
                                                                     separators=(",", ":")).encode()).hexdigest()}
        generated = {"expected.json": json.dumps(result, indent=2) + "\n",
                     "seed_review_projection.json": projection, "_Unassigned.svg": orphan_svg}
        for name, content in generated.items():
            path = HERE / "expected" / name
            if write:
                path.parent.mkdir(exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
            else:
                assert path.read_text(encoding="utf-8") == content, f"Stale expected/{name}"
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps(demonstrate(args.write), indent=2))
