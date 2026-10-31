"""Committed byte contracts survive actual Git clean and checkout. Stdlib + Git; no network.

This checks repository checkout policy, not external CRLF drawing-manifest compatibility.
The complete graph/estimate/line workflows and actual drawn_truth refusals have separate tests.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = 'examples/graph-export/multi-appearance/review/'
TARGETS = [REVIEW + name for name in ('statements.json', 'review.html', 'review_sheet.csv')]
TARGETS += ['examples/impact-estimate/' + folder + '/' + stem + extension
            for folder, stem in [('pump-vfd-site', 'impact'), ('pump-vfd-defaults', 'impact'),
                                 ('steam-traps-site', 'impact'), ('steam-traps-defaults', 'impact'),
                                 ('needs-E1', 'needs'), ('needs-E8', 'needs')]
            for extension in ('.md', '.json')]
TARGETS += ['scripts/draw_pid_from_model.py', 'data/bayer_rt/process_model.json',
            'data/bayer_rt/pid_layout.json', 'data/te_process_model.json', 'data/te_pid_layout.json']
RAW_FAMILIES = ('out/review_kit', 'examples/review-and-mapping',
                'examples/own-drawing/deliverable', 'examples/from-description/assisted',
                'examples/from-description/mgpi', 'examples/pump-revision/inputs',
                'examples/pump-revision/worked', 'examples/team-context/inputs',
                'examples/team-context/worked')
ORDINARY = ('scripts/line_layers.py', 'scripts/context_register.py', 'data/questions.json',
            'examples/graph-export/multi-appearance/model.json')
GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_ATTR_NOSYSTEM='1')


def git(folder, args, mode, data=None):
    command = ['git', '-c', 'core.autocrlf=' + mode, '-c', 'core.safecrlf=false',
               '-c', 'core.attributesfile=' + os.devnull, *args]
    result = subprocess.run(command, cwd=folder, env=GIT_ENV, input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode:
        raise AssertionError(result.stderr.decode('utf-8', errors='replace'))
    return result.stdout


def attributes(folder, paths, mode):
    raw = git(folder, ['check-attr', '-z', '--stdin', 'text', 'eol'], mode,
              b''.join(path.encode('utf-8') + b'\0' for path in paths)).split(b'\0')[:-1]
    return {(raw[n].decode('utf-8'), raw[n + 1].decode('utf-8')): raw[n + 2].decode('utf-8')
            for n in range(0, len(raw), 3)}


def indexed_bytes(folder, mode):
    records = git(folder, ['ls-files', '-s', '-z'], mode).split(b'\0')[:-1]
    entries = [(row.split(b'\t', 1)[1].decode('utf-8'), row.split()[1]) for row in records]
    raw = git(folder, ['cat-file', '--batch'], mode, b''.join(oid + b'\n' for _, oid in entries))
    result, offset = {}, 0
    for path, oid in entries:
        end = raw.index(b'\n', offset)
        header = raw[offset:end].split()
        if header[:2] != [oid, b'blob']:
            raise AssertionError('Unexpected Git object response for ' + path)
        length = int(header[2])
        result[path] = raw[end + 1:end + 1 + length]
        offset = end + 2 + length
    if offset != len(raw):
        raise AssertionError('Unexpected remaining Git object data')
    return result


class CheckoutContracts(unittest.TestCase):
    def test_git_filters_retain_lf_contracts_and_existing_raw_packets(self):
        self.assertIsNotNone(shutil.which('git'), 'Git is required for checkout-contract controls')
        targets = {path: (ROOT / path).read_bytes() for path in TARGETS}
        self.assertEqual(len(targets), 20)
        for path, raw in targets.items():
            self.assertNotIn(b'\r', raw, path + ' must materialize as committed LF bytes')
        protected = {}
        for family in RAW_FAMILIES:
            folder = ROOT / family
            if folder.is_dir():
                for path in folder.rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts:
                        protected[path.relative_to(ROOT).as_posix()] = path.read_bytes()
        self.assertTrue(protected, 'Existing raw-byte families must be present')
        ordinary = {path: (ROOT / path).read_bytes() for path in ORDINARY}
        synthetic = {'checkout-control.bin': b'\0raw\r\nbytes\xff',
                     'checkout-control.txt': b'ordinary LF control\n'}
        policies = {'.gitattributes': (ROOT / '.gitattributes').read_bytes()}
        for name in ('examples/pump-revision/.gitattributes', 'examples/team-context/.gitattributes'):
            if (ROOT / name).is_file():
                policies[name] = (ROOT / name).read_bytes()
        clean_count = checkout_count = 0
        with tempfile.TemporaryDirectory(prefix='gitbytes-') as tmp:
            home = Path(tmp)
            for ingest in ('false', 'true'):
                repo = home / ('i' + ingest[0])
                repo.mkdir()
                git(repo, ['init', '--quiet', '--template='], ingest)
                for name, raw in {**targets, **protected, **ordinary, **synthetic, **policies}.items():
                    path = repo / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                git(repo, ['add', '--force', '--all'], ingest)
                attrs = attributes(repo, [*targets, *protected, *ordinary], ingest)
                for name in targets:
                    self.assertEqual((attrs[name, 'text'], attrs[name, 'eol']), ('set', 'lf'), name)
                for name in protected:
                    self.assertEqual(attrs[name, 'text'], 'unset', name)
                for name in ordinary:
                    self.assertEqual((attrs[name, 'text'], attrs[name, 'eol']),
                                     ('unspecified', 'unspecified'), name + ' must keep its ordinary policy')
                index = indexed_bytes(repo, ingest)
                for name, raw in targets.items():
                    self.assertEqual(index[name], raw, name)
                    clean_count += 1
                for name, raw in protected.items():
                    self.assertEqual(index[name], raw, name)
                self.assertEqual(index['checkout-control.bin'], synthetic['checkout-control.bin'])
                for checkout in ('false', 'true'):
                    folder = home / (ingest[0] + checkout[0])
                    folder.mkdir()
                    git(repo, ['checkout-index', '--all', '--prefix=' + folder.as_posix() + '/'], checkout)
                    for name, raw in targets.items():
                        self.assertEqual((folder / name).read_bytes(), raw, name)
                        checkout_count += 1
                    for name, raw in protected.items():
                        self.assertEqual((folder / name).read_bytes(), raw, name)
                    self.assertEqual((folder / 'checkout-control.bin').read_bytes(), synthetic['checkout-control.bin'])
                    expected = b'ordinary LF control\r\n' if checkout == 'true' else synthetic['checkout-control.txt']
                    self.assertEqual((folder / 'checkout-control.txt').read_bytes(), expected,
                                     'The negative control must actually exercise the selected Git text filter')
        self.assertEqual((clean_count, checkout_count), (40, 80))
        print('Git byte contracts: 40 indexed + 80 checkout target comparisons; '
              + str(len(protected)) + ' existing raw-packet files retained per configuration')

    def test_current_drawing_manifests_match_exact_working_bytes(self):
        seen = set()
        for manifest, model, layout in (
                ('data/bayer_rt/pid/manifest.json', 'data/bayer_rt/process_model.json', 'data/bayer_rt/pid_layout.json'),
                ('data/te_pid/manifest.json', 'data/te_process_model.json', 'data/te_pid_layout.json')):
            saved = json.loads((ROOT / manifest).read_bytes())
            for field, name in (('generator_sha256', 'scripts/draw_pid_from_model.py'),
                                ('model_sha256', model), ('layout_sha256', layout)):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), saved[field],
                                 name + ' must retain the current manifest raw-byte contract')
                seen.add(name)
        self.assertEqual(len(seen), 5)

    def test_historical_manifest_identity_is_not_relabelled_current(self):
        current = hashlib.sha256((ROOT / 'scripts/draw_pid_from_model.py').read_bytes()).hexdigest()
        for name in ('data/te_pid/rev-a/manifest.json', 'data/te_pid/rev-c/manifest.json'):
            saved = json.loads((ROOT / name).read_bytes())
            self.assertNotEqual(current, saved['generator_sha256'], name)
        # These raw identity predicates do not claim actual drawn_truth API execution.


if __name__ == '__main__':
    unittest.main()
