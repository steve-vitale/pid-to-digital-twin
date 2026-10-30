"""Run illustrative real child programs through the repository test runner, offline and stdlib only."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import textwrap
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_tests as runner

# These counts describe the authored fixture programs, not production tests or a plant.
CASES = {
    'complete': (0, 0, 0, 0, '''
        import unittest
        print('Ordinary prose: a skipped action is not a test skip; example skipped=9.')
        class Checks(unittest.TestCase):
            def test_one(self): self.assertEqual(2 + 2, 4)
            def test_two(self): self.assertTrue(True)
        unittest.main()
    '''),
    'class_method_subtest_stdout': (0, 4, 0, 0, '''
        import sys
        import unittest
        @unittest.skip('ILLUSTRATIVE missing source cache')
        class AbsentSource(unittest.TestCase):
            def test_one(self): pass
            def test_two(self): pass
        class Checks(unittest.TestCase):
            @unittest.skip('ILLUSTRATIVE unavailable dependency')
            def test_method(self): pass
            def test_subcase(self):
                for value in (0, 1):
                    with self.subTest(value=value):
                        if value == 0: self.skipTest('ILLUSTRATIVE missing subcase input')
                        self.assertEqual(value, 1)
        unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
    '''),
    'platform_and_extra_notice': (0, 1, 1, 1, '''
        import sys
        import unittest
        print('SKIP illustrative extra check group unavailable')
        class Checks(unittest.TestCase):
            def test_simulated_platform_constraint(self):
                print('\\nSKIP [platform] illustrative simulated constraint', file=sys.stderr)
                self.skipTest('ILLUSTRATIVE simulated platform restriction, not an OS probe')
        unittest.main()
    '''),
    'failure_with_skip_stderr': (1, 1, 0, 0, '''
        import unittest
        class Checks(unittest.TestCase):
            def test_failure(self): self.fail('ILLUSTRATIVE failure control')
            @unittest.skip('ILLUSTRATIVE absent source')
            def test_skipped(self): pass
        unittest.main()
    '''),
}


def demonstrate():
    records = {}
    with tempfile.TemporaryDirectory(prefix='test-coverage-') as folder:
        base = Path(folder)
        for name, (exit_code, cases, platform, extra, source) in CASES.items():
            script = name + '.py'
            (base / script).write_text(textwrap.dedent(source), encoding='utf-8')
            output = io.StringIO()
            # Only scope selection and prereqs are replaced. subprocess.run executes the actual child program.
            with patch.object(runner, 'ROOT', base), patch.object(runner, 'TESTS', (script,)), \
                 patch.object(runner, 'prerequisites', return_value=[]), contextlib.redirect_stdout(output):
                actual = runner.main([])
            text = output.getvalue()
            expected_summary = (f'FULL CACHED-DATA: 1/1 scripts passed; 0 failed; ' if not exit_code else
                                'FULL CACHED-DATA: 0/1 scripts passed; 1 failed; ')
            expected_summary += (f'{cases} unittest case(s) skipped; {platform} platform notice(s); '
                                 f'{extra} additional skipped-check notice(s).')
            summary, = [line for line in text.splitlines() if line.startswith('FULL CACHED-DATA:')]
            assert actual == exit_code and summary == expected_summary, text
            complete = 'FULL CACHED-DATA suite passed.' in text
            assert complete == (exit_code == cases == platform == extra == 0), text
            records[name] = dict(exit=actual, summary=summary, complete_suite_claim=complete)
    return dict(schema='test-coverage-example-1',
                scope='Illustrative real child programs, not a repository-suite run or engineering approval',
                cases=records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='compare with the committed illustrative result')
    args = parser.parse_args()
    result = demonstrate()
    if args.check:
        expected = json.loads((HERE / 'expected.json').read_text(encoding='utf-8'))
        assert result == expected, 'current child results differ from committed illustrative evidence'
    print(json.dumps(result, indent=2))
