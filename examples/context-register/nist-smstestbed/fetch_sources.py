"""Fetch this packet's original files with the repository's existing pinned fetcher.

The local registry is separate from the eight-workflow matrix registry. It adds no
HTTP implementation and changes no global fetch registry or original source file.
"""
import argparse
import importlib.util
import json
from pathlib import Path

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-mb',type=float,default=1)
    parser.add_argument('--dest',type=Path,default=ROOT/'data/external/nist-smstestbed')
    args = parser.parse_args()
    registry = json.loads((PACKET/'fetch.json').read_text(encoding='utf-8'))
    sources, pins = registry['FILE_SOURCES_entry'], registry['pins_entry']
    spec = importlib.util.spec_from_file_location('packet_corpus_fetch', ROOT/'scripts/fetch_corpus.py')
    fetcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetcher)
    problems = fetcher.validate_file_pins(pins,sources=sources)
    if problems:
        raise SystemExit('\n'.join(problems))
    fetcher.FILE_SOURCES.update(sources)
    receipt = fetcher.fetch_pinned('nist-smstestbed',args.max_mb,args.dest,pins=pins)
    args.dest.mkdir(parents=True,exist_ok=True)
    (args.dest/'FETCHED.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('Fetched/verified '+str(len(receipt['files']))+' pinned originals; saved FETCHED.json beside them.')


if __name__ == '__main__':
    main()
