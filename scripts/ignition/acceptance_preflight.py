"""Offline current-candidate preflight and captured-quality checks. Stdlib only.

Never imports gateway helpers, reads credentials, starts processes, or contacts a target.
A PASS is a local file check, not native Ignition acceptance. Runtime stages remain
NOT RUN: an authorized operator must collect and review native evidence separately.

Usage:
  python -S scripts/ignition/acceptance_preflight.py
  python -S scripts/ignition/acceptance_preflight.py --observations capture.json
  python -S scripts/ignition/acceptance_preflight.py --require-native

JSON goes to stdout; redirect it to a new local receipt if desired. No files are changed.
Exit 0: offline checks passed; 2: invalid/missing candidate or observations;
3: --require-native requested but native acceptance remains NOT RUN.
"""
import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
REVIEW = "out/review/current-gateway-2026-10-10"
ARTIFACTS = {
    "out/ignition/gateway/PIDTwin.zip",
    "out/ignition/gateway/twin_provider.json",
    "out/ignition/gateway/build_meta.json",
}
# Fixed inventory for this reviewed candidate. New inputs require explicit review,
# rather than accepting a shortened manifest that hides an unchecked dependency.
BUILD_INPUTS = {
    "data/external/te-braatz/d00_te.dat", "data/external/te-braatz/d06_te.dat",
    "data/te_display_layout.json", "data/te_process_model.json", "out/svg/overview.svg",
    "out/twin/r2-tiles-trace/codex/ignition/tags.json",
    "out/twin/r2-tiles-trace/codex/plant_model.json", "scripts/display_contract.py",
    "scripts/normal_bands.py",
} | {f"data/drawings/{prefix}_{i}.jpg" for prefix in ("open100", "thumb") for i in range(12)} | {
    f"out/twin/r2-tiles-trace/codex/svg/sheet_{i}.svg" for i in range(12)
} | {f"scripts/ignition/{name}.py" for name in (
    "build_gateway", "build_hmi", "build_mimic", "build_views", "gw", "te_channels")}
QUALITY_COUNTS = {"good_te_recorded": 52,
                  "good_open100_synthetic_if_source_running": 24,
                  "bad_te_unavailable": 1,
                  "non_good_open100_placeholder": 334}
STAGES = {
    "native_import_fidelity": "Native held provider/project exports, import logs, normalization and source reconciliation.",
    "native_tag_quality_liveness": "Per-path quality, finite values and advancing source timestamps for the exact contract; source identity and unique replay channel mapping.",
    "native_navigation": "All contract routes, reload, header/equipment/stream/drawing links, Back/Forward, repeated clicks and login interruptions; screenshots and errors.",
    "native_history": "Actual TwinHistory query results, expected path coverage, ordered timestamps, quality, units and visible trend/history rows; historical storage configuration alone is insufficient.",
    "native_read_only_configuration": "Held tag access/OPC configuration and effective role permissions, examined without writing any tag.",
    "native_display_semantics": "Spatial/unit layouts, narrow and desktop viewports, unknown markers, metadata-only callout, unresolved FT 1401 records, percent levels and output meaning.",
    "native_alarm_pipeline": "Actual observed existing alarm states, gateway errors and liveness/plausibility evidence; a static alarm export is insufficient.",
    "native_write_rejection": "Separately approved isolated write-probe evidence; read-only configuration does not establish actual write rejection.",
    "native_fault_recovery": "Separately approved fault/disconnect/reconnect test evidence; fabricated offline values do not establish runtime recovery.",
    "operator_site_acceptance": "Qualified operator/site review and sign-off; technical tests do not establish production readiness.",
}


class InvalidEvidence(ValueError):
    pass


