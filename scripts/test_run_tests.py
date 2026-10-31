"""Stdlib runner controls: explicit scope, fail-closed prerequisites and exit status."""
import contextlib
import hashlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_te_data
import run_tests as runner
import verify_te_topology


class RunnerControls(unittest.TestCase):
    def fixture(self, root, cached=True):
        paths = runner.SOURCE_FILES + runner.TESTS + runner.FULL_FILES
        for relative in paths:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
        if cached:
            for name in fetch_te_data.FILES:
                path = root / 'data/external/te-braatz' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'cache fixture')
            path = root / 'data/external/te-ricker/temexd_mod.zip'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'cache fixture')

    def invoke(self, args, issues=(), returncode=0):
        output = io.StringIO()
        result = subprocess.CompletedProcess([], returncode, stdout='test result\n', stderr='failure details' if returncode else '')
        with patch.object(runner, 'prerequisites', return_value=issues), \
             patch.object(runner.subprocess, 'run', return_value=result) as run, \
             contextlib.redirect_stdout(output):
            status = runner.main(args)
        return status, output.getvalue(), run

    def test_missing_prerequisites_never_launch_tests(self):
        status, output, run = self.invoke([], [('cache', 'missing d00_te.dat'), ('dependency', 'missing asyncua')])
        self.assertEqual(status, 2)
        run.assert_not_called()
        self.assertIn('no test scripts ran', output)
        self.assertIn('NOT executed', output)
        self.assertIn('python scripts/fetch_te_data.py', output)
        self.assertIn('python -m pip install -r requirements.txt', output)
        self.assertNotIn('suite passed', output)

    def test_present_prerequisites_runs_all_without_skips(self):
        status, output, run = self.invoke([])
        self.assertEqual(status, 0)
        self.assertEqual([c.args[0][-1] for c in run.call_args_list], list(runner.TESTS))
        self.assertIn('FULL CACHED-DATA suite passed', output)
        self.assertNotIn('SKIP', output)
        self.assertEqual(len(set(runner.TESTS)), len(runner.TESTS))

    def test_platform_skips_are_surfaced_and_withhold_the_complete_pass(self):
        output = io.StringIO()
        result = subprocess.CompletedProcess([], 0, stdout='OK (skipped=1)\n',
                                             stderr='SKIP [platform] case: this Windows account cannot create symlinks\n')
        with patch.object(runner, 'prerequisites', return_value=[]), \
             patch.object(runner.subprocess, 'run', return_value=result), contextlib.redirect_stdout(output):
            self.assertEqual(runner.main([]), 0)
        text = output.getvalue()
        self.assertIn('SKIP (platform) case: this Windows account cannot create symlinks', text)
        self.assertIn(f'{len(runner.TESTS)} unittest case(s) skipped; {len(runner.TESTS)} platform notice(s)', text)
        self.assertIn('do not add them to the unittest case count', text)
        self.assertIn('not a complete pass here', text)
        self.assertNotIn('FULL CACHED-DATA suite passed', text)

    def test_unittest_skips_in_either_stream_withhold_complete_pass(self):
        for stdout, stderr in (('OK (skipped=9)\n', ''), ('ordinary test log\n', 'OK (skipped=9)\n')):
            with self.subTest(stdout=stdout):
                result = subprocess.CompletedProcess([], 0, stdout=stdout, stderr=stderr)
                with patch.object(runner, 'prerequisites', return_value=[]), \
                     patch.object(runner.subprocess, 'run', return_value=result), \
                     contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(runner.main([]), 0)
                self.assertIn(f'{9 * len(runner.TESTS)} unittest case(s) skipped; 0 platform notice(s)', output.getvalue())
                self.assertIn('not a complete pass here', output.getvalue())
                self.assertNotIn('FULL CACHED-DATA suite passed', output.getvalue())

    def test_skip_notices_do_not_classify_caches_as_platform_constraints(self):
        self.assertEqual(runner.coverage_notices('SKIP optional cache unavailable\n', 'OK\n'),
                         (0, [], ['optional cache unavailable']))
        self.assertEqual(runner.coverage_notices('SKIP [platform] simulated constraint\n', 'OK (skipped=1)\n'),
                         (1, ['simulated constraint'], []))
        self.assertEqual(runner.coverage_notices('Example: OK (skipped=9)\nordinary prose says skipped=8\n',
                                                 'OK (expected failures=2)\n'), (0, [], []))
        self.assertEqual(runner.coverage_notices('', 'FAILED (failures=1, errors=2, skipped=3)\n'), (3, [], []))

    def test_additional_skipped_check_withholds_complete_pass(self):
        result = subprocess.CompletedProcess([], 0, stdout='SKIP optional source unavailable\nOK\n', stderr='')
        with patch.object(runner, 'prerequisites', return_value=[]), \
             patch.object(runner.subprocess, 'run', return_value=result), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.main([]), 0)
        self.assertIn(f'{len(runner.TESTS)} additional skipped-check notice(s)', output.getvalue())
        self.assertIn('not a complete pass here', output.getvalue())
        self.assertNotIn('SKIP (platform)', output.getvalue())

    def test_public_example_executes_real_children_and_matches_declared_counts(self):
        result = subprocess.run([runner.sys.executable, '-S',
                                 str(runner.ROOT / 'examples/test-coverage/demonstrate.py'), '--check'],
                                capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('class_method_subtest_stdout', result.stdout)
        self.assertIn('failure_with_skip_stderr', result.stdout)

    def test_source_only_exclusions_and_label_are_explicit(self):
        status, output, run = self.invoke(['--source-only'])
        self.assertEqual(status, 0)
        self.assertEqual([c.args[0][-1] for c in run.call_args_list], list(runner.SOURCE_TESTS))
        self.assertTrue(all('-S' in c.args[0] for c in run.call_args_list))
        self.assertIn('NOT a full-suite pass', output)
        self.assertNotIn('FULL CACHED-DATA suite passed', output)
        for name in runner.FULL_ONLY_TESTS:
            self.assertIn(name, output)

    def test_capture_and_handoff_cohort_runs_offline_once(self):
        required = ('scripts/test_source_evidence.py', 'scripts/test_source_capture_mode.py',
                    'scripts/test_source_handoff.py')
        status, _, run = self.invoke(['--source-only'])
        self.assertEqual(status, 0)
        launched = [c.args[0][-1] for c in run.call_args_list]
        for name in required:
            self.assertEqual(launched.count(name), 1, name)
            self.assertNotIn(name, runner.FULL_ONLY_TESTS)

    def test_missing_handoff_seed_or_methods_prevents_child_execution(self):
        required = ('scripts/source_evidence.py', 'scripts/source_handoff.py', '.gitattributes', 'NOTICE.md',
                    *(f'examples/source-handoff/fixture/{name}' for name in
                      ('I01V01-VER.EX01.xml', 'embedded.model.json', 'PROVENANCE.json', 'EXPECTED.json')))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, cached=False)
            for name in required:
                with self.subTest(missing=name):
                    path = root / name
                    raw = path.read_bytes()
                    path.unlink()
                    with patch.object(runner, 'ROOT', root), \
                         patch.object(runner.subprocess, 'run', side_effect=AssertionError('child forbidden')), \
                         contextlib.redirect_stdout(io.StringIO()) as output:
                        self.assertEqual(runner.main(['--source-only']), 2)
                    self.assertIn('missing committed file: ' + name, output.getvalue())
                    self.assertIn('no test scripts ran', output.getvalue())
                    path.write_bytes(raw)

    def test_handoff_platform_subcheck_notice_withholds_complete_pass(self):
        result = subprocess.CompletedProcess([], 0, stdout='', stderr=(
            'test_PT08_filesystem_git_checkout_relocation ... \n'
            'SKIP [platform] PT08 escaping-symlink creation unavailable: WinError 1314\n'
            'ok\n\nOK\n'))
        with patch.object(runner, 'prerequisites', return_value=[]), \
             patch.object(runner.subprocess, 'run', return_value=result), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.main([]), 0)
        self.assertIn(f'0 unittest case(s) skipped; {len(runner.TESTS)} platform notice(s); '
                      '0 additional skipped-check notice(s)', output.getvalue())
        self.assertIn('not a complete pass here', output.getvalue())
        self.assertNotIn('FULL CACHED-DATA suite passed', output.getvalue())

    def test_test_failure_is_nonzero_in_both_modes(self):
        for args in ([], ['--source-only']):
            with self.subTest(args=args):
                status, output, _ = self.invoke(args, returncode=17)
                self.assertEqual(status, 1)
                self.assertIn('FAIL', output)
                self.assertIn('failure details', output)
                self.assertNotIn('suite passed', output)

    def test_execution_failure_does_not_report_pass(self):
        with patch.object(runner, 'prerequisites', return_value=[]), \
             patch.object(runner.subprocess, 'run', side_effect=OSError('cannot execute')), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.main([]), 1)
        self.assertIn('could not run', output.getvalue())

    def test_check_only_never_runs_tests_or_claims_suite_pass(self):
        status, output, run = self.invoke(['--check-prerequisites'])
        self.assertEqual(status, 0)
        run.assert_not_called()
        self.assertIn('tests NOT RUN', output)
        self.assertNotIn('suite passed', output)

    def test_local_checks_missing_present_and_corrupt(self):
        expected = hashlib.sha256(b'cache fixture').hexdigest()
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(fetch_te_data, 'FILES', {'d00_te.dat': expected, 'd06_te.dat': expected}), \
             patch.object(fetch_te_data, 'EVALUATION_FILES', {}), \
             patch.object(verify_te_topology, 'REVISED_SHA256', expected), \
             patch.object(runner.importlib.util, 'find_spec', return_value=object()), \
             patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')), \
             patch.object(runner.subprocess, 'run', side_effect=AssertionError('process forbidden')):
            root = Path(tmp)
            self.fixture(root, cached=False)
            issues = runner.prerequisites(root, False)
            self.assertEqual([kind for kind, _ in issues], ['cache', 'cache', 'source-cache'])
            self.assertTrue(any('d00_te.dat' in reason for _, reason in issues))
            self.assertTrue(any('d06_te.dat' in reason for _, reason in issues))
            self.fixture(root)
            self.assertEqual(runner.prerequisites(root, False), [])
            (root / 'data/external/te-braatz/d06_te.dat').write_bytes(b'corrupt')
            self.assertTrue(any('checksum mismatch' in reason for _, reason in runner.prerequisites(root, False)))
            with patch.object(runner.importlib.util, 'find_spec', return_value=None):
                kinds = [kind for kind, _ in runner.prerequisites(root, False)]
                self.assertEqual(kinds.count('dependency'), len(runner.DEPENDENCIES))

    def test_source_only_needs_no_cache_or_dependency_discovery(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(runner.importlib.util, 'find_spec', side_effect=AssertionError('dependency discovery forbidden')):
            root = Path(tmp)
            self.fixture(root, cached=False)
            self.assertEqual(runner.prerequisites(root, True), [])
            # Empty or partial committed scorer data cannot produce a zero-drawing green result.
            drawing = root / runner.DRAWINGS / '0.graphml'
            drawing.unlink()
            self.assertIn(('source', f'missing committed file: {runner.DRAWINGS}/0.graphml'), runner.prerequisites(root, True))
            drawing.write_bytes(b'')
            self.assertIn(('source', f'empty committed file: {runner.DRAWINGS}/0.graphml'), runner.prerequisites(root, True))


if __name__ == '__main__':
    unittest.main()
