"""Local one-sheet PNG + existing extraction -> unverified review bundle (stdlib only).

This imports supplied extraction; it never calls a model, traces, scores, connects
signals or approves operations. Input schema: site-drawing-intake-1. See --help.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import zlib

import build_twin
import generate
import pi_mapping

SCHEMA = "site-drawing-intake-1"
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_IMAGE_BYTES = 100 * 1024 * 1024
MAX_PIXELS = 50_000_000
CLASSES = frozenset(("tank", "pump", "valve", "instrumentation", "inlet/outlet", "general"))
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
LIMITATIONS = [
    "Imported extraction and producer claims were supplied, not independently verified; no model was run.",
    "PNG structure and CRCs checked, not full pixel decoding, readability or revision authority.",
    "Class roles, tag conventions, linked parents and geometry fallback require engineering review.",
    "Connections are unverified undirected adjacency; SVG segments are logical links, not pipe routes.",
    "Supplied confidence and the existing 0.75 highlighting rule are uncalibrated for this drawing; no trained risk model was applied.",
    "No point mapping, signal identity, range, quality, native import or operational approval was established.",
    "Draft-only status is descriptive metadata, not a technical deployment interlock in other tools.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def read_bounded(path, limit):
    require(path.is_file(), f"Not a local regular file: {path}")
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    require(len(content) <= limit, f"Input exceeds {limit} byte limit: {path}")
    return content


def strict_json(content):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    def decimal(value):
        number = float(value)
        require(math.isfinite(number), f"Non-finite JSON number: {value}")
        return number

    return json.loads(content.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant, parse_float=decimal)


def safe_text(value, allow_whitespace=False):
    """Narrow export boundary: reject spreadsheet formulas and invalid XML text."""
    if not isinstance(value, str) or len(value) > 4096:
        return False
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return False
    return all((allow_whitespace and c in "\t\r\n") or (ord(c) >= 32
               and not 0xD800 <= ord(c) <= 0xDFFF and ord(c) not in (0xFFFE, 0xFFFF)) for c in value)


def text_field(obj, key, optional=False):
    value = obj.get(key)
    if optional and value is None:
        return None
    require(safe_text(value) and bool(value.strip()), f"{key} must be nonempty export-safe text (no controls, invalid XML characters or formula prefixes)")
    return value


def png_dimensions(content):
    """Bounded PNG container checks only. Does not decompress or interpret pixels."""
    require(content[:8] == b"\x89PNG\r\n\x1a\n", "Image must be a PNG")
    offset, chunks, dimensions = 8, [], None
    seen_idat, ended_idat = False, False
    while offset < len(content):
        require(offset + 12 <= len(content), "Truncated PNG chunk")
        length = struct.unpack(">I", content[offset:offset + 4])[0]
        end = offset + 12 + length
        require(end <= len(content), "Truncated PNG chunk payload")
        kind = content[offset + 4:offset + 8]
        payload = content[offset + 8:offset + 8 + length]
        expected = struct.unpack(">I", content[offset + 8 + length:end])[0]
        require(zlib.crc32(kind + payload) & 0xffffffff == expected, "PNG chunk CRC mismatch")
        require(bool(re.fullmatch(b"[A-Za-z]{4}", kind)), "Invalid PNG chunk type")
        require(kind[0] & 32 or kind in (b"IHDR", b"PLTE", b"IDAT", b"IEND"), "Unsupported critical PNG chunk")
        require(not kind[2] & 32, "Invalid PNG reserved chunk bit")
        require(kind not in (b"acTL", b"fcTL", b"fdAT"), "Animated PNG is unsupported; supply one rasterized page")
        if not chunks:
            require(kind == b"IHDR" and length == 13, "PNG must start with a 13-byte IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            require(width > 0 and height > 0 and width * height <= MAX_PIXELS, "PNG dimensions exceed supported bounds")
            depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
            require(color in depths and depth in depths[color] and compression == filtering == 0
                    and interlace in (0, 1), "Unsupported or invalid PNG IHDR")
            dimensions = [width, height]
        else:
            require(kind != b"IHDR", "Duplicate PNG IHDR")
        if kind == b"PLTE":
            require(not seen_idat and b"PLTE" not in chunks and color not in (0, 4)
                    and 0 < length <= 768 and length % 3 == 0, "Invalid PNG palette")
            require(color != 3 or length // 3 <= 2 ** depth, "PNG palette exceeds bit depth")
        if kind == b"IDAT":
            require(color != 3 or b"PLTE" in chunks, "Indexed PNG requires a preceding palette")
            require(not ended_idat, "PNG IDAT chunks must be consecutive")
            seen_idat = True
        elif seen_idat:
            ended_idat = True
        chunks.append(kind)
        offset = end
        if kind == b"IEND":
            require(length == 0 and offset == len(content), "Invalid PNG end or trailing bytes")
            break
    require(chunks and chunks[-1] == b"IEND" and seen_idat, "PNG needs IDAT and IEND chunks")
    return dimensions


def validate_prediction(pred):
    require(isinstance(pred, dict), "prediction must be an object")
    require(isinstance(pred.get("symbols"), list) and bool(pred["symbols"]), "symbols must be a nonempty list")
    require(isinstance(pred.get("connections"), list), "connections must be a list")
    symbols, ids = [], set()
    for index, symbol in enumerate(pred["symbols"]):
        require(isinstance(symbol, dict), f"symbols[{index}] must be an object")
        sid = symbol.get("id")
        require(isinstance(sid, str) and SAFE_ID.fullmatch(sid) is not None, f"symbols[{index}] has an unsafe or empty id")
        require(sid not in ids, f"Duplicate symbol id: {sid}")
        ids.add(sid)
        require(isinstance(symbol.get("class"), str) and symbol["class"] in CLASSES, f"Unsupported class for {sid}")
        tag = symbol.get("tag")
        require(tag is None or safe_text(tag, allow_whitespace=True), f"Invalid tag for {sid}")
        conf = symbol.get("confidence")
        require(conf is None or finite(conf) and 0 <= conf <= 1, f"Invalid confidence for {sid}")
        require(not ("box" in symbol and "bbox" in symbol), f"Ambiguous box and bbox for {sid}")
        box = symbol.get("box")
        if "bbox" in symbol:
            bbox = symbol["bbox"]
            require(isinstance(bbox, dict) and set(bbox) == {"x_min", "y_min", "x_max", "y_max"}, f"Invalid bbox for {sid}")
            box = [bbox[k] for k in ("x_min", "y_min", "x_max", "y_max")]
        require(isinstance(box, list) and len(box) == 4 and all(finite(v) and 0 <= v <= 1000 for v in box),
                f"Box for {sid} needs four finite coordinates in [0, 1000]")
        require(box[0] < box[2] and box[1] < box[3], f"Box for {sid} is reversed or degenerate")
        # Converter rounds to one decimal; reject geometry it would collapse.
        require(round(box[0], 1) < round(box[2], 1) and round(box[1], 1) < round(box[3], 1),
                f"Box for {sid} collapses at converter precision")
        symbols.append({"id": sid, "class": symbol["class"], "tag": tag, "confidence": conf, "box": box})
    connections, seen = [], set()
    for index, link in enumerate(pred["connections"]):
        require(isinstance(link, dict), f"connections[{index}] must be an object")
        a, b = link.get("from"), link.get("to")
        require(isinstance(a, str) and isinstance(b, str) and a in ids and b in ids,
                f"Unknown connection endpoint at {index}")
        require(a != b, f"Self-link at connection {index}")
        key = frozenset((a, b))
        require(key not in seen, f"Duplicate undirected connection at {index}")
        seen.add(key)
        connections.append({"from": a, "to": b})
    return {"symbols": symbols, "connections": connections}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_inputs(manifest_path, out):
    manifest_path = Path(manifest_path).resolve()
    raw_manifest = read_bounded(manifest_path, MAX_JSON_BYTES)
    manifest = strict_json(raw_manifest)
    require(isinstance(manifest, dict), "Manifest must be an object")
    require(manifest.get("schema_version") == SCHEMA, f"schema_version must be {SCHEMA}")
    identity = {k: text_field(manifest, k) for k in ("drawing_id", "revision")}
    page = manifest.get("page")
    require(type(page) is int and page > 0, "page must be a positive integer")
    identity["page"] = page
    paths = {k: (manifest_path.parent / text_field(manifest, k)).resolve() for k in ("image", "extraction")}
    out = Path(out).absolute()
    require(not out.exists() and not out.is_symlink(), f"Output already exists: {out}")
    require(out.parent.is_dir(), "Output parent directory must already exist")
    resolved_out = out.resolve()
    for source in (manifest_path, *paths.values()):
        require(source != resolved_out and not source.is_relative_to(resolved_out), "Output overlaps an input")
    image = read_bounded(paths["image"], MAX_IMAGE_BYTES)
    dimensions = png_dimensions(image)
    original = read_bounded(paths["extraction"], MAX_JSON_BYTES)
    record = strict_json(original)
    require(isinstance(record, dict), "Extraction JSON must be an object")
    fmt = manifest.get("extraction_format")
    require(fmt in ("prediction", "run-record"), "extraction_format must be prediction or run-record")
    if fmt == "run-record":
        require(not record.get("error") and not record.get("parse_error"), "Failed extraction record cannot be imported")
        if record.get("image_sha256") is not None:
            require(record["image_sha256"] == digest(image), "Run record image_sha256 does not match image")
        prediction = validate_prediction(record.get("prediction"))
    else:
        prediction = validate_prediction(record)
    producer = manifest.get("producer")
    require(isinstance(producer, dict), "producer must describe the supplied extraction")
    producer = {k: text_field(producer, k, optional=k == "model") for k in ("method", "tool", "model")}
    register = {k: text_field(manifest, k, optional=True) for k in ("drawing_number", "system_code", "system_name")}
    sources = {k: {"original_filename": paths[k].name, "sha256": digest(content), "bytes": len(content),
                   "bundle_path": "source/0.png" if k == "image" else "source/extraction-original.json"}
               for k, content in (("image", image), ("extraction", original))}
    provenance = {"schema_version": SCHEMA, "drawing": identity, "internal_sheet": "0", "sources": sources,
                  "manifest_sha256": digest(raw_manifest), "image_size_px": dimensions,
                  "supplied_producer": producer,
                  "supplied_record_producer": {k: record.get(k) for k in ("tool", "model")} if fmt == "run-record" else None,
                  "extraction_format": fmt, "normalized_record": "source/0.json", "original_manifest": "source/intake-manifest-original.json", "limitations": LIMITATIONS,
                  "normalization": "Only supported symbols and connections are converted. Extra input fields remain in the preserved original; tag whitespace and box precision follow build_twin.",
                  "importer_sha256": digest(Path(__file__).read_bytes()),
                  "converter_sha256": digest(Path(build_twin.__file__).read_bytes()),
                  "generator_sha256": digest(Path(generate.__file__).read_bytes()),
                  "pi_mapping_sha256": digest(Path(pi_mapping.__file__).read_bytes())}
    return out, image, original, raw_manifest, prediction, producer, register, provenance


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def import_drawing(manifest_path, out, check_only=False):
    out, image, original, raw_manifest, prediction, producer, register, provenance = load_inputs(manifest_path, out)
    if check_only:
        return {"inputs_valid": True, "exports_written": False, "drawing": provenance["drawing"], "limitations": LIMITATIONS}
    stage = Path(tempfile.mkdtemp(prefix=".site-intake-", dir=out.parent))
    try:
        source = stage / "source"
        source.mkdir()
        (source / "0.png").write_bytes(image)
        (source / "extraction-original.json").write_bytes(original)
        (source / "intake-manifest-original.json").write_bytes(raw_manifest)
        write_json(source / "0.json", {"tool": producer["tool"], "model": producer["model"],
                   "prediction": prediction, "image_sha256": digest(image), "intake": provenance})
        model = build_twin.build("supplied-extraction", source, ["0"], source, {"0": register},
                                 "site-drawing", parent_rule="linked")
        model["meta"]["source_document"] = f"{provenance['drawing']['drawing_id']}, revision {provenance['drawing']['revision']}, page {provenance['drawing']['page']}"
        model["meta"]["extraction_method"] = "Imported supplied extraction; no model or tracer executed by this intake"
        model["meta"]["intake"] = provenance
        model["meta"]["review_requirements"] = {"draft_review_exports_allowed": True, "operational_export_allowed": False,
                    "status_scope": "Descriptive intake readiness only; not an enforced deployment interlock", "blockers": LIMITATIONS[2:6]}
        evidence = {"source_manifest": "intake_manifest.json", "source_drawing": provenance["drawing"],
                    "image_sha256": digest(image), "extraction_sha256": digest(original)}
        for system in model["systems"]:
            system["source_run"] = "source/0.json"
            system.update(evidence)
        for collection in ("units", "instruments", "line_items", "offpage_connectors"):
            for item in model[collection]:
                for appearance in item["provenance"]:
                    appearance["source_run"] = "source/0.json"
                    appearance.update(evidence)
        for stream in model["streams"]:
            stream["source_evidence"] = evidence
        require(not model["dropped"]["symbols"] and not model["dropped"]["connections"], "Converter dropped input items")
        problems = generate.validate_twin(model)
        require(not problems, f"Converted model is invalid: {problems}")
        generate.export_twin(model, stage, images_dir=source)
        write_json(stage / "plant_model.json", model)
        write_json(stage / "intake_manifest.json", provenance)
        (stage / "READ_ME.txt").write_text("UNVERIFIED LOCAL REVIEW BUNDLE\n\n" + "\n".join(LIMITATIONS)
                    + "\n\nSource paths are relative to this bundle. Keep source/ with the model and SVG files.\n", encoding="utf-8")
        require(not out.exists() and not out.is_symlink(), f"Output appeared while preparing bundle: {out}")
        os.rename(stage, out)
        return {"inputs_valid": True, "exports_written": True, "output": str(out), "summary": model["summary"],
                "operational_export_allowed": False, "limitations": LIMITATIONS}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog="Manifest fields: schema_version=site-drawing-intake-1, drawing_id, revision, page, image, extraction, extraction_format=prediction|run-record, producer={method,tool,model}; optional drawing_number, system_code, system_name. PNG and JSON paths are relative to the manifest or absolute local paths. Output must be new, with an existing parent. PNG container checks are not pixel decoding. Publication uses a sibling staging directory; concurrent writers to the same destination are unsupported.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--check-only", action="store_true", help="validate inputs without writing; does not test conversion or exports")
    args = parser.parse_args(argv)
    try:
        result = import_drawing(args.manifest, args.out, args.check_only)
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError) as error:
        parser.exit(2, f"Site drawing intake failed: {error}\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
