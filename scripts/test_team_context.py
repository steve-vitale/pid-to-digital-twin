"""Exercise separate team dependencies, source disputes and portable complete packets. Stdlib only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import context_register
import graph_export

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/team-context'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8')
SCOPES = ('site-a-process', 'site-a-ei', 'site-a-maintenance', 'site-b-process')


def read(path):
    return json.loads(path.read_bytes())


def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


class TeamContext(unittest.TestCase):
    def test_actual_separate_refresh_and_same_base_conflicts_preserve_evidence(self):
        before = hashes(EXAMPLE)
        with tempfile.TemporaryDirectory(prefix='team context ') as tmp:
            out = Path(tmp) / 'journey'
            command = [sys.executable, '-S', str(EXAMPLE / 'reproduce.py'), '--out', str(out)]
            result = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            def packet(scope, stage):
                return out / 'packets' / scope / stage
            initial, refreshed = {}, {}
            for scope in SCOPES:
                initial[scope] = read(packet(scope, 'A') / 'context.json')
                refreshed[scope] = read(packet(scope, 'refreshed') / 'context.json')
                self.assertEqual(refreshed[scope]['decisions'], initial[scope]['decisions'])
                self.assertEqual(refreshed[scope]['ownership_history'], initial[scope]['ownership_history'])
                self.assertTrue(all(d['plant_truth'] == 'unknown' for d in refreshed[scope]['decisions']))
            for scope in SCOPES[:2]:
                answer, = refreshed[scope]['current']['BASIS@P-1']['answers']
                self.assertEqual(answer['freshness'], 'stale')
                self.assertIn('source revision/bytes/locator', answer['changed'])
            for scope in SCOPES[2:]:
                # Both registers were actually refreshed, rather than merely left unopened.
                self.assertEqual(refreshed[scope], initial[scope])
                for name in ('context.json', 'context.md', 'enriched_graph.json', 'enriched_questions.json'):
                    self.assertEqual((packet(scope, 'A') / name).read_bytes(),
                                     (packet(scope, 'refreshed') / name).read_bytes())
            loop = initial['site-a-ei']['current']['LOOP@P-1']
            base = read(packet('site-a-ei', 'B') / 'context.json')
            self.assertEqual(base['current']['BASIS@P-1']['state'], 'partial')
            proposals = []
            for stage in ('proposals-forward', 'proposals-reverse'):
                register = read(packet('site-a-ei', stage) / 'context.json')
                self.assertEqual(register['decisions'][:len(base['decisions'])], base['decisions'])
                self.assertEqual(register['current']['LOOP@P-1'], loop)
                current = register['current']['PROPOSAL@P-1']
                self.assertEqual((current['state'], current['disputed_claims']),
                                 ('disputed', ['proposed-pressure-kPa']))
                records = sorted((d for d in register['decisions'] if d['question_id'] == 'PROPOSAL@P-1'),
                                 key=lambda d: d['answer_id'])
                self.assertEqual({d['value'] for d in records}, {'200 kPa', '220 kPa'})
                self.assertEqual(len({d['answer_id'] for d in records}), 2)
                self.assertEqual(len({d['reviewer'] for d in records}), 2)
                self.assertEqual(records[0]['evidence'], records[1]['evidence'])
                self.assertTrue(all((d['decision'], d['answer_state'], d['plant_truth']) ==
                                    ('proposed', 'partial', 'unknown') for d in records))
                proposals.append(records)
            self.assertEqual(*proposals)  # Complete records, including attribution, IDs and evidence.
            for scope in SCOPES:
                for register_path in (out / 'packets' / scope).glob('*/context.json'):
                    graph = read(register_path.with_name('enriched_graph.json'))
                    self.assertEqual(graph_export.problems(graph), [])
                    context_register.validate_export(graph, read(register_path))
            mapping = read(EXAMPLE / 'inputs/OWNED-SCOPES.json')
            self.assertFalse(mapping['product_schema'])
            self.assertEqual({p['native_asset'] for p in mapping['packets']}, {'P-1'})
            self.assertEqual([p['supplied_company_asset'] for p in mapping['packets']],
                             ['training:site-a:pump-001'] * 3 + ['training:site-b:pump-001'])
            completed = hashes(out)
            refused = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True, timeout=30)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(hashes(out), completed)
        self.assertEqual(hashes(EXAMPLE), before)

    def test_all_worked_pins_survive_git_filters_and_selected_pairs_remain_bound(self):
        # Scoped -text preserves94 evidence files; the3 ordinary entry files have declared LF identities.
        expected = {p.relative_to(EXAMPLE).as_posix(): p.read_bytes() for p in EXAMPLE.rglob('*') if p.is_file()}
        self.assertEqual(len(expected), 97)
        raw = {name for name in expected if name.startswith(('inputs/', 'worked/'))}
        self.assertEqual(len(raw), 94)
        for name in set(expected) - raw:
            self.assertNotIn(b'\r', expected[name], name)
        with tempfile.TemporaryDirectory(prefix='team git ') as tmp:
            tmp = Path(tmp)
            for ingest in ('true', 'false'):
                repo = tmp / ('r' + ingest)
                repo.mkdir()
                shutil.copytree(EXAMPLE, repo / 'packet')
                def git(*args):
                    result = subprocess.run(['git', '-c', 'core.safecrlf=false', '-c', 'core.autocrlf=' + ingest,
                                             *args], cwd=repo, capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result.stdout
                git('init', '--quiet')
                git('add', '--', 'packet')
                for name, data in expected.items():
                    self.assertEqual(git('show', ':packet/' + name), data, name)
                for checkout in ('true', 'false'):
                    dest = tmp / ('c' + ingest + checkout)
                    dest.mkdir()
                    git('-c', 'core.autocrlf=' + checkout, 'checkout-index', '--all', '--force',
                        '--prefix=' + str(dest).replace('\\', '/') + '/')
                    for name, data in expected.items():
                        self.assertEqual((dest / 'packet' / name).read_bytes(), data, name)
                    contexts = list((dest / 'packet/worked/packets').glob('*/*/context.json'))
                    self.assertEqual(len(contexts), 7)
                    for context in contexts:
                        graph = read(context.with_name('enriched_graph.json'))
                        self.assertEqual(graph_export.problems(graph), [])
                        context_register.validate_export(graph, read(context))


if __name__ == '__main__':
    unittest.main()
