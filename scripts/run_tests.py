"""Run every test in one command: python scripts/run_tests.py

Tests that need downloaded data are skipped (and say so) when the data isn't there, so this also runs in CI.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = [
    ("scripts/test_tiling.py", None),
    ("scripts/test_along_line.py", None),
    ("scripts/test_gateway_diff.py", None),
    ("scripts/test_apply_review.py", None),
    ("scripts/test_scorer_controls.py", "data/external/pid2graph"),
]


def main():
    failed = 0
    for script, needs in TESTS:
        if needs and not (ROOT / needs).exists():
            print(f"SKIP  {script} (needs {needs}; run step 3 of the README tutorial)")
            continue
        p = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True)
        status = "PASS" if p.returncode == 0 else "FAIL"
        failed += p.returncode != 0
        last = (p.stdout.strip().splitlines() or [""])[-1]
        print(f"{status}  {script}: {last}")
        if p.returncode:
            print(p.stdout[-2000:], p.stderr[-2000:])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
