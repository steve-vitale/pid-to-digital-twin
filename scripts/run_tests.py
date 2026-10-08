"""Run every test in one command: python scripts/run_tests.py

A test whose data is missing is skipped and says so. The data every test needs is committed, so in a full checkout
(and in CI) nothing is skipped.
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
    ("scripts/test_scorer_controls.py", "data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100"),
]


def main():
    failed = 0
    for script, needs in TESTS:
        if needs and not (ROOT / needs).exists():
            print(f"SKIP  {script} (needs {needs}, which is committed: is this a partial checkout?)")
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
