"""Every script is registered with a kind in data/script_index.json, every tool has a guide that exists, and
docs/SCRIPTS.md matches the registry and the scripts' own docstrings (scripts/script_index.py --check). Stdlib only."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ScriptIndex(unittest.TestCase):
    def test_index_is_complete_and_current(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "script_index.py"), "--check"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unknown_flag_is_a_usage_error_and_writes_nothing(self):
        out = ROOT / "docs" / "SCRIPTS.md"
        before = out.read_bytes() if out.exists() else None
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "script_index.py"), "--bogus"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--bogus", r.stderr)
        self.assertIn("usage", r.stderr.lower())
        self.assertEqual(out.read_bytes() if out.exists() else None, before)


if __name__ == "__main__":
    unittest.main(verbosity=1)
