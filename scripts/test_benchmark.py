"""Community benchmark controls: failures, frozen cohorts, source integrity and reproducible scores."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

import benchmark as b

ROOT = Path(__file__).resolve().parent.parent


class BenchmarkTests(unittest.TestCase):
    def test_historical_recipe_relocation_preserves_saved_attempts(self):
        """Current registration may relocate frozen recipes; it must not rewrite what the old attempt did."""
        for stem in ('description-controls', 'mgpi-development'):
            with self.subTest(suite=stem):
                original = b.read_json(ROOT / f'benchmarks/{stem}.json')
                current = b.read_json(ROOT / f'benchmarks/{stem}-recipe-preserved.json')
                self.assertEqual({k:v for k,v in original.items() if k != 'runs'},
                                 {k:v for k,v in current.items() if k != 'runs'})
                self.assertEqual(len(original['runs']), len(current['runs']))
                for old_path, new_path in zip(original['runs'], current['runs']):
                    self.assertNotEqual(old_path, new_path)
                    old, new = b.read_json(ROOT / old_path), b.read_json(ROOT / new_path)
                    self.assertEqual({k:v for k,v in old.items() if k not in ('recipe','provenance')},
                                     {k:v for k,v in new.items() if k not in ('recipe','provenance')})
                    self.assertTrue(new['provenance'].startswith(old['provenance']))
                    self.assertIn('metadata relocation', new['provenance'])
                    self.assertEqual(len(old['recipe']), len(new['recipe']))
                    for before, after in zip(old['recipe'], new['recipe']):
                        self.assertEqual({k:v for k,v in before.items() if k != 'path'},
                                         {k:v for k,v in after.items() if k != 'path'})
                        # The scorer itself validates the archived content against the historical fingerprint.
                        b.reference(ROOT, after)
                        if before['path'] != after['path']:
                            self.assertTrue(after['path'].startswith('benchmarks/recipes/'))
                            self.assertTrue(after['path'].endswith('.txt'))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='benchmark-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.answer = {'units': [{'id': 'TK-1', 'type': 'tank'}],
                       'streams': [{'id': 'S1', 'from': 'BL', 'to': 'TK-1'}]}
        self.save('input.txt', {'description': 'TK-1 tank, S1 from BL to TK-1. Synthetic.'})
        self.save('expected.json', self.answer)
        self.save('key.json', {'facts': [json.loads(f) for f in sorted(b.native_facts(self.answer))]})
        self.save('prompt.json', {'instructions': 'Use source-backed literal native fields.'})
        self.save('answer.json', self.answer)
        self.case = {'id': 'case1', 'family': 'synthetic', 'split': 'synthetic-control',
                     'evidence': 'authored scorer control', 'source_url': 'repository:fixture',
                     'license': 'synthetic fixture', 'key_author': 'test author',
                     'files': {k: self.ref(p) for k, p in [('input', 'input.txt'), ('key', 'key.json'), ('expected', 'expected.json')]}}
        self.run = {'id': 'run1', 'model': {'provider': 'none', 'id': 'test-model', 'version': 'test-v1'},
                    'interface': 'fixture', 'method': 'reference', 'configuration': {}, 'ran_at': '2026-10-30',
                    'provenance': 'No model call.', 'recipe': [self.ref('prompt.json')], 'cases': ['case1'],
                    'predictions': {'case1': self.ref('answer.json')}}
        self.suite = {'id': 'test', 'version': '1', 'task': 'description-facts', 'protocol': 'literal fields',
                      'registration': 'synthetic software control', 'cases': [self.case], 'runs': ['run.json']}

    def save(self, path, value):
        target = self.root / path
        target.write_bytes(b.encoded(value))
        return target

    def ref(self, path):
        return {'path': path, 'sha256': b.file_hash(self.root / path)}

    def evaluate(self):
        self.save('run.json', self.run)
        return b.evaluate(self.save('suite.json', self.suite), self.root)

    def test_perfect_empty_wrong_and_unscored_names(self):
        perfect = self.evaluate()['results'][0]
        self.assertEqual(perfect['metrics']['facts']['f1'], 1)
        self.assertEqual(perfect['rows'][0]['status'], 'ok')
        wrong = copy.deepcopy(self.answer)
        wrong['streams'][0]['to'] = 'NO-SUCH-UNIT'
        self.save('answer.json', wrong)
        self.run['predictions']['case1'] = self.ref('answer.json')
        self.assertLess(self.evaluate()['results'][0]['metrics']['facts']['f1'], 1)
        self.save('answer.json', {'units': []})
        self.run['predictions']['case1'] = self.ref('answer.json')
        self.assertEqual(self.evaluate()['results'][0]['metrics']['facts']['f1'], 0)
        answer = copy.deepcopy(self.answer)
        answer['units'][0]['name'] = 'Deliberately incorrect, outside this scoring subset'
        self.save('answer.json', answer)
        self.run['predictions']['case1'] = self.ref('answer.json')
        self.assertEqual(self.evaluate()['results'][0]['metrics']['facts']['f1'], 1)

    def test_failed_missing_and_malformed_attempts_are_not_dropped(self):
        for value in ({'prediction': None, 'error': 'failed'}, {'units': 'invalid'}, {'a': 1, 'prediction': []}):
            with self.subTest(value=value):
                self.save('answer.json', value)
                self.run['predictions']['case1'] = self.ref('answer.json')
                row = self.evaluate()['results'][0]
                self.assertEqual(row['metrics']['facts']['f1'], 0)
                self.assertNotEqual(row['rows'][0]['status'], 'ok')
        self.run['predictions'] = {}
        self.assertEqual(self.evaluate()['results'][0]['rows'][0]['status'], 'missing')
        self.assertEqual(self.evaluate()['results'][0]['metrics']['facts']['f1'], 0)

    def test_new_unattempted_case_retains_old_cohort(self):
        before = self.evaluate()['results'][0]
        new = copy.deepcopy(self.case)
        new['id'] = 'case2'
        self.suite['cases'].append(new)
        after = self.evaluate()['results'][0]
        self.assertEqual(before['cohort'], after['cohort'])
        self.assertEqual(after['not_attempted'], ['case2'])
        self.run['cases'].append('case2')
        self.run['predictions']['case2'] = self.ref('answer.json')
        expanded = self.evaluate()['results'][0]
        self.assertNotEqual(before['cohort'], expanded['cohort'])
        self.assertEqual(expanded['case_count'], 2)

    def test_changed_keys_prompt_and_answers_refuse(self):
        for name in ('key.json', 'prompt.json', 'answer.json'):
            original = (self.root / name).read_bytes()
            (self.root / name).write_bytes(original + b' ')
            with self.assertRaisesRegex(ValueError, 'Stale file fingerprint'):
                self.evaluate()
            (self.root / name).write_bytes(original)

    def test_source_newlines_preserve_cohort_and_report(self):
        from unittest.mock import patch
        sources = ['benchmark.py', 'score_pid2graph.py', 'evaluate_vendor.py',
                   'replicate_stats.py', 'score_tags.py', 'test_scorer_controls.py']
        variants = []
        for newline, folder in ((b'\n', 'lf'), (b'\r\n', 'crlf')):
            directory = self.root / folder
            directory.mkdir()
            for name in sources:
                raw = (ROOT / 'scripts' / name).read_bytes().replace(b'\r\n', b'\n')
                (directory / name).write_bytes(raw.replace(b'\n', newline))
            with patch.object(b, '__file__', str(directory / 'benchmark.py')):
                variants.append(b.evaluate(ROOT / 'benchmarks/open100-validation.json', ROOT))
        self.assertEqual(b.encoded(variants[0]), b.encoded(variants[1]))
        self.assertEqual(b.markdown(variants[0]), b.markdown(variants[1]))
        for name in sources:
            self.assertEqual(b.file_hash(self.root / 'lf' / name), b.file_hash(self.root / 'crlf' / name))
        # Source edits still change the fingerprint; binary newlines stay significant.
        source = self.root / 'crlf' / 'score_tags.py'
        source.write_bytes(source.read_bytes() + b'# changed\r\n')
        self.assertNotEqual(b.file_hash(source), b.file_hash(self.root / 'lf' / source.name))
        for directory, raw in (('lf', b'a\nb'), ('crlf', b'a\r\nb')):
            (self.root / directory / 'binary.png').write_bytes(raw)
        self.assertNotEqual(b.file_hash(self.root / 'lf/binary.png'), b.file_hash(self.root / 'crlf/binary.png'))

    def test_replicate_identity_model_versions_and_configuration_stay_separate(self):
        run2 = copy.deepcopy(self.run)
        run2['id'] = 'run2'
        self.suite['runs'].append('run2.json')
        self.save('run2.json', run2)
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.evaluate()
        self.save('answer2.json', self.answer)
        run2['predictions']['case1'] = self.ref('answer2.json')
        self.save('run2.json', run2)
        self.assertEqual(self.evaluate()['summary'][0]['replicates'], 2)
        run2['model']['version'] = 'test-v2'
        self.save('run2.json', run2)
        self.assertEqual(len(self.evaluate()['summary']), 2)
        run2['model']['version'] = 'test-v1'
        run2['configuration'] = {'different_prompt_mode': True}
        self.save('run2.json', run2)
        self.assertEqual(len(self.evaluate()['summary']), 2)

    def test_family_split_and_evidence_are_not_pooled(self):
        new = copy.deepcopy(self.case)
        new.update(id='case2', family='another-family', split='development', evidence='different truth')
        self.suite['cases'].append(new)
        self.run['cases'].append('case2')
        self.run['predictions']['case2'] = self.ref('answer.json')
        report = self.evaluate()
        self.assertEqual(len(report['results']), 2)
        self.assertEqual(len({r['cohort'] for r in report['results']}), 2)

    def test_bad_key_and_path_escape_refuse_before_scoring(self):
        self.save('key.json', {'facts': [['not-a-section', 'x', 'y', 1]]})
        self.case['files']['key'] = self.ref('key.json')
        with self.assertRaisesRegex(ValueError, 'Fact key'):
            self.evaluate()
        with self.assertRaisesRegex(ValueError, 'escapes'):
            b.local(self.root, '../outside.json')

    def test_schema_label_cannot_disable_recorded_metadata_binding(self):
        case = {'files': {'input': {'sha256': 'input-fingerprint'}}}
        self.run.update(recorded_tool='test-cli', configuration={'tiles': '2x2', 'overlap': 0.15, 'trace': 'replace'})
        self.run['recipe'][0]['role'] = 'main_prompt'
        self.save('preface.json', {'instructions': 'Tile-specific preface'})
        preface = dict(self.ref('preface.json'), role='tile_preface')
        self.run['recipe'].append(preface)
        good = {'prediction': self.answer, 'model': 'test-model', 'tool': 'test-cli',
                'image_sha256': 'input-fingerprint', 'prompt_sha256': self.run['recipe'][0]['sha256'],
                'tiling': {'grid': '2x2', 'overlap': 0.15, 'preface_sha256': preface['sha256']}, 'tracer': {'mode': 'replace'}}
        for schema in ('pid-prediction/1', 'unsupported-schema', None):
            record = copy.deepcopy(good)
            if schema:
                record['schema'] = schema
            b.check_saved_metadata(record, self.run, case)
            for field, value in [('model', 'other-model'), ('tool', 'other-cli'),
                                 ('image_sha256', 'wrong-input'), ('prompt_sha256', 'wrong-prompt'),
                                 ('tiling', {'grid': '1x1'}), ('tracer', {'mode': 'augment'})]:
                wrong = dict(record, **{field: value})
                with self.subTest(schema=schema, field=field), self.assertRaises(b.ProvenanceError):
                    b.check_saved_metadata(wrong, self.run, case)
            for wrong_preface in ('0' * 64, self.run['recipe'][0]['sha256']):
                wrong = dict(record, tiling=dict(record['tiling'], preface_sha256=wrong_preface))
                with self.assertRaisesRegex(b.ProvenanceError, 'tile preface'):
                    b.check_saved_metadata(wrong, self.run, case)
        # A failed attempt before metadata was captured still scores as failed, not omitted.
        b.check_saved_metadata({'schema': 'pid-prediction/1', 'prediction': None, 'error': 'timeout'}, self.run, case)
        with self.assertRaisesRegex(b.ProvenanceError, 'envelope needs prediction'):
            b.check_saved_metadata({'schema': 'pid-prediction/1', 'symbols': [], 'connections': []}, self.run, case)

    def test_flattened_drawing_envelope_cannot_bypass_saved_identity(self):
        suite = b.read_json(ROOT / 'benchmarks/open100-validation.json')
        case = copy.deepcopy(suite['cases'][0])
        run = b.read_json(ROOT / suite['runs'][0])
        record = b.read_json(ROOT / run['predictions'][case['id']]['path'])
        for kind, ref in case['files'].items():
            name = kind + Path(ref['path']).suffix
            (self.root / name).write_bytes((ROOT / ref['path']).read_bytes())
            case['files'][kind] = self.ref(name)
        recipe = []
        for i, ref in enumerate(run['recipe']):
            name = 'recipe-' + str(i) + '.md'
            (self.root / name).write_bytes((ROOT / ref['path']).read_bytes())
            recipe.append(dict(self.ref(name), **({'role': ref['role']} if 'role' in ref else {})))
        run.update(cases=[case['id']], recipe=recipe, predictions={})
        self.run = run
        self.suite = dict(suite, cases=[case], runs=['run.json'])
        flat = dict(record)
        flat.update(flat.pop('prediction'))
        flat.update(model='wrong-model', image_sha256='wrong-input', prompt_sha256='wrong-prompt')
        for schema in ('pid-prediction/1', 'vendor-unknown', None):
            candidate = dict(flat)
            if schema:
                candidate['schema'] = schema
            else:
                candidate.pop('schema', None)
            self.save('flat.json', candidate)
            self.run['predictions'] = {case['id']: self.ref('flat.json')}
            with self.subTest(schema=schema), self.assertRaises(b.ProvenanceError):
                self.evaluate()
        self.save('flat.json', record['prediction'])
        self.run['predictions'] = {case['id']: self.ref('flat.json')}
        result = self.evaluate()['results'][0]
        self.assertEqual(result['rows'][0]['status'], 'ok')
        self.assertGreater(result['counts']['symbols_rough']['tp'], 0)

    def test_same_file_hardlink_is_not_another_replicate(self):
        alias = self.root / 'answer-alias.json'
        try:
            os.link(self.root / 'answer.json', alias)
        except OSError as exc:
            self.skipTest('This filesystem cannot create a hardlink: ' + str(exc))
        run2 = copy.deepcopy(self.run)
        run2['id'] = 'hardlink-run'
        run2['predictions']['case1'] = self.ref(alias.name)
        self.save('run2.json', run2)
        self.suite['runs'].append('run2.json')
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.evaluate()

    def test_report_check_refuses_changed_report_and_does_not_overwrite(self):
        self.evaluate()
        args = ['--suite', str(self.root / 'suite.json'), '--root', str(self.root), '--out', str(self.root / 'report')]
        self.assertEqual(b.main(args), 0)
        original = (self.root / 'report.json').read_bytes()
        self.assertEqual(b.main(args + ['--check']), 0)
        self.assertEqual(b.main(args), 2)
        self.assertEqual((self.root / 'report.json').read_bytes(), original)
        (self.root / 'report.md').write_text('Changed report', encoding='utf-8')
        self.assertEqual(b.main(args + ['--check']), 2)

    def test_historical_drawing_counts_match_existing_frozen_scorer(self):
        suite = b.read_json(ROOT / 'benchmarks/open100-validation.json')
        # Two separate drawings make an accidental last-case fingerprint reuse observable.
        suite['cases'] = suite['cases'][:2]
        suite['runs'] = suite['runs'][:1]
        run = b.read_json(ROOT / suite['runs'][0])
        run['cases'] = [c['id'] for c in suite['cases']]
        run['predictions'] = {k: v for k, v in run['predictions'].items() if k in run['cases']}
        local_run = ROOT / 'benchmarks/runs' / Path(run['id'] + '.json')
        # Evaluate an in-memory selected run using mock only for run-file lookup; scores read real keys/answers.
        from unittest.mock import patch
        original = b.read_json
        suite_path = self.save('historical-suite.json', suite)
        def read(path):
            return run if path == (ROOT / suite['runs'][0]).resolve() else original(path)
        with patch.object(b, 'read_json', side_effect=read):
            report = b.evaluate(suite_path, ROOT)
        import score_pid2graph as scorer
        for row, case in zip(report['results'][0]['rows'], suite['cases']):
            pred = original(ROOT / run['predictions'][case['id']]['path'])['prediction']
            expected = scorer.score(ROOT / case['files']['key']['path'], pred, ROOT / case['files']['input']['path'])
            self.assertEqual(row['counts']['networks']['tp'], expected['connections']['tp'])
            self.assertEqual(row['counts']['symbols_rough']['tp'], expected['rough']['classified']['tp'])


if __name__ == '__main__':
    unittest.main()
