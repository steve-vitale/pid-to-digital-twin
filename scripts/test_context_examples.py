"""Reproduce the offline context runbook and check the public-source question-engine bridge.

The small training packet is invented. The Bayer bridge uses committed public-source snapshots;
these offline controls do not read its downloaded original or establish plant truth.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
import graph_export
import context_register

ROOT = Path(__file__).resolve().parent.parent
PACKET = ROOT / 'examples/context-register/illustrative'
ENV = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}


def invoke(*args, cwd=None):
    result = subprocess.run([sys.executable, '-S', str(ROOT / 'scripts/context_register.py'), *map(str, args)],
                            cwd=cwd, env=ENV, capture_output=True, encoding='utf-8', timeout=30)
    return result


class WorkedContext(unittest.TestCase):
    def test_actual_question_engine_bridge_retains_requests_and_partial_answer(self):
        packet = ROOT / 'examples/context-register/bayer'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'screen'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/question_engine.py'), '--model',
                str(ROOT / 'data/bayer_rt/process_model.json'), '--question', 'E18', '--out', str(out)],
                cwd=ROOT, env=ENV, capture_output=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ('questions.json', 'screen.md'):
                self.assertEqual((out / name).read_bytes(), (packet / 'screen' / name).read_bytes(), name)
            _, generated, questions = context_register.load_inputs(ROOT / 'data/bayer_rt/process_model.json',
                                                                   out / 'questions.json')
            register = json.loads((packet / 'expected/context.json').read_text(encoding='utf-8'))
            context_register.validate_register(register)
            self.assertEqual(register['current']['E18@model']['state'], 'partial')
            decision, = register['decisions']
            self.assertEqual(decision['decision'], 'proposed')
            self.assertEqual(decision['plant_truth'], 'unknown')
            self.assertEqual(decision['evidence']['question'], questions['E18@model']['question'])
            self.assertEqual(decision['evidence']['assets'], questions['E18@model']['assets'])
            enriched = json.loads((packet / 'expected/enriched_questions.json').read_text(encoding='utf-8'))
            original = generated['questions'][0]
            for key in ('assets', 'data_requests', 'decision_rule', 'limits'):
                self.assertEqual(enriched['questions'][0][key], original[key])
            report = (packet / 'expected/context.md').read_text(encoding='utf-8')
            self.assertEqual(len(original['data_requests']), 3)
            for request in original['data_requests']:
                self.assertIn(context_register.md(request['item']), report)
                self.assertIn(context_register.md(request['how']), report)
            self.assertIn(context_register.md(original['limits']), report)

    def test_runbook_reproduces_every_expected_file_without_changing_sources(self):
        before = {p.name: p.read_bytes() for p in PACKET.iterdir() if p.is_file()}
        text = (PACKET / 'README.md').read_text(encoding='utf-8')
        block = re.search(r'```sh\n(.*?)```', text, re.S).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            for line in block.splitlines():
                args = shlex.split(line)
                self.assertEqual(args[:2], ['python', '-S'])
                args = [str(ROOT / a) if a.startswith(('scripts/', 'examples/')) else a for a in args[2:]]
                result = subprocess.run([sys.executable, '-S', *args], cwd=tmp, env=ENV,
                                        capture_output=True, encoding='utf-8', timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
            current = Path(tmp) / 'my-context/current'
            expected = PACKET / 'expected'
            self.assertEqual(sorted(p.name for p in current.iterdir()), sorted(p.name for p in expected.iterdir()))
            for path in expected.iterdir():
                self.assertEqual((current / path.name).read_bytes(), path.read_bytes(), path.name)
            register = json.loads((current / 'context.json').read_text(encoding='utf-8'))
            self.assertEqual({v['state'] for v in register['current'].values()},
                             {'answered', 'disputed', 'needs_data', 'unanswered'})
            self.assertTrue(all(v['plant_truth'] == 'unknown' for v in register['decisions']))
            graph = json.loads((current / 'enriched_graph.json').read_text(encoding='utf-8'))
            self.assertEqual(graph['counts']['questions'], 4)
            baseline = graph_export.build(PACKET / 'model.json')
            self.assertEqual({n['id']: n['status'] for n in graph['nodes']},
                             {n['id']: n['status'] for n in baseline['nodes']})
        self.assertEqual(before, {p.name: p.read_bytes() for p in PACKET.iterdir() if p.is_file()})

    def test_source_revision_reopens_only_dependent_answers_and_refuses_old_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            source_root = temp / 'sources'
            source_root.mkdir()
            for name in ('basis.txt', 'later-note.txt', 'service-sheet.txt'):
                (source_root / name).write_bytes((PACKET / name).read_bytes())
            manifest = json.loads((PACKET / 'sources.json').read_text(encoding='utf-8'))
            changed = source_root / 'basis.txt'
            changed.write_bytes(changed.read_bytes() + b'Revision control: synthetic change for test only.\n')
            revised = copy.deepcopy(manifest)
            doc = next(d for d in revised['documents'] if d['id'] == 'BASIS')
            doc['revision'] = 'A-test-revision'
            doc['sha256'] = hashlib.sha256(changed.read_bytes()).hexdigest()
            manifest_path = temp / 'sources.json'
            manifest_path.write_text(json.dumps(revised), encoding='utf-8')
            shared = ['--model', PACKET / 'model.json', '--questions', PACKET / 'questions.json',
                      '--sources', manifest_path, '--source-root', source_root]
            prior = PACKET / 'expected/context.json'
            prior_bytes = prior.read_bytes()
            refused = invoke('apply', *shared, '--register', prior, '--answers', PACKET / 'filled_answers.csv',
                             '--out', temp / 'refused')
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn('stale', refused.stderr)
            self.assertFalse((temp / 'refused').exists())
            refreshed = invoke('apply', *shared, '--register', prior, '--out', temp / 'refreshed')
            self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
            original = json.loads(prior_bytes)
            current = json.loads((temp / 'refreshed/context.json').read_text(encoding='utf-8'))
            self.assertEqual(original['decisions'], current['decisions'])
            self.assertEqual(current['current']['service@P-102']['state'], 'answered')
            freshness = {a['answer_id']: a['freshness'] for q in current['current'].values() for a in q['answers']}
            self.assertEqual(freshness, {'basis-pressure': 'stale', 'later-pressure': 'current',
                                         'range-request': 'current', 'service': 'current'})
            self.assertEqual(prior.read_bytes(), prior_bytes)


if __name__ == '__main__':
    unittest.main()
