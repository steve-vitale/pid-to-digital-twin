"""Explicit optional local Native/complete-evidence handoff. No reference discovery."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

import source_evidence as source

MAX_INPUT = 33554432
MAX_BRIEF = 2097152
SCHEMA = "native-source-handoff-1"
NAMES = ("native.model.json", "source.evidence.json", "handoff.manifest.json")
HEX = re.compile(r"[0-9a-f]{64}\Z")
Error = source.SourceEvidenceError


def _require(ok, message):
    if not ok:
        raise Error(message)


def _acquire(stream):
    chunks, total = [], 0
    while total < MAX_INPUT + 1:
        chunk = stream.read(min(65536, MAX_INPUT + 1 - total))
        _require(type(chunk) is bytes, "invalid binary input")
        if chunk == b"":
            return b"".join(chunks)
        total += len(chunk)
        _require(total <= MAX_INPUT, "selected input exceeds 32MiB")
        chunks.append(chunk)
    raise Error("selected input exceeds 32MiB")


def _read(path):
    with path.open("rb") as stream:
        return _acquire(stream)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return source._native_encoding_bytes(value)


def _parse(raw):
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise Error("invalid strict JSON input") from None
    value = source.load_json_strict(text)
    _canonical(value)
    return value


def _pretty(value):
    _canonical(value)
    return (json.dumps(value, ensure_ascii=False, indent=1, allow_nan=False) + "\n").encode("utf-8")


def _fields(obj, names):
    _require(type(obj) is dict and set(obj) == set(names.split()), "invalid handoff fields")


def _string(value):
    _require(type(value) is str and len(value) > 0, "invalid handoff declaration")
    _canonical(value)


def _hex(value):
    _require(type(value) is str and HEX.fullmatch(value) is not None, "invalid handoff digest")


def _size(value, maximum):
    _require(type(value) is int and 0 <= value <= maximum, "invalid handoff byte size")


def _handoff(value):
    _fields(value, "owned_scope responsible_role company_release_reference company_release_state")
    _string(value["owned_scope"])
    _string(value["responsible_role"])
    ref = value["company_release_reference"]
    _require(type(ref) is dict and type(ref.get("present")) is bool, "invalid company reference")
    _fields(ref, "present value" if ref["present"] else "present")
    if ref["present"]:
        _string(ref["value"])
    _require(value["company_release_state"] == "not_evaluated", "invalid company release state")


def _package_id(manifest):
    return "source-handoff:" + _sha(_canonical({k: v for k, v in manifest.items() if k != "package_id"}))


def _validate(manifest, native, packet, native_raw, evidence_raw):
    # Validate canonical encodability before any semantic hashing/packet admission.
    for value in (manifest, native, packet):
        _canonical(value)
    _require(type(native) is dict and "source_evidence" not in native, "invalid native projection")
    source.validate_packet(packet, native_model=native, require_native_targets=True)
    _fields(manifest, "schema required_capabilities package_id document native evidence provenance handoff")
    _require(manifest["schema"] == SCHEMA and manifest["required_capabilities"] == [SCHEMA],
             "unknown handoff schema/capability")
    d, n, e, p = (manifest[k] for k in ("document", "native", "evidence", "provenance"))
    _fields(d, "document_id raw_source_sha256 raw_size_bytes")
    _string(d["document_id"])
    _hex(d["raw_source_sha256"])
    _size(d["raw_size_bytes"], 268435456)
    _require(all(type(d[k]) is type(packet["document"][k]) and d[k] == packet["document"][k] for k in d),
             "handoff document mismatch")
    _fields(n, "file size_bytes raw_sha256 canonical_sha256")
    _fields(e, "file size_bytes raw_sha256 packet_schema packet_integrity_sha256")
    for obj, raw, name in ((n, native_raw, NAMES[0]), (e, evidence_raw, NAMES[1])):
        _require(obj["file"] == name, "invalid handoff role name")
        _size(obj["size_bytes"], MAX_INPUT)
        _hex(obj["raw_sha256"])
        _require(obj["size_bytes"] == len(raw) and obj["raw_sha256"] == _sha(raw), "handoff raw binding mismatch")
    _hex(n["canonical_sha256"])
    _require(n["canonical_sha256"] == _sha(_canonical(native)) == packet["native_model_sha256"],
             "handoff native binding mismatch")
    _hex(e["packet_integrity_sha256"])
    _require(e["packet_schema"] == source.SCHEMA == packet["schema"] and
             e["packet_integrity_sha256"] == packet["integrity_sha256"], "handoff evidence mismatch")
    _fields(p, "embedded_input_size_bytes embedded_input_raw_sha256 exporter_sha256 validator_sha256 capture_method_attestation")
    _size(p["embedded_input_size_bytes"], MAX_INPUT)
    for key in ("embedded_input_raw_sha256", "exporter_sha256", "validator_sha256"):
        _hex(p[key])
    _require(p["capture_method_attestation"] == "not_provided", "invalid capture attestation")
    _handoff(manifest["handoff"])
    _require(type(manifest["package_id"]) is str and manifest["package_id"] == _package_id(manifest),
             "handoff package identity mismatch")


def _code_hashes():
    return _sha(_read(Path(__file__).resolve())), _sha(_read(Path(source.__file__).resolve()))


def _brief(manifest, packet, manifest_raw, operation, format):
    inspector, validator = _code_hashes()
    brief = {"schema": "native-source-handoff-brief-1", "operation": operation,
             "package_id": manifest["package_id"], "document": manifest["document"],
             "native": manifest["native"], "evidence": manifest["evidence"],
             "manifest": {"file": NAMES[2], "size_bytes": len(manifest_raw), "raw_sha256": _sha(manifest_raw)},
             "completeness": packet["completeness"], "handoff": manifest["handoff"],
             "declared_provenance": manifest["provenance"],
             "receiving_validation": {"inspector_sha256": inspector, "validator_sha256": validator,
                 "artifact_basis": "validated_export_bytes" if operation == "export" else "actual_selected_files"},
             "comparison": "not_compared", "application_status": "unverified", "external_originals": "not_reverified"}
    _canonical(brief)
    if format == "json":
        raw = _canonical(brief) + b"\n"
    else:
        raw = b"Native/source handoff summary\n" + json.dumps(
            brief, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"
    _require(len(raw) <= MAX_BRIEF, "handoff summary exceeds 2MiB")
    return raw


def _identity(path):
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_mode)


def _root(value):
    root = Path(value).resolve(strict=True)
    _require(root.is_dir(), "approved root must be a directory")
    return root


def _selected(root, value, *, regular=False):
    path = Path(value).resolve(strict=regular)
    _require(path.is_relative_to(root), "selected path escapes approved root")
    if regular:
        _require(stat.S_ISREG(path.stat().st_mode), "selected input must be a regular file")
    return path


def _chain(path):
    # Record every existing ancestor: a replaced parent is not the selected directory.
    return {p: _identity(p) for p in (path, *path.parents) if p.exists()}


def _check_chain(snapshot):
    _require(all(p.exists() and _identity(p) == identity for p, identity in snapshot.items()),
             "selected filesystem identity changed")


def _distinct(paths):
    _require(len(set(paths)) == len(paths), "selected file alias")
    existing = [p for p in paths if p.exists()]
    _require(len({_identity(p)[:2] for p in existing}) == len(existing), "selected file alias")


def _role_paths(root, values):
    paths = []
    for value, name in zip(values, NAMES):
        _require(Path(value).name == name, "invalid selected role basename")
        paths.append(_selected(root, value, regular=True))
        _require(paths[-1].name == name, "invalid resolved role basename")
    _require(len({p.parent for p in paths}) == 1, "selected roles require one package parent")
    _distinct(paths)
    return paths


def _inspect(args):
    root = _root(args.root)
    paths = _role_paths(root, (args.native, args.evidence, args.manifest))
    snapshots = [_chain(p) for p in paths]
    raws = [_read(p) for p in paths]
    native, packet, manifest = [_parse(raw) for raw in raws]
    _validate(manifest, native, packet, raws[0], raws[1])
    brief = _brief(manifest, packet, raws[2], "inspect", args.format)
    for selected, p, raw, snapshot in zip((args.native, args.evidence, args.manifest), paths, raws, snapshots):
        _check_chain(snapshot)
        _require(_selected(root, selected, regular=True) == p and _read(p) == raw, "selected bytes changed")
    return brief


def _write_exclusive(path, raw):
    with path.open("xb") as stream:
        view = memoryview(raw)
        while view:
            count = stream.write(view)
            if not count:
                raise OSError("short artifact write")
            view = view[count:]


def _export(args):
    root = _root(args.root)
    # Retain lexical selections as well as resolved paths to detect changed junctions.
    input_path = _selected(root, args.embedded_model, regular=True)
    output = _selected(root, args.out)
    _require(not output.exists() or output.is_dir(), "package parent must be a directory")
    paths = [output / name for name in NAMES]
    _distinct([input_path, *paths])
    _require(not any(p.exists() or p.is_symlink() for p in paths), "handoff target already exists")
    input_snapshot, parent_snapshot = _chain(input_path), _chain(output)
    raw = _read(input_path)
    model = _parse(raw)
    _require(type(model) is dict and "source_evidence" in model, "embedded source packet required")
    packet = model["source_evidence"]
    native = {k: v for k, v in model.items() if k != "source_evidence"}
    source.validate_packet(packet, native_model=model, require_native_targets=True)
    handoff = {"owned_scope": args.owned_scope, "responsible_role": args.responsible_role,
               "company_release_reference": {"present": False} if args.company_reference is None else
                   {"present": True, "value": args.company_reference}, "company_release_state": "not_evaluated"}
    _handoff(handoff)
    native_raw, evidence_raw = _pretty(native), _pretty(packet)
    exporter, validator = _code_hashes()
    manifest = {"schema": SCHEMA, "required_capabilities": [SCHEMA], "package_id": "",
        "document": {k: packet["document"][k] for k in ("document_id", "raw_source_sha256", "raw_size_bytes")},
        "native": {"file": NAMES[0], "size_bytes": len(native_raw), "raw_sha256": _sha(native_raw),
                   "canonical_sha256": _sha(_canonical(native))},
        "evidence": {"file": NAMES[1], "size_bytes": len(evidence_raw), "raw_sha256": _sha(evidence_raw),
                     "packet_schema": packet["schema"], "packet_integrity_sha256": packet["integrity_sha256"]},
        "provenance": {"embedded_input_size_bytes": len(raw), "embedded_input_raw_sha256": _sha(raw),
                       "exporter_sha256": exporter, "validator_sha256": validator,
                       "capture_method_attestation": "not_provided"}, "handoff": handoff}
    manifest["package_id"] = _package_id(manifest)
    manifest_raw = _canonical(manifest) + b"\n"
    raws = [native_raw, evidence_raw, manifest_raw]
    _require(all(len(b) <= MAX_INPUT for b in raws), "generated handoff artifact exceeds 32MiB")
    _validate(manifest, native, packet, native_raw, evidence_raw)
    brief = _brief(manifest, packet, manifest_raw, "export", "text")
    completed = []

    def recheck():
        _check_chain(input_snapshot)
        _check_chain(parent_snapshot)
        _require(_selected(root, args.embedded_model, regular=True) == input_path and
                 _selected(root, args.out) == output, "selected filesystem identity changed")
        _require(_read(input_path) == raw, "selected input bytes changed")
        _distinct([input_path, *paths])
        for i, path in enumerate(paths):
            if i < len(completed):
                _require(_identity(path) == completed[i] and _read(path) == raws[i], "written artifact changed")
            else:
                _require(not path.exists() and not path.is_symlink(), "handoff target already exists")

    recheck()  # Before even creating the directory: a refusal leaves no output.
    begun = False
    try:
        output.mkdir(parents=True, exist_ok=True)
        parent_snapshot = _chain(output)
        for path, artifact in zip(paths, raws):
            recheck()
            begun = True
            _write_exclusive(path, artifact)
            completed.append(_identity(path))
        recheck()
    except (OSError, Error):
        if begun:
            raise Error("incomplete handoff operation; explicit inspect required") from None
        raise
    return brief


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    for name in ("root", "embedded-model", "out", "owned-scope", "responsible-role"):
        export.add_argument("--" + name, required=True)
    export.add_argument("--company-reference")
    inspect = commands.add_parser("inspect")
    for name in ("root", "native", "evidence", "manifest"):
        inspect.add_argument("--" + name, required=True)
    inspect.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        brief = _export(args) if args.command == "export" else _inspect(args)
        sys.stdout.buffer.write(brief)
        sys.stdout.buffer.flush()
    except Error as exc:
        # All SourceEvidenceError messages come from fixed local validation literals.
        print("handoff refused: " + str(exc), file=sys.stderr)
        return 1
    except OSError:
        print("handoff I/O failure; operation may be incomplete; explicit inspect required", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
