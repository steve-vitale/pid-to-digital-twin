"""Exercise the committed current review packet through the actual offline CLI.

The filled CSV is explicitly fictional. These controls establish binding and preservation,
not drawing accuracy, authenticated engineering approval or plant truth.
"""
import copy
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import graph_export
import statements

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'examples/statement-review/bound-sheet0'
GRAPH = ROOT / 'examples/graph-export/sheet0_graph.json'
IMAGE = ROOT / 'data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100/0.png'
REVIEW = PACKET / 'illustrative_review.csv'


def invoke(graph, image, output, sheet=REVIEW):
    return subprocess.run([sys.executable, '-S', str(ROOT / 'scripts/statements.py'), 'apply', str(graph),
        str(sheet), '--image', f'0={image}', '--date', '2026-10-30', '--out', str(output)],
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, capture_output=True, encoding='utf-8', timeout=30)


class BoundPublicExample(unittest.TestCase):
    def test_prior_worksheet_is_retained_and_refuses_the_expanded_graph(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'must-not-exist.json'
            run = invoke(GRAPH, IMAGE, output, PACKET / 'illustrative_review-before-appearances.csv')
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            self.assertIn('stale review fingerprint', run.stdout + run.stderr)
            self.assertFalse(output.exists())
    def test_sample_binds_the_current_graph_and_actual_public_original(self):
        graph = json.loads(GRAPH.read_text(encoding='utf-8'))
        packet = json.loads((PACKET / 'sample.json').read_text(encoding='utf-8'))
        basis, _, _, _ = statements.review_packet(graph, {'0': IMAGE})
        self.assertEqual(packet['review_basis'], basis)
        self.assertEqual(basis['coverage'], 'supplied-original-files')
        self.assertEqual(packet['n'], 12)
        self.assertEqual(packet['seed'], 1032)
        current, _, _ = statements.build(graph)
        by_id = {row['id']: row for row in current}
        for row in packet['statements']:
            self.assertEqual(row['review_fingerprint'], statements.review_fingerprint(by_id[row['id']], basis))
        blank = statements.read_sheet(PACKET / 'sample.csv', strict=True)
        self.assertEqual(len(blank), 12)
        self.assertTrue(all(not row['source_match'] and not row['plant_truth'] for row in blank))
        html = (PACKET / 'sample.html').read_text(encoding='utf-8')
        for row in blank:
            self.assertIn(row['review_fingerprint'], html)

    def test_cli_application_matches_receipt_and_preserves_values_and_note(self):
        before = {p: p.read_bytes() for p in (GRAPH, IMAGE, REVIEW)}
        expected = json.loads((PACKET / 'apply_summary.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'reviewed.json'
            run = invoke(GRAPH, IMAGE, output)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('1 verdict(s) applied, 0 refused', run.stdout)
            reviewed = json.loads(output.read_text(encoding='utf-8'))
        original = json.loads(before[GRAPH])
        self.assertEqual(graph_export.problems(reviewed), [])
        self.assertEqual(statements.canonical_hash(reviewed), expected['output_graph_canonical_sha256'])
        self.assertEqual(len(reviewed['events']) - len(original.get('events', [])), 1)
        event = reviewed['events'][-1]
        self.assertEqual(event['source_match'], 'unclear')
        self.assertIsNone(event['plant_truth'])
        with REVIEW.open(encoding='utf-8', newline='') as stream:
            first = next(csv.DictReader(stream))
        self.assertEqual(event['note'], first['note'])
        self.assertEqual(event['review_fingerprint'], first['review_fingerprint'])
        self.assertEqual(event['review_basis'], expected['review_basis'])
        # Strip only the newly appended checks; every engineering value and status must match the input.
        stripped = copy.deepcopy(reviewed)
        for collection in ('nodes', 'edges'):
            for old, new in zip(original[collection], stripped[collection]):
                for old_obj, new_obj in [(old, new), *zip(old.get('attributes', []), new.get('attributes', []))]:
                    if len(new_obj.get('checks', [])) > len(old_obj.get('checks', [])):
                        self.assertEqual(new_obj['checks'][-1]['note'], first['note'])
                        if 'checks' in old_obj:
                            new_obj['checks'] = old_obj['checks']
                        else:
                            del new_obj['checks']
        stripped['events'] = original.get('events', [])
        if 'events' not in original:
            del stripped['events']
        stripped['counts']['events'] = original['counts']['events']
        self.assertEqual(stripped, original)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_source_revision_and_graph_change_refuse_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / 'changed.png'
            image.write_bytes(IMAGE.read_bytes() + b'\nsynthetic revision control only\n')
            output = root / 'must-not-exist.json'
            run = invoke(GRAPH, image, output)
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            self.assertFalse(output.exists())
            changed = json.loads(GRAPH.read_text(encoding='utf-8'))
            changed['title'] = str(changed.get('title', '')) + ' (synthetic snapshot change)'
            graph = root / 'changed.json'
            graph.write_text(json.dumps(changed), encoding='utf-8')
            run = invoke(graph, IMAGE, output)
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
