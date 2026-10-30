"""Reproduce the offline context runbook and check the public-source question-engine bridge.

The small training packet is invented. The Bayer bridge uses committed public-source snapshots;
these offline controls do not read its downloaded original or establish plant truth.
"""
import copy
import csv
import hashlib
import importlib.util
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
    def test_metropt_expected_write_preflights_both_destinations(self):
        """Regression for --write aliasing an original; labelled local filesystem fixtures, not source evidence."""
        packet = ROOT / 'examples/context-register/metropt3'
        sys.path.insert(0, str(packet))
        try:
            spec = importlib.util.spec_from_file_location('metropt_context_checks', packet / 'check_packet.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / 'original.pdf'
            source.write_bytes(b'ILLUSTRATIVE FILESYSTEM GUARD FIXTURE')
            out = folder / 'expected'
            out.mkdir()
            targets = [out / 'context.json', out / 'context.md']
            for target in targets:
                target.write_bytes(b'previous expected contents')
            for target in targets:
                with self.subTest(alias=target.name):
                    old = target.read_bytes()
                    target.unlink()
                    os.link(source, target)
                    before = {p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
                    with self.assertRaisesRegex(ValueError, 'regular file|linked'):
                        module.preflight_expected(targets, [source])
                    self.assertEqual(before, {p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()})
                    target.unlink()
                    target.write_bytes(old)
            conflict = out / 'ordinary-file'
            conflict.write_text('authored file', encoding='utf-8')
            before = {p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(ValueError, 'directory'):
                module.preflight_expected([targets[0], conflict / 'context.md'], [source])
            self.assertEqual(before, {p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()})

    def test_metropt_offline_packet_retains_qualified_claims_and_collection_requests(self):
        """Committed snapshots are software fixtures; this test does not verify absent original sources."""
        packet = ROOT / 'examples/context-register/metropt3'
        register = json.loads((packet / 'expected/context.json').read_text(encoding='utf-8'))
        context_register.validate_register(register)
        key = json.loads((packet / 'source_key.json').read_text(encoding='utf-8'))
        _, _, questions = context_register.load_inputs(packet / 'model.json', packet / 'questions.json')
        with (packet / 'proposed_answers.csv').open(encoding='utf-8', newline='') as stream:
            proposals = {row['answer_id']: row for row in csv.DictReader(stream)}
        self.assertEqual(len(register['decisions']), 12)
        self.assertEqual(len(register['current']), 6)
        self.assertEqual(sum(q['state'] == 'needs_data' for q in register['current'].values()), 5)
        self.assertFalse(register['ownership_history'])
        self.assertTrue(all(q['owner'] is None for q in register['current'].values()))
        self.assertTrue(all(d['decision'] == 'proposed' and d['plant_truth'] == 'unknown'
                            and not d['reviewer'] and not d['reviewed_on'] for d in register['decisions']))
        decisions = {d['answer_id']: d for d in register['decisions']}
        for fact in key['facts']:
            decision = decisions['MPT-' + fact['id']]
            self.assertEqual(proposals[decision['answer_id']]['evidence_fingerprint'], decision['evidence_fingerprint'])
            self.assertEqual(decision['evidence']['question'], questions[fact['question_id']]['question'])
            for field in ('value', 'answer', 'answer_state', 'claim_key'):
                self.assertEqual(decision[field], fact[field])
            source = decision['evidence']['source']
            self.assertEqual((source['id'], source['sha256'], source['locator']),
                             (fact['document_id'], fact['raw_sha256'], fact['locator']))
        report = (packet / 'expected/context.md').read_text(encoding='utf-8')
        self.assertIn('30Apr', report)
        self.assertIn('Work-record ID/revision', report)
        self.assertIn('chosen metric', report)
        self.assertIn('off or offloaded', report)
        self.assertIn('DV_eletric', report)

    def test_metropt_actual_original_workflow_when_cached(self):
        """An explicit optional original-source check; no downloads and no use of a derived substitute."""
        archive = ROOT / 'data/external/metropt3/metropt3.zip'
        if not archive.is_file():
            self.skipTest('MetroPT original ZIP not cached; run python scripts/fetch_corpus.py metropt3 --max-mb 250')
        packet = ROOT / 'examples/context-register/metropt3'
        before = hashlib.sha256(archive.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'originals'
            prepare = [sys.executable, '-S', str(packet / 'prepare_sources.py'), '--zip', str(archive), '--out', str(source)]
            for command in (prepare, prepare,
                            [sys.executable, '-S', str(packet / 'verify_sources.py'), '--source-root', str(source)],
                            [sys.executable, '-S', str(packet / 'check_packet.py'), '--source-root', str(source)]):
                result = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True, encoding='utf-8', timeout=180)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            description = source / 'Data Description_Metro.pdf'
            description.write_bytes(description.read_bytes() + b'\nTEST-ONLY MANUAL EDIT\n')
            old = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
            refused = subprocess.run(prepare, cwd=ROOT, env=ENV, capture_output=True, encoding='utf-8', timeout=60)
            self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
            self.assertIn('changed original', refused.stderr)
            self.assertEqual(old, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()})
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), before)

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
