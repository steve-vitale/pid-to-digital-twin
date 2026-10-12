"""Synthetic validator fixtures only. No measured people, timings or improvements."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import review_effort as re


def fixture():
    p = re.template()
    for k, v in p.items():
        if v == '':
            p[k] = 'SYNTHETIC TEST PLACEHOLDER'
    p.update(synthetic=True, frozen_at='2026-01-01T00:00:00Z',
             tasks=[{'task_id': 'test-task', 'source_bundle_sha256': 'a' * 64, 'truth_reference': 'test-key'}],
             assignments=[{'assignment_id': arm, 'task_id': 'test-task', 'arm': arm,
                           'reviewer_id': 'test-' + arm, 'period': 1} for arm in re.ARMS])
    records = [{'assignment_id': arm, 'protocol_sha256': re.digest(p), 'source_bundle_sha256': 'a' * 64,
                'evidence_kind': 'synthetic', 'status': 'complete', 'preparation_minutes': 0, 'review_minutes': 0,
                'residual_critical_errors': 0, 'audit': {'reviewer_id': 'test-auditor', 'truth_reference': 'test-key',
                'artifact_reference': 'test-artifact', 'evidence_reference': 'test-audit'}} for arm in re.ARMS]
    return p, records


class Tests(unittest.TestCase):
    def test_valid_zero_is_observed(self):
        p, r = fixture()
        out = re.summarize(p, r)
        self.assertEqual(out['arms']['baseline']['review_minutes']['median'], 0)
        self.assertEqual(len(out['complete_task_pairs']), 1)
        self.assertIn('SYNTHETIC', out['evidence_label'])

    def test_missing_is_not_zero(self):
        p, _ = fixture()
        out = re.summarize(p, [])
        self.assertEqual(out['arms']['baseline']['statuses']['missing'], 1)
        self.assertIsNone(out['arms']['baseline']['review_minutes']['sum'])
        self.assertEqual(out['incomplete_task_pairs'], 1)

    def test_failed_and_abstained_keep_denominator(self):
        p, records = fixture()
        for r, status in zip(records, ('failed', 'abstained')):
            r.update(status=status, reason='synthetic failure', preparation_minutes=3, review_minutes=None,
                     residual_critical_errors=None)
        out = re.summarize(p, records)
        self.assertEqual(out['arms']['baseline']['assigned'], 1)
        self.assertEqual(out['arms']['ai_assisted']['statuses']['abstained'], 1)
        self.assertEqual(out['complete_task_pairs'], [])
        self.assertIsNone(out['assignments'][0]['total_labor_minutes'])

    def test_nonfinite_negative_boolean_or_string_times_rejected(self):
        for bad in (-1, float('nan'), float('inf'), True, '1'):
            p, r = fixture()
            r[0]['review_minutes'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                re.summarize(p, r)

    def test_critical_count_needs_truth_independence_and_evidence(self):
        for change in ({'reviewer_id': 'test-baseline'}, {'truth_reference': 'wrong'},
                       {'evidence_reference': ''}, {'artifact_reference': ''}):
            p, r = fixture()
            r[0]['audit'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                re.summarize(p, r)

    def test_complete_cannot_hide_missing_quality_or_time(self):
        for field in ('review_minutes', 'preparation_minutes', 'residual_critical_errors'):
            p, r = fixture()
            r[0][field] = None
            with self.subTest(field=field), self.assertRaises(ValueError):
                re.summarize(p, r)

    def test_hash_mismatch_rejected(self):
        for field in ('source_bundle_sha256', 'protocol_sha256'):
            p, r = fixture()
            r[0][field] = 'b' * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                re.summarize(p, r)

    def test_no_duplicate_unknown_or_synthetic_mixed_records(self):
        p, r = fixture()
        with self.assertRaises(ValueError):
            re.summarize(p, r + [r[0]])
        r[0]['assignment_id'] = 'unregistered'
        with self.assertRaises(ValueError):
            re.summarize(p, r)
        p, r = fixture()
        r[0]['evidence_kind'] = 'human_observation'
        with self.assertRaises(ValueError):
            re.summarize(p, r)

    def test_same_task_crossover_and_missing_arm_rejected(self):
        p, _ = fixture()
        p['assignments'][1]['reviewer_id'] = p['assignments'][0]['reviewer_id']
        with self.assertRaises(ValueError):
            re.validate_protocol(p)
        p, _ = fixture()
        p['assignments'].pop()
        with self.assertRaises(ValueError):
            re.validate_protocol(p)

    def test_blank_template_not_a_frozen_protocol(self):
        with self.assertRaises(ValueError):
            re.validate_protocol(re.template())

    def test_deltas_direction_and_total_labor(self):
        p, r = fixture()
        r[0].update(preparation_minutes=5, review_minutes=3, residual_critical_errors=1)
        r[1].update(preparation_minutes=8, review_minutes=2, residual_critical_errors=2)
        pair = re.summarize(p, r)['complete_task_pairs'][0]
        self.assertEqual(pair['review_minutes_ai_minus_baseline'], -1)
        self.assertEqual(pair['total_labor_minutes_ai_minus_baseline'], 2)
        self.assertEqual(pair['residual_critical_errors_ai_minus_baseline'], 1)

    def test_strict_json_rejects_duplicate_keys_and_constants(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'bad.json'
            for raw in ('{"x": 1, "x": 2}', '{"nested": {"x": 1, "x": 2}}', '[NaN]', '[Infinity]'):
                path.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    re.read_json(path)

    def test_malformed_ids_rejected(self):
        for bad in ([], {}, None, 3):
            p, r = fixture()
            r[0]['assignment_id'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                re.summarize(p, r)
            p['assignments'][0]['task_id'] = bad
            with self.assertRaises(ValueError):
                re.validate_protocol(p)

    def test_cli_valid_and_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p, r = fixture()
            pp, rp = Path(d) / 'protocol.json', Path(d) / 'records.json'
            pp.write_text(json.dumps(p)); rp.write_text(json.dumps(r))
            command = [sys.executable, '-S', str(Path(re.__file__)), 'report', str(pp), str(rp)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('SYNTHETIC', json.loads(result.stdout)['evidence_label'])
            rp.write_text('{')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(result.stdout)


if __name__ == '__main__':
    unittest.main()
