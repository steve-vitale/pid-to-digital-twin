"""Offline workflow contract tests. All execute subprocesses are FAKE, never models."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

from platform_capabilities import symlink_or_skip

import site_extraction_workflow as workflow
from test_site_drawing_intake import png


class WorkflowControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'Drawing ü; $(do not run).png'
        self.image.write_bytes(png())
        self.job = self.root / 'job'
        workflow.prepare(self.image, 'UTIL-A', 'A', 2, self.job)
        self.record = {'tool': 'synthetic-contract-fixture', 'synthetic_contract_fixture': True,
                       'model': workflow.RECIPE['model'], 'image_sha256': workflow.intake.digest(png()),
                       'prompt_sha256': workflow.RECIPE['prompt_sha256'],
                       'prediction': {'symbols': [{'id': 'tank', 'class': 'tank', 'tag': None,
                       'confidence': None, 'box': [10, 20, 30, 40]}], 'connections': []}}
        self.record_path = self.root / 'receipt.json'
        self.save()
        self.out = self.root / 'review'

    def save(self):
        workflow.write_json(self.record_path, self.record)

    def collect(self, check=False):
        return workflow.collect(self.job, self.record_path, 'contract-fixture', self.out, check)

    def test_offline_modes_never_spawn_or_network(self):
        with (patch.object(subprocess, 'run', side_effect=AssertionError('no subprocess')),
              patch.object(urllib.request, 'urlopen', side_effect=AssertionError('no network'))):
            result = workflow.prepare(self.image, 'X', 'B', 1, self.root / 'checked', True)
            self.assertFalse(result['written'])
            self.assertFalse((self.root / 'checked').exists())
            workflow.prepare(self.image, 'X', 'B', 1, self.root / 'second')
            self.assertFalse(self.collect(True)['written'])
            self.assertFalse(self.out.exists())
            self.collect()
            receipt = workflow.read_json(self.out / 'extraction_handoff.json')
            self.assertTrue(receipt['synthetic_contract_fixture'])
            self.assertFalse(receipt['new_model_run'])
            model = workflow.read_json(self.out / 'plant_model.json')
            self.assertFalse(model['meta']['review_requirements']['operational_export_allowed'])
            self.assertIn('SYNTHETIC CONTRACT FIXTURE', (self.out / 'READ_ME.txt').read_text())

    def test_bad_receipts_do_not_publish(self):
        for field, value in [('model', None), ('image_sha256', 'wrong'), ('prompt_sha256', 'wrong'),
                             ('error', 'failed'), ('parse_error', 'bad'), ('exit_code', 1), ('exit_code', False),
                             ('tiling', {'grid': '2x2'}), ('synthetic_contract_fixture', False)]:
            original = copy.deepcopy(self.record)
            self.record[field] = value
            self.save()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.collect()
            self.assertFalse(self.out.exists())
            self.record = original
        self.record_path.write_text('{"tool": 1, "tool": 2}')
        with self.assertRaises(ValueError):
            self.collect()

    def test_changed_job_sources_rejected(self):
        for relative in ['source/0.png', 'source/prompt.md']:
            path = self.job / relative
            saved = path.read_bytes()
            path.write_bytes(saved + b'x')
            with self.assertRaises(ValueError):
                self.collect()
            path.write_bytes(saved)
        self.assertFalse(self.out.exists())

    def test_arbitrary_filename_and_revision_preserved(self):
        self.collect()
        receipt = workflow.read_json(self.out / 'extraction_handoff.json')
        self.assertEqual(receipt['job']['original_filename'], self.image.name)
        self.assertEqual(receipt['job']['drawing'], {'drawing_id': 'UTIL-A', 'revision': 'A', 'page': 2})
        self.assertEqual((self.out / 'source/0.png').read_bytes(), self.image.read_bytes())
        self.assertEqual((self.out / 'source/prepared-prompt.md').read_bytes(), (self.job / 'source/prompt.md').read_bytes())

    def test_recollect_never_overwrites_review_state(self):
        self.collect()
        marker = self.out / 'review_queue.csv'
        marker.write_text('reviewer decisions preserved')
        with self.assertRaises(ValueError):
            self.collect()
        self.assertEqual(marker.read_text(), 'reviewer decisions preserved')

    def test_symlink_outputs_rejected(self):
        symlink_or_skip(self, self.out, self.root / 'missing-target')
        with self.assertRaises(ValueError):
            self.collect()
        with self.assertRaises(ValueError):
            workflow.prepare(self.image, 'X', 'A', 1, self.out)

    def test_atomic_collection_failure(self):
        with patch.object(workflow.os, 'rename', side_effect=OSError('simulated rename failure')):
            with self.assertRaises(OSError):
                self.collect()
        self.assertFalse(self.out.exists())
        self.assertFalse(list(self.root.glob('.site-collect-*')))

    def fake_cli(self, command, **kwargs):
        self.assertIsInstance(command, list)
        self.assertNotIn('shell', kwargs)
        self.assertIn('--ignore-user-config', command)
        self.assertIn('read-only', command)
        self.assertIn('shell_tool', command)
        self.assertIn('unified_exec', command)
        self.assertIn('web_search="disabled"', command)
        self.assertEqual(command[command.index('-m') + 1], workflow.RECIPE['model'])
        self.assertEqual(kwargs['input'], (self.job / 'source/prompt.md').read_text())
        path = Path(command[command.index('-i') + 1])
        self.assertEqual(path.read_bytes(), png())
        Path(command[command.index('-o') + 1]).write_text(json.dumps(self.record['prediction']))
        return subprocess.CompletedProcess(command, 0, '', 'model: gpt-6.1-sol\nprovider: fake-contract-only\n')

    def test_fake_execute_then_collect_and_explicit_retry(self):
        with patch.object(subprocess, 'run', side_effect=self.fake_cli) as fake:
            workflow.execute(self.job)
            with self.assertRaises(ValueError):
                workflow.execute(self.job)
            self.assertEqual(fake.call_count, 1)
            workflow.execute(self.job, retry_of='attempt-0001')
            self.assertEqual(fake.call_count, 2)
        for name in ['attempt-0001', 'attempt-0002']:
            status = workflow.read_json(self.job / 'attempts' / name / 'status.json')
            self.assertEqual(status['state'], 'succeeded')
        workflow.collect(self.job, self.job / 'attempts/attempt-0001/0.json', 'cli-replay', self.out)
        receipt = workflow.read_json(self.out / 'extraction_handoff.json')
        self.assertEqual(receipt['execution']['provider'], 'fake-contract-only')

    def test_process_failures_retained_never_collected(self):
        for index, failure in enumerate([FileNotFoundError('codex not installed'),
                                        subprocess.TimeoutExpired('FAKE codex', 600),
                                        RuntimeError('unexpected failure')]):
            prior = None if index == 0 else f'attempt-{index:04d}'
            with patch.object(subprocess, 'run', side_effect=failure), self.assertRaises(ValueError):
                workflow.execute(self.job, retry_of=prior)
            status = workflow.read_json(self.job / f'attempts/attempt-{index + 1:04d}/status.json')
            self.assertEqual(status['state'], 'failed')
        self.assertFalse(self.out.exists())

    def test_partial_nonzero_output_rejected(self):
        def partial(*args, **kwargs):
            result = self.fake_cli(*args, **kwargs)
            result.returncode = 1
            return result
        with patch.object(subprocess, 'run', side_effect=partial), self.assertRaises(ValueError):
            workflow.execute(self.job)
        attempt = self.job / 'attempts/attempt-0001'
        self.assertTrue((attempt / '0.json').is_file())
        self.assertEqual(workflow.read_json(attempt / 'status.json')['state'], 'failed')
        with self.assertRaises(ValueError):
            workflow.collect(self.job, attempt / '0.json', 'cli-replay', self.out)

    def test_incomplete_attempt_is_not_success(self):
        with patch.object(subprocess, 'run', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            workflow.execute(self.job)
        attempt = self.job / 'attempts/attempt-0001'
        self.assertEqual(workflow.read_json(attempt / 'status.json')['state'], 'incomplete')
        fake = dict(self.record, tool='codex', exit_code=0, access_path='fake', synthetic_contract_fixture=False)
        workflow.write_json(attempt / '0.json', fake)
        with self.assertRaises(ValueError):
            workflow.collect(self.job, attempt / '0.json', 'cli-replay', self.out)

    def test_native_replay_requires_deviation(self):
        native = dict(self.record, tool='codex-native', access_path='native', reasoning_effort='unverified/inherited', synthetic_contract_fixture=False)
        _, job = workflow.load_job(self.job)
        with self.assertRaises(ValueError):
            workflow.validate_record(native, job, 'native-replay')
        native['recipe_deviation'] = 'Native wrapper differs; fixture only'
        workflow.validate_record(native, job, 'native-replay')

    def test_invalid_or_missing_cli_output_is_failed(self):
        for index, (raw, log) in enumerate([
                ('not JSON', 'model: gpt-6.1-sol\n'),
                (json.dumps(self.record['prediction']), 'provider: fake\n'),
                (None, 'model: gpt-6.1-sol\n'),
                ('{"symbols": [], "connections": []}', 'model: gpt-6.1-sol\n')]):
            def invalid(command, **kwargs):
                if raw is not None:
                    Path(command[command.index('-o') + 1]).write_text(raw)
                return subprocess.CompletedProcess(command, 0, '', log)
            prior = None if index == 0 else f'attempt-{index:04d}'
            with patch.object(subprocess, 'run', side_effect=invalid), self.assertRaises(ValueError):
                workflow.execute(self.job, retry_of=prior)
            status = workflow.read_json(self.job / f'attempts/attempt-{index + 1:04d}/status.json')
            self.assertEqual(status['state'], 'failed')

    def test_fixture_cannot_masquerade_as_native(self):
        native = dict(self.record, tool='codex-native', access_path='native',
                      reasoning_effort='unverified', recipe_deviation='wrapper difference')
        _, job = workflow.load_job(self.job)
        with self.assertRaises(ValueError):
            workflow.validate_record(native, job, 'native-replay')

    def test_stale_implementation_rejects_execute(self):
        with patch.object(workflow, 'code_hashes', return_value={'different': 'code'}), \
             patch.object(subprocess, 'run', side_effect=AssertionError('must not call')), self.assertRaises(ValueError):
            workflow.execute(self.job)
        self.assertFalse(list((self.job / 'attempts').iterdir()))


if __name__ == '__main__':
    unittest.main()
