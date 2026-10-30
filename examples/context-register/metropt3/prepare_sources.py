"""Offline extraction of two exact original MetroPT-3 members; never downloads or replaces a cache."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
DEFAULT_SOURCE = ROOT / 'data/external/metropt3/context'


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def verify_file(path, pin):
    if not path.is_file() or path.stat().st_size != pin['bytes'] or sha256(path) != pin['sha256']:
        raise ValueError(f'{path.name}: missing or changed original; expected pinned size and SHA-256')


def ordinary_path(path):
    for part in (path.absolute(), *path.absolute().parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Source-cache destination contains an alias; use an ordinary directory')


def prepare(archive, destination):
    pins = json.loads((PACKET / 'originals.json').read_text(encoding='utf-8'))
    verify_file(archive, pins['archive'])
    ordinary_path(destination)
    if destination.exists():
        if not destination.is_dir() or {p.name for p in destination.iterdir()} != set(pins['members']):
            raise ValueError('Existing source-cache destination is not the complete pinned pair; preserve it and use a fresh folder')
        for name, pin in pins['members'].items():
            ordinary_path(destination / name)
            verify_file(destination / name, pin)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='metropt-originals-', dir=destination.parent) as temp:
        staged = Path(temp) / 'pair'
        staged.mkdir()
        with zipfile.ZipFile(archive) as zipped:
            for name, pin in pins['members'].items():
                with zipped.open(name) as source, (staged / name).open('wb') as target:
                    shutil.copyfileobj(source, target)
                verify_file(staged / name, pin)
        # A new directory only. Existing documents are never overwritten or repaired.
        if destination.exists():
            raise ValueError('Destination appeared during preparation; no source cache replaced')
        staged.rename(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, default=ROOT / 'data/external/metropt3/metropt3.zip')
    parser.add_argument('--out', type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    try:
        prepare(args.zip, args.out)
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
        parser.exit(2, f'MetroPT originals: {error}\nFetch explicitly with python scripts/fetch_corpus.py metropt3 --max-mb 250\n')
    print('Two pinned original members present; offline, source bytes unchanged.')


if __name__ == '__main__':
    main()
