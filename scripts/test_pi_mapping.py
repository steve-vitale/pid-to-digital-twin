"""Synthetic offline PI mapping/export controls. No licensed PI runtime needed."""
import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import generate
from pi_mapping import FIELDS, mapping_config, pi_csv_text, plan_mapping, reconciliation
from test_generate_validation import twin_fixture, snapshot

ROOT = Path(__file__).resolve().parents[1]


def row(**updates):
    result = dict(asset_id='I-1', archive='SYNTHETIC-ARCHIVE', point='TEST.PV', value_type='Double',
                  uom='bar', reviewed_by='Synthetic reviewer', review_note='Synthetic contract test only')
    result.update(updates)
    return result


class PIMappingTests(unittest.TestCase):
    def test_candidate_header_migration_and_row_equivalence(self):
        models = [twin_fixture(), plan_mapping(twin_fixture(), [row()])[0]]
        callout = twin_fixture()
        callout['instruments'][0]['reviewed_valve_association'] = 'V-1'
        models.append(callout)
        for model in models:
            with self.subTest(mapped='pi_point' in model['instruments'][0]):
                with tempfile.TemporaryDirectory() as tmp:
                    generate.export_twin(model, tmp)
                    folder = Path(tmp) / 'pi'
                    def read(name):
                        with (folder / name).open(encoding='utf-8-sig', newline='') as stream:
                            return list(csv.reader(stream))
                    legacy = read('pi_builder_af.csv')
                    candidate = read('pi_builder_UNVALIDATED_candidate_v1.csv')
                    self.assertEqual(legacy[1:], candidate[1:])
                    self.assertEqual(candidate[0], ['AttributeType' if x == 'AttributeValueType' else x for x in legacy[0]])
                    report = json.loads((folder / 'reconciliation.json').read_text())
                    self.assertIn('not native-import-ready', report['candidate_schema']['status'])
                    self.assertEqual(report['attributes'][0]['config_string'], candidate[-1][-1])
                    if model is callout:
                        self.assertEqual(candidate[-1][-2:], ['', ''])

    def test_actual_reviewed_callout_remains_blocked(self):
        model = json.loads((ROOT / 'out/twin/r2-tiles-trace/codex/plant_model.json').read_text())
        target = next(x for x in model['instruments'] if x['id'] == 'S0-IN019')
        self.assertEqual(target['reviewed_valve_association'], 'S0-VL013')
        result, report = plan_mapping(model, [row(asset_id='S0-IN019')])
        self.assertFalse(report['valid'])
        self.assertEqual(result, model)
        attribute = next(r for r in generate.twin_pi_rows(model) if 'S0-IN019 |' in r[4])
        self.assertEqual(attribute[-2:], ['', ''])

    def test_unsupported_mapping_locations_fail_before_writes(self):
        mapped, _ = plan_mapping(twin_fixture(), [row()])
        mapping = mapped['instruments'][0]['pi_point']
        model = twin_fixture()
        model['units'][0]['pi_point'] = mapping
        self.assertFalse(plan_mapping(model, [])[1]['valid'])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'export'
            with self.assertRaises(generate.ModelValidationError):
                generate.export_twin(model, out)
            self.assertFalse(out.exists())
            seed = json.loads((ROOT / 'data/te_process_model.json').read_text())
            seed['instruments'][0]['pi_point'] = mapping
            with self.assertRaises(generate.ModelValidationError):
                generate.export_seed(seed, out)
            self.assertFalse(out.exists())

    def test_cli_duplicate_json_and_nonfinite_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / 'model.json'
            original = json.dumps(twin_fixture())
            for bad in (original.replace('"id": "I-1"', '"id": "I-1", "id": "I-2"'),
                        original.replace('"confidence": null', '"confidence": NaN')):
                model.write_text(bad)
                before = model.read_bytes()
                result = self.run_cli(root, self.csv([row()]))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(model.read_bytes(), before)

    def test_partial_and_full_diff_independent_of_opc(self):
        model = twin_fixture()
        model['instruments'].append(dict(copy.deepcopy(model['instruments'][0]), id='I-2'))
        model['instruments'][0]['data_point'] = {'server': 'OPC', 'point': 'unrelated'}
        mapped, report = plan_mapping(model, [row(), row(asset_id='I-2')])
        self.assertTrue(report['valid'])
        self.assertNotIn('pi_point', model['instruments'][0])
        self.assertEqual(len(report['mapping_changes']), 2)
        partial, report = plan_mapping(mapped, [row(point='NEW.PV')])
        self.assertEqual(len(report['mapping_changes']), 1)
        self.assertIn('I-2', report['mappings_after'])
        replaced, report = plan_mapping(partial, [], replace_all=True)
        self.assertEqual(report['mappings_after'], {})
        self.assertEqual(len(report['mapping_changes']), 2)
        self.assertEqual(replaced['instruments'][0]['data_point'], model['instruments'][0]['data_point'])

    def test_fail_closed_rows(self):
        invalids = [row(asset_id='MISSING'), row(point=''), row(value_type='unknown'), row(value_type='Float64'),
                    row(point='tag;ReadOnly=False'), row(archive='%Server%'), row(point='=1+1'),
                    row(point='a\\b'), row(point='a|b'), row(archive='[Link]'), row(point='*.PV'), row(point='a\nb'), row(point=' PLACE.PV'),
                    row(reviewed_by=''), row(review_note='unknown'), row(uom='TBD'), row(extra='ignored?')]
        for bad in invalids:
            with self.subTest(bad=bad):
                model = twin_fixture()
                result, report = plan_mapping(model, [row(), bad], replace_all=True)
                self.assertFalse(report['valid'])
                self.assertEqual(result, model)
                self.assertEqual(report['mapping_changes'], [])

    def test_duplicate_rows_and_model_ids(self):
        model = twin_fixture()
        self.assertFalse(plan_mapping(model, [row(), row()])[1]['valid'])
        model['instruments'].append(copy.deepcopy(model['instruments'][0]))
        self.assertFalse(plan_mapping(model, [row()])[1]['valid'])

    def test_callouts_and_rejected_blocked(self):
        for field in ({'reviewed_valve_association': 'V-1'}, {'ops_review': {'status': 'rejected'}}):
            model = twin_fixture()
            model['instruments'][0].update(field)
            self.assertFalse(plan_mapping(model, [row()])[1]['valid'])
            if 'reviewed_valve_association' in field:
                attrs = [r for r in generate.twin_pi_rows(model) if r[3] == 'Attribute']
                self.assertEqual(attrs[0][-2:], ['', ''])

    def test_export_mapping_and_placeholders(self):
        model = twin_fixture()
        baseline = generate.twin_pi_rows(model)
        self.assertIn('PLACEHOLDER', baseline[-1][-1])
        model['instruments'][0]['data_point'] = {'server': 'OPC', 'point': 'TAG'}
        self.assertEqual(generate.twin_pi_rows(model), baseline)
        mapped, _ = plan_mapping(model, [row(value_type='Single', uom='')])
        attrs = generate.twin_pi_rows(mapped)
        self.assertEqual(attrs[-1][-4:], ['Single', '', 'PI Point', '\\\\SYNTHETIC-ARCHIVE\\TEST.PV'])
        self.assertEqual(mapping_config(mapped['instruments'][0]['pi_point']), attrs[-1][-1])

    def test_invalid_manual_mapping_preserves_export_bundle(self):
        model = twin_fixture()
        mapped, _ = plan_mapping(model, [row()])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            generate.export_twin(mapped, output)
            before = snapshot(output)
            for changes in ({'point': 'X;ReadOnly=False'}, {'uom': None}, {'extra': 'x'}):
                bad = copy.deepcopy(mapped)
                bad['instruments'][0]['pi_point'].update(changes)
                with self.assertRaises(generate.ModelValidationError):
                    generate.export_twin(bad, output)
                self.assertEqual(before, snapshot(output))
            mapped['instruments'][0]['reviewed_valve_association'] = 'V-1'
            with self.assertRaises(generate.ModelValidationError):
                generate.export_twin(mapped, output)
            self.assertEqual(before, snapshot(output))

    def test_csv_formula_and_quotes(self):
        text = pi_csv_text(['x'], [['=HYPERLINK("bad")'], [' \t@SUM(1)'], ['ordinary, "text"'], ['\n=1']])
        parsed = list(csv.reader(io.StringIO(text.lstrip('\ufeff'))))
        self.assertTrue(parsed[1][0].startswith("'="))
        self.assertTrue(parsed[2][0].startswith("'"))
        self.assertEqual(parsed[3][0], 'ordinary, "text"')
        self.assertTrue(parsed[4][0].startswith("'"))

    def test_reconciliation_is_explicitly_unverified(self):
        mapped, _ = plan_mapping(twin_fixture(), [row()])
        report = reconciliation(mapped, generate.twin_pi_rows(mapped))
        self.assertIn('NOT tested', report['status'])
        self.assertEqual(report['expected_attribute_rows'], 1)
        self.assertEqual(report['unmapped_asset_ids'], [])
        self.assertIn('reviewed_by', report['mapped']['I-1'])

    def run_cli(self, root, content, *flags):
        model = root / 'model.json'
        mapping = root / 'mapping.csv'
        mapping.write_text(content, encoding='utf-8')
        return subprocess.run([sys.executable, "-S", str(ROOT / 'scripts/map_pi_points.py'), str(model), str(mapping), *flags],
                              text=True, capture_output=True)

    def csv(self, rows):
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue()

    def test_cli_dry_run_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / 'model.json'
            model.write_text(json.dumps(twin_fixture()), encoding='utf-8')
            original = model.read_bytes()
            dry = self.run_cli(root, self.csv([row()]), '--dry-run')
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertEqual(model.read_bytes(), original)
            self.assertEqual({p.name for p in root.iterdir()}, {'model.json', 'mapping.csv'})
            self.assertEqual(len(json.loads(dry.stdout)['mapping_changes']), 1)
            applied = self.run_cli(root, self.csv([row()]))
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(json.loads(applied.stdout)['mappings_after'], json.loads(dry.stdout)['mappings_after'])
            self.assertIn('pi_point', json.loads(model.read_text())['instruments'][0])

    def test_cli_malformed_no_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / 'model.json'
            model.write_text(json.dumps(twin_fixture()), encoding='utf-8')
            before = model.read_bytes()
            for content in ('asset_id,asset_id\nI-1,I-1\n', self.csv([row()]) + 'I-1,a,b,c,d,e,f,extra\n',
                            self.csv([row()]).replace('Double', 'Unknown'), ','.join(FIELDS) + '\nI-1\n'):
                result = self.run_cli(root, content)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(model.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
