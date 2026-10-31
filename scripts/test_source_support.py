"""Offline controls for bounded source-judgment labels, exact evidence joins and failure accounting."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark as b
import source_support as ss

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'benchmarks/source-support'


class SourceSupport(unittest.TestCase):
    def setUp(self):
        self.packet = b.read_json(PACKET / 'mgpi.input.json')
        self.key = b.read_json(PACKET / 'mgpi.key.json')
        self.reference = b.read_json(ROOT / 'benchmarks/controls/source-support/mgpi-reference.json')

    def test_reference_empty_and_uniform_approval_have_distinct_outcomes(self):
        rows, diagnostics = ss.score(self.packet, self.key, self.reference)
        self.assertEqual(rows['judgments'], {'tp': 6, 'predicted': 6, 'truth': 6})
        self.assertEqual(diagnostics['exact_label_accuracy'], 1)
        self.assertFalse(diagnostics['reason_quality_scored'])
        controls = ss.controls(self.packet, self.key)
        self.assertEqual(controls['empty']['judgments']['tp'], 0)
        for label in ss.LABELS:
            self.assertEqual(controls['all_' + label]['judgments'], {'tp': 2, 'predicted': 6, 'truth': 6})

    def test_false_approval_historical_extrapolation_and_silence_are_distinct_errors(self):
        supplied = copy.deepcopy(self.reference)
        for row in supplied['decisions']:
            if row['id'] in ('SJ003', 'SJ005', 'SJ006'):
                row['judgment'] = 'supported'
        counts, diagnostics = ss.score(self.packet, self.key, supplied)
        self.assertEqual(counts['judgments']['tp'], 3)
        errors = {row['id']: row['expected'] for row in diagnostics['incorrect_judgments']}
        self.assertEqual(errors, {'SJ003': 'contradicted', 'SJ005': 'insufficient-evidence',
                                  'SJ006': 'insufficient-evidence'})

    def test_missing_judgment_is_not_silently_abstained_or_renormalized(self):
        supplied = copy.deepcopy(self.reference)
        supplied['decisions'].pop()
        counts, diagnostics = ss.score(self.packet, self.key, supplied)
        self.assertEqual(counts['judgments'], {'tp': 5, 'predicted': 5, 'truth': 6})
        self.assertEqual(diagnostics['exact_label_accuracy'], 5 / 6)
        self.assertEqual(diagnostics['missing_judgments'], ['SJ006'])

    def test_unknown_duplicate_padded_and_cross_claim_references_refuse(self):
        for field, value in [('id', 'SJ999'), ('id', ' SJ001'), ('judgment', 'maybe'),
                             ('evidence_ids', ['E02']), ('evidence_ids', ['E01', 'E01']), ('reason', '')]:
            with self.subTest(field=field, value=value):
                answer = copy.deepcopy(self.reference)
                answer['decisions'][0][field] = value
                with self.assertRaises(ValueError):
                    ss.score(self.packet, self.key, answer)
        answer = copy.deepcopy(self.reference)
        answer['decisions'].append(copy.deepcopy(answer['decisions'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate decision'):
            ss.score(self.packet, self.key, answer)

    def test_bad_keys_and_source_evidence_joins_refuse_before_model_scoring(self):
        for mutate in (lambda p, k: k['judgments'].pop('SJ003'),
                       lambda p, k: k['judgments'].update(SJ003='unknown'),
                       lambda p, k: p['items'][0].update(admitted_evidence_ids=['nonexistent']),
                       lambda p, k: p['evidence'][0].update(source_ids=['nonexistent']),
                       lambda p, k: p['sources'][0].update(sha256='incorrect'),
                       lambda p, k: p['items'].append(copy.deepcopy(p['items'][0]))):
            p, k = copy.deepcopy(self.packet), copy.deepcopy(self.key)
            mutate(p, k)
            with self.assertRaises(ValueError):
                ss.score(p, k, None)

    def test_rationale_quality_is_explicitly_unscored(self):
        answer = copy.deepcopy(self.reference)
        for row in answer['decisions']:
            row['reason'] = 'Wrong explanation; this negative example exposes the unscored prose boundary.'
        counts, diagnostics = ss.score(self.packet, self.key, answer)
        self.assertEqual(counts['judgments']['tp'], 6)
        self.assertFalse(diagnostics['reason_quality_scored'])

    def test_projection_keeps_frozen_labels_multiple_sources_and_exact_time_scope(self):
        original = b.read_json(PACKET / 'review_key.json')
        expected = {row['id']: row['judgment'] for row in original['answers']}
        for family in ('mgpi', 'nist'):
            packet = b.read_json(PACKET / (family + '.input.json'))
            key = b.read_json(PACKET / (family + '.key.json'))
            self.assertEqual(key['judgments'], {item['id']: expected[item['id']] for item in packet['items']})
            self.assertTrue(all(item['claim_time_scope'] for item in packet['items']))
            ss.validate(packet, key)
        nist = b.read_json(PACKET / 'nist.input.json')
        self.assertEqual(len(next(e for e in nist['evidence'] if e['id'] == 'E06')['source_ids']), 2)
        self.assertEqual(len(next(e for e in nist['evidence'] if e['id'] == 'E09')['source_ids']), 3)
        projection = b.read_json(PACKET / 'KEY_PROVENANCE.json')
        for path, expected_hash in projection['public_projection_sha256_lf'].items():
            raw = (ROOT / path).read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_hash, path)

    def test_actual_benchmark_refuses_bad_data_and_retains_invalid_answer_as_failure(self):
        with tempfile.TemporaryDirectory(prefix='source-judgments-') as folder:
            root = Path(folder)
            def save(name, value):
                (root / name).write_bytes(b.encoded(value))
                return {'path': name, 'sha256': b.file_hash(root / name)}
            files = {'input': save('input.json', self.packet), 'key': save('key.json', self.key)}
            answer = copy.deepcopy(self.reference)
            answer['decisions'][0]['evidence_ids'] = ['E02']
            prediction = save('answer.json', answer)
            recipe = save('prompt.json', {'instructions': 'Synthetic control, no model trial'})
            run = {'id': 'control', 'ran_at': 'not-a-model-trial', 'interface': 'synthetic',
                   'method': 'source-review-control', 'provenance': 'synthetic evaluator control',
                   'model': {'provider': 'synthetic', 'id': 'control', 'version': '1'},
                   'configuration': {}, 'recipe': [recipe], 'cases': ['claims'],
                   'predictions': {'claims': prediction}}
            save('run.json', run)
            suite = {'id': 'test', 'version': '1', 'task': 'source-support', 'protocol': 'fixed claim labels',
                     'registration': 'synthetic software control', 'cases': [{
                         'id': 'claims', 'family': 'synthetic', 'split': 'synthetic-control',
                         'evidence': 'synthetic test', 'source_url': 'repository:test', 'license': 'test',
                         'key_author': 'test', 'files': files}], 'runs': ['run.json']}
            save('suite.json', suite)
            row = b.evaluate(root / 'suite.json', root)['results'][0]
            self.assertEqual(row['rows'][0]['status'], 'invalid-answer')
            self.assertEqual(row['rows'][0]['diagnostics']['expected_judgments'], 6)
            self.assertEqual(row['counts']['judgments']['tp'], 0)
            self.assertIn('decision evidence_ids', row['rows'][0]['note'])
            suite['cases'][0]['files']['key'] = save('key.json', {'judgments': {}})
            save('suite.json', suite)
            with self.assertRaisesRegex(ValueError, 'every exact claim'):
                b.evaluate(root / 'suite.json', root)


if __name__ == '__main__':
    unittest.main()
