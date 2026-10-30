"""Offline point-mapping safety regressions: python scripts/test_map_points.py."""
import contextlib
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import map_points


def instrument(key, tag, sheet='0', point=None, **extra):
    item = {'id': key, 'tag': tag, 'provenance': [{'sheet': sheet}], **extra}
    if point is not None:
        item['data_point'] = {'server': 'old', 'base_path': 'old-path', 'point': point}
    return item


def row(tag='FT-1', asset_id='', point='new'):
    return {'tag': tag, 'asset_id': asset_id, 'server': ' OPC ', 'base_path': ' ns=1;s=plant ', 'point': point}


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.model = {'instruments': [instrument('a', 'FT-1', point='a-old'),
                                      instrument('b', 'PT-2', point='b-old'),
                                      instrument('c', 'TT-3', 1, 'c-old')]}
        self.before = copy.deepcopy(self.model)

    def plan(self, rows, **kwargs):
        result = map_points.plan_mapping(self.model, rows, 'io.csv', **kwargs)
        self.assertEqual(self.model, self.before, 'planning must never mutate its input')
        return result

    def test_partial_preserves_other_sheets_and_omitted_targets(self):
        updated, report = self.plan([row('ft_1')], scope={'0'})
        self.assertTrue(report['valid'])
        self.assertEqual(updated['instruments'][1:], self.before['instruments'][1:])
        self.assertEqual(report['mapped'][0]['how'], 'normalized tag')
        self.assertEqual(report['mapping_changes'][0]['before']['point'], 'a-old')
        self.assertEqual(report['mapping_changes'][0]['after']['point'], 'new')
        self.assertEqual(set(report['mappings_before']), {'a', 'b', 'c'})
        self.assertEqual(set(report['mappings_after']), {'a', 'b', 'c'})
        self.assertEqual(updated['instruments'][0]['data_point']['server'], 'OPC')

    def test_explicit_unknown_or_rejected_id_never_falls_back(self):
        self.model['instruments'].append(instrument('rejected', 'XX-4', point='keep', ops_review={'status': 'rejected'}))
        self.before = copy.deepcopy(self.model)
        for pin in ('typo', 'rejected'):
            with self.subTest(pin=pin):
                self.model = copy.deepcopy(self.before)
                updated, report = self.plan([row(asset_id=pin)])
                self.assertFalse(report['valid'])
                self.assertEqual(updated, self.model)
                self.assertIn('no tag fallback', report['errors'][0]['reason'])
                self.assertEqual(report['mapping_changes'], [])

    def test_duplicate_rows_reject_entire_transaction(self):
        for second in (row(), row(point='conflict'), row('different-tag', 'a')):
            with self.subTest(second=second):
                updated, report = self.plan([row(), second, row('TT-3')], replace_all=True)
                self.assertFalse(report['valid'])
                self.assertEqual(updated, self.before)
                self.assertEqual(report['mappings_before'], report['mappings_after'])
                self.assertIn('duplicate target', report['errors'][0]['reason'])

    def test_scope_blocks_assignments_outside_scope_and_unknown_sheet(self):
        for scope, rows in (({'0'}, [row('TT-3')]), ({'typo'}, [row()])):
            with self.subTest(scope=scope):
                updated, report = self.plan(rows, scope=scope, replace_all=True)
                self.assertFalse(report['valid'])
                self.assertEqual(updated, self.before)

    def test_explicit_replacement_removes_only_scoped_mappings(self):
        updated, report = self.plan([row()], scope={'0'}, replace_all=True)
        self.assertTrue(report['valid'])
        self.assertNotIn('data_point', updated['instruments'][1])
        self.assertEqual(updated['instruments'][2], self.before['instruments'][2])
        self.assertEqual([(c['asset'], c['kind']) for c in report['mapping_changes']], [('a', 'changed'), ('b', 'removed')])
        self.assertEqual(report['mapping_changes'][1]['before']['point'], 'b-old')
        self.assertIsNone(report['mapping_changes'][1]['after'])

    def test_empty_partial_is_noop_empty_explicit_replacement_clears_scope(self):
        updated, report = self.plan([])
        self.assertEqual(updated, self.before)
        self.assertEqual(report['mapping_changes'], [])
        updated, report = self.plan([], scope={'1'}, replace_all=True)
        self.assertEqual([c['asset'] for c in report['mapping_changes']], ['c'])
        self.assertEqual(updated['instruments'][:2], self.before['instruments'][:2])

    def test_duplicate_tag_ambiguity_requires_pin(self):
        self.model['instruments'].append(instrument('d', 'FT 1', '0', 'd-old'))
        self.before = copy.deepcopy(self.model)
        updated, report = self.plan([row()])
        self.assertEqual(updated, self.before)
        self.assertEqual(report['ambiguous'][0]['assets'], ['a', 'd'])
        self.assertEqual(report['mapped'], [])
        updated, report = self.plan([row(asset_id='a')])
        self.assertTrue(report['valid'])
        self.assertEqual(updated['instruments'][-1], self.before['instruments'][-1])
        self.assertEqual(report['mapped'][0]['how'], 'asset_id')

    def test_sheet_scope_does_not_guess_between_global_tag_duplicates(self):
        self.model['instruments'].append(instrument('d', 'FT 1', '1', 'd-old'))
        self.before = copy.deepcopy(self.model)
        updated, report = self.plan([row()], scope={'0'})
        self.assertEqual(updated, self.before)
        self.assertEqual(report['ambiguous'][0]['assets'], ['a', 'd'])

    def test_duplicate_model_ids_reject_without_mutation(self):
        self.model['instruments'].append(instrument('a', 'DIFFERENT', '1', 'duplicate'))
        self.before = copy.deepcopy(self.model)
        updated, report = self.plan([row()])
        self.assertFalse(report['valid'])
        self.assertEqual(updated, self.before)
        self.assertIn('duplicate model asset_id', report['errors'][0]['reason'])

    def test_reviewed_callout_cannot_be_mapped_by_id_or_tag(self):
        self.model['instruments'][0]['reviewed_valve_association'] = {'valve': 'v'}
        self.before = copy.deepcopy(self.model)
        for pin in ('', 'a'):
            updated, report = self.plan([row(asset_id=pin)])
            self.assertEqual(updated, self.before)
            self.assertIn('signal requires separate review', report['ambiguous'][0]['reason'])
            self.assertEqual(report['mapped'], [])

    def test_replacement_refuses_unresolved_or_blocked_rows(self):
        for kind in ('unknown-tag', 'duplicate-tag', 'callout'):
            with self.subTest(kind=kind):
                self.model = copy.deepcopy(self.before)
                if kind == 'duplicate-tag':
                    self.model['instruments'].append(instrument('d', 'FT 1'))
                if kind == 'callout':
                    self.model['instruments'][0]['reviewed_valve_association'] = {'valve': 'v'}
                current = copy.deepcopy(self.model)
                updated, report = map_points.plan_mapping(self.model, [row('unknown' if kind == 'unknown-tag' else 'FT-1')], 'io.csv', replace_all=True)
                self.assertFalse(report['valid'])
                self.assertEqual(updated, current)
                self.assertEqual(self.model, current)

    def test_bad_addresses_reject_whole_update(self):
        for key in ('server', 'base_path', 'point'):
            bad = row('PT-2')
            bad[key] = ' '
            updated, report = self.plan([row(), bad])
            self.assertFalse(report['valid'])
            self.assertEqual(updated, self.before)

    def test_idempotency_and_added_mapping(self):
        self.model['instruments'][0].pop('data_point')
        self.before = copy.deepcopy(self.model)
        updated, report = self.plan([row()])
        self.assertEqual(report['mapping_changes'][0]['kind'], 'added')
        again, report = map_points.plan_mapping(updated, [row()], 'io.csv')
        self.assertEqual(again, updated)
        self.assertEqual(report['mapping_changes'], [])

    def test_rejected_instrument_preserved_by_replace_all(self):
        self.model['instruments'][1]['ops_review'] = {'status': 'rejected'}
        self.before = copy.deepcopy(self.model)
        updated, report = self.plan([row()], replace_all=True)
        self.assertTrue(report['valid'])
        self.assertEqual(updated['instruments'][1], self.before['instruments'][1])

    def test_cli_dry_run_and_invalid_apply_write_nothing(self):
        for args, rows, expected_exit in ((['--dry-run', '--replace-all'], [row()], 0),
                                         ([], [row(asset_id='bad')], 1),
                                         (['--dry-run'], [row(), row()], 1)):
            with self.subTest(args=args, rows=rows), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                model_path = root / 'model.json'
                raw = json.dumps(self.model, indent=2) + '\n'
                model_path.write_text(raw)
                csv_path = root / 'io.csv'
                with csv_path.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(row()))
                    writer.writeheader()
                    writer.writerows(rows)
                output = io.StringIO()
                code = 0
                with patch.object(map_points, 'ROOT', root), patch.object(sys, 'argv', ['map_points', str(model_path), str(csv_path), '--json', *args]), contextlib.redirect_stdout(output):
                    try:
                        map_points.main()
                    except SystemExit as exc:
                        code = exc.code
                self.assertEqual(code, expected_exit)
                self.assertEqual(model_path.read_text(), raw)
                self.assertFalse((root / 'out').exists())
                report = json.loads(output.getvalue())
                self.assertEqual(report['valid'], expected_exit == 0)
                self.assertEqual(set(report['mappings_before']), {'a', 'b', 'c'})
                if expected_exit == 0:
                    self.assertEqual([c['kind'] for c in report['mapping_changes']], ['changed', 'removed', 'removed'])

    def test_cli_malformed_csv_rejects_without_writes(self):
        cases = ['tag,server,point\nFT-1,OPC,new\n',
                 'tag,server,base_path,point,point\nFT-1,OPC,path,new,other\n',
                 'tag,server,base_path,point\nFT-1,OPC,path,new,extra\n']
        for csv_text in cases:
            with self.subTest(csv_text=csv_text), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                model_path = root / 'model.json'
                original = json.dumps(self.model)
                model_path.write_text(original)
                csv_path = root / 'bad.csv'
                csv_path.write_text(csv_text)
                with patch.object(map_points, 'ROOT', root), patch.object(sys, 'argv', ['map_points', str(model_path), str(csv_path)]), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        map_points.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(model_path.read_text(), original)
                self.assertFalse((root / 'out').exists())

    def test_cli_apply_then_repeat_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_path = root / 'model.json'
            model_path.write_text(json.dumps(self.model, indent=2) + '\n')
            csv_path = root / 'io.csv'
            csv_path.write_text('tag,server,base_path,point\nFT-1,OPC,path,new\n')
            def run():
                output = io.StringIO()
                with patch.object(map_points, 'ROOT', root), patch.object(sys, 'argv', ['map_points', str(model_path), str(csv_path), '--json']), contextlib.redirect_stdout(output):
                    map_points.main()
                return json.loads(output.getvalue())
            self.assertTrue(run()['valid'])
            first = model_path.read_bytes()
            self.assertEqual(run()['mapping_changes'], [])
            self.assertEqual(model_path.read_bytes(), first)
            reports = list((root / 'out' / 'mapping').glob('*.json'))
            self.assertEqual(len(reports), 1)
            self.assertEqual(json.loads(reports[0].read_text())['mapping_changes'], [])

    def test_cli_missing_files_are_refused_in_plain_words(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_path = root / 'model.json'
            model_path.write_text(json.dumps(self.model))
            csv_path = root / 'io.csv'
            csv_path.write_text('tag,server,base_path,point\nFT-1,OPC,path,new\n')
            for args, missing in (([root / 'nope.json', csv_path], 'nope.json'), ([model_path, root / 'nope.csv'], 'nope.csv')):
                with self.subTest(missing=missing):
                    err = io.StringIO()
                    with patch.object(map_points, 'ROOT', root), patch.object(sys, 'argv', ['map_points', *map(str, args)]), contextlib.redirect_stderr(err):
                        with self.assertRaises(SystemExit) as raised:
                            map_points.main()
                    self.assertEqual(raised.exception.code, 2)
                    self.assertIn(missing, err.getvalue())
                    self.assertFalse((root / 'out').exists())

    def test_cli_report_redirected_to_a_file_is_lf_with_one_final_newline(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_path = root / 'model.json'
            model_path.write_text(json.dumps(self.model))
            csv_path = root / 'io.csv'
            csv_path.write_text('tag,server,base_path,point\nFT-1,OPC,path,new\n')
            with (root / 'plan.md').open('wb') as out:
                p = subprocess.run([sys.executable, str(Path(map_points.__file__)), str(model_path), str(csv_path),
                                    '--dry-run'], stdout=out, stderr=subprocess.PIPE, timeout=120)
            self.assertEqual(p.returncode, 0, p.stderr)
            text = (root / 'plan.md').read_bytes()
            self.assertNotIn(b'\r\n', text)
            self.assertTrue(text.endswith(b'}\n') and not text.endswith(b'\n\n'), text[-20:])

    def source_csv(self):
        return (b'tag,server,base_path,point,description\r\n\r\n'
                b'FT-1,OPC,ns=1;s=plant,F1,"first line\r\nsecond line"\r\n\r\n'
                b'PT-2,OPC,ns=1;s=plant,P2,plain\r\n')

    def source_cli(self, root, model_path, csv_path, *args):
        output = io.StringIO()
        code = 0
        with patch.object(map_points, 'ROOT', root), patch.object(sys, 'argv',
                ['map_points', str(model_path), str(csv_path), '--json', *args]), contextlib.redirect_stdout(output):
            try:
                map_points.main()
            except SystemExit as exc:
                code = exc.code
        return code, json.loads(output.getvalue())

    def test_cli_retains_exact_raw_hash_and_physical_spans_for_newline_variants(self):
        for newline in (b'\r\n', b'\n', b'\r'):
            for bom in (b'', b'\xef\xbb\xbf'):
                with self.subTest(newline=newline, bom=bom), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    model_path, csv_path = root/'model.json', root/'io.csv'
                    model_path.write_text(json.dumps(self.model), encoding='utf-8')
                    original = model_path.read_bytes()
                    raw = bom + self.source_csv().replace(b'\r\n', newline)
                    csv_path.write_bytes(raw)
                    code, report = self.source_cli(root, model_path, csv_path, '--dry-run')
                    self.assertEqual(code, 0)
                    digest = hashlib.sha256(raw).hexdigest()
                    self.assertEqual(report['io_list_evidence'], {'file': 'io.csv', 'bytes': len(raw), 'sha256': digest})
                    self.assertEqual([(r['row'], r['row_end']) for r in report['mapped']], [(3, 4), (6, 6)])
                    for key, span in [('a', [3, 4]), ('b', [6, 6])]:
                        self.assertEqual(report['mappings_after'][key]['source_lines'], span)
                        self.assertEqual(report['mappings_after'][key]['source_sha256'], digest)
                    self.assertEqual(report['mappings_after']['a']['source'], 'io.csv lines 3-4')
                    self.assertEqual(report['mappings_after']['b']['source'], 'io.csv line 6')
                    self.assertEqual(model_path.read_bytes(), original)
                    self.assertEqual(csv_path.read_bytes(), raw)
                    self.assertFalse((root/'out').exists())
                    self.assertNotIn(str(root), json.dumps(report['io_list_evidence']))

    def test_source_revision_is_visible_without_remapping_or_relabelling_omitted_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_path, csv_path = root/'model.json', root/'io.csv'
            self.model['instruments'][2]['data_point'].update(source='older.csv line 9', source_sha256='a'*64, source_lines=[9, 9])
            model_path.write_text(json.dumps(self.model, indent=2)+'\n', encoding='utf-8')
            raw = self.source_csv()
            csv_path.write_bytes(raw)
            self.assertEqual(self.source_cli(root, model_path, csv_path)[0], 0)
            first = model_path.read_bytes()
            self.assertEqual(self.source_cli(root, model_path, csv_path)[1]['mapping_changes'], [])
            self.assertEqual(model_path.read_bytes(), first)
            csv_path.write_bytes(raw.replace(b'plain', b'revised source prose'))
            _, plan = self.source_cli(root, model_path, csv_path, '--dry-run')
            self.assertEqual(model_path.read_bytes(), first)
            self.assertEqual([c['asset'] for c in plan['mapping_changes']], ['a', 'b'])
            for change in plan['mapping_changes']:
                self.assertNotEqual(change['before']['source_sha256'], change['after']['source_sha256'])
                for field in ('server', 'base_path', 'point'):
                    self.assertEqual(change['before'][field], change['after'][field])
            csv_path.write_bytes(b'tag,server,base_path,point\nFT-1,OPC,ns=1;s=plant,F1\n')
            self.assertEqual(self.source_cli(root, model_path, csv_path)[0], 0)
            final = json.loads(model_path.read_text(encoding='utf-8'))
            previous = json.loads(first)
            self.assertEqual(final['instruments'][1:], previous['instruments'][1:])
            self.assertEqual(final['instruments'][0]['data_point']['source_lines'], [2, 2])

    def test_duplicate_refusal_cites_both_actual_spans_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_path, csv_path = root/'model.json', root/'io.csv'
            model_path.write_text(json.dumps(self.model), encoding='utf-8')
            original = model_path.read_bytes()
            csv_path.write_bytes(self.source_csv().replace(b'PT-2', b'FT-1'))
            code, report = self.source_cli(root, model_path, csv_path)
            self.assertEqual(code, 1)
            self.assertEqual((report['errors'][0]['row'], report['errors'][0]['row_end']), (6, 6))
            self.assertIn('first assigned on lines 3-4', report['errors'][0]['reason'])
            self.assertEqual(report['mappings_before'], report['mappings_after'])
            self.assertEqual(model_path.read_bytes(), original)
            self.assertFalse((root/'out').exists())

    def test_csv_columns_cannot_supply_hashes_or_locations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_path, csv_path = root/'model.json', root/'io.csv'
            model_path.write_text(json.dumps(self.model), encoding='utf-8')
            raw = b'tag,server,base_path,point,source_sha256,source_lines,row,row_end\nFT-1,OPC,path,P,FORGED,"[999,999]",999,999\n'
            csv_path.write_bytes(raw)
            code, report = self.source_cli(root, model_path, csv_path, '--dry-run')
            self.assertEqual(code, 0)
            mapping = report['mappings_after']['a']
            self.assertEqual(mapping['source_lines'], [2, 2])
            self.assertEqual(mapping['source_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual((report['mapped'][0]['row'], report['mapped'][0]['row_end']), (2, 2))

    def test_unresolved_worklists_use_actual_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_path, csv_path = root/'model.json', root/'io.csv'
            self.model['instruments'].append(instrument('duplicate', 'FT 1'))
            model_path.write_text(json.dumps(self.model), encoding='utf-8')
            csv_path.write_bytes(self.source_csv().replace(b'PT-2', b'UNKNOWN'))
            code, report = self.source_cli(root, model_path, csv_path, '--dry-run')
            self.assertEqual(code, 0)
            self.assertEqual((report['ambiguous'][0]['row'], report['ambiguous'][0]['row_end']), (3, 4))
            self.assertEqual((report['not_on_drawing'][0]['row'], report['not_on_drawing'][0]['row_end']), (6, 6))
            self.assertEqual(report['mappings_before'], report['mappings_after'])

    def test_source_snapshot_is_read_once_before_decoding(self):
        raw = b'\xef\xbb\xbf' + self.source_csv()
        with patch.object(Path, 'read_bytes', return_value=raw) as read:
            _, records, spans, evidence = map_points.read_io_list(Path('io.csv'))
        read.assert_called_once()
        self.assertEqual([r['tag'] for r in records], ['FT-1', 'PT-2'])
        self.assertEqual(spans, [(3, 4), (6, 6)])
        self.assertEqual(evidence['sha256'], hashlib.sha256(raw).hexdigest())

    def test_direct_dict_planner_does_not_invent_file_provenance(self):
        updated, report = self.plan([row()])
        mapping = updated['instruments'][0]['data_point']
        self.assertNotIn('source_sha256', mapping)
        self.assertNotIn('source_lines', mapping)
        self.assertIn('no file locator', mapping['source'])
        self.assertIn('logical rows', report['row_locator_kind'])


if __name__ == '__main__':
    unittest.main()