def strict_json(path):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise InvalidEvidence(f"duplicate JSON key: {key}")
            obj[key] = value
        return obj

    def constant(value):
        raise InvalidEvidence(f"nonfinite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=constant)


def local_file(root, relative):
    """All receipt references must be canonical, root-contained regular files."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise InvalidEvidence("invalid local relative path")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or pure.as_posix() != relative or ".." in pure.parts:
        raise InvalidEvidence(f"unsafe local path: {relative}")
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise InvalidEvidence(f"missing or out-of-root file: {relative}")
    return path


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def records(value, label):
    if not isinstance(value, list) or not value:
        raise InvalidEvidence(f"missing/non-list {label}")
    result = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise InvalidEvidence(f"invalid hash record in {label}")
        name, size, digest = item["path"], item["bytes"], item["sha256"]
        if not isinstance(name, str) or name in result:
            raise InvalidEvidence(f"duplicate/invalid path in {label}")
        if type(size) is not int or size <= 0 or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise InvalidEvidence(f"invalid size/hash for {name}")
        result[name] = item
    return result


def verify_records(root, entries):
    for name, expected in entries.items():
        data = local_file(root, name).read_bytes()
        if len(data) != expected["bytes"] or sha256(data) != expected["sha256"]:
            raise InvalidEvidence(f"candidate bytes/hash mismatch: {name}")


def historical_receipt_integrity(root, manifest_path, contract_path):
    """Advisory only: old check logs/handoff files are not tests of current code."""
    manifest = strict_json(local_file(root, manifest_path))
    entries = records(manifest.get("checks_and_handoff"), "checks and handoff")
    drift = []
    checked = 0
    for name, record in entries.items():
        if name == contract_path:  # mandatory candidate binding, checked separately
            continue
        checked += 1
        try:
            verify_records(root, {name: record})
        except (OSError, ValueError) as error:
            drift.append({"path": name, "error": str(error)})
    return {"status": "DRIFT" if drift else "PASS", "checked_file_count": checked,
            "changed_or_unavailable": drift,
            "scope": "historical check/handoff file hashes only; never current test execution",
            "note": "Drift does not change artifact identity or authorize regeneration; rerun current tests separately and retain historical receipts."}


def candidate(root, manifest_path, contract_path):
    manifest = strict_json(local_file(root, manifest_path))
    contract = strict_json(local_file(root, contract_path))
    if not isinstance(manifest, dict) or not isinstance(contract, dict):
        raise InvalidEvidence("manifest and contract must be objects")
    commit = manifest.get("reviewed_model_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or commit != contract.get("reviewed_model_commit"):
        raise InvalidEvidence("reviewed model commit missing/mismatched")
    artifacts = records(manifest.get("artifacts"), "manifest artifacts")
    if set(artifacts) != ARTIFACTS or records(contract.get("artifacts"), "contract artifacts") != artifacts:
        raise InvalidEvidence("manifest/contract must describe the same three current artifacts")
    inputs = records(manifest.get("build_inputs"), "build inputs")
    if set(inputs) != BUILD_INPUTS:
        raise InvalidEvidence("current-candidate build-input inventory differs (missing or unexpected path)")
    if set(inputs) & set(artifacts):
        raise InvalidEvidence("build input and artifact paths overlap")
    handoff = records(manifest.get("checks_and_handoff"), "checks and handoff")
    if contract_path not in handoff:
        raise InvalidEvidence("browser contract is not bound by the handoff manifest")
    # Do not mistake historical test-log/runner hashes for current test execution.
    verify_records(root, {**inputs, **artifacts, contract_path: handoff[contract_path]})
    if (contract.get("project"), contract.get("provider"), contract.get("relative_project_base")) != (
            "PIDTwin", "Twin", "/data/perspective/client/PIDTwin"):
        raise InvalidEvidence("unexpected project/provider/base")
    routes, views = contract.get("routes"), contract.get("views")
    if not isinstance(routes, dict) or not isinstance(views, dict) or len(routes) != 24 or len(views) != 24:
        raise InvalidEvidence("current candidate requires 24 routes and 24 views (23 control-room routes plus /m)")
    for route, page in routes.items():
        if not isinstance(route, str) or not route.startswith("/") or route.startswith("//") or any(c in route for c in ("?", "#", "\\", ":")) or ".." in route.split("/"):
            raise InvalidEvidence("invalid contract route")
        if not isinstance(page, dict) or page.get("viewPath") not in views:
            raise InvalidEvidence(f"missing view for route: {route}")
    if {p["viewPath"] for p in routes.values()} != set(views):
        raise InvalidEvidence("route/view inventory mismatch")
    quality = contract.get("expected_runtime_quality")
    if not isinstance(quality, dict) or set(quality) != set(QUALITY_COUNTS):
        raise InvalidEvidence("missing/unknown quality group")
    seen = set()
    for name, count in QUALITY_COUNTS.items():
        paths = quality[name]
        if not isinstance(paths, list) or len(paths) != count:
            raise InvalidEvidence(f"incorrect current-candidate quality count: {name}")
        for path in paths:
            if not isinstance(path, str) or not path.startswith("[Twin]") or not path.endswith("/PV") or path in seen:
                raise InvalidEvidence("invalid, duplicate or overlapping quality path")
            seen.add(path)
    if contract.get("prohibited_pv_asset_ids") != ["S0-IN019"] or contract.get("unmapped_clarification_asset_ids") != ["S0-IN002", "S0-IN003"]:
        raise InvalidEvidence("reviewed callout/clarification scope changed")
    identity = {"reviewed_model_commit": commit,
                "manifest_sha256": sha256(local_file(root, manifest_path).read_bytes()),
                "artifacts": [artifacts[k] for k in sorted(artifacts)],
                "browser_contract_sha256": sha256(local_file(root, contract_path).read_bytes())}
    identity["candidate_id"] = sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())
    return identity, contract, len(inputs)


def timestamp(value):
    if not isinstance(value, str):
        raise InvalidEvidence("timestamp must be an ISO-8601 string with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidEvidence("invalid timestamp") from error
    if parsed.tzinfo is None:
        raise InvalidEvidence("timestamp requires timezone")
    return parsed


def check_observations(data, identity, contract):
    """Validate captured/synthetic samples, never authenticate or execute a native test.

    observation schema: schema_version=1, candidate_id, evidence_kind (synthetic or
    native_capture), source_identity (nonempty string), open100_source_running=true,
    samples=[{path, observations=[{observed_at, source_timestamp, quality, value}]}].
    Good groups need two Good finite samples with advancing source timestamps; bad
    groups need at least one observation (SC-212 must be Bad, placeholders non-Good).
    Good samples must be no more than 60s old at observation, not in its future.
    Non-Good groups may omit/null source_timestamp and value; observed_at is always
    required. If a source timestamp is provided, it must be valid and not future.
    """
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise InvalidEvidence("unsupported observation schema")
    if data.get("candidate_id") != identity["candidate_id"]:
        raise InvalidEvidence("observations are for a different candidate")
    if data.get("evidence_kind") not in ("synthetic", "native_capture"):
        raise InvalidEvidence("explicit evidence_kind required")
    if not isinstance(data.get("source_identity"), str) or not data["source_identity"].strip():
        raise InvalidEvidence("source identity required; do not include credentials")
    if data.get("open100_source_running") is not True:
        raise InvalidEvidence("full Good mapped-point check requires explicit running synthetic OPEN100 source observation")
    groups = contract["expected_runtime_quality"]
    expected = {path: group for group, paths in groups.items() for path in paths}
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise InvalidEvidence("samples must be a list")
    seen = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise InvalidEvidence("sample must be an object")
        path = sample.get("path")
        if not isinstance(path, str) or path not in expected or path in seen:
            raise InvalidEvidence("unknown or duplicate sample path")
        seen.add(path)
        group = expected[path]
        good = group.startswith("good_")
        observations = sample.get("observations")
        if not isinstance(observations, list) or len(observations) < (2 if good else 1):
            raise InvalidEvidence(f"insufficient observations: {path}")
        previous = None
        previous_observed = None
        for observation in observations:
            if not isinstance(observation, dict):
                raise InvalidEvidence("observation must be an object")
            quality = observation.get("quality")
            if quality not in ("Good", "Bad", "Uncertain"):
                raise InvalidEvidence(f"unknown quality: {path}")
            observed = timestamp(observation.get("observed_at"))
            raw_source = observation.get("source_timestamp")
            source = timestamp(raw_source) if good or raw_source is not None else None
            if source is not None and (observed - source).total_seconds() < 0:
                raise InvalidEvidence(f"future source timestamp: {path}")
            if previous_observed is not None and observed <= previous_observed:
                raise InvalidEvidence(f"observation times do not advance: {path}")
            previous_observed = observed
            if good:
                value = observation.get("value")
                if quality != "Good" or type(value) not in (int, float) or not math.isfinite(value):
                    raise InvalidEvidence(f"expected Good finite numeric sample: {path}")
                if (observed - source).total_seconds() > 60 or (previous is not None and source <= previous):
                    raise InvalidEvidence(f"stale/nonadvancing Good source timestamp: {path}")
            elif quality == "Good" or (group == "bad_te_unavailable" and quality != "Bad"):
                raise InvalidEvidence(f"unavailable/placeholder quality violation: {path}")
            previous = source
    if seen != set(expected):
        raise InvalidEvidence(f"missing sample paths: {len(set(expected) - seen)}")
    return {"status": "PASS", "scope": "offline captured-sample validation only",
            "evidence_kind": data["evidence_kind"], "path_count": len(seen),
            "native_evidence_authenticated": False,
            "note": "Synthetic fixtures are not native evidence. A native_capture label is an unverified provenance assertion; operator review remains required."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", default=f"{REVIEW}/manifest.json")
    parser.add_argument("--contract", default=f"{REVIEW}/browser-contract.json")
    parser.add_argument("--observations", help="root-relative local capture/fixture JSON; never a URL")
    parser.add_argument("--require-native", action="store_true", help="reject offline-only results; this tool never establishes native acceptance")
    args = parser.parse_args(argv)
    report = {"schema_version": 1, "mode": "offline_read_only", "native_acceptance": "NOT RUN",
              "offline_candidate_preflight": {"status": "NOT RUN"},
              "offline_observation_check": {"status": "NOT RUN"},
              "historical_receipt_integrity": {"status": "NOT RUN"},
              "runtime_stages": [{"id": name, "status": "NOT RUN", "required_evidence": evidence,
                                  "requires_separate_action_approval": name in ("native_write_rejection", "native_fault_recovery")}
                                 for name, evidence in STAGES.items()],
              "limitations": ["This tool does not authorize or execute startup, import, account/security changes, source switching, browser access, write probes or fault injection.",
                              "Preflight does not rerun artifact semantic tests, validate an Ignition-native schema, authenticate capture provenance, or establish operator/site acceptance.",
                              "Candidate identity is bound to local manifest bytes, not a cryptographically trusted release signature.",
                              "Build-input checking covers only manifest-listed files; it is not a complete source dependency audit (for example, upstream generate.py is not listed)."]}
    active = "offline_candidate_preflight"
    try:
        identity, contract, input_count = candidate(args.root, args.manifest, args.contract)
        report["candidate"] = identity
        report["historical_receipt_integrity"] = historical_receipt_integrity(args.root, args.manifest, args.contract)
        report[active] = {"status": "PASS", "scope": "local build-input/artifact/contract identity only",
                          "build_input_count": input_count, "artifact_count": 3}
        report["coverage"] = {"routes": contract["routes"], "quality_groups": contract["expected_runtime_quality"],
                              "prohibited_pv_asset_ids": contract["prohibited_pv_asset_ids"],
                              "unmapped_clarification_asset_ids": contract["unmapped_clarification_asset_ids"]}
        if args.observations:
            active = "offline_observation_check"
            report[active] = check_observations(strict_json(local_file(args.root, args.observations)), identity, contract)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        report[active] = {"status": "FAIL", "error": str(error)}
        print(json.dumps(report, indent=2, allow_nan=False))
        return 2
    print(json.dumps(report, indent=2, allow_nan=False))
    return 3 if args.require_native else 0


if __name__ == "__main__":
    raise SystemExit(main())
