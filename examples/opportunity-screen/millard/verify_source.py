"""Check one pinned public bulletin; --fetch explicitly downloads only missing bytes.

Fixed-case example helper, standard library only. No PDF interpretation, model call
or source-authority decision. Changed existing files are refused, never replaced.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def verify(data, pin):
    if len(data) != pin['bytes'] or hashlib.sha256(data).hexdigest() != pin['sha256']:
        raise ValueError('bulletin bytes do not match the pinned original; preserve the file and investigate')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=ROOT / 'data/external/millard/bulletin.pdf')
    ap.add_argument('--fetch', action='store_true', help='download only if the source is absent; network required')
    args = ap.parse_args(argv)
    pin = json.loads((HERE / 'source.json').read_text(encoding='utf-8'))
    try:
        if args.source.is_symlink():
            raise ValueError('source path must not be a symbolic link')
        if args.source.exists():
            verify(args.source.read_bytes(), pin)
            print('Original bytes match; no download. Source meaning and current applicability remain unverified.')
            return 0
        if not args.fetch:
            raise ValueError('original missing; supply --source or explicitly use --fetch')
        request = urllib.request.Request(pin['download_url'], headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=45) as response:
            data = response.read(pin['bytes'] + 1)
        verify(data, pin)
        args.source.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also refuses a destination created while downloading.
        with args.source.open('xb') as output:
            output.write(data)
        print('Pinned original downloaded and checked. No source interpretation or company approval is implied.')
        return 0
    except (OSError, ValueError) as exc:
        print(f'Refused: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
