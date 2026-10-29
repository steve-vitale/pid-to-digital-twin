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


if __name__ == "__main__":
    unittest.main(verbosity=1)
