"""Download the Tennessee Eastman simulation runs the Ignition replay server uses, and check them.

Source: the Braatz group's open TE data (University of Illinois, NCSA-style license), via the same GitHub mirror
scripts/verify_te_source.py uses for teprob.f. Each file is checked against the SHA-256 recorded when this project
first used it, so a changed upstream file is caught instead of silently replayed.

  d00_te.dat  normal operation, 960 samples (3 simulated minutes each)
  d06_te.dat  fault IDV(6), loss of A feed

Usage: python scripts/fetch_te_data.py
"""
import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "external" / "te-braatz"
BASE = "https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/master/"
FILES = {
    "d00_te.dat": "57d56da4199e3d73582855d810be1d13d931386fd728bf1694798c7b0a03678c",
    "d06_te.dat": "8a3adc7121eaa9b9300c27f9c57a8ab356315401cb964310a4a8244dd34bf79d",
}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for name, want in FILES.items():
        path = DEST / name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == want:
            print(f"{name}: already present, checksum OK")
            continue
        with urllib.request.urlopen(BASE + name, timeout=60) as r:
            data = r.read()
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            raise SystemExit(f"{name}: checksum mismatch (got {got[:16]}..., expected {want[:16]}...). Not saved.")
        path.write_bytes(data)
        print(f"{name}: downloaded, {len(data):,} bytes, checksum OK")


if __name__ == "__main__":
    main()
