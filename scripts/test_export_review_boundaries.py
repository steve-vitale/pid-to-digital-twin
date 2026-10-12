"""Offline regression controls for SVG text, review CSV and mapped-callout boundaries."""
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import apply_review
import generate
import pi_mapping
from test_generate_validation import twin_fixture

ROOT = Path(__file__).resolve().parents[1]
NS = '{http://www.w3.org/2000/svg}'


class ExportReviewBoundaryTests(unittest.TestCase):
    def apply(self, model, rows):
        return apply_review.apply(model, rows, 'Offline reviewer', '2026-10-11', apply_review.index(model))

    def test_twin_svg_attribute_values_are_preserved_as_text(self):
        model = twin_fixture()
        text = 'quoted " value \' & <engineering text>'
        unit, instrument = model['units'][0], model['instruments'][0]
        unit['id'] = text
        instrument.update(id='instrument ' + text, parent=text, pair=text, tag=text,
                          ops_review={'status': text})
        model['line_items'][0]['unit'] = text
        instrument['provenance'][0]['symbol'] = text
        model['streams'] = [dict(id='stream ' + text, sheet='0', kind='pipe',
                                 **{'from': text, 'to': instrument['id']},
                                 from_symbol='s1', to_symbol=text)]
        with tempfile.TemporaryDirectory() as tmp:
            generate.export_twin(model, tmp)
            root = ET.fromstring((Path(tmp) / 'svg/sheet_0.svg').read_text())
        group = next(n for n in root.iter(NS + 'g') if n.get('data-asset') == instrument['id'])
        self.assertEqual(group.attrib, {
            'id': instrument['id'] + '-s0-' + text, 'data-asset': instrument['id'],
            'data-tag': text, 'data-class': 'instrumentation', 'data-confidence': 'None',
            'data-status': text, 'data-symbol': text, 'data-pair': text, 'data-parent': text})
        link = next(n for n in root.iter(NS + 'line') if n.get('class') == 'lk')
        self.assertEqual(link.get('data-stream'), 'stream ' + text)
        self.assertEqual((link.get('data-from'), link.get('data-to')), (text, instrument['id']))
        self.assertEqual(len(list(root.iter(NS + 'g'))), 3)

    def test_reported_symbol_attribute_boundary(self):
        model = twin_fixture()
        # An inert attribute-shaped string checks the same serialization boundary.
        symbol = 'source" unexpected="literal'
        model['instruments'][0]['provenance'][0]['symbol'] = symbol
        svg = generate.twin_svgs(model)['0']
        root = ET.fromstring(svg)
        group = next(n for n in root.iter(NS + 'g') if n.get('data-asset') == 'I-1')
        self.assertEqual(group.get('id'), 'I-1-s0-' + symbol)
        self.assertEqual(group.get('data-symbol'), symbol)
        self.assertNotIn('unexpected', group.attrib)

    def test_seed_svg_text_and_attributes_remain_literal(self):
        model = json.loads((ROOT / 'data/te_process_model.json').read_text())
        text = 'quoted " value \' & <engineering text>'
        unit = model['units'][0]
        old_id = unit['id']
        unit.update(id=text, name=text)
        for group in ('instruments', 'final_elements'):
            for item in model[group]:
                if item['unit'] == old_id:
                    item['unit'] = text
        for stream in model['streams']:
            for end in ('from', 'to'):
                if stream[end] == old_id:
                    stream[end] = text
        instrument = model['instruments'][0]
        instrument.update(tag='FI-' + text, uom=text, description=text)
        with tempfile.TemporaryDirectory() as tmp:
            generate.export_seed(model, tmp)
            root = ET.fromstring((Path(tmp) / 'svg/overview.svg').read_text())
        group = next(n for n in root.iter(NS + 'g') if n.get('data-tag') == instrument['tag'])
        self.assertEqual(group.get('data-uom'), text)
        self.assertEqual(set(group.attrib), {'id', 'data-tag', 'data-unit', 'data-uom', 'transform'})
        self.assertIn(text, ''.join(root.itertext()))

    def test_every_review_csv_cell_uses_text_encoding(self):
        values = ['=1+1', '+engineering', '-engineering', '@engineering', ' \t=1',
                  'line\nbreak', '\rtext', "'literal", "'=literal", 'ordinary', 3, None]
        for header in (generate.REVIEW_COLS, generate.TWIN_REVIEW_COLS):
            for value in values:
                with self.subTest(columns=len(header), value=value):
                    rows = list(csv.reader(io.StringIO(generate._csv_text(header, [[value] * len(header)]).lstrip('\ufeff'))))
                    self.assertEqual(rows[0], header)
                    expected = generate.review_csv_cell(value)
                    self.assertEqual(rows[1], [str(expected) if expected is not None else ''] * len(header))
                    if isinstance(value, str) and value != 'ordinary':
                        self.assertEqual(expected, "'" + value)

    def test_notes_export_round_trip_preserves_model_text_and_history(self):
        for kind in ('twin', 'seed'):
            for text in ('=1+1', '+engineering', '-engineering', '@engineering',
                         "'literal", "'=literal", 'line\nbreak', 'ordinary'):
                with self.subTest(kind=kind, text=text):
                    model = twin_fixture() if kind == 'twin' else json.loads((ROOT / 'data/te_process_model.json').read_text())
                    item = model['instruments'][0]
                    key = item.get('id') or item['tag']
                    self.assertTrue(self.apply(model, [{'item_id': key, 'OPS_notes': text}])['applied'])
                    before = copy.deepcopy(model)
                    with tempfile.TemporaryDirectory() as tmp:
                        exporter = generate.export_twin if kind == 'twin' else generate.export_seed
                        filename = 'review_queue.csv' if kind == 'twin' else 'ops_review_sheet.csv'
                        exporter(model, tmp)
                        with (Path(tmp) / filename).open(encoding='utf-8-sig', newline='') as stream:
                            rows = list(csv.DictReader(stream))
                    row = next(r for r in rows if r['item_id'] == key)
                    self.assertEqual(row['OPS_notes'], generate.review_csv_cell(text))
                    log = self.apply(model, rows)
                    self.assertFalse(log['applied'])
                    self.assertFalse(log['refused'])
                    self.assertEqual(model, before)
                    self.assertEqual(item['ops_review']['notes'], text)

    def test_new_literal_apostrophe_note_is_not_stripped(self):
        model = twin_fixture()
        self.apply(model, [{'item_id': 'I-1', 'OPS_notes': "'=literal"}])
        self.assertEqual(model['instruments'][0]['ops_review']['notes'], "'=literal")

    def test_encoded_identifiers_resolve_and_ambiguities_refuse(self):
        model = twin_fixture()
        model['instruments'][0]['id'] = '=instrument'
        log = self.apply(model, [{'item_id': "'=instrument", 'OPS_notes': 'Review note'}])
        self.assertTrue(log['applied'])
        collision = copy.deepcopy(model['instruments'][0])
        collision['id'] = "'=instrument"
        model['instruments'].append(collision)
        before = copy.deepcopy(model)
        log = self.apply(model, [{'item_id': "'=instrument", 'OPS_notes': 'Do not guess'}])
        self.assertFalse(log['applied'])
        self.assertIn('ambiguous', log['refused'][0]['reason'])
        self.assertEqual(model, before)

    def test_mapped_callout_review_refuses_without_mutation(self):
        for mapping in ('data_point', 'pi_point', 'both', 'empty_pi_point'):
            with self.subTest(mapping=mapping):
                model = twin_fixture()
                model['instruments'][0]['parent'] = 'V-1'
                if mapping in ('pi_point', 'both'):
                    row = dict(asset_id='I-1', archive='TEST-ARCHIVE', point='TEST.PV',
                               value_type='Double', uom='bar', reviewed_by='Synthetic reviewer',
                               review_note='Synthetic fixture')
                    model, report = pi_mapping.plan_mapping(model, [row])
                    self.assertTrue(report['valid'])
                if mapping in ('data_point', 'both'):
                    model['instruments'][0]['data_point'] = {'point': 'existing'}
                if mapping == 'empty_pi_point':
                    model['instruments'][0]['pi_point'] = {}
                before = copy.deepcopy(model)
                log = self.apply(model, [{'item_id': 'I-1', 'OPS_confirm_or_correct': 'correct',
                                         'OPS_correct_value': 'parent=V-1;variable=unknown',
                                         'OPS_scope': 'valve_association', 'OPS_notes': 'Review'}])
                self.assertFalse(log['applied'])
                self.assertIn('mapping requires separate review', log['refused'][0]['reason'])
                self.assertEqual(model, before)
                if mapping == 'pi_point':
                    self.assertTrue(pi_mapping.plan_mapping(model, [])[1]['valid'])
                    with tempfile.TemporaryDirectory() as tmp:
                        generate.export_twin(model, tmp)

    def test_unmapped_callout_review_still_applies(self):
        model = twin_fixture()
        model['instruments'][0]['parent'] = 'V-1'
        log = self.apply(model, [{'item_id': 'I-1', 'OPS_confirm_or_correct': 'correct',
                                 'OPS_correct_value': 'parent=V-1;variable=unknown',
                                 'OPS_scope': 'valve_association'}])
        self.assertTrue(log['applied'])
        self.assertEqual(model['instruments'][0]['reviewed_valve_association'], 'V-1')


if __name__ == '__main__':
    unittest.main()
