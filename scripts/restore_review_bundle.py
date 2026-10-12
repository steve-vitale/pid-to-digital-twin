"""Restore a separately supplied, trusted review bundle into a new directory.

Usage: python scripts/restore_review_bundle.py REVIEW.gitbundle NEW_DIRECTORY
This public source snapshot includes no review bundle or private review history.
The helper is retained for compatible user-supplied bundles at the documented
baseline. It does not fetch from a network remote or verify publication approval.
"""
import argparse
import subprocess
from pathlib import Path

BASELINE = '20aa7cd32ea0ee793394f063bbdf8234f5a12590'
BRANCH = 'process-mimic-aligned-review'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve(strict=True)
    destination = args.destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        parser.error('Destination must be new or empty; existing repositories are not changed.')
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '-q', str(destination)], check=True)
    # Preserve the input repository's boundary before fetch traverses the old commit.
    (destination / '.git' / 'shallow').write_text(BASELINE + '\n')
    git = ['git', '-C', str(destination)]
    subprocess.run(git + ['bundle', 'verify', str(bundle)], check=True)
    subprocess.run(git + ['fetch', str(bundle), 'refs/heads/' + BRANCH + ':refs/heads/' + BRANCH], check=True)
    subprocess.run(git + ['checkout', '-q', BRANCH], check=True)
    subprocess.run(git + ['rev-parse', 'HEAD'], check=True)
    print('Restored exact review commits. Pre-baseline history remains intentionally unavailable.')


if __name__ == '__main__':
    main()
