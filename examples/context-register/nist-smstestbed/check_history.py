"""Exercise retained-history guards through the real CLI using pinned NIST originals.

No source or existing packet output is edited. All working registers are disposable.
Use --out FILE to record the deterministic software result. Standard library only.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]


def check():
    manifest = json.loads((PACKET / 'sources.json').read_text(encoding='utf-8'))
    originals = [ROOT / 'data/external/nist-smstestbed' / d['path'] for d in manifest['documents']]
    source_bytes = {p: p.read_bytes() for p in originals}
    base = [sys.executable, '-S', str(ROOT / 'scripts/context_register.py'), 'apply',
            '--model', str(PACKET / 'model.json'), '--questions', str(PACKET / 'questions.json'),
            '--sources', str(PACKET / 'sources.json'), '--source-root', str(ROOT / 'data/external/nist-smstestbed')]
    with tempfile.TemporaryDirectory(prefix='context-history-') as folder:
        scratch = Path(folder)
        working = scratch / 'working'
        register = working / 'context.json'

        def invoke(*args, expect=0):
            result = subprocess.run(base + list(map(str, args)), cwd=ROOT, capture_output=True,
                                    encoding='utf-8', timeout=30)
            assert result.returncode == expect, result.stdout + result.stderr
            return result

        def snapshot():
            return {p.relative_to(scratch).as_posix(): p.read_bytes() for p in scratch.rglob('*') if p.is_file()}

        invoke('--answers', PACKET / 'proposed_answers.csv', '--out', working)
        first = json.loads(register.read_text(encoding='utf-8'))
        assert len(first['decisions']) == 10 and not first['ownership_history']
        baseline = scratch / 'baseline.json'
        baseline.write_bytes(register.read_bytes())
        before = snapshot()
        result = invoke('--out', working, expect=2)
        assert '--register' in result.stderr and 'retained history' in result.stderr
        assert snapshot() == before, 'omitted register changed files'
        result = invoke('--answers', PACKET / 'proposed_answers.csv', '--out', working, expect=2)
        assert snapshot() == before, 'resubmitted proposals without register changed files'
        invoke('--register', register, '--out', working)
        assert snapshot() == before, 'unchanged refresh was not byte-idempotent'

        with (PACKET / 'proposed_answers.csv').open(encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        rows[0]['note'] += ' Synthetic history-extension control only; no human review.'
        revised = scratch / 'revised.csv'
        text = io.StringIO(newline='')
        writer = csv.DictWriter(text, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerow(rows[0])
        revised.write_text(text.getvalue(), encoding='utf-8', newline='')
        invoke('--answers', revised, '--register', register, '--out', working)
        newer = json.loads(register.read_text(encoding='utf-8'))
        assert len(newer['decisions']) == 11 and newer['decisions'][:10] == first['decisions']
        before = snapshot()
        result = invoke('--register', baseline, '--out', working, expect=2)
        assert 'history prefix' in result.stderr
        assert snapshot() == before, 'older register changed files'
        invoke('--register', register, '--out', working)
        assert snapshot() == before, 'current register refresh changed history or other outputs'
        fork = scratch / 'explicit-fork'
        invoke('--register', baseline, '--out', fork)
        assert json.loads((fork / 'context.json').read_text(encoding='utf-8'))['decisions'] == first['decisions']
    assert all(p.read_bytes() == value for p, value in source_bytes.items()), 'original source changed'
    return dict(schema='nist-context-history-check-1', initial_proposals=10, extended_decisions=11,
                omitted_register_refused=True, resubmission_without_register_refused=True,
                older_register_refused=True, refusal_preserves_all_workspace_bytes=True,
                unchanged_refresh_byte_idempotent=True, explicit_new_directory_fork_allowed=True,
                original_source_bytes_unchanged=True, no_human_signoff=True,
                evidence_role='Seen development software controls using actual pinned originals; not an adoption or accuracy result')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        result = json.dumps(check(), indent=2) + '\n'
    except (OSError, ValueError, AssertionError) as exc:
        print('FAIL: history check requires the pinned originals and valid CLI results: ' + str(exc), file=sys.stderr)
        sys.exit(1)
    if args.out:
        args.out.write_text(result, encoding='utf-8', newline='\n')
    print(result, end='')
