"""Fetch a subset of the PID2Graph dataset without downloading the whole 9.3 GB archive.

PID2Graph (Zenodo record 14803338, CC BY-SA 4.0) is one zip file. A zip keeps its table of contents (the "central
directory") at the end, so we can read that over HTTP range requests, then fetch only the entries we want.

Usage:
  python scripts/fetch_pid2graph.py --list [--filter TEXT]     # show entries (optionally filtered)
  python scripts/fetch_pid2graph.py --get TEXT [--get TEXT ...] # extract entries whose path contains TEXT

Files land in data/external/pid2graph/. The OPEN100 drawings and answer keys are already committed there (see
NOTICE.md), so this is only needed for the holdout-B set ("Complete/Dataset PID/") or to re-fetch from the source.
Dataset files keep their CC BY-SA 4.0 license.
"""
import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://zenodo.org/records/14803338/files/PID2Graph.zip?download=1"
OUT = Path(__file__).resolve().parent.parent / "data" / "external" / "pid2graph"
BLOCK = 1 << 20  # fetch in 1 MiB blocks; zipfile issues many small reads


class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable view of a remote file, backed by HTTP range requests and a small block cache."""

    def __init__(self, url):
        self.url, self.pos, self.cache, self.fetched = url, 0, {}, 0
        req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            self.size = int(r.headers["Content-Range"].split("/")[-1])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def _block(self, n):
        if n not in self.cache:
            start, end = n * BLOCK, min((n + 1) * BLOCK, self.size) - 1
            req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req, timeout=120) as r:
                self.cache[n] = r.read()
            self.fetched += end - start + 1
            if len(self.cache) > 64:  # keep memory bounded
                self.cache.pop(next(iter(self.cache)))
        return self.cache[n]

    def readinto(self, buf):
        if self.pos >= self.size:
            return 0
        want = min(len(buf), self.size - self.pos)
        got = 0
        while got < want:
            n, off = divmod(self.pos, BLOCK)
            chunk = self._block(n)[off:off + want - got]
            buf[got:got + len(chunk)] = chunk
            got += len(chunk)
            self.pos += len(chunk)
        return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--filter", default="")
    ap.add_argument("--get", action="append", default=[])
    args = ap.parse_args()

    remote = HttpRangeFile(URL)
    zf = zipfile.ZipFile(io.BufferedReader(remote, buffer_size=BLOCK))
    infos = zf.infolist()
    if args.list:
        shown = [i for i in infos if args.filter.lower() in i.filename.lower()]
        for i in shown:
            print(f"{i.file_size:>12,}  {i.filename}")
        print(f"-- {len(shown)} of {len(infos)} entries; archive {remote.size / 1e9:.2f} GB; "
              f"downloaded {remote.fetched / 1e6:.1f} MB to list", file=sys.stderr)
    if args.get:
        picked = [i for i in infos if not i.is_dir() and any(g.lower() in i.filename.lower() for g in args.get)]
        total = sum(i.file_size for i in picked)
        print(f"extracting {len(picked)} entries ({total / 1e6:.1f} MB uncompressed) to {OUT}", file=sys.stderr)
        for i in picked:
            zf.extract(i, OUT)
        print(f"downloaded {remote.fetched / 1e6:.1f} MB of {remote.size / 1e9:.2f} GB", file=sys.stderr)


if __name__ == "__main__":
    main()
