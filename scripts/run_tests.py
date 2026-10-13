"""Explicit offline test modes; never downloads, installs, or contacts a gateway.

Default/--full: all registered tests, using installed dependencies and cached TE data.
--source-only: stdlib and committed-fixture checks only (NOT a full-suite pass).
--check-prerequisites: read-only preflight for the selected mode; does not run tests.
Exit codes: 0 selected checks pass, 1 test failure, 2 missing/invalid prerequisites.
"""
import argparse
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TESTS = (
    "scripts/test_display_contract.py",
    "scripts/test_process_mimic.py",
    "scripts/test_tiling.py",
    "scripts/test_apply_review.py",
    "scripts/test_scorer_controls.py",
    "scripts/test_pid2graph_synthetic_adapter.py",
    "scripts/test_generate_validation.py",
    "scripts/test_export_review_boundaries.py",
    "scripts/test_site_drawing_intake.py",
    "scripts/test_site_extraction_workflow.py",
    "scripts/test_pi_mapping.py",
    "scripts/test_check_pi_export.py",
    "scripts/test_gateway_acceptance_preflight.py",
    "scripts/test_review_effort.py",
    "scripts/test_map_points.py",
    "scripts/test_run_tests.py",
)
# These tests need cached data or third-party imports, even though none needs a gateway.
FULL_ONLY_TESTS = (
    "scripts/test_te_channels.py",
    "scripts/test_along_line.py",
    "scripts/test_trace_connections_v2.py",
    "scripts/test_gateway_diff.py",
    "scripts/test_current_gateway_artifacts.py",
)
TESTS = SOURCE_TESTS + FULL_ONLY_TESTS
DEPENDENCIES = {"numpy": "numpy", "cv2": "opencv-python-headless",
                "asyncua": "asyncua", "cryptography": "cryptography"}
TWIN = "out/twin/r2-tiles-trace/codex"
DRAWINGS = "data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100"
SOURCE_FILES = (
    "data/te_process_model.json", "data/te_display_layout.json",
    "data/fixtures/water_utility_twin.json", "data/fixtures/water_utility_display.json",
    "data/dataset_adapters/pid2graph_synthetic.json",
    "out/ignition/gateway/twin_provider.json", "out/ignition/gateway/build_meta.json",
    "out/svg/overview.svg", f"{TWIN}/plant_model.json",
    "data/pi_builder_reference.json", "out/pi/pi_builder_af.csv", f"{TWIN}/pi/pi_builder_af.csv",
) + tuple(f"{TWIN}/svg/sheet_{i}.svg" for i in range(12)) + tuple(
    f"{DRAWINGS}/{i}.{extension}" for i in range(12) for extension in ("graphml", "png"))


def prerequisites(root, source_only):
    """Check local files and module discovery only; never import third-party code."""
    issues = []
    scripts = SOURCE_TESTS if source_only else TESTS
    paths = SOURCE_FILES + scripts
    if not source_only:
        paths += ("out/ignition/gateway/PIDTwin.zip", f"{TWIN}/ignition/tags.json")
    for relative in paths:
        path = root / relative
        if not path.is_file():
            issues.append(("source", f"missing committed file: {relative}"))
        else:
            try:
                with path.open("rb") as stream:
                    if not stream.read(1):
                        issues.append(("source", f"empty committed file: {relative}"))
            except OSError as error:
                issues.append(("source", f"unreadable committed file: {relative}: {error}"))
    if source_only:
        return issues
    for module, package in DEPENDENCIES.items():
        if importlib.util.find_spec(module) is None:
            issues.append(("dependency", f"missing Python module {module} (package {package})"))
    # This local stdlib module only defines download functions. Do NOT call main().
    from fetch_te_data import FILES
    for name, expected in FILES.items():
        path = root / "data/external/te-braatz" / name
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            issues.append(("cache", f"missing/unreadable cached TE data: {path.relative_to(root)}: {error.strerror}"))
        else:
            if actual != expected:
                issues.append(("cache", f"checksum mismatch: {path.relative_to(root)}"))
    return issues


def report_remediation(issues):
    print("Separate setup/remediation steps (NOT executed by this runner):")
    kinds = {kind for kind, _ in issues}
    if "source" in kinds:
        print("  Restore the listed committed files from a complete checkout; do not overwrite local work blindly.")
    if "dependency" in kinds:
        print("  python -m pip install -r requirements.txt  # may access the network; use your chosen environment")
    if "cache" in kinds:
        print("  python scripts/fetch_te_data.py  # network download if cache is absent/invalid; verifies hashes")
    print("  python scripts/run_tests.py --source-only  # narrower checks; NOT a full-suite pass")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--full", action="store_true", help="full cached-data suite (default)")
    modes.add_argument("--source-only", action="store_true", help="stdlib and committed fixtures only; excludes four full-only scripts")
    parser.add_argument("--check-prerequisites", action="store_true", help="preflight only; no tests or setup actions")
    args = parser.parse_args(argv)
    label = "SOURCE-ONLY" if args.source_only else "FULL CACHED-DATA"
    print(f"Mode: {label}. No downloads, installs, servers, or gateway operations.")
    if args.source_only:
        print("Scope exclusions (not run): " + ", ".join(FULL_ONLY_TESTS))
    issues = prerequisites(ROOT, args.source_only)
    if issues:
        for _, reason in issues:
            print("BLOCKED  " + reason)
        print(f"{label}: prerequisite check failed; no test scripts ran. No suite pass.")
        report_remediation(issues)
        return 2
    if args.check_prerequisites:
        print(f"{label}: prerequisites present; tests NOT RUN. Module discovery does not verify binary compatibility.")
        return 0
    selected = SOURCE_TESTS if args.source_only else TESTS
    failed = 0
    skipped = []  # (script, reason): platform gaps printed by scripts/platform_capabilities.py, never silent
    for script in selected:
        # -S makes the source-only promise testable even on a machine with packages installed.
        command = [sys.executable] + (["-S"] if args.source_only else []) + [script]
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        except OSError as error:
            failed += 1
            print(f"FAIL  {script}: could not run: {error}")
            continue
        failed += result.returncode != 0
        status = "PASS" if result.returncode == 0 else "FAIL"
        last = (result.stdout.strip().splitlines() or result.stderr.strip().splitlines() or [""])[-1]
        print(f"{status}  {script}: {last}".rstrip())
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            if line.startswith("SKIP "):
                skipped.append((script, line[5:]))
                print(f"      SKIP (platform) {line[5:]}")
        if result.returncode:
            print(result.stdout[-2000:], result.stderr[-2000:])
    print(f"{label}: {len(selected) - failed}/{len(selected)} scripts passed; {failed} failed; "
          f"{len(skipped)} sub-case(s) skipped by the platform.")
    if args.source_only:
        print("SOURCE-ONLY result is NOT a full-suite pass; cached-data and dependency checks were excluded.")
    elif not failed and skipped:
        print("FULL CACHED-DATA scripts passed, but the SKIP lines above did not run on this machine: "
              "not a complete pass here. This is offline evidence, not gateway/runtime acceptance.")
    elif not failed:
        print("FULL CACHED-DATA suite passed. This is offline evidence, not gateway/runtime acceptance.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
