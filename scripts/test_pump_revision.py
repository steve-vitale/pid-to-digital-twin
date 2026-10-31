"""Run a source-change journey and protect its evidence pins through actual Git filters. Stdlib only."""
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
EXAMPLE = ROOT / 'examples/pump-revision'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8')


def read(path):
    return json.loads(path.read_bytes())


def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


class PumpRevision(unittest.TestCase):
    def test_actual_revision_retains_history_and_limits_review_to_dependencies(self):
        before = hashes(EXAMPLE)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'journey'
            command = [sys.executable, '-S', str(EXAMPLE / 'reproduce.py'), '--out', str(out)]
            result = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            a = read(out / 'A/current/context.json')
            refreshed = read(out / 'B/refreshed/context.json')
            b = read(out / 'B/current/context.json')
            self.assertEqual(refreshed['decisions'], a['decisions'])
            self.assertEqual(refreshed['ownership_history'], a['ownership_history'])
            self.assertEqual(b['decisions'][:len(a['decisions'])], a['decisions'])
            self.assertEqual(b['ownership_history'][:len(a['ownership_history'])], a['ownership_history'])
            self.assertEqual(refreshed['current']['PUMP-NOTE@P-1']['answers'][0]['freshness'], 'stale')
            self.assertEqual(refreshed['current']['TANK-SERVICE@TK-1'], a['current']['TANK-SERVICE@TK-1'])
            self.assertEqual([d['value'] for d in b['decisions'] if d['answer_id'] == 'pump-note'], ['12 m', '12 kPa'])
            self.assertTrue(all(d['plant_truth'] == 'unknown' for d in b['decisions']))
            for relative in ('A/current', 'B/refreshed', 'B/current'):
                packet = out / relative
                graph = read(packet / 'enriched_graph.json')
                register = read(packet / 'context.json')
                self.assertEqual(graph_export.problems(graph), [])
                context_register.validate_export(graph, register)
                self.assertEqual(register['current']['E1@P-1']['state'], 'unanswered')
            # A new run must not replace either the evidence or a completed destination.
            completed = hashes(out)
            refused = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True, timeout=30)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(hashes(out), completed)
        self.assertEqual(hashes(EXAMPLE), before)

    def test_worked_evidence_survives_real_git_clean_and_checkout_filters(self):
        # This previously failed: normal Git text conversion changed source bytes and broke bound pairs.
        expected = {str(p.relative_to(EXAMPLE)).replace('\\', '/'): p.read_bytes()
                    for directory in ('inputs', 'worked') for p in (EXAMPLE / directory).rglob('*') if p.is_file()}
        self.assertTrue(expected)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for clean in ('true', 'false'):
                repo = tmp / ('clean-' + clean)
                repo.mkdir()
                shutil.copytree(EXAMPLE, repo / 'packet')
                def git(*args):
                    result = subprocess.run(['git', '-c', 'core.safecrlf=false', '-c', 'core.autocrlf=' + clean,
                                             *args], cwd=repo, capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result.stdout
                git('init', '--quiet')
                git('add', '--', 'packet')
                for name, original in expected.items():
                    self.assertEqual(git('show', ':packet/' + name), original, name)
                for checkout in ('true', 'false'):
                    dest = tmp / ('checkout-' + clean + '-' + checkout)
                    dest.mkdir()
                    prefix = str(dest).replace('\\', '/') + '/'
                    git('-c', 'core.autocrlf=' + checkout, 'checkout-index', '--all', '--force', '--prefix=' + prefix)
                    for name, original in expected.items():
                        self.assertEqual((dest / 'packet' / name).read_bytes(), original, name)
                    for relative in ('A/current', 'B/refreshed', 'B/current'):
                        packet = dest / 'packet/worked' / relative
                        graph = read(packet / 'enriched_graph.json')
                        self.assertEqual(graph_export.problems(graph), [])
                        context_register.validate_export(graph, read(packet / 'context.json'))


if __name__ == '__main__':
    unittest.main()
