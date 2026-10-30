"""Exercise actual CLIs, history and scoped staleness on disposable copies of the pinned originals."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from prepare_sources import DEFAULT_SOURCE, PACKET, ROOT, sha256, verify_file


def invoke(command, sources, source_root, out, register=None, answers=None, questions=None, expected=0):
    args = [sys.executable, '-S', str(ROOT / 'scripts/context_register.py'), command,
            '--model', str(PACKET / 'model.json'), '--questions', str(questions or PACKET / 'questions.json'),
            '--sources', str(sources), '--source-root', str(source_root), '--out', str(out)]
    for flag, value in [('--register', register), ('--answers', answers)]:
        if value:
            args += [flag, str(value)]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, encoding='utf-8', timeout=60)
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}


def stale_answers(register):
    return {answer['answer_id'] for q in register['current'].values() for answer in q['answers']
            if answer['freshness'] == 'stale'}


def preflight_expected(destinations, protected):
    """Refuse known aliases and path conflicts for BOTH expected files before either write."""
    for path in destinations:
        for n, part in enumerate((path.absolute(), *path.absolute().parents)):
            try:
                info = part.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Expected output contains a symlink/reparse alias; no expected files changed')
            if n and not stat.S_ISDIR(info.st_mode):
                raise ValueError('Expected output parent must be a directory; no expected files changed')
            if not n and (not stat.S_ISREG(info.st_mode) or info.st_nlink > 1):
                raise ValueError('Expected output must be a regular file without hard-link aliases; no expected files changed')
        for source in protected:
            if path.resolve() == source.resolve() or (path.exists() and source.exists() and path.samefile(source)):
                raise ValueError('Expected output aliases a known input; no expected files changed')
    for n, path in enumerate(destinations):
        for other in destinations[n + 1:]:
            if path.resolve() == other.resolve() or (path.exists() and other.exists() and path.samefile(other)):
                raise ValueError('Expected outputs alias each other; no expected files changed')


def check(write=False, source_root=DEFAULT_SOURCE, expected_root=None):
    pins = json.loads((PACKET / 'originals.json').read_text(encoding='utf-8'))
    expected_dir = Path(expected_root) if expected_root is not None else PACKET / 'expected'
    names = ['context.json', 'context.md']
    destinations = [expected_dir / name for name in names]
    protected = [p for p in PACKET.iterdir() if p.is_file()]
    protected += [source_root / name for name in pins['members']]
    protected += [ROOT / pins['archive']['path']]
    if write:
        preflight_expected(destinations, protected)
    original_hashes = {name: sha256(source_root / name) for name in pins['members']}
    for name, pin in pins['members'].items():
        verify_file(source_root / name, pin)
    model_before = (PACKET / 'model.json').read_bytes()
    key = json.loads((PACKET / 'source_key.json').read_text(encoding='utf-8'))
    manifest = json.loads((PACKET / 'sources.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='metropt-context-') as temp:
        scratch = Path(temp)
        base = scratch / 'current'
        invoke('prepare', PACKET / 'sources.json', source_root, base)
        invoke('apply', PACKET / 'sources.json', source_root, base, answers=PACKET / 'proposed_answers.csv')
        original = json.loads((base / 'context.json').read_text(encoding='utf-8'))
        assert len(original['decisions']) == 12 and len(original['current']) == 6
        assert not original['ownership_history']
        assert {q['state'] for q in original['current'].values()} == {'partial', 'needs_data'}
        assert sum(q['state'] == 'needs_data' for q in original['current'].values()) == 5
        assert all(q['owner'] is None and q['ownership'] == 'needs_owner' for q in original['current'].values())
        assert all(d['decision'] == 'proposed' and d['source_match'] == 'match' and d['plant_truth'] == 'unknown'
                   and d['owner'] is None and not d['reviewer'] and not d['reviewed_on'] for d in original['decisions'])
        decisions = {d['answer_id']: d for d in original['decisions']}
        for fact in key['facts']:
            decision = decisions['MPT-' + fact['id']]
            assert decision['question_id'] == fact['question_id']
            assert decision['evidence']['source'] == {
                'id': fact['document_id'], 'revision': fact['document_revision'], 'sha256': fact['raw_sha256'],
                'locator_id': fact['locator_id'], 'locator': fact['locator']}
            for field in ['claim_key', 'value', 'answer', 'answer_state']:
                assert decision[field] == fact[field], (fact['id'], field)
            assert [a['id'] for a in decision['evidence']['assets']] == ['MPT-APU']
        assert decisions['MPT-M01']['claim_key'] != decisions['MPT-M02']['claim_key']
        assert '#1' in decisions['MPT-M03']['value'] and decisions['MPT-M03']['value'].count('#1') == 2
        assert '30Apr' in decisions['MPT-M04']['value'] and '5/29/2020' in decisions['MPT-M04']['value']
        assert 'DV_eletric' in decisions['MPT-M08']['value']
        report = (base / 'context.md').read_text(encoding='utf-8')
        for expected in ['Work-record ID/revision', 'return-to-service', 'chosen metric', 'timezone',
                         '172918', 'Oil_temperature', 'Motor_current', 'needs owner']:
            assert expected in report, expected
        before = snapshot(base)
        invoke('apply', PACKET / 'sources.json', source_root, base, register=base / 'context.json',
               answers=PACKET / 'proposed_answers.csv')
        assert snapshot(base) == before, 'identical proposal reapplication changed files/history'

        counts = {}
        for did, expected_count in [('MPT-DESCRIPTION', 8), ('MPT-CSV', 4)]:
            copied = scratch / did
            copied.mkdir()
            revised = copy.deepcopy(manifest)
            for doc in revised['documents']:
                destination = copied / doc['path']
                shutil.copyfile(source_root / doc['path'], destination)
                if doc['id'] == did:
                    with destination.open('ab') as stream:
                        stream.write(b'\nSYNTHETIC REVISION FOR SOFTWARE STALENESS CONTROL ONLY\n')
                    doc.update(sha256=sha256(destination), revision=doc['revision'] + '-synthetic-revision')
            sources = copied / 'sources.json'
            sources.write_text(json.dumps(revised), encoding='utf-8')
            out = scratch / (did + '-refresh')
            invoke('apply', sources, copied, out, register=base / 'context.json')
            current = json.loads((out / 'context.json').read_text(encoding='utf-8'))
            wanted = {'MPT-' + f['id'] for f in key['facts'] if f['document_id'] == did}
            assert stale_answers(current) == wanted and len(wanted) == expected_count
            assert current['decisions'] == original['decisions'] and not current['ownership_history']
            refused = invoke('apply', sources, copied, base, register=base / 'context.json',
                             answers=PACKET / 'proposed_answers.csv', expected=2)
            assert 'stale' in refused.stderr and snapshot(base) == before
            counts[did] = len(wanted)

        changed = copy.deepcopy(json.loads((PACKET / 'questions.json').read_text(encoding='utf-8')))
        target = next(q for q in changed['questions'] if q['question_id'] == 'MPT-EFFECTIVENESS')
        target['data_requests'][0]['fields'] += ' SYNTHETIC REQUEST REVISION FOR SOFTWARE CONTROL ONLY.'
        questions = scratch / 'changed-questions.json'
        questions.write_text(json.dumps(changed), encoding='utf-8')
        out = scratch / 'question-refresh'
        invoke('apply', PACKET / 'sources.json', source_root, out, register=base / 'context.json', questions=questions)
        current = json.loads((out / 'context.json').read_text(encoding='utf-8'))
        assert stale_answers(current) == {'MPT-M05', 'MPT-M06'}
        assert current['decisions'] == original['decisions']

        missing = scratch / 'missing'
        missing.mkdir()
        refused = invoke('apply', PACKET / 'sources.json', missing, base, register=base / 'context.json', expected=2)
        assert 'unavailable' in refused.stderr and snapshot(base) == before
        assert (PACKET / 'model.json').read_bytes() == model_before
        assert original_hashes == {name: sha256(source_root / name) for name in pins['members']}
        contents = {name: (base / name).read_bytes() for name in names}
        if write:
            preflight_expected(destinations, protected)
            expected_dir.mkdir(parents=True, exist_ok=True)
            for name, data in contents.items():
                (expected_dir / name).write_bytes(data)
        else:
            for name, data in contents.items():
                assert (expected_dir / name).read_bytes().replace(b'\r\n', b'\n') == data.replace(b'\r\n', b'\n'), name
        assert (PACKET / 'model.json').read_bytes() == model_before
        assert original_hashes == {name: sha256(source_root / name) for name in pins['members']}
        return {'role': 'Development software controls on actual original copies; synthetic revisions, no operational events.',
                'questions': 6, 'proposals': 12, 'needs_data': 5, 'partial': 1, 'all_need_owner': True,
                'source_changes_stale_exactly': counts, 'effectiveness_request_change_stales': ['MPT-M05', 'MPT-M06'],
                'reapplication_byte_identical': True, 'stale_answers_and_missing_originals_refuse_without_writes': True,
                'original_bytes_and_decision_history_preserved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Regenerate the two expected outputs after the behavior checks')
    parser.add_argument('--source-root', type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    try:
        result = check(args.write, args.source_root)
    except (OSError, ValueError, AssertionError) as error:
        parser.exit(2, f'MetroPT packet check: {error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
