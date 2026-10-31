"""Actual-CLI controls for source preservation and native identity corrections (fictional development data)."""
import copy
import csv
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import generate


def model():
    return json.loads((ROOT / 'examples/review-and-mapping/native-identity/model.json').read_text(encoding='utf-8'))


class ReviewIdentity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='review-identity-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'model.json'
        self.save(model())

    def save(self, value):
        self.path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')

    def read(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def cli(self, script, *args, code=0):
        result = subprocess.run([sys.executable, '-S', str(ROOT / 'scripts' / script), *map(str, args)],
                                cwd=ROOT, capture_output=True, encoding='utf-8',
                                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def review(self, rows, code=0, dry=False):
        sheet = self.root / 'review.csv'
        fields = ['item_id', 'OPS_confirm_or_correct', 'OPS_correct_value', 'OPS_notes', 'OPS_alarm_priority_H_M_L_none']
        with sheet.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        result = self.cli('apply_review.py', self.path, sheet, '--reviewer', 'Fictional test reviewer',
                          '--date', '2026-10-30', '--record-dir', self.root / 'receipts',
                          *(['--dry-run'] if dry else []), code=code)
        chosen = re.search(r'^Record: (.+)$', result.stdout, re.M)
        record = self.root / 'receipts' / (chosen.group(1) if chosen else 'no-record.json')
        return result, json.loads(record.read_text(encoding='utf-8')) if record.exists() else None

    def correction(self, ident='PT-900', value='tag=PT-902'):
        return {'item_id': ident, 'OPS_confirm_or_correct': 'correct', 'OPS_correct_value': value}

    def graph(self, name):
        p = self.root / (name + '.json')
        self.cli('graph_export.py', self.path, '--out', p)
        return json.loads(p.read_text(encoding='utf-8'))

    def test_native_rename_preserves_graph_screen_and_source(self):
        before = self.read()
        graph = self.graph('before')
        self.cli('question_engine.py', '--model', self.path, '--question', 'C2', '--out', self.root / 'before-screen')
        rows = [self.correction(), self.correction('PV-900', 'tag=PV-902')]
        _, log = self.review(rows)
        after = self.read()
        new_graph = self.graph('after')
        names = {'PT-900': 'PT-902', 'PV-900': 'PV-902'}
        edge = lambda e: (e['type'], e['from'], e['to'])
        self.assertEqual([(t, names.get(a, a), names.get(b, b)) for t, a, b in map(edge, graph['edges'])],
                         list(map(edge, new_graph['edges'])))
        self.cli('question_engine.py', '--model', self.path, '--question', 'C2', '--out', self.root / 'after-screen')
        findings = lambda p: json.loads((self.root / p / 'questions.json').read_text(encoding='utf-8'))['questions']
        self.assertEqual(findings('before-screen'), findings('after-screen'))
        for group in ('instruments', 'final_elements'):
            for original, revised in zip(before[group], after[group]):
                revised = copy.deepcopy(revised)
                revised.pop('ops_review', None)
                revised['tag'] = original['tag']
                self.assertEqual(original, revised)
        refs = [r for a in log['applied'] for r in a.get('reference_changes', [])]
        self.assertEqual({r['path'] for r in refs}, {
            'controllers[0].measurement', 'controllers[1].measurement', 'interlocks[0].measurement',
            'limits[0].tag', 'line_layers.networks[0].members[0]', 'line_layers.instrument_lines[0].from',
            'controllers[0].output.final_element', 'controllers[1].output.split_range[0]',
            'interlocks[0].final_element', 'limits[1].tag', 'line_layers.networks[0].members[1]',
            'line_layers.segments[0].to', 'line_layers.actuator_stems[0].from'})
        self.assertEqual(after['instruments'][0]['ops_review']['history'][-1]['reference_changes'],
                         log['applied'][0]['reference_changes'])
        self.assertIn('external_companions', log['applied'][0]['identity_change'])
        self.assertEqual(after['controllers'][0]['source'], before['controllers'][0]['source'])

    def test_alarm_metadata_is_opaque_and_neighbours_unchanged(self):
        for value in (None, [], [0], [123, 456], {'value': 0, 'status': 'estimated'}, 'unknown', False):
            with self.subTest(value=value):
                source = model()
                source['instruments'][0]['alarm_setpoints'] = value
                source['final_elements'][0]['alarm_setpoints'] = copy.deepcopy(value)
                self.save(source)
                self.review([{'item_id': 'TT-900', 'OPS_confirm_or_correct': 'confirm'}])
                changed = self.read()
                self.assertEqual(changed['instruments'][0], source['instruments'][0])
                self.assertEqual(changed['final_elements'], source['final_elements'])

    def test_foreign_te_tag_does_not_borrow_te_alarm(self):
        source = model()
        source['instruments'][1]['tag'] = 'PT-107'
        source['instruments'][1].pop('alarm_setpoints', None)
        self.save(source)
        _, record = self.review([{'item_id': 'PT-107', 'OPS_alarm_priority_H_M_L_none': 'H'}])
        self.assertEqual(len(record['needs_moc']), 1)
        self.assertNotIn('alarm_setpoints', self.read()['instruments'][1])

    def test_unknown_alarm_basis_stays_unresolved_including_none_requests(self):
        for value in (None, [], False, 0, 'unknown', {'status': 'unreadable'}, [None]):
            for priority in ('H', 'none'):
                with self.subTest(value=value, priority=priority):
                    source = model()
                    source['instruments'][0]['alarm_setpoints'] = value
                    self.save(source)
                    _, record = self.review([{'item_id': 'PT-900', 'OPS_alarm_priority_H_M_L_none': priority}])
                    self.assertEqual(record['applied'][0]['alarm_basis'], 'unresolved')
                    self.assertEqual(len(record['needs_moc']), 1)
                    self.assertIn('does not establish which alarms exist', record['needs_moc'][0]['why'])
                    self.assertEqual(self.read()['instruments'][0]['alarm_setpoints'], value)

    def test_explicit_supplied_metadata_precedes_te_reference(self):
        source = json.loads((ROOT / 'data/te_process_model.json').read_text(encoding='utf-8'))
        for values, expected in ((None, 'unresolved'), ([0], 'supplied-setpoints')):
            item = next(it for it in source['instruments'] if it['tag'] == 'PT-107')
            item['alarm_setpoints'] = values
            self.save(source)
            _, record = self.review([{'item_id': 'PT-107', 'OPS_alarm_priority_H_M_L_none': 'none'}])
            self.assertEqual(record['applied'][0]['alarm_basis'], expected)
            self.assertEqual(next(it for it in self.read()['instruments'] if it['tag'] == 'PT-107')['alarm_setpoints'], values)

    def test_auxiliary_id_and_generated_tag_sheet_roundtrip(self):
        self.review([{'item_id': 'pressure-record', 'OPS_confirm_or_correct': 'confirm'}])
        rows = [dict(zip(generate.REVIEW_COLS, row)) for row in generate.review_rows(self.read())]
        self.assertIn('PT-900', [row['item_id'] for row in rows])
        for row in rows:
            for key in list(row):
                if key not in ('item_id', 'OPS_confirm_or_correct', 'OPS_correct_value', 'OPS_notes', 'OPS_alarm_priority_H_M_L_none'):
                    del row[key]
        _, record = self.review(rows)
        self.assertEqual(record['applied'], [])
        self.assertEqual(record['refused'], [])

    def test_same_and_regenerated_sheet_replay_and_two_renames(self):
        rows = [self.correction()]
        self.review(rows)
        before = self.path.read_bytes()
        _, record = self.review(rows)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(record['unchanged'], 1)
        self.review([self.correction('PT-902', 'tag=PT-903')])
        latest = self.path.read_bytes()
        self.review(rows, code=1)
        self.assertEqual(latest, self.path.read_bytes())
        item = self.read()['instruments'][0]
        self.assertEqual(item['former_tag'], 'Original-PT-900')
        self.assertEqual([h['changes']['tag'] for h in item['ops_review']['history']],
                         [['PT-900', 'PT-902'], ['PT-902', 'PT-903']])
        graph = self.graph('twice')
        self.assertTrue({'PT-900', 'PT-902'}.issubset(next(n for n in graph['nodes'] if n['id'] == 'PT-903')['aliases']))

    def test_collision_reserved_and_chain_refusal_preserve_model(self):
        for tag in ('PV-900', 'PIC-900', 'T-1', 'N1', 'J1', 'L1', 'PLANT', 'BL', 'stream:new', 'tt-900'):
            with self.subTest(tag=tag):
                self.save(model())
                before = self.path.read_bytes()
                _, record = self.review([self.correction(value='tag=' + tag)], code=1)
                self.assertEqual(before, self.path.read_bytes())
                self.assertTrue(record['refused'])
        self.save(model())
        before = self.path.read_bytes()
        self.review([self.correction(value='tag=TT-900'), self.correction('TT-900', 'tag=TT-902')], code=1)
        # The independent ordinary rename may succeed; the colliding first row must not touch its references.
        after = self.read()
        self.assertEqual(after['instruments'][0]['tag'], 'PT-900')
        self.assertEqual(after['controllers'][0]['measurement'], 'PT-900')

    def test_conflicting_rows_and_duplicate_destinations_refuse(self):
        for rows in ([self.correction(), self.correction(value='tag=PT-903')],
                     [self.correction(), self.correction('TT-900', 'tag=PT-902')]):
            self.save(model())
            before = self.path.read_bytes()
            self.review(rows, code=1)
            self.assertEqual(before, self.path.read_bytes())

    def test_contradictory_metadata_and_repeated_cell_fields_refuse(self):
        for rows in ([self.correction(), {'item_id': 'PT-900', 'OPS_confirm_or_correct': 'reject'}],
                     [{**self.correction(), 'OPS_notes': 'first'}, {**self.correction(), 'OPS_notes': 'second'}],
                     [self.correction(value='tag=PT-902;tag=PT-903')]):
            self.save(model())
            before = self.path.read_bytes()
            self.review(rows, code=1)
            self.assertEqual(before, self.path.read_bytes())

    def test_receipts_survive_replay_and_later_decisions(self):
        rows = [self.correction()]
        self.review(rows)
        first = {p.name: p.read_bytes() for p in (self.root / 'receipts').iterdir()}
        self.review(rows)
        replay = {p.name: p.read_bytes() for p in (self.root / 'receipts').iterdir()}
        self.assertTrue(all(replay[name] == value for name, value in first.items()))
        self.assertEqual(len(replay), 4)
        self.review(rows)
        self.assertEqual(replay, {p.name: p.read_bytes() for p in (self.root / 'receipts').iterdir()})
        self.review([self.correction('PT-902', 'tag=PT-903')])
        latest = {p.name: p.read_bytes() for p in (self.root / 'receipts').iterdir()}
        self.assertTrue(all(latest[name] == value for name, value in replay.items()))
        self.assertEqual(len(latest), 6)

    def test_duplicate_json_keys_refuse_before_mutation(self):
        self.path.write_text('{"meta":{},"units":[],"units":[]}', encoding='utf-8')
        before = self.path.read_bytes()
        self.review([self.correction()], code=2)
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse((self.root / 'receipts').exists())

    def test_ambiguous_csv_headers_and_overflow_refuse_before_writes(self):
        for content in ('item_id,item_id,OPS_confirm_or_correct\nPT-900,TT-900,reject\n',
                        'item_id,OPS_confirm_or_correct\nPT-900,reject,TT-900\n'):
            sheet = self.root / 'ambiguous.csv'
            sheet.write_text(content, encoding='utf-8')
            before = self.path.read_bytes()
            self.cli('apply_review.py', self.path, sheet, '--reviewer', 'Fictional',
                     '--record-dir', self.root / 'receipts', code=2)
            self.assertEqual(before, self.path.read_bytes())
            self.assertFalse((self.root / 'receipts').exists())

    def test_duplicate_original_and_auxiliary_identities_refuse_before_records(self):
        for mode in ('tag', 'id', 'controller'):
            source = model()
            if mode == 'tag':
                source['instruments'][1]['tag'] = 'PT-900'
            elif mode == 'id':
                source['instruments'][1]['id'] = 'pressure-record'
            else:
                source['controllers'][0]['tag'] = 'PT-900'
            self.save(source)
            before = self.path.read_bytes()
            self.review([self.correction()], code=2)
            self.assertEqual(before, self.path.read_bytes())
            self.assertFalse((self.root / 'receipts').exists())

    def test_new_name_cannot_retarget_later_sheet_row(self):
        _, record = self.review([self.correction(), {'item_id': 'PT-902', 'OPS_confirm_or_correct': 'reject'}], code=1)
        self.assertEqual(len(record['refused']), 1)
        self.assertEqual(self.read()['instruments'][0]['ops_review']['status'], 'corrected')

    def test_unplaced_refs_preserved_in_role_and_order(self):
        source = model()
        source['controllers'][0]['measurement_unplaced'] = ['TT-900', 'PT-900', 'PT-900']
        source['controllers'][0]['output_unplaced'] = ['PV-901', 'PV-900']
        self.save(source)
        self.review([self.correction(), self.correction('PV-900', 'tag=PV-902')])
        self.assertEqual(self.read()['controllers'][0]['measurement_unplaced'], ['TT-900', 'PT-902', 'PT-902'])
        self.assertEqual(self.read()['controllers'][0]['output_unplaced'], ['PV-901', 'PV-902'])

    def test_malformed_reference_refuses_entire_rename_row(self):
        source = model()
        source['controllers'][0]['measurement'] = {'unsupported': 'PT-900'}
        self.save(source)
        before = self.path.read_bytes()
        self.review([self.correction()], code=1)
        self.assertEqual(before, self.path.read_bytes())

    def test_dry_run_preserves_every_input_and_creates_no_receipt(self):
        before = self.path.read_bytes()
        result, _ = self.review([self.correction()], dry=True)
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse((self.root / 'receipts').exists())
        self.assertIn('controllers[0].measurement', result.stdout)

    def test_native_staging_regenerates_with_current_identity(self):
        self.review([self.correction()])
        self.cli('generate.py', self.path, '--out', self.root / 'generated')
        tags = (self.root / 'generated/ignition/tags.json').read_text(encoding='utf-8')
        self.assertIn('.PT-902', tags)
        self.assertIn('PT-902', (self.root / 'generated/ops_review_sheet.csv').read_text(encoding='utf-8-sig'))
        self.assertEqual(self.read()['instruments'][0]['provenance'][0]['tag_as_extracted'], 'PT-900')

    def test_public_example_reproduces_complete_model_and_record(self):
        example = ROOT / 'examples/review-and-mapping/native-identity'
        self.assertEqual({p.relative_to(example).as_posix() for p in example.rglob('*') if p.is_file()}, {
            'README.md', 'model.json', 'review.csv', 'expected/model.json',
            'expected/change_record.json', 'expected/change_record.md'})
        result = self.cli('apply_review.py', self.path, example / 'review.csv',
                          '--reviewer', 'Fictional example reviewer', '--date', '2026-10-30',
                          '--record-dir', self.root / 'receipts')
        self.assertEqual(self.path.read_bytes(), (example / 'expected/model.json').read_bytes().replace(b'\r\n', b'\n'))
        name = re.search(r'^Record: (.+)$', result.stdout, re.M).group(1)
        actual = json.loads((self.root / 'receipts' / name).read_text(encoding='utf-8'))
        expected = json.loads((example / 'expected/change_record.json').read_text(encoding='utf-8'))
        original_location = expected['model']
        expected['model'] = actual['model']  # Working-copy location is the only variable record field.
        self.assertEqual(expected, actual)
        markdown = (example / 'expected/change_record.md').read_text(encoding='utf-8')
        self.assertEqual(markdown.replace(original_location, actual['model'], 1),
                         (self.root / 'receipts' / name).with_suffix('.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
