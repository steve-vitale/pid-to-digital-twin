"""Fetch only the pinned public CSB MGPI report for optional original-source review. No figures are republished."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
URL = 'https://www.csb.gov/file.aspx?DocumentId=6047'
SHA256 = '2e8f0ef9db7b9c65b790dbb3c1a2f12f90a9a7051e531189b5868ce2c2e6a07e'
MAX_BYTES = 8 * 1024 * 1024


def main():
    folder = ROOT / 'data/external/csb-mgpi'
    target = folder / 'csb-2017-01-i-ks.pdf'
    downloaded = False
    if target.exists():
        with target.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
    else:
        request = urllib.request.Request(URL, headers={'User-Agent': 'pid-to-digital-twin original-source review'})
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read(MAX_BYTES + 1)
        downloaded = True
    if len(raw) > MAX_BYTES or not raw.startswith(b'%PDF') or hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('Original report does not match the pinned PDF; nothing accepted')
    folder.mkdir(parents=True, exist_ok=True)
    if downloaded:
        with target.open('xb') as stream:
            stream.write(raw)
    receipt = {'url': URL, 'sha256_raw': SHA256, 'bytes': len(raw), 'downloaded': downloaded,
               'use': 'Original-source review only; no CSB figure redistribution or engineering approval'}
    (folder / 'FETCH_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
